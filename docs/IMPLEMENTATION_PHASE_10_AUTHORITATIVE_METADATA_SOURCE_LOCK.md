# Phase 10: Authoritative Metadata and Source Lock

## Purpose

Phase 10 closes the input-definition gap identified by Phase 09. It freezes exactly what must be known before the fifteen-object exposed-development cohort can be executed: authoritative Delta Scuti catalogue coordinates and replayable raw photometry bytes.

It does not lower the evidence gate to fit the data currently available. The scientific output remains suppressed until every required input is independently locked.

## Authoritative catalogue contract

The catalogue contract targets the OGLE-IV LMC Delta Scuti collection and the corresponding VizieR catalogue `J/AcA/73/105`. It requires 15,256 identity rows and 15,256 parameter rows.

The fixed-width identity record supplies:

- current OGLE-IV object identity;
- catalogue subtype, `singlemode` or `multimode`;
- coordinates;
- OGLE-IV, OGLE-III, and OGLE-II aliases.

The parameter record supplies:

- the current object identity;
- mean I and optional V magnitude;
- primary period and uncertainty;
- epoch and I-band amplitude;
- optional additional periods.

## Identity policy

A requested identity can be resolved in only two ways:

1. exact and unique current OGLE-IV ID;
2. exact and unique match in the explicit OGLE-III alias field.

String similarity, numeric suffix equality, nearest coordinates, and inferred numbering continuity are forbidden. The period row must then join by the exact current object identity.

## Mode boundary

The catalogue subtype is preserved verbatim. `multimode` remains `multimode`. `singlemode` becomes `singlemode_radial_order_unresolved`. The code does not infer fundamental or first-overtone radial order from the subtype alone.

## Metadata lock

Each promoted Delta Scuti lock contains:

- requested and current identities;
- match basis;
- subtype and restrained mode label;
- period and period uncertainty;
- identity-row SHA-256;
- parameter-row SHA-256;
- complete identity-file SHA-256;
- complete parameter-file SHA-256;
- authority, source URLs, and catalogue release;
- canonical lock SHA-256.

A row cannot be promoted unless every field and digest passes.

## Source lock

Each of the fifteen raw photometry sources must independently reproduce:

- repository and commit;
- repository path;
- Git blob SHA-1;
- byte count;
- observation count;
- SHA-256;
- at least 240 retainable observations.

A metadata lock cannot substitute for a source lock, and a source lock cannot substitute for claim-grade metadata.

## Optional cohort execution

When all fifteen objects are input-ready, `run_phase10.py --execute-ready` invokes the unchanged Phase-08/Phase-07 object gate:

- signed simultaneous harmonics h1-h8;
- HC3 full coefficient covariance;
- h1-h4 DERD recovery;
- h5-h8 independent recurrence forecast;
- target-specific cadence calibration;
- covariance propagation;
- source, SNR, structure, score, and stability gates.

Only a complete denominator permits family-level Wilson intervals.

## Current state

The protocol seal, catalogue-contract seal, exact 5+5+5 structure, ten non-Delta-Scuti metadata coordinates, and five cached Phase-08 records verify. The authoritative catalogue bytes and all fifteen complete raw source files are absent from the release runtime.

The current decision is:

`PHASE10_IMPLEMENTED_CATALOG_CONTRACT_LOCKED_EXECUTION_BLOCKED_BY_AUTHORITATIVE_ROWS_AND_RAW_SOURCE_BYTES`

## Scientific boundary

Phase 10 locks inputs for normalized waveform testing. It does not identify a unique internal stellar mechanism, establish a transparent shell, or infer stellar or shell mass. Those claims require independent mechanism-sensitive and scale-sensitive observables.
