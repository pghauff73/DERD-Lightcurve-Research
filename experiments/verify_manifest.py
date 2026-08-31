#!/usr/bin/env python3
"""Verify the deterministic repository SHA-256 manifest."""
from __future__ import annotations

import argparse
from pathlib import Path

from derd.provenance import verify_repository_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    manifest = arguments.manifest or root / "research/MANIFEST_SHA256.txt"
    result = verify_repository_manifest(root, manifest)
    print(f"checked={result.checked_count}")
    print(f"missing={len(result.missing)}")
    print(f"mismatched={len(result.mismatched)}")
    print(f"malformed={len(result.malformed)}")
    if not result.valid:
        for label, values in (
            ("missing", result.missing),
            ("mismatched", result.mismatched),
            ("malformed", result.malformed),
        ):
            for value in values:
                print(f"{label}: {value}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
