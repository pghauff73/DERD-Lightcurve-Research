# Phase 08 implementation handoff

## Completed

- six-object raw-photometry development cohort across three pulsator families;
- byte-count, observation-count, Git blob SHA-1, and SHA-256 verification;
- target-specific signed eight-harmonic extraction and full covariance transport;
- independent actual-cadence null calibration for every object;
- stage-specific abstention, rejection, and qualification labels;
- source-completeness versus cleaning separation;
- deterministic acquisition-priority queue;
- four CSV evidence tables, six harmonic-exchange records, four figures, and a complete
  machine-readable result;
- tests covering seed isolation, source-cleaning orthogonality, period-evidence gating,
  source-byte verification, and a synthetic three-family cohort.

## Scientific result

No object crossed the complete gate. Three objects stop at recovery-harmonic evidence, one
RRab object reaches but fails the forecast-harmonic gate, and two Delta Scuti objects remain
engineering-only because their period coordinates originate in a legacy feature table.
All six nominal recurrence candidates violate at least one frozen structural constraint.

## Next implementation target

Construct a claim-grade 15-object exposed development cohort with at least five objects per
family. Freeze an external period and mode source for every object before inspecting its
DERD score. Preserve the current six objects as development history and do not move them
into a pristine sealed holdout.

## Raw-data policy

The release does not redistribute the six third-party raw files. Run
`experiments/fetch_phase08_sources.py` after reviewing source and OGLE reuse requirements.
The fetcher refuses to write data unless all four byte-level checks pass.
