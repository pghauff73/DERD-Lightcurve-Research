"""Cryptographic manifests for prospective star-identity holdout governance."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Seal:
    algorithm: str
    digest: str
    canonical_payload: str

    def as_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "digest": self.digest,
            "canonical_payload": self.canonical_payload,
        }


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def seal_payload(payload: object) -> Seal:
    canonical = canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Seal(algorithm="sha256", digest=digest, canonical_payload=canonical)


def verify_seal(payload: object, digest: str) -> bool:
    return seal_payload(payload).digest == str(digest).lower()


def assert_no_sealed_evaluation(
    star_ids: list[str],
    roles: Mapping[str, str],
    *,
    sealed_role: str = "sealed_holdout",
) -> None:
    evaluated = set(star_ids)
    sealed = {star_id for star_id, role in roles.items() if role == sealed_role}
    overlap = sorted(evaluated & sealed)
    if overlap:
        raise PermissionError(f"sealed stars cannot be evaluated: {overlap}")


def stratified_role_partition(
    records: list[Mapping[str, str]],
    *,
    sealed_per_stratum: int,
    minimum_development_per_stratum: int,
    seed: int = 20260808,
) -> dict[str, str]:
    """Assign complete stars to development or sealed holdout by stratum.

    Records must contain unique ``star_id`` and non-empty ``stratum`` fields.
    Assignment uses only identifiers, stratum labels, and the fixed seed.
    """

    if sealed_per_stratum < 1:
        raise ValueError("sealed_per_stratum must be positive")
    if minimum_development_per_stratum < 1:
        raise ValueError("minimum_development_per_stratum must be positive")
    identifiers = [str(record.get("star_id", "")).strip() for record in records]
    if not identifiers or any(not value for value in identifiers):
        raise ValueError("every record must contain a non-empty star_id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("star IDs must be unique")

    grouped: dict[str, list[str]] = {}
    for record, star_id in zip(records, identifiers, strict=True):
        stratum = str(record.get("stratum", "")).strip()
        if not stratum:
            raise ValueError(f"record {star_id} is missing stratum")
        grouped.setdefault(stratum, []).append(star_id)

    roles: dict[str, str] = {}
    for stratum, members in sorted(grouped.items()):
        required = sealed_per_stratum + minimum_development_per_stratum
        if len(members) < required:
            raise ValueError(
                f"stratum {stratum!r} has {len(members)} stars but requires at least {required}"
            )
        ranked = sorted(
            members,
            key=lambda star_id: hashlib.sha256(
                f"{seed}:{stratum}:{star_id}".encode("utf-8")
            ).digest(),
        )
        sealed = set(ranked[:sealed_per_stratum])
        for star_id in members:
            roles[star_id] = "sealed_holdout" if star_id in sealed else "development"
    return roles
