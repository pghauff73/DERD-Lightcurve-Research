"""Corrected reference implementation of the DERD waveform family."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from . import geometric, kepler
from .normalization import NormalizationStats, minmax_normalize
from .parameters import DERDParameters


class TimeLaw(str, Enum):
    """How phase is mapped to elliptical radius."""

    GEOMETRIC = "geometric"
    KEPLER = "kepler"


class OutputNormalization(str, Enum):
    """Scaling applied after the two normalized components are combined."""

    NONE = "none"
    SAMPLE = "sample"
    CANONICAL = "canonical"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    time_law: TimeLaw = TimeLaw.GEOMETRIC
    output_normalization: OutputNormalization = OutputNormalization.CANONICAL
    normalization_grid_size: int = 4096

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_law", TimeLaw(self.time_law))
        object.__setattr__(self, "output_normalization", OutputNormalization(self.output_normalization))
        if self.normalization_grid_size < 256:
            raise ValueError("normalization_grid_size must be at least 256")


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    phase: NDArray[np.float64]
    component_1: NDArray[np.float64]
    component_2: NDArray[np.float64]
    raw: NDArray[np.float64]
    values: NDArray[np.float64]
    parameters: DERDParameters
    config: ModelConfig
    normalization: NormalizationStats | None

    def as_summary(self) -> dict[str, object]:
        return {
            "parameters": self.parameters.as_dict(),
            "time_law": self.config.time_law.value,
            "output_normalization": self.config.output_normalization.value,
            "normalization_grid_size": self.config.normalization_grid_size,
            "normalization": None if self.normalization is None else self.normalization.as_dict(),
            "sample_count": int(self.values.size),
            "value_min": float(np.min(self.values)),
            "value_max": float(np.max(self.values)),
        }


def _as_phase(phase: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(phase, dtype=np.float64)
    if values.size == 0:
        raise ValueError("phase must not be empty")
    if not np.all(np.isfinite(values)):
        raise ValueError("phase contains non-finite values")
    return values


def _radius_function(time_law: TimeLaw) -> Callable[[ArrayLike, float], NDArray[np.float64]]:
    if time_law is TimeLaw.GEOMETRIC:
        return geometric.normalized_radius
    if time_law is TimeLaw.KEPLER:
        return kepler.normalized_radius
    raise AssertionError(f"unhandled time law {time_law!r}")


def components(
    phase: ArrayLike,
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Evaluate both individually normalized radius components."""

    phase_array = _as_phase(phase)
    law = TimeLaw(time_law)
    radius = _radius_function(law)
    first = radius(phase_array, parameters.e1)
    shifted_phase = np.mod(phase_array + parameters.phase_ratio, 1.0)
    second = radius(shifted_phase, parameters.e2)
    return first, second


def raw_waveform(
    phase: ArrayLike,
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
) -> NDArray[np.float64]:
    """Return ``-u1 + amplitude_ratio*u2(phase+phase_ratio)`` without final scaling."""

    first, second = components(phase, parameters, time_law=time_law)
    return -first + parameters.amplitude_ratio * second


def canonical_reference(
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    grid_size: int = 4096,
) -> NDArray[np.float64]:
    """Evaluate the raw model on a fixed full-cycle grid used only for normalization."""

    if grid_size < 256:
        raise ValueError("grid_size must be at least 256")
    grid = np.linspace(0.0, 1.0, int(grid_size), endpoint=False, dtype=np.float64)
    return raw_waveform(grid, parameters, time_law=TimeLaw(time_law))


def evaluate(
    phase: ArrayLike,
    parameters: DERDParameters,
    *,
    config: ModelConfig | None = None,
) -> ModelEvaluation:
    """Evaluate a corrected DERD model with explicit, cadence-stable normalization."""

    active = ModelConfig() if config is None else config
    phase_array = _as_phase(phase)
    first, second = components(phase_array, parameters, time_law=active.time_law)
    raw = -first + parameters.amplitude_ratio * second

    stats: NormalizationStats | None
    if active.output_normalization is OutputNormalization.NONE:
        values = raw.copy()
        stats = None
    elif active.output_normalization is OutputNormalization.SAMPLE:
        values, stats = minmax_normalize(raw)
    else:
        reference = canonical_reference(
            parameters,
            time_law=active.time_law,
            grid_size=active.normalization_grid_size,
        )
        values, stats = minmax_normalize(raw, reference_values=reference)

    return ModelEvaluation(
        phase=phase_array.copy(),
        component_1=first,
        component_2=second,
        raw=raw,
        values=values,
        parameters=parameters,
        config=active,
        normalization=stats,
    )


def waveform(
    phase: ArrayLike,
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    output_normalization: OutputNormalization | str = OutputNormalization.CANONICAL,
    normalization_grid_size: int = 4096,
) -> NDArray[np.float64]:
    """Convenience wrapper returning only the model values."""

    return evaluate(
        phase,
        parameters,
        config=ModelConfig(
            time_law=TimeLaw(time_law),
            output_normalization=OutputNormalization(output_normalization),
            normalization_grid_size=normalization_grid_size,
        ),
    ).values


def peak_phase(
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    grid_size: int = 1024,
    normalization_grid_size: int = 2048,
) -> float:
    """Return the intrinsic maximum phase with parabolic sub-grid refinement."""

    if grid_size < 128:
        raise ValueError("grid_size must be at least 128")
    grid = np.linspace(0.0, 1.0, int(grid_size), endpoint=False, dtype=np.float64)
    # Positive affine normalization does not change the maximum location, so
    # use the raw waveform here and avoid a second canonical-grid evaluation.
    values = raw_waveform(grid, parameters, time_law=time_law)
    index = int(np.argmax(values))
    previous = float(values[(index - 1) % grid_size])
    center = float(values[index])
    following = float(values[(index + 1) % grid_size])
    denominator = previous - 2.0 * center + following
    if abs(denominator) <= np.finfo(np.float64).eps:
        offset = 0.0
    else:
        offset = 0.5 * (previous - following) / denominator
        offset = float(np.clip(offset, -0.5, 0.5))
    return float(((index + offset) / grid_size) % 1.0)


def peak_aligned_waveform(
    phase: ArrayLike,
    parameters: DERDParameters,
    *,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    output_normalization: OutputNormalization | str = OutputNormalization.CANONICAL,
    normalization_grid_size: int = 2048,
    peak_grid_size: int = 1024,
) -> NDArray[np.float64]:
    """Evaluate the waveform after quotienting out arbitrary global phase.

    The model's own maximum is shifted to observational phase zero. This keeps
    the four declared DERD shape dimensions while treating epoch choice as an
    observational coordinate, not a fifth physical parameter.
    """

    active_phase = peak_phase(
        parameters,
        time_law=time_law,
        grid_size=peak_grid_size,
        normalization_grid_size=normalization_grid_size,
    )
    shifted = np.mod(_as_phase(phase) + active_phase, 1.0)
    return waveform(
        shifted,
        parameters,
        time_law=time_law,
        output_normalization=output_normalization,
        normalization_grid_size=normalization_grid_size,
    )
