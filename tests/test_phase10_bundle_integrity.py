from __future__ import annotations

import json
from pathlib import Path

from experiments.build_manifest import declared_raw_exclusions


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_phase10_raw_exclusions_cover_cohort_and_authoritative_catalogs() -> None:
    manifest = json.loads(
        (REPOSITORY_ROOT / "data/manifests/phase10_development_cohort.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        row["source_relative_path"]
        for row in manifest["targets"]
    }
    expected.update(
        {
            "data/external/phase10_catalogs/ident.dat",
            "data/external/phase10_catalogs/dsct.dat",
        }
    )
    assert expected.issubset(set(declared_raw_exclusions(REPOSITORY_ROOT)))


def test_phase10_release_contains_no_complete_third_party_input_bytes() -> None:
    forbidden = set(declared_raw_exclusions(REPOSITORY_ROOT))
    present = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file()
    }
    assert forbidden.isdisjoint(present)
