import numpy as np
import pytest

from derd.normalization import (
    DegenerateNormalizationError,
    minmax_normalize,
    positive_affine_invariance_error,
)


def test_positive_affine_normalization_invariance() -> None:
    rng = np.random.default_rng(20260807)
    values = rng.normal(size=2048)
    error = positive_affine_invariance_error(values, scale=7.3, offset=-42.0)
    assert error < 2e-14


def test_reference_values_control_scaling() -> None:
    reference = np.array([-2.0, 0.0, 3.0])
    sample = np.array([0.0, 1.0])
    result, stats = minmax_normalize(sample, reference_values=reference)
    np.testing.assert_allclose(result, [0.4, 0.6])
    assert stats.minimum == -2.0
    assert stats.maximum == 3.0


def test_degenerate_normalization_is_explicit() -> None:
    with pytest.raises(DegenerateNormalizationError):
        minmax_normalize(np.ones(10))
