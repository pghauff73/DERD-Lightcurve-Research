"""Leakage-resistant preprocessing for observational light curves."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .lightcurve import LightCurve


@dataclass(frozen=True, slots=True)
class CleaningReport:
    input_count: int
    output_count: int
    removed_count: int
    error_threshold: float

    def as_dict(self) -> dict[str, object]:
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "removed_count": self.removed_count,
            "error_threshold": self.error_threshold,
        }


@dataclass(frozen=True, slots=True)
class TrainMinMaxScaler:
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.minimum) or not np.isfinite(self.maximum):
            raise ValueError("scaler bounds must be finite")
        if self.maximum <= self.minimum:
            raise ValueError("scaler maximum must exceed minimum")

    @property
    def span(self) -> float:
        return self.maximum - self.minimum

    def transform_values(self, values: ArrayLike) -> NDArray[np.float64]:
        array = np.asarray(values, dtype=np.float64)
        if not np.all(np.isfinite(array)):
            raise ValueError("values must be finite")
        return (array - self.minimum) / self.span

    def transform_errors(self, errors: ArrayLike) -> NDArray[np.float64]:
        array = np.asarray(errors, dtype=np.float64)
        if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
            raise ValueError("errors must be finite and positive")
        return array / self.span

    def as_dict(self) -> dict[str, float]:
        return {"minimum": self.minimum, "maximum": self.maximum, "span": self.span}


def clean_light_curve(curve: LightCurve, *, maximum_error_factor: float = 5.0) -> tuple[LightCurve, CleaningReport]:
    """Remove only gross uncertainty outliers, not brightness extrema.

    Variable-star maxima and minima are signal. Therefore this cleaner does not
    sigma-clip the measured values. It removes observations whose quoted error
    exceeds ``maximum_error_factor`` times the median quoted error.
    """

    if maximum_error_factor <= 1.0 or not np.isfinite(maximum_error_factor):
        raise ValueError("maximum_error_factor must be finite and greater than one")
    threshold = float(np.median(curve.error) * maximum_error_factor)
    mask = curve.error <= threshold
    if np.count_nonzero(mask) < 8:
        raise ValueError("cleaning would leave fewer than eight observations")
    cleaned = curve.subset(mask)
    return cleaned, CleaningReport(
        input_count=curve.size,
        output_count=cleaned.size,
        removed_count=curve.size - cleaned.size,
        error_threshold=threshold,
    )


def fold_phase(time: ArrayLike, period: float, *, epoch: float = 0.0) -> NDArray[np.float64]:
    values = np.asarray(time, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("time must contain finite values")
    if not np.isfinite(period) or period <= 0.0:
        raise ValueError("period must be finite and positive")
    if not np.isfinite(epoch):
        raise ValueError("epoch must be finite")
    return np.mod((values - epoch) / period, 1.0)


def fit_train_minmax(values: ArrayLike) -> TrainMinMaxScaler:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size < 2 or not np.all(np.isfinite(array)):
        raise ValueError("at least two finite training values are required")
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    if maximum - minimum <= np.finfo(np.float64).eps * max(1.0, abs(minimum), abs(maximum)):
        raise ValueError("training values are effectively constant")
    return TrainMinMaxScaler(minimum=minimum, maximum=maximum)


def inverse_variance_weights(errors: ArrayLike, *, clip_ratio: float = 1000.0) -> NDArray[np.float64]:
    array = np.asarray(errors, dtype=np.float64).reshape(-1)
    if array.size == 0 or not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError("errors must be finite and positive")
    if clip_ratio <= 1.0 or not np.isfinite(clip_ratio):
        raise ValueError("clip_ratio must be finite and greater than one")
    weights = 1.0 / np.square(array)
    median = float(np.median(weights))
    if median <= 0.0 or not np.isfinite(median):
        raise ValueError("cannot normalize inverse-variance weights")
    weights /= median
    return np.clip(weights, 1.0 / clip_ratio, clip_ratio)
