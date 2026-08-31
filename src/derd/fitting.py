"""Deterministic multi-start least-squares fitting for the four DERD dimensions."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

from .metrics import metric_bundle
from .model import OutputNormalization, TimeLaw, peak_aligned_waveform, peak_phase, waveform
from .normalization import DegenerateNormalizationError, minmax_normalize
from .parameters import DERDParameters

DEFAULT_LOWER = np.array([0.0, 0.0, 0.01, 0.0], dtype=np.float64)
DEFAULT_UPPER = np.array([0.98, 0.98, 2.0, np.nextafter(1.0, 0.0)], dtype=np.float64)


@dataclass(frozen=True, slots=True)
class DERDFitResult:
    parameters: DERDParameters
    prediction: NDArray[np.float64]
    metrics: dict[str, float]
    success: bool
    message: str
    evaluations: int
    starts_attempted: int
    jacobian_singular_values: NDArray[np.float64]
    jacobian_condition_number: float
    covariance: NDArray[np.float64] | None
    time_law: TimeLaw
    peak_aligned: bool = False
    intrinsic_peak_phase: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "parameters": self.parameters.as_dict(),
            "metrics": self.metrics,
            "success": self.success,
            "message": self.message,
            "evaluations": self.evaluations,
            "starts_attempted": self.starts_attempted,
            "jacobian_singular_values": self.jacobian_singular_values.tolist(),
            "jacobian_condition_number": self.jacobian_condition_number,
            "covariance": None if self.covariance is None else self.covariance.tolist(),
            "time_law": self.time_law.value,
            "peak_aligned": self.peak_aligned,
            "intrinsic_peak_phase": self.intrinsic_peak_phase,
        }


def _validate_bounds(
    lower: ArrayLike | None, upper: ArrayLike | None
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    low = DEFAULT_LOWER.copy() if lower is None else np.asarray(lower, dtype=np.float64)
    high = DEFAULT_UPPER.copy() if upper is None else np.asarray(upper, dtype=np.float64)
    if low.shape != (4,) or high.shape != (4,):
        raise ValueError("lower and upper bounds must each contain four values")
    if not np.all(np.isfinite(low)) or not np.all(np.isfinite(high)):
        raise ValueError("bounds must be finite")
    if np.any(low >= high):
        raise ValueError("every lower bound must be strictly below its upper bound")
    if low[0] < 0.0 or low[1] < 0.0 or high[0] >= 1.0 or high[1] >= 1.0:
        raise ValueError("eccentricity bounds must remain within [0, 1)")
    if low[2] <= 0.0:
        raise ValueError("amplitude lower bound must be positive")
    if low[3] < 0.0 or high[3] > 1.0:
        raise ValueError("phase bounds must lie within [0, 1]")
    return low, high


def _initial_points(
    low: NDArray[np.float64],
    high: NDArray[np.float64],
    *,
    starts: int,
    seed: int,
    supplied: Iterable[ArrayLike] | None,
) -> list[NDArray[np.float64]]:
    if starts < 1:
        raise ValueError("starts must be positive")
    points: list[NDArray[np.float64]] = []
    if supplied is not None:
        for point in supplied:
            values = np.asarray(point, dtype=np.float64)
            if values.shape != (4,):
                raise ValueError("every supplied initial point must contain four values")
            points.append(np.clip(values, low, high))

    deterministic = [
        np.array([0.10, 0.30, 0.35, 0.25]),
        np.array([0.30, 0.70, 0.55, 0.75]),
        np.array([0.70, 0.30, 0.85, 0.50]),
        np.array([0.15, 0.80, 1.20, 0.90]),
    ]
    for point in deterministic:
        if len(points) >= starts:
            break
        points.append(np.clip(point, low, high))

    rng = np.random.default_rng(seed)
    while len(points) < starts:
        points.append(rng.uniform(low, high))
    return points[:starts]


def predict_from_fit(
    phase: ArrayLike,
    result: DERDFitResult,
    *,
    normalization_grid_size: int = 2048,
    peak_grid_size: int = 1024,
) -> NDArray[np.float64]:
    if result.peak_aligned:
        return peak_aligned_waveform(
            phase,
            result.parameters,
            time_law=result.time_law,
            normalization_grid_size=normalization_grid_size,
            peak_grid_size=peak_grid_size,
        )
    return waveform(
        phase,
        result.parameters,
        time_law=result.time_law,
        output_normalization=OutputNormalization.CANONICAL,
        normalization_grid_size=normalization_grid_size,
    )


def fit_waveform(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    weights: ArrayLike | None = None,
    starts: int = 12,
    seed: int = 20260807,
    lower_bounds: ArrayLike | None = None,
    upper_bounds: ArrayLike | None = None,
    initial_points: Iterable[ArrayLike] | None = None,
    normalization_grid_size: int = 2048,
    peak_grid_size: int = 1024,
    max_function_evaluations: int = 500,
    normalize_target: bool = True,
    align_peak: bool = False,
) -> DERDFitResult:
    """Fit the corrected four-parameter model using deterministic multi-start search."""

    x = np.asarray(phase, dtype=np.float64).reshape(-1)
    y = np.asarray(flux, dtype=np.float64).reshape(-1)
    if x.size != y.size or x.size < 8:
        raise ValueError("phase and flux must have the same size and at least eight samples")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("phase and flux must be finite")
    if normalize_target:
        y, _ = minmax_normalize(y)
    law = TimeLaw(time_law)
    low, high = _validate_bounds(lower_bounds, upper_bounds)

    if weights is None:
        root_weights = np.ones_like(y)
        metric_weights = None
    else:
        metric_weights = np.asarray(weights, dtype=np.float64).reshape(-1)
        if metric_weights.size != y.size or np.any(metric_weights < 0.0) or not np.all(np.isfinite(metric_weights)):
            raise ValueError("weights must be finite, non-negative, and match the data size")
        root_weights = np.sqrt(metric_weights)

    penalty = np.full_like(y, 1e3)

    def model_values(vector: NDArray[np.float64]) -> NDArray[np.float64]:
        params = DERDParameters.from_iterable(vector)
        if align_peak:
            return peak_aligned_waveform(
                x,
                params,
                time_law=law,
                output_normalization=OutputNormalization.CANONICAL,
                normalization_grid_size=normalization_grid_size,
                peak_grid_size=peak_grid_size,
            )
        return waveform(
            x,
            params,
            time_law=law,
            output_normalization=OutputNormalization.CANONICAL,
            normalization_grid_size=normalization_grid_size,
        )

    def residual(vector: NDArray[np.float64]) -> NDArray[np.float64]:
        try:
            prediction = model_values(vector)
        except (ValueError, DegenerateNormalizationError, FloatingPointError):
            return penalty
        if not np.all(np.isfinite(prediction)):
            return penalty
        return (prediction - y) * root_weights

    best = None
    total_evaluations = 0
    starts_list = _initial_points(low, high, starts=starts, seed=seed, supplied=initial_points)
    for point in starts_list:
        result = least_squares(
            residual,
            point,
            bounds=(low, high),
            method="trf",
            x_scale="jac",
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
            max_nfev=max_function_evaluations,
        )
        total_evaluations += int(result.nfev)
        if best is None or float(result.cost) < float(best.cost):
            best = result

    assert best is not None
    parameters = DERDParameters.from_iterable(best.x)
    prediction = model_values(best.x)

    singular_values = np.linalg.svd(best.jac, compute_uv=False)
    if singular_values.size == 0 or singular_values[-1] <= np.finfo(np.float64).eps:
        condition_number = math.inf
    else:
        condition_number = float(singular_values[0] / singular_values[-1])

    covariance: NDArray[np.float64] | None = None
    rank = int(np.linalg.matrix_rank(best.jac))
    dof = y.size - best.x.size
    if rank == best.x.size and dof > 0:
        residual_variance = float(2.0 * best.cost / dof)
        try:
            covariance = residual_variance * np.linalg.inv(best.jac.T @ best.jac)
        except np.linalg.LinAlgError:
            covariance = None

    intrinsic_peak = (
        peak_phase(
            parameters,
            time_law=law,
            grid_size=peak_grid_size,
            normalization_grid_size=normalization_grid_size,
        )
        if align_peak
        else None
    )
    return DERDFitResult(
        parameters=parameters,
        prediction=prediction,
        metrics=metric_bundle(y, prediction, weights=metric_weights, phase=x),
        success=bool(best.success),
        message=str(best.message),
        evaluations=total_evaluations,
        starts_attempted=len(starts_list),
        jacobian_singular_values=singular_values,
        jacobian_condition_number=condition_number,
        covariance=covariance,
        time_law=law,
        peak_aligned=bool(align_peak),
        intrinsic_peak_phase=intrinsic_peak,
    )
