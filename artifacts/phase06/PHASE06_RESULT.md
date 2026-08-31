# Phase 06 result: harmonic phase-convention proof gate

Status: `PHASE06_PHASE_CONVENTION_GATE_COMPLETE_LEGACY_TABLES_NONQUALIFYING`

## Research action implemented

Phase 06 reverse-engineers the phase and amplitude convention used by the discovered harmonic feature tables, tests whether those tables preserve the complex coefficients required by the DERD recurrence, and defines a lossless replacement exchange schema.

The frozen source fits each harmonic as `a*sin(...) + b*cos(...) + c`, stores `sqrt(a^2+b^2)`, computes phase with `arctan(b/a)`, and then stores `phase_n - phase_1`. This loses coefficient quadrants, omits the absolute fundamental phase, and is not invariant to a change of epoch for harmonics above the fundamental.

## Synthetic held-out information test

Thresholds were selected on a deterministic development partition and scored on an independent holdout.

| Representation | Holdout ROC AUC | Balanced accuracy |
|---|---:|---:|
| Canonical signed coefficients, 8 harmonics | 1.0000 | 1.0000 |
| Canonical signed coefficients, 4 harmonics | 1.0000 | 1.0000 |
| Legacy relative phases treated as absolute | 0.6536 | 0.6107 |
| Best branch of ambiguous legacy row | 0.9821 | 0.9310 |

Four harmonics provide zero overidentifying real degrees of freedom for an unconstrained complex order-two recurrence: the recurrence is fitted, not forecast. Six or more harmonics are retained as the minimum two-coefficient forecast gate.

## Frozen-source provenance audit

The frozen implementation repeats its three frequency passes on the same unmodified data. Exact execution would therefore repeat all three amplitude and phase blocks. The compact catalog samples do not satisfy that necessary invariant:

| Object | Blocks repeat? | Maximum relative amplitude-block change |
|---|---:|---:|
| OGLE-LMC-CEP-0001 | False | 0.934 |
| OGLE-LMC-RRLYR-00001 | False | 0.855 |
| OGLE-LMC-DSCT-0001 | False | 0.503 |

This does not prove the catalog values are wrong. It proves that the exact frozen source file is insufficient provenance for reproducing those table blocks. A different source revision, hidden state, or undocumented processing step is required.

## Gate decision

`LEGACY_FEATURE_TABLES_BLOCKED_FROM_EXACT_DERD_HARMONIC_PROOF`

Catalog rows may be used for exploratory ranking only after explicit ambiguity labelling. They cannot be promoted to complex-coefficient evidence. The new DERD Harmonic Exchange 1.0 schema stores signed sine and cosine coefficients, reference epoch, fundamental frequency, source digest, and optional covariance, preserving the information needed for a genuine harmonic forecast.

## Physical scope

This phase concerns waveform information and provenance only. It does not identify internal radial orbits, a transparent external shell, or a shell mass.
