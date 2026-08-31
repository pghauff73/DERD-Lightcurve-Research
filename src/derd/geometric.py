"""Geometric-phase elliptical radius functions."""
from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _validate_eccentricity(eccentricity: float) -> float:
    e = float(eccentricity)
    if not math.isfinite(e) or not 0.0 <= e < 1.0:
        raise ValueError("eccentricity must be finite and satisfy 0 <= e < 1")
    return e


def true_anomaly(phase: ArrayLike) -> NDArray[np.float64]:
    """Map phase in cycles to true anomaly in radians."""

    values = np.asarray(phase, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("phase contains non-finite values")
    return 2.0 * math.pi * np.mod(values, 1.0)


def radius_over_semimajor_axis(
    phase: ArrayLike, eccentricity: float
) -> NDArray[np.float64]:
    """Return ``r/a = (1-e^2)/(1+e cos(theta))`` under uniform true anomaly."""

    e = _validate_eccentricity(eccentricity)
    theta = true_anomaly(phase)
    return (1.0 - e * e) / (1.0 + e * np.cos(theta))


def normalized_radius(phase: ArrayLike, eccentricity: float) -> NDArray[np.float64]:
    """Return the analytically min-max-normalized geometric radius.

    The stable closed form

    ``u = (1-e)(1-cos(theta)) / (2(1+e cos(theta)))``

    is exactly equivalent to normalizing ``r/a`` between periapsis ``1-e`` and
    apoapsis ``1+e``. It also supplies the continuous ``e -> 0`` limit instead of
    dividing by a vanishing sampled range.
    """

    e = _validate_eccentricity(eccentricity)
    theta = true_anomaly(phase)
    cosine = np.cos(theta)
    return (1.0 - e) * (1.0 - cosine) / (2.0 * (1.0 + e * cosine))
