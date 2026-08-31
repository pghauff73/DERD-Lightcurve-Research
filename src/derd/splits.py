"""Deterministic star-identity and circular phase-block splits."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class PhaseBlockSplit:
    train_indices: NDArray[np.int64]
    test_indices: NDArray[np.int64]
    start_rank: int
    test_count: int
    phase_min: float
    phase_max: float
    wraps: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "train_indices": self.train_indices.tolist(),
            "test_indices": self.test_indices.tolist(),
            "start_rank": self.start_rank,
            "test_count": self.test_count,
            "phase_min": self.phase_min,
            "phase_max": self.phase_max,
            "wraps": self.wraps,
        }


def _stable_integer(label: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def circular_phase_block_split(
    phase: ArrayLike,
    *,
    star_id: str,
    test_fraction: float = 0.20,
    minimum_test: int = 4,
    minimum_train: int = 12,
    seed: int = 20260807,
) -> PhaseBlockSplit:
    """Hold out one contiguous block in circular phase-rank order.

    The membership is deterministic for a star ID and seed. Contiguity is in
    sorted phase rank rather than a fixed-width phase interval, which keeps the
    test count stable under irregular cadence.
    """

    values = np.asarray(phase, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("phase must contain finite values")
    if not 0.0 < test_fraction < 0.5:
        raise ValueError("test_fraction must lie between zero and 0.5")
    n = int(values.size)
    test_count = max(int(minimum_test), int(round(test_fraction * n)))
    if n - test_count < minimum_train:
        test_count = n - minimum_train
    if test_count < 1:
        raise ValueError("not enough observations for the requested split")

    normalized = np.mod(values, 1.0)
    order = np.argsort(normalized, kind="mergesort")
    start = _stable_integer(star_id, seed) % n
    positions = (start + np.arange(test_count, dtype=np.int64)) % n
    test = np.sort(order[positions]).astype(np.int64)
    mask = np.ones(n, dtype=bool)
    mask[test] = False
    train = np.flatnonzero(mask).astype(np.int64)
    if np.intersect1d(train, test).size or train.size + test.size != n:
        raise AssertionError("split construction produced overlap or loss")

    held_phases = normalized[test]
    wraps = bool(start + test_count > n)
    return PhaseBlockSplit(
        train_indices=train,
        test_indices=test,
        start_rank=int(start),
        test_count=int(test_count),
        phase_min=float(np.min(held_phases)),
        phase_max=float(np.max(held_phases)),
        wraps=wraps,
    )


def star_identity_partition(star_ids: list[str], *, holdout_fraction: float, seed: int = 20260807) -> dict[str, str]:
    """Assign complete stars, never observations, to development or holdout."""

    if len(star_ids) != len(set(star_ids)):
        raise ValueError("star_ids must be unique")
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must lie between zero and one")
    ranked = sorted(star_ids, key=lambda item: _stable_integer(item, seed))
    count = max(1, int(round(len(ranked) * holdout_fraction)))
    holdout = set(ranked[:count])
    return {star_id: ("holdout" if star_id in holdout else "development") for star_id in star_ids}
