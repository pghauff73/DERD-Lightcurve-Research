# Phase-19 implementation handoff

## Public operator package

Share only `DERD_Phase19_External_Replication_Kit.zip` with an external operator.

Do not share `DERD_Phase19_Private_Evaluator.zip` until the operator has returned and frozen the SHA-256 of `submission.json`.

## External execution sequence

1. Operator extracts the public kit.
2. Operator runs `python verify_kit.py`.
3. Operator installs the wheel in a controlled environment.
4. Operator runs all seven tasks with `derd.phase19_external_runner`.
5. Operator sends the submission JSON, its SHA-256, environment manifest, and signed independence statement.
6. Custodian runs the private evaluator.
7. Only a passing, independence-qualified submission may add an external computational-replication edge.

## Current state

- public kit sealed: yes;
- private evaluator separated: yes;
- local clean-room seven-task replay: passed;
- external submission received: no;
- external computational edge: not added;
- independent observing-source edge: not added;
- C17: open, not promoted.
