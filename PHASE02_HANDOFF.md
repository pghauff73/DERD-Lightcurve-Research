# DERD v0.2 Phase-02 implementation handoff

## Gate status

`PHASE02_ENGINEERING_SHAKEDOWN_COMPLETE_C17_NOT_PROMOTED`

The complete software gate contains 77 passing tests. The observational run contains 20 LMC
classical Cepheids, balanced between 10 fundamental-mode and 10 first-overtone targets,
with 24 mirrored I-band observations per target. The capsule contains 480 observations,
380 training points, and 100 held-out points.

The best DERD model beat the best primary Fourier baseline on 12 of 20 targets. Fourier won
or tied on 8. The median best-DERD minus best-Fourier held-out RMSE was `-0.005018`. This
mixed result supports continued study but not promotion of the broad descriptor claim.

## Run the complete test gate

```bash
python -m pip install -e '.[test,research]'
python -m pytest
```

## Reproduce Phase 01

```bash
python experiments/run_phase01.py --output-directory artifacts/phase01
```

## Reproduce the 20-star shakedown

```bash
python experiments/run_phase02.py \
  --output-directory artifacts/phase02 \
  --starts 4 \
  --max-function-evaluations 180 \
  --normalization-grid-size 512 \
  --peak-grid-size 256 \
  --period-grid-count 101 \
  --bootstrap-repetitions 3
```

## Fetch complete official OGLE files

The local shakedown uses 24-row executable excerpts. Complete the capsule with:

```bash
python experiments/fetch_complete_ogle.py \
  --manifest data/manifests/phase02_targets.csv \
  --destination data/official/ogle_lmc_cepheids/I \
  --band I \
  --acknowledge-ogle
```

This command records SHA-256 values and requires explicit acknowledgement of OGLE reuse
and citation obligations. The `data/official/` directory is intentionally ignored by Git.

## Inspect the primary outputs

- `artifacts/phase02/PHASE02_RESULT.md`
- `artifacts/phase02/phase02_summary.json`
- `artifacts/phase02/phase02_star_results.csv`
- `artifacts/phase02/details/`
- `artifacts/phase02/predictions/`
- `research/diagnostics/phase02_first_pass_raw_bic_summary.json`
- `research/eh_lib/EH_LIB_REPRODUCTION_CONTRACT.json`
- `research/MANIFEST_SHA256.txt`

## Findings requiring follow-up

- Four local period scans reached the edge of the provisional search window and require a
  wider scan on complete observations.
- `OGLE-LMC-CEP-0003` crossed the provisional `1e5` DERD-K condition-number warning gate.
- First-overtone results were approximately balanced, whereas the tiny fundamental-mode
  subset favoured DERD more often. This is exploratory and not a population conclusion.
- Raw high-order BIC selection extrapolated catastrophically on sparse phase blocks. The
  contradiction is retained, and the primary selector now uses training-only stability gates.
- EH Lib remains blocked until the exact observation identity and the original `99.6%`
  metric are supplied and frozen.

## Scientific stop rule

Do not use this phase to claim a universal Fourier replacement, internal Keplerian stellar
orbits, a universal transparent shell, or a shell mass. Complete-data, cross-class,
independent-observable, and sealed-holdout gates remain locked.

## Verify capsule integrity

```bash
python experiments/build_manifest.py
python experiments/verify_manifest.py
```

The manifest excludes itself, Git metadata, Python caches, virtual environments, and build
outputs. A verification failure is a hard reproducibility stop.
