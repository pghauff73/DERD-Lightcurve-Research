"""Phase-05 cadence-aware validation of the DERD harmonic triage engine."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .harmonic_screen import ComplexFourierFit, HarmonicScreenResult, fit_complex_fourier, screen_harmonics
from .io import TargetRecord, read_ogle_photometry
from .model import waveform
from .parameters import DERDParameters
from .period import adaptive_verify_catalog_period
from .preprocess import clean_light_curve, fold_phase
from .spectral import raw_derd_complex_coefficients


@dataclass(frozen=True, slots=True)
class Phase05Config:
    fourier_order: int = 8
    fit_harmonics: int = 4
    fourier_ridge: float = 1.0e-4
    synthetic_repetitions_per_class: int = 12
    synthetic_seed: int = 20260809
    development_fraction: float = 0.70
    bootstrap_repetitions: int = 64
    bootstrap_seed: int = 20260810
    minimum_harmonic_snr: float = 3.0
    minimum_snr_harmonics: int = 4
    maximum_design_condition_number: float = 1.0e4
    period_relative_spans: tuple[float, ...] = (0.001, 0.005, 0.02)
    period_grid_count: int = 101


@dataclass(frozen=True, slots=True)
class ThresholdCalibration:
    threshold: float
    development_metrics: dict[str, float | int]
    holdout_metrics: dict[str, float | int]

    def as_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "development_metrics": self.development_metrics,
            "holdout_metrics": self.holdout_metrics,
        }


@dataclass(frozen=True, slots=True)
class SyntheticScreenRecord:
    synthetic_id: str
    template_star_id: str
    label: int
    null_family: str
    noise_multiplier: float
    score: float
    flags: tuple[str, ...]
    split: str

    def as_dict(self) -> dict[str, object]:
        return {
            "synthetic_id": self.synthetic_id,
            "template_star_id": self.template_star_id,
            "label": self.label,
            "null_family": self.null_family,
            "noise_multiplier": self.noise_multiplier,
            "score": self.score,
            "flags": list(self.flags),
            "split": self.split,
        }


def _hash_fraction(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return integer / float(2**64)


def _classification_metrics(labels: NDArray[np.int64], scores: NDArray[np.float64], threshold: float) -> dict[str, float | int]:
    prediction = scores <= threshold
    positive = labels == 1
    negative = ~positive
    tp = int(np.count_nonzero(prediction & positive))
    fn = int(np.count_nonzero((~prediction) & positive))
    tn = int(np.count_nonzero((~prediction) & negative))
    fp = int(np.count_nonzero(prediction & negative))
    sensitivity = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    accuracy = (tp + tn) / max(1, labels.size)
    balanced = 0.5 * (sensitivity + specificity)
    positive_scores = scores[positive]
    negative_scores = scores[negative]
    if positive_scores.size and negative_scores.size:
        comparisons = positive_scores[:, None] - negative_scores[None, :]
        auc = float(
            (np.count_nonzero(comparisons < 0.0) + 0.5 * np.count_nonzero(comparisons == 0.0))
            / comparisons.size
        )
    else:
        auc = float("nan")
    return {
        "sample_count": int(labels.size),
        "positive_count": int(np.count_nonzero(positive)),
        "negative_count": int(np.count_nonzero(negative)),
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced),
        "roc_auc": auc,
    }


def calibrate_score_threshold(records: Iterable[SyntheticScreenRecord]) -> ThresholdCalibration:
    rows = tuple(records)
    development = [row for row in rows if row.split == "development"]
    holdout = [row for row in rows if row.split == "holdout"]
    if not development or not holdout:
        raise ValueError("both development and holdout synthetic records are required")
    development_scores = np.asarray([row.score for row in development], dtype=np.float64)
    development_labels = np.asarray([row.label for row in development], dtype=np.int64)
    finite = development_scores[np.isfinite(development_scores)]
    if finite.size < 2:
        raise ValueError("not enough finite development scores")
    unique = np.unique(finite)
    candidates = np.concatenate(
        (
            [np.nextafter(unique[0], -np.inf)],
            (unique[:-1] + unique[1:]) / 2.0,
            [np.nextafter(unique[-1], np.inf)],
        )
    )
    best_threshold = float(candidates[0])
    best_key = (-math.inf, -math.inf, math.inf)
    for threshold in candidates:
        metrics = _classification_metrics(development_labels, development_scores, float(threshold))
        key = (
            float(metrics["balanced_accuracy"]),
            float(metrics["specificity"]),
            -float(threshold),
        )
        if key > best_key:
            best_key = key
            best_threshold = float(threshold)
    development_metrics = _classification_metrics(
        development_labels, development_scores, best_threshold
    )
    holdout_scores = np.asarray([row.score for row in holdout], dtype=np.float64)
    holdout_labels = np.asarray([row.label for row in holdout], dtype=np.int64)
    holdout_metrics = _classification_metrics(
        holdout_labels, holdout_scores, best_threshold
    )
    return ThresholdCalibration(
        threshold=best_threshold,
        development_metrics=development_metrics,
        holdout_metrics=holdout_metrics,
    )


def _normalize_waveform(values: NDArray[np.float64]) -> NDArray[np.float64]:
    centered = values - float(np.mean(values))
    span = float(np.max(centered) - np.min(centered))
    if span <= np.finfo(np.float64).eps:
        raise ValueError("synthetic waveform is effectively constant")
    return centered / span


def _generic_fourier_signal(phase: NDArray[np.float64], *, rng: np.random.Generator, order: int) -> NDArray[np.float64]:
    decay = float(rng.uniform(0.20, 0.85))
    amplitudes = np.exp(-decay * np.arange(order, dtype=np.float64))
    amplitudes *= rng.uniform(0.5, 1.5, size=order)
    phases = np.cumsum(rng.normal(0.0, 1.35, size=order))
    values = np.zeros_like(phase)
    for harmonic in range(1, order + 1):
        values += amplitudes[harmonic - 1] * np.cos(
            2.0 * math.pi * harmonic * phase + phases[harmonic - 1]
        )
    return _normalize_waveform(values)


def _phase_scrambled_derd_signal(phase: NDArray[np.float64], *, rng: np.random.Generator, order: int) -> NDArray[np.float64]:
    parameters = DERDParameters(
        float(rng.uniform(0.03, 0.92)),
        float(rng.uniform(0.03, 0.92)),
        float(np.exp(rng.uniform(math.log(0.05), math.log(5.0)))),
        float(rng.random()),
    )
    coefficients = raw_derd_complex_coefficients(
        parameters, maximum_harmonic=order
    )[1:]
    scrambled = np.abs(coefficients) * np.exp(
        1j * rng.uniform(-math.pi, math.pi, size=order)
    )
    values = np.zeros_like(phase)
    for harmonic, coefficient in enumerate(scrambled, start=1):
        values += 2.0 * np.real(
            coefficient * np.exp(1j * 2.0 * math.pi * harmonic * phase)
        )
    return _normalize_waveform(values)


def _positive_derd_signal(phase: NDArray[np.float64], *, rng: np.random.Generator) -> NDArray[np.float64]:
    parameters = DERDParameters(
        float(rng.uniform(0.03, 0.92)),
        float(rng.uniform(0.03, 0.92)),
        float(np.exp(rng.uniform(math.log(0.05), math.log(5.0)))),
        float(rng.random()),
    )
    epoch = float(rng.random())
    values = waveform(
        np.mod(phase + epoch, 1.0),
        parameters,
        time_law="geometric",
        output_normalization="canonical",
        normalization_grid_size=1024,
    )
    if bool(rng.integers(0, 2)):
        values = -values
    return _normalize_waveform(np.asarray(values, dtype=np.float64))


def _safe_screen(fourier: ComplexFourierFit, *, fit_harmonics: int) -> tuple[float, tuple[str, ...]]:
    try:
        result = screen_harmonics(
            fourier.coefficients[1:],
            fit_harmonics=fit_harmonics,
            minimum_harmonic_snr=None,
        )
        return result.score, result.flags
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return 1.0e6, ("NUMERICAL_SCREEN_FAILURE",)


def cadence_aware_synthetic_controls(
    records: Iterable[TargetRecord],
    *,
    data_root: str | Path,
    noise_multiplier: float,
    config: Phase05Config | None = None,
) -> list[SyntheticScreenRecord]:
    active = Phase05Config() if config is None else config
    if not np.isfinite(noise_multiplier) or noise_multiplier <= 0.0:
        raise ValueError("noise_multiplier must be finite and positive")
    rng = np.random.default_rng(active.synthetic_seed + int(round(noise_multiplier * 1000)))
    output: list[SyntheticScreenRecord] = []
    for record in records:
        curve = read_ogle_photometry(
            Path(data_root) / record.relative_path,
            star_id=record.star_id,
            band="I",
        )
        cleaned, _ = clean_light_curve(curve)
        flux = cleaned.to_relative_flux()
        phase = fold_phase(
            flux.time, record.period_days, epoch=float(np.min(flux.time))
        )
        observed_span = float(np.ptp(flux.value))
        amplitude_scale = max(observed_span, 5.0 * float(np.median(flux.error)))
        for label in (1, 0):
            for repetition in range(active.synthetic_repetitions_per_class):
                if label == 1:
                    family = "derd_geometric"
                    shape = _positive_derd_signal(phase, rng=rng)
                elif repetition % 2 == 0:
                    family = "generic_fourier"
                    shape = _generic_fourier_signal(
                        phase, rng=rng, order=active.fourier_order
                    )
                else:
                    family = "phase_scrambled_derd"
                    shape = _phase_scrambled_derd_signal(
                        phase, rng=rng, order=active.fourier_order
                    )
                amplitude = amplitude_scale * float(rng.uniform(0.65, 1.35))
                signal = 1.0 + amplitude * shape
                errors = flux.error * noise_multiplier
                noisy = signal + rng.normal(0.0, errors)
                fourier = fit_complex_fourier(
                    phase,
                    noisy,
                    order=active.fourier_order,
                    errors=errors,
                    ridge=active.fourier_ridge,
                )
                score, flags = _safe_screen(
                    fourier, fit_harmonics=active.fit_harmonics
                )
                synthetic_id = (
                    f"N{noise_multiplier:.3f}:{record.star_id}:"
                    f"{family}:{repetition:03d}"
                )
                split = (
                    "development"
                    if _hash_fraction(synthetic_id) < active.development_fraction
                    else "holdout"
                )
                output.append(
                    SyntheticScreenRecord(
                        synthetic_id=synthetic_id,
                        template_star_id=record.star_id,
                        label=label,
                        null_family=family,
                        noise_multiplier=float(noise_multiplier),
                        score=float(score),
                        flags=tuple(flags),
                        split=split,
                    )
                )
    return output


def _screen_curve(
    record: TargetRecord,
    *,
    data_root: Path,
    period: float,
    config: Phase05Config,
    extra_weights: NDArray[np.float64] | None = None,
) -> tuple[ComplexFourierFit, HarmonicScreenResult]:
    curve = read_ogle_photometry(
        data_root / record.relative_path,
        star_id=record.star_id,
        band="I",
    )
    cleaned, _ = clean_light_curve(curve)
    flux = cleaned.to_relative_flux()
    phase = fold_phase(flux.time, period, epoch=float(np.min(flux.time)))
    if extra_weights is None:
        fit = fit_complex_fourier(
            phase,
            flux.value,
            order=config.fourier_order,
            errors=flux.error,
            ridge=config.fourier_ridge,
        )
    else:
        base_weights = 1.0 / np.square(flux.error)
        fit = fit_complex_fourier(
            phase,
            flux.value,
            order=config.fourier_order,
            weights=base_weights * extra_weights,
            ridge=config.fourier_ridge,
        )
    result = screen_harmonics(
        fit.coefficients[1:],
        fit_harmonics=config.fit_harmonics,
        coefficient_snr=fit.coefficient_snr[1:],
        minimum_harmonic_snr=config.minimum_harmonic_snr,
    )
    return fit, result


def screen_observational_pilot(
    records: Iterable[TargetRecord],
    *,
    data_root: str | Path,
    threshold: float,
    synthetic_development_scores: ArrayLike,
    synthetic_development_labels: ArrayLike,
    config: Phase05Config | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active = Phase05Config() if config is None else config
    root = Path(data_root)
    development_scores = np.asarray(synthetic_development_scores, dtype=np.float64)
    development_labels = np.asarray(synthetic_development_labels, dtype=np.int64)
    positive_reference = development_scores[development_labels == 1]
    negative_reference = development_scores[development_labels == 0]
    if not positive_reference.size or not negative_reference.size:
        raise ValueError("synthetic references must contain both labels")
    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        fit, result = _screen_curve(
            record,
            data_root=root,
            period=record.period_days,
            config=active,
        )
        curve = read_ogle_photometry(
            root / record.relative_path,
            star_id=record.star_id,
            band="I",
        )
        cleaned, _ = clean_light_curve(curve)
        flux = cleaned.to_relative_flux()
        adaptive = adaptive_verify_catalog_period(
            flux.time,
            flux.value,
            record.period_days,
            relative_spans=active.period_relative_spans,
            grid_count=active.period_grid_count,
            bins=8,
        )
        _, adaptive_result = _screen_curve(
            record,
            data_root=root,
            period=adaptive.best_period,
            config=active,
        )

        rng = np.random.default_rng(active.bootstrap_seed + 1009 * index)
        bootstrap_scores: list[float] = []
        bootstrap_parameters: list[tuple[float, float, float, float]] = []
        for _ in range(active.bootstrap_repetitions):
            multipliers = rng.exponential(1.0, size=flux.size)
            try:
                _, boot_result = _screen_curve(
                    record,
                    data_root=root,
                    period=record.period_days,
                    config=active,
                    extra_weights=multipliers,
                )
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                continue
            bootstrap_scores.append(float(boot_result.score))
            bootstrap_parameters.append(
                boot_result.candidate.parameters.as_tuple()
            )
        score_array = np.asarray(bootstrap_scores, dtype=np.float64)
        stable_fraction = float(np.mean(score_array <= threshold)) if score_array.size else 0.0
        snr_count = int(
            np.count_nonzero(
                fit.coefficient_snr[1:] >= active.minimum_harmonic_snr
            )
        )
        quality_flags = list(result.flags)
        if fit.design_condition_number > active.maximum_design_condition_number:
            quality_flags.append("FOURIER_DESIGN_ILL_CONDITIONED")
        if snr_count < active.minimum_snr_harmonics:
            quality_flags.append("TOO_FEW_SIGNIFICANT_HARMONICS")
        candidate = bool(result.score <= threshold)
        eligible = bool(
            candidate
            and fit.design_condition_number <= active.maximum_design_condition_number
            and snr_count >= active.minimum_snr_harmonics
        )
        if eligible and stable_fraction >= 0.80:
            priority = "ACQUISITION_PRIORITY_A"
        elif candidate and stable_fraction >= 0.50:
            priority = "ACQUISITION_PRIORITY_B_LOW_SNR"
        elif snr_count < active.minimum_snr_harmonics:
            priority = "INSUFFICIENT_HARMONIC_EVIDENCE"
        else:
            priority = "LOW_PRIORITY"
        null_percentile = float(np.mean(negative_reference <= result.score))
        positive_percentile = float(np.mean(positive_reference <= result.score))
        row = {
            "star_id": record.star_id,
            "mode": record.mode,
            "catalog_period_days": record.period_days,
            "screen_score": result.score,
            "synthetic_threshold": threshold,
            "below_threshold": candidate,
            "eligible_candidate": eligible,
            "priority": priority,
            "bootstrap_successes": int(score_array.size),
            "bootstrap_below_threshold_fraction": stable_fraction,
            "bootstrap_score_median": float(np.median(score_array)) if score_array.size else float("nan"),
            "bootstrap_score_q10": float(np.quantile(score_array, 0.10)) if score_array.size else float("nan"),
            "bootstrap_score_q90": float(np.quantile(score_array, 0.90)) if score_array.size else float("nan"),
            "null_score_percentile": null_percentile,
            "positive_score_percentile": positive_percentile,
            "harmonics_snr_ge_3": snr_count,
            "fourier_design_condition_number": fit.design_condition_number,
            "fourier_residual_rmse": fit.residual_rmse,
            "adaptive_period_days": adaptive.best_period,
            "adaptive_period_relative_delta": adaptive.relative_delta,
            "adaptive_period_resolved": adaptive.resolved,
            "adaptive_period_screen_score": adaptive_result.score,
            "period_score_delta": adaptive_result.score - result.score,
            "e1": result.candidate.parameters.e1,
            "e2": result.candidate.parameters.e2,
            "amplitude_ratio": result.candidate.parameters.amplitude_ratio,
            "phase_ratio": result.candidate.parameters.phase_ratio,
            "fit_residual": result.candidate.fit_residual,
            "forecast_residual": result.candidate.forecast_residual,
            "recurrence_condition_number": result.recurrence.system_condition_number,
            "flags": ";".join(sorted(set(quality_flags))),
        }
        rows.append(row)
        details.append(
            {
                "record": {
                    "star_id": record.star_id,
                    "mode": record.mode,
                    "period_days": record.period_days,
                    "relative_path": record.relative_path,
                },
                "fourier": fit.as_dict(include_coefficients=True),
                "screen": result.as_dict(include_coefficients=True),
                "adaptive_period": adaptive.as_dict(),
                "adaptive_screen": adaptive_result.as_dict(include_coefficients=False),
                "bootstrap": {
                    "requested": active.bootstrap_repetitions,
                    "successful": int(score_array.size),
                    "scores": [float(value) for value in score_array],
                    "parameters": [list(values) for values in bootstrap_parameters],
                },
                "decision": {
                    "threshold": threshold,
                    "eligible_candidate": eligible,
                    "priority": priority,
                    "quality_flags": sorted(set(quality_flags)),
                },
            }
        )
    rows.sort(key=lambda row: (float(row["screen_score"]), str(row["star_id"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows, details


def minimum_viable_observation_sweep(
    *,
    sample_counts: Iterable[int],
    noise_ratio: float,
    seeds: int = 5,
    repetitions_per_class: int = 75,
    config: Phase05Config | None = None,
) -> tuple[list[dict[str, float | int]], list[dict[str, float | int | bool]], int | None]:
    """Vary only observation count under uniform phase coverage.

    This is an optimistic acquisition-design experiment: phase is uniform,
    harmonic order, signal families, noise ratio, ridge, and score definition are
    held fixed.  It estimates a minimum viable *count*, not a universal theorem
    about every cadence.
    """

    active = Phase05Config() if config is None else config
    counts = tuple(int(value) for value in sample_counts)
    if not counts or any(value < 2 * active.fourier_order + 2 for value in counts):
        raise ValueError("sample counts must exceed the Fourier design dimension")
    if seeds < 2 or repetitions_per_class < 20:
        raise ValueError("sweep requires at least two seeds and twenty repetitions per class")
    if not np.isfinite(noise_ratio) or noise_ratio <= 0.0:
        raise ValueError("noise_ratio must be finite and positive")

    replicate_rows: list[dict[str, float | int]] = []
    summary_rows: list[dict[str, float | int | bool]] = []
    for sample_count in counts:
        for seed_index in range(seeds):
            rng = np.random.default_rng(
                active.synthetic_seed + 7919 * sample_count + 104729 * seed_index
            )
            records: list[SyntheticScreenRecord] = []
            for label in (1, 0):
                for repetition in range(repetitions_per_class):
                    phase = np.sort(rng.random(sample_count))
                    if label == 1:
                        family = "derd_geometric"
                        shape = _positive_derd_signal(phase, rng=rng)
                    elif repetition % 2 == 0:
                        family = "generic_fourier"
                        shape = _generic_fourier_signal(
                            phase, rng=rng, order=active.fourier_order
                        )
                    else:
                        family = "phase_scrambled_derd"
                        shape = _phase_scrambled_derd_signal(
                            phase, rng=rng, order=active.fourier_order
                        )
                    errors = np.full(sample_count, noise_ratio, dtype=np.float64)
                    values = 1.0 + shape + rng.normal(0.0, errors)
                    fourier = fit_complex_fourier(
                        phase,
                        values,
                        order=active.fourier_order,
                        errors=errors,
                        ridge=active.fourier_ridge,
                    )
                    score, flags = _safe_screen(
                        fourier, fit_harmonics=active.fit_harmonics
                    )
                    synthetic_id = (
                        f"MVE:N{sample_count}:S{seed_index}:"
                        f"{family}:{repetition:03d}"
                    )
                    split = (
                        "development"
                        if _hash_fraction(synthetic_id) < active.development_fraction
                        else "holdout"
                    )
                    records.append(
                        SyntheticScreenRecord(
                            synthetic_id=synthetic_id,
                            template_star_id=f"UNIFORM-N{sample_count}",
                            label=label,
                            null_family=family,
                            noise_multiplier=1.0,
                            score=float(score),
                            flags=tuple(flags),
                            split=split,
                        )
                    )
            calibration = calibrate_score_threshold(records)
            holdout = calibration.holdout_metrics
            replicate_rows.append(
                {
                    "sample_count": sample_count,
                    "seed_index": seed_index,
                    "noise_ratio": float(noise_ratio),
                    "threshold": calibration.threshold,
                    "holdout_roc_auc": float(holdout["roc_auc"]),
                    "holdout_balanced_accuracy": float(holdout["balanced_accuracy"]),
                    "holdout_sensitivity": float(holdout["sensitivity"]),
                    "holdout_specificity": float(holdout["specificity"]),
                    "holdout_sample_count": int(holdout["sample_count"]),
                }
            )
        subset = [row for row in replicate_rows if row["sample_count"] == sample_count]
        auc = np.asarray([float(row["holdout_roc_auc"]) for row in subset])
        balanced = np.asarray(
            [float(row["holdout_balanced_accuracy"]) for row in subset]
        )
        gate = bool(
            float(np.median(auc)) >= 0.80
            and float(np.quantile(auc, 0.10)) >= 0.75
            and float(np.median(balanced)) >= 0.75
            and float(np.quantile(balanced, 0.10)) >= 0.70
        )
        summary_rows.append(
            {
                "sample_count": sample_count,
                "seed_count": seeds,
                "repetitions_per_class_per_seed": repetitions_per_class,
                "noise_ratio": float(noise_ratio),
                "median_roc_auc": float(np.median(auc)),
                "roc_auc_q10": float(np.quantile(auc, 0.10)),
                "roc_auc_q90": float(np.quantile(auc, 0.90)),
                "median_balanced_accuracy": float(np.median(balanced)),
                "balanced_accuracy_q10": float(np.quantile(balanced, 0.10)),
                "balanced_accuracy_q90": float(np.quantile(balanced, 0.90)),
                "minimum_viable_gate_pass": gate,
            }
        )
    passing = [int(row["sample_count"]) for row in summary_rows if bool(row["minimum_viable_gate_pass"])]
    minimum_viable = min(passing) if passing else None
    return replicate_rows, summary_rows, minimum_viable
