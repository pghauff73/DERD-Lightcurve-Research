"""Adapters for catalog tables containing harmonic amplitudes and phases."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
from numpy.typing import NDArray

from .harmonic_screen import HarmonicScreenResult, screen_harmonics


class HarmonicPhaseConvention(str, Enum):
    """Declared mappings from catalog amplitude/phase values to ``c_n``.

    Absolute conventions are lossless when the catalog phase is documented.
    Relative conventions are retained only for backwards-compatible exploratory
    work.  A generic list of relative phases is *not* sufficient to reconstruct
    complex coefficients unless its exact harmonic-order and epoch convention is
    independently verified.  Phase 06 therefore blocks relative conventions from
    evidence-bearing catalog screens by default.
    """

    COSINE_RELATIVE = "cosine_relative"
    SINE_RELATIVE = "sine_relative"
    COSINE_ABSOLUTE = "cosine_absolute"
    SINE_ABSOLUTE = "sine_absolute"


@dataclass(frozen=True, slots=True)
class CatalogHarmonicRecord:
    object_id: str
    amplitudes: NDArray[np.float64]
    phases: NDArray[np.float64]
    metadata: Mapping[str, str]

    @property
    def harmonic_count(self) -> int:
        return int(self.amplitudes.size)


@dataclass(frozen=True, slots=True)
class CatalogScreenRecord:
    object_id: str
    convention: HarmonicPhaseConvention
    result: HarmonicScreenResult
    metadata: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "object_id": self.object_id,
            "convention": self.convention.value,
            **self.result.as_dict(include_coefficients=False),
            "metadata": dict(self.metadata),
        }


def coefficients_from_amplitude_phase(
    amplitudes: Iterable[float],
    phases: Iterable[float],
    *,
    convention: HarmonicPhaseConvention | str,
    allow_unsafe_relative: bool = False,
) -> NDArray[np.complex128]:
    amplitude = np.asarray(tuple(amplitudes), dtype=np.float64).reshape(-1)
    phase = np.asarray(tuple(phases), dtype=np.float64).reshape(-1)
    if amplitude.size < 1 or amplitude.size != phase.size:
        raise ValueError("amplitudes and phases must have the same non-zero length")
    if not np.all(np.isfinite(amplitude)) or np.any(amplitude < 0.0):
        raise ValueError("amplitudes must be finite and non-negative")
    if not np.all(np.isfinite(phase)):
        raise ValueError("phases must be finite")
    active = HarmonicPhaseConvention(convention)
    if active in {
        HarmonicPhaseConvention.COSINE_RELATIVE,
        HarmonicPhaseConvention.SINE_RELATIVE,
    } and not allow_unsafe_relative:
        raise ValueError(
            "relative phase values do not uniquely determine complex coefficients; "
            "use phase_convention.audit_legacy_phase_summary or explicitly set "
            "allow_unsafe_relative=True for non-evidentiary exploration"
        )
    phase_shift = 0.0
    if active in {
        HarmonicPhaseConvention.SINE_RELATIVE,
        HarmonicPhaseConvention.SINE_ABSOLUTE,
    }:
        phase_shift = -math.pi / 2.0
    # A*cos(n theta + phi) has positive complex coefficient A/2*exp(i phi).
    return 0.5 * amplitude * np.exp(1j * (phase + phase_shift))


def read_feature_catalog(
    path: str | Path,
    *,
    object_column: str = "LC",
    amplitude_prefix: str = "freq1_harmonics_amplitude_",
    phase_prefix: str = "freq1_harmonics_rel_phase_",
    harmonics: int = 4,
) -> list[CatalogHarmonicRecord]:
    if harmonics < 1:
        raise ValueError("harmonics must be positive")
    source = Path(path)
    records: list[CatalogHarmonicRecord] = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {object_column}
        required.update(f"{amplitude_prefix}{index}" for index in range(harmonics))
        required.update(f"{phase_prefix}{index}" for index in range(harmonics))
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"catalog missing columns: {sorted(missing)}")
        for row in reader:
            object_id = str(row[object_column]).strip()
            if not object_id:
                raise ValueError("catalog contains an empty object identifier")
            amplitudes = np.asarray(
                [float(row[f"{amplitude_prefix}{index}"]) for index in range(harmonics)],
                dtype=np.float64,
            )
            phases = np.asarray(
                [float(row[f"{phase_prefix}{index}"]) for index in range(harmonics)],
                dtype=np.float64,
            )
            metadata = {
                key: value
                for key, value in row.items()
                if key not in required and value is not None
            }
            records.append(
                CatalogHarmonicRecord(
                    object_id=object_id,
                    amplitudes=amplitudes,
                    phases=phases,
                    metadata=metadata,
                )
            )
    if not records:
        raise ValueError("catalog contains no records")
    return records


def screen_feature_catalog(
    records: Iterable[CatalogHarmonicRecord],
    *,
    convention: HarmonicPhaseConvention | str,
    fit_harmonics: int = 4,
    allow_unsafe_relative: bool = False,
) -> list[CatalogScreenRecord]:
    active = HarmonicPhaseConvention(convention)
    results: list[CatalogScreenRecord] = []
    for record in records:
        coefficients = coefficients_from_amplitude_phase(
            record.amplitudes,
            record.phases,
            convention=active,
            allow_unsafe_relative=allow_unsafe_relative,
        )
        results.append(
            CatalogScreenRecord(
                object_id=record.object_id,
                convention=active,
                result=screen_harmonics(
                    coefficients, fit_harmonics=fit_harmonics
                ),
                metadata=record.metadata,
            )
        )
    return results
