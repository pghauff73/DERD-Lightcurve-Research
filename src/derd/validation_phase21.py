"""Phase-21 authoritative Delta-Scuti unlock and frozen-pilot firewall."""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .harmonic_extraction import git_blob_sha1_file
from .io import sha256_file
from .ogle_catalog import canonical_json_sha256
from .ogle_catalog_phase21 import validate_metadata_lock_manifest, validate_row_receipt
from .validation_phase09 import EXPECTED_FAMILIES, count_observations, wilson_interval


EXPECTED_IDS: Mapping[str, tuple[str, ...]] = {
    "classical_cepheid": (
        "OGLE-LMC-CEP-0002", "OGLE-LMC-CEP-0004", "OGLE-LMC-CEP-0005",
        "OGLE-LMC-CEP-0006", "OGLE-LMC-CEP-0010",
    ),
    "rr_lyrae": (
        "OGLE-LMC-RRLYR-00001", "OGLE-LMC-RRLYR-00003", "OGLE-LMC-RRLYR-00004",
        "OGLE-LMC-RRLYR-00005", "OGLE-LMC-RRLYR-00006",
    ),
    "delta_scuti": (
        "OGLE-LMC-DSCT-0003", "OGLE-LMC-DSCT-0004", "OGLE-LMC-DSCT-0005",
        "OGLE-LMC-DSCT-0006", "OGLE-LMC-DSCT-0007",
    ),
}

DECISION_PARTIAL = (
    "PHASE21_AUTHORITATIVE_DSCT_CROSSWALK_PARTIALLY_UNLOCKED_"
    "COMPLETE_PILOT_BLOCKED_BY_METADATA_AND_SOURCE_BYTES"
)
DECISION_READY = "PHASE21_COMPLETE_15_OBJECT_DEVELOPMENT_PILOT_EXECUTED"


@dataclass(frozen=True, slots=True)
class TargetReadiness:
    object_id: str
    family: str
    metadata_ready: bool
    metadata_status: str
    effective_object_id: str
    effective_mode: str
    effective_period_days: float
    effective_period_error_days: float | None
    source_ready: bool
    source_checks: Mapping[str, bool]
    inherited_evidence: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "family": self.family,
            "metadata_ready": self.metadata_ready,
            "metadata_status": self.metadata_status,
            "effective_object_id": self.effective_object_id,
            "effective_mode": self.effective_mode,
            "effective_period_days": self.effective_period_days,
            "effective_period_error_days": self.effective_period_error_days,
            "source_ready": self.source_ready,
            "source_checks": dict(self.source_checks),
            "inherited_evidence": self.inherited_evidence,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class Phase21Assessment:
    cohort_valid: bool
    protocol_valid: bool
    row_receipt_valid: bool
    metadata_lock_manifest_valid: bool
    family_counts: Mapping[str, int]
    targets: tuple[TargetReadiness, ...]
    metadata_ready_count: int
    dsct_locked_count: int
    dsct_unresolved_count: int
    source_ready_count: int
    inherited_evidence_count: int
    fresh_result_count: int
    primary_outputs_suppressed: bool
    decision: str
    c17_promoted: bool = False

    @property
    def execution_inputs_ready(self) -> bool:
        return (
            self.cohort_valid and self.protocol_valid and self.row_receipt_valid
            and self.metadata_lock_manifest_valid and self.metadata_ready_count == 15
            and self.source_ready_count == 15
        )

    @property
    def complete(self) -> bool:
        return self.execution_inputs_ready and self.fresh_result_count == 15

    def as_dict(self) -> dict[str, Any]:
        return {
            "cohort_valid": self.cohort_valid,
            "protocol_valid": self.protocol_valid,
            "row_receipt_valid": self.row_receipt_valid,
            "metadata_lock_manifest_valid": self.metadata_lock_manifest_valid,
            "family_counts": dict(self.family_counts),
            "targets": [t.as_dict() for t in self.targets],
            "metadata_ready_count": self.metadata_ready_count,
            "dsct_locked_count": self.dsct_locked_count,
            "dsct_unresolved_count": self.dsct_unresolved_count,
            "source_ready_count": self.source_ready_count,
            "inherited_evidence_count": self.inherited_evidence_count,
            "fresh_result_count": self.fresh_result_count,
            "execution_inputs_ready": self.execution_inputs_ready,
            "complete": self.complete,
            "primary_outputs_suppressed": self.primary_outputs_suppressed,
            "decision": self.decision,
            "c17_promoted": self.c17_promoted,
        }


def _read_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_manifest_valid(payload: Mapping[str, Any]) -> bool:
    expected = str(payload.get("sha256_canonical_json", ""))
    body = dict(payload)
    body.pop("sha256_canonical_json", None)
    return len(expected) == 64 and canonical_json_sha256(body) == expected


def _validate_cohort(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, int], tuple[str, ...]]:
    blockers: list[str] = []
    targets = payload.get("targets", [])
    family_counts = {family: sum(row.get("family") == family for row in targets) for family in EXPECTED_FAMILIES}
    if len(targets) != 15:
        blockers.append("COHORT_MUST_CONTAIN_EXACTLY_15_TARGETS")
    if family_counts != {family: 5 for family in EXPECTED_FAMILIES}:
        blockers.append("COHORT_MUST_CONTAIN_EXACTLY_5_PER_FAMILY")
    ids = [str(row.get("object_id")) for row in targets]
    paths = [str(row.get("source_repository_path")) for row in targets]
    if len(ids) != len(set(ids)):
        blockers.append("DUPLICATE_OBJECT_ID")
    if len(paths) != len(set(paths)):
        blockers.append("DUPLICATE_SOURCE_PATH")
    expected_flat = {item for family in EXPECTED_IDS.values() for item in family}
    if set(ids) != expected_flat:
        blockers.append("FROZEN_IDENTITY_DENOMINATOR_CHANGED")
    for family, expected in EXPECTED_IDS.items():
        actual = tuple(row["object_id"] for row in targets if row["family"] == family)
        if actual != expected:
            blockers.append(f"{family.upper()}_IDENTITY_ORDER_OR_MEMBERSHIP_CHANGED")
    if not all(row.get("evidence_role") == "exposed-development-only" for row in targets):
        blockers.append("NON_DEVELOPMENT_IDENTITY_IN_COHORT")
    if not _canonical_manifest_valid(payload):
        blockers.append("COHORT_CANONICAL_HASH_MISMATCH")
    return not blockers, family_counts, tuple(blockers)


def _source_readiness(
    root: Path,
    row: Mapping[str, Any],
    receipt_record: Mapping[str, Any] | None = None,
) -> tuple[bool, dict[str, bool], list[str]]:
    path = root / str(row["source_relative_path"])
    receipt_verified = bool(
        receipt_record
        and receipt_record.get("status") == "VERIFIED_AND_FROZEN"
        and receipt_record.get("object_id") == row.get("object_id")
        and receipt_record.get("source_repository") == row.get("source_repository")
        and receipt_record.get("source_commit") == row.get("source_commit")
        and receipt_record.get("source_repository_path") == row.get("source_repository_path")
        and receipt_record.get("source_git_blob_sha1") == row.get("source_git_blob_sha1")
        and int(receipt_record.get("source_byte_count", -1)) == int(row.get("source_byte_count", -2))
        and int(receipt_record.get("source_observation_count", -1)) == int(row.get("source_observation_count", -2))
        and isinstance(receipt_record.get("source_sha256"), str)
        and len(receipt_record.get("source_sha256")) == 64
    )
    effective_expected_sha = (
        str(row.get("source_sha256"))
        if isinstance(row.get("source_sha256"), str) and len(str(row.get("source_sha256"))) == 64
        else (str(receipt_record.get("source_sha256")) if receipt_verified else None)
    )
    checks = {
        "source_file_present": path.is_file(),
        "source_byte_count": False,
        "source_observation_count": False,
        "source_git_blob_sha1": False,
        "source_receipt_verified": receipt_verified or (
            isinstance(row.get("source_sha256"), str) and len(str(row.get("source_sha256"))) == 64
        ),
        "source_sha256_frozen": effective_expected_sha is not None,
        "source_sha256_matches": False,
    }
    if path.is_file():
        checks["source_byte_count"] = path.stat().st_size == int(row["source_byte_count"])
        try:
            checks["source_observation_count"] = count_observations(path) == int(row["source_observation_count"])
            checks["source_git_blob_sha1"] = git_blob_sha1_file(path) == str(row["source_git_blob_sha1"])
            if checks["source_sha256_frozen"]:
                checks["source_sha256_matches"] = sha256_file(path) == effective_expected_sha
        except (OSError, UnicodeError, ValueError):
            pass
    blockers = [name.upper() + "_FAILED" for name, passed in checks.items() if not passed]
    return all(checks.values()), checks, blockers


def assess_phase21(
    *,
    root: str | Path,
    cohort_path: str | Path = "data/manifests/phase21_development_cohort.json",
    receipt_path: str | Path = "data/manifests/phase21_authoritative_catalog_row_receipt.json",
    lock_path: str | Path = "data/manifests/phase21_delta_scuti_metadata_lock.json",
    protocol_path: str | Path = "research/preregistration/phase21_authoritative_dsct_pilot_protocol.json",
    seal_path: str | Path = "research/preregistration/phase21_authoritative_dsct_pilot_protocol.seal.json",
    ledger_path: str | Path = "artifacts/phase19/phase19_cumulative_ledger.json",
    fresh_results_path: str | Path | None = None,
    source_receipt_path: str | Path | None = "artifacts/phase21/phase21_source_acquisition_receipt.json",
) -> Phase21Assessment:
    root = Path(root).resolve()
    def p(value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    cohort = _read_json(p(cohort_path))
    receipt = _read_json(p(receipt_path))
    lock_manifest = _read_json(p(lock_path))
    protocol = _read_json(p(protocol_path))
    seal = _read_json(p(seal_path))
    ledger = _read_json(p(ledger_path)) if p(ledger_path).is_file() else {"records": []}

    cohort_valid, family_counts, _ = _validate_cohort(cohort)
    receipt_valid, _ = validate_row_receipt(receipt)
    locks_valid, _ = validate_metadata_lock_manifest(lock_manifest, receipt=receipt)
    protocol_valid = (
        _canonical_manifest_valid(protocol)
        and protocol.get("protocol_id") == seal.get("protocol_id")
        and protocol.get("sha256_canonical_json") == seal.get("sha256_canonical_json")
    )

    locks = {row["requested_object_id"]: row for row in lock_manifest.get("records", [])}
    unresolved = {row["requested_object_id"]: row for row in lock_manifest.get("unresolved_records", [])}
    inherited_ids = {str(row.get("object_id")) for row in ledger.get("records", [])}
    receipt_by_id: dict[str, Mapping[str, Any]] = {}
    if source_receipt_path is not None and p(source_receipt_path).is_file():
        source_receipt = _read_json(p(source_receipt_path))
        receipt_by_id = {str(r.get("object_id")): r for r in source_receipt.get("targets", []) if isinstance(r, dict)}

    fresh_ids: set[str] = set()
    if fresh_results_path is not None and p(fresh_results_path).is_file():
        fresh = _read_json(p(fresh_results_path))
        fresh_ids = {str(row.get("object_id")) for row in fresh.get("records", [])}

    target_rows: list[TargetReadiness] = []
    for row in cohort["targets"]:
        object_id = str(row["object_id"])
        family = str(row["family"])
        blockers: list[str] = []
        if family != "delta_scuti":
            metadata_ready = (
                str(row.get("period_evidence_grade", "")).startswith("EXTERNAL_CATALOG")
                and str(row.get("mode_evidence_grade", "")).startswith("EXTERNAL_CATALOG")
                and row.get("metadata_identity_status") == "RESOLVED_EXACT"
                and float(row.get("catalog_period_days", 0.0)) > 0.0
            )
            metadata_status = "CARRIED_FORWARD_CLAIM_GRADE_METADATA" if metadata_ready else "NONCLAIM_METADATA"
            effective_id = object_id
            effective_mode = str(row["mode"])
            effective_period = float(row["catalog_period_days"])
            period_error = None
        elif object_id in locks:
            lock = locks[object_id]
            metadata_ready = True
            metadata_status = "LOCKED_EXACT_TWO_HOP_CROSSWALK"
            effective_id = str(lock["current_object_id"])
            effective_mode = str(lock["mode_label"])
            effective_period = float(lock["primary_period_days"])
            period_error = float(lock["primary_period_error_days"])
        elif object_id in unresolved:
            metadata_ready = False
            metadata_status = "UNRESOLVED_NO_EXACT_CURRENT_CATALOG_CROSSWALK"
            effective_id = object_id
            effective_mode = "unresolved"
            effective_period = float(row["catalog_period_days"])
            period_error = None
            blockers.extend([
                "AUTHORITATIVE_IDENTITY_CROSSWALK_UNRESOLVED",
                "AUTHORITATIVE_PERIOD_UNAVAILABLE",
                "AUTHORITATIVE_SUBTYPE_UNAVAILABLE",
            ])
        else:
            metadata_ready = False
            metadata_status = "AUTHORITATIVE_METADATA_LOCK_MISSING"
            effective_id = object_id
            effective_mode = "unresolved"
            effective_period = float(row["catalog_period_days"])
            period_error = None
            blockers.append("AUTHORITATIVE_METADATA_LOCK_MISSING")
        if not metadata_ready and family != "delta_scuti":
            blockers.append("CLAIM_GRADE_METADATA_FAILED")
        source_ready, source_checks, source_blockers = _source_readiness(
            root, row, receipt_by_id.get(object_id)
        )
        blockers.extend(source_blockers)
        target_rows.append(TargetReadiness(
            object_id=object_id, family=family,
            metadata_ready=metadata_ready, metadata_status=metadata_status,
            effective_object_id=effective_id, effective_mode=effective_mode,
            effective_period_days=effective_period,
            effective_period_error_days=period_error,
            source_ready=source_ready, source_checks=source_checks,
            inherited_evidence=object_id in inherited_ids,
            blockers=tuple(dict.fromkeys(blockers)),
        ))

    metadata_ready_count = sum(t.metadata_ready for t in target_rows)
    source_ready_count = sum(t.source_ready for t in target_rows)
    inherited_count = sum(t.inherited_evidence for t in target_rows)
    fresh_count = sum(t.object_id in fresh_ids for t in target_rows)
    complete = (
        cohort_valid and protocol_valid and receipt_valid and locks_valid
        and metadata_ready_count == 15 and source_ready_count == 15 and fresh_count == 15
    )
    return Phase21Assessment(
        cohort_valid=cohort_valid,
        protocol_valid=protocol_valid,
        row_receipt_valid=receipt_valid,
        metadata_lock_manifest_valid=locks_valid,
        family_counts=family_counts,
        targets=tuple(target_rows),
        metadata_ready_count=metadata_ready_count,
        dsct_locked_count=len(locks),
        dsct_unresolved_count=len(unresolved),
        source_ready_count=source_ready_count,
        inherited_evidence_count=inherited_count,
        fresh_result_count=fresh_count,
        primary_outputs_suppressed=not complete,
        decision=DECISION_READY if complete else DECISION_PARTIAL,
    )


def family_coverage(assessment: Phase21Assessment) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in EXPECTED_FAMILIES:
        targets = [t for t in assessment.targets if t.family == family]
        rows.append({
            "family": family,
            "declared": len(targets),
            "metadata_ready": sum(t.metadata_ready for t in targets),
            "source_ready": sum(t.source_ready for t in targets),
            "inherited_evidence": sum(t.inherited_evidence for t in targets),
            "fresh_results": 0,
            "population_fraction_status": "SUPPRESSED" if assessment.primary_outputs_suppressed else "OPEN",
        })
    return rows


def synthetic_full_cohort_control() -> Mapping[str, Any]:
    """Positive control for the denominator firewall and Wilson interval path."""
    outcomes = {
        "classical_cepheid": [True, False, True, False, False],
        "rr_lyrae": [False, False, True, False, True],
        "delta_scuti": [True, True, False, False, False],
    }
    rows=[]
    for family, values in outcomes.items():
        low, high = wilson_interval(sum(values), len(values))
        rows.append({"family":family,"qualified":sum(values),"n":len(values),"fraction":sum(values)/len(values),"wilson_low":low,"wilson_high":high})
    payload={
        "control_id":"DERD-PHASE21-SYNTHETIC-COMPLETE-DENOMINATOR-CONTROL-1.0",
        "astronomical_evidence":False,
        "complete_denominator":True,
        "family_intervals_emitted":True,
        "rows":rows,
    }
    payload["sha256_canonical_json"]=canonical_json_sha256(payload)
    return payload


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader(); w.writerows(rows)
