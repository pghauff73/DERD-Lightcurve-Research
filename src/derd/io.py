"""Light-curve parsers, target manifests, and deterministic checksums."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from .lightcurve import LightCurve, ValueDomain


@dataclass(frozen=True, slots=True)
class TargetRecord:
    star_id: str
    mode: str
    period_days: float
    relative_path: str
    source_blob_sha: str
    source_repository: str
    source_commit: str
    period_source_repository: str
    period_source_commit: str

    @classmethod
    def from_mapping(cls, row: dict[str, str]) -> "TargetRecord":
        period = float(row["period_days"])
        if not np.isfinite(period) or period <= 0.0:
            raise ValueError(f"invalid period for {row.get('star_id', '<unknown>')}")
        return cls(
            star_id=row["star_id"].strip(),
            mode=row["mode"].strip(),
            period_days=period,
            relative_path=row["relative_path"].strip(),
            source_blob_sha=row["source_blob_sha"].strip(),
            source_repository=row["source_repository"].strip(),
            source_commit=row["source_commit"].strip(),
            period_source_repository=row["period_source_repository"].strip(),
            period_source_commit=row["period_source_commit"].strip(),
        )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_ogle_photometry(
    path: str | Path,
    *,
    star_id: str,
    band: str = "I",
    metadata: dict[str, object] | None = None,
) -> LightCurve:
    """Read the three-column OGLE photometry format.

    Columns are HJD-2450000, magnitude, and one-sigma magnitude error.
    Blank lines and lines beginning with ``#`` are ignored.
    """

    source = Path(path)
    rows: list[tuple[float, float, float]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            if len(fields) != 3:
                raise ValueError(f"{source}:{line_number}: expected three columns")
            try:
                rows.append(tuple(float(field) for field in fields))
            except ValueError as exc:
                raise ValueError(f"{source}:{line_number}: non-numeric photometry") from exc
    if not rows:
        raise ValueError(f"{source} contains no photometry")
    array = np.asarray(rows, dtype=np.float64)
    provenance = dict(metadata or {})
    provenance.update(
        {
            "local_path": str(source),
            "local_sha256": sha256_file(source),
            "format": "OGLE three-column photometry",
            "time_system": "HJD-2450000",
        }
    )
    return LightCurve(
        star_id=star_id,
        time=array[:, 0],
        value=array[:, 1],
        error=array[:, 2],
        band=band,
        domain=ValueDomain.MAGNITUDE,
        metadata=provenance,
    )


def read_target_manifest(path: str | Path) -> list[TargetRecord]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "star_id",
            "mode",
            "period_days",
            "relative_path",
            "source_blob_sha",
            "source_repository",
            "source_commit",
            "period_source_repository",
            "period_source_commit",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"target manifest missing columns: {missing}")
        records = [TargetRecord.from_mapping(dict(row)) for row in reader]
    if not records:
        raise ValueError("target manifest is empty")
    ids = [record.star_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("target manifest contains duplicate star IDs")
    return records


def write_json(path: str | Path, payload: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_checksum_manifest(paths: Iterable[str | Path], destination: str | Path, *, root: str | Path) -> None:
    root_path = Path(root).resolve()
    entries: list[tuple[str, str]] = []
    for item in paths:
        path = Path(item).resolve()
        entries.append((str(path.relative_to(root_path)), sha256_file(path)))
    entries.sort()
    Path(destination).write_text(
        "".join(f"{digest}  {relative}\n" for relative, digest in entries),
        encoding="utf-8",
    )
