from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase19 import (
    PHASE19_CLASSIFICATION,
    PHASE19_DECISION,
    canonical_sha256,
    evaluate_task,
    verify_submission_self_hash,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase19_protocol_is_sealed_and_committed() -> None:
    protocol = json.loads(
        (ROOT / "research/preregistration/phase19_external_group_replay_protocol.json").read_text()
    )
    seal = json.loads(
        (ROOT / "research/preregistration/phase19_external_group_replay_protocol.seal.json").read_text()
    )
    assert canonical_json_sha256(protocol) == seal["sha256_canonical_json"]
    commitment = protocol["blind_answer_commitment"]
    assert commitment["algorithm"] == "HMAC-SHA256"
    assert len(commitment["hmac_sha256"]) == 64
    assert not commitment["private_key_disclosed_in_public_kit"]
    assert not commitment["private_answer_key_disclosed_in_public_kit"]


def test_phase19_task_manifest_is_self_sealed_and_complete() -> None:
    manifest_path = ROOT / "data/manifests/phase19_replication_tasks.json"
    manifest = json.loads(manifest_path.read_text())
    declared = manifest.pop("sha256_canonical_json")
    assert canonical_json_sha256(manifest) == declared
    seal = json.loads(
        (ROOT / "data/manifests/phase19_replication_tasks.seal.json").read_text()
    )
    assert seal["sha256_canonical_json"] == declared
    assert manifest["task_count"] == 7
    assert manifest["task_types"] == {
        "synthetic_photometry": 4,
        "observational_exchange": 3,
    }
    assert len({task["task_id"] for task in manifest["tasks"]}) == 7
    assert not manifest["answer_labels_disclosed"]
    assert not manifest["raw_third_party_photometry_included"]


def test_phase19_every_public_input_matches_declared_hash() -> None:
    manifest = json.loads((ROOT / "data/manifests/phase19_replication_tasks.json").read_text())
    for task in manifest["tasks"]:
        path = ROOT / "replication/phase19/inputs" / task["input_path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == task["input_sha256"]


def test_phase19_one_synthetic_and_one_exchange_task_are_deterministic() -> None:
    manifest = json.loads((ROOT / "data/manifests/phase19_replication_tasks.json").read_text())
    chosen = []
    for task_type in ("synthetic_photometry", "observational_exchange"):
        task = next(row for row in manifest["tasks"] if row["task_type"] == task_type)
        path = ROOT / "replication/phase19/inputs" / task["input_path"]
        left = evaluate_task(task, path)
        right = evaluate_task(task, path)
        assert left.projection_sha256 == right.projection_sha256
        assert canonical_sha256(left.projection) == left.projection_sha256
        chosen.append(left)
    assert len(chosen) == 2


def test_phase19_public_kit_contains_no_private_answer_material() -> None:
    kit = ROOT / "release/phase19/DERD_Phase19_External_Replication_Kit.zip"
    assert kit.is_file()
    with zipfile.ZipFile(kit) as archive:
        names = archive.namelist()
        lowered = [name.lower() for name in names]
        assert "kit_sha256sums.txt" in lowered
        assert not any("answer_key" in name for name in lowered)
        assert not any("commitment_key" in name for name in lowered)
        assert not any("private_evaluator" in name for name in lowered)
        assert not any(name.endswith(".complete.dat") for name in lowered)


def test_phase19_public_kit_checksums_verify() -> None:
    kit = ROOT / "release/phase19/DERD_Phase19_External_Replication_Kit.zip"
    with zipfile.ZipFile(kit) as archive:
        manifest = archive.read("KIT_SHA256SUMS.txt").decode("utf-8")
        for line in manifest.splitlines():
            expected, relative = line.split("  ", 1)
            assert hashlib.sha256(archive.read(relative)).hexdigest() == expected


def test_phase19_local_control_passes_but_is_not_external() -> None:
    control = json.loads(
        (ROOT / "artifacts/phase19/phase19_local_cleanroom_control.json").read_text()
    )
    assert control["all_tasks_passed"]
    assert control["task_count"] == 7
    assert control["answer_labels_redacted"]
    assert not control["answer_key_disclosed"]
    assert not control["counts_as_external_computational_replication"]
    assert not control["counts_as_independent_astrophysical_replication"]


def test_phase19_summary_and_graph_preserve_boundaries() -> None:
    summary = json.loads((ROOT / "artifacts/phase19/phase19_summary.json").read_text())
    assert summary["decision"] == PHASE19_DECISION
    assert summary["classification"] == PHASE19_CLASSIFICATION
    assert summary["local_cleanroom_control"]["all_tasks_passed"]
    assert summary["external_operator"]["verified_submission_count"] == 0
    assert not summary["external_operator"]["external_computational_replication_edge_added"]
    firewall = summary["population_firewall"]
    assert firewall["unique_astronomical_objects"] == 5
    assert firewall["external_computational_replication_count"] == 0
    assert firewall["external_independent_replication_count"] == 0
    assert not firewall["family_outputs_allowed"]
    assert not firewall["c17_promoted"]
    graph = summary["reproducibility_graph"]
    graph_copy = dict(graph)
    declared = graph_copy.pop("sha256_canonical_json")
    assert canonical_json_sha256(graph_copy) == declared
    assert graph["external_computational_replication_count"] == 0
    assert graph["external_independent_replication_count"] == 0
    assert graph["unique_object_denominator"] == 5


def test_phase19_submission_self_hash_contract() -> None:
    payload = {
        "submission_schema": "DERD-PHASE19-EXTERNAL-SUBMISSION-1.0",
        "kit_id": "example",
        "operator": {},
        "environment": {},
        "task_results": [],
    }
    payload["submission_sha256"] = canonical_sha256(payload)
    assert verify_submission_self_hash(payload)
    payload["kit_id"] = "tampered"
    assert not verify_submission_self_hash(payload)


def test_private_material_is_not_tracked_in_repository() -> None:
    forbidden = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if "phase19_answer_key" in name or "phase19_commitment_key" in name:
            forbidden.append(path)
    assert forbidden == []
