import numpy as np
import pytest

from derd.model import (
    ModelConfig,
    OutputNormalization,
    TimeLaw,
    evaluate,
    waveform,
)
from derd.normalization import DegenerateNormalizationError
from derd.parameters import DERDParameters


def test_corrected_model_is_deterministic() -> None:
    phase = np.linspace(0.0, 1.0, 512, endpoint=False)
    parameters = DERDParameters(0.1, 0.746, 0.5016, 0.92)
    first = waveform(phase, parameters, time_law="geometric")
    second = waveform(phase, parameters, time_law="geometric")
    assert np.array_equal(first, second)


def test_all_four_declared_dimensions_are_effective() -> None:
    phase = np.linspace(0.0, 1.0, 1024, endpoint=False)
    base = DERDParameters(0.20, 0.65, 0.55, 0.23)
    base_values = waveform(phase, base)
    variants = {
        "e1": base.with_dimension("e1", 0.45),
        "e2": base.with_dimension("e2", 0.35),
        "amplitude_ratio": base.with_dimension("amplitude_ratio", 0.90),
        "phase_ratio": base.with_dimension("phase_ratio", 0.41),
    }
    for name, parameters in variants.items():
        changed = waveform(phase, parameters)
        assert float(np.max(np.abs(changed - base_values))) > 1e-3, name


def test_phase_shift_is_continuous_not_integer_quantized() -> None:
    phase = np.linspace(0.0, 1.0, 512, endpoint=False)
    base = DERDParameters(0.2, 0.7, 0.5, 0.28)
    shifted = base.with_dimension("phase_ratio", base.phase_ratio + 1e-5)
    difference = float(np.max(np.abs(waveform(phase, shifted) - waveform(phase, base))))
    assert difference > 1e-8
    assert difference < 1e-2


def test_canonical_normalization_is_independent_of_observation_subset() -> None:
    full_phase = np.linspace(0.0, 1.0, 1024, endpoint=False)
    indices = np.array([3, 19, 80, 201, 470, 700, 900])
    parameters = DERDParameters(0.23, 0.71, 0.62, 0.37)
    full = waveform(full_phase, parameters, normalization_grid_size=4096)
    subset = waveform(full_phase[indices], parameters, normalization_grid_size=4096)
    np.testing.assert_allclose(subset, full[indices], atol=2e-14, rtol=2e-14)


def test_geometric_and_kepler_time_laws_are_distinct_for_nonzero_eccentricity() -> None:
    phase = np.linspace(0.0, 1.0, 512, endpoint=False)
    parameters = DERDParameters(0.3, 0.8, 0.6, 0.21)
    geometric = waveform(phase, parameters, time_law=TimeLaw.GEOMETRIC)
    kepler = waveform(phase, parameters, time_law=TimeLaw.KEPLER)
    assert float(np.max(np.abs(geometric - kepler))) > 0.05


def test_degenerate_component_cancellation_is_rejected() -> None:
    phase = np.linspace(0.0, 1.0, 128, endpoint=False)
    parameters = DERDParameters(0.4, 0.4, 1.0, 0.0)
    with pytest.raises(DegenerateNormalizationError):
        waveform(phase, parameters)


def test_evaluation_exposes_audit_metadata() -> None:
    phase = np.linspace(0.0, 1.0, 64, endpoint=False)
    parameters = DERDParameters(0.1, 0.7, 0.5, 0.2)
    result = evaluate(
        phase,
        parameters,
        config=ModelConfig(
            time_law=TimeLaw.KEPLER,
            output_normalization=OutputNormalization.CANONICAL,
            normalization_grid_size=512,
        ),
    )
    summary = result.as_summary()
    assert summary["sample_count"] == 64
    assert summary["time_law"] == "kepler"
    assert summary["normalization"] is not None
