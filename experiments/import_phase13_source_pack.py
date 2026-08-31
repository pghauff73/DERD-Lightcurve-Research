#!/usr/bin/env python3
"""Import the single frozen Phase-13 acquisition target and merge receipts.

The importer accepts only the target ranked first by the frozen acquisition-order
manifest.  It validates byte count, observation count, Git-blob SHA-1, and
SHA-256 before atomically installing the file.  Raw bytes are not intended for
redistribution in the release bundle.
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
        "manifest_sha256": (
            target.source_sha256 is not None and actual_sha256 == target.source_sha256
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
    return {
        str(row["object_id"]): row
        for row in payload.get("targets", [])
        if isinstance(row, Mapping) and row.get("object_id")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest", type=Path,
        default=Path("data/manifests/phase10_development_cohort.json"),
    )
    parser.add_argument(
        "--acquisition-order", type=Path,
        default=Path("data/manifests/phase13_acquisition_order.json"),
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--prior-receipt", type=Path,
        default=Path("artifacts/phase12/phase12_source_acquisition_receipt.json"),
    )
    parser.add_argument(
        "--receipt", type=Path,
        default=Path("artifacts/phase13/phase13_source_acquisition_receipt.json"),
    )
    parser.add_argument("--acknowledge-ogle-attribution", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_ogle_attribution:
        parser.error("--acknowledge-ogle-attribution is required")

    root = args.root.resolve()
    resolve = lambda path: path if path.is_absolute() else root / path
    manifest_path = resolve(args.manifest)
    order_path = resolve(args.acquisition_order)
    input_dir = args.input_dir.resolve()
    prior_path = resolve(args.prior_receipt)
    receipt_path = resolve(args.receipt)

    manifest, wrapped_targets = load_phase10_manifest(manifest_path)
    acquisition = json.loads(order_path.read_text(encoding="utf-8"))
    selected_id = str(acquisition.get("selected_target", {}).get("object_id", ""))
    if not selected_id:
        raise ValueError("acquisition-order manifest does not identify a selected target")
    target_map = {item.phase09.object_id: item.phase09 for item in wrapped_targets}
    if selected_id not in target_map:
        raise ValueError("selected acquisition target is absent from frozen cohort")
    selected = target_map[selected_id]
    inherited = prior_rows(prior_path)

    rows: list[dict[str, Any]] = []
    invalid = 0
    newly_verified = 0
    locally_present_verified = 0
    for wrapped in wrapped_targets:
        target = wrapped.phase09
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
        if target.object_id == selected_id:
            source = next(
                (
                    path for path in candidate_paths(
                        input_dir, target.object_id, target.source_repository_path
                    ) if path.is_file()
                ),
                None,
            )
            if source is None:
                rows.append(base | {"status": "SELECTED_SOURCE_NOT_PRESENT"})
                continue
            verification = verify_payload(target, source.read_bytes())
            if not verification["valid"]:
                invalid += 1
                rows.append(
                    base | verification | {
                        "status": "REJECTED_VERIFICATION_FAILURE",
                        "transport": "LOCAL_RIGHTS_REVIEWED_PHASE13_IMPORT",
                        "input_path": str(source),
                    }
                )
                continue
            destination = root / target.source_relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(source.read_bytes())
            temporary.replace(destination)
            newly_verified += 1
            locally_present_verified += 1
            rows.append(
                base | verification | {
                    "status": "VERIFIED_AND_FROZEN",
                    "transport": "LOCAL_RIGHTS_REVIEWED_PHASE13_IMPORT",
                    "input_path": str(source),
                    "selected_by_acquisition_order": True,
                }
            )
            continue

        old = inherited.get(target.object_id)
        if old is not None and old.get("status") == "VERIFIED_AND_FROZEN":
            preserved = dict(old)
            preserved.update(base)
            destination = root / target.source_relative_path
            preserved["receipt_history"] = "PRESERVED_FROM_PHASE12_RECEIPT"
            preserved["locally_present"] = destination.is_file()
            if destination.is_file():
                locally_present_verified += 1
            rows.append(preserved)
        else:
            rows.append(base | {"status": "NOT_SELECTED_IN_PHASE13_PACK"})

    receipt = {
        "receipt_id": "DERD-PHASE13-SOURCE-LOCK-RECEIPT-1.0",
        "receipt_profile": "PHASE13-TEMPORAL-REPLICATION-SOURCE-LOCK",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_id": manifest.get("manifest_id"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "acquisition_order_relative_path": order_path.relative_to(root).as_posix(),
        "acquisition_order_sha256": hashlib.sha256(order_path.read_bytes()).hexdigest(),
        "selected_object_id": selected_id,
        "prior_receipt_relative_path": (
            prior_path.relative_to(root).as_posix() if prior_path.is_file() else None
        ),
        "prior_receipt_sha256": (
            hashlib.sha256(prior_path.read_bytes()).hexdigest() if prior_path.is_file() else None
        ),
        "attribution_acknowledged": True,
        "dry_run": False,
        "targets": rows,
        "verified_count": sum(row.get("status") == "VERIFIED_AND_FROZEN" for row in rows),
        "newly_verified_count": newly_verified,
        "locally_present_verified_count": locally_present_verified,
        "pending_count": sum(
            row.get("status") in {"NOT_SELECTED_IN_PHASE13_PACK", "SELECTED_SOURCE_NOT_PRESENT"}
            for row in rows
        ),
        "invalid_count": invalid,
        "raw_bytes_redistributed_in_release": False,
        "claim_boundary": "source-lock evidence only; not a physical claim certificate",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"receipt={receipt_path}")
    print(f"selected={selected_id}")
    print(f"newly_verified={newly_verified}")
    print(f"invalid={invalid}")
    return 1 if invalid or newly_verified != 1 else 0


if __name__ == "__main__":
    raise SystemExit(main())
