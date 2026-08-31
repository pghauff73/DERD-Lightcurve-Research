# Phase 02 result: 20-Cepheid observational shakedown

## Gate decision

**PHASE02_ENGINEERING_SHAKEDOWN_COMPLETE_C17_NOT_PROMOTED**

The parser, provenance manifest, magnitude-to-flux conversion, star-level identity controls, circular phase-block holdout, training-only epoch and scaling, DERD-G/DERD-K fits, Fourier baselines, residual metrics, and identifiability diagnostics executed end to end.

This is not a confirmatory proof of C17. The local capsule contains only the first 24 mirrored I-band observations of each target. It is intentionally a small engineering shakedown.

## Aggregate results

- Targets: 20 (10 fundamental-mode F, 10 first-overtone 1O)
- Observations: 480 total, 380 training, 100 held out
- Best DERD beats best Fourier on 12 targets
- Best Fourier beats or ties best DERD on 8 targets
- Median best-DERD minus best-Fourier RMSE: -0.005018
- Training-only Fourier stability gate rejected at least one order for 5 targets
- Raw ungated BIC produced held-out RMSE above 1 on 3 targets; retained as a diagnostic

| Model | Median held-out RMSE | Mean held-out RMSE | Wins |
|---|---:|---:|---:|
| DERD-G | 0.081066 | 0.165059 | 6 |
| DERD-K | 0.081047 | 0.153564 | 6 |
| Fourier order 2 | 0.106832 | 0.147284 | 7 |
| Fourier stability-gated BIC | 0.115934 | 0.219915 | 1 |

| Mode | Targets | DERD wins | Median best DERD RMSE | Median best Fourier RMSE | Median difference |
|---|---:|---:|---:|---:|---:|
| 1O | 10 | 5 | 0.088104 | 0.074755 | 0.003489 |
| F | 10 | 7 | 0.068224 | 0.105889 | -0.033965 |

## Per-star results

| Star | Mode | Period (d) | Winner | Best DERD RMSE | Best Fourier RMSE | Difference | BIC order |
|---|---|---:|---|---:|---:|---:|---:|
| OGLE-LMC-CEP-0001 | 1O | 0.3068181 | derd_k | 0.066233 | 0.067856 | -0.001624 | 3 |
| OGLE-LMC-CEP-0002 | F | 3.1181490 | fourier_order2 | 0.440138 | 0.245311 | 0.194828 | 2 |
| OGLE-LMC-CEP-0003 | 1O | 0.3500957 | derd_g | 0.111129 | 0.119541 | -0.008413 | 2 |
| OGLE-LMC-CEP-0004 | 1O | 2.2296385 | fourier_order2 | 0.076098 | 0.043244 | 0.032854 | 2 |
| OGLE-LMC-CEP-0005 | F | 5.6119491 | derd_k | 0.037648 | 0.087832 | -0.050184 | 3 |
| OGLE-LMC-CEP-0006 | 1O | 3.2947501 | derd_g | 0.196063 | 0.420680 | -0.224617 | 3 |
| OGLE-LMC-CEP-0007 | 1O | 0.7090827 | fourier_order2 | 0.165676 | 0.154437 | 0.011240 | 4 |
| OGLE-LMC-CEP-0009 | 1O | 2.0243667 | fourier_order2 | 0.100109 | 0.081654 | 0.018455 | 2 |
| OGLE-LMC-CEP-0010 | 1O | 2.5655853 | derd_k | 0.046002 | 0.057713 | -0.011711 | 2 |
| OGLE-LMC-CEP-0012 | F | 2.6601839 | derd_k | 0.496977 | 0.573860 | -0.076883 | 3 |
| OGLE-LMC-CEP-0013 | 1O | 1.5985688 | fourier_order2 | 0.153908 | 0.114847 | 0.039061 | 2 |
| OGLE-LMC-CEP-0014 | 1O | 3.1356338 | fourier_bic | 0.042333 | 0.035161 | 0.007172 | 3 |
| OGLE-LMC-CEP-0015 | 1O | 1.6556995 | derd_g | 0.026326 | 0.026519 | -0.000194 | 3 |
| OGLE-LMC-CEP-0017 | F | 3.6772904 | derd_g | 0.024764 | 0.056247 | -0.031482 | 5 |
| OGLE-LMC-CEP-0018 | F | 4.0478369 | fourier_order2 | 0.297179 | 0.236452 | 0.060727 | 2 |
| OGLE-LMC-CEP-0021 | F | 5.4579579 | fourier_order2 | 0.494760 | 0.168166 | 0.326593 | 2 |
| OGLE-LMC-CEP-0023 | F | 1.7018187 | derd_g | 0.076512 | 0.112961 | -0.036448 | 5 |
| OGLE-LMC-CEP-0025 | F | 3.7334902 | derd_g | 0.059936 | 0.098817 | -0.038881 | 3 |
| OGLE-LMC-CEP-0026 | F | 2.5706724 | derd_k | 0.014884 | 0.074007 | -0.059123 | 5 |
| OGLE-LMC-CEP-0027 | F | 3.5229124 | derd_k | 0.008219 | 0.021062 | -0.012843 | 5 |

## Identifiability gate

Median Jacobian condition number: DERD-G 84.4, DERD-K 26.4.

Fits exceeding the provisional 1e5 warning gate: DERD-G 0, DERD-K 1.

Warning-gated stars: OGLE-LMC-CEP-0003.

Parameters from warning-gated fits must not be interpreted as unique physical measurements.

The local period-verification grid hit its +/-0.1 percent boundary for 4 stars, so those checks require a wider follow-up scan.

## Bootstrap spot checks

- `OGLE-LMC-CEP-0001`: 3/3 fits succeeded; phase circular standard deviation 0.08898.
- `OGLE-LMC-CEP-0002`: 3/3 fits succeeded; phase circular standard deviation 0.11044.
- `OGLE-LMC-CEP-0006`: 3/3 fits succeeded; phase circular standard deviation 0.00070.
- `OGLE-LMC-CEP-0023`: 3/3 fits succeeded; phase circular standard deviation 0.01521.

## Scientific boundary

The first pass exposed high-order Fourier instability on sparse phase blocks. The final run keeps the raw BIC result for audit and adds a training-only condition/span gate without inspecting held-out data.

The shakedown tests whether a corrected four-dimensional DERD waveform can be fit and evaluated without information leakage. It does not test the paper's claims that all pulsators possess a transparent outer shell, that motion is solely gravitational, or that shell mass can be inferred from normalized photometry.

## Next promotion gate

1. Retrieve complete official OGLE light curves and verify checksums.
2. Freeze a larger star-identity development set and an untouched final holdout.
3. Add RR Lyrae and Delta Scuti strata before evaluating broad C17 wording.
4. Add periodic spline/PCA/Gaussian-process baselines and uncertainty calibration.
5. Keep physical shell claims closed until independent non-photometric predictions exist.
