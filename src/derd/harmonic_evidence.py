"""Weighted signed-harmonic extraction with a lossless covariance record.

The fitted series is

    y(t) = c0 + sum_n [a_n sin(2 pi n f (t-t0))
                       + b_n cos(2 pi n f (t-t0))].

The exchange covariance uses the fixed ordering

    [a_1, ..., a_N, b_1, ..., b_N].

Keeping the signed sine/cosine coefficients and their full covariance avoids the
quadrant and reference-epoch information loss identified in Phase 06.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .harmonic_exchange import CanonicalHarmonicSeries
from .phase_convention import canonical_coefficients_from_sine_cosine
from .preprocess import fold_phase

_EPS = np.finfo(np.float64).eps


def _finite_vector(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite values")
    return array


def _nearest_psd(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    tolerance = max(1.0, float(np.max(np.abs(eigenvalues)))) * 1.0e-13
    clipped = np.where(eigenvalues < tolerance, np.maximum(eigenvalues, 0.0), eigenvalues)
    output = (eigenvectors * clipped) @ eigenvectors.T
    return 0.5 * (output + output.T)


def phase_coverage(phase: ArrayLike, *, bins: int = 12) -> dict[str, Any]:
    values = np.mod(_finite_vector(phase, name="phase"), 1.0)
    if bins < 4:
        raise ValueError("bins must be at least four")
    labels = np.floor(values * bins).astype(np.int64)
    labels = np.clip(labels, 0, bins - 1)
    counts = np.bincount(labels, minlength=bins)
    occupied = int(np.count_nonzero(counts))
    expected = values.size / bins
    chi_square_uniform = float(np.sum(np.square(counts - expected) / max(expected, _EPS)))
    maximum_gap = 0.0
    ordered = np.sort(values)
    if ordered.size:
        wrapped = np.concatenate((ordered, [ordered[0] + 1.0]))
        maximum_gap = float(np.max(np.diff(wrapped)))
    return {
        "bins": int(bins),
        "occupied_bins": occupied,
        "counts": [int(value) for value in counts],
        "occupancy_fraction": float(occupied / bins),
        "maximum_circular_gap": maximum_gap,
        "chi_square_uniform": chi_square_uniform,
    }


@dataclass(frozen=True, slots=True)
class SignedHarmonicFit:
    order: int
    fundamental_frequency: float
    reference_epoch: float
    intercept: float
    sine_coefficients: NDArray[np.float64]
    cosine_coefficients: NDArray[np.float64]
    coefficient_covariance: NDArray[np.float64]
    intercept_variance: float
    design_condition_number: float
    normal_condition_number: float
    effective_rank: int
    sample_count: int
    residual_rmse: float
    weighted_chi_square: float
    reduced_chi_square: float
    covariance_inflation: float
    ridge: float
    phase_coverage: Mapping[str, Any]

    def __post_init__(self) -> None:
        sine = np.asarray(self.sine_coefficients, dtype=np.float64).reshape(-1)
        cosine = np.asarray(self.cosine_coefficients, dtype=np.float64).reshape(-1)
        covariance = np.asarray(self.coefficient_covariance, dtype=np.float64)
        if sine.size != self.order or cosine.size != self.order:
            raise ValueError("coefficient arrays must match order")
        if covariance.shape != (2 * self.order, 2 * self.order):
            raise ValueError("coefficient covariance has the wrong shape")
        if not np.all(np.isfinite(covariance)):
            raise ValueError("coefficient covariance must be finite")
        if not np.allclose(covariance, covariance.T, atol=1.0e-12, rtol=1.0e-10):
            raise ValueError("coefficient covariance must be symmetric")
        if np.min(np.linalg.eigvalsh(covariance)) < -1.0e-10:
            raise ValueError("coefficient covariance must be positive semidefinite")
        object.__setattr__(self, "sine_coefficients", sine)
        object.__setattr__(self, "cosine_coefficients", cosine)
        object.__setattr__(self, "coefficient_covariance", covariance)
        object.__setattr__(self, "phase_coverage", dict(self.phase_coverage))

    @property
    def complex_coefficients(self) -> NDArray[np.complex128]:
        return canonical_coefficients_from_sine_cosine(
            self.sine_coefficients, self.cosine_coefficients
        )

    @property
    def coefficient_standard_errors(self) -> NDArray[np.float64]:
        n = self.order
        diagonal = np.diag(self.coefficient_covariance)
        variance = (diagonal[:n] + diagonal[n:]) / 4.0
        return np.sqrt(np.maximum(variance, 0.0))

    @property
    def coefficient_snr(self) -> NDArray[np.float64]:
        errors = self.coefficient_standard_errors
        return np.divide(
            np.abs(self.complex_coefficients),
            errors,
            out=np.full_like(errors, np.inf),
            where=errors > 0.0,
        )

    def to_exchange(
        self,
        *,
        object_id: str,
        time_unit: str,
        value_unit: str,
        source_locator: str,
        source_sha256: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> CanonicalHarmonicSeries:
        attached = dict(metadata or {})
        attached.update(
            {
                "extraction_model": "weighted_signed_harmonic_regression",
                "coefficient_covariance_order": "sine_1..sine_N,cosine_1..cosine_N",
                "intercept": self.intercept,
                "intercept_variance": self.intercept_variance,
                "design_condition_number": self.design_condition_number,
                "normal_condition_number": self.normal_condition_number,
                "effective_rank": self.effective_rank,
                "sample_count": self.sample_count,
                "residual_rmse": self.residual_rmse,
                "weighted_chi_square": self.weighted_chi_square,
                "reduced_chi_square": self.reduced_chi_square,
                "covariance_inflation": self.covariance_inflation,
                "ridge": self.ridge,
                "phase_coverage": dict(self.phase_coverage),
                "coefficient_snr": [float(value) for value in self.coefficient_snr],
            }
        )
        return CanonicalHarmonicSeries(
            object_id=object_id,
            fundamental_frequency=self.fundamental_frequency,
            reference_epoch=self.reference_epoch,
            time_unit=time_unit,
            value_unit=value_unit,
            sine_coefficients=self.sine_coefficients,
            cosine_coefficients=self.cosine_coefficients,
            coefficient_covariance=self.coefficient_covariance,
            source_locator=source_locator,
            source_sha256=source_sha256,
            intercept=self.intercept,
            metadata=attached,
        )

    def as_dict(self, *, include_covariance: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "order": self.order,
            "fundamental_frequency": self.fundamental_frequency,
            "reference_epoch": self.reference_epoch,
            "intercept": self.intercept,
            "sine_coefficients": [float(value) for value in self.sine_coefficients],
            "cosine_coefficients": [float(value) for value in self.cosine_coefficients],
            "complex_coefficients": [
                {"real": float(value.real), "imag": float(value.imag)}
                for value in self.complex_coefficients
            ],
            "coefficient_standard_errors": [
                float(value) for value in self.coefficient_standard_errors
            ],
            "coefficient_snr": [float(value) for value in self.coefficient_snr],
            "intercept_variance": self.intercept_variance,
            "design_condition_number": self.design_condition_number,
            "normal_condition_number": self.normal_condition_number,
            "effective_rank": self.effective_rank,
            "sample_count": self.sample_count,
            "residual_rmse": self.residual_rmse,
            "weighted_chi_square": self.weighted_chi_square,
            "reduced_chi_square": self.reduced_chi_square,
            "covariance_inflation": self.covariance_inflation,
            "ridge": self.ridge,
            "phase_coverage": dict(self.phase_coverage),
        }
        if include_covariance:
            payload["coefficient_covariance"] = self.coefficient_covariance.tolist()
        return payload


def fit_signed_harmonics(
    time: ArrayLike,
    values: ArrayLike,
    errors: ArrayLike,
    *,
    period: float,
    reference_epoch: float | None = None,
    order: int = 8,
    ridge: float = 1.0e-4,
    coverage_bins: int = 12,
    inflate_covariance: bool = True,
) -> SignedHarmonicFit:
    """Fit signed harmonic coefficients and their full covariance.

    The quoted errors define the generalized least-squares weights.  When
    ``inflate_covariance`` is true, the formal covariance is multiplied by
    ``max(1, chi2/dof)`` so waveform mismatch cannot make the coefficient
    uncertainty artificially small.
    """

    t = _finite_vector(time, name="time")
    y = _finite_vector(values, name="values")
    sigma = _finite_vector(errors, name="errors")
    if t.size != y.size or t.size != sigma.size:
        raise ValueError("time, values, and errors must have matching lengths")
    if np.any(sigma <= 0.0):
        raise ValueError("errors must be strictly positive")
    if order < 4:
        raise ValueError("order must be at least four")
    parameter_count = 1 + 2 * order
    if t.size <= parameter_count + 2:
        raise ValueError("sample count must exceed the harmonic design dimension")
    if not math.isfinite(period) or period <= 0.0:
        raise ValueError("period must be finite and positive")
    if not math.isfinite(ridge) or ridge < 0.0:
        raise ValueError("ridge must be finite and non-negative")
    epoch = float(np.min(t)) if reference_epoch is None else float(reference_epoch)
    if not math.isfinite(epoch):
        raise ValueError("reference_epoch must be finite")

    phase = fold_phase(t, period, epoch=epoch)
    harmonics = np.arange(1, order + 1, dtype=np.float64)
    angle = 2.0 * math.pi * phase[:, None] * harmonics[None, :]
    design = np.column_stack((np.ones(t.size), np.sin(angle), np.cos(angle)))
    weights = 1.0 / np.square(sigma)
    square_root_weights = np.sqrt(weights)
    weighted_design = design * square_root_weights[:, None]
    weighted_target = y * square_root_weights
    normal = weighted_design.T @ weighted_design
    regularizer = np.zeros_like(normal)
    if ridge > 0.0:
        harmonic_scale = float(np.trace(normal[1:, 1:]) / (normal.shape[0] - 1))
        regularizer[1:, 1:] = np.eye(normal.shape[0] - 1) * ridge * harmonic_scale
    penalized = normal + regularizer
    right_hand = weighted_design.T @ weighted_target
    beta = np.linalg.solve(penalized, right_hand)
    prediction = design @ beta
    residual = y - prediction
    rank = int(np.linalg.matrix_rank(weighted_design))
    degrees_of_freedom = max(1, t.size - rank)
    chi_square = float(np.sum(np.square(residual / sigma)))
    reduced_chi_square = chi_square / degrees_of_freedom
    inflation = max(1.0, reduced_chi_square) if inflate_covariance else 1.0

    inverse = np.linalg.pinv(penalized)
    covariance_beta = inflation * inverse @ normal @ inverse
    covariance_beta = _nearest_psd(covariance_beta)
    coefficient_covariance = _nearest_psd(covariance_beta[1:, 1:])

    return SignedHarmonicFit(
        order=order,
        fundamental_frequency=1.0 / float(period),
        reference_epoch=epoch,
        intercept=float(beta[0]),
        sine_coefficients=np.asarray(beta[1 : 1 + order], dtype=np.float64),
        cosine_coefficients=np.asarray(beta[1 + order :], dtype=np.float64),
        coefficient_covariance=coefficient_covariance,
        intercept_variance=float(covariance_beta[0, 0]),
        design_condition_number=float(np.linalg.cond(weighted_design)),
        normal_condition_number=float(np.linalg.cond(penalized)),
        effective_rank=rank,
        sample_count=int(t.size),
        residual_rmse=float(np.sqrt(np.mean(np.square(residual)))),
        weighted_chi_square=chi_square,
        reduced_chi_square=float(reduced_chi_square),
        covariance_inflation=float(inflation),
        ridge=float(ridge),
        phase_coverage=phase_coverage(phase, bins=coverage_bins),
    )
