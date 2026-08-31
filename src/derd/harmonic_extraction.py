"""Lossless weighted harmonic extraction from irregular raw photometry.

This module implements the Phase-07 evidence gate:

raw photometry -> signed sine/cosine coefficients -> full covariance ->
DERD-HARMONIC-EXCHANGE-1.0.

The extraction is deliberately generic.  It estimates a periodic Fourier
representation and does not optimize the DERD recurrence itself.  The first
four harmonics may later be used for algebraic recovery and harmonics five and
above remain available as a spectral-domain forecast test.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Literal, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize_scalar

from .harmonic_exchange import CanonicalHarmonicSeries
from .lightcurve import LightCurve, ValueDomain
from .preprocess import fold_phase

CovarianceEstimator = Literal["photometric", "hc3"]
_EPS = np.finfo(np.float64).eps


def git_blob_sha1_bytes(data: bytes) -> str:
    """Return the Git object ID for a regular blob containing ``data``."""

    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def git_blob_sha1_file(path: str | Path) -> str:
    return git_blob_sha1_bytes(Path(path).read_bytes())


def _nearest_psd(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    symmetric = 0.5 * (matrix + matrix.T)
    values, vectors = np.linalg.eigh(symmetric)
    scale = max(1.0, float(np.max(np.abs(values))))
    clipped = np.clip(values, 0.0, None)
    clipped[clipped < 1.0e-15 * scale] = 0.0
    output = (vectors * clipped) @ vectors.T
    return 0.5 * (output + output.T)


def phase_coverage_statistics(phase: ArrayLike, *, bins: int = 12) -> dict[str, Any]:
    values = np.mod(np.asarray(phase, dtype=np.float64).reshape(-1), 1.0)
    if values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("phase must contain at least two finite values")
    if bins < 4:
        raise ValueError("bins must be at least four")
    counts, _ = np.histogram(values, bins=bins, range=(0.0, 1.0))
    ordered = np.sort(values)
    gaps = np.diff(np.concatenate((ordered, [ordered[0] + 1.0])))
    return {
        "bin_count": int(bins),
        "bin_counts": [int(value) for value in counts],
        "occupied_bins": int(np.count_nonzero(counts)),
        "minimum_bin_count": int(np.min(counts)),
        "maximum_bin_count": int(np.max(counts)),
        "maximum_circular_phase_gap": float(np.max(gaps)),
        "median_circular_phase_gap": float(np.median(gaps)),
    }


def _weighted_design(
    phase: NDArray[np.float64],
    *,
    order: int,
) -> NDArray[np.float64]:
    columns: list[NDArray[np.float64]] = [np.ones(phase.size, dtype=np.float64)]
    for harmonic in range(1, order + 1):
        columns.append(np.sin(2.0 * math.pi * harmonic * phase))
    for harmonic in range(1, order + 1):
        columns.append(np.cos(2.0 * math.pi * harmonic * phase))
    return np.column_stack(columns)


@dataclass(frozen=True, slots=True)
class WeightedHarmonicExtraction:
    """A lossless harmonic exchange record plus extraction diagnostics."""

    series: CanonicalHarmonicSeries
    intercept: float
    intercept_standard_error: float
    period_days: float
    sample_count: int
    effective_rank: int
    design_condition_number: float
    ridge: float
    covariance_estimator: CovarianceEstimator
    residual_rmse: float
    weighted_reduced_chi_square: float
    harmonic_wald_snr: NDArray[np.float64]
    complex_standard_errors: NDArray[np.float64]
    phase_coverage: Mapping[str, Any]
    photometric_covariance_trace: float
    robust_covariance_trace: float

    def __post_init__(self) -> None:
        snr = np.asarray(self.harmonic_wald_snr, dtype=np.float64).reshape(-1)
        errors = np.asarray(self.complex_standard_errors, dtype=np.float64).reshape(-1)
        if snr.size != self.series.harmonic_count or errors.size != self.series.harmonic_count:
            raise ValueError("diagnostic arrays must match harmonic count")
        if not np.all(np.isfinite(snr)) or np.any(snr < 0.0):
            raise ValueError("harmonic_wald_snr must be finite and non-negative")
        if not np.all(np.isfinite(errors)) or np.any(errors < 0.0):
            raise ValueError("complex_standard_errors must be finite and non-negative")
        object.__setattr__(self, "harmonic_wald_snr", snr)
        object.__setattr__(self, "complex_standard_errors", errors)
        object.__setattr__(self, "phase_coverage", dict(self.phase_coverage))

    def as_dict(self, *, include_exchange: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "intercept": self.intercept,
            "intercept_standard_error": self.intercept_standard_error,
            "period_days": self.period_days,
            "sample_count": self.sample_count,
            "harmonic_count": self.series.harmonic_count,
            "effective_rank": self.effective_rank,
            "design_condition_number": self.design_condition_number,
            "ridge": self.ridge,
            "covariance_estimator": self.covariance_estimator,
            "residual_rmse": self.residual_rmse,
            "weighted_reduced_chi_square": self.weighted_reduced_chi_square,
            "harmonic_wald_snr": [float(value) for value in self.harmonic_wald_snr],
            "complex_standard_errors": [
                float(value) for value in self.complex_standard_errors
            ],
            "phase_coverage": dict(self.phase_coverage),
            "photometric_covariance_trace": self.photometric_covariance_trace,
            "robust_covariance_trace": self.robust_covariance_trace,
        }
        if include_exchange:
            payload["exchange"] = self.series.as_dict()
        return payload


@dataclass(frozen=True, slots=True)
class HarmonicPeriodProfile:
    catalog_period_days: float
    best_period_days: float
    relative_delta: float
    catalog_chi_square: float
    best_chi_square: float
    reduced_chi_square_at_best: float
    relative_span: float
    grid_count: int
    resolved: bool
    profile_lower_days: float | None
    profile_upper_days: float | None

    @property
    def profile_half_width_days(self) -> float | None:
        if self.profile_lower_days is None or self.profile_upper_days is None:
            return None
        return 0.5 * (self.profile_upper_days - self.profile_lower_days)

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalog_period_days": self.catalog_period_days,
            "best_period_days": self.best_period_days,
            "relative_delta": self.relative_delta,
            "catalog_chi_square": self.catalog_chi_square,
            "best_chi_square": self.best_chi_square,
            "reduced_chi_square_at_best": self.reduced_chi_square_at_best,
            "relative_span": self.relative_span,
            "grid_count": self.grid_count,
            "resolved": self.resolved,
            "profile_lower_days": self.profile_lower_days,
            "profile_upper_days": self.profile_upper_days,
            "profile_half_width_days": self.profile_half_width_days,
        }


def _solve_weighted_harmonics(
    phase: NDArray[np.float64],
    values: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    order: int,
    ridge: float,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    float,
    int,
    float,
    float,
    NDArray[np.float64],
]:
    design = _weighted_design(phase, order=order)
    inverse_variance = 1.0 / np.square(errors)
    sqrt_weight = np.sqrt(inverse_variance)
    weighted_design = design * sqrt_weight[:, None]
    weighted_values = values * sqrt_weight
    normal = weighted_design.T @ weighted_design
    regularizer = np.zeros_like(normal)
    if ridge > 0.0:
        scale = float(np.trace(normal) / normal.shape[0])
        regularizer[1:, 1:] = np.eye(normal.shape[0] - 1) * ridge * scale
    penalized = normal + regularizer
    right = weighted_design.T @ weighted_values
    beta = np.linalg.solve(penalized, right)
    fitted = design @ beta
    residual = values - fitted
    condition = float(np.linalg.cond(weighted_design))
    rank = int(np.linalg.matrix_rank(weighted_design))
    dof = max(1, values.size - rank)
    chi_square = float(np.sum(np.square(residual / errors)))
    reduced_chi_square = chi_square / dof

    inverse_penalized = np.linalg.pinv(penalized, hermitian=True)
    photometric_covariance = inverse_penalized @ normal @ inverse_penalized

    leverage = np.einsum(
        "ij,jk,ik->i",
        weighted_design,
        inverse_penalized,
        weighted_design,
        optimize=True,
    )
    leverage = np.clip(leverage, 0.0, 1.0 - 1.0e-9)
    adjusted = residual / (1.0 - leverage)
    score_rows = design * (inverse_variance * adjusted)[:, None]
    meat = score_rows.T @ score_rows
    robust_covariance = inverse_penalized @ meat @ inverse_penalized
    robust_covariance = _nearest_psd(robust_covariance)
    photometric_covariance = _nearest_psd(photometric_covariance)
    return (
        beta,
        fitted,
        residual,
        photometric_covariance,
        condition,
        rank,
        reduced_chi_square,
        chi_square,
        robust_covariance,
    )


def fit_weighted_harmonic_exchange(
    curve: LightCurve,
    *,
    period_days: float,
    order: int = 8,
    reference_epoch: float | None = None,
    ridge: float = 1.0e-8,
    covariance_estimator: CovarianceEstimator = "hc3",
    source_locator: str | None = None,
    source_sha256: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    phase_bins: int = 12,
) -> WeightedHarmonicExtraction:
    """Extract signed harmonics and a full covariance from raw photometry.

    Magnitudes are converted to relative flux before fitting.  The design is
    simultaneous, so every harmonic is estimated conditionally on the others.
    The covariance order in the exchange record is
    ``[sin_1,...,sin_N,cos_1,...,cos_N]``.
    """

    if not math.isfinite(period_days) or period_days <= 0.0:
        raise ValueError("period_days must be finite and positive")
    if order < 1:
        raise ValueError("order must be positive")
    if curve.size < 2 * order + 3:
        raise ValueError("light curve has too few observations for requested harmonic order")
    if not math.isfinite(ridge) or ridge < 0.0:
        raise ValueError("ridge must be finite and non-negative")
    if covariance_estimator not in {"photometric", "hc3"}:
        raise ValueError("unsupported covariance_estimator")

    active_curve = curve.to_relative_flux() if curve.domain is ValueDomain.MAGNITUDE else curve
    epoch = float(np.min(active_curve.time)) if reference_epoch is None else float(reference_epoch)
    if not math.isfinite(epoch):
        raise ValueError("reference_epoch must be finite")
    phase = fold_phase(active_curve.time, period_days, epoch=epoch)
    solved = _solve_weighted_harmonics(
        phase,
        active_curve.value,
        active_curve.error,
        order=order,
        ridge=ridge,
    )
    (
        beta,
        fitted,
        residual,
        photometric_covariance,
        condition,
        rank,
        reduced_chi_square,
        _chi_square,
        robust_covariance,
    ) = solved
    covariance_full = (
        photometric_covariance if covariance_estimator == "photometric" else robust_covariance
    )
    harmonic_covariance = covariance_full[1:, 1:]
    sine = beta[1 : order + 1]
    cosine = beta[order + 1 :]

    wald_snr = np.zeros(order, dtype=np.float64)
    complex_errors = np.zeros(order, dtype=np.float64)
    for index in range(order):
        positions = np.asarray([index, order + index], dtype=np.int64)
        block = harmonic_covariance[np.ix_(positions, positions)]
        vector = np.asarray([sine[index], cosine[index]], dtype=np.float64)
        inverse = np.linalg.pinv(block, hermitian=True)
        statistic = float(vector @ inverse @ vector)
        wald_snr[index] = math.sqrt(max(0.0, statistic))
        complex_errors[index] = 0.5 * math.sqrt(
            max(0.0, float(block[0, 0] + block[1, 1]))
        )

    local_sha = source_sha256 or str(active_curve.metadata.get("local_sha256", ""))
    if not local_sha:
        raise ValueError("source_sha256 is required when absent from curve metadata")
    locator = source_locator or str(active_curve.metadata.get("source_locator", ""))
    if not locator:
        locator = str(active_curve.metadata.get("local_path", "local-photometry"))

    exchange_metadata = dict(metadata or {})
    exchange_metadata.update(
        {
            "period_days": float(period_days),
            "reference_epoch_policy": (
                "minimum_observation_time" if reference_epoch is None else "explicit"
            ),
            "observation_count": int(active_curve.size),
            "input_domain": curve.domain.value,
            "fit_domain": active_curve.domain.value,
            "band": active_curve.band,
            "intercept": float(beta[0]),
            "covariance_estimator": covariance_estimator,
            "coefficient_covariance_order": [
                *[f"sin_{value}" for value in range(1, order + 1)],
                *[f"cos_{value}" for value in range(1, order + 1)],
            ],
            "ridge": float(ridge),
            "design_condition_number": condition,
            "weighted_reduced_chi_square": reduced_chi_square,
            "residual_rmse": float(np.sqrt(np.mean(np.square(residual)))),
            "phase_coverage": phase_coverage_statistics(phase, bins=phase_bins),
        }
    )
    series = CanonicalHarmonicSeries(
        object_id=active_curve.star_id,
        fundamental_frequency=1.0 / float(period_days),
        reference_epoch=epoch,
        time_unit="day",
        value_unit="relative_flux",
        sine_coefficients=sine,
        cosine_coefficients=cosine,
        coefficient_covariance=harmonic_covariance,
        source_locator=locator,
        source_sha256=local_sha,
        intercept=float(beta[0]),
        metadata=exchange_metadata,
    )
    return WeightedHarmonicExtraction(
        series=series,
        intercept=float(beta[0]),
        intercept_standard_error=math.sqrt(max(0.0, float(covariance_full[0, 0]))),
        period_days=float(period_days),
        sample_count=int(active_curve.size),
        effective_rank=rank,
        design_condition_number=condition,
        ridge=float(ridge),
        covariance_estimator=covariance_estimator,
        residual_rmse=float(np.sqrt(np.mean(np.square(residual)))),
        weighted_reduced_chi_square=reduced_chi_square,
        harmonic_wald_snr=wald_snr,
        complex_standard_errors=complex_errors,
        phase_coverage=phase_coverage_statistics(phase, bins=phase_bins),
        photometric_covariance_trace=float(np.trace(photometric_covariance[1:, 1:])),
        robust_covariance_trace=float(np.trace(robust_covariance[1:, 1:])),
    )


def _harmonic_chi_square(
    curve: LightCurve,
    period_days: float,
    *,
    order: int,
    reference_epoch: float,
    ridge: float,
) -> tuple[float, float]:
    active = curve.to_relative_flux() if curve.domain is ValueDomain.MAGNITUDE else curve
    phase = fold_phase(active.time, period_days, epoch=reference_epoch)
    solved = _solve_weighted_harmonics(
        phase,
        active.value,
        active.error,
        order=order,
        ridge=ridge,
    )
    chi_square = float(solved[7])
    reduced = float(solved[6])
    return chi_square, reduced


def refine_period_by_weighted_harmonics(
    curve: LightCurve,
    catalog_period_days: float,
    *,
    order: int = 8,
    relative_span: float = 2.0e-4,
    grid_count: int = 201,
    ridge: float = 1.0e-8,
    reference_epoch: float | None = None,
) -> HarmonicPeriodProfile:
    """Refine a catalog period using only a generic weighted harmonic fit.

    The objective does not include a DERD recurrence term.  This keeps period
    selection logically upstream of the model-family compatibility test.
    """

    if not math.isfinite(catalog_period_days) or catalog_period_days <= 0.0:
        raise ValueError("catalog_period_days must be finite and positive")
    if not 0.0 < relative_span < 0.05:
        raise ValueError("relative_span must lie between zero and 0.05")
    if grid_count < 21 or grid_count % 2 == 0:
        raise ValueError("grid_count must be an odd integer of at least 21")
    active = curve.to_relative_flux() if curve.domain is ValueDomain.MAGNITUDE else curve
    epoch = float(np.min(active.time)) if reference_epoch is None else float(reference_epoch)
    offsets = np.linspace(-relative_span, relative_span, grid_count)
    periods = catalog_period_days * (1.0 + offsets)
    chi = np.asarray(
        [
            _harmonic_chi_square(
                active,
                float(period),
                order=order,
                reference_epoch=epoch,
                ridge=ridge,
            )[0]
            for period in periods
        ],
        dtype=np.float64,
    )
    index = int(np.argmin(chi))
    step = float(periods[1] - periods[0])
    resolved = bool(index not in {0, grid_count - 1})
    if resolved:
        lower = float(periods[max(0, index - 1)])
        upper = float(periods[min(grid_count - 1, index + 1)])

        def objective(period: float) -> float:
            return _harmonic_chi_square(
                active,
                float(period),
                order=order,
                reference_epoch=epoch,
                ridge=ridge,
            )[0]

        optimized = minimize_scalar(
            objective,
            bounds=(lower, upper),
            method="bounded",
            options={"xatol": max(1.0e-14, step * 1.0e-6)},
        )
        best_period = float(optimized.x)
        best_chi = float(optimized.fun)
    else:
        best_period = float(periods[index])
        best_chi = float(chi[index])

    _, reduced = _harmonic_chi_square(
        active,
        best_period,
        order=order,
        reference_epoch=epoch,
        ridge=ridge,
    )
    catalog_chi = _harmonic_chi_square(
        active,
        catalog_period_days,
        order=order,
        reference_epoch=epoch,
        ridge=ridge,
    )[0]

    # The residual model is imperfect, so scale the nominal one-parameter
    # Delta-chi-square=1 contour by max(1, reduced chi-square).
    threshold = best_chi + max(1.0, reduced)
    dense_offsets = np.linspace(-relative_span, relative_span, max(2001, 5 * grid_count))
    dense_periods = catalog_period_days * (1.0 + dense_offsets)
    dense_chi = np.asarray(
        [
            _harmonic_chi_square(
                active,
                float(period),
                order=order,
                reference_epoch=epoch,
                ridge=ridge,
            )[0]
            for period in dense_periods
        ],
        dtype=np.float64,
    )
    accepted = dense_periods[dense_chi <= threshold]
    profile_lower = float(np.min(accepted)) if accepted.size else None
    profile_upper = float(np.max(accepted)) if accepted.size else None
    return HarmonicPeriodProfile(
        catalog_period_days=float(catalog_period_days),
        best_period_days=best_period,
        relative_delta=(best_period - catalog_period_days) / catalog_period_days,
        catalog_chi_square=float(catalog_chi),
        best_chi_square=best_chi,
        reduced_chi_square_at_best=float(reduced),
        relative_span=float(relative_span),
        grid_count=int(grid_count),
        resolved=resolved,
        profile_lower_days=profile_lower,
        profile_upper_days=profile_upper,
    )


def draw_complex_coefficients(
    series: CanonicalHarmonicSeries,
    *,
    draws: int,
    seed: int,
) -> NDArray[np.complex128]:
    """Draw complex harmonic vectors from an exchange covariance."""

    if draws < 1:
        raise ValueError("draws must be positive")
    covariance = series.coefficient_covariance
    if covariance is None:
        raise ValueError("coefficient covariance is required")
    mean = np.concatenate((series.sine_coefficients, series.cosine_coefficients))
    rng = np.random.default_rng(int(seed))
    samples = rng.multivariate_normal(
        mean,
        _nearest_psd(np.asarray(covariance, dtype=np.float64)),
        size=int(draws),
        check_valid="raise",
        method="eigh",
    )
    order = series.harmonic_count
    sine = samples[:, :order]
    cosine = samples[:, order:]
    return 0.5 * (cosine - 1j * sine)
