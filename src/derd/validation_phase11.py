"""Phase-11 progressive evidence unlock.

Phase 10 deliberately used an all-or-nothing complete-cohort gate.  Phase 11
adds a target-level execution frontier so scientifically valid objects can be
processed as their source and metadata locks arrive, without exposing partial
family fractions or weakening the frozen 5+5+5 denominator.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .harmonic_exchange import write_harmonic_exchange
from .ogle_catalog import canonical_json_sha256
from .validation_phase07 import Phase07Config
from .validation_phase08 import (
    Phase08Config,
    Phase08CohortAssessment,
    Phase08Target,
    assess_cohort,
)
from .validation_phase10 import Phase10Assessment, Phase10TargetReadiness


PHASE11_DECISION_BLOCKED = "PHASE11_NO_FRESH_TARGET_EXECUTION_READY"
PHASE11_DECISION_UNLOCKED = "PHASE11_TARGET_LEVEL_EXECUTION_UNLOCKED_POPULATION_GATE_CLOSED"
PHASE11_DECISION_COMPLETE = "PHASE11_COMPLETE_COHORT_EXECUTED_POPULATION_OUTPUTS_AVAILABLE"

EXPECTED_FAMILY_SIZE = 5
EXPECTED_TOTAL = 15


@dataclass(frozen=True, slots=True)
class Phase11Config:
    """Frozen computation coordinates for progressive target execution."""

    synthetic_samples_per_class: int = 96
    propagation_draws: int = 2048
    period_grid_count: int = 101
    minimum_observations: int = 240
    fast: bool = False

    def target_config(self) -> Phase07Config:
        config = Phase07Config(
            synthetic_samples_per_class=self.synthetic_samples_per_class,
            propagation_draws=self.propagation_draws,
            observation_sweep_counts=(),
            observation_sweep_repetitions=1,
            minimum_observations=self.minimum_observations,
            period_grid_count=self.period_grid_count,
        )
        if self.fast:
            config = replace(
                config,
                synthetic_samples_per_class=24,
                propagation_draws=256,
                period_grid_count=51,
            )
        return config

    def as_dict(self) -> dict[str, Any]:
        return {
            "synthetic_samples_per_class": self.synthetic_samples_per_class,
            "propagation_draws": self.propagation_draws,
            "period_grid_count": self.period_grid_count,
            "minimum_observations": self.minimum_observations,
            "fast": self.fast,
        }


@dataclass(frozen=True, slots=True)
class Phase11Execution:
    """Fresh target-level execution plus cryptographic input/result bindings."""

    cohort: Phase08CohortAssessment
    records: tuple[Mapping[str, Any], ...]
    config_sha256: str
    receipt_sha256: str | None

    @property
    def fresh_execution_count(self) -> int:
        return len(self.records)

    def as_dict(self, *, include_controls: bool = False) -> dict[str, Any]:
        return {
            "fresh_execution_count": self.fresh_execution_count,
            "config_sha256": self.config_sha256,
            "receipt_sha256": self.receipt_sha256,
            "records": [dict(row) for row in self.records],
            "cohort": self.cohort.as_dict(include_controls=include_controls),
        }


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_sha256(config: Phase11Config) -> str:
    return canonical_json_sha256(config.as_dict())


def convert_ready_target(item: Phase10TargetReadiness) -> Phase08Target:
    """Convert one fully locked Phase-10 target into a Phase-08 evidence target."""

    if not item.execution_ready:
        raise ValueError(f"target is not execution-ready: {item.target.object_id}")
    source = item.phase09_source
    target = item.target.phase09
    expected_sha = source.effective_expected_sha256
    if expected_sha is None:
        raise ValueError(f"missing frozen SHA-256 for {target.object_id}")

    period_grade = target.period_evidence_grade
    period_source = target.period_source
    object_id = target.object_id
    if item.target.metadata_lock_required:
        period_grade = "EXTERNAL_CATALOG_OGLE_IV_PRIMARY_PERIOD"
        period_source = "OGLE-IV LMC DSCT authoritative metadata lock"
        object_id = item.effective_object_id

    return Phase08Target(
        object_id=object_id,
        family=target.family,
        mode=item.effective_mode,
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
    )


def input_lock_payload(
    item: Phase10TargetReadiness,
    target: Phase08Target,
    *,
    config_digest: str,
    receipt_digest: str | None,
) -> dict[str, Any]:
    """Return the exact evidence coordinates bound to a fresh execution."""

    return {
        "declared_object_id": item.target.object_id,
        "effective_object_id": target.object_id,
        "family": target.family,
        "mode": target.mode,
        "period_days": target.catalog_period_days,
        "period_evidence_grade": target.period_evidence_grade,
        "period_source": target.period_source,
        "source_repository": target.source_repository,
        "source_commit": target.source_commit,
        "source_repository_path": target.source_repository_path,
        "source_git_blob_sha1": target.source_git_blob_sha1,
        "source_sha256": target.source_sha256,
        "source_byte_count": target.source_byte_count,
        "metadata_lock_sha256": (
            None if item.metadata_lock is None else str(item.metadata_lock.get("sha256_canonical_json"))
        ),
        "phase11_config_sha256": config_digest,
        "source_receipt_sha256": receipt_digest,
        "evidence_role": target.evidence_role,
        "physical_claim_scope": "waveform-only",
    }


def population_firewall(
    declared: Iterable[Phase10TargetReadiness],
    fresh_object_ids: Iterable[str],
) -> dict[str, Any]:
    """Suppress fractions unless every frozen family denominator is complete."""

    declared_rows = tuple(declared)
    fresh = set(fresh_object_ids)
    families = sorted({row.target.family for row in declared_rows})
    coverage: list[dict[str, Any]] = []
    complete = len(declared_rows) == EXPECTED_TOTAL
    for family in families:
        subset = [row for row in declared_rows if row.target.family == family]
        executed = sum(
            row.effective_object_id in fresh or row.target.object_id in fresh
            for row in subset
        )
        family_complete = len(subset) == EXPECTED_FAMILY_SIZE and executed == EXPECTED_FAMILY_SIZE
        complete = complete and family_complete
        coverage.append(
            {
                "family": family,
                "declared_count": len(subset),
                "fresh_execution_count": executed,
                "family_denominator_complete": family_complete,
                "fractions_suppressed": not family_complete,
            }
        )
    return {
        "complete_cohort_denominator": complete,
        "primary_family_outputs_allowed": complete,
        "family_coverage": coverage,
        "firewall_rule": (
            "No family fraction or Wilson interval is emitted until all five declared "
            "objects in every family have fresh, lock-bound executions."
        ),
    }


def execute_ready_targets(
    assessment: Phase10Assessment,
    *,
    root: str | Path,
    output: str | Path,
    config: Phase11Config | None = None,
    receipt_path: str | Path | None = None,
) -> Phase11Execution | None:
    """Execute every currently ready target, while retaining the denominator firewall."""

    active = Phase11Config() if config is None else config
    ready_items = tuple(item for item in assessment.targets if item.execution_ready)
    if not ready_items:
        return None

    root_path = Path(root).resolve()
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = root_path / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    receipt_digest: str | None = None
    if receipt_path is not None:
        receipt_file = Path(receipt_path)
        if not receipt_file.is_absolute():
            receipt_file = root_path / receipt_file
        if receipt_file.is_file():
            receipt_digest = sha256_file(receipt_file)

    converted = tuple(convert_ready_target(item) for item in ready_items)
    cohort = assess_cohort(
        converted,
        root=root_path,
        config=Phase08Config(
            target_config=active.target_config(),
            minimum_objects_per_family_for_population_inference=EXPECTED_FAMILY_SIZE,
            minimum_total_objects_for_population_inference=EXPECTED_TOTAL,
        ),
    )
    by_id = {item.effective_object_id: item for item in ready_items}
    by_declared = {item.target.object_id: item for item in ready_items}
    digest = config_sha256(active)
    records: list[Mapping[str, Any]] = []
    exchange_dir = output_path / "harmonic_exchange"

    for target_result in cohort.targets:
        target = target_result.target
        readiness = by_id.get(target.object_id) or by_declared.get(target.object_id)
        if readiness is None:
            raise RuntimeError(f"execution result has no readiness record: {target.object_id}")
        exchange = target_result.result.harmonic_fit.to_exchange(
            object_id=target.object_id,
            time_unit="day",
            value_unit="relative_flux",
            source_locator=target.source_locator,
            source_sha256=target.source_sha256,
            metadata={
                "phase": "11",
                "family": target.family,
                "mode": target.mode,
                "catalog_period_days": target.catalog_period_days,
                "period_evidence_grade": target.period_evidence_grade,
                "period_source": target.period_source,
                "evidence_role": target.evidence_role,
                "physical_claim_scope": "waveform-only",
            },
        )
        exchange_path = exchange_dir / f"{target.object_id}.json"
        write_harmonic_exchange(exchange_path, exchange)
        result_payload = target_result.as_dict(include_controls=False)
        locked_input = input_lock_payload(
            readiness,
            target,
            config_digest=digest,
            receipt_digest=receipt_digest,
        )
        record = {
            "object_id": target.object_id,
            "declared_object_id": readiness.target.object_id,
            "family": target.family,
            "input_lock": locked_input,
            "input_lock_sha256": canonical_json_sha256(locked_input),
            "result": result_payload,
            "result_sha256": canonical_json_sha256(result_payload),
            "exchange_relative_path": exchange_path.relative_to(root_path).as_posix(),
            "exchange_sha256": sha256_file(exchange_path),
            "stage_reached": target_result.stage_reached,
            "disposition": target_result.disposition,
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        }
        records.append(record)

    records.sort(key=lambda row: str(row["object_id"]))
    return Phase11Execution(
        cohort=cohort,
        records=tuple(records),
        config_sha256=digest,
        receipt_sha256=receipt_digest,
    )


def frontier_rows(
    assessment: Phase10Assessment,
    fresh_object_ids: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Describe every frozen target, including those not yet executable."""

    fresh = set(fresh_object_ids)
    rows: list[dict[str, Any]] = []
    for item in assessment.targets:
        if item.execution_ready:
            frontier = "FRESH_EXECUTED" if (
                item.target.object_id in fresh or item.effective_object_id in fresh
            ) else "EXECUTION_READY"
        elif item.metadata_ready and not item.source_ready:
            frontier = "SOURCE_LOCK_REQUIRED"
        elif item.source_ready and not item.metadata_ready:
            frontier = "METADATA_LOCK_REQUIRED"
        else:
            frontier = "METADATA_AND_SOURCE_LOCKS_REQUIRED"
        rows.append(
            {
                "object_id": item.target.object_id,
                "effective_object_id": item.effective_object_id,
                "family": item.target.family,
                "metadata_ready": item.metadata_ready,
                "source_ready": item.source_ready,
                "cached_result_ready": item.cached_result_ready,
                "execution_ready": item.execution_ready,
                "fresh_executed": frontier == "FRESH_EXECUTED",
                "frontier": frontier,
                "blocker_count": len(item.blockers),
                "blockers": "|".join(item.blockers),
            }
        )
    return rows


def phase11_decision(
    assessment: Phase10Assessment,
    execution: Phase11Execution | None,
) -> str:
    if execution is None or execution.fresh_execution_count == 0:
        return PHASE11_DECISION_BLOCKED
    firewall = population_firewall(
        assessment.targets,
        [row["object_id"] for row in execution.records],
    )
    if firewall["primary_family_outputs_allowed"]:
        return PHASE11_DECISION_COMPLETE
    return PHASE11_DECISION_UNLOCKED
