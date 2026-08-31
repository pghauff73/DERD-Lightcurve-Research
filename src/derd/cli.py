"""Command-line entry points for deterministic DERD generation and experiments."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .baselines import fit_fourier
from .fitting import fit_waveform
from .historical import PaperEllipseEquation, implied_period_from_paper_axis, paper_waveform
from .iurm import SweepSpec, write_sweep
from .model import TimeLaw, waveform
from .parameters import DERDParameters, DIMENSION_NAMES


def _parameters(namespace: argparse.Namespace) -> DERDParameters:
    return DERDParameters(
        namespace.e1,
        namespace.e2,
        namespace.amplitude_ratio,
        namespace.phase_ratio,
    )


def _add_parameters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--e1", type=float, required=True)
    parser.add_argument("--e2", type=float, required=True)
    parser.add_argument("--amplitude-ratio", type=float, required=True)
    parser.add_argument("--phase-ratio", type=float, required=True)


def _write_curve(path: Path, phase: np.ndarray, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["phase", "value"])
        writer.writerows(zip(phase.tolist(), values.tolist(), strict=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="derd", description="DERD research implementation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate one corrected waveform")
    _add_parameters(generate)
    generate.add_argument("--time-law", choices=[law.value for law in TimeLaw], default="geometric")
    generate.add_argument("--samples", type=int, default=512)
    generate.add_argument("--output", type=Path, required=True)

    sweep = subparsers.add_parser("sweep", help="run an IURMv1.1.1 one-dimension sweep")
    _add_parameters(sweep)
    sweep.add_argument("--active-dimension", choices=DIMENSION_NAMES, required=True)
    sweep.add_argument("--start", type=float, required=True)
    sweep.add_argument("--stop", type=float, required=True)
    sweep.add_argument("--count", type=int, default=11)
    sweep.add_argument("--time-law", choices=[law.value for law in TimeLaw], default="geometric")
    sweep.add_argument("--experiment-id", default="IURM-DERD-SWEEP")
    sweep.add_argument("--output-directory", type=Path, required=True)

    demo = subparsers.add_parser("fit-demo", help="fit deterministic synthetic data")
    _add_parameters(demo)
    demo.add_argument("--time-law", choices=[law.value for law in TimeLaw], default="geometric")
    demo.add_argument("--samples", type=int, default=256)
    demo.add_argument("--starts", type=int, default=8)
    demo.add_argument("--output", type=Path, required=True)

    audit = subparsers.add_parser("audit-historical", help="reproduce printed-code defects")
    audit.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        params = _parameters(args)
        phase = np.linspace(0.0, 1.0, args.samples, endpoint=False)
        values = waveform(phase, params, time_law=args.time_law)
        _write_curve(args.output, phase, values)
        return 0

    if args.command == "sweep":
        base = _parameters(args)
        spec = SweepSpec(
            experiment_id=args.experiment_id,
            active_dimension=args.active_dimension,
            values=tuple(np.linspace(args.start, args.stop, args.count)),
            frozen_parameters=base,
            time_law=TimeLaw(args.time_law),
        )
        write_sweep(spec, args.output_directory)
        return 0

    if args.command == "fit-demo":
        truth = _parameters(args)
        phase = np.linspace(0.0, 1.0, args.samples, endpoint=False)
        target = waveform(phase, truth, time_law=args.time_law)
        fitted = fit_waveform(
            phase,
            target,
            time_law=args.time_law,
            starts=args.starts,
            initial_points=[truth.as_tuple()],
            normalize_target=False,
        )
        fourier = fit_fourier(phase, target, order=2, normalize_target=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "truth": truth.as_dict(),
                    "derd_fit": fitted.as_dict(),
                    "fourier_order_2": fourier.as_dict(),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return 0

    if args.command == "audit-historical":
        cycle = PaperEllipseEquation(0.1).calc(1000)
        first = paper_waveform(0.7, 0.3, 0.3, 0.28)
        second = paper_waveform(0.7, 0.3, 0.3, 0.71)
        payload = {
            "requested_samples": 1000,
            "returned_samples": cycle.sample_count,
            "implied_period_seconds": implied_period_from_paper_axis(),
            "declared_phase_changes_output": bool(not np.array_equal(first, second)),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return 0

    raise AssertionError(f"unhandled command {args.command!r}")
