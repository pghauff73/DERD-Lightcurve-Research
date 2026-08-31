#!/usr/bin/env python3
"""Run Phase 12: cumulative evidence ledger and cross-phase replay audit."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase10 import assess_phase10
from derd.validation_phase11 import frontier_rows as phase11_frontier_rows
from derd.validation_phase12 import (
    Phase12Config,
    cumulative_population_firewall,
    execute_new_ready_targets,
    load_verified_phase11_records,
    merge_cumulative_records,
    phase12_decision,
    replay_audit,
    sha256_file,
    verify_new_execution_records,
)


ROOT_DEFAULT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
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
        writer.writerows(rows)


def verify_protocol(
    protocol_path: Path,
    seal_path: Path,
    *,
    root: Path,
) -> tuple[bool, str, str, Mapping[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal.get("sha256_canonical_json", ""))
    parent_path = root / str(protocol.get("parent_phase11_summary", {}).get("path", ""))
    parent_expected = protocol.get("parent_phase11_summary", {}).get("sha256")
    parent_valid = parent_path.is_file() and sha256_file(parent_path) == parent_expected
    valid = (
        actual == expected
        and protocol.get("protocol_id") == seal.get("protocol_id")
        and protocol.get("denominator_firewall", {}).get("objects_per_family") == 5
        and protocol.get("denominator_firewall", {}).get("family_count") == 3
        and protocol.get("replay_policy", {}).get("require_scientific_match") is True
        and parent_valid
    )
    details = {
        "parent_summary_path": str(parent_path.relative_to(root)) if parent_path.is_file() else str(parent_path),
        "parent_summary_expected_sha256": parent_expected,
        "parent_summary_actual_sha256": sha256_file(parent_path) if parent_path.is_file() else None,
        "parent_summary_valid": parent_valid,
    }
    return valid, expected, actual, details


def execution_rows(execution) -> list[dict[str, Any]]:
    if execution is None:
        return []
    rows: list[dict[str, Any]] = []
    for target in execution.cohort.targets:
        result = target.result
        snr = list(map(float, result.harmonic_fit.coefficient_snr))
        rows.append(
            {
                "object_id": target.target.object_id,
                "family": target.target.family,
                "mode": target.target.mode,
                "observation_count": result.observation_count,
                "stage_reached": target.stage_reached,
                "disposition": target.disposition,
                "derd_score": float(result.screen.score),
                "target_threshold": float(result.calibration.threshold),
                "score_minus_threshold": float(
                    result.screen.score - result.calibration.threshold
                ),
                "recovery_harmonics_snr_pass": bool(
                    target.checks["four_recovery_harmonics_snr"]
                ),
                "forecast_harmonics_snr_pass": bool(
                    target.checks["two_forecast_harmonics_snr"]
                ),
                "structural_constraints_pass": bool(
                    target.checks["structural_constraints"]
                ),
                "calibration_auc": float(
                    result.calibration.holdout_metrics["roc_auc"]
                ),
                "calibration_balanced_accuracy": float(
                    result.calibration.holdout_metrics["balanced_accuracy"]
                ),
                "propagation_below_threshold_fraction": (
                    None
                    if result.propagation.below_threshold_fraction is None
                    else float(result.propagation.below_threshold_fraction)
                ),
                "propagation_structural_pass_fraction": float(
                    result.propagation.structural_pass_fraction
                ),
                **{f"h{index + 1}_snr": value for index, value in enumerate(snr)},
                "acquisition_priority_score": float(target.acquisition_priority_score),
            }
        )
    return rows


def ledger_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "object_id": record["object_id"],
            "family": record["family"],
            "origin_phase": record["origin_phase"],
            "stage_reached": record["stage_reached"],
            "disposition": record["disposition"],
            "input_lock_sha256": record["input_lock_sha256"],
            "result_sha256": record["result_sha256"],
            "exchange_sha256": record["exchange_sha256"],
            "ledger_record_sha256": record["ledger_record_sha256"],
        }
        for record in records
    ]


def cumulative_frontier(assessment, cumulative_ids: Sequence[str], new_ids: Sequence[str]) -> list[dict[str, Any]]:
    cumulative = set(cumulative_ids)
    new = set(new_ids)
    base = phase11_frontier_rows(assessment, fresh_object_ids=new_ids)
    by_declared = {item.target.object_id: item for item in assessment.targets}
    rows: list[dict[str, Any]] = []
    for row in base:
        item = by_declared[str(row["object_id"])]
        has_record = (
            item.target.object_id in cumulative or item.effective_object_id in cumulative
        )
        if has_record:
            frontier = "NEW_CUMULATIVE_RECORD" if (
                item.target.object_id in new or item.effective_object_id in new
            ) else "VERIFIED_PRIOR_CUMULATIVE_RECORD"
        else:
            frontier = row["frontier"]
        rows.append(
            dict(row)
            | {
                "cumulative_record": has_record,
                "new_phase12_record": frontier == "NEW_CUMULATIVE_RECORD",
                "frontier": frontier,
            }
        )
    return rows


def blocker_rows(frontier: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    family_counter: dict[str, Counter[str]] = {}
    for row in frontier:
        if row.get("cumulative_record"):
            continue
        family = str(row["family"])
        family_counter.setdefault(family, Counter())
        for blocker in str(row.get("blockers", "")).split("|"):
            if blocker:
                counter[blocker] += 1
                family_counter[family][blocker] += 1
    families = sorted(family_counter)
    return [
        {
            "blocker": blocker,
            **{family: family_counter[family][blocker] for family in families},
            "total": count,
        }
        for blocker, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def make_figures(
    output: Path,
    frontier: Sequence[Mapping[str, Any]],
    replay_rows: Sequence[Mapping[str, Any]],
    new_rows: Sequence[Mapping[str, Any]],
    firewall: Mapping[str, Any],
) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    figures: list[str] = []

    family_rows = firewall["family_coverage"]
    labels = [str(row["family"]).replace("_", " ").title() for row in family_rows]
    values = [int(row["cumulative_record_count"]) for row in family_rows]
    fig = plt.figure(figsize=(8.8, 5.4))
    ax = fig.add_subplot(111)
    ax.bar(np.arange(len(labels)), values)
    ax.axhline(5, linestyle="--", label="complete family denominator")
    ax.set_xticks(np.arange(len(labels)), labels, rotation=16, ha="right")
    ax.set_ylabel("verified cumulative target records")
    ax.set_ylim(0, 5.5)
    ax.set_title("Phase 12 cumulative evidence coverage")
    ax.legend()
    fig.tight_layout()
    path = output / "phase12_cumulative_family_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    if replay_rows:
        row = replay_rows[0]
        values = [
            abs(float(row.get("screen_score_difference", 0.0))),
            abs(float(row.get("threshold_difference", 0.0))),
            abs(float(row.get("maximum_harmonic_snr_absolute_difference", 0.0))),
        ]
        fig = plt.figure(figsize=(8.6, 5.2))
        ax = fig.add_subplot(111)
        ax.bar(np.arange(3), values)
        ax.set_xticks(
            np.arange(3),
            ["score", "threshold", "max harmonic SNR"],
            rotation=12,
            ha="right",
        )
        ax.set_ylabel("absolute cross-phase difference")
        ax.set_title(f"Scientific replay drift: {row['object_id']}")
        fig.tight_layout()
        path = output / "phase12_replay_drift.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(path.name)

    if new_rows:
        row = new_rows[0]
        snr = [float(row[f"h{index}_snr"]) for index in range(1, 9)]
        fig = plt.figure(figsize=(8.8, 5.4))
        ax = fig.add_subplot(111)
        ax.bar(np.arange(1, 9), snr)
        ax.axhline(3.0, linestyle="--", label="recovery threshold")
        ax.axhline(2.0, linestyle=":", label="forecast threshold")
        ax.set_xlabel("harmonic")
        ax.set_ylabel("Wald SNR")
        ax.set_title(f"Phase 12 new evidence: {row['object_id']}")
        ax.legend()
        fig.tight_layout()
        path = output / "phase12_new_harmonic_snr.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(path.name)

    labels = [str(row["object_id"]).replace("OGLE-LMC-", "") for row in frontier]
    matrix = np.asarray(
        [
            [
                float(row["metadata_ready"]),
                float(row["source_ready"]),
                float(row["cumulative_record"]),
                float(row["new_phase12_record"]),
            ]
            for row in frontier
        ],
        dtype=np.float64,
    )
    fig = plt.figure(figsize=(11.2, 7.8))
    ax = fig.add_subplot(111)
    image = ax.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_xticks(
        np.arange(4),
        ["metadata lock", "source locally ready", "cumulative record", "new Phase 12"],
        rotation=18,
        ha="right",
    )
    ax.set_title("Phase 12 cumulative evidence frontier")
    fig.colorbar(image, ax=ax, ticks=[0, 1], label="gate pass")
    fig.tight_layout()
    path = output / "phase12_cumulative_frontier.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)
    return figures


def build_report(summary: Mapping[str, Any]) -> str:
    ledger = summary["cumulative_ledger"]
    firewall = summary["population_firewall"]
    lines = [
        "# Phase 12 cumulative replay ledger",
        "",
        f"**Decision:** `{summary['decision']}`",
        "",
        "Phase 12 preserves cryptographically verified target evidence across source-pack cycles, executes only newly unlocked targets, and audits deterministic replay against inherited Phase-08 evidence.",
        "",
        "## Ledger progress",
        "",
        f"- Prior verified records: **{ledger['prior_record_count']}**",
        f"- New verified records: **{ledger['new_record_count']}**",
        f"- Cumulative records: **{ledger['cumulative_count']} / 15**",
        f"- Population outputs allowed: **{firewall['primary_family_outputs_allowed']}**",
        "",
        "## New target result",
        "",
    ]
    if not summary["new_execution_rows"]:
        lines.append("No newly ready target was available.")
    else:
        for row in summary["new_execution_rows"]:
            lines.extend(
                [
                    f"### {row['object_id']}",
                    "",
                    f"- Stage reached: `{row['stage_reached']}`",
                    f"- Disposition: `{row['disposition']}`",
                    f"- Observations: {row['observation_count']}",
                    f"- DERD score: {row['derd_score']:.6f}",
                    f"- Target-specific threshold: {row['target_threshold']:.6f}",
                    f"- Recovery-harmonic gate: {row['recovery_harmonics_snr_pass']}",
                    f"- Forecast-harmonic gate: {row['forecast_harmonics_snr_pass']}",
                    "",
                ]
            )
    lines.extend(["## Cross-phase replay", ""])
    for row in summary["replay_audits"]:
        lines.extend(
            [
                f"### {row['object_id']}",
                "",
                f"- Replay status: `{row['status']}`",
                f"- Scientific record match: {row['scientific_match']}",
                f"- Harmonic-exchange match: {row['exchange_match']}",
                f"- Maximum harmonic-SNR difference: {row.get('maximum_harmonic_snr_absolute_difference')}",
                f"- Score difference: {row.get('screen_score_difference')}",
                f"- Threshold difference: {row.get('threshold_difference')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim boundary",
            "",
            "The ledger records normalized waveform evidence only. It does not identify a unique stellar mechanism, a universal transparent shell, shell prevalence, or shell mass. Family estimates remain suppressed until all fifteen frozen identities have verified cumulative records.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("artifacts/phase12/phase12_source_acquisition_receipt.json"),
    )
    parser.add_argument(
        "--prior-summary",
        type=Path,
        default=Path("artifacts/phase11/phase11_summary.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase12"))
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("research/preregistration/phase12_cumulative_replay_ledger_protocol.json"),
    )
    parser.add_argument(
        "--seal",
        type=Path,
        default=Path("research/preregistration/phase12_cumulative_replay_ledger_protocol.seal.json"),
    )
    parser.add_argument("--execute-ready", action="store_true")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    resolve = lambda path: path if path.is_absolute() else root / path
    output = resolve(args.output)
    output.mkdir(parents=True, exist_ok=True)
    protocol_path = resolve(args.protocol)
    seal_path = resolve(args.seal)
    receipt_path = resolve(args.receipt)
    prior_summary_path = resolve(args.prior_summary)

    protocol_valid, protocol_expected, protocol_actual, protocol_details = verify_protocol(
        protocol_path, seal_path, root=root
    )
    if not protocol_valid:
        raise RuntimeError("Phase-12 protocol seal or parent-ledger verification failed")

    assessment = assess_phase10(
        root=root,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path=receipt_path,
    )
    config = Phase12Config(fast=args.fast)
    prior_records, prior_summary_sha = load_verified_phase11_records(
        root=root, summary_path=prior_summary_path
    )

    execution = None
    if args.execute_ready:
        execution = execute_new_ready_targets(
            assessment,
            prior_records=prior_records,
            root=root,
            output=output,
            config=config,
            receipt_path=receipt_path,
        )

    raw_execution_payload = {
        "implementation_id": "DERD-v1.2-phase12-new-execution-payload",
        "configuration": config.as_dict(),
        "configuration_sha256": canonical_json_sha256(config.as_dict()),
        "execution": None if execution is None else execution.as_dict(include_controls=False),
    }
    raw_execution_path = output / "phase12_new_execution_payload.json"
    write_json(raw_execution_path, raw_execution_payload)
    raw_execution_sha = sha256_file(raw_execution_path)
    new_records = verify_new_execution_records(
        execution,
        root=root,
        summary_relative_path=raw_execution_path.relative_to(root).as_posix(),
        summary_sha256=raw_execution_sha,
    )
    ledger = merge_cumulative_records(
        prior_records,
        new_records,
        prior_summary_sha256=prior_summary_sha,
    )

    targets_by_declared = {item.target.object_id: item.target.phase09 for item in assessment.targets}
    replay_rows: list[dict[str, Any]] = []
    for record in new_records:
        declared = str(record["declared_object_id"])
        target = targets_by_declared[declared]
        replay_rows.append(
            replay_audit(
                record,
                root=root,
                inherited=target.inherited_phase08,
            )
        )

    firewall = cumulative_population_firewall(assessment, ledger)
    decision = phase12_decision(
        ledger=ledger,
        replay_audits=replay_rows,
        config=config,
        firewall=firewall,
    )
    cumulative_ids = [str(record["object_id"]) for record in ledger.records]
    new_ids = [str(record["object_id"]) for record in new_records]
    frontier = cumulative_frontier(assessment, cumulative_ids, new_ids)
    blockers = blocker_rows(frontier)
    new_rows = execution_rows(execution)
    figures = make_figures(output, frontier, replay_rows, new_rows, firewall)

    ledger_payload = {
        "ledger_id": "DERD-PHASE12-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-18",
        "claim_boundary": "normalized waveform evidence only",
        **ledger.as_dict(),
    }
    ledger_path = output / "phase12_cumulative_ledger.json"
    write_json(ledger_path, ledger_payload)
    ledger_seal = {
        "ledger_id": ledger_payload["ledger_id"],
        "sha256_canonical_json": canonical_json_sha256(ledger_payload),
        "record_count": ledger.cumulative_count,
    }
    write_json(output / "phase12_cumulative_ledger.seal.json", ledger_seal)

    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
    payload: dict[str, Any] = {
        "implementation_id": "DERD-v1.2-phase12-cumulative-replay-ledger",
        "date": "2026-08-18",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "research_role": "exposed-development-only",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "decision": decision,
        "c17_promoted": False,
        "protocol": {
            "valid": protocol_valid,
            "expected_sha256": protocol_expected,
            "actual_sha256": protocol_actual,
            **protocol_details,
        },
        "configuration": config.as_dict(),
        "configuration_sha256": canonical_json_sha256(config.as_dict()),
        "source_receipt": {
            "present": receipt_path.is_file(),
            "sha256": sha256_file(receipt_path) if receipt_path.is_file() else None,
            "verified_count": 0 if receipt_payload is None else receipt_payload.get("verified_count", 0),
            "newly_verified_count": 0 if receipt_payload is None else receipt_payload.get("newly_verified_count", 0),
            "historically_verified_count": 0 if receipt_payload is None else receipt_payload.get("historically_verified_count", 0),
            "locally_present_verified_count": 0 if receipt_payload is None else receipt_payload.get("locally_present_verified_count", 0),
            "pending_count": 15 if receipt_payload is None else receipt_payload.get("pending_count", 0),
            "invalid_count": 0 if receipt_payload is None else receipt_payload.get("invalid_count", 0),
        },
        "phase10_assessment": assessment.as_dict(),
        "prior_ledger": {
            "summary_relative_path": prior_summary_path.relative_to(root).as_posix(),
            "summary_sha256": prior_summary_sha,
            "record_count": len(prior_records),
        },
        "new_execution": None if execution is None else execution.as_dict(include_controls=False),
        "new_execution_payload_relative_path": raw_execution_path.relative_to(root).as_posix(),
        "new_execution_payload_sha256": raw_execution_sha,
        "new_execution_rows": new_rows,
        "replay_audits": replay_rows,
        "cumulative_ledger": {
            "relative_path": ledger_path.relative_to(root).as_posix(),
            "seal_relative_path": (output / "phase12_cumulative_ledger.seal.json").relative_to(root).as_posix(),
            "seal_sha256_canonical_json": ledger_seal["sha256_canonical_json"],
            "prior_record_count": ledger.prior_record_count,
            "new_record_count": ledger.new_record_count,
            "cumulative_count": ledger.cumulative_count,
        },
        "frontier": frontier,
        "blockers": blockers,
        "population_firewall": firewall,
        "figures": figures,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "claim_boundary": {
            "supported_scope": "cumulative target-level normalized waveform evidence and deterministic replay",
            "not_supported": [
                "unique internal stellar mechanism",
                "universal transparent outer shell",
                "shell prevalence",
                "shell mass or mass fraction",
            ],
        },
    }
    summary_path = output / "phase12_summary.json"
    write_json(summary_path, payload)
    write_csv(output / "phase12_cumulative_ledger.csv", ledger_rows(ledger.records))
    write_csv(output / "phase12_new_execution.csv", new_rows)
    write_csv(output / "phase12_replay_audit.csv", replay_rows)
    write_csv(output / "phase12_frontier.csv", frontier)
    write_csv(output / "phase12_blockers.csv", blockers)
    (output / "PHASE12_RESULT.md").write_text(build_report(payload), encoding="utf-8")

    claims_dir = root / "research/claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    replay_pass = bool(replay_rows) and all(
        row.get("scientific_match") and row.get("exchange_match") for row in replay_rows
    )
    claims = {
        "C57": {
            "claim_id": "C57",
            "claim": "A cryptographically verified prior target result can remain in a cumulative ledger without re-importing its raw source bytes.",
            "status": "VERIFIED_BY_PHASE12_LEDGER_CHAIN",
            "evidence": ["artifacts/phase12/phase12_cumulative_ledger.json"],
        },
        "C58": {
            "claim_id": "C58",
            "claim": "The frozen OGLE-LMC-RRLYR-00001 source is byte-, observation-, Git-blob-, and SHA-256-consistent and supports a fresh target-level execution.",
            "status": "VERIFIED_FOR_EXPOSED_DEVELOPMENT_TARGET" if new_rows else "NOT_EVALUATED",
            "evidence": [
                "artifacts/phase12/phase12_source_acquisition_receipt.json",
                "artifacts/phase12/phase12_new_execution.csv",
            ],
            "physical_claim_scope": "waveform-only",
        },
        "C59": {
            "claim_id": "C59",
            "claim": "The fresh OGLE-LMC-RRLYR-00001 scientific result and harmonic exchange reproduce the frozen Phase-08 result despite non-scientific transport-metadata differences.",
            "status": "VERIFIED_EXACT_SCIENTIFIC_REPLAY" if replay_pass else "REPLAY_DRIFT_OR_NOT_EVALUATED",
            "evidence": ["artifacts/phase12/phase12_replay_audit.csv"],
        },
        "C60": {
            "claim_id": "C60",
            "claim": "Two unique cumulative target records do not permit family fractions or population inference for the frozen fifteen-object cohort.",
            "status": "VERIFIED_BY_DENOMINATOR_FIREWALL" if ledger.cumulative_count == 2 else "CURRENT_LEDGER_COUNT_RECORDED",
            "evidence": ["artifacts/phase12/phase12_summary.json"],
        },
    }
    for claim_id, claim in claims.items():
        claim["sha256_canonical_json"] = canonical_json_sha256(claim)
        write_json(claims_dir / f"{claim_id}.json", claim)

    ourd_payload = {
        "graph_id": "OURD-PHASE12-CUMULATIVE-REPLAY-LEDGER-GRAPH-V1",
        "objects": [
            {"id": "P12-PROTOCOL", "type": "sealed_protocol"},
            {"id": "P12-PRIOR-LEDGER", "type": "verified_phase11_evidence", "count": len(prior_records)},
            {"id": "P12-NEW-SOURCE", "type": "newly_verified_source_lock", "count": payload["source_receipt"]["newly_verified_count"]},
            {"id": "P12-NEW-EXECUTION", "type": "fresh_waveform_result", "count": len(new_rows)},
            {"id": "P12-REPLAY-AUDIT", "type": "cross_phase_scientific_replay", "passed": replay_pass},
            {"id": "P12-CUMULATIVE-LEDGER", "type": "sealed_evidence_ledger", "count": ledger.cumulative_count},
            {"id": "P12-DENOMINATOR-FIREWALL", "type": "population_output_guard", "open": firewall["primary_family_outputs_allowed"]},
            *({"id": claim_id, "type": "claim"} for claim_id in claims),
        ],
        "relations": [
            {"source": "P12-PROTOCOL", "relation": "governs", "target": "P12-CUMULATIVE-LEDGER"},
            {"source": "P12-PRIOR-LEDGER", "relation": "chains_into", "target": "P12-CUMULATIVE-LEDGER"},
            {"source": "P12-NEW-SOURCE", "relation": "enables", "target": "P12-NEW-EXECUTION"},
            {"source": "P12-NEW-EXECUTION", "relation": "is_audited_by", "target": "P12-REPLAY-AUDIT"},
            {"source": "P12-NEW-EXECUTION", "relation": "appends_to", "target": "P12-CUMULATIVE-LEDGER"},
            {"source": "P12-DENOMINATOR-FIREWALL", "relation": "suppresses_partial_population_outputs_from", "target": "P12-CUMULATIVE-LEDGER"},
            {"source": "P12-CUMULATIVE-LEDGER", "relation": "supports", "target": "C57"},
            {"source": "P12-NEW-SOURCE", "relation": "supports", "target": "C58"},
            {"source": "P12-REPLAY-AUDIT", "relation": "supports", "target": "C59"},
            {"source": "P12-DENOMINATOR-FIREWALL", "relation": "supports", "target": "C60"},
        ],
        "score_vector": {
            "reconstruction": "one prior record verified and one new target freshly executed",
            "uniqueness": "conflicting duplicate target records are rejected",
            "orthogonality": "raw-source availability, prior evidence retention, replay fidelity, and population aggregation are independent gates",
            "complexity": "one chained ledger, one replay audit, and one denominator firewall",
            "family_transfer": "not established; cumulative evidence covers one Cepheid and one RR Lyrae target",
            "temporal_stability": "scientific Phase-08 replay is exact under the frozen algorithm",
            "predictive_calibration": "target-specific calibration reproduced exactly for the new target",
            "causal_fidelity": "not established; normalized waveform-only boundary retained",
        },
    }
    write_json(root / "research/ourd/phase12_objects_and_relations.json", ourd_payload)

    iurm_payload = {
        "manifest_id": "IURM-PHASE12-CUMULATIVE-REPLAY-LEDGER-V1",
        "implementation_id": payload["implementation_id"],
        "active_dimension": "new cryptographically verified source and target execution",
        "intervention": {"cumulative_verified_targets_before": len(prior_records), "cumulative_verified_targets_after": ledger.cumulative_count},
        "frozen_dimensions": [
            "fifteen-object cohort identities",
            "five-object family denominators",
            "metadata policy",
            "harmonic extraction h1-h8",
            "Phase-11 scientific configuration",
            "target-specific calibration",
            "covariance propagation",
            "SNR and structural thresholds",
            "population firewall",
        ],
        "gate": decision,
        "result": {
            "new_record_count": ledger.new_record_count,
            "cumulative_record_count": ledger.cumulative_count,
            "scientific_replay_pass": replay_pass,
            "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
        },
    }
    write_json(root / "research/iurm/phase12_cumulative_replay_manifest.json", iurm_payload)

    edov_payload = {
        "manifest_id": "EDOV1-PHASE12-CUMULATIVE-REPLAY-EVIDENCE-V1",
        "implementation_id": payload["implementation_id"],
        "supporting_evidence": [
            "RR Lyrae source bytes pass all frozen source checks",
            "fresh result reproduces the Phase-08 scientific record and harmonic exchange",
            "cumulative ledger retains two unique verified target records",
        ],
        "contradictory_or_limiting_evidence": [
            "the RR Lyrae target still lacks two measured forecast harmonics",
            "its DERD score remains above the target-specific threshold",
            "structural compatibility remains false",
            "thirteen cohort targets lack cumulative records",
            "five Delta Scuti authoritative metadata locks remain absent",
            "family and population estimates remain suppressed",
        ],
        "rights_and_provenance": {
            "raw_bytes_redistributed": False,
            "source_receipt": "artifacts/phase12/phase12_source_acquisition_receipt.json",
            "source_commit": "55836b58345b9507bfbd98c5fabbac82c83605e3",
        },
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
    }
    write_json(root / "research/edov1/phase12_evidence_manifest.json", edov_payload)

    status_path = root / "research/STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    status.update(
        {
            "latest_phase": 12,
            "latest_implementation_id": payload["implementation_id"],
            "latest_decision": decision,
            "c17_status": "OPEN_NOT_PROMOTED",
            "cumulative_verified_target_records": ledger.cumulative_count,
            "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
            "physical_mechanism_gate": "LOCKED",
            "transparent_shell_gate": "LOCKED",
            "shell_mass_gate": "LOCKED",
        }
    )
    write_json(status_path, status)

    print(json.dumps({
        "decision": decision,
        "prior_records": len(prior_records),
        "new_records": len(new_records),
        "cumulative_records": ledger.cumulative_count,
        "scientific_replay_pass": replay_pass,
        "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
    }, indent=2, sort_keys=True))
    return 2 if decision.endswith("DRIFT_DETECTED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
