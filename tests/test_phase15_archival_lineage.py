from __future__ import annotations

import json
from pathlib import Path

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase15 import (
    LINEAGE_CONFIG_DRIFT,
    Phase15Config,
    audit_archival_lineage,
    load_verified_phase14_ledger,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase15_parent_ledger_verifies() -> None:
    records, summary_sha, ledger_sha, temporal, period = load_verified_phase14_ledger(root=ROOT)
    assert len(records) == 4
    assert len(summary_sha) == 64
    assert len(ledger_sha) == 64
    assert len(temporal) == 1
    assert len(period) == 1


def test_phase15_archival_lineage_detects_configuration_sensitive_drift() -> None:
    cohort = json.loads((ROOT / "data/manifests/phase10_development_cohort.json").read_text())
    row = next(item for item in cohort["targets"] if item["object_id"] == "OGLE-LMC-CEP-0010")
    inherited = row["inherited_phase08"]
    audit, _ = audit_archival_lineage(
        root=ROOT,
        object_id="OGLE-LMC-CEP-0010",
        expected_phase08_record_sha256=inherited["canonical_target_record_sha256"],
        expected_phase08_exchange_sha256=inherited["exchange_sha256"],
    )
    assert audit.source_coordinates_match
    assert audit.phase07_source_verified
    assert audit.phase08_record_hash_verified
    assert audit.phase08_exchange_hash_verified
    assert not audit.exchange_exact
    assert audit.classification == LINEAGE_CONFIG_DRIFT
    assert audit.maximum_harmonic_snr_absolute_difference > 0.0
    assert not audit.stage_match


def test_phase15_generated_ledger_and_sidecar_are_sealed() -> None:
    summary = json.loads((ROOT / "artifacts/phase15/phase15_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.5-phase15-archival-lineage-promotion"
    assert summary["cumulative_ledger"]["cumulative_count"] == 5
    assert not summary["population_firewall"]["primary_family_outputs_allowed"]
    assert summary["archival_lineage_audit"]["classification"] == LINEAGE_CONFIG_DRIFT

    ledger_path = ROOT / summary["cumulative_ledger"]["relative_path"]
    seal_path = ROOT / summary["cumulative_ledger"]["seal_relative_path"]
    ledger = json.loads(ledger_path.read_text())
    seal = json.loads(seal_path.read_text())
    assert canonical_json_sha256(ledger) == seal["sha256_canonical_json"]
    assert seal["record_count"] == 5
    assert seal["archival_lineage_audit_count"] == 1

    ref = ledger["archival_lineage_audits"][0]
    sidecar = ROOT / ref["relative_path"]
    assert sha256_file(sidecar) == ref["file_sha256"]


def test_phase15_config_is_stable() -> None:
    assert Phase15Config().selected_object_id == "OGLE-LMC-CEP-0010"
