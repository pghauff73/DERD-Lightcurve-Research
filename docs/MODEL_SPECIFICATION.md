# DERD reference model specification, version 0.2

## 1. Scope

This package converts the dual-elliptic radius-difference idea into three separately
identified computational objects:

1. **PAPER-2024**, a faithful audit reconstruction of the code printed in *Cephids
   Pulsating Stars – Transparent Outer Shell*;
2. **DERD-G-0.2**, a corrected geometric-phase waveform descriptor;
3. **DERD-K-0.2**, a corrected Kepler-time candidate.

The corrected models are waveform models. Their parameters are not treated as measured
stellar orbital elements, radii, or masses unless an independent physical-identification
gate is passed. The transparent-shell and gravity-only mechanism claims remain outside
this implementation phase.

## 2. Authoritative parameter schema

The single public schema is

\[
\Theta=(e_1,e_2,A,\phi),
\]

where

- \(0\le e_1<1\),
- \(0\le e_2<1\),
- \(A>0\),
- \(\phi\in[0,1)\) cycles.

The implementation names these dimensions `e1`, `e2`, `amplitude_ratio`, and
`phase_ratio`. This replaces the inconsistent historical four-label, five-output, and
seven-output interfaces with one explicit four-dimensional object.

## 3. Component functions

### 3.1 DERD-G: geometric phase

With \(\theta=2\pi t\), the focus-radius equation is

\[
\frac{r_G}{a}=\frac{1-e^2}{1+e\cos\theta}.
\]

The exact min-max-normalized radius is implemented in its stable closed form

\[
u_G(t;e)=
\frac{(1-e)(1-\cos 2\pi t)}{2(1+e\cos 2\pi t)}.
\]

This formula supplies the continuous circular limit

\[
u_G(t;0)=\frac{1-\cos 2\pi t}{2}
\]

without dividing by a numerically vanishing sampled range.

### 3.2 DERD-K: Kepler time

Mean anomaly is \(M=2\pi t\). Eccentric anomaly is the unique solution of

\[
E-e\sin E=M.
\]

The radius is \(r_K/a=1-e\cos E\), and its exact normalized form is

\[
u_K(t;e)=\frac{1-\cos E(t;e)}{2}.
\]

The solver uses bounded Newton iterations and a monotone bisection fallback. DERD-G and
DERD-K are never silently blended.

## 4. Dual-radius combination

For either time law,

\[
z(t;\Theta)=-u(t;e_1)+A\,u((t+\phi)\bmod 1;e_2).
\]

The reference output is

\[
y(t;\Theta)=\frac{z(t;\Theta)-z_{\min}}{z_{\max}-z_{\min}},
\]

where the extrema are estimated on a deterministic full-cycle reference grid rather than
from the observation timestamps. Consequently, changing cadence or omitting the true
maximum from an observation does not redefine the model's scale.

A zero-span combination, such as identical components with \(A=1\) and \(\phi=0\), is
rejected explicitly.

## 5. Proven normalization result

For any finite nonconstant vector \(x\), \(\alpha>0\), and finite \(\beta\),

\[
N(\alpha x+\beta)=N(x).
\]

Therefore the normalized model does not retain absolute semi-major axis, radius scale,
flux offset, or positive flux scale. Those quantities cannot be recovered from this
waveform alone. The code contains a numerical property test for this theorem.

## 6. Geometric harmonic structure

Let

\[
q=\frac{e}{1+\sqrt{1-e^2}}.
\]

For \(0\le e<1\),

\[
\frac{r_G(\theta)}{a}=\sqrt{1-e^2}
\left[1+2\sum_{n=1}^{\infty}(-q)^n\cos(n\theta)\right].
\]

For nonzero \(e_1,e_2\), the positive-frequency coefficients of the unscaled geometric
DERD combination have the form

\[
c_n=C_1z_1^n+C_2z_2^n,
\qquad
z_1=-q_1,
\qquad
z_2=-q_2e^{i2\pi\phi}.
\]

They therefore satisfy

\[
c_{n+2}-(z_1+z_2)c_{n+1}+z_1z_2c_n=0,
\qquad n\ge 1.
\]

Final positive affine normalization changes the common coefficient scale but preserves
this recurrence for nonzero harmonics. `derd.spectral` implements the exact coefficients,
the inverse \(q\mapsto e\), and recurrence residual tests.

## 7. Fitting contract

`derd.fit_waveform` uses deterministic multi-start bounded nonlinear least squares. It
returns:

- the four fitted dimensions;
- RMSE, MAE, \(R^2\), and lag-1 residual autocorrelation;
- the Jacobian singular values and condition number;
- an approximate covariance matrix only when the local Jacobian has full rank;
- total function evaluations and the optimization message.

A low residual does not override a poor condition number. Parameter interpretation must
be withheld in an ill-conditioned region even when waveform reconstruction is strong.

## 8. Baseline contract

`derd.baselines.fit_fourier` supplies an explicit harmonic-regression baseline with
\(1+2K\) effective coefficients at order \(K\). Future real-star evaluation must compare
DERD and baseline models on star-level held-out data under both matched-complexity and
best-supported-complexity conditions.

## 9. Locked claims

Version 0.2 does **not** implement or certify:

- a universal replacement for Fourier analysis;
- literal internal Keplerian stellar orbits;
- a gravity-only pulsation mechanism;
- a universal transparent outer shell;
- a shell mass fraction;
- the historical approximately 99.6% EH Lib result.

Those are separate claims with separate evidence and promotion gates.

## 10. Observational phase-origin contract

The source model contains four declared shape dimensions but real observations have an
arbitrary epoch. Phase 02 removes that coordinate without promoting it to a fifth physical
dimension:

1. test membership is frozen using catalog-period phase relative to the earliest local time;
2. a smooth Fourier fit to training observations only estimates the maximum-flux epoch;
3. observational phase zero is placed at that training-estimated maximum;
4. each DERD candidate is shifted by its own intrinsic peak phase before residuals are
   evaluated.

This quotient removes global phase while preserving the four-dimensional shape schema.

## 11. Leakage-resistant photometric contract

OGLE magnitudes are converted to relative flux using

\[
F/F_0=10^{-0.4(m-m_0)},
\qquad
\sigma_F=\frac{\ln 10}{2.5}F\sigma_m.
\]

The reference magnitude is a coordinate scale only. Final min-max scaling is fitted on
training flux values and applied unchanged to held-out values. Held-out values may
therefore fall outside the interval zero to one, which is retained rather than clipped.

## 12. Phase-02 baseline stability contract

A first pass showed that BIC can select a high-order Fourier regression with a poorly
conditioned weighted design matrix when only 19 training observations surround a held-out
phase block. The raw result is retained. The primary best-supported-complexity baseline
now applies two training-only gates:

- weighted design condition number no greater than `1e4`;
- dense full-cycle prediction span no greater than three times the training-target span.

No held-out value participates in this gate. The fixed order-two baseline remains separate.

## 13. Phase-02 evidence boundary

The executed sample contains 20 development Cepheids, balanced between fundamental and
first-overtone modes, with 24 mirrored I-band observations per target. It validates the
pipeline mechanics only. Complete official light curves, cross-class strata, uncertainty
calibration, and a sealed star-identity holdout are required before C17 can be promoted.
