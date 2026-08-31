#!/usr/bin/env python3
"""Import a rights-reviewed incremental source pack and merge source receipts.

Phase 12 preserves historically verified source locks from Phase 11 while
installing any newly supplied files.  Historical verification does not imply
that bytes are locally present: execution readiness still requires the source
file itself to exist and pass every frozen check.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from derd.harmonic_extraction import git_blob_sha1_bytes
from derd.validation_phase10 import load_phase10_manifest


def verify_payload(target, payload: bytes) -> dict[str, Any]:
    actual_blob = git_blob_sha1_bytes(payload)
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    observations = sum(
        bool(line.strip()) and not line.lstrip().startswith(b"#")
        for line in payload.splitlines()
    )
    checks = {
        "byte_count": len(payload) == target.source_byte_count,
        "observation_count": observations == target.source_observation_count,
        "git_blob_sha1": actual_blob == target.source_git_blob_sha1,
        "manifest_sha256_if_frozen": (
            target.source_sha256 is None or actual_sha256 == target.source_sha256
        ),
    }
    return {
        "checks": checks,
        "source_byte_count": len(payload),
        "source_observation_count": observations,
        "source_git_blob_sha1": actual_blob,
        "source_sha256": actual_sha256,
        "valid": all(checks.values()),
    }


def candidate_paths(input_dir: Path, object_id: str, repository_path: str) -> tuple[Path, ...]:
    name = Path(repository_path).name
    return (
        input_dir / f"{object_id}.complete.dat",
        input_dir / f"{object_id}.dat",
        input_dir / name,
    )


def prior_rows(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: dict[str, Mapping[str, Any]] = {}
    for row in payload.get("targets", []):
        if isinstance(row, Mapping) and row.get("object_id"):
            rows[str(row["object_id"])] = row
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase10_development_cohort.json"),
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--prior-receipt",
        type=Path,
        default=Path("artifacts/phase11/phase11_source_acquisition_receipt.json"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("artifacts/phase12/phase12_source_acquisition_receipt.json"),
    )
    parser.add_argument("--acknowledge-ogle-attribution", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_ogle_attribution:
        parser.error("--acknowledge-ogle-attribution is required")

    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    input_dir = args.input_dir.resolve()
    prior_path = args.prior_receipt if args.prior_receipt.is_absolute() else root / args.prior_receipt
    receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    manifest, targets = load_phase10_manifest(manifest_path)
    inherited = prior_rows(prior_path)

    rows: list[dict[str, Any]] = []
    invalid = 0
    newly_verified = 0
    historically_verified = 0
    locally_present_verified = 0
    for wrapped in targets:
        target = wrapped.phase09
        source = next(
            (
                path
                for path in candidate_paths(
                    input_dir, target.object_id, target.source_repository_path
                )
                if path.is_file()
            ),
            None,
        )
        base = {
            "object_id": target.object_id,
            "source_repository": target.source_repository,
            "source_commit": target.source_commit,
            "source_repository_path": target.source_repository_path,
            "source_git_blob_sha1": target.source_git_blob_sha1,
            "source_byte_count": target.source_byte_count,
            "source_observation_count": target.source_observation_count,
            "destination_relative_path": target.source_relative_path,
        }
        if source is not None:
            payload = source.read_bytes()
            verification = verify_payload(target, payload)
            if not verification["valid"]:
                invalid += 1
                rows.append(
                    base
                    | verification
                    | {
                        "status": "REJECTED_VERIFICATION_FAILURE",
                        "transport": "LOCAL_RIGHTS_REVIEWED_INCREMENTAL_IMPORT",
                        "input_path": str(source),
                        "receipt_history": "PHASE12_NEW_PACK",
                    }
                )
                continue
            destination = root / target.source_relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(destination)
            newly_verified += 1
            locally_present_verified += 1
            rows.append(
                base
                | verification
                | {
                    "status": "VERIFIED_AND_FROZEN",
                    "transport": "LOCAL_RIGHTS_REVIEWED_INCREMENTAL_IMPORT",
                    "input_path": str(source),
                    "receipt_history": "PHASE12_NEW_PACK",
                }
            )
            continue

        old = inherited.get(target.object_id)
        if old is not None and old.get("status") == "VERIFIED_AND_FROZEN":
            preserved = dict(old)
            preserved.update(base)
            preserved["receipt_history"] = "PRESERVED_FROM_PRIOR_RECEIPT"
            destination = root / target.source_relative_path
            preserved["locally_present"] = destination.is_file()
            historically_verified += 1
            if destination.is_file():
                locally_present_verified += 1
            rows.append(preserved)
        else:
            rows.append(base | {"status": "NOT_PRESENT_IN_PROGRESSIVE_PACK"})

    verified_count = sum(row.get("status") == "VERIFIED_AND_FROZEN" for row in rows)
    receipt = {
        "receipt_id": "PHASE09-SOURCE-ACQUISITION-RECEIPT-V1",
        "receipt_profile": "PHASE12-CUMULATIVE-SOURCE-LOCK-RECEIPT-V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_id": manifest.get("manifest_id"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "prior_receipt_relative_path": (
            prior_path.relative_to(root).as_posix() if prior_path.is_file() else None
        ),
        "prior_receipt_sha256": (
            hashlib.sha256(prior_path.read_bytes()).hexdigest() if prior_path.is_file() else None
        ),
        "attribution_acknowledged": True,
        "dry_run": False,
        "targets": rows,
        "verified_count": verified_count,
        "newly_verified_count": newly_verified,
        "historically_verified_count": historically_verified,
        "locally_present_verified_count": locally_present_verified,
        "pending_count": sum(
            row.get("status") == "NOT_PRESENT_IN_PROGRESSIVE_PACK" for row in rows
        ),
        "invalid_count": invalid,
        "raw_bytes_redistributed_in_release": False,
        "claim_boundary": "source-lock evidence only; not a physical claim certificate",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"receipt={receipt_path}")
    print(f"verified={verified_count}")
    print(f"newly_verified={newly_verified}")
    print(f"historically_verified={historically_verified}")
    print(f"locally_present_verified={locally_present_verified}")
    print(f"pending={receipt['pending_count']}")
    print(f"invalid={invalid}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
