#!/usr/bin/env python3
"""Run the Phase-09 claim-grade cohort preflight and, when ready, execution.

The default mode is safe: it audits the frozen 15-object cohort, validates the
protocol seal, verifies inherited Phase-08 records, and suppresses family-level
primary outputs while any required source or metadata dimension is incomplete.
Use --execute-ready only after the preflight reports cohort_execution_ready=true.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import sys
from typing import Any

import numpy as np

from derd.harmonic_exchange import write_harmonic_exchange
from derd.validation_phase07 import Phase07Config
from derd.validation_phase08 import Phase08Config, Phase08Target, assess_cohort
from derd.validation_phase09 import (
    Phase09Assessment,
    assess_phase09,
    synthetic_governance_control,
    wilson_interval,
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def readiness_rows(assessment: Phase09Assessment) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in assessment.target_readiness:
        rows.append({
            "object_id": item.target.object_id,
            "family": item.target.family,
            "mode": item.target.mode,
            "period_days": item.target.catalog_period_days,
            "period_evidence_grade": item.target.period_evidence_grade,
            "mode_evidence_grade": item.target.mode_evidence_grade,
            "metadata_identity_status": item.target.metadata_identity_status,
            "expected_observations": item.target.source_observation_count,
            "actual_observations": item.source_actual_observation_count,
            "metadata_ready": item.metadata_ready,
            "source_ready": item.source_ready,
            "cached_result_ready": item.cached_result_ready,
            "executable_now": item.executable_now,
            "source_sha256_frozen": item.checks["source_sha256_frozen"],
            "acquisition_receipt_verified": item.acquisition_receipt_verified,
            "blocker_count": len(item.blockers),
            "blockers": ";".join(item.blockers),
        })
    return rows


def blocker_rows(assessment: Phase09Assessment) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    for item in assessment.target_readiness:
        for blocker in item.blockers:
            row = counts.setdefault(blocker, {family: 0 for family in assessment.family_counts})
            row[item.target.family] += 1
    rows: list[dict[str, Any]] = []
    for blocker in sorted(counts):
        family_counts = counts[blocker]
        rows.append({
            "blocker": blocker,
            **family_counts,
            "total": sum(family_counts.values()),
        })
    return sorted(rows, key=lambda row: (-row["total"], row["blocker"]))


def execute_complete_cohort(
    assessment: Phase09Assessment,
    *,
    root: Path,
    output: Path,
    fast: bool,
) -> dict[str, Any]:
    if not assessment.cohort_execution_ready:
        raise RuntimeError("Phase-09 cohort is not execution-ready")

    target_config = Phase07Config(
        synthetic_samples_per_class=96,
        propagation_draws=2048,
        observation_sweep_counts=(),
        observation_sweep_repetitions=1,
        minimum_observations=240,
        period_grid_count=101,
    )
    if fast:
        target_config = replace(
            target_config,
            synthetic_samples_per_class=24,
            propagation_draws=256,
            period_grid_count=51,
        )
    converted: list[Phase08Target] = []
    for item in assessment.target_readiness:
        target = item.target
        if item.effective_expected_sha256 is None:
            raise RuntimeError(f"missing frozen SHA-256 for {target.object_id}")
        converted.append(Phase08Target(
            object_id=target.object_id,
            family=target.family,
            mode=target.mode,
            catalog_period_days=target.catalog_period_days,
            period_evidence_grade=target.period_evidence_grade,
            source_relative_path=target.source_relative_path,
            source_repository_path=target.source_repository_path,
            source_git_blob_sha1=target.source_git_blob_sha1,
            source_sha256=item.effective_expected_sha256,
            source_byte_count=target.source_byte_count,
            source_repository=target.source_repository,
            source_commit=target.source_commit,
            period_source=target.period_source,
            evidence_role=target.evidence_role,
        ))
    cohort = assess_cohort(
        converted,
        root=root,
        config=Phase08Config(
            target_config=target_config,
            minimum_objects_per_family_for_population_inference=5,
            minimum_total_objects_for_population_inference=15,
        ),
    )

    exchange_dir = output / "harmonic_exchange"
    for item in cohort.targets:
        target = item.target
        exchange = item.result.harmonic_fit.to_exchange(
            object_id=target.object_id,
            time_unit="day",
            value_unit="relative_flux",
            source_locator=target.source_locator,
            source_sha256=target.source_sha256,
            metadata={
                "phase": "09",
                "family": target.family,
                "mode": target.mode,
                "catalog_period_days": target.catalog_period_days,
                "period_evidence_grade": target.period_evidence_grade,
                "period_source": target.period_source,
                "evidence_role": target.evidence_role,
                "physical_claim_scope": "waveform-only",
            },
        )
        write_harmonic_exchange(exchange_dir / f"{target.object_id}.json", exchange)

    family_outputs: list[dict[str, Any]] = []
    for family_row in cohort.family_summary:
        family = family_row["family"]
        n = int(family_row["object_count"])
        row: dict[str, Any] = dict(family_row)
        for label, count_key in (
            ("recovery", "recovery_ready_count"),
            ("forecast", "forecast_measured_count"),
            ("structural", "structurally_compatible_count"),
            ("qualified", "qualified_count"),
        ):
            count = int(row[count_key])
            low, high = wilson_interval(count, n)
            row[f"{label}_fraction"] = count / n
            row[f"{label}_wilson95_low"] = low
            row[f"{label}_wilson95_high"] = high
        family_outputs.append(row)
    return {
        "status": "COMPLETE_COHORT_EXECUTED",
        "cohort": cohort.as_dict(include_controls=False),
        "primary_family_outputs": family_outputs,
    }


def make_figures(output: Path, assessment: Phase09Assessment) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    items = list(assessment.target_readiness)
    labels = [item.target.object_id.replace("OGLE-LMC-", "") for item in items]
    matrix = np.asarray([
        [
            float(item.metadata_ready),
            float(item.source_ready),
            float(item.cached_result_ready),
            float(item.executable_now),
        ]
        for item in items
    ])
    figures: list[str] = []

    fig = plt.figure(figsize=(10.8, 7.2))
    ax = fig.add_subplot(111)
    image = ax.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(items)), labels)
    ax.set_xticks(
        np.arange(4),
        ["claim-grade metadata", "source replay", "verified cached result", "executable now"],
        rotation=20,
        ha="right",
    )
    ax.set_title("Phase 09 readiness matrix")
    fig.colorbar(image, ax=ax, ticks=[0, 1], label="gate pass")
    fig.tight_layout()
    path = output / "phase09_readiness_matrix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    blockers = blocker_rows(assessment)
    fig = plt.figure(figsize=(11.0, 6.8))
    ax = fig.add_subplot(111)
    display = blockers[:12]
    names = [row["blocker"].replace("_", " ").title() for row in display]
    values = [row["total"] for row in display]
    ax.barh(np.arange(len(display)), values)
    ax.set_yticks(np.arange(len(display)), names)
    ax.invert_yaxis()
    ax.set_xlabel("affected declared targets")
    ax.set_title("Phase 09 blockers retained by EDOv1")
    fig.tight_layout()
    path = output / "phase09_blocker_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    families = list(assessment.partial_family_summary)
    fig = plt.figure(figsize=(9.2, 5.8))
    ax = fig.add_subplot(111)
    x = np.arange(len(families))
    width = 0.25
    ax.bar(x - width, [row["declared_objects"] for row in families], width, label="declared")
    ax.bar(x, [row["metadata_ready_objects"] for row in families], width, label="metadata ready")
    ax.bar(x + width, [row["verified_result_objects"] for row in families], width, label="verified result")
    ax.set_xticks(x, [row["family"].replace("_", " ").title() for row in families])
    ax.set_ylabel("objects")
    ax.set_title("Phase 09 family evidence coverage")
    ax.legend()
    fig.tight_layout()
    path = output / "phase09_family_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))
    return figures


def build_report(summary: dict[str, Any]) -> str:
    assessment = summary["assessment"]
    lines = [
        "# Phase 09 result: claim-grade multi-family development cohort",
        "",
        "## Decision",
        "",
        f"`{assessment['decision']}`",
        "",
        "Phase 09 is implemented as a hard-gated 5+5+5 development cohort. The frozen protocol seal, declared population, inherited Phase-08 evidence, source acquisition state, and period/mode provenance are audited independently. Family-level primary fractions are suppressed until all 15 identities are replayable and claim-grade.",
        "",
        "## Gate state",
        "",
        "| Gate | Result |",
        "|---|---:|",
        f"| Protocol seal valid | {assessment['protocol_valid']} |",
        f"| Cohort structure 5+5+5 valid | {assessment['cohort_structure_ready']} |",
        f"| All period/mode identities claim-grade | {assessment['cohort_metadata_ready']} |",
        f"| All source bytes replay-ready | {assessment['cohort_sources_ready']} |",
        f"| Acquisition receipt present | {assessment['acquisition_receipt_present']} |",
        f"| Acquisition receipt header valid | {assessment['acquisition_receipt_header_valid']} |",
        f"| Receipt-frozen source objects | {assessment['acquisition_receipt_verified_count']} / 15 |",
        f"| Verified inherited object results | {assessment['inherited_result_count']} / 15 |",
        f"| Primary outputs suppressed | {assessment['primary_outputs_suppressed']} |",
        "",
        "## Family coverage",
        "",
        "| Family | Declared | Metadata ready | Source ready | Verified result | Recovery-ready in inherited evidence | Forecast-measured in inherited evidence | Qualified in inherited evidence |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in assessment["partial_family_summary"]:
        lines.append(
            f"| {row['family']} | {row['declared_objects']} | {row['metadata_ready_objects']} | "
            f"{row['source_ready_objects']} | {row['verified_result_objects']} | "
            f"{row['recovery_ready_count']} | {row['forecast_measured_count']} | {row['qualified_count']} |"
        )
    lines.extend([
        "",
        "These are evidence-availability counts, not population estimates. No denominator-5 family fraction is reported while the cohort is incomplete.",
        "",
        "## Target blockers",
        "",
        "| Object | Family | Metadata | Source | Cached result | Principal blockers |",
        "|---|---|:---:|:---:|:---:|---|",
    ])
    for item in assessment["target_readiness"]:
        blockers = ", ".join(item["blockers"]) or "none"
        lines.append(
            f"| {item['target']['object_id']} | {item['target']['family']} | "
            f"{'pass' if item['metadata_ready'] else 'block'} | "
            f"{'pass' if item['source_ready'] else 'block'} | "
            f"{'yes' if item['cached_result_ready'] else 'no'} | {blockers} |"
        )
    if summary.get("execution") is not None:
        lines.extend([
            "",
            "## Completed cohort execution",
            "",
            "All source and metadata gates passed and the unchanged Phase-08 object gate was executed for all fifteen identities. The resulting family fractions and Wilson intervals are recorded in the machine-readable execution object.",
        ])
    lines.extend([
        "",
        "## Main research finding",
        "",
        "The most important Phase-09 result is a provenance failure that would otherwise be easy to hide. The Cepheid and RR Lyrae coordinates are externally cross-checked, but the selected Delta Scuti mirror identities still lack an authoritative old-to-current catalog crosswalk and mode assignment. The release therefore refuses to relabel legacy PeriodLS coordinates as claim-grade periods.",
        "",
        "Raw mirror bytes are also excluded from the distributable package. The acquisition tool can freeze them locally by Git commit, repository path, Git blob SHA-1, byte count, and SHA-256, but the current isolated runtime could not complete that network operation.",
        "",
        "## Synthetic governance control",
        "",
        "A deterministic 15-object non-astrophysical control verifies that the aggregation code computes family fractions and Wilson intervals only after a complete cohort is supplied. It is a software control, not DERD evidence.",
        "",
        "## Scientific boundary",
        "",
        "The paper's normalized waveform removes the absolute mass scale. Phase 09 therefore concerns waveform compatibility only. It cannot identify an internal orbital mechanism, establish a universal transparent outer shell, or estimate shell mass.",
        "",
        "## Next executable action",
        "",
        "Resolve five Delta Scuti identities against an authoritative catalog, freeze their official periods and singlemode/multimode labels, retrieve and hash all 15 raw files, then invoke this unchanged runner with `--execute-ready`. Until then, C17 remains open and unpromoted.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase09_development_cohort.json"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("research/preregistration/phase09_multifamily_development_protocol.json"),
    )
    parser.add_argument(
        "--seal",
        type=Path,
        default=Path("research/preregistration/phase09_multifamily_development_protocol.seal.json"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("artifacts/phase09/phase09_acquisition_receipt.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase09"))
    parser.add_argument("--execute-ready", action="store_true")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    output.mkdir(parents=True, exist_ok=True)
    assessment = assess_phase09(
        root=root,
        manifest_path=args.manifest,
        protocol_path=args.protocol,
        seal_path=args.seal,
        acquisition_receipt_path=args.receipt,
    )
    execution: dict[str, Any] | None = None
    if args.execute_ready:
        execution = execute_complete_cohort(
            assessment,
            root=root,
            output=output,
            fast=args.fast,
        )

    readiness = readiness_rows(assessment)
    blockers = blocker_rows(assessment)
    control = synthetic_governance_control()
    figures = make_figures(output, assessment)
    assessment_payload = assessment.as_dict()
    if execution is not None:
        assessment_payload["completed_result_count"] = len(assessment.target_readiness)
        assessment_payload["primary_outputs_suppressed"] = False
        assessment_payload["primary_family_outputs"] = execution["primary_family_outputs"]
        assessment_payload["decision"] = "PHASE09_DEVELOPMENT_COHORT_COMPLETE_C17_NOT_PROMOTED"
    summary = {
        "implementation_id": "DERD-v0.9-phase09-claim-grade-development-cohort",
        "date": "2026-08-17",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "research_role": "exposed-development-only",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "assessment": assessment_payload,
        "execution": execution,
        "synthetic_governance_control": control,
        "figures": figures,
    }
    write_json(output / "phase09_summary.json", summary)
    write_json(output / "phase09_governance_control.json", control)
    write_csv(output / "phase09_target_readiness.csv", readiness)
    write_csv(output / "phase09_blockers.csv", blockers)
    write_csv(output / "phase09_family_coverage.csv", [dict(row) for row in assessment.partial_family_summary])
    (output / "PHASE09_RESULT.md").write_text(build_report(summary), encoding="utf-8")

    print(f"decision={summary['assessment']['decision']}")
    print(f"protocol_valid={assessment.protocol_valid}")
    print(f"cohort_structure_ready={assessment.cohort_structure_ready}")
    print(f"cohort_metadata_ready={assessment.cohort_metadata_ready}")
    print(f"cohort_sources_ready={assessment.cohort_sources_ready}")
    print(f"inherited_results={assessment.inherited_result_count}/15")
    print(f"primary_outputs_suppressed={assessment.primary_outputs_suppressed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
