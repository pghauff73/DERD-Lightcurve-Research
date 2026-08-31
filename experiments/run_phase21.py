#!/usr/bin/env python3
"""Run Phase 21 authoritative Delta-Scuti unlock and pilot-readiness audit."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase21 import assess_phase21, family_coverage, synthetic_full_cohort_control, write_csv


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _figures(out: Path, summary: Mapping[str, Any], targets: list[Mapping[str, Any]], families: list[Mapping[str, Any]], blockers: list[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    # Readiness matrix
    labels=[row["object_id"] for row in targets]
    matrix=np.array([[int(row["metadata_ready"]), int(row["source_ready"]), int(row["inherited_evidence"])] for row in targets], dtype=float)
    fig,ax=plt.subplots(figsize=(9,7))
    im=ax.imshow(matrix,aspect="auto",vmin=0,vmax=1)
    ax.set_xticks([0,1,2], ["Metadata", "Raw source", "Inherited evidence"])
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.set_title("Phase 21 target readiness")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]): ax.text(j,i,"✓" if matrix[i,j] else "×",ha="center",va="center")
    fig.colorbar(im,ax=ax,label="Gate state")
    fig.tight_layout(); fig.savefig(out/"phase21_readiness_matrix.png",dpi=180); plt.close(fig)

    # blockers
    top=blockers[:12]
    fig,ax=plt.subplots(figsize=(9,5))
    ax.barh([r["blocker"] for r in reversed(top)],[r["count"] for r in reversed(top)])
    ax.set_xlabel("Targets")
    ax.set_title("Phase 21 evidence blockers")
    fig.tight_layout(); fig.savefig(out/"phase21_blocker_counts.png",dpi=180); plt.close(fig)

    # family coverage
    x=np.arange(len(families)); width=0.22
    fig,ax=plt.subplots(figsize=(8,5))
    ax.bar(x-width,[r["metadata_ready"] for r in families],width,label="Metadata")
    ax.bar(x,[r["source_ready"] for r in families],width,label="Raw source")
    ax.bar(x+width,[r["inherited_evidence"] for r in families],width,label="Inherited evidence")
    ax.set_xticks(x,[r["family"] for r in families],rotation=15)
    ax.set_ylim(0,5.5); ax.set_ylabel("Objects of 5")
    ax.set_title("Frozen family-denominator coverage")
    ax.legend(); fig.tight_layout(); fig.savefig(out/"phase21_family_coverage.png",dpi=180); plt.close(fig)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=".")
    args=parser.parse_args()
    root=Path(args.root).resolve(); out=root/"artifacts/phase21"; out.mkdir(parents=True,exist_ok=True)

    assessment=assess_phase21(root=root)
    targets=[row.as_dict() for row in assessment.targets]
    families=family_coverage(assessment)
    blocker_counter=Counter(blocker for row in assessment.targets for blocker in row.blockers)
    blockers=[{"blocker":k,"count":v} for k,v in sorted(blocker_counter.items(), key=lambda kv:(-kv[1],kv[0]))]

    lock=json.loads((root/"data/manifests/phase21_delta_scuti_metadata_lock.json").read_text())
    receipt=json.loads((root/"data/manifests/phase21_authoritative_catalog_row_receipt.json").read_text())
    parent_ledger=json.loads((root/"artifacts/phase19/phase19_cumulative_ledger.json").read_text())
    parent_ledger_sha=canonical_json_sha256(parent_ledger)
    ledger={
        "ledger_id":"DERD-PHASE21-DEVELOPMENT-EVIDENCE-LEDGER-1.0",
        "implementation_id":"DERD-v2.1-phase21-authoritative-dsct-pilot",
        "parent_ledger_path":"artifacts/phase19/phase19_cumulative_ledger.json",
        "parent_ledger_sha256":parent_ledger_sha,
        "records":parent_ledger.get("records",[]),
        "record_count":len(parent_ledger.get("records",[])),
        "fresh_phase21_record_count":0,
        "delta_scuti_metadata_unlocks":[r["requested_object_id"] for r in lock["records"]],
        "delta_scuti_unresolved":[r["requested_object_id"] for r in lock["unresolved_records"]],
        "population_outputs_suppressed":assessment.primary_outputs_suppressed,
        "claim_boundary":"development waveform evidence only; no C17 or physical mechanism/shell promotion",
    }
    ledger["sha256_canonical_json"]=canonical_json_sha256(ledger)
    seal={"ledger_id":ledger["ledger_id"],"sha256_canonical_json":ledger["sha256_canonical_json"],"sealed_at_utc":"2026-08-25T00:00:00Z"}

    correction=[]
    cohort={r["object_id"]:r for r in json.loads((root/"data/manifests/phase21_development_cohort.json").read_text())["targets"]}
    for r in lock["records"]:
        old=float(cohort[r["requested_object_id"]]["catalog_period_days"])
        new=float(r["primary_period_days"])
        correction.append({
            "requested_object_id":r["requested_object_id"],
            "current_object_id":r["current_object_id"],
            "legacy_diagnostic_period_days":old,
            "authoritative_period_days":new,
            "absolute_difference_days":new-old,
            "period_ratio_authoritative_to_legacy":new/old,
            "mode_label":r["mode_label"],
        })

    summary={
        "implementation_id":"DERD-v2.1-phase21-authoritative-dsct-pilot",
        "assessment":assessment.as_dict(),
        "authoritative_row_receipt_sha256":receipt["sha256_canonical_json"],
        "metadata_lock_manifest_sha256":lock["sha256_canonical_json"],
        "period_coordinate_corrections":correction,
        "family_coverage":families,
        "blockers":blockers,
        "execution_ledger_sha256":ledger["sha256_canonical_json"],
        "synthetic_positive_control":synthetic_full_cohort_control(),
        "physical_claim_boundary":{
            "c17_promoted":False,
            "unique_internal_mechanism":False,
            "transparent_outer_shell":False,
            "shell_mass":False,
        },
    }
    summary["sha256_canonical_json"]=canonical_json_sha256(summary)

    _write_json(out/"phase21_summary.json",summary)
    _write_json(out/"phase21_catalog_lock_receipt.json",receipt)
    _write_json(out/"phase21_source_verification.json",{
        "source_ready_count":assessment.source_ready_count,
        "targets":[{"object_id":r["object_id"],"source_ready":r["source_ready"],"source_checks":r["source_checks"]} for r in targets],
    })
    _write_json(out/"phase21_execution_ledger.json",ledger)
    _write_json(out/"phase21_execution_ledger.seal.json",seal)
    _write_json(out/"phase21_synthetic_complete_control.json",summary["synthetic_positive_control"])
    write_csv(out/"phase21_target_readiness.csv",targets)
    write_csv(out/"phase21_family_coverage.csv",families)
    write_csv(out/"phase21_blockers.csv",blockers)
    write_csv(out/"phase21_period_coordinate_corrections.csv",correction)
    _figures(out,summary,targets,families,blockers)

    locked=", ".join(r["requested_object_id"] for r in lock["records"])
    unresolved=", ".join(r["requested_object_id"] for r in lock["unresolved_records"])
    report=f"""# Phase 21 result: authoritative Delta-Scuti unlock and frozen pilot\n\n```text\n{assessment.decision}\nC17_NOT_PROMOTED\nNOT_A_PHYSICAL_CLAIM_CERTIFICATE\n```\n\n## Executive result\n\n- Frozen denominator: **5 classical Cepheids + 5 RR Lyrae + 5 Delta Scuti**.\n- Claim-grade metadata ready: **{assessment.metadata_ready_count}/15**.\n- Delta Scuti exact two-hop locks: **{assessment.dsct_locked_count}/5**.\n- Delta Scuti unresolved exact crosswalks: **{assessment.dsct_unresolved_count}/5**.\n- Complete raw source locks available locally: **{assessment.source_ready_count}/15**.\n- Cryptographically retained inherited development records: **{assessment.inherited_evidence_count}/15**.\n- Fresh Phase-21 target executions: **{assessment.fresh_result_count}/15**.\n- Family fractions and Wilson intervals: **suppressed**.\n\n## Authoritative metadata advancement\n\nThe Phase-10 assumption that a current catalogue row could be reached directly from the old `OGLE-LMC-DSCT-NNNN` label was replaced by a two-hop exact relation:\n\n```text\nold OGLE-III object ID\n→ old OGLE-III field identity\n→ current catalogue OGLE-III cross-reference field\n```\n\nExact locks were promoted for: **{locked}**.\n\nNo exact current-catalogue crosswalk was accepted for: **{unresolved}**. Their identities were not guessed from zero padding, numeric suffixes, or sky proximity.\n\n## Period-coordinate findings\n\nThe three promoted authoritative periods materially differ from the legacy feature-table coordinates. This means the earlier Delta Scuti engineering screens cannot be promoted merely by relabelling them; they require fresh execution under the authoritative periods.\n\n## Population firewall\n\nThe exact 15-object denominator remains frozen. Partial coverage cannot emit family prevalence estimates, Wilson intervals, or a population claim. The synthetic positive control verifies that the interval path opens only when all denominator records are complete.\n\n## Remaining gates\n\n1. Resolve the authoritative disposition or reclassification of the two unmatched old Delta Scuti identities.\n2. Acquire and freeze all fifteen complete raw light curves.\n3. Execute all fifteen targets under the unchanged Phase-21 configuration.\n4. Only then emit family descriptive intervals.\n\nNo waveform result here establishes an internal gravitational mechanism, a transparent outer shell, or a shell mass.\n"""
    (out/"PHASE21_RESULT.md").write_text(report,encoding="utf-8")
    print(json.dumps({"decision":assessment.decision,"metadata_ready":assessment.metadata_ready_count,"dsct_locked":assessment.dsct_locked_count,"source_ready":assessment.source_ready_count,"inherited":assessment.inherited_evidence_count,"fresh":assessment.fresh_result_count,"summary_sha256":summary["sha256_canonical_json"]},indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
