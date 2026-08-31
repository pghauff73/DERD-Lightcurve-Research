# Phase 08: multi-family raw-photometry harmonic-forecast cohort

## Purpose

Phase 08 applies one frozen waveform-evidence gate to six exposed development objects:

- two classical Cepheids;
- two RR Lyrae stars;
- two Delta Scuti candidates.

It tests whether the Phase-07 result was an isolated target artefact and identifies the
first failing dimension for each object. It is not a prospective confirmation, a
population estimate, or evidence for a transparent shell.

## Evidence chain

```text
byte-frozen raw photometry
  -> source SHA-256 and Git blob verification
  -> conservative uncertainty cleaning
  -> catalog-period phase coordinate
  -> simultaneous signed h1-h8 regression
  -> full coefficient covariance
  -> target-specific actual-cadence null calibration
  -> h1-h4 algebraic recovery
  -> h5-h8 independent recurrence forecast
  -> covariance propagation
  -> stage-specific abstain/reject/qualify decision
```

The raw mirror bytes are excluded from the redistributable bundle. The release contains a
retrieval program, byte counts, observation counts, SHA-256 values, Git blob object IDs,
and source locators.

## Frozen dimensions

| Dimension | Frozen value |
|---|---|
| Harmonic order | 8 |
| Recovery harmonics | h1-h4 |
| Forecast harmonics | h5-h8 |
| Minimum clean observations | 240 |
| Recovery Wald SNR | 3.0 for all four |
| Forecast Wald SNR | 2.0 for at least two |
| Phase coverage | at least 10 of 12 bins |
| Maximum design condition | 10,000 |
| Synthetic calibration | 96 positives and 96 nulls per target |
| Covariance propagation | 2,048 draws per target |
| Cadence AUC gate | 0.80 |
| Cadence balanced-accuracy gate | 0.75 |
| Structural and threshold stability | 0.80 |

Each target receives independent deterministic synthetic and covariance seeds derived from
its object identifier. This avoids giving all stars an identical Monte Carlo coordinate.

## Orthogonal source and cleaning dimensions

Phase 08 repairs a reusable helper defect discovered when a Delta Scuti light curve
contained large quoted-error points. Source completeness now means that the input bytes
match the frozen Git blob and SHA-256. Cleaning is recorded separately. Removing a gross
uncertainty outlier no longer turns a byte-complete source into an incomplete source.

## Period evidence levels

- `EXTERNAL_CATALOG_MIRROR` and `EXTERNAL_CATALOG_CROSSCHECK` may enter the claim-grade
  waveform gate.
- `LEGACY_FEATURE_TABLE_DIAGNOSTIC` is engineering-only. It can exercise the pipeline and
  prioritize retrieval, but it cannot support a final object-level compatibility claim.

Period refinement remains a generic diagnostic. It does not optimize DERD compatibility
and does not silently replace the frozen period coordinate.

## Cohort inference boundary

Population inference requires at least five exposed development objects per family and at
least fifteen objects overall before a cohort statistic is interpreted. Phase 08 contains
only two per family. Regardless of individual outcomes, C17 cannot be promoted by this
tranche.

## Run

```bash
PYTHONPATH=src python experiments/fetch_phase08_sources.py \
  --acknowledge-third-party-terms
PYTHONPATH=src python experiments/run_phase08.py \
  --manifest data/manifests/phase08_cohort_sources.json \
  --output artifacts/phase08
```

## Principal output

See `artifacts/phase08/PHASE08_RESULT.md`. The cohort contains 2,138 raw measurements and
2,135 retained measurements. No object qualifies as a development harmonic forecast.
One RRab object reaches the forecast-harmonic stage, but it does not measure two forecast
harmonics at the frozen SNR threshold.
