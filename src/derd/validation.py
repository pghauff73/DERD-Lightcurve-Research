"""Phase-02 observational shakedown pipeline.

The pipeline deliberately separates catalog facts, train-only preprocessing,
model fitting, and held-out evaluation. It is an engineering shakedown, not a
promotion of the paper's physical shell interpretation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .baselines import fit_fourier, predict_fourier, select_fourier_order, select_stable_fourier_order
from .fitting import DERDFitResult, fit_waveform, predict_from_fit
from .io import TargetRecord, read_ogle_photometry
from .metrics import metric_bundle
from .model import TimeLaw
from .period import estimate_epoch_of_maximum, verify_catalog_period
from .preprocess import clean_light_curve, fit_train_minmax, fold_phase, inverse_variance_weights
from .splits import circular_phase_block_split


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    test_fraction: float = 0.20
    split_seed: int = 20260807
    fit_seed: int = 20260807
    starts: int = 6
    maximum_function_evaluations: int = 300
    normalization_grid_size: int = 1024
    peak_grid_size: int = 512
    matched_fourier_order: int = 2
    selectable_fourier_orders: tuple[int, ...] = (1, 2, 3, 4, 5)
    period_relative_span: float = 0.001
    period_grid_count: int = 201


@dataclass(frozen=True, slots=True)
class StarBenchmark:
    row: dict[str, Any]
    detail: dict[str, Any]
    predictions: dict[str, NDArray[np.float64]]


def _fit_derd(
    train_phase: NDArray[np.float64],
    train_value: NDArray[np.float64],
    train_weights: NDArray[np.float64],
    *,
    law: TimeLaw,
    config: ValidationConfig,
    seed_offset: int,
) -> DERDFitResult:
    return fit_waveform(
        train_phase,
        train_value,
        weights=train_weights,
        time_law=law,
        starts=config.starts,
        seed=config.fit_seed + seed_offset,
        max_function_evaluations=config.maximum_function_evaluations,
        normalize_target=False,
        align_peak=True,
        normalization_grid_size=config.normalization_grid_size,
        peak_grid_size=config.peak_grid_size,
    )


def _model_metrics(
    observed: NDArray[np.float64],
    predicted: NDArray[np.float64],
    weights: NDArray[np.float64],
    phase: NDArray[np.float64],
) -> dict[str, float]:
    return metric_bundle(observed, predicted, weights=weights, phase=phase)


def benchmark_star(
    record: TargetRecord,
    *,
    data_root: str | Path,
    config: ValidationConfig | None = None,
) -> StarBenchmark:
    active = ValidationConfig() if config is None else config
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
    train_weights = weights[train]
    test_weights = weights[test]

    period_bins = min(8, max(4, train.size // 3))
    period_check = verify_catalog_period(
        flux.time[train],
        flux.value[train],
        record.period_days,
        relative_span=active.period_relative_span,
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
        seed_offset=identity_seed,
    )
    derd_k = _fit_derd(
        train_phase,
        train_value,
        train_weights,
        law=TimeLaw.KEPLER,
        config=active,
        seed_offset=identity_seed + 10000,
    )
    derd_g_test = predict_from_fit(
        test_phase,
        derd_g,
        normalization_grid_size=active.normalization_grid_size,
        peak_grid_size=active.peak_grid_size,
    )
    derd_k_test = predict_from_fit(
        test_phase,
        derd_k,
        normalization_grid_size=active.normalization_grid_size,
        peak_grid_size=active.peak_grid_size,
    )

    fourier_matched = fit_fourier(
        train_phase,
        train_value,
        order=active.matched_fourier_order,
        weights=train_weights,
        normalize_target=False,
    )
    fourier_matched_test = predict_fourier(test_phase, fourier_matched)
    fourier_selection_raw = select_fourier_order(
        train_phase,
        train_value,
        orders=active.selectable_fourier_orders,
        weights=train_weights,
        criterion="bic",
        normalize_target=False,
    )
    fourier_selection = select_stable_fourier_order(
        train_phase,
        train_value,
        orders=active.selectable_fourier_orders,
        weights=train_weights,
        criterion="bic",
        normalize_target=False,
        maximum_condition_number=1.0e4,
        maximum_prediction_span_factor=3.0,
    )
    fourier_selected_test = predict_fourier(test_phase, fourier_selection.selected)
    fourier_raw_test = predict_fourier(test_phase, fourier_selection_raw.selected)

    predictions = {
        "phase": phase,
        "observed": value,
        "observed_error": error,
        "is_test": np.isin(np.arange(flux.size), test).astype(np.float64),
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
        "fourier_order2": predict_fourier(phase, fourier_matched),
        "fourier_bic": predict_fourier(phase, fourier_selection.selected),
        "fourier_bic_raw": predict_fourier(phase, fourier_selection_raw.selected),
    }

    test_metrics = {
        "derd_g": _model_metrics(test_value, derd_g_test, test_weights, test_phase),
        "derd_k": _model_metrics(test_value, derd_k_test, test_weights, test_phase),
        "fourier_order2": _model_metrics(test_value, fourier_matched_test, test_weights, test_phase),
        "fourier_bic": _model_metrics(test_value, fourier_selected_test, test_weights, test_phase),
        "fourier_bic_raw": _model_metrics(test_value, fourier_raw_test, test_weights, test_phase),
    }
    primary_models = ("derd_g", "derd_k", "fourier_order2", "fourier_bic")
    winner = min(primary_models, key=lambda name: test_metrics[name]["rmse"])
    derd_best = min(test_metrics["derd_g"]["rmse"], test_metrics["derd_k"]["rmse"])
    fourier_best = min(test_metrics["fourier_order2"]["rmse"], test_metrics["fourier_bic"]["rmse"])

    row: dict[str, Any] = {
        "star_id": record.star_id,
        "mode": record.mode,
        "period_days": record.period_days,
        "observation_count_raw": raw.size,
        "observation_count_clean": cleaned.size,
        "train_count": int(train.size),
        "test_count": int(test.size),
        "catalog_period_pdm_score": period_check.catalog_score,
        "local_best_period_days": period_check.best_period,
        "period_relative_delta": period_check.relative_delta,
        "epoch_hjd_minus_2450000": epoch,
        "epoch_peak_phase_from_training": epoch_peak_phase,
        "fourier_bic_order": fourier_selection.selected.order,
        "fourier_bic_raw_order": fourier_selection_raw.selected.order,
        "fourier_bic_rejected_orders": ";".join(
            f"{order}:{'+'.join(reasons)}" for order, reasons in sorted(fourier_selection.rejected.items())
        ),
        "winner": winner,
        "best_derd_rmse": derd_best,
        "best_fourier_rmse": fourier_best,
        "derd_minus_fourier_rmse": derd_best - fourier_best,
        "derd_g_condition_number": derd_g.jacobian_condition_number,
        "derd_k_condition_number": derd_k.jacobian_condition_number,
        "local_file_sha256": raw.metadata["local_sha256"],
    }
    for model_name, metrics in test_metrics.items():
        for metric_name, metric_value in metrics.items():
            row[f"test_{model_name}_{metric_name}"] = metric_value
    for prefix, fit in (("derd_g", derd_g), ("derd_k", derd_k)):
        for name, value_item in fit.parameters.as_dict().items():
            row[f"{prefix}_{name}"] = value_item
        row[f"{prefix}_train_rmse"] = fit.metrics["rmse"]
        row[f"{prefix}_success"] = fit.success

    detail = {
        "target": {
            "star_id": record.star_id,
            "mode": record.mode,
            "period_days": record.period_days,
            "source_blob_sha": record.source_blob_sha,
            "source_repository": record.source_repository,
            "source_commit": record.source_commit,
            "period_source_repository": record.period_source_repository,
            "period_source_commit": record.period_source_commit,
        },
        "cleaning": cleaning.as_dict(),
        "split": split.as_dict(),
        "epoch": {
            "reference_epoch": reference_epoch,
            "training_estimated_epoch": epoch,
            "training_peak_phase": epoch_peak_phase,
        },
        "scaler": scaler.as_dict(),
        "period_check": period_check.as_dict(),
        "fits": {
            "derd_g": derd_g.as_dict(),
            "derd_k": derd_k.as_dict(),
            "fourier_order2": fourier_matched.as_dict(),
            "fourier_selection_stable": fourier_selection.as_dict(),
            "fourier_selection_raw": fourier_selection_raw.as_dict(),
        },
        "test_metrics": test_metrics,
        "winner": winner,
    }
    return StarBenchmark(row=row, detail=detail, predictions=predictions)


def benchmark_targets(
    records: Iterable[TargetRecord],
    *,
    data_root: str | Path,
    config: ValidationConfig | None = None,
) -> list[StarBenchmark]:
    active = ValidationConfig() if config is None else config
    return [benchmark_star(record, data_root=data_root, config=active) for record in records]
