# Phase 07 result: raw-photometry harmonic forecast gate

## Decision

```text
ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE
COMPONENT_STATUS=INSUFFICIENT_MEASURED_FORECAST_HARMONICS
C17_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## What was tested

The exposed development target `OGLE-LMC-CEP-0010` was upgraded from the historical
24-row excerpt to the complete 372-observation public-repository mirror.
The local file reproduced Git blob `fd82c05bb3a62ba9a8c614ac51eb315124090381` exactly.  A simultaneous
weighted eight-harmonic fit was extracted in relative-flux space and written to
`DERD-HARMONIC-EXCHANGE-1.0` with signed sine/cosine coefficients, a frozen
epoch, and a full HC3 coefficient covariance.

The first four harmonics were used for algebraic DERD recovery. Harmonics 5-8
were left unused by recovery and treated as the forecast dimensions.

## Source and coverage

| Dimension | Result |
|---|---:|
| observations | 372 |
| time span | 2377.620970 days |
| median quoted magnitude error | 0.005000 mag |
| occupied 12-bin phase cells | 12 / 12 |
| maximum circular phase gap | 0.018577 |
| harmonic design condition number | 1.828139 |
| weighted reduced chi-square | 2.768287 |

## Period gate

| Quantity | Value |
|---|---:|
| catalog period | 2.5655853000 days |
| generic-harmonic refined period | 2.5655780368 days |
| relative shift | -2.83102072e-06 |
| profile interval | 2.5655704196 to 2.5655858131 days |
| chi-square reduction | 2.309799 |

The period was refined with a generic weighted harmonic objective, not with the
DERD recurrence score.  The recurrence result changed from
1.928686 at the catalog period to 1.905220
at the refined period, so the decision does not depend on a large period
coordinate displacement.

## Measured harmonic information

| Harmonic role | Wald SNR values | Gate |
|---|---|---|
| recovery, h1-h4 | 182.895, 15.061, 3.821, 3.117 | all four >= 3.0: True |
| forecast, h5-h8 | 1.760, 1.336, 1.699, 0.832 | at least two >= 2.0: False |

The complete light curve is sufficient to estimate the four recovery harmonics,
but it does not measure two independent forecast harmonics at the frozen SNR
threshold.  More observations did not manufacture high-order signal that the
star's light curve does not contain strongly.

## Actual-cadence calibration

The synthetic threshold was selected only on the synthetic development split,
using the real time coordinates, quoted errors, measured flux scale, and the
same extraction/screening pipeline.

| Metric | Value |
|---|---:|
| selected score threshold | 1.470082 |
| holdout ROC AUC | 0.796277 |
| holdout balanced accuracy | 0.754255 |
| holdout sensitivity | 0.700000 |
| holdout specificity | 0.808511 |
| real-star nominal score | 1.905220 |

The real-star score is above
the development-selected compatibility threshold.

## Covariance propagation

| Quantity | Value |
|---|---:|
| successful coefficient draws | 4096 / 4096 |
| median score | 1.817910 |
| 5-95% score interval | 1.020579 to 2.944032 |
| fraction below threshold | 0.125977 |
| median forecast residual | 0.457607 |
| 5-95% forecast-residual interval | 0.288269 to 0.704915 |

A qualifying result required at least 80% of covariance draws to remain below
the compatibility threshold.  The observed fraction was
0.125977.

## Actual-cadence MVHE intervention

The only active IURMv1.1.1 dimension was observation count. The time/error
coordinates were sampled from this real cadence, while synthetic family,
noise scaling, harmonic order, recurrence dimensions, score, and promotion
thresholds were frozen.

| Observations | Median AUC | q10 AUC | Median balanced accuracy | q10 balanced accuracy | Pass |
|---:|---:|---:|---:|---:|:---:|
| 80 | 0.832956 | 0.679947 | 0.797289 | 0.651748 | no |
| 120 | 0.877451 | 0.803333 | 0.815899 | 0.710065 | yes |
| 160 | 0.886190 | 0.715909 | 0.799813 | 0.714423 | no |
| 240 | 0.882609 | 0.784231 | 0.818615 | 0.728648 | yes |
| 320 | 0.886364 | 0.821001 | 0.831845 | 0.735852 | yes |
| 372 | 0.914377 | 0.845330 | 0.848346 | 0.767436 | yes |


The first pointwise pass was
`120`,
but the pointwise pattern was non-monotonic.  The conservative gate therefore
requires the candidate count and every larger tested count to pass, with at
least 3 tested levels in the passing tail.
The first sustained pass was
`240`
across 3 levels.  This is the provisional
actual-cadence MVHE floor for this one exposed target.  The earlier MVHE-160
value remains an optimistic uniform-phase lower bound rather than a
survey-cadence guarantee.

## Combined evidence gate

The integrated gate also requires source completeness, phase coverage, design
conditioning, four significant recovery harmonics, two significant forecast
harmonics, recurrence structural compatibility, score stability under the
coefficient covariance, and actual-cadence calibration performance. Its
blockers were:

- `forecast_harmonics_snr`
- `structural_constraints`
- `score_below_cadence_threshold`
- `uncertainty_structural_stability`
- `uncertainty_threshold_stability`
- `cadence_calibration_auc`

## Claim boundary

This phase establishes a reproducible raw-photometry-to-exchange pipeline and a
negative development result for one exposed first-overtone Cepheid.  It does
not establish or refute DERD for other stars or classes.  It does not identify
an internal orbital mechanism, external transparent shell, or shell mass.
