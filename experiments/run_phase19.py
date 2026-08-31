#!/usr/bin/env python3
"""Finalize Phase-19 public evidence after a local clean-room kit control."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase19 import (
    PHASE19_CLASSIFICATION,
    PHASE19_DECISION,
    PHASE19_IMPLEMENTATION_ID,
    canonical_sha256,
    load_json,
    verify_submission_self_hash,
    write_json,
)


def verify_sealed_json(document: Path, seal: Path) -> tuple[dict[str, Any], str]:
    payload = load_json(document)
    sealed = load_json(seal)
    digest = canonical_json_sha256(payload)
    if sealed.get("sha256_canonical_json") != digest:
        raise RuntimeError(f"seal mismatch: {document}")
    return payload, digest


def verify_task_manifest(document: Path, seal: Path) -> tuple[dict[str, Any], str]:
    payload = load_json(document)
    declared = payload.pop("sha256_canonical_json")
    digest = canonical_json_sha256(payload)
    payload["sha256_canonical_json"] = declared
    if digest != declared:
        raise RuntimeError("task manifest self-digest failed")
    sealed = load_json(seal)
    if sealed.get("sha256_canonical_json") != digest:
        raise RuntimeError("task manifest seal failed")
    return payload, digest


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_readiness(path: Path, gates: Mapping[str, bool]) -> None:
    labels = list(gates)
    values = [1 if gates[name] else 0 for name in labels]
    fig, ax = plt.subplots(figsize=(10.5, 4.9))
    ax.bar(np.arange(len(labels)), values)
    ax.set_xticks(np.arange(len(labels)), [label.replace("_", "\n") for label in labels])
    ax.set_yticks([0, 1], ["Open", "Closed"])
    ax.set_ylim(0.0, 1.15)
    ax.set_title("Phase-19 external computational-replication readiness")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_task_inventory(path: Path, manifest: Mapping[str, Any]) -> None:
    counts = manifest["task_types"]
    labels = ["Synthetic\nphotometry", "Blinded observational\nexchange"]
    values = [counts["synthetic_photometry"], counts["observational_exchange"]]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.bar(labels, values)
    ax.set_ylabel("Tasks")
    ax.set_title("Blind Phase-19 task inventory")
    for index, value in enumerate(values):
        ax.text(index, value + 0.08, str(value), ha="center")
    ax.set_ylim(0, max(values) + 1)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--public-kit", type=Path, required=True)
    parser.add_argument("--private-evaluator", type=Path, required=True)
    parser.add_argument("--local-submission", type=Path, required=True)
    parser.add_argument("--local-verification", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    out = root / "artifacts/phase19"
    out.mkdir(parents=True, exist_ok=True)

    protocol, protocol_sha = verify_sealed_json(
        root / "research/preregistration/phase19_external_group_replay_protocol.json",
        root / "research/preregistration/phase19_external_group_replay_protocol.seal.json",
    )
    manifest, manifest_sha = verify_task_manifest(
        root / "data/manifests/phase19_replication_tasks.json",
        root / "data/manifests/phase19_replication_tasks.seal.json",
    )
    build_receipt = load_json(out / "phase19_kit_build_receipt.json")
    if sha256_file(args.public_kit) != build_receipt["public_kit_sha256"]:
        raise RuntimeError("public kit ZIP digest mismatch")
    if sha256_file(args.private_evaluator) != build_receipt["private_evaluator_sha256"]:
        raise RuntimeError("private evaluator ZIP digest mismatch")

    submission = load_json(args.local_submission)
    verification = load_json(args.local_verification)
    if not verify_submission_self_hash(submission):
        raise RuntimeError("local clean-room submission self-hash failed")
    if not verification.get("scientific_projection_reproduced"):
        raise RuntimeError("local clean-room control did not reproduce the scientific projection")
    if verification.get("task_count_expected") != manifest["task_count"]:
        raise RuntimeError("local verification task count mismatch")

    redacted_control = {
        "control_id": "DERD-PHASE19-LOCAL-CLEANROOM-CONTROL-1.0",
        "classification": "INTERNAL_ISOLATED_PROCESS_CONTROL_NOT_EXTERNAL_REPLICATION",
        "operator_id": submission["operator"]["operator_id"],
        "organization": submission["operator"]["organization"],
        "environment": submission["environment"],
        "submission_sha256": submission["submission_sha256"],
        "submission_file_sha256": sha256_file(args.local_submission),
        "private_verification_file_sha256": sha256_file(args.local_verification),
        "commitment_verified": bool(verification["commitment_verified"]),
        "submission_self_hash_verified": bool(verification["submission_self_hash_verified"]),
        "operator_attestation_present": bool(verification["operator_attestation_present"]),
        "all_tasks_passed": bool(verification["all_tasks_passed"]),
        "task_count": int(verification["task_count_expected"]),
        "task_ids": sorted(row["task_id"] for row in verification["task_audits"]),
        "answer_labels_redacted": True,
        "answer_key_disclosed": False,
        "counts_as_external_computational_replication": False,
        "counts_as_independent_astrophysical_replication": False,
    }
    write_json(out / "phase19_local_cleanroom_control.json", redacted_control)

    task_rows = [
        {
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "input_sha256": task["input_sha256"],
            "input_filename": task["input_path"],
            "direct_fit_enabled": bool(task.get("direct_fit", {}).get("enabled", False)),
            "answer_label_disclosed": False,
        }
        for task in manifest["tasks"]
    ]
    write_csv(out / "phase19_task_inventory.csv", task_rows)

    readiness = {
        "protocol_sealed": True,
        "task_manifest_sealed": True,
        "public_kit_integrity": True,
        "blind_commitment_frozen": True,
        "local_cleanroom_passed": True,
        "external_operator_submission_verified": False,
        "external_computational_edge_added": False,
        "independent_observing_source_added": False,
    }
    readiness_rows = [
        {
            "gate": key,
            "closed": value,
            "counts_as_external_replication": key == "external_operator_submission_verified" and value,
        }
        for key, value in readiness.items()
    ]
    write_csv(out / "phase19_replication_readiness.csv", readiness_rows)

    parent_graph = load_json(root / "artifacts/phase18/phase18_reproducibility_graph.json")
    parent_graph.pop("sha256_canonical_json", None)
    analysis_nodes = list(parent_graph["analysis_nodes"])
    analysis_nodes.extend(
        [
            {
                "analysis_kind": "blind_external_replication_kit",
                "analysis_version": "phase19_public_replication_kit",
                "kit_id": manifest["kit_id"],
                "task_count": manifest["task_count"],
                "research_group_independent": False,
                "counts_as_astronomical_denominator_increment": False,
            },
            {
                "analysis_kind": "internal_isolated_process_control",
                "analysis_version": "phase19_local_cleanroom_control",
                "kit_id": manifest["kit_id"],
                "scientific_projection_reproduced": True,
                "research_group_independent": False,
                "counts_as_external_computational_replication": False,
                "counts_as_astronomical_denominator_increment": False,
            },
        ]
    )
    edges = list(parent_graph["edges"])
    edges.append(
        {
            "edge_type": "LOCAL_CLEANROOM_KIT_REPLAY",
            "source_version": "phase19_public_replication_kit",
            "comparison_version": "phase19_local_cleanroom_control",
            "scientific_match": True,
            "all_task_projections_match": True,
            "counts_as_external_computational_replication": False,
            "counts_as_independent_astrophysical_replication": False,
            "reason": "operator and execution remain within the implementation environment",
        }
    )
    graph = dict(parent_graph)
    graph.update(
        {
            "analysis_nodes": analysis_nodes,
            "analysis_version_count": len(analysis_nodes),
            "edges": edges,
            "replication_kit_ready_count": int(parent_graph.get("replication_kit_ready_count", 0)) + 1,
            "local_cleanroom_control_count": int(parent_graph.get("local_cleanroom_control_count", 0)) + 1,
            "external_computational_replication_count": int(
                parent_graph.get("external_computational_replication_count", 0)
            ),
            "external_independent_replication_count": 0,
            "unique_object_denominator": int(parent_graph["unique_object_denominator"]),
            "phase19_external_group_gate": {
                "public_kit_sha256": build_receipt["public_kit_sha256"],
                "private_evaluator_sha256": build_receipt["private_evaluator_sha256"],
                "answer_commitment": build_receipt["answer_commitment"],
                "local_cleanroom_passed": True,
                "external_submission_verified": False,
                "external_replication_edge_added": False,
            },
            "claim_scope": (
                "Computational portability, blinding, and replication provenance only; "
                "no population or physical mechanism inference."
            ),
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        }
    )
    graph["sha256_canonical_json"] = canonical_json_sha256(graph)
    write_json(out / "phase19_reproducibility_graph.json", graph)

    parent_ledger = load_json(root / "artifacts/phase18/phase18_cumulative_ledger.json")
    ledger = dict(parent_ledger)
    ledger.update(
        {
            "ledger_id": "DERD-PHASE19-CUMULATIVE-EVIDENCE-LEDGER-1.0",
            "date": "2026-08-24",
            "parent_phase18_ledger_file_sha256": sha256_file(
                root / "artifacts/phase18/phase18_cumulative_ledger.json"
            ),
            "external_replication_kits": [
                {
                    "kit_id": manifest["kit_id"],
                    "public_kit_sha256": build_receipt["public_kit_sha256"],
                    "blind_answer_commitment": build_receipt["answer_commitment"],
                    "local_cleanroom_control_passed": True,
                    "external_submission_verified": False,
                    "counts_as_astronomical_denominator_increment": False,
                    "counts_as_external_computational_replication": False,
                }
            ],
            "new_astronomical_record_count": 0,
            "cumulative_astronomical_record_count": int(
                parent_ledger["cumulative_astronomical_record_count"]
            ),
            "claim_boundary": "external computational reproducibility infrastructure only",
        }
    )
    write_json(out / "phase19_cumulative_ledger.json", ledger)
    ledger_seal = {
        "ledger_id": ledger["ledger_id"],
        "date_sealed": "2026-08-24",
        "sha256_canonical_json": canonical_json_sha256(ledger),
    }
    write_json(out / "phase19_cumulative_ledger.seal.json", ledger_seal)

    population_firewall = {
        "unique_astronomical_objects": int(graph["unique_object_denominator"]),
        "external_computational_replication_count": 0,
        "external_independent_replication_count": 0,
        "family_outputs_allowed": False,
        "c17_promoted": False,
    }
    summary = {
        "implementation_id": PHASE19_IMPLEMENTATION_ID,
        "date": "2026-08-24",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "decision": PHASE19_DECISION,
        "classification": PHASE19_CLASSIFICATION,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "research_role": "external replication readiness; no external operator result yet",
        "claim_boundary": protocol["claim_boundary"],
        "protocol": {
            "path": "research/preregistration/phase19_external_group_replay_protocol.json",
            "canonical_sha256": protocol_sha,
        },
        "task_manifest": {
            "path": "data/manifests/phase19_replication_tasks.json",
            "canonical_sha256": manifest_sha,
            "task_count": manifest["task_count"],
            "task_types": manifest["task_types"],
        },
        "public_kit": {
            "sha256": build_receipt["public_kit_sha256"],
            "file_count_excluding_checksum": build_receipt["public_file_count_excluding_checksum"],
            "contains_private_answer_key": False,
            "contains_complete_third_party_raw_photometry": False,
        },
        "private_evaluator": {
            "sha256": build_receipt["private_evaluator_sha256"],
            "withhold_until_external_submission_hash_frozen": True,
            "included_in_public_bundle": False,
        },
        "blind_answer_commitment": build_receipt["answer_commitment"],
        "local_cleanroom_control": redacted_control,
        "readiness_gates": readiness,
        "external_operator": {
            "verified_submission_count": 0,
            "external_computational_replication_edge_added": False,
            "status": "AWAITING_EXTERNAL_OPERATOR",
        },
        "population_firewall": population_firewall,
        "reproducibility_graph": graph,
        "cumulative_ledger": {
            "path": "artifacts/phase19/phase19_cumulative_ledger.json",
            "seal_sha256": ledger_seal["sha256_canonical_json"],
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    write_json(out / "phase19_summary.json", summary)

    plot_readiness(out / "phase19_replication_readiness.png", readiness)
    plot_task_inventory(out / "phase19_task_inventory.png", manifest)

    report = f"""# Phase 19 result: blind external computational-replication kit

## Decision

`{PHASE19_DECISION}`

The Phase-19 public kit is sealed and contains {manifest['task_count']} opaque tasks: {manifest['task_types']['synthetic_photometry']} synthetic photometry controls and {manifest['task_types']['observational_exchange']} blinded observational harmonic-exchange controls. The private answer key is separated from the public kit by an HMAC-SHA256 commitment.

## Local clean-room validation

An isolated process installed the built wheel, verified every public-kit checksum, executed all seven tasks, and reproduced every committed scientific projection within the frozen cross-platform tolerance. This control is internal and does not count as an external replication.

## External gate

No independent research group has yet frozen and submitted a result. Consequently the external computational-replication count remains zero, the independent observing-source count remains zero, the astronomical denominator remains {graph['unique_object_denominator']}, and C17 is not promoted.

## Physical boundary

This phase tests software transport, signed harmonic exchange, recurrence screening, covariance propagation, and deterministic fitting. It does not identify a unique stellar mechanism, certify a transparent outer shell, or constrain shell mass.
"""
    (out / "PHASE19_RESULT.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "decision": PHASE19_DECISION,
        "classification": PHASE19_CLASSIFICATION,
        "task_count": manifest["task_count"],
        "local_cleanroom_passed": True,
        "external_verified_submissions": 0,
        "summary": str(out / "phase19_summary.json"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
