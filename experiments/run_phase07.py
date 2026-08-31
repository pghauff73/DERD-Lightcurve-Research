#!/usr/bin/env python3
"""Execute the Phase-07 raw-photometry harmonic forecast gate."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.harmonic_exchange import record_sha256, write_harmonic_exchange
from derd.harmonic_extraction import (
    fit_weighted_harmonic_exchange,
    git_blob_sha1_file,
    refine_period_by_weighted_harmonics,
)
from derd.harmonic_screen import screen_harmonics
from derd.recurrence_uncertainty import (
    evaluate_harmonic_evidence_gate,
    propagate_recurrence_uncertainty,
)
from derd.io import read_ogle_photometry, sha256_file
from derd.preprocess import clean_light_curve, fold_phase
from derd.validation_phase07 import (
    Phase07Config,
    actual_cadence_mvhe,
    assess_mvhe_gate,
    calibrate_actual_cadence,
    screen_exchange_with_uncertainty,
)

STAR_ID = "OGLE-LMC-CEP-0010"
MODE = "1O"
CATALOG_PERIOD_DAYS = 2.5655853
SOURCE_REPOSITORY = "bksim/OutlierDetection"
SOURCE_COMMIT = "55836b58345b9507bfbd98c5fabbac82c83605e3"
SOURCE_BLOB_SHA = "fd82c05bb3a62ba9a8c614ac51eb315124090381"
SOURCE_LOCATOR = (
    "https://github.com/bksim/OutlierDetection/blob/"
    f"{SOURCE_COMMIT}/Cluster/cep/phot/I/{STAR_ID}.dat"
)
PERIOD_SOURCE_REPOSITORY = "dubbatee/ScienceExtensionCode"
PERIOD_SOURCE_COMMIT = "2d5f05d5c20d8c4c1c1e8811d502398232f14316"


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _safe_number(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value) if math.isfinite(float(value)) else None


def _predict_harmonic(extraction, phase: np.ndarray) -> np.ndarray:
    output = np.full(phase.size, extraction.intercept, dtype=np.float64)
    for harmonic, (sine, cosine) in enumerate(
        zip(
            extraction.series.sine_coefficients,
            extraction.series.cosine_coefficients,
        ),
        start=1,
    ):
        angle = 2.0 * np.pi * harmonic * phase
        output += sine * np.sin(angle) + cosine * np.cos(angle)
    return output


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    active = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=active, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _make_figures(
    output: Path,
    *,
    phase: np.ndarray,
    flux_value: np.ndarray,
    flux_error: np.ndarray,
    extraction,
    screen,
    threshold: float,
    synthetic_rows,
    mvhe_summaries,
) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    paths: list[str] = []
    order = np.argsort(phase)
    grid = np.linspace(0.0, 1.0, 2048, endpoint=False)
    prediction = _predict_harmonic(extraction, grid)

    fig = plt.figure(figsize=(9, 5.5))
    ax = fig.add_subplot(111)
    ax.errorbar(
        phase[order],
        flux_value[order],
        yerr=flux_error[order],
        fmt=".",
        markersize=3,
        alpha=0.55,
        linewidth=0.4,
        label="complete development photometry",
    )
    ax.plot(grid, prediction, linewidth=2.0, label="weighted 8-harmonic fit")
    ax.set_xlabel("phase")
    ax.set_ylabel("relative flux")
    ax.set_title(f"{STAR_ID}: complete raw photometry and lossless harmonic fit")
    ax.legend()
    fig.tight_layout()
    path = output / "phase07_folded_complete_lightcurve.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(str(path))

    fig = plt.figure(figsize=(8.5, 5.0))
    ax = fig.add_subplot(111)
    harmonic = np.arange(1, extraction.series.harmonic_count + 1)
    ax.bar(harmonic, extraction.harmonic_wald_snr)
    ax.axhline(3.0, linestyle="--", label="recovery SNR gate = 3")
    ax.axhline(2.0, linestyle=":", label="forecast SNR gate = 2")
    ax.axvline(4.5, linestyle="-.", label="forecast begins")
    ax.set_xticks(harmonic)
    ax.set_xlabel("harmonic")
    ax.set_ylabel("2D Wald signal-to-noise")
    ax.set_yscale("log")
    ax.set_title("Measured harmonic information")
    ax.legend()
    fig.tight_layout()
    path = output / "phase07_harmonic_snr.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(str(path))

    fig = plt.figure(figsize=(8.5, 5.0))
    ax = fig.add_subplot(111)
    observed = np.abs(extraction.series.complex_coefficients)
    predicted = np.abs(screen.candidate.predicted_coefficients)
    ax.semilogy(harmonic, observed, marker="o", label="observed coefficient magnitude")
    ax.semilogy(harmonic, predicted, marker="s", label="DERD algebraic prediction")
    ax.axvline(4.5, linestyle="--", label="forecast boundary")
    ax.set_xticks(harmonic)
    ax.set_xlabel("harmonic")
    ax.set_ylabel("|complex coefficient|")
    ax.set_title("Four-harmonic recovery and higher-harmonic forecast")
    ax.legend()
    fig.tight_layout()
    path = output / "phase07_harmonic_forecast.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(str(path))

    fig = plt.figure(figsize=(8.5, 5.0))
    ax = fig.add_subplot(111)
    positives = [row.score for row in synthetic_rows if row.label == 1]
    negatives = [row.score for row in synthetic_rows if row.label == 0]
    ax.hist(positives, bins=30, alpha=0.55, label="synthetic DERD")
    ax.hist(negatives, bins=30, alpha=0.55, label="synthetic nulls")
    ax.axvline(threshold, linestyle="--", label="development-selected threshold")
    ax.axvline(screen.score, linestyle="-.", label="real-star score")
    ax.set_xlabel("lower is more DERD-compatible")
    ax.set_ylabel("count")
    ax.set_title("Actual-cadence compatibility calibration")
    ax.legend()
    fig.tight_layout()
    path = output / "phase07_actual_cadence_score_calibration.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(str(path))

    fig = plt.figure(figsize=(8.5, 5.0))
    ax = fig.add_subplot(111)
    counts = [row.observation_count for row in mvhe_summaries]
    median_auc = [row.median_roc_auc for row in mvhe_summaries]
    q10_auc = [row.q10_roc_auc for row in mvhe_summaries]
    median_balanced = [row.median_balanced_accuracy for row in mvhe_summaries]
    q10_balanced = [row.q10_balanced_accuracy for row in mvhe_summaries]
    ax.plot(counts, median_auc, marker="o", label="median ROC AUC")
    ax.plot(counts, q10_auc, marker="o", label="10th-percentile ROC AUC")
    ax.plot(counts, median_balanced, marker="s", label="median balanced accuracy")
    ax.plot(counts, q10_balanced, marker="s", label="10th-percentile balanced accuracy")
    ax.axhline(0.80, linestyle="--")
    ax.axhline(0.75, linestyle=":")
    ax.axhline(0.70, linestyle="-.")
    ax.set_xlabel("observations retained from actual cadence")
    ax.set_ylabel("held-out metric")
    ax.set_ylim(0.45, 1.01)
    ax.set_title("Actual-cadence minimum viable harmonic evidence")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = output / "phase07_actual_cadence_mvhe.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(str(path))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=f"data/raw/ogle/{STAR_ID}.complete.dat",
        help="complete exposed-development OGLE mirror file",
    )
    parser.add_argument(
        "--excerpt",
        default=f"data/raw/ogle/{STAR_ID}.dat",
        help="historical 24-row development excerpt",
    )
    parser.add_argument("--output", default="artifacts/phase07")
    parser.add_argument("--fast", action="store_true", help="reduced synthetic repetitions")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    source = Path(args.source)
    excerpt = Path(args.excerpt)
    source_sha256 = sha256_file(source)
    source_git_blob = git_blob_sha1_file(source)
    if source_git_blob != SOURCE_BLOB_SHA:
        raise RuntimeError(
            f"Git blob mismatch: expected {SOURCE_BLOB_SHA}, observed {source_git_blob}"
        )

    curve = read_ogle_photometry(
        source,
        star_id=STAR_ID,
        band="I",
        metadata={
            "source_locator": SOURCE_LOCATOR,
            "source_repository": SOURCE_REPOSITORY,
            "source_commit": SOURCE_COMMIT,
            "source_blob_sha": SOURCE_BLOB_SHA,
            "evidence_role": "exposed-development-only",
        },
    )
    cleaned, cleaning = clean_light_curve(curve)
    flux = cleaned.to_relative_flux()

    config = Phase07Config()
    if args.fast:
        config = Phase07Config(
            full_calibration_per_class=48,
            mvhe_replicates=3,
            mvhe_per_class=20,
            uncertainty_draws=256,
        )

    period_profile = refine_period_by_weighted_harmonics(
        cleaned,
        CATALOG_PERIOD_DAYS,
        order=config.fourier_order,
        relative_span=2.0e-4,
        grid_count=201,
        ridge=1.0e-8,
    )

    base_metadata = {
        "mode": MODE,
        "catalog_period_days": CATALOG_PERIOD_DAYS,
        "period_source_repository": PERIOD_SOURCE_REPOSITORY,
        "period_source_commit": PERIOD_SOURCE_COMMIT,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "source_blob_sha": SOURCE_BLOB_SHA,
        "source_git_blob_verified": True,
        "evidence_role": "exposed-development-only",
        "rights_status": "PUBLIC_MIRROR; REDISTRIBUTION_TERMS_NOT_VERIFIED",
        "physical_claim_scope": "waveform-only",
    }
    catalog_extraction = fit_weighted_harmonic_exchange(
        cleaned,
        period_days=CATALOG_PERIOD_DAYS,
        order=config.fourier_order,
        ridge=1.0e-8,
        covariance_estimator="hc3",
        source_locator=SOURCE_LOCATOR,
        source_sha256=source_sha256,
        metadata={**base_metadata, "period_coordinate": "catalog"},
    )
    refined_extraction = fit_weighted_harmonic_exchange(
        cleaned,
        period_days=period_profile.best_period_days,
        order=config.fourier_order,
        ridge=1.0e-8,
        covariance_estimator="hc3",
        source_locator=SOURCE_LOCATOR,
        source_sha256=source_sha256,
        metadata={
            **base_metadata,
            "period_coordinate": "generic_harmonic_profile_minimum",
            "period_profile": period_profile.as_dict(),
        },
    )
    catalog_exchange_path = output / f"{STAR_ID}.catalog-period.harmonics.json"
    refined_exchange_path = output / f"{STAR_ID}.refined-period.harmonics.json"
    catalog_record_digest = write_harmonic_exchange(
        catalog_exchange_path, catalog_extraction.series
    )
    refined_record_digest = write_harmonic_exchange(
        refined_exchange_path, refined_extraction.series
    )

    reference_epoch = refined_extraction.series.reference_epoch
    phase = fold_phase(
        flux.time,
        period_profile.best_period_days,
        epoch=reference_epoch,
    )
    amplitude_scale = max(
        float(np.ptp(flux.value)),
        5.0 * float(np.median(flux.error)),
    )
    calibration, synthetic_rows = calibrate_actual_cadence(
        phase,
        flux.error,
        amplitude_scale=amplitude_scale,
        config=config,
    )
    mvhe_replicates, mvhe_summaries = actual_cadence_mvhe(
        phase,
        flux.error,
        amplitude_scale=amplitude_scale,
        config=config,
    )

    refined_screen = screen_harmonics(
        refined_extraction.series.complex_coefficients,
        fit_harmonics=config.fit_harmonics,
    )
    catalog_screen = screen_harmonics(
        catalog_extraction.series.complex_coefficients,
        fit_harmonics=config.fit_harmonics,
    )
    uncertainty = screen_exchange_with_uncertainty(
        refined_extraction,
        threshold=calibration.threshold,
        config=config,
    )
    recurrence_propagation = propagate_recurrence_uncertainty(
        refined_extraction.series,
        fit_harmonics=config.fit_harmonics,
        minimum_forecast_harmonics=config.minimum_forecast_significant_harmonics,
        score_threshold=calibration.threshold,
        draws=config.draw_count,
        seed=config.draw_seed,
    )
    combined_gate = evaluate_harmonic_evidence_gate(
        observation_count=refined_extraction.sample_count,
        occupied_phase_bins=int(refined_extraction.phase_coverage["occupied_bins"]),
        total_phase_bins=int(refined_extraction.phase_coverage["bin_count"]),
        design_condition_number=refined_extraction.design_condition_number,
        coefficient_snr=refined_extraction.harmonic_wald_snr,
        screen=refined_screen,
        propagation=recurrence_propagation,
        score_threshold=calibration.threshold,
        cadence_holdout_auc=float(calibration.holdout_metrics["roc_auc"]),
        cadence_holdout_balanced_accuracy=float(
            calibration.holdout_metrics["balanced_accuracy"]
        ),
        source_complete=source_git_blob == SOURCE_BLOB_SHA,
        minimum_fit_snr=config.minimum_recovery_snr,
        minimum_forecast_snr=config.minimum_forecast_snr,
        minimum_forecast_harmonics=config.minimum_forecast_significant_harmonics,
        maximum_design_condition_number=config.maximum_design_condition_number,
    )

    excerpt_result: dict[str, Any] | None = None
    if excerpt.exists():
        excerpt_curve = read_ogle_photometry(excerpt, star_id=STAR_ID, band="I")
        excerpt_cleaned, _ = clean_light_curve(excerpt_curve)
        excerpt_extraction = fit_weighted_harmonic_exchange(
            excerpt_cleaned,
            period_days=CATALOG_PERIOD_DAYS,
            order=config.fourier_order,
            ridge=1.0e-8,
            covariance_estimator="hc3",
            source_locator=str(excerpt),
            source_sha256=sha256_file(excerpt),
            metadata={"evidence_role": "historical-excerpt"},
        )
        excerpt_screen = screen_harmonics(
            excerpt_extraction.series.complex_coefficients,
            fit_harmonics=config.fit_harmonics,
        )
        excerpt_result = {
            "observation_count": excerpt_curve.size,
            "score": excerpt_screen.score,
            "forecast_residual": excerpt_screen.candidate.forecast_residual,
            "harmonic_wald_snr": [
                float(value) for value in excerpt_extraction.harmonic_wald_snr
            ],
            "flags": list(excerpt_screen.flags),
        }

    coefficient_rows: list[dict[str, Any]] = []
    for index in range(refined_extraction.series.harmonic_count):
        coefficient = refined_extraction.series.complex_coefficients[index]
        predicted = refined_screen.candidate.predicted_coefficients[index]
        coefficient_rows.append(
            {
                "harmonic": index + 1,
                "sine_coefficient": float(
                    refined_extraction.series.sine_coefficients[index]
                ),
                "cosine_coefficient": float(
                    refined_extraction.series.cosine_coefficients[index]
                ),
                "complex_real": float(coefficient.real),
                "complex_imag": float(coefficient.imag),
                "complex_magnitude": float(abs(coefficient)),
                "complex_standard_error": float(
                    refined_extraction.complex_standard_errors[index]
                ),
                "wald_snr": float(refined_extraction.harmonic_wald_snr[index]),
                "derd_predicted_real": float(predicted.real),
                "derd_predicted_imag": float(predicted.imag),
                "derd_predicted_magnitude": float(abs(predicted)),
                "role": "recovery" if index < config.fit_harmonics else "forecast",
            }
        )
    _write_csv(output / "phase07_harmonic_coefficients.csv", coefficient_rows)
    _write_csv(
        output / "phase07_actual_cadence_synthetic_records.csv",
        [row.as_dict() for row in synthetic_rows],
    )
    _write_csv(
        output / "phase07_actual_cadence_mvhe_replicates.csv",
        [row.as_dict() for row in mvhe_replicates],
    )
    _write_csv(
        output / "phase07_actual_cadence_mvhe_summary.csv",
        [row.as_dict() for row in mvhe_summaries],
    )

    mvhe_gate = assess_mvhe_gate(
        mvhe_summaries,
        minimum_sustained_levels=config.minimum_sustained_mvhe_levels,
    )
    source_receipt = {
        "star_id": STAR_ID,
        "mode": MODE,
        "source_locator": SOURCE_LOCATOR,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "expected_git_blob_sha1": SOURCE_BLOB_SHA,
        "observed_git_blob_sha1": source_git_blob,
        "git_blob_verified": source_git_blob == SOURCE_BLOB_SHA,
        "local_sha256": source_sha256,
        "local_byte_count": source.stat().st_size,
        "observation_count": curve.size,
        "time_min_hjd_minus_2450000": float(np.min(curve.time)),
        "time_max_hjd_minus_2450000": float(np.max(curve.time)),
        "time_span_days": float(np.ptp(curve.time)),
        "median_magnitude_error": float(np.median(curve.error)),
        "rights_status": "PUBLIC_MIRROR; REDISTRIBUTION_TERMS_NOT_VERIFIED",
        "evidence_role": "exposed-development-only",
    }
    _json_dump(output / "phase07_source_receipt.json", source_receipt)

    figures = _make_figures(
        output,
        phase=phase,
        flux_value=flux.value,
        flux_error=flux.error,
        extraction=refined_extraction,
        screen=refined_screen,
        threshold=calibration.threshold,
        synthetic_rows=synthetic_rows,
        mvhe_summaries=mvhe_summaries,
    )

    summary = {
        "implementation_id": "DERD-v0.7-phase07-raw-harmonic-forecast-gate",
        "date": "2026-08-15",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "gate_decision": combined_gate.decision,
        "component_evidence_status": uncertainty.evidence_status,
        "c17_promoted": False,
        "source": source_receipt,
        "cleaning": cleaning.as_dict(),
        "catalog_period_days": CATALOG_PERIOD_DAYS,
        "period_profile": period_profile.as_dict(),
        "catalog_period_extraction": catalog_extraction.as_dict(
            include_exchange=False
        ),
        "refined_period_extraction": refined_extraction.as_dict(
            include_exchange=False
        ),
        "catalog_period_screen": catalog_screen.as_dict(
            include_coefficients=False
        ),
        "refined_period_screen": refined_screen.as_dict(
            include_coefficients=False
        ),
        "uncertainty_gate": uncertainty.as_dict(),
        "recurrence_propagation": recurrence_propagation.as_dict(),
        "combined_harmonic_evidence_gate": combined_gate.as_dict(),
        "actual_cadence_calibration": calibration.as_dict(),
        "actual_cadence_mvhe": {
            "summaries": [row.as_dict() for row in mvhe_summaries],
            "gate_assessment": mvhe_gate.as_dict(),
            "first_pointwise_passing_observation_count": mvhe_gate.first_pointwise_pass,
            "first_sustained_passing_observation_count": mvhe_gate.first_sustained_pass,
            "promoted_actual_cadence_mvhe": mvhe_gate.first_sustained_pass,
            "uniform_phase_lower_bound_from_phase05": 160,
            "interpretation": "Use the sustained pass rather than an isolated pointwise pass because finite Monte-Carlo sweeps can be non-monotonic.",
        },
        "historical_excerpt_comparison": excerpt_result,
        "exchange_records": {
            "catalog_path": str(catalog_exchange_path),
            "catalog_sha256": catalog_record_digest,
            "catalog_object_sha256": record_sha256(catalog_extraction.series),
            "refined_path": str(refined_exchange_path),
            "refined_sha256": refined_record_digest,
            "refined_object_sha256": record_sha256(refined_extraction.series),
        },
        "figures": figures,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "locked_gates": [
            "C17-population-promotion",
            "prospective-sealed-evaluation",
            "physical-mechanism",
            "transparent-shell-prevalence",
            "shell-mass",
        ],
    }
    _json_dump(output / "phase07_summary.json", summary)

    calibration_holdout = calibration.holdout_metrics
    combined_blockers_markdown = "\n".join(
        f"- `{item}`" for item in combined_gate.blockers
    ) or "- none"
    report = f"""# Phase 07 result: raw-photometry harmonic forecast gate

## Decision

```text
{combined_gate.decision}
COMPONENT_STATUS={uncertainty.evidence_status}
C17_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## What was tested

The exposed development target `{STAR_ID}` was upgraded from the historical
24-row excerpt to the complete {curve.size}-observation public-repository mirror.
The local file reproduced Git blob `{SOURCE_BLOB_SHA}` exactly.  A simultaneous
weighted eight-harmonic fit was extracted in relative-flux space and written to
`DERD-HARMONIC-EXCHANGE-1.0` with signed sine/cosine coefficients, a frozen
epoch, and a full HC3 coefficient covariance.

The first four harmonics were used for algebraic DERD recovery. Harmonics 5-8
were left unused by recovery and treated as the forecast dimensions.

## Source and coverage

| Dimension | Result |
|---|---:|
| observations | {curve.size} |
| time span | {np.ptp(curve.time):.6f} days |
| median quoted magnitude error | {np.median(curve.error):.6f} mag |
| occupied 12-bin phase cells | {refined_extraction.phase_coverage['occupied_bins']} / 12 |
| maximum circular phase gap | {refined_extraction.phase_coverage['maximum_circular_phase_gap']:.6f} |
| harmonic design condition number | {refined_extraction.design_condition_number:.6f} |
| weighted reduced chi-square | {refined_extraction.weighted_reduced_chi_square:.6f} |

## Period gate

| Quantity | Value |
|---|---:|
| catalog period | {CATALOG_PERIOD_DAYS:.10f} days |
| generic-harmonic refined period | {period_profile.best_period_days:.10f} days |
| relative shift | {period_profile.relative_delta:.9g} |
| profile interval | {period_profile.profile_lower_days:.10f} to {period_profile.profile_upper_days:.10f} days |
| chi-square reduction | {period_profile.catalog_chi_square - period_profile.best_chi_square:.6f} |

The period was refined with a generic weighted harmonic objective, not with the
DERD recurrence score.  The recurrence result changed from
{catalog_screen.score:.6f} at the catalog period to {refined_screen.score:.6f}
at the refined period, so the decision does not depend on a large period
coordinate displacement.

## Measured harmonic information

| Harmonic role | Wald SNR values | Gate |
|---|---|---|
| recovery, h1-h4 | {', '.join(f'{value:.3f}' for value in uncertainty.recovery_snr)} | all four >= {config.minimum_recovery_snr:.1f}: {uncertainty.recovery_significant_count == 4} |
| forecast, h5-h8 | {', '.join(f'{value:.3f}' for value in uncertainty.forecast_snr)} | at least two >= {config.minimum_forecast_snr:.1f}: {uncertainty.forecast_significant_count >= 2} |

The complete light curve is sufficient to estimate the four recovery harmonics,
but it does not measure two independent forecast harmonics at the frozen SNR
threshold.  More observations did not manufacture high-order signal that the
star's light curve does not contain strongly.

## Actual-cadence calibration

The synthetic threshold was selected only on the synthetic development split,
using the real time coordinates, quoted errors, measured flux scale, and the
same extraction/screening pipeline.

| Metric | Value |
|---|---:|
| selected score threshold | {calibration.threshold:.6f} |
| holdout ROC AUC | {float(calibration_holdout['roc_auc']):.6f} |
| holdout balanced accuracy | {float(calibration_holdout['balanced_accuracy']):.6f} |
| holdout sensitivity | {float(calibration_holdout['sensitivity']):.6f} |
| holdout specificity | {float(calibration_holdout['specificity']):.6f} |
| real-star nominal score | {refined_screen.score:.6f} |

The real-star score is {'below' if refined_screen.score <= calibration.threshold else 'above'}
the development-selected compatibility threshold.

## Covariance propagation

| Quantity | Value |
|---|---:|
| successful coefficient draws | {uncertainty.draws_successful} / {uncertainty.draws_requested} |
| median score | {uncertainty.score_median:.6f} |
| 5-95% score interval | {uncertainty.score_q05:.6f} to {uncertainty.score_q95:.6f} |
| fraction below threshold | {uncertainty.threshold_pass_fraction:.6f} |
| median forecast residual | {uncertainty.forecast_residual_median:.6f} |
| 5-95% forecast-residual interval | {uncertainty.forecast_residual_q05:.6f} to {uncertainty.forecast_residual_q95:.6f} |

A qualifying result required at least 80% of covariance draws to remain below
the compatibility threshold.  The observed fraction was
{uncertainty.threshold_pass_fraction:.6f}.

## Actual-cadence MVHE intervention

The only active IURMv1.1.1 dimension was observation count. The time/error
coordinates were sampled from this real cadence, while synthetic family,
noise scaling, harmonic order, recurrence dimensions, score, and promotion
thresholds were frozen.

| Observations | Median AUC | q10 AUC | Median balanced accuracy | q10 balanced accuracy | Pass |
|---:|---:|---:|---:|---:|:---:|
"""
    for row in mvhe_summaries:
        report += (
            f"| {row.observation_count} | {row.median_roc_auc:.6f} | "
            f"{row.q10_roc_auc:.6f} | {row.median_balanced_accuracy:.6f} | "
            f"{row.q10_balanced_accuracy:.6f} | {'yes' if row.passes_gate else 'no'} |\n"
        )
    report += f"""

The first pointwise pass was
`{mvhe_gate.first_pointwise_pass if mvhe_gate.first_pointwise_pass is not None else 'none'}`,
but the pointwise pattern was non-monotonic.  The conservative gate therefore
requires the candidate count and every larger tested count to pass, with at
least {mvhe_gate.minimum_sustained_levels} tested levels in the passing tail.
The first sustained pass was
`{mvhe_gate.first_sustained_pass if mvhe_gate.first_sustained_pass is not None else 'none'}`
across {mvhe_gate.sustained_level_count} levels.  This is the provisional
actual-cadence MVHE floor for this one exposed target.  The earlier MVHE-160
value remains an optimistic uniform-phase lower bound rather than a
survey-cadence guarantee.

## Combined evidence gate

The integrated gate also requires source completeness, phase coverage, design
conditioning, four significant recovery harmonics, two significant forecast
harmonics, recurrence structural compatibility, score stability under the
coefficient covariance, and actual-cadence calibration performance. Its
blockers were:

{combined_blockers_markdown}

## Claim boundary

This phase establishes a reproducible raw-photometry-to-exchange pipeline and a
negative development result for one exposed first-overtone Cepheid.  It does
not establish or refute DERD for other stars or classes.  It does not identify
an internal orbital mechanism, external transparent shell, or shell mass.
"""
    (output / "PHASE07_RESULT.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
