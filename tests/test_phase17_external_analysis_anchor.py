from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase17 import (
    EDGE_EXTERNAL_CONSISTENT_PARTIAL,
    ExternalFourierAnchor,
    FourierInvariantEstimate,
    compare_external_anchor,
    extend_reproducibility_graph,
    fit_weighted_cosine_series,
    load_external_anchor,
    verify_source,
)

ROOT = Path(__file__).resolve().parents[1]


def _circular_difference(left: float, right: float) -> float:
    return float(np.angle(np.exp(1j * (left - right))))


def test_cosine_invariants_recovered_from_signed_series() -> None:
    period = 2.3
    time = np.linspace(0.0, 10.0 * period, 600, endpoint=False)
    phase = np.mod(time / period, 1.0)
    amplitudes = np.array([0.4, 0.13, 0.07])
    phases = np.array([0.8, 2.4, 5.2])
    values = np.full(time.size, 15.0)
    for harmonic, (amplitude, angle) in enumerate(zip(amplitudes, phases, strict=True), start=1):
        values += amplitude * np.cos(2.0 * math.pi * harmonic * phase + angle)
    error = np.full(time.size, 0.01)
    fit = fit_weighted_cosine_series(time, values, error, period_days=period, reference_epoch=0.0)
    inv = fit["invariants"]
    assert np.isclose(inv["r21"], amplitudes[1] / amplitudes[0], atol=1e-12)
    assert np.isclose(inv["r31"], amplitudes[2] / amplitudes[0], atol=1e-12)
    assert abs(_circular_difference(inv["phi21"], phases[1] - 2.0 * phases[0])) < 1e-12
    assert abs(_circular_difference(inv["phi31"], phases[2] - 3.0 * phases[0])) < 1e-12


def test_partial_overlap_consistency_classification() -> None:
    anchor = ExternalFourierAnchor(
        object_id="STAR",
        object_type="DCEP-F",
        period_days=3.0,
        r21=0.30,
        r21_error=0.02,
        phi21=4.0,
        phi21_error=0.10,
        r31=0.12,
        r31_error=0.02,
        phi31=2.0,
        phi31_error=0.10,
        citation="example",
        doi="example",
        arxiv_id="example",
        band="V",
        method_summary="example",
        minimum_measurements=50,
        source_scope="example",
    )
    estimate = FourierInvariantEstimate(
        object_id="STAR",
        period_days=3.0,
        period_bootstrap_standard_error_days=1e-4,
        reference_epoch=0.0,
        r21=0.31,
        phi21=4.02,
        r31=0.13,
        phi31=2.02,
        covariance=np.diag([0.02**2, 0.10**2, 0.02**2, 0.10**2]),
        bootstrap_mean=np.array([0.31, 4.02, 0.13, 2.02]),
        bootstrap_standard_error=np.array([0.02, 0.10, 0.02, 0.10]),
        bootstrap_percentile_95=np.array([[0.27, 3.82, 0.09, 1.82], [0.35, 4.22, 0.17, 2.22]]),
        sample_count=33,
        bootstrap_sample_count=20,
        bootstrap_draws=100,
        residual_rmse_mag=0.01,
        weighted_reduced_chi_square=1.0,
        design_condition_number=2.0,
    )
    audit = compare_external_anchor(estimate, anchor)
    assert audit.classification == EDGE_EXTERNAL_CONSISTENT_PARTIAL
    assert audit.joint_consistency_at_5_percent
    assert not audit.local_source_meets_external_minimum_count
    assert not audit.counts_as_independent_astrophysical_replication
    assert not audit.counts_as_astronomical_denominator_increment


def test_source_verification_uses_git_blob_and_sha256(tmp_path: Path) -> None:
    source = tmp_path / "source.dat"
    source.write_text("1 2 0.1\n2 3 0.1\n", encoding="utf-8")
    data = source.read_bytes()
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    result = verify_source(
        source,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        expected_git_blob_sha1=blob,
        expected_bytes=len(data),
        expected_observations=2,
    )
    assert result["all_checks_passed"]


def test_generated_external_anchor_and_audit_are_sealed() -> None:
    anchor_path = ROOT / "data/evidence/phase17_jurkovic2022_vband_anchor.json"
    anchor_payload = json.loads(anchor_path.read_text())
    expected = anchor_payload.pop("sha256_canonical_json")
    assert canonical_json_sha256(anchor_payload) == expected
    anchor = load_external_anchor(anchor_path)
    assert anchor.object_id == "OGLE-LMC-CEP-0002"
    assert anchor.minimum_measurements == 50

    audit_path = ROOT / "artifacts/phase17/phase17_external_analysis_audit.json"
    audit = json.loads(audit_path.read_text())
    expected_audit = audit.pop("sha256_canonical_json")
    assert canonical_json_sha256(audit) == expected_audit
    assert audit["classification"] == EDGE_EXTERNAL_CONSISTENT_PARTIAL
    assert audit["joint_consistency_at_5_percent"]
    assert audit["p_value"] > 0.05
    assert max(abs(value) for value in audit["marginal_z"].values()) < 2.0
    assert not audit["counts_as_independent_astrophysical_replication"]


def test_phase17_graph_preserves_denominator_and_external_independence_zero() -> None:
    summary = json.loads((ROOT / "artifacts/phase17/phase17_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.7-phase17-external-analysis-anchor"
    graph = summary["reproducibility_graph"]
    assert graph["unique_object_denominator"] == 5
    assert graph["analysis_version_count"] == 11
    assert graph["duplicate_analysis_inflation_prevented"] == 6
    assert graph["external_analysis_consistency_count"] == 1
    assert graph["external_independent_replication_count"] == 0
    assert not summary["population_firewall"]["primary_family_outputs_allowed"]

    graph_copy = dict(graph)
    expected = graph_copy.pop("sha256_canonical_json")
    assert canonical_json_sha256(graph_copy) == expected


def test_extend_graph_has_no_denominator_increment() -> None:
    phase16 = json.loads((ROOT / "artifacts/phase16/phase16_reproducibility_graph.json").read_text())
    audit_payload = json.loads((ROOT / "artifacts/phase17/phase17_external_analysis_audit.json").read_text())
    # Use generated graph as the authoritative execution check and test invariants.
    generated = json.loads((ROOT / "artifacts/phase17/phase17_reproducibility_graph.json").read_text())
    assert len(generated["analysis_nodes"]) == len(phase16["analysis_nodes"]) + 2
    assert len(generated["edges"]) == len(phase16["edges"]) + 1
    assert generated["phase17_external_anchor"]["classification"] == audit_payload["classification"]
    assert generated["unique_object_denominator"] == phase16["unique_object_denominator"]
