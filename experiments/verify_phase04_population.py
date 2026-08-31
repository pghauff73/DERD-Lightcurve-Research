#!/usr/bin/env python3
"""Verify a Phase-04 role seal and its linked source artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from derd.population import verify_role_manifest
from derd.provenance import sha256_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("role_manifest")
    parser.add_argument("seal_file")
    parser.add_argument("--candidate-manifest")
    parser.add_argument("--contract")
    parser.add_argument("--analysis-plan")
    parser.add_argument("--code-manifest")
    args = parser.parse_args()

    payload = json.loads(Path(args.role_manifest).read_text(encoding="utf-8"))
    seal = json.loads(Path(args.seal_file).read_text(encoding="utf-8"))
    checks = {
        "role_seal": verify_role_manifest(payload, seal),
    }
    linked = (
        ("candidate_manifest", args.candidate_manifest, "candidate_manifest_sha256"),
        ("contract", args.contract, "contract_sha256"),
        ("analysis_plan", args.analysis_plan, "analysis_plan_sha256"),
        ("code_manifest", args.code_manifest, "code_manifest_sha256"),
    )
    for label, path_text, key in linked:
        if path_text is None:
            continue
        checks[label] = sha256_path(path_text) == str(payload.get(key, ""))
    valid = all(checks.values())
    print(json.dumps({"valid": valid, "checks": checks, "digest": seal.get("digest")}, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
