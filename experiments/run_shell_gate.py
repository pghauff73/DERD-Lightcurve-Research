#!/usr/bin/env python3
"""Evaluate one explicitly dimensional transparent-shell feasibility point."""
from __future__ import annotations

import argparse
import json

from derd.shell import evaluate_shell, minimum_radius_for_optical_depth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell-mass-kg", type=float, required=True)
    parser.add_argument("--shell-radius-m", type=float, required=True)
    parser.add_argument("--opacity-m2-per-kg", type=float, required=True)
    parser.add_argument("--covering-fraction", type=float, default=1.0)
    parser.add_argument("--maximum-optical-depth", type=float, default=0.1)
    args = parser.parse_args()
    point = evaluate_shell(
        args.shell_mass_kg,
        args.shell_radius_m,
        args.opacity_m2_per_kg,
        covering_fraction=args.covering_fraction,
    )
    payload = point.as_dict()
    payload["minimum_radius_for_maximum_optical_depth_m"] = minimum_radius_for_optical_depth(
        args.shell_mass_kg,
        args.opacity_m2_per_kg,
        args.maximum_optical_depth,
        covering_fraction=args.covering_fraction,
    )
    payload["scope"] = "dimensional feasibility calculation; not a shell detection or mass inference"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
