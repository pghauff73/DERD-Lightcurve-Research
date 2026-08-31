# DERD v0.6 Phase-06 implementation handoff

## Implemented research action

Phase 06 closes the `verified-harmonic-phase-convention` investigation for the discovered legacy feature tables. The result is negative but high-value: the table convention does not uniquely preserve the complex coefficients needed by the DERD harmonic proof, and the exact frozen extraction source does not reproduce its own three nominal frequency blocks as observed in compact catalog samples.

The release adds a lossless canonical exchange schema so future summary catalogs can qualify.

## Main entry points

```bash
PYTHONPATH=src python experiments/run_phase06.py --output artifacts/phase06
PYTHONPATH=src pytest -q
python experiments/build_code_manifest.py --root .
python experiments/build_manifest.py --root .
python experiments/verify_manifest.py --manifest research/CODE_MANIFEST_SHA256.txt
python experiments/verify_manifest.py
```

Primary modules:

- `src/derd/phase_convention.py`
- `src/derd/harmonic_exchange.py`
- `src/derd/validation_phase06.py`
- `experiments/run_phase06.py`

## Frozen decision

```text
LEGACY_FEATURE_TABLES_BLOCKED_FROM_EXACT_DERD_HARMONIC_PROOF
```

Reasons:

- `arctan(b/a)` loses the coefficient quadrant;
- the absolute fundamental phase is absent;
- `phase_n - phase_1` is not epoch invariant for `n > 1`;
- four harmonics have zero independent recurrence-forecast degrees of freedom;
- the exact frozen three-pass source requires repeated blocks, while the sampled tables contain different blocks.

## Reproduction outputs

- `artifacts/phase06/phase06_summary.json`
- `artifacts/phase06/phase06_synthetic_information_test.csv`
- `artifacts/phase06/phase06_frozen_source_catalog_audit.csv`
- `artifacts/phase06/phase06_epoch_sensitivity.csv`
- `artifacts/phase06/PHASE06_RESULT.md`
- `data/examples/phase06_canonical_harmonic_exchange.json`

## Next research gate

Acquire or generate development summaries in `DERD-HARMONIC-EXCHANGE-1.0` format with at least six harmonics, signed coefficients, a frozen epoch, uncertainty covariance, and source digests. For raw photometry, retain the Phase-05 MVHE-160 lower-bound target and run the full actual-cadence extraction directly rather than passing through legacy relative phases.

Prospective Phase-04 sealed identities remain unopened.
