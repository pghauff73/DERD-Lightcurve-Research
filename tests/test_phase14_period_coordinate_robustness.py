from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from derd.lightcurve import LightCurve, ValueDomain
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase13 import acquisition_candidates_from_phase08
from derd.validation_phase14 import (
    Phase14Config,
    load_verified_phase13_ledger,
    run_period_coordinate_audit,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase13_parent_ledger_and_phase14_order_are_reconstructable() -> None:
    records, summary_sha, ledger_sha, sidecars = load_verified_phase13_ledger(root=ROOT)
    assert len(records) == 3
    assert len(summary_sha) == 64
    assert ledger_sha == "c853f61700d9d6541369a8be7e13a7d7b3948c11119a7a56b569920d8ae4182f"
    assert len(sidecars) == 1
    candidates = acquisition_candidates_from_phase08(
        root=ROOT,
        excluded_object_ids=[str(row["object_id"]) for row in records],
    )
    assert candidates[0].object_id == "OGLE-LMC-CEP-0002"
    frozen = json.loads((ROOT / "data/manifests/phase14_acquisition_order.json").read_text())
    assert frozen["selected_target"]["object_id"] == candidates[0].object_id
    assert frozen["ranked_candidates"] == [candidate.as_dict() for candidate in candidates]


def test_phase14_protocol_is_sealed() -> None:
    protocol = json.loads(
        (ROOT / "research/preregistration/phase14_period_coordinate_robustness_ledger_protocol.json").read_text()
    )
    seal = json.loads(
        (ROOT / "research/preregistration/phase14_period_coordinate_robustness_ledger_protocol.seal.json").read_text()
    )
    assert canonical_json_sha256(protocol) == seal["sha256_canonical_json"]
    assert protocol["acquisition_order"]["selected_object_id"] == "OGLE-LMC-CEP-0002"
    assert protocol["denominator_firewall"]["total_records_required"] == 15
    assert protocol["period_coordinate_policy"]["refinement_objective"].startswith("generic phase-dispersion")


def test_period_coordinate_audit_is_deterministic() -> None:
    rng = np.random.default_rng(1401)
    true_period = 0.73
    catalog_period = true_period * 1.00025
    time = np.sort(rng.uniform(0.0, 180.0, 360))
    phase = np.mod(time / true_period, 1.0)
    values = (
        1.0
        + 0.25 * np.sin(2.0 * np.pi * phase)
        + 0.07 * np.cos(4.0 * np.pi * phase)
        + 0.025 * np.sin(6.0 * np.pi * phase)
        + rng.normal(0.0, 0.01, time.size)
    )
    errors = np.full(time.size, 0.01)
    curve = LightCurve(
        star_id="SYNTHETIC-P14",
        time=time,
        value=values,
        error=errors,
        domain=ValueDomain.FLUX,
        metadata={"local_sha256": "0" * 64},
    )
    config = Phase14Config(
        stationary_replicates=48,
        drift_replicates=48,
        development_fraction=0.65,
        drift_severities=(0.5, 1.0),
        temporal_random_seed=1414,
        period_surface_grid_count=21,
        period_grid_count=51,
    )
    first = run_period_coordinate_audit(
        curve,
        catalog_period=catalog_period,
        reference_epoch=0.0,
        config=config,
    )
    second = run_period_coordinate_audit(
        curve,
        catalog_period=catalog_period,
        reference_epoch=0.0,
        config=config,
    )
    assert first.as_dict() == second.as_dict()
    assert len(first.surface_rows) == 21
    assert first.refined_dispersion_score <= first.catalog_dispersion_score
    assert len(first.catalog_temporal_audit.blocks) == 3
    assert len(first.refined_temporal_audit.blocks) == 3


def test_phase14_generated_ledger_and_period_sidecar_are_sealed() -> None:
    summary = json.loads((ROOT / "artifacts/phase14/phase14_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.4-phase14-period-coordinate-robustness-ledger"
    assert summary["cumulative_ledger"]["cumulative_count"] == 4
    assert not summary["population_firewall"]["primary_family_outputs_allowed"]
    assert summary["period_coordinate_robustness"]["audit"]["classification"] == (
        "TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT"
    )

    ledger_path = ROOT / summary["cumulative_ledger"]["relative_path"]
    seal_path = ROOT / summary["cumulative_ledger"]["seal_relative_path"]
    ledger = json.loads(ledger_path.read_text())
    seal = json.loads(seal_path.read_text())
    assert canonical_json_sha256(ledger) == seal["sha256_canonical_json"]
    assert seal["record_count"] == 4
    assert seal["period_coordinate_audit_count"] == 1
    assert seal["inherited_temporal_audit_count"] == 1

    sidecar_ref = ledger["period_coordinate_audits"][0]
    sidecar_path = ROOT / sidecar_ref["relative_path"]
    assert sha256_file(sidecar_path) == sidecar_ref["file_sha256"]
    sidecar = json.loads(sidecar_path.read_text())
    without_self = {key: value for key, value in sidecar.items() if key != "sha256_canonical_json"}
    assert canonical_json_sha256(without_self) == sidecar["sha256_canonical_json"]
    assert sidecar["audit"]["object_id"] == "OGLE-LMC-CEP-0002"
