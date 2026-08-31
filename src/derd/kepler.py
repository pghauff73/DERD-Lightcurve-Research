"""Kepler-time elliptical radius functions."""
from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _validate_eccentricity(eccentricity: float) -> float:
    e = float(eccentricity)
    if not math.isfinite(e) or not 0.0 <= e < 1.0:
        raise ValueError("eccentricity must be finite and satisfy 0 <= e < 1")
    return e


def solve_eccentric_anomaly(
    mean_anomaly: ArrayLike,
    eccentricity: float,
    *,
    tolerance: float = 1e-13,
    max_iterations: int = 64,
) -> NDArray[np.float64]:
    """Solve ``E - e sin(E) = M`` with Newton iterations and bisection fallback.

    The function accepts arbitrary finite mean anomalies, preserving complete cycles.
    For ``0 <= e < 1`` the scalar equation is monotone, making the fallback bracket
    deterministic and reliable even near ``e = 1``.
    """

    e = _validate_eccentricity(eccentricity)
    M = np.asarray(mean_anomaly, dtype=np.float64)
    if not np.all(np.isfinite(M)):
        raise ValueError("mean_anomaly contains non-finite values")
    if tolerance <= 0.0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be finite and positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")

    two_pi = 2.0 * math.pi
    cycles = np.floor(M / two_pi)
    wrapped = M - cycles * two_pi
    if e == 0.0:
        return wrapped + cycles * two_pi

    if e < 0.8:
        E = wrapped.copy()
    else:
        sign = np.where(np.sin(wrapped) >= 0.0, 1.0, -1.0)
        E = wrapped + 0.85 * e * sign
        E = np.clip(E, 0.0, two_pi)

    converged = np.zeros(E.shape, dtype=bool)
    for _ in range(max_iterations):
        residual = E - e * np.sin(E) - wrapped
        derivative = 1.0 - e * np.cos(E)
        step = residual / derivative
        E_next = E - step
        # Newton can occasionally step outside the monotone bracket at high e.
        E_next = np.where((E_next >= 0.0) & (E_next <= two_pi), E_next, E)
        converged_now = np.abs(residual) <= tolerance
        converged |= converged_now
        E = np.where(converged, E, E_next)
        if bool(np.all(converged)):
            break

    residual = E - e * np.sin(E) - wrapped
    failed = np.abs(residual) > max(tolerance * 8.0, 1e-14)
    if np.any(failed):
        flat_E = E.reshape(-1)
        flat_M = wrapped.reshape(-1)
        flat_failed = failed.reshape(-1)
        for index in np.flatnonzero(flat_failed):
            target = float(flat_M[index])
            low, high = 0.0, two_pi
            for _ in range(96):
                mid = 0.5 * (low + high)
                value = mid - e * math.sin(mid) - target
                if value > 0.0:
                    high = mid
                else:
                    low = mid
                if high - low <= tolerance:
                    break
            flat_E[index] = 0.5 * (low + high)
        E = flat_E.reshape(E.shape)

    return E + cycles * two_pi


def eccentric_anomaly_from_phase(
    phase: ArrayLike, eccentricity: float
) -> NDArray[np.float64]:
    values = np.asarray(phase, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("phase contains non-finite values")
    mean_anomaly = 2.0 * math.pi * np.mod(values, 1.0)
    return solve_eccentric_anomaly(mean_anomaly, eccentricity)


def radius_over_semimajor_axis(
    phase: ArrayLike, eccentricity: float
) -> NDArray[np.float64]:
    e = _validate_eccentricity(eccentricity)
    E = eccentric_anomaly_from_phase(phase, e)
    return 1.0 - e * np.cos(E)


def normalized_radius(phase: ArrayLike, eccentricity: float) -> NDArray[np.float64]:
    """Return analytically normalized Kepler-time radius.

    Since ``r/a = 1-e cos(E)`` spans ``[1-e, 1+e]``, normalization reduces to
    ``(1-cos(E))/2``. Eccentricity remains active through Kepler's equation, and the
    expression has a well-defined circular limit.
    """

    e = _validate_eccentricity(eccentricity)
    E = eccentric_anomaly_from_phase(phase, e)
    return 0.5 * (1.0 - np.cos(E))
