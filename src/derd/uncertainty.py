"""Training-only conformal-style prediction interval calibration."""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class SymmetricCalibration:
    nominal_coverage: float
    quantile: float
    calibration_count: int
    standardized: bool
    finite_sample_rank: int

    def as_dict(self) -> dict[str, object]:
        return {
            "nominal_coverage": self.nominal_coverage,
            "quantile": self.quantile,
            "calibration_count": self.calibration_count,
            "standardized": self.standardized,
            "finite_sample_rank": self.finite_sample_rank,
        }


@dataclass(frozen=True, slots=True)
class IntervalMetrics:
    empirical_coverage: float
    mean_width: float
    median_width: float
    interval_score: float
    miss_below_count: int
    miss_above_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "empirical_coverage": self.empirical_coverage,
            "mean_width": self.mean_width,
            "median_width": self.median_width,
            "interval_score": self.interval_score,
            "miss_below_count": self.miss_below_count,
            "miss_above_count": self.miss_above_count,
        }


def _paired(observed: ArrayLike, predicted: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    y = np.asarray(observed, dtype=np.float64).reshape(-1)
    p = np.asarray(predicted, dtype=np.float64).reshape(-1)
    if y.size == 0 or y.size != p.size or not np.all(np.isfinite(y)) or not np.all(np.isfinite(p)):
        raise ValueError("observed and predicted must be finite and have matching non-zero size")
    return y, p


def calibrate_symmetric_interval(
    observed: ArrayLike,
    predicted: ArrayLike,
    *,
    nominal_coverage: float = 0.90,
    scale: ArrayLike | None = None,
    minimum_scale: float = 1.0e-6,
) -> SymmetricCalibration:
    """Calibrate an absolute or error-standardized symmetric residual interval.

    The finite-sample rank is ``ceil((n + 1) * coverage)`` and is clipped to
    the available calibration count. All inputs must come from training-only
    out-of-fold predictions when the result is used on a held-out set.
    """

    y, p = _paired(observed, predicted)
    if not 0.5 < nominal_coverage < 1.0:
        raise ValueError("nominal_coverage must lie between 0.5 and 1")
    if not np.isfinite(minimum_scale) or minimum_scale <= 0.0:
        raise ValueError("minimum_scale must be finite and positive")
    residual = np.abs(y - p)
    standardized = scale is not None
    if scale is not None:
        s = np.asarray(scale, dtype=np.float64).reshape(-1)
        if s.size != y.size or not np.all(np.isfinite(s)) or np.any(s <= 0.0):
            raise ValueError("scale must be finite, positive, and match observations")
        residual = residual / np.maximum(s, minimum_scale)
    sorted_residual = np.sort(residual)
    rank = min(y.size, max(1, int(math.ceil((y.size + 1) * nominal_coverage))))
    return SymmetricCalibration(
        nominal_coverage=float(nominal_coverage),
        quantile=float(sorted_residual[rank - 1]),
        calibration_count=int(y.size),
        standardized=standardized,
        finite_sample_rank=rank,
    )


def prediction_interval(
    predicted: ArrayLike,
    calibration: SymmetricCalibration,
    *,
    scale: ArrayLike | None = None,
    minimum_scale: float = 1.0e-6,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    p = np.asarray(predicted, dtype=np.float64).reshape(-1)
    if p.size == 0 or not np.all(np.isfinite(p)):
        raise ValueError("predicted must contain finite values")
    if calibration.standardized:
        if scale is None:
            raise ValueError("a prediction scale is required for standardized calibration")
        s = np.asarray(scale, dtype=np.float64).reshape(-1)
        if s.size != p.size or not np.all(np.isfinite(s)) or np.any(s <= 0.0):
            raise ValueError("scale must be finite, positive, and match predicted")
        radius = calibration.quantile * np.maximum(s, minimum_scale)
    else:
        if scale is not None:
            raise ValueError("scale must be omitted for unstandardized calibration")
        radius = np.full_like(p, calibration.quantile)
    return p - radius, p + radius


def interval_metrics(
    observed: ArrayLike,
    lower: ArrayLike,
    upper: ArrayLike,
    *,
    nominal_coverage: float,
) -> IntervalMetrics:
    y = np.asarray(observed, dtype=np.float64).reshape(-1)
    low = np.asarray(lower, dtype=np.float64).reshape(-1)
    high = np.asarray(upper, dtype=np.float64).reshape(-1)
    if y.size == 0 or y.size != low.size or y.size != high.size:
        raise ValueError("observed, lower, and upper must have matching non-zero size")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(low)) or not np.all(np.isfinite(high)):
        raise ValueError("interval inputs must be finite")
    if np.any(high < low):
        raise ValueError("upper interval bounds must not be below lower bounds")
    if not 0.5 < nominal_coverage < 1.0:
        raise ValueError("nominal_coverage must lie between 0.5 and 1")
    below = y < low
    above = y > high
    covered = ~(below | above)
    width = high - low
    alpha = 1.0 - nominal_coverage
    score = width.copy()
    score[below] += (2.0 / alpha) * (low[below] - y[below])
    score[above] += (2.0 / alpha) * (y[above] - high[above])
    return IntervalMetrics(
        empirical_coverage=float(np.mean(covered)),
        mean_width=float(np.mean(width)),
        median_width=float(np.median(width)),
        interval_score=float(np.mean(score)),
        miss_below_count=int(np.count_nonzero(below)),
        miss_above_count=int(np.count_nonzero(above)),
    )
