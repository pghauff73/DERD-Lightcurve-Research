import numpy as np

from derd.geometric import radius_over_semimajor_axis
from derd.model import OutputNormalization, raw_waveform, waveform
from derd.parameters import DERDParameters
from derd.spectral import (
    eccentricity_from_q,
    q_from_eccentricity,
    radius_over_semimajor_axis_series,
    raw_derd_complex_coefficients,
    recurrence_residuals,
    recurrence_roots,
)


def test_q_eccentricity_round_trip() -> None:
    for eccentricity in [0.0, 0.01, 0.3, 0.7, 0.99]:
        recovered = eccentricity_from_q(q_from_eccentricity(eccentricity))
        np.testing.assert_allclose(recovered, eccentricity, atol=2e-15, rtol=0.0)



def test_complex_coefficients_are_stable_near_circular_limit() -> None:
    from derd.spectral import normalized_radius_complex_coefficients

    coefficients = normalized_radius_complex_coefficients(1e-14, maximum_harmonic=4)
    np.testing.assert_allclose(coefficients[0], 0.5, atol=5e-15)
    np.testing.assert_allclose(coefficients[1], -0.25, atol=5e-15)
    assert abs(coefficients[2]) < 2e-15

def test_radius_fourier_series_matches_closed_form() -> None:
    phase = np.linspace(0.0, 1.0, 2048, endpoint=False)
    exact = radius_over_semimajor_axis(phase, 0.7)
    series = radius_over_semimajor_axis_series(phase, 0.7, terms=80)
    np.testing.assert_allclose(series, exact, atol=2e-13, rtol=2e-13)


def test_analytic_raw_coefficients_match_numerical_fft() -> None:
    parameters = DERDParameters(0.24, 0.73, 0.62, 0.31)
    sample_count = 32768
    phase = np.linspace(0.0, 1.0, sample_count, endpoint=False)
    raw = raw_waveform(phase, parameters, time_law="geometric")
    numerical = np.fft.fft(raw) / sample_count
    analytic = raw_derd_complex_coefficients(parameters, maximum_harmonic=12)
    np.testing.assert_allclose(numerical[:13], analytic, atol=3e-13, rtol=3e-12)


def test_geometric_harmonics_satisfy_second_order_recurrence() -> None:
    parameters = DERDParameters(0.24, 0.73, 0.62, 0.31)
    coefficients = raw_derd_complex_coefficients(parameters, maximum_harmonic=20)
    z1, z2 = recurrence_roots(parameters)
    residual = recurrence_residuals(coefficients, z1=z1, z2=z2, first_harmonic=1)
    assert float(np.max(np.abs(residual))) < 5e-17


def test_final_minmax_scaling_preserves_nonzero_harmonic_recurrence() -> None:
    parameters = DERDParameters(0.24, 0.73, 0.62, 0.31)
    sample_count = 65536
    phase = np.linspace(0.0, 1.0, sample_count, endpoint=False)
    values = waveform(
        phase,
        parameters,
        time_law="geometric",
        output_normalization=OutputNormalization.CANONICAL,
        normalization_grid_size=sample_count,
    )
    coefficients = np.fft.fft(values)[:20] / sample_count
    z1, z2 = recurrence_roots(parameters)
    residual = recurrence_residuals(coefficients, z1=z1, z2=z2, first_harmonic=1)
    assert float(np.max(np.abs(residual))) < 2e-13
