# Phase 04 readiness result

Status: `PHASE03_RELEASE_CLOSED_PHASE04_READINESS_IMPLEMENTED_POPULATION_NOT_ACQUIRED`

## Work completed

The Phase-03 implementation was reconstructed as a self-contained repository addition, its missing adaptive period audit was restored, and the complete experiment was replayed. The replay reproduced the original Phase-03 summary, per-star table, detailed JSON, and report byte for byte. It also generated the previously absent 20 per-star prediction files.

Phase-04 readiness now operates before any new light-curve fit. It contains:

- a frozen ten-stratum population contract;
- a sealed confirmatory analysis plan;
- file SHA-256, authority, source locator, and reuse-basis checks;
- minimum observation-count and phase-coverage checks;
- permanent exclusion of prior-exposed stars from the pristine holdout;
- deterministic star-identity role assignment;
- a cryptographic seal linked to the candidate manifest, contract, analysis plan, and code manifest;
- a guard that refuses development evaluation of a sealed star identity.

## Phase-03 replay

| Verification object | Result |
|---|---|
| Summary JSON | byte identical |
| Per-star CSV | byte identical |
| Detailed JSON | byte identical |
| Markdown report | byte identical |
| Prediction files regenerated | 20 |
| Replay runtime | about 34 seconds in the release environment |

The scientific result is unchanged. Training-selected DERD won 9 of 20 comparisons, the mean paired RMSE difference was approximately -0.009685, and the provisional noninferiority gate remained failed because the 95 percent interval crossed the +0.02 margin.

## Current-pilot readiness audit

The existing 20-star engineering capsule was deliberately submitted to the Phase-04 gate. It was rejected before role assignment.

| Gate finding | Count |
|---|---:|
| Source files with matching SHA-256 | 20 |
| Prior-exposed stars | 20 |
| Stars below 50-observation minimum | 20 |
| Stars below 10-of-12 phase-bin minimum | 20 |
| Underfilled or absent strata | 10 |
| Candidate population | 20 |
| Required population | 150 |
| Total recorded blocking findings | 71 |

The represented strata are `CEP-F` and `CEP-1O`, with ten stars each. Every other required stratum has zero candidates. The current stars remain useful development evidence, but none can enter the pristine sealed holdout.

## Governance-system positive control

A clearly labelled synthetic governance fixture, containing no astrophysical evidence, exercised the complete role-sealing path:

| Role | Synthetic identities |
|---|---:|
| Development | 100 |
| Sealed holdout | 50 |

All linked digest checks passed. A development-only evaluation manifest passed the guard. A deliberate manifest containing one sealed identity was blocked with a non-zero exit status.

Synthetic role seal:

```text
8dfeea4cb50cbadf7b1710883712b294469e8ae4737443b0fa526bd6b84dca3f
```

## Verification

- 115 unit and integration tests pass.
- Python compilation passes.
- The code and protocol manifest verifies every listed file.
- Phase-03 output replay is deterministic for all core scientific artifacts.
- The current population fails safely.
- The synthetic governance path passes and the sealed probe is rejected.

## Evidence boundary

This release proves software, reproducibility, provenance, and prospective-governance properties. It does not add evidence for literal internal Keplerian motion, a universal transparent external shell, or a shell-mass fraction. Those claims remain gated behind independent observables and physically identifiable models.
