import hashlib
from pathlib import Path

import numpy as np
import pytest

from derd.harmonic_exchange import (
    CanonicalHarmonicSeries,
    covariance_from_standard_errors,
    read_harmonic_exchange,
    record_sha256,
    write_harmonic_exchange,
)


def example_series(harmonics: int = 6) -> CanonicalHarmonicSeries:
    covariance = covariance_from_standard_errors(
        np.full(harmonics, 0.01), np.full(harmonics, 0.02)
    )
    return CanonicalHarmonicSeries(
        object_id="SYNTHETIC-HEX-001",
        fundamental_frequency=11.3105,
        reference_epoch=2450000.0,
        time_unit="day",
        value_unit="relative_flux",
        sine_coefficients=np.linspace(0.1, 0.01, harmonics),
        cosine_coefficients=np.linspace(-0.05, 0.02, harmonics),
        coefficient_covariance=covariance,
        source_locator="sha256:test-source",
        source_sha256=hashlib.sha256(b"source").hexdigest(),
        intercept=1.234,
        metadata={"role": "unit-test"},
    )


def test_exchange_round_trip_is_byte_stable(tmp_path: Path) -> None:
    series = example_series()
    path = tmp_path / "harmonics.json"
    digest = write_harmonic_exchange(path, series)
    restored = read_harmonic_exchange(path)
    assert digest == record_sha256(series)
    assert record_sha256(restored) == digest
    np.testing.assert_allclose(restored.complex_coefficients, series.complex_coefficients)
    assert restored.intercept == pytest.approx(1.234)
    assert restored.coefficient_covariance_order[0] == "sin_1"
    assert restored.coefficient_covariance_order[-1] == f"cos_{series.harmonic_count}"
    assert restored.qualifies_for_two_harmonic_forecast
    assert restored.recurrence_forecast_harmonics == 2


def test_exchange_requires_signed_lossless_inputs() -> None:
    with pytest.raises(ValueError):
        CanonicalHarmonicSeries(
            object_id="bad",
            fundamental_frequency=1.0,
            reference_epoch=0.0,
            time_unit="day",
            value_unit="flux",
            sine_coefficients=np.ones(4),
            cosine_coefficients=np.ones(3),
            source_locator="x",
            source_sha256="0" * 64,
        )


def test_four_harmonic_exchange_is_not_two_forecast_ready() -> None:
    series = example_series(harmonics=4)
    assert not series.qualifies_for_two_harmonic_forecast
    assert series.recurrence_forecast_harmonics == 0
