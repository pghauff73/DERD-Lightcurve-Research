from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from derd.harmonic_exchange import read_harmonic_exchange
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase20 import (
    effective_mass_controls,
    invariant_vector_from_signed_coefficients,
    optimal_circular_shape_rmse,
    run_mechanism_tournament,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase20_protocol_is_sealed() -> None:
    protocol = json.loads(
        (ROOT / "research/preregistration/phase20_multiband_mechanism_falsification_protocol.json").read_text()
    )
    seal = json.loads(
        (ROOT / "research/preregistration/phase20_multiband_mechanism_falsification_protocol.seal.json").read_text()
    )
    assert canonical_json_sha256(protocol) == seal["sha256_canonical_json"]
    assert not protocol["promotion_policy"]["c17_promoted"]
    assert protocol["promotion_policy"]["population_denominator_increment"] == 0


def test_phase20_summary_preserves_falsification_boundaries() -> None:
    summary = json.loads((ROOT / "artifacts/phase20/phase20_summary.json").read_text())
    assert summary["multiband"]["strict_band_invariance_rejected"]
    assert not summary["multiband"]["same_band_epoch_invariance_rejected"]
    assert summary["gravity_only_test"]["ballistic_positive_control_passed"]
    assert summary["gravity_only_test"]["all_periodic_controls_failed"]
    assert summary["certificate"] == "NOT_A_PHYSICAL_CLAIM_CERTIFICATE"


def test_phase20_real_multiband_results_have_expected_direction() -> None:
    summary = json.loads((ROOT / "artifacts/phase20/phase20_summary.json").read_text())
    comparisons = summary["multiband"]["comparisons"]
    assert comparisons["I_vs_V_merged"]["p_value"] < 1.0e-10
    assert comparisons["V_OGLEIII_vs_V_OGLEIV"]["p_value"] > 0.95
    models = summary["multiband"]["shape_model_comparison"]
    assert models["rmse"]["shared_components_band_weights"] < models["rmse"]["separate_derd"]
    assert models["bootstrap_wins"]["shared_components_band_weights"] >= 60


def test_phase20_nonderd_surrogates_pass_joint_gate() -> None:
    summary = json.loads((ROOT / "artifacts/phase20/phase20_summary.json").read_text())
    rows = summary["mechanism_tournament"]["holdout_family_summary"]
    passing = {
        row["family"]
        for row in rows
        if row["family"] != "derd_geometric"
        and row["joint_fit_and_screen_pass_fraction"] > 0.0
    }
    assert "radius_temperature_projection" in passing
    assert "spot_rotation" in passing
    assert "cse_reprocessing" in passing


def test_effective_mass_positive_and_periodic_negative_controls() -> None:
    controls = effective_mass_controls()
    assert controls[0].model_id == "inverse_square_ballistic_segment"
    assert controls[0].gate_pass
    assert all(not control.gate_pass for control in controls[1:])
    assert all(control.sign_changes >= 2 for control in controls[1:])


def test_invariant_vector_is_epoch_invariant_under_harmonic_phase_rotation() -> None:
    sine = np.asarray([0.7, 0.2, -0.1, 0.03])
    cosine = np.asarray([0.1, -0.15, 0.08, 0.02])
    original = invariant_vector_from_signed_coefficients(sine, cosine)
    shift = 0.173
    complex_coefficients = 0.5 * (cosine - 1j * sine)
    harmonic = np.arange(1, complex_coefficients.size + 1)
    rotated = complex_coefficients * np.exp(-2j * np.pi * harmonic * shift)
    shifted_sine = -2.0 * rotated.imag
    shifted_cosine = 2.0 * rotated.real
    moved = invariant_vector_from_signed_coefficients(shifted_sine, shifted_cosine)
    assert np.allclose(original, moved, atol=1.0e-12, rtol=1.0e-12)


def test_fft_alignment_is_zero_for_identical_series() -> None:
    series = read_harmonic_exchange(
        ROOT / "artifacts/phase14/harmonic_exchange/OGLE-LMC-CEP-0002.json"
    )
    result = optimal_circular_shape_rmse(series, series, grid_size=2048)
    assert result["minimum_rmse"] < 1.0e-10
    assert abs(result["best_lag_cycles"]) < 1.0e-5


def test_small_mechanism_tournament_is_deterministic() -> None:
    left = run_mechanism_tournament(cases_per_family=12, sample_count=96, holdout_count=18, seed=1122)
    right = run_mechanism_tournament(cases_per_family=12, sample_count=96, holdout_count=18, seed=1122)
    assert left.thresholds == right.thresholds
    assert left.holdout_family_summary == right.holdout_family_summary


def test_phase20_raw_files_are_excluded_from_repository_manifest() -> None:
    expected = {
        "data/raw/phase20_external/OGLE-LMC-CEP-0002_OGLEIII_V.dat",
        "data/raw/phase20_external/OGLE-LMC-CEP-0002_OGLEIV_V.dat",
        "data/raw/phase20_external/OGLE-LMC-CEP-0002_merged_V.dat",
    }
    text = (ROOT / "experiments/build_manifest.py").read_text()
    assert all(relative in text for relative in expected)
