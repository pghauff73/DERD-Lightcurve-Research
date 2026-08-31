from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from derd.harmonic_evidence import fit_signed_harmonics, phase_coverage
from derd.harmonic_exchange import read_harmonic_exchange, write_harmonic_exchange
from derd.model import waveform
from derd.parameters import DERDParameters
from derd.recurrence_uncertainty import (
    RecurrencePropagation,
    evaluate_harmonic_evidence_gate,
    propagate_recurrence_uncertainty,
)
from derd.harmonic_screen import screen_harmonics
from derd.validation_phase07 import (
    Phase07Config,
    generate_actual_cadence_controls,
    run_phase07_target,
)


def _synthetic_fit(*, n: int = 240, error: float = 0.01):
    rng = np.random.default_rng(19)
    phase = np.sort(rng.random(n))
    parameters = DERDParameters(0.31, 0.72, 0.66, 0.27)
    value = waveform(phase, parameters, time_law="geometric")
    sigma = np.full(n, error)
    noisy = value + rng.normal(0.0, sigma)
    return phase, sigma, fit_signed_harmonics(
        phase,
        noisy,
        sigma,
        period=1.0,
        reference_epoch=0.0,
        order=8,
        ridge=1.0e-6,
    )


def test_phase_coverage_reports_circular_gap() -> None:
    report = phase_coverage(np.linspace(0.0, 1.0, 120, endpoint=False), bins=12)
    assert report["occupied_bins"] == 12
    assert report["occupancy_fraction"] == 1.0
    assert report["maximum_circular_gap"] == pytest.approx(1.0 / 120.0)


def test_signed_fit_has_psd_lossless_covariance(tmp_path: Path) -> None:
    _, _, fit = _synthetic_fit()
    assert fit.coefficient_covariance.shape == (16, 16)
    assert np.min(np.linalg.eigvalsh(fit.coefficient_covariance)) >= -1.0e-12
    assert fit.design_condition_number < 10.0
    series = fit.to_exchange(
        object_id="SYNTH-P07",
        time_unit="cycle",
        value_unit="normalized_flux",
        source_locator="synthetic:test",
        source_sha256=hashlib.sha256(b"synthetic").hexdigest(),
    )
    target = tmp_path / "exchange.json"
    write_harmonic_exchange(target, series)
    replay = read_harmonic_exchange(target)
    assert np.allclose(replay.sine_coefficients, fit.sine_coefficients)
    assert np.allclose(replay.cosine_coefficients, fit.cosine_coefficients)
    assert np.allclose(replay.coefficient_covariance, fit.coefficient_covariance)


def test_covariance_propagation_succeeds_on_high_signal_control() -> None:
    _, _, fit = _synthetic_fit(n=500, error=0.002)
    series = fit.to_exchange(
        object_id="SYNTH-P07",
        time_unit="cycle",
        value_unit="normalized_flux",
        source_locator="synthetic:test",
        source_sha256=hashlib.sha256(b"synthetic").hexdigest(),
    )
    propagation = propagate_recurrence_uncertainty(
        series, score_threshold=3.0, draws=256, seed=8
    )
    assert propagation.successful_draws == 256
    assert propagation.numerical_failure_fraction == 0.0
    assert propagation.score_quantiles["median"] is not None


def test_gate_fails_when_recovery_harmonics_are_low_snr() -> None:
    parameters = DERDParameters(0.30, 0.70, 0.60, 0.25)
    from derd.spectral import raw_derd_complex_coefficients

    coefficients = raw_derd_complex_coefficients(parameters, maximum_harmonic=8)[1:]
    screen = screen_harmonics(coefficients, fit_harmonics=4)
    propagation = RecurrencePropagation(
        requested_draws=100,
        successful_draws=100,
        numerical_failure_fraction=0.0,
        structural_pass_fraction=1.0,
        below_threshold_fraction=1.0,
        score_quantiles={"q05": 0.0, "q10": 0.0, "median": 0.0, "q90": 0.0, "q95": 0.0},
        forecast_residual_quantiles={"q05": 0.0, "q10": 0.0, "median": 0.0, "q90": 0.0, "q95": 0.0},
        unconstrained_forecast_quantiles={"q05": 0.0, "q10": 0.0, "median": 0.0, "q90": 0.0, "q95": 0.0},
        e1_quantiles={"q05": 0.3, "q10": 0.3, "median": 0.3, "q90": 0.3, "q95": 0.3},
        e2_quantiles={"q05": 0.7, "q10": 0.7, "median": 0.7, "q90": 0.7, "q95": 0.7},
        amplitude_ratio_quantiles={"q05": 0.6, "q10": 0.6, "median": 0.6, "q90": 0.6, "q95": 0.6},
        phase_ratio_quantiles={"q05": 0.25, "q10": 0.25, "median": 0.25, "q90": 0.25, "q95": 0.25},
        flag_counts={},
        seed=1,
    )
    gate = evaluate_harmonic_evidence_gate(
        observation_count=300,
        occupied_phase_bins=12,
        total_phase_bins=12,
        design_condition_number=2.0,
        coefficient_snr=np.asarray([100.0, 10.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        screen=screen,
        propagation=propagation,
        score_threshold=3.0,
        cadence_holdout_auc=0.9,
        cadence_holdout_balanced_accuracy=0.8,
        source_complete=True,
    )
    assert not gate.passed
    assert "four_recovery_harmonics_snr" in gate.blockers
    assert "forecast_harmonics_snr" in gate.blockers


def test_actual_cadence_calibration_runs() -> None:
    rng = np.random.default_rng(2)
    phase = np.sort(rng.random(120))
    errors = np.full(120, 0.01)
    calibration = generate_actual_cadence_controls(
        phase=phase,
        errors=errors,
        observed_span=0.5,
        config=Phase07Config(
            synthetic_samples_per_class=12,
            propagation_draws=128,
            observation_sweep_repetitions=2,
        ),
    )
    assert math.isfinite(calibration.threshold)
    assert calibration.holdout_metrics["sample_count"] > 0


def test_run_target_rejects_wrong_blob_sha(tmp_path: Path) -> None:
    path = tmp_path / "curve.dat"
    rows = [f"{index:.1f} {15 + 0.1 * math.sin(index):.6f} 0.01" for index in range(60)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Git blob"):
        run_phase07_target(
            source_path=path,
            object_id="TEST",
            mode="F",
            catalog_period=3.0,
            expected_git_blob_sha1="0" * 40,
            source_locator="synthetic:test",
            config=Phase07Config(
                synthetic_samples_per_class=10,
                propagation_draws=128,
                observation_sweep_repetitions=2,
            ),
        )
