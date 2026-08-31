"""Fast algebraic screening for the geometric DERD harmonic signature.

The geometric DERD model has non-zero complex Fourier coefficients that form a
sum of two geometric sequences.  Consequently, away from degenerate cases,
they satisfy an order-two linear recurrence.  This module turns that theorem
into a candidate-triage engine.  It does *not* infer stellar structure: it only
tests whether a measured harmonic sequence is compatible with the constrained
waveform family under an explicitly declared Fourier convention.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .parameters import DERDParameters
from .spectral import eccentricity_from_q, raw_derd_complex_coefficients

_EPS = np.finfo(np.float64).eps


def _complex_array(values: ArrayLike, *, minimum: int = 1) -> NDArray[np.complex128]:
    array = np.asarray(values, dtype=np.complex128).reshape(-1)
    if array.size < minimum:
        raise ValueError(f"at least {minimum} complex coefficients are required")
    if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
        raise ValueError("coefficients must be finite")
    if float(np.linalg.norm(array)) <= _EPS:
        raise ValueError("coefficient sequence is effectively zero")
    return array


def _real_array(values: ArrayLike, *, size: int, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size != size:
        raise ValueError(f"{name} must contain {size} values")
    if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError(f"{name} must be finite and positive")
    return array


@dataclass(frozen=True, slots=True)
class ComplexFourierFit:
    """Weighted real Fourier regression expressed as complex coefficients.

    The convention is

    ``y(phi) = c0 + sum(c[n] exp(i 2 pi n phi) + conjugate)``.
    """

    order: int
    coefficients: NDArray[np.complex128]
    coefficient_standard_errors: NDArray[np.float64]
    coefficient_snr: NDArray[np.float64]
    design_condition_number: float
    ridge: float
    residual_rmse: float
    effective_rank: int
    sample_count: int

    def as_dict(self, *, include_coefficients: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "order": self.order,
            "design_condition_number": self.design_condition_number,
            "ridge": self.ridge,
            "residual_rmse": self.residual_rmse,
            "effective_rank": self.effective_rank,
            "sample_count": self.sample_count,
            "coefficient_snr": [float(value) for value in self.coefficient_snr[1:]],
            "coefficient_standard_errors": [
                float(value) for value in self.coefficient_standard_errors[1:]
            ],
        }
        if include_coefficients:
            payload["coefficients"] = [
                {"real": float(value.real), "imag": float(value.imag)}
                for value in self.coefficients
            ]
        return payload


@dataclass(frozen=True, slots=True)
class RecurrenceFit:
    """Least-squares fit of ``c[n+2] = S*c[n+1] - P*c[n]``."""

    sum_roots: complex
    product_roots: complex
    roots: tuple[complex, complex]
    normalized_residual: float
    system_condition_number: float
    fit_harmonics: int

    def as_dict(self) -> dict[str, object]:
        def encoded(value: complex) -> dict[str, float]:
            return {"real": float(value.real), "imag": float(value.imag)}

        return {
            "sum_roots": encoded(self.sum_roots),
            "product_roots": encoded(self.product_roots),
            "roots": [encoded(value) for value in self.roots],
            "root_magnitudes": [float(abs(value)) for value in self.roots],
            "normalized_residual": self.normalized_residual,
            "system_condition_number": self.system_condition_number,
            "fit_harmonics": self.fit_harmonics,
        }


@dataclass(frozen=True, slots=True)
class AlgebraicDERDCandidate:
    """One root assignment mapped to the four DERD shape dimensions."""

    parameters: DERDParameters
    epoch_ratio: float
    scale: float
    root_1: complex
    root_2: complex
    residue_1: complex
    residue_2: complex
    fit_residual: float
    forecast_residual: float | None
    ratio_imaginary_residual: float
    opposite_sign_residues: bool
    root_domain_penalty: float
    amplitude_domain_penalty: float
    total_score: float
    predicted_coefficients: NDArray[np.complex128]

    def as_dict(self, *, include_coefficients: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "parameters": self.parameters.as_dict(),
            "epoch_ratio": self.epoch_ratio,
            "scale": self.scale,
            "root_magnitudes": [float(abs(self.root_1)), float(abs(self.root_2))],
            "root_phases_cycles": [
                float((np.angle(self.root_1) / (2.0 * math.pi)) % 1.0),
                float((np.angle(self.root_2) / (2.0 * math.pi)) % 1.0),
            ],
            "fit_residual": self.fit_residual,
            "forecast_residual": self.forecast_residual,
            "ratio_imaginary_residual": self.ratio_imaginary_residual,
            "opposite_sign_residues": self.opposite_sign_residues,
            "root_domain_penalty": self.root_domain_penalty,
            "amplitude_domain_penalty": self.amplitude_domain_penalty,
            "total_score": self.total_score,
        }
        if include_coefficients:
            payload["predicted_coefficients"] = [
                {"real": float(value.real), "imag": float(value.imag)}
                for value in self.predicted_coefficients
            ]
        return payload


@dataclass(frozen=True, slots=True)
class HarmonicScreenResult:
    """Complete fast-screen result for a positive-harmonic sequence."""

    fit_harmonics: int
    available_harmonics: int
    recurrence: RecurrenceFit
    candidate: AlgebraicDERDCandidate
    unconstrained_forecast_residual: float | None
    harmonic_energy: float
    fit_energy: float
    holdout_energy: float
    score: float
    evidence_level: str
    flags: tuple[str, ...]

    def as_dict(self, *, include_coefficients: bool = False) -> dict[str, object]:
        return {
            "fit_harmonics": self.fit_harmonics,
            "available_harmonics": self.available_harmonics,
            "recurrence": self.recurrence.as_dict(),
            "candidate": self.candidate.as_dict(
                include_coefficients=include_coefficients
            ),
            "unconstrained_forecast_residual": self.unconstrained_forecast_residual,
            "harmonic_energy": self.harmonic_energy,
            "fit_energy": self.fit_energy,
            "holdout_energy": self.holdout_energy,
            "score": self.score,
            "evidence_level": self.evidence_level,
            "flags": list(self.flags),
        }


def fit_complex_fourier(
    phase: ArrayLike,
    values: ArrayLike,
    *,
    order: int,
    errors: ArrayLike | None = None,
    weights: ArrayLike | None = None,
    ridge: float = 0.0,
) -> ComplexFourierFit:
    """Fit a weighted Fourier series and return complex positive harmonics.

    ``ridge`` is dimensionless.  It is multiplied by the mean diagonal of the
    weighted normal matrix and applied only to harmonic terms, not the mean.
    """

    if order < 1:
        raise ValueError("order must be positive")
    phi = np.mod(np.asarray(phase, dtype=np.float64).reshape(-1), 1.0)
    target = np.asarray(values, dtype=np.float64).reshape(-1)
    if phi.size != target.size or phi.size < 2 * order + 2:
        raise ValueError("phase and values must match and exceed Fourier dimension")
    if not np.all(np.isfinite(phi)) or not np.all(np.isfinite(target)):
        raise ValueError("phase and values must be finite")
    if errors is not None and weights is not None:
        raise ValueError("provide errors or weights, not both")
    if errors is not None:
        sigma = _real_array(errors, size=phi.size, name="errors")
        active_weights = 1.0 / np.square(sigma)
    elif weights is not None:
        active_weights = _real_array(weights, size=phi.size, name="weights")
    else:
        active_weights = np.ones(phi.size, dtype=np.float64)
    active_weights /= float(np.median(active_weights))
    if not math.isfinite(ridge) or ridge < 0.0:
        raise ValueError("ridge must be finite and non-negative")

    columns: list[NDArray[np.float64]] = [np.ones(phi.size, dtype=np.float64)]
    for harmonic in range(1, order + 1):
        angle = 2.0 * math.pi * harmonic * phi
        columns.extend((np.cos(angle), np.sin(angle)))
    design = np.column_stack(columns)
    square_root_weights = np.sqrt(active_weights)
    weighted_design = design * square_root_weights[:, None]
    weighted_target = target * square_root_weights
    normal = weighted_design.T @ weighted_design
    regularizer = np.zeros_like(normal)
    if ridge > 0.0:
        scale = float(np.trace(normal) / normal.shape[0])
        regularizer[1:, 1:] = np.eye(normal.shape[0] - 1) * ridge * scale
    penalized = normal + regularizer
    right_hand = weighted_design.T @ weighted_target
    beta = np.linalg.solve(penalized, right_hand)
    prediction = design @ beta
    residual = target - prediction
    residual_rmse = float(np.sqrt(np.mean(np.square(residual))))
    effective_rank = int(np.linalg.matrix_rank(weighted_design))
    condition = float(np.linalg.cond(weighted_design))

    degrees_of_freedom = max(1, phi.size - effective_rank)
    weighted_rss = float(np.sum(active_weights * np.square(residual)))
    residual_variance = weighted_rss / degrees_of_freedom
    covariance = residual_variance * np.linalg.pinv(penalized) @ normal @ np.linalg.pinv(penalized)

    coefficients = np.zeros(order + 1, dtype=np.complex128)
    standard_errors = np.zeros(order + 1, dtype=np.float64)
    coefficients[0] = complex(float(beta[0]), 0.0)
    standard_errors[0] = math.sqrt(max(0.0, float(covariance[0, 0])))
    for harmonic in range(1, order + 1):
        cosine_index = 2 * harmonic - 1
        sine_index = 2 * harmonic
        coefficients[harmonic] = complex(
            float(beta[cosine_index]) / 2.0,
            -float(beta[sine_index]) / 2.0,
        )
        variance = (
            float(covariance[cosine_index, cosine_index])
            + float(covariance[sine_index, sine_index])
        ) / 4.0
        standard_errors[harmonic] = math.sqrt(max(0.0, variance))
    coefficient_snr = np.divide(
        np.abs(coefficients),
        standard_errors,
        out=np.full_like(standard_errors, np.inf),
        where=standard_errors > 0.0,
    )
    return ComplexFourierFit(
        order=order,
        coefficients=coefficients,
        coefficient_standard_errors=standard_errors,
        coefficient_snr=coefficient_snr,
        design_condition_number=condition,
        ridge=float(ridge),
        residual_rmse=residual_rmse,
        effective_rank=effective_rank,
        sample_count=int(phi.size),
    )


def fit_second_order_recurrence(
    coefficients: ArrayLike,
    *,
    fit_harmonics: int | None = None,
) -> RecurrenceFit:
    """Fit the two-root recurrence to ``c1, c2, ...`` by complex least squares."""

    sequence = _complex_array(coefficients, minimum=4)
    active_count = sequence.size if fit_harmonics is None else int(fit_harmonics)
    if active_count < 4 or active_count > sequence.size:
        raise ValueError("fit_harmonics must lie between four and sequence length")
    active = sequence[:active_count]
    matrix = np.column_stack((active[1:-1], -active[:-2]))
    target = active[2:]
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    sum_roots = complex(solution[0])
    product_roots = complex(solution[1])
    roots_array = np.roots(np.asarray([1.0 + 0.0j, -sum_roots, product_roots]))
    prediction = matrix @ solution
    denominator = max(float(np.linalg.norm(target)), _EPS)
    normalized_residual = float(np.linalg.norm(prediction - target) / denominator)
    condition = float(np.linalg.cond(matrix))
    return RecurrenceFit(
        sum_roots=sum_roots,
        product_roots=product_roots,
        roots=(complex(roots_array[0]), complex(roots_array[1])),
        normalized_residual=normalized_residual,
        system_condition_number=condition,
        fit_harmonics=active_count,
    )


def predict_from_recurrence(
    first: complex,
    second: complex,
    *,
    sum_roots: complex,
    product_roots: complex,
    harmonics: int,
) -> NDArray[np.complex128]:
    if harmonics < 2:
        raise ValueError("harmonics must be at least two")
    output = np.zeros(harmonics, dtype=np.complex128)
    output[0] = complex(first)
    output[1] = complex(second)
    for index in range(2, harmonics):
        output[index] = sum_roots * output[index - 1] - product_roots * output[index - 2]
    return output


def _residues(first: complex, second: complex, root_1: complex, root_2: complex) -> tuple[complex, complex]:
    matrix = np.asarray([[1.0, 1.0], [root_1, root_2]], dtype=np.complex128)
    if float(abs(np.linalg.det(matrix))) <= 1.0e-14:
        raise ValueError("recurrence roots are too close to separate residues")
    values = np.linalg.solve(matrix, np.asarray([first, second], dtype=np.complex128))
    return complex(values[0]), complex(values[1])


def _harmonic_prefactor(eccentricity: float) -> float:
    root = math.sqrt(max(0.0, 1.0 - eccentricity * eccentricity))
    return root / (2.0 * (1.0 + root))


def _relative_error(
    prediction: NDArray[np.complex128],
    target: NDArray[np.complex128],
    *,
    reference_energy: float | None = None,
) -> float:
    numerator = float(np.linalg.norm(prediction - target))
    if reference_energy is None:
        denominator = float(np.linalg.norm(target))
    else:
        denominator = float(reference_energy)
    return numerator / max(denominator, _EPS)


def _candidate_for_assignment(
    sequence: NDArray[np.complex128],
    recurrence: RecurrenceFit,
    *,
    root_1: complex,
    root_2: complex,
    fit_harmonics: int,
) -> AlgebraicDERDCandidate:
    residue_1, residue_2 = _residues(sequence[0], sequence[1], root_1, root_2)
    q_raw_1 = float(abs(root_1))
    q_raw_2 = float(abs(root_2))
    q_1 = float(np.clip(q_raw_1, 1.0e-8, 1.0 - 1.0e-8))
    q_2 = float(np.clip(q_raw_2, 1.0e-8, 1.0 - 1.0e-8))
    e_1 = eccentricity_from_q(q_1)
    e_2 = eccentricity_from_q(q_2)
    prefactor_1 = _harmonic_prefactor(e_1)
    prefactor_2 = _harmonic_prefactor(e_2)
    if abs(residue_1) <= 1.0e-14 or prefactor_2 <= 1.0e-14:
        amplitude_ratio = 1.0e6
    else:
        amplitude_ratio = float(
            abs(residue_2 / residue_1) * prefactor_1 / prefactor_2
        )
    safe_amplitude = float(np.clip(amplitude_ratio, 1.0e-6, 1.0e6))
    phase_ratio = float((np.angle(root_2 / root_1) / (2.0 * math.pi)) % 1.0)
    epoch_ratio = float((np.angle(-root_1) / (2.0 * math.pi)) % 1.0)
    parameters = DERDParameters(e_1, e_2, safe_amplitude, phase_ratio)

    maximum_harmonic = int(sequence.size)
    base = raw_derd_complex_coefficients(
        parameters, maximum_harmonic=maximum_harmonic
    )[1:]
    harmonics = np.arange(1, maximum_harmonic + 1, dtype=np.float64)
    rotated = base * np.exp(1j * 2.0 * math.pi * harmonics * epoch_ratio)
    active_model = rotated[:fit_harmonics]
    active_target = sequence[:fit_harmonics]
    denominator = float(np.sum(np.abs(active_model) ** 2))
    if denominator <= _EPS:
        scale = 0.0
    else:
        scale = float(
            np.real(np.vdot(active_model, active_target)) / denominator
        )
    predicted = scale * rotated
    fit_residual = _relative_error(
        predicted[:fit_harmonics], active_target
    )
    if maximum_harmonic > fit_harmonics:
        holdout_reference = max(
            float(np.linalg.norm(sequence[fit_harmonics:])),
            0.05 * float(np.linalg.norm(active_target)),
        )
        forecast_residual: float | None = _relative_error(
            predicted[fit_harmonics:],
            sequence[fit_harmonics:],
            reference_energy=holdout_reference,
        )
    else:
        forecast_residual = None

    ratio_1 = residue_1 / root_1 if abs(root_1) > _EPS else complex(np.inf, np.inf)
    ratio_2 = residue_2 / root_2 if abs(root_2) > _EPS else complex(np.inf, np.inf)
    imaginary_1 = abs(ratio_1.imag) / max(abs(ratio_1), _EPS)
    imaginary_2 = abs(ratio_2.imag) / max(abs(ratio_2), _EPS)
    ratio_imaginary_residual = float(math.sqrt((imaginary_1**2 + imaginary_2**2) / 2.0))
    opposite_sign = bool(float(np.real(ratio_1) * np.real(ratio_2)) < 0.0)

    root_domain_penalty = float(
        math.sqrt(
            (
                max(0.0, q_raw_1 - 0.999) ** 2
                + max(0.0, q_raw_2 - 0.999) ** 2
                + max(0.0, 1.0e-5 - q_raw_1) ** 2
                + max(0.0, 1.0e-5 - q_raw_2) ** 2
            )
            / 2.0
        )
        / 0.10
    )
    log_amplitude = math.log10(max(amplitude_ratio, 1.0e-300))
    amplitude_domain_penalty = float(
        max(0.0, -2.0 - log_amplitude) + max(0.0, log_amplitude - 2.0)
    )
    consistency_penalty = ratio_imaginary_residual + (0.0 if opposite_sign else 1.0)
    forecast_term = 0.0 if forecast_residual is None else forecast_residual
    total_score = float(
        fit_residual
        + forecast_term
        + 0.5 * consistency_penalty
        + root_domain_penalty
        + 0.25 * amplitude_domain_penalty
        + recurrence.normalized_residual
    )
    return AlgebraicDERDCandidate(
        parameters=parameters,
        epoch_ratio=epoch_ratio,
        scale=scale,
        root_1=root_1,
        root_2=root_2,
        residue_1=residue_1,
        residue_2=residue_2,
        fit_residual=fit_residual,
        forecast_residual=forecast_residual,
        ratio_imaginary_residual=ratio_imaginary_residual,
        opposite_sign_residues=opposite_sign,
        root_domain_penalty=root_domain_penalty,
        amplitude_domain_penalty=amplitude_domain_penalty,
        total_score=total_score,
        predicted_coefficients=predicted,
    )


def screen_harmonics(
    coefficients: ArrayLike,
    *,
    fit_harmonics: int = 4,
    minimum_forecast_harmonics: int = 2,
    minimum_harmonic_snr: float | None = None,
    coefficient_snr: ArrayLike | None = None,
) -> HarmonicScreenResult:
    """Screen ``c1, c2, ...`` for the constrained geometric DERD signature.

    Four harmonics are the minimum for algebraic recovery.  Six or more provide
    a genuine harmonic-forecast test.  Fewer than two holdout harmonics are
    labelled ``SHAPE_ONLY`` and must not be treated as predictive evidence.
    """

    sequence = _complex_array(coefficients, minimum=4)
    if fit_harmonics < 4 or fit_harmonics > sequence.size:
        raise ValueError("fit_harmonics must lie between four and sequence length")
    recurrence = fit_second_order_recurrence(
        sequence, fit_harmonics=fit_harmonics
    )
    candidates: list[AlgebraicDERDCandidate] = []
    roots = recurrence.roots
    for root_1, root_2 in (roots, roots[::-1]):
        try:
            candidates.append(
                _candidate_for_assignment(
                    sequence,
                    recurrence,
                    root_1=root_1,
                    root_2=root_2,
                    fit_harmonics=fit_harmonics,
                )
            )
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            continue
    if not candidates:
        raise ValueError("no numerically separable recurrence-root assignment")
    candidate = min(candidates, key=lambda item: item.total_score)

    recurrence_prediction = predict_from_recurrence(
        sequence[0],
        sequence[1],
        sum_roots=recurrence.sum_roots,
        product_roots=recurrence.product_roots,
        harmonics=sequence.size,
    )
    if sequence.size > fit_harmonics:
        holdout_reference = max(
            float(np.linalg.norm(sequence[fit_harmonics:])),
            0.05 * float(np.linalg.norm(sequence[:fit_harmonics])),
        )
        unconstrained_forecast: float | None = _relative_error(
            recurrence_prediction[fit_harmonics:],
            sequence[fit_harmonics:],
            reference_energy=holdout_reference,
        )
    else:
        unconstrained_forecast = None

    flags: list[str] = []
    holdout_count = sequence.size - fit_harmonics
    if holdout_count < minimum_forecast_harmonics:
        flags.append("INSUFFICIENT_HARMONIC_FORECAST")
        evidence_level = "SHAPE_ONLY"
    else:
        evidence_level = "HARMONIC_FORECAST"
    if recurrence.system_condition_number > 1.0e6:
        flags.append("RECURRENCE_ILL_CONDITIONED")
    if candidate.root_domain_penalty > 0.0:
        flags.append("ROOT_OUTSIDE_PHYSICAL_Q_DOMAIN")
    if not candidate.opposite_sign_residues:
        flags.append("RESIDUE_SIGN_CONSTRAINT_FAILED")
    if candidate.ratio_imaginary_residual > 0.25:
        flags.append("RESIDUE_PHASE_CONSTRAINT_WEAK")
    if candidate.amplitude_domain_penalty > 0.0:
        flags.append("AMPLITUDE_RATIO_EXTREME")
    if minimum_harmonic_snr is not None:
        if coefficient_snr is None:
            raise ValueError("coefficient_snr is required when minimum_harmonic_snr is set")
        snr = np.asarray(coefficient_snr, dtype=np.float64).reshape(-1)
        if snr.size != sequence.size or not np.all(np.isfinite(snr)):
            raise ValueError("coefficient_snr must match the coefficient sequence")
        if int(np.count_nonzero(snr >= minimum_harmonic_snr)) < fit_harmonics:
            flags.append("INSUFFICIENT_HARMONIC_SNR")

    return HarmonicScreenResult(
        fit_harmonics=fit_harmonics,
        available_harmonics=int(sequence.size),
        recurrence=recurrence,
        candidate=candidate,
        unconstrained_forecast_residual=unconstrained_forecast,
        harmonic_energy=float(np.sum(np.abs(sequence) ** 2)),
        fit_energy=float(np.sum(np.abs(sequence[:fit_harmonics]) ** 2)),
        holdout_energy=float(np.sum(np.abs(sequence[fit_harmonics:]) ** 2)),
        score=candidate.total_score,
        evidence_level=evidence_level,
        flags=tuple(flags),
    )


def rank_screen_results(
    labelled_results: Iterable[tuple[str, HarmonicScreenResult]],
) -> list[tuple[int, str, HarmonicScreenResult]]:
    ordered = sorted(labelled_results, key=lambda item: (item[1].score, item[0]))
    return [(index + 1, label, result) for index, (label, result) in enumerate(ordered)]
