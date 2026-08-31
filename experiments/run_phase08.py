#!/usr/bin/env python3
"""Execute the Phase-08 multi-family harmonic-forecast development cohort."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.harmonic_exchange import write_harmonic_exchange
from derd.validation_phase07 import Phase07Config
from derd.validation_phase08 import (
    Phase08Config,
    Phase08Target,
    assess_cohort,
)


def json_dump(path: Path, payload: Any) -> None:
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
    active = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=active, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_targets(path: Path) -> list[Phase08Target]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Phase08Target(
            object_id=row["object_id"],
            family=row["family"],
            mode=row["mode"],
            catalog_period_days=float(row["catalog_period_days"]),
            period_evidence_grade=row["period_evidence_grade"],
            source_relative_path=row["source_relative_path"],
            source_repository_path=row["source_repository_path"],
            source_git_blob_sha1=row["source_git_blob_sha1"],
            source_sha256=row["source_sha256"],
            source_byte_count=int(row["source_byte_count"]),
            source_repository=row["source_repository"],
            source_commit=row["source_commit"],
            period_source=row["period_source"],
            evidence_role=row.get("evidence_role", "exposed-development-only"),
        )
        for row in payload["targets"]
    ]


def make_figures(output: Path, assessment) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    targets = list(assessment.targets)
    labels = [item.target.object_id.replace("OGLE-LMC-", "") for item in targets]
    figures: list[str] = []

    fig = plt.figure(figsize=(11, 5.8))
    ax = fig.add_subplot(111)
    x = np.arange(len(targets))
    scores = [item.result.screen.score for item in targets]
    thresholds = [item.result.calibration.threshold for item in targets]
    ax.plot(x, scores, marker="o", label="observed DERD screen score")
    ax.plot(x, thresholds, marker="s", label="target-specific cadence threshold")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("lower is more DERD-compatible")
    ax.set_title("Phase 08 target-specific compatibility screen")
    ax.legend()
    fig.tight_layout()
    path = output / "phase08_score_vs_threshold.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    fig = plt.figure(figsize=(11, 6.2))
    ax = fig.add_subplot(111)
    snr = np.asarray([item.result.harmonic_fit.coefficient_snr for item in targets])
    image = ax.imshow(np.log10(np.maximum(snr, 1.0e-3)), aspect="auto")
    ax.set_yticks(np.arange(len(targets)), labels)
    ax.set_xticks(np.arange(snr.shape[1]), [f"h{i}" for i in range(1, snr.shape[1] + 1)])
    ax.axvline(3.5, linestyle="--", linewidth=1.5)
    ax.set_title("log10 harmonic Wald SNR; forecast begins at h5")
    fig.colorbar(image, ax=ax, label="log10 SNR")
    fig.tight_layout()
    path = output / "phase08_harmonic_snr_matrix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    ranked = sorted(targets, key=lambda item: item.acquisition_priority_score, reverse=True)
    fig = plt.figure(figsize=(10.5, 5.8))
    ax = fig.add_subplot(111)
    rank_labels = [item.target.object_id.replace("OGLE-LMC-", "") for item in ranked]
    values = [item.acquisition_priority_score for item in ranked]
    ax.barh(np.arange(len(ranked)), values)
    ax.set_yticks(np.arange(len(ranked)), rank_labels)
    ax.invert_yaxis()
    ax.set_xlabel("engineering acquisition-priority score (0-100)")
    ax.set_title("Next-observation priority, not a DERD probability")
    fig.tight_layout()
    path = output / "phase08_acquisition_priority.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    ordered_stages = [
        "SOURCE_OR_SAMPLING",
        "PERIOD_PROVENANCE",
        "RECOVERY_HARMONICS",
        "FORECAST_HARMONICS",
        "DERD_COMPATIBILITY",
        "CALIBRATION_AND_STABILITY",
        "QUALIFIED_DEVELOPMENT_FORECAST",
    ]
    counts = [assessment.stage_counts.get(stage, 0) for stage in ordered_stages]
    fig = plt.figure(figsize=(10.5, 5.6))
    ax = fig.add_subplot(111)
    ax.bar(np.arange(len(ordered_stages)), counts)
    ax.set_xticks(
        np.arange(len(ordered_stages)),
        [stage.replace("_", " ").title() for stage in ordered_stages],
        rotation=35,
        ha="right",
    )
    ax.set_ylabel("objects stopping at gate")
    ax.set_title("Phase 08 evidence ladder")
    fig.tight_layout()
    path = output / "phase08_evidence_ladder.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))
    return figures


def build_report(summary: dict[str, Any]) -> str:
    cohort = summary["cohort"]
    lines = [
        "# Phase 08 result: multi-family raw-photometry harmonic-forecast cohort",
        "",
        "## Decision",
        "",
        f"`{cohort['decision']}`",
        "",
        "This exposed development cohort applies the same lossless eight-harmonic, target-specific cadence, covariance-aware gate to classical Cepheid, RR Lyrae, and Delta Scuti objects. It is not a prospective confirmatory sample and does not promote C17 or any physical shell claim.",
        "",
        "## Cohort summary",
        "",
        "| Family | Objects | Claim-grade periods | Recovery-ready | Forecast measured | Structurally compatible | Qualified |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in cohort["family_summary"]:
        lines.append(
            f"| {row['family']} | {row['object_count']} | {row['claim_grade_period_count']} | "
            f"{row['recovery_ready_count']} | {row['forecast_measured_count']} | "
            f"{row['structurally_compatible_count']} | {row['qualified_count']} |"
        )
    lines.extend([
        "",
        "## Per-object gate",
        "",
        "| Object | Family | Mode | N clean | Score / threshold | h1-h4 ready | h5-h8 measured | Cadence AUC | Structural flags | Disposition |",
        "|---|---|---|---:|---:|:---:|:---:|---:|---|---|",
    ])
    for item in cohort["targets"]:
        target = item["target"]
        result = item["result"]
        snr = result["harmonic_fit"]["coefficient_snr"]
        forecast_count = sum(value >= 2.0 for value in snr[4:])
        flags = ", ".join(item["structural_flags"]) or "none"
        lines.append(
            f"| {target['object_id']} | {target['family']} | {target['mode']} | {result['observation_count']} | "
            f"{result['screen']['score']:.4f} / {result['calibration']['threshold']:.4f} | "
            f"{'yes' if item['checks']['four_recovery_harmonics_snr'] else 'no'} | {forecast_count} | "
            f"{result['calibration']['holdout_metrics']['roc_auc']:.3f} | {flags} | {item['disposition']} |"
        )
    ranked = sorted(cohort["targets"], key=lambda row: row["acquisition_priority_score"], reverse=True)
    lines.extend([
        "",
        "## Acquisition queue",
        "",
        "The priority score is a deterministic engineering heuristic. It is not a probability that DERD is true.",
        "",
        "| Rank | Object | Priority | Approx. recovery N | Approx. forecast N | Current stopping stage |",
        "|---:|---|---:|---:|---:|---|",
    ])
    for index, item in enumerate(ranked, start=1):
        recovery = item["approximate_recovery_observations"]
        forecast = item["approximate_forecast_observations"]
        lines.append(
            f"| {index} | {item['target']['object_id']} | {item['acquisition_priority_score']:.2f} | "
            f"{recovery if recovery is not None else 'n/a'} | {forecast if forecast is not None else 'n/a'} | {item['stage_reached']} |"
        )
    lines.extend([
        "",
        "## Interpretation boundary",
        "",
        "A target can fail because its high-order harmonics are unmeasured, because the recovered recurrence violates DERD root/residue constraints, because target-specific null calibration is inadequate, or because the candidate is unstable under coefficient covariance. These failure modes are kept separate. None of them identifies or excludes a transparent shell by itself.",
        "",
        "## Next gate",
        "",
        "Acquire or retrieve complete claim-grade periods and raw photometry for at least five exposed development objects in each family, pre-register the cohort-level statistic, and rerun this exact gate before opening any sealed identity.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase08_cohort_sources.json"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase08"))
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    targets = load_targets(args.manifest)
    target_config = Phase07Config(
        synthetic_samples_per_class=96,
        propagation_draws=2048,
        observation_sweep_counts=(),
        observation_sweep_repetitions=1,
        minimum_observations=240,
        period_grid_count=101,
    )
    if args.fast:
        target_config = replace(
            target_config,
            synthetic_samples_per_class=24,
            propagation_draws=256,
            period_grid_count=51,
        )
    config = Phase08Config(target_config=target_config)
    assessment = assess_cohort(targets, root=args.root, config=config)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    target_rows: list[dict[str, Any]] = []
    snr_rows: list[dict[str, Any]] = []
    acquisition_rows: list[dict[str, Any]] = []
    for item in assessment.targets:
        target = item.target
        result = item.result
        exchange = result.harmonic_fit.to_exchange(
            object_id=target.object_id,
            time_unit="day",
            value_unit="relative_flux",
            source_locator=target.source_locator,
            source_sha256=target.source_sha256,
            metadata={
                "family": target.family,
                "mode": target.mode,
                "catalog_period_days": target.catalog_period_days,
                "period_evidence_grade": target.period_evidence_grade,
                "period_source": target.period_source,
                "evidence_role": target.evidence_role,
                "physical_claim_scope": "waveform-only",
            },
        )
        write_harmonic_exchange(output / "harmonic_exchange" / f"{target.object_id}.json", exchange)
        target_rows.append({
            "object_id": target.object_id,
            "family": target.family,
            "mode": target.mode,
            "period_days": target.catalog_period_days,
            "period_evidence_grade": target.period_evidence_grade,
            "raw_observations": item.cleaning["input_count"],
            "clean_observations": item.cleaning["output_count"],
            "occupied_phase_bins": result.harmonic_fit.phase_coverage["occupied_bins"],
            "design_condition_number": result.harmonic_fit.design_condition_number,
            "screen_score": result.screen.score,
            "cadence_threshold": result.calibration.threshold,
            "cadence_auc": result.calibration.holdout_metrics["roc_auc"],
            "cadence_balanced_accuracy": result.calibration.holdout_metrics["balanced_accuracy"],
            "recovery_ready": item.checks["four_recovery_harmonics_snr"],
            "forecast_harmonics_measured": sum(
                value >= target_config.minimum_forecast_snr
                for value in result.harmonic_fit.coefficient_snr[target_config.fit_harmonics :]
            ),
            "structural_flags": ";".join(item.structural_flags),
            "structural_pass_fraction": result.propagation.structural_pass_fraction,
            "threshold_pass_fraction": result.propagation.below_threshold_fraction,
            "stage_reached": item.stage_reached,
            "disposition": item.disposition,
        })
        for harmonic, snr in enumerate(result.harmonic_fit.coefficient_snr, start=1):
            snr_rows.append({
                "object_id": target.object_id,
                "family": target.family,
                "harmonic": harmonic,
                "role": "recovery" if harmonic <= target_config.fit_harmonics else "forecast",
                "wald_snr": float(snr),
                "threshold": target_config.minimum_recovery_snr if harmonic <= target_config.fit_harmonics else target_config.minimum_forecast_snr,
                "passes": bool(snr >= (target_config.minimum_recovery_snr if harmonic <= target_config.fit_harmonics else target_config.minimum_forecast_snr)),
            })
        acquisition_rows.append({
            "object_id": target.object_id,
            "family": target.family,
            "mode": target.mode,
            "priority_score": item.acquisition_priority_score,
            "approximate_recovery_observations": item.approximate_recovery_observations,
            "approximate_forecast_observations": item.approximate_forecast_observations,
            "stage_reached": item.stage_reached,
            "disposition": item.disposition,
            "warning": "engineering queue only; not a DERD probability",
        })

    acquisition_rows.sort(key=lambda row: float(row["priority_score"]), reverse=True)
    write_csv(output / "phase08_target_results.csv", target_rows)
    write_csv(output / "phase08_harmonic_snr.csv", snr_rows)
    write_csv(output / "phase08_acquisition_ranking.csv", acquisition_rows)
    write_csv(output / "phase08_family_summary.csv", list(assessment.family_summary))

    figures = make_figures(output, assessment)
    summary = {
        "implementation_id": "DERD-v0.8-phase08-multifamily-harmonic-forecast-cohort",
        "date": "2026-08-15",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "research_role": "EXPOSED_DEVELOPMENT_COHORT",
        "manifest": str(args.manifest),
        "configuration": {
            "fourier_order": target_config.fourier_order,
            "fit_harmonics": target_config.fit_harmonics,
            "synthetic_samples_per_class": target_config.synthetic_samples_per_class,
            "propagation_draws": target_config.propagation_draws,
            "minimum_observations": target_config.minimum_observations,
            "minimum_recovery_snr": target_config.minimum_recovery_snr,
            "minimum_forecast_snr": target_config.minimum_forecast_snr,
            "minimum_forecast_significant_harmonics": target_config.minimum_forecast_significant_harmonics,
            "target_specific_independent_seeds": True,
        },
        "cohort": assessment.as_dict(include_controls=False),
        "figures": figures,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }
    json_dump(output / "phase08_summary.json", summary)
    (output / "PHASE08_RESULT.md").write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({
        "decision": assessment.decision,
        "objects": len(assessment.targets),
        "qualified": sum(item.disposition == "QUALIFIES_AS_DEVELOPMENT_HARMONIC_FORECAST" for item in assessment.targets),
        "output": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
