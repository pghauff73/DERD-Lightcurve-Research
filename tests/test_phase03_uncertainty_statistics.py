import numpy as np
import pytest

from derd.statistics import paired_bootstrap_comparison
from derd.uncertainty import calibrate_symmetric_interval, interval_metrics, prediction_interval


def test_absolute_interval_uses_finite_sample_rank():
    observed = np.arange(9, dtype=float)
    predicted = observed + np.linspace(-0.4, 0.4, 9)
    calibration = calibrate_symmetric_interval(observed, predicted, nominal_coverage=0.8)
    assert calibration.finite_sample_rank == 8
    assert calibration.calibration_count == 9
    assert not calibration.standardized


def test_standardized_interval_scales_width():
    observed = np.array([0.0, 1.0, 2.0, 3.0])
    predicted = np.array([0.1, 0.9, 2.2, 2.8])
    scale = np.array([0.1, 0.2, 0.3, 0.4])
    calibration = calibrate_symmetric_interval(
        observed, predicted, nominal_coverage=0.75, scale=scale
    )
    lower, upper = prediction_interval(np.array([1.0, 1.0]), calibration, scale=np.array([0.1, 0.4]))
    assert (upper[1] - lower[1]) > (upper[0] - lower[0])


def test_interval_metrics_count_misses_and_score():
    observed = np.array([0.0, 1.0, 2.0])
    lower = np.array([-0.1, 0.8, 2.1])
    upper = np.array([0.1, 1.2, 2.3])
    result = interval_metrics(observed, lower, upper, nominal_coverage=0.9)
    assert result.empirical_coverage == pytest.approx(2.0 / 3.0)
    assert result.miss_below_count == 1
    assert result.miss_above_count == 0
    assert result.interval_score > result.mean_width


def test_prediction_interval_requires_scale_only_when_standardized():
    calibration = calibrate_symmetric_interval([0, 1, 2], [0.1, 0.9, 2.1], scale=[1, 1, 1])
    with pytest.raises(ValueError, match="required"):
        prediction_interval([0.0], calibration)
    absolute = calibrate_symmetric_interval([0, 1, 2], [0.1, 0.9, 2.1])
    with pytest.raises(ValueError, match="omitted"):
        prediction_interval([0.0], absolute, scale=[1.0])


def test_paired_bootstrap_is_deterministic_and_interpretable():
    first = np.array([0.10, 0.11, 0.12, 0.13])
    second = np.array([0.15, 0.16, 0.17, 0.18])
    a = paired_bootstrap_comparison(first, second, repetitions=1000, seed=5)
    b = paired_bootstrap_comparison(first, second, repetitions=1000, seed=5)
    assert a.as_dict() == b.as_dict()
    assert a.first_model_win_count == 4
    assert a.mean_difference < 0.0
    assert a.noninferiority_pass_mean


def test_paired_bootstrap_ties_have_unit_sign_test_p_value():
    result = paired_bootstrap_comparison([1.0, 2.0], [1.0, 2.0], repetitions=100)
    assert result.exact_sign_test_p_value == 1.0
    assert result.first_model_win_count == 0


@pytest.mark.parametrize(
    "first,second,repetitions",
    [([1.0], [1.0], 100), ([1.0, 2.0], [1.0], 100), ([1.0, 2.0], [1.0, 2.0], 10)],
)
def test_paired_bootstrap_rejects_invalid_inputs(first, second, repetitions):
    with pytest.raises(ValueError):
        paired_bootstrap_comparison(first, second, repetitions=repetitions)
