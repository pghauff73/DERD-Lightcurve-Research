"""IURMv1.1.1 one-active-dimension experiment helpers."""
from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .model import OutputNormalization, TimeLaw, waveform
from .parameters import DERDParameters, DIMENSION_NAMES


@dataclass(frozen=True, slots=True)
class SweepSpec:
    experiment_id: str
    active_dimension: str
    values: tuple[float, ...]
    frozen_parameters: DERDParameters
    time_law: TimeLaw = TimeLaw.GEOMETRIC
    samples: int = 512
    normalization_grid_size: int = 4096

    def __post_init__(self) -> None:
        if self.active_dimension not in DIMENSION_NAMES:
            raise ValueError(f"active_dimension must be one of {DIMENSION_NAMES}")
        if not self.values:
            raise ValueError("values must not be empty")
        if self.samples < 32:
            raise ValueError("samples must be at least 32")
        object.__setattr__(self, "time_law", TimeLaw(self.time_law))



def _shape_features(values: NDArray[np.float64]) -> dict[str, float]:
    centered = values - np.mean(values)
    standard_deviation = float(np.std(values))
    if standard_deviation <= np.finfo(np.float64).eps:
        skewness = 0.0
        kurtosis_excess = 0.0
    else:
        z = centered / standard_deviation
        skewness = float(np.mean(z**3))
        kurtosis_excess = float(np.mean(z**4) - 3.0)
    derivative = np.roll(values, -1) - values
    coefficients = np.fft.rfft(values) / values.size
    features: dict[str, float] = {
        "mean": float(np.mean(values)),
        "standard_deviation": standard_deviation,
        "skewness": skewness,
        "kurtosis_excess": kurtosis_excess,
        "phase_of_minimum": float(np.argmin(values) / values.size),
        "phase_of_maximum": float(np.argmax(values) / values.size),
        "derivative_energy": float(np.mean(derivative**2)),
    }
    for harmonic in range(1, min(5, coefficients.size)):
        features[f"harmonic_{harmonic}_amplitude"] = float(2.0 * abs(coefficients[harmonic]))
        features[f"harmonic_{harmonic}_phase"] = float(np.angle(coefficients[harmonic]))
    return features


def run_sweep(spec: SweepSpec) -> list[dict[str, object]]:
    """Vary exactly one declared dimension while freezing the other three."""

    phase = np.linspace(0.0, 1.0, spec.samples, endpoint=False, dtype=np.float64)
    rows: list[dict[str, object]] = []
    frozen = spec.frozen_parameters.as_dict()
    for index, active_value in enumerate(spec.values):
        parameters = spec.frozen_parameters.with_dimension(spec.active_dimension, active_value)
        current = parameters.as_dict()
        for name in DIMENSION_NAMES:
            if name == spec.active_dimension:
                continue
            if current[name] != frozen[name]:
                raise AssertionError(f"IURM gate failed: frozen dimension {name} changed")
        values = waveform(
            phase,
            parameters,
            time_law=spec.time_law,
            output_normalization=OutputNormalization.CANONICAL,
            normalization_grid_size=spec.normalization_grid_size,
        )
        rows.append(
            {
                "experiment_id": spec.experiment_id,
                "row_index": index,
                "active_dimension": spec.active_dimension,
                "active_value": float(active_value),
                "time_law": spec.time_law.value,
                **parameters.as_dict(),
                **_shape_features(values),
            }
        )
    return rows


def write_sweep(
    spec: SweepSpec,
    output_directory: str | Path,
) -> tuple[Path, Path]:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows = run_sweep(spec)
    csv_path = directory / f"{spec.experiment_id}.csv"
    json_path = directory / f"{spec.experiment_id}.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps(
            {
                "spec": {
                    "experiment_id": spec.experiment_id,
                    "active_dimension": spec.active_dimension,
                    "values": list(spec.values),
                    "frozen_parameters": spec.frozen_parameters.as_dict(),
                    "time_law": spec.time_law.value,
                    "samples": spec.samples,
                    "normalization_grid_size": spec.normalization_grid_size,
                },
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return csv_path, json_path
