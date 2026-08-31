# DERD Light-Curve Research

**Reproducible waveform-model research and evidence gates for Cepheid, RR Lyrae, and Delta Scuti light curves.**

[![CI](https://github.com/pghauff73/DERD-Lightcurve-Research/actions/workflows/ci.yml/badge.svg)](https://github.com/pghauff73/DERD-Lightcurve-Research/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![Release](https://img.shields.io/badge/release-v2.1.0-informational)](DERD_v2.1_RELEASE_NOTES.md)
[![Research status](https://img.shields.io/badge/status-hypothesis%20testing-orange)](DERD_v2.1_FINAL_REPORT.md)

## What this repository contains

This repository implements and tests the **DERD difference-of-radii waveform model**. The model represents a normalized periodic light curve using two out-of-phase elliptical-radius components and four principal parameters:

1. amplitude ratio;
2. eccentricity of component A;
3. eccentricity of component B;
4. phase-difference ratio.

The implementation is surrounded by a staged evidence system rather than a single best-fit demonstration. Across twenty-one phases, the project adds synthetic verification, leakage-resistant train/test contracts, harmonic transport, covariance-aware uncertainty, authoritative catalogue identity gates, source-byte provenance, cumulative replay ledgers, external-replication tooling, and mechanism-falsification tests.

> **Scientific boundary:** this repository tests waveform behavior, reproducibility, and observational compatibility. It is **not** a certificate that stellar interiors literally follow Keplerian orbits, that pulsators universally possess a transparent outer shell, or that any shell has a particular mass.

## Phase 21 status

Phase 21 freezes a development denominator of:

| Family | Objects |
|---|---:|
| Classical Cepheids | 5 |
| RR Lyrae | 5 |
| Delta Scuti | 5 |
| **Total** | **15** |

Current gate state:

- **13/15** objects have claim-grade metadata;
- **3/5** Delta Scuti identities have exact two-hop catalogue locks;
- **2/5** Delta Scuti crosswalks remain unresolved and are not guessed;
- **0/15** complete local raw-source locks are bundled;
- family-level prevalence outputs and Wilson intervals remain suppressed;
- **C17 is not promoted**;
- the release is marked `NOT_A_PHYSICAL_CLAIM_CERTIFICATE`.

Read [`DERD_v2.1_FINAL_REPORT.md`](DERD_v2.1_FINAL_REPORT.md) and [`artifacts/phase21/PHASE21_RESULT.md`](artifacts/phase21/PHASE21_RESULT.md) before interpreting results.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,research]'
```

## Verify the repository

```bash
PYTHONPATH=src:. python -m pytest
PYTHONPATH=src:. python -m compileall -q src experiments
PYTHONPATH=src:. python experiments/verify_manifest.py \
  --manifest research/CODE_MANIFEST_SHA256.txt
PYTHONPATH=src:. python experiments/verify_manifest.py
```

The frozen v2.1 bundle reports **273 passing tests**. Its release and repository manifests are retained under `research/` and at the repository root.

## Run Phase 21

Verify the authoritative catalogue receipt and current readiness:

```bash
PYTHONPATH=src:. python experiments/import_phase21_catalog_rows.py --root .
PYTHONPATH=src:. python experiments/run_phase21.py --root .
```

Import a rights-reviewed local source pack:

```bash
PYTHONPATH=src:. python experiments/import_phase21_source_pack.py \
  SOURCE_PACK \
  --root . \
  --acknowledge-rights-and-attribution
```

Execute the complete cohort only after every metadata and source gate passes:

```bash
PYTHONPATH=src:. python experiments/execute_phase21_cohort.py --root .
```

## Repository map

| Path | Purpose |
|---|---|
| `src/derd/` | DERD models, fitting, validation, and phase-specific evidence logic |
| `experiments/` | Reproducible phase runners, importers, and integrity tools |
| `tests/` | Unit, regression, provenance, and gate-behavior tests |
| `docs/` | Mathematical specifications and implementation documents |
| `research/preregistration/` | Frozen protocols and seals |
| `research/claims/` | Machine-readable claim objects and dispositions |
| `research/ourd/` | Object/relation evidence models |
| `research/iurm/` | One-variable-at-a-time intervention records |
| `research/edov1/` | Evidence-discovery records, including blockers |
| `artifacts/phaseXX/` | Results, receipts, figures, and machine-readable summaries |
| `data/manifests/` | Identity, metadata, and source-lock contracts |

A detailed phase-by-phase guide is available in [`README_IMPLEMENTATION.md`](README_IMPLEMENTATION.md). The release map is in [`RELEASE_INDEX.md`](RELEASE_INDEX.md).

## Data and provenance policy

Third-party raw photometry is intentionally not redistributed where rights have not been verified. Local source files are accepted only through explicit provenance and integrity checks, including repository/path identity, byte count, observation count, Git blob identity where applicable, and SHA-256.

Do not replace an unresolved catalogue identity with suffix matching, zero-padding, nearest-coordinate matching, or a convenient substitute object. Missing evidence remains missing.

## Citation

A machine-readable citation record is provided in [`CITATION.cff`](CITATION.cff).

Suggested software citation:

> Pamela G. Hauff. *DERD Light-Curve Research*, version 2.1.0, 2026.

## License status

No open-source license has yet been selected for this research repository. See [`LICENSE-STATUS.md`](LICENSE-STATUS.md). Until a license is deliberately chosen, normal copyright restrictions apply.
