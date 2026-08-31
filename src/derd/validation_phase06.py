"""Phase-06 validation of phase-convention information loss."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .catalog_harmonics import coefficients_from_amplitude_phase
from .harmonic_screen import screen_harmonics
from .parameters import DERDParameters
from .phase_convention import (
    AmbiguousScreenResult,
    LegacyPhaseSummary,
    ambiguity_bounded_screen,
    legacy_summary_from_complex_coefficients,
)
from .spectral import raw_derd_complex_coefficients


@dataclass(frozen=True, slots=True)
class Phase06Config:
    seed: int = 20260815
    samples_per_class: int = 100
    development_fraction: float = 0.70
    harmonics: int = 8
    fit_harmonics: int = 4
    ambiguity_grid_size: int = 17


@dataclass(frozen=True, slots=True)
class PhaseConventionSyntheticRecord:
    sample_id: str
    label: int
    family: str
    split: str
    epoch_ratio: float
    canonical_full_score: float
    canonical_four_score: float
    unsafe_relative_score: float
    ambiguity_best_score: float
    ambiguity_median_score: float
    ambiguity_worst_score: float
    ambiguity_sequences: int
    legacy_interval_width: float
    legacy_branch_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "label": self.label,
            "family": self.family,
            "split": self.split,
            "epoch_ratio": self.epoch_ratio,
            "canonical_full_score": self.canonical_full_score,
            "canonical_four_score": self.canonical_four_score,
            "unsafe_relative_score": self.unsafe_relative_score,
            "ambiguity_best_score": self.ambiguity_best_score,
            "ambiguity_median_score": self.ambiguity_median_score,
            "ambiguity_worst_score": self.ambiguity_worst_score,
            "ambiguity_sequences": self.ambiguity_sequences,
            "legacy_interval_width": self.legacy_interval_width,
            "legacy_branch_count": self.legacy_branch_count,
        }


def _hash_fraction(label: str) -> float:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big", signed=False)
    return integer / float(2**64)


def _observed_derd_coefficients(
    rng: np.random.Generator,
    *,
    harmonics: int,
) -> tuple[NDArray[np.complex128], float]:
    parameters = DERDParameters(
        float(rng.uniform(0.05, 0.90)),
        float(rng.uniform(0.05, 0.90)),
        float(np.exp(rng.uniform(math.log(0.08), math.log(4.0)))),
        float(rng.random()),
    )
    base = raw_derd_complex_coefficients(
        parameters, maximum_harmonic=harmonics
    )[1:]
    epoch = float(rng.random())
    scale = float(np.exp(rng.uniform(math.log(0.3), math.log(3.0))))
    if bool(rng.integers(0, 2)):
        scale = -scale
    harmonic = np.arange(1, harmonics + 1, dtype=np.float64)
    observed = scale * base * np.exp(1j * 2.0 * math.pi * harmonic * epoch)
    return observed.astype(np.complex128), epoch


def _generic_fourier_coefficients(
    rng: np.random.Generator,
    *,
    harmonics: int,
) -> tuple[NDArray[np.complex128], float]:
    decay = float(rng.uniform(0.20, 0.85))
    amplitude = np.exp(-decay * np.arange(harmonics, dtype=np.float64))
    amplitude *= rng.uniform(0.4, 1.6, size=harmonics)
    phase = np.cumsum(rng.normal(0.0, 1.30, size=harmonics))
    coefficient = amplitude * np.exp(1j * phase)
    epoch = float(rng.random())
    harmonic = np.arange(1, harmonics + 1, dtype=np.float64)
    coefficient *= np.exp(1j * 2.0 * math.pi * harmonic * epoch)
    coefficient *= float(np.exp(rng.uniform(math.log(0.3), math.log(3.0))))
    return coefficient.astype(np.complex128), epoch




def _phase_scrambled_derd_coefficients(
    rng: np.random.Generator,
    *,
    harmonics: int,
) -> tuple[NDArray[np.complex128], float]:
    parameters = DERDParameters(
        float(rng.uniform(0.05, 0.90)),
        float(rng.uniform(0.05, 0.90)),
        float(np.exp(rng.uniform(math.log(0.08), math.log(4.0)))),
        float(rng.random()),
    )
    base = raw_derd_complex_coefficients(
        parameters, maximum_harmonic=harmonics
    )[1:]
    coefficient = np.abs(base) * np.exp(
        1j * rng.uniform(-math.pi, math.pi, size=harmonics)
    )
    epoch = float(rng.random())
    harmonic = np.arange(1, harmonics + 1, dtype=np.float64)
    coefficient *= np.exp(1j * 2.0 * math.pi * harmonic * epoch)
    coefficient *= float(np.exp(rng.uniform(math.log(0.3), math.log(3.0))))
    return coefficient.astype(np.complex128), epoch

def _safe_score(coefficients: NDArray[np.complex128], *, fit_harmonics: int) -> float:
    try:
        return float(
            screen_harmonics(
                coefficients,
                fit_harmonics=fit_harmonics,
                minimum_harmonic_snr=None,
            ).score
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return 1.0e6


def _legacy_unsafe_score(summary: LegacyPhaseSummary, *, fit_harmonics: int) -> float:
    coefficients = coefficients_from_amplitude_phase(
        summary.amplitudes,
        summary.relative_phases,
        convention="sine_relative",
        allow_unsafe_relative=True,
    )
    return _safe_score(coefficients, fit_harmonics=fit_harmonics)


def generate_phase_convention_controls(
    config: Phase06Config | None = None,
) -> list[PhaseConventionSyntheticRecord]:
    active = Phase06Config() if config is None else config
    if active.harmonics < 6:
        raise ValueError("Phase-06 controls require at least six canonical harmonics")
    rng = np.random.default_rng(active.seed)
    rows: list[PhaseConventionSyntheticRecord] = []
    for label in (1, 0):
        for index in range(active.samples_per_class):
            if label == 1:
                family = "geometric_derd"
                coefficients, epoch = _observed_derd_coefficients(
                    rng, harmonics=active.harmonics
                )
            elif index % 2 == 0:
                family = "generic_fourier"
                coefficients, epoch = _generic_fourier_coefficients(
                    rng, harmonics=active.harmonics
                )
            else:
                family = "phase_scrambled_derd_amplitudes"
                coefficients, epoch = _phase_scrambled_derd_coefficients(
                    rng, harmonics=active.harmonics
                )
            sample_id = f"PHASE06:{family}:{index:04d}"
            split = (
                "development"
                if _hash_fraction(sample_id) < active.development_fraction
                else "holdout"
            )
            four = coefficients[:4]
            summary = legacy_summary_from_complex_coefficients(four)
            ambiguity: AmbiguousScreenResult = ambiguity_bounded_screen(
                summary,
                fit_harmonics=4,
                fundamental_phase_grid_size=active.ambiguity_grid_size,
            )
            rows.append(
                PhaseConventionSyntheticRecord(
                    sample_id=sample_id,
                    label=label,
                    family=family,
                    split=split,
                    epoch_ratio=epoch,
                    canonical_full_score=_safe_score(
                        coefficients, fit_harmonics=active.fit_harmonics
                    ),
                    canonical_four_score=_safe_score(
                        four, fit_harmonics=active.fit_harmonics
                    ),
                    unsafe_relative_score=_legacy_unsafe_score(
                        summary, fit_harmonics=active.fit_harmonics
                    ),
                    ambiguity_best_score=ambiguity.best_score,
                    ambiguity_median_score=ambiguity.median_score,
                    ambiguity_worst_score=ambiguity.worst_score,
                    ambiguity_sequences=ambiguity.evaluated_sequences,
                    legacy_interval_width=ambiguity.audit.feasible_fundamental_phase.width,
                    legacy_branch_count=ambiguity.audit.discrete_branch_count_after_global_sign_quotient,
                )
            )
    return rows


def _classification_metrics(
    labels: NDArray[np.int64],
    scores: NDArray[np.float64],
    threshold: float,
) -> dict[str, float | int]:
    finite_scores = np.nan_to_num(scores, nan=1.0e6, posinf=1.0e6, neginf=-1.0e6)
    prediction = finite_scores <= threshold
    positive = labels == 1
    negative = labels == 0
    tp = int(np.count_nonzero(prediction & positive))
    fn = int(np.count_nonzero((~prediction) & positive))
    tn = int(np.count_nonzero((~prediction) & negative))
    fp = int(np.count_nonzero(prediction & negative))
    sensitivity = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    positive_scores = finite_scores[positive]
    negative_scores = finite_scores[negative]
    comparison = positive_scores[:, None] - negative_scores[None, :]
    auc = float(
        (
            np.count_nonzero(comparison < 0.0)
            + 0.5 * np.count_nonzero(comparison == 0.0)
        )
        / max(1, comparison.size)
    )
    return {
        "sample_count": int(labels.size),
        "positive_count": int(np.count_nonzero(positive)),
        "negative_count": int(np.count_nonzero(negative)),
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "balanced_accuracy": float(0.5 * (sensitivity + specificity)),
        "roc_auc": auc,
    }


def calibrate_representation(
    records: Iterable[PhaseConventionSyntheticRecord],
    *,
    score_field: str,
) -> dict[str, object]:
    rows = tuple(records)
    development = [row for row in rows if row.split == "development"]
    holdout = [row for row in rows if row.split == "holdout"]
    if not development or not holdout:
        raise ValueError("both development and holdout records are required")
    development_scores = np.asarray(
        [float(getattr(row, score_field)) for row in development], dtype=np.float64
    )
    development_labels = np.asarray([row.label for row in development], dtype=np.int64)
    finite = np.unique(
        np.nan_to_num(development_scores, nan=1.0e6, posinf=1.0e6, neginf=-1.0e6)
    )
    candidates = np.concatenate(
        (
            [np.nextafter(finite[0], -np.inf)],
            (finite[:-1] + finite[1:]) / 2.0,
            [np.nextafter(finite[-1], np.inf)],
        )
    )
    best_threshold = float(candidates[0])
    best_key = (-math.inf, -math.inf, math.inf)
    for threshold in candidates:
        metrics = _classification_metrics(
            development_labels, development_scores, float(threshold)
        )
        key = (
            float(metrics["balanced_accuracy"]),
            float(metrics["specificity"]),
            -float(threshold),
        )
        if key > best_key:
            best_key = key
            best_threshold = float(threshold)
    holdout_scores = np.asarray(
        [float(getattr(row, score_field)) for row in holdout], dtype=np.float64
    )
    holdout_labels = np.asarray([row.label for row in holdout], dtype=np.int64)
    return {
        "score_field": score_field,
        "threshold": best_threshold,
        "development_metrics": _classification_metrics(
            development_labels, development_scores, best_threshold
        ),
        "holdout_metrics": _classification_metrics(
            holdout_labels, holdout_scores, best_threshold
        ),
    }
