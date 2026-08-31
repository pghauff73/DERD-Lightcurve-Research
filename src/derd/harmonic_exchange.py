"""Lossless exchange schema for harmonic evidence.

The schema stores signed sine and cosine coefficients, a fundamental frequency,
and the reference epoch.  Those fields are sufficient to reconstruct the
canonical positive-frequency complex coefficients without a quadrant or epoch
ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import NDArray

from .phase_convention import canonical_coefficients_from_sine_cosine

SCHEMA_VERSION = "DERD-HARMONIC-EXCHANGE-1.0"
CANONICAL_SERIES = "y=c0+sum(c_n*exp(i*2*pi*n*f*(t-t0))+conjugate)"


@dataclass(frozen=True, slots=True)
class CanonicalHarmonicSeries:
    object_id: str
    fundamental_frequency: float
    reference_epoch: float
    time_unit: str
    value_unit: str
    sine_coefficients: NDArray[np.float64]
    cosine_coefficients: NDArray[np.float64]
    source_locator: str
    source_sha256: str
    intercept: float = 0.0
    coefficient_covariance: NDArray[np.float64] | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.object_id.strip():
            raise ValueError("object_id must be non-empty")
        if not math.isfinite(self.fundamental_frequency) or self.fundamental_frequency <= 0.0:
            raise ValueError("fundamental_frequency must be finite and positive")
        if not math.isfinite(self.reference_epoch):
            raise ValueError("reference_epoch must be finite")
        if not self.time_unit.strip() or not self.value_unit.strip():
            raise ValueError("time_unit and value_unit must be non-empty")
        if not self.source_locator.strip():
            raise ValueError("source_locator must be non-empty")
        if not math.isfinite(self.intercept):
            raise ValueError("intercept must be finite")
        digest = self.source_sha256.lower().strip()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("source_sha256 must be a 64-character hexadecimal digest")
        sine = np.asarray(self.sine_coefficients, dtype=np.float64).reshape(-1)
        cosine = np.asarray(self.cosine_coefficients, dtype=np.float64).reshape(-1)
        if sine.size < 1 or sine.size != cosine.size:
            raise ValueError("sine and cosine coefficients must have equal non-zero length")
        if not np.all(np.isfinite(sine)) or not np.all(np.isfinite(cosine)):
            raise ValueError("harmonic coefficients must be finite")
        covariance = self.coefficient_covariance
        if covariance is not None:
            covariance = np.asarray(covariance, dtype=np.float64)
            expected = 2 * sine.size
            if covariance.shape != (expected, expected):
                raise ValueError(f"coefficient_covariance must have shape {(expected, expected)}")
            if not np.all(np.isfinite(covariance)):
                raise ValueError("coefficient_covariance must be finite")
            if not np.allclose(covariance, covariance.T, atol=1.0e-12, rtol=1.0e-10):
                raise ValueError("coefficient_covariance must be symmetric")
        object.__setattr__(self, "sine_coefficients", sine)
        object.__setattr__(self, "cosine_coefficients", cosine)
        object.__setattr__(self, "coefficient_covariance", covariance)
        object.__setattr__(self, "source_sha256", digest)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def harmonic_count(self) -> int:
        return int(self.sine_coefficients.size)

    @property
    def coefficient_covariance_order(self) -> tuple[str, ...]:
        return tuple(
            [f"sin_{index}" for index in range(1, self.harmonic_count + 1)]
            + [f"cos_{index}" for index in range(1, self.harmonic_count + 1)]
        )

    @property
    def complex_coefficients(self) -> NDArray[np.complex128]:
        return canonical_coefficients_from_sine_cosine(
            self.sine_coefficients, self.cosine_coefficients
        )

    @property
    def recurrence_forecast_harmonics(self) -> int:
        return max(0, self.harmonic_count - 4)

    @property
    def qualifies_for_two_harmonic_forecast(self) -> bool:
        return self.harmonic_count >= 6

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "canonical_series": CANONICAL_SERIES,
            "object_id": self.object_id,
            "fundamental_frequency": self.fundamental_frequency,
            "reference_epoch": self.reference_epoch,
            "time_unit": self.time_unit,
            "value_unit": self.value_unit,
            "harmonic_count": self.harmonic_count,
            "intercept": float(self.intercept),
            "sine_coefficients": [float(value) for value in self.sine_coefficients],
            "cosine_coefficients": [float(value) for value in self.cosine_coefficients],
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "metadata": dict(self.metadata or {}),
        }
        if self.coefficient_covariance is not None:
            payload["coefficient_covariance_order"] = list(
                self.coefficient_covariance_order
            )
            payload["coefficient_covariance_dimension"] = int(
                self.coefficient_covariance.shape[0]
            )
            payload["coefficient_covariance"] = self.coefficient_covariance.tolist()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanonicalHarmonicSeries":
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported harmonic exchange schema version")
        return cls(
            object_id=str(payload["object_id"]),
            fundamental_frequency=float(payload["fundamental_frequency"]),
            reference_epoch=float(payload["reference_epoch"]),
            time_unit=str(payload["time_unit"]),
            value_unit=str(payload["value_unit"]),
            sine_coefficients=np.asarray(payload["sine_coefficients"], dtype=np.float64),
            cosine_coefficients=np.asarray(payload["cosine_coefficients"], dtype=np.float64),
            source_locator=str(payload["source_locator"]),
            source_sha256=str(payload["source_sha256"]),
            intercept=float(
                payload.get(
                    "intercept",
                    (payload.get("metadata") or {}).get("intercept", 0.0),
                )
            ),
            coefficient_covariance=(
                None
                if payload.get("coefficient_covariance") is None
                else np.asarray(payload["coefficient_covariance"], dtype=np.float64)
            ),
            metadata=dict(payload.get("metadata") or {}),
        )


def canonical_json_bytes(series: CanonicalHarmonicSeries) -> bytes:
    return (
        json.dumps(series.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def record_sha256(series: CanonicalHarmonicSeries) -> str:
    return hashlib.sha256(canonical_json_bytes(series)).hexdigest()


def write_harmonic_exchange(path: str | Path, series: CanonicalHarmonicSeries) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(series)
    target.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_harmonic_exchange(path: str | Path) -> CanonicalHarmonicSeries:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("harmonic exchange document must contain an object")
    return CanonicalHarmonicSeries.from_dict(payload)


def source_digest_from_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def covariance_from_standard_errors(
    sine_standard_errors: Iterable[float],
    cosine_standard_errors: Iterable[float],
) -> NDArray[np.float64]:
    sine = np.asarray(tuple(sine_standard_errors), dtype=np.float64).reshape(-1)
    cosine = np.asarray(tuple(cosine_standard_errors), dtype=np.float64).reshape(-1)
    if sine.size < 1 or sine.size != cosine.size:
        raise ValueError("standard-error arrays must have equal non-zero length")
    if not np.all(np.isfinite(sine)) or not np.all(np.isfinite(cosine)):
        raise ValueError("standard errors must be finite")
    if np.any(sine < 0.0) or np.any(cosine < 0.0):
        raise ValueError("standard errors must be non-negative")
    variances = np.concatenate((np.square(sine), np.square(cosine)))
    return np.diag(variances)
