#!/usr/bin/env python3
"""Build the public Phase-19 blind replication kit and private evaluator.

The public kit contains no answer key.  The private evaluator must be withheld
from external operators until their submission hash is frozen.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import stat
import sys
import zipfile

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase12 import sha256_file
from derd.validation_phase19 import (
    PHASE19_IMPLEMENTATION_ID,
    PHASE19_KIT_ID,
    PHASE19_PROTOCOL_ID,
    build_answer_key,
    build_public_tasks,
    canonical_sha256,
    generate_secret_key,
    keyed_answer_commitment,
    load_json,
    write_json,
)


def _write_text(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.name != "KIT_SHA256SUMS.txt":
            yield path


def _write_checksums(root: Path) -> int:
    files = tuple(_iter_files(root))
    (root / "KIT_SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    return len(files)


def _zip_tree(source: Path, destination: Path, *, comment: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.comment = comment.encode("utf-8")
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def _public_readme() -> str:
    return """# DERD Phase-19 blind external replication kit

This kit tests computational portability of the frozen DERD harmonic pipeline.
It contains four opaque synthetic photometry controls and three blinded,
derived observational harmonic-exchange controls. It contains no private
answer key and no complete third-party raw stellar photometry.

## Execute

1. Create an isolated Python 3.10+ environment.
2. Install the exact DERD wheel from `software/` and compatible NumPy/SciPy.
3. Verify the kit:

   `python verify_kit.py`

4. Run every task:

   `python -m derd.phase19_external_runner --kit . --output submission.json --operator-id YOUR_ID --organization YOUR_ORGANIZATION --wheel software/derd_lightcurve-1.9.0-py3-none-any.whl`

5. Freeze and transmit the SHA-256 of `submission.json` before the private
   answer key is disclosed.

## Independence declaration

A numeric match is necessary but not sufficient for an external-replication
edge. The operator must be outside the implementation team, must not receive
the private evaluator before submission, and must execute the commands in an
environment they control.

## Scope

This kit tests software execution, signed harmonic transport, recurrence
screening, uncertainty propagation, and deterministic direct fitting. It does
not establish a unique stellar mechanism, a transparent shell, or a mass
estimate.
"""


def _verify_kit_script() -> str:
    return r'''#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

root = Path(__file__).resolve().parent
manifest = root / "KIT_SHA256SUMS.txt"
failures = []
checked = 0
for line in manifest.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    expected, relative = line.split("  ", 1)
    path = root / relative
    if not path.is_file():
        failures.append(f"missing:{relative}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    checked += 1
    if actual != expected:
        failures.append(f"mismatch:{relative}")
print(f"checked={checked}")
for failure in failures:
    print(failure)
raise SystemExit(1 if failures else 0)
'''


def _private_verifier_script() -> str:
    return r'''#!/usr/bin/env python3
from pathlib import Path
import argparse
import json

from derd.validation_phase19 import (
    Phase19NumericalTolerance,
    verify_submission_against_answer_key,
    write_json,
)

parser = argparse.ArgumentParser()
parser.add_argument("submission", type=Path)
parser.add_argument("--public-protocol", type=Path, required=True)
parser.add_argument("--output", type=Path, default=Path("verification.json"))
args = parser.parse_args()
root = Path(__file__).resolve().parent
answer = json.loads((root / "phase19_answer_key.json").read_text(encoding="utf-8"))
key = bytes.fromhex((root / "phase19_commitment_key.hex").read_text(encoding="utf-8").strip())
protocol = json.loads(args.public_protocol.read_text(encoding="utf-8"))
submission = json.loads(args.submission.read_text(encoding="utf-8"))
verification = verify_submission_against_answer_key(
    submission=submission,
    answer_key=answer,
    secret_key=key,
    public_commitment=protocol["blind_answer_commitment"]["hmac_sha256"],
    tolerance=Phase19NumericalTolerance(**protocol["numerical_tolerance"]),
)
write_json(args.output, verification)
print(json.dumps({
    "output": str(args.output),
    "scientific_projection_reproduced": verification["scientific_projection_reproduced"],
    "all_tasks_passed": verification["all_tasks_passed"],
}, sort_keys=True))
raise SystemExit(0 if verification["scientific_projection_reproduced"] else 1)
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-zip", type=Path, required=True)
    parser.add_argument("--private-zip", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    wheel = args.wheel.resolve()
    public = args.public_dir.resolve()
    private = args.private_dir.resolve()
    for directory in (public, private):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    input_dir = root / "replication/phase19/inputs"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    tasks, private_origin = build_public_tasks(root=root, public_input_dir=input_dir)

    manifest_base = {
        "manifest_id": "DERD-PHASE19-TASK-MANIFEST-1.0",
        "kit_id": PHASE19_KIT_ID,
        "implementation_id": PHASE19_IMPLEMENTATION_ID,
        "date_frozen": "2026-08-24",
        "task_count": len(tasks),
        "task_types": {
            "synthetic_photometry": sum(row["task_type"] == "synthetic_photometry" for row in tasks),
            "observational_exchange": sum(row["task_type"] == "observational_exchange" for row in tasks),
        },
        "tasks": tasks,
        "answer_labels_disclosed": False,
        "raw_third_party_photometry_included": False,
    }
    manifest = dict(manifest_base)
    manifest["sha256_canonical_json"] = canonical_json_sha256(manifest_base)
    manifest_path = root / "data/manifests/phase19_replication_tasks.json"
    write_json(manifest_path, manifest)
    manifest_seal = {
        "manifest_id": manifest["manifest_id"],
        "date_sealed": "2026-08-24",
        "sha256_canonical_json": manifest["sha256_canonical_json"],
    }
    manifest_seal_path = root / "data/manifests/phase19_replication_tasks.seal.json"
    write_json(manifest_seal_path, manifest_seal)

    answer_key = build_answer_key(
        task_manifest=manifest,
        kit_input_dir=input_dir,
        private_origin=private_origin,
    )
    secret = generate_secret_key()
    commitment = keyed_answer_commitment(answer_key, secret)

    parent_summary = root / "artifacts/phase18/phase18_summary.json"
    parent_graph = root / "artifacts/phase18/phase18_reproducibility_graph.json"
    parent_ledger = root / "artifacts/phase18/phase18_cumulative_ledger.json"
    protocol = {
        "protocol_id": PHASE19_PROTOCOL_ID,
        "implementation_id": PHASE19_IMPLEMENTATION_ID,
        "date_frozen": "2026-08-24",
        "parent_phase18": {
            "summary_path": str(parent_summary.relative_to(root)),
            "summary_sha256": sha256_file(parent_summary),
            "graph_path": str(parent_graph.relative_to(root)),
            "graph_sha256": sha256_file(parent_graph),
            "ledger_path": str(parent_ledger.relative_to(root)),
            "ledger_sha256": sha256_file(parent_ledger),
        },
        "public_task_manifest": {
            "path": str(manifest_path.relative_to(root)),
            "sha256": sha256_file(manifest_path),
            "canonical_sha256": manifest["sha256_canonical_json"],
            "task_count": len(tasks),
        },
        "blind_answer_commitment": {
            "algorithm": "HMAC-SHA256",
            "hmac_sha256": commitment,
            "private_key_disclosed_in_public_kit": False,
            "private_answer_key_disclosed_in_public_kit": False,
            "disclosure_time": "after external submission SHA-256 is frozen",
        },
        "numerical_tolerance": {"absolute": 2.0e-7, "relative": 2.0e-6},
        "external_operator_gate": {
            "operator_outside_implementation_team": True,
            "operator_controls_execution_environment": True,
            "no_pre_submission_answer_key_access": True,
            "submission_self_hash_required": True,
            "all_seven_task_projections_must_pass": True,
            "environment_manifest_required": True,
            "signed_operator_attestation_requested": True,
        },
        "local_cleanroom_policy": {
            "may_validate_kit_portability": True,
            "counts_as_external_replication": False,
            "counts_as_independent_astrophysical_replication": False,
        },
        "replication_policy": {
            "successful_external_execution_adds_external_computational_edge": True,
            "successful_external_execution_adds_astronomical_denominator": False,
            "successful_external_execution_adds_independent_observing_source": False,
            "successful_external_execution_proves_physical_mechanism": False,
        },
        "claim_boundary": (
            "Computational portability of a frozen DERD workflow only; no population, "
            "unique mechanism, transparent-shell, prevalence, or mass claim."
        ),
    }
    protocol_path = root / "research/preregistration/phase19_external_group_replay_protocol.json"
    write_json(protocol_path, protocol)
    protocol_seal = {
        "protocol_id": PHASE19_PROTOCOL_ID,
        "date_sealed": "2026-08-24",
        "sha256_canonical_json": canonical_json_sha256(protocol),
    }
    protocol_seal_path = root / "research/preregistration/phase19_external_group_replay_protocol.seal.json"
    write_json(protocol_seal_path, protocol_seal)

    # Public kit.
    _write_text(public / "README.md", _public_readme())
    _write_text(public / "verify_kit.py", _verify_kit_script(), executable=True)
    _write_text(
        public / "run_replication.sh",
        "#!/bin/sh\nset -eu\npython verify_kit.py\npython -m derd.phase19_external_runner --kit . --output submission.json --operator-id \"${OPERATOR_ID:?}\" --organization \"${ORGANIZATION:?}\" --wheel software/derd_lightcurve-1.9.0-py3-none-any.whl\n",
        executable=True,
    )
    _write_text(
        public / "requirements-lock.txt",
        "numpy==2.3.5\nscipy==1.17.0\n",
    )
    _write_text(
        public / "Containerfile",
        "FROM python:3.13-slim\nWORKDIR /opt/phase19\nCOPY . /opt/phase19\nRUN pip install --no-cache-dir numpy==2.3.5 scipy==1.17.0 software/derd_lightcurve-1.9.0-py3-none-any.whl\nENTRYPOINT [\"python\", \"-m\", \"derd.phase19_external_runner\"]\n",
    )
    environment = {
        "reference_python": "3.13.5",
        "reference_numpy": "2.3.5",
        "reference_scipy": "1.17.0",
        "minimum_python": "3.10",
        "cross_platform_tolerance": protocol["numerical_tolerance"],
    }
    write_json(public / "environment-lock.json", environment)
    shutil.copy2(protocol_path, public / "phase19_protocol.json")
    shutil.copy2(protocol_seal_path, public / "phase19_protocol.seal.json")
    (public / "tasks").mkdir()
    shutil.copy2(manifest_path, public / "tasks/task_manifest.json")
    shutil.copy2(manifest_seal_path, public / "tasks/task_manifest.seal.json")
    shutil.copytree(input_dir, public / "inputs")
    (public / "software").mkdir()
    shutil.copy2(wheel, public / "software" / wheel.name)
    submission_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DERD Phase-19 external submission",
        "type": "object",
        "required": [
            "submission_schema",
            "kit_id",
            "task_manifest_sha256",
            "operator",
            "environment",
            "task_results",
            "submission_sha256",
        ],
        "properties": {
            "submission_schema": {"const": "DERD-PHASE19-EXTERNAL-SUBMISSION-1.0"},
            "kit_id": {"const": PHASE19_KIT_ID},
            "task_results": {"type": "array", "minItems": len(tasks), "maxItems": len(tasks)},
        },
    }
    write_json(public / "SUBMISSION_SCHEMA.json", submission_schema)
    kit_metadata = {
        "kit_id": PHASE19_KIT_ID,
        "implementation_id": PHASE19_IMPLEMENTATION_ID,
        "task_count": len(tasks),
        "wheel_file": wheel.name,
        "wheel_sha256": sha256_file(wheel),
        "answer_commitment": commitment,
        "contains_private_answer_key": False,
        "contains_complete_third_party_raw_photometry": False,
    }
    write_json(public / "KIT_METADATA.json", kit_metadata)
    checksum_count = _write_checksums(public)
    _zip_tree(public, args.public_zip.resolve(), comment=PHASE19_KIT_ID)

    # Private evaluator.
    write_json(private / "phase19_answer_key.json", answer_key)
    _write_text(private / "phase19_commitment_key.hex", secret.hex() + "\n")
    _write_text(private / "verify_phase19_submission.py", _private_verifier_script(), executable=True)
    _write_text(
        private / "README_PRIVATE.md",
        "# Private Phase-19 evaluator\n\nDo not transmit this directory or its ZIP to an external operator before the operator's submission SHA-256 is frozen. Install the exact DERD wheel from the public kit, then run `python verify_phase19_submission.py submission.json --public-protocol /path/to/phase19_protocol.json`.\n",
    )
    private_metadata = {
        "kit_id": PHASE19_KIT_ID,
        "answer_key_sha256": sha256_file(private / "phase19_answer_key.json"),
        "commitment_key_sha256": sha256_file(private / "phase19_commitment_key.hex"),
        "public_commitment": commitment,
        "public_kit_sha256": sha256_file(args.public_zip.resolve()),
        "withhold_until_submission_hash_frozen": True,
    }
    write_json(private / "PRIVATE_METADATA.json", private_metadata)
    private_files = [path for path in sorted(private.rglob("*")) if path.is_file()]
    (private / "PRIVATE_SHA256SUMS.txt").write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(private).as_posix()}\n"
            for path in private_files
            if path.name != "PRIVATE_SHA256SUMS.txt"
        ),
        encoding="utf-8",
    )
    _zip_tree(private, args.private_zip.resolve(), comment="DERD-PHASE19-PRIVATE-EVALUATOR")

    build_receipt = {
        "implementation_id": PHASE19_IMPLEMENTATION_ID,
        "kit_id": PHASE19_KIT_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "public_kit_zip": str(args.public_zip.resolve()),
        "public_kit_sha256": sha256_file(args.public_zip.resolve()),
        "private_evaluator_zip": str(args.private_zip.resolve()),
        "private_evaluator_sha256": sha256_file(args.private_zip.resolve()),
        "public_file_count_excluding_checksum": checksum_count,
        "task_count": len(tasks),
        "answer_commitment": commitment,
        "private_answer_in_public_kit": False,
    }
    write_json(root / "artifacts/phase19/phase19_kit_build_receipt.json", build_receipt)
    print(json.dumps(build_receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
