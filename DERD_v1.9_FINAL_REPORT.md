# DERD v1.9 Phase-19 Final Report

## Blind External Computational-Replication Kit

**Release:** `DERD-v1.9-phase19-external-group-replay-kit`  
**Decision:** `PHASE19_EXTERNAL_REPLICATION_KIT_SEALED_LOCAL_CLEANROOM_CONTROL_PASSED_EXTERNAL_GROUP_SUBMISSION_PENDING`  
**Classification:** `EXTERNAL_REPLICATION_READY_INTERNAL_CLEANROOM_VALIDATED_NO_EXTERNAL_REPLICATION_EDGE_YET`  
**Certificate boundary:** `NOT_A_PHYSICAL_CLAIM_CERTIFICATE`

## 1. Phase objective

Phase 19 implements the first sealed package intended for execution by a research operator outside the DERD implementation lineage. Its purpose is to test whether the frozen DERD computational workflow can be transported to an independently controlled environment without revealing the expected scientific outputs in advance.

The phase tests computational reproducibility only. It does not introduce an independent observing source, add a new astronomical object, establish population performance, identify a unique stellar mechanism, demonstrate a transparent exterior shell, or constrain shell mass.

## 2. Public and private package separation

The release is divided into two cryptographically related artifacts.

### Public operator kit

The public kit contains:

- the frozen DERD 1.9.0 wheel;
- seven opaque tasks;
- public task metadata and input hashes;
- a checksum verifier;
- an external task runner;
- an operator attestation and environment-recording contract;
- a submission self-hash contract.

It contains no answer key, no HMAC secret, no private verifier, and no complete third-party stellar photometry.

### Private evaluator

The private evaluator contains:

- the seven-task answer key;
- the HMAC commitment key;
- the submission verifier;
- its own checksum manifest and withholding instructions.

The evaluator must remain undisclosed until the external operator has frozen and transmitted the SHA-256 of `submission.json`.

The public answer commitment is:

```text
8512a7041f7f665db83bd458824a9775d43115f9df3d25501a948b7506292988
```

## 3. Blind task design

The public kit contains seven tasks:

| Task class | Count | Purpose |
|---|---:|---|
| Synthetic photometry | 4 | Test deterministic light-curve ingestion, signed harmonic extraction, recurrence screening, covariance propagation, and direct DERD fitting |
| Observational harmonic exchange | 3 | Test transport and evaluation of lossless signed harmonic vectors and covariance without redistributing raw third-party photometry |
| **Total** | **7** | Frozen external computational-replication workload |

The observational controls are derived from exposed-development records for three previously analysed objects. Their astronomical identities and source locators are withheld from the public task interface. These tasks test computational transport of the existing harmonic evidence system, not independent raw-photometry extraction.

## 4. Frozen numerical gate

Every external submission must satisfy all of the following:

1. the task-manifest and input-file hashes verify;
2. the operator runs in an environment under their control;
3. the private evaluator was not available before submission;
4. the submission contains all seven task outputs;
5. the submission self-hash verifies;
6. the environment manifest and operator attestation are present;
7. every committed scientific projection agrees within the frozen tolerance:

```text
absolute tolerance = 2.0e-7
relative tolerance = 2.0e-6
```

A numerical pass is necessary but not sufficient for an external replication edge. Independence must also be documented.

## 5. Local clean-room control

The public kit was extracted and executed in an isolated process using its packaged wheel. The control:

- verified every public checksum;
- installed the wheel in a separate environment;
- ran all seven opaque tasks;
- generated a self-hashed submission;
- verified the HMAC answer commitment;
- reproduced every committed scientific projection within tolerance.

| Control dimension | Result |
|---|---:|
| Public tasks executed | 7 of 7 |
| Task projections passed | 7 of 7 |
| Public checksum verification | Passed |
| Submission self-hash | Passed |
| HMAC commitment | Passed |
| Operator attestation present | Yes |
| Counts as external computational replication | **No** |
| Counts as independent astrophysical replication | **No** |

The local submission SHA-256 is:

```text
b3401df5287b0cbc829e2f0b256b82373826b830a9b8aaeedfd1639484a4ab30
```

This validates the kit and evaluator. Because the operator and execution remain within the implementation lineage, it does not close the external gate.

## 6. Reproducibility-graph state

Phase 19 adds two non-denominator nodes:

- the sealed blind replication kit;
- the internal isolated-process control.

It adds one internal clean-room replay edge, explicitly marked as non-external.

| Evidence dimension | Current value |
|---|---:|
| Unique astronomical objects | 5 |
| Verified external submissions | 0 |
| External computational-replication edges | 0 |
| Independent observing-source replications | 0 |
| Independent astrophysical replications | 0 |
| Population outputs allowed | No |
| C17 promoted | No |

The astronomical denominator is unchanged. Seven tasks, two packages, and one internal replay do not create additional stars.

## 7. OURD, IURMv1.1.1, and EDOv1 implementation

### OURD

Phase 19 represents the public kit, private evaluator, answer commitment, task manifest, operator environment, submission, verification result, replication edge, astronomical denominator, and claim boundary as separate typed objects.

### IURMv1.1.1

The intended external intervention varies one dimension:

```text
analysis operator:
internal implementation lineage -> independent external operator
```

The wheel, public inputs, task manifest, tolerances, answer commitment, result schema, and evaluator remain fixed.

### EDOv1

The evidence record retains all limiting facts:

- no external operator has submitted results;
- no independent observing source is included;
- the observational tasks begin from derived harmonic-exchange records;
- the local clean-room control is internal;
- C17 remains open;
- all mechanism, transparent-shell, prevalence, and mass claims remain locked.

## 8. Claims advanced

| Claim | Status |
|---|---|
| C91: a public seven-task kit can be constructed without disclosing the answer key | Verified |
| C92: the public and private packages are bound by a frozen HMAC-SHA256 commitment | Verified |
| C93: all public inputs and package files are checksum-verifiable | Verified |
| C94: an isolated internal process reproduces all committed projections | Verified |
| C95: the internal control does not qualify as external replication | Enforced |
| C96: Phase 19 does not change the astronomical denominator or promote C17 | Enforced |
| C17: DERD is competitive across pulsator populations | Open, not promoted |

## 9. Physical-claim boundary

The source paper defines a normalized four-parameter waveform based on the difference between two out-of-phase elliptical-radius functions. Its printed implementation normalizes both component-radius sequences and the final resultant and states that mass is factored out. The radial core-shell interpretation and transparent outer-shell proposition are later physical hypotheses.

Phase 19 therefore tests only computational portability of the waveform-analysis system. It cannot certify:

```text
UNIQUE_INTERNAL_MECHANISM
LITERAL_INTERNAL_KEPLERIAN_MOTION
UNIVERSAL_TRANSPARENT_OUTER_SHELL
SHELL_PREVALENCE
SHELL_MASS_OR_MASS_FRACTION
```

## 10. Verification summary

| Release check | Result |
|---|---:|
| Unit and integration tests | 248 passed |
| Python compilation | Passed |
| JSON documents parsed | 319 |
| Code-manifest entries | 307 verified |
| Repository-manifest entries | 999 verified |
| Bundle-checksum entries | 1,000 verified |
| Clean incremental-patch application | Passed |
| Tests after clean patch application | 248 passed |
| Tests after ZIP extraction | 248 passed |
| Public-kit checksums | Passed |
| Private material in public kit | 0 files |
| Complete raw third-party photometry in release bundle | 0 files |
| ZIP integrity | Passed |

## 11. External operator sequence

The external group should:

1. receive only the public kit;
2. verify `KIT_SHA256SUMS.txt`;
3. create an environment it controls;
4. install the packaged wheel;
5. run all seven tasks;
6. freeze the resulting `submission.json` SHA-256;
7. transmit the submission, hash, environment manifest, and signed independence statement;
8. allow the custodian to run the private evaluator only after the submission hash is frozen.

Only a passing, independence-qualified submission may add the first external computational-replication edge.

## 12. Current conclusion

Phase 19 is implemented, sealed, locally validated, patch-replayable, and ready for an external operator.

The scientific promotion gate remains open because no independent group has executed the package. The correct status is therefore:

```text
REPLICATION KIT READY
INTERNAL CLEAN-ROOM CONTROL PASSED
EXTERNAL SUBMISSION PENDING
NO EXTERNAL REPLICATION EDGE
NO POPULATION OR PHYSICAL CLAIM PROMOTION
```
