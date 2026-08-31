"""Phase-21 exact two-hop OGLE-III to current Delta-Scuti crosswalks.

The legacy OGLE-III ``ident.dat`` does not use the old ``OGLE-LMC-DSCT-NNNN``
identity as the current catalogue cross-reference.  It maps that object to a
field identity such as ``LMC158.5.3261``.  Phase 21 therefore requires two
explicit exact hops:

``old object ID -> old field ID -> current ident.OGLE-III field``.

No numeric-suffix, nearest-coordinate, or zero-padding fallback is permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

from .ogle_catalog import canonical_json_sha256


@dataclass(frozen=True, slots=True)
class Ogle3LmcDsctLegacyIdentity:
    object_id: str
    field_id: str
    subtype: str
    ra_hms: str
    dec_dms: str
    raw_row_sha256: str

    @classmethod
    def parse(cls, raw_line: str) -> "Ogle3LmcDsctLegacyIdentity":
        line = raw_line.strip()
        parts = line.split()
        if len(parts) < 6:
            raise ValueError("legacy OGLE-III DSCT identity row requires six fields")
        object_id, field, number, subtype, ra_hms, dec_dms = parts[:6]
        if not object_id.startswith("OGLE-LMC-DSCT-"):
            raise ValueError(f"unexpected legacy DSCT identity: {object_id!r}")
        if not field.startswith("LMC") or not number.isdigit():
            raise ValueError("legacy field identity must be an LMC field plus integer object number")
        subtype = subtype.lower()
        if subtype not in {"singlemode", "multimode"}:
            raise ValueError(f"unexpected legacy subtype: {subtype!r}")
        return cls(
            object_id=object_id,
            field_id=f"{field}.{number}",
            subtype=subtype,
            ra_hms=ra_hms,
            dec_dms=dec_dms,
            raw_row_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "field_id": self.field_id,
            "subtype": self.subtype,
            "ra_hms": self.ra_hms,
            "dec_dms": self.dec_dms,
            "raw_row_sha256": self.raw_row_sha256,
        }


def validate_row_receipt(payload: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Validate a Phase-21 authoritative row-level receipt.

    This intentionally validates a row-query receipt, not a full-catalogue byte
    hash.  The scope distinction is part of the evidence object.
    """

    blockers: list[str] = []
    body = dict(payload)
    expected = str(body.pop("sha256_canonical_json", ""))
    if len(expected) != 64 or canonical_json_sha256(body) != expected:
        blockers.append("ROW_RECEIPT_CANONICAL_HASH_MISMATCH")
    records = payload.get("records", [])
    if not isinstance(records, list) or len(records) != 5:
        blockers.append("ROW_RECEIPT_MUST_CONTAIN_FIVE_RECORDS")
        return False, tuple(blockers)
    requested: list[str] = []
    for row in records:
        if not isinstance(row, dict):
            blockers.append("ROW_RECEIPT_RECORD_NOT_OBJECT")
            continue
        record_body = dict(row)
        record_expected = str(record_body.pop("record_sha256", ""))
        if len(record_expected) != 64 or canonical_json_sha256(record_body) != record_expected:
            blockers.append(f"{row.get('requested_object_id','UNKNOWN')}:RECORD_HASH_MISMATCH")
        requested_id = str(row.get("requested_object_id", ""))
        requested.append(requested_id)
        old = row.get("old_identity")
        if not isinstance(old, dict):
            blockers.append(f"{requested_id}:OLD_IDENTITY_MISSING")
            continue
        if str(old.get("object_id")) != requested_id:
            blockers.append(f"{requested_id}:OLD_IDENTITY_OBJECT_MISMATCH")
        field_id = str(old.get("ogle3_field_id", ""))
        if not field_id.startswith("LMC") or field_id.count(".") < 2:
            blockers.append(f"{requested_id}:OLD_FIELD_ID_INVALID")
        status = row.get("resolution_status")
        current = row.get("current_identity")
        params = row.get("current_parameters")
        if status == "LOCKED_EXACT_TWO_HOP_CROSSWALK":
            if not isinstance(current, dict) or not isinstance(params, dict):
                blockers.append(f"{requested_id}:LOCKED_ROW_MISSING_CURRENT_DATA")
            else:
                if current.get("ogle3_field_id") != field_id:
                    blockers.append(f"{requested_id}:TWO_HOP_FIELD_ID_MISMATCH")
                if current.get("current_object_id") != params.get("current_object_id"):
                    blockers.append(f"{requested_id}:CURRENT_ID_PARAMETER_ID_MISMATCH")
                period = params.get("primary_period_days")
                error = params.get("primary_period_error_days")
                if not isinstance(period, (int, float)) or float(period) <= 0:
                    blockers.append(f"{requested_id}:PERIOD_INVALID")
                if not isinstance(error, (int, float)) or float(error) < 0:
                    blockers.append(f"{requested_id}:PERIOD_ERROR_INVALID")
        elif status == "NO_EXACT_CURRENT_CATALOG_CROSSWALK":
            if current is not None or params is not None:
                blockers.append(f"{requested_id}:UNRESOLVED_ROW_MUST_NOT_CONTAIN_INFERRED_MATCH")
        else:
            blockers.append(f"{requested_id}:UNKNOWN_RESOLUTION_STATUS")
    if len(set(requested)) != 5:
        blockers.append("ROW_RECEIPT_REQUESTED_IDS_NOT_UNIQUE")
    return not blockers, tuple(blockers)


def validate_metadata_lock_manifest(
    payload: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    body = dict(payload)
    expected = str(body.pop("sha256_canonical_json", ""))
    if len(expected) != 64 or canonical_json_sha256(body) != expected:
        blockers.append("METADATA_LOCK_MANIFEST_HASH_MISMATCH")
    if payload.get("row_receipt_sha256") != receipt.get("sha256_canonical_json"):
        blockers.append("METADATA_LOCK_RECEIPT_LINK_MISMATCH")
    records = payload.get("records", [])
    unresolved = payload.get("unresolved_records", [])
    if len(records) != 3 or len(unresolved) != 2:
        blockers.append("EXPECTED_THREE_LOCKS_AND_TWO_UNRESOLVED_RECORDS")
    seen: set[str] = set()
    receipt_by_id = {str(r["requested_object_id"]): r for r in receipt.get("records", [])}
    for row in records:
        requested = str(row.get("requested_object_id", ""))
        seen.add(requested)
        row_body = dict(row)
        expected_row = str(row_body.pop("lock_sha256", ""))
        if len(expected_row) != 64 or canonical_json_sha256(row_body) != expected_row:
            blockers.append(f"{requested}:LOCK_HASH_MISMATCH")
        receipt_row = receipt_by_id.get(requested)
        if receipt_row is None or receipt_row.get("resolution_status") != "LOCKED_EXACT_TWO_HOP_CROSSWALK":
            blockers.append(f"{requested}:LOCK_NOT_SUPPORTED_BY_RECEIPT")
        elif row.get("old_ogle3_field_id") != receipt_row["old_identity"]["ogle3_field_id"]:
            blockers.append(f"{requested}:LOCK_OLD_FIELD_MISMATCH")
        if row.get("match_basis") != "EXACT_TWO_HOP_OGLE3_FIELD_ID_CROSSWALK":
            blockers.append(f"{requested}:LOCK_MATCH_BASIS_INVALID")
        if row.get("mode_label") not in {"singlemode_radial_order_unresolved", "multimode"}:
            blockers.append(f"{requested}:LOCK_MODE_LABEL_INVALID")
    for row in unresolved:
        requested = str(row.get("requested_object_id", ""))
        seen.add(requested)
        row_body = dict(row)
        expected_row = str(row_body.pop("record_sha256", ""))
        if len(expected_row) != 64 or canonical_json_sha256(row_body) != expected_row:
            blockers.append(f"{requested}:UNRESOLVED_HASH_MISMATCH")
        receipt_row = receipt_by_id.get(requested)
        if receipt_row is None or receipt_row.get("resolution_status") != "NO_EXACT_CURRENT_CATALOG_CROSSWALK":
            blockers.append(f"{requested}:UNRESOLVED_NOT_SUPPORTED_BY_RECEIPT")
        if row.get("status") != "UNRESOLVED_NO_EXACT_CURRENT_CATALOG_CROSSWALK":
            blockers.append(f"{requested}:UNRESOLVED_STATUS_INVALID")
    if seen != set(payload.get("requested_object_ids", [])):
        blockers.append("LOCK_AND_UNRESOLVED_IDENTITIES_DO_NOT_COVER_DENOMINATOR")
    return not blockers, tuple(blockers)


def exact_two_hop_match(
    legacy: Ogle3LmcDsctLegacyIdentity,
    current_rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Return one exact current match or ``None``; ambiguity is an error."""

    matches = [row for row in current_rows if row.get("ogle3_field_id") == legacy.field_id]
    if len(matches) > 1:
        raise ValueError(f"ambiguous exact current crosswalk for {legacy.object_id}")
    return matches[0] if matches else None
