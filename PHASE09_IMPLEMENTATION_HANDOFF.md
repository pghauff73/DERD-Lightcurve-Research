# Phase 09 Implementation Handoff

## Release identity

`DERD-v0.9-phase09-claim-grade-development-cohort`

## Run the preflight

```bash
cd derd-v0.9
python experiments/run_phase09.py --root .
```

Expected current decision:

```text
PHASE09_IMPLEMENTED_EXECUTION_BLOCKED_BY_METADATA_AND_SOURCE_GATES
```

## Inspect planned source retrieval

```bash
python experiments/fetch_phase09_sources.py \
  --root . \
  --dry-run
```

## Acquire source bytes locally

This operation requires explicit attribution acknowledgement:

```bash
python experiments/fetch_phase09_sources.py \
  --root . \
  --acknowledge-ogle-attribution \
  --continue-on-error
```

The script writes raw bytes under `data/raw/phase09_cohort/` only after checking byte count, Git blob SHA-1, and any already frozen SHA-256. It writes a separate acquisition receipt and does not mutate the frozen cohort manifest.

## Resolve the Delta Scuti metadata gate

Before scientific execution, replace the five unresolved Delta Scuti metadata coordinates with an authoritative, documented crosswalk that supplies:

- exact catalog identity;
- primary period;
- singlemode or multimode classification;
- source locator and provenance grade.

Do not overwrite the frozen cohort file. Create a new versioned manifest, record the transformation, and seal it before inspecting object scores.

## Execute the complete cohort

Only after preflight reports `cohort_execution_ready=true`:

```bash
python experiments/run_phase09.py \
  --root . \
  --execute-ready
```

The runner will then create all fifteen harmonic-exchange records and family-level fractions with Wilson intervals.

## Verify the release

```bash
python -m pytest -q
python -m compileall -q src experiments tests
python experiments/build_code_manifest.py --root .
python experiments/build_manifest.py --root .
python experiments/build_bundle_checksums.py --root .
python experiments/verify_manifest.py --root . research/MANIFEST_CODE_SHA256.txt
python experiments/verify_manifest.py --root . research/MANIFEST_SHA256.txt
```

## Evidence boundary

This release is not a physical-claim certificate. It concerns normalized waveform evidence only.
