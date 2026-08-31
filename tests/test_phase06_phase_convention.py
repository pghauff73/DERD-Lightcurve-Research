import json
import math
from pathlib import Path

import numpy as np

from derd.parameters import DERDParameters
from derd.phase_convention import (
    LegacyPhaseSummary,
    PhaseRecoverability,
    ambiguity_bounded_screen,
    audit_legacy_phase_summary,
    canonical_coefficients_from_sine_cosine,
    coefficients_from_legacy_summary,
    feasible_fundamental_phase_interval,
    frequency_blocks_repeat_under_frozen_source,
    legacy_summary_from_complex_coefficients,
    legacy_summary_from_sine_cosine,
    principal_mod_pi,
    recurrence_overidentifying_real_degrees_of_freedom,
    shift_sine_phases,
    source_relative_phases_from_sine_phases,
    standard_epoch_invariant_relative_phases,
)
from derd.spectral import raw_derd_complex_coefficients


def test_signed_sine_cosine_conversion_round_trip() -> None:
    sine = np.asarray([1.2, -0.7, 0.4])
    cosine = np.asarray([-0.3, 0.9, 0.2])
    coefficients = canonical_coefficients_from_sine_cosine(sine, cosine)
    np.testing.assert_allclose(coefficients.real, cosine / 2.0)
    np.testing.assert_allclose(coefficients.imag, -sine / 2.0)


def test_legacy_phase_is_modulo_pi_and_loses_quadrant() -> None:
    first = legacy_summary_from_sine_cosine([1.0, 0.4], [0.5, -0.2])
    second = legacy_summary_from_sine_cosine([-1.0, -0.4], [-0.5, 0.2])
    np.testing.assert_allclose(first.amplitudes, second.amplitudes)
    np.testing.assert_allclose(first.relative_phases, second.relative_phases)


def test_source_relative_phase_is_not_epoch_invariant() -> None:
    phases = np.asarray([0.2, -0.7, 1.1, -2.0])
    shifted = shift_sine_phases(phases, epoch_shift_cycles=0.071)
    legacy_before = source_relative_phases_from_sine_phases(phases)
    legacy_after = source_relative_phases_from_sine_phases(shifted)
    invariant_before = standard_epoch_invariant_relative_phases(phases)
    invariant_after = standard_epoch_invariant_relative_phases(shifted)
    assert not np.allclose(legacy_before[1:], legacy_after[1:])
    np.testing.assert_allclose(invariant_before, invariant_after, atol=2e-14)


def test_feasible_interval_recovers_source_fundamental_principal_phase() -> None:
    phases = np.asarray([0.31, -0.8, 0.91, -1.2])
    summary = legacy_summary_from_sine_cosine(np.cos(phases), np.sin(phases))
    interval = feasible_fundamental_phase_interval(summary.relative_phases)
    expected = float(principal_mod_pi([phases[0]])[0])
    assert interval.consistent
    assert interval.lower <= expected <= interval.upper


def test_legacy_summary_has_continuous_and_discrete_ambiguity() -> None:
    coefficients = raw_derd_complex_coefficients(
        DERDParameters(0.26, 0.72, 0.63, 0.29), maximum_harmonic=4
    )[1:]
    summary = legacy_summary_from_complex_coefficients(coefficients)
    audit = audit_legacy_phase_summary(summary)
    assert audit.recoverability is PhaseRecoverability.CONTINUOUS_AND_BRANCH_AMBIGUOUS
    assert audit.discrete_branch_count_after_global_sign_quotient == 8
    assert audit.recurrence_overidentifying_real_degrees_of_freedom == 0
    assert not audit.qualifies_for_unique_complex_screen
    assert "ONE_ARGUMENT_ARCTAN_LOSES_QUADRANT" in audit.flags


def test_same_legacy_row_reconstructs_distinct_complex_sequences() -> None:
    summary = LegacyPhaseSummary(
        amplitudes=np.asarray([1.0, 0.5, 0.3, 0.2]),
        relative_phases=np.asarray([0.0, -0.2, 0.3, -0.1]),
    )
    interval = feasible_fundamental_phase_interval(summary.relative_phases)
    phase_a = interval.lower + 0.25 * interval.width
    phase_b = interval.lower + 0.75 * interval.width
    first = coefficients_from_legacy_summary(
        summary,
        fundamental_principal_phase=phase_a,
        branch_bits=(0, 0, 0, 0),
    )
    second = coefficients_from_legacy_summary(
        summary,
        fundamental_principal_phase=phase_b,
        branch_bits=(0, 1, 0, 1),
    )
    assert not np.allclose(first, second)
    np.testing.assert_allclose(np.abs(first), np.abs(second))


def test_four_harmonics_have_zero_recurrence_forecast_dof() -> None:
    assert recurrence_overidentifying_real_degrees_of_freedom(4) == 0
    assert recurrence_overidentifying_real_degrees_of_freedom(5) == 2
    assert recurrence_overidentifying_real_degrees_of_freedom(8) == 8


def test_ambiguity_screen_never_qualifies() -> None:
    coefficients = raw_derd_complex_coefficients(
        DERDParameters(0.31, 0.74, 0.55, 0.22), maximum_harmonic=4
    )[1:]
    summary = legacy_summary_from_complex_coefficients(coefficients)
    result = ambiguity_bounded_screen(summary, fundamental_phase_grid_size=17)
    assert result.evaluated_sequences == 17 * 8
    assert result.evidence_level == "AMBIGUITY_BOUND_ONLY"
    assert not result.qualifies
    assert math.isfinite(result.best_score)


def test_frozen_source_requires_repeated_frequency_blocks() -> None:
    repeated_a = np.tile(np.asarray([[1.0, 0.5, 0.25, 0.125]]), (3, 1))
    repeated_p = np.tile(np.asarray([[0.0, 0.1, -0.2, 0.3]]), (3, 1))
    assert frequency_blocks_repeat_under_frozen_source(repeated_a, repeated_p)
    repeated_a[1, 0] = 0.9
    assert not frequency_blocks_repeat_under_frozen_source(repeated_a, repeated_p)


def test_compact_catalog_samples_violate_frozen_source_repeat_invariant() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "data/evidence/phase06_frozen_catalog_samples.json").read_text()
    )
    assert len(payload["records"]) == 3
    for record in payload["records"]:
        assert not frequency_blocks_repeat_under_frozen_source(
            record["amplitude_blocks"], record["relative_phase_blocks"]
        )
