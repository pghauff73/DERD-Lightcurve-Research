#!/usr/bin/env python3
"""Run the Phase-05 DERD harmonic-signature screening experiment."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.io import read_target_manifest, sha256_file
from derd.validation_phase05 import (
    Phase05Config,
    cadence_aware_synthetic_controls,
    calibrate_score_threshold,
    screen_observational_pilot,
    minimum_viable_observation_sweep,
)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot write an empty CSV")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(json_safe(row))


def generate_figures(output: Path, synthetic: list[dict[str, Any]], real_rows: list[dict[str, Any]], noise_metrics: list[dict[str, Any]], mve_summary: list[dict[str, Any]]) -> list[str]:
    import matplotlib.pyplot as plt

    generated: list[str] = []
    reference = [row for row in synthetic if row["noise_multiplier"] == 1.0 and row["split"] == "holdout"]
    positive = [row["score"] for row in reference if row["label"] == 1 and row["score"] < 1.0e5]
    negative = [row["score"] for row in reference if row["label"] == 0 and row["score"] < 1.0e5]
    upper = float(np.quantile(np.asarray(positive + negative), 0.95)) if positive and negative else 10.0
    plt.figure(figsize=(8.8, 5.2))
    plt.hist(positive, bins=30, alpha=0.65, label="Synthetic DERD")
    plt.hist(negative, bins=30, alpha=0.65, label="Null families")
    plt.xlim(0.0, max(0.5, upper))
    plt.xlabel("Harmonic-screen score, lower is more DERD-compatible")
    plt.ylabel("Holdout control count")
    plt.title("Phase 05 cadence-aware synthetic holdout")
    plt.legend()
    plt.tight_layout()
    path = output / "phase05_synthetic_score_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    ranked = sorted(real_rows, key=lambda row: int(row["rank"]))
    labels = [str(row["star_id"]).replace("OGLE-LMC-CEP-", "CEP-") for row in ranked]
    scores = [float(row["screen_score"]) for row in ranked]
    plt.figure(figsize=(10.5, 6.0))
    positions = np.arange(len(ranked))
    plt.bar(positions, scores)
    plt.xticks(positions, labels, rotation=75, ha="right")
    plt.ylabel("Catalog-period harmonic-screen score")
    plt.title("Existing 20-star excerpt: provisional spectral triage")
    plt.tight_layout()
    path = output / "phase05_real_candidate_ranking.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    stability = [float(row["bootstrap_below_threshold_fraction"]) for row in ranked]
    plt.figure(figsize=(10.5, 5.4))
    plt.bar(positions, stability)
    plt.axhline(0.80, linestyle="--", linewidth=1.2, label="Priority-A stability gate")
    plt.xticks(positions, labels, rotation=75, ha="right")
    plt.ylabel("Bayesian-bootstrap fraction below threshold")
    plt.ylim(0.0, 1.05)
    plt.title("Candidate-score stability under observation reweighting")
    plt.legend()
    plt.tight_layout()
    path = output / "phase05_bootstrap_stability.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    noise = [float(row["noise_multiplier"]) for row in noise_metrics]
    auc = [float(row["holdout_roc_auc"]) for row in noise_metrics]
    balanced = [float(row["holdout_balanced_accuracy"]) for row in noise_metrics]
    plt.figure(figsize=(7.8, 5.0))
    plt.plot(noise, auc, marker="o", label="ROC AUC")
    plt.plot(noise, balanced, marker="o", label="Balanced accuracy")
    plt.xlabel("Photometric-noise multiplier")
    plt.ylabel("Synthetic holdout performance")
    plt.ylim(0.0, 1.05)
    plt.title("IURMv1.1.1 one-dimension noise sweep")
    plt.legend()
    plt.tight_layout()
    path = output / "phase05_noise_sensitivity.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    counts = [int(row["sample_count"]) for row in mve_summary]
    median_auc = [float(row["median_roc_auc"]) for row in mve_summary]
    auc_q10 = [float(row["roc_auc_q10"]) for row in mve_summary]
    median_balanced = [float(row["median_balanced_accuracy"]) for row in mve_summary]
    balanced_q10 = [float(row["balanced_accuracy_q10"]) for row in mve_summary]
    plt.figure(figsize=(8.4, 5.2))
    plt.plot(counts, median_auc, marker="o", label="Median ROC AUC")
    plt.plot(counts, auc_q10, marker="o", label="ROC AUC 10th percentile")
    plt.plot(counts, median_balanced, marker="o", label="Median balanced accuracy")
    plt.plot(counts, balanced_q10, marker="o", label="Balanced accuracy 10th percentile")
    plt.axhline(0.75, linestyle="--", linewidth=1.0)
    plt.xlabel("Observations per star")
    plt.ylabel("Synthetic holdout performance")
    plt.ylim(0.0, 1.05)
    plt.title("Minimum viable harmonic-evidence sweep")
    plt.legend()
    plt.tight_layout()
    path = output / "phase05_minimum_viable_observations.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)
    return generated


def build_report(summary: dict[str, Any], real_rows: list[dict[str, Any]]) -> str:
    calibration = summary["reference_calibration"]
    holdout = calibration["holdout_metrics"]
    priorities: dict[str, int] = {}
    for row in real_rows:
        priorities[str(row["priority"])] = priorities.get(str(row["priority"]), 0) + 1
    top = sorted(real_rows, key=lambda row: int(row["rank"]))[:8]
    lines = [
        "# Phase 05 result: DERD harmonic-signature candidate triage",
        "",
        f"Release status: `{summary['status']}`",
        "",
        "## High-gain target implemented",
        "",
        "The geometric DERD model implies an order-two recurrence in its non-zero complex Fourier coefficients. Phase 05 converts that theorem into a fast algebraic screen that recovers a candidate four-parameter DERD description, tests residue-phase and sign constraints, forecasts higher harmonics, and ranks objects before expensive nonlinear light-curve fitting.",
        "",
        "The screen is a waveform-family triage device. It does not identify a stellar core-shell mechanism, external shell, or shell mass.",
        "",
        "## Cadence-aware synthetic control",
        "",
        f"The reference threshold was calibrated only on the synthetic development split and evaluated on a separate synthetic holdout. The frozen threshold is **{calibration['threshold']:.6g}**.",
        "",
        "| Metric | Synthetic holdout |",
        "|---|---:|",
        f"| Sample count | {holdout['sample_count']} |",
        f"| ROC AUC | {holdout['roc_auc']:.4f} |",
        f"| Balanced accuracy | {holdout['balanced_accuracy']:.4f} |",
        f"| Sensitivity | {holdout['sensitivity']:.4f} |",
        f"| Specificity | {holdout['specificity']:.4f} |",
        "",
        "The null set contains both smooth generic Fourier curves and phase-scrambled DERD-amplitude curves. All controls use the same 20 cadences and quoted uncertainty scales as the exposed Cepheid excerpt.",
        "",
        "## Minimum viable harmonic evidence",
        "",
        f"The current 24-point cadence did not separate the synthetic families reliably. Under an optimistic uniform-phase experiment with the observed median noise ratio held fixed, the first observation count passing all frozen robustness gates was **{summary['minimum_viable_harmonic_evidence']['minimum_viable_observation_count']} observations per star**.",
        "",
        "This is an acquisition-design lower bound, not a universal sample-size theorem. Uneven phase coverage, multimode structure, modulation, and catalog systematics can require more observations.",
        "",
        "## Existing 20-star excerpt",
        "",
        "The excerpt remains development evidence: 24 observations per star are insufficient for confirmatory harmonic inference. Candidate labels below are acquisition priorities, not detections.",
        "",
        "| Priority | Count |",
        "|---|---:|",
    ]
    for name, count in sorted(priorities.items()):
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "### Highest-ranked acquisition targets",
            "",
            "| Rank | Star | Mode | Score | Bootstrap support | SNR harmonics | Decision |",
            "|---:|---|---|---:|---:|---:|---|",
        ]
    )
    for row in top:
        lines.append(
            f"| {row['rank']} | {row['star_id']} | {row['mode']} | {row['screen_score']:.4f} | {row['bootstrap_below_threshold_fraction']:.3f} | {row['harmonics_snr_ge_3']} | {row['priority']} |"
        )
    lines.extend(
        [
            "",
            "## Gate decision",
            "",
            "`HARMONIC_TRIAGE_ENGINE_IMPLEMENTED_CATALOG_SCALE_PROOF_NOT_YET_RUN`",
            "",
            "The next data action is to use the ranked list to acquire complete official light curves for development targets, then run the same algorithm over frozen Cepheid, RR Lyrae, and Delta Scuti harmonic catalogs under a verified phase convention. The prospective Phase-04 sealed identities remain untouched.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "artifacts/phase05").resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = Phase05Config()
    manifest_path = root / "data/manifests/phase02_targets.csv"
    records = read_target_manifest(manifest_path)

    all_synthetic_records = []
    noise_metrics: list[dict[str, Any]] = []
    calibrations: dict[str, Any] = {}
    for noise_multiplier in (0.5, 1.0, 2.0):
        controls = cadence_aware_synthetic_controls(
            records,
            data_root=root / "data",
            noise_multiplier=noise_multiplier,
            config=config,
        )
        calibration = calibrate_score_threshold(controls)
        all_synthetic_records.extend(controls)
        calibrations[f"noise_{noise_multiplier:.1f}"] = calibration.as_dict()
        noise_metrics.append(
            {
                "noise_multiplier": noise_multiplier,
                "threshold": calibration.threshold,
                "development_roc_auc": calibration.development_metrics["roc_auc"],
                "development_balanced_accuracy": calibration.development_metrics["balanced_accuracy"],
                "holdout_roc_auc": calibration.holdout_metrics["roc_auc"],
                "holdout_balanced_accuracy": calibration.holdout_metrics["balanced_accuracy"],
                "holdout_sensitivity": calibration.holdout_metrics["sensitivity"],
                "holdout_specificity": calibration.holdout_metrics["specificity"],
            }
        )
    reference_controls = [
        row for row in all_synthetic_records if row.noise_multiplier == 1.0
    ]
    reference_calibration = calibrate_score_threshold(reference_controls)
    development = [row for row in reference_controls if row.split == "development"]
    real_rows, real_details = screen_observational_pilot(
        records,
        data_root=root / "data",
        threshold=reference_calibration.threshold,
        synthetic_development_scores=[row.score for row in development],
        synthetic_development_labels=[row.label for row in development],
        config=config,
    )

    # Minimal viable harmonic evidence: observation count is the only active dimension.
    from derd.io import read_ogle_photometry
    from derd.preprocess import clean_light_curve
    observed_noise_ratios = []
    for record in records:
        curve = read_ogle_photometry(root / "data" / record.relative_path, star_id=record.star_id)
        cleaned, _ = clean_light_curve(curve)
        flux = cleaned.to_relative_flux()
        observed_noise_ratios.append(float(np.median(flux.error) / max(np.ptp(flux.value), np.finfo(float).eps)))
    reference_noise_ratio = float(np.median(np.asarray(observed_noise_ratios)))
    mve_replicates, mve_summary, minimum_viable_count = minimum_viable_observation_sweep(
        sample_counts=(24, 40, 60, 80, 120, 160, 240, 400),
        noise_ratio=reference_noise_ratio,
        seeds=5,
        repetitions_per_class=75,
        config=config,
    )

    synthetic_rows = [row.as_dict() for row in all_synthetic_records]
    write_csv(output / "phase05_synthetic_controls.csv", synthetic_rows)
    write_csv(output / "phase05_noise_sensitivity.csv", noise_metrics)
    write_csv(output / "phase05_candidate_ranking.csv", real_rows)
    write_csv(output / "phase05_minimum_evidence_replicates.csv", mve_replicates)
    write_csv(output / "phase05_minimum_evidence_summary.csv", mve_summary)
    write_json(output / "phase05_details.json", real_details)

    priority_counts: dict[str, int] = {}
    for row in real_rows:
        priority_counts[str(row["priority"])] = priority_counts.get(str(row["priority"]), 0) + 1
    summary = {
        "artifact_id": "DERD-PHASE05-HARMONIC-SCREEN-001",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HARMONIC_TRIAGE_ENGINE_IMPLEMENTED_CATALOG_SCALE_PROOF_NOT_YET_RUN",
        "method": {
            "positive_harmonic_convention": "f(phi)=c0+sum(c_n exp(i2pi n phi)+conjugate)",
            "fourier_order": config.fourier_order,
            "fit_harmonics": config.fit_harmonics,
            "forecast_harmonics": config.fourier_order - config.fit_harmonics,
            "fourier_ridge": config.fourier_ridge,
            "score_direction": "lower_is_more_compatible",
            "candidate_threshold_source": "cadence-aware synthetic development split at noise multiplier 1.0",
        },
        "source_population": {
            "star_count": len(records),
            "manifest": str(manifest_path.relative_to(root)),
            "manifest_sha256": sha256_file(manifest_path),
            "observations_per_star": 24,
            "exposure_status": "PREVIOUSLY_EXAMINED_DEVELOPMENT_EVIDENCE",
        },
        "config": asdict(config),
        "calibrations": calibrations,
        "reference_calibration": reference_calibration.as_dict(),
        "noise_sensitivity": noise_metrics,
        "minimum_viable_harmonic_evidence": {
            "active_dimension": "observation_count",
            "phase_coverage": "uniform_optimistic_design",
            "reference_noise_ratio": reference_noise_ratio,
            "gate": {
                "median_roc_auc_minimum": 0.80,
                "roc_auc_q10_minimum": 0.75,
                "median_balanced_accuracy_minimum": 0.75,
                "balanced_accuracy_q10_minimum": 0.70
            },
            "minimum_viable_observation_count": minimum_viable_count,
            "summary": mve_summary
        },
        "real_screen": {
            "priority_counts": priority_counts,
            "below_threshold_count": int(sum(bool(row["below_threshold"]) for row in real_rows)),
            "eligible_candidate_count": int(sum(bool(row["eligible_candidate"]) for row in real_rows)),
            "top_ranked": [
                {
                    key: row[key]
                    for key in (
                        "rank",
                        "star_id",
                        "mode",
                        "screen_score",
                        "bootstrap_below_threshold_fraction",
                        "harmonics_snr_ge_3",
                        "priority",
                    )
                }
                for row in real_rows[:8]
            ],
        },
        "interpretation_limits": [
            "The cadence-aware synthetic benchmark shows that the screen is not an adequate discriminator at the exposed 24-observation cadence; it is not an astrophysical prevalence estimate.",
            "The 20 real files contain only 24 observations each and cannot promote C17 or any physical mechanism claim.",
            "Four-harmonic catalog tables provide shape-only evidence unless additional harmonics or raw photometry supply a forecast test.",
            "A catalog phase convention must be verified before cross-catalog scores are compared.",
            "Normalized harmonic compatibility cannot determine absolute radius, mass, shell mass, or causal stellar dynamics.",
        ],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }
    figures = generate_figures(output, synthetic_rows, real_rows, noise_metrics, mve_summary)
    summary["figures"] = figures
    write_json(output / "phase05_summary.json", summary)
    report = build_report(summary, real_rows)
    (output / "PHASE05_RESULT.md").write_text(report, encoding="utf-8")
    print(json.dumps(json_safe(summary["real_screen"]), indent=2, sort_keys=True))
    print(f"threshold={reference_calibration.threshold:.8g}")
    print(f"holdout_auc={reference_calibration.holdout_metrics['roc_auc']:.6f}")
    print(f"holdout_balanced_accuracy={reference_calibration.holdout_metrics['balanced_accuracy']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
