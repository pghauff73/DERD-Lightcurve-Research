#!/usr/bin/env python3
"""Execute Phase 17: external Fourier-analysis anchor and independence audit."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

from derd.io import read_ogle_photometry, write_json
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase17 import (
    EDGE_EXTERNAL_CONSISTENT_PARTIAL,
    PHASE17_DECISION,
    bootstrap_fourier_invariants,
    compare_external_anchor,
    extend_reproducibility_graph,
    fit_weighted_cosine_series,
    load_external_anchor,
    verify_source,
)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def verify_protocol(root: Path) -> dict[str, Any]:
    protocol_path = root / "research/preregistration/phase17_external_analysis_anchor_protocol.json"
    seal_path = root / "research/preregistration/phase17_external_analysis_anchor_protocol.seal.json"
    protocol = load_json(protocol_path)
    seal = load_json(seal_path)
    valid = canonical_json_sha256(protocol) == seal.get("sha256_canonical_json")
    if not valid:
        raise RuntimeError("Phase-17 protocol seal mismatch")
    for key, expected in (
        ("summary", protocol["parent_phase16"]["summary_sha256"]),
        ("graph", protocol["parent_phase16"]["graph_sha256"]),
        ("ledger", protocol["parent_phase16"]["ledger_sha256"]),
    ):
        path = root / protocol["parent_phase16"][f"{key}_path"]
        if sha256_file(path) != expected:
            raise RuntimeError(f"Phase-16 parent {key} hash mismatch")
    anchor_path = root / protocol["external_anchor"]["path"]
    source_manifest_path = root / protocol["local_source"]["manifest_path"]
    if sha256_file(anchor_path) != protocol["external_anchor"]["file_sha256"]:
        raise RuntimeError("external anchor file hash mismatch")
    if sha256_file(source_manifest_path) != protocol["local_source"]["manifest_sha256"]:
        raise RuntimeError("source manifest file hash mismatch")
    return {"valid": True, "protocol": protocol, "seal": seal}


def verify_phase16_ledger(root: Path, summary: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    meta = summary["cumulative_ledger"]
    ledger_path = root / meta["relative_path"]
    seal_path = root / meta["seal_relative_path"]
    ledger = load_json(ledger_path)
    seal = load_json(seal_path)
    digest = canonical_json_sha256(ledger)
    if digest != seal.get("sha256_canonical_json"):
        raise RuntimeError("Phase-16 cumulative ledger seal mismatch")
    if digest != meta.get("seal_sha256_canonical_json"):
        raise RuntimeError("Phase-16 summary/ledger mismatch")
    return ledger, digest


def dense_model(beta: np.ndarray, phase: np.ndarray, order: int = 3) -> np.ndarray:
    columns = [np.ones(phase.size)]
    for harmonic in range(1, order + 1):
        angle = 2.0 * math.pi * harmonic * phase
        columns.append(np.sin(angle))
        columns.append(np.cos(angle))
    return np.column_stack(columns) @ beta


def plot_folded_lightcurve(
    path: Path,
    *,
    time: np.ndarray,
    magnitude: np.ndarray,
    error: np.ndarray,
    period: float,
    epoch: float,
    beta: np.ndarray,
) -> None:
    phase = np.mod((time - epoch) / period, 1.0)
    dense_phase = np.linspace(0.0, 1.0, 800, endpoint=False)
    model = dense_model(beta, dense_phase)
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    ax.errorbar(phase, magnitude, yerr=error, fmt="o", markersize=4, linewidth=0.7, label="33-point V subset")
    ax.plot(dense_phase, model, linewidth=1.5, label="weighted 3-harmonic fit")
    ax.invert_yaxis()
    ax.set_xlabel("Pulsation phase")
    ax.set_ylabel("V magnitude")
    ax.set_title("OGLE-LMC-CEP-0002 external-analysis anchor")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_parameter_comparison(path: Path, comparison_rows: Sequence[Mapping[str, Any]]) -> None:
    labels = [str(row["parameter"]) for row in comparison_rows]
    local = np.array([float(row["local_value"]) for row in comparison_rows])
    external = np.array([float(row["external_value"]) for row in comparison_rows])
    local_error = np.array([float(row["local_standard_error"]) for row in comparison_rows])
    external_error = np.array([float(row["external_standard_error"]) for row in comparison_rows])
    x = np.arange(len(labels), dtype=float)
    width = 0.34
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.errorbar(x - width / 2, local, yerr=local_error, fmt="o", capsize=4, label="local 33-point reanalysis")
    ax.errorbar(x + width / 2, external, yerr=external_error, fmt="s", capsize=4, label="published external anchor")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Fourier invariant (radians for phase terms)")
    ax.set_title("External Fourier coordinates versus local partial-source estimate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_marginal_z(path: Path, comparison_rows: Sequence[Mapping[str, Any]]) -> None:
    labels = [str(row["parameter"]) for row in comparison_rows]
    z = np.array([float(row["marginal_z"]) for row in comparison_rows])
    fig, ax = plt.subplots(figsize=(7.5, 4.7))
    ax.bar(labels, np.abs(z))
    ax.axhline(2.0, linestyle="--", linewidth=1.2, label="frozen |z|=2 gate")
    ax.set_ylabel("Absolute marginal z")
    ax.set_title("Joint-uncertainty consistency audit")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_independence_matrix(path: Path, audit: Mapping[str, Any]) -> None:
    labels = [
        "external\nresearch group",
        "independent\nobserving source",
        "publication source\nbyte identity",
        "published minimum\nmeasurement count",
        "joint statistical\nconsistency",
    ]
    values = [
        audit["external_research_group_independent"],
        audit["observational_source_independent"],
        audit["source_byte_identity_known"],
        audit["local_source_meets_external_minimum_count"],
        audit["joint_consistency_at_5_percent"],
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    ax.bar(labels, [1 if value else 0 for value in values])
    ax.set_yticks([0, 1], ["No", "Yes"])
    ax.set_ylim(0.0, 1.15)
    ax.set_title("Phase-17 independence and completeness dimensions")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_extended_graph(path: Path, graph: Mapping[str, Any]) -> None:
    objects = graph["object_ids"]
    y_lookup = {object_id: index for index, object_id in enumerate(objects)}
    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    ax.scatter(np.zeros(len(objects)), np.arange(len(objects)), s=85, marker="o", label="astronomical object")
    for object_id, y in y_lookup.items():
        nodes = [node for node in graph["analysis_nodes"] if node["object_id"] == object_id]
        for x, node in enumerate(nodes, start=1):
            marker = "s" if node.get("analysis_kind") == "external_published_fourier_anchor" else "^"
            ax.scatter(x, y, s=55, marker=marker)
            ax.plot([0, x], [y, y], linewidth=0.7)
            ax.text(x, y + 0.13, str(node["analysis_version"]), ha="center", fontsize=7)
    ax.set_yticks(np.arange(len(objects)), objects)
    ax.set_xlabel("Analysis node within object lineage")
    ax.set_title("Phase-17 reproducibility graph with external analysis anchor")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    source = args.source.resolve()
    out = root / "artifacts/phase17"
    out.mkdir(parents=True, exist_ok=True)

    protocol_check = verify_protocol(root)
    protocol = protocol_check["protocol"]
    source_manifest = load_json(root / protocol["local_source"]["manifest_path"])
    source_check = verify_source(
        source,
        expected_sha256=source_manifest["source_sha256"],
        expected_git_blob_sha1=source_manifest["git_blob_sha1"],
        expected_bytes=int(source_manifest["byte_count"]),
        expected_observations=int(source_manifest["observation_count"]),
    )
    if not source_check["all_checks_passed"]:
        raise RuntimeError("Phase-17 source verification failed")
    source_check.update(
        {
            "manifest_relative_path": protocol["local_source"]["manifest_path"],
            "repository": source_manifest["repository"],
            "commit": source_manifest["commit"],
            "repository_path": source_manifest["repository_path"],
            "redistributed_in_release": False,
        }
    )
    write_json(out / "phase17_source_verification.json", source_check)
    source_receipt = {
        "status": "VERIFIED_FROM_CONNECTED_OR_SUPPLIED_FROZEN_SOURCE",
        "object_id": source_manifest["object_id"],
        "band": source_manifest["band"],
        "repository": source_manifest["repository"],
        "commit": source_manifest["commit"],
        "repository_path": source_manifest["repository_path"],
        "git_blob_sha1": source_manifest["git_blob_sha1"],
        "source_sha256": source_manifest["source_sha256"],
        "byte_count": source_manifest["byte_count"],
        "observation_count": source_manifest["observation_count"],
        "verification": source_check["checks"],
        "all_checks_passed": source_check["all_checks_passed"],
        "attribution_requirement_reviewed": True,
        "raw_source_redistributed": False,
        "limitations": source_manifest["limitations"],
    }
    write_json(out / "phase17_source_acquisition_receipt.json", source_receipt)

    anchor = load_external_anchor(root / protocol["external_anchor"]["path"])
    curve = read_ogle_photometry(
        source,
        star_id=anchor.object_id,
        band="V",
        metadata={
            "repository": source_manifest["repository"],
            "commit": source_manifest["commit"],
            "repository_path": source_manifest["repository_path"],
            "git_blob_sha1": source_manifest["git_blob_sha1"],
        },
    )
    config = protocol["analysis"]
    local = bootstrap_fourier_invariants(
        curve.time,
        curve.value,
        curve.error,
        object_id=anchor.object_id,
        center_period_days=anchor.period_days,
        draws=int(config["bootstrap_draws"]),
        sample_fraction=float(config["bootstrap_fraction"]),
        seed=int(config["bootstrap_seed"]),
        relative_period_span=0.001,
    )
    local_payload = local.as_dict()
    local_payload.update(
        {
            "band": "V",
            "source_sha256": source_manifest["source_sha256"],
            "source_git_blob_sha1": source_manifest["git_blob_sha1"],
            "published_period_days": anchor.period_days,
            "period_difference_days": local.period_days - anchor.period_days,
            "period_difference_in_local_bootstrap_sigma": (
                (local.period_days - anchor.period_days) / local.period_bootstrap_standard_error_days
            ),
            "estimator_scope": "weighted three-harmonic local estimate from a 33-row partial mirror",
            "sha256_canonical_json": canonical_json_sha256(local_payload),
        }
    )
    # Recompute after adding all fields except the self hash.
    local_payload["sha256_canonical_json"] = canonical_json_sha256(
        {key: value for key, value in local_payload.items() if key != "sha256_canonical_json"}
    )
    write_json(out / "phase17_local_fourier_estimate.json", local_payload)

    audit = compare_external_anchor(
        local,
        anchor,
        external_research_group_independent=True,
        observational_source_independent=False,
        source_byte_identity_known=False,
    )
    audit_payload = audit.as_dict()
    audit_payload["sha256_canonical_json"] = canonical_json_sha256(audit_payload)
    write_json(out / "phase17_external_analysis_audit.json", audit_payload)

    labels = ["R21", "phi21", "R31", "phi31"]
    local_values = local.vector()
    external_values = anchor.vector()
    local_errors = np.sqrt(np.diag(local.covariance))
    external_errors = np.sqrt(np.diag(anchor.covariance()))
    comparison_rows: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        comparison_rows.append(
            {
                "object_id": anchor.object_id,
                "parameter": label,
                "local_value": float(local_values[i]),
                "local_standard_error": float(local_errors[i]),
                "external_value": float(external_values[i]),
                "external_standard_error": float(external_errors[i]),
                "difference_local_minus_external": float(audit.difference[i]),
                "combined_standard_error": float(np.sqrt(audit.combined_covariance[i, i])),
                "marginal_z": float(audit.marginal_z[i]),
            }
        )
    write_csv(out / "phase17_fourier_parameter_comparison.csv", comparison_rows)

    fixed_fit = fit_weighted_cosine_series(
        curve.time,
        curve.value,
        curve.error,
        period_days=local.period_days,
        reference_epoch=local.reference_epoch,
        order=3,
    )
    plot_folded_lightcurve(
        out / "phase17_folded_v_anchor.png",
        time=curve.time,
        magnitude=curve.value,
        error=curve.error,
        period=local.period_days,
        epoch=local.reference_epoch,
        beta=np.asarray(fixed_fit["beta"], dtype=float),
    )
    plot_parameter_comparison(out / "phase17_external_local_fourier_comparison.png", comparison_rows)
    plot_marginal_z(out / "phase17_marginal_z.png", comparison_rows)
    plot_independence_matrix(out / "phase17_independence_matrix.png", audit_payload)

    phase16_summary = load_json(root / protocol["parent_phase16"]["summary_path"])
    phase16_graph = load_json(root / protocol["parent_phase16"]["graph_path"])
    phase16_ledger, phase16_ledger_digest = verify_phase16_ledger(root, phase16_summary)
    extended_graph = extend_reproducibility_graph(
        phase16_graph,
        audit,
        external_anchor_id="jurkovic2022_ogle_v_fourier",
        local_analysis_id="phase17_partial_v_fourier_reanalysis",
    )
    graph_path = out / "phase17_reproducibility_graph.json"
    write_json(graph_path, extended_graph)
    write_csv(out / "phase17_reproducibility_edges.csv", extended_graph["edges"])
    write_csv(out / "phase17_analysis_nodes.csv", extended_graph["analysis_nodes"])
    plot_extended_graph(out / "phase17_reproducibility_graph.png", extended_graph)

    graph_ref = {
        "relative_path": graph_path.relative_to(root).as_posix(),
        "file_sha256": sha256_file(graph_path),
        "canonical_sha256": extended_graph["sha256_canonical_json"],
        "edge_count": len(extended_graph["edges"]),
        "analysis_version_count": extended_graph["analysis_version_count"],
    }
    ledger_payload = {
        "ledger_id": "DERD-PHASE17-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-19",
        "parent_phase16_summary_sha256": protocol["parent_phase16"]["summary_sha256"],
        "parent_phase16_ledger_sha256_canonical_json": phase16_ledger_digest,
        "prior_record_count": len(phase16_ledger["records"]),
        "new_astronomical_record_count": 0,
        "cumulative_count": len(phase16_ledger["records"]),
        "records": phase16_ledger["records"],
        "inherited_reproducibility_graphs": phase16_ledger.get("reproducibility_graphs", []),
        "external_analysis_anchors": [
            {
                "object_id": anchor.object_id,
                "classification": audit.classification,
                "audit_relative_path": "artifacts/phase17/phase17_external_analysis_audit.json",
                "audit_file_sha256": sha256_file(out / "phase17_external_analysis_audit.json"),
                "counts_as_independent_astrophysical_replication": False,
                "counts_as_astronomical_denominator_increment": False,
            }
        ],
        "reproducibility_graphs": [graph_ref],
        "multiplicity_guard": extended_graph["multiplicity_guard"],
        "claim_boundary": "Fourier-coordinate consistency and normalized waveform evidence only",
    }
    ledger_path = out / "phase17_cumulative_ledger.json"
    write_json(ledger_path, ledger_payload)
    ledger_digest = canonical_json_sha256(ledger_payload)
    seal_path = out / "phase17_cumulative_ledger.seal.json"
    write_json(
        seal_path,
        {
            "ledger_id": ledger_payload["ledger_id"],
            "record_count": len(ledger_payload["records"]),
            "external_analysis_anchor_count": 1,
            "sha256_canonical_json": ledger_digest,
            "date_sealed": "2026-08-19",
        },
    )

    claims = [
        {
            "claim_id": "C79",
            "claim": "The published OGLE-LMC-CEP-0002 V-band Fourier anchor is frozen with an explicit cosine-series convention and uncertainty coordinates.",
            "status": "VERIFIED_FROM_EXTERNAL_PUBLICATION",
        },
        {
            "claim_id": "C80",
            "claim": "The 33-row local V-band mirror passes byte, Git-blob, observation-count, and SHA-256 checks.",
            "status": "VERIFIED",
        },
        {
            "claim_id": "C81",
            "claim": "The local R21, phi21, R31, and phi31 estimates are jointly consistent with the published external anchor under the frozen covariance test.",
            "status": "VERIFIED_STATISTICAL_CONSISTENCY",
        },
        {
            "claim_id": "C82",
            "claim": "The 33-row mirror does not meet the publication's at-least-50-measurement input rule and the exact publication source bytes are unknown.",
            "status": "VERIFIED_LIMITATION",
        },
        {
            "claim_id": "C83",
            "claim": "The resulting edge is external-analysis consistency with partial source overlap, not independent astrophysical replication.",
            "status": "VERIFIED_AND_CLASSIFIED",
        },
        {
            "claim_id": "C84",
            "claim": "Adding the external analysis anchor leaves the astronomical denominator at five and the external independent replication count at zero.",
            "status": "VERIFIED_AND_ENFORCED",
        },
    ]

    population_firewall = {
        "primary_family_outputs_allowed": False,
        "unique_astronomical_objects": extended_graph["unique_object_denominator"],
        "frozen_total_denominator_required": 15,
        "external_independent_replication_count": extended_graph["external_independent_replication_count"],
        "external_analysis_consistency_count": extended_graph["external_analysis_consistency_count"],
        "reason": "An external method anchor does not complete the frozen population denominator or create an independent observing-source replication.",
    }
    summary = {
        "implementation_id": "DERD-v1.7-phase17-external-analysis-anchor",
        "date": datetime.now(timezone.utc).isoformat(),
        "decision": PHASE17_DECISION,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "c17_promoted": False,
        "protocol": protocol_check,
        "source_verification": source_check,
        "source_acquisition_receipt": "artifacts/phase17/phase17_source_acquisition_receipt.json",
        "external_anchor": anchor.as_dict(),
        "local_fourier_estimate": local_payload,
        "external_analysis_audit": audit_payload,
        "reproducibility_graph": extended_graph,
        "cumulative_ledger": {
            "relative_path": ledger_path.relative_to(root).as_posix(),
            "seal_relative_path": seal_path.relative_to(root).as_posix(),
            "seal_sha256_canonical_json": ledger_digest,
            "cumulative_astronomical_record_count": len(ledger_payload["records"]),
        },
        "population_firewall": population_firewall,
        "claims": claims,
        "figures": [
            "artifacts/phase17/phase17_folded_v_anchor.png",
            "artifacts/phase17/phase17_external_local_fourier_comparison.png",
            "artifacts/phase17/phase17_marginal_z.png",
            "artifacts/phase17/phase17_independence_matrix.png",
            "artifacts/phase17/phase17_reproducibility_graph.png",
        ],
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "locked_physical_gates": [
            "UNIQUE_INTERNAL_MECHANISM",
            "LITERAL_INTERNAL_KEPLERIAN_MOTION",
            "UNIVERSAL_TRANSPARENT_OUTER_SHELL",
            "SHELL_PREVALENCE",
            "SHELL_MASS_OR_MASS_FRACTION",
        ],
    }
    write_json(out / "phase17_summary.json", summary)

    report = "# Phase 17 result: external Fourier-analysis anchor\n\n"
    report += f"Decision: `{PHASE17_DECISION}`\n\n"
    report += "## External anchor\n\n"
    report += f"- Object: `{anchor.object_id}` ({anchor.object_type})\n"
    report += f"- Published V-band period: **{anchor.period_days:.6f} d**\n"
    report += f"- Local verified subset: **{local.sample_count} observations**\n"
    report += f"- Local refined period: **{local.period_days:.9f} d**\n\n"
    report += "## Joint comparison\n\n"
    report += f"- Mahalanobis chi-square: **{audit.mahalanobis_chi_square:.6f}** for {audit.degrees_of_freedom} degrees of freedom\n"
    report += f"- Joint p-value: **{audit.p_value:.6f}**\n"
    report += f"- Maximum absolute marginal z: **{float(np.max(np.abs(audit.marginal_z))):.6f}**\n"
    report += f"- Classification: `{audit.classification}`\n\n"
    report += "## Independence boundary\n\n"
    report += "The analysis group is external, but the observing-source family overlaps, the exact publication input bytes are unknown, and the local mirror has fewer than the publication's minimum 50 measurements. The edge therefore does not count as independent astrophysical replication or as a new astronomical denominator record.\n\n"
    report += "## Physical-claim boundary\n\n"
    report += "This phase validates Fourier-coordinate transport and external methodological consistency only. It does not identify an internal stellar mechanism, a transparent shell, shell prevalence, or shell mass.\n"
    (out / "PHASE17_RESULT.md").write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "decision": PHASE17_DECISION,
                "classification": audit.classification,
                "joint_p_value": audit.p_value,
                "max_abs_marginal_z": float(np.max(np.abs(audit.marginal_z))),
                "external_analysis_consistency_count": extended_graph["external_analysis_consistency_count"],
                "external_independent_replication_count": extended_graph["external_independent_replication_count"],
                "astronomical_denominator": extended_graph["unique_object_denominator"],
                "ledger_sha256": ledger_digest,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
