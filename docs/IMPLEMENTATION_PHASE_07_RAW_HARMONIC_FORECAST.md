# Phase 07 implementation: raw-photometry harmonic forecast gate

## Purpose

Phase 07 implements the first complete chain from byte-frozen raw photometry to a covariance-aware DERD harmonic-forecast decision. It uses one exposed development target, `OGLE-LMC-CEP-0010`, and does not inspect a prospective sealed identity.

The tested waveform family is the four-parameter DERD descriptor. This implementation does not promote the paper's internal-orbit, transparent-shell, or shell-mass interpretations.

## Evidence chain

```text
Git blob identity
  -> three-column photometry parser
  -> quoted-error-only cleaning
  -> magnitude-to-relative-flux conversion
  -> generic-harmonic period profile
  -> simultaneous signed eight-harmonic regression
  -> HC3 coefficient covariance
  -> DERD-HARMONIC-EXCHANGE-1.0
  -> four-harmonic recovery
  -> four unused forecast harmonics
  -> actual-cadence null calibration
  -> covariance propagation
  -> integrated evidence gate
```

## Frozen source

| Field | Value |
|---|---|
| Object | `OGLE-LMC-CEP-0010` |
| Mode | `1O` |
| Observations | 372 |
| Time span | 2377.620970 days |
| Source commit | `55836b58345b9507bfbd98c5fabbac82c83605e3` |
| Git blob SHA-1 | `fd82c05bb3a62ba9a8c614ac51eb315124090381` |
| Local SHA-256 | `574d7252996f5ee71169a97f2d7b52a8acbdb0898df65a7b61f5419ae9f063e0` |
| Byte verification | `True` |
| Role | exposed development only |

No brightness sigma clipping is performed. All 372 observations passed the quoted-error gate.

## Signed harmonic model

The fitted model is

\[
y(t)=c_0+\sum_{n=1}^8\left[a_n\sin(2\pi n f(t-t_0))+b_n\cos(2\pi n f(t-t_0))\right].\]

The canonical positive-frequency coefficient is

\[
C_n=\frac{b_n-i a_n}{2}.\]

The exchange stores `c0`, the signed `a_n` and `b_n`, the reference epoch, fundamental frequency, source digest, and full covariance ordered as

```text
sin_1 ... sin_8, cos_1 ... cos_8
```

## Period coordinate

The catalog period was 2.5655853000 days. A generic weighted-harmonic profile, which does not include a DERD score, selected 2.5655780368 days, a relative change of -2.83102072e-06. The recurrence score changed from 1.928686 to 1.905220; the conclusion is not driven by a large period displacement.

## Harmonic evidence

| Harmonic | Wald SNR | Role |
|---:|---:|---|
| 1 | 182.894893 | recovery |
| 2 | 15.061330 | recovery |
| 3 | 3.820704 | recovery |
| 4 | 3.116553 | recovery |
| 5 | 1.759561 | forecast |
| 6 | 1.336439 | forecast |
| 7 | 1.698583 | forecast |
| 8 | 0.832390 | forecast |


All four recovery harmonics cross SNR 3. None of the four forecast harmonics crosses SNR 2. The nominal screen score is 1.905220, above the development-selected threshold 1.470082. Structural flags are `RESIDUE_SIGN_CONSTRAINT_FAILED;RESIDUE_PHASE_CONSTRAINT_WEAK`.

## Actual-cadence calibration

| Metric | Development | Holdout |
|---|---:|---:|
| ROC AUC | 0.945206 | 0.796277 |
| Balanced accuracy | 0.902618 | 0.754255 |
| Sensitivity | 0.858333 | 0.700000 |
| Specificity | 0.946903 | 0.808511 |

The holdout balanced accuracy passes 0.75. ROC AUC is 0.796277, below the frozen 0.80 gate.

## Covariance propagation

From 4096 successful draws:

- structural pass fraction: 0.004150;
- below-threshold fraction: 0.125977;
- median score: 1.817910;
- median forecast residual: 0.457607.

These are uncertainty diagnostics for the coefficient estimate, not posterior probabilities of a stellar mechanism.

## IURMv1.1.1 acquisition intervention

Only observation count was varied. The pointwise pattern was 80 fail, 120 pass, 160 fail, 240 pass, 320 pass, and 372 pass. To avoid promoting a single Monte-Carlo island, the conservative rule requires the candidate count and every larger tested count to pass across at least three levels. The first sustained pass is therefore **240 observations**, not 120.

This does not mean 240 observations guarantee qualifying DERD evidence. The real target still lacks significant forecast harmonics at 372 observations. Observation count and harmonic information content are separate dimensions.

## Integrated decision

```text
ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE
```

Blockers:
- `forecast_harmonics_snr`
- `structural_constraints`
- `score_below_cadence_threshold`
- `uncertainty_structural_stability`
- `uncertainty_threshold_stability`
- `cadence_calibration_auc`


## Promotion boundary

A pass would establish compatibility of a light-curve harmonic sequence with the geometric DERD constraints under the frozen screen. It would not uniquely identify internal Keplerian motion, a transparent external shell, or a shell mass. Those claims require independent observables and separate models.
