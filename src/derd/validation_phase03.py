"""Phase-03 observational methods: nonlinear baseline and uncertainty calibration.

All model selection and interval calibration occur inside the outer training
partition. The existing 20-star excerpt is reused only as an engineering
population; it is not a pristine confirmatory sample because Phase 02 already
examined it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .baselines import fit_fourier, predict_fourier
from .cross_validation import circular_phase_folds
from .fitting import DERDFitResult, fit_waveform, predict_from_fit
from .io import TargetRecord, read_ogle_photometry
from .kernels import (
    PeriodicKernelSelection,
    predict_periodic_kernel,
    select_periodic_kernel_ridge,
)
from .metrics import metric_bundle
from .model import TimeLaw
from .period import adaptive_verify_catalog_period, estimate_epoch_of_maximum
from .preprocess import clean_light_curve, fit_train_minmax, fold_phase, inverse_variance_weights
from .splits import circular_phase_block_split
from .uncertainty import (
    calibrate_symmetric_interval,
    interval_metrics,
    prediction_interval,
)


MODEL_NAMES = ("derd_g", "derd_k", "fourier_order2", "periodic_krr")


@dataclass(frozen=True, slots=True)
class Phase03Config:
    test_fraction: float = 0.20
    split_seed: int = 20260807
    fit_seed: int = 20260808
    starts: int = 2
    cv_starts: int = 1
    maximum_function_evaluations: int = 100
    cv_maximum_function_evaluations: int = 60
    normalization_grid_size: int = 256
    peak_grid_size: int = 128
    matched_fourier_order: int = 2
    outer_cv_folds: int = 4
    kernel_inner_folds: int = 3
    kernel_length_scales: tuple[float, ...] = (0.05, 0.10, 0.20, 0.35, 0.50, 0.70, 1.00, 1.50, 2.00)
    kernel_ridges: tuple[float, ...] = (1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1)
    period_relative_spans: tuple[float, ...] = (0.001, 0.005, 0.02)
    period_grid_count: int = 101
    interval_coverage: float = 0.90


@dataclass(frozen=True, slots=True)
class Phase03StarBenchmark:
    row: dict[str, Any]
    detail: dict[str, Any]
    predictions: dict[str, NDArray[np.float64]]


def _fit_derd(
    phase: NDArray[np.float64],
    value: NDArray[np.float64],
    weights: NDArray[np.float64],
    *,
    law: TimeLaw,
    config: Phase03Config,
    seed: int,
    cross_validation: bool = False,
) -> DERDFitResult:
    return fit_waveform(
        phase,
        value,
        weights=weights,
        time_law=law,
        starts=config.cv_starts if cross_validation else config.starts,
        seed=seed,
        max_function_evaluations=(
            config.cv_maximum_function_evaluations
            if cross_validation
            else config.maximum_function_evaluations
        ),
        normalize_target=False,
        align_peak=True,
        normalization_grid_size=config.normalization_grid_size,
        peak_grid_size=config.peak_grid_size,
    )


def _kernel_selection(
    phase: NDArray[np.float64],
    value: NDArray[np.float64],
    weights: NDArray[np.float64],
    *,
    config: Phase03Config,
    label: str,
    seed: int,
) -> PeriodicKernelSelection:
    folds = min(config.kernel_inner_folds, max(2, phase.size // 4))
    return select_periodic_kernel_ridge(
        phase,
        value,
        weights=weights,
        length_scales=config.kernel_length_scales,
        ridges=config.kernel_ridges,
        folds=folds,
        label=label,
        seed=seed,
        maximum_condition_number=1.0e8,
        maximum_prediction_span_factor=3.0,
    )


def _out_of_fold_predictions(
    phase: NDArray[np.float64],
    value: NDArray[np.float64],
    weights: NDArray[np.float64],
    *,
    star_id: str,
    config: Phase03Config,
    identity_seed: int,
) -> tuple[dict[str, NDArray[np.float64]], tuple[dict[str, object], ...]]:
    folds = circular_phase_folds(
        phase,
        folds=config.outer_cv_folds,
        label=f"{star_id}:phase03-oof",
        seed=config.split_seed + 301,
        minimum_train=8,
    )
    predictions = {name: np.full_like(value, np.nan) for name in MODEL_NAMES}
    audit: list[dict[str, object]] = []
    for fold in folds:
        train = fold.train_indices
        validation = fold.validation_indices
        fold_seed = config.fit_seed + identity_seed + fold.fold * 1000

        derd_g = _fit_derd(
            phase[train],
            value[train],
            weights[train],
            law=TimeLaw.GEOMETRIC,
            config=config,
            seed=fold_seed + 1,
            cross_validation=True,
        )
        derd_k = _fit_derd(
            phase[train],
            value[train],
            weights[train],
            law=TimeLaw.KEPLER,
            config=config,
            seed=fold_seed + 2,
            cross_validation=True,
        )
        fourier = fit_fourier(
            phase[train],
            value[train],
            order=config.matched_fourier_order,
            weights=weights[train],
            normalize_target=False,
        )
        kernel = _kernel_selection(
            phase[train],
            value[train],
            weights[train],
            config=config,
            label=f"{star_id}:outer-{fold.fold}:kernel-inner",
            seed=fold_seed + 3,
        )

        predictions["derd_g"][validation] = predict_from_fit(
            phase[validation],
            derd_g,
            normalization_grid_size=config.normalization_grid_size,
            peak_grid_size=config.peak_grid_size,
        )
        predictions["derd_k"][validation] = predict_from_fit(
            phase[validation],
            derd_k,
            normalization_grid_size=config.normalization_grid_size,
            peak_grid_size=config.peak_grid_size,
        )
        predictions["fourier_order2"][validation] = predict_fourier(
            phase[validation], fourier
        )
        predictions["periodic_krr"][validation] = predict_periodic_kernel(
            phase[validation], kernel.fit
        )
        audit.append(
            {
                **fold.as_dict(),
                "derd_g_condition_number": derd_g.jacobian_condition_number,
                "derd_k_condition_number": derd_k.jacobian_condition_number,
                "kernel_selected_length_scale": kernel.selected_length_scale,
                "kernel_selected_ridge": kernel.selected_ridge,
                "kernel_fallback_used": kernel.fallback_used,
                "kernel_length_scale_boundary_hit": bool(
                    np.isclose(kernel.selected_length_scale, max(config.kernel_length_scales))
                ),
            }
        )

    for name, prediction in predictions.items():
        if not np.all(np.isfinite(prediction)):
            raise RuntimeError(f"out-of-fold prediction incomplete for {name}")
    return predictions, tuple(audit)


def benchmark_star_phase03(
    record: TargetRecord,
    *,
    data_root: str | Path,
    config: Phase03Config | None = None,
) -> Phase03StarBenchmark:
    active = Phase03Config() if config is None else config
    source_path = Path(data_root) / record.relative_path
    raw = read_ogle_photometry(
        source_path,
        star_id=record.star_id,
        band="I",
        metadata={
            "source_repository": record.source_repository,
            "source_commit": record.source_commit,
            "source_blob_sha": record.source_blob_sha,
            "period_source_repository": record.period_source_repository,
            "period_source_commit": record.period_source_commit,
        },
    )
    cleaned, cleaning = clean_light_curve(raw)
    flux = cleaned.to_relative_flux()

    reference_epoch = float(np.min(flux.time))
    reference_phase = fold_phase(flux.time, record.period_days, epoch=reference_epoch)
    split = circular_phase_block_split(
        reference_phase,
        star_id=record.star_id,
        test_fraction=active.test_fraction,
        seed=active.split_seed,
    )
    train = split.train_indices
    test = split.test_indices

    raw_weights = inverse_variance_weights(flux.error)
    epoch, epoch_peak_phase = estimate_epoch_of_maximum(
        flux.time[train],
        flux.value[train],
        record.period_days,
        weights=raw_weights[train],
        order=3,
    )
    phase = fold_phase(flux.time, record.period_days, epoch=epoch)
    scaler = fit_train_minmax(flux.value[train])
    value = scaler.transform_values(flux.value)
    error = scaler.transform_errors(flux.error)
    weights = inverse_variance_weights(error)

    train_phase = phase[train]
    test_phase = phase[test]
    train_value = value[train]
    test_value = value[test]
    train_error = error[train]
    test_error = error[test]
    train_weights = weights[train]
    test_weights = weights[test]

    period_bins = min(8, max(4, train.size // 3))
    adaptive_period = adaptive_verify_catalog_period(
        flux.time[train],
        flux.value[train],
        record.period_days,
        relative_spans=active.period_relative_spans,
        grid_count=active.period_grid_count,
        bins=period_bins,
    )

    identity_seed = sum(ord(character) for character in record.star_id)
    derd_g = _fit_derd(
        train_phase,
        train_value,
        train_weights,
        law=TimeLaw.GEOMETRIC,
        config=active,
        seed=active.fit_seed + identity_seed + 1,
    )
    derd_k = _fit_derd(
        train_phase,
        train_value,
        train_weights,
        law=TimeLaw.KEPLER,
        config=active,
        seed=active.fit_seed + identity_seed + 2,
    )
    fourier = fit_fourier(
        train_phase,
        train_value,
        order=active.matched_fourier_order,
        weights=train_weights,
        normalize_target=False,
    )
    kernel = _kernel_selection(
        train_phase,
        train_value,
        train_weights,
        config=active,
        label=f"{record.star_id}:phase03-full-kernel",
        seed=active.fit_seed + identity_seed + 3,
    )

    full_predictions = {
        "derd_g": predict_from_fit(
            phase,
            derd_g,
            normalization_grid_size=active.normalization_grid_size,
            peak_grid_size=active.peak_grid_size,
        ),
        "derd_k": predict_from_fit(
            phase,
            derd_k,
            normalization_grid_size=active.normalization_grid_size,
            peak_grid_size=active.peak_grid_size,
        ),
        "fourier_order2": predict_fourier(phase, fourier),
        "periodic_krr": predict_periodic_kernel(phase, kernel.fit),
    }

    oof_predictions, oof_audit = _out_of_fold_predictions(
        train_phase,
        train_value,
        train_weights,
        star_id=record.star_id,
        config=active,
        identity_seed=identity_seed,
    )
    oof_metrics = {
        name: metric_bundle(
            train_value,
            prediction,
            weights=train_weights,
            phase=train_phase,
        )
        for name, prediction in oof_predictions.items()
    }

    test_metrics = {
        name: metric_bundle(
            test_value,
            prediction[test],
            weights=test_weights,
            phase=test_phase,
        )
        for name, prediction in full_predictions.items()
    }

    calibrations: dict[str, object] = {}
    absolute_calibrations: dict[str, object] = {}
    interval_results: dict[str, object] = {}
    absolute_interval_results: dict[str, object] = {}
    lower_bounds: dict[str, NDArray[np.float64]] = {}
    upper_bounds: dict[str, NDArray[np.float64]] = {}
    for name in MODEL_NAMES:
        calibration = calibrate_symmetric_interval(
            train_value,
            oof_predictions[name],
            nominal_coverage=active.interval_coverage,
            scale=train_error,
        )
        lower, upper = prediction_interval(
            full_predictions[name][test],
            calibration,
            scale=test_error,
        )
        absolute_calibration = calibrate_symmetric_interval(
            train_value,
            oof_predictions[name],
            nominal_coverage=active.interval_coverage,
        )
        absolute_lower, absolute_upper = prediction_interval(
            full_predictions[name][test],
            absolute_calibration,
        )
        calibrations[name] = calibration
        absolute_calibrations[name] = absolute_calibration
        interval_results[name] = interval_metrics(
            test_value,
            lower,
            upper,
            nominal_coverage=active.interval_coverage,
        )
        absolute_interval_results[name] = interval_metrics(
            test_value,
            absolute_lower,
            absolute_upper,
            nominal_coverage=active.interval_coverage,
        )
        lower_bounds[name] = lower
        upper_bounds[name] = upper

    selected_derd = min(
        ("derd_g", "derd_k"),
        key=lambda name: oof_metrics[name]["weighted_rmse"],
    )
    selected_baseline = min(
        ("fourier_order2", "periodic_krr"),
        key=lambda name: oof_metrics[name]["weighted_rmse"],
    )
    preselected_model = min(
        MODEL_NAMES,
        key=lambda name: oof_metrics[name]["weighted_rmse"],
    )
    descriptive_test_winner = min(
        MODEL_NAMES,
        key=lambda name: test_metrics[name]["rmse"],
    )

    row: dict[str, Any] = {
        "star_id": record.star_id,
        "mode": record.mode,
        "period_days": record.period_days,
        "observation_count_raw": raw.size,
        "observation_count_clean": cleaned.size,
        "train_count": int(train.size),
        "test_count": int(test.size),
        "period_scan_best_period_days": adaptive_period.best_period,
        "period_scan_relative_delta": adaptive_period.relative_delta,
        "period_scan_resolved": adaptive_period.resolved,
        "period_scan_stages": len(adaptive_period.stages),
        "period_scan_max_span": adaptive_period.stages[-1].relative_span,
        "kernel_length_scale": kernel.selected_length_scale,
        "kernel_ridge": kernel.selected_ridge,
        "kernel_cv_weighted_rmse": kernel.cross_validated_weighted_rmse,
        "kernel_condition_number": kernel.fit.condition_number,
        "kernel_effective_parameters": kernel.fit.effective_parameters,
        "kernel_fallback_used": kernel.fallback_used,
        "kernel_length_scale_boundary_hit": bool(
            np.isclose(kernel.selected_length_scale, max(active.kernel_length_scales))
        ),
        "selected_derd_by_training_cv": selected_derd,
        "selected_baseline_by_training_cv": selected_baseline,
        "preselected_model_by_training_cv": preselected_model,
        "descriptive_test_winner": descriptive_test_winner,
        "selected_derd_test_rmse": test_metrics[selected_derd]["rmse"],
        "selected_baseline_test_rmse": test_metrics[selected_baseline]["rmse"],
        "primary_derd_minus_baseline_rmse": (
            test_metrics[selected_derd]["rmse"] - test_metrics[selected_baseline]["rmse"]
        ),
        "preselected_model_test_rmse": test_metrics[preselected_model]["rmse"],
        "derd_g_condition_number": derd_g.jacobian_condition_number,
        "derd_k_condition_number": derd_k.jacobian_condition_number,
        "local_file_sha256": raw.metadata["local_sha256"],
    }
    for name in MODEL_NAMES:
        for metric_name, metric_value in oof_metrics[name].items():
            row[f"oof_{name}_{metric_name}"] = metric_value
        for metric_name, metric_value in test_metrics[name].items():
            row[f"test_{name}_{metric_name}"] = metric_value
        interval = interval_results[name]
        row[f"interval_{name}_coverage"] = interval.empirical_coverage
        row[f"interval_{name}_mean_width"] = interval.mean_width
        row[f"interval_{name}_score"] = interval.interval_score
        row[f"interval_{name}_quantile"] = calibrations[name].quantile
        absolute_interval = absolute_interval_results[name]
        row[f"interval_absolute_{name}_coverage"] = absolute_interval.empirical_coverage
        row[f"interval_absolute_{name}_mean_width"] = absolute_interval.mean_width
        row[f"interval_absolute_{name}_score"] = absolute_interval.interval_score
        row[f"interval_absolute_{name}_quantile"] = absolute_calibrations[name].quantile

    for prefix, fit in (("derd_g", derd_g), ("derd_k", derd_k)):
        for parameter_name, parameter_value in fit.parameters.as_dict().items():
            row[f"{prefix}_{parameter_name}"] = parameter_value

    predictions: dict[str, NDArray[np.float64]] = {
        "phase": phase,
        "observed": value,
        "observed_error": error,
        "is_test": np.isin(np.arange(flux.size), test).astype(np.float64),
        **full_predictions,
    }
    for name in MODEL_NAMES:
        full_lower = np.full(flux.size, np.nan)
        full_upper = np.full(flux.size, np.nan)
        full_lower[test] = lower_bounds[name]
        full_upper[test] = upper_bounds[name]
        predictions[f"{name}_interval_lower"] = full_lower
        predictions[f"{name}_interval_upper"] = full_upper

    detail = {
        "target": {
            "star_id": record.star_id,
            "mode": record.mode,
            "period_days": record.period_days,
            "source_blob_sha": record.source_blob_sha,
            "source_repository": record.source_repository,
            "source_commit": record.source_commit,
        },
        "cleaning": cleaning.as_dict(),
        "split": split.as_dict(),
        "epoch": {
            "reference_epoch": reference_epoch,
            "training_estimated_epoch": epoch,
            "training_peak_phase": epoch_peak_phase,
        },
        "scaler": scaler.as_dict(),
        "adaptive_period_check": adaptive_period.as_dict(),
        "fits": {
            "derd_g": derd_g.as_dict(),
            "derd_k": derd_k.as_dict(),
            "fourier_order2": fourier.as_dict(),
            "periodic_krr": kernel.as_dict(),
        },
        "out_of_fold_audit": list(oof_audit),
        "out_of_fold_metrics": oof_metrics,
        "test_metrics": test_metrics,
        "interval_calibrations": {
            "error_standardized": {
                name: calibration.as_dict() for name, calibration in calibrations.items()
            },
            "absolute": {
                name: calibration.as_dict() for name, calibration in absolute_calibrations.items()
            },
        },
        "interval_test_metrics": {
            "error_standardized": {
                name: result.as_dict() for name, result in interval_results.items()
            },
            "absolute": {
                name: result.as_dict() for name, result in absolute_interval_results.items()
            },
        },
        "selection": {
            "selected_derd_by_training_cv": selected_derd,
            "selected_baseline_by_training_cv": selected_baseline,
            "preselected_model_by_training_cv": preselected_model,
            "descriptive_test_winner": descriptive_test_winner,
        },
    }
    return Phase03StarBenchmark(row=row, detail=detail, predictions=predictions)


def benchmark_targets_phase03(
    records: Iterable[TargetRecord],
    *,
    data_root: str | Path,
    config: Phase03Config | None = None,
) -> list[Phase03StarBenchmark]:
    active = Phase03Config() if config is None else config
    return [benchmark_star_phase03(record, data_root=data_root, config=active) for record in records]
