from __future__ import annotations

import json
from pathlib import Path

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase10 import (
    PHASE10_DECISION_BLOCKED,
    assess_phase10,
    synthetic_catalog_lock_control,
)
from derd.validation_phase09 import verify_protocol


ROOT = Path(__file__).resolve().parents[1]


def assessment():
    return assess_phase10(
        root=ROOT,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path="artifacts/phase10/phase10_source_acquisition_receipt.json",
    )


def test_phase10_protocol_and_contract_are_sealed() -> None:
    valid, expected, actual = verify_protocol(
        ROOT / "research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        ROOT / "research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
    )
    assert valid
    assert expected == actual
    result = assessment()
    assert result.catalog_contract_valid


def test_current_phase10_gate_is_honestly_blocked() -> None:
    result = assessment()
    assert result.cohort_structure_ready
    assert result.family_counts == {
        "classical_cepheid": 5,
        "delta_scuti": 5,
        "rr_lyrae": 5,
    }
    assert result.metadata_ready_count == 10
    assert result.source_ready_count == 0
    assert result.cached_result_count == 5
    assert result.execution_ready_count == 0
    assert result.primary_outputs_suppressed
    assert result.decision == PHASE10_DECISION_BLOCKED
    assert not result.c17_promoted


def test_delta_scuti_legacy_coordinates_are_not_promoted() -> None:
    rows = [row for row in assessment().targets if row.target.family == "delta_scuti"]
    assert len(rows) == 5
    assert all(not row.metadata_ready for row in rows)
    assert all("AUTHORITATIVE_METADATA_LOCK_MISSING" in row.blockers for row in rows)
    assert all("DELTA_SCUTI_PERIOD_NOT_LOCKED" in row.blockers for row in rows)


def test_synthetic_catalog_lock_control_is_deterministic_and_noninventive() -> None:
    first = synthetic_catalog_lock_control()
    second = synthetic_catalog_lock_control()
    assert first == second
    digest = first["sha256_canonical_json"]
    payload = dict(first)
    payload.pop("sha256_canonical_json")
    assert digest == canonical_json_sha256(payload)
    assert first["resolved_count"] == 5
    assert first["all_locks_verify"]
    assert first["all_crosswalked"]
    assert not first["singlemode_radial_order_invented"]


def test_tampered_catalog_contract_fails(tmp_path: Path) -> None:
    contract = json.loads((ROOT / "data/manifests/phase10_authoritative_catalog_contract.json").read_text())
    contract["record_count"] = 1
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    result = assess_phase10(
        root=ROOT,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path=path,
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
    )
    assert not result.catalog_contract_valid
