# Phase 06: harmonic phase-convention proof gate

## Objective

Phase 05 established that geometric DERD has a constrained complex-harmonic sequence and that a genuine forecast test requires more harmonic information than the exposed 24-point pilot can supply. Phase 06 addresses the next blocking dimension: whether discovered catalog amplitude/phase columns preserve the complex coefficients required by the recurrence proof.

This is a provenance and waveform-information study. It does not infer internal stellar motion, an external transparent shell, or shell mass.

## Frozen source convention

The audited source fits each harmonic independently as

\[
y_n(t)=a_n\sin(2\pi n f t)+b_n\cos(2\pi n f t)+c_n.
\]

It stores

\[
A_n=\sqrt{a_n^2+b_n^2}
\]

and

\[
p_n=\arctan\!\left(\frac{b_n}{a_n}\right).
\]

The catalog relative phase is then

\[
d_n=p_n-p_1.
\]

The canonical positive-frequency coefficient used by the DERD proof engine is

\[
C_n=\frac{b_n-i a_n}{2}.
\]

### Quadrant loss

The one-argument arctangent identifies

\[
(a_n,b_n)\quad\text{and}\quad(-a_n,-b_n),
\]

because both have the same ratio. Thus each stored phase is known only modulo \(\pi\). After quotienting one global sign, a four-harmonic row retains at least

\[
2^{4-1}=8
\]

discrete quadrant branches.

### Missing continuous phase

The source stores \(p_n-p_1\), but does not store \(p_1\). A continuum of fundamental principal phases can therefore reconstruct the same row, subject to the principal-arctangent interval.

### Epoch non-invariance

For an epoch shift of \(\tau\) periods, an absolute sine phase transforms as

\[
\phi_n' = \phi_n + 2\pi n\tau.
\]

The invariant harmonic combination is

\[
\psi_n=\phi_n-n\phi_1.
\]

The source quantity \(\phi_n-\phi_1\) instead transforms by an additional
\(2\pi(n-1)\tau\) before principal-branch wrapping. It is not an epoch-invariant descriptor when \(n>1\).

## Four-harmonic evidence degree

An unconstrained complex order-two recurrence contains two complex coefficients, or four real fitted dimensions. With \(N\) complex harmonics, the recurrence supplies \(N-2\) complex equations. The overidentifying residual degrees of freedom are

\[
2(N-2)-4=2(N-4).
\]

For \(N=4\), this equals zero. Four harmonics can support constrained shape triage through DERD root and residue restrictions, but they cannot provide an independent recurrence forecast. Phase 06 retains the Phase-05 requirement of at least six harmonics for two complex forecast coefficients.

## Frozen-source block provenance test

The frozen code loops over three nominal frequency blocks, but does not assign the computed residual `data2` back to `data`. Each loop therefore runs on the same input and same dominant frequency. Exact deterministic execution of that source must repeat all three amplitude and phase blocks.

Compact first-row samples from the Cepheid, RR Lyrae, and Delta Scuti tables do not repeat those blocks. This does not establish that the table values are false. It establishes that the exact frozen source file is not a complete reproducer of the table values. At least one different revision, hidden state, or undocumented processing step is required.

## Lossless replacement

`DERD-HARMONIC-EXCHANGE-1.0` stores:

- object identity;
- fundamental frequency;
- reference epoch;
- time and value units;
- signed sine coefficients \(a_n\);
- signed cosine coefficients \(b_n\);
- source locator and SHA-256;
- optional full coefficient covariance;
- arbitrary provenance metadata.

The canonical coefficients are reconstructed without ambiguity as

\[
C_n=(b_n-i a_n)/2.
\]

The exchange object is canonical-JSON serializable and receives its own SHA-256 record digest.

## Decision rule

A legacy catalog row is barred from evidence-bearing DERD recurrence screening when any of the following applies:

1. signed sine/cosine coefficients are absent;
2. the absolute reference epoch or fundamental phase is absent;
3. only common-subtracted relative phases are present;
4. fewer than six harmonics are available for the planned forecast gate;
5. the extraction source cannot reproduce the table convention.

Legacy rows may still be used for explicitly labelled exploratory acquisition ranking. A phase-marginalized minimum score is a permissive compatibility bound, not a measurement of the actual complex sequence.
