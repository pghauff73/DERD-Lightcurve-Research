"""Validated light-curve objects and photometric-domain conversions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


class ValueDomain(str, Enum):
    """Physical representation carried by a light curve."""

    MAGNITUDE = "magnitude"
    FLUX = "flux"


@dataclass(frozen=True, slots=True)
class LightCurve:
    """Immutable, time-sorted single-band light curve.

    ``error`` is the one-sigma uncertainty in the same domain as ``value``.
    Metadata is copied into a read-only mapping so provenance cannot be changed
    accidentally after construction.
    """

    star_id: str
    time: NDArray[np.float64]
    value: NDArray[np.float64]
    error: NDArray[np.float64]
    band: str = "I"
    domain: ValueDomain = ValueDomain.MAGNITUDE
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        star_id = str(self.star_id).strip()
        band = str(self.band).strip()
        if not star_id:
            raise ValueError("star_id must not be empty")
        if not band:
            raise ValueError("band must not be empty")

        time = np.asarray(self.time, dtype=np.float64).reshape(-1)
        value = np.asarray(self.value, dtype=np.float64).reshape(-1)
        error = np.asarray(self.error, dtype=np.float64).reshape(-1)
        if time.size == 0 or time.size != value.size or time.size != error.size:
            raise ValueError("time, value, and error must have the same non-zero size")
        if not np.all(np.isfinite(time)):
            raise ValueError("time contains non-finite values")
        if not np.all(np.isfinite(value)):
            raise ValueError("value contains non-finite values")
        if not np.all(np.isfinite(error)) or np.any(error <= 0.0):
            raise ValueError("error values must be finite and strictly positive")

        order = np.argsort(time, kind="mergesort")
        time = np.array(time[order], dtype=np.float64, copy=True)
        value = np.array(value[order], dtype=np.float64, copy=True)
        error = np.array(error[order], dtype=np.float64, copy=True)
        time.setflags(write=False)
        value.setflags(write=False)
        error.setflags(write=False)

        object.__setattr__(self, "star_id", star_id)
        object.__setattr__(self, "band", band)
        object.__setattr__(self, "domain", ValueDomain(self.domain))
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "error", error)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def size(self) -> int:
        return int(self.time.size)

    def subset(self, selector: ArrayLike) -> "LightCurve":
        """Return a validated subset selected by indices or a Boolean mask."""

        raw = np.asarray(selector)
        if raw.dtype == np.bool_:
            mask = raw.reshape(-1)
            if mask.size != self.size:
                raise ValueError("Boolean selector must match light-curve size")
            indices = np.flatnonzero(mask)
        else:
            indices = np.asarray(selector, dtype=np.int64).reshape(-1)
            if np.any(indices < 0) or np.any(indices >= self.size):
                raise IndexError("subset index is outside the light curve")
        if indices.size == 0:
            raise ValueError("subset must contain at least one observation")
        return LightCurve(
            star_id=self.star_id,
            time=self.time[indices],
            value=self.value[indices],
            error=self.error[indices],
            band=self.band,
            domain=self.domain,
            metadata=self.metadata,
        )

    def to_relative_flux(self, reference_magnitude: float | None = None) -> "LightCurve":
        """Convert magnitudes to relative flux with propagated one-sigma errors.

        For magnitude ``m`` and reference ``m0``::

            F/F0 = 10**[-0.4 (m - m0)]
            sigma_F = (ln(10)/2.5) F sigma_m

        Existing flux-domain curves are returned unchanged.
        """

        if self.domain is ValueDomain.FLUX:
            return self
        m0 = float(np.median(self.value)) if reference_magnitude is None else float(reference_magnitude)
        if not np.isfinite(m0):
            raise ValueError("reference_magnitude must be finite")
        flux = np.power(10.0, -0.4 * (self.value - m0))
        flux_error = (np.log(10.0) / 2.5) * flux * self.error
        metadata = dict(self.metadata)
        metadata.update(
            {
                "magnitude_reference": m0,
                "conversion": "relative_flux=10**(-0.4*(m-m0))",
            }
        )
        return LightCurve(
            star_id=self.star_id,
            time=self.time,
            value=flux,
            error=flux_error,
            band=self.band,
            domain=ValueDomain.FLUX,
            metadata=metadata,
        )
