import numpy as np
import pytest

from derd.lightcurve import LightCurve, ValueDomain


def sample_curve():
    return LightCurve(
        star_id="X",
        time=np.array([3.0, 1.0, 2.0]),
        value=np.array([10.0, 11.0, 12.0]),
        error=np.array([0.1, 0.2, 0.3]),
        metadata={"source": "test"},
    )


def test_curve_is_sorted_stably():
    curve = sample_curve()
    assert curve.time.tolist() == [1.0, 2.0, 3.0]
    assert curve.value.tolist() == [11.0, 12.0, 10.0]


def test_curve_arrays_are_read_only():
    curve = sample_curve()
    with pytest.raises(ValueError):
        curve.value[0] = 99.0


def test_curve_rejects_nonpositive_errors():
    with pytest.raises(ValueError):
        LightCurve("X", np.arange(3), np.arange(3), np.array([1.0, 0.0, 1.0]))


def test_subset_accepts_boolean_mask():
    subset = sample_curve().subset(np.array([True, False, True]))
    assert subset.size == 2


def test_subset_rejects_empty_selection():
    with pytest.raises(ValueError):
        sample_curve().subset(np.array([False, False, False]))


def test_magnitude_to_flux_is_monotonic():
    curve = sample_curve().to_relative_flux(reference_magnitude=11.0)
    assert curve.domain is ValueDomain.FLUX
    # Smaller magnitude is brighter and therefore has greater flux.
    assert curve.value[-1] > curve.value[0]
    assert np.all(curve.error > 0.0)


def test_flux_conversion_is_idempotent():
    flux = sample_curve().to_relative_flux()
    assert flux.to_relative_flux() is flux
