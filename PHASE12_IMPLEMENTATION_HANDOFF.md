# Phase 12 implementation handoff

## Release identity

`DERD-v1.2-phase12-cumulative-replay-ledger`

## Completed

- cryptographic verification and chaining of prior Phase-11 evidence records;
- cumulative ledger and independent ledger seal;
- conflict rejection for duplicate target identities;
- execution of only newly ready targets not already represented in the ledger;
- exact scientific replay comparison against inherited Phase-08 records;
- narrow transport-metadata projection for source-path and human period-label changes;
- cumulative family-coverage firewall;
- claims C57-C60;
- Phase-12 OURD, IURMv1.1.1 and EDOv1 objects;
- cumulative tables, replay audit, frontier, blockers, and figures.

## Current result

The cumulative ledger contains two verified exposed-development targets:

```text
OGLE-LMC-CEP-0004
stage=RECOVERY_HARMONICS
disposition=ABSTAIN_INSUFFICIENT_RECOVERY_HARMONIC_SIGNAL
origin=phase11

OGLE-LMC-RRLYR-00001
stage=FORECAST_HARMONICS
disposition=ABSTAIN_INSUFFICIENT_MEASURED_FORECAST_HARMONICS
origin=phase12
```

The fresh RR Lyrae result reproduces the Phase-08 scientific projection and harmonic exchange exactly. Its h1-h4 recovery harmonics pass, but h5-h8 provide no pair above the frozen forecast SNR threshold.

## Current blockers

1. Thirteen frozen target identities lack cumulative records.
2. Thirteen raw source files are not locally available for new execution.
3. Nine source SHA-256 coordinates remain pending acquisition.
4. Five Delta Scuti identities still require authoritative crosswalk, period, uncertainty, and subtype locks.
5. Family fractions, Wilson intervals, and population claims remain suppressed.
6. Every current identity is exposed development evidence and cannot become a pristine confirmatory holdout.

## Resume commands

Import another rights-reviewed source subset while preserving the current receipt:

```bash
PYTHONPATH=src:. python experiments/import_phase12_source_pack.py \
  --root . \
  --input-dir /path/to/source-pack \
  --prior-receipt artifacts/phase12/phase12_source_acquisition_receipt.json \
  --receipt artifacts/phase12/phase12_source_acquisition_receipt.next.json \
  --acknowledge-ogle-attribution
```

Promote the new receipt after review, then execute and append newly ready targets:

```bash
mv artifacts/phase12/phase12_source_acquisition_receipt.next.json \
   artifacts/phase12/phase12_source_acquisition_receipt.json

PYTHONPATH=src:. python experiments/run_phase12.py \
  --root . \
  --receipt artifacts/phase12/phase12_source_acquisition_receipt.json \
  --output artifacts/phase12 \
  --execute-ready
```

Import authoritative Delta Scuti catalogue files using the Phase-10 tools before executing those targets.

## Promotion rule

Individual target results may be reported only with their exact evidence stage, disposition, and exposed-development status. Do not emit family fractions or Wilson intervals until all fifteen frozen identities have unique, verified cumulative records.
