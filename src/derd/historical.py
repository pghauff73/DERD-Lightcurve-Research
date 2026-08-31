"""Faithful computational capsule for the algorithm printed in the source paper.

This module intentionally retains the historical implementation's numerical choices:
``0.333`` instead of exact ``1/3``, an iterative true-anomaly stepper, integer sample
phase slicing, and the literal phase value ``0.28``. It is an audit object, not the
corrected reference model.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .normalization import minmax_normalize

G_PAPER = 6.673e-11
M_SUN_PAPER = 1.9891e30


@dataclass(frozen=True, slots=True)
class HistoricalCycle:
    time: NDArray[np.float64]
    distance_raw: NDArray[np.float64]
    distance_normalized: NDArray[np.float64]
    theta: NDArray[np.float64]

    @property
    def sample_count(self) -> int:
        return int(self.time.size)


class PaperEllipseEquation:
    """Line-by-line compatible reconstruction of the paper's ``EllipseEquation``."""

    def __init__(self, eccentricity: float):
        self.e = float(eccentricity)
        if not 0.0 <= self.e < 1.0:
            raise ValueError("eccentricity must satisfy 0 <= e < 1")
        self.a = (G_PAPER * M_SUN_PAPER / (4.0 * math.pi * math.pi)) ** 0.333
        self.b = math.sqrt(self.a * self.a * (1.0 - self.e * self.e))
        self.P = 1.0

    def calc_r(self, theta: float) -> float:
        return self.a * (1.0 - self.e**2) / (1.0 + self.e * math.cos(theta))

    def calc_v(self, radius: float) -> float:
        return math.sqrt(G_PAPER * M_SUN_PAPER * (2.0 / radius - 1.0 / self.a))

    def calc(self, requested_samples: int) -> HistoricalCycle:
        if requested_samples < 2:
            raise ValueError("requested_samples must be at least two")
        time: list[float] = []
        distance: list[float] = []
        theta_values: list[float] = []
        theta = 0.0
        current_time = 0.0
        count = 0
        dt = self.P / requested_samples

        while 0.0 <= theta < 2.0 * math.pi and count < 10000:
            radius = self.calc_r(theta)
            velocity = self.calc_v(radius)
            x = radius * math.cos(theta)
            y = radius * math.sin(theta)
            d_theta = 2.0 * math.pi / requested_samples
            overflow_count = 0
            while overflow_count < 10:
                overflow_count += 1
                theta_dash = theta + d_theta
                radius_dash = self.calc_r(theta_dash)
                x_dash = radius_dash * math.cos(theta_dash)
                y_dash = radius_dash * math.sin(theta_dash)
                d_distance = math.hypot(x_dash - x, y_dash - y)
                dt_dash = velocity / d_distance
                dt_ratio = dt_dash * dt
                if 1.0 <= dt_ratio < 1.0001:
                    break
                d_theta *= dt_ratio

            time.append(current_time)
            distance.append(math.hypot(x, y))
            theta_values.append(theta)
            current_time += dt
            count += 1
            theta += d_theta

        raw = np.asarray(distance, dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            normalized = raw / (np.max(raw) - np.min(raw))
            normalized = normalized - np.min(normalized)
        return HistoricalCycle(
            time=np.asarray(time, dtype=np.float64),
            distance_raw=raw,
            distance_normalized=normalized,
            theta=np.asarray(theta_values, dtype=np.float64),
        )


def extend_signal(signal: NDArray[np.float64], repetitions: int) -> NDArray[np.float64]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    return np.resize(np.asarray(signal, dtype=np.float64), repetitions * len(signal))


def paper_waveform(
    e1: float,
    e2: float,
    amplitude_ratio: float,
    phase_declared: float,
    *,
    requested_samples: int = 1000,
    hardcoded_phase: float = 0.28,
) -> NDArray[np.float64]:
    """Reproduce the printed combination path, including its unused phase variable."""

    _ = float(phase_declared)  # Deliberately unused, matching the printed code.
    cycle_1 = PaperEllipseEquation(e1).calc(requested_samples)
    cycle_2 = PaperEllipseEquation(e2).calc(requested_samples)
    count = min(cycle_1.sample_count, cycle_2.sample_count)
    first = cycle_1.distance_normalized[:count]
    second_extended = extend_signal(cycle_2.distance_normalized[:count], 2)
    start = int(count * hardcoded_phase)
    second = float(amplitude_ratio) * second_extended[start : start + count]
    result = extend_signal(-first + second, 2)
    normalized, _ = minmax_normalize(result)
    return normalized


def paper_semimajor_axis() -> float:
    return (G_PAPER * M_SUN_PAPER / (4.0 * math.pi * math.pi)) ** 0.333


def exact_semimajor_axis_for_one_second_period() -> float:
    return (G_PAPER * M_SUN_PAPER / (4.0 * math.pi * math.pi)) ** (1.0 / 3.0)


def implied_period_from_paper_axis() -> float:
    axis = paper_semimajor_axis()
    return math.sqrt(4.0 * math.pi**2 * axis**3 / (G_PAPER * M_SUN_PAPER))
