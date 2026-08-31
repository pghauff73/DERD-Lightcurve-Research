#!/usr/bin/env python3
"""Refuse accidental evaluation of Phase-04 sealed star identities."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from derd.sealing import assert_no_sealed_evaluation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("role_manifest")
    parser.add_argument("evaluation_manifest")
    parser.add_argument("--star-id-column", default="star_id")
    args = parser.parse_args()

    payload = json.loads(Path(args.role_manifest).read_text(encoding="utf-8"))
    roles = {str(row["star_id"]): str(row["role"]) for row in payload["roles"]}
    with Path(args.evaluation_manifest).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or args.star_id_column not in reader.fieldnames:
            raise ValueError(f"evaluation manifest must contain {args.star_id_column}")
        star_ids = [str(row[args.star_id_column]).strip() for row in reader]
    assert_no_sealed_evaluation(star_ids, roles)
    print(json.dumps({"allowed": True, "evaluated_star_count": len(star_ids)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
