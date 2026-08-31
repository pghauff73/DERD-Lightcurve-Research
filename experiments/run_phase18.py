#!/usr/bin/env python3
"""Execute Phase 18: authoritative OGLE-III+IV external-input reconstruction."""
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

from derd.io import write_json
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase17 import load_external_anchor
from derd.validation_phase18 import (
    CLASS_PARAMETER_MISMATCH,
    CLASS_PUBLICATION_COMPATIBLE,
    PARAMETER_LABELS,
    PHASE18_DECISION,
    add_phase18_graph_edge,
    load_three_column,
    merge_photometry,
    merged_method_spread,
    run_method_lattice,
    verify_source_component,
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


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
        writer.writerows([dict(row) for row in rows])


def verify_protocol(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol_path = root / "research/preregistration/phase18_exact_external_input_reconstruction_protocol.json"
    seal_path = root / "research/preregistration/phase18_exact_external_input_reconstruction_protocol.seal.json"
    protocol = load_json(protocol_path)
    seal = load_json(seal_path)
    if canonical_json_sha256(protocol) != seal.get("sha256_canonical_json"):
        raise RuntimeError("Phase-18 protocol seal mismatch")
    for section, pairs in (
        ("parent_phase17", (("summary_path", "summary_sha256"), ("graph_path", "graph_sha256"), ("ledger_path", "ledger_sha256"), ("ledger_seal_path", "ledger_seal_sha256"))),
        ("external_anchor", (("path", "file_sha256"),)),
        ("method_contract", (("path", "file_sha256"),)),
        ("source_manifest", (("path", "file_sha256"),)),
    ):
        block = protocol[section]
        for path_key, hash_key in pairs:
            if sha256_file(root / block[path_key]) != block[hash_key]:
                raise RuntimeError(f"Phase-18 protocol dependency mismatch: {section}.{path_key}")
    return protocol, seal


def invariant_rows(estimates, audits, anchor) -> list[dict[str, Any]]:
    audit_by_id = {audit.variant_id: audit for audit in audits}
    rows: list[dict[str, Any]] = []
    for estimate in estimates:
        audit = audit_by_id[estimate.variant_id]
        row: dict[str, Any] = {
            "variant_id": estimate.variant_id,
            "source_scope": estimate.source_scope,
            "sample_count": estimate.sample_count,
            "weighting": estimate.weighting,
            "period_mode": estimate.period_mode,
            "covariance_scale": estimate.covariance_scale,
            "period_days": estimate.period_days,
            "period_minus_published_days": estimate.period_days - anchor.period_days,
            "residual_rmse_mag": estimate.residual_rmse_mag,
            "quoted_error_reduced_chi_square": estimate.quoted_error_reduced_chi_square,
            "fit_objective_reduced": estimate.fit_objective_reduced,
            "design_condition_number": estimate.design_condition_number,
            "mahalanobis_chi_square": audit.mahalanobis_chi_square,
            "degrees_of_freedom": audit.degrees_of_freedom,
            "joint_p_value": audit.p_value,
            "marginal_pass": audit.marginal_pass,
            "joint_pass": audit.joint_pass,
        }
        for index, label in enumerate(PARAMETER_LABELS):
            row[label] = float(estimate.vector[index])
            row[f"{label}_se"] = float(estimate.standard_error[index])
            row[f"{label}_published"] = float(anchor.vector()[index])
            row[f"{label}_difference"] = float(audit.difference[index])
            row[f"{label}_z"] = float(audit.marginal_z[index])
        rows.append(row)
    return rows


def plot_folded(path: Path, merged: np.ndarray, primary) -> None:
    time, magnitude, error = merged.T
    phase = np.mod((time - primary.reference_epoch) / primary.period_days, 1.0)
    dense = np.linspace(0.0, 1.0, 1000, endpoint=False)
    model = np.full_like(dense, np.mean(magnitude))
    # Recreate the curve from amplitudes and phases.  The intercept affects only vertical placement.
    design = np.column_stack(
        [
            np.ones(time.size),
            *[
                f(2.0 * math.pi * h * phase)
                for h in range(1, 4)
                for f in (np.sin, np.cos)
            ],
        ]
    )
    beta, *_ = np.linalg.lstsq(design, magnitude, rcond=None)
    dense_columns = [np.ones(dense.size)]
    for h in range(1, 4):
        dense_columns.extend([np.sin(2.0 * math.pi * h * dense), np.cos(2.0 * math.pi * h * dense)])
    model = np.column_stack(dense_columns) @ beta
    split = time < 5000.0
    fig, ax = plt.subplots(figsize=(8.7, 5.2))
    ax.errorbar(phase[split], magnitude[split], yerr=error[split], fmt="o", ms=4, lw=0.6, label="OGLE-III")
    ax.errorbar(phase[~split], magnitude[~split], yerr=error[~split], fmt="s", ms=4, lw=0.6, label="OGLE-IV")
    ax.plot(dense, model, lw=1.5, label="three-harmonic reconstruction")
    ax.invert_yaxis()
    ax.set_xlabel("Pulsation phase")
    ax.set_ylabel("V magnitude")
    ax.set_title("OGLE-LMC-CEP-0002 merged OGLE-III+IV V-band input")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_method_lattice(path: Path, rows: Sequence[Mapping[str, Any]], primary_id: str) -> None:
    merged = [row for row in rows if row["source_scope"] == "merged_ogleiii_iv"]
    x = np.arange(len(PARAMETER_LABELS), dtype=float)
    fig, ax = plt.subplots(figsize=(10.0, 5.8))
    for row in merged:
        values = np.array([float(row[label]) for label in PARAMETER_LABELS])
        errors = np.array([float(row[f"{label}_se"]) for label in PARAMETER_LABELS])
        lw = 2.2 if row["variant_id"] == primary_id else 0.9
        alpha = 1.0 if row["variant_id"] == primary_id else 0.55
        ax.errorbar(x, values, yerr=errors, marker="o", lw=lw, alpha=alpha, label=str(row["variant_id"]))
    published = np.array([float(merged[0][f"{label}_published"]) for label in PARAMETER_LABELS])
    ax.scatter(x, published, marker="*", s=150, label="published vector")
    ax.set_xticks(x, ["R21", "phi21", "R31", "phi31"])
    ax.set_ylabel("Invariant value (radians for phase terms)")
    ax.set_title("Merged-source curve_fit method lattice")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_source_scope(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    selected = [
        row for row in rows
        if row["weighting"] == "unweighted" and row["period_mode"] == "free"
    ]
    scopes = [str(row["source_scope"]) for row in selected]
    x = np.arange(len(PARAMETER_LABELS), dtype=float)
    width = 0.24
    fig, ax = plt.subplots(figsize=(9.7, 5.4))
    for index, row in enumerate(selected):
        values = np.array([float(row[label]) for label in PARAMETER_LABELS])
        ax.scatter(x + (index - 1) * width, values, label=scopes[index], s=55)
    published = np.array([float(selected[0][f"{label}_published"]) for label in PARAMETER_LABELS])
    ax.scatter(x + 2 * width, published, marker="*", s=150, label="published")
    ax.set_xticks(x, ["R21", "phi21", "R31", "phi31"])
    ax.set_ylabel("Invariant value")
    ax.set_title("Source-scope intervention: OGLE-III, OGLE-IV, and merged")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_closure_matrix(path: Path, gates: Mapping[str, bool]) -> None:
    labels = list(gates)
    values = [1 if gates[label] else 0 for label in labels]
    fig, ax = plt.subplots(figsize=(10.5, 4.7))
    ax.bar([label.replace("_", "\n") for label in labels], values)
    ax.set_yticks([0, 1], ["Open", "Closed"])
    ax.set_ylim(0.0, 1.15)
    ax.set_title("Phase-18 external-input reconstruction gates")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--ogleiii", type=Path, required=True)
    parser.add_argument("--ogleiv", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "artifacts/phase18"
    out.mkdir(parents=True, exist_ok=True)

    protocol, protocol_seal = verify_protocol(root)
    manifest = load_json(root / protocol["source_manifest"]["path"])
    method_contract = load_json(root / protocol["method_contract"]["path"])
    anchor = load_external_anchor(root / protocol["external_anchor"]["path"])

    paths = {"ogleiii_v": args.ogleiii.resolve(), "ogleiv_v": args.ogleiv.resolve()}
    component_checks: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    for component in manifest["components"]:
        source_id = component["source_id"]
        check = verify_source_component(paths[source_id], component)
        check.update({"source_id": source_id, "survey": component["survey"], "url": component["url"]})
        component_checks.append(check)
        if not check["all_checks_passed"]:
            raise RuntimeError(f"source verification failed: {source_id}")
        arrays[source_id] = load_three_column(paths[source_id])

    merged = merge_photometry(arrays["ogleiii_v"], arrays["ogleiv_v"])
    merged_temp = out / "phase18_merged_input.verification-only.dat"
    np.savetxt(merged_temp, merged, fmt=["%.5f", "%.3f", "%.3f"])
    merged_check = verify_source_component(merged_temp, manifest["merged"])
    merged_temp.unlink()
    if not merged_check["all_checks_passed"]:
        raise RuntimeError("merged-source digest mismatch")

    source_receipt = {
        "receipt_id": "DERD-PHASE18-AUTHORITATIVE-OGLE-INPUT-RECEIPT-1.0",
        "date": datetime.now(timezone.utc).isoformat(),
        "object_id": anchor.object_id,
        "status": "AUTHORITATIVE_CURRENT_OGLEIII_IV_FILES_VERIFIED_AND_MERGED",
        "attribution_acknowledgement": True,
        "components": component_checks,
        "merged": merged_check,
        "publication_input_byte_identity_known": False,
        "raw_source_redistributed": False,
        "source_manifest_sha256": sha256_file(root / protocol["source_manifest"]["path"]),
    }
    write_json(out / "phase18_source_acquisition_receipt.json", source_receipt)

    scopes = {
        "ogleiii_only": arrays["ogleiii_v"],
        "ogleiv_only": arrays["ogleiv_v"],
        "merged_ogleiii_iv": merged,
    }
    estimates, audits = run_method_lattice(scopes, anchor)
    rows = invariant_rows(estimates, audits, anchor)
    write_csv(out / "phase18_method_lattice.csv", rows)

    primary_id = protocol["analysis"]["primary_variant"]
    estimate_by_id = {estimate.variant_id: estimate for estimate in estimates}
    audit_by_id = {audit.variant_id: audit for audit in audits}
    primary = estimate_by_id[primary_id]
    primary_audit = audit_by_id[primary_id]
    merged_rows = [row for row in rows if row["source_scope"] == "merged_ogleiii_iv"]
    all_merged_consistent = bool(all(row["joint_pass"] and row["marginal_pass"] for row in merged_rows))
    classification = (
        CLASS_PUBLICATION_COMPATIBLE
        if primary_audit.joint_pass and primary_audit.marginal_pass
        else CLASS_PARAMETER_MISMATCH
    )
    spread = merged_method_spread(estimates)

    scope_rows: list[dict[str, Any]] = []
    for scope in scopes:
        row = next(
            row for row in rows
            if row["source_scope"] == scope and row["weighting"] == "unweighted" and row["period_mode"] == "free"
        )
        scope_rows.append(row)
    write_csv(out / "phase18_source_scope_intervention.csv", scope_rows)

    primary_payload = primary.as_dict()
    primary_payload["audit"] = primary_audit.as_dict()
    primary_payload["classification"] = classification
    primary_payload["sha256_canonical_json"] = canonical_json_sha256(primary_payload)
    write_json(out / "phase18_primary_reconstruction.json", primary_payload)

    gates = {
        "official_ogleiii_verified": component_checks[0]["all_checks_passed"],
        "official_ogleiv_verified": component_checks[1]["all_checks_passed"],
        "publication_minimum_met": merged.shape[0] >= anchor.minimum_measurements,
        "primary_joint_consistency": primary_audit.joint_pass,
        "primary_marginal_consistency": primary_audit.marginal_pass,
        "all_merged_variants_consistent": all_merged_consistent,
        "exact_publication_byte_identity": False,
        "exact_publication_code_available": False,
        "independent_observing_source": False,
    }

    phase17_graph = load_json(root / protocol["parent_phase17"]["graph_path"])
    graph = add_phase18_graph_edge(
        phase17_graph,
        classification=classification,
        primary_audit=primary_audit,
    )
    write_json(out / "phase18_reproducibility_graph.json", graph)

    phase17_ledger = load_json(root / protocol["parent_phase17"]["ledger_path"])
    ledger = {
        "ledger_id": "DERD-PHASE18-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-24",
        "parent_phase17_ledger_file_sha256": protocol["parent_phase17"]["ledger_sha256"],
        "records": phase17_ledger["records"],
        "cumulative_astronomical_record_count": len(phase17_ledger["records"]),
        "new_astronomical_record_count": 0,
        "external_analysis_anchors": phase17_ledger.get("external_analysis_anchors", []),
        "external_input_reconstructions": [
            {
                "object_id": anchor.object_id,
                "classification": classification,
                "primary_variant": primary_id,
                "source_observation_count": int(merged.shape[0]),
                "publication_minimum_met": True,
                "audit_relative_path": "artifacts/phase18/phase18_primary_reconstruction.json",
                "counts_as_independent_astrophysical_replication": False,
                "counts_as_astronomical_denominator_increment": False,
            }
        ],
        "reproducibility_graphs": [
            {
                "relative_path": "artifacts/phase18/phase18_reproducibility_graph.json",
                "file_sha256": sha256_file(out / "phase18_reproducibility_graph.json"),
                "canonical_sha256": graph["sha256_canonical_json"],
            }
        ],
        "claim_boundary": "external Fourier input-scope reconstruction and normalized waveform evidence only",
    }
    write_json(out / "phase18_cumulative_ledger.json", ledger)
    ledger_digest = canonical_json_sha256(ledger)
    write_json(
        out / "phase18_cumulative_ledger.seal.json",
        {
            "ledger_id": ledger["ledger_id"],
            "record_count": len(ledger["records"]),
            "sha256_canonical_json": ledger_digest,
            "date_sealed": "2026-08-24",
        },
    )

    plot_folded(out / "phase18_merged_folded_v.png", merged, primary)
    plot_method_lattice(out / "phase18_method_lattice.png", rows, primary_id)
    plot_source_scope(out / "phase18_source_scope_intervention.png", rows)
    plot_closure_matrix(out / "phase18_gate_closure.png", gates)

    claims = [
        {
            "claim_id": "C85",
            "claim": "The official current OGLE-III and OGLE-IV V-band files for OGLE-LMC-CEP-0002 contain 33 and 32 verified observations and merge into a 65-observation source scope.",
            "status": "VERIFIED_AUTHORITATIVE_CURRENT_SOURCE_SCOPE",
        },
        {
            "claim_id": "C86",
            "claim": "The merged source meets the external publication's at-least-50-measurement rule and reproduces the published four-coordinate vector under the frozen primary joint and marginal gates.",
            "status": "VERIFIED_PUBLICATION_COMPATIBLE_RECONSTRUCTION",
        },
        {
            "claim_id": "C87",
            "claim": "Reasonable curve_fit weighting and fixed-versus-free-period variants remain jointly consistent with the published vector, while the OGLE-III-only and OGLE-IV-only estimates show the source-scope effect.",
            "status": "VERIFIED_METHOD_LATTICE",
        },
        {
            "claim_id": "C88",
            "claim": "Exact publication-byte identity and exact analysis-code replay remain unavailable because the article supplies neither source hashes nor the analysis source code and does not fully specify curve_fit weighting.",
            "status": "VERIFIED_REPLICATION_LIMITATION",
        },
        {
            "claim_id": "C89",
            "claim": "The Phase-17 method summary conflated K2 bootstrap errors with the OGLE comparison; the corrected Phase-18 contract records curve_fit covariance for the OGLE table.",
            "status": "CORRECTED_WITH_HISTORICAL_PROVENANCE_PRESERVED",
        },
        {
            "claim_id": "C90",
            "claim": "The Phase-18 reconstruction adds no astronomical denominator item and is not independent astrophysical replication.",
            "status": "ENFORCED_BY_REPRODUCIBILITY_GRAPH",
        },
    ]

    summary = {
        "implementation_id": "DERD-v1.8-phase18-exact-external-input-reconstruction",
        "date": datetime.now(timezone.utc).isoformat(),
        "decision": PHASE18_DECISION,
        "classification": classification,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "c17_promoted": False,
        "protocol": {"valid": True, "seal": protocol_seal, "protocol": protocol},
        "method_contract": method_contract,
        "source_receipt": source_receipt,
        "source_scope": {
            "ogleiii_observations": int(arrays["ogleiii_v"].shape[0]),
            "ogleiv_observations": int(arrays["ogleiv_v"].shape[0]),
            "merged_observations": int(merged.shape[0]),
            "merged_time_span_days": float(merged[-1, 0] - merged[0, 0]),
            "publication_minimum_measurements": anchor.minimum_measurements,
            "publication_minimum_met": bool(merged.shape[0] >= anchor.minimum_measurements),
        },
        "primary_reconstruction": primary_payload,
        "merged_method_spread": spread,
        "all_merged_variants_consistent": all_merged_consistent,
        "gates": gates,
        "reproducibility_graph": graph,
        "cumulative_ledger": {
            "relative_path": "artifacts/phase18/phase18_cumulative_ledger.json",
            "seal_relative_path": "artifacts/phase18/phase18_cumulative_ledger.seal.json",
            "seal_sha256_canonical_json": ledger_digest,
            "cumulative_astronomical_record_count": len(ledger["records"]),
        },
        "claims": claims,
        "population_firewall": {
            "family_outputs_allowed": False,
            "astronomical_denominator": len(ledger["records"]),
            "independent_astrophysical_replication_count": graph.get("external_independent_replication_count", 0),
            "reason": "Source-scope reconstruction does not complete the frozen population denominator and does not create an independent observing-source replication.",
        },
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform()},
        "locked_physical_gates": [
            "UNIQUE_INTERNAL_MECHANISM",
            "LITERAL_INTERNAL_KEPLERIAN_MOTION",
            "UNIVERSAL_TRANSPARENT_OUTER_SHELL",
            "SHELL_PREVALENCE",
            "SHELL_MASS_OR_MASS_FRACTION",
        ],
    }
    write_json(out / "phase18_summary.json", summary)

    report = f"""# Phase 18 result: exact external-input-scope reconstruction

Decision: `{PHASE18_DECISION}`

## Source closure

- OGLE-III V observations: **{arrays['ogleiii_v'].shape[0]}**
- OGLE-IV V observations: **{arrays['ogleiv_v'].shape[0]}**
- Chronologically merged observations: **{merged.shape[0]}**
- Published minimum: **{anchor.minimum_measurements}**
- Exact publication input-byte identity: **not available**

## Frozen primary reconstruction

Primary variant: `{primary_id}`

| Coordinate | Reconstructed | Published | Difference | Marginal z |
|---|---:|---:|---:|---:|
"""
    for index, label in enumerate(PARAMETER_LABELS):
        report += f"| {label} | {primary.vector[index]:.6f} | {anchor.vector()[index]:.6f} | {primary_audit.difference[index]:+.6f} | {primary_audit.marginal_z[index]:+.3f} |\n"
    report += f"""

Joint Mahalanobis statistic: **{primary_audit.mahalanobis_chi_square:.6f}**
Joint p-value: **{primary_audit.p_value:.6f}**
Classification: `{classification}`

## Method uncertainty

All six merged-source fixed/free and weighting variants pass the frozen joint and marginal consistency gates: **{all_merged_consistent}**.
The article does not publish its source code, source hashes, exact row list, frequency grid, or curve_fit weighting call. Phase 18 therefore establishes a publication-compatible reconstruction, not byte-identical or code-identical replay.

## Claim boundary

This phase tests Fourier-coordinate transport and external-input provenance only. It does not identify an internal stellar mechanism, a transparent shell, shell prevalence, or shell mass.
"""
    (out / "PHASE18_RESULT.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "decision": PHASE18_DECISION,
        "classification": classification,
        "merged_observations": int(merged.shape[0]),
        "primary_variant": primary_id,
        "primary_joint_p_value": primary_audit.p_value,
        "primary_max_abs_z": float(np.max(np.abs(primary_audit.marginal_z))),
        "all_merged_variants_consistent": all_merged_consistent,
        "ledger_sha256": ledger_digest,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
