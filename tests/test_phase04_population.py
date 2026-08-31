from pathlib import Path
import hashlib

import pytest

from derd.population import (
    PopulationContract,
    StratumRequirement,
    audit_population,
    build_role_manifest,
    verify_role_manifest,
)


def _contract():
    return PopulationContract(
        contract_id="test-contract",
        required_fields=(
            "star_id", "stratum", "family", "period_days", "observation_count",
            "phase_coverage_bins", "relative_path", "source_sha256",
            "source_authority", "license_or_reuse_basis",
        ),
        requirements=(
            StratumRequirement("S", "family", "test", 2, 1),
        ),
        minimum_development=2,
        minimum_sealed_holdout=1,
        minimum_clean_observations=5,
        minimum_phase_coverage_bins=3,
        star_identity_rule="one star",
        rights_rule="rights",
    )


def _records(tmp_path: Path):
    rows = []
    for index in range(3):
        path = tmp_path / f"star-{index}.dat"
        path.write_text("\n".join(str(value) for value in range(6)) + "\n")
        rows.append({
            "star_id": f"star-{index}",
            "stratum": "S",
            "family": "family",
            "period_days": "1.5",
            "observation_count": "6",
            "phase_coverage_bins": "3",
            "relative_path": path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_authority": "authority",
            "license_or_reuse_basis": "permitted",
        })
    return rows


def test_population_audit_passes_complete_small_contract(tmp_path):
    records = _records(tmp_path)
    audit = audit_population(records, _contract(), data_root=tmp_path)
    assert audit.ready_for_sealing
    assert audit.files_verified == 3
    assert audit.stratum_deficits == {"S": 0}


def test_population_audit_rejects_prior_exposure(tmp_path):
    records = _records(tmp_path)
    audit = audit_population(records, _contract(), data_root=tmp_path, exposed_star_ids={"star-1"})
    assert not audit.ready_for_sealing
    assert audit.exposed_overlap == ("star-1",)
    assert any(issue.code == "PRIOR_EXPOSURE" for issue in audit.issues)


def test_population_audit_rejects_hash_mismatch(tmp_path):
    records = _records(tmp_path)
    records[0]["source_sha256"] = "0" * 64
    audit = audit_population(records, _contract(), data_root=tmp_path)
    assert not audit.ready_for_sealing
    assert any(issue.code == "SOURCE_SHA256_MISMATCH" for issue in audit.issues)


def test_population_audit_rejects_quality_deficit(tmp_path):
    records = _records(tmp_path)
    records[0]["observation_count"] = "4"
    records[1]["phase_coverage_bins"] = "2"
    audit = audit_population(records, _contract(), data_root=tmp_path)
    codes = {issue.code for issue in audit.issues}
    assert "INSUFFICIENT_OBSERVATIONS" in codes
    assert "INSUFFICIENT_PHASE_COVERAGE" in codes


def test_population_audit_rejects_underfilled_stratum(tmp_path):
    records = _records(tmp_path)[:2]
    audit = audit_population(records, _contract(), data_root=tmp_path)
    assert audit.stratum_deficits["S"] == 1
    assert any(issue.code == "STRATUM_DEFICIT" for issue in audit.issues)


def test_population_audit_rejects_path_escape(tmp_path):
    records = _records(tmp_path)
    records[0]["relative_path"] = "../outside.dat"
    audit = audit_population(records, _contract(), data_root=tmp_path)
    assert any(issue.code == "UNSAFE_RELATIVE_PATH" for issue in audit.issues)


def test_population_role_manifest_links_and_verifies_artifacts(tmp_path):
    records = _records(tmp_path)
    contract = _contract()
    audit = audit_population(records, contract, data_root=tmp_path)
    digest = "a" * 64
    payload, seal = build_role_manifest(
        records,
        contract,
        audit,
        candidate_manifest_sha256=digest,
        contract_sha256=digest,
        analysis_plan_sha256=digest,
        code_manifest_sha256=digest,
        seed=7,
    )
    assert verify_role_manifest(payload, seal)
    assert sum(row["role"] == "sealed_holdout" for row in payload["roles"]) == 1
    payload["seed"] = 8
    assert not verify_role_manifest(payload, seal)


def test_population_role_manifest_refuses_failed_audit(tmp_path):
    records = _records(tmp_path)[:2]
    contract = _contract()
    audit = audit_population(records, contract, data_root=tmp_path)
    with pytest.raises(ValueError, match="not passed"):
        build_role_manifest(
            records,
            contract,
            audit,
            candidate_manifest_sha256="a" * 64,
            contract_sha256="a" * 64,
            analysis_plan_sha256="a" * 64,
            code_manifest_sha256="a" * 64,
        )
