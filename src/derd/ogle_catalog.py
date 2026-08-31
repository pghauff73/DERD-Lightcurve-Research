"""Authoritative OGLE catalogue parsing and cryptographic metadata locks.

Phase 10 separates *catalogue coordinates* from *photometric evidence*.  The
primary use case is resolving an OGLE-III LMC delta-Scuti identity through the
explicit OGLE-III identifier field in the OGLE-IV ``ident.dat`` file and then
joining it to the primary period in ``dsct.dat``.

The parser follows the byte ranges published in the OGLE/VizieR catalogue
ReadMe for J/AcA/73/105.  It deliberately preserves the catalogue subtype
(``singlemode`` or ``multimode``); it does not invent a radial-mode label for a
single-mode object.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


OGLE4_LMC_DSCT_RECORD_COUNT = 15_256
OGLE4_LMC_DSCT_IDENT_FILENAME = "ident.dat"
OGLE4_LMC_DSCT_PARAMETERS_FILENAME = "dsct.dat"


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_text_line(line: str) -> str:
    """Hash one logical catalogue row after removing only its line terminator."""

    return hashlib.sha256(line.rstrip("\r\n").encode("utf-8")).hexdigest()




def normalize_lmc_dsct_id(value: str | None) -> str | None:
    """Normalize OGLE LMC DSCT aliases without changing the numeric identity.

    OGLE catalogue cross-reference columns may omit the leading ``OGLE-`` to
    fit legacy fixed-width fields.  This normalization is explicit and exact;
    it is not a suffix-similarity match.
    """

    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("OGLE-LMC-DSCT-"):
        return text
    if text.startswith("LMC-DSCT-"):
        return "OGLE-" + text
    return text

def _slice(line: str, start: int, stop: int | None = None) -> str:
    """Return a stripped 1-indexed inclusive fixed-width field."""

    zero_start = start - 1
    zero_stop = None if stop is None else stop
    return line[zero_start:zero_stop].strip()


def _optional_float(text: str) -> float | None:
    value = text.strip()
    if not value or value == "-":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite catalogue value: {value!r}")
    return parsed


@dataclass(frozen=True, slots=True)
class Ogle4LmcDsctIdentity:
    object_id: str
    subtype: str
    ra_hms: str
    dec_dms: str
    ogle4_id: str | None
    ogle3_id: str | None
    ogle2_id: str | None
    other_name: str | None
    row_sha256: str

    @classmethod
    def parse(cls, raw_line: str) -> "Ogle4LmcDsctIdentity":
        line = raw_line.rstrip("\r\n")
        if len(line) < 56:
            raise ValueError("OGLE-IV ident row is shorter than the required coordinate fields")
        object_id = _slice(line, 1, 19)
        subtype = _slice(line, 22, 31).lower()
        if not object_id.startswith("OGLE-LMC-DSCT-"):
            raise ValueError(f"unexpected OGLE LMC DSCT identity: {object_id!r}")
        if subtype not in {"singlemode", "multimode"}:
            raise ValueError(f"unexpected delta-Scuti subtype: {subtype!r}")
        ra_hms = f"{_slice(line, 34, 35)}:{_slice(line, 37, 38)}:{_slice(line, 40, 44)}"
        dec_dms = f"{_slice(line, 46, 48)}:{_slice(line, 50, 51)}:{_slice(line, 53, 56)}"

        def optional(start: int, stop: int | None = None) -> str | None:
            value = _slice(line, start, stop)
            return value or None

        return cls(
            object_id=object_id,
            subtype=subtype,
            ra_hms=ra_hms,
            dec_dms=dec_dms,
            ogle4_id=optional(59, 74),
            ogle3_id=optional(76, 90),
            ogle2_id=optional(92, 107),
            other_name=optional(109, None),
            row_sha256=sha256_text_line(line),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "subtype": self.subtype,
            "ra_hms": self.ra_hms,
            "dec_dms": self.dec_dms,
            "ogle4_id": self.ogle4_id,
            "ogle3_id": self.ogle3_id,
            "ogle2_id": self.ogle2_id,
            "other_name": self.other_name,
            "row_sha256": self.row_sha256,
        }


@dataclass(frozen=True, slots=True)
class Ogle4LmcDsctParameters:
    object_id: str
    mean_i_mag: float
    mean_v_mag: float | None
    primary_period_days: float
    primary_period_error_days: float
    primary_epoch_hjd_minus_2450000: float
    primary_i_amplitude_mag: float
    secondary_period_days: float | None
    tertiary_period_days: float | None
    row_sha256: str

    @classmethod
    def parse(cls, raw_line: str) -> "Ogle4LmcDsctParameters":
        line = raw_line.rstrip("\r\n")
        if len(line) < 102:
            raise ValueError("OGLE-IV dsct row is shorter than the required primary-period fields")
        object_id = _slice(line, 1, 19)
        if not object_id.startswith("OGLE-LMC-DSCT-"):
            raise ValueError(f"unexpected OGLE LMC DSCT parameter identity: {object_id!r}")
        period = float(_slice(line, 37, 46))
        period_error = float(_slice(line, 48, 57))
        if not (math.isfinite(period) and period > 0.0):
            raise ValueError("primary period must be finite and positive")
        if not (math.isfinite(period_error) and period_error >= 0.0):
            raise ValueError("primary period error must be finite and non-negative")
        return cls(
            object_id=object_id,
            mean_i_mag=float(_slice(line, 22, 27)),
            mean_v_mag=_optional_float(_slice(line, 29, 34)),
            primary_period_days=period,
            primary_period_error_days=period_error,
            primary_epoch_hjd_minus_2450000=float(_slice(line, 60, 69)),
            primary_i_amplitude_mag=float(_slice(line, 72, 76)),
            secondary_period_days=_optional_float(_slice(line, 105, 114)),
            tertiary_period_days=_optional_float(_slice(line, 173, 182)),
            row_sha256=sha256_text_line(line),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "mean_i_mag": self.mean_i_mag,
            "mean_v_mag": self.mean_v_mag,
            "primary_period_days": self.primary_period_days,
            "primary_period_error_days": self.primary_period_error_days,
            "primary_epoch_hjd_minus_2450000": self.primary_epoch_hjd_minus_2450000,
            "primary_i_amplitude_mag": self.primary_i_amplitude_mag,
            "secondary_period_days": self.secondary_period_days,
            "tertiary_period_days": self.tertiary_period_days,
            "row_sha256": self.row_sha256,
        }


@dataclass(frozen=True, slots=True)
class DeltaScutiMetadataLock:
    requested_object_id: str
    current_object_id: str
    match_basis: str
    subtype: str
    mode_label: str
    primary_period_days: float
    primary_period_error_days: float
    identity_row_sha256: str
    parameter_row_sha256: str
    identity_catalog_sha256: str
    parameter_catalog_sha256: str
    authority: str
    identity_source_url: str
    parameter_source_url: str
    catalogue_release: str
    lock_sha256: str

    @classmethod
    def create(
        cls,
        *,
        requested_object_id: str,
        identity: Ogle4LmcDsctIdentity,
        parameters: Ogle4LmcDsctParameters,
        match_basis: str,
        identity_catalog_sha256: str,
        parameter_catalog_sha256: str,
        authority: str,
        identity_source_url: str,
        parameter_source_url: str,
        catalogue_release: str,
    ) -> "DeltaScutiMetadataLock":
        if identity.object_id != parameters.object_id:
            raise ValueError("identity and parameter rows do not describe the same object")
        if match_basis not in {"DIRECT_CURRENT_ID", "OGLE_IV_IDENT_OGLE_III_ID"}:
            raise ValueError(f"unsupported match basis: {match_basis}")
        mode_label = (
            "multimode"
            if identity.subtype == "multimode"
            else "singlemode_radial_order_unresolved"
        )
        payload = {
            "requested_object_id": requested_object_id,
            "current_object_id": identity.object_id,
            "match_basis": match_basis,
            "subtype": identity.subtype,
            "mode_label": mode_label,
            "primary_period_days": parameters.primary_period_days,
            "primary_period_error_days": parameters.primary_period_error_days,
            "identity_row_sha256": identity.row_sha256,
            "parameter_row_sha256": parameters.row_sha256,
            "identity_catalog_sha256": identity_catalog_sha256,
            "parameter_catalog_sha256": parameter_catalog_sha256,
            "authority": authority,
            "identity_source_url": identity_source_url,
            "parameter_source_url": parameter_source_url,
            "catalogue_release": catalogue_release,
        }
        return cls(**payload, lock_sha256=canonical_json_sha256(payload))

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_object_id": self.requested_object_id,
            "current_object_id": self.current_object_id,
            "match_basis": self.match_basis,
            "subtype": self.subtype,
            "mode_label": self.mode_label,
            "primary_period_days": self.primary_period_days,
            "primary_period_error_days": self.primary_period_error_days,
            "identity_row_sha256": self.identity_row_sha256,
            "parameter_row_sha256": self.parameter_row_sha256,
            "identity_catalog_sha256": self.identity_catalog_sha256,
            "parameter_catalog_sha256": self.parameter_catalog_sha256,
            "authority": self.authority,
            "identity_source_url": self.identity_source_url,
            "parameter_source_url": self.parameter_source_url,
            "catalogue_release": self.catalogue_release,
            "lock_sha256": self.lock_sha256,
        }


def parse_identity_catalog(lines: Iterable[str]) -> tuple[Ogle4LmcDsctIdentity, ...]:
    records = tuple(Ogle4LmcDsctIdentity.parse(line) for line in lines if line.strip() and not line.lstrip().startswith("#"))
    _ensure_unique((record.object_id for record in records), "identity object_id")
    return records


def parse_parameter_catalog(lines: Iterable[str]) -> tuple[Ogle4LmcDsctParameters, ...]:
    records = tuple(Ogle4LmcDsctParameters.parse(line) for line in lines if line.strip() and not line.lstrip().startswith("#"))
    _ensure_unique((record.object_id for record in records), "parameter object_id")
    return records


def _ensure_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"duplicate {label}: {sorted(duplicates)!r}")


def resolve_delta_scuti_metadata(
    requested_ids: Sequence[str],
    identities: Sequence[Ogle4LmcDsctIdentity],
    parameters: Sequence[Ogle4LmcDsctParameters],
    *,
    identity_catalog_sha256: str,
    parameter_catalog_sha256: str,
    authority: str,
    identity_source_url: str,
    parameter_source_url: str,
    catalogue_release: str,
) -> tuple[DeltaScutiMetadataLock, ...]:
    """Resolve requested OGLE-III/current IDs without string-assumption shortcuts.

    A request may match either the current catalogue object ID or the explicit
    ``OGLE-III`` cross-reference column.  Exactly one identity row and exactly
    one parameter row are required.
    """

    by_current = {normalize_lmc_dsct_id(record.object_id): record for record in identities}
    by_old: dict[str, list[Ogle4LmcDsctIdentity]] = {}
    for record in identities:
        normalized_old = normalize_lmc_dsct_id(record.ogle3_id)
        if normalized_old:
            by_old.setdefault(normalized_old, []).append(record)
    by_parameter = {record.object_id: record for record in parameters}
    locks: list[DeltaScutiMetadataLock] = []
    for requested in requested_ids:
        normalized_requested = normalize_lmc_dsct_id(requested)
        if normalized_requested is None:
            raise KeyError("empty requested identity")
        candidates: list[tuple[Ogle4LmcDsctIdentity, str]] = []
        if normalized_requested in by_current:
            candidates.append((by_current[normalized_requested], "DIRECT_CURRENT_ID"))
        for candidate in by_old.get(normalized_requested, []):
            if not any(existing.object_id == candidate.object_id for existing, _ in candidates):
                candidates.append((candidate, "OGLE_IV_IDENT_OGLE_III_ID"))
        if len(candidates) != 1:
            raise KeyError(
                f"{requested}: expected exactly one authoritative identity match, found {len(candidates)}"
            )
        identity, basis = candidates[0]
        try:
            parameter = by_parameter[identity.object_id]
        except KeyError as error:
            raise KeyError(f"{requested}: parameter row missing for {identity.object_id}") from error
        locks.append(
            DeltaScutiMetadataLock.create(
                requested_object_id=requested,
                identity=identity,
                parameters=parameter,
                match_basis=basis,
                identity_catalog_sha256=identity_catalog_sha256,
                parameter_catalog_sha256=parameter_catalog_sha256,
                authority=authority,
                identity_source_url=identity_source_url,
                parameter_source_url=parameter_source_url,
                catalogue_release=catalogue_release,
            )
        )
    _ensure_unique((lock.current_object_id for lock in locks), "resolved current object_id")
    return tuple(locks)


def load_catalog_lines(path: str | Path) -> tuple[str, ...]:
    return tuple(Path(path).read_text(encoding="utf-8").splitlines())


def verify_lock_payload(lock_payload: Mapping[str, Any]) -> bool:
    expected = str(lock_payload.get("lock_sha256", ""))
    payload = dict(lock_payload)
    payload.pop("lock_sha256", None)
    return len(expected) == 64 and canonical_json_sha256(payload) == expected
