# Phase 17: External Fourier-Analysis Anchor

## Purpose

Phase 17 adds the first analysis node produced by a research group external to the DERD implementation. It does not claim an independent observing-source replication. Instead, it tests whether a locally reconstructed, provenance-frozen OGLE V-band subset yields cosine-series Fourier invariants consistent with the values published by Jurkovic et al. (2022) for `OGLE-LMC-CEP-0002`.

## External coordinates

The external anchor uses

\[
m(t)=m_0+\sum_i A_i\cos(2\pi i f t+\phi_i),
\]

\[
R_{i1}=A_i/A_1,
\qquad
\phi_{i1}=\phi_i-i\phi_1.
\]

The frozen published coordinates are `R21`, `phi21`, `R31`, and `phi31`, including their reported one-sigma uncertainties.

## Local estimator

The local fit is simultaneous and weighted:

\[
m(t)=c+\sum_{n=1}^{3}\left[a_n\sin(2\pi n\varphi)+b_n\cos(2\pi n\varphi)\right].
\]

It is converted to the cosine convention through

\[
A_n=\sqrt{a_n^2+b_n^2},
\qquad
\phi_n=\operatorname{atan2}(-a_n,b_n).
\]

The period is selected by minimizing the generic weighted Fourier residual within a frozen ±0.1% interval around the published period. DERD compatibility does not select the period.

## Uncertainty

The implementation performs 2,000 deterministic resamples, each containing 60% of the available observations without replacement. The period and three-harmonic fit are recomputed for every resample. Circular phase coordinates are unwrapped around the full-sample estimate before covariance estimation.

The comparison statistic is

\[
Q=(\hat{\theta}_{\rm local}-\theta_{\rm ext})^T
(\Sigma_{\rm local}+\Sigma_{\rm ext})^{-1}
(\hat{\theta}_{\rm local}-\theta_{\rm ext}),
\]

with four degrees of freedom.

## Independence classification

A result can be statistically consistent while failing the independence gate. Phase 17 requires all of the following for an independent astrophysical replication:

1. external research-group independence;
2. an independent observing source;
3. known identity of the exact publication input bytes;
4. source completeness relative to the published method;
5. joint and marginal statistical consistency.

The current edge has external analysis-group independence, but not observing-source independence, exact byte identity, or the publication's minimum 50-measurement input. Its classification is therefore `EXTERNAL_ANALYSIS_CONSISTENT_PARTIAL_SOURCE_OVERLAP`.

## Claim boundary

This phase tests Fourier-coordinate transport, uncertainty, and evidence provenance. It does not identify a unique stellar mechanism and cannot establish an exterior shell or mass scale.
