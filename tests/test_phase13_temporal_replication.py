from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from derd.harmonic_evidence import fit_signed_harmonics
from derd.lightcurve import LightCurve, ValueDomain
from derd.validation_phase13 import (
    Phase13Config,
    acquisition_candidates_from_phase08,
    load_verified_phase12_ledger,
    pairwise_temporal_test,
    run_temporal_replication_audit,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase12_parent_ledger_and_acquisition_order_are_reconstructable() -> None:
    records, summary_sha, ledger_sha = load_verified_phase12_ledger(root=ROOT)
    assert len(records) == 2
    assert len(summary_sha) == 64
    assert ledger_sha == "5a1e582967576e72985c1b15200a4852eff1044f553e1e0fb3ae937ddab46211"
    candidates = acquisition_candidates_from_phase08(
        root=ROOT,
        excluded_object_ids=[str(row["object_id"]) for row in records],
    )
    assert candidates[0].object_id == "OGLE-LMC-RRLYR-00004"
    assert candidates[0].priority > candidates[1].priority
    frozen = json.loads((ROOT / "data/manifests/phase13_acquisition_order.json").read_text())
    assert frozen["selected_target"]["object_id"] == candidates[0].object_id


def test_identical_harmonic_fits_have_zero_pairwise_temporal_score() -> None:
    time = np.linspace(0.0, 10.0, 160, endpoint=False)
    period = 0.8
    phase = np.mod(time / period, 1.0)
    values = 1.0 + 0.2 * np.sin(2.0 * np.pi * phase) + 0.04 * np.cos(4.0 * np.pi * phase)
    errors = np.full(time.size, 0.01)
    fit = fit_signed_harmonics(
        time,
        values,
        errors,
        period=period,
        reference_epoch=0.0,
        order=8,
    )
    result = pairwise_temporal_test(
        fit, fit, block_a=0, block_b=1, harmonics=4
    )
    assert result.wald_statistic == 0.0
    assert result.normalized_score == 0.0
    assert result.p_value == 1.0


def test_temporal_audit_is_deterministic_and_emits_three_blocks() -> None:
    rng = np.random.default_rng(9123)
    period = 0.71
    time = np.sort(rng.uniform(0.0, 120.0, 360))
    phase = np.mod(time / period, 1.0)
    values = (
        1.0
        + 0.25 * np.sin(2.0 * np.pi * phase)
        + 0.07 * np.cos(4.0 * np.pi * phase)
        + 0.025 * np.sin(6.0 * np.pi * phase)
        + rng.normal(0.0, 0.01, time.size)
    )
    errors = np.full(time.size, 0.01)
    curve = LightCurve(
        star_id="SYNTHETIC-P13",
        time=time,
        value=values,
        error=errors,
        domain=ValueDomain.FLUX,
        metadata={"local_sha256": "0" * 64},
    )
    config = Phase13Config(
        minimum_block_observations=100,
        stationary_replicates=48,
        drift_replicates=48,
        development_fraction=0.65,
        drift_severities=(0.5, 1.0),
        random_seed=42,
    )
    first = run_temporal_replication_audit(
        curve, period=period, reference_epoch=0.0, config=config
    )
    second = run_temporal_replication_audit(
        curve, period=period, reference_epoch=0.0, config=config
    )
    assert len(first.blocks) == 3
    assert all(row.observation_count == 120 for row in first.blocks)
    assert len(first.pairwise_tests) == 3
    assert len(first.calibration_rows) == 2
    assert first.as_dict() == second.as_dict()


def test_phase13_protocol_is_sealed() -> None:
    from derd.ogle_catalog import canonical_json_sha256

    protocol = json.loads(
        (ROOT / "research/preregistration/phase13_temporal_replication_ledger_protocol.json").read_text()
    )
    seal = json.loads(
        (ROOT / "research/preregistration/phase13_temporal_replication_ledger_protocol.seal.json").read_text()
    )
    assert canonical_json_sha256(protocol) == seal["sha256_canonical_json"]
    assert protocol["denominator_firewall"]["total_records_required"] == 15


def test_phase13_generated_ledger_and_temporal_sidecar_are_sealed() -> None:
    from derd.ogle_catalog import canonical_json_sha256
    from derd.validation_phase12 import sha256_file

    summary = json.loads((ROOT / "artifacts/phase13/phase13_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.3-phase13-temporal-replication-ledger"
    assert summary["cumulative_ledger"]["cumulative_count"] == 3
    assert not summary["population_firewall"]["primary_family_outputs_allowed"]

    ledger_path = ROOT / summary["cumulative_ledger"]["relative_path"]
    seal_path = ROOT / summary["cumulative_ledger"]["seal_relative_path"]
    ledger = json.loads(ledger_path.read_text())
    seal = json.loads(seal_path.read_text())
    assert canonical_json_sha256(ledger) == seal["sha256_canonical_json"]
    assert seal["record_count"] == 3
    assert seal["temporal_audit_count"] == 1

    sidecar_ref = ledger["temporal_audits"][0]
    sidecar_path = ROOT / sidecar_ref["relative_path"]
    assert sha256_file(sidecar_path) == sidecar_ref["file_sha256"]
    sidecar = json.loads(sidecar_path.read_text())
    sidecar_without_self = {
        key: value for key, value in sidecar.items() if key != "sha256_canonical_json"
    }
    assert canonical_json_sha256(sidecar_without_self) == sidecar["sha256_canonical_json"]
    assert sidecar["audit"]["disposition"] == "TEMPORAL_REPLICATION_NOT_SUPPORTED"
