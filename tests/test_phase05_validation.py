import numpy as np

from derd.validation_phase05 import (
    SyntheticScreenRecord,
    calibrate_score_threshold,
)


def record(identifier: str, label: int, score: float, split: str) -> SyntheticScreenRecord:
    return SyntheticScreenRecord(
        synthetic_id=identifier,
        template_star_id="T",
        label=label,
        null_family="derd_geometric" if label else "generic_fourier",
        noise_multiplier=1.0,
        score=score,
        flags=(),
        split=split,
    )


def test_threshold_calibration_separates_simple_scores() -> None:
    rows = [
        record("p1", 1, 0.1, "development"),
        record("p2", 1, 0.2, "development"),
        record("n1", 0, 1.0, "development"),
        record("n2", 0, 1.2, "development"),
        record("p3", 1, 0.15, "holdout"),
        record("n3", 0, 1.1, "holdout"),
    ]
    calibration = calibrate_score_threshold(rows)
    assert 0.2 < calibration.threshold < 1.0
    assert calibration.development_metrics["balanced_accuracy"] == 1.0
    assert calibration.holdout_metrics["balanced_accuracy"] == 1.0


def test_threshold_calibration_is_deterministic() -> None:
    rows = [
        record("p1", 1, 0.2, "development"),
        record("n1", 0, 0.8, "development"),
        record("p2", 1, 0.3, "holdout"),
        record("n2", 0, 0.9, "holdout"),
    ]
    first = calibrate_score_threshold(rows)
    second = calibrate_score_threshold(rows[::-1])
    np.testing.assert_allclose(first.threshold, second.threshold)
