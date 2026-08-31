# Phase 20 Implementation Handoff

## Status

```text
PHASE20_MULTIBAND_AND_MECHANISM_TESTS_COMPLETE_STRICT_PASSBAND_INVARIANCE_REJECTED_DERD_UNIQUENESS_REJECTED_GRAVITY_ONLY_PERIODIC_MOTION_FORMALLY_REJECTED
C17_OPEN_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## Main results

- I versus merged V invariants: chi-square **123.256374**, p **1.076e-25**.
- OGLE-III V versus OGLE-IV V: p **0.992279**.
- Shared latent components with band weights: **62 / 64** bootstrap wins.
- Non-DERD families with at least one joint holdout pass: radius_temperature_projection, vdp_hydrodynamic_surrogate, two_zone_surrogate, shock_modified, spot_rotation, cse_reprocessing.
- Ballistic inverse-square control passes; all periodic effective-mass controls fail.

## Reproduction

The optimization-heavy components are intentionally isolated in fresh Python processes:

```bash
./experiments/run_phase20_all.sh .
```

The wrapper executes the passband model worker, the mechanism-tournament worker, and then the main aggregation process. Official V-band raw sources are local-only and must match the hashes in `data/manifests/phase20_multiband_sources.json`.

## Next gate

The next high-information experiment is a physical-observable test using simultaneous radius, radial velocity, temperature, and multiband photometry. A photometry-only DERD fit should be frozen before withheld kinematics are inspected.
