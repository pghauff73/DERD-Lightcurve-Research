import pytest

from derd.parameters import DERDParameters


def test_phase_is_wrapped_to_canonical_interval() -> None:
    assert DERDParameters(0.1, 0.2, 0.3, 1.25).phase_ratio == pytest.approx(0.25)
    assert DERDParameters(0.1, 0.2, 0.3, -0.1).phase_ratio == pytest.approx(0.9)


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        DERDParameters(-0.1, 0.2, 0.3, 0.0)
    with pytest.raises(ValueError):
        DERDParameters(0.1, 1.0, 0.3, 0.0)
    with pytest.raises(ValueError):
        DERDParameters(0.1, 0.2, 0.0, 0.0)
    with pytest.raises(ValueError):
        DERDParameters(float("nan"), 0.2, 0.3, 0.0)


def test_one_dimension_replacement_preserves_other_dimensions() -> None:
    base = DERDParameters(0.1, 0.2, 0.3, 0.4)
    changed = base.with_dimension("e2", 0.7)
    assert changed.e1 == base.e1
    assert changed.e2 == 0.7
    assert changed.amplitude_ratio == base.amplitude_ratio
    assert changed.phase_ratio == base.phase_ratio


def test_from_iterable_requires_exactly_four_values() -> None:
    with pytest.raises(ValueError):
        DERDParameters.from_iterable([0.1, 0.2, 0.3])
