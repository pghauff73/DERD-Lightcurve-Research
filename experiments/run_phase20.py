#!/usr/bin/env python3
"""Execute DERD Phase 20: multiband projection and mechanism falsification."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from derd.harmonic_exchange import (
    CanonicalHarmonicSeries,
    read_harmonic_exchange,
    write_harmonic_exchange,
)
from derd.harmonic_extraction import fit_weighted_harmonic_exchange
from derd.io import read_ogle_photometry, sha256_file
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase20 import (
    compare_invariants,
    effective_mass_controls,
    optimal_circular_shape_rmse,
)

PHASE_ID = "DERD-v2.0-phase20-multiband-mechanism-falsification"
DECISION = (
    "PHASE20_MULTIBAND_AND_MECHANISM_TESTS_COMPLETE_"
    "STRICT_PASSBAND_INVARIANCE_REJECTED_DERD_UNIQUENESS_REJECTED_"
    "GRAVITY_ONLY_PERIODIC_MOTION_FORMALLY_REJECTED"
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _verify_source(path: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    actual = {
        "path": str(path),
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
        "observation_count": len(lines),
    }
    checks = {
        "sha256": actual["sha256"] == expected["sha256"],
        "byte_count": actual["byte_count"] == expected["byte_count"],
        "observation_count": actual["observation_count"] == expected["observation_count"],
    }
    if not all(checks.values()):
        raise ValueError(f"source verification failed for {path}: {checks}")
    return {**actual, "checks": checks, "all_checks_pass": True}


def _fit_v_series(
    root: Path,
    source_row: Mapping[str, Any],
    *,
    period_days: float,
    reference_epoch: float,
    label: str,
) -> tuple[CanonicalHarmonicSeries, dict[str, Any]]:
    path = root / source_row["source_relative_path"]
    curve = read_ogle_photometry(
        path,
        star_id="OGLE-LMC-CEP-0002",
        band="V",
        metadata={
            "source_locator": source_row.get("url", source_row["source_relative_path"]),
            "source_role": "Phase-20 passband projection experiment",
            "source_scope": label,
        },
    )
    extraction = fit_weighted_harmonic_exchange(
        curve,
        period_days=period_days,
        order=8,
        reference_epoch=reference_epoch,
        ridge=1.0e-4,
        covariance_estimator="hc3",
        source_locator=source_row.get("url", source_row["source_relative_path"]),
        source_sha256=source_row["sha256"],
        metadata={
            "phase": 20,
            "scope": label,
            "claim_boundary": "signed harmonic and passband-shape evidence only",
        },
    )
    diagnostics = extraction.as_dict(include_exchange=False)
    diagnostics["source_scope"] = label
    return extraction.series, diagnostics


def _comparison_row(name: str, comparison: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "comparison": name,
        "mahalanobis_chi_square": comparison.mahalanobis_chi_square,
        "degrees_of_freedom": comparison.degrees_of_freedom,
        "p_value": comparison.p_value,
    }
    for index, label in enumerate(comparison.first.labels):
        row[f"first_{label}"] = comparison.first.vector[index]
        row[f"first_{label}_se"] = comparison.first.standard_error[index]
        row[f"second_{label}"] = comparison.second.vector[index]
        row[f"second_{label}_se"] = comparison.second.standard_error[index]
        row[f"delta_{label}"] = comparison.difference[index]
    return row


def _model_rows(comparison: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in comparison["rmse"]:
        rows.append(
            {
                "model": name,
                "rmse": comparison["rmse"][name],
                "bic": comparison["bic"][name],
                "bootstrap_wins": comparison["bootstrap_wins"][name],
                "bootstrap_draws": comparison["bootstrap_draws"],
            }
        )
    return rows


def _plot_invariants(path: Path, comparison: Any) -> None:
    labels = list(comparison.first.labels)
    x = np.arange(len(labels))
    width = 0.18
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    axis.errorbar(
        x - width,
        comparison.first.vector,
        yerr=comparison.first.standard_error,
        fmt="o",
        capsize=4,
        label="I band",
    )
    axis.errorbar(
        x + width,
        comparison.second.vector,
        yerr=comparison.second.standard_error,
        fmt="o",
        capsize=4,
        label="V band",
    )
    axis.set_xticks(x, labels)
    axis.set_ylabel("Harmonic invariant")
    axis.set_title("OGLE-LMC-CEP-0002: I versus merged V harmonic invariants")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_model_comparison(path: Path, comparison: Mapping[str, Any]) -> None:
    names = list(comparison["bic"])
    values = np.asarray([comparison["bic"][name] for name in names], dtype=float)
    values -= float(np.min(values))
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    axis.bar(np.arange(len(names)), values)
    axis.set_xticks(np.arange(len(names)), [name.replace("_", "\n") for name in names])
    axis.set_ylabel("ΔBIC from best representation-level model")
    axis.set_title("Passband model comparison")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_tournament(path: Path, rows: list[Mapping[str, Any]]) -> None:
    names = [str(row["family"]).replace("_", "\n") for row in rows]
    values = [float(row["joint_fit_and_screen_pass_fraction"]) for row in rows]
    figure, axis = plt.subplots(figsize=(12.0, 6.0))
    axis.bar(np.arange(len(rows)), values)
    axis.set_xticks(np.arange(len(rows)), names, rotation=25, ha="right")
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Holdout joint fit-and-screen pass fraction")
    axis.set_title("Synthetic mechanism tournament: DERD gate is not unique")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_effective_mass(path: Path, controls: list[Mapping[str, Any]]) -> None:
    names = [str(row["model_id"]).replace("_", "\n") for row in controls]
    values = [float(row["positive_mass_fraction"]) for row in controls]
    figure, axis = plt.subplots(figsize=(10.0, 5.5))
    axis.bar(np.arange(len(controls)), values)
    axis.axhline(0.95, linestyle="--", linewidth=1.2, label="frozen pass threshold")
    axis.set_xticks(np.arange(len(controls)), names)
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Fraction with positive inferred M_eff")
    axis.set_title("Gravity-only effective-mass controls")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _report(summary: Mapping[str, Any]) -> str:
    iv = summary["multiband"]["comparisons"]["I_vs_V_merged"]
    vv = summary["multiband"]["comparisons"]["V_OGLEIII_vs_V_OGLEIV"]
    shape = summary["multiband"]["shape_model_comparison"]
    tournament = summary["mechanism_tournament"]
    controls = summary["gravity_only_test"]["controls"]
    family_rows = tournament["holdout_family_summary"]
    nonderd_passers = [
        row for row in family_rows
        if row["family"] != "derd_geometric"
        and row["joint_fit_and_screen_pass_fraction"] > 0.0
    ]
    nonderd_lines = "\n".join(
        f"- `{row['family']}`: joint pass fraction {row['joint_fit_and_screen_pass_fraction']:.3f}"
        for row in nonderd_passers
    ) or "- No non-DERD family passed."
    control_lines = "\n".join(
        f"- `{row['model_id']}`: positive-mass fraction {row['positive_mass_fraction']:.3f}, "
        f"CV {row['coefficient_of_variation_positive']:.3f}, pass={row['gate_pass']}"
        for row in controls
    )
    return f"""# DERD Phase 20 Result\n\n## Decision\n\n```text\n{summary['decision']}\nC17_OPEN_NOT_PROMOTED\nNOT_A_PHYSICAL_CLAIM_CERTIFICATE\n```\n\nPhase 20 performs three orthogonal falsification experiments: a real I-versus-V passband test, a synthetic mechanism tournament, and a gravity-only effective-mass test.\n\n## Experiment A: passband invariance\n\nFor `OGLE-LMC-CEP-0002`, the I-band and merged V-band harmonic invariant vectors differ strongly:\n\n- joint Mahalanobis statistic: **{iv['mahalanobis_chi_square']:.6f}** on {iv['degrees_of_freedom']} dimensions;\n- p-value: **{iv['p_value']:.3e}**.\n\nBy contrast, the two V-band observing epochs are mutually consistent:\n\n- OGLE-III V versus OGLE-IV V p-value: **{vv['p_value']:.6f}**.\n\nThis rejects one strict band-invariant normalized waveform for this exposed-development star. It does not reject a shared physical oscillator projected through band-dependent temperature, opacity, or atmospheric weights.\n\nThe representation-level comparison favours shared latent components with band-specific weights:\n\n- strict shared DERD RMSE: **{shape['rmse']['shared_derd']:.6f}**;\n- separate DERD RMSE: **{shape['rmse']['separate_derd']:.6f}**;\n- shared-components RMSE: **{shape['rmse']['shared_components_band_weights']:.6f}**;\n- shared-components bootstrap wins: **{shape['bootstrap_wins']['shared_components_band_weights']} / {shape['bootstrap_draws']}**.\n\nThis BIC comparison is explicitly representation-level. It uses covariance-sampled h1-h8 reconstructions, not independent raw points.\n\n## Experiment B: mechanism tournament\n\nThresholds were selected only from development DERD positives and generic-Fourier nulls, then applied to held-out cases from ten frozen mechanism families. Several non-DERD families passed both the nonlinear fit and harmonic-screen gates:\n\n{nonderd_lines}\n\nTherefore, a good DERD fit plus a low harmonic-screen score is **not a unique gravitational signature**. The mechanism generators are controlled surrogates, not full stellar-evolution models, so the experiment disproves uniqueness rather than estimating astrophysical prevalence.\n\n## Experiment C: gravity-only effective mass\n\nFor a gravity-only radial trajectory,\n\n\\[\nM_{{\\rm eff}}(t)=-\\frac{{R(t)^2\\ddot R(t)}}{{G}}\n\\]\n\nmust remain positive and approximately constant. The inverse-square ballistic control passes; every nonconstant periodic control fails:\n\n{control_lines}\n\nThere is also a formal contradiction: at a local minimum of any nonconstant twice-differentiable periodic radius, \\(\\ddot R\\ge0\\), while gravity-only inverse-square motion requires \\(\\ddot R=-GM/R^2<0\\). A positive-mass gravity-only force cannot sustain a periodic radial breathing cycle without an outward force.\n\n## Integrated conclusion\n\nThe following claims are rejected or narrowed:\n\n1. one normalized DERD curve is passband invariant for this test star;\n2. DERD fit and recurrence structure uniquely identify gravity;\n3. positive-mass gravity alone sustains periodic radial pulsation.\n\nThe strongest surviving model is a gravity-restored nonlinear hydrodynamic oscillator whose radius, temperature, opacity, and atmosphere project differently into each passband. DERD may remain useful as a reduced coordinate system, but its parameters are not yet uniquely physical.\n"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bootstrap-draws", type=int, default=64)
    parser.add_argument("--tournament-cases", type=int, default=30)
    parser.add_argument("--invariant-draws", type=int, default=20000)
    parser.add_argument("--reuse-workers", action="store_true", help="reuse precomputed isolated worker JSON files")
    args = parser.parse_args()
    root = args.root.resolve()
    artifacts = root / "artifacts" / "phase20"
    artifacts.mkdir(parents=True, exist_ok=True)
    exchanges = artifacts / "harmonic_exchange"
    exchanges.mkdir(parents=True, exist_ok=True)

    source_manifest = json.loads(
        (root / "data/manifests/phase20_multiband_sources.json").read_text(encoding="utf-8")
    )
    source_receipt: dict[str, Any] = {"manifest_id": source_manifest["manifest_id"], "sources": []}
    for row in source_manifest["v_sources"]:
        source_receipt["sources"].append(
            _verify_source(root / row["source_relative_path"], row)
        )
    source_receipt["all_sources_pass"] = all(row["all_checks_pass"] for row in source_receipt["sources"])
    _write_json(artifacts / "phase20_source_verification.json", source_receipt)

    i_series = read_harmonic_exchange(
        root / source_manifest["i_harmonic_exchange"]["relative_path"]
    )
    period_days = 1.0 / i_series.fundamental_frequency
    reference_epoch = i_series.reference_epoch
    v_series: dict[str, CanonicalHarmonicSeries] = {}
    v_diagnostics: list[dict[str, Any]] = []
    for row in source_manifest["v_sources"]:
        label = str(row["source_id"])
        series, diagnostics = _fit_v_series(
            root,
            row,
            period_days=period_days,
            reference_epoch=reference_epoch,
            label=label,
        )
        v_series[label] = series
        diagnostics["exchange_sha256"] = write_harmonic_exchange(
            exchanges / f"OGLE-LMC-CEP-0002_{label}.json", series
        )
        v_diagnostics.append(diagnostics)

    comparisons = {
        "I_vs_V_merged": compare_invariants(
            i_series,
            v_series["merged_v"],
            draws=args.invariant_draws,
            first_seed=20260825,
            second_seed=20260826,
        ),
        "I_vs_V_OGLEIII": compare_invariants(
            i_series,
            v_series["ogleiii_v"],
            draws=args.invariant_draws,
            first_seed=20260827,
            second_seed=20260828,
        ),
        "V_OGLEIII_vs_V_OGLEIV": compare_invariants(
            v_series["ogleiii_v"],
            v_series["ogleiv_v"],
            draws=args.invariant_draws,
            first_seed=20260829,
            second_seed=20260830,
        ),
    }
    comparison_rows = [
        _comparison_row(name, comparison) for name, comparison in comparisons.items()
    ]
    _write_csv(artifacts / "phase20_harmonic_invariant_comparisons.csv", comparison_rows)

    shape_lag = {
        "I_vs_V_merged": optimal_circular_shape_rmse(i_series, v_series["merged_v"]),
        "I_vs_V_OGLEIII": optimal_circular_shape_rmse(i_series, v_series["ogleiii_v"]),
    }
    worker_environment = dict(os.environ)
    worker_environment["PYTHONPATH"] = str(root / "src")
    worker_environment.setdefault("OMP_NUM_THREADS", "1")
    worker_environment.setdefault("OPENBLAS_NUM_THREADS", "1")
    worker_environment.setdefault("MKL_NUM_THREADS", "1")

    shape_worker_output = artifacts / "phase20_passband_shape_worker.json"
    if not args.reuse_workers:
        subprocess.run(
            [
                sys.executable,
                str(root / "experiments/run_phase20_shape_worker.py"),
                "--root",
                str(root),
                "--bootstrap-draws",
                str(args.bootstrap_draws),
                "--output",
                str(shape_worker_output),
            ],
            check=True,
            env=worker_environment,
        )
    elif not shape_worker_output.is_file():
        raise FileNotFoundError(shape_worker_output)
    shape_models = json.loads(shape_worker_output.read_text(encoding="utf-8"))
    _write_csv(artifacts / "phase20_passband_model_comparison.csv", _model_rows(shape_models))

    tournament_worker_output = artifacts / "phase20_mechanism_tournament.json"
    if not args.reuse_workers:
        subprocess.run(
            [
                sys.executable,
                str(root / "experiments/run_phase20_tournament_worker.py"),
                "--cases",
                str(args.tournament_cases),
                "--output",
                str(tournament_worker_output),
            ],
            check=True,
            env=worker_environment,
        )
    elif not tournament_worker_output.is_file():
        raise FileNotFoundError(tournament_worker_output)
    tournament = json.loads(tournament_worker_output.read_text(encoding="utf-8"))
    tournament_rows = [dict(row) for row in tournament["holdout_family_summary"]]
    _write_csv(artifacts / "phase20_mechanism_tournament_summary.csv", tournament_rows)
    _write_csv(
        artifacts / "phase20_mechanism_tournament_records.csv",
        [dict(record) for record in tournament["records"]],
    )

    controls = [control.as_dict() for control in effective_mass_controls()]
    _write_csv(artifacts / "phase20_effective_mass_controls.csv", controls)

    gravity_theorem = {
        "theorem_id": "PHASE20-GRAVITY-ONLY-PERIODIC-RADIAL-IMPOSSIBILITY",
        "statement": (
            "No nonconstant twice-differentiable positive periodic radius R(t) can satisfy "
            "R_ddot=-G*M/R^2 for constant G>0 and M>0 at every time."
        ),
        "proof": (
            "A nonconstant continuous periodic function attains a local minimum. At a twice-differentiable "
            "minimum, R_ddot is non-negative. The inverse-square equation requires R_ddot<0 for all positive R. "
            "The conditions contradict."
        ),
        "scope": "gravity-only radial equation with constant positive enclosed mass and no outward force",
        "does_not_exclude": [
            "gravity-restored hydrodynamic pulsation with pressure and thermal forces",
            "nonradial orbital motion with angular momentum",
            "time-dependent or additional forces",
        ],
    }
    _write_json(artifacts / "phase20_gravity_only_theorem.json", gravity_theorem)

    summary = {
        "phase_id": PHASE_ID,
        "decision": DECISION,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "object_id": "OGLE-LMC-CEP-0002",
        "claim_boundary": (
            "passband projection, synthetic mechanism non-uniqueness, and gravity-only mathematical falsification"
        ),
        "multiband": {
            "period_days": period_days,
            "reference_epoch": reference_epoch,
            "v_extraction_diagnostics": v_diagnostics,
            "comparisons": {name: value.as_dict() for name, value in comparisons.items()},
            "shape_lag": shape_lag,
            "shape_model_comparison": shape_models,
            "strict_band_invariance_rejected": comparisons["I_vs_V_merged"].p_value < 0.01,
            "same_band_epoch_invariance_rejected": comparisons["V_OGLEIII_vs_V_OGLEIV"].p_value < 0.01,
        },
        "mechanism_tournament": {key: value for key, value in tournament.items() if key != "records"},
        "gravity_only_test": {
            "formal_theorem": gravity_theorem,
            "controls": controls,
            "ballistic_positive_control_passed": controls[0]["gate_pass"],
            "all_periodic_controls_failed": all(not row["gate_pass"] for row in controls[1:]),
        },
        "integrated_interpretation": {
            "rejected": [
                "strict passband-invariant normalized waveform for this exposed-development star",
                "unique gravitational interpretation of DERD fit plus harmonic recurrence",
                "positive-mass gravity-only periodic radial pulsation",
            ],
            "survives": [
                "DERD as an approximate reduced harmonic coordinate system",
                "gravity-restored nonlinear hydrodynamics",
                "band-dependent radius-temperature-opacity-atmosphere projection",
                "subclass mechanisms such as mode coupling, tides, shocks, rotation, and circumstellar reprocessing",
            ],
        },
    }
    summary["sha256_canonical_json"] = canonical_json_sha256(summary)
    _write_json(artifacts / "phase20_summary.json", summary)
    (artifacts / "PHASE20_RESULT.md").write_text(_report(summary), encoding="utf-8")

    _plot_invariants(artifacts / "phase20_multiband_invariants.png", comparisons["I_vs_V_merged"])
    _plot_model_comparison(artifacts / "phase20_passband_model_comparison.png", shape_models)
    _plot_tournament(artifacts / "phase20_mechanism_tournament.png", tournament_rows)
    _plot_effective_mass(artifacts / "phase20_effective_mass_controls.png", controls)

    print(f"phase_id={PHASE_ID}")
    print(f"decision={DECISION}")
    print(f"I_vs_V_p={comparisons['I_vs_V_merged'].p_value:.6e}")
    print(f"V_epoch_p={comparisons['V_OGLEIII_vs_V_OGLEIV'].p_value:.6e}")
    print(
        "shared_component_wins="
        f"{shape_models['bootstrap_wins']['shared_components_band_weights']}/{shape_models['bootstrap_draws']}"
    )
    print(f"summary={artifacts / 'phase20_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
