# DERD Phase 20 Implementation Specification

## Identifier

`DERD-v2.0-phase20-multiband-mechanism-falsification`

## Research question

Phase 20 asks three separate questions:

1. Is one normalized DERD waveform invariant between I and V passbands for `OGLE-LMC-CEP-0002`?
2. Do a good DERD fit and a low recurrence-screen score uniquely indicate a DERD or gravitational generating mechanism?
3. Can positive-mass inverse-square gravity alone sustain a nonconstant periodic radial trajectory?

## Experiment A: covariance-aware passband test

The I-band input is the lossless signed h1-h8 exchange frozen in Phase 14. The V-band input consists of verified official OGLE-III and OGLE-IV observations, fitted simultaneously at the same period and reference epoch with an eight-harmonic weighted regression and HC3 covariance.

The invariant vector is

\[
(R_{21},\phi_{21},R_{31},\phi_{31}).
\]

Strict I/V invariance is rejected when the joint Mahalanobis p-value is below 0.01. The same-band OGLE-III V versus OGLE-IV V comparison is a temporal negative control.

## Experiment B: projection-model comparison

Three representation-level models are compared on covariance-sampled h1-h8 reconstructions:

- one strict shared DERD curve;
- separate DERD curves;
- two shared latent radius-like components with band-specific linear weights.

The criterion is BIC on 256-point reconstructions with 64 covariance draws. This is explicitly a representation-level heuristic, not a raw-point likelihood comparison.

## Experiment C: synthetic mechanism tournament

Ten controlled generator families produce 30 cases each. Deterministic SHA-256 assignment creates development and holdout partitions. Thresholds are selected only from DERD positives and generic-Fourier nulls, then applied to all held-out families. Any non-DERD joint fit-and-screen pass disproves uniqueness of the signature.

## Experiment D: gravity-only falsifier

For

\[
\ddot R=-\frac{GM}{R^2},
\]

the inferred effective mass is

\[
M_{\rm eff}=-\frac{R^2\ddot R}{G}.
\]

A positive control uses a nonperiodic inverse-square ballistic segment. Three nonconstant periodic trajectories are negative controls. A formal theorem establishes that a periodic positive radius cannot satisfy the gravity-only equation globally because every nonconstant periodic radius has a local minimum with nonnegative acceleration.

## Claim boundary

Phase 20 does not infer stellar mass, shell mass, shell prevalence, a unique internal mechanism, or literal Keplerian motion.
