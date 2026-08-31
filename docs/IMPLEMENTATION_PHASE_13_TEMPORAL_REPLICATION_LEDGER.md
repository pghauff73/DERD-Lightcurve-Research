# Phase 13 implementation: temporal replication ledger

## Purpose

Phase 13 extends the Phase-12 cumulative waveform-evidence ledger by one result-blind acquisition and adds an orthogonal temporal-replication audit. The new audit asks whether the signed harmonic coefficients measured from a complete light curve remain statistically compatible across chronological observation blocks.

This is a waveform-stability test. It is not a test of shell mass, a unique internal mechanism, or literal internal Keplerian motion.

## Frozen acquisition rule

Candidates are taken from the frozen Phase-08 cohort, restricted to claim-grade period evidence, and filtered to remove identities already represented in the verified Phase-12 ledger. Candidates are sorted by decreasing frozen acquisition-priority score, with object identity as a deterministic tie-breaker.

The selected Phase-13 target is:

```text
OGLE-LMC-RRLYR-00004
```

Its selection precedes and does not depend on the Phase-13 recomputation or temporal result.

## Base evidence replay

The source importer verifies four independent source coordinates:

1. byte count;
2. observation count;
3. Git blob SHA-1;
4. SHA-256.

The fresh target-level computation reuses the Phase-08/Phase-12 scientific coordinates:

```text
synthetic samples per class = 96
covariance draws = 2048
period grid count = 101
minimum observations = 240
```

The scientific result and lossless harmonic exchange are compared with the inherited Phase-08 record. Numerical or exchange drift is a hard failure. A local path or human-readable period-label difference may be recorded as transport metadata drift.

## Temporal replication model

After conservative uncertainty cleaning and magnitude-to-relative-flux conversion, the time-sorted light curve is split into three equal-count chronological blocks. Every block is fitted at a common catalog period and common reference epoch with

\[
y(t)=c_0+\sum_{n=1}^{8}\left[a_n\sin(n\omega t)+b_n\cos(n\omega t)\right].
\]

For recovery harmonics h1 through h4, define

\[
\boldsymbol\beta_k=(a_{1,k},\ldots,a_{4,k},b_{1,k},\ldots,b_{4,k})^T
\]

for block \(k\), with covariance \(\Sigma_k\). For blocks \(i,j\), Phase 13 computes

\[
W_{ij}=(\boldsymbol\beta_i-\boldsymbol\beta_j)^T
(\Sigma_i+\Sigma_j)^+
(\boldsymbol\beta_i-\boldsymbol\beta_j),
\]

and the normalized temporal score

\[
T_{ij}=\frac{W_{ij}}{\operatorname{rank}(\Sigma_i+\Sigma_j)}.
\]

The object score is

\[
T_{\max}=\max_{i<j}T_{ij}.
\]

## Actual-cadence calibration

A full eight-harmonic fit supplies a stationary baseline. Wild residual bootstrap replicates preserve the actual observation times, errors, and residual magnitudes. The stationary threshold is the 95th percentile of development stationary scores.

A one-dimensional controlled-drift family modifies h2 through h4 only in the final chronological block. Severity is the sole active IURMv1.1.1 dimension. Held-out drift detection must achieve both:

```text
ROC AUC >= 0.80
balanced accuracy >= 0.75
```

The first severity at which that level and every larger tested level pass is the sustained detectable-drift coordinate.

## Phase-13 result

For `OGLE-LMC-RRLYR-00004`:

```text
observations = 360
chronological blocks = 120 + 120 + 120
all block-quality gates = pass
all blocks h1-h4 SNR >= 3 = fail
maximum temporal score = 3.4326544455
stationary threshold = 2.9151015296
first sustained detectable severity = 0.75
temporal disposition = TEMPORAL_REPLICATION_NOT_SUPPORTED
```

The largest pairwise change occurs between blocks 2 and 3:

```text
W = 27.4612355642
df = 8
W/df = 3.4326544455
p = 0.0005883168
```

This does not prove a physical change in the star. It establishes that the fixed-period h1-h4 coefficient vector is not supported as stationary under the frozen actual-cadence audit, while higher-order signal remains too weak for every block to independently satisfy the four-recovery-harmonic gate.

## Ledger and denominator firewall

The base result is appended as the third unique cumulative record. The temporal audit is stored as a separately hashed sidecar bound to the new ledger record. Family fractions and population estimates remain suppressed until all fifteen frozen identities have verified cumulative records.

## Reproduction

```bash
PYTHONPATH=src:. python experiments/import_phase13_source_pack.py \
  --root . \
  --input-dir /path/to/rights-reviewed/source-pack \
  --acknowledge-ogle-attribution

PYTHONPATH=src:. python experiments/run_phase13.py \
  --root . \
  --execute-ready
```

The raw third-party light curve is used locally and excluded from the redistributable evidence bundle.
