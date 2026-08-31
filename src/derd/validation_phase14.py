"""Phase-14 period-coordinate robustness and cumulative-ledger extension.

Phase 13 added chronological harmonic replication. Phase 14 selects the next
result-blind exposed-development target, replays its frozen Phase-08 result,
and adds an orthogonal period-coordinate robustness audit. The period is
refined with a generic phase-dispersion objective, never by minimizing the
DERD compatibility score. Temporal stationarity is then evaluated at both the
catalog and independently refined periods.

This module concerns normalized waveform evidence only. It does not identify a
unique internal stellar mechanism, a transparent shell, or a shell mass.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .ogle_catalog import canonical_json_sha256
from .period import adaptive_verify_catalog_period, phase_dispersion_score
from .preprocess import clean_light_curve
from .lightcurve import LightCurve, ValueDomain
from .validation_phase12 import VerifiedLedger, merge_cumulative_records, sha256_file, verify_evidence_record
from .validation_phase13 import (
    Phase13Config,
    TemporalReplicationAudit,
    _score_simulation,
    run_temporal_replication_audit,
)


PHASE14_DECISION_UPDATED = (
    "PHASE14_PERIOD_ROBUSTNESS_LEDGER_UPDATED_POPULATION_GATE_CLOSED"
)
PHASE14_DECISION_BLOCKED = "PHASE14_NO_NEW_ACQUISITION_TARGET_READY"
PHASE14_DECISION_DRIFT = "PHASE14_SCIENTIFIC_REPLAY_DRIFT_DETECTED"

PERIOD_ROBUST_BOTH_PASS = "TEMPORAL_STATIONARITY_ROBUST_TO_PERIOD_REFINEMENT"
PERIOD_RESCUES = "PERIOD_REFINEMENT_RESCUES_TEMPORAL_STATIONARITY_GATE"
PERIOD_BREAKS = "PERIOD_REFINEMENT_BREAKS_TEMPORAL_STATIONARITY_GATE"
PERIOD_ROBUST_BOTH_FAIL = "TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT"


@dataclass(frozen=True, slots=True)
class Phase14Config:
    """Frozen Phase-14 scientific and coordinate-robustness settings."""

    synthetic_samples_per_class: int = 96
    propagation_draws: int = 2048
    period_grid_count: int = 101
    minimum_observations: int = 240
    fast: bool = False
    require_scientific_replay_match: bool = True
    temporal_blocks: int = 3
    minimum_block_observations: int = 100
    phase_bins: int = 12
    minimum_occupied_phase_bins: int = 10
    harmonic_order: int = 8
    temporal_fit_harmonics: int = 4
    harmonic_ridge: float = 1.0e-4
    maximum_design_condition_number: float = 1.0e4
    minimum_recovery_snr: float = 3.0
    stationary_replicates: int = 192
    drift_replicates: int = 192
    development_fraction: float = 0.70
    stationary_quantile: float = 0.95
    drift_severities: tuple[float, ...] = (0.25, 0.50, 0.75, 1.00)
    minimum_drift_auc: float = 0.80
    minimum_drift_balanced_accuracy: float = 0.75
    temporal_random_seed: int = 2026081814
    period_relative_spans: tuple[float, ...] = (0.001, 0.005, 0.02)
    period_bins: int = 8
    period_surface_span: float = 0.001
    period_surface_grid_count: int = 101

    def phase12_dict(self) -> dict[str, Any]:
        return {
            "synthetic_samples_per_class": self.synthetic_samples_per_class,
            "propagation_draws": self.propagation_draws,
            "period_grid_count": self.period_grid_count,
            "minimum_observations": self.minimum_observations,
            "fast": self.fast,
            "require_scientific_replay_match": self.require_scientific_replay_match,
        }

    def phase13(self, *, random_seed: int | None = None) -> Phase13Config:
        return Phase13Config(
            synthetic_samples_per_class=self.synthetic_samples_per_class,
            propagation_draws=self.propagation_draws,
            period_grid_count=self.period_grid_count,
            minimum_observations=self.minimum_observations,
            fast=self.fast,
            require_scientific_replay_match=self.require_scientific_replay_match,
            temporal_blocks=self.temporal_blocks,
            minimum_block_observations=self.minimum_block_observations,
            phase_bins=self.phase_bins,
            minimum_occupied_phase_bins=self.minimum_occupied_phase_bins,
            harmonic_order=self.harmonic_order,
            temporal_fit_harmonics=self.temporal_fit_harmonics,
            harmonic_ridge=self.harmonic_ridge,
            maximum_design_condition_number=self.maximum_design_condition_number,
            minimum_recovery_snr=self.minimum_recovery_snr,
            stationary_replicates=self.stationary_replicates,
            drift_replicates=self.drift_replicates,
            development_fraction=self.development_fraction,
            stationary_quantile=self.stationary_quantile,
            drift_severities=self.drift_severities,
            minimum_drift_auc=self.minimum_drift_auc,
            minimum_drift_balanced_accuracy=self.minimum_drift_balanced_accuracy,
            random_seed=self.temporal_random_seed if random_seed is None else random_seed,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.phase12_dict(),
            "temporal_blocks": self.temporal_blocks,
            "minimum_block_observations": self.minimum_block_observations,
            "phase_bins": self.phase_bins,
            "minimum_occupied_phase_bins": self.minimum_occupied_phase_bins,
            "harmonic_order": self.harmonic_order,
            "temporal_fit_harmonics": self.temporal_fit_harmonics,
            "harmonic_ridge": self.harmonic_ridge,
            "maximum_design_condition_number": self.maximum_design_condition_number,
            "minimum_recovery_snr": self.minimum_recovery_snr,
            "stationary_replicates": self.stationary_replicates,
            "drift_replicates": self.drift_replicates,
            "development_fraction": self.development_fraction,
            "stationary_quantile": self.stationary_quantile,
            "drift_severities": list(self.drift_severities),
            "minimum_drift_auc": self.minimum_drift_auc,
            "minimum_drift_balanced_accuracy": self.minimum_drift_balanced_accuracy,
            "temporal_random_seed": self.temporal_random_seed,
            "period_relative_spans": list(self.period_relative_spans),
            "period_bins": self.period_bins,
            "period_surface_span": self.period_surface_span,
            "period_surface_grid_count": self.period_surface_grid_count,
        }


@dataclass(frozen=True, slots=True)
class PeriodSurfaceRow:
    period_days: float
    relative_offset: float
    phase_dispersion_score: float
    temporal_score: float

    def as_dict(self) -> dict[str, float]:
        return {
            "period_days": self.period_days,
            "relative_offset": self.relative_offset,
            "phase_dispersion_score": self.phase_dispersion_score,
            "temporal_score": self.temporal_score,
        }


@dataclass(frozen=True, slots=True)
class PeriodCoordinateAudit:
    object_id: str
    catalog_period_days: float
    refined_period_days: float
    relative_period_delta: float
    refinement_resolved: bool
    catalog_dispersion_score: float
    refined_dispersion_score: float
    catalog_temporal_audit: TemporalReplicationAudit
    refined_temporal_audit: TemporalReplicationAudit
    surface_rows: tuple[PeriodSurfaceRow, ...]
    minimum_temporal_score_period_days: float
    minimum_temporal_score: float
    temporal_score_fractional_reduction: float
    classification: str

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "object_id": self.object_id,
            "catalog_period_days": self.catalog_period_days,
            "refined_period_days": self.refined_period_days,
            "relative_period_delta": self.relative_period_delta,
            "refinement_resolved": self.refinement_resolved,
            "catalog_dispersion_score": self.catalog_dispersion_score,
            "refined_dispersion_score": self.refined_dispersion_score,
            "catalog_temporal_audit": self.catalog_temporal_audit.as_dict(),
            "refined_temporal_audit": self.refined_temporal_audit.as_dict(),
            "surface_rows": [row.as_dict() for row in self.surface_rows],
            "minimum_temporal_score_period_days": self.minimum_temporal_score_period_days,
            "minimum_temporal_score": self.minimum_temporal_score,
            "temporal_score_fractional_reduction": self.temporal_score_fractional_reduction,
            "classification": self.classification,
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
            "claim_scope": "period-coordinate robustness of temporal signed-harmonic evidence only",
        }
        payload["sha256_canonical_json"] = canonical_json_sha256(payload)
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_verified_phase13_ledger(
    *,
    root: str | Path,
    summary_path: str | Path = "artifacts/phase13/phase13_summary.json",
) -> tuple[tuple[Mapping[str, Any], ...], str, str, tuple[Mapping[str, Any], ...]]:
    """Verify the Phase-13 ledger, records, and temporal-audit sidecars."""

    root_path = Path(root).resolve()
    candidate = Path(summary_path)
    summary_file = candidate if candidate.is_absolute() else root_path / candidate
    _require(summary_file.is_file(), f"Phase-13 summary missing: {summary_file}")
    summary_sha = sha256_file(summary_file)
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    _require(
        summary.get("implementation_id") == "DERD-v1.3-phase13-temporal-replication-ledger",
        "unexpected Phase-13 implementation identifier",
    )
    _require(bool(summary.get("protocol", {}).get("valid")), "Phase-13 protocol invalid")
    ledger_meta = summary.get("cumulative_ledger")
    _require(isinstance(ledger_meta, Mapping), "Phase-13 ledger metadata missing")
    ledger_path = root_path / str(ledger_meta.get("relative_path", ""))
    seal_path = root_path / str(ledger_meta.get("seal_relative_path", ""))
    _require(ledger_path.is_file() and seal_path.is_file(), "Phase-13 ledger or seal missing")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    ledger_digest = canonical_json_sha256(ledger)
    _require(ledger_digest == seal.get("sha256_canonical_json"), "Phase-13 ledger seal mismatch")
    _require(ledger_digest == ledger_meta.get("seal_sha256_canonical_json"), "summary ledger digest mismatch")
    rows = ledger.get("records")
    _require(isinstance(rows, list), "Phase-13 ledger records malformed")
    _require(len(rows) == 3, "Phase-13 ledger must contain exactly three records")

    provenance_fields = {
        "origin_phase",
        "origin_summary_relative_path",
        "origin_summary_sha256",
        "ledger_record_sha256",
    }
    verified: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        _require(isinstance(row, Mapping), "Phase-13 ledger record is not an object")
        base = {key: value for key, value in row.items() if key not in provenance_fields}
        _require(canonical_json_sha256(base) == row.get("ledger_record_sha256"), "record digest mismatch")
        origin_relative = str(row.get("origin_summary_relative_path", ""))
        origin_path = root_path / origin_relative
        _require(origin_path.is_file(), f"origin summary missing: {row.get('object_id')}")
        _require(sha256_file(origin_path) == row.get("origin_summary_sha256"), "origin summary hash mismatch")
        checked = verify_evidence_record(
            base,
            root=root_path,
            origin_phase=str(row.get("origin_phase")),
            origin_summary_relative_path=origin_relative,
            origin_summary_sha256=str(row.get("origin_summary_sha256")),
        )
        _require(checked == dict(row), f"record provenance mismatch: {row.get('object_id')}")
        object_id = str(row["object_id"])
        _require(object_id not in seen, f"duplicate Phase-13 object: {object_id}")
        seen.add(object_id)
        verified.append(dict(row))

    sidecars = ledger.get("temporal_audits", [])
    _require(isinstance(sidecars, list), "Phase-13 temporal sidecars malformed")
    checked_sidecars: list[Mapping[str, Any]] = []
    for ref in sidecars:
        _require(isinstance(ref, Mapping), "temporal sidecar reference malformed")
        path = root_path / str(ref.get("relative_path", ""))
        _require(path.is_file(), "Phase-13 temporal sidecar missing")
        _require(sha256_file(path) == ref.get("file_sha256"), "Phase-13 temporal sidecar file hash mismatch")
        payload = json.loads(path.read_text(encoding="utf-8"))
        without_self = {key: value for key, value in payload.items() if key != "sha256_canonical_json"}
        _require(canonical_json_sha256(without_self) == payload.get("sha256_canonical_json"), "Phase-13 temporal sidecar canonical hash mismatch")
        _require(payload.get("sha256_canonical_json") == ref.get("canonical_sha256"), "Phase-13 temporal sidecar reference mismatch")
        checked_sidecars.append(dict(ref))

    verified.sort(key=lambda item: str(item["object_id"]))
    return tuple(verified), summary_sha, ledger_digest, tuple(checked_sidecars)


def run_period_coordinate_audit(
    curve: LightCurve,
    *,
    catalog_period: float,
    reference_epoch: float | None = None,
    config: Phase14Config | None = None,
) -> PeriodCoordinateAudit:
    """Test whether generic period refinement changes the temporal gate result."""

    active = Phase14Config() if config is None else config
    cleaned, _ = clean_light_curve(curve, maximum_error_factor=5.0)
    flux = cleaned.to_relative_flux() if cleaned.domain is ValueDomain.MAGNITUDE else cleaned
    time = np.asarray(flux.time, dtype=np.float64)
    values = np.asarray(flux.value, dtype=np.float64)
    errors = np.asarray(flux.error, dtype=np.float64)
    epoch = float(np.min(time)) if reference_epoch is None else float(reference_epoch)

    period_check = adaptive_verify_catalog_period(
        time,
        values,
        catalog_period,
        relative_spans=active.period_relative_spans,
        grid_count=active.period_grid_count,
        bins=active.period_bins,
    )
    refined = float(period_check.best_period)

    offsets = np.linspace(
        -active.period_surface_span,
        active.period_surface_span,
        active.period_surface_grid_count,
        dtype=np.float64,
    )
    temporal_config = active.phase13()
    rows: list[PeriodSurfaceRow] = []
    for offset in offsets:
        period = float(catalog_period * (1.0 + offset))
        rows.append(
            PeriodSurfaceRow(
                period_days=period,
                relative_offset=float(offset),
                phase_dispersion_score=float(
                    phase_dispersion_score(time, values, period, bins=active.period_bins)
                ),
                temporal_score=float(
                    _score_simulation(
                        time=time,
                        values=values,
                        errors=errors,
                        period=period,
                        reference_epoch=epoch,
                        config=temporal_config,
                    )
                ),
            )
        )

    catalog_audit = run_temporal_replication_audit(
        curve,
        period=float(catalog_period),
        reference_epoch=epoch,
        config=temporal_config,
    )
    refined_audit = run_temporal_replication_audit(
        curve,
        period=refined,
        reference_epoch=epoch,
        config=temporal_config,
    )
    catalog_pass = catalog_audit.actual_below_stationary_threshold
    refined_pass = refined_audit.actual_below_stationary_threshold
    if catalog_pass and refined_pass:
        classification = PERIOD_ROBUST_BOTH_PASS
    elif not catalog_pass and refined_pass:
        classification = PERIOD_RESCUES
    elif catalog_pass and not refined_pass:
        classification = PERIOD_BREAKS
    else:
        classification = PERIOD_ROBUST_BOTH_FAIL

    finite_rows = [row for row in rows if np.isfinite(row.temporal_score)]
    minimum = min(finite_rows, key=lambda row: row.temporal_score)
    denominator = max(abs(catalog_audit.actual_temporal_score), np.finfo(float).eps)
    reduction = (
        catalog_audit.actual_temporal_score - minimum.temporal_score
    ) / denominator

    return PeriodCoordinateAudit(
        object_id=curve.star_id,
        catalog_period_days=float(catalog_period),
        refined_period_days=refined,
        relative_period_delta=float(period_check.relative_delta),
        refinement_resolved=bool(period_check.resolved),
        catalog_dispersion_score=float(period_check.stages[0].catalog_score),
        refined_dispersion_score=float(period_check.best_score),
        catalog_temporal_audit=catalog_audit,
        refined_temporal_audit=refined_audit,
        surface_rows=tuple(rows),
        minimum_temporal_score_period_days=float(minimum.period_days),
        minimum_temporal_score=float(minimum.temporal_score),
        temporal_score_fractional_reduction=float(reduction),
        classification=classification,
    )


def period_audit_sidecar(
    audit: PeriodCoordinateAudit,
    *,
    ledger_record: Mapping[str, Any],
    configuration_sha256: str,
    source_receipt_sha256: str | None,
) -> dict[str, Any]:
    payload = {
        "sidecar_id": "DERD-PHASE14-PERIOD-COORDINATE-ROBUSTNESS-SIDECAR-1.0",
        "object_id": audit.object_id,
        "ledger_record_sha256": ledger_record["ledger_record_sha256"],
        "input_lock_sha256": ledger_record["input_lock_sha256"],
        "result_sha256": ledger_record["result_sha256"],
        "exchange_sha256": ledger_record["exchange_sha256"],
        "phase14_configuration_sha256": configuration_sha256,
        "source_receipt_sha256": source_receipt_sha256,
        "audit": audit.as_dict(),
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "claim_boundary": "period-coordinate robustness of normalized waveform evidence only",
    }
    payload["sha256_canonical_json"] = canonical_json_sha256(payload)
    return payload


def merge_phase14_ledger(
    prior_records: Sequence[Mapping[str, Any]],
    new_records: Sequence[Mapping[str, Any]],
    *,
    prior_summary_sha256: str,
) -> VerifiedLedger:
    return merge_cumulative_records(
        prior_records,
        new_records,
        prior_summary_sha256=prior_summary_sha256,
    )
