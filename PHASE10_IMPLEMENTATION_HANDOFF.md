# Phase 10 implementation handoff

## Release identity

`DERD-v1.0-phase10-authoritative-metadata-source-lock`

## Completed

- fixed-width OGLE-IV LMC Delta Scuti identity and parameter parsers;
- exact OGLE-III crosswalk policy;
- restrained single-mode label;
- row, file, and lock SHA-256 transport;
- rights-aware catalogue and source importers;
- exact 5+5+5 Phase-10 readiness audit;
- optional complete-cohort execution hook;
- complete-denominator output suppression;
- synthetic five-object crosswalk positive control;
- claims C48-C53 and OURD/IURM/EDOv1 records.

## Current blockers

1. `ident.dat` and `dsct.dat` are absent, so zero of five selected Delta Scuti metadata locks are promoted.
2. All fifteen raw photometry files are absent from the release runtime.
3. Ten source SHA-256 values remain pending a verified acquisition receipt.
4. Family fractions and Wilson intervals are suppressed.

## Resume commands

Import authoritative catalogue files from a rights-reviewed local directory:

```bash
PYTHONPATH=src python experiments/fetch_phase10_catalogs.py \
  --root . \
  --input-dir /path/to/authoritative/catalog \
  --acknowledge-citation

PYTHONPATH=src python experiments/build_phase10_metadata_lock.py \
  --root .
```

Import a rights-reviewed source pack:

```bash
PYTHONPATH=src python experiments/fetch_phase10_sources.py \
  --root . \
  --input-dir /path/to/source-pack \
  --acknowledge-third-party-terms
```

Audit readiness and execute only when every object is ready:

```bash
PYTHONPATH=src python experiments/run_phase10.py --root .
PYTHONPATH=src python experiments/run_phase10.py --root . --execute-ready
```

## Promotion rule

Do not report family fractions from a partial denominator. Do not replace missing authoritative metadata with legacy feature-table periods, suffix matching, or inferred radial modes.
