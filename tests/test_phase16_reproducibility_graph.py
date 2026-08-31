from __future__ import annotations

import json
from pathlib import Path

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase16 import (
    EDGE_CONFIG_DRIFT,
    EDGE_EXACT,
    build_reproducibility_graph,
    load_verified_phase15_ledger,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase16_parent_ledger_verifies() -> None:
    records, summary_sha, ledger_sha, ledger, lineage = load_verified_phase15_ledger(root=ROOT)
    assert len(records) == 5
    assert len(summary_sha) == 64
    assert len(ledger_sha) == 64
    assert ledger["cumulative_count"] == 5
    assert lineage["object_id"] == "OGLE-LMC-CEP-0010"


def test_phase16_graph_counts_and_multiplicity_guard() -> None:
    records, _, _, _, lineage = load_verified_phase15_ledger(root=ROOT)
    graph = build_reproducibility_graph(root=ROOT, ledger_records=records, phase15_lineage=lineage)
    assert graph.unique_object_denominator == 5
    assert graph.analysis_version_count == 9
    assert graph.duplicate_analysis_inflation_prevented == 4
    assert graph.exact_replay_count == 3
    assert graph.configuration_drift_count == 1
    assert graph.external_independent_replication_count == 0
    assert graph.single_version_objects == ("OGLE-LMC-CEP-0004",)
    assert sum(edge.classification == EDGE_EXACT for edge in graph.edges) == 3
    assert sum(edge.classification == EDGE_CONFIG_DRIFT for edge in graph.edges) == 1
    assert all(not edge.counts_as_independent_astrophysical_replication for edge in graph.edges)


def test_phase16_generated_graph_and_ledger_are_sealed() -> None:
    summary = json.loads((ROOT / "artifacts/phase16/phase16_summary.json").read_text())
    assert summary["implementation_id"] == "DERD-v1.6-phase16-reproducibility-graph"
    graph = summary["reproducibility_graph"]
    assert graph["unique_object_denominator"] == 5
    assert graph["analysis_version_count"] == 9
    assert graph["exact_replay_count"] == 3
    assert graph["configuration_drift_count"] == 1
    assert not summary["population_firewall"]["primary_family_outputs_allowed"]

    graph_path = ROOT / "artifacts/phase16/phase16_reproducibility_graph.json"
    graph_file = json.loads(graph_path.read_text())
    without_self = {key: value for key, value in graph_file.items() if key != "sha256_canonical_json"}
    assert canonical_json_sha256(without_self) == graph_file["sha256_canonical_json"]

    ledger_path = ROOT / summary["cumulative_ledger"]["relative_path"]
    seal_path = ROOT / summary["cumulative_ledger"]["seal_relative_path"]
    ledger = json.loads(ledger_path.read_text())
    seal = json.loads(seal_path.read_text())
    assert canonical_json_sha256(ledger) == seal["sha256_canonical_json"]
    assert seal["record_count"] == 5
    ref = ledger["reproducibility_graphs"][0]
    assert sha256_file(ROOT / ref["relative_path"]) == ref["file_sha256"]
