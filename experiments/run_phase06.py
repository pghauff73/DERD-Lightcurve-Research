#!/usr/bin/env python3
"""Run Phase 06: phase-convention proof gate and lossless exchange schema."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from derd.harmonic_exchange import CanonicalHarmonicSeries, write_harmonic_exchange
from derd.parameters import DERDParameters
from derd.phase_convention import (
    LegacyPhaseSummary,
    ambiguity_bounded_screen,
    audit_legacy_phase_summary,
    frequency_blocks_repeat_under_frozen_source,
    legacy_summary_from_complex_coefficients,
    shift_sine_phases,
    sine_cosine_from_canonical_coefficients,
    source_relative_phases_from_sine_phases,
    standard_epoch_invariant_relative_phases,
)
from derd.spectral import raw_derd_complex_coefficients
from derd.validation_phase06 import (
    Phase06Config,
    calibrate_representation,
    generate_phase_convention_controls,
)
from derd.catalog_harmonics import coefficients_from_amplitude_phase
from derd.harmonic_screen import screen_harmonics


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(json_safe(row))


def source_catalog_audit(root: Path, *, ambiguity_grid_size: int) -> list[dict[str, Any]]:
    payload = json.loads(
        (root / "data/evidence/phase06_frozen_catalog_samples.json").read_text(
            encoding="utf-8"
        )
    )
    rows: list[dict[str, Any]] = []
    for record in payload["records"]:
        amplitude = np.asarray(record["amplitude_blocks"], dtype=np.float64)
        phase = np.asarray(record["relative_phase_blocks"], dtype=np.float64)
        first_norm = max(float(np.linalg.norm(amplitude[0])), np.finfo(float).eps)
        maximum_relative_amplitude_change = float(
            np.max(np.linalg.norm(amplitude[1:] - amplitude[0], axis=1) / first_norm)
        )
        maximum_phase_change = float(np.max(np.abs(phase[1:] - phase[0])))
        summary = LegacyPhaseSummary(amplitude[0], phase[0])
        audit = audit_legacy_phase_summary(summary)
        ambiguity = ambiguity_bounded_screen(
            summary,
            fit_harmonics=4,
            fundamental_phase_grid_size=ambiguity_grid_size,
        )
        rows.append(
            {
                "object_id": record["object_id"],
                "catalog_path": record["catalog_path"],
                "catalog_blob_sha1": record["catalog_blob_sha1"],
                "frozen_source_repeat_invariant": frequency_blocks_repeat_under_frozen_source(
                    amplitude, phase
                ),
                "maximum_relative_amplitude_block_change": maximum_relative_amplitude_change,
                "maximum_absolute_relative_phase_block_change": maximum_phase_change,
                "recoverability": audit.recoverability.value,
                "feasible_fundamental_phase_width": audit.feasible_fundamental_phase.width,
                "quadrant_branch_count": audit.discrete_branch_count_after_global_sign_quotient,
                "recurrence_overidentifying_real_dof": audit.recurrence_overidentifying_real_degrees_of_freedom,
                "qualifies_for_unique_complex_screen": audit.qualifies_for_unique_complex_screen,
                "qualifies_for_harmonic_forecast": audit.qualifies_for_harmonic_forecast,
                "ambiguity_best_score": ambiguity.best_score,
                "ambiguity_median_score": ambiguity.median_score,
                "ambiguity_worst_score": ambiguity.worst_score,
                "flags": ";".join(audit.flags),
            }
        )
    return rows


def epoch_sensitivity() -> list[dict[str, float]]:
    parameters = DERDParameters(0.28, 0.77, 0.62, 0.31)
    base = raw_derd_complex_coefficients(parameters, maximum_harmonic=8)[1:]
    harmonic = np.arange(1, 9, dtype=np.float64)
    rows: list[dict[str, float]] = []
    for epoch in np.linspace(0.0, 1.0, 161, endpoint=False):
        coefficients = base * np.exp(1j * 2.0 * math.pi * harmonic * epoch)
        canonical_full = screen_harmonics(coefficients, fit_harmonics=4).score
        canonical_four = screen_harmonics(coefficients[:4], fit_harmonics=4).score
        summary = legacy_summary_from_complex_coefficients(coefficients[:4])
        unsafe = coefficients_from_amplitude_phase(
            summary.amplitudes,
            summary.relative_phases,
            convention="sine_relative",
            allow_unsafe_relative=True,
        )
        unsafe_score = screen_harmonics(unsafe, fit_harmonics=4).score
        rows.append(
            {
                "epoch_ratio": float(epoch),
                "canonical_full_score": float(canonical_full),
                "canonical_four_score": float(canonical_four),
                "unsafe_relative_score": float(unsafe_score),
            }
        )
    return rows


def phase_invariance_demo() -> dict[str, Any]:
    phases = np.asarray([0.21, -0.77, 1.19, -2.02], dtype=np.float64)
    shift = 0.071
    shifted = shift_sine_phases(phases, epoch_shift_cycles=shift)
    source_before = source_relative_phases_from_sine_phases(phases)
    source_after = source_relative_phases_from_sine_phases(shifted)
    standard_before = standard_epoch_invariant_relative_phases(phases)
    standard_after = standard_epoch_invariant_relative_phases(shifted)
    return {
        "epoch_shift_cycles": shift,
        "source_relative_before": source_before,
        "source_relative_after": source_after,
        "source_max_change": float(np.max(np.abs(source_after - source_before))),
        "standard_relative_before": standard_before,
        "standard_relative_after": standard_after,
        "standard_max_change": float(np.max(np.abs(standard_after - standard_before))),
    }


def write_exchange_example(root: Path) -> dict[str, Any]:
    parameters = DERDParameters(0.33, 0.74, 0.57, 0.26)
    harmonics = 8
    epoch = 0.173
    scale = -1.4
    base = raw_derd_complex_coefficients(parameters, maximum_harmonic=harmonics)[1:]
    n = np.arange(1, harmonics + 1, dtype=np.float64)
    coefficients = scale * base * np.exp(1j * 2.0 * math.pi * n * epoch)
    sine, cosine = sine_cosine_from_canonical_coefficients(coefficients)
    source_bytes = json.dumps(
        {
            "parameters": parameters.as_dict(),
            "epoch": epoch,
            "scale": scale,
            "harmonics": harmonics,
        },
        sort_keys=True,
    ).encode("utf-8")
    series = CanonicalHarmonicSeries(
        object_id="SYNTHETIC-DERD-HEX-001",
        fundamental_frequency=1.0,
        reference_epoch=epoch,
        time_unit="cycle",
        value_unit="arbitrary_normalized_flux",
        sine_coefficients=sine,
        cosine_coefficients=cosine,
        source_locator="synthetic:phase06-fixed-example",
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        metadata={
            "purpose": "lossless exchange-schema positive control",
            "not_observational_evidence": True,
        },
    )
    target = root / "data/examples/phase06_canonical_harmonic_exchange.json"
    digest = write_harmonic_exchange(target, series)
    replay = screen_harmonics(series.complex_coefficients, fit_harmonics=4)
    return {
        "path": str(target.relative_to(root)),
        "record_sha256": digest,
        "harmonic_count": series.harmonic_count,
        "forecast_harmonics": series.recurrence_forecast_harmonics,
        "screen_score": replay.score,
        "evidence_level": replay.evidence_level,
        "flags": list(replay.flags),
    }


def generate_figures(
    output: Path,
    calibrations: dict[str, dict[str, Any]],
    epoch_rows: list[dict[str, float]],
    synthetic_rows: list[dict[str, Any]],
) -> list[str]:
    import matplotlib.pyplot as plt

    generated: list[str] = []
    labels = [
        "Canonical 8\n(4 fit + 4 forecast)",
        "Canonical 4\n(no forecast)",
        "Legacy relative\nunsafe direct",
        "Legacy relative\nambiguity minimum",
    ]
    fields = [
        "canonical_full_score",
        "canonical_four_score",
        "unsafe_relative_score",
        "ambiguity_best_score",
    ]
    auc = [float(calibrations[field]["holdout_metrics"]["roc_auc"]) for field in fields]
    balanced = [
        float(calibrations[field]["holdout_metrics"]["balanced_accuracy"])
        for field in fields
    ]
    x = np.arange(len(fields))
    width = 0.36
    plt.figure(figsize=(9.2, 5.4))
    plt.bar(x - width / 2.0, auc, width=width, label="ROC AUC")
    plt.bar(x + width / 2.0, balanced, width=width, label="Balanced accuracy")
    plt.axhline(0.5, linestyle="--", linewidth=1.0)
    plt.xticks(x, labels)
    plt.ylim(0.0, 1.05)
    plt.ylabel("Held-out discrimination")
    plt.title("Information retained by harmonic representations")
    plt.legend()
    plt.tight_layout()
    path = output / "phase06_information_preservation.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    epoch = [row["epoch_ratio"] for row in epoch_rows]
    canonical = [max(row["canonical_full_score"], 1.0e-15) for row in epoch_rows]
    unsafe = [max(row["unsafe_relative_score"], 1.0e-15) for row in epoch_rows]
    plt.figure(figsize=(9.0, 5.2))
    plt.semilogy(epoch, canonical, label="Canonical signed coefficients, 8 harmonics")
    plt.semilogy(epoch, unsafe, label="Legacy relative phases treated as absolute")
    plt.xlabel("Epoch shift / period")
    plt.ylabel("DERD harmonic-screen score")
    plt.title("Exact DERD waveform: epoch sensitivity introduced by unsafe conversion")
    plt.legend()
    plt.tight_layout()
    path = output / "phase06_epoch_sensitivity.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)

    positive = [row for row in synthetic_rows if row["label"] == 1 and row["split"] == "holdout"]
    negative = [row for row in synthetic_rows if row["label"] == 0 and row["split"] == "holdout"]
    plt.figure(figsize=(8.8, 5.2))
    plt.hist(
        [min(float(row["ambiguity_best_score"]), 10.0) for row in positive],
        bins=25,
        alpha=0.65,
        label="DERD positives",
    )
    plt.hist(
        [min(float(row["ambiguity_best_score"]), 10.0) for row in negative],
        bins=25,
        alpha=0.65,
        label="Generic Fourier nulls",
    )
    plt.xlabel("Best score over missing phase and quadrant branches")
    plt.ylabel("Holdout cases")
    plt.title("Legacy four-harmonic ambiguity search")
    plt.legend()
    plt.tight_layout()
    path = output / "phase06_ambiguity_score_overlap.png"
    plt.savefig(path, dpi=180)
    plt.close()
    generated.append(path.name)
    return generated


def build_report(summary: dict[str, Any]) -> str:
    cal = summary["representation_calibration"]
    source_rows = summary["frozen_source_catalog_audit"]
    lines = [
        "# Phase 06 result: harmonic phase-convention proof gate",
        "",
        f"Status: `{summary['status']}`",
        "",
        "## Research action implemented",
        "",
        "Phase 06 reverse-engineers the phase and amplitude convention used by the discovered harmonic feature tables, tests whether those tables preserve the complex coefficients required by the DERD recurrence, and defines a lossless replacement exchange schema.",
        "",
        "The frozen source fits each harmonic as `a*sin(...) + b*cos(...) + c`, stores `sqrt(a^2+b^2)`, computes phase with `arctan(b/a)`, and then stores `phase_n - phase_1`. This loses coefficient quadrants, omits the absolute fundamental phase, and is not invariant to a change of epoch for harmonics above the fundamental.",
        "",
        "## Synthetic held-out information test",
        "",
        "Thresholds were selected on a deterministic development partition and scored on an independent holdout.",
        "",
        "| Representation | Holdout ROC AUC | Balanced accuracy |",
        "|---|---:|---:|",
    ]
    names = {
        "canonical_full_score": "Canonical signed coefficients, 8 harmonics",
        "canonical_four_score": "Canonical signed coefficients, 4 harmonics",
        "unsafe_relative_score": "Legacy relative phases treated as absolute",
        "ambiguity_best_score": "Best branch of ambiguous legacy row",
    }
    for key, name in names.items():
        metrics = cal[key]["holdout_metrics"]
        lines.append(
            f"| {name} | {metrics['roc_auc']:.4f} | {metrics['balanced_accuracy']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Four harmonics provide zero overidentifying real degrees of freedom for an unconstrained complex order-two recurrence: the recurrence is fitted, not forecast. Six or more harmonics are retained as the minimum two-coefficient forecast gate.",
            "",
            "## Frozen-source provenance audit",
            "",
            "The frozen implementation repeats its three frequency passes on the same unmodified data. Exact execution would therefore repeat all three amplitude and phase blocks. The compact catalog samples do not satisfy that necessary invariant:",
            "",
            "| Object | Blocks repeat? | Maximum relative amplitude-block change |",
            "|---|---:|---:|",
        ]
    )
    for row in source_rows:
        lines.append(
            f"| {row['object_id']} | {row['frozen_source_repeat_invariant']} | {row['maximum_relative_amplitude_block_change']:.3f} |"
        )
    lines.extend(
        [
            "",
            "This does not prove the catalog values are wrong. It proves that the exact frozen source file is insufficient provenance for reproducing those table blocks. A different source revision, hidden state, or undocumented processing step is required.",
            "",
            "## Gate decision",
            "",
            "`LEGACY_FEATURE_TABLES_BLOCKED_FROM_EXACT_DERD_HARMONIC_PROOF`",
            "",
            "Catalog rows may be used for exploratory ranking only after explicit ambiguity labelling. They cannot be promoted to complex-coefficient evidence. The new DERD Harmonic Exchange 1.0 schema stores signed sine and cosine coefficients, reference epoch, fundamental frequency, source digest, and optional covariance, preserving the information needed for a genuine harmonic forecast.",
            "",
            "## Physical scope",
            "",
            "This phase concerns waveform information and provenance only. It does not identify internal radial orbits, a transparent external shell, or a shell mass.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase06"))
    parser.add_argument("--samples-per-class", type=int, default=100)
    parser.add_argument("--ambiguity-grid-size", type=int, default=17)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output
    output.mkdir(parents=True, exist_ok=True)

    config = Phase06Config(
        samples_per_class=args.samples_per_class,
        ambiguity_grid_size=args.ambiguity_grid_size,
    )
    controls = generate_phase_convention_controls(config)
    synthetic_rows = [row.as_dict() for row in controls]
    fields = (
        "canonical_full_score",
        "canonical_four_score",
        "unsafe_relative_score",
        "ambiguity_best_score",
    )
    calibrations = {
        field: calibrate_representation(controls, score_field=field) for field in fields
    }
    catalog_rows = source_catalog_audit(
        root, ambiguity_grid_size=config.ambiguity_grid_size
    )
    epoch_rows = epoch_sensitivity()
    invariance = phase_invariance_demo()
    exchange = write_exchange_example(root)

    summary: dict[str, Any] = {
        "implementation_id": "DERD-v0.6-phase06-phase-convention-gate",
        "status": "PHASE06_PHASE_CONVENTION_GATE_COMPLETE_LEGACY_TABLES_NONQUALIFYING",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "seed": config.seed,
            "samples_per_class": config.samples_per_class,
            "development_fraction": config.development_fraction,
            "harmonics": config.harmonics,
            "fit_harmonics": config.fit_harmonics,
            "ambiguity_grid_size": config.ambiguity_grid_size,
        },
        "representation_calibration": calibrations,
        "frozen_source_catalog_audit": catalog_rows,
        "phase_invariance_demo": invariance,
        "canonical_exchange_positive_control": exchange,
        "source_code_findings": {
            "fit_model": "a*sin(2*pi*f*t)+b*cos(2*pi*f*t)+c",
            "amplitude": "sqrt(a^2+b^2)",
            "stored_phase": "arctan(b/a)",
            "stored_relative_phase": "stored_phase_n-stored_phase_1",
            "frozen_three_pass_data_update": "data2 is computed but never assigned back to data",
            "catalog_proof_qualification": False,
        },
        "gate_decision": "LEGACY_FEATURE_TABLES_BLOCKED_FROM_EXACT_DERD_HARMONIC_PROOF",
        "physical_claim_certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }

    write_csv(output / "phase06_synthetic_information_test.csv", synthetic_rows)
    write_csv(output / "phase06_frozen_source_catalog_audit.csv", catalog_rows)
    write_csv(output / "phase06_epoch_sensitivity.csv", epoch_rows)
    generated = generate_figures(output, calibrations, epoch_rows, synthetic_rows)
    summary["figures"] = generated
    write_json(output / "phase06_summary.json", summary)
    (output / "PHASE06_RESULT.md").write_text(build_report(summary), encoding="utf-8")
    (output / "run.log").write_text(
        json.dumps(json_safe(summary), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(json_safe(summary), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
