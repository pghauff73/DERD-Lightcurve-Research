# Phase 07 implementation handoff

## Release identity

```text
DERD-v0.7-phase07-raw-harmonic-forecast-gate
ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE
C17_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## Completed

- reconstructed and Git-blob-verified all 372 observations for `OGLE-LMC-CEP-0010`;
- implemented simultaneous weighted signed-harmonic extraction;
- added explicit exchange intercept and covariance ordering;
- added photometric and HC3 covariance estimators;
- implemented generic-harmonic period profiling upstream of DERD screening;
- retained four recovery and four genuinely unused forecast harmonics;
- added actual-cadence DERD and null-family calibration;
- propagated the full coefficient covariance through the nonlinear recurrence screen;
- implemented a conservative sustained MVHE gate;
- added integrated source, SNR, structure, stability and calibration checks.

## Result

The target fails the integrated gate. Four recovery harmonics are measured, but zero forecast harmonics reach SNR 2. The nominal score is above threshold, the residue constraints fail, structural stability is 0.4150%, and the cadence holdout AUC is 0.7963 against a 0.80 gate.

The target-specific observation-count experiment has its first sustained synthetic pass at 240 observations. This is an acquisition-planning floor, not a detection threshold.

## Reproduction

```bash
python -m pip install -e '.[test,research]'
python -m pytest
python experiments/run_phase07.py
python experiments/build_code_manifest.py
python experiments/build_manifest.py
python experiments/verify_manifest.py --manifest research/CODE_MANIFEST_SHA256.txt
python experiments/verify_manifest.py
```

## Next research gate

Acquire and freeze a development set spanning the preregistered pulsator strata. Each target must retain at least six harmonics, with four recovery harmonics at SNR 3 and at least two forecast harmonics at SNR 2, before the recurrence result can qualify. Sealed identities remain unopened.
