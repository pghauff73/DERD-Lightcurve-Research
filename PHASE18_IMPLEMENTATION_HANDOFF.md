# Phase 18 implementation handoff

## Run

Retrieve and verify both official source files:

```bash
python experiments/fetch_phase18_external_input.py \
  --root . \
  --acknowledge-ogle-citation
```

Execute the reconstruction:

```bash
PYTHONPATH=src:. python experiments/run_phase18.py \
  --root . \
  --ogleiii data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIII_V.dat \
  --ogleiv data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIV_V.dat
```

## Read first

- `artifacts/phase18/PHASE18_RESULT.md`
- `artifacts/phase18/phase18_summary.json`
- `artifacts/phase18/phase18_method_lattice.csv`
- `data/evidence/phase18_jurkovic2022_method_contract.json`
- `docs/IMPLEMENTATION_PHASE_18_EXACT_EXTERNAL_INPUT_RECONSTRUCTION.md`

## Evidence boundary

The release reconstructs the authoritative current OGLE-III plus OGLE-IV input scope and reproduces the published Fourier vector statistically. It does not claim exact publication byte identity or exact analysis-code replay, because neither was published. It adds no astronomical denominator item and no independent astrophysical replication edge.
