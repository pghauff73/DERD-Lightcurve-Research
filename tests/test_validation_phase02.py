from pathlib import Path

import numpy as np

from derd.io import read_target_manifest
from derd.validation import ValidationConfig, benchmark_star


def test_observational_pipeline_is_deterministic():
    root = Path(__file__).resolve().parents[1]
    record = read_target_manifest(root / "data/manifests/phase02_targets.csv")[0]
    config = ValidationConfig(
        starts=2,
        maximum_function_evaluations=80,
        normalization_grid_size=512,
        peak_grid_size=256,
        period_grid_count=51,
    )
    first = benchmark_star(record, data_root=root / "data", config=config)
    second = benchmark_star(record, data_root=root / "data", config=config)
    assert first.row["winner"] == second.row["winner"]
    assert np.isclose(first.row["test_derd_g_rmse"], second.row["test_derd_g_rmse"])


def test_observational_pipeline_never_uses_same_point_in_both_sets():
    root = Path(__file__).resolve().parents[1]
    record = read_target_manifest(root / "data/manifests/phase02_targets.csv")[1]
    config = ValidationConfig(
        starts=2,
        maximum_function_evaluations=50,
        normalization_grid_size=512,
        peak_grid_size=256,
        period_grid_count=51,
    )
    result = benchmark_star(record, data_root=root / "data", config=config)
    train = set(result.detail["split"]["train_indices"])
    test = set(result.detail["split"]["test_indices"])
    assert not train.intersection(test)


def test_test_predictions_are_present_for_all_four_models():
    root = Path(__file__).resolve().parents[1]
    record = read_target_manifest(root / "data/manifests/phase02_targets.csv")[2]
    config = ValidationConfig(
        starts=2,
        maximum_function_evaluations=50,
        normalization_grid_size=512,
        peak_grid_size=256,
        period_grid_count=51,
    )
    result = benchmark_star(record, data_root=root / "data", config=config)
    assert {"derd_g", "derd_k", "fourier_order2", "fourier_bic"}.issubset(result.predictions)
