import numpy as np
import pytest

from derd.kernels import (
    fit_periodic_kernel_ridge,
    periodic_squared_exponential_kernel,
    predict_periodic_kernel,
    select_periodic_kernel_ridge,
)


def _signal(n=24):
    phase = np.linspace(0.0, 1.0, n, endpoint=False)
    value = 0.5 + 0.3 * np.cos(2.0 * np.pi * phase) + 0.1 * np.sin(4.0 * np.pi * phase)
    return phase, value


def test_periodic_kernel_is_symmetric_and_periodic():
    phase, _ = _signal(10)
    kernel = periodic_squared_exponential_kernel(phase, phase, length_scale=0.5)
    shifted = periodic_squared_exponential_kernel(phase + 1.0, phase, length_scale=0.5)
    assert np.allclose(kernel, kernel.T)
    assert np.allclose(kernel, shifted)
    assert np.allclose(np.diag(kernel), 1.0)


def test_periodic_kernel_fit_predicts_training_signal():
    phase, value = _signal(24)
    fit = fit_periodic_kernel_ridge(phase, value, length_scale=0.7, ridge=1.0e-4)
    prediction = predict_periodic_kernel(phase, fit)
    assert np.sqrt(np.mean((prediction - value) ** 2)) < 0.01
    assert fit.condition_number > 1.0
    assert 0.0 < fit.effective_parameters <= phase.size


def test_periodic_kernel_prediction_wraps_phase():
    phase, value = _signal(20)
    fit = fit_periodic_kernel_ridge(phase, value, length_scale=0.5, ridge=1.0e-3)
    assert np.allclose(
        predict_periodic_kernel(np.array([0.1, 0.7]), fit),
        predict_periodic_kernel(np.array([1.1, -0.3]), fit),
    )


def test_periodic_kernel_selection_is_deterministic():
    phase, value = _signal(20)
    kwargs = dict(
        length_scales=(0.3, 0.7),
        ridges=(1.0e-3, 1.0e-2),
        folds=4,
        label="selection",
        seed=11,
    )
    first = select_periodic_kernel_ridge(phase, value, **kwargs)
    second = select_periodic_kernel_ridge(phase, value, **kwargs)
    assert first.selected_length_scale == second.selected_length_scale
    assert first.selected_ridge == second.selected_ridge
    assert first.cross_validated_weighted_rmse == second.cross_validated_weighted_rmse
    assert len(first.candidates) == 4


def test_periodic_kernel_selection_rejects_constant_target():
    phase = np.linspace(0.0, 1.0, 12, endpoint=False)
    with pytest.raises(ValueError, match="non-constant"):
        select_periodic_kernel_ridge(phase, np.ones_like(phase), folds=3)


@pytest.mark.parametrize("length_scale,ridge", [(0.0, 0.1), (0.5, 0.0), (-1.0, 0.1)])
def test_periodic_kernel_rejects_nonpositive_hyperparameters(length_scale, ridge):
    phase, value = _signal(8)
    with pytest.raises(ValueError):
        fit_periodic_kernel_ridge(phase, value, length_scale=length_scale, ridge=ridge)
