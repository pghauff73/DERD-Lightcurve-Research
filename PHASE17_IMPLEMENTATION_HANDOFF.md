# Phase 17 implementation handoff

## Release

`DERD-v1.7-phase17-external-analysis-anchor`

## Execute

```bash
PYTHONPATH=src:. python experiments/run_phase17.py \
  --root . \
  --source data/raw/phase17_external/OGLE-LMC-CEP-0002_V.dat
```

The source file must satisfy the exact SHA-256, Git-blob, byte-count, and observation-count coordinates in `data/manifests/phase17_external_v_source_manifest.json`.

## Retrieve the source

```bash
python experiments/fetch_phase17_v_source.py \
  --root . \
  --acknowledge-attribution
```

The raw source is excluded from redistributable releases.

## Main outputs

- `artifacts/phase17/phase17_summary.json`
- `artifacts/phase17/phase17_external_analysis_audit.json`
- `artifacts/phase17/phase17_fourier_parameter_comparison.csv`
- `artifacts/phase17/phase17_reproducibility_graph.json`
- `artifacts/phase17/phase17_cumulative_ledger.json`
- `artifacts/phase17/PHASE17_RESULT.md`

## Scientific interpretation

The four local Fourier coordinates are statistically consistent with the external published anchor under the frozen joint covariance test. This is an external-analysis consistency result with partial source overlap, not an independent observing-source replication and not a new astronomical denominator record.
