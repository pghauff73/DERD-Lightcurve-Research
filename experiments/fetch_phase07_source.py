#!/usr/bin/env python3
"""Fetch the frozen Phase-07 development source with explicit rights acknowledgement.

The target is a public GitHub mirror, not a claim of official OGLE provenance.
The script verifies both the Git blob object ID and the expected SHA-256 before
writing the file.  Redistribution rights are not asserted by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from derd.harmonic_extraction import git_blob_sha1_bytes

STAR_ID = "OGLE-LMC-CEP-0010"
SOURCE_COMMIT = "55836b58345b9507bfbd98c5fabbac82c83605e3"
RAW_URL = (
    "https://raw.githubusercontent.com/bksim/OutlierDetection/"
    f"{SOURCE_COMMIT}/Cluster/cep/phot/I/{STAR_ID}.dat"
)
EXPECTED_GIT_BLOB_SHA1 = "fd82c05bb3a62ba9a8c614ac51eb315124090381"
EXPECTED_SHA256 = "574d7252996f5ee71169a97f2d7b52a8acbdb0898df65a7b61f5419ae9f063e0"
EXPECTED_BYTE_COUNT = 8928


def verify_source_bytes(data: bytes) -> dict[str, object]:
    git_blob = git_blob_sha1_bytes(data)
    sha256 = hashlib.sha256(data).hexdigest()
    checks = {
        "git_blob_sha1": git_blob,
        "sha256": sha256,
        "byte_count": len(data),
        "git_blob_matches": git_blob == EXPECTED_GIT_BLOB_SHA1,
        "sha256_matches": sha256 == EXPECTED_SHA256,
        "byte_count_matches": len(data) == EXPECTED_BYTE_COUNT,
    }
    if not all(
        checks[key]
        for key in ("git_blob_matches", "sha256_matches", "byte_count_matches")
    ):
        raise ValueError(f"source verification failed: {checks}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(f"data/raw/ogle/{STAR_ID}.complete.dat"),
    )
    parser.add_argument(
        "--acknowledge-third-party-terms",
        action="store_true",
        help=(
            "confirm that the caller will inspect and comply with the source and "
            "underlying survey terms before using or redistributing the bytes"
        ),
    )
    args = parser.parse_args()
    if not args.acknowledge_third_party_terms:
        parser.error("--acknowledge-third-party-terms is required")

    request = Request(RAW_URL, headers={"User-Agent": "DERD-evidence-fetch/0.7"})
    with urlopen(request, timeout=60) as response:
        data = response.read()
    checks = verify_source_bytes(data)

    destination = args.destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=destination.name + ".", delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(destination)

    print(f"wrote={destination}")
    for key, value in checks.items():
        print(f"{key}={value}")
    print("rights_status=PUBLIC_MIRROR; REDISTRIBUTION_TERMS_NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
