import numpy as np

from derd.geometric import normalized_radius, radius_over_semimajor_axis
from derd.normalization import minmax_normalize


def test_geometric_normalized_radius_has_exact_endpoints() -> None:
    phase = np.array([0.0, 0.5, 1.0])
    for eccentricity in [0.0, 0.1, 0.7, 0.99]:
        values = normalized_radius(phase, eccentricity)
        np.testing.assert_allclose(values, [0.0, 1.0, 0.0], atol=2e-14)


def test_geometric_closed_form_matches_raw_minmax_normalization() -> None:
    phase = np.linspace(0.0, 1.0, 4096, endpoint=False)
    for eccentricity in [0.05, 0.3, 0.8]:
        raw = radius_over_semimajor_axis(phase, eccentricity)
        sampled, _ = minmax_normalize(raw)
        analytic = normalized_radius(phase, eccentricity)
        np.testing.assert_allclose(analytic, sampled, atol=2e-14, rtol=2e-14)


def test_circular_limit_is_non_degenerate_shape_limit() -> None:
    phase = np.linspace(0.0, 1.0, 32, endpoint=False)
    expected = 0.5 * (1.0 - np.cos(2.0 * np.pi * phase))
    np.testing.assert_allclose(normalized_radius(phase, 0.0), expected)
