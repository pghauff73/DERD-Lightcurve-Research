from pathlib import Path

import numpy as np

from derd.harmonic_extraction import (
    draw_complex_coefficients,
    fit_weighted_harmonic_exchange,
    git_blob_sha1_bytes,
    phase_coverage_statistics,
    refine_period_by_weighted_harmonics,
)
from derd.lightcurve import LightCurve, ValueDomain


def synthetic_fourier_curve(*, period: float = 2.75, count: int = 240) -> tuple[LightCurve, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(71)
    time = np.sort(rng.uniform(0.0, 900.0, count))
    phase = np.mod(time / period, 1.0)
    sine = np.asarray([0.12, -0.045, 0.021, 0.012, -0.006, 0.003])
    cosine = np.asarray([-0.03, 0.026, -0.012, 0.007, 0.004, -0.002])
    values = np.full(count, 1.3)
    for harmonic in range(1, 7):
        angle = 2.0 * np.pi * harmonic * phase
        values += sine[harmonic - 1] * np.sin(angle)
        values += cosine[harmonic - 1] * np.cos(angle)
    curve = LightCurve(
        star_id="SYNTHETIC-PHASE07",
        time=time,
        value=values,
        error=np.full(count, 0.01),
        band="I",
        domain=ValueDomain.FLUX,
        metadata={"local_sha256": "a" * 64, "source_locator": "unit-test"},
    )
    return curve, sine, cosine


def test_weighted_extraction_recovers_signed_coefficients() -> None:
    curve, sine, cosine = synthetic_fourier_curve()
    result = fit_weighted_harmonic_exchange(
        curve,
        period_days=2.75,
        order=6,
        reference_epoch=0.0,
        ridge=0.0,
        covariance_estimator="photometric",
    )
    np.testing.assert_allclose(result.series.sine_coefficients, sine, atol=2e-13)
    np.testing.assert_allclose(result.series.cosine_coefficients, cosine, atol=2e-13)
    assert result.series.qualifies_for_two_harmonic_forecast
    assert result.design_condition_number < 3.0
    assert result.phase_coverage["occupied_bins"] == 12
    assert result.series.coefficient_covariance is not None
    assert result.series.coefficient_covariance.shape == (12, 12)


def test_hc3_covariance_is_symmetric_psd() -> None:
    curve, _, _ = synthetic_fourier_curve()
    rng = np.random.default_rng(72)
    noisy = LightCurve(
        star_id=curve.star_id,
        time=curve.time,
        value=curve.value + rng.normal(0.0, curve.error),
        error=curve.error,
        band=curve.band,
        domain=curve.domain,
        metadata=curve.metadata,
    )
    result = fit_weighted_harmonic_exchange(
        noisy,
        period_days=2.75,
        order=6,
        reference_epoch=0.0,
        covariance_estimator="hc3",
    )
    covariance = result.series.coefficient_covariance
    assert covariance is not None
    np.testing.assert_allclose(covariance, covariance.T, atol=1e-14)
    assert float(np.min(np.linalg.eigvalsh(covariance))) >= -1e-14
    assert np.all(result.harmonic_wald_snr >= 0.0)
    draws = draw_complex_coefficients(result.series, draws=16, seed=9)
    assert draws.shape == (16, 6)


def test_period_profile_recovers_injected_period() -> None:
    curve, _, _ = synthetic_fourier_curve(period=2.75)
    profile = refine_period_by_weighted_harmonics(
        curve,
        2.7504,
        order=6,
        relative_span=5e-4,
        grid_count=101,
        reference_epoch=0.0,
    )
    assert profile.resolved
    assert abs(profile.best_period_days - 2.75) < 2e-6
    assert profile.best_chi_square < profile.catalog_chi_square


def test_git_blob_hash_matches_git_definition() -> None:
    assert git_blob_sha1_bytes(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_phase_coverage_reports_circular_gap() -> None:
    report = phase_coverage_statistics(np.linspace(0.0, 1.0, 25, endpoint=False), bins=12)
    assert report["occupied_bins"] == 12
    assert report["maximum_circular_phase_gap"] < 0.05
