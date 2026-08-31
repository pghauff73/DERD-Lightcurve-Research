"""Phase-20 mechanism-discrimination and passband-projection experiments.

This module contains three orthogonal experiments:

1. A covariance-aware I-versus-V harmonic-invariant comparison for
   OGLE-LMC-CEP-0002.
2. A frozen synthetic mechanism tournament that asks whether non-DERD
   mechanisms can pass DERD waveform and harmonic-screen gates.
3. A formal and numerical gravity-only radial-motion falsifier based on the
   effective mass ``M_eff=-R^2 R_ddot/G``.

The experiments are waveform-only. They do not infer stellar mass, a shell
mass, or a unique internal mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from scipy.stats import chi2

from .fitting import fit_waveform, predict_from_fit
from .geometric import normalized_radius
from .harmonic_exchange import CanonicalHarmonicSeries
from .harmonic_screen import fit_complex_fourier, screen_harmonics
from .model import waveform
from .parameters import DERDParameters

_EPS = np.finfo(np.float64).eps


@dataclass(frozen=True, slots=True)
class InvariantEstimate:
    labels: tuple[str, ...]
    vector: NDArray[np.float64]
    covariance: NDArray[np.float64]
    standard_error: NDArray[np.float64]
    draws: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "labels": list(self.labels),
            "vector": dict(zip(self.labels, [float(v) for v in self.vector], strict=True)),
            "standard_error": dict(
                zip(self.labels, [float(v) for v in self.standard_error], strict=True)
            ),
            "covariance": self.covariance.tolist(),
            "draws": self.draws,
        }


@dataclass(frozen=True, slots=True)
class InvariantComparison:
    first: InvariantEstimate
    second: InvariantEstimate
    difference: NDArray[np.float64]
    combined_covariance: NDArray[np.float64]
    mahalanobis_chi_square: float
    degrees_of_freedom: int
    p_value: float

    def as_dict(self) -> dict[str, Any]:
        labels = self.first.labels
        return {
            "first": self.first.as_dict(),
            "second": self.second.as_dict(),
            "difference_second_minus_first": dict(
                zip(labels, [float(v) for v in self.difference], strict=True)
            ),
            "combined_covariance": self.combined_covariance.tolist(),
            "mahalanobis_chi_square": self.mahalanobis_chi_square,
            "degrees_of_freedom": self.degrees_of_freedom,
            "p_value": self.p_value,
        }


@dataclass(frozen=True, slots=True)
class ShapeModelComparison:
    grid_size: int
    shared_derd_parameters: NDArray[np.float64]
    separate_derd_parameters: tuple[NDArray[np.float64], NDArray[np.float64]]
    shared_component_parameters: NDArray[np.float64]
    shared_component_band_coefficients: tuple[NDArray[np.float64], NDArray[np.float64]]
    rmse: Mapping[str, float]
    bic: Mapping[str, float]
    bootstrap_draws: int
    bootstrap_wins: Mapping[str, int]
    bootstrap_delta_bic: Mapping[str, Mapping[str, float]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "grid_size": self.grid_size,
            "shared_derd_parameters": self.shared_derd_parameters.tolist(),
            "separate_derd_parameters": [
                self.separate_derd_parameters[0].tolist(),
                self.separate_derd_parameters[1].tolist(),
            ],
            "shared_component_parameters": self.shared_component_parameters.tolist(),
            "shared_component_band_coefficients": [
                self.shared_component_band_coefficients[0].tolist(),
                self.shared_component_band_coefficients[1].tolist(),
            ],
            "rmse": dict(self.rmse),
            "bic": dict(self.bic),
            "bootstrap_draws": self.bootstrap_draws,
            "bootstrap_wins": dict(self.bootstrap_wins),
            "bootstrap_delta_bic": {
                key: dict(value) for key, value in self.bootstrap_delta_bic.items()
            },
            "interpretation_limit": (
                "The comparison uses covariance-sampled h1-h8 reconstructions, "
                "not independent raw observations. BIC is therefore a representation-level heuristic."
            ),
        }


@dataclass(frozen=True, slots=True)
class MechanismRecord:
    case_id: str
    family: str
    split: str
    heldout_rmse: float
    harmonic_screen_score: float
    forecast_residual: float
    flags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family": self.family,
            "split": self.split,
            "heldout_rmse": self.heldout_rmse,
            "harmonic_screen_score": self.harmonic_screen_score,
            "forecast_residual": self.forecast_residual,
            "flags": list(self.flags),
        }


@dataclass(frozen=True, slots=True)
class MechanismTournament:
    thresholds: Mapping[str, float]
    threshold_development_metrics: Mapping[str, Mapping[str, float]]
    holdout_family_summary: tuple[Mapping[str, Any], ...]
    records: tuple[MechanismRecord, ...]

    def as_dict(self, *, include_records: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "thresholds": dict(self.thresholds),
            "threshold_development_metrics": {
                key: dict(value) for key, value in self.threshold_development_metrics.items()
            },
            "holdout_family_summary": [dict(row) for row in self.holdout_family_summary],
            "interpretation_limit": (
                "The generators are controlled mechanism surrogates, not full stellar-evolution "
                "models. Passing a gate disproves uniqueness; it does not establish astrophysical prevalence."
            ),
        }
        if include_records:
            payload["records"] = [record.as_dict() for record in self.records]
        return payload


@dataclass(frozen=True, slots=True)
class EffectiveMassControl:
    model_id: str
    periodic: bool
    positive_mass_fraction: float
    median_effective_mass: float
    coefficient_of_variation_positive: float
    sign_changes: int
    gate_pass: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "periodic": self.periodic,
            "positive_mass_fraction": self.positive_mass_fraction,
            "median_effective_mass": self.median_effective_mass,
            "coefficient_of_variation_positive": self.coefficient_of_variation_positive,
            "sign_changes": self.sign_changes,
            "gate_pass": self.gate_pass,
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reconstruct_harmonic_series(
    series: CanonicalHarmonicSeries, phase: ArrayLike
) -> NDArray[np.float64]:
    phi = np.mod(np.asarray(phase, dtype=np.float64).reshape(-1), 1.0)
    values = np.full(phi.size, float(series.intercept), dtype=np.float64)
    for harmonic, (sine, cosine) in enumerate(
        zip(series.sine_coefficients, series.cosine_coefficients, strict=True), start=1
    ):
        angle = 2.0 * math.pi * harmonic * phi
        values += sine * np.sin(angle) + cosine * np.cos(angle)
    return values


def minmax(values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    span = float(np.ptp(array))
    if not np.isfinite(span) or span <= _EPS:
        raise ValueError("values are effectively constant")
    return (array - float(np.min(array))) / span


def peak_align(values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return np.roll(array, -int(np.argmax(array)))


def invariant_vector_from_signed_coefficients(
    sine: ArrayLike, cosine: ArrayLike
) -> NDArray[np.float64]:
    s = np.asarray(sine, dtype=np.float64).reshape(-1)
    c = np.asarray(cosine, dtype=np.float64).reshape(-1)
    if s.size < 3 or s.size != c.size:
        raise ValueError("at least three matched harmonics are required")
    amplitudes = np.hypot(s, c)
    if amplitudes[0] <= _EPS:
        raise ValueError("fundamental amplitude is effectively zero")
    phases = np.arctan2(-s, c)
    output = np.empty(4, dtype=np.float64)
    output[0] = amplitudes[1] / amplitudes[0]
    output[1] = ((phases[1] - 2.0 * phases[0] + math.pi) % (2.0 * math.pi)) - math.pi
    output[2] = amplitudes[2] / amplitudes[0]
    output[3] = ((phases[2] - 3.0 * phases[0] + math.pi) % (2.0 * math.pi)) - math.pi
    return output


def invariant_estimate(
    series: CanonicalHarmonicSeries,
    *,
    draws: int = 20000,
    seed: int = 20260825,
) -> InvariantEstimate:
    if series.coefficient_covariance is None:
        raise ValueError("coefficient covariance is required")
    if draws < 1000:
        raise ValueError("at least 1000 draws are required")
    mean = np.concatenate((series.sine_coefficients, series.cosine_coefficients))
    point = invariant_vector_from_signed_coefficients(
        series.sine_coefficients, series.cosine_coefficients
    )
    rng = np.random.default_rng(seed)
    samples = rng.multivariate_normal(
        mean, series.coefficient_covariance, size=draws, check_valid="ignore"
    )
    values = np.asarray(
        [
            invariant_vector_from_signed_coefficients(
                sample[: series.harmonic_count], sample[series.harmonic_count :]
            )
            for sample in samples
        ],
        dtype=np.float64,
    )
    for index in (1, 3):
        values[:, index] = point[index] + (
            (values[:, index] - point[index] + math.pi) % (2.0 * math.pi) - math.pi
        )
    covariance = np.cov(values, rowvar=False)
    return InvariantEstimate(
        labels=("R21", "phi21", "R31", "phi31"),
        vector=point,
        covariance=covariance,
        standard_error=np.sqrt(np.maximum(0.0, np.diag(covariance))),
        draws=draws,
    )


def compare_invariants(
    first: CanonicalHarmonicSeries,
    second: CanonicalHarmonicSeries,
    *,
    draws: int = 20000,
    first_seed: int = 20260825,
    second_seed: int = 20260826,
) -> InvariantComparison:
    estimate_a = invariant_estimate(first, draws=draws, seed=first_seed)
    estimate_b = invariant_estimate(second, draws=draws, seed=second_seed)
    difference = estimate_b.vector - estimate_a.vector
    for index in (1, 3):
        difference[index] = (
            (difference[index] + math.pi) % (2.0 * math.pi)
        ) - math.pi
    combined = estimate_a.covariance + estimate_b.covariance
    statistic = float(difference @ np.linalg.pinv(combined) @ difference)
    dof = int(np.linalg.matrix_rank(combined))
    return InvariantComparison(
        first=estimate_a,
        second=estimate_b,
        difference=difference,
        combined_covariance=combined,
        mahalanobis_chi_square=statistic,
        degrees_of_freedom=dof,
        p_value=float(chi2.sf(statistic, dof)),
    )


def optimal_circular_shape_rmse(
    first: CanonicalHarmonicSeries,
    second: CanonicalHarmonicSeries,
    *,
    grid_size: int = 8192,
    maximum_lag: float = 0.08,
    lag_steps: int = 3201,
) -> dict[str, float]:
    """Return the best phase-only alignment without an expensive brute-force scan.

    Min-max normalization is invariant to a circular phase shift.  A dense FFT
    cross-correlation therefore identifies the best discrete shift, after which
    a bounded scalar refinement evaluates the analytic harmonic series.
    ``lag_steps`` is retained for API compatibility and reported as a provenance
    coordinate; it no longer controls a quadratic scan.
    """
    from scipy.optimize import minimize_scalar

    if grid_size < 256:
        raise ValueError("grid_size must be at least 256")
    phase = np.linspace(0.0, 1.0, grid_size, endpoint=False, dtype=np.float64)
    first_values = minmax(reconstruct_harmonic_series(first, phase))
    second_values = minmax(reconstruct_harmonic_series(second, phase))
    centered_first = first_values - float(np.mean(first_values))
    centered_second = second_values - float(np.mean(second_values))
    correlation = np.fft.ifft(
        np.conj(np.fft.fft(centered_first)) * np.fft.fft(centered_second)
    ).real
    signed_shifts = np.arange(grid_size, dtype=np.int64)
    signed_shifts[signed_shifts > grid_size // 2] -= grid_size
    allowed = np.abs(signed_shifts / grid_size) <= maximum_lag
    candidate_indices = np.flatnonzero(allowed)
    best_index = int(candidate_indices[np.argmax(correlation[candidate_indices])])
    discrete_lag = float(signed_shifts[best_index] / grid_size)

    def objective(lag: float) -> float:
        shifted = minmax(
            reconstruct_harmonic_series(second, np.mod(phase + lag, 1.0))
        )
        return float(np.sqrt(np.mean(np.square(first_values - shifted))))

    half_width = 2.5 / grid_size
    lower = max(-maximum_lag, discrete_lag - half_width)
    upper = min(maximum_lag, discrete_lag + half_width)
    refined = minimize_scalar(
        objective,
        bounds=(lower, upper),
        method="bounded",
        options={"xatol": 1.0e-10, "maxiter": 80},
    )
    lag = float(refined.x) if refined.success else discrete_lag
    rmse = float(refined.fun) if refined.success else objective(discrete_lag)
    return {
        "minimum_rmse": rmse,
        "best_lag_cycles": lag,
        "grid_size": int(grid_size),
        "lag_steps_legacy_coordinate": int(lag_steps),
        "method": "FFT discrete alignment plus bounded analytic refinement",
    }


def _derd_aligned(phase: NDArray[np.float64], vector: NDArray[np.float64]) -> NDArray[np.float64]:
    parameters = DERDParameters.from_iterable(vector)
    values = waveform(
        phase,
        parameters,
        time_law="geometric",
        normalization_grid_size=1024,
    )
    return peak_align(values)


def _least_squares_best(
    residual: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    starts: Iterable[NDArray[np.float64]],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    *,
    maximum_evaluations: int,
) -> tuple[NDArray[np.float64], float]:
    best_x: NDArray[np.float64] | None = None
    best_cost = math.inf
    for start in starts:
        fit = least_squares(
            residual,
            np.clip(np.asarray(start, dtype=np.float64), lower, upper),
            bounds=(lower, upper),
            max_nfev=maximum_evaluations,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        cost = float(2.0 * fit.cost)
        if cost < best_cost:
            best_cost = cost
            best_x = fit.x
    assert best_x is not None
    return best_x, best_cost


def compare_passband_shape_models(
    first: CanonicalHarmonicSeries,
    second: CanonicalHarmonicSeries,
    *,
    grid_size: int = 256,
    bootstrap_draws: int = 64,
    seed: int = 20260825,
) -> ShapeModelComparison:
    phase = np.linspace(0.0, 1.0, grid_size, endpoint=False, dtype=np.float64)
    first_curve = peak_align(minmax(reconstruct_harmonic_series(first, phase)))
    second_curve = peak_align(minmax(reconstruct_harmonic_series(second, phase)))
    combined_count = 2 * grid_size
    rng = np.random.default_rng(seed)
    derd_lower = np.array([0.0, 0.0, 0.01, 0.0], dtype=np.float64)
    derd_upper = np.array([0.98, 0.98, 2.0, np.nextafter(1.0, 0.0)])
    deterministic = [
        np.array([0.10, 0.30, 0.35, 0.25]),
        np.array([0.30, 0.70, 0.55, 0.75]),
        np.array([0.70, 0.30, 0.85, 0.50]),
        np.array([0.15, 0.80, 1.20, 0.90]),
    ]
    nominal_starts = [*deterministic]
    nominal_starts.extend(
        rng.uniform(derd_lower, derd_upper) for _ in range(8)
    )
    shared_parameters, shared_rss = _least_squares_best(
        lambda vector: np.concatenate(
            (
                _derd_aligned(phase, vector) - first_curve,
                _derd_aligned(phase, vector) - second_curve,
            )
        ),
        nominal_starts,
        derd_lower,
        derd_upper,
        maximum_evaluations=400,
    )
    separate_parameters: list[NDArray[np.float64]] = []
    separate_rss = 0.0
    for target in (first_curve, second_curve):
        parameters, rss = _least_squares_best(
            lambda vector, target=target: _derd_aligned(phase, vector) - target,
            nominal_starts,
            derd_lower,
            derd_upper,
            maximum_evaluations=400,
        )
        separate_parameters.append(parameters)
        separate_rss += rss

    component_lower = np.zeros(4, dtype=np.float64)
    component_upper = np.array([0.98, 0.98, np.nextafter(1.0, 0.0), np.nextafter(1.0, 0.0)])

    def component_basis(vector: NDArray[np.float64]) -> NDArray[np.float64]:
        e1, e2, internal_phase, global_phase = vector
        active = np.mod(phase + global_phase, 1.0)
        return np.column_stack(
            (
                np.ones(grid_size, dtype=np.float64),
                normalized_radius(active, e1),
                normalized_radius(np.mod(active + internal_phase, 1.0), e2),
            )
        )

    def component_residual(
        vector: NDArray[np.float64],
        curve_a: NDArray[np.float64],
        curve_b: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        design = component_basis(vector)
        beta_a = np.linalg.lstsq(design, curve_a, rcond=None)[0]
        beta_b = np.linalg.lstsq(design, curve_b, rcond=None)[0]
        return np.concatenate((design @ beta_a - curve_a, design @ beta_b - curve_b))

    component_starts = [
        rng.uniform(component_lower, component_upper) for _ in range(16)
    ]
    component_parameters, component_rss = _least_squares_best(
        lambda vector: component_residual(vector, first_curve, second_curve),
        component_starts,
        component_lower,
        component_upper,
        maximum_evaluations=600,
    )
    design = component_basis(component_parameters)
    beta_first = np.linalg.lstsq(design, first_curve, rcond=None)[0]
    beta_second = np.linalg.lstsq(design, second_curve, rcond=None)[0]

    rss_map = {
        "shared_derd": shared_rss,
        "separate_derd": separate_rss,
        "shared_components_band_weights": component_rss,
    }
    parameter_counts = {
        "shared_derd": 4,
        "separate_derd": 8,
        "shared_components_band_weights": 10,
    }
    rmse = {
        name: float(math.sqrt(value / combined_count)) for name, value in rss_map.items()
    }
    bic = {
        name: float(
            combined_count * math.log(max(value / combined_count, _EPS))
            + parameter_counts[name] * math.log(combined_count)
        )
        for name, value in rss_map.items()
    }

    def sample_curve(series: CanonicalHarmonicSeries) -> NDArray[np.float64]:
        if series.coefficient_covariance is None:
            raise ValueError("coefficient covariance is required")
        mean = np.concatenate((series.sine_coefficients, series.cosine_coefficients))
        draw = rng.multivariate_normal(mean, series.coefficient_covariance, check_valid="ignore")
        harmonic_count = series.harmonic_count
        sampled = CanonicalHarmonicSeries(
            object_id=series.object_id,
            fundamental_frequency=series.fundamental_frequency,
            reference_epoch=series.reference_epoch,
            time_unit=series.time_unit,
            value_unit=series.value_unit,
            sine_coefficients=draw[:harmonic_count],
            cosine_coefficients=draw[harmonic_count:],
            source_locator=series.source_locator,
            source_sha256=series.source_sha256,
            intercept=series.intercept,
            coefficient_covariance=series.coefficient_covariance,
            metadata=series.metadata,
        )
        return peak_align(minmax(reconstruct_harmonic_series(sampled, phase)))

    bootstrap_bic: list[dict[str, float]] = []
    for _ in range(bootstrap_draws):
        curve_a = sample_curve(first)
        curve_b = sample_curve(second)

        def local_starts(center: NDArray[np.float64], lower: NDArray[np.float64], upper: NDArray[np.float64]) -> list[NDArray[np.float64]]:
            return [
                center,
                np.clip(center + rng.normal(0.0, 0.05, center.size), lower, upper),
            ]

        _, rss_shared = _least_squares_best(
            lambda vector: np.concatenate(
                (
                    _derd_aligned(phase, vector) - curve_a,
                    _derd_aligned(phase, vector) - curve_b,
                )
            ),
            local_starts(shared_parameters, derd_lower, derd_upper),
            derd_lower,
            derd_upper,
            maximum_evaluations=120,
        )
        rss_separate = 0.0
        for target, center in zip(
            (curve_a, curve_b), separate_parameters, strict=True
        ):
            _, rss = _least_squares_best(
                lambda vector, target=target: _derd_aligned(phase, vector) - target,
                local_starts(center, derd_lower, derd_upper),
                derd_lower,
                derd_upper,
                maximum_evaluations=120,
            )
            rss_separate += rss
        _, rss_component = _least_squares_best(
            lambda vector: component_residual(vector, curve_a, curve_b),
            local_starts(component_parameters, component_lower, component_upper),
            component_lower,
            component_upper,
            maximum_evaluations=120,
        )
        active_rss = {
            "shared_derd": rss_shared,
            "separate_derd": rss_separate,
            "shared_components_band_weights": rss_component,
        }
        bootstrap_bic.append(
            {
                name: float(
                    combined_count * math.log(max(value / combined_count, _EPS))
                    + parameter_counts[name] * math.log(combined_count)
                )
                for name, value in active_rss.items()
            }
        )

    wins = {
        name: int(
            sum(min(row, key=row.get) == name for row in bootstrap_bic)
        )
        for name in parameter_counts
    }

    def delta_summary(first_name: str, second_name: str) -> dict[str, float]:
        values = np.asarray(
            [row[first_name] - row[second_name] for row in bootstrap_bic],
            dtype=np.float64,
        )
        return {
            "median": float(np.median(values)),
            "q05": float(np.quantile(values, 0.05)),
            "q95": float(np.quantile(values, 0.95)),
            "fraction_below_zero": float(np.mean(values < 0.0)),
        }

    return ShapeModelComparison(
        grid_size=grid_size,
        shared_derd_parameters=shared_parameters,
        separate_derd_parameters=(separate_parameters[0], separate_parameters[1]),
        shared_component_parameters=component_parameters,
        shared_component_band_coefficients=(beta_first, beta_second),
        rmse=rmse,
        bic=bic,
        bootstrap_draws=bootstrap_draws,
        bootstrap_wins=wins,
        bootstrap_delta_bic={
            "components_minus_shared_derd": delta_summary(
                "shared_components_band_weights", "shared_derd"
            ),
            "components_minus_separate_derd": delta_summary(
                "shared_components_band_weights", "separate_derd"
            ),
            "separate_minus_shared_derd": delta_summary(
                "separate_derd", "shared_derd"
            ),
        },
    )


def _normalize_signal(values: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(values, dtype=np.float64)
    return minmax(values)


def _interpolate_periodic(template: NDArray[np.float64], phase: NDArray[np.float64]) -> NDArray[np.float64]:
    location = np.mod(phase, 1.0) * template.size
    integer = np.floor(location).astype(np.int64) % template.size
    fraction = location - np.floor(location)
    return template[integer] * (1.0 - fraction) + template[(integer + 1) % template.size] * fraction


def _vdp_templates() -> tuple[NDArray[np.float64], ...]:
    output: list[NDArray[np.float64]] = []
    grid = np.linspace(0.0, 1.0, 2048, endpoint=False)
    for mu in (0.5, 1.2, 2.2, 3.5):
        def equation(_time: float, state: NDArray[np.float64], mu: float = mu) -> list[float]:
            return [state[1], mu * (1.0 - state[0] ** 2) * state[1] - state[0]]

        solution = solve_ivp(
            equation,
            (0.0, 80.0),
            (0.1, 0.0),
            rtol=1.0e-6,
            atol=1.0e-8,
            dense_output=True,
            max_step=0.08,
        )
        late_time = np.linspace(50.0, 80.0, 6000)
        late_value = solution.sol(late_time)[0]
        crossings = np.where((late_value[:-1] < 0.0) & (late_value[1:] >= 0.0))[0]
        period = float(np.median(np.diff(late_time[crossings])[-4:]))
        epoch = float(late_time[crossings[-2]])
        output.append(_normalize_signal(solution.sol(epoch + grid * period)[0]))
    return tuple(output)


def _hash_split(case_id: str) -> str:
    fraction = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:16], 16) / float(16**16)
    return "development" if fraction < 2.0 / 3.0 else "holdout"


def _mechanism_generators(seed: int) -> Mapping[str, Callable[[NDArray[np.float64], np.random.Generator], NDArray[np.float64]]]:
    templates = _vdp_templates()

    def derd(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        parameters = DERDParameters(
            float(rng.uniform(0.03, 0.92)),
            float(rng.uniform(0.03, 0.92)),
            float(np.exp(rng.uniform(math.log(0.05), math.log(2.0)))),
            float(rng.random()),
        )
        return waveform(
            phase,
            parameters,
            time_law="geometric",
            normalization_grid_size=256,
        )

    def generic_fourier(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        values = np.zeros_like(phase)
        decay = float(rng.uniform(0.15, 0.8))
        for harmonic in range(1, 9):
            values += (
                math.exp(-decay * harmonic)
                * float(rng.uniform(0.5, 1.5))
                * np.cos(2.0 * math.pi * harmonic * phase + float(rng.uniform(-math.pi, math.pi)))
            )
        return _normalize_signal(values)

    def two_pole(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        root_1 = float(rng.uniform(0.15, 0.75)) * np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
        root_2 = float(rng.uniform(0.15, 0.75)) * np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
        residue_1 = complex(float(rng.normal()), float(rng.normal()))
        residue_2 = complex(float(rng.normal()), float(rng.normal()))
        values = np.zeros_like(phase)
        for harmonic in range(1, 13):
            coefficient = residue_1 * root_1**harmonic + residue_2 * root_2**harmonic
            values += 2.0 * np.real(
                coefficient * np.exp(2j * math.pi * harmonic * phase)
            )
        return _normalize_signal(values)

    def radius_temperature(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        radius_amplitude = float(rng.uniform(0.015, 0.08))
        temperature_amplitude = float(rng.uniform(0.01, 0.05))
        lag = float(rng.uniform(0.05, 0.35))
        radius = 1.0 + radius_amplitude * (
            np.sin(2.0 * math.pi * phase)
            + float(rng.uniform(0.1, 0.5))
            * np.sin(4.0 * math.pi * phase + float(rng.uniform(-1.0, 1.0)))
        )
        temperature = 1.0 + temperature_amplitude * (
            np.sin(2.0 * math.pi * (phase - lag))
            + float(rng.uniform(0.05, 0.3))
            * np.sin(4.0 * math.pi * (phase - lag) + float(rng.uniform(-1.0, 1.0)))
        )
        return _normalize_signal(radius**2 * temperature**4)

    def vdp(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        template = templates[int(rng.integers(0, len(templates)))]
        return _interpolate_periodic(template, phase + float(rng.random()))

    def two_zone(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        first = _interpolate_periodic(
            templates[int(rng.integers(0, len(templates)))], phase + float(rng.random())
        )
        second = _interpolate_periodic(
            templates[int(rng.integers(0, len(templates)))],
            phase + float(rng.uniform(0.05, 0.45)),
        )
        return _normalize_signal(first + float(rng.uniform(0.15, 0.8)) * second)

    def shock(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        sharpness = float(rng.uniform(1.5, 4.5))
        base = np.exp(sharpness * np.cos(2.0 * math.pi * (phase - float(rng.random()))))
        location = float(rng.random())
        width = float(rng.uniform(0.015, 0.06))
        distance = ((phase - location + 0.5) % 1.0) - 0.5
        bump = (
            float(rng.uniform(-0.3, 0.3))
            * np.exp(-0.5 * np.square(distance / width))
            * float(np.max(base))
        )
        return _normalize_signal(base + bump)

    def tidal(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        eccentricity = float(rng.uniform(0.15, 0.75))

        def force(active_phase: NDArray[np.float64]) -> NDArray[np.float64]:
            mean_anomaly = 2.0 * math.pi * np.mod(active_phase, 1.0)
            eccentric_anomaly = mean_anomaly.copy()
            for _ in range(10):
                eccentric_anomaly -= (
                    eccentric_anomaly
                    - eccentricity * np.sin(eccentric_anomaly)
                    - mean_anomaly
                ) / (1.0 - eccentricity * np.cos(eccentric_anomaly))
            radius = 1.0 - eccentricity * np.cos(eccentric_anomaly)
            return np.power(radius, -3.0)

        lag = float(rng.uniform(0.02, 0.2))
        return _normalize_signal(
            force(phase) + float(rng.uniform(0.2, 0.8)) * force(phase - lag)
        )

    def spot(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        return _normalize_signal(
            np.sin(2.0 * math.pi * phase + float(rng.uniform(0.0, 2.0 * math.pi)))
            + float(rng.uniform(0.05, 0.35))
            * np.sin(4.0 * math.pi * phase + float(rng.uniform(0.0, 2.0 * math.pi)))
        )

    def cse(phase: NDArray[np.float64], rng: np.random.Generator) -> NDArray[np.float64]:
        lag = float(rng.uniform(0.03, 0.25))
        base = np.sin(2.0 * math.pi * phase) + float(rng.uniform(0.1, 0.35)) * np.sin(
            4.0 * math.pi * phase + float(rng.uniform(0.0, 2.0 * math.pi))
        )
        delayed = np.sin(2.0 * math.pi * (phase - lag)) + float(rng.uniform(0.1, 0.35)) * np.sin(
            4.0 * math.pi * (phase - lag) + float(rng.uniform(0.0, 2.0 * math.pi))
        )
        return _normalize_signal(base + float(rng.uniform(0.2, 0.8)) * delayed)

    return {
        "derd_geometric": derd,
        "generic_fourier": generic_fourier,
        "two_pole_transfer": two_pole,
        "radius_temperature_projection": radius_temperature,
        "vdp_hydrodynamic_surrogate": vdp,
        "two_zone_surrogate": two_zone,
        "shock_modified": shock,
        "tidal_kepler_response": tidal,
        "spot_rotation": spot,
        "cse_reprocessing": cse,
    }


def _calibrate_lower_threshold(
    records: Iterable[MechanismRecord], field: str
) -> tuple[float, dict[str, float]]:
    rows = [
        row
        for row in records
        if row.split == "development"
        and row.family in {"derd_geometric", "generic_fourier"}
    ]
    values = np.asarray([float(getattr(row, field)) for row in rows], dtype=np.float64)
    labels = np.asarray([row.family == "derd_geometric" for row in rows], dtype=bool)
    unique = np.unique(values)
    candidates = np.concatenate(
        (
            [np.nextafter(unique[0], -np.inf)],
            (unique[:-1] + unique[1:]) / 2.0,
            [np.nextafter(unique[-1], np.inf)],
        )
    )
    best: tuple[tuple[float, float, float], float, dict[str, float]] | None = None
    for threshold in candidates:
        predicted = values <= threshold
        tp = int(np.count_nonzero(predicted & labels))
        fn = int(np.count_nonzero(~predicted & labels))
        tn = int(np.count_nonzero(~predicted & ~labels))
        fp = int(np.count_nonzero(predicted & ~labels))
        sensitivity = tp / max(1, tp + fn)
        specificity = tn / max(1, tn + fp)
        balanced = 0.5 * (sensitivity + specificity)
        metrics = {
            "true_positive": float(tp),
            "false_negative": float(fn),
            "true_negative": float(tn),
            "false_positive": float(fp),
            "sensitivity": float(sensitivity),
            "specificity": float(specificity),
            "balanced_accuracy": float(balanced),
        }
        key = (balanced, specificity, -float(threshold))
        if best is None or key > best[0]:
            best = (key, float(threshold), metrics)
    assert best is not None
    return best[1], best[2]


def run_mechanism_tournament(
    *,
    cases_per_family: int = 30,
    sample_count: int = 128,
    holdout_count: int = 24,
    noise_sigma: float = 0.012,
    seed: int = 20260825,
) -> MechanismTournament:
    if cases_per_family < 12:
        raise ValueError("cases_per_family must be at least 12")
    rng = np.random.default_rng(seed)
    generators = _mechanism_generators(seed)
    records: list[MechanismRecord] = []
    dense_phase = np.linspace(0.0, 1.0, 2048, endpoint=False)
    for family, generator in generators.items():
        for repetition in range(cases_per_family):
            case_id = f"{family}:{repetition:03d}"
            phase = np.sort(rng.uniform(0.0, 1.0, sample_count))
            dense_values = generator(dense_phase, rng)
            dense_values = np.roll(dense_values, -int(np.argmax(dense_values)))
            extended_phase = np.concatenate((dense_phase, [1.0]))
            extended_value = np.concatenate((dense_values, [dense_values[0]]))
            signal = np.interp(phase, extended_phase, extended_value)
            noisy = _normalize_signal(signal + rng.normal(0.0, noise_sigma, sample_count))

            holdout_start = (repetition * 11) % sample_count
            holdout_indices = np.arange(
                holdout_start, holdout_start + holdout_count
            ) % sample_count
            train_mask = np.ones(sample_count, dtype=bool)
            train_mask[holdout_indices] = False
            fit = fit_waveform(
                phase[train_mask],
                noisy[train_mask],
                time_law="geometric",
                starts=2,
                seed=seed + repetition,
                normalization_grid_size=256,
                peak_grid_size=256,
                max_function_evaluations=80,
                normalize_target=False,
                align_peak=True,
            )
            prediction = predict_from_fit(
                phase[~train_mask],
                fit,
                normalization_grid_size=256,
                peak_grid_size=256,
            )
            heldout_rmse = float(
                np.sqrt(np.mean(np.square(prediction - noisy[~train_mask])))
            )
            fourier = fit_complex_fourier(
                phase,
                noisy,
                order=8,
                errors=np.full(sample_count, noise_sigma),
                ridge=1.0e-4,
            )
            try:
                screen = screen_harmonics(
                    fourier.coefficients[1:],
                    fit_harmonics=4,
                    minimum_harmonic_snr=None,
                )
                score = float(screen.score)
                forecast = float(
                    screen.candidate.forecast_residual
                    if screen.candidate.forecast_residual is not None
                    else 1.0e6
                )
                flags = tuple(screen.flags)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                score = 1.0e6
                forecast = 1.0e6
                flags = ("NUMERICAL_SCREEN_FAILURE",)
            records.append(
                MechanismRecord(
                    case_id=case_id,
                    family=family,
                    split=_hash_split(case_id),
                    heldout_rmse=heldout_rmse,
                    harmonic_screen_score=score,
                    forecast_residual=forecast,
                    flags=flags,
                )
            )

    rmse_threshold, rmse_metrics = _calibrate_lower_threshold(
        records, "heldout_rmse"
    )
    score_threshold, score_metrics = _calibrate_lower_threshold(
        records, "harmonic_screen_score"
    )
    forecast_threshold, forecast_metrics = _calibrate_lower_threshold(
        records, "forecast_residual"
    )
    thresholds = {
        "heldout_rmse": rmse_threshold,
        "harmonic_screen_score": score_threshold,
        "forecast_residual": forecast_threshold,
    }

    summary: list[Mapping[str, Any]] = []
    for family in generators:
        rows = [row for row in records if row.family == family and row.split == "holdout"]
        fit_pass = np.asarray(
            [row.heldout_rmse <= rmse_threshold for row in rows], dtype=bool
        )
        screen_pass = np.asarray(
            [row.harmonic_screen_score <= score_threshold for row in rows],
            dtype=bool,
        )
        forecast_pass = np.asarray(
            [row.forecast_residual <= forecast_threshold for row in rows],
            dtype=bool,
        )
        summary.append(
            {
                "family": family,
                "holdout_count": len(rows),
                "median_heldout_rmse": float(np.median([row.heldout_rmse for row in rows])),
                "median_harmonic_screen_score": float(
                    np.median([row.harmonic_screen_score for row in rows])
                ),
                "median_forecast_residual": float(
                    np.median([row.forecast_residual for row in rows])
                ),
                "fit_pass_fraction": float(np.mean(fit_pass)),
                "screen_pass_fraction": float(np.mean(screen_pass)),
                "forecast_pass_fraction": float(np.mean(forecast_pass)),
                "joint_fit_and_screen_pass_fraction": float(
                    np.mean(fit_pass & screen_pass)
                ),
            }
        )

    return MechanismTournament(
        thresholds=thresholds,
        threshold_development_metrics={
            "heldout_rmse": rmse_metrics,
            "harmonic_screen_score": score_metrics,
            "forecast_residual": forecast_metrics,
        },
        holdout_family_summary=tuple(summary),
        records=tuple(records),
    )


def _effective_mass_summary(
    model_id: str,
    radius: NDArray[np.float64],
    acceleration: NDArray[np.float64],
    *,
    periodic: bool,
    gravity_constant: float = 1.0,
) -> EffectiveMassControl:
    effective_mass = -np.square(radius) * acceleration / gravity_constant
    positive = effective_mass > 0.0
    positive_values = effective_mass[positive]
    if positive_values.size:
        median = float(np.median(positive_values))
        mean = float(np.mean(positive_values))
        cv = float(np.std(positive_values) / abs(mean)) if abs(mean) > _EPS else math.inf
    else:
        median = float("nan")
        cv = math.inf
    sign = np.sign(effective_mass)
    sign = sign[sign != 0.0]
    sign_changes = int(np.count_nonzero(sign[1:] != sign[:-1])) if sign.size > 1 else 0
    positive_fraction = float(np.mean(positive))
    gate_pass = bool(positive_fraction >= 0.95 and cv <= 0.10)
    return EffectiveMassControl(
        model_id=model_id,
        periodic=periodic,
        positive_mass_fraction=positive_fraction,
        median_effective_mass=median,
        coefficient_of_variation_positive=cv,
        sign_changes=sign_changes,
        gate_pass=gate_pass,
    )


def effective_mass_controls() -> tuple[EffectiveMassControl, ...]:
    """Return positive and negative controls for the gravity-only mass test.

    Units are dimensionless with ``G=M=1``. The ballistic segment is a positive
    control. The remaining models are non-constant periodic radius curves and
    must fail because a positive inverse-square acceleration is inward at every
    time, whereas a periodic radius needs outward acceleration near a minimum.
    """

    def ballistic_equation(_time: float, state: NDArray[np.float64]) -> list[float]:
        return [state[1], -1.0 / state[0] ** 2]

    solution = solve_ivp(
        ballistic_equation,
        (0.0, 0.45),
        (1.5, 0.05),
        rtol=1.0e-11,
        atol=1.0e-13,
        dense_output=True,
        max_step=0.002,
    )
    time_ballistic = np.linspace(0.0, 0.45, 512)
    radius_ballistic = solution.sol(time_ballistic)[0]
    acceleration_ballistic = -1.0 / np.square(radius_ballistic)

    phase = np.linspace(0.0, 1.0, 2048, endpoint=False)
    omega = 2.0 * math.pi
    harmonic_radius = 1.0 + 0.05 * np.cos(omega * phase) + 0.01 * np.cos(2.0 * omega * phase)
    harmonic_acceleration = -0.05 * omega**2 * np.cos(omega * phase) - 0.04 * omega**2 * np.cos(2.0 * omega * phase)

    parameters = DERDParameters(0.35, 0.72, 0.58, 0.23)
    derd_values = waveform(
        phase,
        parameters,
        time_law="geometric",
        normalization_grid_size=2048,
    )
    derd_radius = 1.0 + 0.06 * (derd_values - float(np.mean(derd_values)))
    derd_fft = np.fft.rfft(derd_radius)
    frequencies = np.fft.rfftfreq(phase.size, d=1.0 / phase.size)
    derd_acceleration = np.fft.irfft(
        -np.square(2.0 * math.pi * frequencies) * derd_fft,
        n=phase.size,
    )

    pressure_radius = 1.0 + 0.045 * np.cos(omega * phase) + 0.012 * np.sin(2.0 * omega * phase + 0.4)
    pressure_acceleration = -0.045 * omega**2 * np.cos(omega * phase) - 0.048 * omega**2 * np.sin(2.0 * omega * phase + 0.4)

    return (
        _effective_mass_summary(
            "inverse_square_ballistic_segment",
            radius_ballistic,
            acceleration_ballistic,
            periodic=False,
        ),
        _effective_mass_summary(
            "harmonic_breathing_mode",
            harmonic_radius,
            harmonic_acceleration,
            periodic=True,
        ),
        _effective_mass_summary(
            "derd_waveform_interpreted_as_radius",
            derd_radius,
            derd_acceleration,
            periodic=True,
        ),
        _effective_mass_summary(
            "pressure_supported_hydrodynamic_surrogate",
            pressure_radius,
            pressure_acceleration,
            periodic=True,
        ),
    )
