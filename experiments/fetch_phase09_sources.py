#!/usr/bin/env python3
"""Rights-aware Phase-09 source retriever and SHA-256 freezer.

The frozen cohort manifest identifies each source by repository, commit, path,
Git blob SHA-1 and byte count. This script downloads the exact bytes only after
explicit attribution acknowledgement, verifies the Git object identity, writes
locally staged files, and emits a separate acquisition receipt. The manifest is
not silently rewritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

from derd.harmonic_extraction import git_blob_sha1_bytes
from derd.validation_phase09 import load_manifest


def raw_url(repository: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"


def fetch_bytes(url: str, *, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DERD-Phase09-Evidence-Retriever/0.9"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def verify_payload(target, payload: bytes) -> dict[str, Any]:
    actual_blob = git_blob_sha1_bytes(payload)
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    checks = {
        "byte_count": len(payload) == target.source_byte_count,
        "git_blob_sha1": actual_blob == target.source_git_blob_sha1,
        "manifest_sha256_if_frozen": (
            target.source_sha256 is None or actual_sha256 == target.source_sha256
        ),
    }
    return {
        "checks": checks,
        "source_byte_count": len(payload),
        "source_git_blob_sha1": actual_blob,
        "source_sha256": actual_sha256,
        "valid": all(checks.values()),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase09_development_cohort.json"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("artifacts/phase09/phase09_acquisition_receipt.json"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--acknowledge-ogle-attribution",
        action="store_true",
        help="required before any third-party mirror bytes are downloaded",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.acknowledge_ogle_attribution:
        parser.error("--acknowledge-ogle-attribution is required unless --dry-run is used")

    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    manifest_payload, targets = load_manifest(manifest_path)
    rows: list[dict[str, Any]] = []
    failures = 0

    for target in targets:
        destination = root / target.source_relative_path
        url = raw_url(
            target.source_repository,
            target.source_commit,
            target.source_repository_path,
        )
        base = {
            "object_id": target.object_id,
            "source_repository": target.source_repository,
            "source_commit": target.source_commit,
            "source_repository_path": target.source_repository_path,
            "source_git_blob_sha1": target.source_git_blob_sha1,
            "source_byte_count": target.source_byte_count,
            "destination_relative_path": target.source_relative_path,
            "retrieval_url": url,
        }
        if args.dry_run:
            rows.append(base | {"status": "DRY_RUN_NOT_RETRIEVED"})
            continue
        try:
            payload = fetch_bytes(url, timeout=args.timeout)
            verification = verify_payload(target, payload)
            if not verification["valid"]:
                failures += 1
                rows.append(base | verification | {"status": "REJECTED_VERIFICATION_FAILURE"})
                if not args.continue_on_error:
                    break
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(destination)
            rows.append(base | verification | {"status": "VERIFIED_AND_FROZEN"})
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            failures += 1
            rows.append(base | {
                "status": "RETRIEVAL_FAILED",
                "error_type": type(error).__name__,
                "error": str(error),
            })
            if not args.continue_on_error:
                break

    receipt = {
        "receipt_id": "PHASE09-SOURCE-ACQUISITION-RECEIPT-V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_id": manifest_payload.get("manifest_id"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "attribution_acknowledged": bool(args.acknowledge_ogle_attribution),
        "dry_run": bool(args.dry_run),
        "targets": rows,
        "verified_count": sum(row["status"] == "VERIFIED_AND_FROZEN" for row in rows),
        "failure_count": failures,
        "raw_bytes_redistributed_in_release": False,
    }
    write_json(receipt_path, receipt)
    print(f"receipt={receipt_path}")
    print(f"verified={receipt['verified_count']}")
    print(f"failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
