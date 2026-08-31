from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase18 import (
    CLASS_PUBLICATION_COMPATIBLE,
    PARAMETER_LABELS,
    fit_curve_fit_invariants,
    load_three_column,
    merge_photometry,
    verify_source_component,
)

ROOT = Path(__file__).resolve().parents[1]


def _circular_error(left: float, right: float) -> float:
    return float(np.angle(np.exp(1j * (left - right))))


def test_curve_fit_recovers_synthetic_cosine_invariants() -> None:
    period = 2.75
    time = np.linspace(0.0, 20.0 * period, 500, endpoint=False)
    phase = time / period
    amplitudes = np.array([0.4, 0.12, 0.06])
    angles = np.array([0.8, 2.2, 4.9])
    magnitude = np.full(time.size, 15.0)
    for harmonic, (amplitude, angle) in enumerate(zip(amplitudes, angles, strict=True), start=1):
        magnitude += amplitude * np.cos(2.0 * math.pi * harmonic * phase + angle)
    error = np.full(time.size, 0.01)
    photometry = np.column_stack([time, magnitude, error])
    estimate = fit_curve_fit_invariants(
        photometry,
        variant_id="synthetic",
        source_scope="synthetic",
        center_period_days=period,
        weighting="quoted_absolute",
        period_mode="free",
    )
    assert np.isclose(estimate.period_days, period, atol=1e-9)
    assert np.isclose(estimate.vector[0], amplitudes[1] / amplitudes[0], atol=1e-9)
    assert np.isclose(estimate.vector[2], amplitudes[2] / amplitudes[0], atol=1e-9)
    assert abs(_circular_error(estimate.vector[1], angles[1] - 2.0 * angles[0])) < 1e-8
    assert abs(_circular_error(estimate.vector[3], angles[2] - 3.0 * angles[0])) < 1e-8


def test_merge_is_strictly_chronological() -> None:
    left = np.array([[1.0, 2.0, 0.1], [3.0, 4.0, 0.1]])
    right = np.array([[2.0, 3.0, 0.1], [4.0, 5.0, 0.1]])
    merged = merge_photometry(left, right)
    assert merged.shape == (4, 3)
    assert np.array_equal(merged[:, 0], [1.0, 2.0, 3.0, 4.0])


def test_source_component_verification(tmp_path: Path) -> None:
    source = tmp_path / "source.dat"
    source.write_text("1.00000 2.000 0.100\n2.00000 3.000 0.100\n", encoding="utf-8")
    payload = source.read_bytes()
    expected = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_blob_sha1": hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest(),
        "byte_count": len(payload),
        "observation_count": 2,
        "first_time": 1.0,
        "last_time": 2.0,
    }
    result = verify_source_component(source, expected)
    assert result["all_checks_passed"]
    assert load_three_column(source).shape == (2, 3)


def test_phase18_protocol_and_source_manifest_are_sealed() -> None:
    protocol = json.loads(
        (ROOT / "research/preregistration/phase18_exact_external_input_reconstruction_protocol.json").read_text()
    )
    seal = json.loads(
        (ROOT / "research/preregistration/phase18_exact_external_input_reconstruction_protocol.seal.json").read_text()
    )
    assert canonical_json_sha256(protocol) == seal["sha256_canonical_json"]
    manifest = json.loads((ROOT / "data/manifests/phase18_external_input_manifest.json").read_text())
    expected = manifest.pop("sha256_canonical_json")
    assert canonical_json_sha256(manifest) == expected
    assert manifest["merged"]["observation_count"] == 65
    assert manifest["merged"]["meets_publication_minimum"]


def test_phase18_generated_result_passes_publication_vector_gate() -> None:
    summary = json.loads((ROOT / "artifacts/phase18/phase18_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.8-phase18-exact-external-input-reconstruction"
    assert summary["classification"] == CLASS_PUBLICATION_COMPATIBLE
    assert summary["source_scope"]["merged_observations"] == 65
    assert summary["source_scope"]["publication_minimum_met"]
    assert summary["all_merged_variants_consistent"]
    audit = summary["primary_reconstruction"]["audit"]
    assert audit["joint_pass"]
    assert audit["marginal_pass"]
    assert audit["p_value"] > 0.05
    assert max(abs(value) for value in audit["marginal_z"].values()) < 2.0


def test_phase18_preserves_denominator_and_replication_boundary() -> None:
    summary = json.loads((ROOT / "artifacts/phase18/phase18_summary.json").read_text())
    assert summary["population_firewall"]["astronomical_denominator"] == 5
    assert summary["population_firewall"]["independent_astrophysical_replication_count"] == 0
    assert not summary["population_firewall"]["family_outputs_allowed"]
    graph = summary["reproducibility_graph"]
    graph_copy = dict(graph)
    expected = graph_copy.pop("sha256_canonical_json")
    assert canonical_json_sha256(graph_copy) == expected
    assert graph["phase18_multiplicity_guard"]["external_input_reconstruction_does_not_increment_denominator"]
    assert len(PARAMETER_LABELS) == 4
