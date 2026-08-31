#!/usr/bin/env python3
"""Execute Phase 03: nonlinear baseline, calibration, and promotion-gate audit."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.io import read_target_manifest, sha256_file
from derd.statistics import paired_bootstrap_comparison
from derd.validation_phase03 import (
    MODEL_NAMES,
    Phase03Config,
    benchmark_targets_phase03,
)


def finite_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return finite_json(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = sorted({key for row in rows for key in row})
    preferred = [
        "star_id",
        "mode",
        "period_days",
        "observation_count_raw",
        "train_count",
        "test_count",
        "selected_derd_by_training_cv",
        "selected_baseline_by_training_cv",
        "preselected_model_by_training_cv",
        "descriptive_test_winner",
        "selected_derd_test_rmse",
        "selected_baseline_test_rmse",
        "primary_derd_minus_baseline_rmse",
    ]
    columns = preferred + [column for column in columns if column not in preferred]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: finite_json(row.get(key)) for key in columns})


def write_predictions(path: Path, predictions: dict[str, np.ndarray]) -> None:
    columns = list(predictions)
    size = len(predictions[columns[0]])
    order = np.argsort(predictions["phase"], kind="mergesort")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for index in order:
            writer.writerow([float(predictions[column][index]) for column in columns])
    if sum(1 for _ in path.open("r", encoding="utf-8")) != size + 1:
        raise AssertionError("prediction CSV row count mismatch")


def aggregate(rows: list[dict[str, Any]], *, interval_coverage: float) -> dict[str, Any]:
    test_rmse = {
        model: np.asarray([row[f"test_{model}_rmse"] for row in rows], dtype=np.float64)
        for model in MODEL_NAMES
    }
    oof_rmse = {
        model: np.asarray([row[f"oof_{model}_weighted_rmse"] for row in rows], dtype=np.float64)
        for model in MODEL_NAMES
    }
    selected_derd = np.asarray([row["selected_derd_test_rmse"] for row in rows], dtype=np.float64)
    selected_baseline = np.asarray([row["selected_baseline_test_rmse"] for row in rows], dtype=np.float64)
    paired = paired_bootstrap_comparison(
        selected_derd,
        selected_baseline,
        repetitions=20000,
        confidence=0.95,
        seed=20260808,
        noninferiority_margin=0.02,
    )

    interval_summary: dict[str, object] = {}
    total_test = sum(int(row["test_count"]) for row in rows)
    for calibration_mode, prefix in (("error_standardized", "interval"), ("absolute", "interval_absolute")):
        mode_payload: dict[str, object] = {}
        for model in MODEL_NAMES:
            pooled_coverage = sum(
                float(row[f"{prefix}_{model}_coverage"]) * int(row["test_count"])
                for row in rows
            ) / total_test
            pooled_width = sum(
                float(row[f"{prefix}_{model}_mean_width"]) * int(row["test_count"])
                for row in rows
            ) / total_test
            pooled_score = sum(
                float(row[f"{prefix}_{model}_score"]) * int(row["test_count"])
                for row in rows
            ) / total_test
            mode_payload[model] = {
                "nominal_coverage": interval_coverage,
                "pooled_empirical_coverage": float(pooled_coverage),
                "absolute_calibration_error": float(abs(pooled_coverage - interval_coverage)),
                "pooled_mean_width": float(pooled_width),
                "pooled_interval_score": float(pooled_score),
                "stars_at_or_above_nominal": int(
                    sum(float(row[f"{prefix}_{model}_coverage"]) >= interval_coverage for row in rows)
                ),
            }
        interval_summary[calibration_mode] = mode_payload

    mode_summary: dict[str, object] = {}
    for mode in sorted({str(row["mode"]) for row in rows}):
        members = [row for row in rows if row["mode"] == mode]
        deltas = np.asarray(
            [row["primary_derd_minus_baseline_rmse"] for row in members], dtype=np.float64
        )
        mode_summary[mode] = {
            "target_count": len(members),
            "selected_derd_win_count": int(np.count_nonzero(deltas < 0.0)),
            "median_primary_difference": float(np.median(deltas)),
            "mean_primary_difference": float(np.mean(deltas)),
        }

    statistical_gate = bool(paired.noninferiority_pass_mean)
    data_gates = {
        "complete_official_photometry": False,
        "multiple_pulsator_classes": False,
        "prospectively_sealed_star_identity_holdout": False,
        "minimum_qualifying_population": False,
    }
    promotion = statistical_gate and all(data_gates.values())
    return {
        "status": "PHASE03_METHODS_AND_CALIBRATION_COMPLETE_C17_NOT_PROMOTED",
        "implementation_id": "DERD-v0.3-phase03",
        "target_count": len(rows),
        "mode_counts": dict(Counter(str(row["mode"]) for row in rows)),
        "mode_summary": mode_summary,
        "observations": {
            "total": int(sum(row["observation_count_clean"] for row in rows)),
            "training": int(sum(row["train_count"] for row in rows)),
            "held_out": int(total_test),
            "source_scope": "24-row mirrored excerpt per target",
        },
        "heldout_rmse": {
            model: {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
            }
            for model, values in test_rmse.items()
        },
        "training_oof_weighted_rmse": {
            model: {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
            }
            for model, values in oof_rmse.items()
        },
        "selection": {
            "selected_derd_law_counts": dict(Counter(row["selected_derd_by_training_cv"] for row in rows)),
            "selected_baseline_counts": dict(Counter(row["selected_baseline_by_training_cv"] for row in rows)),
            "preselected_model_counts": dict(Counter(row["preselected_model_by_training_cv"] for row in rows)),
            "descriptive_test_winner_counts": dict(Counter(row["descriptive_test_winner"] for row in rows)),
        },
        "primary_comparison": paired.as_dict(),
        "interval_calibration": interval_summary,
        "period_scan": {
            "resolved_count": int(sum(bool(row["period_scan_resolved"]) for row in rows)),
            "unresolved_count": int(sum(not bool(row["period_scan_resolved"]) for row in rows)),
            "unresolved_stars": [row["star_id"] for row in rows if not row["period_scan_resolved"]],
            "stage_count_distribution": dict(Counter(str(row["period_scan_stages"]) for row in rows)),
            "maximum_span_distribution": dict(Counter(str(row["period_scan_max_span"]) for row in rows)),
            "maximum_absolute_relative_delta": float(
                max(abs(float(row["period_scan_relative_delta"])) for row in rows)
            ),
        },
        "periodic_kernel": {
            "length_scale_counts": dict(Counter(str(row["kernel_length_scale"]) for row in rows)),
            "ridge_counts": dict(Counter(str(row["kernel_ridge"]) for row in rows)),
            "fallback_count": int(sum(bool(row["kernel_fallback_used"]) for row in rows)),
            "length_scale_boundary_hit_count": int(
                sum(bool(row["kernel_length_scale_boundary_hit"]) for row in rows)
            ),
            "length_scale_boundary_hit_stars": [
                row["star_id"] for row in rows if row["kernel_length_scale_boundary_hit"]
            ],
            "median_effective_parameters": float(
                np.median([row["kernel_effective_parameters"] for row in rows])
            ),
            "median_condition_number": float(
                np.median([row["kernel_condition_number"] for row in rows])
            ),
        },
        "promotion_gate": {
            "statistical_noninferiority_gate": statistical_gate,
            "data_gates": data_gates,
            "promoted": promotion,
            "decision": "DENIED_INCOMPLETE_DATA_CLASS_SCOPE_AND_NO_PRISTINE_SEALED_HOLDOUT",
        },
        "evidence_boundary": {
            "allowed": [
                "pipeline feasibility",
                "training-only model selection feasibility",
                "periodic-kernel baseline feasibility",
                "cross-validated interval calibration feasibility",
                "hypothesis generation for a larger study",
            ],
            "not_allowed": [
                "broad Cepheid population performance claim",
                "RR Lyrae or Delta Scuti performance claim",
                "Fourier replacement claim",
                "physical orbit identification",
                "transparent-shell detection",
                "stellar or shell mass inference",
            ],
        },
    }


def plot_results(output: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[Path]:
    import matplotlib.pyplot as plt

    figures: list[Path] = []
    labels = [row["star_id"].replace("OGLE-LMC-CEP-", "") for row in rows]
    x = np.arange(len(rows))
    display = {
        "derd_g": "DERD-G",
        "derd_k": "DERD-K",
        "fourier_order2": "Fourier order 2",
        "periodic_krr": "Periodic KRR",
    }

    fig, ax = plt.subplots(figsize=(14, 6))
    for model in MODEL_NAMES:
        ax.plot(x, [row[f"test_{model}_rmse"] for row in rows], marker="o", label=display[model])
    ax.set_xticks(x, labels, rotation=70)
    ax.set_yscale("log")
    ax.set_xlabel("OGLE-LMC-CEP identifier suffix")
    ax.set_ylabel("Held-out RMSE on train-scaled relative flux")
    ax.set_title("Phase-03 held-out error by model and target")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = output / "phase03_heldout_rmse_by_star.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(12, 5))
    deltas = [row["primary_derd_minus_baseline_rmse"] for row in rows]
    ax.axhline(0.0, linestyle="--")
    ax.bar(labels, deltas)
    ax.set_xlabel("OGLE-LMC-CEP identifier suffix")
    ax.set_ylabel("Train-selected DERD RMSE minus train-selected baseline RMSE")
    ax.set_title("Primary leakage-resistant per-star comparison")
    ax.tick_params(axis="x", rotation=70)
    fig.tight_layout()
    path = output / "phase03_primary_rmse_delta.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(9, 5))
    coverage = [
        summary["interval_calibration"]["error_standardized"][model]["pooled_empirical_coverage"]
        for model in MODEL_NAMES
    ]
    ax.bar([display[model] for model in MODEL_NAMES], coverage)
    ax.axhline(
        summary["interval_calibration"]["error_standardized"][MODEL_NAMES[0]]["nominal_coverage"],
        linestyle="--",
        label="Nominal coverage",
    )
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Pooled held-out interval coverage")
    ax.set_title("Training-only cross-validated 90% interval calibration")
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    fig.tight_layout()
    path = output / "phase03_interval_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(labels, [abs(row["period_scan_relative_delta"]) for row in rows])
    ax.set_yscale("log")
    ax.set_xlabel("OGLE-LMC-CEP identifier suffix")
    ax.set_ylabel("Absolute best period offset / catalog period")
    ax.set_title("Adaptive training-only period verification")
    ax.tick_params(axis="x", rotation=70)
    fig.tight_layout()
    path = output / "phase03_adaptive_period_offsets.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(7, 6))
    cv = [row[f"oof_{row['preselected_model_by_training_cv']}_weighted_rmse"] for row in rows]
    test = [row["preselected_model_test_rmse"] for row in rows]
    ax.scatter(cv, test)
    maximum = max(max(cv), max(test))
    ax.plot([0.0, maximum], [0.0, maximum], linestyle="--")
    ax.set_xlabel("Training-only OOF weighted RMSE")
    ax.set_ylabel("Held-out RMSE")
    ax.set_title("Preselection error versus held-out error")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = output / "phase03_cv_vs_test.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)
    return figures


def render_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    primary = summary["primary_comparison"]
    interval = summary["interval_calibration"]
    lines = [
        "# Phase 03 result: nonlinear baseline, uncertainty calibration, and promotion gate",
        "",
        f"Status: `{summary['status']}`",
        "",
        "## Implemented",
        "",
        "- Periodic squared-exponential kernel-ridge baseline with nested, training-only phase-block selection.",
        "- Four-fold circular phase out-of-fold predictions for DERD-G, DERD-K, Fourier order 2, and periodic KRR.",
        "- Training-only 90% error-standardized symmetric interval calibration and held-out coverage audit.",
        "- Adaptive period verification using staged +/-0.1%, +/-0.5%, and +/-2% scans.",
        "- Train-only selection of DERD time law and comparator baseline before held-out scoring.",
        "- Paired star-level bootstrap confidence intervals, exact sign test, and noninferiority gate.",
        "- Cryptographic future-holdout protocol and explicit no-promotion decision logic.",
        "",
        "## Dataset boundary",
        "",
        f"The executable population remains {summary['target_count']} LMC classical Cepheids with "
        f"{summary['observations']['total']} observations, of which {summary['observations']['held_out']} are held out. "
        "Each source file is still a 24-row mirror excerpt rather than a complete official light curve.",
        "",
        "## Held-out performance",
        "",
        "| Model | Median RMSE | Mean RMSE | Descriptive wins |",
        "|---|---:|---:|---:|",
    ]
    display = {
        "derd_g": "DERD-G",
        "derd_k": "DERD-K",
        "fourier_order2": "Fourier order 2",
        "periodic_krr": "Periodic KRR",
    }
    for model in MODEL_NAMES:
        metrics = summary["heldout_rmse"][model]
        wins = summary["selection"]["descriptive_test_winner_counts"].get(model, 0)
        lines.append(f"| {display[model]} | {metrics['median']:.6f} | {metrics['mean']:.6f} | {wins} |")

    lines.extend(
        [
            "",
            "## Primary preselected comparison",
            "",
            "For each star, DERD-G versus DERD-K and Fourier order 2 versus periodic KRR were selected using "
            "training-only out-of-fold weighted RMSE. The selected DERD and selected baseline were then evaluated "
            "once on the existing held-out phase block.",
            "",
            f"- Mean DERD-minus-baseline RMSE: {primary['mean_difference']:.6f}",
            f"- Median DERD-minus-baseline RMSE: {primary['median_difference']:.6f}",
            f"- 95% bootstrap CI for mean difference: [{primary['mean_confidence_interval'][0]:.6f}, "
            f"{primary['mean_confidence_interval'][1]:.6f}]",
            f"- 95% bootstrap CI for median difference: [{primary['median_confidence_interval'][0]:.6f}, "
            f"{primary['median_confidence_interval'][1]:.6f}]",
            f"- DERD wins: {primary['first_model_win_count']} of {primary['sample_count']}",
            f"- Exact two-sided sign-test p-value: {primary['exact_sign_test_p_value']:.6g}",
            f"- Provisional +0.02 RMSE noninferiority gate: "
            f"{'pass' if primary['noninferiority_pass_mean'] else 'fail'}",
            "",
            "The statistical output is developmental because the same stars were visible in Phase 02 and the "
            "photometry excerpts are sparse. It cannot serve as a pristine confirmatory result.",
            "",
            "## Interval calibration",
            "",
            "| Model | Nominal | Pooled coverage | Absolute error | Mean width | Interval score |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for calibration_mode, mode_label in (("error_standardized", "Error-standardized"), ("absolute", "Absolute residual")):
        lines.append(f"| **{mode_label}** |  |  |  |  |  |")
        for model in MODEL_NAMES:
            metrics = interval[calibration_mode][model]
            lines.append(
                f"| {display[model]} | {metrics['nominal_coverage']:.3f} | "
                f"{metrics['pooled_empirical_coverage']:.3f} | {metrics['absolute_calibration_error']:.3f} | "
                f"{metrics['pooled_mean_width']:.6f} | {metrics['pooled_interval_score']:.6f} |"
            )

    lines.extend(
        [
            "",
            "## Adaptive period scan",
            "",
            f"Resolved before exhausting the staged scan for {summary['period_scan']['resolved_count']} of "
            f"{summary['target_count']} stars. Unresolved targets: "
            f"{', '.join(summary['period_scan']['unresolved_stars']) or 'none'}.",
            "",
            "The adaptive scan is a diagnostic only. The main waveform benchmark retains catalog periods so that "
            "period policy is not silently changed between phases.",
            "",
            f"The periodic-kernel length-scale grid was widened after the first Phase-03 pass selected its former "
            f"upper boundary for all targets. The final expanded grid still hit its 2.0 boundary for "
            f"{summary['periodic_kernel']['length_scale_boundary_hit_count']} targets; those cases are explicitly flagged.",
            "",
            "## Gate decision",
            "",
            f"`{summary['promotion_gate']['decision']}`",
            "",
            "C17 remains open and unpromoted. Even a statistical noninferiority pass cannot compensate for missing "
            "complete photometry, absence of RR Lyrae and Delta Scuti strata, and lack of a prospectively sealed "
            "star-identity holdout. This is the OURD/IURMv1.1.1 rule that dimensions do not pay each other's debts.",
            "",
            "The paper's physical orbit, transparent-shell, and shell-mass claims remain outside this phase. "
            "Normalized light-curve matching is not treated as mass or mechanism evidence.",
            "",
            "## Per-star primary results",
            "",
            "| Star | Mode | Selected DERD | Selected baseline | DERD RMSE | Baseline RMSE | Difference | Period stages |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['star_id']} | {row['mode']} | {row['selected_derd_by_training_cv']} | "
            f"{row['selected_baseline_by_training_cv']} | {row['selected_derd_test_rmse']:.6f} | "
            f"{row['selected_baseline_test_rmse']:.6f} | {row['primary_derd_minus_baseline_rmse']:.6f} | "
            f"{row['period_scan_stages']} |"
        )
    lines.extend(
        [
            "",
            "## Immediate next gate",
            "",
            "1. Import complete official I-band observations under the frozen attribution and checksum procedure.",
            "2. Build a new candidate pool and cryptographically seal star identities before any Phase-04 scoring.",
            "3. Add RR Lyrae and Delta Scuti ingestion capsules with class-specific period and multimode policies.",
            "4. Calibrate intervals on a larger development population, then evaluate the sealed holdout once.",
            "5. Open physical-mechanism tests only after independent radial-velocity, colour, spectral, or diameter predictions exist.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/manifests/phase02_targets.csv")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-directory", default="artifacts/phase03")
    parser.add_argument("--starts", type=int, default=2)
    parser.add_argument("--cv-starts", type=int, default=1)
    parser.add_argument("--max-function-evaluations", type=int, default=100)
    parser.add_argument("--cv-max-function-evaluations", type=int, default=60)
    parser.add_argument("--normalization-grid-size", type=int, default=256)
    parser.add_argument("--peak-grid-size", type=int, default=128)
    parser.add_argument("--period-grid-count", type=int, default=101)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output_directory)
    output.mkdir(parents=True, exist_ok=True)
    prediction_directory = output / "predictions"
    prediction_directory.mkdir(parents=True, exist_ok=True)

    config = Phase03Config(
        starts=args.starts,
        cv_starts=args.cv_starts,
        maximum_function_evaluations=args.max_function_evaluations,
        cv_maximum_function_evaluations=args.cv_max_function_evaluations,
        normalization_grid_size=args.normalization_grid_size,
        peak_grid_size=args.peak_grid_size,
        period_grid_count=args.period_grid_count,
    )
    records = read_target_manifest(args.manifest)
    benchmarks = benchmark_targets_phase03(records, data_root=args.data_root, config=config)
    rows = [benchmark.row for benchmark in benchmarks]
    details = {benchmark.row["star_id"]: benchmark.detail for benchmark in benchmarks}
    for benchmark in benchmarks:
        write_predictions(
            prediction_directory / f"{benchmark.row['star_id']}.csv",
            benchmark.predictions,
        )

    summary = aggregate(rows, interval_coverage=config.interval_coverage)
    figures = plot_results(output, rows, summary)
    write_csv(output / "phase03_star_results.csv", rows)
    (output / "phase03_details.json").write_text(
        json.dumps(finite_json(details), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "phase03_summary.json").write_text(
        json.dumps(finite_json(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "PHASE03_RESULT.md").write_text(render_report(rows, summary), encoding="utf-8")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "implementation_id": "DERD-v0.3-phase03",
        "config": asdict(config),
        "manifest": args.manifest,
        "manifest_sha256": sha256_file(args.manifest),
        "cwd": os.getcwd(),
        "figures": [str(path.relative_to(output)) for path in figures],
    }
    (output / "environment.json").write_text(
        json.dumps(finite_json(environment), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(finite_json(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
