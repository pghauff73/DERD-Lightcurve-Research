# DERD v1.3 release notes

## Phase 13 temporal replication ledger

Release identity:

```text
DERD-v1.3-phase13-temporal-replication-ledger
```

Decision:

```text
PHASE13_TEMPORAL_REPLICATION_LEDGER_UPDATED_POPULATION_GATE_CLOSED
```

Phase 13 adds `OGLE-LMC-RRLYR-00004` as the third cumulative exposed-development record. The target was selected from a frozen Phase-08 acquisition ranking before its Phase-13 result was recomputed. Its scientific projection and signed harmonic exchange reproduce the Phase-08 record exactly.

The new temporal tier splits the 360-observation light curve into three chronological blocks and compares h1-h4 signed coefficient vectors using covariance-aware Wald tests. All three blocks pass observation, phase-coverage, and conditioning gates. They do not all measure h1-h4 above SNR 3. The maximum temporal score is 3.432654, above an actual-cadence stationary threshold of 2.915102.

A controlled one-dimensional drift experiment first achieves sustained held-out detection performance at severity 0.75. The temporal disposition is `TEMPORAL_REPLICATION_NOT_SUPPORTED` for this exposed-development target.

The ledger now contains 3 of 15 objects. C17, family fractions, population inference, internal-mechanism claims, the universal transparent-shell claim, and shell-mass claims remain closed.
