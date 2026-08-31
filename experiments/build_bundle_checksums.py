#!/usr/bin/env python3
"""Build stable checksums for every redistributable file in a DERD bundle.

The checksum file excludes itself and all third-party complete raw photometry.
The repository manifest also excludes the bundle checksum file, removing the
otherwise circular relation between the two integrity objects.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from derd.provenance import iter_repository_files, sha256_path
try:
    from experiments.build_manifest import DEFAULT_EXCLUSIONS, declared_raw_exclusions
except ModuleNotFoundError:  # direct script execution from experiments/
    from build_manifest import DEFAULT_EXCLUSIONS, declared_raw_exclusions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, default=Path("BUNDLE_SHA256SUMS.txt"))
    args = parser.parse_args()
    root = args.root.resolve()
    destination = args.destination if args.destination.is_absolute() else root / args.destination
    try:
        destination_relative = destination.resolve().relative_to(root).as_posix()
    except ValueError:
        destination_relative = None
    exclusions = tuple(dict.fromkeys((
        *DEFAULT_EXCLUSIONS,
        *declared_raw_exclusions(root),
        *(() if destination_relative is None else (destination_relative,)),
    )))
    files = tuple(iter_repository_files(root, excluded_relative_paths=exclusions))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(
            f"{sha256_path(path)}  {path.relative_to(root).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(files)} entries to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
