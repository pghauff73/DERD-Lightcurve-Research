"""Scale-aware transparency and ideal spherical-shell theory gates.

These functions do not infer a shell from a light curve. They expose the
additional dimensional information a physical shell claim would require.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ShellFeasibilityPoint:
    shell_mass_kg: float
    shell_radius_m: float
    opacity_m2_per_kg: float
    covering_fraction: float
    surface_density_kg_per_m2: float
    optical_depth: float

    def as_dict(self) -> dict[str, float]:
        return {
            "shell_mass_kg": self.shell_mass_kg,
            "shell_radius_m": self.shell_radius_m,
            "opacity_m2_per_kg": self.opacity_m2_per_kg,
            "covering_fraction": self.covering_fraction,
            "surface_density_kg_per_m2": self.surface_density_kg_per_m2,
            "optical_depth": self.optical_depth,
        }


def _positive(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def shell_surface_density(shell_mass_kg: float, shell_radius_m: float, *, covering_fraction: float = 1.0) -> float:
    """Mean mass column for a geometrically thin shell."""

    mass = _positive("shell_mass_kg", shell_mass_kg)
    radius = _positive("shell_radius_m", shell_radius_m)
    cover = float(covering_fraction)
    if not math.isfinite(cover) or not 0.0 < cover <= 1.0:
        raise ValueError("covering_fraction must lie in (0, 1]")
    return mass / (4.0 * math.pi * radius * radius * cover)


def optical_depth(
    shell_mass_kg: float,
    shell_radius_m: float,
    opacity_m2_per_kg: float,
    *,
    covering_fraction: float = 1.0,
) -> float:
    opacity = _positive("opacity_m2_per_kg", opacity_m2_per_kg)
    return opacity * shell_surface_density(
        shell_mass_kg,
        shell_radius_m,
        covering_fraction=covering_fraction,
    )


def minimum_radius_for_optical_depth(
    shell_mass_kg: float,
    opacity_m2_per_kg: float,
    maximum_optical_depth: float,
    *,
    covering_fraction: float = 1.0,
) -> float:
    mass = _positive("shell_mass_kg", shell_mass_kg)
    opacity = _positive("opacity_m2_per_kg", opacity_m2_per_kg)
    tau = _positive("maximum_optical_depth", maximum_optical_depth)
    cover = float(covering_fraction)
    if not math.isfinite(cover) or not 0.0 < cover <= 1.0:
        raise ValueError("covering_fraction must lie in (0, 1]")
    return math.sqrt(opacity * mass / (4.0 * math.pi * cover * tau))


def evaluate_shell(
    shell_mass_kg: float,
    shell_radius_m: float,
    opacity_m2_per_kg: float,
    *,
    covering_fraction: float = 1.0,
) -> ShellFeasibilityPoint:
    density = shell_surface_density(
        shell_mass_kg,
        shell_radius_m,
        covering_fraction=covering_fraction,
    )
    tau = optical_depth(
        shell_mass_kg,
        shell_radius_m,
        opacity_m2_per_kg,
        covering_fraction=covering_fraction,
    )
    return ShellFeasibilityPoint(
        shell_mass_kg=float(shell_mass_kg),
        shell_radius_m=float(shell_radius_m),
        opacity_m2_per_kg=float(opacity_m2_per_kg),
        covering_fraction=float(covering_fraction),
        surface_density_kg_per_m2=density,
        optical_depth=tau,
    )


def ideal_spherical_shell_acceleration_inside(
    interior_radius_m: float,
    shell_inner_radius_m: float,
    shell_mass_kg: float,
) -> float:
    """Return the Newtonian gravitational acceleration inside an ideal shell.

    The value is exactly zero by the shell theorem when the evaluation point is
    strictly inside the shell's inner radius. The mass is validated but does not
    enter the result, which is the scientific point of this gate.
    """

    radius = float(interior_radius_m)
    inner = _positive("shell_inner_radius_m", shell_inner_radius_m)
    _positive("shell_mass_kg", shell_mass_kg)
    if not math.isfinite(radius) or radius < 0.0:
        raise ValueError("interior_radius_m must be finite and non-negative")
    if radius >= inner:
        raise ValueError("evaluation point must lie strictly inside the shell")
    return 0.0
