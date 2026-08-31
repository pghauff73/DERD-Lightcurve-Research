"""Transparent Fourier regression baselines for matched waveform comparisons."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .metrics import information_criteria, metric_bundle
from .normalization import minmax_normalize


@dataclass(frozen=True, slots=True)
class FourierFitResult:
    order: int
    coefficients: NDArray[np.float64]
    prediction: NDArray[np.float64]
    metrics: dict[str, float]
    effective_parameters: int
    residual_sum_squares: float
    aic: float
    aicc: float
    bic: float
    design_condition_number: float
    dense_prediction_span: float

    def as_dict(self) -> dict[str, object]:
        return {
            "order": self.order,
            "coefficients": self.coefficients.tolist(),
            "metrics": self.metrics,
            "effective_parameters": self.effective_parameters,
            "residual_sum_squares": self.residual_sum_squares,
            "aic": self.aic,
            "aicc": self.aicc,
            "bic": self.bic,
            "design_condition_number": self.design_condition_number,
            "dense_prediction_span": self.dense_prediction_span,
        }


@dataclass(frozen=True, slots=True)
class FourierSelectionResult:
    criterion: str
    selected: FourierFitResult
    candidates: tuple[FourierFitResult, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion,
            "selected_order": self.selected.order,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class StableFourierSelectionResult:
    criterion: str
    selected: FourierFitResult
    candidates: tuple[FourierFitResult, ...]
    eligible_orders: tuple[int, ...]
    rejected: dict[int, tuple[str, ...]]
    maximum_condition_number: float
    maximum_prediction_span_factor: float

    def as_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion,
            "selected_order": self.selected.order,
            "eligible_orders": list(self.eligible_orders),
            "rejected": {str(order): list(reasons) for order, reasons in self.rejected.items()},
            "maximum_condition_number": self.maximum_condition_number,
            "maximum_prediction_span_factor": self.maximum_prediction_span_factor,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


def fourier_design_matrix(phase: ArrayLike, order: int) -> NDArray[np.float64]:
    if order < 0:
        raise ValueError("order must be non-negative")
    values = np.asarray(phase, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("phase must contain finite values")
    columns = [np.ones_like(values)]
    for harmonic in range(1, order + 1):
        angle = 2.0 * math.pi * harmonic * values
        columns.append(np.cos(angle))
        columns.append(np.sin(angle))
    return np.column_stack(columns)


def predict_fourier(
    phase: ArrayLike,
    fit_or_coefficients: FourierFitResult | ArrayLike,
    *,
    order: int | None = None,
) -> NDArray[np.float64]:
    if isinstance(fit_or_coefficients, FourierFitResult):
        coefficients = fit_or_coefficients.coefficients
        active_order = fit_or_coefficients.order
    else:
        coefficients = np.asarray(fit_or_coefficients, dtype=np.float64).reshape(-1)
        if order is None:
            if coefficients.size < 1 or (coefficients.size - 1) % 2:
                raise ValueError("cannot infer Fourier order from coefficient count")
            active_order = (coefficients.size - 1) // 2
        else:
            active_order = int(order)
    design = fourier_design_matrix(phase, active_order)
    if coefficients.size != design.shape[1]:
        raise ValueError("coefficient count does not match Fourier order")
    return design @ coefficients


def fit_fourier(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    order: int,
    weights: ArrayLike | None = None,
    normalize_target: bool = True,
) -> FourierFitResult:
    x = np.asarray(phase, dtype=np.float64).reshape(-1)
    y = np.asarray(flux, dtype=np.float64).reshape(-1)
    if x.size != y.size or x.size == 0:
        raise ValueError("phase and flux must have the same non-zero size")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("phase and flux must be finite")
    if normalize_target:
        y, _ = minmax_normalize(y)

    design = fourier_design_matrix(x, order)
    if design.shape[1] >= x.size:
        raise ValueError("Fourier model must have fewer coefficients than observations")
    if weights is None:
        weighted_design = design
        weighted_target = y
    else:
        w = np.asarray(weights, dtype=np.float64).reshape(-1)
        if w.size != y.size or np.any(w < 0.0) or not np.all(np.isfinite(w)):
            raise ValueError("weights must be finite, non-negative, and match the data size")
        root = np.sqrt(w)
        weighted_design = design * root[:, None]
        weighted_target = y * root

    coefficients, *_ = np.linalg.lstsq(weighted_design, weighted_target, rcond=None)
    prediction = design @ coefficients
    rss = float(np.sum(np.square(y - prediction)))
    criteria = information_criteria(rss, y.size, design.shape[1])
    design_condition = float(np.linalg.cond(weighted_design))
    dense_phase = np.linspace(0.0, 1.0, 2048, endpoint=False, dtype=np.float64)
    dense_prediction = fourier_design_matrix(dense_phase, order) @ coefficients
    dense_span = float(np.ptp(dense_prediction))
    return FourierFitResult(
        order=int(order),
        coefficients=coefficients,
        prediction=prediction,
        metrics=metric_bundle(y, prediction, weights=weights, phase=x),
        effective_parameters=int(design.shape[1]),
        residual_sum_squares=rss,
        aic=criteria["aic"],
        aicc=criteria["aicc"],
        bic=criteria["bic"],
        design_condition_number=design_condition,
        dense_prediction_span=dense_span,
    )


def select_fourier_order(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    orders: Iterable[int] = range(1, 6),
    weights: ArrayLike | None = None,
    criterion: str = "bic",
    normalize_target: bool = False,
) -> FourierSelectionResult:
    criterion_name = criterion.lower()
    if criterion_name not in {"aic", "aicc", "bic"}:
        raise ValueError("criterion must be aic, aicc, or bic")
    candidates = tuple(
        fit_fourier(
            phase,
            flux,
            order=int(order),
            weights=weights,
            normalize_target=normalize_target,
        )
        for order in orders
    )
    if not candidates:
        raise ValueError("at least one Fourier order is required")
    selected = min(candidates, key=lambda fit: getattr(fit, criterion_name))
    return FourierSelectionResult(criterion=criterion_name, selected=selected, candidates=candidates)


def select_stable_fourier_order(
    phase: ArrayLike,
    flux: ArrayLike,
    *,
    orders: Iterable[int] = range(1, 6),
    weights: ArrayLike | None = None,
    criterion: str = "bic",
    normalize_target: bool = False,
    maximum_condition_number: float = 1.0e4,
    maximum_prediction_span_factor: float = 3.0,
) -> StableFourierSelectionResult:
    """Select order using training-only numerical-stability gates.

    Candidates are rejected when their weighted design matrix is ill-conditioned
    or when a dense full-cycle prediction spans more than a fixed multiple of
    the training target span. Held-out observations are never inspected.
    """

    criterion_name = criterion.lower()
    if criterion_name not in {"aic", "aicc", "bic"}:
        raise ValueError("criterion must be aic, aicc, or bic")
    if maximum_condition_number <= 1.0 or not np.isfinite(maximum_condition_number):
        raise ValueError("maximum_condition_number must be finite and greater than one")
    if maximum_prediction_span_factor <= 1.0 or not np.isfinite(maximum_prediction_span_factor):
        raise ValueError("maximum_prediction_span_factor must be finite and greater than one")
    target = np.asarray(flux, dtype=np.float64).reshape(-1)
    if target.size == 0 or not np.all(np.isfinite(target)):
        raise ValueError("flux must contain finite values")
    target_span = float(np.ptp(target))
    if target_span <= np.finfo(np.float64).eps:
        raise ValueError("stable Fourier selection requires a non-constant target")
    candidates = tuple(
        fit_fourier(
            phase,
            target,
            order=int(order),
            weights=weights,
            normalize_target=normalize_target,
        )
        for order in orders
    )
    if not candidates:
        raise ValueError("at least one Fourier order is required")
    rejected: dict[int, tuple[str, ...]] = {}
    eligible: list[FourierFitResult] = []
    for candidate in candidates:
        reasons: list[str] = []
        if candidate.design_condition_number > maximum_condition_number:
            reasons.append("design_condition")
        if candidate.dense_prediction_span > maximum_prediction_span_factor * target_span:
            reasons.append("dense_prediction_span")
        if reasons:
            rejected[candidate.order] = tuple(reasons)
        else:
            eligible.append(candidate)
    if not eligible:
        # A first-order periodic regression is the conservative deterministic
        # fallback. Its rejection remains visible in the audit record.
        selected = min(candidates, key=lambda fit: fit.order)
        eligible_orders: tuple[int, ...] = ()
    else:
        selected = min(eligible, key=lambda fit: getattr(fit, criterion_name))
        eligible_orders = tuple(candidate.order for candidate in eligible)
    return StableFourierSelectionResult(
        criterion=criterion_name,
        selected=selected,
        candidates=candidates,
        eligible_orders=eligible_orders,
        rejected=rejected,
        maximum_condition_number=float(maximum_condition_number),
        maximum_prediction_span_factor=float(maximum_prediction_span_factor),
    )
