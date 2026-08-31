# DERD v2.1 final report

## Phase 21: authoritative Delta Scuti unlock and frozen 15-object pilot

### Decision

```text
PHASE21_AUTHORITATIVE_DSCT_CROSSWALK_PARTIALLY_UNLOCKED
3_OF_5_DSCT_METADATA_LOCKS_PROMOTED
2_OF_5_EXACT_CURRENT_CROSSWALKS_UNRESOLVED
COMPLETE_15_OBJECT_EXECUTION_BLOCKED_BY_RAW_SOURCE_BYTES
C17_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## Research gain

Phase 21 corrects a subtle but important identity assumption. The old OGLE-III Delta Scuti object label is first resolved to its OGLE-III field identity, and only then matched against the current catalogue's explicit OGLE-III cross-reference field. The implementation rejects numeric-suffix, zero-padding, nearest-coordinate, and legacy-period shortcuts.

Three frozen identities now have authoritative row-level locks:

- `OGLE-LMC-DSCT-0003` → `OGLE-LMC-DSCT-00003`, period `0.06644253 d`;
- `OGLE-LMC-DSCT-0005` → `OGLE-LMC-DSCT-00005`, period `0.06768650 d`;
- `OGLE-LMC-DSCT-0006` → `OGLE-LMC-DSCT-00006`, period `0.12224786 d`.

No exact current-catalogue crosswalk is accepted for old `OGLE-LMC-DSCT-0004` or `OGLE-LMC-DSCT-0007`. They remain unresolved pending authoritative reclassification, retirement, or another exact cross-catalogue relation.

## Current gate state

| Dimension | Result |
|---|---:|
| Frozen cohort structure | 5 Cepheid + 5 RR Lyrae + 5 Delta Scuti |
| Claim-grade metadata | 13 / 15 |
| Delta Scuti authoritative locks | 3 / 5 |
| Delta Scuti exact crosswalks unresolved | 2 / 5 |
| Complete locally frozen raw sources | 0 / 15 |
| Inherited development evidence records | 5 / 15 |
| Fresh Phase-21 target results | 0 / 15 |
| Family fractions and Wilson intervals | Suppressed |

The authoritative periods differ materially from the legacy feature-table coordinates. Earlier Delta Scuti engineering results therefore cannot be promoted by metadata relabelling; they require fresh execution under the corrected periods.

## Implemented system

- exact two-hop OGLE-III field-ID crosswalk parser and validator;
- row-level authoritative query receipt with explicit scope limits;
- three cryptographic metadata locks and two unresolved records;
- immutable 5+5+5 denominator validator;
- rights-aware source-pack importer with repository, commit, path, blob, bytes, observations, and SHA-256 checks;
- complete-cohort executor using the unchanged h1-h8, HC3 covariance, recovery, forecast, calibration, and structural gates;
- population-output firewall and synthetic complete-denominator positive control;
- claims C97-C102;
- OURD, IURMv1.1.1, and EDOv1 evidence objects;
- release tests, code compilation, repository manifests, and bundle integrity controls.

## Claim boundary

This phase advances metadata provenance and development-cohort readiness. It does not establish that DERD is superior across pulsator populations. It does not identify a unique gravitational mechanism, a transparent exterior shell, shell prevalence, or shell mass.

## Next gate

1. Resolve the two unmatched legacy Delta Scuti identities through authoritative evidence.
2. Import and freeze all fifteen complete raw light curves.
3. Execute all fifteen target-level analyses under the frozen Phase-21 configuration.
4. Emit family descriptive intervals only after the complete denominator exists.
