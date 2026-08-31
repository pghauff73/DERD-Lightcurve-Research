"""Phase-convention provenance and recoverability gates.

The legacy feature tables studied in Phase 06 were generated from code that fits

``y(t) = a_n sin(2 pi n f t) + b_n cos(2 pi n f t) + c_n``

and stores ``sqrt(a_n**2 + b_n**2)`` together with
``arctan(b_n / a_n)``.  The latter is a one-argument arctangent, so it loses the
quadrant of ``(a_n, b_n)``.  The table then subtracts the first stored phase from
all four phases.  That subtraction is not invariant to a change of epoch for
harmonics above the fundamental.

This module makes those information losses explicit.  It can enumerate
coefficient sequences that are compatible with a legacy row, but it never
promotes such an enumeration to a unique complex-harmonic measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import itertools
import math
from typing import Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .harmonic_screen import HarmonicScreenResult, screen_harmonics

_TWO_PI = 2.0 * math.pi
_HALF_PI = 0.5 * math.pi
_EPS = 64.0 * np.finfo(np.float64).eps


class PhaseRecoverability(str, Enum):
    """Information state of an amplitude/phase representation."""

    UNIQUE_CANONICAL = "unique_canonical"
    BRANCH_AMBIGUOUS = "branch_ambiguous"
    CONTINUOUS_AND_BRANCH_AMBIGUOUS = "continuous_and_branch_ambiguous"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True, slots=True)
class LegacyPhaseSummary:
    """A frozen-source amplitude and relative-phase row.

    ``relative_phases[n-1]`` is the source value ``p_n - p_1`` where each
    ``p_n = arctan(b_n/a_n)`` lies on the principal interval modulo numerical
    edge cases.
    """

    amplitudes: NDArray[np.float64]
    relative_phases: NDArray[np.float64]

    def __post_init__(self) -> None:
        amplitude = np.asarray(self.amplitudes, dtype=np.float64).reshape(-1)
        relative = np.asarray(self.relative_phases, dtype=np.float64).reshape(-1)
        if amplitude.size < 1 or amplitude.size != relative.size:
            raise ValueError("amplitudes and relative_phases must have equal non-zero length")
        if not np.all(np.isfinite(amplitude)) or np.any(amplitude < 0.0):
            raise ValueError("amplitudes must be finite and non-negative")
        if not np.all(np.isfinite(relative)):
            raise ValueError("relative phases must be finite")
        if abs(float(relative[0])) > 1.0e-9:
            raise ValueError("the first legacy relative phase must be zero")
        object.__setattr__(self, "amplitudes", amplitude)
        object.__setattr__(self, "relative_phases", relative)

    @property
    def harmonic_count(self) -> int:
        return int(self.amplitudes.size)


@dataclass(frozen=True, slots=True)
class FundamentalPhaseInterval:
    lower: float
    upper: float
    consistent: bool

    @property
    def width(self) -> float:
        return max(0.0, float(self.upper - self.lower))

    def as_dict(self) -> dict[str, float | bool]:
        return {
            "lower": float(self.lower),
            "upper": float(self.upper),
            "width": self.width,
            "consistent": self.consistent,
        }


@dataclass(frozen=True, slots=True)
class LegacyPhaseAudit:
    harmonic_count: int
    recoverability: PhaseRecoverability
    feasible_fundamental_phase: FundamentalPhaseInterval
    discrete_branch_count_after_global_sign_quotient: int
    recurrence_overidentifying_real_degrees_of_freedom: int
    qualifies_for_unique_complex_screen: bool
    qualifies_for_harmonic_forecast: bool
    flags: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "harmonic_count": self.harmonic_count,
            "recoverability": self.recoverability.value,
            "feasible_fundamental_phase": self.feasible_fundamental_phase.as_dict(),
            "discrete_branch_count_after_global_sign_quotient": self.discrete_branch_count_after_global_sign_quotient,
            "recurrence_overidentifying_real_degrees_of_freedom": self.recurrence_overidentifying_real_degrees_of_freedom,
            "qualifies_for_unique_complex_screen": self.qualifies_for_unique_complex_screen,
            "qualifies_for_harmonic_forecast": self.qualifies_for_harmonic_forecast,
            "flags": list(self.flags),
        }


@dataclass(frozen=True, slots=True)
class AmbiguousScreenResult:
    """A lower-bound search over missing legacy phase information.

    This is deliberately labelled an ambiguity bound.  The best score is the
    most DERD-compatible coefficient sequence among many sequences represented
    by the same catalog row.  It is not evidence that the measured sequence was
    that best branch.
    """

    audit: LegacyPhaseAudit
    best_score: float
    median_score: float
    worst_score: float
    best_fundamental_phase: float
    best_branch_bits: tuple[int, ...]
    evaluated_sequences: int
    best_result: HarmonicScreenResult | None
    evidence_level: str = "AMBIGUITY_BOUND_ONLY"
    qualifies: bool = False

    def as_dict(self, *, include_best_result: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "audit": self.audit.as_dict(),
            "best_score": self.best_score,
            "median_score": self.median_score,
            "worst_score": self.worst_score,
            "best_fundamental_phase": self.best_fundamental_phase,
            "best_branch_bits": list(self.best_branch_bits),
            "evaluated_sequences": self.evaluated_sequences,
            "evidence_level": self.evidence_level,
            "qualifies": self.qualifies,
        }
        if include_best_result and self.best_result is not None:
            payload["best_result"] = self.best_result.as_dict(include_coefficients=False)
        return payload


def _float_array(values: ArrayLike, *, name: str, non_negative: bool = False) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size < 1 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite values")
    if non_negative and np.any(array < 0.0):
        raise ValueError(f"{name} must be non-negative")
    return array


def principal_mod_pi(phase: ArrayLike) -> NDArray[np.float64]:
    """Map angles to the one-argument-arctangent interval ``[-pi/2, pi/2)``."""

    values = np.asarray(phase, dtype=np.float64)
    return np.mod(values + _HALF_PI, math.pi) - _HALF_PI


def wrap_to_pi(phase: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(phase, dtype=np.float64)
    return np.mod(values + math.pi, _TWO_PI) - math.pi


def canonical_coefficients_from_sine_cosine(
    sine_coefficients: ArrayLike,
    cosine_coefficients: ArrayLike,
) -> NDArray[np.complex128]:
    """Convert signed sine/cosine coefficients to the canonical complex series.

    For ``y = a sin(n theta) + b cos(n theta)``, the positive-frequency
    coefficient in ``y = c exp(i n theta) + conjugate`` is
    ``c = (b - i a)/2``.
    """

    sine = _float_array(sine_coefficients, name="sine_coefficients")
    cosine = _float_array(cosine_coefficients, name="cosine_coefficients")
    if sine.size != cosine.size:
        raise ValueError("sine and cosine coefficients must have equal length")
    return 0.5 * (cosine - 1j * sine)


def sine_cosine_from_canonical_coefficients(
    coefficients: Iterable[complex],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    values = np.asarray(tuple(coefficients), dtype=np.complex128).reshape(-1)
    if values.size < 1:
        raise ValueError("at least one complex coefficient is required")
    if not np.all(np.isfinite(values.real)) or not np.all(np.isfinite(values.imag)):
        raise ValueError("coefficients must be finite")
    sine = -2.0 * values.imag
    cosine = 2.0 * values.real
    return sine.astype(np.float64), cosine.astype(np.float64)


def legacy_summary_from_sine_cosine(
    sine_coefficients: ArrayLike,
    cosine_coefficients: ArrayLike,
) -> LegacyPhaseSummary:
    """Reproduce the frozen source's amplitude and phase reduction."""

    sine = _float_array(sine_coefficients, name="sine_coefficients")
    cosine = _float_array(cosine_coefficients, name="cosine_coefficients")
    if sine.size != cosine.size:
        raise ValueError("sine and cosine coefficients must have equal length")
    amplitude = np.hypot(sine, cosine)
    # atan2 gives the same principal angle as arctan(b/a) except that it retains
    # the quadrant.  Mapping modulo pi reproduces the information actually kept
    # by the one-argument arctangent while handling a=0 deterministically.
    principal = principal_mod_pi(np.arctan2(cosine, sine))
    relative = principal - float(principal[0])
    return LegacyPhaseSummary(amplitude, relative)


def legacy_summary_from_complex_coefficients(
    coefficients: Iterable[complex],
) -> LegacyPhaseSummary:
    sine, cosine = sine_cosine_from_canonical_coefficients(coefficients)
    return legacy_summary_from_sine_cosine(sine, cosine)


def standard_epoch_invariant_relative_phases(
    sine_phases: ArrayLike,
) -> NDArray[np.float64]:
    """Return ``phi_n - n*phi_1`` wrapped to ``[-pi, pi)``."""

    phase = _float_array(sine_phases, name="sine_phases")
    harmonic = np.arange(1, phase.size + 1, dtype=np.float64)
    return wrap_to_pi(phase - harmonic * float(phase[0]))


def shift_sine_phases(sine_phases: ArrayLike, *, epoch_shift_cycles: float) -> NDArray[np.float64]:
    phase = _float_array(sine_phases, name="sine_phases")
    if not math.isfinite(epoch_shift_cycles):
        raise ValueError("epoch_shift_cycles must be finite")
    harmonic = np.arange(1, phase.size + 1, dtype=np.float64)
    return phase + _TWO_PI * harmonic * float(epoch_shift_cycles)


def source_relative_phases_from_sine_phases(sine_phases: ArrayLike) -> NDArray[np.float64]:
    principal = principal_mod_pi(_float_array(sine_phases, name="sine_phases"))
    return principal - float(principal[0])


def feasible_fundamental_phase_interval(relative_phases: ArrayLike) -> FundamentalPhaseInterval:
    relative = _float_array(relative_phases, name="relative_phases")
    relative = relative - float(relative[0])
    lower = max(float(-_HALF_PI - delta) for delta in relative)
    upper = min(float(_HALF_PI - delta) for delta in relative)
    consistent = bool(lower <= upper + _EPS)
    if not consistent:
        return FundamentalPhaseInterval(lower=lower, upper=upper, consistent=False)
    clipped_lower = max(lower, -_HALF_PI)
    clipped_upper = min(upper, _HALF_PI)
    return FundamentalPhaseInterval(
        lower=float(clipped_lower),
        upper=float(clipped_upper),
        consistent=bool(clipped_lower <= clipped_upper + _EPS),
    )


def recurrence_overidentifying_real_degrees_of_freedom(harmonic_count: int) -> int:
    """Real residual degrees of freedom after fitting a complex order-two recurrence."""

    count = int(harmonic_count)
    if count < 1:
        raise ValueError("harmonic_count must be positive")
    return max(0, 2 * (count - 4))


def audit_legacy_phase_summary(summary: LegacyPhaseSummary) -> LegacyPhaseAudit:
    interval = feasible_fundamental_phase_interval(summary.relative_phases)
    flags = [
        "ONE_ARGUMENT_ARCTAN_LOSES_QUADRANT",
        "ABSOLUTE_FUNDAMENTAL_PHASE_NOT_REPORTED",
        "COMMON_PHASE_SUBTRACTION_IS_NOT_EPOCH_INVARIANT_FOR_N_GT_1",
    ]
    if not interval.consistent:
        flags.append("RELATIVE_PHASE_ROW_INCONSISTENT_WITH_PRINCIPAL_ARCTAN_INTERVAL")
        recoverability = PhaseRecoverability.INCONSISTENT
    elif interval.width > 1.0e-12:
        recoverability = PhaseRecoverability.CONTINUOUS_AND_BRANCH_AMBIGUOUS
    else:
        recoverability = PhaseRecoverability.BRANCH_AMBIGUOUS
    branches = 2 ** max(0, summary.harmonic_count - 1)
    dof = recurrence_overidentifying_real_degrees_of_freedom(summary.harmonic_count)
    if dof == 0:
        flags.append("FOUR_HARMONICS_HAVE_ZERO_RECURRENCE_FORECAST_DEGREES_OF_FREEDOM")
    if summary.harmonic_count < 6:
        flags.append("INSUFFICIENT_HARMONICS_FOR_TWO_COEFFICIENT_FORECAST")
    return LegacyPhaseAudit(
        harmonic_count=summary.harmonic_count,
        recoverability=recoverability,
        feasible_fundamental_phase=interval,
        discrete_branch_count_after_global_sign_quotient=branches,
        recurrence_overidentifying_real_degrees_of_freedom=dof,
        qualifies_for_unique_complex_screen=False,
        qualifies_for_harmonic_forecast=False,
        flags=tuple(flags),
    )


def coefficients_from_legacy_summary(
    summary: LegacyPhaseSummary,
    *,
    fundamental_principal_phase: float,
    branch_bits: Sequence[int] | None = None,
) -> NDArray[np.complex128]:
    """Construct one of many canonical coefficient sequences represented by a row."""

    if not math.isfinite(fundamental_principal_phase):
        raise ValueError("fundamental_principal_phase must be finite")
    interval = feasible_fundamental_phase_interval(summary.relative_phases)
    if not interval.consistent:
        raise ValueError("legacy relative phases are inconsistent")
    tolerance = 1.0e-10
    if not (interval.lower - tolerance <= fundamental_principal_phase <= interval.upper + tolerance):
        raise ValueError("fundamental phase lies outside the feasible principal interval")
    if branch_bits is None:
        bits = (0,) * summary.harmonic_count
    else:
        bits = tuple(int(value) for value in branch_bits)
        if len(bits) != summary.harmonic_count or any(value not in (0, 1) for value in bits):
            raise ValueError("branch_bits must contain one zero/one value per harmonic")
    if bits[0] != 0:
        raise ValueError("the first branch bit is fixed to zero after quotienting global sign")
    principal = float(fundamental_principal_phase) + summary.relative_phases
    if np.any(principal < -_HALF_PI - tolerance) or np.any(principal > _HALF_PI + tolerance):
        raise ValueError("reconstructed principal phases leave the arctangent interval")
    true_sine_phase = principal + math.pi * np.asarray(bits, dtype=np.float64)
    return 0.5 * summary.amplitudes * np.exp(1j * (true_sine_phase - _HALF_PI))


def iter_branch_bits(harmonic_count: int) -> Iterable[tuple[int, ...]]:
    count = int(harmonic_count)
    if count < 1:
        raise ValueError("harmonic_count must be positive")
    for tail in itertools.product((0, 1), repeat=max(0, count - 1)):
        yield (0, *tail)


def ambiguity_bounded_screen(
    summary: LegacyPhaseSummary,
    *,
    fit_harmonics: int = 4,
    fundamental_phase_grid_size: int = 129,
) -> AmbiguousScreenResult:
    """Search the missing continuous phase and quadrant branches.

    The returned minimum is a permissive compatibility bound.  Because the
    source row does not identify which sequence was measured, ``qualifies`` is
    always false.
    """

    if fundamental_phase_grid_size < 3:
        raise ValueError("fundamental_phase_grid_size must be at least three")
    audit = audit_legacy_phase_summary(summary)
    interval = audit.feasible_fundamental_phase
    if not interval.consistent:
        return AmbiguousScreenResult(
            audit=audit,
            best_score=math.inf,
            median_score=math.inf,
            worst_score=math.inf,
            best_fundamental_phase=math.nan,
            best_branch_bits=(),
            evaluated_sequences=0,
            best_result=None,
        )
    if interval.width <= 1.0e-14:
        phases = np.asarray([(interval.lower + interval.upper) / 2.0])
    else:
        inset = min(1.0e-12, interval.width / 1000.0)
        phases = np.linspace(
            interval.lower + inset,
            interval.upper - inset,
            fundamental_phase_grid_size,
        )
    scores: list[float] = []
    best_score = math.inf
    best_phase = math.nan
    best_bits: tuple[int, ...] = ()
    best_result: HarmonicScreenResult | None = None
    for bits in iter_branch_bits(summary.harmonic_count):
        for phase in phases:
            coefficients = coefficients_from_legacy_summary(
                summary,
                fundamental_principal_phase=float(phase),
                branch_bits=bits,
            )
            try:
                result = screen_harmonics(
                    coefficients,
                    fit_harmonics=fit_harmonics,
                    minimum_harmonic_snr=None,
                )
                score = float(result.score)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                score = math.inf
                result = None
            scores.append(score)
            if score < best_score:
                best_score = score
                best_phase = float(phase)
                best_bits = bits
                best_result = result
    finite = np.asarray([value for value in scores if math.isfinite(value)], dtype=np.float64)
    if finite.size == 0:
        median = math.inf
        worst = math.inf
    else:
        median = float(np.median(finite))
        worst = float(np.max(finite))
    return AmbiguousScreenResult(
        audit=audit,
        best_score=best_score,
        median_score=median,
        worst_score=worst,
        best_fundamental_phase=best_phase,
        best_branch_bits=best_bits,
        evaluated_sequences=len(scores),
        best_result=best_result,
    )


def frequency_blocks_repeat_under_frozen_source(
    amplitude_blocks: ArrayLike,
    phase_blocks: ArrayLike,
    *,
    atol: float = 1.0e-12,
    rtol: float = 1.0e-10,
) -> bool:
    """Test a necessary output invariant of the frozen three-pass source.

    The source recomputes all three blocks from the same unmodified ``data``.
    Therefore deterministic execution of that exact code must repeat the first
    amplitude and phase block in blocks two and three.
    """

    amplitude = np.asarray(amplitude_blocks, dtype=np.float64)
    phase = np.asarray(phase_blocks, dtype=np.float64)
    if amplitude.ndim != 2 or phase.ndim != 2 or amplitude.shape != phase.shape:
        raise ValueError("amplitude_blocks and phase_blocks must be equal two-dimensional arrays")
    if amplitude.shape[0] < 2 or amplitude.shape[1] < 1:
        raise ValueError("at least two non-empty frequency blocks are required")
    if not np.all(np.isfinite(amplitude)) or not np.all(np.isfinite(phase)):
        raise ValueError("blocks must be finite")
    first_a = np.broadcast_to(amplitude[0], amplitude[1:].shape)
    first_p = np.broadcast_to(phase[0], phase[1:].shape)
    return bool(
        np.allclose(amplitude[1:], first_a, atol=atol, rtol=rtol)
        and np.allclose(phase[1:], first_p, atol=atol, rtol=rtol)
    )
