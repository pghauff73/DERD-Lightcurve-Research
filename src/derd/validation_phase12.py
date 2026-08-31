"""Phase-12 cumulative replay ledger and deterministic cross-phase audit.

Phase 11 unlocked one target at a time while retaining a complete-denominator
firewall.  Phase 12 adds a cumulative evidence ledger so a validated prior
execution does not need its raw source bytes to be re-imported merely to remain
counted as completed evidence.  Newly available targets are executed under the
unchanged Phase-11 scientific coordinates, appended only after cryptographic
validation, and compared with any inherited Phase-08 record.

The ledger is deliberately evidence-preserving rather than score-seeking:
conflicting duplicate records, tampered hashes, missing exchange artifacts, and
scientific replay drift are hard failures.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .ogle_catalog import canonical_json_sha256
from .validation_phase10 import Phase10Assessment
from .validation_phase11 import (
    EXPECTED_FAMILY_SIZE,
    EXPECTED_TOTAL,
    Phase11Config,
    Phase11Execution,
    execute_ready_targets,
)


PHASE12_DECISION_BLOCKED = "PHASE12_NO_NEW_TARGET_EXECUTION_READY"
PHASE12_DECISION_UPDATED = (
    "PHASE12_CUMULATIVE_LEDGER_UPDATED_REPLAY_AUDIT_PASSED_POPULATION_GATE_CLOSED"
)
PHASE12_DECISION_DRIFT = "PHASE12_SCIENTIFIC_REPLAY_DRIFT_DETECTED"
PHASE12_DECISION_COMPLETE = "PHASE12_COMPLETE_COHORT_LEDGER_POPULATION_OUTPUTS_AVAILABLE"


@dataclass(frozen=True, slots=True)
class Phase12Config:
    """Frozen coordinates for Phase-12 cumulative execution and replay checks."""

    synthetic_samples_per_class: int = 96
    propagation_draws: int = 2048
    period_grid_count: int = 101
    minimum_observations: int = 240
    fast: bool = False
    require_scientific_replay_match: bool = True

    def phase11(self) -> Phase11Config:
        return Phase11Config(
            synthetic_samples_per_class=self.synthetic_samples_per_class,
            propagation_draws=self.propagation_draws,
            period_grid_count=self.period_grid_count,
            minimum_observations=self.minimum_observations,
            fast=self.fast,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "synthetic_samples_per_class": self.synthetic_samples_per_class,
            "propagation_draws": self.propagation_draws,
            "period_grid_count": self.period_grid_count,
            "minimum_observations": self.minimum_observations,
            "fast": self.fast,
            "require_scientific_replay_match": self.require_scientific_replay_match,
        }


@dataclass(frozen=True, slots=True)
class VerifiedLedger:
    """Cryptographically verified cumulative evidence records."""

    records: tuple[Mapping[str, Any], ...]
    prior_summary_sha256: str
    prior_record_count: int
    new_record_count: int

    @property
    def cumulative_count(self) -> int:
        return len(self.records)

    def as_dict(self) -> dict[str, Any]:
        return {
            "prior_summary_sha256": self.prior_summary_sha256,
            "prior_record_count": self.prior_record_count,
            "new_record_count": self.new_record_count,
            "cumulative_count": self.cumulative_count,
            "records": [dict(record) for record in self.records],
        }


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def verify_evidence_record(
    record: Mapping[str, Any],
    *,
    root: str | Path,
    origin_phase: str,
    origin_summary_relative_path: str,
    origin_summary_sha256: str,
) -> dict[str, Any]:
    """Verify one Phase-11-style evidence record and add immutable provenance."""

    root_path = Path(root).resolve()
    required = {
        "object_id",
        "declared_object_id",
        "family",
        "input_lock",
        "input_lock_sha256",
        "result",
        "result_sha256",
        "exchange_relative_path",
        "exchange_sha256",
        "stage_reached",
        "disposition",
        "certificate",
    }
    missing = sorted(required - set(record))
    _require(not missing, f"evidence record missing fields: {missing}")

    object_id = str(record["object_id"])
    input_lock = record["input_lock"]
    result = record["result"]
    _require(isinstance(input_lock, Mapping), f"input lock is not an object: {object_id}")
    _require(isinstance(result, Mapping), f"result is not an object: {object_id}")
    _require(
        canonical_json_sha256(input_lock) == record["input_lock_sha256"],
        f"input-lock digest mismatch: {object_id}",
    )
    _require(
        canonical_json_sha256(result) == record["result_sha256"],
        f"result digest mismatch: {object_id}",
    )
    _require(_is_sha256(record["exchange_sha256"]), f"invalid exchange digest: {object_id}")

    exchange_path = root_path / str(record["exchange_relative_path"])
    _require(exchange_path.is_file(), f"exchange artifact missing: {object_id}")
    _require(
        sha256_file(exchange_path) == record["exchange_sha256"],
        f"exchange digest mismatch: {object_id}",
    )

    target = result.get("target")
    _require(isinstance(target, Mapping), f"result target missing: {object_id}")
    _require(target.get("object_id") == object_id, f"result identity mismatch: {object_id}")
    _require(target.get("family") == record["family"], f"result family mismatch: {object_id}")
    _require(result.get("stage_reached") == record["stage_reached"], f"stage mismatch: {object_id}")
    _require(result.get("disposition") == record["disposition"], f"disposition mismatch: {object_id}")
    _require(
        record.get("certificate") == "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        f"certificate boundary missing: {object_id}",
    )

    payload = dict(record)
    payload.update(
        {
            "origin_phase": origin_phase,
            "origin_summary_relative_path": origin_summary_relative_path,
            "origin_summary_sha256": origin_summary_sha256,
            "ledger_record_sha256": canonical_json_sha256(record),
        }
    )
    return payload


def load_verified_phase11_records(
    *,
    root: str | Path,
    summary_path: str | Path = "artifacts/phase11/phase11_summary.json",
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """Load and verify the prior Phase-11 evidence ledger."""

    root_path = Path(root).resolve()
    candidate = Path(summary_path)
    summary_file = candidate if candidate.is_absolute() else root_path / candidate
    _require(summary_file.is_file(), f"prior summary missing: {summary_file}")
    summary_sha = sha256_file(summary_file)
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    _require(
        summary.get("implementation_id") == "DERD-v1.1-phase11-progressive-evidence-unlock",
        "unexpected prior implementation identifier",
    )
    _require(bool(summary.get("protocol", {}).get("valid")), "prior Phase-11 protocol was not valid")
    execution = summary.get("fresh_execution")
    _require(isinstance(execution, Mapping), "prior Phase-11 execution block missing")
    raw_records = execution.get("records", [])
    _require(isinstance(raw_records, list), "prior Phase-11 records are malformed")

    verified: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    relative_summary = summary_file.relative_to(root_path).as_posix()
    for raw in raw_records:
        _require(isinstance(raw, Mapping), "prior evidence record is not an object")
        item = verify_evidence_record(
            raw,
            root=root_path,
            origin_phase="phase11",
            origin_summary_relative_path=relative_summary,
            origin_summary_sha256=summary_sha,
        )
        object_id = str(item["object_id"])
        _require(object_id not in seen, f"duplicate prior object: {object_id}")
        seen.add(object_id)
        verified.append(item)
    verified.sort(key=lambda row: str(row["object_id"]))
    return tuple(verified), summary_sha


def subset_new_ready_assessment(
    assessment: Phase10Assessment,
    *,
    excluded_object_ids: Iterable[str],
) -> Phase10Assessment:
    """Return an assessment containing only ready objects absent from the ledger."""

    excluded = set(excluded_object_ids)
    rows = tuple(
        item
        for item in assessment.targets
        if item.execution_ready
        and item.target.object_id not in excluded
        and item.effective_object_id not in excluded
    )
    return Phase10Assessment(
        protocol_valid=assessment.protocol_valid,
        protocol_expected_sha256=assessment.protocol_expected_sha256,
        protocol_actual_sha256=assessment.protocol_actual_sha256,
        cohort_manifest_sha256=assessment.cohort_manifest_sha256,
        metadata_lock_manifest_sha256=assessment.metadata_lock_manifest_sha256,
        catalog_contract_valid=assessment.catalog_contract_valid,
        cohort_structure_ready=assessment.cohort_structure_ready,
        family_counts=assessment.family_counts,
        targets=rows,
        metadata_ready_count=sum(item.metadata_ready for item in rows),
        source_ready_count=sum(item.source_ready for item in rows),
        cached_result_count=sum(item.cached_result_ready for item in rows),
        execution_ready_count=sum(item.execution_ready for item in rows),
        primary_outputs_suppressed=True,
        decision=assessment.decision,
        c17_promoted=False,
    )


def execute_new_ready_targets(
    assessment: Phase10Assessment,
    *,
    prior_records: Sequence[Mapping[str, Any]],
    root: str | Path,
    output: str | Path,
    config: Phase12Config | None = None,
    receipt_path: str | Path | None = None,
) -> Phase11Execution | None:
    """Execute only targets not already represented in the verified ledger."""

    active = Phase12Config() if config is None else config
    excluded = [str(record["object_id"]) for record in prior_records]
    subset = subset_new_ready_assessment(assessment, excluded_object_ids=excluded)
    if not subset.targets:
        return None
    return execute_ready_targets(
        subset,
        root=root,
        output=output,
        config=active.phase11(),
        receipt_path=receipt_path,
    )


def scientific_result_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the scientifically meaningful record, excluding transport labels.

    Phase 08 and later phases can legitimately use different local relative paths
    and more concise human-readable period-source labels while producing the same
    measured and calibrated result.  These two transport fields are excluded; all
    numerical, structural, source-object, and evidence-gate coordinates remain.
    """

    payload = json.loads(json.dumps(record, sort_keys=True))
    target = dict(payload.get("target", {}))
    target.pop("source_relative_path", None)
    target.pop("period_source", None)
    payload["target"] = target
    return payload


def harmonic_exchange_projection(exchange: Mapping[str, Any]) -> dict[str, Any]:
    """Return the lossless coefficient object without phase-label metadata drift."""

    payload = json.loads(json.dumps(exchange, sort_keys=True))
    metadata = dict(payload.get("metadata", {}))
    metadata.pop("phase", None)
    metadata.pop("period_source", None)
    payload["metadata"] = metadata
    return payload


def _max_abs_difference(values_a: Sequence[float], values_b: Sequence[float]) -> float:
    _require(len(values_a) == len(values_b), "vector lengths differ during replay audit")
    return max((abs(float(a) - float(b)) for a, b in zip(values_a, values_b)), default=0.0)


def replay_audit(
    fresh_record: Mapping[str, Any],
    *,
    root: str | Path,
    inherited: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare a fresh execution with its frozen Phase-08 record, when available."""

    object_id = str(fresh_record["object_id"])
    if inherited is None:
        return {
            "object_id": object_id,
            "status": "NO_INHERITED_PHASE08_RECORD",
            "comparable": False,
            "scientific_match": None,
            "exchange_match": None,
            "full_record_match": None,
        }

    root_path = Path(root).resolve()
    summary_path = root_path / str(inherited["summary_relative_path"])
    exchange_path = root_path / str(inherited["exchange_relative_path"])
    _require(summary_path.is_file(), f"inherited summary missing: {object_id}")
    _require(exchange_path.is_file(), f"inherited exchange missing: {object_id}")
    _require(
        sha256_file(exchange_path) == inherited["exchange_sha256"],
        f"inherited exchange digest mismatch: {object_id}",
    )
    prior_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    matches = [
        row
        for row in prior_summary.get("cohort", {}).get("targets", [])
        if row.get("target", {}).get("object_id") == object_id
    ]
    _require(len(matches) == 1, f"inherited target record is not unique: {object_id}")
    prior_record = matches[0]
    _require(
        canonical_json_sha256(prior_record) == inherited["canonical_target_record_sha256"],
        f"inherited target digest mismatch: {object_id}",
    )

    fresh_result = fresh_record["result"]
    full_match = canonical_json_sha256(prior_record) == canonical_json_sha256(fresh_result)
    scientific_prior = scientific_result_projection(prior_record)
    scientific_fresh = scientific_result_projection(fresh_result)
    scientific_match = scientific_prior == scientific_fresh

    fresh_exchange_path = root_path / str(fresh_record["exchange_relative_path"])
    _require(fresh_exchange_path.is_file(), f"fresh exchange missing: {object_id}")
    prior_exchange = json.loads(exchange_path.read_text(encoding="utf-8"))
    fresh_exchange = json.loads(fresh_exchange_path.read_text(encoding="utf-8"))
    exchange_match = harmonic_exchange_projection(prior_exchange) == harmonic_exchange_projection(
        fresh_exchange
    )

    prior_snr = prior_record["result"]["harmonic_fit"]["coefficient_snr"]
    fresh_snr = fresh_result["result"]["harmonic_fit"]["coefficient_snr"]
    target_drift: dict[str, dict[str, Any]] = {}
    for field in ("source_relative_path", "period_source"):
        before = prior_record.get("target", {}).get(field)
        after = fresh_result.get("target", {}).get(field)
        if before != after:
            target_drift[field] = {"phase08": before, "fresh": after}

    if full_match:
        status = "EXACT_RECORD_REPLAY_MATCH"
    elif scientific_match and exchange_match:
        status = "SCIENTIFIC_REPLAY_MATCH_METADATA_TRANSPORT_DRIFT"
    else:
        status = "SCIENTIFIC_REPLAY_DRIFT_DETECTED"

    return {
        "object_id": object_id,
        "status": status,
        "comparable": True,
        "full_record_match": full_match,
        "scientific_match": scientific_match,
        "exchange_match": exchange_match,
        "phase08_record_sha256": canonical_json_sha256(prior_record),
        "fresh_record_sha256": canonical_json_sha256(fresh_result),
        "phase08_scientific_sha256": canonical_json_sha256(scientific_prior),
        "fresh_scientific_sha256": canonical_json_sha256(scientific_fresh),
        "maximum_harmonic_snr_absolute_difference": _max_abs_difference(prior_snr, fresh_snr),
        "screen_score_difference": float(
            fresh_result["result"]["screen"]["score"]
            - prior_record["result"]["screen"]["score"]
        ),
        "threshold_difference": float(
            fresh_result["result"]["calibration"]["threshold"]
            - prior_record["result"]["calibration"]["threshold"]
        ),
        "stage_match": fresh_result["stage_reached"] == prior_record["stage_reached"],
        "disposition_match": fresh_result["disposition"] == prior_record["disposition"],
        "transport_metadata_differences": target_drift,
    }


def verify_new_execution_records(
    execution: Phase11Execution | None,
    *,
    root: str | Path,
    summary_relative_path: str,
    summary_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    if execution is None:
        return ()
    verified = [
        verify_evidence_record(
            record,
            root=root,
            origin_phase="phase12",
            origin_summary_relative_path=summary_relative_path,
            origin_summary_sha256=summary_sha256,
        )
        for record in execution.records
    ]
    seen: set[str] = set()
    for record in verified:
        object_id = str(record["object_id"])
        _require(object_id not in seen, f"duplicate new object: {object_id}")
        seen.add(object_id)
    return tuple(sorted(verified, key=lambda row: str(row["object_id"])))


def merge_cumulative_records(
    prior_records: Sequence[Mapping[str, Any]],
    new_records: Sequence[Mapping[str, Any]],
    *,
    prior_summary_sha256: str,
) -> VerifiedLedger:
    """Merge unique evidence records; conflicting duplicates are forbidden."""

    merged: dict[str, Mapping[str, Any]] = {}
    for record in [*prior_records, *new_records]:
        object_id = str(record["object_id"])
        if object_id in merged:
            existing = merged[object_id]
            if (
                existing.get("result_sha256") != record.get("result_sha256")
                or existing.get("input_lock_sha256") != record.get("input_lock_sha256")
                or existing.get("exchange_sha256") != record.get("exchange_sha256")
            ):
                raise ValueError(f"conflicting duplicate evidence record: {object_id}")
            continue
        merged[object_id] = record
    rows = tuple(merged[key] for key in sorted(merged))
    return VerifiedLedger(
        records=rows,
        prior_summary_sha256=prior_summary_sha256,
        prior_record_count=len(prior_records),
        new_record_count=len(new_records),
    )


def cumulative_population_firewall(
    assessment: Phase10Assessment,
    ledger: VerifiedLedger,
) -> dict[str, Any]:
    """Return cumulative coverage while suppressing incomplete denominators."""

    recorded = {str(record["object_id"]) for record in ledger.records}
    families = sorted({item.target.family for item in assessment.targets})
    complete = len(assessment.targets) == EXPECTED_TOTAL
    coverage: list[dict[str, Any]] = []
    for family in families:
        declared = [item for item in assessment.targets if item.target.family == family]
        count = sum(
            item.target.object_id in recorded or item.effective_object_id in recorded
            for item in declared
        )
        family_complete = len(declared) == EXPECTED_FAMILY_SIZE and count == EXPECTED_FAMILY_SIZE
        complete = complete and family_complete
        coverage.append(
            {
                "family": family,
                "declared_count": len(declared),
                "cumulative_record_count": count,
                "family_denominator_complete": family_complete,
                "fractions_suppressed": not family_complete,
            }
        )
    return {
        "cumulative_record_count": ledger.cumulative_count,
        "complete_cohort_denominator": complete,
        "primary_family_outputs_allowed": complete,
        "family_coverage": coverage,
        "firewall_rule": (
            "No family fraction, Wilson interval, or population claim is emitted until "
            "all fifteen declared targets have verified cumulative evidence records."
        ),
    }


def phase12_decision(
    *,
    ledger: VerifiedLedger,
    replay_audits: Sequence[Mapping[str, Any]],
    config: Phase12Config,
    firewall: Mapping[str, Any],
) -> str:
    drift = any(row.get("status") == "SCIENTIFIC_REPLAY_DRIFT_DETECTED" for row in replay_audits)
    if drift and config.require_scientific_replay_match:
        return PHASE12_DECISION_DRIFT
    if firewall.get("primary_family_outputs_allowed"):
        return PHASE12_DECISION_COMPLETE
    if ledger.new_record_count:
        return PHASE12_DECISION_UPDATED
    return PHASE12_DECISION_BLOCKED
