#!/usr/bin/env python3
"""Rights-aware retrieval/import of the two authoritative Phase-10 catalog files.

Network access is optional.  In a restricted environment, provide ``--input-dir``
containing ``ident.dat`` and ``dsct.dat``.  Accepted bytes are copied only after
basic catalogue-record checks and are accompanied by a SHA-256 receipt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

from derd.ogle_catalog import OGLE4_LMC_DSCT_RECORD_COUNT


SOURCES = {
    "ident.dat": "https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/dsct/ident.dat",
    "dsct.dat": "https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/dsct/dsct.dat",
}


def count_records(data: bytes) -> int:
    return sum(bool(line.strip()) and not line.lstrip().startswith(b"#") for line in data.splitlines())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("data/external/phase10_catalogs"))
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase10/phase10_catalog_acquisition_receipt.json"))
    parser.add_argument("--acknowledge-ogle-citation", action="store_true")
    parser.add_argument("--allow-small-fixture", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    if not args.acknowledge_ogle_citation:
        raise SystemExit("refusing retrieval/import without --acknowledge-ogle-citation")
    root = args.root.resolve()

    def resolve(path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else root / path

    input_dir = resolve(args.input_dir)
    destination = resolve(args.destination)
    receipt_path = resolve(args.receipt)
    assert destination is not None and receipt_path is not None
    destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    all_valid = True
    for filename, url in SOURCES.items():
        try:
            if input_dir is not None:
                data = (input_dir / filename).read_bytes()
                transport = "LOCAL_RIGHTS_REVIEWED_IMPORT"
            else:
                request = urllib.request.Request(url, headers={"User-Agent": "DERD-evidence-capsule/1.0"})
                with urllib.request.urlopen(request, timeout=args.timeout) as response:
                    data = response.read()
                transport = "HTTPS_DOWNLOAD"
            count = count_records(data)
            valid = count == OGLE4_LMC_DSCT_RECORD_COUNT or args.allow_small_fixture
            if not valid:
                raise ValueError(f"{filename}: record count {count} != {OGLE4_LMC_DSCT_RECORD_COUNT}")
            target = destination / filename
            target.write_bytes(data)
            records.append({
                "filename": filename,
                "source_url": url,
                "transport": transport,
                "destination_relative_path": target.relative_to(root).as_posix(),
                "byte_count": len(data),
                "record_count": count,
                "sha256": hashlib.sha256(data).hexdigest(),
                "status": "VERIFIED_AND_FROZEN",
            })
        except Exception as error:  # retained in receipt; caller gets nonzero exit
            all_valid = False
            records.append({
                "filename": filename,
                "source_url": url,
                "status": "FAILED",
                "error_type": type(error).__name__,
                "error": str(error),
            })
    receipt = {
        "receipt_id": "PHASE10-AUTHORITATIVE-CATALOG-ACQUISITION-V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "acknowledgement": "OGLE citation and VizieR acknowledgement accepted for research use",
        "all_valid": all_valid,
        "files": records,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote receipt to {receipt_path}")
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
