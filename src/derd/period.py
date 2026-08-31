"""Catalog-period verification and training-only epoch estimation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .baselines import fit_fourier, predict_fourier
from .preprocess import fold_phase


@dataclass(frozen=True, slots=True)
class PeriodCheck:
    catalog_period: float
    best_period: float
    catalog_score: float
    best_score: float
    relative_delta: float
    grid_count: int
    relative_span: float

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_period": self.catalog_period,
            "best_period": self.best_period,
            "catalog_score": self.catalog_score,
            "best_score": self.best_score,
            "relative_delta": self.relative_delta,
            "grid_count": self.grid_count,
            "relative_span": self.relative_span,
        }


def phase_dispersion_score(
    time: ArrayLike,
    values: ArrayLike,
    period: float,
    *,
    bins: int = 8,
) -> float:
    """Return within-bin variance divided by total variance; lower is better."""

    t = np.asarray(time, dtype=np.float64).reshape(-1)
    y = np.asarray(values, dtype=np.float64).reshape(-1)
    if t.size != y.size or t.size < max(8, bins):
        raise ValueError("time and values must match and contain enough observations")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        raise ValueError("time and values must be finite")
    phase = fold_phase(t, period, epoch=float(np.min(t)))
    labels = np.floor(phase * bins).astype(int)
    labels = np.clip(labels, 0, bins - 1)
    numerator = 0.0
    populated = 0
    for label in range(bins):
        member = y[labels == label]
        if member.size >= 2:
            numerator += float(np.sum(np.square(member - np.mean(member))))
            populated += 1
    denominator = float(np.sum(np.square(y - np.mean(y))))
    if denominator <= np.finfo(np.float64).eps or populated < 2:
        return float("inf")
    return numerator / denominator


def verify_catalog_period(
    time: ArrayLike,
    values: ArrayLike,
    catalog_period: float,
    *,
    relative_span: float = 0.001,
    grid_count: int = 201,
    bins: int = 8,
) -> PeriodCheck:
    if not np.isfinite(catalog_period) or catalog_period <= 0.0:
        raise ValueError("catalog_period must be finite and positive")
    if relative_span <= 0.0 or relative_span >= 0.1:
        raise ValueError("relative_span must lie between zero and 0.1")
    if grid_count < 11 or grid_count % 2 == 0:
        raise ValueError("grid_count must be an odd integer of at least 11")
    offsets = np.linspace(-relative_span, relative_span, grid_count)
    periods = catalog_period * (1.0 + offsets)
    scores = np.asarray(
        [phase_dispersion_score(time, values, period, bins=bins) for period in periods],
        dtype=np.float64,
    )
    best_index = int(np.argmin(scores))
    center_index = grid_count // 2
    best = float(periods[best_index])
    return PeriodCheck(
        catalog_period=float(catalog_period),
        best_period=best,
        catalog_score=float(scores[center_index]),
        best_score=float(scores[best_index]),
        relative_delta=(best - catalog_period) / catalog_period,
        grid_count=int(grid_count),
        relative_span=float(relative_span),
    )


def estimate_epoch_of_maximum(
    time: ArrayLike,
    flux: ArrayLike,
    period: float,
    *,
    weights: ArrayLike | None = None,
    order: int = 3,
    grid_size: int = 4096,
) -> tuple[float, float]:
    """Estimate a maximum-flux epoch using only supplied observations.

    Returns ``(epoch, peak_phase_relative_to_min_time)``. The Fourier smooth is
    only a phase-origin estimator and is not counted as a DERD fit.
    """

    t = np.asarray(time, dtype=np.float64).reshape(-1)
    y = np.asarray(flux, dtype=np.float64).reshape(-1)
    if t.size != y.size or t.size < 8:
        raise ValueError("time and flux must match and contain at least eight observations")
    reference = float(np.min(t))
    phase = fold_phase(t, period, epoch=reference)
    fit = fit_fourier(phase, y, order=order, weights=weights, normalize_target=False)
    grid = np.linspace(0.0, 1.0, int(grid_size), endpoint=False, dtype=np.float64)
    smooth = predict_fourier(grid, fit)
    index = int(np.argmax(smooth))
    peak_phase = float(grid[index])
    epoch = reference + peak_phase * period
    return epoch, peak_phase


@dataclass(frozen=True, slots=True)
class AdaptivePeriodCheck:
    """A staged catalog-period audit that widens only after a grid-edge result."""

    catalog_period: float
    best_period: float
    best_score: float
    relative_delta: float
    resolved: bool
    stages: tuple[PeriodCheck, ...]
    boundary_tolerance_steps: float = 0.51

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_period": self.catalog_period,
            "best_period": self.best_period,
            "best_score": self.best_score,
            "relative_delta": self.relative_delta,
            "resolved": self.resolved,
            "stages": [stage.as_dict() for stage in self.stages],
            "boundary_tolerance_steps": self.boundary_tolerance_steps,
        }


def adaptive_verify_catalog_period(
    time: ArrayLike,
    values: ArrayLike,
    catalog_period: float,
    *,
    relative_spans: tuple[float, ...] = (0.001, 0.005, 0.02),
    grid_count: int = 101,
    bins: int = 8,
    boundary_tolerance_steps: float = 0.51,
) -> AdaptivePeriodCheck:
    """Verify a catalog period using progressively wider training-only grids.

    A stage is resolved when its optimum is not on either grid boundary. If the
    optimum remains on a boundary, the next prespecified span is evaluated. The
    function never substitutes the returned period into a scientific fit by
    itself; callers must treat it as a diagnostic unless substitution was
    preregistered separately.
    """

    spans = tuple(float(value) for value in relative_spans)
    if not spans or any(not np.isfinite(value) or value <= 0.0 or value >= 0.1 for value in spans):
        raise ValueError("relative_spans must contain values between zero and 0.1")
    if any(later <= earlier for earlier, later in zip(spans, spans[1:])):
        raise ValueError("relative_spans must be strictly increasing")

    if not np.isfinite(boundary_tolerance_steps) or not 0.0 < boundary_tolerance_steps < 1.0:
        raise ValueError("boundary_tolerance_steps must lie between zero and one")

    stages: list[PeriodCheck] = []
    resolved = False
    for span in spans:
        stage = verify_catalog_period(
            time,
            values,
            catalog_period,
            relative_span=span,
            grid_count=grid_count,
            bins=bins,
        )
        stages.append(stage)
        grid_step = 2.0 * span / (grid_count - 1)
        boundary = abs(stage.relative_delta) >= span - boundary_tolerance_steps * grid_step
        if not boundary:
            resolved = True
            break

    selected = min(stages, key=lambda stage: stage.best_score)
    return AdaptivePeriodCheck(
        catalog_period=float(catalog_period),
        best_period=selected.best_period,
        best_score=selected.best_score,
        relative_delta=selected.relative_delta,
        resolved=resolved,
        stages=tuple(stages),
        boundary_tolerance_steps=float(boundary_tolerance_steps),
    )
