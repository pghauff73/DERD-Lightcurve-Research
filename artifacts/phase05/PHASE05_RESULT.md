# Phase 05 result: DERD harmonic-signature candidate triage

Release status: `HARMONIC_TRIAGE_ENGINE_IMPLEMENTED_CATALOG_SCALE_PROOF_NOT_YET_RUN`

## High-gain target implemented

The geometric DERD model implies an order-two recurrence in its non-zero complex Fourier coefficients. Phase 05 converts that theorem into a fast algebraic screen that recovers a candidate four-parameter DERD description, tests residue-phase and sign constraints, forecasts higher harmonics, and ranks objects before expensive nonlinear light-curve fitting.

The screen is a waveform-family triage device. It does not identify a stellar core-shell mechanism, external shell, or shell mass.

## Cadence-aware synthetic control

The reference threshold was calibrated only on the synthetic development split and evaluated on a separate synthetic holdout. The frozen threshold is **2.06744**.

| Metric | Synthetic holdout |
|---|---:|
| Sample count | 146 |
| ROC AUC | 0.4764 |
| Balanced accuracy | 0.5597 |
| Sensitivity | 0.2394 |
| Specificity | 0.8800 |

The null set contains both smooth generic Fourier curves and phase-scrambled DERD-amplitude curves. All controls use the same 20 cadences and quoted uncertainty scales as the exposed Cepheid excerpt.

## Minimum viable harmonic evidence

The current 24-point cadence did not separate the synthetic families reliably. Under an optimistic uniform-phase experiment with the observed median noise ratio held fixed, the first observation count passing all frozen robustness gates was **160 observations per star**.

This is an acquisition-design lower bound, not a universal sample-size theorem. Uneven phase coverage, multimode structure, modulation, and catalog systematics can require more observations.

## Existing 20-star excerpt

The excerpt remains development evidence: 24 observations per star are insufficient for confirmatory harmonic inference. Candidate labels below are acquisition priorities, not detections.

| Priority | Count |
|---|---:|
| ACQUISITION_PRIORITY_B_LOW_SNR | 1 |
| INSUFFICIENT_HARMONIC_EVIDENCE | 16 |
| LOW_PRIORITY | 3 |

### Highest-ranked acquisition targets

| Rank | Star | Mode | Score | Bootstrap support | SNR harmonics | Decision |
|---:|---|---|---:|---:|---:|---|
| 1 | OGLE-LMC-CEP-0010 | 1O | 1.7675 | 0.609 | 1 | ACQUISITION_PRIORITY_B_LOW_SNR |
| 2 | OGLE-LMC-CEP-0023 | F | 2.2164 | 0.000 | 3 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 3 | OGLE-LMC-CEP-0025 | F | 2.2361 | 0.047 | 0 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 4 | OGLE-LMC-CEP-0005 | F | 2.3493 | 0.000 | 3 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 5 | OGLE-LMC-CEP-0003 | 1O | 2.4596 | 0.062 | 0 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 6 | OGLE-LMC-CEP-0013 | 1O | 2.4799 | 0.000 | 1 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 7 | OGLE-LMC-CEP-0001 | 1O | 2.7013 | 0.125 | 0 | INSUFFICIENT_HARMONIC_EVIDENCE |
| 8 | OGLE-LMC-CEP-0007 | 1O | 2.8174 | 0.016 | 0 | INSUFFICIENT_HARMONIC_EVIDENCE |

## Gate decision

`HARMONIC_TRIAGE_ENGINE_IMPLEMENTED_CATALOG_SCALE_PROOF_NOT_YET_RUN`

The next data action is to use the ranked list to acquire complete official light curves for development targets, then run the same algorithm over frozen Cepheid, RR Lyrae, and Delta Scuti harmonic catalogs under a verified phase convention. The prospective Phase-04 sealed identities remain untouched.
