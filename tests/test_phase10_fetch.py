from __future__ import annotations

import hashlib

from derd.harmonic_extraction import git_blob_sha1_bytes
from derd.validation_phase09 import Phase09Target
from experiments.fetch_phase10_sources import raw_url, verify_payload


def target(data: bytes) -> Phase09Target:
    return Phase09Target(
        object_id="OGLE-LMC-CEP-TEST",
        family="classical_cepheid",
        mode="F",
        catalog_period_days=1.0,
        period_evidence_grade="EXTERNAL_CATALOG_TEST",
        mode_evidence_grade="EXTERNAL_CATALOG_TEST",
        period_source="fixture",
        metadata_identity_status="RESOLVED_EXACT",
        source_repository="owner/repository",
        source_commit="a" * 40,
        source_repository_path="path/test.dat",
        source_git_blob_sha1=git_blob_sha1_bytes(data),
        source_byte_count=len(data),
        source_observation_count=len(data.splitlines()),
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_sha256_status="FROZEN",
        source_relative_path="data/raw/test.dat",
        evidence_role="exposed-development-only",
    )


def test_commit_pinned_url() -> None:
    assert raw_url("owner/repo", "b" * 40, "x.dat") == f"https://raw.githubusercontent.com/owner/repo/{'b'*40}/x.dat"


def test_payload_verification_includes_observation_count() -> None:
    data = b"1 2 3\n2 3 4\n"
    result = verify_payload(target(data), data)
    assert result["valid"]
    assert all(result["checks"].values())


def test_payload_change_is_rejected() -> None:
    data = b"1 2 3\n"
    result = verify_payload(target(data), data + b"2 3 4\n")
    assert not result["valid"]
    assert not result["checks"]["byte_count"]
    assert not result["checks"]["observation_count"]
    assert not result["checks"]["git_blob_sha1"]
