#!/usr/bin/env python3
"""Fetch and freeze the Phase-17 V-band source after attribution acknowledgement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

from derd.io import write_json
from derd.validation_phase17 import verify_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--acknowledge-attribution", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "data/manifests/phase17_external_v_source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination = root / manifest["source_relative_path"]
    receipt_path = root / "artifacts/phase17/phase17_source_acquisition_receipt.json"
    if not args.acknowledge_attribution:
        write_json(
            receipt_path,
            {
                "status": "BLOCKED_ATTRIBUTION_ACKNOWLEDGEMENT_REQUIRED",
                "object_id": manifest["object_id"],
                "destination": destination.relative_to(root).as_posix(),
            },
        )
        raise SystemExit("pass --acknowledge-attribution after reviewing the source attribution requirements")

    url = (
        "https://raw.githubusercontent.com/"
        f"{manifest['repository']}/{manifest['commit']}/{manifest['repository_path']}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = Request(url, headers={"User-Agent": "DERD-evidence-fetcher/1.7"})
        with urlopen(request, timeout=args.timeout) as response:
            payload = response.read()
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        check = verify_source(
            temporary,
            expected_sha256=manifest["source_sha256"],
            expected_git_blob_sha1=manifest["git_blob_sha1"],
            expected_bytes=int(manifest["byte_count"]),
            expected_observations=int(manifest["observation_count"]),
        )
        if not check["all_checks_passed"]:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("downloaded source failed frozen verification")
        temporary.replace(destination)
        status = "VERIFIED_AND_FROZEN"
        error = None
    except Exception as exc:  # network and verification failures are evidence events
        status = "FAILED"
        error = f"{type(exc).__name__}: {exc}"
        check = {}

    receipt = {
        "status": status,
        "object_id": manifest["object_id"],
        "url": url,
        "destination": destination.relative_to(root).as_posix(),
        "attribution_acknowledged": True,
        "verification": check,
        "error": error,
        "raw_source_redistributed": False,
    }
    write_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if status == "VERIFIED_AND_FROZEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
