# Phase 19: blind external computational-replication kit

## Purpose

Phase 19 freezes a portable DERD challenge so an operator outside the implementation team can execute the same signed-harmonic, recurrence, covariance-propagation, and direct-fit workflow without receiving expected answers in advance.

## Public/private split

The public kit contains:

- four opaque synthetic photometry tasks;
- three blinded observational harmonic-exchange tasks;
- the `derd-lightcurve` 1.9.0 wheel;
- a checksum verifier;
- a container recipe;
- exact task and protocol seals;
- a submission schema.

The private evaluator contains:

- the expected scientific projections;
- the hidden control roles;
- the HMAC commitment key;
- the submission verifier.

The private evaluator must not be supplied to an external operator until the operator's submission SHA-256 has been frozen.

## Frozen external gate

A computational-replication edge may be added only when:

1. the operator is outside the implementation team;
2. the operator controls the execution environment;
3. the operator attests that the answer key was unavailable before submission;
4. the public kit verifies cleanly;
5. all seven task projections reproduce within the frozen absolute and relative tolerance;
6. the submission self-hash and environment manifest verify.

A passing external run does not increment the astronomical denominator, establish an independent observing source, or prove a stellar mechanism.

## Local clean-room control

A separate local virtual environment installed the wheel from the public kit and reproduced all seven projections. This validates packaging and portability only. It remains internal to the implementation lineage and is not an external replication.

## Commands

External operator:

```bash
python verify_kit.py
python -m derd.phase19_external_runner \
  --kit . \
  --output submission.json \
  --operator-id OPERATOR \
  --organization ORGANIZATION \
  --wheel software/derd_lightcurve-1.9.0-py3-none-any.whl
sha256sum submission.json
```

Private evaluation, only after the submission hash is frozen:

```bash
python verify_phase19_submission.py submission.json \
  --public-protocol /path/to/phase19_protocol.json \
  --output verification.json
```

## Claim boundary

Phase 19 concerns computational reproducibility. It does not identify literal internal Keplerian motion, a universal transparent shell, shell prevalence, or shell mass.
