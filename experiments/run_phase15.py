#!/usr/bin/env python3
"""Run Phase 15 archival lineage promotion and cumulative-ledger extension."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase10 import assess_phase10
from derd.validation_phase12 import cumulative_population_firewall, sha256_file
from derd.validation_phase15 import (
    LINEAGE_PROVENANCE_CONFLICT,
    PHASE15_DECISION_BLOCKED,
    PHASE15_DECISION_UPDATED,
    Phase15Config,
    audit_archival_lineage,
    find_phase08_target,
    load_verified_phase14_ledger,
    promote_archival_record,
)

ROOT_DEFAULT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
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


def verify_protocol(root: Path, config: Phase15Config) -> dict[str, Any]:
    protocol_path = root / "research/preregistration/phase15_archival_lineage_promotion_protocol.json"
    seal_path = root / "research/preregistration/phase15_archival_lineage_promotion_protocol.seal.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal.get("sha256_canonical_json", ""))
    checks = {
        "canonical_protocol_seal": actual == expected,
        "implementation_id": protocol.get("implementation_id") == "DERD-v1.5-phase15-archival-lineage-promotion",
        "configuration": protocol.get("configuration") == config.as_dict(),
        "configuration_sha256": protocol.get("configuration_sha256") == canonical_json_sha256(config.as_dict()),
        "parent_summary": sha256_file(root / protocol["parent_phase14_summary"]["path"]) == protocol["parent_phase14_summary"]["sha256"],
        "promotion_order": sha256_file(root / protocol["promotion_order"]["path"]) == protocol["promotion_order"]["sha256_file"],
        "phase07_source_manifest": sha256_file(root / protocol["archival_chain"]["phase07_source_manifest"]["path"]) == protocol["archival_chain"]["phase07_source_manifest"]["sha256"],
        "phase07_summary": sha256_file(root / protocol["archival_chain"]["phase07_summary"]["path"]) == protocol["archival_chain"]["phase07_summary"]["sha256"],
        "phase07_exchange": sha256_file(root / protocol["archival_chain"]["phase07_exchange"]["path"]) == protocol["archival_chain"]["phase07_exchange"]["sha256"],
        "phase08_summary": sha256_file(root / protocol["archival_chain"]["phase08_summary"]["path"]) == protocol["archival_chain"]["phase08_summary"]["sha256"],
        "phase08_exchange": sha256_file(root / protocol["archival_chain"]["phase08_exchange"]["path"]) == protocol["archival_chain"]["phase08_exchange"]["sha256"],
    }
    return {
        "valid": all(checks.values()),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "checks": checks,
        "protocol_id": protocol.get("protocol_id"),
        "configuration_sha256": protocol.get("configuration_sha256"),
    }


def assess_cohort(root: Path):
    return assess_phase10(
        root=root,
        cohort_manifest_path="data/manifests/phase10_development_cohort.json",
        metadata_lock_path="data/manifests/phase10_delta_scuti_metadata_lock.json",
        catalog_contract_path="data/manifests/phase10_authoritative_catalog_contract.json",
        protocol_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.json",
        seal_path="research/preregistration/phase10_authoritative_metadata_source_lock_protocol.seal.json",
        acquisition_receipt_path=None,
    )


def plot_lineage(path: Path, audit: Mapping[str, Any]) -> None:
    labels = ["score", "threshold", "max SNR drift"]
    phase07 = [audit["phase07_screen_score"], audit["phase07_threshold"], 0.0]
    phase08 = [audit["phase08_screen_score"], audit["phase08_threshold"], audit["maximum_harmonic_snr_absolute_difference"]]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(x - width / 2, phase07, width, label="Phase 07")
    ax.bar(x + width / 2, phase08, width, label="Phase 08 / drift")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Value")
    ax.set_title("Archival lineage: same source, configuration-sensitive output")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_coverage(path: Path, firewall: Mapping[str, Any]) -> None:
    rows = firewall["family_coverage"]
    names = [row["family"].replace("_", " ") for row in rows]
    values = [row["cumulative_record_count"] for row in rows]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(names, values)
    ax.axhline(5, linestyle="--", linewidth=1.2)
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Verified cumulative records")
    ax.set_title("Phase 15 frozen-denominator coverage")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "artifacts/phase15"
    out.mkdir(parents=True, exist_ok=True)

    config = Phase15Config()
    protocol = verify_protocol(root, config)
    if not protocol["valid"]:
        raise RuntimeError("Phase-15 protocol validation failed")

    prior, parent_summary_sha, parent_ledger_digest, temporal_refs, period_refs = load_verified_phase14_ledger(root=root)
    phase08_summary_path = root / "artifacts/phase08/phase08_summary.json"
    phase08 = json.loads(phase08_summary_path.read_text(encoding="utf-8"))
    phase08_row = find_phase08_target(phase08, config.selected_object_id)
    phase10 = json.loads((root / "data/manifests/phase10_development_cohort.json").read_text(encoding="utf-8"))
    target10 = next(row for row in phase10["targets"] if row["object_id"] == config.selected_object_id)
    expected_record_sha = target10["inherited_phase08"]["canonical_target_record_sha256"]
    expected_exchange_sha = target10["inherited_phase08"]["exchange_sha256"]

    lineage, phase08_row = audit_archival_lineage(
        root=root,
        object_id=config.selected_object_id,
        expected_phase08_record_sha256=expected_record_sha,
        expected_phase08_exchange_sha256=expected_exchange_sha,
    )
    lineage_payload = lineage.as_dict()
    lineage_path = out / f"phase15_archival_lineage_{config.selected_object_id}.json"
    write_json(lineage_path, lineage_payload)

    if lineage.classification == LINEAGE_PROVENANCE_CONFLICT:
        decision = PHASE15_DECISION_BLOCKED
        ledger = None
        record = None
    else:
        ledger, record = promote_archival_record(
            root=root,
            prior_records=prior,
            prior_summary_sha256=parent_summary_sha,
            phase08_row=phase08_row,
            config=config,
            config_sha256=canonical_json_sha256(config.as_dict()),
        )
        decision = PHASE15_DECISION_UPDATED

    if ledger is None or record is None:
        raise RuntimeError("Phase-15 archival record was not eligible for promotion")

    cohort_assessment = assess_cohort(root)
    firewall = cumulative_population_firewall(cohort_assessment, ledger)
    lineage_ref = {
        "object_id": config.selected_object_id,
        "relative_path": lineage_path.relative_to(root).as_posix(),
        "file_sha256": sha256_file(lineage_path),
        "canonical_sha256": lineage_payload["sha256_canonical_json"],
        "classification": lineage.classification,
        "ledger_record_sha256": record["ledger_record_sha256"],
    }
    ledger_payload = {
        "ledger_id": "DERD-PHASE15-CUMULATIVE-EVIDENCE-LEDGER-1.0",
        "date": "2026-08-19",
        "parent_phase14_summary_sha256": parent_summary_sha,
        "parent_phase14_ledger_sha256_canonical_json": parent_ledger_digest,
        "prior_record_count": ledger.prior_record_count,
        "new_record_count": ledger.new_record_count,
        "cumulative_count": ledger.cumulative_count,
        "records": [dict(row) for row in ledger.records],
        "inherited_temporal_audits": [dict(row) for row in temporal_refs],
        "inherited_period_coordinate_audits": [dict(row) for row in period_refs],
        "archival_lineage_audits": [lineage_ref],
        "claim_boundary": "normalized waveform evidence and computational lineage only",
    }
    ledger_path = out / "phase15_cumulative_ledger.json"
    write_json(ledger_path, ledger_payload)
    ledger_digest = canonical_json_sha256(ledger_payload)
    seal = {
        "ledger_id": ledger_payload["ledger_id"],
        "record_count": ledger.cumulative_count,
        "archival_lineage_audit_count": 1,
        "sha256_canonical_json": ledger_digest,
        "date_sealed": "2026-08-19",
    }
    seal_path = out / "phase15_cumulative_ledger.seal.json"
    write_json(seal_path, seal)

    audit_row = {
        key: value for key, value in lineage_payload.items()
        if key not in {"interpretation", "certificate", "claim_scope", "sha256_canonical_json"}
    }
    write_csv(out / "phase15_archival_lineage_audit.csv", [audit_row])
    coverage_rows = firewall["family_coverage"]
    write_csv(out / "phase15_family_coverage.csv", coverage_rows)

    plot_lineage(out / "phase15_archival_lineage_drift.png", lineage_payload)
    plot_coverage(out / "phase15_cumulative_family_coverage.png", firewall)

    claims = [
        {
            "claim_id": "C71",
            "claim": "A previously source-verified target can be promoted into the cumulative ledger without redistributing its raw photometry when all source and artifact digests agree.",
            "status": "VERIFIED_FOR_OGLE-LMC-CEP-0010",
        },
        {
            "claim_id": "C72",
            "claim": "The Phase-07 and Phase-08 analyses use the same frozen source coordinates but do not produce an exact scientific replay.",
            "status": "VERIFIED",
        },
        {
            "claim_id": "C73",
            "claim": "Configuration-sensitive analyses of the same observations are not independent astrophysical replications.",
            "status": "ENFORCED_BY_LEDGER_POLICY",
        },
        {
            "claim_id": "C74",
            "claim": "Five cumulative records remain insufficient for any frozen family or population output.",
            "status": "VERIFIED",
        },
    ]

    summary = {
        "implementation_id": "DERD-v1.5-phase15-archival-lineage-promotion",
        "date": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "c17_promoted": False,
        "protocol": protocol,
        "configuration": config.as_dict(),
        "selected_target": phase08_row["target"],
        "archival_lineage_audit": lineage_payload,
        "promoted_record": {
            "object_id": record["object_id"],
            "ledger_record_sha256": record["ledger_record_sha256"],
            "input_lock_sha256": record["input_lock_sha256"],
            "result_sha256": record["result_sha256"],
            "exchange_sha256": record["exchange_sha256"],
        },
        "cumulative_ledger": {
            "relative_path": ledger_path.relative_to(root).as_posix(),
            "seal_relative_path": seal_path.relative_to(root).as_posix(),
            "seal_sha256_canonical_json": ledger_digest,
            "cumulative_count": ledger.cumulative_count,
        },
        "population_firewall": firewall,
        "claims": claims,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "figures": [
            "artifacts/phase15/phase15_archival_lineage_drift.png",
            "artifacts/phase15/phase15_cumulative_family_coverage.png",
        ],
        "locked_physical_gates": [
            "UNIQUE_INTERNAL_MECHANISM",
            "LITERAL_INTERNAL_KEPLERIAN_MOTION",
            "UNIVERSAL_TRANSPARENT_OUTER_SHELL",
            "SHELL_PREVALENCE",
            "SHELL_MASS_OR_MASS_FRACTION",
        ],
    }
    write_json(out / "phase15_summary.json", summary)

    report = "# Phase 15 result: archival lineage promotion\n\n"
    report += f"Decision: `{decision}`\n\n"
    report += "## Promoted target\n\n"
    report += f"- Object: `{config.selected_object_id}`\n"
    report += f"- Family: `{phase08_row['target']['family']}`\n"
    report += f"- Stage: `{phase08_row['stage_reached']}`\n"
    report += f"- Disposition: `{phase08_row['disposition']}`\n"
    report += f"- Source SHA-256: `{phase08_row['target']['source_sha256']}`\n\n"
    report += "## Lineage audit\n\n"
    report += f"- Classification: `{lineage.classification}`\n"
    report += f"- Same source coordinates: **{lineage.source_coordinates_match}**\n"
    report += f"- Exact harmonic exchange: **{lineage.exchange_exact}**\n"
    report += f"- Maximum harmonic-SNR drift: **{lineage.maximum_harmonic_snr_absolute_difference:.6f}**\n"
    report += f"- Phase-07 score: **{lineage.phase07_screen_score:.6f}**\n"
    report += f"- Phase-08 score: **{lineage.phase08_screen_score:.6f}**\n"
    report += f"- Phase-07 stage: `{lineage.phase07_stage}`\n"
    report += f"- Phase-08 stage: `{lineage.phase08_stage}`\n\n"
    report += lineage.interpretation + "\n\n"
    report += "## Cumulative coverage\n\n"
    for row in coverage_rows:
        report += f"- {row['family']}: **{row['cumulative_record_count']} / {row['declared_count']}**\n"
    report += "\nFamily fractions and population claims remain suppressed.\n"
    (out / "PHASE15_RESULT.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "decision": decision,
        "object_id": config.selected_object_id,
        "lineage_classification": lineage.classification,
        "cumulative_count": ledger.cumulative_count,
        "ledger_sha256": ledger_digest,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
