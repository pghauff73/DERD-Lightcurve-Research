#!/usr/bin/env python3
"""Run Phase 16 cross-version reproducibility graph and multiplicity guard."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase10 import assess_phase10
from derd.validation_phase12 import VerifiedLedger, cumulative_population_firewall, sha256_file
from derd.validation_phase16 import (
    EDGE_CONFIG_DRIFT,
    EDGE_EXACT,
    PHASE16_DECISION,
    build_reproducibility_graph,
    load_verified_phase15_ledger,
)

ROOT_DEFAULT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


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
        writer.writerows(rows)


def verify_protocol(root: Path) -> dict[str, Any]:
    protocol_path = root / "research/preregistration/phase16_reproducibility_graph_protocol.json"
    seal_path = root / "research/preregistration/phase16_reproducibility_graph_protocol.seal.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal.get("sha256_canonical_json", ""))
    checks = {
        "canonical_protocol_seal": actual == expected,
        "implementation_id": protocol.get("implementation_id") == "DERD-v1.6-phase16-reproducibility-graph",
        "parent_summary": sha256_file(root / protocol["parent_phase15_summary"]["path"]) == protocol["parent_phase15_summary"]["sha256"],
        "replay_inputs": all(
            sha256_file(root / row["path"]) == row["sha256"]
            for row in protocol["required_replay_inputs"]
        ),
        "multiplicity_guard": bool(protocol["multiplicity_guard"]["one_denominator_record_per_astronomical_object"]),
    }
    return {
        "valid": all(checks.values()),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "protocol_id": protocol.get("protocol_id"),
        "checks": checks,
        "expected_counts": protocol["expected_counts"],
    }


def assess_cohort(root: Path):
    return assess_phase10(
        root=root,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path=None,
    )


def plot_classifications(path: Path, graph: Mapping[str, Any]) -> None:
    counts = {
        "exact replay": graph["exact_replay_count"],
        "config drift": graph["configuration_drift_count"],
        "single version": len(graph["single_version_objects"]),
        "external replication": graph["external_independent_replication_count"],
    }
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(list(counts), list(counts.values()))
    ax.set_ylabel("Count")
    ax.set_title("Phase 16 reproducibility classifications")
    ax.tick_params(axis="x", rotation=18)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_multiplicity(path: Path, graph: Mapping[str, Any]) -> None:
    labels = ["analysis versions", "unique objects", "inflation blocked"]
    values = [
        graph["analysis_version_count"],
        graph["unique_object_denominator"],
        graph["duplicate_analysis_inflation_prevented"],
    ]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(labels, values)
    ax.set_ylabel("Count")
    ax.set_title("Evidence multiplicity guard")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_graph(path: Path, graph: Mapping[str, Any]) -> None:
    objects = graph["object_ids"]
    y = np.arange(len(objects))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.scatter(np.zeros(len(objects)), y, s=80, label="ledger object")
    x_max = 0
    for index, object_id in enumerate(objects):
        versions = [node["analysis_version"] for node in graph["analysis_nodes"] if node["object_id"] == object_id]
        for j, version in enumerate(versions, start=1):
            ax.scatter(j, index, s=55)
            ax.text(j, index + 0.11, version, ha="center", fontsize=8)
            ax.plot([0, j], [index, index], linewidth=0.8)
            x_max = max(x_max, j)
    ax.set_yticks(y, objects)
    ax.set_xticks(range(x_max + 1))
    ax.set_xlabel("Analysis-version node index")
    ax.set_title("Object-to-analysis reproducibility graph")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "artifacts/phase16"
    out.mkdir(parents=True, exist_ok=True)

    protocol = verify_protocol(root)
    if not protocol["valid"]:
        raise RuntimeError("Phase-16 protocol validation failed")

    records, parent_summary_sha, parent_ledger_digest, parent_ledger, lineage = load_verified_phase15_ledger(root=root)
    graph = build_reproducibility_graph(root=root, ledger_records=records, phase15_lineage=lineage)
    graph_payload = graph.as_dict()
    expected = protocol["expected_counts"]
    if not (
        graph.unique_object_denominator == expected["unique_objects"]
        and graph.exact_replay_count == expected["exact_replay_edges"]
        and graph.configuration_drift_count == expected["configuration_sensitive_drift_edges"]
        and len(graph.single_version_objects) == expected["single_version_objects"]
        and graph.external_independent_replication_count == expected["external_independent_replications"]
    ):
        raise RuntimeError("Phase-16 graph counts differ from frozen protocol")

    graph_path = out / "phase16_reproducibility_graph.json"
    write_json(graph_path, graph_payload)
    write_csv(out / "phase16_reproducibility_edges.csv", [edge.as_dict() for edge in graph.edges])
    write_csv(out / "phase16_analysis_nodes.csv", list(graph.analysis_nodes))

    graph_ref = {
        "relative_path": graph_path.relative_to(root).as_posix(),
        "file_sha256": sha256_file(graph_path),
        "canonical_sha256": graph_payload["sha256_canonical_json"],
        "edge_count": len(graph.edges),
        "analysis_version_count": graph.analysis_version_count,
    }
    ledger_payload = {
        "ledger_id": "DERD-PHASE16-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-19",
        "parent_phase15_summary_sha256": parent_summary_sha,
        "parent_phase15_ledger_sha256_canonical_json": parent_ledger_digest,
        "prior_record_count": len(records),
        "new_record_count": 0,
        "cumulative_count": len(records),
        "records": [dict(row) for row in records],
        "inherited_temporal_audits": parent_ledger.get("inherited_temporal_audits", []),
        "inherited_period_coordinate_audits": parent_ledger.get("inherited_period_coordinate_audits", []),
        "inherited_archival_lineage_audits": parent_ledger.get("archival_lineage_audits", []),
        "reproducibility_graphs": [graph_ref],
        "multiplicity_guard": graph_payload["multiplicity_guard"],
        "claim_boundary": "computational reproducibility and normalized waveform evidence only",
    }
    ledger_path = out / "phase16_cumulative_ledger.json"
    write_json(ledger_path, ledger_payload)
    ledger_digest = canonical_json_sha256(ledger_payload)
    seal_path = out / "phase16_cumulative_ledger.seal.json"
    write_json(
        seal_path,
        {
            "ledger_id": ledger_payload["ledger_id"],
            "record_count": len(records),
            "reproducibility_graph_count": 1,
            "sha256_canonical_json": ledger_digest,
            "date_sealed": "2026-08-19",
        },
    )

    ledger = VerifiedLedger(
        records=records,
        prior_summary_sha256=parent_summary_sha,
        prior_record_count=len(records),
        new_record_count=0,
    )
    firewall = cumulative_population_firewall(assess_cohort(root), ledger)
    write_csv(out / "phase16_family_coverage.csv", firewall["family_coverage"])

    plot_classifications(out / "phase16_reproducibility_classifications.png", graph_payload)
    plot_multiplicity(out / "phase16_multiplicity_guard.png", graph_payload)
    plot_graph(out / "phase16_reproducibility_graph.png", graph_payload)

    claims = [
        {
            "claim_id": "C75",
            "claim": "Three same-source, same-configuration analyses reproduce their scientific projection and harmonic exchange exactly.",
            "status": "VERIFIED",
        },
        {
            "claim_id": "C76",
            "claim": "One same-source comparison exhibits configuration-sensitive scientific drift and is not an exact replay.",
            "status": "VERIFIED",
        },
        {
            "claim_id": "C77",
            "claim": "Nine analysis-version nodes contribute only five astronomical denominator records.",
            "status": "VERIFIED_AND_ENFORCED",
        },
        {
            "claim_id": "C78",
            "claim": "The current evidence graph contains no external independent astrophysical replication.",
            "status": "VERIFIED",
        },
    ]

    summary = {
        "implementation_id": "DERD-v1.6-phase16-reproducibility-graph",
        "date": datetime.now(timezone.utc).isoformat(),
        "decision": PHASE16_DECISION,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "c17_promoted": False,
        "protocol": protocol,
        "reproducibility_graph": graph_payload,
        "cumulative_ledger": {
            "relative_path": ledger_path.relative_to(root).as_posix(),
            "seal_relative_path": seal_path.relative_to(root).as_posix(),
            "seal_sha256_canonical_json": ledger_digest,
            "cumulative_count": len(records),
        },
        "population_firewall": firewall,
        "claims": claims,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "figures": [
            "artifacts/phase16/phase16_reproducibility_classifications.png",
            "artifacts/phase16/phase16_multiplicity_guard.png",
            "artifacts/phase16/phase16_reproducibility_graph.png",
        ],
        "locked_physical_gates": [
            "UNIQUE_INTERNAL_MECHANISM",
            "LITERAL_INTERNAL_KEPLERIAN_MOTION",
            "UNIVERSAL_TRANSPARENT_OUTER_SHELL",
            "SHELL_PREVALENCE",
            "SHELL_MASS_OR_MASS_FRACTION",
        ],
    }
    write_json(out / "phase16_summary.json", summary)

    report = "# Phase 16 result: cross-version reproducibility graph\n\n"
    report += f"Decision: `{PHASE16_DECISION}`\n\n"
    report += "## Graph summary\n\n"
    report += f"- Unique astronomical objects: **{graph.unique_object_denominator}**\n"
    report += f"- Analysis-version nodes: **{graph.analysis_version_count}**\n"
    report += f"- Exact scientific replay edges: **{graph.exact_replay_count}**\n"
    report += f"- Configuration-sensitive drift edges: **{graph.configuration_drift_count}**\n"
    report += f"- Single-version objects: **{len(graph.single_version_objects)}**\n"
    report += f"- External independent replications: **{graph.external_independent_replication_count}**\n"
    report += f"- Duplicate analysis inflation prevented: **{graph.duplicate_analysis_inflation_prevented}**\n\n"
    report += "## Edge classifications\n\n"
    for edge in graph.edges:
        report += f"- `{edge.object_id}`: `{edge.source_version}` → `{edge.comparison_version}` = `{edge.classification}`\n"
    report += "\n## Multiplicity rule\n\n"
    report += graph_payload["multiplicity_guard"] + "\n\n"
    report += "Family fractions and population claims remain suppressed because the frozen 15-object denominator is incomplete.\n"
    (out / "PHASE16_RESULT.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "decision": PHASE16_DECISION,
        "unique_objects": graph.unique_object_denominator,
        "analysis_versions": graph.analysis_version_count,
        "exact_replay_edges": graph.exact_replay_count,
        "configuration_drift_edges": graph.configuration_drift_count,
        "ledger_sha256": ledger_digest,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
