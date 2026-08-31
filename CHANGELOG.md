# Changelog

## 2.1.0 - Phase 21

- Corrected the legacy-to-current Delta Scuti identity relation to a two-hop exact OGLE-III field-ID crosswalk.
- Promoted authoritative row-level metadata locks for three of five frozen Delta Scuti identities.
- Retained two unresolved identities without numeric-suffix or positional inference.
- Added source-pack import, complete-cohort execution, period-coordinate correction, denominator firewall, and 16 additional tests.
- Kept C17, physical mechanism, transparent-shell, and shell-mass promotion gates closed.

## DERD v1.7, Phase 17 external-analysis anchor, 2026-08-19

### Added

- a frozen peer-reviewed OGLE V-band Fourier anchor for `OGLE-LMC-CEP-0002`;
- weighted simultaneous cosine-coordinate reconstruction from a provenance-verified 33-row V-band mirror;
- deterministic 60-percent subsample bootstrap covariance with period refitting;
- joint Mahalanobis and marginal-z consistency gates;
- explicit analysis-group, observing-source, byte-identity, and source-completeness dimensions;
- an external-analysis consistency edge in the reproducibility graph without denominator inflation;
- Phase-17 claims C79-C84, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- the four local Fourier coordinates are jointly consistent with the external published coordinates;
- the joint p-value is approximately `0.777354`, and the maximum absolute marginal z is approximately `1.27549`;
- the local mirror has 33 observations and does not satisfy the publication's minimum-50 input rule;
- exact publication source bytes are unknown and both analyses use the OGLE survey family;
- the edge is classified as `EXTERNAL_ANALYSIS_CONSISTENT_PARTIAL_SOURCE_OVERLAP`;
- the external independent astrophysical replication count remains zero;
- the astronomical denominator remains five and population outputs remain suppressed.

### Scope

Phase 17 validates Fourier-coordinate transport and external methodological consistency. It does not promote C17 or certify a physical mechanism, transparent shell, shell prevalence, or shell mass.


## DERD v1.6, Phase 16 cross-version reproducibility graph, 2026-08-19

### Added

- a sealed cross-version graph linking astronomical objects to all retained analysis-version nodes;
- exact-replay, configuration-sensitive-drift, single-version, and external-independent-replication classifications;
- a one-object-one-denominator multiplicity guard;
- Phase-16 claims C75-C78, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- five astronomical objects are represented by nine analysis-version nodes;
- three same-source, same-configuration edges replay exactly;
- one same-source edge exhibits configuration-sensitive scientific drift;
- one object has only a single analysis version;
- four duplicate denominator increments are prevented;
- no external independent astrophysical replication is present;
- population outputs remain suppressed.

### Scope

Phase 16 establishes computational replay structure and evidence multiplicity. It does not promote C17 or certify a physical mechanism, transparent shell, shell prevalence, or shell mass.

## DERD v1.5, Phase 15 archival lineage promotion, 2026-08-19

### Added

- digest-bound promotion of a previously source-verified Phase-08 target without raw-byte redistribution;
- a Phase-07 versus Phase-08 same-source lineage audit;
- explicit configuration-sensitive-drift classification;
- cumulative-ledger growth from four to five astronomical objects;
- Phase-15 claims C71-C74, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- `OGLE-LMC-CEP-0010` passes frozen source and archived-artifact checks;
- Phase-07 and Phase-08 share the same source coordinates but differ in coefficients, SNR values, score, threshold, evidence stage, and disposition;
- those versions are retained separately but contribute only one astronomical denominator record;
- cumulative coverage reaches three Cepheids, two RR Lyrae stars, and zero Delta Scuti stars;
- all family and population outputs remain suppressed.

### Scope

Phase 15 advances archival provenance and configuration sensitivity. It does not treat software lineage as independent astronomical replication and does not promote any physical shell claim.

## DERD v1.4, Phase 14 period-coordinate robustness ledger, 2026-08-18

### Added

- result-blind acquisition of the next claim-grade Phase-08 target absent from the Phase-13 ledger;
- exact Phase-08 scientific and harmonic-exchange replay for `OGLE-LMC-CEP-0002`;
- generic phase-dispersion period refinement independent of DERD compatibility;
- a narrow 101-point period-coordinate surface carrying phase dispersion and temporal score;
- complete chronological stationarity audits at catalog and refined periods;
- a separately hashed period-coordinate sidecar bound to the fourth cumulative evidence record;
- Phase-14 claims C66-C70, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- `OGLE-LMC-CEP-0002` is freshly evaluated from 366 observations;
- its Phase-08 scientific record and harmonic exchange replay exactly;
- the base DERD score `2.572199` remains above threshold `2.094903`;
- h4 remains below the full-light-curve recovery SNR gate;
- phase dispersion improves at a relative period shift of `-2.0e-5`;
- the temporal score decreases only about 2.4% and remains above the independently calibrated threshold at both periods;
- the coordinate classification is `TEMPORAL_STATIONARITY_FAILURE_ROBUST_TO_PERIOD_REFINEMENT`;
- the cumulative ledger grows from three to four objects;
- all family and population outputs remain suppressed.

### Scope

Phase 14 tests target-level waveform replay, signed-harmonic temporal stability, and period-coordinate robustness. It does not promote C17 or certify an internal mechanism, transparent shell, shell prevalence, or mass claim.

## DERD v1.3, Phase 13 temporal replication ledger, 2026-08-18

### Added

- result-blind acquisition ranking from frozen Phase-08 evidence;
- source import restricted to the highest-ranked eligible identity;
- exact Phase-08 scientific and harmonic-exchange replay for the new target;
- three equal-count chronological harmonic fits at a common period and epoch;
- covariance-aware pairwise h1-h4 temporal Wald tests;
- actual-cadence stationary bootstrap and controlled h2-h4 drift-severity calibration;
- a separately hashed temporal sidecar bound to the cumulative evidence record;
- Phase-13 claims C61-C65, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- `OGLE-LMC-RRLYR-00004` is freshly evaluated from 360 observations;
- its Phase-08 scientific record and harmonic exchange replay exactly;
- the base DERD score `2.016039` remains above threshold `1.871738`;
- h4 remains below the full-light-curve recovery SNR gate;
- three chronological blocks of 120 observations pass quality gates but do not all measure h1-h4 above SNR 3;
- the maximum temporal score `3.432654` exceeds the stationary threshold `2.915102`;
- controlled drift is first detected with sustained frozen performance at severity `0.75`;
- the cumulative ledger grows from two to three objects;
- all family and population outputs remain suppressed.

### Scope

Phase 13 tests target-level waveform replay and signed-harmonic temporal stability. It does not promote C17 or certify an internal mechanism, transparent shell, shell prevalence, or mass claim.

## DERD v1.2, Phase 12 cumulative replay ledger, 2026-08-18

### Added

- a cryptographically chained cumulative target-evidence ledger;
- verification of prior input-lock, result, and harmonic-exchange digests;
- execution of only newly unlocked targets absent from the cumulative ledger;
- hard rejection of conflicting duplicate records and tampered artifacts;
- deterministic cross-phase scientific replay auditing with a narrow transport-metadata allowance;
- Phase-12 claims C57-C60, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- one prior Cepheid record and one new RR Lyrae record form a two-target cumulative ledger;
- `OGLE-LMC-RRLYR-00001` is freshly evaluated from 332 observations;
- all four recovery harmonics pass SNR 3, but no two forecast harmonics pass SNR 2;
- the target DERD score `2.651028` remains above threshold `2.144635`;
- the fresh scientific projection and harmonic exchange reproduce the Phase-08 record exactly;
- thirteen target records and five authoritative Delta Scuti metadata locks remain pending;
- all family-level and population outputs remain suppressed.

### Scope

Phase 12 proves cumulative evidence retention and deterministic scientific replay. It does not promote C17 or certify an internal mechanism, transparent shell, shell prevalence, or mass claim.

## DERD v1.1, Phase 11 progressive evidence unlock, 2026-08-18

### Added

- progressive rights-reviewed source-pack import;
- target-level execution as soon as metadata and source locks pass;
- input-lock, result and harmonic-exchange SHA-256 bindings;
- a complete-denominator firewall for family fractions and Wilson intervals;
- Phase-11 claims C54-C56, OURD, IURMv1.1.1, EDOv1, tests, tables and figures.

### Evidence result

- one of fifteen raw source locks is verified;
- `OGLE-LMC-CEP-0004` is freshly evaluated from 367 observations;
- h3 and h4 remain below the frozen recovery-harmonic SNR threshold;
- the target-specific DERD score is above its compatibility threshold;
- fourteen source locks and five authoritative Delta Scuti metadata locks remain pending;
- all family-level outputs remain suppressed.

### Scope

Phase 11 unlocks target-level evidence without opening the population gate. C17 and all physical mechanism, transparent-shell and mass claims remain unpromoted.

## DERD v1.0, Phase 10 authoritative metadata and source lock, 2026-08-18

### Added

- sealed OGLE-IV/VizieR LMC Delta Scuti catalogue contract;
- fixed-width identity and parameter parsers;
- exact current-ID and explicit OGLE-III crosswalk resolution;
- row, catalogue-file, and canonical metadata-lock SHA-256 values;
- a single-mode radial-order restraint;
- rights-aware catalogue and photometry acquisition receipts;
- optional complete-cohort execution and family Wilson intervals;
- Phase-10 claims C48-C53, OURD, IURMv1.1.1, EDOv1, tests, tables, and figures.

### Evidence result

- protocol seal, catalogue contract, and exact 5+5+5 structure pass;
- ten of fifteen targets have claim-grade metadata;
- zero of five Delta Scuti metadata locks are promoted because authoritative catalogue bytes are absent;
- zero of fifteen raw sources are replay-ready in the release runtime;
- five prior object records remain cryptographically verified;
- primary family outputs remain suppressed.

### Scope

Phase 10 proves the input-lock and abstention machinery. It does not complete the astronomical cohort, promote C17, or certify an internal mechanism, transparent shell, or mass claim.

## DERD v0.9, Phase 09 claim-grade multi-family development cohort, 2026-08-17

### Added

- exact 5+5+5 exposed-development cohort declaration;
- claim-grade period, mode, and identity provenance gates;
- source acquisition receipts bound to the frozen cohort manifest;
- byte-count, observation-count, Git blob SHA-1, and SHA-256 replay checks;
- cryptographic reuse audit for five inherited Phase-08 object records;
- complete-cohort suppression of family-level fractions;
- Wilson interval aggregation for a future fully executed cohort;
- Phase-09 OURD, IURMv1.1.1, EDOv1, claims, tests, tables, and figures.

### Evidence result

- the protocol seal and exact 5+5+5 structure pass;
- five inherited object records pass their frozen artifact checks;
- the five selected Delta Scuti metadata records fail the claim-grade period, mode, and identity gates;
- no raw source file is bundled or replay-ready in the current package;
- the runtime retrieval attempt timed out before accepting any source bytes;
- primary family fractions remain suppressed.

### Scope

This release implements the Phase-09 gate but does not claim a completed astronomical cohort. C17 remains open and unpromoted. Internal mechanism, transparent-shell, and mass gates remain locked.

## DERD v0.8, Phase 08 multi-family raw cohort, 2026-08-15

### Added

- six byte-verified exposed development objects across classical Cepheid, RR Lyrae, and Delta Scuti families;
- a common lossless eight-harmonic, target-specific cadence, covariance-aware gate;
- independent deterministic calibration coordinates per object;
- period-provenance, recovery-harmonic, forecast-harmonic, structural, calibration, and stability stages;
- separation of source-byte completeness from conservative uncertainty cleaning;
- a deterministic acquisition queue and a sealed Phase-09 development protocol;
- six harmonic-exchange records, four cohort tables, four figures, and Phase-08 claims C39-C43.

### Evidence result

- 2,138 raw observations and 2,135 retained observations;
- one object reached the forecast-harmonic stage;
- no object measured at least two forecast harmonics above the frozen SNR threshold;
- no nominal candidate passed every DERD structural constraint;
- no object qualified, and C17 remains unpromoted.

### Scope

Phase 08 is exposed development evidence only. It does not estimate a population prevalence and does not certify internal Keplerian motion, a transparent shell, or shell mass.

## DERD v0.7, Phase 07 raw-photometry harmonic forecast gate, 2026-08-15

### Added

- exact Git blob and SHA-256 verification for a complete exposed-development mirror source;
- acknowledgement-gated third-party source retrieval without bundling raw bytes;
- simultaneous weighted signed eight-harmonic extraction from irregular photometry;
- explicit intercept, HC3 full coefficient covariance, and covariance ordering in the exchange record;
- generic harmonic period profiling independent of the DERD recurrence score;
- actual-cadence synthetic threshold calibration and covariance-aware recurrence propagation;
- an integrated source, coverage, conditioning, SNR, structure, score, and uncertainty gate;
- a sustained MVHE promotion rule and claims C34 through C38.

### Evidence result

- `OGLE-LMC-CEP-0010` supplied 372 observations and a well-conditioned eight-harmonic fit;
- all four recovery harmonics passed SNR 3, while no h5-h8 forecast harmonic passed SNR 2;
- the nominal score `1.905220` exceeded threshold `1.470082`;
- only `0.125977` of covariance draws fell below threshold and structural pass fraction was `0.004150`;
- actual-cadence holdout ROC AUC was `0.796277`, below the frozen `0.80` gate;
- the integrated decision was `ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE`;
- the first sustained actual-cadence acquisition pass was `240` observations.

### Scope

This is one exposed first-overtone Cepheid and a target-specific synthetic cadence study. It does not promote C17 or any physical core-shell, transparent-shell, or mass claim.

## DERD v0.6, Phase 06 harmonic phase-convention gate, 2026-08-15

### Added

- a formal audit of the frozen `arctan(b/a)` phase convention;
- quadrant-loss, missing-fundamental-phase, and epoch-invariance tests;
- explicit enumeration of compatible legacy coefficient branches;
- a recurrence overidentification degree calculator;
- a frozen-source three-block reproducibility invariant;
- compact Cepheid, RR Lyrae, and Delta Scuti provenance samples;
- the lossless `DERD-HARMONIC-EXCHANGE-1.0` schema;
- a deterministic development/holdout information-preservation experiment;
- 14 additional tests and claims C29 through C33.

### Evidence result

- canonical signed coefficients remained epoch invariant to numerical precision;
- treating the legacy relative phases as absolute reduced held-out ROC AUC to `0.6536`;
- all three compact catalog samples violated the exact frozen source's required repeated-block invariant;
- the legacy rows are blocked from exact complex-harmonic proof, while remaining available for explicitly ambiguous exploratory triage.

### Scope

The result rejects an information-losing and incompletely reproduced catalog transport format as a proof substrate. It does not reject DERD and does not promote a physical stellar mechanism.

## DERD v0.5, Phase 05 harmonic screen and minimum viable evidence, 2026-08-08

### Added

- algebraic two-root recurrence and residue-constraint screening;
- exact recovery tests under arbitrary observational epoch and real scale;
- weighted complex Fourier extraction with coefficient uncertainty and SNR;
- catalog amplitude/phase adapters with explicit sine/cosine conventions;
- cadence-aware generic-Fourier and phase-scrambled null controls;
- Bayesian-bootstrap acquisition ranking for the exposed 20-star pilot;
- an IURMv1.1.1 observation-count sweep defining an optimistic minimum viable
  harmonic-evidence target.

### Evidence result

- the current 24-point cadence failed discrimination: holdout ROC AUC `0.4764`;
- no current pilot star passed score, SNR, conditioning, and stability together;
- the first tested uniform-phase count passing all frozen robustness gates was `160`
  observations per star.

### Scope

This is a candidate-triage and acquisition-design release. It does not promote C17 or any
physical core-shell, transparent-shell, or mass claim.

## DERD v0.4, Phase 04 readiness and Phase 03 release closure, 2026-08-08

### Added

- self-contained reconstruction of the Phase-03 repository additions;
- direct tests for circular cross-validation, periodic kernel ridge, uncertainty calibration,
  paired statistics, cryptographic sealing, and Phase-04 population qualification;
- a frozen ten-stratum Phase-04 population contract requiring 100 development and 50
  pristine sealed stars;
- source-file SHA-256, authority, reuse-basis, observation-count, phase-coverage, and
  prior-exposure gates before role assignment;
- a sealed analysis plan linked cryptographically to the candidate manifest, contract,
  code manifest, and deterministic role assignment;
- a guard that refuses any development evaluation containing a sealed star identity;
- separate code and full-release manifests to avoid artifact-sealing circularity.

### Verification

- 113 unit and integration tests pass;
- the current 20-star pilot is correctly rejected as a Phase-04 candidate because it is
  exposed, sparse, phase-incomplete, single-family, and below all population minima;
- a synthetic governance-only population passes the full audit, seal, verification, and
  development guard while the deliberate sealed-star probe is blocked.

### Scope

Phase 04 is ready to receive lawful, complete, multi-class data. No new astrophysical
performance claim is promoted by this readiness release.

## DERD v0.2, Phase 02 observational shakedown, 2026-08-07

### Added

- immutable observational `LightCurve` model and OGLE three-column parser;
- magnitude-to-relative-flux conversion with propagated uncertainty;
- deterministic circular phase-block holdout and star-identity role manifests;
- training-only scaling, epoch estimation, period verification, and inverse-variance weights;
- held-out DERD-G and DERD-K prediction with local identifiability diagnostics;
- Fourier order-two and training-only stability-gated BIC baselines;
- RMSE, weighted RMSE, MAE, maximum error, residual autocorrelation, and Durbin-Watson metrics;
- deterministic bootstrap spot checks;
- 20-target LMC Cepheid engineering capsule with frozen provenance and SHA-256 values;
- EH Lib reproduction contract, physical-claim gates, and shell optical-depth feasibility code;
- 45 additional tests, bringing the complete gate to 77 passing tests.

### Evidence result

- best DERD lower held-out RMSE than the best primary Fourier baseline on 12 of 20 targets;
- best Fourier lower or tied on 8 of 20 targets;
- median best-DERD minus best-Fourier RMSE: `-0.005018`;
- one local DERD-K fit crossed the provisional `1e5` condition-number warning gate;
- raw ungated BIC instability was preserved as a contradiction artifact and corrected using
  training-only condition and prediction-span gates.

### Scope

This release completes an engineering shakedown only. It does not promote C17 to a
confirmatory result and does not certify internal Keplerian motion, a universal transparent
shell, or shell mass.

## DERD v0.1, Phase 01 mathematical and software foundation, 2026-08-07

### Added

- faithful historical paper capsule;
- frozen GitHub provenance capsule;
- corrected DERD-G and DERD-K models;
- continuous phase control and validated four-parameter schema;
- direct nonlinear fitting, Fourier baseline, formal normalization tests, harmonic recurrence
  tests, and IURMv1.1.1 one-dimension sweeps;
- 32-test initial verification gate.

## DERD v1.8, Phase 18 exact external-input reconstruction, 2026-08-24

### Added

- authoritative current OGLE-III and OGLE-IV V-band source manifests for `OGLE-LMC-CEP-0002`;
- a verified 65-observation chronological merge satisfying the external publication's minimum count;
- a corrected external-method contract separating K2 bootstrap uncertainty from OGLE `curve_fit` covariance;
- an 18-variant IURMv1.1.1 lattice over source scope, weighting, and fixed/free period;
- curve-fit covariance propagation and joint published-vector consistency tests;
- source retriever, execution runner, claims C85-C90, OURD graph, EDOv1 contradiction record, and new tests.

### Result

The frozen primary merged-source reconstruction is jointly consistent with the published four-coordinate Fourier vector. All six merged-source variants pass the joint and marginal consistency gates. Exact publication bytes and exact code replay remain unavailable.

### Scope

No astronomical denominator item or independent astrophysical replication edge is added. C17 and all physical shell and mechanism gates remain closed.

## DERD v1.9, Phase 19 blind external-group replay kit, 2026-08-24

### Added

- seven opaque external-replication tasks;
- a wheel-based public kit with self-verification and container recipe;
- a separately packaged private answer key and HMAC-SHA256 commitment;
- submission self-hashing, environment capture, numerical verification, and operator-independence gates;
- an internal isolated-process control that reproduces all seven scientific projections;
- claims C91-C96 and Phase-19 OURD, IURMv1.1.1, EDOv1, graph, and ledger objects.

### Result

The public kit is ready and the internal clean-room control passed. No external research-group submission has yet been verified, so no external computational or independent astrophysical replication edge is added.

### Scope

Phase 19 implements the external-replication instrument. It does not itself constitute external replication and does not promote C17 or any physical transparent-shell or mass claim.

## 2.0.0 - Phase 20

- Added covariance-aware I/V passband invariance tests.
- Added shared-component versus DERD projection comparison.
- Added ten-family synthetic mechanism tournament.
- Added formal and numerical gravity-only periodic-motion falsifier.
