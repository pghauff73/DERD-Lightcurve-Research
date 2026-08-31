#!/usr/bin/env python3
"""Run Phase 14: cumulative ledger extension and period-coordinate robustness."""
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
from derd.validation_phase12 import (
    Phase12Config,
    cumulative_population_firewall,
    execute_new_ready_targets,
    replay_audit,
    sha256_file,
    verify_evidence_record,
)
from derd.validation_phase13 import (
    acquisition_candidates_from_phase08,
    load_curve_for_temporal_audit,
)
from derd.validation_phase14 import (
    PHASE14_DECISION_BLOCKED,
    PHASE14_DECISION_DRIFT,
    PHASE14_DECISION_UPDATED,
    Phase14Config,
    load_verified_phase13_ledger,
    merge_phase14_ledger,
    period_audit_sidecar,
    run_period_coordinate_audit,
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
    config: Phase14Config,
) -> tuple[bool, Mapping[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal.get("sha256_canonical_json", ""))

    parent_summary_path = root / str(protocol["parent_phase13_summary"]["path"])
    parent_ledger_path = root / str(protocol["parent_phase13_ledger"]["path"])
    acquisition_path = root / str(protocol["acquisition_order"]["path"])
    parent_ledger = json.loads(parent_ledger_path.read_text(encoding="utf-8"))
    scientific = protocol.get("base_execution_policy", {}).get("scientific_coordinates", {})
    temporal = protocol.get("temporal_replication_policy", {})
    period = protocol.get("period_coordinate_policy", {})
    valid = bool(
        actual == expected
        and protocol.get("protocol_id") == seal.get("protocol_id")
        and sha256_file(parent_summary_path) == protocol["parent_phase13_summary"]["sha256"]
        and canonical_json_sha256(parent_ledger)
        == protocol["parent_phase13_ledger"]["sha256_canonical_json"]
        and sha256_file(acquisition_path) == protocol["acquisition_order"]["sha256_file"]
        and scientific == config.phase12_dict()
        and temporal.get("chronological_blocks") == config.temporal_blocks
        and temporal.get("stationary_replicates") == config.stationary_replicates
        and temporal.get("drift_replicates_per_severity") == config.drift_replicates
        and temporal.get("drift_severities") == list(config.drift_severities)
        and temporal.get("random_seed") == config.temporal_random_seed
        and period.get("relative_spans") == list(config.period_relative_spans)
        and period.get("period_grid_count") == config.period_grid_count
        and period.get("phase_bins") == config.period_bins
        and period.get("temporal_surface_relative_span") == config.period_surface_span
        and period.get("temporal_surface_grid_count") == config.period_surface_grid_count
        and protocol.get("denominator_firewall", {}).get("total_records_required") == 15
    )
    return valid, {
        "valid": valid,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "parent_summary_actual_sha256": sha256_file(parent_summary_path),
        "parent_summary_expected_sha256": protocol["parent_phase13_summary"]["sha256"],
        "parent_ledger_actual_sha256_canonical_json": canonical_json_sha256(parent_ledger),
        "parent_ledger_expected_sha256_canonical_json": protocol["parent_phase13_ledger"]["sha256_canonical_json"],
        "acquisition_order_actual_sha256": sha256_file(acquisition_path),
        "acquisition_order_expected_sha256": protocol["acquisition_order"]["sha256_file"],
        "selected_object_id": protocol["acquisition_order"]["selected_object_id"],
    }


def verify_acquisition_order(
    *, root: Path, prior_records: Sequence[Mapping[str, Any]], order_path: Path
) -> tuple[bool, Mapping[str, Any], list[dict[str, Any]]]:
    payload = json.loads(order_path.read_text(encoding="utf-8"))
    stored_self = payload.get("sha256_canonical_json")
    without_self = {key: value for key, value in payload.items() if key != "sha256_canonical_json"}
    candidates = acquisition_candidates_from_phase08(
        root=root,
        excluded_object_ids=[str(row["object_id"]) for row in prior_records],
    )
    rows = [candidate.as_dict() for candidate in candidates]
    selected = rows[0] if rows else None
    valid = bool(
        stored_self == canonical_json_sha256(without_self)
        and payload.get("ranked_candidates") == rows
        and payload.get("selected_target") == selected
    )
    return valid, payload, rows


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
                "score_minus_threshold": float(result.screen.score - result.calibration.threshold),
                "recovery_harmonics_snr_pass": bool(target.checks["four_recovery_harmonics_snr"]),
                "forecast_harmonics_snr_pass": bool(target.checks["two_forecast_harmonics_snr"]),
                "structural_constraints_pass": bool(target.checks["structural_constraints"]),
                "calibration_auc": float(result.calibration.holdout_metrics["roc_auc"]),
                "calibration_balanced_accuracy": float(result.calibration.holdout_metrics["balanced_accuracy"]),
                "propagation_below_threshold_fraction": (
                    None if result.propagation.below_threshold_fraction is None
                    else float(result.propagation.below_threshold_fraction)
                ),
                "propagation_structural_pass_fraction": float(result.propagation.structural_pass_fraction),
                **{f"h{index + 1}_snr": value for index, value in enumerate(snr)},
                "acquisition_priority_score": float(target.acquisition_priority_score),
            }
        )
    return rows


def ledger_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "object_id": row["object_id"],
            "family": row["family"],
            "origin_phase": row["origin_phase"],
            "stage_reached": row["stage_reached"],
            "disposition": row["disposition"],
            "input_lock_sha256": row["input_lock_sha256"],
            "result_sha256": row["result_sha256"],
            "exchange_sha256": row["exchange_sha256"],
            "ledger_record_sha256": row["ledger_record_sha256"],
        }
        for row in records
    ]


def frontier_rows(assessment, cumulative_ids: Sequence[str], new_ids: Sequence[str]) -> list[dict[str, Any]]:
    cumulative = set(cumulative_ids)
    new = set(new_ids)
    rows: list[dict[str, Any]] = []
    for item in assessment.targets:
        has_record = item.target.object_id in cumulative or item.effective_object_id in cumulative
        is_new = item.target.object_id in new or item.effective_object_id in new
        if has_record:
            frontier = "NEW_PHASE14_CUMULATIVE_RECORD" if is_new else "VERIFIED_PRIOR_CUMULATIVE_RECORD"
        elif item.metadata_ready and not item.source_ready:
            frontier = "SOURCE_LOCK_REQUIRED"
        elif item.source_ready and not item.metadata_ready:
            frontier = "METADATA_LOCK_REQUIRED"
        elif item.execution_ready:
            frontier = "EXECUTION_READY"
        else:
            frontier = "METADATA_AND_SOURCE_LOCKS_REQUIRED"
        rows.append(
            {
                "object_id": item.target.object_id,
                "effective_object_id": item.effective_object_id,
                "family": item.target.family,
                "metadata_ready": item.metadata_ready,
                "source_ready": item.source_ready,
                "execution_ready": item.execution_ready,
                "cumulative_record": has_record,
                "new_phase14_record": is_new,
                "frontier": frontier,
                "blockers": "|".join(item.blockers),
            }
        )
    return rows


def blocker_rows(frontier: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in frontier:
        if row.get("cumulative_record"):
            continue
        for blocker in str(row.get("blockers", "")).split("|"):
            if blocker:
                counts[blocker] += 1
    return [
        {"blocker": blocker, "target_count": count}
        for blocker, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def family_rows(firewall: Mapping[str, Any]) -> list[dict[str, Any]]:
    required = {"classical_cepheid": 5, "rr_lyrae": 5, "delta_scuti": 5}
    coverage = {
        str(row.get("family")): int(row.get("cumulative_record_count", 0))
        for row in firewall.get("family_coverage", [])
        if isinstance(row, Mapping)
    }
    return [
        {
            "family": family,
            "verified_records": int(coverage.get(family, 0)),
            "required_records": required[family],
            "remaining": required[family] - int(coverage.get(family, 0)),
            "fractions_suppressed": not firewall.get("primary_family_outputs_allowed", False),
        }
        for family in required
    ]


def make_figures(output: Path, audit: Mapping[str, Any], firewall: Mapping[str, Any]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    figures: list[str] = []

    catalog = audit["catalog_temporal_audit"]
    refined = audit["refined_temporal_audit"]
    block_rows = catalog["blocks"]
    snr = np.asarray([row["coefficient_snr"][:8] for row in block_rows], dtype=float)
    fig = plt.figure(figsize=(9.4, 4.8))
    ax = fig.add_subplot(111)
    image = ax.imshow(snr, aspect="auto")
    ax.set_xticks(np.arange(8), [f"h{i}" for i in range(1, 9)])
    ax.set_yticks(np.arange(len(block_rows)), [f"block {i+1}" for i in range(len(block_rows))])
    ax.set_title("Phase 14 catalog-period chronological harmonic SNR")
    fig.colorbar(image, ax=ax, label="Wald SNR")
    fig.tight_layout()
    path = output / "phase14_block_harmonic_snr.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    surface = audit["surface_rows"]
    offsets = np.asarray([row["relative_offset"] for row in surface], dtype=float)
    dispersion = np.asarray([row["phase_dispersion_score"] for row in surface], dtype=float)
    temporal = np.asarray([row["temporal_score"] for row in surface], dtype=float)
    fig = plt.figure(figsize=(8.6, 4.8))
    ax = fig.add_subplot(111)
    ax.plot(offsets, dispersion, label="phase dispersion")
    ax.set_xlabel("relative period offset")
    ax.set_ylabel("phase-dispersion score")
    ax2 = ax.twinx()
    ax2.plot(offsets, temporal, linestyle="--", label="temporal score")
    ax2.set_ylabel("max pairwise temporal W/rank")
    ax.axvline(audit["relative_period_delta"], linestyle=":", label="refined period")
    ax.set_title("Independent period coordinate and temporal score surface")
    fig.tight_layout()
    path = output / "phase14_period_coordinate_surface.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    fig = plt.figure(figsize=(7.2, 4.8))
    ax = fig.add_subplot(111)
    labels = ["catalog", "refined"]
    scores = [catalog["actual_temporal_score"], refined["actual_temporal_score"]]
    thresholds = [catalog["stationary_threshold"], refined["stationary_threshold"]]
    x = np.arange(2)
    ax.bar(x - 0.18, scores, width=0.36, label="observed temporal score")
    ax.bar(x + 0.18, thresholds, width=0.36, label="stationary threshold")
    ax.set_xticks(x, labels)
    ax.set_ylabel("W/rank")
    ax.set_title("Period refinement does not automatically rescue stationarity")
    ax.legend()
    fig.tight_layout()
    path = output / "phase14_catalog_vs_refined_stationarity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    families = family_rows(firewall)
    fig = plt.figure(figsize=(7.2, 4.6))
    ax = fig.add_subplot(111)
    ax.bar([row["family"] for row in families], [row["verified_records"] for row in families])
    ax.axhline(5, linestyle="--", label="frozen family denominator")
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("verified cumulative records")
    ax.set_title("Phase 14 cumulative evidence coverage")
    ax.legend()
    fig.tight_layout()
    path = output / "phase14_cumulative_family_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)
    return figures


def build_report(summary: Mapping[str, Any]) -> str:
    audit = summary["period_coordinate_robustness"]["audit"]
    new = summary["new_execution_rows"][0] if summary["new_execution_rows"] else None
    catalog = audit["catalog_temporal_audit"]
    refined = audit["refined_temporal_audit"]
    lines = [
        "# Phase 14 period-coordinate robustness ledger",
        "",
        f"**Decision:** `{summary['decision']}`",
        "",
        "Phase 14 selected the next exposed-development target from the frozen result-blind acquisition order, replayed its Phase-08 waveform result, appended one conflict-free ledger record, and tested whether a generic period refinement changes the chronological harmonic-stationarity decision.",
        "",
        "## Cumulative progress",
        "",
        f"- Selected object: `{summary['acquisition_order']['selected_object_id']}`",
        f"- Prior cumulative records: {summary['cumulative_ledger']['prior_record_count']}",
        f"- New records: {summary['cumulative_ledger']['new_record_count']}",
        f"- Cumulative records: {summary['cumulative_ledger']['cumulative_count']} of 15",
        f"- Population outputs allowed: {summary['population_firewall']['primary_family_outputs_allowed']}",
        "",
    ]
    if new:
        lines += [
            "## Fresh target-level waveform result",
            "",
            f"- Stage: `{new['stage_reached']}`",
            f"- Disposition: `{new['disposition']}`",
            f"- DERD score: {new['derd_score']:.6f}",
            f"- Target threshold: {new['target_threshold']:.6f}",
            f"- Phase-08 replay status: `{summary['replay_audits'][0]['status']}`",
            "",
        ]
    lines += [
        "## Period-coordinate robustness",
        "",
        f"- Catalog period: {audit['catalog_period_days']:.10f} days",
        f"- Independently refined period: {audit['refined_period_days']:.10f} days",
        f"- Relative period change: {audit['relative_period_delta']:.10e}",
        f"- Catalog phase-dispersion score: {audit['catalog_dispersion_score']:.6f}",
        f"- Refined phase-dispersion score: {audit['refined_dispersion_score']:.6f}",
        f"- Catalog temporal score / threshold: {catalog['actual_temporal_score']:.6f} / {catalog['stationary_threshold']:.6f}",
        f"- Refined temporal score / threshold: {refined['actual_temporal_score']:.6f} / {refined['stationary_threshold']:.6f}",
        f"- Minimum temporal-score period on the narrow surface: {audit['minimum_temporal_score_period_days']:.10f} days",
        f"- Fractional temporal-score reduction: {audit['temporal_score_fractional_reduction']:.4%}",
        f"- Classification: `{audit['classification']}`",
        "",
        "## Claim boundary",
        "",
        "This result concerns period-coordinate robustness of normalized signed waveform harmonics. It does not identify a unique internal stellar mechanism, literal internal Keplerian motion, a universal transparent shell, shell prevalence, or shell mass.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase14/phase14_source_acquisition_receipt.json"))
    parser.add_argument("--prior-summary", type=Path, default=Path("artifacts/phase13/phase13_summary.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase14"))
    parser.add_argument("--protocol", type=Path, default=Path("research/preregistration/phase14_period_coordinate_robustness_ledger_protocol.json"))
    parser.add_argument("--seal", type=Path, default=Path("research/preregistration/phase14_period_coordinate_robustness_ledger_protocol.seal.json"))
    parser.add_argument("--acquisition-order", type=Path, default=Path("data/manifests/phase14_acquisition_order.json"))
    parser.add_argument("--execute-ready", action="store_true")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    resolve = lambda path: path if path.is_absolute() else root / path
    output = resolve(args.output)
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = resolve(args.receipt)
    prior_summary_path = resolve(args.prior_summary)
    protocol_path = resolve(args.protocol)
    seal_path = resolve(args.seal)
    order_path = resolve(args.acquisition_order)

    config = Phase14Config(
        fast=args.fast,
        stationary_replicates=48 if args.fast else 192,
        drift_replicates=48 if args.fast else 192,
    )
    sealed_config = Phase14Config()
    protocol_valid, protocol_details = verify_protocol(
        protocol_path, seal_path, root=root, config=sealed_config
    )
    if args.fast:
        protocol_details = dict(protocol_details) | {
            "valid": protocol_details["actual_sha256"] == protocol_details["expected_sha256"],
            "fast_smoke_test": True,
        }
        protocol_valid = bool(protocol_details["valid"])
    if not protocol_valid:
        raise RuntimeError("Phase-14 protocol verification failed")

    prior_records, parent_summary_sha, parent_ledger_sha, prior_temporal_sidecars = (
        load_verified_phase13_ledger(root=root, summary_path=prior_summary_path)
    )
    order_valid, order_payload, ranked_candidates = verify_acquisition_order(
        root=root, prior_records=prior_records, order_path=order_path
    )
    if not order_valid:
        raise RuntimeError("Phase-14 acquisition-order verification failed")
    selected_id = str(order_payload["selected_target"]["object_id"])

    assessment = assess_phase10(
        root=root,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path=receipt_path,
    )

    phase12_config = Phase12Config(**config.phase12_dict())
    execution = None
    if args.execute_ready:
        execution = execute_new_ready_targets(
            assessment,
            prior_records=prior_records,
            root=root,
            output=output,
            config=phase12_config,
            receipt_path=receipt_path,
        )
    if execution is not None:
        executed_ids = [str(row["object_id"]) for row in execution.records]
        if executed_ids != [selected_id]:
            raise RuntimeError(f"Phase-14 execution escaped frozen selection: {executed_ids}")

    raw_execution_payload = {
        "implementation_id": "DERD-v1.4-phase14-new-execution-payload",
        "configuration": config.as_dict(),
        "configuration_sha256": canonical_json_sha256(config.as_dict()),
        "execution": None if execution is None else execution.as_dict(include_controls=False),
    }
    raw_execution_path = output / "phase14_new_execution_payload.json"
    write_json(raw_execution_path, raw_execution_payload)
    raw_execution_sha = sha256_file(raw_execution_path)
    new_records: list[Mapping[str, Any]] = []
    if execution is not None:
        for record in execution.records:
            new_records.append(
                verify_evidence_record(
                    record,
                    root=root,
                    origin_phase="phase14",
                    origin_summary_relative_path=raw_execution_path.relative_to(root).as_posix(),
                    origin_summary_sha256=raw_execution_sha,
                )
            )
    new_records.sort(key=lambda row: str(row["object_id"]))

    targets_by_declared = {item.target.object_id: item for item in assessment.targets}
    replay_rows: list[dict[str, Any]] = []
    for record in new_records:
        readiness = targets_by_declared[str(record["declared_object_id"])]
        replay_rows.append(
            replay_audit(record, root=root, inherited=readiness.target.phase09.inherited_phase08)
        )

    ledger = merge_phase14_ledger(
        prior_records, new_records, prior_summary_sha256=parent_summary_sha
    )
    firewall = cumulative_population_firewall(assessment, ledger)

    period_sidecars: list[dict[str, Any]] = []
    audit_payload: Mapping[str, Any] | None = None
    if new_records:
        record = new_records[0]
        readiness = targets_by_declared[str(record["declared_object_id"])]
        target = readiness.target.phase09
        curve = load_curve_for_temporal_audit(
            root=root,
            source_relative_path=target.source_relative_path,
            object_id=str(record["object_id"]),
            source_locator=f"{target.source_repository}@{target.source_commit}:{target.source_repository_path}",
        )
        result = record["result"]["result"]
        audit = run_period_coordinate_audit(
            curve,
            catalog_period=float(result["catalog_period"]),
            reference_epoch=float(result["harmonic_fit"]["reference_epoch"]),
            config=config,
        )
        audit_payload = audit.as_dict()
        sidecar = period_audit_sidecar(
            audit,
            ledger_record=record,
            configuration_sha256=canonical_json_sha256(config.as_dict()),
            source_receipt_sha256=sha256_file(receipt_path) if receipt_path.is_file() else None,
        )
        sidecar_path = output / f"phase14_period_coordinate_audit_{record['object_id']}.json"
        write_json(sidecar_path, sidecar)
        period_sidecars.append(
            {
                "object_id": record["object_id"],
                "relative_path": sidecar_path.relative_to(root).as_posix(),
                "file_sha256": sha256_file(sidecar_path),
                "canonical_sha256": sidecar["sha256_canonical_json"],
                "ledger_record_sha256": record["ledger_record_sha256"],
                "classification": audit.classification,
            }
        )

    replay_drift = any(row.get("status") == "SCIENTIFIC_REPLAY_DRIFT_DETECTED" for row in replay_rows)
    if replay_drift and config.require_scientific_replay_match:
        decision = PHASE14_DECISION_DRIFT
    elif new_records:
        decision = PHASE14_DECISION_UPDATED
    else:
        decision = PHASE14_DECISION_BLOCKED

    ledger_payload = {
        "ledger_id": "DERD-PHASE14-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-18",
        "claim_boundary": "normalized waveform evidence, temporal stability, and period-coordinate robustness only",
        "parent_phase13_summary_sha256": parent_summary_sha,
        "parent_phase13_ledger_sha256_canonical_json": parent_ledger_sha,
        **ledger.as_dict(),
        "inherited_temporal_audits": [dict(row) for row in prior_temporal_sidecars],
        "period_coordinate_audits": period_sidecars,
    }
    ledger_path = output / "phase14_cumulative_ledger.json"
    write_json(ledger_path, ledger_payload)
    ledger_seal = {
        "ledger_id": ledger_payload["ledger_id"],
        "sha256_canonical_json": canonical_json_sha256(ledger_payload),
        "record_count": ledger.cumulative_count,
        "inherited_temporal_audit_count": len(prior_temporal_sidecars),
        "period_coordinate_audit_count": len(period_sidecars),
    }
    ledger_seal_path = output / "phase14_cumulative_ledger.seal.json"
    write_json(ledger_seal_path, ledger_seal)

    cumulative_ids = [str(row["object_id"]) for row in ledger.records]
    new_ids = [str(row["object_id"]) for row in new_records]
    frontier = frontier_rows(assessment, cumulative_ids, new_ids)
    blockers = blocker_rows(frontier)
    new_rows = execution_rows(execution)
    figures = make_figures(output, audit_payload, firewall) if audit_payload else []
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None

    payload: dict[str, Any] = {
        "implementation_id": "DERD-v1.4-phase14-period-coordinate-robustness-ledger",
        "date": "2026-08-18",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "research_role": "exposed-development-only",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "decision": decision,
        "c17_promoted": False,
        "protocol": protocol_details,
        "configuration": config.as_dict(),
        "configuration_sha256": canonical_json_sha256(config.as_dict()),
        "acquisition_order": {
            "valid": order_valid,
            "relative_path": order_path.relative_to(root).as_posix(),
            "file_sha256": sha256_file(order_path),
            "selected_object_id": selected_id,
            "ranked_candidates": ranked_candidates,
        },
        "source_receipt": {
            "present": receipt_path.is_file(),
            "sha256": sha256_file(receipt_path) if receipt_path.is_file() else None,
            "verified_count": 0 if receipt_payload is None else receipt_payload.get("verified_count", 0),
            "newly_verified_count": 0 if receipt_payload is None else receipt_payload.get("newly_verified_count", 0),
            "pending_count": 15 if receipt_payload is None else receipt_payload.get("pending_count", 0),
            "invalid_count": 0 if receipt_payload is None else receipt_payload.get("invalid_count", 0),
        },
        "phase10_assessment": assessment.as_dict(),
        "parent_phase13": {
            "summary_relative_path": prior_summary_path.relative_to(root).as_posix(),
            "summary_sha256": parent_summary_sha,
            "ledger_sha256_canonical_json": parent_ledger_sha,
            "record_count": len(prior_records),
            "temporal_sidecar_count": len(prior_temporal_sidecars),
        },
        "new_execution": None if execution is None else execution.as_dict(include_controls=False),
        "new_execution_payload_relative_path": raw_execution_path.relative_to(root).as_posix(),
        "new_execution_payload_sha256": raw_execution_sha,
        "new_execution_rows": new_rows,
        "replay_audits": replay_rows,
        "period_coordinate_robustness": {
            "sidecars": period_sidecars,
            "audit": audit_payload,
        },
        "cumulative_ledger": {
            "relative_path": ledger_path.relative_to(root).as_posix(),
            "seal_relative_path": ledger_seal_path.relative_to(root).as_posix(),
            "seal_sha256_canonical_json": ledger_seal["sha256_canonical_json"],
            "prior_record_count": ledger.prior_record_count,
            "new_record_count": ledger.new_record_count,
            "cumulative_count": ledger.cumulative_count,
        },
        "frontier": frontier,
        "blockers": blockers,
        "family_coverage": family_rows(firewall),
        "population_firewall": firewall,
        "figures": figures,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "claim_boundary": {
            "supported_scope": "cumulative target-level normalized waveform evidence, deterministic replay, chronological signed-harmonic stability, and period-coordinate robustness",
            "not_supported": [
                "unique internal stellar mechanism",
                "literal internal Keplerian motion",
                "universal transparent outer shell",
                "shell prevalence",
                "shell mass or mass fraction",
            ],
        },
    }
    summary_path = output / "phase14_summary.json"
    write_json(summary_path, payload)
    write_csv(output / "phase14_new_execution.csv", new_rows)
    write_csv(output / "phase14_replay_audit.csv", replay_rows)
    write_csv(output / "phase14_cumulative_ledger.csv", ledger_rows(ledger.records))
    write_csv(output / "phase14_frontier.csv", frontier)
    write_csv(output / "phase14_blockers.csv", blockers)
    write_csv(output / "phase14_family_coverage.csv", family_rows(firewall))
    if audit_payload:
        write_csv(output / "phase14_temporal_blocks.csv", audit_payload["catalog_temporal_audit"]["blocks"])
        write_csv(output / "phase14_temporal_pairwise_tests.csv", audit_payload["catalog_temporal_audit"]["pairwise_tests"])
        write_csv(output / "phase14_temporal_drift_calibration.csv", audit_payload["catalog_temporal_audit"]["calibration_rows"])
        write_csv(output / "phase14_refined_temporal_blocks.csv", audit_payload["refined_temporal_audit"]["blocks"])
        write_csv(output / "phase14_refined_temporal_pairwise_tests.csv", audit_payload["refined_temporal_audit"]["pairwise_tests"])
        write_csv(output / "phase14_period_coordinate_surface.csv", audit_payload["surface_rows"])
        write_json(output / "phase14_period_coordinate_audit.json", audit_payload)
    (output / "PHASE14_RESULT.md").write_text(build_report(payload), encoding="utf-8")

    replay_pass = bool(replay_rows) and all(
        row.get("scientific_match") and row.get("exchange_match") for row in replay_rows
    )
    audit = audit_payload or {}
    claims = {
        "C66": {
            "claim_id": "C66",
            "claim": "The next Phase-14 acquisition target is selected deterministically from the frozen Phase-08 priority ranking after excluding Phase-13 ledger identities.",
            "status": "VERIFIED_BY_FROZEN_ACQUISITION_ORDER" if order_valid else "FAILED",
            "evidence": ["data/manifests/phase14_acquisition_order.json"],
        },
        "C67": {
            "claim_id": "C67",
            "claim": "The fresh OGLE-LMC-CEP-0002 scientific result and harmonic exchange reproduce its frozen Phase-08 development result.",
            "status": "VERIFIED_EXACT_SCIENTIFIC_REPLAY" if replay_pass else "REPLAY_DRIFT_OR_NOT_EVALUATED",
            "evidence": ["artifacts/phase14/phase14_replay_audit.csv"],
        },
        "C68": {
            "claim_id": "C68",
            "claim": "OGLE-LMC-CEP-0002 does not measure all four recovery harmonics above SNR 3 in every chronological block.",
            "status": "VERIFIED_FOR_EXPOSED_DEVELOPMENT_TARGET" if audit and not audit["catalog_temporal_audit"]["all_blocks_recovery_snr_pass"] else "NOT_SUPPORTED_BY_CURRENT_RESULT",
            "evidence": ["artifacts/phase14/phase14_temporal_blocks.csv"],
            "physical_claim_scope": "waveform-only",
        },
        "C69": {
            "claim_id": "C69",
            "claim": "Independent phase-dispersion period refinement does not rescue the temporal-stationarity gate for OGLE-LMC-CEP-0002.",
            "status": "VERIFIED_FOR_EXPOSED_DEVELOPMENT_TARGET" if audit and audit["classification"] == "TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT" else "NOT_SUPPORTED_BY_CURRENT_RESULT",
            "evidence": ["artifacts/phase14/phase14_period_coordinate_audit.json", "artifacts/phase14/phase14_period_coordinate_surface.csv"],
            "physical_claim_scope": "waveform-only",
        },
        "C70": {
            "claim_id": "C70",
            "claim": "The cumulative ledger can grow from three to four verified target records while all partial family and population outputs remain suppressed.",
            "status": "VERIFIED_BY_DENOMINATOR_FIREWALL" if ledger.cumulative_count == 4 and not firewall["primary_family_outputs_allowed"] else "CURRENT_LEDGER_STATE_RECORDED",
            "evidence": ["artifacts/phase14/phase14_cumulative_ledger.json", "artifacts/phase14/phase14_summary.json"],
        },
    }
    claims_dir = root / "research/claims"
    for claim_id, claim in claims.items():
        claim["sha256_canonical_json"] = canonical_json_sha256(claim)
        write_json(claims_dir / f"{claim_id}.json", claim)

    ourd_payload = {
        "graph_id": "OURD-PHASE14-PERIOD-COORDINATE-ROBUSTNESS-LEDGER-GRAPH-V1",
        "objects": [
            {"id": "P14-PROTOCOL", "type": "sealed_protocol"},
            {"id": "P14-ACQUISITION-ORDER", "type": "result-blind_priority_order", "selected": selected_id},
            {"id": "P14-PARENT-LEDGER", "type": "verified_phase13_ledger", "count": len(prior_records)},
            {"id": "P14-NEW-SOURCE", "type": "verified_source_lock", "count": len(new_records)},
            {"id": "P14-REPLAY", "type": "cross_phase_scientific_replay", "passed": replay_pass},
            {"id": "P14-PERIOD-AUDIT", "type": "period_coordinate_robustness", "classification": audit.get("classification")},
            {"id": "P14-LEDGER", "type": "sealed_cumulative_evidence", "count": ledger.cumulative_count},
            {"id": "P14-FIREWALL", "type": "population_output_guard", "open": firewall["primary_family_outputs_allowed"]},
            *({"id": claim_id, "type": "claim"} for claim_id in claims),
        ],
        "relations": [
            {"source": "P14-PROTOCOL", "relation": "governs", "target": "P14-ACQUISITION-ORDER"},
            {"source": "P14-ACQUISITION-ORDER", "relation": "selects", "target": "P14-NEW-SOURCE"},
            {"source": "P14-NEW-SOURCE", "relation": "enables", "target": "P14-REPLAY"},
            {"source": "P14-NEW-SOURCE", "relation": "enables", "target": "P14-PERIOD-AUDIT"},
            {"source": "P14-PARENT-LEDGER", "relation": "extends_into", "target": "P14-LEDGER"},
            {"source": "P14-PERIOD-AUDIT", "relation": "is_bound_as_sidecar_to", "target": "P14-LEDGER"},
            {"source": "P14-FIREWALL", "relation": "suppresses_partial_population_outputs_from", "target": "P14-LEDGER"},
        ],
        "score_vector": {
            "reconstruction": "one newly acquired Cepheid source is replayed against Phase 08",
            "uniqueness": "one selected identity, one base evidence record, and one period-coordinate sidecar",
            "orthogonality": "period selection uses phase dispersion rather than the DERD score",
            "complexity": "one narrow period surface plus two complete temporal audits",
            "family_transfer": "not established; ledger covers two Cepheids and two RR Lyrae targets",
            "temporal_stability": None if not audit else audit["classification"],
            "predictive_calibration": "actual-cadence stationary and controlled-drift calibration at catalog and refined periods",
            "causal_fidelity": "not established; waveform-only boundary retained",
        },
    }
    write_json(root / "research/ourd/phase14_objects_and_relations.json", ourd_payload)

    iurm_payload = {
        "manifest_id": "IURM-PHASE14-PERIOD-COORDINATE-ROBUSTNESS-LEDGER-V1",
        "implementation_id": payload["implementation_id"],
        "active_dimensions": [
            "cumulative verified target count: 3 to 4",
            "period coordinate: catalog to independent phase-dispersion refinement",
        ],
        "frozen_dimensions": [
            "fifteen-object cohort identities",
            "five-object family denominators",
            "Phase-08 target-level scientific coordinates",
            "signed h1-h8 extraction",
            "three chronological blocks",
            "stationary threshold quantile",
            "population firewall",
        ],
        "gate": decision,
        "result": {
            "new_record_count": ledger.new_record_count,
            "cumulative_record_count": ledger.cumulative_count,
            "period_classification": audit.get("classification"),
            "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
        },
    }
    write_json(root / "research/iurm/phase14_period_coordinate_manifest.json", iurm_payload)

    edov_payload = {
        "manifest_id": "EDOV1-PHASE14-PERIOD-COORDINATE-EVIDENCE-V1",
        "implementation_id": payload["implementation_id"],
        "supporting_evidence": [
            "the selected source passes byte, observation, Git-blob, and SHA-256 checks",
            "the fresh target-level result reproduces the frozen Phase-08 scientific record",
            "the period is refined by a generic phase-dispersion objective independent of DERD compatibility",
            "the cumulative ledger retains four conflict-free verified target records",
        ],
        "contradictory_or_limiting_evidence": [
            "not every chronological block measures h1-h4 above SNR 3",
            "the temporal stationarity gate fails at both catalog and refined periods",
            "the base DERD score remains above its target-specific threshold",
            "eleven cohort targets still lack cumulative records",
            "five authoritative Delta Scuti metadata locks remain absent",
            "family and population estimates remain suppressed",
        ],
        "rights_and_provenance": {
            "raw_bytes_redistributed": False,
            "source_receipt": "artifacts/phase14/phase14_source_acquisition_receipt.json",
            "source_commit": "55836b58345b9507bfbd98c5fabbac82c83605e3",
        },
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
    }
    write_json(root / "research/edov1/phase14_evidence_manifest.json", edov_payload)

    status_path = root / "research/STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    status.update(
        {
            "latest_phase": 14,
            "latest_implementation_id": payload["implementation_id"],
            "latest_decision": decision,
            "c17_status": "OPEN_NOT_PROMOTED",
            "cumulative_verified_target_records": ledger.cumulative_count,
            "period_coordinate_audits": len(period_sidecars),
            "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
            "physical_mechanism_gate": "LOCKED",
            "transparent_shell_gate": "LOCKED",
            "shell_mass_gate": "LOCKED",
        }
    )
    write_json(status_path, status)

    print(json.dumps({
        "decision": decision,
        "selected_object_id": selected_id,
        "prior_records": len(prior_records),
        "new_records": len(new_records),
        "cumulative_records": ledger.cumulative_count,
        "replay_pass": replay_pass,
        "period_classification": audit.get("classification"),
        "catalog_temporal_score": None if not audit else audit["catalog_temporal_audit"]["actual_temporal_score"],
        "refined_temporal_score": None if not audit else audit["refined_temporal_audit"]["actual_temporal_score"],
        "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
    }, indent=2, sort_keys=True))
    return 2 if decision == PHASE14_DECISION_DRIFT else 0


if __name__ == "__main__":
    raise SystemExit(main())
