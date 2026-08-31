from __future__ import annotations

import json
from pathlib import Path

import pytest

from derd.ogle_catalog_phase21 import (
    Ogle3LmcDsctLegacyIdentity,
    exact_two_hop_match,
    validate_metadata_lock_manifest,
    validate_row_receipt,
)
from derd.validation_phase21 import (
    EXPECTED_IDS,
    _validate_cohort,
    assess_phase21,
    synthetic_full_cohort_control,
)

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_legacy_identity_parser_preserves_field_identity():
    row = Ogle3LmcDsctLegacyIdentity.parse(
        "OGLE-LMC-DSCT-0003 LMC158.5 3261 SINGLEMODE 04:30:21.19 -70:12:54.7"
    )
    assert row.object_id == "OGLE-LMC-DSCT-0003"
    assert row.field_id == "LMC158.5.3261"
    assert row.subtype == "singlemode"


def test_exact_two_hop_match_uses_field_id_not_numeric_suffix():
    legacy = Ogle3LmcDsctLegacyIdentity.parse(
        "OGLE-LMC-DSCT-0003 LMC158.5 3261 SINGLEMODE 04:30:21.19 -70:12:54.7"
    )
    current = [
        {"current_object_id": "OGLE-LMC-DSCT-00003", "ogle3_field_id": "LMC158.5.3261"},
        {"current_object_id": "OGLE-LMC-DSCT-99999", "ogle3_field_id": "LMC999.9.3"},
    ]
    assert exact_two_hop_match(legacy, current)["current_object_id"] == "OGLE-LMC-DSCT-00003"


def test_no_numeric_suffix_fallback_is_permitted():
    legacy = Ogle3LmcDsctLegacyIdentity.parse(
        "OGLE-LMC-DSCT-0004 LMC157.5 3394 SINGLEMODE 04:30:52.40 -69:35:42.2"
    )
    current = [{"current_object_id": "OGLE-LMC-DSCT-00004", "ogle3_field_id": "LMC999.9.3394"}]
    assert exact_two_hop_match(legacy, current) is None


def test_ambiguous_exact_crosswalk_is_rejected():
    legacy = Ogle3LmcDsctLegacyIdentity.parse(
        "OGLE-LMC-DSCT-0005 LMC156.6 844 SINGLEMODE 04:31:08.06 -69:11:34.8"
    )
    rows = [
        {"current_object_id": "A", "ogle3_field_id": legacy.field_id},
        {"current_object_id": "B", "ogle3_field_id": legacy.field_id},
    ]
    with pytest.raises(ValueError):
        exact_two_hop_match(legacy, rows)


def test_authoritative_row_receipt_validates():
    valid, blockers = validate_row_receipt(
        load("data/manifests/phase21_authoritative_catalog_row_receipt.json")
    )
    assert valid, blockers


def test_metadata_lock_has_three_locks_and_two_unresolved():
    receipt = load("data/manifests/phase21_authoritative_catalog_row_receipt.json")
    lock = load("data/manifests/phase21_delta_scuti_metadata_lock.json")
    valid, blockers = validate_metadata_lock_manifest(lock, receipt=receipt)
    assert valid, blockers
    assert lock["locked_count"] == 3
    assert lock["unresolved_count"] == 2
    assert {r["requested_object_id"] for r in lock["records"]} == {
        "OGLE-LMC-DSCT-0003", "OGLE-LMC-DSCT-0005", "OGLE-LMC-DSCT-0006"
    }


def test_unmatched_records_do_not_contain_inferred_current_ids():
    receipt = load("data/manifests/phase21_authoritative_catalog_row_receipt.json")
    unmatched = [r for r in receipt["records"] if r["resolution_status"].startswith("NO_EXACT")]
    assert {r["requested_object_id"] for r in unmatched} == {
        "OGLE-LMC-DSCT-0004", "OGLE-LMC-DSCT-0007"
    }
    assert all(r["current_identity"] is None and r["current_parameters"] is None for r in unmatched)


def test_frozen_cohort_is_exact_5_plus_5_plus_5():
    cohort = load("data/manifests/phase21_development_cohort.json")
    valid, counts, blockers = _validate_cohort(cohort)
    assert valid, blockers
    assert counts == {"classical_cepheid": 5, "rr_lyrae": 5, "delta_scuti": 5}
    for family, identities in EXPECTED_IDS.items():
        assert tuple(r["object_id"] for r in cohort["targets"] if r["family"] == family) == identities


def test_phase21_current_assessment_is_honestly_blocked():
    assessment = assess_phase21(root=ROOT)
    assert assessment.metadata_ready_count == 13
    assert assessment.dsct_locked_count == 3
    assert assessment.dsct_unresolved_count == 2
    assert assessment.source_ready_count == 0
    assert assessment.inherited_evidence_count == 5
    assert assessment.fresh_result_count == 0
    assert assessment.primary_outputs_suppressed
    assert not assessment.c17_promoted


def test_authoritative_periods_replace_legacy_diagnostic_coordinates():
    summary = load("artifacts/phase21/phase21_summary.json")
    rows = {r["requested_object_id"]: r for r in summary["period_coordinate_corrections"]}
    assert rows["OGLE-LMC-DSCT-0003"]["authoritative_period_days"] == pytest.approx(0.06644253)
    assert rows["OGLE-LMC-DSCT-0005"]["authoritative_period_days"] == pytest.approx(0.06768650)
    assert rows["OGLE-LMC-DSCT-0006"]["authoritative_period_days"] == pytest.approx(0.12224786)
    assert all(abs(r["absolute_difference_days"]) > 0.01 for r in rows.values())


def test_singlemode_is_not_promoted_to_radial_order():
    lock = load("data/manifests/phase21_delta_scuti_metadata_lock.json")
    assert all(r["mode_label"] == "singlemode_radial_order_unresolved" for r in lock["records"])


def test_synthetic_complete_control_opens_interval_path_only_as_nonastronomical_control():
    control = synthetic_full_cohort_control()
    assert control["complete_denominator"]
    assert control["family_intervals_emitted"]
    assert not control["astronomical_evidence"]
    assert all(row["n"] == 5 and 0 <= row["wilson_low"] <= row["wilson_high"] <= 1 for row in control["rows"])


def test_tampered_receipt_fails():
    receipt = load("data/manifests/phase21_authoritative_catalog_row_receipt.json")
    receipt["records"][0]["current_parameters"]["primary_period_days"] *= 2
    valid, blockers = validate_row_receipt(receipt)
    assert not valid
    assert blockers


def test_no_complete_third_party_raw_files_are_bundled_in_working_tree():
    assert not list((ROOT / "data/raw/phase09_cohort").glob("*.complete.dat"))
