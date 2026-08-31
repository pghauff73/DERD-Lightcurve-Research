# DERD v0.9 Release Notes

## Added

- Frozen fifteen-object Phase-09 development cohort manifest.
- Exact 5+5+5 population-structure audit.
- Claim-grade period, mode, and catalog-identity gates.
- Rights-aware raw-source retriever with Git blob, byte, observation-count, and SHA-256 verification.
- Manifest-bound source acquisition receipt.
- Cryptographic reuse checks for five inherited Phase-08 target records.
- Suppression of incomplete family-level fractions.
- Wilson interval calculations for a future complete cohort.
- Deterministic non-astrophysical aggregation control.
- Phase-09 readiness, blocker, and family-coverage tables and figures.
- Machine-readable OURD, IURMv1.1.1, EDOv1, and claim objects.

## Corrected

- Source readiness now checks actual observation count in addition to byte and digest identity.
- Acquisition receipts are ignored unless their header matches the current frozen cohort manifest and records attribution acknowledgement.
- The repository manifest automatically excludes every Phase-09 raw source path, even when those files are acquired locally.
- Direct `pytest` execution now includes the `src` package path through project configuration.
- The full repository manifest excludes `BUNDLE_SHA256SUMS.txt`; bundle checksums include the repository manifest and exclude themselves, removing the prior circular hash relation.

## Current scientific decision

`PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_AND_SOURCE_GATES`

The exact 5+5+5 cohort is declared, but current evidence is incomplete. The selected Delta Scuti records do not yet have claim-grade period, mode, and identity crosswalks, and the redistributable release contains no third-party raw photometry bytes.

C17 remains open and unpromoted. Physical mechanism and transparent-shell claims remain locked.
