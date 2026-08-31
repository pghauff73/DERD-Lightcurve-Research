"""Phase-04 population qualification and prospective holdout governance.

The population layer deliberately operates before model fitting. It checks source
provenance, file integrity, stratum coverage, and exposure history, then permits
cryptographic role assignment only when every frozen gate passes.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .provenance import sha256_path
from .sealing import seal_payload, stratified_role_partition, verify_seal


_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class StratumRequirement:
    stratum_id: str
    family: str
    description: str
    development_minimum: int
    sealed_minimum: int

    @property
    def total_minimum(self) -> int:
        return self.development_minimum + self.sealed_minimum

    def as_dict(self) -> dict[str, object]:
        return {
            "stratum_id": self.stratum_id,
            "family": self.family,
            "description": self.description,
            "development_minimum": self.development_minimum,
            "sealed_minimum": self.sealed_minimum,
            "total_minimum": self.total_minimum,
        }


@dataclass(frozen=True, slots=True)
class PopulationContract:
    contract_id: str
    required_fields: tuple[str, ...]
    requirements: tuple[StratumRequirement, ...]
    minimum_development: int
    minimum_sealed_holdout: int
    minimum_clean_observations: int
    minimum_phase_coverage_bins: int
    star_identity_rule: str
    rights_rule: str

    @property
    def requirement_by_id(self) -> dict[str, StratumRequirement]:
        return {item.stratum_id: item for item in self.requirements}

    def as_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "required_fields": list(self.required_fields),
            "minimum_development": self.minimum_development,
            "minimum_sealed_holdout": self.minimum_sealed_holdout,
            "minimum_clean_observations": self.minimum_clean_observations,
            "minimum_phase_coverage_bins": self.minimum_phase_coverage_bins,
            "star_identity_rule": self.star_identity_rule,
            "rights_rule": self.rights_rule,
            "requirements": [item.as_dict() for item in self.requirements],
        }


@dataclass(frozen=True, slots=True)
class PopulationIssue:
    code: str
    severity: str
    message: str
    star_id: str | None = None
    stratum: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "star_id": self.star_id,
            "stratum": self.stratum,
        }


@dataclass(frozen=True, slots=True)
class PopulationAudit:
    contract_id: str
    candidate_count: int
    unique_star_count: int
    file_verification_requested: bool
    files_verified: int
    stratum_counts: dict[str, int]
    stratum_deficits: dict[str, int]
    family_counts: dict[str, int]
    exposed_overlap: tuple[str, ...]
    issues: tuple[PopulationIssue, ...]
    ready_for_sealing: bool

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    def as_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "candidate_count": self.candidate_count,
            "unique_star_count": self.unique_star_count,
            "file_verification_requested": self.file_verification_requested,
            "files_verified": self.files_verified,
            "stratum_counts": dict(sorted(self.stratum_counts.items())),
            "stratum_deficits": dict(sorted(self.stratum_deficits.items())),
            "family_counts": dict(sorted(self.family_counts.items())),
            "exposed_overlap": list(self.exposed_overlap),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "ready_for_sealing": self.ready_for_sealing,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def load_population_contract(path: str | Path) -> PopulationContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required_fields = tuple(str(value) for value in payload.get("required_fields", ()))
    if not required_fields:
        raise ValueError("population contract has no required_fields")
    requirements: list[StratumRequirement] = []
    for item in payload.get("strata", ()):  # type: ignore[assignment]
        requirement = StratumRequirement(
            stratum_id=str(item["stratum_id"]).strip(),
            family=str(item["family"]).strip(),
            description=str(item["description"]).strip(),
            development_minimum=int(item["development_minimum"]),
            sealed_minimum=int(item["sealed_minimum"]),
        )
        if not requirement.stratum_id or requirement.development_minimum < 1 or requirement.sealed_minimum < 1:
            raise ValueError("invalid stratum requirement")
        requirements.append(requirement)
    if not requirements:
        raise ValueError("population contract has no strata")
    identifiers = [item.stratum_id for item in requirements]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("population contract contains duplicate strata")
    minimum_counts = payload.get("minimum_counts", {})
    quality = payload.get("data_quality", {})
    return PopulationContract(
        contract_id=str(payload["contract_id"]),
        required_fields=required_fields,
        requirements=tuple(requirements),
        minimum_development=int(minimum_counts.get("development", 0)),
        minimum_sealed_holdout=int(minimum_counts.get("sealed_holdout", 0)),
        minimum_clean_observations=int(quality.get("minimum_clean_observations", 0)),
        minimum_phase_coverage_bins=int(quality.get("minimum_phase_coverage_bins", 0)),
        star_identity_rule=str(payload.get("star_identity_rule", "")),
        rights_rule=str(payload.get("rights_rule", "")),
    )


def read_population_manifest(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("candidate manifest has no header")
        rows = [
            {str(key): str(value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    if not rows:
        raise ValueError("candidate manifest is empty")
    return rows


def read_exposed_star_ids(path: str | Path | None) -> set[str]:
    if path is None:
        return set()
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            values = payload.get("star_ids", payload.get("exposed_star_ids", ()))
        else:
            values = payload
        return {str(value).strip() for value in values if str(value).strip()}
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "star_id" not in reader.fieldnames:
                raise ValueError("exposed CSV must contain star_id")
            return {
                str(row.get("star_id", "")).strip()
                for row in reader
                if str(row.get("star_id", "")).strip()
            }
    return {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in _HEX for character in value.lower())


def _safe_candidate_path(data_root: Path, relative: str) -> Path:
    if not relative:
        raise ValueError("relative_path is empty")
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("relative_path must be relative")
    candidate = (data_root / raw).resolve()
    root = data_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("relative_path escapes data root") from exc
    return candidate


def audit_population(
    records: Sequence[Mapping[str, str]],
    contract: PopulationContract,
    *,
    data_root: str | Path | None = None,
    exposed_star_ids: Iterable[str] = (),
    verify_files: bool = True,
) -> PopulationAudit:
    issues: list[PopulationIssue] = []
    requirement_by_id = contract.requirement_by_id
    exposed = {str(value).strip() for value in exposed_star_ids if str(value).strip()}
    star_ids = [str(record.get("star_id", "")).strip() for record in records]
    counts: dict[str, int] = {item.stratum_id: 0 for item in contract.requirements}
    family_counts: dict[str, int] = {}
    files_verified = 0
    seen: set[str] = set()
    duplicates: set[str] = set()
    root = None if data_root is None else Path(data_root)

    for index, record in enumerate(records, start=1):
        star_id = str(record.get("star_id", "")).strip()
        stratum = str(record.get("stratum", "")).strip()
        if star_id in seen:
            duplicates.add(star_id)
        seen.add(star_id)

        for field in contract.required_fields:
            if not str(record.get(field, "")).strip():
                issues.append(
                    PopulationIssue(
                        code="MISSING_REQUIRED_FIELD",
                        severity="error",
                        message=f"row {index} is missing required field {field}",
                        star_id=star_id or None,
                        stratum=stratum or None,
                    )
                )

        if stratum and stratum not in requirement_by_id:
            issues.append(
                PopulationIssue(
                    code="UNKNOWN_STRATUM",
                    severity="error",
                    message=f"stratum {stratum!r} is not in the frozen contract",
                    star_id=star_id or None,
                    stratum=stratum,
                )
            )
        elif stratum:
            counts[stratum] += 1
            family = requirement_by_id[stratum].family
            family_counts[family] = family_counts.get(family, 0) + 1

        period_text = str(record.get("period_days", "")).strip()
        if period_text:
            try:
                period = float(period_text)
            except ValueError:
                period = float("nan")
            if not math.isfinite(period) or period <= 0.0:
                issues.append(
                    PopulationIssue(
                        code="INVALID_PERIOD",
                        severity="error",
                        message="period_days must be finite and positive",
                        star_id=star_id or None,
                        stratum=stratum or None,
                    )
                )

        observation_text = str(record.get("observation_count", "")).strip()
        if contract.minimum_clean_observations > 0 and observation_text:
            try:
                observation_count = int(observation_text)
            except ValueError:
                observation_count = -1
            if observation_count < contract.minimum_clean_observations:
                issues.append(
                    PopulationIssue(
                        code="INSUFFICIENT_OBSERVATIONS",
                        severity="error",
                        message=(
                            f"requires at least {contract.minimum_clean_observations} clean observations, "
                            f"observed {observation_text!r}"
                        ),
                        star_id=star_id or None,
                        stratum=stratum or None,
                    )
                )

        coverage_text = str(record.get("phase_coverage_bins", "")).strip()
        if contract.minimum_phase_coverage_bins > 0 and coverage_text:
            try:
                coverage_bins = int(coverage_text)
            except ValueError:
                coverage_bins = -1
            if coverage_bins < contract.minimum_phase_coverage_bins:
                issues.append(
                    PopulationIssue(
                        code="INSUFFICIENT_PHASE_COVERAGE",
                        severity="error",
                        message=(
                            f"requires at least {contract.minimum_phase_coverage_bins} occupied phase bins, "
                            f"observed {coverage_text!r}"
                        ),
                        star_id=star_id or None,
                        stratum=stratum or None,
                    )
                )

        expected_sha = str(record.get("source_sha256", "")).strip().lower()
        if expected_sha and not _valid_sha256(expected_sha):
            issues.append(
                PopulationIssue(
                    code="INVALID_SOURCE_SHA256",
                    severity="error",
                    message="source_sha256 must contain 64 hexadecimal characters",
                    star_id=star_id or None,
                    stratum=stratum or None,
                )
            )

        if verify_files:
            if root is None:
                issues.append(
                    PopulationIssue(
                        code="DATA_ROOT_REQUIRED",
                        severity="error",
                        message="data_root is required when file verification is enabled",
                        star_id=star_id or None,
                        stratum=stratum or None,
                    )
                )
            else:
                try:
                    candidate = _safe_candidate_path(root, str(record.get("relative_path", "")).strip())
                except ValueError as exc:
                    issues.append(
                        PopulationIssue(
                            code="UNSAFE_RELATIVE_PATH",
                            severity="error",
                            message=str(exc),
                            star_id=star_id or None,
                            stratum=stratum or None,
                        )
                    )
                else:
                    if not candidate.is_file():
                        issues.append(
                            PopulationIssue(
                                code="SOURCE_FILE_MISSING",
                                severity="error",
                                message=f"source file not found: {candidate}",
                                star_id=star_id or None,
                                stratum=stratum or None,
                            )
                        )
                    elif _valid_sha256(expected_sha):
                        actual = sha256_path(candidate)
                        if actual != expected_sha:
                            issues.append(
                                PopulationIssue(
                                    code="SOURCE_SHA256_MISMATCH",
                                    severity="error",
                                    message=f"expected {expected_sha}, observed {actual}",
                                    star_id=star_id or None,
                                    stratum=stratum or None,
                                )
                            )
                        else:
                            files_verified += 1

    for star_id in sorted(value for value in duplicates if value):
        issues.append(
            PopulationIssue(
                code="DUPLICATE_STAR_ID",
                severity="error",
                message="candidate manifest must contain one package row per star",
                star_id=star_id,
            )
        )

    exposed_overlap = tuple(sorted(set(star_ids) & exposed - {""}))
    for star_id in exposed_overlap:
        issues.append(
            PopulationIssue(
                code="PRIOR_EXPOSURE",
                severity="error",
                message="star was used in an earlier development or shakedown phase",
                star_id=star_id,
            )
        )

    deficits: dict[str, int] = {}
    for requirement in contract.requirements:
        deficit = max(0, requirement.total_minimum - counts[requirement.stratum_id])
        deficits[requirement.stratum_id] = deficit
        if deficit:
            issues.append(
                PopulationIssue(
                    code="STRATUM_DEFICIT",
                    severity="error",
                    message=(
                        f"requires {requirement.total_minimum} stars, observed "
                        f"{counts[requirement.stratum_id]}"
                    ),
                    stratum=requirement.stratum_id,
                )
            )

    required_total = contract.minimum_development + contract.minimum_sealed_holdout
    if len(set(star_ids) - {""}) < required_total:
        issues.append(
            PopulationIssue(
                code="TOTAL_POPULATION_DEFICIT",
                severity="error",
                message=(
                    f"contract requires at least {required_total} unique stars, observed "
                    f"{len(set(star_ids) - {''})}"
                ),
            )
        )

    ready = not any(issue.severity == "error" for issue in issues)
    return PopulationAudit(
        contract_id=contract.contract_id,
        candidate_count=len(records),
        unique_star_count=len(set(star_ids) - {""}),
        file_verification_requested=verify_files,
        files_verified=files_verified,
        stratum_counts=counts,
        stratum_deficits=deficits,
        family_counts=family_counts,
        exposed_overlap=exposed_overlap,
        issues=tuple(issues),
        ready_for_sealing=ready,
    )


def build_role_manifest(
    records: Sequence[Mapping[str, str]],
    contract: PopulationContract,
    audit: PopulationAudit,
    *,
    candidate_manifest_sha256: str,
    contract_sha256: str,
    analysis_plan_sha256: str,
    code_manifest_sha256: str,
    seed: int = 20260808,
) -> tuple[dict[str, object], dict[str, str]]:
    if not audit.ready_for_sealing:
        raise ValueError("population audit has not passed")
    if not all(_valid_sha256(value) for value in (
        candidate_manifest_sha256,
        contract_sha256,
        analysis_plan_sha256,
        code_manifest_sha256,
    )):
        raise ValueError("all linked artifact digests must be SHA-256 values")
    sealed_values = {item.sealed_minimum for item in contract.requirements}
    development_values = {item.development_minimum for item in contract.requirements}
    if len(sealed_values) != 1 or len(development_values) != 1:
        raise ValueError("current role partition requires uniform per-stratum minima")
    roles = stratified_role_partition(
        [dict(record) for record in records],
        sealed_per_stratum=next(iter(sealed_values)),
        minimum_development_per_stratum=next(iter(development_values)),
        seed=seed,
    )
    role_rows = [
        {**{str(key): str(value) for key, value in record.items()}, "role": roles[str(record["star_id"])]}
        for record in records
    ]
    role_rows.sort(key=lambda row: (row["stratum"], row["role"], row["star_id"]))
    payload: dict[str, object] = {
        "implementation_id": "DERD-v0.4-phase04-readiness",
        "protocol": "PHASE04_STRATIFIED_STAR_IDENTITY_HOLDOUT",
        "contract_id": contract.contract_id,
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "contract_sha256": contract_sha256,
        "analysis_plan_sha256": analysis_plan_sha256,
        "code_manifest_sha256": code_manifest_sha256,
        "seed": seed,
        "population_audit": audit.as_dict(),
        "roles": role_rows,
    }
    return payload, seal_payload(payload).as_dict()


def verify_role_manifest(payload: Mapping[str, object], seal: Mapping[str, str]) -> bool:
    digest = str(seal.get("digest", ""))
    if not _valid_sha256(digest):
        return False
    return verify_seal(dict(payload), digest)
