# DERD implementation phase 02

## Objective

Phase 02 implements the first observational gate in the roadmap. It tests whether the
corrected four-dimensional waveform models can be evaluated on real variable-star
photometry with explicit provenance, deterministic preprocessing, held-out prediction,
and contradiction reporting.

## Implemented system

- immutable, validated `LightCurve` objects;
- OGLE three-column photometry parser;
- magnitude-to-relative-flux conversion with uncertainty propagation;
- deterministic circular phase-block holdout;
- training-only maximum-flux epoch estimation;
- training-only min-max scaling and inverse-variance weights;
- peak-aligned DERD-G and DERD-K fitting;
- fixed order-two Fourier baseline;
- raw BIC order selection retained as a diagnostic;
- condition-and-span-gated BIC selection using training data only;
- held-out RMSE, weighted RMSE, MAE, maximum error, residual autocorrelation, and
  Durbin-Watson statistics;
- Jacobian singular values, condition numbers, and local covariance where identifiable;
- deterministic bootstrap spot checks;
- official OGLE completion fetcher with explicit attribution acknowledgement;
- EH Lib reproduction contract;
- dimensional transparent-shell feasibility calculator.

## Executed observational capsule

The development capsule contains 20 LMC classical Cepheids:

- 10 fundamental-mode targets;
- 10 first-overtone targets;
- 24 mirrored I-band observations per target;
- 380 training observations and 100 held-out observations in total.

Each held-out set is one contiguous block in circular phase-rank order. There is no sealed
confirmatory star holdout in this phase.

## Result

The best of DERD-G and DERD-K had lower held-out RMSE than the best primary Fourier
baseline on 12 of 20 targets. The best Fourier baseline won or tied on 8 of 20. Median
best-DERD minus best-Fourier RMSE was approximately `-0.005018`.

DERD-G and DERD-K each won six targets. Fixed order-two Fourier won seven, and the
stability-gated BIC baseline won one. The result is mixed rather than universally
favourable, which is exactly what a useful shakedown should reveal.

## Issue discovered and corrected

Ungated BIC selected high Fourier orders that catastrophically extrapolated through sparse
held-out phase blocks. Three raw-BIC fits had held-out RMSE above one, and the worst was
approximately 58.79. The raw result is preserved in `research/diagnostics/`.

The corrected primary baseline rejects a candidate using only training information when:

- the weighted design condition number exceeds `1e4`; or
- its dense-cycle prediction span exceeds three times the training-target span.

The gate rejected at least one order for five targets. It never inspected the held-out
observations.

## Identifiability

Median local Jacobian condition numbers were approximately:

- DERD-G: 84.4;
- DERD-K: 26.4.

One DERD-K fit crossed the provisional `1e5` warning gate. Its parameters are not eligible
for physical interpretation. Bootstrap spot checks also showed substantial variation in
some fitted dimensions, so descriptive performance and parameter stability remain
separate gates.

## Decision

`PHASE02_ENGINEERING_SHAKEDOWN_COMPLETE_C17_NOT_PROMOTED`

The result supports continued study of DERD as a restricted waveform family. It does not
prove that DERD replaces Fourier analysis, identifies stellar dynamics, demonstrates a
transparent shell, or estimates shell mass.

## Next promotion gate

1. Retrieve complete official OGLE files and freeze their checksums.
2. Increase the development set and create an untouched star-identity holdout.
3. Add RR Lyrae and Delta Scuti strata.
4. Add periodic spline, PCA/template, and Gaussian-process baselines.
5. Calibrate uncertainties and repeatability across epochs and passbands.
