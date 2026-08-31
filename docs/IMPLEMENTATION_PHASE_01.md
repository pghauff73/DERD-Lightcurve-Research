# Phase 0–1 implementation report

## Implemented tranche

This tranche establishes the reproducible mathematical and software foundation required
before real-star benchmarking.

### Corrected reference models

- Added `DERD-G-0.1`, using uniform geometric phase.
- Added `DERD-K-0.1`, using a tested Kepler-equation solver.
- Added one authoritative four-parameter schema.
- Replaced integer phase slicing with direct continuous periodic evaluation.
- Replaced sampled component normalization with analytic normalized radii, including a
  stable circular limit.
- Added cadence-stable full-cycle output normalization.
- Added explicit rejection of zero-span combinations.

### Historical capsule

- Preserved the printed `0.333` exponent.
- Preserved the iterative anomaly stepping.
- Preserved integer sample phase slicing.
- Preserved the literal `0.28` shift and intentionally unused declared `Phase` value.
- Exposed the returned sample count and implied-period discrepancy as testable outputs.

### Proof and audit utilities

- Implemented the positive-affine normalization invariance test.
- Implemented exact geometric Fourier coefficients.
- Implemented the two-root harmonic recurrence and numerical residual test.
- Added Jacobian singular values and a local identifiability condition number to fits.

### Experimental infrastructure

- Added deterministic one-active-dimension IURMv1.1.1 sweeps.
- Added a direct nonlinear DERD fitter.
- Added an explicit Fourier regression baseline.
- Added a CLI, machine-readable claim files, OURD objects, and EDOv1 provenance records.
- Added continuous integration for Python 3.10–3.12.

## Validation result

The local gate consists of unit tests, a deterministic phase-01 experiment, source hashes,
and a patch hash. The result files are under `artifacts/phase01/`.

Passing this gate proves software behavior and selected mathematical properties only. It
does not promote the physical shell or internal-orbit hypotheses.

## Immediate next gate

The next tranche should construct the **20-star shakedown set** and its frozen manifest,
then implement star-identity splits, period/phase preprocessing, uncertainty-aware
residuals, and matched DERD/Fourier evaluation. EH Lib should enter only as a
single-object reproduction capsule, not as the confirmatory validation set.
