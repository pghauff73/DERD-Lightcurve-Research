from __future__ import annotations

import json
from pathlib import Path

import pytest

from derd.ogle_catalog import (
    Ogle4LmcDsctIdentity,
    Ogle4LmcDsctParameters,
    normalize_lmc_dsct_id,
    resolve_delta_scuti_metadata,
    verify_lock_payload,
)


def fixed_line(length: int, fields: tuple[tuple[int, int, str], ...]) -> str:
    chars = [" "] * length
    for start, stop, value in fields:
        width = stop - start + 1
        chars[start - 1 : stop] = value[:width].ljust(width)
    return "".join(chars)


def identity_line(*, current: int = 10003, old: int = 3, subtype: str = "singlemode") -> str:
    return fixed_line(136, (
        (1, 19, f"OGLE-LMC-DSCT-{current:05d}"),
        (22, 31, subtype),
        (34, 35, "05"),
        (37, 38, "21"),
        (40, 44, "12.34"),
        (46, 48, "-69"),
        (50, 51, "44"),
        (53, 56, "01.2"),
        (59, 74, f"OGLE-LMC-DSCT-{current:05d}"),
        (76, 90, f"LMC-DSCT-{old:04d}"),
    ))


def parameter_line(*, current: int = 10003, period: float = 0.12345678) -> str:
    return fixed_line(238, (
        (1, 19, f"OGLE-LMC-DSCT-{current:05d}"),
        (22, 27, "18.123"),
        (29, 34, "18.456"),
        (37, 46, f"{period:10.8f}"),
        (48, 57, f"{0.00000011:10.8f}"),
        (60, 69, f"{9000.12345:10.5f}"),
        (72, 76, "0.123"),
    ))


def test_parse_published_fixed_width_contract() -> None:
    identity = Ogle4LmcDsctIdentity.parse(identity_line())
    parameters = Ogle4LmcDsctParameters.parse(parameter_line())
    assert identity.object_id == "OGLE-LMC-DSCT-10003"
    assert identity.ogle3_id == "LMC-DSCT-0003"
    assert identity.subtype == "singlemode"
    assert parameters.object_id == identity.object_id
    assert parameters.primary_period_days == pytest.approx(0.12345678)
    assert parameters.primary_period_error_days == pytest.approx(0.00000011)
    assert len(identity.row_sha256) == 64
    assert len(parameters.row_sha256) == 64


def test_alias_normalization_is_explicit_not_suffix_matching() -> None:
    assert normalize_lmc_dsct_id("LMC-DSCT-0003") == "OGLE-LMC-DSCT-0003"
    assert normalize_lmc_dsct_id("OGLE-LMC-DSCT-0003") == "OGLE-LMC-DSCT-0003"
    assert normalize_lmc_dsct_id("0003") == "0003"


def test_crosswalk_resolution_preserves_noninvented_mode() -> None:
    lock = resolve_delta_scuti_metadata(
        ["OGLE-LMC-DSCT-0003"],
        [Ogle4LmcDsctIdentity.parse(identity_line())],
        [Ogle4LmcDsctParameters.parse(parameter_line())],
        identity_catalog_sha256="1" * 64,
        parameter_catalog_sha256="2" * 64,
        authority="fixture",
        identity_source_url="fixture://ident",
        parameter_source_url="fixture://parameters",
        catalogue_release="fixture-v1",
    )[0]
    assert lock.match_basis == "OGLE_IV_IDENT_OGLE_III_ID"
    assert lock.current_object_id == "OGLE-LMC-DSCT-10003"
    assert lock.mode_label == "singlemode_radial_order_unresolved"
    assert verify_lock_payload(lock.as_dict())


def test_duplicate_crosswalk_is_rejected() -> None:
    identities = [
        Ogle4LmcDsctIdentity.parse(identity_line(current=10003)),
        Ogle4LmcDsctIdentity.parse(identity_line(current=10004)),
    ]
    parameters = [
        Ogle4LmcDsctParameters.parse(parameter_line(current=10003)),
        Ogle4LmcDsctParameters.parse(parameter_line(current=10004)),
    ]
    with pytest.raises(KeyError, match="exactly one"):
        resolve_delta_scuti_metadata(
            ["OGLE-LMC-DSCT-0003"], identities, parameters,
            identity_catalog_sha256="1" * 64,
            parameter_catalog_sha256="2" * 64,
            authority="fixture",
            identity_source_url="fixture://ident",
            parameter_source_url="fixture://parameters",
            catalogue_release="fixture-v1",
        )
