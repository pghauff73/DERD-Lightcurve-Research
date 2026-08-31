"""Phase-07 raw-photometry harmonic-forecast validation.

This module preserves the Phase-06 lossless signed-coefficient representation,
calibrates the DERD recurrence screen under the target's actual cadence, and
applies a covariance-aware evidence gate.  It is a waveform-evidence test only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .harmonic_evidence import SignedHarmonicFit, fit_signed_harmonics
from .harmonic_exchange import CanonicalHarmonicSeries
from .harmonic_extraction import (
    WeightedHarmonicExtraction,
    draw_complex_coefficients,
    git_blob_sha1_bytes,
)
from .harmonic_screen import HarmonicScreenResult, fit_complex_fourier, screen_harmonics
from .io import read_ogle_photometry
from .period import adaptive_verify_catalog_period
from .preprocess import clean_light_curve, fold_phase
from .recurrence_uncertainty import (
    HarmonicEvidenceGate,
    RecurrencePropagation,
    evaluate_harmonic_evidence_gate,
    propagate_recurrence_uncertainty,
)
from .validation_phase05 import (
    SyntheticScreenRecord,
    ThresholdCalibration,
    _generic_fourier_signal,
    _phase_scrambled_derd_signal,
    _positive_derd_signal,
    calibrate_score_threshold,
)


@dataclass(frozen=True, slots=True)
class Phase07Config:
    fourier_order: int = 8
    fit_harmonics: int = 4
    fourier_ridge: float = 1.0e-4
    harmonic_ridge: float = 1.0e-4
    development_fraction: float = 0.70

    # Current names.
    synthetic_samples_per_class: int = 160
    synthetic_seed: int = 2026081507
    propagation_draws: int = 4096
    propagation_seed: int = 2026081509
    observation_sweep_counts: tuple[int, ...] = (80, 120, 160, 240, 320, 372)
    observation_sweep_repetitions: int = 24
    observation_sweep_seed: int = 2026081510

    # Compatibility names retained for the v0.6/v0.7 research API.
    full_calibration_per_class: int | None = None
    full_calibration_seed: int | None = None
    uncertainty_draws: int | None = None
    uncertainty_seed: int | None = None
    mvhe_counts: tuple[int, ...] = (80, 120, 160, 240, 320, 372)
    mvhe_replicates: int | None = None
    mvhe_per_class: int | None = None
    mvhe_seed: int = 2026081508

    minimum_observations: int = 160
    minimum_recovery_snr: float = 3.0
    minimum_forecast_snr: float = 2.0
    minimum_forecast_significant_harmonics: int = 2
    maximum_design_condition_number: float = 1.0e4
    minimum_median_auc: float = 0.80
    minimum_q10_auc: float = 0.75
    minimum_median_balanced_accuracy: float = 0.75
    minimum_q10_balanced_accuracy: float = 0.70
    minimum_sustained_mvhe_levels: int = 3
    period_relative_spans: tuple[float, ...] = (0.001, 0.005, 0.02)
    period_grid_count: int = 101

    @property
    def calibration_per_class(self) -> int:
        return int(self.full_calibration_per_class or self.synthetic_samples_per_class)

    @property
    def calibration_seed(self) -> int:
        return int(self.full_calibration_seed or self.synthetic_seed)

    @property
    def draw_count(self) -> int:
        return int(self.uncertainty_draws or self.propagation_draws)

    @property
    def draw_seed(self) -> int:
        return int(self.uncertainty_seed or self.propagation_seed)

    @property
    def sweep_repetitions(self) -> int:
        return int(self.mvhe_replicates or self.observation_sweep_repetitions)

    @property
    def sweep_per_class(self) -> int:
        return int(self.mvhe_per_class or max(12, min(48, self.synthetic_samples_per_class)))


@dataclass(frozen=True, slots=True)
class CadenceCalibration:
    threshold: float
    development_metrics: dict[str, float | int]
    holdout_metrics: dict[str, float | int]
    records: tuple[SyntheticScreenRecord, ...]

    def as_dict(self, *, include_records: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "threshold": self.threshold,
            "development_metrics": dict(self.development_metrics),
            "holdout_metrics": dict(self.holdout_metrics),
        }
        if include_records:
            payload["records"] = [row.as_dict() for row in self.records]
        return payload


@dataclass(frozen=True, slots=True)
class MVHEReplicate:
    observation_count: int
    replicate: int
    threshold: float
    holdout_roc_auc: float
    holdout_balanced_accuracy: float
    holdout_sensitivity: float
    holdout_specificity: float
    development_roc_auc: float
    development_balanced_accuracy: float

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class MVHESummary:
    observation_count: int
    replicate_count: int
    median_roc_auc: float
    q10_roc_auc: float
    median_balanced_accuracy: float
    q10_balanced_accuracy: float
    median_threshold: float
    passes_gate: bool

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class MVHEGateAssessment:
    """Pointwise and sustained decisions for a noisy observation-count sweep.

    A pointwise pass can be a Monte-Carlo fluctuation.  The promoted observation
    floor is therefore the first count whose result passes together with every
    larger tested count, with at least ``minimum_sustained_levels`` levels in
    that tail.
    """

    first_pointwise_pass: int | None
    first_sustained_pass: int | None
    minimum_sustained_levels: int
    sustained_level_count: int
    non_monotonic_pointwise_pattern: bool
    pass_pattern: tuple[tuple[int, bool], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "first_pointwise_pass": self.first_pointwise_pass,
            "first_sustained_pass": self.first_sustained_pass,
            "minimum_sustained_levels": self.minimum_sustained_levels,
            "sustained_level_count": self.sustained_level_count,
            "non_monotonic_pointwise_pattern": self.non_monotonic_pointwise_pattern,
            "pass_pattern": [
                {"observation_count": count, "passes_gate": passed}
                for count, passed in self.pass_pattern
            ],
        }


def assess_mvhe_gate(
    summaries: Iterable[MVHESummary],
    *,
    minimum_sustained_levels: int = 3,
) -> MVHEGateAssessment:
    """Convert pointwise MVHE results into a conservative sustained gate.

    The input is sorted by observation count.  The first sustained pass is the
    first passing count for which every larger tested count also passes, and
    whose tail contains at least ``minimum_sustained_levels`` tested counts.
    """

    if minimum_sustained_levels < 1:
        raise ValueError("minimum_sustained_levels must be positive")
    ordered = sorted(tuple(summaries), key=lambda row: row.observation_count)
    counts = [row.observation_count for row in ordered]
    if len(counts) != len(set(counts)):
        raise ValueError("MVHE summaries must have unique observation counts")
    pattern = tuple((row.observation_count, bool(row.passes_gate)) for row in ordered)
    first_pointwise = next((count for count, passed in pattern if passed), None)

    first_sustained: int | None = None
    sustained_levels = 0
    for index, (count, passed) in enumerate(pattern):
        tail = pattern[index:]
        if (
            passed
            and len(tail) >= minimum_sustained_levels
            and all(tail_passed for _, tail_passed in tail)
        ):
            first_sustained = count
            sustained_levels = len(tail)
            break

    seen_pass = False
    non_monotonic = False
    for _, passed in pattern:
        if passed:
            seen_pass = True
        elif seen_pass:
            non_monotonic = True
            break

    return MVHEGateAssessment(
        first_pointwise_pass=first_pointwise,
        first_sustained_pass=first_sustained,
        minimum_sustained_levels=minimum_sustained_levels,
        sustained_level_count=sustained_levels,
        non_monotonic_pointwise_pattern=non_monotonic,
        pass_pattern=pattern,
    )


@dataclass(frozen=True, slots=True)
class ExchangeUncertaintyResult:
    nominal_score: float
    nominal_forecast_residual: float | None
    threshold: float
    draws_requested: int
    draws_successful: int
    score_median: float
    score_q05: float
    score_q95: float
    threshold_pass_fraction: float
    forecast_residual_median: float
    forecast_residual_q05: float
    forecast_residual_q95: float
    nominal_flags: tuple[str, ...]
    quality_flags: tuple[str, ...]
    recovery_snr: tuple[float, ...]
    forecast_snr: tuple[float, ...]
    recovery_significant_count: int
    forecast_significant_count: int
    qualifies: bool
    evidence_status: str

    def as_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for key in ("nominal_flags", "quality_flags", "recovery_snr", "forecast_snr"):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True, slots=True)
class Phase07TargetResult:
    object_id: str
    mode: str
    catalog_period: float
    source_sha256: str
    source_git_blob_sha1: str
    observation_count: int
    period_check: dict[str, Any]
    harmonic_fit: SignedHarmonicFit
    screen: HarmonicScreenResult
    calibration: CadenceCalibration
    propagation: RecurrencePropagation
    gate: HarmonicEvidenceGate
    observation_sweep_replicates: tuple[dict[str, Any], ...]
    observation_sweep_summary: tuple[dict[str, Any], ...]
    required_observations: tuple[dict[str, Any], ...]

    def as_dict(self, *, include_controls: bool = False) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "mode": self.mode,
            "catalog_period": self.catalog_period,
            "source_sha256": self.source_sha256,
            "source_git_blob_sha1": self.source_git_blob_sha1,
            "observation_count": self.observation_count,
            "period_check": self.period_check,
            "harmonic_fit": self.harmonic_fit.as_dict(include_covariance=True),
            "screen": self.screen.as_dict(include_coefficients=True),
            "calibration": self.calibration.as_dict(include_records=include_controls),
            "propagation": self.propagation.as_dict(),
            "gate": self.gate.as_dict(),
            "observation_sweep_replicates": list(self.observation_sweep_replicates),
            "observation_sweep_summary": list(self.observation_sweep_summary),
            "required_observations": list(self.required_observations),
        }


def _hash_fraction(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def _safe_score(
    phase: NDArray[np.float64],
    values: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    config: Phase07Config,
) -> tuple[float, tuple[str, ...]]:
    try:
        fit = fit_complex_fourier(
            phase,
            values,
            order=config.fourier_order,
            errors=errors,
            ridge=config.fourier_ridge,
        )
        result = screen_harmonics(fit.coefficients[1:], fit_harmonics=config.fit_harmonics)
        return float(result.score), tuple(result.flags)
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return 1.0e6, ("NUMERICAL_SCREEN_FAILURE",)


def synthetic_actual_cadence_records(
    phase: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    amplitude_scale: float,
    per_class: int,
    seed: int,
    development_fraction: float,
    label_prefix: str,
    config: Phase07Config,
) -> list[SyntheticScreenRecord]:
    phase = np.asarray(phase, dtype=np.float64).reshape(-1)
    errors = np.asarray(errors, dtype=np.float64).reshape(-1)
    if phase.size != errors.size or phase.size < 18:
        raise ValueError("phase and errors must match and support order-eight fitting")
    if per_class < 8:
        raise ValueError("per_class must be at least eight")
    if not math.isfinite(amplitude_scale) or amplitude_scale <= 0.0:
        raise ValueError("amplitude_scale must be finite and positive")
    rng = np.random.default_rng(int(seed))
    rows: list[SyntheticScreenRecord] = []
    for label in (1, 0):
        for repetition in range(per_class):
            if label == 1:
                family = "derd_geometric"
                unit = _positive_derd_signal(phase, rng=rng)
            elif repetition % 2 == 0:
                family = "phase_scrambled_derd"
                unit = _phase_scrambled_derd_signal(phase, rng=rng, order=config.fourier_order)
            else:
                family = "generic_fourier"
                unit = _generic_fourier_signal(phase, rng=rng, order=config.fourier_order)
            values = 1.0 + amplitude_scale * unit + rng.normal(0.0, errors)
            score, flags = _safe_score(phase, values, errors, config=config)
            synthetic_id = f"{label_prefix}:{family}:{repetition:04d}"
            split = "development" if _hash_fraction(synthetic_id) < development_fraction else "holdout"
            rows.append(
                SyntheticScreenRecord(
                    synthetic_id=synthetic_id,
                    template_star_id=label_prefix,
                    label=label,
                    null_family=family,
                    noise_multiplier=1.0,
                    score=score,
                    flags=flags,
                    split=split,
                )
            )
    return rows


def generate_actual_cadence_controls(
    *,
    phase: NDArray[np.float64],
    errors: NDArray[np.float64],
    observed_span: float,
    config: Phase07Config | None = None,
) -> CadenceCalibration:
    active = Phase07Config() if config is None else config
    amplitude = max(float(observed_span), 5.0 * float(np.median(errors)))
    records = synthetic_actual_cadence_records(
        np.asarray(phase, dtype=np.float64),
        np.asarray(errors, dtype=np.float64),
        amplitude_scale=amplitude,
        per_class=active.calibration_per_class,
        seed=active.calibration_seed,
        development_fraction=active.development_fraction,
        label_prefix="PHASE07-ACTUAL-CADENCE",
        config=active,
    )
    calibration = calibrate_score_threshold(records)
    return CadenceCalibration(
        threshold=float(calibration.threshold),
        development_metrics=dict(calibration.development_metrics),
        holdout_metrics=dict(calibration.holdout_metrics),
        records=tuple(records),
    )


def calibrate_actual_cadence(
    phase: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    amplitude_scale: float,
    config: Phase07Config | None = None,
) -> tuple[ThresholdCalibration, list[SyntheticScreenRecord]]:
    active = Phase07Config() if config is None else config
    rows = synthetic_actual_cadence_records(
        np.asarray(phase, dtype=np.float64),
        np.asarray(errors, dtype=np.float64),
        amplitude_scale=float(amplitude_scale),
        per_class=active.calibration_per_class,
        seed=active.calibration_seed,
        development_fraction=active.development_fraction,
        label_prefix="PHASE07-FULL-CADENCE",
        config=active,
    )
    return calibrate_score_threshold(rows), rows


def phase_stratified_subset(
    phase: NDArray[np.float64],
    count: int,
    *,
    rng: np.random.Generator,
) -> NDArray[np.int64]:
    values = np.mod(np.asarray(phase, dtype=np.float64).reshape(-1), 1.0)
    if count < 1 or count > values.size:
        raise ValueError("count must lie between one and sample size")
    if count == values.size:
        return np.arange(values.size, dtype=np.int64)
    order = np.argsort(values, kind="mergesort")
    boundaries = np.linspace(0.0, float(values.size), count + 1)
    selected: list[int] = []
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        start = int(math.floor(lower))
        stop = min(values.size, max(start + 1, int(math.floor(upper))))
        selected.append(int(order[int(rng.integers(start, stop))]))
    return np.sort(np.asarray(selected, dtype=np.int64))


def actual_cadence_mvhe(
    phase: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    amplitude_scale: float,
    config: Phase07Config | None = None,
) -> tuple[list[MVHEReplicate], list[MVHESummary]]:
    active = Phase07Config() if config is None else config
    replicates: list[MVHEReplicate] = []
    for count in active.mvhe_counts:
        if count > phase.size:
            continue
        for replicate in range(active.sweep_repetitions):
            seed = active.mvhe_seed + count * 1009 + replicate * 7919
            rng = np.random.default_rng(seed)
            indices = phase_stratified_subset(phase, count, rng=rng)
            rows = synthetic_actual_cadence_records(
                np.asarray(phase)[indices],
                np.asarray(errors)[indices],
                amplitude_scale=amplitude_scale,
                per_class=active.sweep_per_class,
                seed=seed + 17,
                development_fraction=active.development_fraction,
                label_prefix=f"PHASE07-MVHE-{count:04d}-R{replicate:02d}",
                config=active,
            )
            calibration = calibrate_score_threshold(rows)
            h = calibration.holdout_metrics
            d = calibration.development_metrics
            replicates.append(
                MVHEReplicate(
                    observation_count=count,
                    replicate=replicate,
                    threshold=float(calibration.threshold),
                    holdout_roc_auc=float(h["roc_auc"]),
                    holdout_balanced_accuracy=float(h["balanced_accuracy"]),
                    holdout_sensitivity=float(h["sensitivity"]),
                    holdout_specificity=float(h["specificity"]),
                    development_roc_auc=float(d["roc_auc"]),
                    development_balanced_accuracy=float(d["balanced_accuracy"]),
                )
            )
    summaries: list[MVHESummary] = []
    for count in sorted({row.observation_count for row in replicates}):
        subset = [row for row in replicates if row.observation_count == count]
        auc = np.asarray([row.holdout_roc_auc for row in subset])
        bal = np.asarray([row.holdout_balanced_accuracy for row in subset])
        threshold = np.asarray([row.threshold for row in subset])
        med_auc, q10_auc = float(np.median(auc)), float(np.quantile(auc, 0.10))
        med_bal, q10_bal = float(np.median(bal)), float(np.quantile(bal, 0.10))
        summaries.append(
            MVHESummary(
                observation_count=count,
                replicate_count=len(subset),
                median_roc_auc=med_auc,
                q10_roc_auc=q10_auc,
                median_balanced_accuracy=med_bal,
                q10_balanced_accuracy=q10_bal,
                median_threshold=float(np.median(threshold)),
                passes_gate=(
                    med_auc >= active.minimum_median_auc
                    and q10_auc >= active.minimum_q10_auc
                    and med_bal >= active.minimum_median_balanced_accuracy
                    and q10_bal >= active.minimum_q10_balanced_accuracy
                ),
            )
        )
    return replicates, summaries


def screen_exchange_with_uncertainty(
    extraction: WeightedHarmonicExtraction,
    *,
    threshold: float,
    config: Phase07Config | None = None,
) -> ExchangeUncertaintyResult:
    active = Phase07Config() if config is None else config
    series: CanonicalHarmonicSeries = extraction.series
    nominal = screen_harmonics(series.complex_coefficients, fit_harmonics=active.fit_harmonics)
    draws = draw_complex_coefficients(series, draws=active.draw_count, seed=active.draw_seed)
    scores: list[float] = []
    forecasts: list[float] = []
    for coefficients in draws:
        try:
            item = screen_harmonics(coefficients, fit_harmonics=active.fit_harmonics)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            continue
        scores.append(float(item.score))
        if item.candidate.forecast_residual is not None:
            forecasts.append(float(item.candidate.forecast_residual))
    score_array = np.asarray(scores)
    forecast_array = np.asarray(forecasts)
    recovery_snr = extraction.harmonic_wald_snr[: active.fit_harmonics]
    forecast_snr = extraction.harmonic_wald_snr[active.fit_harmonics :]
    recovery_count = int(np.count_nonzero(recovery_snr >= active.minimum_recovery_snr))
    forecast_count = int(np.count_nonzero(forecast_snr >= active.minimum_forecast_snr))
    flags = list(nominal.flags)
    if extraction.design_condition_number > active.maximum_design_condition_number:
        flags.append("HARMONIC_DESIGN_ILL_CONDITIONED")
    if recovery_count < active.fit_harmonics:
        flags.append("RECOVERY_HARMONICS_NOT_SIGNIFICANT")
    if forecast_count < active.minimum_forecast_significant_harmonics:
        flags.append("FORECAST_HARMONICS_NOT_MEASURED")
    if series.harmonic_count < active.fit_harmonics + 2:
        flags.append("INSUFFICIENT_HARMONIC_FORECAST_DIMENSION")
    fraction = float(np.mean(score_array <= threshold)) if score_array.size else 0.0
    qualifies = bool(
        nominal.score <= threshold
        and fraction >= 0.80
        and recovery_count >= active.fit_harmonics
        and forecast_count >= active.minimum_forecast_significant_harmonics
        and extraction.design_condition_number <= active.maximum_design_condition_number
        and series.harmonic_count >= active.fit_harmonics + 2
    )
    if qualifies:
        status = "QUALIFIES_AS_DEVELOPMENT_HARMONIC_FORECAST"
    elif recovery_count < active.fit_harmonics:
        status = "INSUFFICIENT_RECOVERY_HARMONIC_SIGNAL"
    elif forecast_count < active.minimum_forecast_significant_harmonics:
        status = "INSUFFICIENT_MEASURED_FORECAST_HARMONICS"
    elif nominal.score > threshold:
        status = "DERD_HARMONIC_COMPATIBILITY_NOT_SUPPORTED"
    else:
        status = "DERD_HARMONIC_SCORE_UNSTABLE_UNDER_COVARIANCE"

    def q(array: NDArray[np.float64], p: float) -> float:
        return float(np.quantile(array, p)) if array.size else math.nan

    return ExchangeUncertaintyResult(
        nominal_score=float(nominal.score),
        nominal_forecast_residual=nominal.candidate.forecast_residual,
        threshold=float(threshold),
        draws_requested=active.draw_count,
        draws_successful=int(score_array.size),
        score_median=q(score_array, 0.50),
        score_q05=q(score_array, 0.05),
        score_q95=q(score_array, 0.95),
        threshold_pass_fraction=fraction,
        forecast_residual_median=q(forecast_array, 0.50),
        forecast_residual_q05=q(forecast_array, 0.05),
        forecast_residual_q95=q(forecast_array, 0.95),
        nominal_flags=tuple(nominal.flags),
        quality_flags=tuple(sorted(set(flags))),
        recovery_snr=tuple(float(v) for v in recovery_snr),
        forecast_snr=tuple(float(v) for v in forecast_snr),
        recovery_significant_count=recovery_count,
        forecast_significant_count=forecast_count,
        qualifies=qualifies,
        evidence_status=status,
    )


def _real_observation_sweep(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    period: float,
    reference_epoch: float,
    config: Phase07Config,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    phase = fold_phase(time, period, epoch=reference_epoch)
    rows: list[dict[str, Any]] = []
    counts = tuple(sorted({int(c) for c in config.observation_sweep_counts if 2 * config.fourier_order + 4 < c <= time.size}))
    for count in counts:
        repetitions = 1 if count == time.size else config.observation_sweep_repetitions
        for replicate in range(repetitions):
            rng = np.random.default_rng(config.observation_sweep_seed + count * 1009 + replicate * 7919)
            idx = phase_stratified_subset(phase, count, rng=rng)
            fit = fit_signed_harmonics(
                time[idx], values[idx], errors[idx], period=period,
                reference_epoch=reference_epoch, order=config.fourier_order,
                ridge=config.harmonic_ridge,
            )
            row: dict[str, Any] = {
                "observation_count": count,
                "replicate": replicate,
                "design_condition_number": fit.design_condition_number,
                "screen_score": float(screen_harmonics(fit.complex_coefficients, fit_harmonics=config.fit_harmonics).score),
            }
            for harmonic, snr in enumerate(fit.coefficient_snr, start=1):
                row[f"snr_h{harmonic}"] = float(snr)
            rows.append(row)
    summaries: list[dict[str, Any]] = []
    for count in counts:
        subset = [row for row in rows if row["observation_count"] == count]
        summary: dict[str, Any] = {"observation_count": count, "replicate_count": len(subset)}
        for harmonic in range(1, config.fourier_order + 1):
            values_h = np.asarray([row[f"snr_h{harmonic}"] for row in subset])
            summary[f"snr_h{harmonic}_median"] = float(np.median(values_h))
            summary[f"snr_h{harmonic}_q10"] = float(np.quantile(values_h, 0.10))
            summary[f"snr_h{harmonic}_q90"] = float(np.quantile(values_h, 0.90))
        scores = np.asarray([row["screen_score"] for row in subset])
        summary["screen_score_median"] = float(np.median(scores))
        summaries.append(summary)
    return tuple(rows), tuple(summaries)


def _required_observations(
    coefficient_snr: NDArray[np.float64],
    *,
    observation_count: int,
    fit_harmonics: int,
    recovery_threshold: float,
    forecast_threshold: float,
) -> tuple[dict[str, Any], ...]:
    output: list[dict[str, Any]] = []
    for index, snr in enumerate(np.asarray(coefficient_snr), start=1):
        target = recovery_threshold if index <= fit_harmonics else forecast_threshold
        required = None if not math.isfinite(float(snr)) or snr <= 0 else int(math.ceil(observation_count * (target / float(snr)) ** 2))
        output.append({
            "harmonic": index,
            "observed_snr": float(snr),
            "target_snr": float(target),
            "approximate_required_observations": required,
            "assumption": "independent-noise square-root-N scaling; optimistic",
        })
    return tuple(output)


def run_phase07_target(
    *,
    source_path: str | Path,
    object_id: str,
    mode: str,
    catalog_period: float,
    expected_git_blob_sha1: str,
    source_locator: str,
    config: Phase07Config | None = None,
) -> Phase07TargetResult:
    active = Phase07Config() if config is None else config
    path = Path(source_path)
    raw = path.read_bytes()
    blob_sha1 = git_blob_sha1_bytes(raw)
    if blob_sha1 != expected_git_blob_sha1:
        raise ValueError(
            f"Git blob SHA-1 mismatch: expected {expected_git_blob_sha1}, observed {blob_sha1}"
        )
    source_sha256 = hashlib.sha256(raw).hexdigest()
    curve = read_ogle_photometry(path, star_id=object_id, band="I")
    cleaned, cleaning = clean_light_curve(curve)
    flux = cleaned.to_relative_flux()
    reference_epoch = float(np.min(flux.time))
    period_check = adaptive_verify_catalog_period(
        flux.time, flux.value, catalog_period,
        relative_spans=active.period_relative_spans,
        grid_count=active.period_grid_count,
    ).as_dict()
    fit = fit_signed_harmonics(
        flux.time, flux.value, flux.error,
        period=catalog_period,
        reference_epoch=reference_epoch,
        order=active.fourier_order,
        ridge=active.harmonic_ridge,
    )
    screen = screen_harmonics(fit.complex_coefficients, fit_harmonics=active.fit_harmonics)
    phase = fold_phase(flux.time, catalog_period, epoch=reference_epoch)
    calibration = generate_actual_cadence_controls(
        phase=phase,
        errors=flux.error,
        observed_span=float(np.ptp(flux.value)),
        config=active,
    )
    exchange = fit.to_exchange(
        object_id=object_id,
        time_unit="day",
        value_unit="relative_flux",
        source_locator=source_locator,
        source_sha256=source_sha256,
        metadata={"mode": mode, "catalog_period": catalog_period},
    )
    propagation = propagate_recurrence_uncertainty(
        exchange,
        fit_harmonics=active.fit_harmonics,
        minimum_forecast_harmonics=active.minimum_forecast_significant_harmonics,
        score_threshold=calibration.threshold,
        draws=active.draw_count,
        seed=active.draw_seed,
    )
    gate = evaluate_harmonic_evidence_gate(
        observation_count=fit.sample_count,
        occupied_phase_bins=int(fit.phase_coverage["occupied_bins"]),
        total_phase_bins=int(fit.phase_coverage["bins"]),
        design_condition_number=fit.design_condition_number,
        coefficient_snr=fit.coefficient_snr,
        screen=screen,
        propagation=propagation,
        score_threshold=calibration.threshold,
        cadence_holdout_auc=float(calibration.holdout_metrics["roc_auc"]),
        cadence_holdout_balanced_accuracy=float(calibration.holdout_metrics["balanced_accuracy"]),
        source_complete=True,
        minimum_observations=active.minimum_observations,
        minimum_fit_snr=active.minimum_recovery_snr,
        minimum_forecast_snr=active.minimum_forecast_snr,
        minimum_forecast_harmonics=active.minimum_forecast_significant_harmonics,
        maximum_design_condition_number=active.maximum_design_condition_number,
    )
    sweep_rows, sweep_summary = _real_observation_sweep(
        flux.time, flux.value, flux.error,
        period=catalog_period,
        reference_epoch=reference_epoch,
        config=active,
    )
    required = _required_observations(
        fit.coefficient_snr,
        observation_count=fit.sample_count,
        fit_harmonics=active.fit_harmonics,
        recovery_threshold=active.minimum_recovery_snr,
        forecast_threshold=active.minimum_forecast_snr,
    )
    return Phase07TargetResult(
        object_id=object_id,
        mode=mode,
        catalog_period=float(catalog_period),
        source_sha256=source_sha256,
        source_git_blob_sha1=blob_sha1,
        observation_count=fit.sample_count,
        period_check=period_check,
        harmonic_fit=fit,
        screen=screen,
        calibration=calibration,
        propagation=propagation,
        gate=gate,
        observation_sweep_replicates=sweep_rows,
        observation_sweep_summary=sweep_summary,
        required_observations=required,
    )
