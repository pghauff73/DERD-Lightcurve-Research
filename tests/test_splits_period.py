import numpy as np
import pytest

from derd.period import estimate_epoch_of_maximum, phase_dispersion_score, verify_catalog_period
from derd.preprocess import fold_phase
from derd.splits import circular_phase_block_split, star_identity_partition


def test_phase_block_split_is_deterministic():
    phase = np.linspace(0.0, 1.0, 30, endpoint=False)
    first = circular_phase_block_split(phase, star_id="A")
    second = circular_phase_block_split(phase, star_id="A")
    assert np.array_equal(first.test_indices, second.test_indices)


def test_phase_block_split_has_no_overlap():
    split = circular_phase_block_split(np.linspace(0, 1, 30, endpoint=False), star_id="A")
    assert np.intersect1d(split.train_indices, split.test_indices).size == 0
    assert split.train_indices.size + split.test_indices.size == 30


def test_star_partition_never_splits_identity():
    result = star_identity_partition([f"S{i}" for i in range(10)], holdout_fraction=0.2)
    assert set(result.values()) == {"development", "holdout"}
    assert sum(value == "holdout" for value in result.values()) == 2


def test_phase_dispersion_prefers_true_period():
    time = np.linspace(0.0, 20.0, 200)
    value = np.sin(2 * np.pi * time / 2.0)
    assert phase_dispersion_score(time, value, 2.0) < phase_dispersion_score(time, value, 2.2)


def test_period_verification_returns_small_delta_for_clean_signal():
    time = np.linspace(0.0, 50.0, 300)
    value = np.cos(2 * np.pi * time / 3.0)
    check = verify_catalog_period(time, value, 3.0, relative_span=0.01, grid_count=101, bins=12)
    assert abs(check.relative_delta) < 0.001


def test_epoch_estimator_places_peak_near_zero():
    period = 2.0
    time = np.linspace(0.0, 20.0, 200, endpoint=False)
    flux = 1.0 + 0.2 * np.cos(2 * np.pi * (time - 0.4) / period)
    epoch, _ = estimate_epoch_of_maximum(time, flux, period)
    phase = fold_phase([0.4], period, epoch=epoch)[0]
    assert min(phase, 1.0 - phase) < 0.02


def test_invalid_period_grid_count_is_rejected():
    with pytest.raises(ValueError):
        verify_catalog_period(np.arange(10.0), np.arange(10.0), 1.0, grid_count=100)


def test_adaptive_period_scan_stops_on_interior_solution():
    from derd.period import adaptive_verify_catalog_period

    time = np.linspace(0.0, 20.0, 200)
    period = 1.25
    values = np.sin(2.0 * np.pi * time / period)
    result = adaptive_verify_catalog_period(
        time,
        values,
        period,
        relative_spans=(0.001, 0.005),
        grid_count=51,
        bins=8,
    )
    assert result.resolved
    assert len(result.stages) == 1
    assert abs(result.relative_delta) < 0.001


def test_adaptive_period_scan_validates_span_order():
    from derd.period import adaptive_verify_catalog_period
    import pytest

    time = np.linspace(0.0, 10.0, 50)
    values = np.sin(time)
    with pytest.raises(ValueError, match="strictly increasing"):
        adaptive_verify_catalog_period(time, values, 1.0, relative_spans=(0.01, 0.005))
