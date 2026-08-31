"""Deterministic paired population summaries for model-comparison evidence."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.stats import binomtest


@dataclass(frozen=True, slots=True)
class PairedComparison:
    sample_count: int
    mean_difference: float
    median_difference: float
    mean_confidence_interval: tuple[float, float]
    median_confidence_interval: tuple[float, float]
    first_model_win_count: int
    second_model_win_or_tie_count: int
    exact_sign_test_p_value: float
    noninferiority_margin: float
    noninferiority_pass_mean: bool
    bootstrap_repetitions: int

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "mean_difference": self.mean_difference,
            "median_difference": self.median_difference,
            "mean_confidence_interval": list(self.mean_confidence_interval),
            "median_confidence_interval": list(self.median_confidence_interval),
            "first_model_win_count": self.first_model_win_count,
            "second_model_win_or_tie_count": self.second_model_win_or_tie_count,
            "exact_sign_test_p_value": self.exact_sign_test_p_value,
            "noninferiority_margin": self.noninferiority_margin,
            "noninferiority_pass_mean": self.noninferiority_pass_mean,
            "bootstrap_repetitions": self.bootstrap_repetitions,
        }


def paired_bootstrap_comparison(
    first: ArrayLike,
    second: ArrayLike,
    *,
    repetitions: int = 20000,
    confidence: float = 0.95,
    seed: int = 20260808,
    noninferiority_margin: float = 0.02,
) -> PairedComparison:
    """Compare paired errors using first-minus-second differences.

    A negative difference favours the first model. The noninferiority gate
    passes only when the upper confidence bound for the mean difference does
    not exceed ``noninferiority_margin``.
    """

    a = np.asarray(first, dtype=np.float64).reshape(-1)
    b = np.asarray(second, dtype=np.float64).reshape(-1)
    if a.size < 2 or a.size != b.size or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("paired inputs must be finite, matching, and contain at least two values")
    if repetitions < 100:
        raise ValueError("repetitions must be at least 100")
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must lie between 0.5 and 1")
    if not np.isfinite(noninferiority_margin) or noninferiority_margin < 0.0:
        raise ValueError("noninferiority_margin must be finite and non-negative")

    difference = a - b
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, difference.size, size=(repetitions, difference.size))
    samples = difference[indices]
    boot_mean = np.mean(samples, axis=1)
    boot_median = np.median(samples, axis=1)
    alpha = 1.0 - confidence
    mean_ci = tuple(float(value) for value in np.quantile(boot_mean, [alpha / 2.0, 1.0 - alpha / 2.0]))
    median_ci = tuple(float(value) for value in np.quantile(boot_median, [alpha / 2.0, 1.0 - alpha / 2.0]))
    wins = int(np.count_nonzero(difference < 0.0))
    non_ties = int(np.count_nonzero(difference != 0.0))
    p_value = 1.0 if non_ties == 0 else float(binomtest(wins, non_ties, p=0.5, alternative="two-sided").pvalue)
    return PairedComparison(
        sample_count=int(difference.size),
        mean_difference=float(np.mean(difference)),
        median_difference=float(np.median(difference)),
        mean_confidence_interval=mean_ci,
        median_confidence_interval=median_ci,
        first_model_win_count=wins,
        second_model_win_or_tie_count=int(difference.size - wins),
        exact_sign_test_p_value=p_value,
        noninferiority_margin=float(noninferiority_margin),
        noninferiority_pass_mean=bool(mean_ci[1] <= noninferiority_margin),
        bootstrap_repetitions=int(repetitions),
    )
