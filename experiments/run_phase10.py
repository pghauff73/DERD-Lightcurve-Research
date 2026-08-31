#!/usr/bin/env python3
"""Run Phase 10: authoritative metadata/source lock and optional cohort execution."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping

import numpy as np

from derd.harmonic_exchange import write_harmonic_exchange
from derd.validation_phase07 import Phase07Config
from derd.validation_phase08 import Phase08Config, Phase08Target, assess_cohort
from derd.validation_phase09 import wilson_interval
from derd.validation_phase10 import Phase10Assessment, assess_phase10, synthetic_catalog_lock_control


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def readiness_rows(assessment: Phase10Assessment) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in assessment.targets:
        rows.append({
            "object_id": item.target.object_id,
            "family": item.target.family,
            "metadata_lock_required": item.target.metadata_lock_required,
            "metadata_ready": item.metadata_ready,
            "source_ready": item.source_ready,
            "cached_result_ready": item.cached_result_ready,
            "execution_ready": item.execution_ready,
            "effective_object_id": item.effective_object_id,
            "effective_mode": item.effective_mode,
            "effective_period_days": item.effective_period_days,
            "effective_period_error_days": item.effective_period_error_days,
            "blocker_count": len(item.blockers),
            "blockers": "|".join(item.blockers),
        })
    return rows


def blocker_rows(assessment: Phase10Assessment) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    for item in assessment.targets:
        for blocker in item.blockers:
            row = counts.setdefault(blocker, {family: 0 for family in assessment.family_counts})
            row[item.target.family] += 1
    rows: list[dict[str, Any]] = []
    for blocker, per_family in counts.items():
        rows.append({"blocker": blocker, **per_family, "total": sum(per_family.values())})
    return sorted(rows, key=lambda row: (-row["total"], row["blocker"]))


def family_readiness_rows(assessment: Phase10Assessment) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in assessment.family_counts:
        subset = [item for item in assessment.targets if item.target.family == family]
        rows.append({
            "family": family,
            "declared_count": len(subset),
            "metadata_ready_count": sum(item.metadata_ready for item in subset),
            "source_ready_count": sum(item.source_ready for item in subset),
            "cached_result_count": sum(item.cached_result_ready for item in subset),
            "execution_ready_count": sum(item.execution_ready for item in subset),
            "primary_fraction_suppressed": assessment.primary_outputs_suppressed,
        })
    return rows


def execute_complete_cohort(
    assessment: Phase10Assessment,
    *,
    root: Path,
    output: Path,
    fast: bool,
) -> Mapping[str, Any]:
    if not assessment.cohort_execution_ready:
        raise RuntimeError("Phase-10 cohort is not execution-ready")
    target_config = Phase07Config(
        synthetic_samples_per_class=96,
        propagation_draws=2048,
        observation_sweep_counts=(),
        observation_sweep_repetitions=1,
        minimum_observations=240,
        period_grid_count=101,
    )
    if fast:
        target_config = replace(target_config, synthetic_samples_per_class=24, propagation_draws=256, period_grid_count=51)
    converted: list[Phase08Target] = []
    for item in assessment.targets:
        source = item.phase09_source
        target = item.target.phase09
        expected_sha = source.effective_expected_sha256
        if expected_sha is None:
            raise RuntimeError(f"missing frozen SHA-256 for {target.object_id}")
        period_grade = target.period_evidence_grade
        mode = item.effective_mode
        period_source = target.period_source
        object_id = target.object_id
        if item.target.metadata_lock_required:
            period_grade = "EXTERNAL_CATALOG_OGLE_IV_PRIMARY_PERIOD"
            period_source = "OGLE-IV LMC DSCT authoritative metadata lock"
            object_id = item.effective_object_id
        converted.append(Phase08Target(
            object_id=object_id,
            family=target.family,
            mode=mode,
            catalog_period_days=item.effective_period_days,
            period_evidence_grade=period_grade,
            source_relative_path=target.source_relative_path,
            source_repository_path=target.source_repository_path,
            source_git_blob_sha1=target.source_git_blob_sha1,
            source_sha256=expected_sha,
            source_byte_count=target.source_byte_count,
            source_repository=target.source_repository,
            source_commit=target.source_commit,
            period_source=period_source,
            evidence_role=target.evidence_role,
        ))
    cohort = assess_cohort(
        converted,
        root=root,
        config=Phase08Config(
            target_config=target_config,
            minimum_objects_per_family_for_population_inference=5,
            minimum_total_objects_for_population_inference=15,
        ),
    )
    exchange_dir = output / "harmonic_exchange"
    for item in cohort.targets:
        target = item.target
        exchange = item.result.harmonic_fit.to_exchange(
            object_id=target.object_id,
            time_unit="day",
            value_unit="relative_flux",
            source_locator=target.source_locator,
            source_sha256=target.source_sha256,
            metadata={
                "phase": "10",
                "family": target.family,
                "mode": target.mode,
                "catalog_period_days": target.catalog_period_days,
                "period_evidence_grade": target.period_evidence_grade,
                "period_source": target.period_source,
                "evidence_role": target.evidence_role,
                "physical_claim_scope": "waveform-only",
            },
        )
        write_harmonic_exchange(exchange_dir / f"{target.object_id}.json", exchange)
    family_outputs: list[dict[str, Any]] = []
    for family_row in cohort.family_summary:
        row = dict(family_row)
        n = int(row["object_count"])
        for label, count_key in (
            ("recovery", "recovery_ready_count"),
            ("forecast", "forecast_measured_count"),
            ("structural", "structurally_compatible_count"),
            ("qualified", "qualified_count"),
        ):
            count = int(row[count_key])
            low, high = wilson_interval(count, n)
            row[f"{label}_fraction"] = count / n
            row[f"{label}_wilson95_low"] = low
            row[f"{label}_wilson95_high"] = high
        family_outputs.append(row)
    return {
        "status": "PHASE10_COMPLETE_COHORT_EXECUTED",
        "cohort": cohort.as_dict(include_controls=False),
        "primary_family_outputs": family_outputs,
    }


def make_figures(output: Path, assessment: Phase10Assessment) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    output.mkdir(parents=True, exist_ok=True)
    figures: list[str] = []
    labels = [item.target.object_id.replace("OGLE-LMC-", "") for item in assessment.targets]
    matrix = np.asarray([
        [float(item.metadata_ready), float(item.source_ready), float(item.cached_result_ready), float(item.execution_ready)]
        for item in assessment.targets
    ])
    fig = plt.figure(figsize=(11.2, 7.6))
    ax = fig.add_subplot(111)
    image = ax.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_xticks(np.arange(4), ["metadata lock", "source lock", "cached result", "execution ready"], rotation=18, ha="right")
    ax.set_title("Phase 10 authoritative input-lock readiness")
    fig.colorbar(image, ax=ax, ticks=[0, 1], label="gate pass")
    fig.tight_layout()
    path = output / "phase10_readiness_matrix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    blockers = blocker_rows(assessment)[:14]
    fig = plt.figure(figsize=(11.5, 7.2))
    ax = fig.add_subplot(111)
    ax.barh(np.arange(len(blockers)), [row["total"] for row in blockers])
    ax.set_yticks(np.arange(len(blockers)), [row["blocker"].replace("_", " ").title() for row in blockers])
    ax.invert_yaxis()
    ax.set_xlabel("declared targets affected")
    ax.set_title("Phase 10 EDOv1 blockers")
    fig.tight_layout()
    path = output / "phase10_blocker_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)

    family_rows = family_readiness_rows(assessment)
    x = np.arange(len(family_rows))
    width = 0.24
    fig = plt.figure(figsize=(9.5, 6.2))
    ax = fig.add_subplot(111)
    ax.bar(x - width, [row["metadata_ready_count"] for row in family_rows], width, label="metadata")
    ax.bar(x, [row["source_ready_count"] for row in family_rows], width, label="sources")
    ax.bar(x + width, [row["cached_result_count"] for row in family_rows], width, label="cached results")
    ax.set_xticks(x, [row["family"].replace("_", " ").title() for row in family_rows])
    ax.set_ylim(0, 5.4)
    ax.set_ylabel("objects passing gate")
    ax.set_title("Phase 10 family evidence coverage")
    ax.legend()
    fig.tight_layout()
    path = output / "phase10_family_readiness.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path.name)
    return figures


def build_report(summary: Mapping[str, Any]) -> str:
    assessment = summary["assessment"]
    control = summary["synthetic_catalog_lock_control"]
    return f"""# DERD Phase 10 Result\n\n## Decision\n\n```text\n{assessment['decision']}\nC17_OPEN_NOT_PROMOTED\nNOT_A_PHYSICAL_CLAIM_CERTIFICATE\n```\n\nPhase 10 freezes the authoritative metadata and replayable source coordinates required by the Phase-09 5+5+5 denominator. It does not weaken the waveform-only claim boundary and it does not infer shell mass, literal internal orbits, or a transparent exterior shell.\n\n## Gate status\n\n| Gate | Result |\n|---|---:|\n| Protocol seal valid | {assessment['protocol_valid']} |\n| Catalog contract valid | {assessment['catalog_contract_valid']} |\n| Exact 5+5+5 cohort | {assessment['cohort_structure_ready']} |\n| Claim-grade metadata locks | {assessment['metadata_ready_count']} / 15 |\n| Replay-ready raw sources | {assessment['source_ready_count']} / 15 |\n| Cryptographically verified cached results | {assessment['cached_result_count']} / 15 |\n| Objects executable now | {assessment['execution_ready_count']} / 15 |\n| Primary family outputs suppressed | {assessment['primary_outputs_suppressed']} |\n\n## Main implementation advance\n\nThe release adds fixed-width parsers for the OGLE-IV LMC delta-Scuti `ident.dat` and `dsct.dat` files, an explicit OGLE-III-to-OGLE-IV crosswalk resolver, row-level and file-level SHA-256 locks, rights-aware catalog and photometry importers, and a complete execution hook for the fifteen-object cohort. Numeric suffix similarity and legacy `PeriodLS` values are forbidden as claim-grade replacements.\n\nSingle-mode catalogue subtype is preserved as `singlemode_radial_order_unresolved`; it is not silently converted into a fundamental or first-overtone radial-mode label.\n\n## Current blocking evidence\n\nThe authoritative catalogue bytes are not present in the release runtime, so the five selected delta-Scuti identities, subtypes, periods, and period uncertainties cannot yet be locked. The fifteen complete raw light-curve files are also absent. Family fractions and Wilson intervals remain suppressed.\n\n## Positive control\n\nThe synthetic fixed-width catalogue control resolved {control['resolved_count']} of {control['requested_count']} OGLE-III identities through explicit crosswalk fields. All locks verified: {control['all_locks_verify']}. Radial mode invented for single-mode objects: {control['singlemode_radial_order_invented']}.\n\n## Next deterministic operation\n\n1. Import or retrieve authoritative `ident.dat` and `dsct.dat` with the OGLE citation acknowledgement.\n2. Build the five row-level delta-Scuti metadata locks.\n3. Import or retrieve all fifteen commit-pinned raw photometry files and freeze their SHA-256 receipts.\n4. Re-run Phase 10 with `--execute-ready`; only then calculate family-level Wilson intervals.\n"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/phase10_development_cohort.json"))
    parser.add_argument("--metadata-lock", type=Path, default=Path("data/manifests/phase10_delta_scuti_metadata_lock.json"))
    parser.add_argument("--catalog-contract", type=Path, default=Path("data/manifests/phase10_authoritative_catalog_contract.json"))
    parser.add_argument("--protocol", type=Path, default=Path("research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json"))
    parser.add_argument("--seal", type=Path, default=Path("research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json"))
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/phase10/phase10_source_acquisition_receipt.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase10"))
    parser.add_argument("--execute-ready", action="store_true")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    output = resolve(args.output)
    output.mkdir(parents=True, exist_ok=True)
    assessment = assess_phase10(
        root=root,
        cohort_manifest_path=args.manifest,
        metadata_lock_path=args.metadata_lock,
        catalog_contract_path=args.catalog_contract,
        protocol_path=args.protocol,
        seal_path=args.seal,
        acquisition_receipt_path=args.receipt,
    )
    execution: Mapping[str, Any] | None = None
    if args.execute_ready:
        execution = execute_complete_cohort(assessment, root=root, output=output, fast=args.fast)
    control = synthetic_catalog_lock_control()
    blocker_summary = blocker_rows(assessment)
    family_readiness = family_readiness_rows(assessment)
    figures = make_figures(output, assessment)
    payload = {
        "implementation_id": "DERD-v1.0-phase10-authoritative-metadata-source-lock",
        "date": "2026-08-18",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "research_role": "exposed-development-only",
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__},
        "assessment": assessment.as_dict(),
        "blocker_summary": blocker_summary,
        "family_readiness": family_readiness,
        "execution": execution,
        "synthetic_catalog_lock_control": control,
        "figures": figures,
    }
    write_json(output / "phase10_summary.json", payload)
    write_json(output / "phase10_synthetic_catalog_lock_control.json", control)
    write_csv(output / "phase10_target_readiness.csv", readiness_rows(assessment))
    write_csv(output / "phase10_blockers.csv", blocker_summary)
    write_csv(output / "phase10_family_readiness.csv", family_readiness)
    (output / "PHASE10_RESULT.md").write_text(build_report(payload), encoding="utf-8")
    print(f"decision={assessment.decision}")
    print(f"metadata_ready={assessment.metadata_ready_count}/15")
    print(f"source_ready={assessment.source_ready_count}/15")
    print(f"cached_results={assessment.cached_result_count}/15")
    print(f"execution_ready={assessment.execution_ready_count}/15")
    print(f"primary_outputs_suppressed={assessment.primary_outputs_suppressed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
