"""Dual-elliptic radius-difference research implementation."""
from .fitting import DERDFitResult, fit_waveform, predict_from_fit
from .lightcurve import LightCurve, ValueDomain
from .harmonic_exchange import CanonicalHarmonicSeries
from .phase_convention import (
    AmbiguousScreenResult,
    LegacyPhaseAudit,
    LegacyPhaseSummary,
    PhaseRecoverability,
    ambiguity_bounded_screen,
    audit_legacy_phase_summary,
    canonical_coefficients_from_sine_cosine,
)
from .harmonic_screen import (
    AlgebraicDERDCandidate,
    ComplexFourierFit,
    HarmonicScreenResult,
    RecurrenceFit,
    fit_complex_fourier,
    fit_second_order_recurrence,
    rank_screen_results,
    screen_harmonics,
)
from .model import (
    ModelConfig,
    ModelEvaluation,
    OutputNormalization,
    TimeLaw,
    components,
    evaluate,
    peak_aligned_waveform,
    peak_phase,
    raw_waveform,
    waveform,
)
from .parameters import DERDParameters, DIMENSION_NAMES

__all__ = [
    "DERDFitResult",
    "DERDParameters",
    "DIMENSION_NAMES",
    "LightCurve",
    "ModelConfig",
    "ModelEvaluation",
    "OutputNormalization",
    "TimeLaw",
    "ValueDomain",
    "components",
    "evaluate",
    "fit_waveform",
    "peak_aligned_waveform",
    "peak_phase",
    "predict_from_fit",
    "raw_waveform",
    "waveform",
    "AlgebraicDERDCandidate",
    "ComplexFourierFit",
    "HarmonicScreenResult",
    "RecurrenceFit",
    "fit_complex_fourier",
    "fit_second_order_recurrence",
    "rank_screen_results",
    "screen_harmonics",
    "AmbiguousScreenResult",
    "CanonicalHarmonicSeries",
    "LegacyPhaseAudit",
    "LegacyPhaseSummary",
    "PhaseRecoverability",
    "ambiguity_bounded_screen",
    "audit_legacy_phase_summary",
    "canonical_coefficients_from_sine_cosine",
]

__version__ = "2.0.0"
