"""Phase-13 temporal replication audit and cumulative-ledger extension.

Phase 12 established a cumulative target-level evidence ledger.  Phase 13 adds
an orthogonal temporal replication tier: a new source is selected from a frozen
pre-existing acquisition ranking, its Phase-08 scientific result is replayed,
and its signed harmonic coefficients are compared across chronological blocks.

The temporal audit is deliberately separate from the population denominator.
A stable or unstable waveform coefficient record does not identify a unique
internal stellar mechanism, a transparent shell, or a shell mass.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import chi2

from .harmonic_evidence import SignedHarmonicFit, fit_signed_harmonics, phase_coverage
from .io import read_ogle_photometry
from .lightcurve import LightCurve, ValueDomain
from .ogle_catalog import canonical_json_sha256
from .preprocess import clean_light_curve, fold_phase
from .validation_phase12 import (
    VerifiedLedger,
    merge_cumulative_records,
    sha256_file,
    verify_evidence_record,
)


PHASE13_DECISION_UPDATED = (
    "PHASE13_TEMPORAL_REPLICATION_LEDGER_UPDATED_POPULATION_GATE_CLOSED"
)
PHASE13_DECISION_BLOCKED = "PHASE13_NO_NEW_ACQUISITION_TARGET_READY"
PHASE13_DECISION_DRIFT = "PHASE13_SCIENTIFIC_REPLAY_DRIFT_DETECTED"
PHASE13_TEMPORAL_SUPPORTED = "TEMPORAL_REPLICATION_SUPPORTED_FOR_WAVEFORM_COEFFICIENTS"
PHASE13_TEMPORAL_NOT_SUPPORTED = "TEMPORAL_REPLICATION_NOT_SUPPORTED"
PHASE13_TEMPORAL_INSUFFICIENT = "TEMPORAL_REPLICATION_INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class Phase13Config:
    """Frozen coordinates for one-target temporal replication analysis."""

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
    random_seed: int = 2026081813

    def phase12_dict(self) -> dict[str, Any]:
        return {
            "synthetic_samples_per_class": self.synthetic_samples_per_class,
            "propagation_draws": self.propagation_draws,
            "period_grid_count": self.period_grid_count,
            "minimum_observations": self.minimum_observations,
            "fast": self.fast,
            "require_scientific_replay_match": self.require_scientific_replay_match,
        }

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
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionCandidate:
    object_id: str
    family: str
    mode: str
    priority: float
    source_repository_path: str
    source_git_blob_sha1: str
    source_sha256: str
    period_days: float
    period_evidence_grade: str
    rank: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "family": self.family,
            "mode": self.mode,
            "priority": self.priority,
            "source_repository_path": self.source_repository_path,
            "source_git_blob_sha1": self.source_git_blob_sha1,
            "source_sha256": self.source_sha256,
            "period_days": self.period_days,
            "period_evidence_grade": self.period_evidence_grade,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class TemporalBlockFit:
    block_index: int
    start_time: float
    end_time: float
    observation_count: int
    occupied_phase_bins: int
    maximum_circular_phase_gap: float
    design_condition_number: float
    coefficient_snr: tuple[float, ...]
    sine_coefficients: tuple[float, ...]
    cosine_coefficients: tuple[float, ...]
    recovery_snr_pass: bool
    block_quality_pass: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "block_index": self.block_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "observation_count": self.observation_count,
            "occupied_phase_bins": self.occupied_phase_bins,
            "maximum_circular_phase_gap": self.maximum_circular_phase_gap,
            "design_condition_number": self.design_condition_number,
            "coefficient_snr": list(self.coefficient_snr),
            "sine_coefficients": list(self.sine_coefficients),
            "cosine_coefficients": list(self.cosine_coefficients),
            "recovery_snr_pass": self.recovery_snr_pass,
            "block_quality_pass": self.block_quality_pass,
        }


@dataclass(frozen=True, slots=True)
class PairwiseTemporalTest:
    block_a: int
    block_b: int
    wald_statistic: float
    effective_rank: int
    normalized_score: float
    p_value: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "block_a": self.block_a,
            "block_b": self.block_b,
            "wald_statistic": self.wald_statistic,
            "effective_rank": self.effective_rank,
            "normalized_score": self.normalized_score,
            "p_value": self.p_value,
        }


@dataclass(frozen=True, slots=True)
class DriftCalibrationRow:
    severity: float
    threshold: float
    development_stationary_count: int
    holdout_stationary_count: int
    holdout_drift_count: int
    roc_auc: float
    balanced_accuracy: float
    sensitivity: float
    specificity: float
    power_gate_pass: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "threshold": self.threshold,
            "development_stationary_count": self.development_stationary_count,
            "holdout_stationary_count": self.holdout_stationary_count,
            "holdout_drift_count": self.holdout_drift_count,
            "roc_auc": self.roc_auc,
            "balanced_accuracy": self.balanced_accuracy,
            "sensitivity": self.sensitivity,
            "specificity": self.specificity,
            "power_gate_pass": self.power_gate_pass,
        }


@dataclass(frozen=True, slots=True)
class TemporalReplicationAudit:
    object_id: str
    period_days: float
    reference_epoch: float
    observation_count: int
    blocks: tuple[TemporalBlockFit, ...]
    pairwise_tests: tuple[PairwiseTemporalTest, ...]
    actual_temporal_score: float
    stationary_threshold: float
    actual_below_stationary_threshold: bool
    all_blocks_quality_pass: bool
    all_blocks_recovery_snr_pass: bool
    calibration_rows: tuple[DriftCalibrationRow, ...]
    first_sustained_detectable_severity: float | None
    calibration_power_pass: bool
    disposition: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "object_id": self.object_id,
            "period_days": self.period_days,
            "reference_epoch": self.reference_epoch,
            "observation_count": self.observation_count,
            "blocks": [row.as_dict() for row in self.blocks],
            "pairwise_tests": [row.as_dict() for row in self.pairwise_tests],
            "actual_temporal_score": self.actual_temporal_score,
            "stationary_threshold": self.stationary_threshold,
            "actual_below_stationary_threshold": self.actual_below_stationary_threshold,
            "all_blocks_quality_pass": self.all_blocks_quality_pass,
            "all_blocks_recovery_snr_pass": self.all_blocks_recovery_snr_pass,
            "calibration_rows": [row.as_dict() for row in self.calibration_rows],
            "first_sustained_detectable_severity": self.first_sustained_detectable_severity,
            "calibration_power_pass": self.calibration_power_pass,
            "disposition": self.disposition,
            "blockers": list(self.blockers),
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
            "claim_scope": "temporal stability of signed waveform harmonics only",
        }
        payload["sha256_canonical_json"] = canonical_json_sha256(payload)
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _hash_fraction(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) / float(2**64)


def load_verified_phase12_ledger(
    *,
    root: str | Path,
    summary_path: str | Path = "artifacts/phase12/phase12_summary.json",
) -> tuple[tuple[Mapping[str, Any], ...], str, str]:
    """Verify the Phase-12 summary, ledger seal, record hashes and exchanges."""

    root_path = Path(root).resolve()
    candidate = Path(summary_path)
    summary_file = candidate if candidate.is_absolute() else root_path / candidate
    _require(summary_file.is_file(), f"Phase-12 summary missing: {summary_file}")
    summary_sha = sha256_file(summary_file)
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    _require(
        summary.get("implementation_id") == "DERD-v1.2-phase12-cumulative-replay-ledger",
        "unexpected Phase-12 implementation identifier",
    )
    _require(bool(summary.get("protocol", {}).get("valid")), "Phase-12 protocol invalid")
    ledger_meta = summary.get("cumulative_ledger")
    _require(isinstance(ledger_meta, Mapping), "Phase-12 ledger metadata missing")
    ledger_path = root_path / str(ledger_meta.get("relative_path", ""))
    seal_path = root_path / str(ledger_meta.get("seal_relative_path", ""))
    _require(ledger_path.is_file(), "Phase-12 ledger file missing")
    _require(seal_path.is_file(), "Phase-12 ledger seal missing")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    ledger_digest = canonical_json_sha256(ledger)
    _require(ledger_digest == seal.get("sha256_canonical_json"), "Phase-12 ledger seal mismatch")
    _require(ledger_digest == ledger_meta.get("seal_sha256_canonical_json"), "summary ledger digest mismatch")
    rows = ledger.get("records")
    _require(isinstance(rows, list), "Phase-12 ledger records malformed")
    _require(len(rows) == int(seal.get("record_count", -1)), "Phase-12 record count mismatch")
    _require(len(rows) == int(ledger.get("cumulative_count", -1)), "Phase-12 cumulative count mismatch")

    verified: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    provenance_fields = {
        "origin_phase",
        "origin_summary_relative_path",
        "origin_summary_sha256",
        "ledger_record_sha256",
    }
    for row in rows:
        _require(isinstance(row, Mapping), "Phase-12 ledger record is not an object")
        base = {key: value for key, value in row.items() if key not in provenance_fields}
        _require(
            canonical_json_sha256(base) == row.get("ledger_record_sha256"),
            f"Phase-12 record digest mismatch: {row.get('object_id')}",
        )
        origin_relative = str(row.get("origin_summary_relative_path", ""))
        origin_path = root_path / origin_relative
        _require(origin_path.is_file(), f"record origin summary missing: {row.get('object_id')}")
        _require(
            sha256_file(origin_path) == row.get("origin_summary_sha256"),
            f"record origin summary digest mismatch: {row.get('object_id')}",
        )
        checked = verify_evidence_record(
            base,
            root=root_path,
            origin_phase=str(row.get("origin_phase")),
            origin_summary_relative_path=origin_relative,
            origin_summary_sha256=str(row.get("origin_summary_sha256")),
        )
        _require(checked == dict(row), f"Phase-12 record provenance mismatch: {row.get('object_id')}")
        object_id = str(row["object_id"])
        _require(object_id not in seen, f"duplicate Phase-12 object: {object_id}")
        seen.add(object_id)
        verified.append(dict(row))
    verified.sort(key=lambda item: str(item["object_id"]))
    return tuple(verified), summary_sha, ledger_digest


def acquisition_candidates_from_phase08(
    *,
    root: str | Path,
    excluded_object_ids: Iterable[str],
    summary_path: str | Path = "artifacts/phase08/phase08_summary.json",
) -> tuple[AcquisitionCandidate, ...]:
    """Rank claim-grade exposed targets using only frozen Phase-08 evidence."""

    root_path = Path(root).resolve()
    source = Path(summary_path)
    summary_file = source if source.is_absolute() else root_path / source
    payload = json.loads(summary_file.read_text(encoding="utf-8"))
    _require(
        payload.get("implementation_id") == "DERD-v0.8-phase08-multifamily-harmonic-forecast-cohort",
        "unexpected Phase-08 implementation identifier",
    )
    excluded = set(excluded_object_ids)
    raw: list[dict[str, Any]] = []
    for row in payload.get("cohort", {}).get("targets", []):
        target = row.get("target", {})
        object_id = str(target.get("object_id", ""))
        grade = str(target.get("period_evidence_grade", ""))
        source_sha = str(target.get("source_sha256", ""))
        if not object_id or object_id in excluded:
            continue
        if not grade.startswith("EXTERNAL_CATALOG"):
            continue
        if len(source_sha) != 64:
            continue
        raw.append(
            {
                "object_id": object_id,
                "family": str(target.get("family", "")),
                "mode": str(target.get("mode", "")),
                "priority": float(row.get("acquisition_priority_score", 0.0)),
                "source_repository_path": str(target.get("source_repository_path", "")),
                "source_git_blob_sha1": str(target.get("source_git_blob_sha1", "")),
                "source_sha256": source_sha,
                "period_days": float(target.get("catalog_period_days")),
                "period_evidence_grade": grade,
            }
        )
    raw.sort(key=lambda item: (-item["priority"], item["object_id"]))
    return tuple(
        AcquisitionCandidate(rank=index + 1, **item)
        for index, item in enumerate(raw)
    )


def _coefficient_vector_and_covariance(
    fit: SignedHarmonicFit,
    *,
    harmonics: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    order = fit.order
    if not 1 <= harmonics <= order:
        raise ValueError("harmonics must lie within fitted order")
    indices = np.asarray(
        [*range(harmonics), *range(order, order + harmonics)], dtype=np.int64
    )
    vector = np.concatenate(
        (fit.sine_coefficients[:harmonics], fit.cosine_coefficients[:harmonics])
    )
    covariance = fit.coefficient_covariance[np.ix_(indices, indices)]
    return np.asarray(vector, dtype=np.float64), np.asarray(covariance, dtype=np.float64)


def pairwise_temporal_test(
    fit_a: SignedHarmonicFit,
    fit_b: SignedHarmonicFit,
    *,
    block_a: int,
    block_b: int,
    harmonics: int,
) -> PairwiseTemporalTest:
    vector_a, covariance_a = _coefficient_vector_and_covariance(fit_a, harmonics=harmonics)
    vector_b, covariance_b = _coefficient_vector_and_covariance(fit_b, harmonics=harmonics)
    difference = vector_a - vector_b
    covariance = 0.5 * (covariance_a + covariance_a.T) + 0.5 * (
        covariance_b + covariance_b.T
    )
    rank = int(np.linalg.matrix_rank(covariance))
    _require(rank > 0, "temporal covariance has zero rank")
    inverse = np.linalg.pinv(covariance, hermitian=True)
    statistic = float(difference @ inverse @ difference)
    normalized = statistic / rank
    return PairwiseTemporalTest(
        block_a=block_a,
        block_b=block_b,
        wald_statistic=statistic,
        effective_rank=rank,
        normalized_score=normalized,
        p_value=float(chi2.sf(statistic, rank)),
    )


def _fit_temporal_blocks(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    errors: NDArray[np.float64],
    *,
    period: float,
    reference_epoch: float,
    config: Phase13Config,
) -> tuple[tuple[SignedHarmonicFit, ...], tuple[TemporalBlockFit, ...], tuple[PairwiseTemporalTest, ...], float]:
    indices = np.array_split(np.arange(time.size, dtype=np.int64), config.temporal_blocks)
    fits: list[SignedHarmonicFit] = []
    rows: list[TemporalBlockFit] = []
    for block_index, selection in enumerate(indices):
        _require(selection.size > 0, "empty temporal block")
        fit = fit_signed_harmonics(
            time[selection],
            values[selection],
            errors[selection],
            period=period,
            reference_epoch=reference_epoch,
            order=config.harmonic_order,
            ridge=config.harmonic_ridge,
            coverage_bins=config.phase_bins,
            inflate_covariance=True,
        )
        coverage = dict(fit.phase_coverage)
        snr = tuple(float(value) for value in fit.coefficient_snr)
        quality = bool(
            selection.size >= config.minimum_block_observations
            and int(coverage["occupied_bins"]) >= config.minimum_occupied_phase_bins
            and fit.design_condition_number <= config.maximum_design_condition_number
        )
        recovery = bool(
            len(snr) >= config.temporal_fit_harmonics
            and all(
                value >= config.minimum_recovery_snr
                for value in snr[: config.temporal_fit_harmonics]
            )
        )
        fits.append(fit)
        rows.append(
            TemporalBlockFit(
                block_index=block_index,
                start_time=float(time[selection[0]]),
                end_time=float(time[selection[-1]]),
                observation_count=int(selection.size),
                occupied_phase_bins=int(coverage["occupied_bins"]),
                maximum_circular_phase_gap=float(coverage["maximum_circular_gap"]),
                design_condition_number=float(fit.design_condition_number),
                coefficient_snr=snr,
                sine_coefficients=tuple(float(value) for value in fit.sine_coefficients),
                cosine_coefficients=tuple(float(value) for value in fit.cosine_coefficients),
                recovery_snr_pass=recovery,
                block_quality_pass=quality,
            )
        )
    comparisons = tuple(
        pairwise_temporal_test(
            fits[i],
            fits[j],
            block_a=i,
            block_b=j,
            harmonics=config.temporal_fit_harmonics,
        )
        for i in range(len(fits))
        for j in range(i + 1, len(fits))
    )
    score = max(row.normalized_score for row in comparisons)
    return tuple(fits), tuple(rows), comparisons, float(score)


def _predict_harmonic_fit(
    fit: SignedHarmonicFit,
    time: NDArray[np.float64],
    *,
    period: float,
    reference_epoch: float,
) -> NDArray[np.float64]:
    phase = fold_phase(time, period, epoch=reference_epoch)
    theta = 2.0 * math.pi * phase
    prediction = np.full(time.size, fit.intercept, dtype=np.float64)
    for index in range(fit.order):
        harmonic = index + 1
        prediction += fit.sine_coefficients[index] * np.sin(harmonic * theta)
        prediction += fit.cosine_coefficients[index] * np.cos(harmonic * theta)
    return prediction


def _drifted_prediction(
    fit: SignedHarmonicFit,
    time: NDArray[np.float64],
    *,
    period: float,
    reference_epoch: float,
    severity: float,
    last_block_indices: NDArray[np.int64],
) -> NDArray[np.float64]:
    prediction = _predict_harmonic_fit(
        fit, time, period=period, reference_epoch=reference_epoch
    )
    phase = fold_phase(time[last_block_indices], period, epoch=reference_epoch)
    theta = 2.0 * math.pi * phase
    # One active drift severity controls a frozen h2-h4 deformation family.
    transformations = {
        2: (1.0 + 0.20 * severity, +0.10 * severity),
        3: (1.0 + 0.50 * severity, -0.15 * severity),
        4: (max(0.10, 1.0 - 0.40 * severity), +0.20 * severity),
    }
    delta = np.zeros(last_block_indices.size, dtype=np.float64)
    for harmonic, (scale, phase_cycles) in transformations.items():
        index = harmonic - 1
        old_complex = 0.5 * (
            fit.cosine_coefficients[index] - 1j * fit.sine_coefficients[index]
        )
        new_complex = old_complex * scale * np.exp(1j * 2.0 * math.pi * phase_cycles)
        old_component = 2.0 * np.real(old_complex * np.exp(1j * harmonic * theta))
        new_component = 2.0 * np.real(new_complex * np.exp(1j * harmonic * theta))
        delta += new_component - old_component
    prediction[last_block_indices] += delta
    return prediction


def _drift_metrics(
    stationary: NDArray[np.float64],
    drift: NDArray[np.float64],
    *,
    threshold: float,
) -> dict[str, float | int]:
    stationary = np.asarray(stationary, dtype=np.float64)
    drift = np.asarray(drift, dtype=np.float64)
    tn = int(np.count_nonzero(stationary <= threshold))
    fp = int(stationary.size - tn)
    tp = int(np.count_nonzero(drift > threshold))
    fn = int(drift.size - tp)
    sensitivity = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    balanced = 0.5 * (sensitivity + specificity)
    comparisons = drift[:, None] - stationary[None, :]
    auc = float(
        (
            np.count_nonzero(comparisons > 0.0)
            + 0.5 * np.count_nonzero(comparisons == 0.0)
        )
        / max(1, comparisons.size)
    )
    return {
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "balanced_accuracy": float(balanced),
        "roc_auc": auc,
    }


def _score_simulation(
    *,
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    errors: NDArray[np.float64],
    period: float,
    reference_epoch: float,
    config: Phase13Config,
) -> float:
    try:
        _, _, _, score = _fit_temporal_blocks(
            time,
            values,
            errors,
            period=period,
            reference_epoch=reference_epoch,
            config=config,
        )
    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
        return float("inf")
    return float(score)


def run_temporal_replication_audit(
    curve: LightCurve,
    *,
    period: float,
    reference_epoch: float | None = None,
    config: Phase13Config | None = None,
) -> TemporalReplicationAudit:
    """Audit chronological stability under actual cadence and quoted errors."""

    active = Phase13Config() if config is None else config
    cleaned, _ = clean_light_curve(curve, maximum_error_factor=5.0)
    flux = cleaned.to_relative_flux() if cleaned.domain is ValueDomain.MAGNITUDE else cleaned
    time = np.asarray(flux.time, dtype=np.float64)
    values = np.asarray(flux.value, dtype=np.float64)
    errors = np.asarray(flux.error, dtype=np.float64)
    epoch = float(np.min(time)) if reference_epoch is None else float(reference_epoch)
    full_fit = fit_signed_harmonics(
        time,
        values,
        errors,
        period=period,
        reference_epoch=epoch,
        order=active.harmonic_order,
        ridge=active.harmonic_ridge,
        coverage_bins=active.phase_bins,
        inflate_covariance=True,
    )
    _, blocks, comparisons, actual_score = _fit_temporal_blocks(
        time,
        values,
        errors,
        period=period,
        reference_epoch=epoch,
        config=active,
    )

    baseline = _predict_harmonic_fit(
        full_fit, time, period=period, reference_epoch=epoch
    )
    residual = values - baseline
    temporal_indices = np.array_split(np.arange(time.size, dtype=np.int64), active.temporal_blocks)
    last_block = temporal_indices[-1]
    rng = np.random.default_rng(active.random_seed)

    stationary_records: list[tuple[str, float, str]] = []
    for index in range(active.stationary_replicates):
        sign = rng.choice(np.asarray([-1.0, 1.0]), size=time.size)
        synthetic = baseline + residual * sign
        score = _score_simulation(
            time=time,
            values=synthetic,
            errors=errors,
            period=period,
            reference_epoch=epoch,
            config=active,
        )
        label = f"stationary:{curve.star_id}:{index}:{active.random_seed}"
        split = "development" if _hash_fraction(label) < active.development_fraction else "holdout"
        stationary_records.append((label, score, split))

    development_stationary = np.asarray(
        [score for _, score, split in stationary_records if split == "development"],
        dtype=np.float64,
    )
    holdout_stationary = np.asarray(
        [score for _, score, split in stationary_records if split == "holdout"],
        dtype=np.float64,
    )
    finite_development = development_stationary[np.isfinite(development_stationary)]
    _require(finite_development.size >= 20, "too few finite stationary development replicates")
    threshold = float(
        np.quantile(finite_development, active.stationary_quantile, method="higher")
    )

    rows: list[DriftCalibrationRow] = []
    for severity_index, severity in enumerate(active.drift_severities):
        drifted_baseline = _drifted_prediction(
            full_fit,
            time,
            period=period,
            reference_epoch=epoch,
            severity=severity,
            last_block_indices=last_block,
        )
        drift_scores: list[float] = []
        for index in range(active.drift_replicates):
            sign = rng.choice(np.asarray([-1.0, 1.0]), size=time.size)
            synthetic = drifted_baseline + residual * sign
            label = (
                f"drift:{curve.star_id}:{severity_index}:{index}:{active.random_seed}"
            )
            if _hash_fraction(label) < active.development_fraction:
                # Development drift simulations are intentionally unused.  The
                # stationary-only threshold remains invariant to the alternative.
                continue
            drift_scores.append(
                _score_simulation(
                    time=time,
                    values=synthetic,
                    errors=errors,
                    period=period,
                    reference_epoch=epoch,
                    config=active,
                )
            )
        drift_array = np.asarray(drift_scores, dtype=np.float64)
        finite_stationary = holdout_stationary[np.isfinite(holdout_stationary)]
        finite_drift = drift_array[np.isfinite(drift_array)]
        _require(finite_stationary.size >= 10, "too few finite stationary holdout replicates")
        _require(finite_drift.size >= 10, "too few finite drift holdout replicates")
        metrics = _drift_metrics(finite_stationary, finite_drift, threshold=threshold)
        power = bool(
            metrics["roc_auc"] >= active.minimum_drift_auc
            and metrics["balanced_accuracy"] >= active.minimum_drift_balanced_accuracy
        )
        rows.append(
            DriftCalibrationRow(
                severity=float(severity),
                threshold=threshold,
                development_stationary_count=int(finite_development.size),
                holdout_stationary_count=int(finite_stationary.size),
                holdout_drift_count=int(finite_drift.size),
                roc_auc=float(metrics["roc_auc"]),
                balanced_accuracy=float(metrics["balanced_accuracy"]),
                sensitivity=float(metrics["sensitivity"]),
                specificity=float(metrics["specificity"]),
                power_gate_pass=power,
            )
        )

    first_sustained: float | None = None
    for index, row in enumerate(rows):
        if row.power_gate_pass and all(later.power_gate_pass for later in rows[index:]):
            first_sustained = row.severity
            break
    calibration_power = first_sustained is not None
    quality_pass = all(row.block_quality_pass for row in blocks)
    recovery_pass = all(row.recovery_snr_pass for row in blocks)
    stationary_pass = bool(actual_score <= threshold)
    blockers: list[str] = []
    if not quality_pass:
        blockers.append("temporal_block_quality")
    if not recovery_pass:
        blockers.append("four_recovery_harmonics_in_every_block")
    if not calibration_power:
        blockers.append("actual_cadence_drift_calibration_power")
    if not stationary_pass:
        blockers.append("temporal_coefficient_stationarity")
    if quality_pass and recovery_pass and calibration_power and stationary_pass:
        disposition = PHASE13_TEMPORAL_SUPPORTED
    elif quality_pass and calibration_power:
        disposition = PHASE13_TEMPORAL_NOT_SUPPORTED
    else:
        disposition = PHASE13_TEMPORAL_INSUFFICIENT

    return TemporalReplicationAudit(
        object_id=curve.star_id,
        period_days=float(period),
        reference_epoch=epoch,
        observation_count=int(time.size),
        blocks=blocks,
        pairwise_tests=comparisons,
        actual_temporal_score=actual_score,
        stationary_threshold=threshold,
        actual_below_stationary_threshold=stationary_pass,
        all_blocks_quality_pass=quality_pass,
        all_blocks_recovery_snr_pass=recovery_pass,
        calibration_rows=tuple(rows),
        first_sustained_detectable_severity=first_sustained,
        calibration_power_pass=calibration_power,
        disposition=disposition,
        blockers=tuple(blockers),
    )


def load_curve_for_temporal_audit(
    *,
    root: str | Path,
    source_relative_path: str,
    object_id: str,
    source_locator: str,
) -> LightCurve:
    root_path = Path(root).resolve()
    source = root_path / source_relative_path
    _require(source.is_file(), f"temporal-audit source missing: {object_id}")
    return read_ogle_photometry(
        source,
        star_id=object_id,
        band="I",
        metadata={
            "source_locator": source_locator,
            "physical_claim_scope": "waveform-only",
        },
    )


def temporal_audit_sidecar(
    audit: TemporalReplicationAudit,
    *,
    ledger_record: Mapping[str, Any],
    configuration_sha256: str,
    source_receipt_sha256: str | None,
) -> dict[str, Any]:
    payload = {
        "sidecar_id": "DERD-PHASE13-TEMPORAL-REPLICATION-SIDECAR-1.0",
        "object_id": audit.object_id,
        "ledger_record_sha256": ledger_record["ledger_record_sha256"],
        "input_lock_sha256": ledger_record["input_lock_sha256"],
        "result_sha256": ledger_record["result_sha256"],
        "exchange_sha256": ledger_record["exchange_sha256"],
        "phase13_configuration_sha256": configuration_sha256,
        "source_receipt_sha256": source_receipt_sha256,
        "audit": audit.as_dict(),
        "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        "claim_boundary": "temporal stability of normalized waveform coefficients only",
    }
    payload["sha256_canonical_json"] = canonical_json_sha256(payload)
    return payload


def merge_phase13_ledger(
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
