"""Parameter schema for the dual-elliptic radius-difference (DERD) model."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable, Mapping

DIMENSION_NAMES = ("e1", "e2", "amplitude_ratio", "phase_ratio")


@dataclass(frozen=True, slots=True)
class DERDParameters:
    """Authoritative four-parameter DERD schema.

    Parameters
    ----------
    e1, e2:
        Eccentricity-shaped waveform controls. Values must satisfy ``0 <= e < 1``.
        In the reference implementation they are phenomenological shape parameters
        unless a separately tested physical interpretation is supplied.
    amplitude_ratio:
        Positive multiplier applied to the second normalized radius component.
    phase_ratio:
        Periodic phase offset in cycles. Any finite value is accepted and wrapped to
        the canonical interval ``[0, 1)``.
    """

    e1: float
    e2: float
    amplitude_ratio: float
    phase_ratio: float

    def __post_init__(self) -> None:
        values = {
            "e1": float(self.e1),
            "e2": float(self.e2),
            "amplitude_ratio": float(self.amplitude_ratio),
            "phase_ratio": float(self.phase_ratio),
        }
        for name, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite; received {value!r}")
        if not 0.0 <= values["e1"] < 1.0:
            raise ValueError("e1 must satisfy 0 <= e1 < 1")
        if not 0.0 <= values["e2"] < 1.0:
            raise ValueError("e2 must satisfy 0 <= e2 < 1")
        if values["amplitude_ratio"] <= 0.0:
            raise ValueError("amplitude_ratio must be strictly positive")

        object.__setattr__(self, "e1", values["e1"])
        object.__setattr__(self, "e2", values["e2"])
        object.__setattr__(self, "amplitude_ratio", values["amplitude_ratio"])
        object.__setattr__(self, "phase_ratio", values["phase_ratio"] % 1.0)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.e1, self.e2, self.amplitude_ratio, self.phase_ratio)

    def as_dict(self) -> dict[str, float]:
        return dict(zip(DIMENSION_NAMES, self.as_tuple(), strict=True))

    def with_dimension(self, name: str, value: float) -> "DERDParameters":
        if name not in DIMENSION_NAMES:
            raise KeyError(f"unknown DERD dimension {name!r}; expected one of {DIMENSION_NAMES}")
        return replace(self, **{name: float(value)})

    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "DERDParameters":
        ordered = tuple(float(value) for value in values)
        if len(ordered) != 4:
            raise ValueError(f"expected four DERD values, received {len(ordered)}")
        return cls(*ordered)

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> "DERDParameters":
        missing = [name for name in DIMENSION_NAMES if name not in values]
        if missing:
            raise ValueError(f"missing DERD dimensions: {', '.join(missing)}")
        return cls(*(float(values[name]) for name in DIMENSION_NAMES))
