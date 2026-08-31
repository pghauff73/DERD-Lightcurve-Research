from __future__ import annotations

import hashlib

import pytest

from derd.harmonic_extraction import git_blob_sha1_bytes

# Import the executable module without installing a separate package.
from experiments.fetch_phase08_sources import verify_target_bytes


def target_for(data: bytes):
    return {
        "object_id": "TEST",
        "source_git_blob_sha1": git_blob_sha1_bytes(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_byte_count": len(data),
        "source_observation_count": len(data.splitlines()),
    }


def test_verify_phase08_source_bytes_checks_all_dimensions() -> None:
    data = b"1.0 15.0 0.1\n2.0 15.1 0.1\n"
    checks = verify_target_bytes(data, target_for(data))
    assert checks["git_blob_matches"]
    assert checks["sha256_matches"]
    assert checks["byte_count_matches"]
    assert checks["observation_count_matches"]


def test_verify_phase08_source_bytes_rejects_tampering() -> None:
    data = b"1.0 15.0 0.1\n"
    with pytest.raises(ValueError, match="verification failed"):
        verify_target_bytes(data + b"2.0 15.1 0.1\n", target_for(data))
