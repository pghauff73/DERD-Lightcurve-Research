"""Explicit predictive and residual metrics for waveform experiments."""
from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _paired(observed: ArrayLike, predicted: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    y = np.asarray(observed, dtype=np.float64).reshape(-1)
    p = np.asarray(predicted, dtype=np.float64).reshape(-1)
    if y.size == 0 or y.size != p.size:
        raise ValueError("observed and predicted must have the same non-zero size")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(p)):
        raise ValueError("observed and predicted must be finite")
    return y, p


def _weights(weights: ArrayLike, size: int) -> NDArray[np.float64]:
    w = np.asarray(weights, dtype=np.float64).reshape(-1)
    if w.size != size or not np.all(np.isfinite(w)) or np.any(w < 0.0):
        raise ValueError("weights must be finite, non-negative, and match the data size")
    total = float(np.sum(w))
    if total <= 0.0:
        raise ValueError("at least one weight must be positive")
    return w


def rmse(observed: ArrayLike, predicted: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    return float(np.sqrt(np.mean((y - p) ** 2)))


def mae(observed: ArrayLike, predicted: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    return float(np.mean(np.abs(y - p)))


def maximum_absolute_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    return float(np.max(np.abs(y - p)))


def weighted_rmse(observed: ArrayLike, predicted: ArrayLike, weights: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    w = _weights(weights, y.size)
    return float(np.sqrt(np.sum(w * np.square(y - p)) / np.sum(w)))


def weighted_mae(observed: ArrayLike, predicted: ArrayLike, weights: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    w = _weights(weights, y.size)
    return float(np.sum(w * np.abs(y - p)) / np.sum(w))


def r_squared(observed: ArrayLike, predicted: ArrayLike) -> float:
    y, p = _paired(observed, predicted)
    denominator = float(np.sum((y - np.mean(y)) ** 2))
    if denominator <= np.finfo(np.float64).eps:
        raise ValueError("R-squared is undefined for a constant observed series")
    return 1.0 - float(np.sum((y - p) ** 2)) / denominator


def lag1_autocorrelation(residuals: ArrayLike) -> float:
    values = np.asarray(residuals, dtype=np.float64).reshape(-1)
    if values.size < 3 or not np.all(np.isfinite(values)):
        raise ValueError("at least three finite residuals are required")
    left = values[:-1] - np.mean(values[:-1])
    right = values[1:] - np.mean(values[1:])
    denominator = math.sqrt(float(left @ left) * float(right @ right))
    if denominator <= np.finfo(np.float64).eps:
        return 0.0
    return float((left @ right) / denominator)


def durbin_watson(residuals: ArrayLike) -> float:
    values = np.asarray(residuals, dtype=np.float64).reshape(-1)
    if values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("at least two finite residuals are required")
    denominator = float(values @ values)
    if denominator <= np.finfo(np.float64).eps:
        return 0.0
    return float(np.sum(np.square(np.diff(values))) / denominator)


def information_criteria(residual_sum_squares: float, sample_count: int, parameter_count: int) -> dict[str, float]:
    """Return Gaussian-residual AIC, AICc, and BIC from ordinary RSS."""

    if not np.isfinite(residual_sum_squares) or residual_sum_squares < 0.0:
        raise ValueError("residual_sum_squares must be finite and non-negative")
    if sample_count < 1 or parameter_count < 1:
        raise ValueError("sample_count and parameter_count must be positive")
    tiny = np.finfo(np.float64).tiny
    base = sample_count * math.log(max(residual_sum_squares / sample_count, tiny))
    aic = base + 2.0 * parameter_count
    denominator = sample_count - parameter_count - 1
    aicc = math.inf if denominator <= 0 else aic + 2.0 * parameter_count * (parameter_count + 1) / denominator
    bic = base + parameter_count * math.log(sample_count)
    return {"aic": float(aic), "aicc": float(aicc), "bic": float(bic)}


def metric_bundle(
    observed: ArrayLike,
    predicted: ArrayLike,
    *,
    weights: ArrayLike | None = None,
    phase: ArrayLike | None = None,
) -> dict[str, float]:
    """Return an auditable metric bundle.

    Residual-order statistics are calculated after sorting by ``phase`` when it
    is supplied. This avoids treating arbitrary file order as temporal order.
    """

    y, p = _paired(observed, predicted)
    residual = y - p
    if phase is not None:
        x = np.asarray(phase, dtype=np.float64).reshape(-1)
        if x.size != y.size or not np.all(np.isfinite(x)):
            raise ValueError("phase must be finite and match the observations")
        residual = residual[np.argsort(np.mod(x, 1.0), kind="mergesort")]
    try:
        r2 = r_squared(y, p)
    except ValueError:
        r2 = float("nan")
    bundle = {
        "rmse": rmse(y, p),
        "mae": mae(y, p),
        "maximum_absolute_error": maximum_absolute_error(y, p),
        "r_squared": r2,
        "residual_lag1_autocorrelation": lag1_autocorrelation(residual) if residual.size >= 3 else float("nan"),
        "durbin_watson": durbin_watson(residual) if residual.size >= 2 else float("nan"),
    }
    if weights is not None:
        bundle["weighted_rmse"] = weighted_rmse(y, p, weights)
        bundle["weighted_mae"] = weighted_mae(y, p, weights)
    return bundle
