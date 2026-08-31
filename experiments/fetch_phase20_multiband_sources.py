#!/usr/bin/env python3
"""Fetch and verify the Phase-20 official OGLE V-band sources."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row_count(data: bytes) -> int:
    return sum(1 for line in data.decode("utf-8").splitlines() if line.strip())


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "DERD-Phase20-evidence-retriever/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--acknowledge-ogle-citation", action="store_true")
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase20/phase20_fetch_receipt.json"))
    args = parser.parse_args()
    if not args.acknowledge_ogle_citation:
        raise SystemExit("Refusing retrieval without --acknowledge-ogle-citation")
    root = args.root.resolve()
    manifest = json.loads((root / "data/manifests/phase20_multiband_sources.json").read_text())
    receipt: dict[str, object] = {
        "date": datetime.now(timezone.utc).isoformat(),
        "acknowledge_ogle_citation": True,
        "status": "STARTED",
        "sources": [],
        "raw_source_redistributed": False,
    }
    downloaded: dict[str, bytes] = {}
    try:
        for row in manifest["v_sources"]:
            if row["source_id"] == "merged_v":
                continue
            payload = _download(row["url"])
            checks = {
                "sha256": _sha256(payload) == row["sha256"],
                "byte_count": len(payload) == row["byte_count"],
                "observation_count": _row_count(payload) == row["observation_count"],
            }
            if not all(checks.values()):
                raise RuntimeError(f"source verification failed for {row['source_id']}: {checks}")
            target = root / row["source_relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".partial")
            temporary.write_bytes(payload)
            temporary.replace(target)
            downloaded[row["source_id"]] = payload
            receipt["sources"].append({"source_id": row["source_id"], "target": str(target), "checks": checks})
        merged = b"".join(downloaded[key] for key in ("ogleiii_v", "ogleiv_v"))
        row = next(item for item in manifest["v_sources"] if item["source_id"] == "merged_v")
        checks = {
            "sha256": _sha256(merged) == row["sha256"],
            "byte_count": len(merged) == row["byte_count"],
            "observation_count": _row_count(merged) == row["observation_count"],
        }
        if not all(checks.values()):
            raise RuntimeError(f"merged-source verification failed: {checks}")
        target = root / row["source_relative_path"]
        target.write_bytes(merged)
        receipt["sources"].append({"source_id": "merged_v", "target": str(target), "checks": checks})
        receipt["status"] = "OFFICIAL_OGLEIII_IV_V_SOURCES_VERIFIED_AND_MERGED"
    except Exception as error:
        receipt["status"] = "FAILED"
        receipt["error"] = f"{type(error).__name__}: {error}"
        path = args.receipt if args.receipt.is_absolute() else root / args.receipt
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        raise
    path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
