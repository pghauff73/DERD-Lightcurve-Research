"""Phase-16 cross-version reproducibility graph and multiplicity guard.

The cumulative ledger contains one denominator record per astronomical object,
but several objects have been analysed by more than one software phase.  This
module builds an explicit graph of analysis versions and distinguishes:

* exact scientific replay with permitted metadata transport drift;
* configuration-sensitive scientific drift on the same source;
* single-version evidence with no replay test;
* external independent replication, which is absent in the current ledger.

Multiple analyses of the same observations never increase the astrophysical
denominator.  The graph concerns computational reproducibility and normalized
waveform evidence only; it does not identify a physical mechanism or shell.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ogle_catalog import canonical_json_sha256
from .validation_phase12 import sha256_file, verify_evidence_record


PHASE16_DECISION = "PHASE16_REPRODUCIBILITY_GRAPH_SEALED_POPULATION_GATE_CLOSED"

EDGE_EXACT = "EXACT_SCIENTIFIC_REPLAY_METADATA_TRANSPORT_DRIFT"
EDGE_CONFIG_DRIFT = "CONFIGURATION_SENSITIVE_SCIENTIFIC_DRIFT"
EDGE_SINGLE = "SINGLE_VERSION_NO_REPLAY_TEST"


@dataclass(frozen=True, slots=True)
class ReproducibilityEdge:
    object_id: str
    source_version: str
    comparison_version: str
    same_observational_source: bool
    same_scientific_configuration: bool
    scientific_match: bool
    exchange_match: bool
    stage_match: bool
    disposition_match: bool
    maximum_harmonic_snr_absolute_difference: float | None
    screen_score_difference: float | None
    threshold_difference: float | None
    classification: str
    counts_as_independent_astrophysical_replication: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "source_version": self.source_version,
            "comparison_version": self.comparison_version,
            "same_observational_source": self.same_observational_source,
            "same_scientific_configuration": self.same_scientific_configuration,
            "scientific_match": self.scientific_match,
            "exchange_match": self.exchange_match,
            "stage_match": self.stage_match,
            "disposition_match": self.disposition_match,
            "maximum_harmonic_snr_absolute_difference": self.maximum_harmonic_snr_absolute_difference,
            "screen_score_difference": self.screen_score_difference,
            "threshold_difference": self.threshold_difference,
            "classification": self.classification,
            "counts_as_independent_astrophysical_replication": self.counts_as_independent_astrophysical_replication,
        }


@dataclass(frozen=True, slots=True)
class ReproducibilityGraph:
    object_ids: tuple[str, ...]
    analysis_nodes: tuple[Mapping[str, Any], ...]
    edges: tuple[ReproducibilityEdge, ...]
    single_version_objects: tuple[str, ...]
    exact_replay_count: int
    configuration_drift_count: int
    external_independent_replication_count: int
    unique_object_denominator: int
    analysis_version_count: int
    duplicate_analysis_inflation_prevented: int

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "object_ids": list(self.object_ids),
            "analysis_nodes": [dict(row) for row in self.analysis_nodes],
            "edges": [row.as_dict() for row in self.edges],
            "single_version_objects": list(self.single_version_objects),
            "exact_replay_count": self.exact_replay_count,
            "configuration_drift_count": self.configuration_drift_count,
            "external_independent_replication_count": self.external_independent_replication_count,
            "unique_object_denominator": self.unique_object_denominator,
            "analysis_version_count": self.analysis_version_count,
            "duplicate_analysis_inflation_prevented": self.duplicate_analysis_inflation_prevented,
            "multiplicity_guard": (
                "Each astronomical object contributes at most one denominator record, regardless of how many "
                "software phases analyse the same source bytes."
            ),
            "certificate": "NOT_A_PHYSICAL_CLAIM_CERTIFICATE",
            "claim_scope": "computational reproducibility and evidence multiplicity only",
        }
        payload["sha256_canonical_json"] = canonical_json_sha256(payload)
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"expected JSON object: {path}")
    return payload


def load_verified_phase15_ledger(
    *,
    root: str | Path,
    summary_path: str | Path = "artifacts/phase15/phase15_summary.json",
) -> tuple[tuple[Mapping[str, Any], ...], str, str, Mapping[str, Any], Mapping[str, Any]]:
    root_path = Path(root).resolve()
    candidate = Path(summary_path)
    summary_file = candidate if candidate.is_absolute() else root_path / candidate
    _require(summary_file.is_file(), f"Phase-15 summary missing: {summary_file}")
    summary_sha = sha256_file(summary_file)
    summary = _load_json(summary_file)
    _require(
        summary.get("implementation_id") == "DERD-v1.5-phase15-archival-lineage-promotion",
        "unexpected Phase-15 implementation identifier",
    )
    _require(bool(summary.get("protocol", {}).get("valid")), "Phase-15 protocol invalid")
    meta = summary.get("cumulative_ledger")
    _require(isinstance(meta, Mapping), "Phase-15 ledger metadata missing")
    ledger_path = root_path / str(meta.get("relative_path", ""))
    seal_path = root_path / str(meta.get("seal_relative_path", ""))
    _require(ledger_path.is_file() and seal_path.is_file(), "Phase-15 ledger or seal missing")
    ledger = _load_json(ledger_path)
    seal = _load_json(seal_path)
    digest = canonical_json_sha256(ledger)
    _require(digest == seal.get("sha256_canonical_json"), "Phase-15 ledger seal mismatch")
    _require(digest == meta.get("seal_sha256_canonical_json"), "Phase-15 summary ledger mismatch")
    rows = ledger.get("records")
    _require(isinstance(rows, list) and len(rows) == 5, "Phase-15 ledger must contain five records")

    provenance_fields = {
        "origin_phase",
        "origin_summary_relative_path",
        "origin_summary_sha256",
        "ledger_record_sha256",
    }
    verified: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        _require(isinstance(row, Mapping), "Phase-15 ledger record malformed")
        base = {key: value for key, value in row.items() if key not in provenance_fields}
        _require(canonical_json_sha256(base) == row.get("ledger_record_sha256"), "record digest mismatch")
        origin_relative = str(row.get("origin_summary_relative_path", ""))
        origin = root_path / origin_relative
        _require(origin.is_file(), f"record origin missing: {row.get('object_id')}")
        _require(sha256_file(origin) == row.get("origin_summary_sha256"), "record origin hash mismatch")
        checked = verify_evidence_record(
            base,
            root=root_path,
            origin_phase=str(row.get("origin_phase")),
            origin_summary_relative_path=origin_relative,
            origin_summary_sha256=str(row.get("origin_summary_sha256")),
        )
        _require(checked == dict(row), f"record provenance mismatch: {row.get('object_id')}")
        object_id = str(row["object_id"])
        _require(object_id not in seen, f"duplicate object: {object_id}")
        seen.add(object_id)
        verified.append(checked)

    refs = ledger.get("archival_lineage_audits", [])
    _require(isinstance(refs, list) and len(refs) == 1, "Phase-15 lineage audit reference missing")
    ref = refs[0]
    audit_path = root_path / str(ref["relative_path"])
    _require(audit_path.is_file(), "Phase-15 lineage sidecar missing")
    _require(sha256_file(audit_path) == ref["file_sha256"], "Phase-15 lineage sidecar file hash mismatch")
    lineage = _load_json(audit_path)
    without_self = {k: v for k, v in lineage.items() if k != "sha256_canonical_json"}
    _require(canonical_json_sha256(without_self) == lineage.get("sha256_canonical_json"), "lineage sidecar canonical hash mismatch")
    _require(lineage.get("sha256_canonical_json") == ref["canonical_sha256"], "lineage reference mismatch")

    verified.sort(key=lambda row: str(row["object_id"]))
    return tuple(verified), summary_sha, digest, ledger, lineage


def _read_csv_one(path: Path) -> Mapping[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _require(len(rows) == 1, f"expected one replay row: {path}")
    return rows[0]


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def build_reproducibility_graph(
    *,
    root: str | Path,
    ledger_records: Sequence[Mapping[str, Any]],
    phase15_lineage: Mapping[str, Any],
) -> ReproducibilityGraph:
    root_path = Path(root).resolve()
    object_ids = tuple(sorted(str(row["object_id"]) for row in ledger_records))
    nodes: list[dict[str, Any]] = []
    edges: list[ReproducibilityEdge] = []

    exact_specs = [
        ("artifacts/phase12/phase12_replay_audit.csv", "phase08", "phase12"),
        ("artifacts/phase13/phase13_replay_audit.csv", "phase08", "phase13"),
        ("artifacts/phase14/phase14_replay_audit.csv", "phase08", "phase14"),
    ]
    versions_by_object: dict[str, set[str]] = {object_id: set() for object_id in object_ids}
    for relative, source_version, comparison_version in exact_specs:
        row = _read_csv_one(root_path / relative)
        object_id = row["object_id"]
        _require(object_id in versions_by_object, f"replay object absent from ledger: {object_id}")
        versions_by_object[object_id].update({source_version, comparison_version})
        edge = ReproducibilityEdge(
            object_id=object_id,
            source_version=source_version,
            comparison_version=comparison_version,
            same_observational_source=True,
            same_scientific_configuration=True,
            scientific_match=_bool(row["scientific_match"]),
            exchange_match=_bool(row["exchange_match"]),
            stage_match=_bool(row["stage_match"]),
            disposition_match=_bool(row["disposition_match"]),
            maximum_harmonic_snr_absolute_difference=float(row["maximum_harmonic_snr_absolute_difference"]),
            screen_score_difference=float(row["screen_score_difference"]),
            threshold_difference=float(row["threshold_difference"]),
            classification=EDGE_EXACT,
            counts_as_independent_astrophysical_replication=False,
        )
        _require(edge.scientific_match and edge.exchange_match, f"recorded exact replay is not exact: {object_id}")
        edges.append(edge)

    lineage_id = str(phase15_lineage["object_id"])
    _require(lineage_id in versions_by_object, "Phase-15 lineage target absent from ledger")
    versions_by_object[lineage_id].update({"phase07", "phase08"})
    edges.append(
        ReproducibilityEdge(
            object_id=lineage_id,
            source_version="phase07",
            comparison_version="phase08",
            same_observational_source=bool(phase15_lineage["source_coordinates_match"]),
            same_scientific_configuration=bool(phase15_lineage["configuration_equal"]),
            scientific_match=bool(phase15_lineage["exchange_exact"] and phase15_lineage["stage_match"] and phase15_lineage["disposition_match"]),
            exchange_match=bool(phase15_lineage["exchange_exact"]),
            stage_match=bool(phase15_lineage["stage_match"]),
            disposition_match=bool(phase15_lineage["disposition_match"]),
            maximum_harmonic_snr_absolute_difference=float(phase15_lineage["maximum_harmonic_snr_absolute_difference"]),
            screen_score_difference=float(phase15_lineage["screen_score_difference"]),
            threshold_difference=float(phase15_lineage["threshold_difference"]),
            classification=EDGE_CONFIG_DRIFT,
            counts_as_independent_astrophysical_replication=False,
        )
    )

    for record in ledger_records:
        object_id = str(record["object_id"])
        origin = str(record["origin_phase"])
        if not versions_by_object[object_id]:
            versions_by_object[object_id].add(origin)
        for version in sorted(versions_by_object[object_id]):
            nodes.append(
                {
                    "node_id": f"{object_id}:{version}",
                    "object_id": object_id,
                    "analysis_version": version,
                    "family": record["family"],
                    "denominator_record": version == origin,
                    "ledger_origin_phase": origin,
                }
            )

    single = tuple(sorted(object_id for object_id, versions in versions_by_object.items() if len(versions) == 1))
    exact_count = sum(edge.classification == EDGE_EXACT for edge in edges)
    drift_count = sum(edge.classification == EDGE_CONFIG_DRIFT for edge in edges)
    version_count = sum(len(versions) for versions in versions_by_object.values())
    unique = len(object_ids)
    return ReproducibilityGraph(
        object_ids=object_ids,
        analysis_nodes=tuple(sorted(nodes, key=lambda row: row["node_id"])),
        edges=tuple(sorted(edges, key=lambda row: (row.object_id, row.source_version, row.comparison_version))),
        single_version_objects=single,
        exact_replay_count=exact_count,
        configuration_drift_count=drift_count,
        external_independent_replication_count=0,
        unique_object_denominator=unique,
        analysis_version_count=version_count,
        duplicate_analysis_inflation_prevented=version_count - unique,
    )
