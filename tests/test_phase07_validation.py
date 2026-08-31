import numpy as np

from derd.harmonic_extraction import fit_weighted_harmonic_exchange
from derd.lightcurve import LightCurve, ValueDomain
from derd.model import waveform
from derd.parameters import DERDParameters
from derd.validation_phase07 import (
    Phase07Config,
    actual_cadence_mvhe,
    calibrate_actual_cadence,
    phase_stratified_subset,
    screen_exchange_with_uncertainty,
)


def exact_derd_curve() -> LightCurve:
    rng = np.random.default_rng(80)
    time = np.sort(rng.uniform(0.0, 80.0, 320))
    period = 1.7
    phase = np.mod(time / period, 1.0)
    values = 1.0 + 0.35 * waveform(
        phase,
        DERDParameters(0.25, 0.78, 0.58, 0.31),
        time_law="geometric",
        output_normalization="canonical",
    )
    return LightCurve(
        star_id="SYNTHETIC-DERD-PHASE07",
        time=time,
        value=values,
        error=np.full(time.size, 0.001),
        domain=ValueDomain.FLUX,
        metadata={"local_sha256": "b" * 64, "source_locator": "unit-test"},
    )


def test_exchange_uncertainty_accepts_high_snr_exact_derd() -> None:
    curve = exact_derd_curve()
    extraction = fit_weighted_harmonic_exchange(
        curve,
        period_days=1.7,
        order=8,
        reference_epoch=0.0,
        covariance_estimator="photometric",
    )
    config = Phase07Config(uncertainty_draws=64, uncertainty_seed=2)
    result = screen_exchange_with_uncertainty(
        extraction,
        threshold=0.2,
        config=config,
    )
    assert result.nominal_score < 0.05
    assert result.qualifies
    assert result.threshold_pass_fraction > 0.8


def test_phase_stratified_subset_is_deterministic_for_seed() -> None:
    phase = np.linspace(0.0, 1.0, 100, endpoint=False)
    first = phase_stratified_subset(phase, 25, rng=np.random.default_rng(3))
    second = phase_stratified_subset(phase, 25, rng=np.random.default_rng(3))
    np.testing.assert_array_equal(first, second)
    assert np.unique(first).size == 25


def test_small_actual_cadence_calibration_and_mvhe_run() -> None:
    curve = exact_derd_curve()
    phase = np.mod(curve.time / 1.7, 1.0)
    config = Phase07Config(
        full_calibration_per_class=12,
        mvhe_counts=(80, 160),
        mvhe_replicates=2,
        mvhe_per_class=12,
    )
    calibration, rows = calibrate_actual_cadence(
        phase,
        curve.error,
        amplitude_scale=0.35,
        config=config,
    )
    assert len(rows) == 24
    assert np.isfinite(calibration.threshold)
    replicates, summaries = actual_cadence_mvhe(
        phase,
        curve.error,
        amplitude_scale=0.35,
        config=config,
    )
    assert len(replicates) == 4
    assert [row.observation_count for row in summaries] == [80, 160]


def _mvhe_summary(count: int, passed: bool):
    from derd.validation_phase07 import MVHESummary

    return MVHESummary(
        observation_count=count,
        replicate_count=12,
        median_roc_auc=0.9 if passed else 0.7,
        q10_roc_auc=0.8 if passed else 0.6,
        median_balanced_accuracy=0.82 if passed else 0.68,
        q10_balanced_accuracy=0.72 if passed else 0.61,
        median_threshold=1.5,
        passes_gate=passed,
    )


def test_mvhe_sustained_gate_rejects_isolated_pointwise_pass() -> None:
    from derd.validation_phase07 import assess_mvhe_gate

    assessment = assess_mvhe_gate(
        [
            _mvhe_summary(80, False),
            _mvhe_summary(120, True),
            _mvhe_summary(160, False),
            _mvhe_summary(240, True),
            _mvhe_summary(320, True),
            _mvhe_summary(372, True),
        ],
        minimum_sustained_levels=3,
    )
    assert assessment.first_pointwise_pass == 120
    assert assessment.first_sustained_pass == 240
    assert assessment.sustained_level_count == 3
    assert assessment.non_monotonic_pointwise_pattern


def test_mvhe_sustained_gate_requires_minimum_tail_length() -> None:
    from derd.validation_phase07 import assess_mvhe_gate

    assessment = assess_mvhe_gate(
        [
            _mvhe_summary(80, False),
            _mvhe_summary(120, True),
            _mvhe_summary(160, True),
        ],
        minimum_sustained_levels=3,
    )
    assert assessment.first_pointwise_pass == 120
    assert assessment.first_sustained_pass is None
    assert assessment.sustained_level_count == 0
