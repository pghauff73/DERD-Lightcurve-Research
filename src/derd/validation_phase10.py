"""Phase-10 authoritative metadata and source-lock gate.

Phase 09 froze the denominator.  Phase 10 freezes the *coordinates* required to
execute it: authoritative catalogue rows, explicit OGLE-III/OGLE-IV identity
relations, and independently replayable source bytes.  No legacy period finder,
string-equality assumption, or partial denominator may satisfy these gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ogle_catalog import (
    DeltaScutiMetadataLock,
    Ogle4LmcDsctIdentity,
    Ogle4LmcDsctParameters,
    canonical_json_sha256,
    resolve_delta_scuti_metadata,
    verify_lock_payload,
)
from .validation_phase09 import (
    EXPECTED_FAMILIES,
    Phase09Target,
    Phase09TargetReadiness,
    assess_target_readiness,
    verify_protocol,
)


PHASE10_DECISION_READY = "PHASE10_AUTHORITATIVE_METADATA_AND_SOURCE_LOCK_COMPLETE"
PHASE10_DECISION_BLOCKED = (
    "PHASE10_IMPLEMENTED_CATALOG_CONTRACT_LOCKED_EXECUTION_BLOCKED_BY_"
    "AUTHORITATIVE_ROWS_AND_RAW_SOURCE_BYTES"
)


@dataclass(frozen=True, slots=True)
class Phase10Target:
    phase09: Phase09Target
    metadata_lock_required: bool
    metadata_lock_key: str | None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase10Target":
        return cls(
            phase09=Phase09Target.from_dict(value),
            metadata_lock_required=bool(value.get("metadata_lock_required", False)),
            metadata_lock_key=(
                None if value.get("metadata_lock_key") in (None, "") else str(value["metadata_lock_key"])
            ),
        )

    @property
    def object_id(self) -> str:
        return self.phase09.object_id

    @property
    def family(self) -> str:
        return self.phase09.family

    def as_dict(self) -> dict[str, Any]:
        payload = self.phase09.as_dict()
        payload["metadata_lock_required"] = self.metadata_lock_required
        payload["metadata_lock_key"] = self.metadata_lock_key
        return payload


@dataclass(frozen=True, slots=True)
class Phase10TargetReadiness:
    target: Phase10Target
    phase09_source: Phase09TargetReadiness
    metadata_lock: Mapping[str, Any] | None
    metadata_checks: Mapping[str, bool]
    blockers: tuple[str, ...]
    effective_object_id: str
    effective_mode: str
    effective_period_days: float
    effective_period_error_days: float | None

    @property
    def metadata_ready(self) -> bool:
        return all(self.metadata_checks.values())

    @property
    def source_ready(self) -> bool:
        return self.phase09_source.source_ready

    @property
    def execution_ready(self) -> bool:
        return self.metadata_ready and self.source_ready

    @property
    def cached_result_ready(self) -> bool:
        return self.phase09_source.cached_result_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.as_dict(),
            "metadata_lock": None if self.metadata_lock is None else dict(self.metadata_lock),
            "metadata_checks": dict(self.metadata_checks),
            "metadata_ready": self.metadata_ready,
            "source_ready": self.source_ready,
            "cached_result_ready": self.cached_result_ready,
            "execution_ready": self.execution_ready,
            "effective_object_id": self.effective_object_id,
            "effective_mode": self.effective_mode,
            "effective_period_days": self.effective_period_days,
            "effective_period_error_days": self.effective_period_error_days,
            "blockers": list(self.blockers),
            "source": self.phase09_source.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class Phase10Assessment:
    protocol_valid: bool
    protocol_expected_sha256: str
    protocol_actual_sha256: str
    cohort_manifest_sha256: str
    metadata_lock_manifest_sha256: str | None
    catalog_contract_valid: bool
    cohort_structure_ready: bool
    family_counts: Mapping[str, int]
    targets: tuple[Phase10TargetReadiness, ...]
    metadata_ready_count: int
    source_ready_count: int
    cached_result_count: int
    execution_ready_count: int
    primary_outputs_suppressed: bool
    decision: str
    c17_promoted: bool = False

    @property
    def cohort_execution_ready(self) -> bool:
        return (
            self.protocol_valid
            and self.catalog_contract_valid
            and self.cohort_structure_ready
            and self.metadata_ready_count == 15
            and self.source_ready_count == 15
            and self.execution_ready_count == 15
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol_valid": self.protocol_valid,
            "protocol_expected_sha256": self.protocol_expected_sha256,
            "protocol_actual_sha256": self.protocol_actual_sha256,
            "cohort_manifest_sha256": self.cohort_manifest_sha256,
            "metadata_lock_manifest_sha256": self.metadata_lock_manifest_sha256,
            "catalog_contract_valid": self.catalog_contract_valid,
            "cohort_structure_ready": self.cohort_structure_ready,
            "family_counts": dict(self.family_counts),
            "targets": [target.as_dict() for target in self.targets],
            "metadata_ready_count": self.metadata_ready_count,
            "source_ready_count": self.source_ready_count,
            "cached_result_count": self.cached_result_count,
            "execution_ready_count": self.execution_ready_count,
            "cohort_execution_ready": self.cohort_execution_ready,
            "primary_outputs_suppressed": self.primary_outputs_suppressed,
            "decision": self.decision,
            "c17_promoted": self.c17_promoted,
        }


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_phase10_manifest(path: str | Path) -> tuple[Mapping[str, Any], tuple[Phase10Target, ...]]:
    payload = _load_json(Path(path))
    targets = tuple(Phase10Target.from_dict(row) for row in payload["targets"])
    return payload, targets


def load_metadata_lock(path: str | Path) -> tuple[Mapping[str, Any], Mapping[str, Mapping[str, Any]]]:
    payload = _load_json(Path(path))
    records = payload.get("records", [])
    by_key: dict[str, Mapping[str, Any]] = {}
    for record in records:
        key = str(record.get("requested_object_id", ""))
        if not key:
            raise ValueError("metadata lock record lacks requested_object_id")
        if key in by_key:
            raise ValueError(f"duplicate metadata lock key: {key}")
        by_key[key] = record
    return payload, by_key


def _valid_lock(record: Mapping[str, Any], requested: str) -> tuple[bool, dict[str, bool]]:
    period = record.get("primary_period_days")
    period_error = record.get("primary_period_error_days")
    checks = {
        "lock_digest": verify_lock_payload(record),
        "requested_identity": record.get("requested_object_id") == requested,
        "current_identity": str(record.get("current_object_id", "")).startswith("OGLE-LMC-DSCT-"),
        "explicit_match_basis": record.get("match_basis") in {
            "DIRECT_CURRENT_ID",
            "OGLE_IV_IDENT_OGLE_III_ID",
        },
        "catalog_subtype": record.get("subtype") in {"singlemode", "multimode"},
        "noninvented_mode_label": record.get("mode_label") in {
            "singlemode_radial_order_unresolved",
            "multimode",
        },
        "positive_period": isinstance(period, (int, float)) and math.isfinite(float(period)) and float(period) > 0.0,
        "nonnegative_period_error": (
            isinstance(period_error, (int, float))
            and math.isfinite(float(period_error))
            and float(period_error) >= 0.0
        ),
        "identity_row_digest": len(str(record.get("identity_row_sha256", ""))) == 64,
        "parameter_row_digest": len(str(record.get("parameter_row_sha256", ""))) == 64,
        "catalog_file_digests": (
            len(str(record.get("identity_catalog_sha256", ""))) == 64
            and len(str(record.get("parameter_catalog_sha256", ""))) == 64
        ),
        "authority_declared": bool(record.get("authority")),
        "source_urls_declared": bool(record.get("identity_source_url")) and bool(record.get("parameter_source_url")),
    }
    return all(checks.values()), checks


def assess_target(
    target: Phase10Target,
    *,
    root: Path,
    metadata_locks: Mapping[str, Mapping[str, Any]],
    acquisition_receipt: Mapping[str, Any] | None,
) -> Phase10TargetReadiness:
    phase09_readiness = assess_target_readiness(
        target.phase09,
        root=root,
        acquisition_receipt=acquisition_receipt,
    )
    blockers = list(phase09_readiness.blockers)
    record: Mapping[str, Any] | None = None
    effective_object_id = target.object_id
    effective_mode = target.phase09.mode
    effective_period = target.phase09.catalog_period_days
    effective_period_error: float | None = None

    if target.metadata_lock_required:
        key = target.metadata_lock_key or target.object_id
        record = metadata_locks.get(key)
        if record is None:
            checks = {"authoritative_metadata_lock_present": False}
            blockers.extend(
                [
                    "AUTHORITATIVE_METADATA_LOCK_MISSING",
                    "DELTA_SCUTI_PERIOD_NOT_LOCKED",
                    "DELTA_SCUTI_SUBTYPE_NOT_LOCKED",
                    "DELTA_SCUTI_IDENTITY_CROSSWALK_NOT_LOCKED",
                ]
            )
        else:
            _, lock_checks = _valid_lock(record, key)
            checks = {"authoritative_metadata_lock_present": True, **lock_checks}
            for name, passed in checks.items():
                if not passed:
                    blockers.append(f"METADATA_LOCK_{name.upper()}_FAILED")
            if all(checks.values()):
                effective_object_id = str(record["current_object_id"])
                effective_mode = str(record["mode_label"])
                effective_period = float(record["primary_period_days"])
                effective_period_error = float(record["primary_period_error_days"])
                # Phase-09 blockers describe the superseded legacy coordinate. Remove
                # only those three metadata blockers; source and evidence blockers stay.
                superseded = {
                    "PERIOD_NOT_CLAIM_GRADE",
                    "MODE_NOT_CLAIM_GRADE",
                    "CATALOG_IDENTITY_NOT_RESOLVED",
                }
                blockers = [item for item in blockers if item not in superseded]
    else:
        checks = {
            "phase09_period_claim_grade": target.phase09.period_claim_grade,
            "phase09_mode_claim_grade": target.phase09.mode_claim_grade,
            "phase09_identity_claim_grade": target.phase09.identity_claim_grade,
        }
        for name, passed in checks.items():
            if not passed:
                blockers.append(f"{name.upper()}_FAILED")

    return Phase10TargetReadiness(
        target=target,
        phase09_source=phase09_readiness,
        metadata_lock=record,
        metadata_checks=checks,
        blockers=tuple(dict.fromkeys(blockers)),
        effective_object_id=effective_object_id,
        effective_mode=effective_mode,
        effective_period_days=effective_period,
        effective_period_error_days=effective_period_error,
    )


def assess_phase10(
    *,
    root: str | Path,
    cohort_manifest_path: str | Path,
    metadata_lock_path: str | Path,
    catalog_contract_path: str | Path,
    protocol_path: str | Path,
    seal_path: str | Path,
    acquisition_receipt_path: str | Path | None = None,
) -> Phase10Assessment:
    root_path = Path(root).resolve()

    def resolved(value: str | Path) -> Path:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else root_path / candidate

    cohort_path = resolved(cohort_manifest_path)
    lock_path = resolved(metadata_lock_path)
    contract_path = resolved(catalog_contract_path)
    protocol_file = resolved(protocol_path)
    seal_file = resolved(seal_path)
    cohort_payload, targets = load_phase10_manifest(cohort_path)
    lock_payload, metadata_locks = load_metadata_lock(lock_path)
    contract = _load_json(contract_path)
    protocol_valid, expected_protocol, actual_protocol = verify_protocol(protocol_file, seal_file)

    family_counts = {family: sum(target.family == family for target in targets) for family in EXPECTED_FAMILIES}
    identities = [target.object_id for target in targets]
    paths = [target.phase09.source_repository_path for target in targets]
    cohort_structure_ready = (
        len(targets) == 15
        and family_counts == {family: 5 for family in EXPECTED_FAMILIES}
        and len(set(identities)) == len(identities)
        and len(set(paths)) == len(paths)
        and all(target.phase09.evidence_role == "exposed-development-only" for target in targets)
    )

    contract_payload = dict(contract)
    contract_digest = contract_payload.pop("sha256_canonical_json", None)
    catalog_contract_valid = (
        isinstance(contract_digest, str)
        and len(contract_digest) == 64
        and canonical_json_sha256(contract_payload) == contract_digest
        and contract.get("contract_id") == cohort_payload.get("catalog_contract_id")
    )

    receipt_payload: Mapping[str, Any] | None = None
    receipts_by_id: dict[str, Mapping[str, Any]] = {}
    if acquisition_receipt_path is not None:
        receipt_file = resolved(acquisition_receipt_path)
        if receipt_file.is_file():
            receipt_payload = _load_json(receipt_file)
            for row in receipt_payload.get("targets", []):
                if isinstance(row, dict) and row.get("object_id"):
                    receipts_by_id[str(row["object_id"])] = row

    target_rows = tuple(
        assess_target(
            target,
            root=root_path,
            metadata_locks=metadata_locks,
            acquisition_receipt=receipts_by_id.get(target.object_id),
        )
        for target in targets
    )
    metadata_ready_count = sum(row.metadata_ready for row in target_rows)
    source_ready_count = sum(row.source_ready for row in target_rows)
    cached_result_count = sum(row.cached_result_ready for row in target_rows)
    execution_ready_count = sum(row.execution_ready for row in target_rows)
    complete = (
        protocol_valid
        and catalog_contract_valid
        and cohort_structure_ready
        and metadata_ready_count == 15
        and source_ready_count == 15
        and execution_ready_count == 15
    )
    return Phase10Assessment(
        protocol_valid=protocol_valid,
        protocol_expected_sha256=expected_protocol,
        protocol_actual_sha256=actual_protocol,
        cohort_manifest_sha256=canonical_json_sha256(cohort_payload),
        metadata_lock_manifest_sha256=canonical_json_sha256(lock_payload),
        catalog_contract_valid=catalog_contract_valid,
        cohort_structure_ready=cohort_structure_ready,
        family_counts=family_counts,
        targets=target_rows,
        metadata_ready_count=metadata_ready_count,
        source_ready_count=source_ready_count,
        cached_result_count=cached_result_count,
        execution_ready_count=execution_ready_count,
        primary_outputs_suppressed=not complete,
        decision=PHASE10_DECISION_READY if complete else PHASE10_DECISION_BLOCKED,
    )


def synthetic_catalog_lock_control() -> Mapping[str, Any]:
    """Exercise fixed-width parsing and OGLE-III crosswalk resolution deterministically."""

    def ident_line(current: int, old: int, subtype: str) -> str:
        # Construct exactly the published fixed-width locations.
        chars = [" "] * 136
        fields = (
            (1, 19, f"OGLE-LMC-DSCT-{current:05d}"),
            (22, 31, subtype),
            (34, 35, "05"),
            (37, 38, "21"),
            (40, 44, "12.34"),
            (46, 48, "-69"),
            (50, 51, "44"),
            (53, 56, "01.2"),
            (59, 74, f"OGLE-LMC-DSCT-{current:05d}"),
            (76, 90, f"LMC-DSCT-{old:04d}"),
        )
        for start, stop, value in fields:
            width = stop - start + 1
            text = value[:width].ljust(width)
            chars[start - 1 : stop] = text
        return "".join(chars)

    def parameter_line(current: int, period: float) -> str:
        chars = [" "] * 238
        fields = (
            (1, 19, f"OGLE-LMC-DSCT-{current:05d}"),
            (22, 27, "18.123"),
            (29, 34, "18.456"),
            (37, 46, f"{period:10.8f}"),
            (48, 57, f"{0.00000011:10.8f}"),
            (60, 69, f"{9000.12345:10.5f}"),
            (72, 76, "0.123"),
        )
        for start, stop, value in fields:
            width = stop - start + 1
            text = value[:width].ljust(width)
            chars[start - 1 : stop] = text
        return "".join(chars)

    requested = [f"OGLE-LMC-DSCT-{value:04d}" for value in range(3, 8)]
    identities = tuple(
        Ogle4LmcDsctIdentity.parse(ident_line(10_000 + index, old, "singlemode" if index % 2 else "multimode"))
        for index, old in enumerate(range(3, 8))
    )
    parameters = tuple(
        Ogle4LmcDsctParameters.parse(parameter_line(10_000 + index, 0.08 + 0.01 * index))
        for index in range(5)
    )
    locks = resolve_delta_scuti_metadata(
        requested,
        identities,
        parameters,
        identity_catalog_sha256="1" * 64,
        parameter_catalog_sha256="2" * 64,
        authority="SYNTHETIC_POSITIVE_CONTROL",
        identity_source_url="synthetic://ident.dat",
        parameter_source_url="synthetic://dsct.dat",
        catalogue_release="synthetic-v1",
    )
    payload = {
        "requested_count": len(requested),
        "resolved_count": len(locks),
        "unique_current_count": len({lock.current_object_id for lock in locks}),
        "all_locks_verify": all(verify_lock_payload(lock.as_dict()) for lock in locks),
        "all_crosswalked": all(lock.match_basis == "OGLE_IV_IDENT_OGLE_III_ID" for lock in locks),
        "singlemode_radial_order_invented": any(
            lock.subtype == "singlemode" and lock.mode_label not in {"singlemode_radial_order_unresolved"}
            for lock in locks
        ),
        "locks": [lock.as_dict() for lock in locks],
    }
    payload["sha256_canonical_json"] = canonical_json_sha256(payload)
    return payload
