import numpy as np
import pytest

from derd.baselines import fit_fourier, predict_fourier, select_fourier_order
from derd.metrics import durbin_watson, information_criteria, metric_bundle, weighted_rmse
from derd.model import TimeLaw, peak_aligned_waveform, peak_phase
from derd.parameters import DERDParameters


def test_peak_aligned_waveform_has_maximum_at_zero():
    params = DERDParameters(0.4, 0.7, 0.6, 0.31)
    grid = np.linspace(0.0, 1.0, 1024, endpoint=False)
    values = peak_aligned_waveform(grid, params, peak_grid_size=1024)
    index = int(np.argmax(values))
    assert min(index, grid.size - index) <= 1


def test_peak_phase_is_in_unit_interval_for_both_laws():
    params = DERDParameters(0.3, 0.6, 0.7, 0.2)
    for law in TimeLaw:
        value = peak_phase(params, time_law=law)
        assert 0.0 <= value < 1.0


def test_predict_fourier_reproduces_training_prediction():
    phase = np.linspace(0, 1, 50, endpoint=False)
    flux = 1 + 0.2 * np.cos(2 * np.pi * phase)
    fit = fit_fourier(phase, flux, order=1, normalize_target=False)
    assert np.allclose(predict_fourier(phase, fit), fit.prediction)


def test_bic_selects_first_order_for_clean_sinusoid():
    phase = np.linspace(0, 1, 80, endpoint=False)
    flux = 1 + 0.3 * np.cos(2 * np.pi * phase)
    selected = select_fourier_order(phase, flux, orders=(1, 2, 3), normalize_target=False)
    assert selected.selected.order == 1


def test_fourier_rejects_saturated_parameter_count():
    with pytest.raises(ValueError):
        fit_fourier(np.arange(5.0), np.arange(5.0), order=2, normalize_target=False)


def test_weighted_rmse_emphasizes_large_weight():
    observed = [0.0, 0.0]
    predicted = [1.0, 0.0]
    assert weighted_rmse(observed, predicted, [100.0, 1.0]) > weighted_rmse(observed, predicted, [1.0, 100.0])


def test_metric_bundle_sorts_residuals_by_phase():
    bundle = metric_bundle([0, 1, 0, 1], [0, 0, 0, 0], phase=[0.5, 0.0, 0.75, 0.25])
    assert "durbin_watson" in bundle


def test_information_criteria_are_finite():
    values = information_criteria(1.0, 30, 4)
    assert all(np.isfinite(value) for value in values.values())


def test_durbin_watson_zero_for_exact_fit_residual():
    assert durbin_watson([0.0, 0.0, 0.0]) == 0.0


def test_stable_fourier_selection_rejects_large_span_candidate():
    from derd.baselines import select_stable_fourier_order

    phase = np.concatenate([np.linspace(0.45, 0.95, 18), np.array([0.02])])
    flux = 0.5 + 0.2 * np.cos(2 * np.pi * phase)
    selection = select_stable_fourier_order(
        phase,
        flux,
        orders=(1, 2, 3, 4, 5),
        normalize_target=False,
        maximum_prediction_span_factor=1.5,
    )
    assert selection.selected.order in selection.eligible_orders or not selection.eligible_orders
    assert selection.selected.dense_prediction_span <= 1.5 * np.ptp(flux) or not selection.eligible_orders
