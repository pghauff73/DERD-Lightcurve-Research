# Phase 14 implementation: period-coordinate robustness ledger

## Purpose

Phase 14 extends the cumulative waveform-evidence ledger by one result-blind acquisition and tests whether the temporal-stationarity conclusion depends on a small error in the adopted pulsation period.

The period intervention is orthogonal to DERD compatibility. The refined period is selected using a generic phase-dispersion statistic, not by minimizing the DERD score or the temporal Wald statistic.

This is a waveform and coordinate-robustness test. It is not a test of shell mass, a unique internal mechanism, or literal internal Keplerian motion.

## Frozen acquisition rule

Candidates come from the frozen Phase-08 cohort, are restricted to claim-grade period evidence, and exclude all objects already represented in the verified Phase-13 ledger. Sorting uses decreasing frozen acquisition-priority score with object identity as the tie-breaker.

The selected target is:

```text
OGLE-LMC-CEP-0002
```

Selection precedes the Phase-14 recomputation and coordinate audit.

## Source and base-result replay

The source importer verifies:

1. byte count;
2. observation count;
3. Git blob SHA-1;
4. SHA-256.

The fresh target-level calculation reuses the Phase-08/Phase-12 coordinates:

```text
synthetic samples per class = 96
covariance draws = 2048
period grid count = 101
minimum observations = 240
```

Scientific output and the lossless signed-harmonic exchange are compared with the inherited Phase-08 record. Scientific drift is a hard failure. Local-path differences are recorded separately as transport metadata.

## Independent period coordinate

For trial period \(P\), phase is

\[
\phi_i(P)=\operatorname{frac}\left(\frac{t_i-t_{\min}}{P}\right).
\]

The data are assigned to eight phase bins. The objective is the ratio of summed within-bin squared residuals to total squared residuals:

\[
D(P)=
\frac{\sum_b\sum_{i\in b}(y_i-\bar y_b)^2}
{\sum_i(y_i-\bar y)^2}.
\]

Lower values indicate greater phase concentration. A staged search uses relative spans

```text
±0.1%, ±0.5%, ±2.0%
```

and widens only when the current optimum is on a boundary.

## Temporal robustness comparison

The Phase-13 chronological h1-h4 coefficient audit is run twice with identical cadence, data, block boundaries, covariance method, stationary-bootstrap coordinates, and drift calibration:

1. at the catalog period;
2. at the independently refined period.

The possible classifications are:

```text
TEMPORAL_STATIONARITY_ROBUST_TO_PERIOD_REFINEMENT
PERIOD_REFINEMENT_RESCUES_TEMPORAL_STATIONARITY_GATE
PERIOD_REFINEMENT_BREAKS_TEMPORAL_STATIONARITY_GATE
TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT
```

A narrow 101-point ±0.1% surface records both phase dispersion and the unthresholded maximum pairwise temporal score. That surface is descriptive; it does not select the refined period.

## Phase-14 result

For `OGLE-LMC-CEP-0002`:

```text
observations = 366
catalog period = 3.1181490000 d
refined period = 3.1180866370 d
relative delta = -2.0e-5
catalog dispersion = 0.0917860413
refined dispersion = 0.0835043400
catalog temporal score = 2.3856438429
catalog stationary threshold = 2.2241818739
refined temporal score = 2.3283246994
refined stationary threshold = 2.2540963080
classification = TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT
```

The minimum temporal score on the narrow surface occurs at the same refined period and is only about 2.4% below the catalog-period score. The failure of the temporal gate therefore survives this independent period correction.

No chronological block independently measures all h1-h4 above SNR 3. This limits the strength of the temporal conclusion and is preserved as contradiction evidence.

## Ledger and denominator firewall

The base waveform result is appended as the fourth unique cumulative record. The period-coordinate audit is stored as a separately hashed sidecar. The earlier Phase-13 temporal sidecar remains inherited and hash-verified.

Family fractions and population estimates remain suppressed until all fifteen frozen identities have verified cumulative evidence records.

## Reproduction

```bash
PYTHONPATH=src:. python experiments/import_phase14_source_pack.py \
  --root . \
  --input-dir /path/to/rights-reviewed/source-pack \
  --acknowledge-ogle-attribution

PYTHONPATH=src:. python experiments/run_phase14.py \
  --root . \
  --execute-ready
```

The third-party raw light curve is used locally and excluded from the redistributable evidence bundle.
