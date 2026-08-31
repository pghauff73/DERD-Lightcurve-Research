from __future__ import annotations

import hashlib
from pathlib import Path

from derd.harmonic_extraction import git_blob_sha1_bytes
from derd.validation_phase09 import Phase09Target
from experiments.fetch_phase09_sources import raw_url, verify_payload


def _target(data: bytes) -> Phase09Target:
    return Phase09Target(
        object_id="OGLE-LMC-CEP-TEST",
        family="classical_cepheid",
        mode="F",
        catalog_period_days=1.0,
        period_evidence_grade="EXTERNAL_CATALOG_TEST",
        mode_evidence_grade="EXTERNAL_CATALOG_TEST",
        period_source="test",
        metadata_identity_status="RESOLVED_EXACT",
        source_repository="owner/repository",
        source_commit="a" * 40,
        source_repository_path="path/lightcurve.dat",
        source_git_blob_sha1=git_blob_sha1_bytes(data),
        source_byte_count=len(data),
        source_observation_count=len(data.splitlines()),
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_sha256_status="FROZEN",
        source_relative_path="data/raw/phase09_cohort/test.complete.dat",
        evidence_role="exposed-development-only",
    )


def test_raw_url_is_commit_pinned() -> None:
    target = _target(b"1 2 3\n")
    assert raw_url(
        target.source_repository,
        target.source_commit,
        target.source_repository_path,
    ) == (
        "https://raw.githubusercontent.com/owner/repository/"
        + "a" * 40
        + "/path/lightcurve.dat"
    )


def test_verify_payload_checks_byte_git_and_sha_dimensions() -> None:
    data = b"1.0 15.0 0.1\n2.0 15.1 0.1\n"
    result = verify_payload(_target(data), data)
    assert result["valid"]
    assert all(result["checks"].values())


def test_verify_payload_rejects_changed_bytes() -> None:
    data = b"1.0 15.0 0.1\n"
    result = verify_payload(_target(data), data + b"2.0 15.1 0.1\n")
    assert not result["valid"]
    assert not result["checks"]["byte_count"]
    assert not result["checks"]["git_blob_sha1"]
    assert not result["checks"]["manifest_sha256_if_frozen"]
