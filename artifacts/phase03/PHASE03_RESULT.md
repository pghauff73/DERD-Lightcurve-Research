# Phase 03 result: nonlinear baseline, uncertainty calibration, and promotion gate

Status: `PHASE03_METHODS_AND_CALIBRATION_COMPLETE_C17_NOT_PROMOTED`

## Implemented

- Periodic squared-exponential kernel-ridge baseline with nested, training-only phase-block selection.
- Four-fold circular phase out-of-fold predictions for DERD-G, DERD-K, Fourier order 2, and periodic KRR.
- Training-only 90% error-standardized symmetric interval calibration and held-out coverage audit.
- Adaptive period verification using staged +/-0.1%, +/-0.5%, and +/-2% scans.
- Train-only selection of DERD time law and comparator baseline before held-out scoring.
- Paired star-level bootstrap confidence intervals, exact sign test, and noninferiority gate.
- Cryptographic future-holdout protocol and explicit no-promotion decision logic.

## Dataset boundary

The executable population remains 20 LMC classical Cepheids with 480 observations, of which 100 are held out. Each source file is still a 24-row mirror excerpt rather than a complete official light curve.

## Held-out performance

| Model | Median RMSE | Mean RMSE | Descriptive wins |
|---|---:|---:|---:|
| DERD-G | 0.080759 | 0.165427 | 3 |
| DERD-K | 0.072034 | 0.156419 | 7 |
| Fourier order 2 | 0.106832 | 0.147284 | 8 |
| Periodic KRR | 0.122305 | 0.161320 | 2 |

## Primary preselected comparison

For each star, DERD-G versus DERD-K and Fourier order 2 versus periodic KRR were selected using training-only out-of-fold weighted RMSE. The selected DERD and selected baseline were then evaluated once on the existing held-out phase block.

- Mean DERD-minus-baseline RMSE: -0.009685
- Median DERD-minus-baseline RMSE: 0.006606
- 95% bootstrap CI for mean difference: [-0.067403, 0.046714]
- 95% bootstrap CI for median difference: [-0.024680, 0.031177]
- DERD wins: 9 of 20
- Exact two-sided sign-test p-value: 0.823803
- Provisional +0.02 RMSE noninferiority gate: fail

The statistical output is developmental because the same stars were visible in Phase 02 and the photometry excerpts are sparse. It cannot serve as a pristine confirmatory result.

## Interval calibration

| Model | Nominal | Pooled coverage | Absolute error | Mean width | Interval score |
|---|---:|---:|---:|---:|---:|
| **Error-standardized** |  |  |  |  |  |
| DERD-G | 0.900 | 0.680 | 0.220 | 0.469793 | 1.816275 |
| DERD-K | 0.900 | 0.700 | 0.200 | 0.400935 | 1.760918 |
| Fourier order 2 | 0.900 | 0.870 | 0.030 | 1.053051 | 1.475737 |
| Periodic KRR | 0.900 | 0.790 | 0.110 | 0.582214 | 1.237835 |
| **Absolute residual** |  |  |  |  |  |
| DERD-G | 0.900 | 0.700 | 0.200 | 0.429352 | 1.824940 |
| DERD-K | 0.900 | 0.700 | 0.200 | 0.365106 | 1.763343 |
| Fourier order 2 | 0.900 | 0.860 | 0.040 | 1.023837 | 1.426790 |
| Periodic KRR | 0.900 | 0.780 | 0.120 | 0.586762 | 1.232890 |

## Adaptive period scan

Resolved before exhausting the staged scan for 20 of 20 stars. Unresolved targets: none.

The adaptive scan is a diagnostic only. The main waveform benchmark retains catalog periods so that period policy is not silently changed between phases.

The periodic-kernel length-scale grid was widened after the first Phase-03 pass selected its former upper boundary for all targets. The final expanded grid still hit its 2.0 boundary for 3 targets; those cases are explicitly flagged.

## Gate decision

`DENIED_INCOMPLETE_DATA_CLASS_SCOPE_AND_NO_PRISTINE_SEALED_HOLDOUT`

C17 remains open and unpromoted. Even a statistical noninferiority pass cannot compensate for missing complete photometry, absence of RR Lyrae and Delta Scuti strata, and lack of a prospectively sealed star-identity holdout. This is the OURD/IURMv1.1.1 rule that dimensions do not pay each other's debts.

The paper's physical orbit, transparent-shell, and shell-mass claims remain outside this phase. Normalized light-curve matching is not treated as mass or mechanism evidence.

## Per-star primary results

| Star | Mode | Selected DERD | Selected baseline | DERD RMSE | Baseline RMSE | Difference | Period stages |
|---|---|---|---|---:|---:|---:|---:|
| OGLE-LMC-CEP-0001 | 1O | derd_g | periodic_krr | 0.070142 | 0.067593 | 0.002549 | 1 |
| OGLE-LMC-CEP-0002 | F | derd_k | fourier_order2 | 0.436174 | 0.245311 | 0.190863 | 1 |
| OGLE-LMC-CEP-0003 | 1O | derd_k | periodic_krr | 0.106173 | 0.124720 | -0.018547 | 1 |
| OGLE-LMC-CEP-0004 | 1O | derd_g | fourier_order2 | 0.085280 | 0.043244 | 0.042036 | 2 |
| OGLE-LMC-CEP-0005 | F | derd_k | periodic_krr | 0.037315 | 0.166261 | -0.128945 | 3 |
| OGLE-LMC-CEP-0006 | 1O | derd_k | fourier_order2 | 0.215180 | 0.420680 | -0.205500 | 1 |
| OGLE-LMC-CEP-0007 | 1O | derd_k | periodic_krr | 0.165906 | 0.148814 | 0.017092 | 1 |
| OGLE-LMC-CEP-0009 | 1O | derd_k | fourier_order2 | 0.101972 | 0.081654 | 0.020318 | 1 |
| OGLE-LMC-CEP-0010 | 1O | derd_g | periodic_krr | 0.076063 | 0.064069 | 0.011994 | 1 |
| OGLE-LMC-CEP-0012 | F | derd_k | periodic_krr | 0.496748 | 0.769724 | -0.272976 | 1 |
| OGLE-LMC-CEP-0013 | 1O | derd_g | fourier_order2 | 0.173310 | 0.114847 | 0.058463 | 1 |
| OGLE-LMC-CEP-0014 | 1O | derd_g | periodic_krr | 0.042036 | 0.044495 | -0.002459 | 1 |
| OGLE-LMC-CEP-0015 | 1O | derd_k | periodic_krr | 0.040122 | 0.029459 | 0.010663 | 1 |
| OGLE-LMC-CEP-0017 | F | derd_k | periodic_krr | 0.057376 | 0.298119 | -0.240743 | 1 |
| OGLE-LMC-CEP-0018 | F | derd_g | periodic_krr | 0.383026 | 0.260109 | 0.122918 | 1 |
| OGLE-LMC-CEP-0021 | F | derd_k | periodic_krr | 0.495143 | 0.216679 | 0.278464 | 1 |
| OGLE-LMC-CEP-0023 | F | derd_k | periodic_krr | 0.050801 | 0.150621 | -0.099820 | 1 |
| OGLE-LMC-CEP-0025 | F | derd_k | fourier_order2 | 0.068003 | 0.098817 | -0.030814 | 2 |
| OGLE-LMC-CEP-0026 | F | derd_g | periodic_krr | 0.070355 | 0.016692 | 0.053664 | 2 |
| OGLE-LMC-CEP-0027 | F | derd_k | periodic_krr | 0.008198 | 0.011110 | -0.002912 | 1 |

## Immediate next gate

1. Import complete official I-band observations under the frozen attribution and checksum procedure.
2. Build a new candidate pool and cryptographically seal star identities before any Phase-04 scoring.
3. Add RR Lyrae and Delta Scuti ingestion capsules with class-specific period and multimode policies.
4. Calibrate intervals on a larger development population, then evaluate the sealed holdout once.
5. Open physical-mechanism tests only after independent radial-velocity, colour, spectral, or diameter predictions exist.
