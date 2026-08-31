"""Phase-19 blind external computational-replication infrastructure.

Phase 19 packages a frozen DERD computational challenge for execution by an
independent operator.  The public kit contains opaque synthetic controls and
three blinded, derived observational harmonic-exchange records.  The expected
scientific outputs and keyed commitment secret are deliberately kept outside
that public kit.

A local clean-room process may validate packaging and portability, but it is
*not* an external replication.  No result in this module identifies a unique
stellar mechanism, a transparent shell, or any stellar mass scale.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import platform
import secrets
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .fitting import fit_waveform
from .harmonic_evidence import fit_signed_harmonics
from .harmonic_exchange import (
    CanonicalHarmonicSeries,
    read_harmonic_exchange,
    record_sha256,
    write_harmonic_exchange,
)
from .harmonic_screen import HarmonicScreenResult, screen_harmonics
from .model import TimeLaw, waveform
from .ogle_catalog import canonical_json_sha256
from .parameters import DERDParameters
from .recurrence_uncertainty import propagate_recurrence_uncertainty
from .validation_phase12 import sha256_file

PHASE19_IMPLEMENTATION_ID = "DERD-v1.9-phase19-external-group-replay-kit"
PHASE19_PROTOCOL_ID = "DERD-PHASE19-EXTERNAL-GROUP-REPLAY-1.0"
PHASE19_KIT_ID = "DERD-PHASE19-BLIND-REPLICATION-KIT-1.0"
PHASE19_DECISION = (
    "PHASE19_EXTERNAL_REPLICATION_KIT_SEALED_LOCAL_CLEANROOM_CONTROL_PASSED_"
    "EXTERNAL_GROUP_SUBMISSION_PENDING"
)
PHASE19_CLASSIFICATION = (
    "EXTERNAL_REPLICATION_READY_INTERNAL_CLEANROOM_VALIDATED_"
    "NO_EXTERNAL_REPLICATION_EDGE_YET"
)

PUBLIC_TASK_TYPES = frozenset({"synthetic_photometry", "observational_exchange"})
DISQUALIFYING_STRUCTURAL_FLAGS = frozenset(
    {
        "RECURRENCE_ILL_CONDITIONED",
        "ROOT_OUTSIDE_PHYSICAL_Q_DOMAIN",
        "RESIDUE_SIGN_CONSTRAINT_FAILED",
        "RESIDUE_PHASE_CONSTRAINT_WEAK",
        "AMPLITUDE_RATIO_EXTREME",
    }
)


@dataclass(frozen=True, slots=True)
class Phase19NumericalTolerance:
    absolute: float = 2.0e-7
    relative: float = 2.0e-6

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Phase19TaskResult:
    task_id: str
    task_type: str
    input_sha256: str
    projection: Mapping[str, Any]
    projection_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "input_sha256": self.input_sha256,
            "projection": dict(self.projection),
            "projection_sha256": self.projection_sha256,
        }


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def keyed_answer_commitment(answer_key: Mapping[str, Any], secret_key: bytes) -> str:
    if len(secret_key) < 32:
        raise ValueError("the commitment key must contain at least 32 bytes")
    return hmac.new(secret_key, canonical_bytes(answer_key), hashlib.sha256).hexdigest()


def verify_answer_commitment(
    answer_key: Mapping[str, Any], secret_key: bytes, expected_commitment: str
) -> bool:
    actual = keyed_answer_commitment(answer_key, secret_key)
    return hmac.compare_digest(actual, expected_commitment)


def _task_seed(base_seed: int, task_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{task_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _irregular_time_grid(
    *, n: int, period: float, cycles: float, seed: int
) -> NDArray[np.float64]:
    if n < 64 or period <= 0.0 or cycles <= 2.0:
        raise ValueError("invalid synthetic cadence configuration")
    rng = np.random.default_rng(seed)
    time = np.sort(rng.uniform(0.0, period * cycles, size=n))
    # A deterministic seasonal gap makes the control less toy-like.
    mask = np.mod(time / period, 9.0) > 1.25
    filtered = time[mask]
    if filtered.size < n:
        extra = np.sort(rng.uniform(0.0, period * cycles, size=n - filtered.size))
        time = np.sort(np.concatenate((filtered, extra)))[:n]
    else:
        time = filtered[:n]
    return np.asarray(time, dtype=np.float64)


def _generic_fourier_null(
    phase: NDArray[np.float64], *, seed: int
) -> NDArray[np.float64]:
    rng = np.random.default_rng(seed)
    amplitudes = np.array([0.46, 0.23, 0.18, 0.13, 0.11, 0.08, 0.07, 0.05])
    phases = rng.uniform(-math.pi, math.pi, size=amplitudes.size)
    values = np.zeros_like(phase)
    for harmonic, (amplitude, angle) in enumerate(
        zip(amplitudes, phases, strict=True), start=1
    ):
        values += amplitude * np.cos(2.0 * math.pi * harmonic * phase + angle)
    values -= np.min(values)
    span = float(np.ptp(values))
    return values / span


def _scrambled_derd_null(
    phase: NDArray[np.float64], *, seed: int
) -> NDArray[np.float64]:
    base = waveform(
        np.linspace(0.0, 1.0, 4096, endpoint=False),
        DERDParameters(0.58, 0.21, 0.73, 0.67),
        time_law=TimeLaw.GEOMETRIC,
    )
    fft = np.fft.rfft(base - np.mean(base))
    rng = np.random.default_rng(seed)
    order = min(8, fft.size - 1)
    phases = rng.uniform(-math.pi, math.pi, size=order)
    values = np.zeros_like(phase)
    for harmonic in range(1, order + 1):
        amplitude = 2.0 * abs(fft[harmonic]) / base.size
        values += amplitude * np.cos(2.0 * math.pi * harmonic * phase + phases[harmonic - 1])
    values -= np.min(values)
    return values / float(np.ptp(values))


def create_synthetic_control(
    *,
    task_id: str,
    role: str,
    output_path: str | Path,
    period_days: float,
    observation_count: int,
    seed: int,
    parameters: DERDParameters | None = None,
) -> dict[str, Any]:
    if role not in {"derd_positive", "generic_fourier_null", "phase_scrambled_null"}:
        raise ValueError(f"unsupported synthetic role {role!r}")
    time = _irregular_time_grid(
        n=observation_count,
        period=period_days,
        cycles=46.0,
        seed=seed,
    )
    epoch = float(time[0])
    phase = np.mod((time - epoch) / period_days, 1.0)
    if role == "derd_positive":
        if parameters is None:
            raise ValueError("positive control requires DERD parameters")
        clean = waveform(phase, parameters, time_law=TimeLaw.GEOMETRIC)
    elif role == "generic_fourier_null":
        clean = _generic_fourier_null(phase, seed=seed + 1)
    else:
        clean = _scrambled_derd_null(phase, seed=seed + 1)
    rng = np.random.default_rng(seed + 2)
    error = 0.009 + 0.004 * rng.random(time.size)
    observed = clean + rng.normal(0.0, error)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(target, np.column_stack((time, observed, error)), fmt=["%.10f", "%.12f", "%.12f"])
    return {
        "task_id": task_id,
        "task_type": "synthetic_photometry",
        "input_path": target.name,
        "input_sha256": sha256_file(target),
        "period_days": float(period_days),
        "reference_epoch": epoch,
        "observation_count": int(time.size),
        "harmonic_order": 8,
        "fit_harmonics": 4,
        "ridge": 1.0e-4,
        "propagation_draws": 384,
        "propagation_seed": _task_seed(seed, task_id),
        "direct_fit": {
            "enabled": True,
            "starts": 4,
            "seed": _task_seed(seed + 99, task_id),
            "max_function_evaluations": 220,
        },
    }


def blind_observational_exchange(
    *, source_path: str | Path, task_id: str, output_path: str | Path
) -> dict[str, Any]:
    series = read_harmonic_exchange(source_path)
    metadata = dict(series.metadata or {})
    metadata.update(
        {
            "phase19_blinded_control": True,
            "original_object_id_withheld": True,
            "original_source_locator_withheld": True,
        }
    )
    blinded = CanonicalHarmonicSeries(
        object_id=task_id,
        fundamental_frequency=series.fundamental_frequency,
        reference_epoch=series.reference_epoch,
        time_unit=series.time_unit,
        value_unit=series.value_unit,
        sine_coefficients=series.sine_coefficients,
        cosine_coefficients=series.cosine_coefficients,
        source_locator=f"phase19:blinded-derived-control:{task_id}",
        source_sha256=series.source_sha256,
        intercept=series.intercept,
        coefficient_covariance=series.coefficient_covariance,
        metadata=metadata,
    )
    target = Path(output_path)
    digest = write_harmonic_exchange(target, blinded)
    return {
        "task_id": task_id,
        "task_type": "observational_exchange",
        "input_path": target.name,
        "input_sha256": digest,
        "harmonic_count": blinded.harmonic_count,
        "fit_harmonics": 4,
        "propagation_draws": 512,
        "propagation_seed": _task_seed(2026082419, task_id),
        "direct_fit": {"enabled": False},
    }


def build_public_tasks(
    *, root: str | Path, public_input_dir: str | Path
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Create opaque task inputs and return tasks plus private origin mapping."""

    repository = Path(root)
    output = Path(public_input_dir)
    output.mkdir(parents=True, exist_ok=True)
    task_specs = (
        (
            "P19-7A31F2",
            "derd_positive",
            0.7421,
            336,
            202608241901,
            DERDParameters(0.24, 0.68, 0.62, 0.29),
        ),
        (
            "P19-C91D44",
            "generic_fourier_null",
            1.1387,
            352,
            202608241902,
            None,
        ),
        (
            "P19-5E08B7",
            "derd_positive",
            0.4932,
            384,
            202608241903,
            DERDParameters(0.71, 0.32, 0.91, 0.73),
        ),
        (
            "P19-A4F663",
            "phase_scrambled_null",
            0.8814,
            368,
            202608241904,
            None,
        ),
    )
    tasks: list[dict[str, Any]] = []
    origin: dict[str, str] = {}
    for task_id, role, period, count, seed, parameters in task_specs:
        task = create_synthetic_control(
            task_id=task_id,
            role=role,
            output_path=output / f"{task_id}.dat",
            period_days=period,
            observation_count=count,
            seed=seed,
            parameters=parameters,
        )
        tasks.append(task)
        origin[task_id] = role

    exchanges = (
        (
            "P19-3BD812",
            repository / "artifacts/phase08/harmonic_exchange/OGLE-LMC-CEP-0002.json",
            "OGLE-LMC-CEP-0002",
        ),
        (
            "P19-E2710C",
            repository / "artifacts/phase11/harmonic_exchange/OGLE-LMC-CEP-0004.json",
            "OGLE-LMC-CEP-0004",
        ),
        (
            "P19-94C05A",
            repository / "artifacts/phase08/harmonic_exchange/OGLE-LMC-RRLYR-00001.json",
            "OGLE-LMC-RRLYR-00001",
        ),
    )
    for task_id, source, object_id in exchanges:
        task = blind_observational_exchange(
            source_path=source,
            task_id=task_id,
            output_path=output / f"{task_id}.json",
        )
        tasks.append(task)
        origin[task_id] = object_id
    return tasks, origin


def _load_photometry(path: str | Path) -> NDArray[np.float64]:
    array = np.loadtxt(path, dtype=np.float64)
    array = np.atleast_2d(array)
    if array.shape[1] != 3 or array.shape[0] < 32:
        raise ValueError("replication photometry must contain at least 32 three-column rows")
    if not np.all(np.isfinite(array)) or np.any(array[:, 2] <= 0.0):
        raise ValueError("replication photometry contains invalid values")
    if np.any(np.diff(array[:, 0]) <= 0.0):
        raise ValueError("replication times must be strictly increasing")
    return array


def _screen_projection(
    series: CanonicalHarmonicSeries,
    *,
    fit_harmonics: int,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    snr = None
    metadata = dict(series.metadata or {})
    if isinstance(metadata.get("coefficient_snr"), list):
        snr = np.asarray(metadata["coefficient_snr"], dtype=np.float64)
    screen: HarmonicScreenResult = screen_harmonics(
        series.complex_coefficients,
        fit_harmonics=fit_harmonics,
        minimum_forecast_harmonics=2,
        minimum_harmonic_snr=None,
        coefficient_snr=snr,
    )
    propagation = propagate_recurrence_uncertainty(
        series,
        fit_harmonics=fit_harmonics,
        minimum_forecast_harmonics=2,
        score_threshold=None,
        draws=draws,
        seed=seed,
    )
    candidate = screen.candidate
    structural_pass = not bool(set(screen.flags).intersection(DISQUALIFYING_STRUCTURAL_FLAGS))
    return {
        "harmonic_count": series.harmonic_count,
        "series_record_sha256": record_sha256(series),
        "sine_coefficients": [float(v) for v in series.sine_coefficients],
        "cosine_coefficients": [float(v) for v in series.cosine_coefficients],
        "coefficient_covariance_sha256": (
            None
            if series.coefficient_covariance is None
            else hashlib.sha256(
                np.asarray(series.coefficient_covariance, dtype="<f8").tobytes(order="C")
            ).hexdigest()
        ),
        "screen": {
            "score": float(screen.score),
            "evidence_level": screen.evidence_level,
            "flags": list(screen.flags),
            "structural_pass": structural_pass,
            "recurrence_system_condition_number": float(
                screen.recurrence.system_condition_number
            ),
            "unconstrained_forecast_residual": (
                None
                if screen.unconstrained_forecast_residual is None
                else float(screen.unconstrained_forecast_residual)
            ),
            "candidate_parameters": candidate.parameters.as_dict(),
            "candidate_total_score": float(candidate.total_score),
            "candidate_forecast_residual": (
                None
                if candidate.forecast_residual is None
                else float(candidate.forecast_residual)
            ),
        },
        "propagation": {
            "requested_draws": propagation.requested_draws,
            "successful_draws": propagation.successful_draws,
            "numerical_failure_fraction": propagation.numerical_failure_fraction,
            "structural_pass_fraction": propagation.structural_pass_fraction,
            "score_quantiles": propagation.score_quantiles,
            "forecast_residual_quantiles": propagation.forecast_residual_quantiles,
            "flag_counts": propagation.flag_counts,
            "seed": propagation.seed,
        },
    }


def evaluate_task(task: Mapping[str, Any], input_path: str | Path) -> Phase19TaskResult:
    task_id = str(task["task_id"])
    task_type = str(task["task_type"])
    if task_type not in PUBLIC_TASK_TYPES:
        raise ValueError(f"unsupported task_type {task_type!r}")
    source = Path(input_path)
    digest = sha256_file(source)
    if digest != str(task["input_sha256"]):
        raise ValueError(f"{task_id}: input SHA-256 mismatch")
    if task_type == "synthetic_photometry":
        data = _load_photometry(source)
        period = float(task["period_days"])
        epoch = float(task["reference_epoch"])
        fit = fit_signed_harmonics(
            data[:, 0],
            data[:, 1],
            data[:, 2],
            period=period,
            reference_epoch=epoch,
            order=int(task["harmonic_order"]),
            ridge=float(task["ridge"]),
        )
        series = fit.to_exchange(
            object_id=task_id,
            time_unit="days",
            source_locator=f"phase19:{task_id}",
            source_sha256=digest,
            value_unit="normalized_flux",
            metadata={"phase19_task": True},
        )
        projection = _screen_projection(
            series,
            fit_harmonics=int(task["fit_harmonics"]),
            draws=int(task["propagation_draws"]),
            seed=int(task["propagation_seed"]),
        )
        projection["coefficient_snr"] = [float(v) for v in fit.coefficient_snr]
        projection["fit_diagnostics"] = {
            "sample_count": fit.sample_count,
            "residual_rmse": fit.residual_rmse,
            "reduced_chi_square": fit.reduced_chi_square,
            "design_condition_number": fit.design_condition_number,
            "normal_condition_number": fit.normal_condition_number,
            "effective_rank": fit.effective_rank,
        }
        direct = dict(task.get("direct_fit") or {})
        if bool(direct.get("enabled", False)):
            phase = np.mod((data[:, 0] - epoch) / period, 1.0)
            weights = 1.0 / np.square(data[:, 2])
            direct_results: dict[str, Any] = {}
            for law in (TimeLaw.GEOMETRIC, TimeLaw.KEPLER):
                result = fit_waveform(
                    phase,
                    data[:, 1],
                    time_law=law,
                    weights=weights,
                    starts=int(direct["starts"]),
                    seed=int(direct["seed"]) + (0 if law is TimeLaw.GEOMETRIC else 1),
                    max_function_evaluations=int(direct["max_function_evaluations"]),
                    normalize_target=True,
                    align_peak=False,
                )
                direct_results[law.value] = {
                    "parameters": result.parameters.as_dict(),
                    "rmse": float(result.metrics["rmse"]),
                    "mae": float(result.metrics["mae"]),
                    "r_squared": float(result.metrics["r_squared"]),
                    "jacobian_condition_number": float(result.jacobian_condition_number),
                    "success": bool(result.success),
                }
            projection["direct_fit"] = direct_results
    else:
        series = read_harmonic_exchange(source)
        if series.object_id != task_id:
            raise ValueError(f"{task_id}: blinded harmonic-exchange object mismatch")
        projection = _screen_projection(
            series,
            fit_harmonics=int(task["fit_harmonics"]),
            draws=int(task["propagation_draws"]),
            seed=int(task["propagation_seed"]),
        )
        metadata = dict(series.metadata or {})
        projection["coefficient_snr"] = [
            float(v) for v in metadata.get("coefficient_snr", [])
        ]
    projection_sha = canonical_sha256(projection)
    return Phase19TaskResult(
        task_id=task_id,
        task_type=task_type,
        input_sha256=digest,
        projection=projection,
        projection_sha256=projection_sha,
    )


def environment_manifest(*, wheel_sha256: str | None = None) -> dict[str, Any]:
    import scipy

    try:
        from . import __version__
    except ImportError:  # pragma: no cover
        __version__ = "unknown"
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "derd_version": __version__,
        "wheel_sha256": wheel_sha256,
        "pid": os.getpid(),
    }


def build_submission(
    *,
    kit_root: str | Path,
    operator_id: str,
    organization: str,
    wheel_sha256: str | None = None,
) -> dict[str, Any]:
    kit = Path(kit_root)
    manifest = load_json(kit / "tasks/task_manifest.json")
    seal = load_json(kit / "tasks/task_manifest.seal.json")
    manifest_copy = dict(manifest)
    expected_manifest_digest = manifest_copy.pop("sha256_canonical_json", None)
    observed_manifest_digest = canonical_json_sha256(manifest_copy)
    if expected_manifest_digest != observed_manifest_digest:
        raise ValueError("task manifest self-digest failed")
    if seal.get("sha256_canonical_json") != observed_manifest_digest:
        raise ValueError("task manifest seal failed")
    results: list[dict[str, Any]] = []
    for task in manifest["tasks"]:
        result = evaluate_task(task, kit / "inputs" / task["input_path"])
        results.append(result.as_dict())
    payload: dict[str, Any] = {
        "submission_schema": "DERD-PHASE19-EXTERNAL-SUBMISSION-1.0",
        "kit_id": manifest["kit_id"],
        "task_manifest_sha256": observed_manifest_digest,
        "operator": {
            "operator_id": operator_id.strip(),
            "organization": organization.strip(),
            "attests_no_pre_submission_answer_key_access": True,
            "attests_independent_command_execution": True,
        },
        "environment": environment_manifest(wheel_sha256=wheel_sha256),
        "task_results": results,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    if not payload["operator"]["operator_id"] or not payload["operator"]["organization"]:
        raise ValueError("operator_id and organization are required")
    payload["submission_sha256"] = canonical_sha256(payload)
    return payload


def verify_submission_self_hash(submission: Mapping[str, Any]) -> bool:
    candidate = dict(submission)
    expected = str(candidate.pop("submission_sha256", ""))
    return hmac.compare_digest(canonical_sha256(candidate), expected)


def _walk_compare(
    expected: Any,
    actual: Any,
    *,
    path: str,
    tolerance: Phase19NumericalTolerance,
    mismatches: list[dict[str, Any]],
) -> None:
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is not actual:
            mismatches.append({"path": path, "expected": expected, "actual": actual})
        return
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        left = float(expected)
        right = float(actual)
        if not math.isfinite(left) or not math.isfinite(right):
            if not (math.isnan(left) and math.isnan(right)) and left != right:
                mismatches.append({"path": path, "expected": expected, "actual": actual})
            return
        allowance = tolerance.absolute + tolerance.relative * max(abs(left), abs(right), 1.0)
        if abs(left - right) > allowance:
            mismatches.append(
                {
                    "path": path,
                    "expected": left,
                    "actual": right,
                    "absolute_difference": abs(left - right),
                    "allowance": allowance,
                }
            )
        return
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for missing in sorted(expected_keys - actual_keys):
            mismatches.append({"path": f"{path}.{missing}", "error": "missing"})
        for extra in sorted(actual_keys - expected_keys):
            mismatches.append({"path": f"{path}.{extra}", "error": "unexpected"})
        for key in sorted(expected_keys & actual_keys):
            _walk_compare(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
                tolerance=tolerance,
                mismatches=mismatches,
            )
        return
    if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)) and isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
        if len(expected) != len(actual):
            mismatches.append(
                {"path": path, "expected_length": len(expected), "actual_length": len(actual)}
            )
            return
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            _walk_compare(
                left,
                right,
                path=f"{path}[{index}]",
                tolerance=tolerance,
                mismatches=mismatches,
            )
        return
    if expected != actual:
        mismatches.append({"path": path, "expected": expected, "actual": actual})


def verify_submission_against_answer_key(
    *,
    submission: Mapping[str, Any],
    answer_key: Mapping[str, Any],
    secret_key: bytes,
    public_commitment: str,
    tolerance: Phase19NumericalTolerance | None = None,
) -> dict[str, Any]:
    active_tolerance = Phase19NumericalTolerance() if tolerance is None else tolerance
    commitment_ok = verify_answer_commitment(answer_key, secret_key, public_commitment)
    self_hash_ok = verify_submission_self_hash(submission)
    expected_by_id = {row["task_id"]: row for row in answer_key["tasks"]}
    actual_by_id = {row["task_id"]: row for row in submission.get("task_results", [])}
    task_audits: list[dict[str, Any]] = []
    for task_id in sorted(set(expected_by_id) | set(actual_by_id)):
        if task_id not in expected_by_id:
            task_audits.append({"task_id": task_id, "passed": False, "error": "unexpected task"})
            continue
        if task_id not in actual_by_id:
            task_audits.append({"task_id": task_id, "passed": False, "error": "missing task"})
            continue
        expected = expected_by_id[task_id]
        actual = actual_by_id[task_id]
        mismatches: list[dict[str, Any]] = []
        if expected["input_sha256"] != actual.get("input_sha256"):
            mismatches.append(
                {
                    "path": "input_sha256",
                    "expected": expected["input_sha256"],
                    "actual": actual.get("input_sha256"),
                }
            )
        _walk_compare(
            expected["projection"],
            actual.get("projection"),
            path="projection",
            tolerance=active_tolerance,
            mismatches=mismatches,
        )
        task_audits.append(
            {
                "task_id": task_id,
                "control_role": expected["control_role"],
                "passed": not mismatches,
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
            }
        )
    all_tasks_passed = bool(task_audits) and all(row["passed"] for row in task_audits)
    operator = dict(submission.get("operator") or {})
    attestation_ok = bool(
        operator.get("attests_no_pre_submission_answer_key_access")
        and operator.get("attests_independent_command_execution")
    )
    return {
        "verification_schema": "DERD-PHASE19-SUBMISSION-VERIFICATION-1.0",
        "commitment_verified": commitment_ok,
        "submission_self_hash_verified": self_hash_ok,
        "operator_attestation_present": attestation_ok,
        "tolerance": active_tolerance.as_dict(),
        "task_count_expected": len(expected_by_id),
        "task_count_submitted": len(actual_by_id),
        "task_audits": task_audits,
        "all_tasks_passed": all_tasks_passed,
        "scientific_projection_reproduced": bool(
            commitment_ok and self_hash_ok and attestation_ok and all_tasks_passed
        ),
        "external_independence_not_established_by_numeric_match_alone": True,
    }


def build_answer_key(
    *,
    task_manifest: Mapping[str, Any],
    kit_input_dir: str | Path,
    private_origin: Mapping[str, str],
) -> dict[str, Any]:
    inputs = Path(kit_input_dir)
    tasks: list[dict[str, Any]] = []
    for task in task_manifest["tasks"]:
        result = evaluate_task(task, inputs / task["input_path"])
        tasks.append(
            {
                "task_id": result.task_id,
                "control_role": str(private_origin[result.task_id]),
                "task_type": result.task_type,
                "input_sha256": result.input_sha256,
                "projection": dict(result.projection),
                "projection_sha256": result.projection_sha256,
            }
        )
    answer: dict[str, Any] = {
        "answer_key_schema": "DERD-PHASE19-PRIVATE-ANSWER-KEY-1.0",
        "kit_id": task_manifest["kit_id"],
        "task_manifest_sha256": task_manifest["sha256_canonical_json"],
        "tasks": tasks,
        "disclosure_policy": (
            "Do not disclose this answer key or commitment key to an external operator "
            "until the operator submission hash has been frozen."
        ),
    }
    answer["answer_key_sha256"] = canonical_sha256(answer)
    return answer


def generate_secret_key() -> bytes:
    return secrets.token_bytes(32)
