from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from derd.harmonic_extraction import git_blob_sha1_file
from derd.validation_phase09 import (
    EXPECTED_FAMILIES,
    Phase09Target,
    assess_phase09,
    assess_target_readiness,
    canonical_json_sha256,
    synthetic_governance_control,
    verify_protocol,
    wilson_interval,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _target_for(path: Path, *, source_sha256: str | None = None) -> Phase09Target:
    return Phase09Target(
        object_id="OGLE-LMC-CEP-TEST",
        family="classical_cepheid",
        mode="F",
        catalog_period_days=1.25,
        period_evidence_grade="EXTERNAL_CATALOG_TEST",
        mode_evidence_grade="EXTERNAL_CATALOG_TEST",
        period_source="synthetic exact catalog",
        metadata_identity_status="RESOLVED_EXACT",
        source_repository="synthetic/repository",
        source_commit="1" * 40,
        source_repository_path="photometry/test.dat",
        source_git_blob_sha1=git_blob_sha1_file(path),
        source_byte_count=path.stat().st_size,
        source_observation_count=len(path.read_text(encoding="utf-8").splitlines()),
        source_sha256=source_sha256,
        source_sha256_status="FROZEN" if source_sha256 else "PENDING_ACQUISITION_RECEIPT",
        source_relative_path=path.name,
        evidence_role="exposed-development-only",
    )


def test_frozen_protocol_seal_verifies() -> None:
    valid, expected, actual = verify_protocol(
        REPOSITORY_ROOT / "research/preregistration/phase09_multifamily_development_protocol.json",
        REPOSITORY_ROOT / "research/preregistration/phase09_multifamily_development_protocol.seal.json",
    )
    assert valid
    assert expected == actual
    assert len(actual) == 64


def test_current_cohort_is_exact_5_plus_5_plus_5_but_hard_gated() -> None:
    result = assess_phase09(
        root=REPOSITORY_ROOT,
        manifest_path="data/manifests/phase09_development_cohort.json",
        protocol_path="research/preregistration/phase09_multifamily_development_protocol.json",
        seal_path="research/preregistration/phase09_multifamily_development_protocol.seal.json",
        acquisition_receipt_path="artifacts/phase09/phase09_acquisition_receipt.json",
    )
    assert result.protocol_valid
    assert result.cohort_structure_ready
    assert result.family_counts == {family: 5 for family in EXPECTED_FAMILIES}
    assert not result.cohort_metadata_ready
    assert not result.cohort_sources_ready
    assert result.inherited_result_count == 5
    assert result.primary_outputs_suppressed
    assert result.primary_family_outputs == ()
    assert result.decision == "PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_AND_SOURCE_GATES"


def test_delta_scuti_legacy_coordinates_are_not_silently_promoted() -> None:
    result = assess_phase09(
        root=REPOSITORY_ROOT,
        manifest_path="data/manifests/phase09_development_cohort.json",
        protocol_path="research/preregistration/phase09_multifamily_development_protocol.json",
        seal_path="research/preregistration/phase09_multifamily_development_protocol.seal.json",
    )
    dsct = [item for item in result.target_readiness if item.target.family == "delta_scuti"]
    assert len(dsct) == 5
    assert all(not item.metadata_ready for item in dsct)
    assert all("PERIOD_NOT_CLAIM_GRADE" in item.blockers for item in dsct)
    assert all("MODE_NOT_CLAIM_GRADE" in item.blockers for item in dsct)
    assert all("CATALOG_IDENTITY_NOT_RESOLVED" in item.blockers for item in dsct)


def test_source_can_be_frozen_by_verified_receipt_without_manifest_rewrite(tmp_path: Path) -> None:
    source = tmp_path / "source.dat"
    source.write_text("".join(f"{index}.0 15.0 0.01\n" for index in range(240)), encoding="utf-8")
    target = _target_for(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    receipt = {
        "object_id": target.object_id,
        "source_commit": target.source_commit,
        "source_repository_path": target.source_repository_path,
        "source_git_blob_sha1": target.source_git_blob_sha1,
        "source_byte_count": target.source_byte_count,
        "destination_relative_path": target.source_relative_path,
        "source_sha256": digest,
        "status": "VERIFIED_AND_FROZEN",
    }
    readiness = assess_target_readiness(target, root=tmp_path, acquisition_receipt=receipt)
    assert readiness.acquisition_receipt_verified
    assert readiness.effective_expected_sha256 == digest
    assert readiness.source_ready
    assert readiness.source_actual_observation_count == 240


def test_source_tampering_and_observation_count_are_detected(tmp_path: Path) -> None:
    source = tmp_path / "source.dat"
    source.write_text("1.0 15.0 0.01\n2.0 15.1 0.01\n", encoding="utf-8")
    target = _target_for(source, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    # Reconstruct explicitly so the expected digests remain frozen while bytes change.
    tampered = Phase09Target(
        **{
            key: getattr(target, key)
            for key in Phase09Target.__dataclass_fields__
        }
    )
    source.write_text("1.0 15.0 0.01\n2.0 15.1 0.01\n3.0 15.2 0.01\n", encoding="utf-8")
    readiness = assess_target_readiness(tampered, root=tmp_path)
    assert not readiness.source_ready
    assert "SOURCE_BYTE_COUNT_MISMATCH" in readiness.blockers
    assert "SOURCE_OBSERVATION_COUNT_MISMATCH" in readiness.blockers
    assert "SOURCE_GIT_BLOB_SHA1_MISMATCH" in readiness.blockers
    assert "SOURCE_SHA256_MISMATCH" in readiness.blockers


def test_tampered_protocol_fails_seal(tmp_path: Path) -> None:
    protocol_path = REPOSITORY_ROOT / "research/preregistration/phase09_multifamily_development_protocol.json"
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    payload["minimum_population"]["total"] = 16
    tampered = tmp_path / "protocol.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    valid, expected, actual = verify_protocol(
        tampered,
        REPOSITORY_ROOT / "research/preregistration/phase09_multifamily_development_protocol.seal.json",
    )
    assert not valid
    assert expected != actual


def test_wilson_interval_and_governance_control_are_deterministic() -> None:
    low, high = wilson_interval(3, 5)
    assert 0.0 < low < 0.6 < high < 1.0
    first = synthetic_governance_control()
    second = synthetic_governance_control()
    assert first == second
    digest = first["sha256_canonical_json"]
    payload = dict(first)
    payload.pop("sha256_canonical_json")
    assert digest == canonical_json_sha256(payload)
    assert first["object_count"] == 15


def test_wilson_interval_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        wilson_interval(1, 0)
    with pytest.raises(ValueError):
        wilson_interval(6, 5)
