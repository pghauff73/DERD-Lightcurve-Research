# Phase 09: Claim-Grade Multi-Family Development Cohort

## Purpose

Phase 09 implements the frozen 5+5+5 exposed-development protocol created at the end of Phase 08. It does not lower the protocol to fit currently available evidence. Instead, it places four independent gates in front of any family-level estimate:

1. exact cohort structure;
2. claim-grade period, mode, and identity provenance;
3. replayable source bytes with Git and SHA-256 verification;
4. a completed object-level harmonic-forecast result for every declared identity.

A family fraction is emitted only when all fifteen objects pass all four gates. Partial evidence is reported as coverage and blocker counts, not as a population estimate.

## Frozen population

The declared cohort contains exactly:

- five classical Cepheids;
- five RR Lyrae stars;
- five Delta Scuti candidates.

All are marked `exposed-development-only`. They may be used to develop and audit the method but cannot later be renamed as a pristine confirmatory holdout.

## Claim-grade metadata rule

A target is metadata-ready only when:

- its period is finite and positive;
- `period_evidence_grade` begins with `EXTERNAL_CATALOG`;
- its mode is resolved;
- `mode_evidence_grade` begins with `EXTERNAL_CATALOG`;
- the identity relation is `RESOLVED_EXACT`.

Legacy `PeriodLS` values remain engineering coordinates. They are not silently promoted to external catalog periods.

## Source gate

Each raw source is identified by:

- repository and commit;
- repository-relative path;
- Git blob SHA-1;
- byte count;
- observation count;
- SHA-256 frozen in the manifest or in a verified acquisition receipt.

The acquisition receipt is accepted only when it is tied to the current cohort manifest, records attribution acknowledgement, is not a dry run, and exactly matches the target identity and source coordinates. The local file must then independently reproduce every frozen digest and count.

## Existing evidence reuse

Five Phase-08 object records are inherited. Reuse is accepted only when:

- the target record is unique in the Phase-08 summary;
- its canonical JSON SHA-256 matches the Phase-09 manifest;
- its harmonic-exchange file exists;
- the exchange SHA-256 matches.

Inherited records are descriptive evidence. They cannot make an incomplete fifteen-object cohort complete.

## Object-level scientific gate

When every target is executable, Phase 09 calls the unchanged Phase-08/Phase-07 object gate:

- signed simultaneous harmonics h1–h8;
- full HC3 coefficient covariance;
- h1–h4 algebraic DERD recovery;
- h5–h8 independent recurrence forecast;
- target-specific cadence calibration;
- covariance propagation;
- source, sampling, SNR, structural, calibration, and stability gates.

The final family statistics use Wilson 95% intervals for recovery-ready, forecast-measured, structurally compatible, and qualified fractions.

## Current implementation state

The software and protocol checks are implemented. The current declared cohort passes the exact 5+5+5 structure gate but does not pass the metadata and source replay gates:

- the selected Delta Scuti identities retain legacy diagnostic periods and unresolved mode/crosswalk metadata;
- third-party raw mirror bytes are intentionally absent from the redistributable release;
- ten target SHA-256 values await verified acquisition receipts;
- five inherited Phase-08 results are cryptographically verified.

Accordingly, the current result is:

`PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_AND_SOURCE_GATES`

## Scientific boundary

Phase 09 evaluates normalized waveform compatibility only. It does not identify a unique internal mechanism, establish a transparent shell, or infer stellar or shell mass. Those claims require independent mechanism-sensitive and scale-sensitive observables.
