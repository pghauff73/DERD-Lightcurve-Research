# Phase 18: exact external-input-scope reconstruction

## Purpose

Phase 18 replaces the Phase-17 33-row partial V-band anchor with a verified, chronological merge of the official current OGLE-III and OGLE-IV V-band files for `OGLE-LMC-CEP-0002`.

The external paper states that available OGLE-III and OGLE-IV V-band observations were merged, targets with fewer than 50 measurements were excluded, and the final cosine-series parameters were obtained with a simultaneous fit. It does not publish source hashes, an exact row list, the analysis source code, the precise Lomb-Scargle grid, or the `curve_fit` weighting call.

Phase 18 therefore proves a **publication-compatible source-scope and parameter reconstruction**, not byte-identical or code-identical replay.

## Frozen source objects

| Component | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| OGLE-III V | 33 | 792 | `bc36f947e8e3d36d197498345b83aa24f9e1a0d9010a99f4fe8a0bab4ccdb855` |
| OGLE-IV V | 32 | 768 | `ef8975b4bed903433ae3b8e66072cafaa5671d2c085eb88d32bd33eaa049067c` |
| Chronological merge | 65 | 1560 | `420871872497c8fccd8afe273a6548d079f59028f1067dcc1cd9c5f56711729d` |

Raw bytes are retrieved locally, verified, used for execution, and excluded from the redistributable bundle.

## Model

The publication's cosine-series form is implemented as

\[
m(t)=m_0+\sum_{i=1}^{3}A_i\cos(2\pi i f(t-t_0)+\phi_i).
\]

The compared invariants are

\[
R_{21}=A_2/A_1,\qquad
\phi_{21}=\phi_2-2\phi_1,
\]

\[
R_{31}=A_3/A_1,\qquad
\phi_{31}=\phi_3-3\phi_1.
\]

The covariance of the four-invariant vector is obtained by propagating the SciPy `curve_fit` covariance through the analytic Jacobian.

## IURMv1.1.1 method lattice

Three dimensions are varied separately:

1. source scope: OGLE-III, OGLE-IV, merged;
2. weighting: unweighted, quoted relative, quoted absolute;
3. period mode: fixed at the published period or freely fine-tuned within ±0.1%.

The preregistered primary result is:

```text
merged_ogleiii_iv_unweighted_free
```

It uses the fewest undocumented assumptions because the article names `curve_fit` but does not state that per-point errors were passed as `sigma`.

## Promotion gate

The primary estimate must satisfy:

- all marginal absolute z-scores below 2;
- a Mahalanobis joint p-value of at least 0.05;
- at least 50 merged measurements;
- both source components passing SHA-256, Git-blob, byte-count and row-count checks.

Passing these gates does not establish exact publication input identity, exact code replay, an independent observing source, or independent astrophysical replication.

## Physical-claim boundary

The source paper normalizes both component radius curves and the resultant and states that mass is factored out. Phase 18 therefore tests only Fourier-coordinate and provenance reconstruction. It does not identify an internal stellar mechanism, a transparent shell, shell prevalence, or shell mass.
