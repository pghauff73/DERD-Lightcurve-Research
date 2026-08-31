# DERD v2.0 Phase-20 Final Report

## Decision

```text
PHASE20_MULTIBAND_AND_MECHANISM_TESTS_COMPLETE_STRICT_PASSBAND_INVARIANCE_REJECTED_DERD_UNIQUENESS_REJECTED_GRAVITY_ONLY_PERIODIC_MOTION_FORMALLY_REJECTED
C17_OPEN_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

## Executive result

Phase 20 performs the first integrated elimination experiment across passband, generating mechanism, and force law. It rejects a strict band-invariant normalized DERD waveform for `OGLE-LMC-CEP-0002`, demonstrates that DERD fit plus recurrence structure is not a unique gravitational signature, and proves that inverse-square gravity alone cannot sustain a periodic radial breathing trajectory.

## Multiband evidence

The I-versus-merged-V invariant comparison gives

\[
\chi^2=123.256374,\qquad p=1.076e-25.
\]

The same-band V epoch control gives

\[
p=0.992279.
\]

The difference is therefore associated with passband projection rather than an obvious V-band epoch drift in this test.

Representation-level RMSE values are:

| Model | RMSE | BIC | Bootstrap wins |
|---|---:|---:|---:|
| Shared DERD | 0.064525 | -2781.529 | 0 |
| Separate DERD | 0.028277 | -3601.384 | 2 |
| Shared components + band weights | 0.018499 | -4023.403 | 62 |

The shared-components model is consistent with a common oscillator projected through wavelength-dependent thermal, opacity, or atmospheric weights. It does not uniquely prove that interpretation.

## Mechanism non-uniqueness

The frozen tournament finds joint holdout passes in these non-DERD surrogate families:

- `radius_temperature_projection`: 0.375
- `vdp_hydrodynamic_surrogate`: 0.273
- `two_zone_surrogate`: 0.167
- `shock_modified`: 0.200
- `spot_rotation`: 0.500
- `cse_reprocessing`: 0.500

These controlled surrogates are not full stellar simulations. Their role is narrower and decisive: they show that the mathematical DERD signature is not unique to a gravitational or DERD generator.

## Gravity-only result

The inverse-square ballistic segment returns a positive, constant effective mass. Every nonconstant periodic control produces sign changes or large variation in inferred mass. More generally, a nonconstant periodic radius must attain a minimum where \(\ddot R\ge0\), contradicting \(\ddot R=-GM/R^2<0\) for positive mass.

Gravity may still provide the restoring skeleton in a pressure-supported hydrodynamic star. The rejected theory is gravity **alone** with no outward force.

## Surviving interpretation

The leading composite interpretation is:

```text
gravity-restored nonlinear hydrodynamics
+ radius/temperature/opacity evolution
+ wavelength-dependent atmospheric projection
```

DERD may remain useful as a compact nonlinear coordinate system, but its parameters are not yet uniquely identifiable as physical orbital coordinates.
