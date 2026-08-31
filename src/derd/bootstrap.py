"""Deterministic bootstrap stability checks for DERD parameters."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .fitting import fit_waveform
from .model import TimeLaw


@dataclass(frozen=True, slots=True)
class BootstrapStability:
    repetitions_requested: int
    repetitions_succeeded: int
    parameter_mean: dict[str, float]
    parameter_std: dict[str, float]
    phase_circular_std: float
    condition_number_median: float

    def as_dict(self) -> dict[str, object]:
        return {
            "repetitions_requested": self.repetitions_requested,
            "repetitions_succeeded": self.repetitions_succeeded,
            "parameter_mean": self.parameter_mean,
            "parameter_std": self.parameter_std,
            "phase_circular_std": self.phase_circular_std,
            "condition_number_median": self.condition_number_median,
        }


def bootstrap_fit_stability(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    weights: ArrayLike | None = None,
    time_law: TimeLaw | str = TimeLaw.GEOMETRIC,
    repetitions: int = 8,
    seed: int = 20260807,
    starts: int = 4,
    max_function_evaluations: int = 250,
) -> BootstrapStability:
    x = np.asarray(phase, dtype=np.float64).reshape(-1)
    y = np.asarray(flux, dtype=np.float64).reshape(-1)
    if x.size != y.size or x.size < 12:
        raise ValueError("phase and flux must match and contain at least twelve observations")
    w = None if weights is None else np.asarray(weights, dtype=np.float64).reshape(-1)
    if w is not None and w.size != x.size:
        raise ValueError("weights must match phase")
    if repetitions < 2:
        raise ValueError("repetitions must be at least two")

    rng = np.random.default_rng(seed)
    vectors: list[list[float]] = []
    conditions: list[float] = []
    for repetition in range(repetitions):
        indices = rng.integers(0, x.size, size=x.size)
        try:
            result = fit_waveform(
                x[indices],
                y[indices],
                weights=None if w is None else w[indices],
                time_law=time_law,
                starts=starts,
                seed=seed + repetition + 1,
                max_function_evaluations=max_function_evaluations,
                normalize_target=False,
                align_peak=True,
                normalization_grid_size=1024,
                peak_grid_size=512,
            )
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            continue
        vectors.append(list(result.parameters.as_tuple()))
        conditions.append(result.jacobian_condition_number)

    if not vectors:
        raise RuntimeError("all bootstrap fits failed")
    matrix = np.asarray(vectors, dtype=np.float64)
    names = ("e1", "e2", "amplitude_ratio", "phase_ratio")
    mean = {name: float(value) for name, value in zip(names, np.mean(matrix, axis=0), strict=True)}
    std = {name: float(value) for name, value in zip(names, np.std(matrix, axis=0, ddof=0), strict=True)}
    angles = 2.0 * np.pi * matrix[:, 3]
    resultant = abs(np.mean(np.exp(1j * angles)))
    phase_circular_std = float(np.sqrt(max(0.0, -2.0 * np.log(max(resultant, 1e-15)))) / (2.0 * np.pi))
    return BootstrapStability(
        repetitions_requested=int(repetitions),
        repetitions_succeeded=int(matrix.shape[0]),
        parameter_mean=mean,
        parameter_std=std,
        phase_circular_std=phase_circular_std,
        condition_number_median=float(np.median(np.asarray(conditions, dtype=np.float64))),
    )
