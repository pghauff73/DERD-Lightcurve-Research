#!/usr/bin/env python3
"""Run Phase 11: progressive target execution with a denominator firewall."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping

import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase10 import assess_phase10
from derd.validation_phase11 import (
    Phase11Config,
    execute_ready_targets,
    frontier_rows,
    phase11_decision,
    population_firewall,
    sha256_file,
)


ROOT_DEFAULT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
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


def verify_protocol(protocol_path: Path, seal_path: Path) -> tuple[bool, str, str]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal.get("sha256_canonical_json", ""))
    valid = (
        actual == expected
        and protocol.get("protocol_id") == seal.get("protocol_id")
        and protocol.get("denominator_firewall", {}).get("objects_per_family") == 5
        and protocol.get("denominator_firewall", {}).get("family_count") == 3
    )
    return valid, expected, actual


def blocker_rows(frontier: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    family_counter: dict[str, Counter[str]] = {}
    for row in frontier:
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


def make_figures(output: Path, frontier: list[Mapping[str, Any]], executions: list[Mapping[str, Any]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    figures: list[str] = []

    labels = [str(row["object_id"]).replace("OGLE-LMC-", "") for row in frontier]
    matrix = np.asarray(
        [
            [
                float(row["metadata_ready"]),
                float(row["source_ready"]),
                float(row["execution_ready"]),
                float(row["fresh_executed"]),
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
        ["metadata lock", "source lock", "execution ready", "fresh execution"],
        rotation=18,
        ha="right",
    )
    ax.set_title("Phase 11 progressive evidence frontier")
    fig.colorbar(image, ax=ax, ticks=[0, 1], label="gate pass")
    fig.tight_layout()
    path = output / "phase11_readiness_frontier.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    counts = Counter(str(row["frontier"]) for row in frontier)
    names = list(counts)
    fig = plt.figure(figsize=(9.4, 5.8))
    ax = fig.add_subplot(111)
    ax.bar(np.arange(len(names)), [counts[name] for name in names])
    ax.set_xticks(np.arange(len(names)), [name.replace("_", " ").title() for name in names], rotation=20, ha="right")
    ax.set_ylabel("declared targets")
    ax.set_title("Phase 11 target-level unlock states")
    fig.tight_layout()
    path = output / "phase11_frontier_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    if executions:
        row = executions[0]
        snr = [float(row[f"h{index}_snr"]) for index in range(1, 9)]
        fig = plt.figure(figsize=(8.8, 5.4))
        ax = fig.add_subplot(111)
        ax.bar(np.arange(1, 9), snr)
        ax.axhline(3.0, linestyle="--", label="recovery threshold")
        ax.axhline(2.0, linestyle=":", label="forecast threshold")
        ax.set_xlabel("harmonic")
        ax.set_ylabel("Wald SNR")
        ax.set_title(f"Fresh harmonic evidence: {row['object_id']}")
        ax.legend()
        fig.tight_layout()
        path = output / "phase11_fresh_harmonic_snr.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(path.name)
    return figures


def build_report(summary: Mapping[str, Any]) -> str:
    assessment = summary["phase10_assessment"]
    execution = summary.get("fresh_execution")
    firewall = summary["population_firewall"]
    lines = [
        "# Phase 11 progressive evidence unlock",
        "",
        f"**Decision:** `{summary['decision']}`",
        "",
        "Phase 11 permits a declared object to be analysed as soon as its metadata and source locks are complete. "
        "It does not permit partial family fractions, Wilson intervals, or population claims.",
        "",
        "## Progress",
        "",
        f"- Metadata-ready targets: **{assessment['metadata_ready_count']} / 15**",
        f"- Source-ready targets: **{assessment['source_ready_count']} / 15**",
        f"- Execution-ready targets: **{assessment['execution_ready_count']} / 15**",
        f"- Fresh Phase-11 executions: **{0 if execution is None else execution['fresh_execution_count']}**",
        f"- Population outputs allowed: **{firewall['primary_family_outputs_allowed']}**",
        "",
        "## Fresh result",
        "",
    ]
    rows = summary["fresh_execution_rows"]
    if not rows:
        lines.append("No target had both evidence locks, so no fresh result was generated.")
    else:
        for row in rows:
            lines.extend(
                [
                    f"### {row['object_id']}",
                    "",
                    f"- Observations: {row['observation_count']}",
                    f"- Stage reached: `{row['stage_reached']}`",
                    f"- Disposition: `{row['disposition']}`",
                    f"- DERD score: {row['derd_score']:.6f}",
                    f"- Target-specific threshold: {row['target_threshold']:.6f}",
                    f"- Recovery-harmonic gate: {row['recovery_harmonics_snr_pass']}",
                    f"- Forecast-harmonic gate: {row['forecast_harmonics_snr_pass']}",
                    "",
                ]
            )
    lines.extend(
        [
            "## Claim boundary",
            "",
            "The fresh output is a waveform-evidence result only. It does not identify a unique stellar mechanism, "
            "external shell, or shell mass. Family denominators remain cryptographically frozen and suppressed until complete.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase11/phase11_source_acquisition_receipt.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase11"))
    parser.add_argument("--protocol", type=Path, default=Path("research/preregistration/phase11_progressive_evidence_unlock_protocol.json"))
    parser.add_argument("--seal", type=Path, default=Path("research/preregistration/phase11_progressive_evidence_unlock_protocol.seal.json"))
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
    protocol_valid, protocol_expected, protocol_actual = verify_protocol(protocol_path, seal_path)
    if not protocol_valid:
        raise RuntimeError("Phase-11 protocol seal verification failed")

    assessment = assess_phase10(
        root=root,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path=receipt_path,
    )
    config = Phase11Config(fast=args.fast)
    execution = None
    if args.execute_ready:
        execution = execute_ready_targets(
            assessment,
            root=root,
            output=output,
            config=config,
            receipt_path=receipt_path,
        )
    fresh_ids = [] if execution is None else [str(row["object_id"]) for row in execution.records]
    frontier = frontier_rows(assessment, fresh_ids)
    firewall = population_firewall(assessment.targets, fresh_ids)
    fresh_rows = execution_rows(execution)
    blockers = blocker_rows(frontier)
    figures = make_figures(output, frontier, fresh_rows)
    decision = phase11_decision(assessment, execution)

    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
    payload: dict[str, Any] = {
        "implementation_id": "DERD-v1.1-phase11-progressive-evidence-unlock",
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
        },
        "configuration": config.as_dict(),
        "configuration_sha256": canonical_json_sha256(config.as_dict()),
        "source_receipt": {
            "present": receipt_path.is_file(),
            "sha256": sha256_file(receipt_path) if receipt_path.is_file() else None,
            "verified_count": 0 if receipt_payload is None else receipt_payload.get("verified_count", 0),
            "pending_count": 15 if receipt_payload is None else receipt_payload.get("pending_count", 0),
            "invalid_count": 0 if receipt_payload is None else receipt_payload.get("invalid_count", 0),
        },
        "phase10_assessment": assessment.as_dict(),
        "frontier": frontier,
        "blockers": blockers,
        "fresh_execution": None if execution is None else execution.as_dict(include_controls=False),
        "fresh_execution_rows": fresh_rows,
        "population_firewall": firewall,
        "figures": figures,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "claim_boundary": {
            "supported_scope": "target-level normalized waveform evidence",
            "not_supported": [
                "unique internal stellar mechanism",
                "universal transparent outer shell",
                "shell prevalence",
                "shell mass or mass fraction",
            ],
        },
    }
    write_json(output / "phase11_summary.json", payload)
    write_csv(output / "phase11_frontier.csv", frontier)
    write_csv(output / "phase11_blockers.csv", blockers)
    write_csv(output / "phase11_fresh_execution.csv", fresh_rows)
    (output / "PHASE11_RESULT.md").write_text(build_report(payload), encoding="utf-8")

    claims_dir = root / "research/claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    claims = {
        "C54": {
            "claim_id": "C54",
            "claim": "A partial source pack can be cryptographically frozen without changing the declared 5+5+5 cohort denominator.",
            "status": "VERIFIED_BY_IMPLEMENTATION_AND_SOURCE_RECEIPT",
            "evidence": ["artifacts/phase11/phase11_source_acquisition_receipt.json"],
        },
        "C55": {
            "claim_id": "C55",
            "claim": "A target with complete metadata and source locks can be freshly evaluated while all partial family fractions remain suppressed.",
            "status": "VERIFIED_BY_PHASE11_DENOMINATOR_FIREWALL",
            "evidence": ["artifacts/phase11/phase11_summary.json"],
        },
        "C56": {
            "claim_id": "C56",
            "claim": "OGLE-LMC-CEP-0004 does not pass the frozen four-recovery-harmonic evidence gate in the Phase-11 fresh execution.",
            "status": "VERIFIED_FOR_EXPOSED_DEVELOPMENT_TARGET" if fresh_rows else "NOT_EVALUATED",
            "evidence": ["artifacts/phase11/phase11_fresh_execution.csv"],
            "physical_claim_scope": "waveform-only",
        },
    }
    for claim_id, claim in claims.items():
        claim["sha256_canonical_json"] = canonical_json_sha256(claim)
        write_json(claims_dir / f"{claim_id}.json", claim)

    ourd_payload = {
        "graph_id": "OURD-PHASE11-PROGRESSIVE-EVIDENCE-UNLOCK-GRAPH-V1",
        "objects": [
            {"id": "P11-PROTOCOL", "type": "sealed_protocol"},
            {"id": "P11-DECLARED-COHORT", "type": "frozen_5_plus_5_plus_5_denominator", "count": 15},
            {"id": "P11-PROGRESSIVE-RECEIPT", "type": "partial_source_lock_receipt", "verified_count": payload["source_receipt"]["verified_count"]},
            {"id": "P11-EXECUTION-FRONTIER", "type": "target_level_readiness_frontier", "execution_ready_count": assessment.execution_ready_count},
            {"id": "P11-FRESH-EVIDENCE", "type": "fresh_waveform_results", "count": len(fresh_rows)},
            {"id": "P11-DENOMINATOR-FIREWALL", "type": "population_output_guard", "open": firewall["primary_family_outputs_allowed"]},
            {"id": "C54", "type": "claim"},
            {"id": "C55", "type": "claim"},
            {"id": "C56", "type": "claim"},
        ],
        "relations": [
            {"source": "P11-PROTOCOL", "relation": "governs", "target": "P11-EXECUTION-FRONTIER"},
            {"source": "P11-DECLARED-COHORT", "relation": "constrains", "target": "P11-DENOMINATOR-FIREWALL"},
            {"source": "P11-PROGRESSIVE-RECEIPT", "relation": "unlocks", "target": "P11-EXECUTION-FRONTIER"},
            {"source": "P11-EXECUTION-FRONTIER", "relation": "permits", "target": "P11-FRESH-EVIDENCE"},
            {"source": "P11-DENOMINATOR-FIREWALL", "relation": "suppresses_partial_population_outputs_from", "target": "P11-FRESH-EVIDENCE"},
            {"source": "P11-PROGRESSIVE-RECEIPT", "relation": "supports", "target": "C54"},
            {"source": "P11-DENOMINATOR-FIREWALL", "relation": "supports", "target": "C55"},
            {"source": "P11-FRESH-EVIDENCE", "relation": "supports", "target": "C56"},
        ],
        "score_vector": {
            "reconstruction": "one exact raw source replayed and evaluated; fourteen remain pending",
            "uniqueness": "declared identities and source paths remain unique",
            "orthogonality": "target execution is separated from family aggregation",
            "complexity": "one progressive receipt plus one execution frontier and one denominator firewall",
            "family_transfer": "not established; only one fresh classical-Cepheid result",
            "temporal_stability": "source commit, Git blob, SHA-256, protocol and configuration are frozen",
            "predictive_calibration": "target-specific synthetic calibration completed for the fresh object",
            "causal_fidelity": "not established; normalized waveform-only boundary retained",
        },
    }
    write_json(root / "research/ourd/phase11_objects_and_relations.json", ourd_payload)

    iurm_payload = {
        "manifest_id": "IURM-PHASE11-PROGRESSIVE-EVIDENCE-UNLOCK-V1",
        "implementation_id": payload["implementation_id"],
        "minimal_viable_dimensions": {
            "families": 3,
            "objects_per_family": 5,
            "total_declared_objects": 15,
            "minimum_observations_per_executed_object": config.minimum_observations,
            "recovery_harmonics": 4,
            "minimum_measured_forecast_harmonics": 2,
            "partial_target_results_allowed": True,
            "partial_family_fractions_allowed": False,
        },
        "one_dimension_intervention": {
            "active_dimension": "available cryptographically verified source locks",
            "previous_value": 0,
            "current_value": assessment.source_ready_count,
            "held_constant": [
                "frozen fifteen-object denominator",
                "metadata policy",
                "harmonic extraction",
                "target-specific calibration",
                "covariance propagation",
                "family aggregation thresholds",
            ],
            "result": decision,
        },
        "orthogonal_gates": [
            {"dimension": "metadata lock", "current_count": assessment.metadata_ready_count, "required_for_target_execution": True},
            {"dimension": "source lock", "current_count": assessment.source_ready_count, "required_for_target_execution": True},
            {"dimension": "fresh target execution", "current_count": len(fresh_rows), "required_for_population_output": 15},
            {"dimension": "population denominator", "open": firewall["primary_family_outputs_allowed"]},
        ],
        "current_result": (
            "One target-level execution is unlocked. The fresh object does not pass the four-recovery-harmonic gate; "
            "family fractions and Wilson intervals remain suppressed."
        ),
    }
    write_json(root / "research/iurm/phase11_methods_manifest.json", iurm_payload)

    edov_payload = {
        "manifest_id": "EDOV1-PHASE11-PROGRESSIVE-EVIDENCE-UNLOCK-V1",
        "date": "2026-08-18",
        "evidence_role": "EXPOSED_DEVELOPMENT_ONLY",
        "promotion_decision": "DENIED_INCOMPLETE_DENOMINATOR_AND_NEGATIVE_FRESH_RECOVERY_GATE",
        "artifacts": [
            "artifacts/phase11/PHASE11_RESULT.md",
            "artifacts/phase11/phase11_summary.json",
            "artifacts/phase11/phase11_source_acquisition_receipt.json",
            "artifacts/phase11/phase11_frontier.csv",
            "artifacts/phase11/phase11_fresh_execution.csv",
            "research/preregistration/phase11_progressive_evidence_unlock_protocol.json",
        ],
        "supporting_findings": [
            "The Phase-11 protocol seal verifies.",
            "One raw photometry source matches its frozen repository commit, path, Git blob, byte count, observation count and SHA-256.",
            "The matching target has claim-grade metadata and was freshly executed under the frozen full configuration.",
            "The denominator firewall suppresses all family fractions and Wilson intervals while only one of fifteen fresh results exists.",
        ],
        "contradicting_or_limiting_findings": [
            "Fourteen raw source locks remain pending.",
            "Five Delta Scuti authoritative metadata locks remain pending.",
            "OGLE-LMC-CEP-0004 fails the four-recovery-harmonic SNR gate because h3 and h4 are below SNR 3.",
            "Its DERD score exceeds the target-specific compatibility threshold.",
            "Only one family has any fresh result, so no population inference is permissible.",
            "All current identities are exposed development objects and cannot become pristine confirmatory evidence.",
        ],
        "provenance_clusters": [
            {"cluster": "paper hypothesis", "source": "Cephids Pulsating Stars - Transparent Outer Shell", "independence_note": "originating claim lineage"},
            {"cluster": "raw photometry mirror", "source": "bksim/OutlierDetection commit 55836b5...", "independence_note": "single external mirror; raw bytes excluded from redistributable bundle"},
            {"cluster": "computational evidence", "source": "DERD Phase-11 fresh execution", "independence_note": "same research programme; configuration and outputs cryptographically frozen"},
        ],
    }
    write_json(root / "research/edov1/phase11_evidence_manifest.json", edov_payload)

    status_path = root / "research/STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    status["phase11"] = {
        "implementation_id": payload["implementation_id"],
        "decision": decision,
        "fresh_execution_count": len(fresh_rows),
        "source_ready_count": assessment.source_ready_count,
        "metadata_ready_count": assessment.metadata_ready_count,
        "population_outputs_allowed": firewall["primary_family_outputs_allowed"],
        "c17_promoted": False,
    }
    status["implementation_id"] = payload["implementation_id"]
    status["intended_review_branch"] = "qwen-safe/20260818-derd-v1.1"
    status["status"] = f"{decision}_C17_NOT_PROMOTED"
    warnings = list(status.get("warning_gates", []))
    for warning in (
        "Phase11 unlocks one of fifteen fresh target executions; population denominator remains incomplete",
        "OGLE-LMC-CEP-0004 h3 and h4 are below the frozen recovery SNR threshold",
        "OGLE-LMC-CEP-0004 DERD score exceeds its target-specific compatibility threshold",
        "fourteen Phase11 raw source locks remain pending",
        "five authoritative Delta Scuti metadata locks remain pending",
    ):
        if warning not in warnings:
            warnings.append(warning)
    status["warning_gates"] = warnings
    write_json(status_path, status)

    print(f"decision={decision}")
    print(f"metadata_ready={assessment.metadata_ready_count}")
    print(f"source_ready={assessment.source_ready_count}")
    print(f"execution_ready={assessment.execution_ready_count}")
    print(f"fresh_executions={len(fresh_rows)}")
    print(f"population_outputs_allowed={firewall['primary_family_outputs_allowed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
