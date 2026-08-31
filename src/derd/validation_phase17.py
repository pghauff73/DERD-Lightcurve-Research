"""Phase-17 external Fourier-analysis anchor and independence classifier.

This phase introduces an analysis performed by an external research group as a
methodological anchor for one object already present in the DERD development
ledger.  It compares published cosine-series Fourier invariants with a local,
lossless reanalysis of a provenance-frozen V-band subset.

The comparison is intentionally narrower than an astrophysical replication:

* the external group is independent of the DERD implementation;
* both analyses draw from the OGLE survey family;
* the locally available mirror contains 33 observations, whereas the published
  workflow required at least 50 and could merge OGLE-III and OGLE-IV data;
* therefore a consistent result is an external-analysis consistency edge, not
  an independent observing-source replication and not a new denominator item.

Nothing in this module identifies a stellar mechanism, an exterior shell, or a
mass scale.  It validates Fourier-coordinate transport and evidence provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize_scalar
from scipy.stats import chi2

from .harmonic_extraction import git_blob_sha1_file
from .ogle_catalog import canonical_json_sha256
from .validation_phase12 import sha256_file

PHASE17_DECISION = (
    "PHASE17_EXTERNAL_ANALYSIS_ANCHOR_CONSISTENT_PARTIAL_SOURCE_"
    "OVERLAP_INDEPENDENT_ASTROPHYSICAL_REPLICATION_STILL_ABSENT"
)

EDGE_EXTERNAL_CONSISTENT_PARTIAL = "EXTERNAL_ANALYSIS_CONSISTENT_PARTIAL_SOURCE_OVERLAP"
EDGE_EXTERNAL_INCONSISTENT_PARTIAL = "EXTERNAL_ANALYSIS_INCONSISTENT_PARTIAL_SOURCE_OVERLAP"
EDGE_EXTERNAL_FULL_REPLICATION = "EXTERNAL_INDEPENDENT_ASTROPHYSICAL_REPLICATION"


@dataclass(frozen=True, slots=True)
class ExternalFourierAnchor:
    """Published cosine-series Fourier invariants and provenance."""

    object_id: str
    object_type: str
    period_days: float
    r21: float
    r21_error: float
    phi21: float
    phi21_error: float
    r31: float
    r31_error: float
    phi31: float
    phi31_error: float
    citation: str
    doi: str
    arxiv_id: str
    band: str
    method_summary: str
    minimum_measurements: int
    source_scope: str

    def vector(self) -> NDArray[np.float64]:
        return np.array([self.r21, self.phi21, self.r31, self.phi31], dtype=np.float64)

    def covariance(self) -> NDArray[np.float64]:
        errors = np.array(
            [self.r21_error, self.phi21_error, self.r31_error, self.phi31_error],
            dtype=np.float64,
        )
        return np.diag(np.square(errors))

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "period_days": self.period_days,
            "r21": self.r21,
            "r21_error": self.r21_error,
            "phi21": self.phi21,
            "phi21_error": self.phi21_error,
            "r31": self.r31,
            "r31_error": self.r31_error,
            "phi31": self.phi31,
            "phi31_error": self.phi31_error,
            "citation": self.citation,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "band": self.band,
            "method_summary": self.method_summary,
            "minimum_measurements": self.minimum_measurements,
            "source_scope": self.source_scope,
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "ExternalFourierAnchor":
        return cls(
            object_id=str(row["object_id"]),
            object_type=str(row["object_type"]),
            period_days=float(row["period_days"]),
            r21=float(row["r21"]),
            r21_error=float(row["r21_error"]),
            phi21=float(row["phi21"]),
            phi21_error=float(row["phi21_error"]),
            r31=float(row["r31"]),
            r31_error=float(row["r31_error"]),
            phi31=float(row["phi31"]),
            phi31_error=float(row["phi31_error"]),
            citation=str(row["citation"]),
            doi=str(row["doi"]),
            arxiv_id=str(row["arxiv_id"]),
            band=str(row["band"]),
            method_summary=str(row["method_summary"]),
            minimum_measurements=int(row["minimum_measurements"]),
            source_scope=str(row["source_scope"]),
        )


@dataclass(frozen=True, slots=True)
class FourierInvariantEstimate:
    """Local cosine-series estimate with bootstrap covariance."""

    object_id: str
    period_days: float
    period_bootstrap_standard_error_days: float
    reference_epoch: float
    r21: float
    phi21: float
    r31: float
    phi31: float
    covariance: NDArray[np.float64]
    bootstrap_mean: NDArray[np.float64]
    bootstrap_standard_error: NDArray[np.float64]
    bootstrap_percentile_95: NDArray[np.float64]
    sample_count: int
    bootstrap_sample_count: int
    bootstrap_draws: int
    residual_rmse_mag: float
    weighted_reduced_chi_square: float
    design_condition_number: float

    def __post_init__(self) -> None:
        covariance = np.asarray(self.covariance, dtype=np.float64)
        mean = np.asarray(self.bootstrap_mean, dtype=np.float64)
        error = np.asarray(self.bootstrap_standard_error, dtype=np.float64)
        interval = np.asarray(self.bootstrap_percentile_95, dtype=np.float64)
        if covariance.shape != (4, 4):
            raise ValueError("covariance must be 4x4")
        if mean.shape != (4,) or error.shape != (4,) or interval.shape != (2, 4):
            raise ValueError("bootstrap arrays have unexpected shape")
        if not np.all(np.isfinite(covariance)):
            raise ValueError("covariance must be finite")
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "bootstrap_mean", mean)
        object.__setattr__(self, "bootstrap_standard_error", error)
        object.__setattr__(self, "bootstrap_percentile_95", interval)

    def vector(self) -> NDArray[np.float64]:
        return np.array([self.r21, self.phi21, self.r31, self.phi31], dtype=np.float64)

    def as_dict(self) -> dict[str, Any]:
        labels = ("r21", "phi21", "r31", "phi31")
        return {
            "object_id": self.object_id,
            "period_days": self.period_days,
            "period_bootstrap_standard_error_days": self.period_bootstrap_standard_error_days,
            "reference_epoch": self.reference_epoch,
            "r21": self.r21,
            "phi21": self.phi21,
            "r31": self.r31,
            "phi31": self.phi31,
            "covariance_order": list(labels),
            "covariance": self.covariance.tolist(),
            "bootstrap_mean": dict(zip(labels, [float(v) for v in self.bootstrap_mean], strict=True)),
            "bootstrap_standard_error": dict(
                zip(labels, [float(v) for v in self.bootstrap_standard_error], strict=True)
            ),
            "bootstrap_percentile_95": {
                label: [float(self.bootstrap_percentile_95[0, i]), float(self.bootstrap_percentile_95[1, i])]
                for i, label in enumerate(labels)
            },
            "sample_count": self.sample_count,
            "bootstrap_sample_count": self.bootstrap_sample_count,
            "bootstrap_draws": self.bootstrap_draws,
            "residual_rmse_mag": self.residual_rmse_mag,
            "weighted_reduced_chi_square": self.weighted_reduced_chi_square,
            "design_condition_number": self.design_condition_number,
        }


@dataclass(frozen=True, slots=True)
class ExternalAnalysisAudit:
    object_id: str
    local_vector: NDArray[np.float64]
    external_vector: NDArray[np.float64]
    difference: NDArray[np.float64]
    combined_covariance: NDArray[np.float64]
    marginal_z: NDArray[np.float64]
    mahalanobis_chi_square: float
    degrees_of_freedom: int
    p_value: float
    all_marginal_absolute_z_below_two: bool
    joint_consistency_at_5_percent: bool
    external_research_group_independent: bool
    observational_source_independent: bool
    local_source_meets_external_minimum_count: bool
    source_byte_identity_known: bool
    classification: str
    counts_as_independent_astrophysical_replication: bool
    counts_as_astronomical_denominator_increment: bool

    def __post_init__(self) -> None:
        for field in ("local_vector", "external_vector", "difference", "marginal_z"):
            value = np.asarray(getattr(self, field), dtype=np.float64)
            if value.shape != (4,):
                raise ValueError(f"{field} must have shape (4,)")
            object.__setattr__(self, field, value)
        covariance = np.asarray(self.combined_covariance, dtype=np.float64)
        if covariance.shape != (4, 4):
            raise ValueError("combined_covariance must be 4x4")
        object.__setattr__(self, "combined_covariance", covariance)

    def as_dict(self) -> dict[str, Any]:
        labels = ("r21", "phi21", "r31", "phi31")
        return {
            "object_id": self.object_id,
            "parameter_order": list(labels),
            "local_vector": dict(zip(labels, [float(v) for v in self.local_vector], strict=True)),
            "external_vector": dict(zip(labels, [float(v) for v in self.external_vector], strict=True)),
            "difference_local_minus_external": dict(
                zip(labels, [float(v) for v in self.difference], strict=True)
            ),
            "combined_covariance": self.combined_covariance.tolist(),
            "marginal_z": dict(zip(labels, [float(v) for v in self.marginal_z], strict=True)),
            "mahalanobis_chi_square": self.mahalanobis_chi_square,
            "degrees_of_freedom": self.degrees_of_freedom,
            "p_value": self.p_value,
            "all_marginal_absolute_z_below_two": self.all_marginal_absolute_z_below_two,
            "joint_consistency_at_5_percent": self.joint_consistency_at_5_percent,
            "external_research_group_independent": self.external_research_group_independent,
            "observational_source_independent": self.observational_source_independent,
            "local_source_meets_external_minimum_count": self.local_source_meets_external_minimum_count,
            "source_byte_identity_known": self.source_byte_identity_known,
            "classification": self.classification,
            "counts_as_independent_astrophysical_replication": self.counts_as_independent_astrophysical_replication,
            "counts_as_astronomical_denominator_increment": self.counts_as_astronomical_denominator_increment,
            "claim_scope": "external Fourier-coordinate consistency and provenance only",
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
        }


def _design(time: NDArray[np.float64], period_days: float, reference_epoch: float, order: int = 3) -> NDArray[np.float64]:
    phase = np.mod((time - reference_epoch) / period_days, 1.0)
    columns: list[NDArray[np.float64]] = [np.ones(time.size, dtype=np.float64)]
    for harmonic in range(1, order + 1):
        angle = 2.0 * math.pi * harmonic * phase
        columns.append(np.sin(angle))
        columns.append(np.cos(angle))
    return np.column_stack(columns)


def fit_weighted_cosine_series(
    time: ArrayLike,
    magnitude: ArrayLike,
    error: ArrayLike,
    *,
    period_days: float,
    reference_epoch: float | None = None,
    order: int = 3,
) -> dict[str, Any]:
    """Fit a simultaneous sine/cosine series and return cosine invariants.

    The fitted form is ``m=c+sum[a_n sin(n wt)+b_n cos(n wt)]``.  It is
    converted to the external paper's cosine convention through
    ``A_n=hypot(a_n,b_n)`` and ``phi_n=atan2(-a_n,b_n)``.
    """

    t = np.asarray(time, dtype=np.float64).reshape(-1)
    y = np.asarray(magnitude, dtype=np.float64).reshape(-1)
    sigma = np.asarray(error, dtype=np.float64).reshape(-1)
    if t.size < 2 * order + 2 or t.size != y.size or t.size != sigma.size:
        raise ValueError("insufficient or inconsistent observations")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        raise ValueError("time and magnitude must be finite")
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0.0):
        raise ValueError("uncertainties must be finite and positive")
    if not math.isfinite(period_days) or period_days <= 0.0:
        raise ValueError("period_days must be positive")
    epoch = float(np.min(t)) if reference_epoch is None else float(reference_epoch)
    design = _design(t, period_days, epoch, order=order)
    weights = 1.0 / np.square(sigma)
    weighted_design = design * np.sqrt(weights)[:, None]
    weighted_values = y * np.sqrt(weights)
    beta, *_ = np.linalg.lstsq(weighted_design, weighted_values, rcond=None)
    fitted = design @ beta
    residual = y - fitted
    chi_square = float(np.sum(np.square(residual / sigma)))
    rank = int(np.linalg.matrix_rank(weighted_design))
    dof = max(1, t.size - rank)

    amplitudes = np.empty(order, dtype=np.float64)
    phases = np.empty(order, dtype=np.float64)
    for harmonic in range(1, order + 1):
        a = float(beta[2 * harmonic - 1])
        b = float(beta[2 * harmonic])
        amplitudes[harmonic - 1] = math.hypot(a, b)
        phases[harmonic - 1] = np.mod(math.atan2(-a, b), 2.0 * math.pi)
    if amplitudes[0] <= np.finfo(np.float64).eps:
        raise ValueError("fundamental amplitude is degenerate")

    invariants = {
        "r21": float(amplitudes[1] / amplitudes[0]),
        "phi21": float(np.mod(phases[1] - 2.0 * phases[0], 2.0 * math.pi)),
        "r31": float(amplitudes[2] / amplitudes[0]),
        "phi31": float(np.mod(phases[2] - 3.0 * phases[0], 2.0 * math.pi)),
    }
    return {
        "period_days": float(period_days),
        "reference_epoch": epoch,
        "beta": beta,
        "fitted": fitted,
        "residual": residual,
        "amplitudes": amplitudes,
        "phases": phases,
        "invariants": invariants,
        "chi_square": chi_square,
        "weighted_reduced_chi_square": chi_square / dof,
        "residual_rmse_mag": float(np.sqrt(np.mean(np.square(residual)))),
        "design_condition_number": float(np.linalg.cond(weighted_design)),
        "effective_rank": rank,
    }


def optimize_period_generic_fourier(
    time: ArrayLike,
    magnitude: ArrayLike,
    error: ArrayLike,
    *,
    center_period_days: float,
    relative_span: float = 0.001,
    order: int = 3,
) -> float:
    """Select period using only weighted generic Fourier residuals."""

    t = np.asarray(time, dtype=np.float64).reshape(-1)
    y = np.asarray(magnitude, dtype=np.float64).reshape(-1)
    sigma = np.asarray(error, dtype=np.float64).reshape(-1)
    epoch = float(np.min(t))
    lower = center_period_days * (1.0 - relative_span)
    upper = center_period_days * (1.0 + relative_span)

    def objective(period: float) -> float:
        return float(
            fit_weighted_cosine_series(
                t, y, sigma, period_days=period, reference_epoch=epoch, order=order
            )["chi_square"]
        )

    result = minimize_scalar(
        objective,
        method="bounded",
        bounds=(lower, upper),
        options={"xatol": 1.0e-13, "maxiter": 500},
    )
    if not result.success or not math.isfinite(float(result.x)):
        raise RuntimeError("period optimization failed")
    return float(result.x)


def _unwrap_around(values: NDArray[np.float64], center: float) -> NDArray[np.float64]:
    return center + np.angle(np.exp(1j * (values - center)))


def bootstrap_fourier_invariants(
    time: ArrayLike,
    magnitude: ArrayLike,
    error: ArrayLike,
    *,
    object_id: str,
    center_period_days: float,
    draws: int = 2000,
    sample_fraction: float = 0.60,
    seed: int = 1701,
    relative_period_span: float = 0.001,
) -> FourierInvariantEstimate:
    """Run a deterministic 60%-without-replacement bootstrap.

    The sampling fraction follows the external paper's stated uncertainty
    procedure.  Each resample refits the period inside the frozen narrow window.
    """

    t = np.asarray(time, dtype=np.float64).reshape(-1)
    y = np.asarray(magnitude, dtype=np.float64).reshape(-1)
    sigma = np.asarray(error, dtype=np.float64).reshape(-1)
    if not (0.0 < sample_fraction <= 1.0):
        raise ValueError("sample_fraction must be in (0,1]")
    sample_count = max(2 * 3 + 2, int(round(sample_fraction * t.size)))
    if sample_count > t.size:
        raise ValueError("bootstrap sample exceeds observation count")

    best_period = optimize_period_generic_fourier(
        t,
        y,
        sigma,
        center_period_days=center_period_days,
        relative_span=relative_period_span,
        order=3,
    )
    full = fit_weighted_cosine_series(
        t,
        y,
        sigma,
        period_days=best_period,
        reference_epoch=float(np.min(t)),
        order=3,
    )
    full_vector = np.array(
        [
            full["invariants"]["r21"],
            full["invariants"]["phi21"],
            full["invariants"]["r31"],
            full["invariants"]["phi31"],
        ],
        dtype=np.float64,
    )

    rng = np.random.default_rng(seed)
    samples = np.empty((draws, 5), dtype=np.float64)
    lower = center_period_days * (1.0 - relative_period_span)
    upper = center_period_days * (1.0 + relative_period_span)
    epoch = float(np.min(t))
    for draw in range(draws):
        indices = np.sort(rng.choice(t.size, size=sample_count, replace=False))
        bt, by, be = t[indices], y[indices], sigma[indices]

        def objective(period: float) -> float:
            return float(
                fit_weighted_cosine_series(
                    bt, by, be, period_days=period, reference_epoch=epoch, order=3
                )["chi_square"]
            )

        result = minimize_scalar(
            objective,
            method="bounded",
            bounds=(lower, upper),
            options={"xatol": 1.0e-11, "maxiter": 250},
        )
        period = float(result.x)
        fitted = fit_weighted_cosine_series(
            bt, by, be, period_days=period, reference_epoch=epoch, order=3
        )
        inv = fitted["invariants"]
        samples[draw] = [period, inv["r21"], inv["phi21"], inv["r31"], inv["phi31"]]

    samples[:, 2] = _unwrap_around(samples[:, 2], full_vector[1])
    samples[:, 4] = _unwrap_around(samples[:, 4], full_vector[3])
    vectors = samples[:, 1:]
    covariance = np.cov(vectors, rowvar=False, ddof=1)
    standard_error = np.std(vectors, axis=0, ddof=1)
    interval = np.percentile(vectors, [2.5, 97.5], axis=0)
    period_standard_error = float(np.std(samples[:, 0], ddof=1))

    return FourierInvariantEstimate(
        object_id=object_id,
        period_days=best_period,
        period_bootstrap_standard_error_days=period_standard_error,
        reference_epoch=epoch,
        r21=float(full_vector[0]),
        phi21=float(full_vector[1]),
        r31=float(full_vector[2]),
        phi31=float(full_vector[3]),
        covariance=covariance,
        bootstrap_mean=np.mean(vectors, axis=0),
        bootstrap_standard_error=standard_error,
        bootstrap_percentile_95=interval,
        sample_count=int(t.size),
        bootstrap_sample_count=sample_count,
        bootstrap_draws=draws,
        residual_rmse_mag=float(full["residual_rmse_mag"]),
        weighted_reduced_chi_square=float(full["weighted_reduced_chi_square"]),
        design_condition_number=float(full["design_condition_number"]),
    )


def compare_external_anchor(
    local: FourierInvariantEstimate,
    external: ExternalFourierAnchor,
    *,
    external_research_group_independent: bool = True,
    observational_source_independent: bool = False,
    source_byte_identity_known: bool = False,
) -> ExternalAnalysisAudit:
    if local.object_id != external.object_id:
        raise ValueError("local and external object identities differ")
    local_vector = local.vector()
    external_vector = external.vector()
    difference = local_vector - external_vector
    combined = local.covariance + external.covariance()
    inverse = np.linalg.pinv(combined, hermitian=True)
    statistic = float(difference @ inverse @ difference)
    dof = int(np.linalg.matrix_rank(combined))
    p_value = float(chi2.sf(statistic, dof))
    standard = np.sqrt(np.diag(combined))
    marginal_z = difference / standard
    marginal_pass = bool(np.all(np.abs(marginal_z) < 2.0))
    joint_pass = bool(p_value >= 0.05)
    count_pass = local.sample_count >= external.minimum_measurements

    full_independent = (
        external_research_group_independent
        and observational_source_independent
        and source_byte_identity_known
        and count_pass
        and marginal_pass
        and joint_pass
    )
    if full_independent:
        classification = EDGE_EXTERNAL_FULL_REPLICATION
    elif marginal_pass and joint_pass:
        classification = EDGE_EXTERNAL_CONSISTENT_PARTIAL
    else:
        classification = EDGE_EXTERNAL_INCONSISTENT_PARTIAL

    return ExternalAnalysisAudit(
        object_id=local.object_id,
        local_vector=local_vector,
        external_vector=external_vector,
        difference=difference,
        combined_covariance=combined,
        marginal_z=marginal_z,
        mahalanobis_chi_square=statistic,
        degrees_of_freedom=dof,
        p_value=p_value,
        all_marginal_absolute_z_below_two=marginal_pass,
        joint_consistency_at_5_percent=joint_pass,
        external_research_group_independent=external_research_group_independent,
        observational_source_independent=observational_source_independent,
        local_source_meets_external_minimum_count=count_pass,
        source_byte_identity_known=source_byte_identity_known,
        classification=classification,
        counts_as_independent_astrophysical_replication=full_independent,
        counts_as_astronomical_denominator_increment=False,
    )


def verify_source(
    path: str | Path,
    *,
    expected_sha256: str,
    expected_git_blob_sha1: str,
    expected_bytes: int,
    expected_observations: int,
) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    byte_count = source.stat().st_size
    observation_count = sum(1 for line in source.read_text(encoding="utf-8").splitlines() if line.strip())
    sha256 = sha256_file(source)
    blob = git_blob_sha1_file(source)
    checks = {
        "sha256": sha256 == expected_sha256,
        "git_blob_sha1": blob == expected_git_blob_sha1,
        "byte_count": byte_count == expected_bytes,
        "observation_count": observation_count == expected_observations,
    }
    return {
        "path": str(source),
        "sha256": sha256,
        "git_blob_sha1": blob,
        "byte_count": byte_count,
        "observation_count": observation_count,
        "checks": checks,
        "all_checks_passed": bool(all(checks.values())),
    }


def extend_reproducibility_graph(
    phase16_graph: Mapping[str, Any],
    audit: ExternalAnalysisAudit,
    *,
    external_anchor_id: str,
    local_analysis_id: str,
) -> dict[str, Any]:
    graph = json.loads(json.dumps(dict(phase16_graph)))
    graph.pop("sha256_canonical_json", None)
    nodes = list(graph.get("analysis_nodes", []))
    nodes.extend(
        [
            {
                "object_id": audit.object_id,
                "analysis_version": external_anchor_id,
                "analysis_kind": "external_published_fourier_anchor",
                "research_group_independent": True,
                "observational_source_family": "OGLE V-band",
            },
            {
                "object_id": audit.object_id,
                "analysis_version": local_analysis_id,
                "analysis_kind": "local_partial_source_fourier_reanalysis",
                "research_group_independent": False,
                "observational_source_family": "OGLE V-band mirror",
            },
        ]
    )
    edge = {
        "object_id": audit.object_id,
        "source_version": external_anchor_id,
        "comparison_version": local_analysis_id,
        "same_observational_source": False,
        "overlapping_observational_source_family": True,
        "same_scientific_configuration": False,
        "scientific_match": audit.joint_consistency_at_5_percent,
        "exchange_match": False,
        "stage_match": None,
        "disposition_match": None,
        "maximum_harmonic_snr_absolute_difference": None,
        "screen_score_difference": None,
        "threshold_difference": None,
        "classification": audit.classification,
        "counts_as_external_analysis_consistency": audit.classification == EDGE_EXTERNAL_CONSISTENT_PARTIAL,
        "counts_as_independent_astrophysical_replication": audit.counts_as_independent_astrophysical_replication,
        "counts_as_astronomical_denominator_increment": False,
    }
    edges = list(graph.get("edges", []))
    edges.append(edge)
    graph["analysis_nodes"] = nodes
    graph["edges"] = edges
    graph["analysis_version_count"] = len(nodes)
    graph["duplicate_analysis_inflation_prevented"] = len(nodes) - int(graph["unique_object_denominator"])
    graph["external_analysis_consistency_count"] = sum(
        row.get("classification") == EDGE_EXTERNAL_CONSISTENT_PARTIAL for row in edges
    )
    graph["external_independent_replication_count"] = sum(
        bool(row.get("counts_as_independent_astrophysical_replication")) for row in edges
    )
    graph["multiplicity_guard"] = (
        "External publications and local reanalyses of the same astronomical identity do not increase the "
        "astronomical denominator. Only an independent source-and-analysis replication may count as an "
        "independent astrophysical edge, and even that does not create a new object identity."
    )
    graph["phase17_external_anchor"] = audit.as_dict()
    graph["certificate"] = "NOT_A_PHYSICAL_CLAIM_CERTIFICATE"
    graph["claim_scope"] = "Fourier-coordinate consistency, analysis independence, and source independence"
    graph["sha256_canonical_json"] = canonical_json_sha256(graph)
    return graph


def load_external_anchor(path: str | Path) -> ExternalFourierAnchor:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("external anchor must be a JSON object")
    expected = payload.get("sha256_canonical_json")
    body = {key: value for key, value in payload.items() if key != "sha256_canonical_json"}
    if expected and canonical_json_sha256(body) != expected:
        raise ValueError("external anchor canonical hash mismatch")
    return ExternalFourierAnchor.from_mapping(body)
