"""Command-line runner for the public Phase-19 blind replication kit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validation_phase19 import build_submission, sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute every task in a sealed DERD Phase-19 replication kit."
    )
    parser.add_argument("--kit", type=Path, required=True, help="extracted public kit directory")
    parser.add_argument("--output", type=Path, required=True, help="submission JSON destination")
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--wheel", type=Path, help="optional installed wheel path for provenance")
    args = parser.parse_args()
    wheel_sha = None
    if args.wheel is not None:
        if not args.wheel.is_file():
            raise FileNotFoundError(args.wheel)
        wheel_sha = sha256_file(args.wheel)
    submission = build_submission(
        kit_root=args.kit,
        operator_id=args.operator_id,
        organization=args.organization,
        wheel_sha256=wheel_sha,
    )
    write_json(args.output, submission)
    print(json.dumps({
        "submission": str(args.output),
        "submission_sha256": submission["submission_sha256"],
        "task_count": len(submission["task_results"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
