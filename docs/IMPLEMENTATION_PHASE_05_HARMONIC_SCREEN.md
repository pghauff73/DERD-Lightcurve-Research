# Phase 05: algebraic DERD harmonic screening and minimum viable evidence

## Purpose

Phase 05 implements the highest-gain test available before the complete ten-stratum
population is acquired.  Instead of running a nonlinear four-parameter fit on every future
light curve, it tests the geometric DERD model's exact harmonic structure and uses the
result to prioritize acquisition and follow-up.

This is a waveform-family screen.  It does not identify a stellar interior, a transparent
outer shell, or a shell mass.

## The spectral invariant

Let `q=e/(1+sqrt(1-e^2))` and

```text
K(e) = sqrt(1-e^2) / [2(1+sqrt(1-e^2))].
```

For positive harmonics of the normalized geometric-radius component,

```text
a_n(e) = -K(e)(-q)^(n-1),  n >= 1.
```

For geometric DERD, after an arbitrary observational epoch `tau` and real scale `s`,

```text
c_n = D1 r1^(n-1) + D2 r2^(n-1),

r1 = -q1 exp(i 2 pi tau),
r2 = -q2 exp(i 2 pi (tau + phi)),
D1 =  s K(e1) exp(i 2 pi tau),
D2 = -s A K(e2) exp(i 2 pi (tau + phi)).
```

Therefore

```text
c_(n+2) - (r1+r2)c_(n+1) + r1 r2 c_n = 0.
```

The residues obey additional constraints:

```text
D1/r1 is real,
D2/r2 is real,
real(D1/r1) and real(D2/r2) have opposite signs.
```

These constraints are stronger than a generic order-two recurrence.  When roots are
separate and nonzero, their magnitudes recover `q1,q2`, their phase difference recovers the
DERD phase ratio, and the residue magnitudes recover the amplitude ratio.  Degenerate
circular, repeated-root, cancellation, and low-signal cases require abstention.

## Implemented pipeline

```text
irregular photometry
  -> weighted complex Fourier coefficients
  -> order-two recurrence roots and residues
  -> physical-q and residue constraints
  -> algebraic DERD parameter candidate
  -> higher-harmonic forecast
  -> synthetic-calibrated acquisition rank
```

Primary modules:

- `src/derd/harmonic_screen.py`
- `src/derd/catalog_harmonics.py`
- `src/derd/validation_phase05.py`
- `experiments/run_phase05.py`

## Minimum viable harmonic evidence

The existing development files contain only 24 observations per star.  A cadence-aware
synthetic holdout did not discriminate DERD controls from generic and phase-scrambled
nulls: ROC AUC was approximately 0.48 at the observed uncertainty scale.

An IURMv1.1.1 experiment then varied only observation count while holding these dimensions
fixed:

- uniform phase coverage;
- median observed error-to-amplitude ratio;
- eight extracted harmonics;
- first four harmonics used for algebraic recovery;
- four harmonics used for forecast;
- null-family mixture;
- Fourier ridge and score definition.

The first count passing all frozen robustness gates was 160 observations per star.  This is
an optimistic acquisition-design lower bound.  Uneven phase coverage, multimode structure,
Blazhko modulation, passband systematics, and period error can require more.

## Catalog-table adapter

`catalog_harmonics.py` accepts tables such as those containing
`freq1_harmonics_amplitude_0..3` and `freq1_harmonics_rel_phase_0..3`.  The sine-versus-
cosine convention must be verified from the generating software before scores from such a
table are interpreted.  Four harmonics provide shape-only evidence; at least six are
required by the default two-harmonic forecast gate.

## Promotion boundary

A low score means only that a harmonic sequence is compatible with the constrained
geometric DERD family under the stated convention.  It cannot establish:

- literal internal Keplerian motion;
- gravitational driving by a spherical external shell;
- universal circumstellar material;
- absolute radius or mass;
- shell mass fraction.
