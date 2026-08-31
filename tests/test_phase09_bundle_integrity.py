from __future__ import annotations

import json
from pathlib import Path

from experiments.build_manifest import phase09_raw_exclusions


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_phase09_raw_exclusions_cover_all_declared_targets() -> None:
    manifest = json.loads(
        (REPOSITORY_ROOT / "data/manifests/phase09_development_cohort.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {row["source_relative_path"] for row in manifest["targets"]}
    assert set(phase09_raw_exclusions(REPOSITORY_ROOT)) == expected
    assert len(expected) == 15


def test_bundle_checksum_file_does_not_hash_itself() -> None:
    checksums = REPOSITORY_ROOT / "BUNDLE_SHA256SUMS.txt"
    if checksums.is_file():
        assert "BUNDLE_SHA256SUMS.txt" not in {
            line.split("  ", 1)[1]
            for line in checksums.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
