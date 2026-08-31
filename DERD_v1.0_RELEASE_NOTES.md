# DERD v1.0 Release Notes

## Added

- Authoritative OGLE-IV/VizieR LMC Delta Scuti catalogue contract with a canonical SHA-256 seal.
- Fixed-width `ident.dat` and `dsct.dat` parsers.
- Exact current-ID and explicit OGLE-III-to-OGLE-IV crosswalk resolution.
- Row-level, catalogue-file-level, and canonical metadata-lock digests.
- A mode-restraint rule that preserves `singlemode` as radial-order unresolved.
- Rights-aware catalogue and raw-photometry acquisition receipts.
- A fifteen-object Phase-10 readiness and optional execution engine.
- A deterministic five-object crosswalk and lock positive control.
- Claims C48-C53 and Phase-10 OURD, IURMv1.1.1, and EDOv1 objects.
- Readiness, blocker, family-coverage tables, and three diagnostic figures.

## Corrected

- Release manifests now exclude all raw paths declared by both Phase 09 and Phase 10.
- Authoritative catalogue bytes are excluded alongside third-party raw photometry unless a redistribution basis is recorded.
- Metadata readiness and source-byte readiness are evaluated independently.
- Legacy numeric suffixes and `PeriodLS` coordinates cannot silently satisfy claim-grade metadata gates.

## Current scientific decision

`PHASE10_IMPLEMENTED_CATALOG_CONTRACT_LOCKED_EXECUTION_BLOCKED_BY_AUTHORITATIVE_ROWS_AND_RAW_SOURCE_BYTES`

The protocol, exact 5+5+5 structure, catalogue contract, acquisition tooling, and execution hook are complete. Ten targets have claim-grade metadata, zero raw sources are replay-ready in the release runtime, and the five selected Delta Scuti records await authoritative row and file locks. Family outputs remain suppressed.

C17 remains open and unpromoted. The release does not certify literal internal Keplerian motion, a universal transparent shell, or shell mass.
