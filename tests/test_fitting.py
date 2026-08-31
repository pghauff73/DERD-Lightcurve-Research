import numpy as np

from derd.baselines import fit_fourier
from derd.fitting import fit_waveform
from derd.model import waveform
from derd.parameters import DERDParameters


def test_direct_fitter_reproduces_synthetic_model_from_truth_start() -> None:
    phase = np.linspace(0.0, 1.0, 192, endpoint=False)
    truth = DERDParameters(0.18, 0.72, 0.58, 0.83)
    target = waveform(phase, truth, normalization_grid_size=1024)
    result = fit_waveform(
        phase,
        target,
        starts=4,
        initial_points=[truth.as_tuple()],
        normalization_grid_size=1024,
        max_function_evaluations=120,
        normalize_target=False,
    )
    assert result.success
    assert result.metrics["rmse"] < 1e-9
    assert np.isfinite(result.jacobian_condition_number)


def test_fourier_baseline_exactly_recovers_known_second_order_signal() -> None:
    phase = np.linspace(0.0, 1.0, 256, endpoint=False)
    signal = (
        1.2
        + 0.5 * np.cos(2.0 * np.pi * phase)
        - 0.2 * np.sin(2.0 * np.pi * phase)
        + 0.3 * np.cos(4.0 * np.pi * phase)
    )
    result = fit_fourier(phase, signal, order=2, normalize_target=False)
    assert result.metrics["rmse"] < 1e-13
    assert result.effective_parameters == 5
