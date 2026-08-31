"""Analytic harmonic structure of the geometric DERD model."""
from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .parameters import DERDParameters


def q_from_eccentricity(eccentricity: float) -> float:
    e = float(eccentricity)
    if not math.isfinite(e) or not 0.0 <= e < 1.0:
        raise ValueError("eccentricity must satisfy 0 <= e < 1")
    if e == 0.0:
        return 0.0
    return e / (1.0 + math.sqrt(1.0 - e * e))


def eccentricity_from_q(q: float) -> float:
    value = float(q)
    if not math.isfinite(value) or not 0.0 <= value < 1.0:
        raise ValueError("q must satisfy 0 <= q < 1")
    return 2.0 * value / (1.0 + value * value)


def radius_over_semimajor_axis_series(
    phase: ArrayLike,
    eccentricity: float,
    *,
    terms: int,
) -> NDArray[np.float64]:
    """Evaluate the truncated absolutely convergent cosine series for ``r/a``."""

    if terms < 0:
        raise ValueError("terms must be non-negative")
    e = float(eccentricity)
    q = q_from_eccentricity(e)
    theta = 2.0 * math.pi * np.mod(np.asarray(phase, dtype=np.float64), 1.0)
    result = np.ones_like(theta)
    for n in range(1, terms + 1):
        result += 2.0 * ((-q) ** n) * np.cos(n * theta)
    return math.sqrt(1.0 - e * e) * result


def normalized_radius_complex_coefficients(
    eccentricity: float,
    *,
    maximum_harmonic: int,
) -> NDArray[np.complex128]:
    """Return non-negative complex Fourier coefficients of normalized geometric radius.

    The convention is ``f(theta) = sum_n c[n] exp(i*n*theta) + conjugate terms``.
    The returned array contains ``c[0]`` through ``c[maximum_harmonic]``.
    """

    if maximum_harmonic < 0:
        raise ValueError("maximum_harmonic must be non-negative")
    e = float(eccentricity)
    q = q_from_eccentricity(e)
    coefficients = np.zeros(maximum_harmonic + 1, dtype=np.complex128)
    root = math.sqrt(1.0 - e * e)
    # Algebraically equivalent forms avoid cancellation and division by e near the
    # circular limit. For n=1, q**0 is one; higher terms vanish when e=q=0.
    coefficients[0] = 0.5 * (1.0 - e / (1.0 + root))
    for n in range(1, maximum_harmonic + 1):
        coefficients[n] = (
            root
            * ((-1.0) ** n)
            * (q ** (n - 1))
            / (2.0 * (1.0 + root))
        )
    return coefficients


def raw_derd_complex_coefficients(
    parameters: DERDParameters,
    *,
    maximum_harmonic: int,
) -> NDArray[np.complex128]:
    """Return analytic coefficients for the unscaled geometric DERD combination."""

    first = normalized_radius_complex_coefficients(
        parameters.e1, maximum_harmonic=maximum_harmonic
    )
    second = normalized_radius_complex_coefficients(
        parameters.e2, maximum_harmonic=maximum_harmonic
    )
    harmonics = np.arange(maximum_harmonic + 1, dtype=np.float64)
    shift = np.exp(1j * 2.0 * math.pi * parameters.phase_ratio * harmonics)
    return -first + parameters.amplitude_ratio * second * shift


def recurrence_roots(parameters: DERDParameters) -> tuple[complex, complex]:
    """Return the two geometric progression roots controlling harmonics ``n >= 1``."""

    if parameters.e1 == 0.0 or parameters.e2 == 0.0:
        raise ValueError("the two-root recurrence formula requires e1 > 0 and e2 > 0")
    z1 = complex(-q_from_eccentricity(parameters.e1), 0.0)
    z2 = -q_from_eccentricity(parameters.e2) * np.exp(
        1j * 2.0 * math.pi * parameters.phase_ratio
    )
    return z1, complex(z2)


def recurrence_residuals(
    coefficients: ArrayLike,
    *,
    z1: complex,
    z2: complex,
    first_harmonic: int = 1,
) -> NDArray[np.complex128]:
    """Evaluate ``c[n+2]-(z1+z2)c[n+1]+z1*z2*c[n]``."""

    values = np.asarray(coefficients, dtype=np.complex128)
    if values.ndim != 1:
        raise ValueError("coefficients must be one-dimensional")
    if first_harmonic < 0:
        raise ValueError("first_harmonic must be non-negative")
    if values.size < first_harmonic + 3:
        raise ValueError("at least three consecutive coefficients are required")
    n = np.arange(first_harmonic, values.size - 2)
    return values[n + 2] - (z1 + z2) * values[n + 1] + z1 * z2 * values[n]
