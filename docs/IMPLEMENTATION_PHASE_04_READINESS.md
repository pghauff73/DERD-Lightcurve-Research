# Phase 04 readiness implementation

Phase 04 begins before any new model fit. Its first task is to prove that the candidate population, source files, exposure history, and prospective role assignment satisfy the frozen contract.

## Implemented gates

1. **Population contract**: ten strata, 100 development stars, and 50 sealed stars.
2. **Data-quality gate**: at least 50 clean observations and 10 occupied bins in a 12-bin phase audit.
3. **Provenance gate**: every candidate package has a SHA-256 value, authority, locator, and reuse basis.
4. **Exposure gate**: any Phase-01, Phase-02, or Phase-03 star is development-only forever.
5. **Prospective seal**: roles are assigned only after all prior gates pass and are linked to the candidate manifest, contract, analysis plan, and code manifest.
6. **Evaluation guard**: a development run aborts if a sealed star identity is present.

## Commands

Audit and seal a qualifying population:

```bash
python experiments/prepare_phase04_population.py candidate.csv \
  --contract data/manifests/phase04_population_contract_v1.json \
  --analysis-plan research/preregistration/phase04_analysis_plan.json \
  --data-root data
```

Verify the role seal and linked artifacts:

```bash
python experiments/verify_phase04_population.py \
  research/sealed/phase04/phase04_role_manifest.json \
  research/sealed/phase04/phase04_role_manifest.seal.json \
  --candidate-manifest candidate.csv \
  --contract data/manifests/phase04_population_contract_v1.json \
  --analysis-plan research/preregistration/phase04_analysis_plan.json \
  --code-manifest research/CODE_MANIFEST_SHA256.txt
```

Guard a proposed development evaluation manifest:

```bash
python experiments/guard_phase04_evaluation.py \
  research/sealed/phase04/phase04_role_manifest.json \
  development_evaluation.csv
```

## Present boundary

The current 20 Cepheid excerpts are an exposed engineering population. The included `phase04_current_pilot_ineligible.csv` is intentionally audited as a failing fixture. It must never be promoted into the pristine holdout.
