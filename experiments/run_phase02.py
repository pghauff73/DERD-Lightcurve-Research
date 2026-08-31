#!/usr/bin/env python3
"""Execute the 20-Cepheid Phase-02 observational shakedown."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.bootstrap import bootstrap_fit_stability
from derd.io import read_target_manifest, sha256_file
from derd.preprocess import inverse_variance_weights
from derd.validation import ValidationConfig, benchmark_targets


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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
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
        "winner",
        "best_derd_rmse",
        "best_fourier_rmse",
        "derd_minus_fourier_rmse",
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
    assert sum(1 for _ in path.open("r", encoding="utf-8")) == size + 1


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    models = ("derd_g", "derd_k", "fourier_order2", "fourier_bic")
    rmse = {
        model: np.asarray([row[f"test_{model}_rmse"] for row in rows], dtype=np.float64)
        for model in models
    }
    deltas = np.asarray([row["derd_minus_fourier_rmse"] for row in rows], dtype=np.float64)
    g_condition = np.asarray([row["derd_g_condition_number"] for row in rows], dtype=np.float64)
    k_condition = np.asarray([row["derd_k_condition_number"] for row in rows], dtype=np.float64)
    period_delta = np.asarray([row["period_relative_delta"] for row in rows], dtype=np.float64)
    mode_summary: dict[str, object] = {}
    for mode in sorted({row["mode"] for row in rows}):
        members = [row for row in rows if row["mode"] == mode]
        mode_summary[mode] = {
            "target_count": len(members),
            "best_derd_beats_best_fourier_count": int(sum(row["derd_minus_fourier_rmse"] < 0.0 for row in members)),
            "median_best_derd_rmse": float(np.median([row["best_derd_rmse"] for row in members])),
            "median_best_fourier_rmse": float(np.median([row["best_fourier_rmse"] for row in members])),
            "median_derd_minus_fourier_rmse": float(np.median([row["derd_minus_fourier_rmse"] for row in members])),
        }
    return {
        "status": "PHASE02_ENGINEERING_SHAKEDOWN_COMPLETE_C17_NOT_PROMOTED",
        "target_count": len(rows),
        "mode_counts": dict(Counter(row["mode"] for row in rows)),
        "mode_summary": mode_summary,
        "observation_count_total": int(sum(row["observation_count_clean"] for row in rows)),
        "train_count_total": int(sum(row["train_count"] for row in rows)),
        "test_count_total": int(sum(row["test_count"] for row in rows)),
        "winner_counts": dict(Counter(row["winner"] for row in rows)),
        "fourier_bic_order_counts": dict(Counter(str(row["fourier_bic_order"]) for row in rows)),
        "fourier_bic_raw_order_counts": dict(Counter(str(row["fourier_bic_raw_order"]) for row in rows)),
        "fourier_stability_gate": {
            "targets_with_rejected_orders": int(sum(bool(row["fourier_bic_rejected_orders"]) for row in rows)),
            "raw_bic_test_rmse_over_1": int(sum(row["test_fourier_bic_raw_rmse"] > 1.0 for row in rows)),
            "raw_bic_maximum_test_rmse": float(max(row["test_fourier_bic_raw_rmse"] for row in rows)),
        },
        "heldout_rmse": {
            model: {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
            }
            for model, values in rmse.items()
        },
        "best_derd_beats_best_fourier_count": int(np.count_nonzero(deltas < 0.0)),
        "best_fourier_beats_or_ties_best_derd_count": int(np.count_nonzero(deltas >= 0.0)),
        "derd_minus_fourier_rmse": {
            "median": float(np.median(deltas)),
            "mean": float(np.mean(deltas)),
            "minimum": float(np.min(deltas)),
            "maximum": float(np.max(deltas)),
        },
        "time_law_comparison": {
            "derd_g_lower_rmse_count": int(np.count_nonzero(rmse["derd_g"] < rmse["derd_k"])),
            "derd_k_lower_or_equal_rmse_count": int(np.count_nonzero(rmse["derd_k"] <= rmse["derd_g"])),
        },
        "identifiability": {
            "derd_g_condition_median": float(np.median(g_condition)),
            "derd_k_condition_median": float(np.median(k_condition)),
            "derd_g_condition_over_1e5": int(np.count_nonzero(g_condition > 1e5)),
            "derd_k_condition_over_1e5": int(np.count_nonzero(k_condition > 1e5)),
            "derd_g_condition_over_1e8": int(np.count_nonzero(g_condition > 1e8)),
            "derd_k_condition_over_1e8": int(np.count_nonzero(k_condition > 1e8)),
            "warning_stars": [
                row["star_id"]
                for row in rows
                if row["derd_g_condition_number"] > 1e5 or row["derd_k_condition_number"] > 1e5
            ],
        },
        "period_check": {
            "median_absolute_relative_delta": float(np.median(np.abs(period_delta))),
            "maximum_absolute_relative_delta": float(np.max(np.abs(period_delta))),
            "grid_boundary_hits": int(np.count_nonzero(np.isclose(np.abs(period_delta), 0.001))),
            "grid_boundary_stars": [
                row["star_id"] for row in rows if np.isclose(abs(row["period_relative_delta"]), 0.001)
            ],
        },
        "evidence_boundary": {
            "sample": "20 LMC classical Cepheids, balanced 10 fundamental and 10 first-overtone",
            "photometry": "first 24 mirrored I-band observations per target",
            "not_in_scope": [
                "complete OGLE light curves",
                "Delta Scuti or RR Lyrae strata",
                "sealed confirmatory holdout",
                "transparent-shell detection",
                "stellar or shell mass inference",
            ],
        },
    }


def plot_results(output: Path, rows: list[dict[str, Any]], all_predictions: dict[str, dict[str, np.ndarray]]) -> list[Path]:
    import matplotlib.pyplot as plt

    figures: list[Path] = []
    labels = [row["star_id"].replace("OGLE-LMC-CEP-", "") for row in rows]
    x = np.arange(len(rows))
    models = [
        ("derd_g", "DERD-G"),
        ("derd_k", "DERD-K"),
        ("fourier_order2", "Fourier order 2"),
        ("fourier_bic", "Fourier stable BIC"),
    ]

    fig, ax = plt.subplots(figsize=(14, 6))
    for key, label in models:
        ax.plot(x, [row[f"test_{key}_rmse"] for row in rows], marker="o", label=label)
    ax.set_xticks(x, labels, rotation=70)
    ax.set_yscale("log")
    ax.set_ylabel("Held-out RMSE on train-scaled relative flux (log scale)")
    ax.set_xlabel("OGLE-LMC-CEP identifier suffix")
    ax.set_title("Phase-02 held-out error by star")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = output / "heldout_rmse_by_star.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    winners = Counter(row["winner"] for row in rows)
    fig, ax = plt.subplots(figsize=(8, 5))
    names = [key for key, _ in models]
    display = [label for _, label in models]
    ax.bar(display, [winners.get(name, 0) for name in names])
    ax.set_ylabel("Stars won by held-out RMSE")
    ax.set_title("Model win count in the 20-star shakedown")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    path = output / "model_win_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(x, [row["derd_g_condition_number"] for row in rows], marker="o", label="DERD-G")
    ax.plot(x, [row["derd_k_condition_number"] for row in rows], marker="o", label="DERD-K")
    ax.axhline(1e5, linestyle="--", label="warning gate 1e5")
    ax.set_yscale("log")
    ax.set_xticks(x, labels, rotation=70)
    ax.set_ylabel("Jacobian condition number")
    ax.set_title("Local DERD parameter identifiability audit")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    path = output / "condition_numbers.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(9, 5))
    deltas = [row["derd_minus_fourier_rmse"] for row in rows]
    ax.axhline(0.0, linestyle="--")
    ax.bar(labels, deltas)
    ax.set_ylabel("best DERD RMSE minus best Fourier RMSE")
    ax.set_xlabel("OGLE-LMC-CEP identifier suffix")
    ax.set_title("Negative values favour DERD; positive values favour Fourier")
    ax.tick_params(axis="x", rotation=70)
    fig.tight_layout()
    path = output / "derd_fourier_rmse_delta.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    ranked = sorted(rows, key=lambda row: row["derd_minus_fourier_rmse"])
    representative = [ranked[0], ranked[-1]]
    for rank_label, row in zip(("derd_best_case", "derd_worst_case"), representative, strict=True):
        star = row["star_id"]
        predictions = all_predictions[star]
        order = np.argsort(predictions["phase"])
        test = predictions["is_test"].astype(bool)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.errorbar(
            predictions["phase"][~test],
            predictions["observed"][~test],
            yerr=predictions["observed_error"][~test],
            fmt="o",
            label="training observations",
        )
        ax.errorbar(
            predictions["phase"][test],
            predictions["observed"][test],
            yerr=predictions["observed_error"][test],
            fmt="s",
            label="held-out observations",
        )
        for key, display_name in models:
            ax.plot(predictions["phase"][order], predictions[key][order], label=display_name)
        ax.set_xlabel("Phase relative to training-estimated maximum")
        ax.set_ylabel("Relative flux scaled from training data only")
        ax.set_title(f"{star}: {rank_label.replace('_', ' ')}")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = output / f"{rank_label}_{star}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(path)
    return figures


def build_report(summary: dict[str, Any], rows: list[dict[str, Any]], bootstrap: dict[str, Any]) -> str:
    rmse = summary["heldout_rmse"]
    lines = [
        "# Phase 02 result: 20-Cepheid observational shakedown",
        "",
        "## Gate decision",
        "",
        f"**{summary['status']}**",
        "",
        "The parser, provenance manifest, magnitude-to-flux conversion, star-level identity controls, "
        "circular phase-block holdout, training-only epoch and scaling, DERD-G/DERD-K fits, Fourier "
        "baselines, residual metrics, and identifiability diagnostics executed end to end.",
        "",
        "This is not a confirmatory proof of C17. The local capsule contains only the first 24 mirrored "
        "I-band observations of each target. It is intentionally a small engineering shakedown.",
        "",
        "## Aggregate results",
        "",
        f"- Targets: {summary['target_count']} (10 fundamental-mode F, 10 first-overtone 1O)",
        f"- Observations: {summary['observation_count_total']} total, "
        f"{summary['train_count_total']} training, {summary['test_count_total']} held out",
        f"- Best DERD beats best Fourier on {summary['best_derd_beats_best_fourier_count']} targets",
        f"- Best Fourier beats or ties best DERD on {summary['best_fourier_beats_or_ties_best_derd_count']} targets",
        f"- Median best-DERD minus best-Fourier RMSE: {summary['derd_minus_fourier_rmse']['median']:.6f}",
        f"- Training-only Fourier stability gate rejected at least one order for "
        f"{summary['fourier_stability_gate']['targets_with_rejected_orders']} targets",
        f"- Raw ungated BIC produced held-out RMSE above 1 on "
        f"{summary['fourier_stability_gate']['raw_bic_test_rmse_over_1']} targets; retained as a diagnostic",
        "",
        "| Model | Median held-out RMSE | Mean held-out RMSE | Wins |",
        "|---|---:|---:|---:|",
    ]
    labels = {
        "derd_g": "DERD-G",
        "derd_k": "DERD-K",
        "fourier_order2": "Fourier order 2",
        "fourier_bic": "Fourier stability-gated BIC",
    }
    for key in labels:
        lines.append(
            f"| {labels[key]} | {rmse[key]['median']:.6f} | {rmse[key]['mean']:.6f} | "
            f"{summary['winner_counts'].get(key, 0)} |"
        )
    lines.extend([
        "",
        "| Mode | Targets | DERD wins | Median best DERD RMSE | Median best Fourier RMSE | Median difference |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for mode, payload in summary["mode_summary"].items():
        lines.append(
            f"| {mode} | {payload['target_count']} | {payload['best_derd_beats_best_fourier_count']} | "
            f"{payload['median_best_derd_rmse']:.6f} | {payload['median_best_fourier_rmse']:.6f} | "
            f"{payload['median_derd_minus_fourier_rmse']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Per-star results",
            "",
            "| Star | Mode | Period (d) | Winner | Best DERD RMSE | Best Fourier RMSE | Difference | BIC order |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['star_id']} | {row['mode']} | {row['period_days']:.7f} | {row['winner']} | "
            f"{row['best_derd_rmse']:.6f} | {row['best_fourier_rmse']:.6f} | "
            f"{row['derd_minus_fourier_rmse']:.6f} | {row['fourier_bic_order']} |"
        )
    lines.extend(
        [
            "",
            "## Identifiability gate",
            "",
            f"Median Jacobian condition number: DERD-G "
            f"{summary['identifiability']['derd_g_condition_median']:.3g}, DERD-K "
            f"{summary['identifiability']['derd_k_condition_median']:.3g}.",
            "",
            f"Fits exceeding the provisional 1e5 warning gate: DERD-G "
            f"{summary['identifiability']['derd_g_condition_over_1e5']}, DERD-K "
            f"{summary['identifiability']['derd_k_condition_over_1e5']}.",
            "",
            f"Warning-gated stars: {', '.join(summary['identifiability']['warning_stars']) or 'none'}.",
            "",
            "Parameters from warning-gated fits must not be interpreted as unique physical measurements.",
            "",
            f"The local period-verification grid hit its +/-0.1 percent boundary for "
            f"{summary['period_check']['grid_boundary_hits']} stars, so those checks require a wider follow-up scan.",
            "",
            "## Bootstrap spot checks",
            "",
        ]
    )
    if bootstrap:
        for star_id, payload in bootstrap.items():
            lines.append(
                f"- `{star_id}`: {payload['repetitions_succeeded']}/{payload['repetitions_requested']} fits "
                f"succeeded; phase circular standard deviation {payload['phase_circular_std']:.5f}."
            )
    else:
        lines.append("Bootstrap execution was disabled; the implementation and unit tests are present.")
    lines.extend(
        [
            "",
            "## Scientific boundary",
            "",
            "The first pass exposed high-order Fourier instability on sparse phase blocks. The final run keeps "
            "the raw BIC result for audit and adds a training-only condition/span gate without inspecting held-out data.",
            "",
            "The shakedown tests whether a corrected four-dimensional DERD waveform can be fit and evaluated "
            "without information leakage. It does not test the paper's claims that all pulsators possess a "
            "transparent outer shell, that motion is solely gravitational, or that shell mass can be inferred "
            "from normalized photometry.",
            "",
            "## Next promotion gate",
            "",
            "1. Retrieve complete official OGLE light curves and verify checksums.",
            "2. Freeze a larger star-identity development set and an untouched final holdout.",
            "3. Add RR Lyrae and Delta Scuti strata before evaluating broad C17 wording.",
            "4. Add periodic spline/PCA/Gaussian-process baselines and uncertainty calibration.",
            "5. Keep physical shell claims closed until independent non-photometric predictions exist.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/manifests/phase02_targets.csv")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-directory", default="artifacts/phase02")
    parser.add_argument("--starts", type=int, default=4)
    parser.add_argument("--max-function-evaluations", type=int, default=180)
    parser.add_argument("--normalization-grid-size", type=int, default=512)
    parser.add_argument("--peak-grid-size", type=int, default=256)
    parser.add_argument("--period-grid-count", type=int, default=101)
    parser.add_argument("--bootstrap-repetitions", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output_directory)
    output.mkdir(parents=True, exist_ok=True)
    (output / "details").mkdir(exist_ok=True)
    (output / "predictions").mkdir(exist_ok=True)

    records = read_target_manifest(args.manifest)
    config = ValidationConfig(
        starts=args.starts,
        maximum_function_evaluations=args.max_function_evaluations,
        normalization_grid_size=args.normalization_grid_size,
        peak_grid_size=args.peak_grid_size,
        period_grid_count=args.period_grid_count,
    )
    benchmarks = benchmark_targets(records, data_root=args.data_root, config=config)
    rows = [item.row for item in benchmarks]
    write_csv(output / "phase02_star_results.csv", rows)

    all_predictions: dict[str, dict[str, np.ndarray]] = {}
    details: dict[str, Any] = {}
    for benchmark in benchmarks:
        star_id = benchmark.row["star_id"]
        all_predictions[star_id] = benchmark.predictions
        details[star_id] = benchmark.detail
        (output / "details" / f"{star_id}.json").write_text(
            json.dumps(finite_json(benchmark.detail), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_predictions(output / "predictions" / f"{star_id}.csv", benchmark.predictions)

    summary = aggregate(rows)
    bootstrap_payload: dict[str, Any] = {}
    if args.bootstrap_repetitions >= 2:
        selected_ids = {
            "OGLE-LMC-CEP-0001",
            "OGLE-LMC-CEP-0006",
            "OGLE-LMC-CEP-0002",
            "OGLE-LMC-CEP-0023",
        }
        by_id = {benchmark.row["star_id"]: benchmark for benchmark in benchmarks}
        for offset, star_id in enumerate(sorted(selected_ids)):
            benchmark = by_id[star_id]
            split = benchmark.detail["split"]
            train = np.asarray(split["train_indices"], dtype=np.int64)
            predictions = benchmark.predictions
            weights = inverse_variance_weights(predictions["observed_error"])[train]
            stability = bootstrap_fit_stability(
                predictions["phase"][train],
                predictions["observed"][train],
                weights=weights,
                repetitions=args.bootstrap_repetitions,
                seed=20260807 + offset * 100,
                starts=3,
                max_function_evaluations=120,
            )
            bootstrap_payload[star_id] = stability.as_dict()
    summary["bootstrap_spot_checks"] = bootstrap_payload
    summary["configuration"] = finite_json(config.__dict__ if hasattr(config, "__dict__") else {
        field: getattr(config, field) for field in config.__dataclass_fields__
    })
    summary["source_manifest_sha256"] = sha256_file("data/manifests/phase02_source_manifest.json")
    (output / "phase02_summary.json").write_text(
        json.dumps(finite_json(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "phase02_details.json").write_text(
        json.dumps(finite_json(details), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    figures = plot_results(output, rows, all_predictions)
    report = build_report(summary, rows, bootstrap_payload)
    (output / "PHASE02_RESULT.md").write_text(report, encoding="utf-8")

    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "cwd": os.getcwd(),
        "configuration": finite_json(summary["configuration"]),
        "figure_files": [path.name for path in figures],
    }
    try:
        import scipy
        environment["scipy"] = scipy.__version__
    except Exception:
        pass
    try:
        import matplotlib
        environment["matplotlib"] = matplotlib.__version__
    except Exception:
        pass
    (output / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(finite_json(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
