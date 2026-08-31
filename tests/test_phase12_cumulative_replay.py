from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import (
    Phase12Config,
    VerifiedLedger,
    cumulative_population_firewall,
    harmonic_exchange_projection,
    merge_cumulative_records,
    scientific_result_projection,
    verify_evidence_record,
)
from experiments.import_phase12_source_pack import verify_payload
from experiments.run_phase12 import verify_protocol


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ("classical_cepheid", "rr_lyrae", "delta_scuti")


def _declared_rows() -> tuple[SimpleNamespace, ...]:
    rows = []
    for family in FAMILIES:
        for index in range(5):
            object_id = f"{family.upper()}-{index}"
            target = SimpleNamespace(object_id=object_id, family=family)
            rows.append(SimpleNamespace(target=target, effective_object_id=object_id))
    return tuple(rows)


def _minimal_record(tmp_path: Path, *, object_id: str = "OBJECT-1", value: float = 1.0) -> dict:
    exchange = tmp_path / f"{object_id}.json"
    exchange.write_text(json.dumps({"value": value}) + "\n", encoding="utf-8")
    input_lock = {"object_id": object_id, "source_sha256": "a" * 64}
    result = {
        "target": {"object_id": object_id, "family": "rr_lyrae"},
        "stage_reached": "FORECAST_HARMONICS",
        "disposition": "ABSTAIN",
        "value": value,
    }
    return {
        "object_id": object_id,
        "declared_object_id": object_id,
        "family": "rr_lyrae",
        "input_lock": input_lock,
        "input_lock_sha256": canonical_json_sha256(input_lock),
        "result": result,
        "result_sha256": canonical_json_sha256(result),
        "exchange_relative_path": exchange.relative_to(tmp_path).as_posix(),
        "exchange_sha256": hashlib.sha256(exchange.read_bytes()).hexdigest(),
        "stage_reached": "FORECAST_HARMONICS",
        "disposition": "ABSTAIN",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
    }


def test_phase12_protocol_seal_and_parent_chain_are_valid() -> None:
    valid, expected, actual, details = verify_protocol(
        ROOT / "research/preregistration/phase12_cumulative_replay_ledger_protocol.json",
        ROOT / "research/preregistration/phase12_cumulative_replay_ledger_protocol.seal.json",
        root=ROOT,
    )
    assert valid
    assert expected == actual
    assert details["parent_summary_valid"]


def test_scientific_projection_ignores_only_transport_labels() -> None:
    first = {
        "target": {
            "object_id": "A",
            "family": "rr_lyrae",
            "source_relative_path": "old/path.dat",
            "period_source": "catalog; 0.5 d",
            "catalog_period_days": 0.5,
        },
        "result": {"score": 1.25},
    }
    second = json.loads(json.dumps(first))
    second["target"]["source_relative_path"] = "new/path.dat"
    second["target"]["period_source"] = "catalog"
    assert scientific_result_projection(first) == scientific_result_projection(second)
    second["result"]["score"] = 1.26
    assert scientific_result_projection(first) != scientific_result_projection(second)


def test_exchange_projection_ignores_phase_and_period_source_labels() -> None:
    first = {"sine_coefficients": [1.0], "metadata": {"phase": "08", "period_source": "old", "mode": "RRab"}}
    second = {"sine_coefficients": [1.0], "metadata": {"phase": "12", "period_source": "new", "mode": "RRab"}}
    assert harmonic_exchange_projection(first) == harmonic_exchange_projection(second)
    second["sine_coefficients"] = [1.1]
    assert harmonic_exchange_projection(first) != harmonic_exchange_projection(second)


def test_record_verifier_rejects_result_tampering(tmp_path: Path) -> None:
    record = _minimal_record(tmp_path)
    verified = verify_evidence_record(
        record,
        root=tmp_path,
        origin_phase="test",
        origin_summary_relative_path="summary.json",
        origin_summary_sha256="b" * 64,
    )
    assert verified["ledger_record_sha256"] == canonical_json_sha256(record)
    tampered = json.loads(json.dumps(record))
    tampered["result"]["value"] = 2.0
    with pytest.raises(ValueError, match="result digest mismatch"):
        verify_evidence_record(
            tampered,
            root=tmp_path,
            origin_phase="test",
            origin_summary_relative_path="summary.json",
            origin_summary_sha256="b" * 64,
        )


def test_cumulative_merge_rejects_conflicting_duplicate() -> None:
    first = {
        "object_id": "A",
        "input_lock_sha256": "a" * 64,
        "result_sha256": "b" * 64,
        "exchange_sha256": "c" * 64,
    }
    conflict = dict(first)
    conflict["result_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="conflicting duplicate"):
        merge_cumulative_records([first], [conflict], prior_summary_sha256="e" * 64)


def test_cumulative_firewall_remains_closed_for_two_records() -> None:
    assessment = SimpleNamespace(targets=_declared_rows())
    records = (
        {"object_id": "CLASSICAL_CEPHEID-0"},
        {"object_id": "RR_LYRAE-0"},
    )
    ledger = VerifiedLedger(
        records=records,
        prior_summary_sha256="a" * 64,
        prior_record_count=1,
        new_record_count=1,
    )
    result = cumulative_population_firewall(assessment, ledger)
    assert result["cumulative_record_count"] == 2
    assert not result["primary_family_outputs_allowed"]
    counts = {row["family"]: row["cumulative_record_count"] for row in result["family_coverage"]}
    assert counts == {"classical_cepheid": 1, "delta_scuti": 0, "rr_lyrae": 1}


def test_phase12_source_payload_verifies_frozen_dimensions() -> None:
    data = b"1.0 18.0 0.1\n2.0 18.1 0.1\n"
    from derd.harmonic_extraction import git_blob_sha1_bytes

    target = SimpleNamespace(
        source_byte_count=len(data),
        source_observation_count=2,
        source_git_blob_sha1=git_blob_sha1_bytes(data),
        source_sha256=hashlib.sha256(data).hexdigest(),
    )
    result = verify_payload(target, data)
    assert result["valid"]
    assert all(result["checks"].values())


def test_phase12_recorded_replay_is_scientifically_exact() -> None:
    summary = json.loads((ROOT / "artifacts/phase12/phase12_summary.json").read_text(encoding="utf-8"))
    audit = summary["replay_audits"]
    assert len(audit) == 1
    row = audit[0]
    assert row["object_id"] == "OGLE-LMC-RRLYR-00001"
    assert row["status"] == "SCIENTIFIC_REPLAY_MATCH_METADATA_TRANSPORT_DRIFT"
    assert row["scientific_match"]
    assert row["exchange_match"]
    assert row["maximum_harmonic_snr_absolute_difference"] == 0.0
    assert row["screen_score_difference"] == 0.0
    assert row["threshold_difference"] == 0.0


def test_phase12_config_defaults_preserve_phase11_scientific_coordinates() -> None:
    config = Phase12Config()
    phase11 = config.phase11()
    assert phase11.synthetic_samples_per_class == 96
    assert phase11.propagation_draws == 2048
    assert phase11.period_grid_count == 101
    assert phase11.minimum_observations == 240
