"""Deterministic normalization utilities and their audit metadata."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray


class DegenerateNormalizationError(ValueError):
    """Raised when min-max normalization has no numerically resolvable span."""


@dataclass(frozen=True, slots=True)
class NormalizationStats:
    minimum: float
    maximum: float
    span: float
    reference_size: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "minimum": self.minimum,
            "maximum": self.maximum,
            "span": self.span,
            "reference_size": self.reference_size,
        }


def _finite_1d(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")
    return array


def minmax_normalize(
    values: ArrayLike,
    *,
    reference_values: ArrayLike | None = None,
    relative_tolerance: float = 1e-14,
) -> tuple[NDArray[np.float64], NormalizationStats]:
    """Normalize ``values`` using extrema from ``reference_values``.

    Supplying a separate reference is important for irregular astronomical sampling:
    model scaling should not change merely because an observing cadence missed the
    true maximum or minimum of a cycle.
    """

    array = _finite_1d(values, name="values")
    reference = array if reference_values is None else _finite_1d(
        reference_values, name="reference_values"
    )
    minimum = float(np.min(reference))
    maximum = float(np.max(reference))
    span = maximum - minimum
    scale = max(1.0, abs(minimum), abs(maximum))
    if not math.isfinite(span) or span <= relative_tolerance * scale:
        raise DegenerateNormalizationError(
            "min-max normalization is undefined because the reference span is zero "
            "or numerically degenerate"
        )
    result = (array - minimum) / span
    return result, NormalizationStats(minimum, maximum, span, int(reference.size))


def positive_affine_invariance_error(
    values: ArrayLike,
    *,
    scale: float,
    offset: float,
) -> float:
    """Return the numerical error in ``N(scale*x + offset) = N(x)`` for ``scale > 0``."""

    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale must be finite and strictly positive")
    if not math.isfinite(offset):
        raise ValueError("offset must be finite")
    array = _finite_1d(values, name="values")
    left, _ = minmax_normalize(array)
    right, _ = minmax_normalize(scale * array + offset)
    return float(np.max(np.abs(left - right)))
