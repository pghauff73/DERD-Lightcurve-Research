import numpy as np
import pytest

from derd.cross_validation import circular_phase_folds


def test_circular_folds_are_deterministic_and_disjoint():
    phase = np.linspace(0.0, 1.0, 24, endpoint=False)
    first = circular_phase_folds(phase, folds=4, label="star", seed=17)
    second = circular_phase_folds(phase, folds=4, label="star", seed=17)
    assert len(first) == 4
    assert [fold.validation_indices.tolist() for fold in first] == [
        fold.validation_indices.tolist() for fold in second
    ]
    held = np.concatenate([fold.validation_indices for fold in first])
    assert sorted(held.tolist()) == list(range(24))
    for fold in first:
        assert not set(fold.train_indices).intersection(fold.validation_indices)


def test_circular_folds_depend_on_label_without_using_flux_values():
    phase = np.linspace(0.0, 1.0, 20, endpoint=False)
    a = circular_phase_folds(phase, folds=4, label="A", seed=3)
    b = circular_phase_folds(phase, folds=4, label="B", seed=3)
    assert [fold.validation_indices.tolist() for fold in a] != [
        fold.validation_indices.tolist() for fold in b
    ]


def test_circular_folds_normalize_phase_modulo_one():
    phase = np.array([-0.1, 0.0, 0.1, 0.9, 1.0, 1.1, 1.9, 2.0, 2.1, 2.9])
    folds = circular_phase_folds(phase, folds=2, minimum_train=4)
    assert sum(len(fold.validation_indices) for fold in folds) == phase.size


@pytest.mark.parametrize(
    "phase,folds,minimum_train",
    [([], 2, 1), ([0.0, 0.1], 3, 1), ([0.0, 0.1, 0.2, 0.3], 2, 3)],
)
def test_circular_folds_reject_invalid_partitions(phase, folds, minimum_train):
    with pytest.raises(ValueError):
        circular_phase_folds(phase, folds=folds, minimum_train=minimum_train)
