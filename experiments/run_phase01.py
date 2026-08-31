#!/usr/bin/env python3
"""Build deterministic Phase 0–1 evidence for the DERD roadmap.

The experiment is deliberately synthetic. It verifies software corrections, mathematical
identities, one-dimension interventions, and benchmark plumbing. It does not evaluate a
real star or promote a physical shell claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from derd.baselines import fit_fourier
from derd.fitting import fit_waveform
from derd.geometric import radius_over_semimajor_axis
from derd.historical import (
    PaperEllipseEquation,
    implied_period_from_paper_axis,
    paper_waveform,
)
from derd.iurm import SweepSpec, run_sweep, write_sweep
from derd.model import OutputNormalization, TimeLaw, raw_waveform, waveform
from derd.normalization import positive_affine_invariance_error
from derd.parameters import DERDParameters
from derd.spectral import (
    radius_over_semimajor_axis_series,
    raw_derd_complex_coefficients,
    recurrence_residuals,
    recurrence_roots,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def run(output_directory: Path) -> dict[str, object]:
    output_directory.mkdir(parents=True, exist_ok=True)
    seed = 20260807
    rng = np.random.default_rng(seed)
    phase = np.linspace(0.0, 1.0, 2048, endpoint=False)
    base = DERDParameters(0.20, 0.70, 0.50, 0.30)

    # C02 numerical property check.
    normalization_values = rng.normal(size=4096)
    normalization_error = positive_affine_invariance_error(
        normalization_values, scale=7.3, offset=-42.0
    )

    # C04/C05 historical reconstruction.
    historical_cycle = PaperEllipseEquation(0.1).calc(1000)
    historical_phase_028 = paper_waveform(0.7, 0.3, 0.3, 0.28)
    historical_phase_071 = paper_waveform(0.7, 0.3, 0.3, 0.71)

    # C01/C06 one-dimension activation.
    base_curve = waveform(phase, base, time_law=TimeLaw.GEOMETRIC)
    interventions = {
        "e1": base.with_dimension("e1", 0.45),
        "e2": base.with_dimension("e2", 0.35),
        "amplitude_ratio": base.with_dimension("amplitude_ratio", 0.90),
        "phase_ratio": base.with_dimension("phase_ratio", 0.41),
    }
    activity = {}
    for dimension, parameters in interventions.items():
        values = waveform(phase, parameters, time_law=TimeLaw.GEOMETRIC)
        activity[dimension] = float(np.max(np.abs(values - base_curve)))

    tiny_phase = base.with_dimension("phase_ratio", base.phase_ratio + 1e-5)
    continuous_phase_response = float(
        np.max(np.abs(waveform(phase, tiny_phase) - base_curve))
    )

    # Time-law gate.
    geometric_values = waveform(phase, base, time_law=TimeLaw.GEOMETRIC)
    kepler_values = waveform(phase, base, time_law=TimeLaw.KEPLER)
    time_law_difference = float(np.max(np.abs(geometric_values - kepler_values)))

    # C21 series and recurrence checks.
    exact_radius = radius_over_semimajor_axis(phase, 0.7)
    series_radius = radius_over_semimajor_axis_series(phase, 0.7, terms=80)
    series_error = float(np.max(np.abs(exact_radius - series_radius)))

    spectral_parameters = DERDParameters(0.24, 0.73, 0.62, 0.31)
    analytic_coefficients = raw_derd_complex_coefficients(
        spectral_parameters, maximum_harmonic=24
    )
    z1, z2 = recurrence_roots(spectral_parameters)
    analytic_recurrence = recurrence_residuals(
        analytic_coefficients, z1=z1, z2=z2, first_harmonic=1
    )

    numerical_count = 65536
    numerical_phase = np.linspace(0.0, 1.0, numerical_count, endpoint=False)
    normalized_values = waveform(
        numerical_phase,
        spectral_parameters,
        time_law=TimeLaw.GEOMETRIC,
        output_normalization=OutputNormalization.CANONICAL,
        normalization_grid_size=numerical_count,
    )
    numerical_coefficients = np.fft.fft(normalized_values)[:24] / numerical_count
    numerical_recurrence = recurrence_residuals(
        numerical_coefficients, z1=z1, z2=z2, first_harmonic=1
    )

    # C17 fitting and baseline plumbing on a controlled synthetic object.
    truth = DERDParameters(0.18, 0.72, 0.58, 0.83)
    fit_phase = np.linspace(0.0, 1.0, 256, endpoint=False)
    target = waveform(fit_phase, truth, normalization_grid_size=2048)
    derd_fit = fit_waveform(
        fit_phase,
        target,
        starts=6,
        seed=seed,
        initial_points=[truth.as_tuple()],
        normalization_grid_size=2048,
        max_function_evaluations=180,
        normalize_target=False,
    )
    fourier_fit = fit_fourier(
        fit_phase,
        target,
        order=2,
        normalize_target=False,
    )

    # IURMv1.1.1 one-active-dimension sweeps.
    sweep_specs = [
        SweepSpec(
            "IURM-DERD-E1-001",
            "e1",
            tuple(np.linspace(0.0, 0.9, 10)),
            base,
            samples=512,
        ),
        SweepSpec(
            "IURM-DERD-E2-001",
            "e2",
            tuple(np.linspace(0.0, 0.9, 10)),
            base,
            samples=512,
        ),
        SweepSpec(
            "IURM-DERD-A-001",
            "amplitude_ratio",
            tuple(np.linspace(0.1, 1.2, 12)),
            base,
            samples=512,
        ),
        SweepSpec(
            "IURM-DERD-PHI-001",
            "phase_ratio",
            tuple(np.linspace(0.0, 0.95, 20)),
            base,
            samples=512,
        ),
    ]
    sweep_outputs = []
    for spec in sweep_specs:
        csv_path, json_path = write_sweep(spec, output_directory)
        sweep_outputs.append(
            {
                "experiment_id": spec.experiment_id,
                "csv": csv_path.name,
                "json": json_path.name,
            }
        )

    # Figure: corrected time laws.
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(phase, geometric_values, label="DERD-G geometric phase")
    ax.plot(phase, kepler_values, label="DERD-K Kepler time", linestyle="--")
    ax.set_xlabel("Phase (cycles)")
    ax.set_ylabel("Normalized waveform")
    ax.set_title("Time law is an explicit, testable model dimension")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_directory / "time_law_comparison.png", dpi=180)
    plt.close(fig)

    # Figure: phase defect versus corrected control.
    corrected_phase_028 = waveform(
        phase, DERDParameters(0.7, 0.3, 0.3, 0.28), time_law=TimeLaw.GEOMETRIC
    )
    corrected_phase_071 = waveform(
        phase, DERDParameters(0.7, 0.3, 0.3, 0.71), time_law=TimeLaw.GEOMETRIC
    )
    historical_phase = np.linspace(0.0, 2.0, historical_phase_028.size, endpoint=False)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(
        historical_phase[: historical_phase_028.size // 2],
        historical_phase_028[: historical_phase_028.size // 2],
        label="Printed path, declared phase 0.28",
    )
    ax.plot(
        historical_phase[: historical_phase_071.size // 2],
        historical_phase_071[: historical_phase_071.size // 2],
        label="Printed path, declared phase 0.71",
        linestyle="--",
    )
    ax.plot(phase, corrected_phase_028, label="Corrected phase 0.28")
    ax.plot(phase, corrected_phase_071, label="Corrected phase 0.71", linestyle=":")
    ax.set_xlabel("Phase (cycles)")
    ax.set_ylabel("Normalized waveform")
    ax.set_title("Declared phase is inert historically and active in the correction")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_directory / "phase_control_audit.png", dpi=180)
    plt.close(fig)

    # Figure: one IURM sweep without combining other dimensions.
    e1_rows = run_sweep(sweep_specs[0])
    plot_phase = np.linspace(0.0, 1.0, 512, endpoint=False)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for row in e1_rows[::2]:
        parameters = DERDParameters(
            row["e1"], row["e2"], row["amplitude_ratio"], row["phase_ratio"]
        )
        ax.plot(plot_phase, waveform(plot_phase, parameters), label=f"e1={row['e1']:.2f}")
    ax.set_xlabel("Phase (cycles)")
    ax.set_ylabel("Normalized waveform")
    ax.set_title("IURMv1.1.1: vary e1 while e2, A, and phase remain frozen")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_directory / "iurm_e1_sweep.png", dpi=180)
    plt.close(fig)

    summary = {
        "implementation_id": "DERD-v0.1-phase01",
        "base_commit": "a0d93a2e95cbe9287326897efc419255c1f39610",
        "seed": seed,
        "scope": "synthetic software and mathematical evidence; not real-star or physical-shell validation",
        "normalization": {
            "positive_affine_invariance_max_abs_error": normalization_error,
        },
        "historical_capsule": {
            "requested_samples": 1000,
            "returned_samples_e_0_1": historical_cycle.sample_count,
            "implied_period_seconds_from_0_333_axis": implied_period_from_paper_axis(),
            "declared_phase_changes_output": bool(
                not np.array_equal(historical_phase_028, historical_phase_071)
            ),
        },
        "corrected_model": {
            "base_parameters": base.as_dict(),
            "dimension_activity_max_abs_difference": activity,
            "continuous_phase_delta": 1e-5,
            "continuous_phase_response_max_abs_difference": continuous_phase_response,
            "geometric_vs_kepler_max_abs_difference": time_law_difference,
        },
        "spectral_proof_checks": {
            "radius_series_terms": 80,
            "radius_series_max_abs_error": series_error,
            "analytic_recurrence_max_abs_residual": float(
                np.max(np.abs(analytic_recurrence))
            ),
            "normalized_fft_recurrence_max_abs_residual": float(
                np.max(np.abs(numerical_recurrence))
            ),
        },
        "synthetic_fit": {
            "truth": truth.as_dict(),
            "derd": derd_fit.as_dict(),
            "fourier_order_2": fourier_fit.as_dict(),
            "interpretation": "pipeline shakedown only; the target was generated by DERD",
        },
        "iurm_sweeps": sweep_outputs,
        "generated_figures": [
            "time_law_comparison.png",
            "phase_control_audit.png",
            "iurm_e1_sweep.png",
        ],
    }
    _write_json(output_directory / "phase01_summary.json", summary)

    report_lines = [
        "# DERD Phase 0–1 deterministic result",
        "",
        f"- Base commit: `{summary['base_commit']}`",
        f"- Historical requested/returned samples: 1000/{historical_cycle.sample_count}",
        f"- Historical declared phase changes output: `{summary['historical_capsule']['declared_phase_changes_output']}`",
        f"- Positive-affine normalization error: `{normalization_error:.3e}`",
        f"- Small continuous phase response: `{continuous_phase_response:.3e}`",
        f"- DERD-G versus DERD-K maximum difference: `{time_law_difference:.6f}`",
        f"- Fourier-series maximum error: `{series_error:.3e}`",
        f"- Analytic recurrence maximum residual: `{np.max(np.abs(analytic_recurrence)):.3e}`",
        f"- Normalized FFT recurrence maximum residual: `{np.max(np.abs(numerical_recurrence)):.3e}`",
        f"- Synthetic DERD self-fit RMSE: `{derd_fit.metrics['rmse']:.3e}`",
        "",
        "This result passes software and mathematical gates only. Real-star, mechanism, and shell claims remain locked.",
        "",
    ]
    report = "\n".join(report_lines)
    (output_directory / "PHASE01_RESULT.md").write_text(report, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "artifacts" / "phase01",
    )
    args = parser.parse_args()
    summary = run(args.output_directory)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
