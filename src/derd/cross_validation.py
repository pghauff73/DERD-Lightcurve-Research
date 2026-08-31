"""Leakage-resistant circular phase cross-validation utilities."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class CircularFold:
    """One deterministic phase-contiguous cross-validation fold."""

    fold: int
    train_indices: NDArray[np.int64]
    validation_indices: NDArray[np.int64]
    validation_phase_min: float
    validation_phase_max: float
    wraps: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "fold": self.fold,
            "train_indices": self.train_indices.tolist(),
            "validation_indices": self.validation_indices.tolist(),
            "validation_phase_min": self.validation_phase_min,
            "validation_phase_max": self.validation_phase_max,
            "wraps": self.wraps,
        }


def _stable_rotation(label: str, seed: int, size: int) -> int:
    if size < 1:
        raise ValueError("size must be positive")
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) % size


def circular_phase_folds(
    phase: ArrayLike,
    *,
    folds: int = 4,
    label: str = "phase-cv",
    seed: int = 20260808,
    minimum_train: int = 8,
) -> tuple[CircularFold, ...]:
    """Partition observations into deterministic contiguous circular phase blocks.

    Each observation appears in exactly one validation fold. Membership depends
    only on phase ranks, ``label``, and ``seed``. Values are never inspected.
    """

    values = np.asarray(phase, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("phase must contain finite values")
    if folds < 2:
        raise ValueError("folds must be at least two")
    if folds > values.size:
        raise ValueError("folds cannot exceed the observation count")
    if values.size - int(np.ceil(values.size / folds)) < minimum_train:
        raise ValueError("each fold must leave at least minimum_train observations")

    normalized = np.mod(values, 1.0)
    ranked = np.argsort(normalized, kind="mergesort")
    rotation = _stable_rotation(label, seed, values.size)
    rotated = np.roll(ranked, -rotation)
    blocks = [np.asarray(block, dtype=np.int64) for block in np.array_split(rotated, folds)]

    all_indices = np.arange(values.size, dtype=np.int64)
    result: list[CircularFold] = []
    seen: list[int] = []
    for fold_number, validation in enumerate(blocks):
        if validation.size == 0:
            raise AssertionError("cross-validation produced an empty fold")
        mask = np.ones(values.size, dtype=bool)
        mask[validation] = False
        train = all_indices[mask]
        held = normalized[validation]
        ranks = np.sort(np.flatnonzero(np.isin(ranked, validation)))
        wraps = bool(ranks.size > 1 and np.any(np.diff(ranks) > 1))
        result.append(
            CircularFold(
                fold=fold_number,
                train_indices=np.sort(train),
                validation_indices=np.sort(validation),
                validation_phase_min=float(np.min(held)),
                validation_phase_max=float(np.max(held)),
                wraps=wraps,
            )
        )
        seen.extend(validation.tolist())

    if sorted(seen) != list(range(values.size)):
        raise AssertionError("folds do not form a complete disjoint partition")
    return tuple(result)
