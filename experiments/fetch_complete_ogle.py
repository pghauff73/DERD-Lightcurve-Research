#!/usr/bin/env python3
"""Fetch complete official OGLE files after explicit attribution acknowledgement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from derd.io import read_target_manifest
from derd.ogle import fetch_official_photometry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/manifests/phase02_targets.csv")
    parser.add_argument("--destination", default="data/official/ogle_lmc_cepheids/I")
    parser.add_argument("--band", choices=("I", "V"), default="I")
    parser.add_argument("--delay-seconds", type=float, default=0.25)
    parser.add_argument(
        "--acknowledge-ogle",
        action="store_true",
        help="Confirm that downstream publications will acknowledge OGLE and cite the collection source.",
    )
    args = parser.parse_args()
    if not args.acknowledge_ogle:
        parser.error("--acknowledge-ogle is required before retrieval")

    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    records = read_target_manifest(args.manifest)
    results = []
    for index, record in enumerate(records):
        path = destination / f"{record.star_id}.dat"
        results.append(fetch_official_photometry(record.star_id, path, band=args.band))
        if index + 1 < len(records) and args.delay_seconds > 0.0:
            time.sleep(args.delay_seconds)
    payload = {
        "status": "OFFICIAL_OGLE_DOWNLOAD_COMPLETE",
        "attribution_acknowledged": True,
        "band": args.band,
        "files": results,
    }
    (destination.parent / f"official_{args.band}_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
