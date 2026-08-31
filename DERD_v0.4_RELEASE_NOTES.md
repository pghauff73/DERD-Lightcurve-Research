# DERD v0.4 release notes

Release label: `DERD-v0.4-phase04-readiness`

## Added

- missing adaptive period-scan implementation required by Phase 03;
- exact deterministic Phase-03 replay and 20 regenerated prediction tables;
- direct tests for all Phase-03 modules;
- ten-stratum Phase-04 population contract;
- frozen and sealed Phase-04 analysis plan;
- candidate-data quality, provenance, rights, hash, and prior-exposure audits;
- deterministic prospective role assignment and linked role seal;
- sealed-star evaluation guard;
- stable code manifest separated from the final release manifest;
- current-pilot negative control and synthetic governance positive control.

## Corrected

The prior Phase-03 handoff contained the new experiment module but omitted `adaptive_verify_catalog_period` from the reconstructed base tree. This prevented a clean replay. The function has now been restored with the original staged-boundary behaviour, including first-minimum tie handling, and the complete output reproduces the recorded Phase-03 result.

## Verification result

- `115` tests pass;
- Phase-03 summary, detailed JSON, per-star CSV, and report are byte-identical to the recorded result;
- current 20-star population is rejected with `71` blocking findings;
- synthetic 150-identity governance fixture seals as 100 development plus 50 holdout;
- deliberate sealed-star evaluation is blocked.

## Scientific status

C17 remains open and unpromoted. No physical mechanism, transparent-shell, or shell-mass claim is promoted.
