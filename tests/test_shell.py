import math

import pytest

from derd.shell import (
    ideal_spherical_shell_acceleration_inside,
    minimum_radius_for_optical_depth,
    optical_depth,
    shell_surface_density,
)


def test_surface_density_scales_as_inverse_radius_squared():
    first = shell_surface_density(10.0, 2.0)
    second = shell_surface_density(10.0, 4.0)
    assert math.isclose(first / second, 4.0)


def test_optical_depth_is_opacity_times_surface_density():
    assert math.isclose(optical_depth(10.0, 2.0, 3.0), 3.0 * shell_surface_density(10.0, 2.0))


def test_minimum_radius_inverts_optical_depth():
    radius = minimum_radius_for_optical_depth(10.0, 2.0, 0.1)
    assert math.isclose(optical_depth(10.0, radius, 2.0), 0.1)


def test_ideal_spherical_shell_has_zero_interior_acceleration():
    assert ideal_spherical_shell_acceleration_inside(1.0, 2.0, 10.0) == 0.0


def test_shell_acceleration_rejects_point_on_shell():
    with pytest.raises(ValueError):
        ideal_spherical_shell_acceleration_inside(2.0, 2.0, 10.0)
