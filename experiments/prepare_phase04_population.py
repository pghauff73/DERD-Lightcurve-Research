#!/usr/bin/env python3
"""Audit a Phase-04 candidate population and seal roles only after every gate passes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from derd.population import (
    audit_population,
    build_role_manifest,
    load_population_contract,
    read_exposed_star_ids,
    read_population_manifest,
)
from derd.provenance import sha256_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_manifest")
    parser.add_argument(
        "--contract",
        default="data/manifests/phase04_population_contract_v1.json",
    )
    parser.add_argument(
        "--analysis-plan",
        default="research/preregistration/phase04_analysis_plan.json",
    )
    parser.add_argument(
        "--code-manifest",
        default="research/CODE_MANIFEST_SHA256.txt",
    )
    parser.add_argument(
        "--exposed-star-ids",
        default="data/manifests/phase04_exposed_star_ids.csv",
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-directory", default="research/sealed/phase04")
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Audit metadata without verifying local data files. Metadata-only audits cannot seal.",
    )
    args = parser.parse_args()

    candidate_path = Path(args.candidate_manifest)
    contract_path = Path(args.contract)
    analysis_plan_path = Path(args.analysis_plan)
    code_manifest_path = Path(args.code_manifest)
    output = Path(args.output_directory)
    output.mkdir(parents=True, exist_ok=True)

    records = read_population_manifest(candidate_path)
    contract = load_population_contract(contract_path)
    exposed = read_exposed_star_ids(args.exposed_star_ids)
    verify_files = not args.metadata_only
    audit = audit_population(
        records,
        contract,
        data_root=args.data_root,
        exposed_star_ids=exposed,
        verify_files=verify_files,
    )
    readiness = {
        "implementation_id": "DERD-v0.4-phase04-readiness",
        "status": "READY_FOR_PROSPECTIVE_SEAL" if audit.ready_for_sealing else "NOT_READY_FOR_PROSPECTIVE_SEAL",
        "metadata_only": bool(args.metadata_only),
        "candidate_manifest": str(candidate_path),
        "candidate_manifest_sha256": sha256_path(candidate_path),
        "contract": str(contract_path),
        "contract_sha256": sha256_path(contract_path),
        "analysis_plan": str(analysis_plan_path),
        "analysis_plan_sha256": sha256_path(analysis_plan_path),
        "code_manifest": str(code_manifest_path),
        "code_manifest_sha256": sha256_path(code_manifest_path),
        "audit": audit.as_dict(),
    }
    (output / "phase04_readiness.json").write_text(
        json.dumps(readiness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.metadata_only or not audit.ready_for_sealing:
        print(json.dumps(readiness, indent=2, sort_keys=True))
        return 2

    payload, seal = build_role_manifest(
        records,
        contract,
        audit,
        candidate_manifest_sha256=readiness["candidate_manifest_sha256"],
        contract_sha256=readiness["contract_sha256"],
        analysis_plan_sha256=readiness["analysis_plan_sha256"],
        code_manifest_sha256=readiness["code_manifest_sha256"],
        seed=args.seed,
    )
    (output / "phase04_role_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "phase04_role_manifest.seal.json").write_text(
        json.dumps(seal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "SEALED", "digest": seal["digest"], "records": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
