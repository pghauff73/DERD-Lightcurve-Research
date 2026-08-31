"""Phase-18 exact-input-scope reconstruction for an external Fourier anchor.

The external publication states that available OGLE-III and OGLE-IV V-band
light curves were merged, sources with fewer than 50 measurements were
excluded, and final Fourier coefficients were obtained with a simultaneous
cosine-series fit.  It does not publish input-file hashes or the analysis
source code.  Phase 18 therefore distinguishes:

* authoritative current OGLE source reconstruction;
* publication-compatible source scope;
* numerical parameter reproduction;
* exact publication byte/code identity.

Only the first three can be tested here.  This module does not identify a
stellar mechanism, a transparent shell, or any mass scale.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import curve_fit
from scipy.stats import chi2

from .harmonic_extraction import git_blob_sha1_file
from .ogle_catalog import canonical_json_sha256
from .validation_phase12 import sha256_file
from .validation_phase17 import ExternalFourierAnchor

PHASE18_DECISION = (
    "PHASE18_AUTHORITATIVE_OGLEIII_IV_INPUT_SCOPE_RECONSTRUCTED_"
    "PUBLISHED_VECTOR_REPRODUCED_EXACT_PUBLICATION_CODE_AND_BYTE_IDENTITY_UNAVAILABLE"
)

CLASS_PUBLICATION_COMPATIBLE = (
    "PUBLICATION_COMPATIBLE_RECONSTRUCTION_AUTHORITATIVE_INPUT_SCOPE_"
    "EXACT_CODE_AND_PUBLICATION_BYTE_IDENTITY_UNAVAILABLE"
)
CLASS_PARAMETER_MISMATCH = (
    "AUTHORITATIVE_INPUT_SCOPE_RECONSTRUCTED_PUBLISHED_PARAMETER_GATE_FAILED"
)

PARAMETER_LABELS = ("r21", "phi21", "r31", "phi31")


@dataclass(frozen=True, slots=True)
class SourceComponent:
    source_id: str
    survey: str
    url: str
    path: str
    sha256: str
    git_blob_sha1: str
    byte_count: int
    observation_count: int
    first_time: float
    last_time: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "survey": self.survey,
            "url": self.url,
            "path": self.path,
            "sha256": self.sha256,
            "git_blob_sha1": self.git_blob_sha1,
            "byte_count": self.byte_count,
            "observation_count": self.observation_count,
            "first_time": self.first_time,
            "last_time": self.last_time,
        }


@dataclass(frozen=True, slots=True)
class CurveFitInvariantEstimate:
    variant_id: str
    source_scope: str
    weighting: str
    period_mode: str
    covariance_scale: str
    sample_count: int
    reference_epoch: float
    period_days: float
    vector: NDArray[np.float64]
    covariance: NDArray[np.float64]
    amplitudes: NDArray[np.float64]
    phases: NDArray[np.float64]
    residual_rmse_mag: float
    quoted_error_reduced_chi_square: float
    fit_objective_reduced: float
    design_condition_number: float
    curve_fit_parameter_count: int

    def __post_init__(self) -> None:
        vector = np.asarray(self.vector, dtype=np.float64)
        covariance = np.asarray(self.covariance, dtype=np.float64)
        amplitudes = np.asarray(self.amplitudes, dtype=np.float64)
        phases = np.asarray(self.phases, dtype=np.float64)
        if vector.shape != (4,):
            raise ValueError("vector must have shape (4,)")
        if covariance.shape != (4, 4):
            raise ValueError("covariance must have shape (4,4)")
        if amplitudes.shape != (3,) or phases.shape != (3,):
            raise ValueError("three amplitudes and phases are required")
        if not np.all(np.isfinite(vector)) or not np.all(np.isfinite(covariance)):
            raise ValueError("estimate must be finite")
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "amplitudes", amplitudes)
        object.__setattr__(self, "phases", phases)

    @property
    def standard_error(self) -> NDArray[np.float64]:
        return np.sqrt(np.maximum(0.0, np.diag(self.covariance)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "source_scope": self.source_scope,
            "weighting": self.weighting,
            "period_mode": self.period_mode,
            "covariance_scale": self.covariance_scale,
            "sample_count": self.sample_count,
            "reference_epoch": self.reference_epoch,
            "period_days": self.period_days,
            "parameter_order": list(PARAMETER_LABELS),
            "vector": dict(zip(PARAMETER_LABELS, [float(v) for v in self.vector], strict=True)),
            "standard_error": dict(
                zip(PARAMETER_LABELS, [float(v) for v in self.standard_error], strict=True)
            ),
            "covariance": self.covariance.tolist(),
            "amplitudes": self.amplitudes.tolist(),
            "phases": self.phases.tolist(),
            "residual_rmse_mag": self.residual_rmse_mag,
            "quoted_error_reduced_chi_square": self.quoted_error_reduced_chi_square,
            "fit_objective_reduced": self.fit_objective_reduced,
            "design_condition_number": self.design_condition_number,
            "curve_fit_parameter_count": self.curve_fit_parameter_count,
        }


@dataclass(frozen=True, slots=True)
class PublishedVectorAudit:
    variant_id: str
    difference: NDArray[np.float64]
    combined_covariance: NDArray[np.float64]
    marginal_z: NDArray[np.float64]
    mahalanobis_chi_square: float
    degrees_of_freedom: int
    p_value: float
    marginal_pass: bool
    joint_pass: bool

    def __post_init__(self) -> None:
        for name in ("difference", "marginal_z"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (4,):
                raise ValueError(f"{name} must have shape (4,)")
            object.__setattr__(self, name, value)
        covariance = np.asarray(self.combined_covariance, dtype=np.float64)
        if covariance.shape != (4, 4):
            raise ValueError("combined_covariance must have shape (4,4)")
        object.__setattr__(self, "combined_covariance", covariance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "difference_local_minus_published": dict(
                zip(PARAMETER_LABELS, [float(v) for v in self.difference], strict=True)
            ),
            "combined_covariance": self.combined_covariance.tolist(),
            "marginal_z": dict(
                zip(PARAMETER_LABELS, [float(v) for v in self.marginal_z], strict=True)
            ),
            "mahalanobis_chi_square": self.mahalanobis_chi_square,
            "degrees_of_freedom": self.degrees_of_freedom,
            "p_value": self.p_value,
            "marginal_pass": self.marginal_pass,
            "joint_pass": self.joint_pass,
        }


def load_three_column(path: str | Path) -> NDArray[np.float64]:
    source = Path(path)
    values = np.loadtxt(source, dtype=np.float64)
    values = np.atleast_2d(values)
    if values.shape[1] != 3 or values.shape[0] < 1:
        raise ValueError(f"{source}: expected non-empty three-column photometry")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{source}: non-finite photometry")
    if np.any(values[:, 2] <= 0.0):
        raise ValueError(f"{source}: uncertainties must be positive")
    if np.any(np.diff(values[:, 0]) <= 0.0):
        raise ValueError(f"{source}: times must be strictly increasing")
    return values


def verify_source_component(path: str | Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    source = Path(path)
    values = load_three_column(source)
    observed = {
        "sha256": sha256_file(source),
        "git_blob_sha1": git_blob_sha1_file(source),
        "byte_count": source.stat().st_size,
        "observation_count": int(values.shape[0]),
        "first_time": float(values[0, 0]),
        "last_time": float(values[-1, 0]),
    }
    checks = {
        "sha256": observed["sha256"] == str(expected["sha256"]),
        "git_blob_sha1": observed["git_blob_sha1"] == str(expected["git_blob_sha1"]),
        "byte_count": observed["byte_count"] == int(expected["byte_count"]),
        "observation_count": observed["observation_count"] == int(expected["observation_count"]),
        "first_time": math.isclose(observed["first_time"], float(expected["first_time"]), abs_tol=1e-10),
        "last_time": math.isclose(observed["last_time"], float(expected["last_time"]), abs_tol=1e-10),
    }
    return {
        "path": str(source),
        "observed": observed,
        "checks": checks,
        "all_checks_passed": bool(all(checks.values())),
    }


def merge_photometry(*components: NDArray[np.float64]) -> NDArray[np.float64]:
    if not components:
        raise ValueError("at least one source component is required")
    merged = np.concatenate([np.asarray(component, dtype=np.float64) for component in components], axis=0)
    order = np.argsort(merged[:, 0], kind="mergesort")
    merged = merged[order]
    if np.any(np.diff(merged[:, 0]) <= 0.0):
        raise ValueError("merged source contains duplicate or non-increasing times")
    return merged


def _linear_initial(
    time: NDArray[np.float64],
    magnitude: NDArray[np.float64],
    error: NDArray[np.float64],
    *,
    period_days: float,
    weighting: str,
) -> tuple[float, NDArray[np.float64], NDArray[np.float64]]:
    epoch = float(np.min(time))
    phase = (time - epoch) / period_days
    columns: list[NDArray[np.float64]] = [np.ones(time.size, dtype=np.float64)]
    for harmonic in range(1, 4):
        angle = 2.0 * math.pi * harmonic * phase
        columns.extend([np.sin(angle), np.cos(angle)])
    design = np.column_stack(columns)
    if weighting == "unweighted":
        weighted_design = design
        weighted_values = magnitude
    else:
        scale = 1.0 / error
        weighted_design = design * scale[:, None]
        weighted_values = magnitude * scale
    beta, *_ = np.linalg.lstsq(weighted_design, weighted_values, rcond=None)
    amplitudes = np.empty(3, dtype=np.float64)
    phases = np.empty(3, dtype=np.float64)
    for harmonic in range(1, 4):
        sine = float(beta[2 * harmonic - 1])
        cosine = float(beta[2 * harmonic])
        amplitudes[harmonic - 1] = math.hypot(sine, cosine)
        phases[harmonic - 1] = math.atan2(-sine, cosine)
    return float(beta[0]), amplitudes, phases


def _cosine_fixed(
    shifted_time: NDArray[np.float64],
    mean: float,
    a1: float,
    a2: float,
    a3: float,
    p1: float,
    p2: float,
    p3: float,
    *,
    frequency: float,
) -> NDArray[np.float64]:
    return (
        mean
        + a1 * np.cos(2.0 * math.pi * frequency * shifted_time + p1)
        + a2 * np.cos(4.0 * math.pi * frequency * shifted_time + p2)
        + a3 * np.cos(6.0 * math.pi * frequency * shifted_time + p3)
    )


def _cosine_free(
    shifted_time: NDArray[np.float64],
    mean: float,
    frequency: float,
    a1: float,
    a2: float,
    a3: float,
    p1: float,
    p2: float,
    p3: float,
) -> NDArray[np.float64]:
    return _cosine_fixed(
        shifted_time,
        mean,
        a1,
        a2,
        a3,
        p1,
        p2,
        p3,
        frequency=frequency,
    )


def fit_curve_fit_invariants(
    photometry: ArrayLike,
    *,
    variant_id: str,
    source_scope: str,
    center_period_days: float,
    weighting: str = "unweighted",
    period_mode: str = "free",
    relative_period_span: float = 0.001,
) -> CurveFitInvariantEstimate:
    """Fit the publication's simultaneous three-harmonic cosine form.

    ``weighting`` is one of ``unweighted``, ``quoted_relative`` or
    ``quoted_absolute``.  The latter two pass the quoted errors to SciPy's
    ``curve_fit`` with ``absolute_sigma`` false and true respectively.
    """

    values = np.asarray(photometry, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("photometry must be an N x 3 array")
    if weighting not in {"unweighted", "quoted_relative", "quoted_absolute"}:
        raise ValueError("unsupported weighting")
    if period_mode not in {"fixed", "free"}:
        raise ValueError("period_mode must be fixed or free")
    time, magnitude, error = values.T
    if time.size < 8:
        raise ValueError("at least eight measurements are required")
    epoch = float(np.min(time))
    shifted = time - epoch
    mean0, amplitudes0, phases0 = _linear_initial(
        time,
        magnitude,
        error,
        period_days=center_period_days,
        weighting=weighting,
    )
    kwargs: dict[str, Any] = {"maxfev": 200000}
    if weighting != "unweighted":
        kwargs["sigma"] = error
        kwargs["absolute_sigma"] = weighting == "quoted_absolute"

    if period_mode == "free":
        frequency0 = 1.0 / center_period_days
        lower_frequency = 1.0 / (center_period_days * (1.0 + relative_period_span))
        upper_frequency = 1.0 / (center_period_days * (1.0 - relative_period_span))
        initial = np.array([mean0, frequency0, *amplitudes0, *phases0], dtype=np.float64)
        lower = np.array(
            [-np.inf, lower_frequency, 0.0, 0.0, 0.0, -100.0 * math.pi, -100.0 * math.pi, -100.0 * math.pi],
            dtype=np.float64,
        )
        upper = np.array(
            [np.inf, upper_frequency, np.inf, np.inf, np.inf, 100.0 * math.pi, 100.0 * math.pi, 100.0 * math.pi],
            dtype=np.float64,
        )
        parameters, parameter_covariance = curve_fit(
            _cosine_free,
            shifted,
            magnitude,
            p0=initial,
            bounds=(lower, upper),
            **kwargs,
        )
        mean, frequency, a1, a2, a3, p1, p2, p3 = [float(v) for v in parameters]
        period = 1.0 / frequency
        fitted = _cosine_free(shifted, *parameters)
        amplitude_indices = (2, 3, 4)
        phase_indices = (5, 6, 7)
    else:
        frequency = 1.0 / center_period_days

        def model_fixed(
            x: NDArray[np.float64],
            mean: float,
            a1: float,
            a2: float,
            a3: float,
            p1: float,
            p2: float,
            p3: float,
        ) -> NDArray[np.float64]:
            return _cosine_fixed(x, mean, a1, a2, a3, p1, p2, p3, frequency=frequency)

        initial = np.array([mean0, *amplitudes0, *phases0], dtype=np.float64)
        lower = np.array(
            [-np.inf, 0.0, 0.0, 0.0, -100.0 * math.pi, -100.0 * math.pi, -100.0 * math.pi],
            dtype=np.float64,
        )
        upper = np.array(
            [np.inf, np.inf, np.inf, np.inf, 100.0 * math.pi, 100.0 * math.pi, 100.0 * math.pi],
            dtype=np.float64,
        )
        parameters, parameter_covariance = curve_fit(
            model_fixed,
            shifted,
            magnitude,
            p0=initial,
            bounds=(lower, upper),
            **kwargs,
        )
        mean, a1, a2, a3, p1, p2, p3 = [float(v) for v in parameters]
        period = center_period_days
        fitted = model_fixed(shifted, *parameters)
        amplitude_indices = (1, 2, 3)
        phase_indices = (4, 5, 6)

    if min(a1, a2, a3) <= 0.0:
        raise RuntimeError("non-positive harmonic amplitude")
    vector = np.array(
        [
            a2 / a1,
            np.mod(p2 - 2.0 * p1, 2.0 * math.pi),
            a3 / a1,
            np.mod(p3 - 3.0 * p1, 2.0 * math.pi),
        ],
        dtype=np.float64,
    )
    jacobian = np.zeros((4, len(parameters)), dtype=np.float64)
    i1, i2, i3 = amplitude_indices
    j1, j2, j3 = phase_indices
    jacobian[0, i1] = -a2 / (a1 * a1)
    jacobian[0, i2] = 1.0 / a1
    jacobian[1, j1] = -2.0
    jacobian[1, j2] = 1.0
    jacobian[2, i1] = -a3 / (a1 * a1)
    jacobian[2, i3] = 1.0 / a1
    jacobian[3, j1] = -3.0
    jacobian[3, j3] = 1.0
    covariance = jacobian @ np.asarray(parameter_covariance, dtype=np.float64) @ jacobian.T

    residual = magnitude - fitted
    rank = int(len(parameters))
    dof = max(1, time.size - rank)
    quoted_chi_square = float(np.sum(np.square(residual / error)))
    if weighting == "unweighted":
        fit_objective = float(np.sum(np.square(residual))) / dof
        design_weights = np.ones_like(error)
        covariance_scale = "curve_fit_default_residual_scaled"
    else:
        fit_objective = quoted_chi_square / dof
        design_weights = 1.0 / error
        covariance_scale = (
            "curve_fit_quoted_errors_absolute"
            if weighting == "quoted_absolute"
            else "curve_fit_quoted_errors_residual_scaled"
        )
    design_columns: list[NDArray[np.float64]] = [np.ones(time.size, dtype=np.float64)]
    for harmonic in range(1, 4):
        angle = 2.0 * math.pi * harmonic * shifted / period
        design_columns.extend([np.sin(angle), np.cos(angle)])
    design = np.column_stack(design_columns) * design_weights[:, None]

    return CurveFitInvariantEstimate(
        variant_id=variant_id,
        source_scope=source_scope,
        weighting=weighting,
        period_mode=period_mode,
        covariance_scale=covariance_scale,
        sample_count=int(time.size),
        reference_epoch=epoch,
        period_days=float(period),
        vector=vector,
        covariance=covariance,
        amplitudes=np.array([a1, a2, a3], dtype=np.float64),
        phases=np.mod(np.array([p1, p2, p3], dtype=np.float64), 2.0 * math.pi),
        residual_rmse_mag=float(np.sqrt(np.mean(np.square(residual)))),
        quoted_error_reduced_chi_square=quoted_chi_square / dof,
        fit_objective_reduced=fit_objective,
        design_condition_number=float(np.linalg.cond(design)),
        curve_fit_parameter_count=len(parameters),
    )


def compare_to_published(
    estimate: CurveFitInvariantEstimate,
    anchor: ExternalFourierAnchor,
    *,
    marginal_absolute_z_max: float = 2.0,
    joint_alpha: float = 0.05,
) -> PublishedVectorAudit:
    difference = estimate.vector - anchor.vector()
    combined = estimate.covariance + anchor.covariance()
    inverse = np.linalg.pinv(combined, hermitian=True)
    statistic = float(difference @ inverse @ difference)
    dof = int(np.linalg.matrix_rank(combined))
    p_value = float(chi2.sf(statistic, dof))
    standard = np.sqrt(np.maximum(np.finfo(float).tiny, np.diag(combined)))
    marginal_z = difference / standard
    return PublishedVectorAudit(
        variant_id=estimate.variant_id,
        difference=difference,
        combined_covariance=combined,
        marginal_z=marginal_z,
        mahalanobis_chi_square=statistic,
        degrees_of_freedom=dof,
        p_value=p_value,
        marginal_pass=bool(np.all(np.abs(marginal_z) < marginal_absolute_z_max)),
        joint_pass=bool(p_value >= joint_alpha),
    )


def run_method_lattice(
    source_scopes: Mapping[str, NDArray[np.float64]],
    anchor: ExternalFourierAnchor,
) -> tuple[list[CurveFitInvariantEstimate], list[PublishedVectorAudit]]:
    estimates: list[CurveFitInvariantEstimate] = []
    audits: list[PublishedVectorAudit] = []
    for scope_name, photometry in source_scopes.items():
        for weighting in ("unweighted", "quoted_relative", "quoted_absolute"):
            for period_mode in ("fixed", "free"):
                variant_id = f"{scope_name}_{weighting}_{period_mode}"
                estimate = fit_curve_fit_invariants(
                    photometry,
                    variant_id=variant_id,
                    source_scope=scope_name,
                    center_period_days=anchor.period_days,
                    weighting=weighting,
                    period_mode=period_mode,
                )
                estimates.append(estimate)
                audits.append(compare_to_published(estimate, anchor))
    return estimates, audits


def circular_range(values: Sequence[float]) -> float:
    angles = np.asarray(values, dtype=np.float64)
    if angles.size == 0:
        return 0.0
    # The largest empty arc is removed; the remainder is the minimum circular span.
    wrapped = np.sort(np.mod(angles, 2.0 * math.pi))
    gaps = np.diff(np.concatenate([wrapped, wrapped[:1] + 2.0 * math.pi]))
    return float(2.0 * math.pi - np.max(gaps))


def merged_method_spread(estimates: Iterable[CurveFitInvariantEstimate]) -> dict[str, float]:
    rows = [estimate for estimate in estimates if estimate.source_scope == "merged_ogleiii_iv"]
    if not rows:
        raise ValueError("no merged estimates")
    vectors = np.vstack([row.vector for row in rows])
    return {
        "r21_range": float(np.ptp(vectors[:, 0])),
        "phi21_circular_range": circular_range(vectors[:, 1]),
        "r31_range": float(np.ptp(vectors[:, 2])),
        "phi31_circular_range": circular_range(vectors[:, 3]),
        "period_range_days": float(np.ptp([row.period_days for row in rows])),
    }


def add_phase18_graph_edge(
    phase17_graph: Mapping[str, Any],
    *,
    classification: str,
    primary_audit: PublishedVectorAudit,
) -> dict[str, Any]:
    graph = json.loads(json.dumps(dict(phase17_graph)))
    graph.pop("sha256_canonical_json", None)
    nodes = list(graph.get("analysis_nodes", []))
    nodes.append(
        {
            "object_id": "OGLE-LMC-CEP-0002",
            "analysis_version": "phase18_authoritative_ogleiii_iv_curvefit",
            "analysis_kind": "publication_input_scope_reconstruction",
            "research_group_independent": False,
            "observational_source_family": "OGLE-III+IV V-band official files",
            "counts_as_astronomical_denominator_increment": False,
        }
    )
    edges = list(graph.get("edges", []))
    edges.append(
        {
            "object_id": "OGLE-LMC-CEP-0002",
            "source_version": "jurkovic2022_ogle_v_fourier",
            "comparison_version": "phase18_authoritative_ogleiii_iv_curvefit",
            "edge_type": classification,
            "source_scope_matches_publication_description": True,
            "publication_minimum_measurements_met": True,
            "exact_publication_source_byte_identity_known": False,
            "exact_publication_code_available": False,
            "joint_consistency": primary_audit.joint_pass,
            "marginal_consistency": primary_audit.marginal_pass,
            "counts_as_independent_astrophysical_replication": False,
            "counts_as_astronomical_denominator_increment": False,
        }
    )
    graph["analysis_nodes"] = nodes
    graph["edges"] = edges
    graph["analysis_version_count"] = len(nodes)
    graph["external_input_reconstruction_count"] = int(
        sum(1 for edge in edges if edge.get("edge_type") == classification)
    )
    graph["external_independent_replication_count"] = int(
        sum(1 for edge in edges if edge.get("counts_as_independent_astrophysical_replication"))
    )
    graph["phase18_multiplicity_guard"] = {
        "inherited_policy": graph.get("multiplicity_guard"),
        "external_input_reconstruction_does_not_increment_denominator": True,
    }
    graph["sha256_canonical_json"] = canonical_json_sha256(graph)
    return graph
