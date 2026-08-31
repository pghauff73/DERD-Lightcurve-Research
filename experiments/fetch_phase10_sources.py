#!/usr/bin/env python3
"""Acquire or import the exact Phase-10 raw source pack.

The source pack is orthogonal to the authoritative catalogue lock.  A local
rights-reviewed import is supported because research runtimes often block DNS.
Every accepted file must match the frozen commit path, Git blob, byte count,
observation count, and any already frozen SHA-256.
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
from derd.validation_phase09 import count_observations
from derd.validation_phase10 import load_phase10_manifest


def raw_url(repository: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"


def verify_payload(target, payload: bytes) -> dict[str, Any]:
    actual_blob = git_blob_sha1_bytes(payload)
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    observation_count = sum(bool(line.strip()) and not line.lstrip().startswith(b"#") for line in payload.splitlines())
    checks = {
        "byte_count": len(payload) == target.source_byte_count,
        "observation_count": observation_count == target.source_observation_count,
        "git_blob_sha1": actual_blob == target.source_git_blob_sha1,
        "manifest_sha256_if_frozen": target.source_sha256 is None or actual_sha256 == target.source_sha256,
    }
    return {
        "checks": checks,
        "source_byte_count": len(payload),
        "source_observation_count": observation_count,
        "source_git_blob_sha1": actual_blob,
        "source_sha256": actual_sha256,
        "valid": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/phase10_development_cohort.json"))
    parser.add_argument("--input-dir", type=Path, help="rights-reviewed directory containing files named by object_id + '.dat'")
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase10/phase10_source_acquisition_receipt.json"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--acknowledge-ogle-attribution", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.acknowledge_ogle_attribution:
        parser.error("--acknowledge-ogle-attribution is required unless --dry-run is used")
    root = args.root.resolve()

    def resolve(path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else root / path

    manifest_path = resolve(args.manifest)
    receipt_path = resolve(args.receipt)
    input_dir = resolve(args.input_dir)
    assert manifest_path is not None and receipt_path is not None
    manifest_payload, targets = load_phase10_manifest(manifest_path)
    rows: list[dict[str, Any]] = []
    failures = 0
    for wrapped in targets:
        target = wrapped.phase09
        destination = root / target.source_relative_path
        url = raw_url(target.source_repository, target.source_commit, target.source_repository_path)
        base = {
            "object_id": target.object_id,
            "source_repository": target.source_repository,
            "source_commit": target.source_commit,
            "source_repository_path": target.source_repository_path,
            "source_git_blob_sha1": target.source_git_blob_sha1,
            "source_byte_count": target.source_byte_count,
            "source_observation_count": target.source_observation_count,
            "destination_relative_path": target.source_relative_path,
            "retrieval_url": url,
        }
        if args.dry_run:
            rows.append(base | {"status": "DRY_RUN_NOT_RETRIEVED"})
            continue
        try:
            if input_dir is not None:
                candidates = [
                    input_dir / f"{target.object_id}.dat",
                    input_dir / Path(target.source_repository_path).name,
                ]
                source = next((path for path in candidates if path.is_file()), None)
                if source is None:
                    raise FileNotFoundError(f"no local source for {target.object_id}")
                payload = source.read_bytes()
                transport = "LOCAL_RIGHTS_REVIEWED_IMPORT"
            else:
                request = urllib.request.Request(url, headers={"User-Agent": "DERD-Phase10-Evidence-Retriever/1.0"})
                with urllib.request.urlopen(request, timeout=args.timeout) as response:
                    payload = response.read()
                transport = "HTTPS_DOWNLOAD"
            verification = verify_payload(target, payload)
            if not verification["valid"]:
                failures += 1
                rows.append(base | verification | {"transport": transport, "status": "REJECTED_VERIFICATION_FAILURE"})
                if not args.continue_on_error:
                    break
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(destination)
            rows.append(base | verification | {"transport": transport, "status": "VERIFIED_AND_FROZEN"})
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            failures += 1
            rows.append(base | {"status": "RETRIEVAL_FAILED", "error_type": type(error).__name__, "error": str(error)})
            if not args.continue_on_error:
                break
    receipt = {
        "receipt_id": "PHASE10-SOURCE-ACQUISITION-RECEIPT-V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_id": manifest_payload.get("manifest_id"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "attribution_acknowledged": bool(args.acknowledge_ogle_attribution),
        "dry_run": bool(args.dry_run),
        "targets": rows,
        "verified_count": sum(row.get("status") == "VERIFIED_AND_FROZEN" for row in rows),
        "failure_count": failures,
        "raw_bytes_redistributed_in_release": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"receipt={receipt_path}")
    print(f"verified={receipt['verified_count']}")
    print(f"failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
