import csv
import math
from pathlib import Path

import numpy as np
import pytest

from derd.catalog_harmonics import (
    HarmonicPhaseConvention,
    coefficients_from_amplitude_phase,
    read_feature_catalog,
    screen_feature_catalog,
)
from derd.harmonic_screen import (
    fit_complex_fourier,
    fit_second_order_recurrence,
    predict_from_recurrence,
    rank_screen_results,
    screen_harmonics,
)
from derd.parameters import DERDParameters
from derd.spectral import raw_derd_complex_coefficients


def observed_coefficients(
    parameters: DERDParameters,
    *,
    harmonics: int = 8,
    epoch: float = 0.17,
    scale: float = -1.7,
) -> np.ndarray:
    base = raw_derd_complex_coefficients(
        parameters, maximum_harmonic=harmonics
    )[1:]
    n = np.arange(1, harmonics + 1)
    return scale * base * np.exp(1j * 2.0 * np.pi * n * epoch)


def test_exact_derd_sequence_scores_near_zero_and_forecasts() -> None:
    parameters = DERDParameters(0.24, 0.73, 0.62, 0.31)
    coefficients = observed_coefficients(parameters)
    result = screen_harmonics(coefficients, fit_harmonics=4)
    assert result.evidence_level == "HARMONIC_FORECAST"
    assert result.score < 2e-10
    assert result.candidate.fit_residual < 2e-11
    assert result.candidate.forecast_residual is not None
    assert result.candidate.forecast_residual < 2e-10
    assert result.candidate.opposite_sign_residues
    assert not result.flags


def test_algebraic_recovery_is_correct_up_to_root_assignment() -> None:
    expected = DERDParameters(0.31, 0.77, 0.48, 0.23)
    result = screen_harmonics(
        observed_coefficients(expected, epoch=0.43, scale=2.2), fit_harmonics=4
    )
    recovered = result.candidate.parameters
    np.testing.assert_allclose(recovered.e1, expected.e1, atol=2e-11)
    np.testing.assert_allclose(recovered.e2, expected.e2, atol=2e-11)
    np.testing.assert_allclose(recovered.amplitude_ratio, expected.amplitude_ratio, atol=3e-10)
    phase_distance = min(
        abs(recovered.phase_ratio - expected.phase_ratio),
        1.0 - abs(recovered.phase_ratio - expected.phase_ratio),
    )
    assert phase_distance < 2e-11


def test_epoch_and_real_scale_do_not_change_shape_score() -> None:
    parameters = DERDParameters(0.42, 0.69, 1.3, 0.37)
    first = screen_harmonics(
        observed_coefficients(parameters, epoch=0.0, scale=1.0)
    )
    second = screen_harmonics(
        observed_coefficients(parameters, epoch=0.817, scale=-4.2)
    )
    assert first.score < 1e-9
    assert second.score < 1e-9


def test_phase_scrambling_breaks_derd_constraints() -> None:
    rng = np.random.default_rng(7)
    parameters = DERDParameters(0.28, 0.81, 0.55, 0.29)
    coefficients = observed_coefficients(parameters)
    scrambled = np.abs(coefficients) * np.exp(1j * rng.uniform(-math.pi, math.pi, coefficients.size))
    exact = screen_harmonics(coefficients)
    null = screen_harmonics(scrambled)
    assert null.score > exact.score + 0.25


def test_recurrence_predictor_reconstructs_exact_sequence() -> None:
    coefficients = observed_coefficients(DERDParameters(0.2, 0.6, 0.7, 0.4))
    recurrence = fit_second_order_recurrence(coefficients, fit_harmonics=6)
    prediction = predict_from_recurrence(
        coefficients[0],
        coefficients[1],
        sum_roots=recurrence.sum_roots,
        product_roots=recurrence.product_roots,
        harmonics=coefficients.size,
    )
    np.testing.assert_allclose(prediction, coefficients, atol=3e-13, rtol=3e-12)


def test_weighted_fourier_fit_recovers_known_complex_coefficients() -> None:
    rng = np.random.default_rng(10)
    phase = np.sort(rng.random(80))
    expected = np.asarray(
        [0.0 + 0.0j, 0.12 - 0.03j, -0.04 + 0.02j, 0.01 - 0.015j]
    )
    values = np.full(phase.size, 1.7)
    for harmonic in range(1, expected.size):
        values += 2.0 * np.real(expected[harmonic] * np.exp(1j * 2.0 * np.pi * harmonic * phase))
    errors = np.linspace(0.01, 0.03, phase.size)
    fit = fit_complex_fourier(phase, values, order=3, errors=errors, ridge=0.0)
    np.testing.assert_allclose(fit.coefficients[0].real, 1.7, atol=2e-14)
    np.testing.assert_allclose(fit.coefficients[1:], expected[1:], atol=2e-14)
    assert fit.residual_rmse < 2e-14


def test_fourier_fit_validates_dimension() -> None:
    with pytest.raises(ValueError):
        fit_complex_fourier([0, 0.1, 0.2], [1, 2, 3], order=2)


def test_four_harmonic_catalog_is_shape_only() -> None:
    coefficients = observed_coefficients(
        DERDParameters(0.3, 0.7, 0.8, 0.2), harmonics=4
    )
    result = screen_harmonics(coefficients)
    assert result.evidence_level == "SHAPE_ONLY"
    assert "INSUFFICIENT_HARMONIC_FORECAST" in result.flags


def test_catalog_cosine_conversion() -> None:
    amplitudes = [2.0, 1.0, 0.5, 0.25]
    phases = [0.0, math.pi / 2.0, math.pi, -math.pi / 2.0]
    coefficients = coefficients_from_amplitude_phase(
        amplitudes,
        phases,
        convention=HarmonicPhaseConvention.COSINE_RELATIVE,
        allow_unsafe_relative=True,
    )
    expected = 0.5 * np.asarray(amplitudes) * np.exp(1j * np.asarray(phases))
    np.testing.assert_allclose(coefficients, expected)


def test_catalog_sine_conversion_applies_quarter_turn() -> None:
    coefficients = coefficients_from_amplitude_phase(
        [2.0, 1.0, 0.5, 0.25],
        [0.0, 0.0, 0.0, 0.0],
        convention="sine_relative",
        allow_unsafe_relative=True,
    )
    np.testing.assert_allclose(coefficients.real, 0.0, atol=2e-16)
    assert np.all(coefficients.imag < 0.0)


def test_relative_catalog_conversion_is_blocked_by_default() -> None:
    with pytest.raises(ValueError, match="do not uniquely determine"):
        coefficients_from_amplitude_phase(
            [1.0, 0.5, 0.25, 0.125],
            [0.0, 0.1, 0.2, 0.3],
            convention="sine_relative",
        )


def test_feature_catalog_reader_and_screen(tmp_path: Path) -> None:
    parameters = DERDParameters(0.35, 0.72, 0.61, 0.27)
    coefficients = observed_coefficients(parameters, harmonics=4, epoch=0.0, scale=1.0)
    amplitudes = 2.0 * np.abs(coefficients)
    phases = np.angle(coefficients)
    path = tmp_path / "features.csv"
    fields = ["LC"]
    fields += [f"freq1_harmonics_amplitude_{i}" for i in range(4)]
    fields += [f"freq1_harmonics_rel_phase_{i}" for i in range(4)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        row = {"LC": "SYNTHETIC-001"}
        row.update({f"freq1_harmonics_amplitude_{i}": amplitudes[i] for i in range(4)})
        row.update({f"freq1_harmonics_rel_phase_{i}": phases[i] for i in range(4)})
        writer.writerow(row)
    records = read_feature_catalog(path)
    screened = screen_feature_catalog(
        records, convention="cosine_relative", allow_unsafe_relative=True
    )
    assert len(screened) == 1
    assert screened[0].object_id == "SYNTHETIC-001"
    assert screened[0].result.score < 2e-9


def test_rank_screen_results_is_deterministic() -> None:
    exact = screen_harmonics(
        observed_coefficients(DERDParameters(0.2, 0.6, 0.7, 0.4))
    )
    rng = np.random.default_rng(3)
    null_coefficients = np.exp(-0.4 * np.arange(8)) * np.exp(
        1j * rng.uniform(-math.pi, math.pi, 8)
    )
    null = screen_harmonics(null_coefficients)
    ranked = rank_screen_results([("null", null), ("exact", exact)])
    assert [item[1] for item in ranked] == ["exact", "null"]
