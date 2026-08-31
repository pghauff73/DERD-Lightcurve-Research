# Phase 21 implementation handoff

## Current state

```text
13/15 claim-grade metadata coordinates
3/5 Delta Scuti exact two-hop locks
2/5 Delta Scuti exact crosswalks unresolved
0/15 complete local raw source locks
5/15 inherited development evidence records
0/15 fresh Phase-21 executions
population outputs suppressed
```

## Commands

Verify the authoritative row receipt and lock manifest:

```bash
PYTHONPATH=src:. python experiments/import_phase21_catalog_rows.py --root .
```

Import a rights-reviewed raw-source directory or ZIP:

```bash
PYTHONPATH=src:. python experiments/import_phase21_source_pack.py SOURCE_PACK \
  --root . --acknowledge-rights-and-attribution
```

Re-run readiness:

```bash
PYTHONPATH=src:. python experiments/run_phase21.py --root .
```

Execute the cohort only after all input gates pass:

```bash
PYTHONPATH=src:. python experiments/execute_phase21_cohort.py --root .
```

## Required next evidence

1. Authoritative reclassification, retirement, or exact crosswalk evidence for old DSCT-0004 and DSCT-0007.
2. Complete verified raw light curves for all fifteen frozen identities.
3. Fresh target execution under authoritative Delta Scuti periods.
4. Family intervals only after the complete denominator is present.
