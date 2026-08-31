# DERD v0.5 Phase-05 implementation handoff

## Implemented target

Phase 05 converts the exact two-root harmonic recurrence of geometric DERD into a fast
candidate-triage engine.  The engine extracts complex harmonics from irregular photometry,
recovers a constrained four-parameter candidate, tests residue and root-domain conditions,
and forecasts withheld harmonics when at least six coefficients are available.

This release is a waveform-family and acquisition-design tool.  It does not infer a
stellar interior, a transparent outer shell, or a shell mass.

## Main entry points

```bash
python experiments/run_phase05.py --output artifacts/phase05
python -m pytest
python experiments/build_code_manifest.py --root .
python experiments/build_manifest.py --root .
python experiments/verify_manifest.py --manifest research/CODE_MANIFEST_SHA256.txt
python experiments/verify_manifest.py
```

Primary modules:

- `src/derd/harmonic_screen.py`
- `src/derd/catalog_harmonics.py`
- `src/derd/validation_phase05.py`
- `experiments/run_phase05.py`

## Frozen Phase-05 decision

The 24-observation exposed cadence is insufficient for the harmonic discriminator.  At the
observed uncertainty scale, the cadence-aware synthetic holdout produced ROC AUC `0.4764`
and balanced accuracy `0.5597`.

The IURMv1.1.1 observation-count experiment varied only observation count under uniform
phase coverage.  The first tested count passing all four frozen robustness gates was `160`
observations per star.  This is an optimistic acquisition lower bound, not a universal
sample-size theorem.

No exposed real pilot star passed score, harmonic-SNR, conditioning, and bootstrap-stability
gates simultaneously.  `OGLE-LMC-CEP-0010` is an acquisition priority only.

## Evidence and claim objects

- `research/claims/C25.json`: exact recurrence and residue theorem
- `research/claims/C26.json`: algebraic recovery software property
- `research/claims/C27.json`: inadequacy of the 24-point cadence
- `research/claims/C28.json`: provisional MVHE-160 acquisition target
- `research/iurm/phase05_harmonic_screen_manifest.json`
- `research/edov1/phase05_evidence_manifest.json`
- `artifacts/phase05/phase05_summary.json`

## Next gate

Acquire complete, provenance-frozen development light curves with at least 160 well-spread
observations per star, or obtain independently verified harmonic summaries with sufficient
harmonics for a genuine forecast test.  Verify the amplitude/phase convention before using
third-party catalog tables.  Prospective Phase-04 sealed identities must remain uninspected.
