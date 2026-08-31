import numpy as np

from derd.kepler import normalized_radius, solve_eccentric_anomaly


def test_kepler_solver_residual_is_small_across_eccentricity_range() -> None:
    mean_anomaly = np.linspace(-4.0 * np.pi, 6.0 * np.pi, 2001)
    for eccentricity in [0.0, 0.3, 0.8, 0.95, 0.999]:
        eccentric_anomaly = solve_eccentric_anomaly(mean_anomaly, eccentricity)
        residual = eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly) - mean_anomaly
        assert float(np.max(np.abs(residual))) < 3e-12


def test_kepler_normalized_radius_has_expected_extrema() -> None:
    phase = np.array([0.0, 0.5, 1.0])
    for eccentricity in [0.0, 0.3, 0.9, 0.999]:
        values = normalized_radius(phase, eccentricity)
        np.testing.assert_allclose(values, [0.0, 1.0, 0.0], atol=4e-13)


def test_circular_kepler_limit_matches_cosine_shape() -> None:
    phase = np.linspace(0.0, 1.0, 64, endpoint=False)
    expected = 0.5 * (1.0 - np.cos(2.0 * np.pi * phase))
    np.testing.assert_allclose(normalized_radius(phase, 0.0), expected)
