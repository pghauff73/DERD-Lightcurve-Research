# DERD v1.2 release notes

## Phase 12 cumulative replay ledger

Release identity:

```text
DERD-v1.2-phase12-cumulative-replay-ledger
```

Decision:

```text
PHASE12_CUMULATIVE_LEDGER_UPDATED_REPLAY_AUDIT_PASSED_POPULATION_GATE_CLOSED
```

Phase 12 preserves verified target evidence across incremental source-pack cycles. A prior target remains counted after its input-lock, result, and harmonic-exchange digests are verified, even when third-party raw bytes are not redistributed in the release. Newly unlocked targets execute under the unchanged Phase-11 scientific coordinates and are appended only after verification.

The first cumulative update adds `OGLE-LMC-RRLYR-00001` to the prior `OGLE-LMC-CEP-0004` record. The RR Lyrae target reaches the forecast-harmonic stage, but it does not measure two forecast harmonics above SNR 2 and its DERD score remains above its target-specific threshold.

A cross-phase audit reproduces the Phase-08 scientific record and harmonic exchange exactly. The only differences are permitted transport labels: the local source path and a human-readable period-source suffix.

The cumulative ledger now contains 2 of 15 frozen objects. Family fractions, Wilson intervals, cross-family comparisons, C17, physical-mechanism, transparent-shell, and mass claims remain closed.
