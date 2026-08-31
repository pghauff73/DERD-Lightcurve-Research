from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from derd.harmonic_extraction import git_blob_sha1_bytes
from derd.validation_phase11 import (
    PHASE11_DECISION_BLOCKED,
    PHASE11_DECISION_COMPLETE,
    PHASE11_DECISION_UNLOCKED,
    Phase11Config,
    config_sha256,
    frontier_rows,
    phase11_decision,
    population_firewall,
)
from experiments.import_phase11_source_pack import candidate_paths, verify_payload
from experiments.run_phase11 import verify_protocol


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ("classical_cepheid", "rr_lyrae", "delta_scuti")


def _row(
    family: str,
    index: int,
    *,
    metadata_ready: bool = True,
    source_ready: bool = True,
    cached_result_ready: bool = False,
) -> SimpleNamespace:
    object_id = f"{family.upper()}-{index}"
    target = SimpleNamespace(object_id=object_id, family=family)
    return SimpleNamespace(
        target=target,
        effective_object_id=object_id,
        metadata_ready=metadata_ready,
        source_ready=source_ready,
        cached_result_ready=cached_result_ready,
        execution_ready=metadata_ready and source_ready,
        blockers=() if metadata_ready and source_ready else ("LOCK_REQUIRED",),
    )


def _declared_rows() -> list[SimpleNamespace]:
    return [_row(family, index) for family in FAMILIES for index in range(5)]


def test_phase11_protocol_seal_is_valid() -> None:
    valid, expected, actual = verify_protocol(
        ROOT / "research/preregistration/phase11_progressive_evidence_unlock_protocol.json",
        ROOT / "research/preregistration/phase11_progressive_evidence_unlock_protocol.seal.json",
    )
    assert valid
    assert expected == actual


def test_phase11_config_digest_is_deterministic_and_changes_with_coordinates() -> None:
    first = Phase11Config()
    assert config_sha256(first) == config_sha256(Phase11Config())
    assert config_sha256(first) != config_sha256(Phase11Config(minimum_observations=241))


def test_population_firewall_suppresses_partial_family_denominators() -> None:
    declared = _declared_rows()
    fresh = [declared[0].target.object_id]
    result = population_firewall(declared, fresh)
    assert not result["complete_cohort_denominator"]
    assert not result["primary_family_outputs_allowed"]
    assert sum(row["fresh_execution_count"] for row in result["family_coverage"]) == 1
    assert all(row["fractions_suppressed"] for row in result["family_coverage"])


def test_population_firewall_opens_only_after_all_fifteen_fresh_executions() -> None:
    declared = _declared_rows()
    fresh = [row.target.object_id for row in declared]
    result = population_firewall(declared, fresh)
    assert result["complete_cohort_denominator"]
    assert result["primary_family_outputs_allowed"]
    assert all(row["family_denominator_complete"] for row in result["family_coverage"])
    assert all(not row["fractions_suppressed"] for row in result["family_coverage"])


def test_frontier_states_keep_pending_and_ready_targets_visible() -> None:
    assessment = SimpleNamespace(
        targets=(
            _row("classical_cepheid", 0, metadata_ready=True, source_ready=True),
            _row("rr_lyrae", 0, metadata_ready=True, source_ready=False),
            _row("delta_scuti", 0, metadata_ready=False, source_ready=True),
            _row("delta_scuti", 1, metadata_ready=False, source_ready=False),
        )
    )
    rows = frontier_rows(assessment, ["CLASSICAL_CEPHEID-0"])
    assert [row["frontier"] for row in rows] == [
        "FRESH_EXECUTED",
        "SOURCE_LOCK_REQUIRED",
        "METADATA_LOCK_REQUIRED",
        "METADATA_AND_SOURCE_LOCKS_REQUIRED",
    ]


def test_phase11_decision_distinguishes_blocked_partial_and_complete() -> None:
    declared = _declared_rows()
    assessment = SimpleNamespace(targets=tuple(declared))
    assert phase11_decision(assessment, None) == PHASE11_DECISION_BLOCKED
    one = SimpleNamespace(fresh_execution_count=1, records=({"object_id": declared[0].target.object_id},))
    assert phase11_decision(assessment, one) == PHASE11_DECISION_UNLOCKED
    complete = SimpleNamespace(
        fresh_execution_count=15,
        records=tuple({"object_id": row.target.object_id} for row in declared),
    )
    assert phase11_decision(assessment, complete) == PHASE11_DECISION_COMPLETE


def test_progressive_source_payload_verifies_all_frozen_dimensions() -> None:
    data = b"1.0 15.0 0.1\n2.0 15.1 0.1\n"
    target = SimpleNamespace(
        source_byte_count=len(data),
        source_observation_count=2,
        source_git_blob_sha1=git_blob_sha1_bytes(data),
        source_sha256=hashlib.sha256(data).hexdigest(),
    )
    result = verify_payload(target, data)
    assert result["valid"]
    assert all(result["checks"].values())
    changed = verify_payload(target, data + b"3.0 15.2 0.1\n")
    assert not changed["valid"]


def test_progressive_pack_candidate_order_prefers_complete_filename(tmp_path: Path) -> None:
    paths = candidate_paths(tmp_path, "OGLE-LMC-CEP-0004", "Cluster/cep/phot/I/OGLE-LMC-CEP-0004.dat")
    assert paths[0].name == "OGLE-LMC-CEP-0004.complete.dat"
    assert paths[1].name == "OGLE-LMC-CEP-0004.dat"
    assert paths[2].name == "OGLE-LMC-CEP-0004.dat"


def test_progressive_receipt_profile_remains_phase09_assessor_compatible() -> None:
    source = (ROOT / "experiments/import_phase11_source_pack.py").read_text(encoding="utf-8")
    assert '"receipt_id": "PHASE09-SOURCE-ACQUISITION-RECEIPT-V1"' in source
    assert '"receipt_profile": "PHASE11-PROGRESSIVE-SOURCE-LOCK-RECEIPT-V1"' in source
