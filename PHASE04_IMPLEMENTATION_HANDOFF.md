# Phase 04 implementation handoff

## Entry points

Audit and seal a real candidate population only after all local source packages are present:

```bash
python experiments/prepare_phase04_population.py candidate.csv \
  --contract data/manifests/phase04_population_contract_v1.json \
  --analysis-plan research/preregistration/phase04_analysis_plan.json \
  --code-manifest research/CODE_MANIFEST_SHA256.txt \
  --data-root data
```

Verify the resulting role seal and linked artifacts:

```bash
python experiments/verify_phase04_population.py \
  research/sealed/phase04/phase04_role_manifest.json \
  research/sealed/phase04/phase04_role_manifest.seal.json \
  --candidate-manifest candidate.csv \
  --contract data/manifests/phase04_population_contract_v1.json \
  --analysis-plan research/preregistration/phase04_analysis_plan.json \
  --code-manifest research/CODE_MANIFEST_SHA256.txt
```

Guard every development evaluation manifest:

```bash
python experiments/guard_phase04_evaluation.py \
  research/sealed/phase04/phase04_role_manifest.json \
  development_evaluation.csv
```

## Data still required

A lawful candidate manifest must contain at least 15 qualifying stars in each of ten strata. Every star package requires at least 50 clean observations and 10 occupied bins in a 12-bin phase audit. Earlier Phase-02 and Phase-03 identities must remain development-only.

The next scientific execution begins only after the readiness output says:

```text
READY_FOR_PROSPECTIVE_SEAL
```

Until then, the system stops before fitting. That stop is an intended proof gate, not an implementation failure.
