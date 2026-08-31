"""Phase-09 claim-grade multi-family development cohort gate.

This module implements the frozen Phase-09 protocol without silently weakening it.
It separates four dimensions that earlier exploratory runs could easily conflate:

1. declared population completeness,
2. claim-grade period/mode identity provenance,
3. replayable raw source bytes,
4. completed object-level harmonic-forecast results.

Family-level primary outputs are suppressed unless all four dimensions pass for all
15 exposed-development identities. Cached Phase-08 results may be audited and
reported descriptively, but cannot make an incomplete Phase-09 cohort look complete.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .harmonic_extraction import git_blob_sha1_file
from .provenance import sha256_path


EXPECTED_FAMILIES = ("classical_cepheid", "delta_scuti", "rr_lyrae")
CLAIM_GRADE_PREFIX = "EXTERNAL_CATALOG"
QUALIFIED_DISPOSITION = "QUALIFIES_AS_DEVELOPMENT_HARMONIC_FORECAST"


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_hex_digest(value: str | None, length: int) -> bool:
    if value is None or len(value) != length:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion.

    This is used only after the complete-cohort gate passes. It is intentionally
    available as a small independently testable primitive rather than being hidden
    inside report-generation code.
    """

    if total <= 0:
        raise ValueError("total must be positive")
    if not 0 <= successes <= total:
        raise ValueError("successes must lie in [0, total]")
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


@dataclass(frozen=True, slots=True)
class Phase09Target:
    object_id: str
    family: str
    mode: str
    catalog_period_days: float
    period_evidence_grade: str
    mode_evidence_grade: str
    period_source: str
    metadata_identity_status: str
    source_repository: str
    source_commit: str
    source_repository_path: str
    source_git_blob_sha1: str
    source_byte_count: int
    source_observation_count: int
    source_sha256: str | None
    source_sha256_status: str
    source_relative_path: str
    evidence_role: str
    inherited_phase08: Mapping[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase09Target":
        return cls(
            object_id=str(value["object_id"]),
            family=str(value["family"]),
            mode=str(value["mode"]),
            catalog_period_days=float(value["catalog_period_days"]),
            period_evidence_grade=str(value["period_evidence_grade"]),
            mode_evidence_grade=str(value["mode_evidence_grade"]),
            period_source=str(value["period_source"]),
            metadata_identity_status=str(value["metadata_identity_status"]),
            source_repository=str(value["source_repository"]),
            source_commit=str(value["source_commit"]),
            source_repository_path=str(value["source_repository_path"]),
            source_git_blob_sha1=str(value["source_git_blob_sha1"]),
            source_byte_count=int(value["source_byte_count"]),
            source_observation_count=int(value["source_observation_count"]),
            source_sha256=(None if value.get("source_sha256") in (None, "") else str(value["source_sha256"])),
            source_sha256_status=str(value["source_sha256_status"]),
            source_relative_path=str(value["source_relative_path"]),
            evidence_role=str(value.get("evidence_role", "exposed-development-only")),
            inherited_phase08=value.get("inherited_phase08"),
        )

    @property
    def source_locator(self) -> str:
        return (
            f"https://github.com/{self.source_repository}/blob/{self.source_commit}/"
            f"{self.source_repository_path}"
        )

    @property
    def period_claim_grade(self) -> bool:
        return (
            math.isfinite(self.catalog_period_days)
            and self.catalog_period_days > 0.0
            and self.period_evidence_grade.startswith(CLAIM_GRADE_PREFIX)
        )

    @property
    def mode_claim_grade(self) -> bool:
        return (
            self.mode not in {"", "unresolved", "unknown"}
            and self.mode_evidence_grade.startswith(CLAIM_GRADE_PREFIX)
        )

    @property
    def identity_claim_grade(self) -> bool:
        return self.metadata_identity_status == "RESOLVED_EXACT"

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "family": self.family,
            "mode": self.mode,
            "catalog_period_days": self.catalog_period_days,
            "period_evidence_grade": self.period_evidence_grade,
            "mode_evidence_grade": self.mode_evidence_grade,
            "period_source": self.period_source,
            "metadata_identity_status": self.metadata_identity_status,
            "source_repository": self.source_repository,
            "source_commit": self.source_commit,
            "source_repository_path": self.source_repository_path,
            "source_git_blob_sha1": self.source_git_blob_sha1,
            "source_byte_count": self.source_byte_count,
            "source_observation_count": self.source_observation_count,
            "source_sha256": self.source_sha256,
            "source_sha256_status": self.source_sha256_status,
            "source_relative_path": self.source_relative_path,
            "source_locator": self.source_locator,
            "evidence_role": self.evidence_role,
            "inherited_phase08": None if self.inherited_phase08 is None else dict(self.inherited_phase08),
        }


@dataclass(frozen=True, slots=True)
class Phase09TargetReadiness:
    target: Phase09Target
    checks: Mapping[str, bool]
    blockers: tuple[str, ...]
    source_actual_sha256: str | None
    source_actual_git_blob_sha1: str | None
    effective_expected_sha256: str | None
    acquisition_receipt_verified: bool
    source_actual_observation_count: int | None
    inherited_record: Mapping[str, Any] | None

    @property
    def metadata_ready(self) -> bool:
        return all(
            self.checks[key]
            for key in ("period_claim_grade", "mode_claim_grade", "identity_claim_grade")
        )

    @property
    def source_ready(self) -> bool:
        return all(
            self.checks[key]
            for key in (
                "source_commit_digest",
                "source_manifest_blob_digest",
                "expected_observation_capacity",
                "source_file_present",
                "source_byte_count",
                "source_observation_count",
                "source_git_blob_sha1",
                "source_sha256_frozen",
                "source_sha256_matches",
            )
        )

    @property
    def cached_result_ready(self) -> bool:
        return self.checks["inherited_result_verified"]

    @property
    def executable_now(self) -> bool:
        return self.metadata_ready and self.source_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.as_dict(),
            "checks": dict(self.checks),
            "blockers": list(self.blockers),
            "metadata_ready": self.metadata_ready,
            "source_ready": self.source_ready,
            "cached_result_ready": self.cached_result_ready,
            "executable_now": self.executable_now,
            "source_actual_sha256": self.source_actual_sha256,
            "source_actual_git_blob_sha1": self.source_actual_git_blob_sha1,
            "effective_expected_sha256": self.effective_expected_sha256,
            "acquisition_receipt_verified": self.acquisition_receipt_verified,
            "source_actual_observation_count": self.source_actual_observation_count,
            "inherited_record": None if self.inherited_record is None else dict(self.inherited_record),
        }


@dataclass(frozen=True, slots=True)
class Phase09Assessment:
    protocol_valid: bool
    protocol_expected_sha256: str
    protocol_actual_sha256: str
    manifest_sha256: str
    target_readiness: tuple[Phase09TargetReadiness, ...]
    acquisition_receipt_present: bool
    acquisition_receipt_header_valid: bool
    acquisition_receipt_verified_count: int
    family_counts: Mapping[str, int]
    cohort_structure_ready: bool
    cohort_metadata_ready: bool
    cohort_sources_ready: bool
    inherited_result_count: int
    completed_result_count: int
    primary_outputs_suppressed: bool
    partial_family_summary: tuple[Mapping[str, Any], ...]
    primary_family_outputs: tuple[Mapping[str, Any], ...]
    decision: str
    c17_promoted: bool = False

    @property
    def cohort_execution_ready(self) -> bool:
        return (
            self.protocol_valid
            and self.cohort_structure_ready
            and self.cohort_metadata_ready
            and self.cohort_sources_ready
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol_valid": self.protocol_valid,
            "protocol_expected_sha256": self.protocol_expected_sha256,
            "protocol_actual_sha256": self.protocol_actual_sha256,
            "manifest_sha256": self.manifest_sha256,
            "target_readiness": [item.as_dict() for item in self.target_readiness],
            "acquisition_receipt_present": self.acquisition_receipt_present,
            "acquisition_receipt_header_valid": self.acquisition_receipt_header_valid,
            "acquisition_receipt_verified_count": self.acquisition_receipt_verified_count,
            "family_counts": dict(self.family_counts),
            "cohort_structure_ready": self.cohort_structure_ready,
            "cohort_metadata_ready": self.cohort_metadata_ready,
            "cohort_sources_ready": self.cohort_sources_ready,
            "cohort_execution_ready": self.cohort_execution_ready,
            "inherited_result_count": self.inherited_result_count,
            "completed_result_count": self.completed_result_count,
            "primary_outputs_suppressed": self.primary_outputs_suppressed,
            "partial_family_summary": [dict(row) for row in self.partial_family_summary],
            "primary_family_outputs": [dict(row) for row in self.primary_family_outputs],
            "decision": self.decision,
            "c17_promoted": self.c17_promoted,
        }


def load_manifest(path: str | Path) -> tuple[Mapping[str, Any], tuple[Phase09Target, ...]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = tuple(Phase09Target.from_dict(row) for row in payload["targets"])
    return payload, targets


def verify_protocol(protocol_path: str | Path, seal_path: str | Path) -> tuple[bool, str, str]:
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    actual = canonical_json_sha256(protocol)
    expected = str(seal["sha256_canonical_json"])
    identity_matches = protocol.get("protocol_id") == seal.get("protocol_id")
    return actual == expected and identity_matches, expected, actual


def count_observations(path: str | Path) -> int:
    """Count non-empty, non-comment observations in a three-column source file."""

    count = 0
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def _load_inherited_record(target: Phase09Target, root: Path) -> tuple[Mapping[str, Any] | None, list[str]]:
    inherited = target.inherited_phase08
    if not inherited:
        return None, []
    blockers: list[str] = []
    summary_path = root / str(inherited["summary_relative_path"])
    exchange_path = root / str(inherited["exchange_relative_path"])
    if not summary_path.is_file():
        return None, ["INHERITED_SUMMARY_MISSING"]
    if not exchange_path.is_file():
        blockers.append("INHERITED_EXCHANGE_MISSING")
    elif sha256_path(exchange_path) != inherited["exchange_sha256"]:
        blockers.append("INHERITED_EXCHANGE_SHA256_MISMATCH")

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    records = [
        item
        for item in payload.get("cohort", {}).get("targets", [])
        if item.get("target", {}).get("object_id") == target.object_id
    ]
    if len(records) != 1:
        blockers.append("INHERITED_TARGET_RECORD_NOT_UNIQUE")
        return None, blockers
    record = records[0]
    if canonical_json_sha256(record) != inherited["canonical_target_record_sha256"]:
        blockers.append("INHERITED_TARGET_RECORD_SHA256_MISMATCH")
    return record, blockers


def assess_target_readiness(
    target: Phase09Target,
    *,
    root: str | Path,
    acquisition_receipt: Mapping[str, Any] | None = None,
) -> Phase09TargetReadiness:
    root_path = Path(root)
    source = root_path / target.source_relative_path
    blockers: list[str] = []
    actual_sha256: str | None = None
    actual_blob: str | None = None
    actual_observation_count: int | None = None
    receipt_verified = False
    effective_expected_sha256 = target.source_sha256
    if acquisition_receipt is not None:
        receipt_verified = bool(
            acquisition_receipt.get("object_id") == target.object_id
            and acquisition_receipt.get("source_commit") == target.source_commit
            and acquisition_receipt.get("source_repository_path") == target.source_repository_path
            and acquisition_receipt.get("source_git_blob_sha1") == target.source_git_blob_sha1
            and int(acquisition_receipt.get("source_byte_count", -1)) == target.source_byte_count
            and acquisition_receipt.get("destination_relative_path") == target.source_relative_path
            and is_hex_digest(str(acquisition_receipt.get("source_sha256", "")), 64)
            and acquisition_receipt.get("status") == "VERIFIED_AND_FROZEN"
        )
        if receipt_verified:
            effective_expected_sha256 = str(acquisition_receipt["source_sha256"])

    checks: dict[str, bool] = {
        "declared_exposed_development": target.evidence_role == "exposed-development-only",
        "family_known": target.family in EXPECTED_FAMILIES,
        "period_claim_grade": target.period_claim_grade,
        "mode_claim_grade": target.mode_claim_grade,
        "identity_claim_grade": target.identity_claim_grade,
        "source_commit_digest": is_hex_digest(target.source_commit, 40),
        "source_manifest_blob_digest": is_hex_digest(target.source_git_blob_sha1, 40),
        "expected_observation_capacity": target.source_observation_count >= 240,
        "source_file_present": source.is_file(),
        "source_byte_count": False,
        "source_observation_count": False,
        "source_git_blob_sha1": False,
        "source_sha256_frozen": is_hex_digest(effective_expected_sha256, 64),
        "acquisition_receipt_verified": receipt_verified,
        "source_sha256_matches": False,
        "inherited_result_verified": False,
    }

    if not checks["declared_exposed_development"]:
        blockers.append("IDENTITY_NOT_DECLARED_EXPOSED_DEVELOPMENT")
    if not checks["family_known"]:
        blockers.append("UNKNOWN_FAMILY")
    if not checks["period_claim_grade"]:
        blockers.append("PERIOD_NOT_CLAIM_GRADE")
    if not checks["mode_claim_grade"]:
        blockers.append("MODE_NOT_CLAIM_GRADE")
    if not checks["identity_claim_grade"]:
        blockers.append("CATALOG_IDENTITY_NOT_RESOLVED")
    if not checks["source_commit_digest"]:
        blockers.append("SOURCE_COMMIT_DIGEST_INVALID")
    if not checks["source_manifest_blob_digest"]:
        blockers.append("SOURCE_GIT_BLOB_DIGEST_INVALID")
    if not checks["expected_observation_capacity"]:
        blockers.append("EXPECTED_OBSERVATION_COUNT_BELOW_PROTOCOL_MINIMUM")

    if source.is_file():
        checks["source_byte_count"] = source.stat().st_size == target.source_byte_count
        actual_observation_count = count_observations(source)
        checks["source_observation_count"] = actual_observation_count == target.source_observation_count
        actual_blob = git_blob_sha1_file(source)
        checks["source_git_blob_sha1"] = actual_blob == target.source_git_blob_sha1
        actual_sha256 = sha256_path(source)
        checks["source_sha256_matches"] = (
            effective_expected_sha256 is not None and actual_sha256 == effective_expected_sha256
        )
        if not checks["source_byte_count"]:
            blockers.append("SOURCE_BYTE_COUNT_MISMATCH")
        if not checks["source_observation_count"]:
            blockers.append("SOURCE_OBSERVATION_COUNT_MISMATCH")
        if not checks["source_git_blob_sha1"]:
            blockers.append("SOURCE_GIT_BLOB_SHA1_MISMATCH")
        if not checks["source_sha256_frozen"]:
            blockers.append("SOURCE_SHA256_NOT_FROZEN")
        elif not checks["source_sha256_matches"]:
            blockers.append("SOURCE_SHA256_MISMATCH")
    else:
        blockers.append("SOURCE_BYTES_MISSING")
        if not checks["source_sha256_frozen"]:
            blockers.append("SOURCE_SHA256_PENDING_ACQUISITION")

    inherited_record, inherited_blockers = _load_inherited_record(target, root_path)
    blockers.extend(inherited_blockers)
    checks["inherited_result_verified"] = inherited_record is not None and not inherited_blockers

    return Phase09TargetReadiness(
        target=target,
        checks=checks,
        blockers=tuple(dict.fromkeys(blockers)),
        source_actual_sha256=actual_sha256,
        source_actual_git_blob_sha1=actual_blob,
        effective_expected_sha256=effective_expected_sha256,
        acquisition_receipt_verified=receipt_verified,
        source_actual_observation_count=actual_observation_count,
        inherited_record=inherited_record if checks["inherited_result_verified"] else None,
    )


def _family_summary(
    readiness: Iterable[Phase09TargetReadiness],
    *,
    complete: bool,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    items = tuple(readiness)
    for family in EXPECTED_FAMILIES:
        subset = [item for item in items if item.target.family == family]
        records = [item.inherited_record for item in subset if item.inherited_record is not None]
        qualified = sum(
            record.get("disposition") == QUALIFIED_DISPOSITION
            for record in records
        )
        recovery = sum(
            bool(record.get("checks", {}).get("four_recovery_harmonics_snr"))
            for record in records
        )
        forecast = sum(
            bool(record.get("checks", {}).get("two_forecast_harmonics_snr"))
            for record in records
        )
        structural = sum(
            bool(record.get("checks", {}).get("structural_constraints"))
            for record in records
        )
        row: dict[str, Any] = {
            "family": family,
            "declared_objects": len(subset),
            "metadata_ready_objects": sum(item.metadata_ready for item in subset),
            "source_ready_objects": sum(item.source_ready for item in subset),
            "verified_result_objects": len(records),
            "recovery_ready_count": recovery,
            "forecast_measured_count": forecast,
            "structurally_compatible_count": structural,
            "qualified_count": qualified,
            "population_estimate_status": "COMPLETE" if complete else "SUPPRESSED_INCOMPLETE_COHORT",
        }
        if complete:
            n = len(records)
            for label, count in (
                ("recovery", recovery),
                ("forecast", forecast),
                ("structural", structural),
                ("qualified", qualified),
            ):
                low, high = wilson_interval(count, n)
                row[f"{label}_fraction"] = count / n
                row[f"{label}_wilson95_low"] = low
                row[f"{label}_wilson95_high"] = high
        rows.append(row)
    return tuple(rows)


def assess_phase09(
    *,
    root: str | Path,
    manifest_path: str | Path,
    protocol_path: str | Path,
    seal_path: str | Path,
    acquisition_receipt_path: str | Path | None = None,
) -> Phase09Assessment:
    root_path = Path(root)
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root_path / manifest_file
    protocol_file = Path(protocol_path)
    if not protocol_file.is_absolute():
        protocol_file = root_path / protocol_file
    seal_file = Path(seal_path)
    if not seal_file.is_absolute():
        seal_file = root_path / seal_file

    manifest, targets = load_manifest(manifest_file)
    protocol_valid, protocol_expected, protocol_actual = verify_protocol(protocol_file, seal_file)
    manifest_sha = sha256_path(manifest_file)
    receipt_by_id: dict[str, Mapping[str, Any]] = {}
    receipt_present = False
    receipt_header_valid = False
    if acquisition_receipt_path is not None:
        receipt_file = Path(acquisition_receipt_path)
        if not receipt_file.is_absolute():
            receipt_file = root_path / receipt_file
        receipt_present = receipt_file.is_file()
        if receipt_present:
            receipt_payload = json.loads(receipt_file.read_text(encoding="utf-8"))
            receipt_header_valid = bool(
                receipt_payload.get("receipt_id") == "PHASE09-SOURCE-ACQUISITION-RECEIPT-V1"
                and receipt_payload.get("manifest_id") == manifest.get("manifest_id")
                and receipt_payload.get("manifest_sha256") == manifest_sha
                and receipt_payload.get("attribution_acknowledged") is True
                and receipt_payload.get("dry_run") is False
            )
            if receipt_header_valid:
                receipt_by_id = {
                    str(row["object_id"]): row
                    for row in receipt_payload.get("targets", [])
                    if isinstance(row, Mapping) and "object_id" in row
                }
    readiness = tuple(
        assess_target_readiness(
            target,
            root=root_path,
            acquisition_receipt=receipt_by_id.get(target.object_id),
        )
        for target in targets
    )

    ids = [target.object_id for target in targets]
    family_counts = {family: sum(target.family == family for target in targets) for family in EXPECTED_FAMILIES}
    minimums = json.loads(protocol_file.read_text(encoding="utf-8"))["minimum_population"]
    source_paths = [target.source_repository_path for target in targets]
    relative_paths = [target.source_relative_path for target in targets]
    structure_ready = bool(
        len(ids) == int(minimums["total"])
        and len(ids) == len(set(ids))
        and len(source_paths) == len(set(source_paths))
        and len(relative_paths) == len(set(relative_paths))
        and all(family_counts[family] == int(minimums[family]) for family in EXPECTED_FAMILIES)
        and all(item.checks["declared_exposed_development"] for item in readiness)
        and all(item.checks["family_known"] for item in readiness)
        and str(manifest.get("protocol_id")) == json.loads(protocol_file.read_text(encoding="utf-8")).get("protocol_id")
        and str(manifest.get("protocol_sha256")) == protocol_expected
    )
    metadata_ready = all(item.metadata_ready for item in readiness)
    sources_ready = all(item.source_ready for item in readiness)
    inherited_count = sum(item.cached_result_ready for item in readiness)
    # In this release, completed results are verified inherited records. Newly executed
    # Phase-09 records can be added by the runner once all sources pass preflight.
    completed_count = inherited_count
    complete = bool(
        protocol_valid
        and structure_ready
        and metadata_ready
        and sources_ready
        and completed_count == len(readiness)
    )
    partial = _family_summary(readiness, complete=False)
    primary = _family_summary(readiness, complete=True) if complete else ()

    if not protocol_valid or not structure_ready:
        decision = "PHASE09_PROTOCOL_OR_COHORT_STRUCTURE_INVALID"
    elif not metadata_ready and not sources_ready:
        decision = "PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_AND_SOURCE_GATES"
    elif not metadata_ready:
        decision = "PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_GATE"
    elif not sources_ready:
        decision = "PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_SOURCE_GATE"
    elif completed_count < len(readiness):
        decision = "PHASE09_READY_FOR_EXECUTION_RESULTS_NOT_YET_COMPLETE"
    else:
        decision = "PHASE09_DEVELOPMENT_COHORT_COMPLETE_C17_NOT_PROMOTED"

    return Phase09Assessment(
        protocol_valid=protocol_valid,
        protocol_expected_sha256=protocol_expected,
        protocol_actual_sha256=protocol_actual,
        manifest_sha256=manifest_sha,
        target_readiness=readiness,
        acquisition_receipt_present=receipt_present,
        acquisition_receipt_header_valid=receipt_header_valid,
        acquisition_receipt_verified_count=sum(item.acquisition_receipt_verified for item in readiness),
        family_counts=family_counts,
        cohort_structure_ready=structure_ready,
        cohort_metadata_ready=metadata_ready,
        cohort_sources_ready=sources_ready,
        inherited_result_count=inherited_count,
        completed_result_count=completed_count,
        primary_outputs_suppressed=not complete,
        partial_family_summary=partial,
        primary_family_outputs=primary,
        decision=decision,
        c17_promoted=False,
    )


def synthetic_governance_control() -> dict[str, Any]:
    """Return a deterministic non-astrophysical positive control for aggregation.

    The control proves only that the population/fraction machinery can represent a
    complete 5+5+5 cohort and compute Wilson intervals. It is not model evidence.
    """

    rows: list[dict[str, Any]] = []
    patterns = {
        "classical_cepheid": (4, 3, 2, 1),
        "delta_scuti": (3, 2, 1, 0),
        "rr_lyrae": (5, 4, 3, 2),
    }
    for family in EXPECTED_FAMILIES:
        recovery, forecast, structural, qualified = patterns[family]
        row: dict[str, Any] = {
            "family": family,
            "object_count": 5,
            "recovery_ready_count": recovery,
            "forecast_measured_count": forecast,
            "structurally_compatible_count": structural,
            "qualified_count": qualified,
        }
        for label, count in (
            ("recovery", recovery),
            ("forecast", forecast),
            ("structural", structural),
            ("qualified", qualified),
        ):
            low, high = wilson_interval(count, 5)
            row[f"{label}_fraction"] = count / 5
            row[f"{label}_wilson95_low"] = low
            row[f"{label}_wilson95_high"] = high
        rows.append(row)
    payload = {
        "control_id": "PHASE09-GOVERNANCE-AGGREGATION-POSITIVE-CONTROL-V1",
        "scientific_evidence": False,
        "object_count": 15,
        "family_rows": rows,
    }
    payload["sha256_canonical_json"] = canonical_json_sha256(payload)
    return payload
