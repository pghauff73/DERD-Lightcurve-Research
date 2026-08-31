#!/usr/bin/env python3
"""Build the Phase-10 authoritative delta-Scuti metadata lock."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from derd.ogle_catalog import (
    OGLE4_LMC_DSCT_RECORD_COUNT,
    canonical_json_sha256,
    load_catalog_lines,
    parse_identity_catalog,
    parse_parameter_catalog,
    resolve_delta_scuti_metadata,
)
from derd.provenance import sha256_path


DEFAULT_REQUESTED = tuple(f"OGLE-LMC-DSCT-{value:04d}" for value in range(3, 8))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ident", type=Path, default=Path("data/external/phase10_catalogs/ident.dat"))
    parser.add_argument("--parameters", type=Path, default=Path("data/external/phase10_catalogs/dsct.dat"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/phase10_delta_scuti_metadata_lock.json"),
    )
    parser.add_argument("--requested-id", action="append", dest="requested_ids")
    parser.add_argument("--allow-small-fixture", action="store_true")
    parser.add_argument("--authority", default="OGLE Collection of Variable Stars / VizieR J/AcA/73/105")
    parser.add_argument("--catalogue-release", default="OGLE-IV LMC DSCT 2023 / VizieR 2025-08-26")
    args = parser.parse_args()
    root = args.root.resolve()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    ident_path = resolve(args.ident)
    parameter_path = resolve(args.parameters)
    output = resolve(args.output)
    if not ident_path.is_file() or not parameter_path.is_file():
        missing = [str(path) for path in (ident_path, parameter_path) if not path.is_file()]
        raise FileNotFoundError("authoritative catalog bytes missing: " + ", ".join(missing))

    identities = parse_identity_catalog(load_catalog_lines(ident_path))
    parameters = parse_parameter_catalog(load_catalog_lines(parameter_path))
    if not args.allow_small_fixture:
        if len(identities) != OGLE4_LMC_DSCT_RECORD_COUNT:
            raise ValueError(f"ident.dat record count {len(identities)} != {OGLE4_LMC_DSCT_RECORD_COUNT}")
        if len(parameters) != OGLE4_LMC_DSCT_RECORD_COUNT:
            raise ValueError(f"dsct.dat record count {len(parameters)} != {OGLE4_LMC_DSCT_RECORD_COUNT}")

    requested = tuple(args.requested_ids or DEFAULT_REQUESTED)
    identity_sha = sha256_path(ident_path)
    parameter_sha = sha256_path(parameter_path)
    locks = resolve_delta_scuti_metadata(
        requested,
        identities,
        parameters,
        identity_catalog_sha256=identity_sha,
        parameter_catalog_sha256=parameter_sha,
        authority=args.authority,
        identity_source_url="https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/dsct/ident.dat",
        parameter_source_url="https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/dsct/dsct.dat",
        catalogue_release=args.catalogue_release,
    )
    payload = {
        "lock_id": "PHASE10-LMC-DSCT-AUTHORITATIVE-METADATA-LOCK-V1",
        "implementation_id": "DERD-v1.0-phase10-authoritative-metadata-source-lock",
        "catalog_contract_id": "DERD-PHASE10-OGLE-AUTHORITATIVE-CATALOG-CONTRACT-1.0",
        "status": "AUTHORITATIVE_METADATA_LOCK_COMPLETE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "requested_object_ids": list(requested),
        "identity_catalog": {
            "path": str(ident_path),
            "sha256": identity_sha,
            "record_count": len(identities),
        },
        "parameter_catalog": {
            "path": str(parameter_path),
            "sha256": parameter_sha,
            "record_count": len(parameters),
        },
        "records": [lock.as_dict() for lock in locks],
        "blockers": [],
        "prohibition": "Singlemode subtype is not promoted to a radial order without a separate authoritative classification.",
    }
    payload["sha256_canonical_json"] = canonical_json_sha256(payload)
    write_json(output, payload)
    print(f"wrote {len(locks)} metadata locks to {output}")
    print(f"identity_catalog_sha256={identity_sha}")
    print(f"parameter_catalog_sha256={parameter_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
