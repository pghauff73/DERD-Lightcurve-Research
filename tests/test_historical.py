import numpy as np

from derd.historical import (
    PaperEllipseEquation,
    exact_semimajor_axis_for_one_second_period,
    implied_period_from_paper_axis,
    paper_semimajor_axis,
    paper_waveform,
)


def test_declared_phase_is_ignored_in_printed_code_path() -> None:
    first = paper_waveform(0.7, 0.3, 0.3, 0.28, requested_samples=300)
    second = paper_waveform(0.7, 0.3, 0.3, 0.71, requested_samples=300)
    assert np.array_equal(first, second)


def test_approximate_cube_root_changes_scale_and_cycle_closure() -> None:
    paper_axis = paper_semimajor_axis()
    exact_axis = exact_semimajor_axis_for_one_second_period()
    assert paper_axis != exact_axis
    assert implied_period_from_paper_axis() < 1.0
    cycle = PaperEllipseEquation(0.1).calc(1000)
    assert cycle.sample_count < 1000
    assert cycle.sample_count > 950


def test_historical_circular_normalization_is_numerically_degenerate() -> None:
    cycle = PaperEllipseEquation(0.0).calc(200)
    raw_span = float(np.max(cycle.distance_raw) - np.min(cycle.distance_raw))
    relative_span = raw_span / float(np.mean(cycle.distance_raw))
    assert relative_span < 1e-14
    # Floating-point noise is stretched across [0, 1], producing a spurious shape.
    assert float(np.ptp(cycle.distance_normalized)) >= 0.99
