# DERD research implementation

This evidence capsule contains twenty-one gated tranches:

- **Phase 01:** historical-code audit, corrected DERD-G and DERD-K mathematics, normalization proofs, spectral tests, synthetic fitting, and IURMv1.1.1 sweeps;
- **Phase 02:** provenance-tracked Cepheid engineering shakedown with held-out phase blocks;
- **Phase 03:** nested model selection, nonlinear periodic baseline, uncertainty calibration, and paired promotion tests;
- **Phase 04 readiness:** ten-stratum population contract, integrity audit, role sealing, and sealed-evaluation guard;
- **Phase 05:** algebraic harmonic-recurrence screen and optimistic uniform-phase MVHE-160;
- **Phase 06:** phase-convention audit and lossless signed harmonic exchange;
- **Phase 07:** complete exposed-development photometry, h1-h8 extraction, covariance transport, actual-cadence calibration, and sustained MVHE-240;
- **Phase 08:** six-object multi-family cohort with stage-specific abstention;
- **Phase 09:** frozen 5+5+5 claim-grade development cohort and complete-denominator suppression;
- **Phase 10:** authoritative OGLE-IV/VizieR metadata contract, explicit OGLE-III crosswalks, row/file locks, and replayable source locks;
- **Phase 11:** progressive target-level evidence unlock with an unchanged fifteen-object denominator and a population-output firewall;
- **Phase 12:** cryptographically chained cumulative target ledger, deterministic cross-phase replay audit, and duplicate-conflict rejection;
- **Phase 13:** result-blind source prioritization, exact target replay, three-block temporal harmonic replication, actual-cadence drift calibration, and a separately sealed temporal sidecar;
- **Phase 14:** independent period-coordinate refinement and temporal-stationarity robustness;
- **Phase 15:** digest-bound archival target promotion and cross-configuration lineage classification;
- **Phase 16:** cross-version reproducibility graph and one-object-one-denominator multiplicity guard;
- **Phase 17:** peer-reviewed external Fourier-analysis anchor, joint uncertainty consistency audit, and source-independence classification.
- **Phase 18:** exact external OGLE-III/IV input reconstruction and method lattice;
- **Phase 19:** sealed blind external-group replication kit;
- **Phase 20:** multiband mechanism falsification and gravity-only theorem;
- **Phase 21:** exact two-hop Delta Scuti metadata unlock and frozen 15-object pilot firewall.

Install and verify:

```bash
python -m pip install -e '.[test,research]'
PYTHONPATH=src:. python -m pytest
PYTHONPATH=src:. python experiments/verify_manifest.py --manifest research/CODE_MANIFEST_SHA256.txt
PYTHONPATH=src:. python experiments/verify_manifest.py
```

Import the one target selected by the frozen Phase-13 acquisition order:

```bash
PYTHONPATH=src:. python experiments/import_phase13_source_pack.py \
  --root . \
  --input-dir /path/to/source-pack \
  --acknowledge-ogle-attribution
```

Execute the fresh target, append it to the cumulative ledger, reproduce its inherited Phase-08 result, and run the temporal-replication audit:

```bash
PYTHONPATH=src:. python experiments/run_phase13.py \
  --root . \
  --receipt artifacts/phase13/phase13_source_acquisition_receipt.json \
  --output artifacts/phase13 \
  --execute-ready
```

The Phase-10 catalogue tools remain the route for authoritative Delta Scuti metadata locks. Earlier experiments remain available through `experiments/run_phase01.py` to `run_phase12.py` and the corresponding implementation documents.

Read first:

- [`docs/MODEL_SPECIFICATION.md`](docs/MODEL_SPECIFICATION.md)
- [`docs/IMPLEMENTATION_PHASE_13_TEMPORAL_REPLICATION_LEDGER.md`](docs/IMPLEMENTATION_PHASE_13_TEMPORAL_REPLICATION_LEDGER.md)
- [`artifacts/phase13/PHASE13_RESULT.md`](artifacts/phase13/PHASE13_RESULT.md)
- [`PHASE13_IMPLEMENTATION_HANDOFF.md`](PHASE13_IMPLEMENTATION_HANDOFF.md)
- [`DERD_v1.3_RELEASE_NOTES.md`](DERD_v1.3_RELEASE_NOTES.md)

This is a waveform-research and evidence system. It is not a certificate for literal internal Keplerian motion, a universal transparent shell, shell prevalence, or shell mass.



## Phase 15 and Phase 16

Run the archival lineage promotion and then construct the reproducibility graph:

```bash
PYTHONPATH=src:. python experiments/run_phase15.py --root .
PYTHONPATH=src:. python experiments/run_phase16.py --root .
```

Read first:

- `DERD_v1.6_RELEASE_NOTES.md`
- `PHASE16_IMPLEMENTATION_HANDOFF.md`
- `artifacts/phase16/PHASE16_RESULT.md`
- `artifacts/phase16/phase16_reproducibility_graph.json`
- `docs/IMPLEMENTATION_PHASE_16_REPRODUCIBILITY_GRAPH.md`

Phase 15 promotes one previously source-verified target without redistributing raw photometry. Phase 16 distinguishes exact software replay from configuration-sensitive drift and ensures that multiple analyses of one star do not inflate the astronomical denominator.


## Phase 17

Run the external Fourier-analysis anchor after retrieving or supplying the exact frozen V-band source:

```bash
python experiments/fetch_phase17_v_source.py --root . --acknowledge-attribution
PYTHONPATH=src:. python experiments/run_phase17.py \
  --root . \
  --source data/raw/phase17_external/OGLE-LMC-CEP-0002_V.dat
```

Read first:

- `DERD_v1.7_RELEASE_NOTES.md`
- `PHASE17_IMPLEMENTATION_HANDOFF.md`
- `artifacts/phase17/PHASE17_RESULT.md`
- `artifacts/phase17/phase17_external_analysis_audit.json`
- `docs/IMPLEMENTATION_PHASE_17_EXTERNAL_ANALYSIS_ANCHOR.md`

The external publication and local reanalysis create one methodological consistency edge. They do not create a new astronomical object or an independent observing-source replication.

## Phase 18

Retrieve the official current OGLE-III and OGLE-IV V-band files and verify their frozen digests:

```bash
python experiments/fetch_phase18_external_input.py \
  --root . \
  --acknowledge-ogle-citation
```

Run the 65-observation external-input reconstruction and method lattice:

```bash
PYTHONPATH=src:. python experiments/run_phase18.py \
  --root . \
  --ogleiii data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIII_V.dat \
  --ogleiv data/raw/phase18_external/OGLE-LMC-CEP-0002_OGLEIV_V.dat
```

Phase 18 establishes a publication-compatible input-scope and Fourier-vector reconstruction. It does not establish exact publication byte identity, code-identical replay, an independent observing source, or a physical transparent-shell claim.

## Phase 19

Build the blind public kit and separately withheld private evaluator:

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
PYTHONPATH=src:. python experiments/build_phase19_replication_kit.py \
  --root . \
  --wheel dist/derd_lightcurve-1.9.0-py3-none-any.whl \
  --public-dir /tmp/phase19-public \
  --private-dir /tmp/phase19-private \
  --public-zip /tmp/DERD_Phase19_External_Replication_Kit.zip \
  --private-zip /tmp/DERD_Phase19_Private_Evaluator.zip
```

An external operator receives only the public ZIP. The private evaluator remains withheld until the operator submission SHA-256 is frozen. A local clean-room replay validates packaging but cannot count as an external computational-replication edge.

## Phase 21

Verify the authoritative row receipt, import any rights-reviewed raw-source pack, and re-run readiness:

```bash
PYTHONPATH=src:. python experiments/import_phase21_catalog_rows.py --root .
PYTHONPATH=src:. python experiments/import_phase21_source_pack.py SOURCE_PACK --root . --acknowledge-rights-and-attribution
PYTHONPATH=src:. python experiments/run_phase21.py --root .
```

Execute the complete cohort only after all metadata and source gates pass:

```bash
PYTHONPATH=src:. python experiments/execute_phase21_cohort.py --root .
```

Phase 21 promotes three exact Delta Scuti metadata locks, retains two unresolved identities without guessing, and keeps all family-level outputs closed until the full denominator is complete.
