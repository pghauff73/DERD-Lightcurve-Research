"""Covariance-aware propagation for the DERD harmonic recurrence screen."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .harmonic_exchange import CanonicalHarmonicSeries
from .harmonic_screen import HarmonicScreenResult, screen_harmonics
from .phase_convention import canonical_coefficients_from_sine_cosine

DISQUALIFYING_STRUCTURAL_FLAGS = frozenset(
    {
        "RECURRENCE_ILL_CONDITIONED",
        "ROOT_OUTSIDE_PHYSICAL_Q_DOMAIN",
        "RESIDUE_SIGN_CONSTRAINT_FAILED",
        "RESIDUE_PHASE_CONSTRAINT_WEAK",
        "AMPLITUDE_RATIO_EXTREME",
    }
)


def _quantiles(values: Iterable[float]) -> dict[str, float | None]:
    array = np.asarray(tuple(values), dtype=np.float64)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"q05": None, "q10": None, "median": None, "q90": None, "q95": None}
    return {
        "q05": float(np.quantile(array, 0.05)),
        "q10": float(np.quantile(array, 0.10)),
        "median": float(np.median(array)),
        "q90": float(np.quantile(array, 0.90)),
        "q95": float(np.quantile(array, 0.95)),
    }


@dataclass(frozen=True, slots=True)
class RecurrencePropagation:
    requested_draws: int
    successful_draws: int
    numerical_failure_fraction: float
    structural_pass_fraction: float
    below_threshold_fraction: float | None
    score_quantiles: dict[str, float | None]
    forecast_residual_quantiles: dict[str, float | None]
    unconstrained_forecast_quantiles: dict[str, float | None]
    e1_quantiles: dict[str, float | None]
    e2_quantiles: dict[str, float | None]
    amplitude_ratio_quantiles: dict[str, float | None]
    phase_ratio_quantiles: dict[str, float | None]
    flag_counts: dict[str, int]
    seed: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_draws": self.requested_draws,
            "successful_draws": self.successful_draws,
            "numerical_failure_fraction": self.numerical_failure_fraction,
            "structural_pass_fraction": self.structural_pass_fraction,
            "below_threshold_fraction": self.below_threshold_fraction,
            "score_quantiles": self.score_quantiles,
            "forecast_residual_quantiles": self.forecast_residual_quantiles,
            "unconstrained_forecast_quantiles": self.unconstrained_forecast_quantiles,
            "e1_quantiles": self.e1_quantiles,
            "e2_quantiles": self.e2_quantiles,
            "amplitude_ratio_quantiles": self.amplitude_ratio_quantiles,
            "phase_ratio_quantiles": self.phase_ratio_quantiles,
            "flag_counts": dict(self.flag_counts),
            "seed": self.seed,
        }


def propagate_recurrence_uncertainty(
    series: CanonicalHarmonicSeries,
    *,
    fit_harmonics: int = 4,
    minimum_forecast_harmonics: int = 2,
    score_threshold: float | None = None,
    draws: int = 2048,
    seed: int = 20260815,
) -> RecurrencePropagation:
    """Propagate the signed-coefficient covariance through the nonlinear screen.

    The returned fractions are uncertainty-propagation diagnostics, not a
    posterior probability for a physical stellar model.
    """

    if series.coefficient_covariance is None:
        raise ValueError("coefficient covariance is required")
    if draws < 128:
        raise ValueError("at least 128 draws are required")
    if fit_harmonics < 4 or fit_harmonics > series.harmonic_count:
        raise ValueError("invalid fit_harmonics")
    mean = np.concatenate((series.sine_coefficients, series.cosine_coefficients))
    covariance = np.asarray(series.coefficient_covariance, dtype=np.float64)
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    tolerance = max(1.0, float(np.max(np.abs(eigenvalues)))) * 1.0e-13
    clipped = np.where(eigenvalues < tolerance, np.maximum(eigenvalues, 0.0), eigenvalues)
    root = eigenvectors @ np.diag(np.sqrt(clipped))
    rng = np.random.default_rng(seed)
    standard = rng.normal(size=(draws, mean.size))
    samples = mean[None, :] + standard @ root.T

    scores: list[float] = []
    forecasts: list[float] = []
    unconstrained: list[float] = []
    e1: list[float] = []
    e2: list[float] = []
    amplitude: list[float] = []
    phase: list[float] = []
    structural_passes = 0
    below_threshold = 0
    flag_counts: dict[str, int] = {}
    n = series.harmonic_count
    for row in samples:
        sine = row[:n]
        cosine = row[n:]
        coefficients = canonical_coefficients_from_sine_cosine(sine, cosine)
        try:
            result: HarmonicScreenResult = screen_harmonics(
                coefficients,
                fit_harmonics=fit_harmonics,
                minimum_forecast_harmonics=minimum_forecast_harmonics,
                minimum_harmonic_snr=None,
            )
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            continue
        scores.append(float(result.score))
        if result.candidate.forecast_residual is not None:
            forecasts.append(float(result.candidate.forecast_residual))
        if result.unconstrained_forecast_residual is not None:
            unconstrained.append(float(result.unconstrained_forecast_residual))
        parameters = result.candidate.parameters
        e1.append(parameters.e1)
        e2.append(parameters.e2)
        amplitude.append(parameters.amplitude_ratio)
        phase.append(parameters.phase_ratio)
        active_flags = set(result.flags)
        for flag in active_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        structural_ok = (
            result.evidence_level == "HARMONIC_FORECAST"
            and not active_flags.intersection(DISQUALIFYING_STRUCTURAL_FLAGS)
        )
        structural_passes += int(structural_ok)
        if score_threshold is not None:
            below_threshold += int(result.score <= score_threshold)

    successful = len(scores)
    return RecurrencePropagation(
        requested_draws=int(draws),
        successful_draws=successful,
        numerical_failure_fraction=float(1.0 - successful / draws),
        structural_pass_fraction=float(structural_passes / max(1, successful)),
        below_threshold_fraction=(
            None
            if score_threshold is None
            else float(below_threshold / max(1, successful))
        ),
        score_quantiles=_quantiles(scores),
        forecast_residual_quantiles=_quantiles(forecasts),
        unconstrained_forecast_quantiles=_quantiles(unconstrained),
        e1_quantiles=_quantiles(e1),
        e2_quantiles=_quantiles(e2),
        amplitude_ratio_quantiles=_quantiles(amplitude),
        phase_ratio_quantiles=_quantiles(phase),
        flag_counts=flag_counts,
        seed=int(seed),
    )


@dataclass(frozen=True, slots=True)
class HarmonicEvidenceGate:
    decision: str
    passed: bool
    checks: dict[str, bool]
    measurements: dict[str, Any]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "passed": self.passed,
            "checks": dict(self.checks),
            "measurements": dict(self.measurements),
            "blockers": list(self.blockers),
        }


def evaluate_harmonic_evidence_gate(
    *,
    observation_count: int,
    occupied_phase_bins: int,
    total_phase_bins: int,
    design_condition_number: float,
    coefficient_snr: NDArray[np.float64],
    screen: HarmonicScreenResult,
    propagation: RecurrencePropagation,
    score_threshold: float,
    cadence_holdout_auc: float,
    cadence_holdout_balanced_accuracy: float,
    source_complete: bool,
    minimum_observations: int = 160,
    minimum_occupied_bins: int = 10,
    maximum_design_condition_number: float = 1.0e4,
    minimum_fit_snr: float = 3.0,
    minimum_forecast_snr: float = 2.0,
    minimum_forecast_harmonics: int = 2,
    minimum_structural_pass_fraction: float = 0.80,
    minimum_threshold_fraction: float = 0.80,
    minimum_cadence_auc: float = 0.80,
    minimum_cadence_balanced_accuracy: float = 0.75,
) -> HarmonicEvidenceGate:
    snr = np.asarray(coefficient_snr, dtype=np.float64).reshape(-1)
    fit_count = min(4, snr.size)
    forecast = snr[4:]
    first_four_snr_count = int(np.count_nonzero(snr[:fit_count] >= minimum_fit_snr))
    forecast_snr_count = int(np.count_nonzero(forecast >= minimum_forecast_snr))
    structural_flags = sorted(
        set(screen.flags).intersection(DISQUALIFYING_STRUCTURAL_FLAGS)
    )
    below_fraction = propagation.below_threshold_fraction
    checks = {
        "source_complete": bool(source_complete),
        "minimum_observation_count": observation_count >= minimum_observations,
        "phase_coverage": occupied_phase_bins >= min(minimum_occupied_bins, total_phase_bins),
        "design_conditioning": design_condition_number <= maximum_design_condition_number,
        "four_recovery_harmonics_snr": first_four_snr_count >= 4,
        "forecast_harmonics_snr": forecast_snr_count >= minimum_forecast_harmonics,
        "harmonic_forecast_available": screen.evidence_level == "HARMONIC_FORECAST",
        "structural_constraints": not structural_flags,
        "score_below_cadence_threshold": screen.score <= score_threshold,
        "uncertainty_structural_stability": (
            propagation.structural_pass_fraction >= minimum_structural_pass_fraction
        ),
        "uncertainty_threshold_stability": (
            below_fraction is not None and below_fraction >= minimum_threshold_fraction
        ),
        "cadence_calibration_auc": cadence_holdout_auc >= minimum_cadence_auc,
        "cadence_calibration_balanced_accuracy": (
            cadence_holdout_balanced_accuracy >= minimum_cadence_balanced_accuracy
        ),
    }
    blockers = tuple(key for key, passed in checks.items() if not passed)
    passed = not blockers
    decision = (
        "PASS_HARMONIC_FORECAST_COMPATIBILITY"
        if passed
        else "ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE"
    )
    return HarmonicEvidenceGate(
        decision=decision,
        passed=passed,
        checks=checks,
        measurements={
            "observation_count": int(observation_count),
            "occupied_phase_bins": int(occupied_phase_bins),
            "total_phase_bins": int(total_phase_bins),
            "design_condition_number": float(design_condition_number),
            "first_four_snr_count_ge_threshold": first_four_snr_count,
            "forecast_snr_count_ge_threshold": forecast_snr_count,
            "coefficient_snr": [float(value) for value in snr],
            "screen_score": float(screen.score),
            "score_threshold": float(score_threshold),
            "structural_flags": structural_flags,
            "uncertainty_structural_pass_fraction": propagation.structural_pass_fraction,
            "uncertainty_below_threshold_fraction": below_fraction,
            "cadence_holdout_auc": float(cadence_holdout_auc),
            "cadence_holdout_balanced_accuracy": float(
                cadence_holdout_balanced_accuracy
            ),
        },
        blockers=blockers,
    )
