"""Phase-08 multi-family raw-photometry harmonic-forecast cohort.

Phase 08 applies the lossless Phase-07 gate to multiple exposed development
objects from three pulsator families.  It is deliberately a cohort-readiness
and falsification screen, not a physical interpretation of the fitted
parameters and not a prospective confirmatory evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .io import read_ogle_photometry
from .preprocess import clean_light_curve
from .recurrence_uncertainty import DISQUALIFYING_STRUCTURAL_FLAGS
from .validation_phase07 import Phase07Config, Phase07TargetResult, run_phase07_target


@dataclass(frozen=True, slots=True)
class Phase08Target:
    object_id: str
    family: str
    mode: str
    catalog_period_days: float
    period_evidence_grade: str
    source_relative_path: str
    source_repository_path: str
    source_git_blob_sha1: str
    source_sha256: str
    source_byte_count: int
    source_repository: str
    source_commit: str
    period_source: str
    evidence_role: str = "exposed-development-only"

    @property
    def source_locator(self) -> str:
        return (
            f"https://github.com/{self.source_repository}/blob/{self.source_commit}/"
            f"{self.source_repository_path}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        } | {"source_locator": self.source_locator}


@dataclass(frozen=True, slots=True)
class Phase08Config:
    target_config: Phase07Config = Phase07Config(
        synthetic_samples_per_class=96,
        propagation_draws=2048,
        observation_sweep_counts=(),
        observation_sweep_repetitions=1,
        minimum_observations=240,
        period_grid_count=101,
    )
    minimum_objects_per_family_for_population_inference: int = 5
    minimum_total_objects_for_population_inference: int = 15
    require_external_period_evidence_for_claim_evidence: bool = True


@dataclass(frozen=True, slots=True)
class Phase08TargetAssessment:
    target: Phase08Target
    result: Phase07TargetResult
    cleaning: dict[str, Any]
    checks: dict[str, bool]
    stage_reached: str
    disposition: str
    structural_flags: tuple[str, ...]
    approximate_recovery_observations: int | None
    approximate_forecast_observations: int | None
    acquisition_priority_score: float

    def as_dict(self, *, include_controls: bool = False) -> dict[str, Any]:
        return {
            "target": self.target.as_dict(),
            "result": self.result.as_dict(include_controls=include_controls),
            "cleaning": dict(self.cleaning),
            "checks": dict(self.checks),
            "stage_reached": self.stage_reached,
            "disposition": self.disposition,
            "structural_flags": list(self.structural_flags),
            "approximate_recovery_observations": self.approximate_recovery_observations,
            "approximate_forecast_observations": self.approximate_forecast_observations,
            "acquisition_priority_score": self.acquisition_priority_score,
        }


@dataclass(frozen=True, slots=True)
class Phase08CohortAssessment:
    targets: tuple[Phase08TargetAssessment, ...]
    family_summary: tuple[dict[str, Any], ...]
    stage_counts: dict[str, int]
    disposition_counts: dict[str, int]
    population_inference_ready: bool
    c17_promoted: bool
    decision: str

    def as_dict(self, *, include_controls: bool = False) -> dict[str, Any]:
        return {
            "targets": [
                target.as_dict(include_controls=include_controls)
                for target in self.targets
            ],
            "family_summary": list(self.family_summary),
            "stage_counts": dict(self.stage_counts),
            "disposition_counts": dict(self.disposition_counts),
            "population_inference_ready": self.population_inference_ready,
            "c17_promoted": self.c17_promoted,
            "decision": self.decision,
        }


def _seed_offset(object_id: str) -> int:
    return int.from_bytes(hashlib.sha256(object_id.encode("utf-8")).digest()[:4], "big")


def target_specific_config(base: Phase07Config, object_id: str) -> Phase07Config:
    """Return a deterministic independent synthetic/calibration coordinate."""

    offset = _seed_offset(object_id)
    return replace(
        base,
        full_calibration_seed=base.calibration_seed + offset,
        uncertainty_seed=base.draw_seed + offset,
        observation_sweep_seed=base.observation_sweep_seed + offset,
        mvhe_seed=base.mvhe_seed + offset,
    )


def _required_counts(result: Phase07TargetResult, config: Phase07Config) -> tuple[int | None, int | None]:
    rows = result.required_observations
    recovery = [
        row["approximate_required_observations"]
        for row in rows[: config.fit_harmonics]
        if row["approximate_required_observations"] is not None
    ]
    recovery_required = max(recovery) if len(recovery) == config.fit_harmonics else None

    forecast = sorted(
        int(row["approximate_required_observations"])
        for row in rows[config.fit_harmonics :]
        if row["approximate_required_observations"] is not None
    )
    k = config.minimum_forecast_significant_harmonics
    forecast_required = forecast[k - 1] if len(forecast) >= k else None
    return recovery_required, forecast_required


def _priority_score(
    result: Phase07TargetResult,
    *,
    config: Phase07Config,
    structural_flags: tuple[str, ...],
) -> float:
    """Heuristic acquisition score. Higher means closer to an evaluable forecast.

    This score is only an engineering queue coordinate. It is not a probability
    that DERD is true for the object.
    """

    snr = np.asarray(result.harmonic_fit.coefficient_snr, dtype=np.float64)
    recovery = snr[: config.fit_harmonics]
    forecast = np.sort(snr[config.fit_harmonics :])[::-1]
    top_forecast = forecast[: config.minimum_forecast_significant_harmonics]
    recovery_fraction = float(
        np.mean(np.minimum(recovery / config.minimum_recovery_snr, 1.0))
    )
    forecast_fraction = (
        float(np.mean(np.minimum(top_forecast / config.minimum_forecast_snr, 1.0)))
        if top_forecast.size == config.minimum_forecast_significant_harmonics
        else 0.0
    )
    sample_fraction = min(result.observation_count / max(1, config.minimum_observations), 1.0)
    calibration_auc = float(result.calibration.holdout_metrics["roc_auc"])
    calibration_ba = float(result.calibration.holdout_metrics["balanced_accuracy"])
    calibration_fraction = 0.5 * min(calibration_auc / config.minimum_median_auc, 1.0) + 0.5 * min(
        calibration_ba / config.minimum_median_balanced_accuracy, 1.0
    )
    structural_fraction = 1.0 / (1.0 + len(structural_flags))
    threshold_fraction = min(
        result.calibration.threshold / max(result.screen.score, np.finfo(float).eps),
        1.0,
    )
    return float(
        100.0
        * (
            0.10 * sample_fraction
            + 0.25 * recovery_fraction
            + 0.25 * forecast_fraction
            + 0.15 * calibration_fraction
            + 0.15 * structural_fraction
            + 0.10 * threshold_fraction
        )
    )


def assess_target(
    target: Phase08Target,
    *,
    root: str | Path,
    config: Phase08Config | None = None,
) -> Phase08TargetAssessment:
    active = Phase08Config() if config is None else config
    root_path = Path(root)
    source = root_path / target.source_relative_path
    if source.stat().st_size != target.source_byte_count:
        raise ValueError(f"source byte-count mismatch for {target.object_id}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != target.source_sha256:
        raise ValueError(f"source SHA-256 mismatch for {target.object_id}")

    curve = read_ogle_photometry(source, star_id=target.object_id, band="I")
    cleaned, cleaning_report = clean_light_curve(curve)
    target_config = target_specific_config(active.target_config, target.object_id)
    result = run_phase07_target(
        source_path=source,
        object_id=target.object_id,
        mode=target.mode,
        catalog_period=target.catalog_period_days,
        expected_git_blob_sha1=target.source_git_blob_sha1,
        source_locator=target.source_locator,
        config=target_config,
    )

    snr = np.asarray(result.harmonic_fit.coefficient_snr, dtype=np.float64)
    recovery_count = int(
        np.count_nonzero(snr[: target_config.fit_harmonics] >= target_config.minimum_recovery_snr)
    )
    forecast_count = int(
        np.count_nonzero(snr[target_config.fit_harmonics :] >= target_config.minimum_forecast_snr)
    )
    structural_flags = tuple(
        sorted(set(result.screen.flags).intersection(DISQUALIFYING_STRUCTURAL_FLAGS))
    )
    period_grade_pass = (
        not active.require_external_period_evidence_for_claim_evidence
        or target.period_evidence_grade.startswith("EXTERNAL_CATALOG")
    )
    below = result.propagation.below_threshold_fraction
    checks = {
        "source_bytes_verified": True,
        "minimum_observation_count": result.observation_count >= target_config.minimum_observations,
        "phase_coverage": int(result.harmonic_fit.phase_coverage["occupied_bins"]) >= 10,
        "design_conditioning": result.harmonic_fit.design_condition_number <= target_config.maximum_design_condition_number,
        "period_evidence_grade": period_grade_pass,
        "four_recovery_harmonics_snr": recovery_count >= target_config.fit_harmonics,
        "two_forecast_harmonics_snr": forecast_count >= target_config.minimum_forecast_significant_harmonics,
        "structural_constraints": not structural_flags,
        "score_below_target_threshold": result.screen.score <= result.calibration.threshold,
        "uncertainty_structural_stability": result.propagation.structural_pass_fraction >= 0.80,
        "uncertainty_threshold_stability": below is not None and below >= 0.80,
        "cadence_calibration_auc": float(result.calibration.holdout_metrics["roc_auc"]) >= 0.80,
        "cadence_calibration_balanced_accuracy": float(result.calibration.holdout_metrics["balanced_accuracy"]) >= 0.75,
    }

    if not all(checks[key] for key in (
        "source_bytes_verified", "minimum_observation_count", "phase_coverage", "design_conditioning"
    )):
        stage = "SOURCE_OR_SAMPLING"
        disposition = "ABSTAIN_SOURCE_OR_SAMPLING_NOT_READY"
    elif not checks["period_evidence_grade"]:
        stage = "PERIOD_PROVENANCE"
        disposition = "ENGINEERING_ONLY_PERIOD_NOT_CLAIM_GRADE"
    elif not checks["four_recovery_harmonics_snr"]:
        stage = "RECOVERY_HARMONICS"
        disposition = "ABSTAIN_INSUFFICIENT_RECOVERY_HARMONIC_SIGNAL"
    elif not checks["two_forecast_harmonics_snr"]:
        stage = "FORECAST_HARMONICS"
        disposition = "ABSTAIN_INSUFFICIENT_MEASURED_FORECAST_HARMONICS"
    elif not checks["structural_constraints"] or not checks["score_below_target_threshold"]:
        stage = "DERD_COMPATIBILITY"
        disposition = "REJECT_DERD_HARMONIC_COMPATIBILITY"
    elif not all(checks[key] for key in (
        "uncertainty_structural_stability", "uncertainty_threshold_stability",
        "cadence_calibration_auc", "cadence_calibration_balanced_accuracy"
    )):
        stage = "CALIBRATION_AND_STABILITY"
        disposition = "ABSTAIN_CALIBRATION_OR_COVARIANCE_UNSTABLE"
    else:
        stage = "QUALIFIED_DEVELOPMENT_FORECAST"
        disposition = "QUALIFIES_AS_DEVELOPMENT_HARMONIC_FORECAST"

    recovery_required, forecast_required = _required_counts(result, target_config)
    return Phase08TargetAssessment(
        target=target,
        result=result,
        cleaning=cleaning_report.as_dict(),
        checks=checks,
        stage_reached=stage,
        disposition=disposition,
        structural_flags=structural_flags,
        approximate_recovery_observations=recovery_required,
        approximate_forecast_observations=forecast_required,
        acquisition_priority_score=_priority_score(
            result, config=target_config, structural_flags=structural_flags
        ),
    )


def assess_cohort(
    targets: Iterable[Phase08Target],
    *,
    root: str | Path,
    config: Phase08Config | None = None,
) -> Phase08CohortAssessment:
    active = Phase08Config() if config is None else config
    assessments = tuple(assess_target(target, root=root, config=active) for target in targets)
    families = sorted({item.target.family for item in assessments})
    family_summary: list[dict[str, Any]] = []
    for family in families:
        subset = [item for item in assessments if item.target.family == family]
        family_summary.append({
            "family": family,
            "object_count": len(subset),
            "claim_grade_period_count": sum(item.checks["period_evidence_grade"] for item in subset),
            "recovery_ready_count": sum(item.checks["four_recovery_harmonics_snr"] for item in subset),
            "forecast_measured_count": sum(item.checks["two_forecast_harmonics_snr"] for item in subset),
            "structurally_compatible_count": sum(item.checks["structural_constraints"] for item in subset),
            "qualified_count": sum(item.disposition == "QUALIFIES_AS_DEVELOPMENT_HARMONIC_FORECAST" for item in subset),
            "median_screen_score": float(np.median([item.result.screen.score for item in subset])),
            "median_cadence_auc": float(np.median([
                float(item.result.calibration.holdout_metrics["roc_auc"]) for item in subset
            ])),
        })

    stage_counts: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    for item in assessments:
        stage_counts[item.stage_reached] = stage_counts.get(item.stage_reached, 0) + 1
        dispositions[item.disposition] = dispositions.get(item.disposition, 0) + 1

    family_counts = {row["family"]: row["object_count"] for row in family_summary}
    population_ready = bool(
        len(assessments) >= active.minimum_total_objects_for_population_inference
        and all(
            count >= active.minimum_objects_per_family_for_population_inference
            for count in family_counts.values()
        )
        and len(family_counts) >= 3
    )
    return Phase08CohortAssessment(
        targets=assessments,
        family_summary=tuple(family_summary),
        stage_counts=stage_counts,
        disposition_counts=dispositions,
        population_inference_ready=population_ready,
        c17_promoted=False,
        decision=(
            "DEVELOPMENT_COHORT_SCREEN_COMPLETE_POPULATION_INFERENCE_NOT_READY_C17_NOT_PROMOTED"
            if not population_ready
            else "DEVELOPMENT_COHORT_SCREEN_COMPLETE_C17_REMAINS_UNPROMOTED"
        ),
    )
