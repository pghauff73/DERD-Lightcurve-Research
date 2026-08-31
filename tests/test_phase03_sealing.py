import json
import pytest

from derd.sealing import (
    assert_no_sealed_evaluation,
    canonical_json,
    seal_payload,
    stratified_role_partition,
    verify_seal,
)


def _records():
    return [
        {"star_id": f"A-{index}", "stratum": "A"} for index in range(5)
    ] + [
        {"star_id": f"B-{index}", "stratum": "B"} for index in range(5)
    ]


def test_seal_is_canonical_and_detects_mutation():
    payload = {"b": 2, "a": [3, 1]}
    seal = seal_payload(payload)
    assert canonical_json(payload) == '{"a":[3,1],"b":2}'
    assert verify_seal(payload, seal.digest)
    assert not verify_seal({"b": 3, "a": [3, 1]}, seal.digest)


def test_stratified_partition_is_deterministic_and_balanced():
    records = _records()
    first = stratified_role_partition(records, sealed_per_stratum=2, minimum_development_per_stratum=3, seed=9)
    second = stratified_role_partition(list(reversed(records)), sealed_per_stratum=2, minimum_development_per_stratum=3, seed=9)
    assert first == second
    for prefix in ("A", "B"):
        assert sum(role == "sealed_holdout" for star, role in first.items() if star.startswith(prefix)) == 2


def test_sealed_evaluation_guard_blocks_overlap():
    roles = {"A": "development", "B": "sealed_holdout"}
    assert_no_sealed_evaluation(["A"], roles)
    with pytest.raises(PermissionError, match="B"):
        assert_no_sealed_evaluation(["A", "B"], roles)


def test_stratified_partition_rejects_duplicate_ids():
    records = [{"star_id": "A", "stratum": "x"}, {"star_id": "A", "stratum": "x"}]
    with pytest.raises(ValueError, match="unique"):
        stratified_role_partition(records, sealed_per_stratum=1, minimum_development_per_stratum=1)


def test_stratified_partition_rejects_underfilled_stratum():
    with pytest.raises(ValueError, match="requires"):
        stratified_role_partition(
            [{"star_id": "A", "stratum": "x"}],
            sealed_per_stratum=1,
            minimum_development_per_stratum=1,
        )
