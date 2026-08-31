#!/usr/bin/env python3
"""Fetch and verify the Phase-18 official OGLE-III and OGLE-IV V sources.

Raw photometry is intentionally local-only.  The script requires explicit
acknowledgement that scientific use must cite the appropriate OGLE catalogue
papers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

from derd.io import write_json
from derd.validation_phase18 import load_three_column, merge_photometry, verify_source_component


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "DERD-Phase18-evidence-retriever/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--destination", type=Path, default=Path("data/raw/phase18_external"))
    parser.add_argument("--acknowledge-ogle-citation", action="store_true")
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase18/phase18_fetch_receipt.json"))
    args = parser.parse_args()
    if not args.acknowledge_ogle_citation:
        raise SystemExit("Refusing retrieval without --acknowledge-ogle-citation")

    root = args.root.resolve()
    manifest = json.loads((root / "data/manifests/phase18_external_input_manifest.json").read_text())
    destination = args.destination if args.destination.is_absolute() else root / args.destination
    destination.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {
        "date": datetime.now(timezone.utc).isoformat(),
        "acknowledge_ogle_citation": True,
        "status": "STARTED",
        "components": [],
        "raw_source_redistributed": False,
    }
    arrays = []
    try:
        for component in manifest["components"]:
            target = destination / Path(component["source_relative_path"]).name
            payload = download(component["url"])
            temporary = target.with_suffix(target.suffix + ".partial")
            temporary.write_bytes(payload)
            check = verify_source_component(temporary, component)
            if not check["all_checks_passed"]:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"source verification failed: {component['source_id']}")
            temporary.replace(target)
            arrays.append(load_three_column(target))
            receipt["components"].append(
                {"source_id": component["source_id"], "target": str(target), "verification": check}
            )
        merged = merge_photometry(*arrays)
        merged_target = destination / Path(manifest["merged"]["source_relative_path"]).name
        import numpy as np
        np.savetxt(merged_target, merged, fmt=["%.5f", "%.3f", "%.3f"])
        merged_check = verify_source_component(merged_target, manifest["merged"])
        if not merged_check["all_checks_passed"]:
            raise RuntimeError("merged-source verification failed")
        receipt["merged"] = merged_check
        receipt["status"] = "AUTHORITATIVE_CURRENT_OGLEIII_IV_FILES_VERIFIED_AND_MERGED"
    except Exception as error:
        receipt["status"] = "FAILED"
        receipt["error"] = f"{type(error).__name__}: {error}"
        receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
        write_json(receipt_path, receipt)
        raise

    receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    write_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
