"""Phase-15 archival lineage promotion and cumulative-ledger extension.

Phase 15 promotes one already completed, source-verified Phase-08 development
record into the cumulative ledger without redistributing or reacquiring the raw
photometry.  Promotion is allowed only when the Phase-07 source manifest, the
Phase-07 source receipt/summary, the Phase-08 target record, the harmonic
exchange artifact, and the frozen Phase-10 cohort coordinates agree.

The module also compares the Phase-07 and Phase-08 analyses of the same source.
Those analyses used different scientific configurations, so disagreement is
reported as configuration-sensitive lineage drift rather than treated as a
failed exact replay or silently averaged away.

This module concerns normalized waveform evidence only.  It does not identify
a unique internal stellar mechanism, a transparent shell, or a shell mass.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .ogle_catalog import canonical_json_sha256
from .validation_phase12 import (
    VerifiedLedger,
    merge_cumulative_records,
    sha256_file,
    verify_evidence_record,
)


PHASE15_DECISION_UPDATED = (
    "PHASE15_ARCHIVAL_LINEAGE_PROMOTED_LEDGER_UPDATED_POPULATION_GATE_CLOSED"
)
PHASE15_DECISION_BLOCKED = "PHASE15_NO_ARCHIVAL_RECORD_ELIGIBLE"

LINEAGE_EXACT = "ARCHIVAL_LINEAGE_SCIENTIFICALLY_EXACT"
LINEAGE_CONFIG_DRIFT = "ARCHIVAL_LINEAGE_CONFIGURATION_SENSITIVE_SCIENTIFIC_DRIFT"
LINEAGE_PROVENANCE_CONFLICT = "ARCHIVAL_LINEAGE_PROVENANCE_CONFLICT"


@dataclass(frozen=True, slots=True)
class Phase15Config:
    selected_object_id: str = "OGLE-LMC-CEP-0010"
    parent_record_count: int = 4
    require_source_coordinate_identity: bool = True
    require_phase08_record_hash: bool = True
    allow_configuration_sensitive_drift: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected_object_id": self.selected_object_id,
            "parent_record_count": self.parent_record_count,
            "require_source_coordinate_identity": self.require_source_coordinate_identity,
            "require_phase08_record_hash": self.require_phase08_record_hash,
            "allow_configuration_sensitive_drift": self.allow_configuration_sensitive_drift,
        }


@dataclass(frozen=True, slots=True)
class ArchivalLineageAudit:
    object_id: str
    source_coordinates_match: bool
    phase07_source_verified: bool
    phase08_record_hash_verified: bool
    phase08_exchange_hash_verified: bool
    phase07_exchange_file_sha256: str
    phase08_exchange_file_sha256: str
    exchange_exact: bool
    maximum_sine_coefficient_absolute_difference: float
    maximum_cosine_coefficient_absolute_difference: float
    maximum_harmonic_snr_absolute_difference: float
    phase07_screen_score: float
    phase08_screen_score: float
    screen_score_difference: float
    phase07_threshold: float
    phase08_threshold: float
    threshold_difference: float
    phase07_stage: str
    phase08_stage: str
    stage_match: bool
    phase07_disposition: str
    phase08_disposition: str
    disposition_match: bool
    configuration_equal: bool
    classification: str
    interpretation: str

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "object_id": self.object_id,
            "source_coordinates_match": self.source_coordinates_match,
            "phase07_source_verified": self.phase07_source_verified,
            "phase08_record_hash_verified": self.phase08_record_hash_verified,
            "phase08_exchange_hash_verified": self.phase08_exchange_hash_verified,
            "phase07_exchange_file_sha256": self.phase07_exchange_file_sha256,
            "phase08_exchange_file_sha256": self.phase08_exchange_file_sha256,
            "exchange_exact": self.exchange_exact,
            "maximum_sine_coefficient_absolute_difference": self.maximum_sine_coefficient_absolute_difference,
            "maximum_cosine_coefficient_absolute_difference": self.maximum_cosine_coefficient_absolute_difference,
            "maximum_harmonic_snr_absolute_difference": self.maximum_harmonic_snr_absolute_difference,
            "phase07_screen_score": self.phase07_screen_score,
            "phase08_screen_score": self.phase08_screen_score,
            "screen_score_difference": self.screen_score_difference,
            "phase07_threshold": self.phase07_threshold,
            "phase08_threshold": self.phase08_threshold,
            "threshold_difference": self.threshold_difference,
            "phase07_stage": self.phase07_stage,
            "phase08_stage": self.phase08_stage,
            "stage_match": self.stage_match,
            "phase07_disposition": self.phase07_disposition,
            "phase08_disposition": self.phase08_disposition,
            "disposition_match": self.disposition_match,
            "configuration_equal": self.configuration_equal,
            "classification": self.classification,
            "interpretation": self.interpretation,
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
            "claim_scope": "archival computational lineage and normalized waveform evidence only",
        }
        payload["sha256_canonical_json"] = canonical_json_sha256(payload)
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"expected JSON object: {path}")
    return payload


def _verify_ledger_record(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    provenance_fields = {
        "origin_phase",
        "origin_summary_relative_path",
        "origin_summary_sha256",
        "ledger_record_sha256",
    }
    base = {key: value for key, value in row.items() if key not in provenance_fields}
    _require(
        canonical_json_sha256(base) == row.get("ledger_record_sha256"),
        f"ledger record digest mismatch: {row.get('object_id')}",
    )
    origin_relative = str(row.get("origin_summary_relative_path", ""))
    origin = root / origin_relative
    _require(origin.is_file(), f"origin summary missing: {row.get('object_id')}")
    _require(
        sha256_file(origin) == row.get("origin_summary_sha256"),
        f"origin summary digest mismatch: {row.get('object_id')}",
    )
    checked = verify_evidence_record(
        base,
        root=root,
        origin_phase=str(row.get("origin_phase")),
        origin_summary_relative_path=origin_relative,
        origin_summary_sha256=str(row.get("origin_summary_sha256")),
    )
    _require(checked == dict(row), f"ledger provenance mismatch: {row.get('object_id')}")
    return checked


def load_verified_phase14_ledger(
    *,
    root: str | Path,
    summary_path: str | Path = "artifacts/phase14/phase14_summary.json",
) -> tuple[
    tuple[Mapping[str, Any], ...],
    str,
    str,
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    """Verify the Phase-14 ledger, records, and inherited sidecars."""

    root_path = Path(root).resolve()
    candidate = Path(summary_path)
    summary_file = candidate if candidate.is_absolute() else root_path / candidate
    _require(summary_file.is_file(), f"Phase-14 summary missing: {summary_file}")
    summary_sha = sha256_file(summary_file)
    summary = _load_json(summary_file)
    _require(
        summary.get("implementation_id")
        == "DERD-v1.4-phase14-period-coordinate-robustness-ledger",
        "unexpected Phase-14 implementation identifier",
    )
    _require(bool(summary.get("protocol", {}).get("valid")), "Phase-14 protocol invalid")

    meta = summary.get("cumulative_ledger")
    _require(isinstance(meta, Mapping), "Phase-14 ledger metadata missing")
    ledger_path = root_path / str(meta.get("relative_path", ""))
    seal_path = root_path / str(meta.get("seal_relative_path", ""))
    _require(ledger_path.is_file() and seal_path.is_file(), "Phase-14 ledger or seal missing")
    ledger = _load_json(ledger_path)
    seal = _load_json(seal_path)
    ledger_digest = canonical_json_sha256(ledger)
    _require(ledger_digest == seal.get("sha256_canonical_json"), "Phase-14 ledger seal mismatch")
    _require(
        ledger_digest == meta.get("seal_sha256_canonical_json"),
        "Phase-14 summary ledger digest mismatch",
    )

    rows = ledger.get("records")
    _require(isinstance(rows, list), "Phase-14 ledger records malformed")
    _require(len(rows) == 4, "Phase-14 ledger must contain exactly four records")
    verified: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        _require(isinstance(row, Mapping), "Phase-14 ledger record is not an object")
        checked = _verify_ledger_record(row, root_path)
        object_id = str(checked["object_id"])
        _require(object_id not in seen, f"duplicate Phase-14 object: {object_id}")
        seen.add(object_id)
        verified.append(checked)

    def verify_sidecars(key: str) -> tuple[Mapping[str, Any], ...]:
        refs = ledger.get(key, [])
        _require(isinstance(refs, list), f"Phase-14 {key} malformed")
        output: list[Mapping[str, Any]] = []
        for ref in refs:
            _require(isinstance(ref, Mapping), f"Phase-14 {key} reference malformed")
            path = root_path / str(ref.get("relative_path", ""))
            _require(path.is_file(), f"Phase-14 {key} sidecar missing")
            _require(sha256_file(path) == ref.get("file_sha256"), f"Phase-14 {key} file hash mismatch")
            payload = _load_json(path)
            without_self = {k: v for k, v in payload.items() if k != "sha256_canonical_json"}
            _require(
                canonical_json_sha256(without_self) == payload.get("sha256_canonical_json"),
                f"Phase-14 {key} canonical hash mismatch",
            )
            _require(
                payload.get("sha256_canonical_json") == ref.get("canonical_sha256"),
                f"Phase-14 {key} reference mismatch",
            )
            output.append(dict(ref))
        return tuple(output)

    verified.sort(key=lambda item: str(item["object_id"]))
    return (
        tuple(verified),
        summary_sha,
        ledger_digest,
        verify_sidecars("inherited_temporal_audits"),
        verify_sidecars("period_coordinate_audits"),
    )


def find_phase08_target(summary: Mapping[str, Any], object_id: str) -> Mapping[str, Any]:
    cohort = summary.get("cohort")
    _require(isinstance(cohort, Mapping), "Phase-08 cohort missing")
    targets = cohort.get("targets")
    _require(isinstance(targets, list), "Phase-08 target list missing")
    matches = [row for row in targets if isinstance(row, Mapping) and row.get("target", {}).get("object_id") == object_id]
    _require(len(matches) == 1, f"Phase-08 target match count is {len(matches)} for {object_id}")
    return matches[0]


def _coefficient_snr_phase07(summary: Mapping[str, Any]) -> np.ndarray:
    measurements = summary["combined_harmonic_evidence_gate"]["measurements"]
    return np.asarray(measurements["coefficient_snr"], dtype=np.float64)


def _coefficient_snr_phase08(row: Mapping[str, Any]) -> np.ndarray:
    return np.asarray(row["checks"] and row["result"]["gate"]["measurements"]["coefficient_snr"], dtype=np.float64)


def audit_archival_lineage(
    *,
    root: str | Path,
    object_id: str,
    expected_phase08_record_sha256: str,
    expected_phase08_exchange_sha256: str,
) -> tuple[ArchivalLineageAudit, Mapping[str, Any]]:
    """Verify source lineage and quantify Phase-07/Phase-08 scientific drift."""

    root_path = Path(root).resolve()
    source_manifest = _load_json(root_path / "data/manifests/phase07_source_manifest.json")
    phase07 = _load_json(root_path / "artifacts/phase07/phase07_summary.json")
    phase08 = _load_json(root_path / "artifacts/phase08/phase08_summary.json")
    row = find_phase08_target(phase08, object_id)
    target = row["target"]

    source = source_manifest["source"]
    phase07_source = phase07["source"]
    source_coordinates_match = bool(
        source_manifest.get("object_id") == object_id
        and target.get("object_id") == object_id
        and source.get("repository") == target.get("source_repository") == phase07_source.get("source_repository")
        and source.get("commit") == target.get("source_commit") == phase07_source.get("source_commit")
        and source.get("path") == target.get("source_repository_path")
        and source.get("git_blob_sha1") == target.get("source_git_blob_sha1") == phase07_source.get("expected_git_blob_sha1")
        and source.get("local_sha256") == target.get("source_sha256") == phase07_source.get("local_sha256")
        and int(source.get("byte_count")) == int(target.get("source_byte_count")) == int(phase07_source.get("local_byte_count"))
        and int(source.get("observation_count")) == int(row["result"].get("observation_count")) == int(phase07_source.get("observation_count"))
    )
    phase07_source_verified = bool(
        source.get("git_blob_verified")
        and phase07_source.get("git_blob_verified")
        and phase07_source.get("observed_git_blob_sha1") == source.get("git_blob_sha1")
    )
    phase08_record_hash_verified = canonical_json_sha256(row) == expected_phase08_record_sha256

    phase07_exchange_path = root_path / "artifacts/phase07/OGLE-LMC-CEP-0010.catalog-period.harmonics.json"
    phase08_exchange_path = root_path / f"artifacts/phase08/harmonic_exchange/{object_id}.json"
    phase07_exchange = _load_json(phase07_exchange_path)
    phase08_exchange = _load_json(phase08_exchange_path)
    phase08_exchange_hash_verified = sha256_file(phase08_exchange_path) == expected_phase08_exchange_sha256
    phase07_exchange_hash = sha256_file(phase07_exchange_path)
    phase08_exchange_hash = sha256_file(phase08_exchange_path)

    sine07 = np.asarray(phase07_exchange["sine_coefficients"], dtype=np.float64)
    sine08 = np.asarray(phase08_exchange["sine_coefficients"], dtype=np.float64)
    cosine07 = np.asarray(phase07_exchange["cosine_coefficients"], dtype=np.float64)
    cosine08 = np.asarray(phase08_exchange["cosine_coefficients"], dtype=np.float64)
    snr07 = _coefficient_snr_phase07(phase07)
    snr08 = _coefficient_snr_phase08(row)

    score07 = float(phase07["combined_harmonic_evidence_gate"]["measurements"]["screen_score"])
    threshold07 = float(phase07["combined_harmonic_evidence_gate"]["measurements"]["score_threshold"])
    score08 = float(row["result"]["gate"]["measurements"]["screen_score"])
    threshold08 = float(row["result"]["gate"]["measurements"]["score_threshold"])
    stage07 = (
        "FORECAST_HARMONICS"
        if phase07["combined_harmonic_evidence_gate"]["checks"]["four_recovery_harmonics_snr"]
        else "RECOVERY_HARMONICS"
    )
    stage08 = str(row["stage_reached"])
    disposition07 = str(phase07["component_evidence_status"])
    disposition08 = str(row["disposition"])

    config07 = {
        "synthetic_samples_per_class": phase07["actual_cadence_calibration"]["development_metrics"]["sample_count"]
        + phase07["actual_cadence_calibration"]["holdout_metrics"]["sample_count"],
        "cleaning_error_threshold": phase07["cleaning"]["error_threshold"],
        "implementation_id": phase07["implementation_id"],
    }
    config08 = {
        **phase08.get("configuration", {}),
        "implementation_id": phase08.get("implementation_id"),
    }
    configuration_equal = config07 == config08
    exchange_exact = phase07_exchange == phase08_exchange

    if not (source_coordinates_match and phase07_source_verified and phase08_record_hash_verified and phase08_exchange_hash_verified):
        classification = LINEAGE_PROVENANCE_CONFLICT
        interpretation = "Archival promotion is blocked because one or more immutable source or artifact coordinates disagree."
    elif exchange_exact and stage07 == stage08 and disposition07 == disposition08:
        classification = LINEAGE_EXACT
        interpretation = "The source and scientific representation replay exactly across the two archived implementations."
    else:
        classification = LINEAGE_CONFIG_DRIFT
        interpretation = (
            "The source identity is exact, but the Phase-07 and Phase-08 scientific configurations produce different "
            "signed coefficients, SNR values, stage labels, or thresholds.  They are retained as separate analysis "
            "versions and are not counted as independent astrophysical replications."
        )

    audit = ArchivalLineageAudit(
        object_id=object_id,
        source_coordinates_match=source_coordinates_match,
        phase07_source_verified=phase07_source_verified,
        phase08_record_hash_verified=phase08_record_hash_verified,
        phase08_exchange_hash_verified=phase08_exchange_hash_verified,
        phase07_exchange_file_sha256=phase07_exchange_hash,
        phase08_exchange_file_sha256=phase08_exchange_hash,
        exchange_exact=exchange_exact,
        maximum_sine_coefficient_absolute_difference=float(np.max(np.abs(sine07 - sine08))),
        maximum_cosine_coefficient_absolute_difference=float(np.max(np.abs(cosine07 - cosine08))),
        maximum_harmonic_snr_absolute_difference=float(np.max(np.abs(snr07 - snr08))),
        phase07_screen_score=score07,
        phase08_screen_score=score08,
        screen_score_difference=float(score08 - score07),
        phase07_threshold=threshold07,
        phase08_threshold=threshold08,
        threshold_difference=float(threshold08 - threshold07),
        phase07_stage=stage07,
        phase08_stage=stage08,
        stage_match=stage07 == stage08,
        phase07_disposition=disposition07,
        phase08_disposition=disposition08,
        disposition_match=disposition07 == disposition08,
        configuration_equal=configuration_equal,
        classification=classification,
        interpretation=interpretation,
    )
    return audit, row


def build_archival_evidence_record(
    *,
    root: str | Path,
    phase08_row: Mapping[str, Any],
    phase08_summary_sha256: str,
    source_manifest_sha256: str,
    phase07_summary_sha256: str,
    phase15_config_sha256: str,
) -> dict[str, Any]:
    """Construct a Phase-11-compatible evidence record from verified archives."""

    root_path = Path(root).resolve()
    target = phase08_row["target"]
    object_id = str(target["object_id"])
    result_payload = dict(phase08_row)
    input_lock = {
        "declared_object_id": object_id,
        "effective_object_id": object_id,
        "family": target["family"],
        "mode": target["mode"],
        "period_days": target["catalog_period_days"],
        "period_evidence_grade": target["period_evidence_grade"],
        "period_source": target["period_source"],
        "source_repository": target["source_repository"],
        "source_commit": target["source_commit"],
        "source_repository_path": target["source_repository_path"],
        "source_git_blob_sha1": target["source_git_blob_sha1"],
        "source_sha256": target["source_sha256"],
        "source_byte_count": target["source_byte_count"],
        "source_observation_count": phase08_row["result"]["observation_count"],
        "phase07_source_manifest_sha256": source_manifest_sha256,
        "phase07_summary_sha256": phase07_summary_sha256,
        "phase08_summary_sha256": phase08_summary_sha256,
        "phase15_config_sha256": phase15_config_sha256,
        "archival_promotion": True,
        "raw_source_reacquired": False,
        "evidence_role": target["evidence_role"],
        "physical_claim_scope": "waveform-only",
    }
    exchange_relative = f"artifacts/phase08/harmonic_exchange/{object_id}.json"
    exchange_path = root_path / exchange_relative
    _require(exchange_path.is_file(), f"Phase-08 exchange missing: {object_id}")
    return {
        "object_id": object_id,
        "declared_object_id": object_id,
        "family": target["family"],
        "input_lock": input_lock,
        "input_lock_sha256": canonical_json_sha256(input_lock),
        "result": result_payload,
        "result_sha256": canonical_json_sha256(result_payload),
        "exchange_relative_path": exchange_relative,
        "exchange_sha256": sha256_file(exchange_path),
        "stage_reached": phase08_row["stage_reached"],
        "disposition": phase08_row["disposition"],
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
    }


def promote_archival_record(
    *,
    root: str | Path,
    prior_records: Sequence[Mapping[str, Any]],
    prior_summary_sha256: str,
    phase08_row: Mapping[str, Any],
    config: Phase15Config,
    config_sha256: str,
) -> tuple[VerifiedLedger, Mapping[str, Any]]:
    root_path = Path(root).resolve()
    source_manifest_path = root_path / "data/manifests/phase07_source_manifest.json"
    phase07_summary_path = root_path / "artifacts/phase07/phase07_summary.json"
    phase08_summary_path = root_path / "artifacts/phase08/phase08_summary.json"
    raw = build_archival_evidence_record(
        root=root_path,
        phase08_row=phase08_row,
        phase08_summary_sha256=sha256_file(phase08_summary_path),
        source_manifest_sha256=sha256_file(source_manifest_path),
        phase07_summary_sha256=sha256_file(phase07_summary_path),
        phase15_config_sha256=config_sha256,
    )
    verified = verify_evidence_record(
        raw,
        root=root_path,
        origin_phase="phase15_archival_promotion",
        origin_summary_relative_path="artifacts/phase08/phase08_summary.json",
        origin_summary_sha256=sha256_file(phase08_summary_path),
    )
    _require(verified["object_id"] == config.selected_object_id, "archival target mismatch")
    ledger = merge_cumulative_records(
        prior_records,
        [verified],
        prior_summary_sha256=prior_summary_sha256,
    )
    return ledger, verified
