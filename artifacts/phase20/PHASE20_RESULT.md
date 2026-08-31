# DERD Phase 20 Result

## Decision

```text
PHASE20_MULTIBAND_AND_MECHANISM_TESTS_COMPLETE_STRICT_PASSBAND_INVARIANCE_REJECTED_DERD_UNIQUENESS_REJECTED_GRAVITY_ONLY_PERIODIC_MOTION_FORMALLY_REJECTED
C17_OPEN_NOT_PROMOTED
NOT_A_PHYSICAL_CLAIM_CERTIFICATE
```

Phase 20 performs three orthogonal falsification experiments: a real I-versus-V passband test, a synthetic mechanism tournament, and a gravity-only effective-mass test.

## Experiment A: passband invariance

For `OGLE-LMC-CEP-0002`, the I-band and merged V-band harmonic invariant vectors differ strongly:

- joint Mahalanobis statistic: **123.256374** on 4 dimensions;
- p-value: **1.076e-25**.

By contrast, the two V-band observing epochs are mutually consistent:

- OGLE-III V versus OGLE-IV V p-value: **0.992279**.

This rejects one strict band-invariant normalized waveform for this exposed-development star. It does not reject a shared physical oscillator projected through band-dependent temperature, opacity, or atmospheric weights.

The representation-level comparison favours shared latent components with band-specific weights:

- strict shared DERD RMSE: **0.064525**;
- separate DERD RMSE: **0.028277**;
- shared-components RMSE: **0.018499**;
- shared-components bootstrap wins: **62 / 64**.

This BIC comparison is explicitly representation-level. It uses covariance-sampled h1-h8 reconstructions, not independent raw points.

## Experiment B: mechanism tournament

Thresholds were selected only from development DERD positives and generic-Fourier nulls, then applied to held-out cases from ten frozen mechanism families. Several non-DERD families passed both the nonlinear fit and harmonic-screen gates:

- `radius_temperature_projection`: joint pass fraction 0.375
- `vdp_hydrodynamic_surrogate`: joint pass fraction 0.273
- `two_zone_surrogate`: joint pass fraction 0.167
- `shock_modified`: joint pass fraction 0.200
- `spot_rotation`: joint pass fraction 0.500
- `cse_reprocessing`: joint pass fraction 0.500

Therefore, a good DERD fit plus a low harmonic-screen score is **not a unique gravitational signature**. The mechanism generators are controlled surrogates, not full stellar-evolution models, so the experiment disproves uniqueness rather than estimating astrophysical prevalence.

## Experiment C: gravity-only effective mass

For a gravity-only radial trajectory,

\[
M_{\rm eff}(t)=-\frac{R(t)^2\ddot R(t)}{G}
\]

must remain positive and approximately constant. The inverse-square ballistic control passes; every nonconstant periodic control fails:

- `inverse_square_ballistic_segment`: positive-mass fraction 1.000, CV 0.000, pass=True
- `harmonic_breathing_mode`: positive-mass fraction 0.347, CV 0.519, pass=False
- `derd_waveform_interpreted_as_radius`: positive-mass fraction 0.558, CV 1.257, pass=False
- `pressure_supported_hydrodynamic_surrogate`: positive-mass fraction 0.464, CV 0.790, pass=False

There is also a formal contradiction: at a local minimum of any nonconstant twice-differentiable periodic radius, \(\ddot R\ge0\), while gravity-only inverse-square motion requires \(\ddot R=-GM/R^2<0\). A positive-mass gravity-only force cannot sustain a periodic radial breathing cycle without an outward force.

## Integrated conclusion

The following claims are rejected or narrowed:

1. one normalized DERD curve is passband invariant for this test star;
2. DERD fit and recurrence structure uniquely identify gravity;
3. positive-mass gravity alone sustains periodic radial pulsation.

The strongest surviving model is a gravity-restored nonlinear hydrodynamic oscillator whose radius, temperature, opacity, and atmosphere project differently into each passband. DERD may remain useful as a reduced coordinate system, but its parameters are not yet uniquely physical.
