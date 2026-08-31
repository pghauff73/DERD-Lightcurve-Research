# Phase 21 implementation: authoritative Delta Scuti unlock and frozen pilot

## Purpose

Phase 21 implements the frozen fifteen-object development pilot while correcting the Delta Scuti identity model inherited from Phase 10. The old OGLE-III object name is not assumed to be the direct value stored in the current catalogue cross-reference. The accepted relation is:

```text
old OGLE-III DSCT object ID
→ old OGLE-III field identity
→ current catalogue OGLE-III cross-reference field
```

No numeric-suffix, zero-padding, nearest-coordinate, or legacy-period fallback is permitted.

## Frozen denominator

Exactly five identities are retained in each family:

- classical Cepheid: 5;
- RR Lyrae: 5;
- Delta Scuti: 5.

The implementation rejects substitutions, duplicates, reordered family identity sets, or non-development roles.

## Metadata result

Three exact two-hop locks are present:

- `OGLE-LMC-DSCT-0003` → `OGLE-LMC-DSCT-00003`;
- `OGLE-LMC-DSCT-0005` → `OGLE-LMC-DSCT-00005`;
- `OGLE-LMC-DSCT-0006` → `OGLE-LMC-DSCT-00006`.

Two old identities remain unresolved because no exact current cross-reference row was accepted:

- `OGLE-LMC-DSCT-0004`;
- `OGLE-LMC-DSCT-0007`.

The lock is explicitly row-level. Full current-catalogue byte files are not falsely claimed to be locally frozen.

## Raw-source gate

Every target requires repository, commit, path, Git blob SHA-1, byte count, observation count, and SHA-256 agreement. `import_phase21_source_pack.py` installs verified data atomically and writes a redistributable receipt. Complete third-party photometry is excluded from the release bundle.

## Execution gate

Once all metadata and source inputs pass, `execute_phase21_cohort.py` executes the unchanged signed h1-h8, HC3 covariance, recovery, forecast, calibration, and structural gates. Family Wilson intervals are emitted only after all fifteen target results exist.

## Claim boundary

Phase 21 is an exposed-development metadata and readiness gate. It cannot confirm C17, identify a unique stellar mechanism, establish a transparent exterior shell, or estimate shell mass.
