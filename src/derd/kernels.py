"""Periodic kernel-ridge baseline with training-only model selection."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .cross_validation import circular_phase_folds
from .metrics import metric_bundle, weighted_rmse


@dataclass(frozen=True, slots=True)
class PeriodicKernelFit:
    length_scale: float
    ridge: float
    train_phase: NDArray[np.float64]
    coefficients: NDArray[np.float64]
    condition_number: float
    effective_parameters: float
    dense_prediction_span: float
    training_metrics: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "length_scale": self.length_scale,
            "ridge": self.ridge,
            "condition_number": self.condition_number,
            "effective_parameters": self.effective_parameters,
            "dense_prediction_span": self.dense_prediction_span,
            "training_metrics": self.training_metrics,
        }


@dataclass(frozen=True, slots=True)
class PeriodicKernelCandidate:
    length_scale: float
    ridge: float
    cross_validated_weighted_rmse: float
    condition_number: float
    effective_parameters: float
    dense_prediction_span: float
    eligible: bool
    rejection_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "length_scale": self.length_scale,
            "ridge": self.ridge,
            "cross_validated_weighted_rmse": self.cross_validated_weighted_rmse,
            "condition_number": self.condition_number,
            "effective_parameters": self.effective_parameters,
            "dense_prediction_span": self.dense_prediction_span,
            "eligible": self.eligible,
            "rejection_reasons": list(self.rejection_reasons),
        }


@dataclass(frozen=True, slots=True)
class PeriodicKernelSelection:
    fit: PeriodicKernelFit
    selected_length_scale: float
    selected_ridge: float
    cross_validated_weighted_rmse: float
    candidates: tuple[PeriodicKernelCandidate, ...]
    eligible_count: int
    fallback_used: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_length_scale": self.selected_length_scale,
            "selected_ridge": self.selected_ridge,
            "cross_validated_weighted_rmse": self.cross_validated_weighted_rmse,
            "eligible_count": self.eligible_count,
            "fallback_used": self.fallback_used,
            "fit": self.fit.as_dict(),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


def periodic_squared_exponential_kernel(
    phase_a: ArrayLike,
    phase_b: ArrayLike,
    *,
    length_scale: float,
) -> NDArray[np.float64]:
    """Return a unit-amplitude periodic squared-exponential kernel matrix."""

    if not np.isfinite(length_scale) or length_scale <= 0.0:
        raise ValueError("length_scale must be finite and positive")
    a = np.asarray(phase_a, dtype=np.float64).reshape(-1)
    b = np.asarray(phase_b, dtype=np.float64).reshape(-1)
    if a.size == 0 or b.size == 0 or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("phases must contain finite values")
    difference = a[:, None] - b[None, :]
    sine = np.sin(math.pi * difference)
    return np.exp(-2.0 * np.square(sine) / (length_scale * length_scale))


def _validated_training(
    phase: ArrayLike,
    flux: ArrayLike,
    weights: ArrayLike | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    x = np.asarray(phase, dtype=np.float64).reshape(-1)
    y = np.asarray(flux, dtype=np.float64).reshape(-1)
    if x.size != y.size or x.size < 4:
        raise ValueError("phase and flux must match and contain at least four observations")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("phase and flux must be finite")
    if weights is None:
        w = np.ones_like(y)
    else:
        w = np.asarray(weights, dtype=np.float64).reshape(-1)
        if w.size != y.size or np.any(w <= 0.0) or not np.all(np.isfinite(w)):
            raise ValueError("weights must be finite, positive, and match flux")
        w = w / float(np.median(w))
    return np.mod(x, 1.0), y, w


def fit_periodic_kernel_ridge(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    length_scale: float,
    ridge: float,
    weights: ArrayLike | None = None,
) -> PeriodicKernelFit:
    """Fit a heteroskedastic periodic kernel-ridge model.

    The solved system is ``(K + diag(ridge / w)) alpha = y``. This is
    symmetric positive definite for positive ridge and weights.
    """

    if not np.isfinite(ridge) or ridge <= 0.0:
        raise ValueError("ridge must be finite and positive")
    x, y, w = _validated_training(phase, flux, weights)
    kernel = periodic_squared_exponential_kernel(x, x, length_scale=length_scale)
    system = kernel + np.diag(float(ridge) / w)
    try:
        coefficients = np.linalg.solve(system, y)
    except np.linalg.LinAlgError as exc:
        raise ValueError("periodic kernel system is singular") from exc
    prediction = kernel @ coefficients
    condition = float(np.linalg.cond(system))
    try:
        smoother = np.linalg.solve(system, kernel)
        effective_parameters = float(np.trace(smoother))
    except np.linalg.LinAlgError:
        effective_parameters = float("nan")
    dense_phase = np.linspace(0.0, 1.0, 2048, endpoint=False, dtype=np.float64)
    dense_prediction = periodic_squared_exponential_kernel(
        dense_phase, x, length_scale=length_scale
    ) @ coefficients
    return PeriodicKernelFit(
        length_scale=float(length_scale),
        ridge=float(ridge),
        train_phase=x,
        coefficients=coefficients,
        condition_number=condition,
        effective_parameters=effective_parameters,
        dense_prediction_span=float(np.ptp(dense_prediction)),
        training_metrics=metric_bundle(y, prediction, weights=w, phase=x),
    )


def predict_periodic_kernel(phase: ArrayLike, fit: PeriodicKernelFit) -> NDArray[np.float64]:
    values = np.asarray(phase, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("phase must contain finite values")
    kernel = periodic_squared_exponential_kernel(
        np.mod(values, 1.0), fit.train_phase, length_scale=fit.length_scale
    )
    prediction = kernel @ fit.coefficients
    if not np.all(np.isfinite(prediction)):
        raise FloatingPointError("periodic kernel prediction is not finite")
    return prediction


def select_periodic_kernel_ridge(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    weights: ArrayLike | None = None,
    length_scales: Iterable[float] = (0.05, 0.10, 0.20, 0.35),
    ridges: Iterable[float] = (1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1),
    folds: int = 4,
    label: str = "periodic-kernel",
    seed: int = 20260808,
    maximum_condition_number: float = 1.0e8,
    maximum_prediction_span_factor: float = 3.0,
) -> PeriodicKernelSelection:
    """Select kernel hyperparameters using only phase-block CV on training data."""

    x, y, w = _validated_training(phase, flux, weights)
    if maximum_condition_number <= 1.0 or not np.isfinite(maximum_condition_number):
        raise ValueError("maximum_condition_number must be finite and greater than one")
    if maximum_prediction_span_factor <= 1.0 or not np.isfinite(maximum_prediction_span_factor):
        raise ValueError("maximum_prediction_span_factor must be finite and greater than one")
    scales = tuple(float(value) for value in length_scales)
    ridge_values = tuple(float(value) for value in ridges)
    if not scales or not ridge_values:
        raise ValueError("at least one length scale and ridge are required")
    if any(not np.isfinite(value) or value <= 0.0 for value in scales + ridge_values):
        raise ValueError("all kernel hyperparameters must be finite and positive")

    fold_set = circular_phase_folds(
        x,
        folds=folds,
        label=label,
        seed=seed,
        minimum_train=max(4, min(8, x.size - int(np.ceil(x.size / folds)))),
    )
    target_span = float(np.ptp(y))
    if target_span <= np.finfo(np.float64).eps:
        raise ValueError("kernel selection requires a non-constant target")

    candidates: list[PeriodicKernelCandidate] = []
    full_fits: dict[tuple[float, float], PeriodicKernelFit] = {}
    for length_scale in scales:
        for ridge in ridge_values:
            oof = np.full_like(y, np.nan)
            failed = False
            for fold in fold_set:
                try:
                    fit = fit_periodic_kernel_ridge(
                        x[fold.train_indices],
                        y[fold.train_indices],
                        length_scale=length_scale,
                        ridge=ridge,
                        weights=w[fold.train_indices],
                    )
                    oof[fold.validation_indices] = predict_periodic_kernel(
                        x[fold.validation_indices], fit
                    )
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    failed = True
                    break
            cv_score = (
                float("inf")
                if failed or not np.all(np.isfinite(oof))
                else weighted_rmse(y, oof, w)
            )
            try:
                full = fit_periodic_kernel_ridge(
                    x,
                    y,
                    length_scale=length_scale,
                    ridge=ridge,
                    weights=w,
                )
                full_fits[(length_scale, ridge)] = full
                condition = full.condition_number
                effective = full.effective_parameters
                span = full.dense_prediction_span
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                condition = float("inf")
                effective = float("nan")
                span = float("inf")
                cv_score = float("inf")

            reasons: list[str] = []
            if not np.isfinite(cv_score):
                reasons.append("cross_validation_failure")
            if condition > maximum_condition_number:
                reasons.append("condition_number")
            if span > maximum_prediction_span_factor * target_span:
                reasons.append("dense_prediction_span")
            candidates.append(
                PeriodicKernelCandidate(
                    length_scale=length_scale,
                    ridge=ridge,
                    cross_validated_weighted_rmse=cv_score,
                    condition_number=condition,
                    effective_parameters=effective,
                    dense_prediction_span=span,
                    eligible=not reasons,
                    rejection_reasons=tuple(reasons),
                )
            )

    eligible = [candidate for candidate in candidates if candidate.eligible]
    fallback_used = not eligible
    selection_pool = eligible or [
        candidate for candidate in candidates if np.isfinite(candidate.cross_validated_weighted_rmse)
    ]
    if not selection_pool:
        raise RuntimeError("all periodic-kernel candidates failed")
    selected = min(
        selection_pool,
        key=lambda candidate: (
            candidate.cross_validated_weighted_rmse,
            candidate.effective_parameters,
            candidate.ridge,
            candidate.length_scale,
        ),
    )
    fit = full_fits[(selected.length_scale, selected.ridge)]
    return PeriodicKernelSelection(
        fit=fit,
        selected_length_scale=selected.length_scale,
        selected_ridge=selected.ridge,
        cross_validated_weighted_rmse=selected.cross_validated_weighted_rmse,
        candidates=tuple(candidates),
        eligible_count=len(eligible),
        fallback_used=fallback_used,
    )
