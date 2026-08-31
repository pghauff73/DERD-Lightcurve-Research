#!/usr/bin/env python3
"""Build the deterministic repository SHA-256 manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from derd.provenance import write_repository_manifest


DEFAULT_EXCLUSIONS = (
    # Bundle checksums include the full repository manifest. Excluding the checksum
    # file here prevents a circular hash relation.
    "BUNDLE_SHA256SUMS.txt",
    # Third-party raw bytes are fetched locally and are not part of the
    # redistributable release while reuse terms remain unverified.
    "data/raw/ogle/OGLE-LMC-CEP-0010.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-CEP-0002.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-CEP-0010.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-RRLYR-00001.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-RRLYR-00004.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-DSCT-0001.complete.dat",
    "data/raw/phase08_cohort/OGLE-LMC-DSCT-0003.complete.dat",
    "data/raw/phase17_external/OGLE-LMC-CEP-0002_V.dat",
    "data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIII_V.dat",
    "data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIV_V.dat",
    "data/raw/phase18_external/OGLE-LMC-CEP-0002_merged_V.dat",
    "data/raw/phase20_external/OGLE-LMC-CEP-0002_OGLEIII_V.dat",
    "data/raw/phase20_external/OGLE-LMC-CEP-0002_OGLEIV_V.dat",
    "data/raw/phase20_external/OGLE-LMC-CEP-0002_merged_V.dat",
)


def _manifest_raw_paths(manifest: Path) -> tuple[str, ...]:
    """Return declared raw-source paths without requiring the bytes to exist."""

    if not manifest.is_file():
        return ()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return tuple(
        str(row["source_relative_path"])
        for row in payload.get("targets", [])
        if isinstance(row, dict) and row.get("source_relative_path")
    )


def declared_raw_exclusions(root: Path) -> tuple[str, ...]:
    """Return every phase-declared third-party raw path.

    Phase 10 carries the Phase-09 source paths forward unchanged, but its own
    cohort manifest is the authoritative release input.  Reading both manifests
    keeps incremental releases and older tests compatible while deduplicating
    paths at the caller.
    """

    manifests = (
        root / "data/manifests/phase09_development_cohort.json",
        root / "data/manifests/phase10_development_cohort.json",
        root / "data/manifests/phase21_development_cohort.json",
    )
    catalog_paths = (
        "data/external/phase10_catalogs/ident.dat",
        "data/external/phase10_catalogs/dsct.dat",
    )
    return tuple(
        dict.fromkeys(
            (
                *(path for manifest in manifests for path in _manifest_raw_paths(manifest)),
                *catalog_paths,
            )
        )
    )


def phase09_raw_exclusions(root: Path) -> tuple[str, ...]:
    """Backward-compatible alias retained for Phase-09 tests and callers."""

    return _manifest_raw_paths(root / "data/manifests/phase09_development_cohort.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="additional repository-relative path to exclude from the manifest",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    destination = arguments.destination or root / "research/MANIFEST_SHA256.txt"
    exclusions = tuple(dict.fromkeys((*DEFAULT_EXCLUSIONS, *declared_raw_exclusions(root), *arguments.exclude)))
    count = write_repository_manifest(
        root,
        destination,
        excluded_relative_paths=exclusions,
    )
    print(f"wrote {count} entries to {destination}")
    for relative in exclusions:
        print(f"excluded={relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
