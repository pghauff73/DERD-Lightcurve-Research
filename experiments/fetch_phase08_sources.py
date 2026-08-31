#!/usr/bin/env python3
"""Fetch and verify the frozen Phase-08 exposed development cohort.

This tool does not assert redistribution rights. It requires explicit caller
acknowledgement and verifies four independent byte-level dimensions before an
atomic write: Git blob SHA-1, SHA-256, byte count, and observation count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
from urllib.request import Request, urlopen

from derd.harmonic_extraction import git_blob_sha1_bytes


def verify_target_bytes(data: bytes, target: dict[str, Any]) -> dict[str, Any]:
    git_blob = git_blob_sha1_bytes(data)
    sha256 = hashlib.sha256(data).hexdigest()
    observation_count = len(data.splitlines())
    checks = {
        "object_id": target["object_id"],
        "git_blob_sha1": git_blob,
        "sha256": sha256,
        "byte_count": len(data),
        "observation_count": observation_count,
        "git_blob_matches": git_blob == target["source_git_blob_sha1"],
        "sha256_matches": sha256 == target["source_sha256"],
        "byte_count_matches": len(data) == int(target["source_byte_count"]),
        "observation_count_matches": observation_count == int(target["source_observation_count"]),
    }
    required = (
        "git_blob_matches",
        "sha256_matches",
        "byte_count_matches",
        "observation_count_matches",
    )
    if not all(bool(checks[key]) for key in required):
        raise ValueError(f"source verification failed: {checks}")
    return checks


def raw_url(target: dict[str, Any]) -> str:
    return (
        f"https://raw.githubusercontent.com/{target['source_repository']}/"
        f"{target['source_commit']}/{target['source_repository_path']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase08_cohort_sources.json"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--object-id", action="append", default=[])
    parser.add_argument("--acknowledge-third-party-terms", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_third_party_terms:
        parser.error("--acknowledge-third-party-terms is required")

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    requested = set(args.object_id)
    targets = [
        target
        for target in payload["targets"]
        if not requested or target["object_id"] in requested
    ]
    missing = requested - {target["object_id"] for target in targets}
    if missing:
        parser.error(f"unknown object IDs: {sorted(missing)}")

    for target in targets:
        request = Request(
            raw_url(target),
            headers={"User-Agent": "DERD-evidence-fetch/0.8"},
        )
        with urlopen(request, timeout=60) as response:
            data = response.read()
        checks = verify_target_bytes(data, target)
        destination = args.root / target["source_relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=destination.name + ".",
            delete=False,
        ) as handle:
            handle.write(data)
            temporary = Path(handle.name)
        temporary.replace(destination)
        print(f"object_id={target['object_id']}")
        print(f"wrote={destination}")
        for key in ("git_blob_sha1", "sha256", "byte_count", "observation_count"):
            print(f"{key}={checks[key]}")
    print("rights_status=PUBLIC_MIRROR; REDISTRIBUTION_TERMS_NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
