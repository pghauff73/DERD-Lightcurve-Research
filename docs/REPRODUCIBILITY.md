# Reproducibility

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,research]'
```

## Unit and mathematical tests

```bash
python -m pytest
```

## Historical audit

```bash
derd audit-historical --output artifacts/phase01/historical_audit.json
```

## Generate a corrected curve

```bash
derd generate \
  --e1 0.10 --e2 0.746 \
  --amplitude-ratio 0.5016 --phase-ratio 0.92 \
  --time-law geometric --samples 512 \
  --output artifacts/example_curve.csv
```

## Run a one-active-dimension experiment

```bash
derd sweep \
  --e1 0.20 --e2 0.70 \
  --amplitude-ratio 0.50 --phase-ratio 0.30 \
  --active-dimension e1 --start 0.0 --stop 0.9 --count 10 \
  --experiment-id IURM-DERD-E1-001 \
  --output-directory artifacts/phase01
```

## Rebuild the complete phase-01 evidence output

```bash
python experiments/run_phase01.py --output-directory artifacts/phase01
```

All experiment seeds and grids are fixed in code. The intended upstream base is recorded
in `research/edov1/evidence_manifest.json`.
