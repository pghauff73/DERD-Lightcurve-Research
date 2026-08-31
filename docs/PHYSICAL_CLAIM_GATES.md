# Physical-claim gates after the waveform shakedown

## Source-derived claims being gated

The source paper proposes four waveform parameters, states that normalization factors out
mass in the printed implementation, then advances a radial core-shell interpretation and a
transparent external shell. These are different evidentiary levels and are not promoted by
a photometric waveform fit.

## Gate P1: radial Kepler compatibility

For a Newtonian inverse-square central force, a strictly radial trajectory has angular
momentum `L = 0`. The conic eccentricity relation is

```text
e^2 = 1 + 2 E L^2 / (mu^2 m^3).
```

At `L = 0`, the trajectory is the degenerate `e = 1` case, not an ordinary ellipse with
`0 <= e < 1`. Therefore DERD eccentricities remain phenomenological unless a non-radial
motion, different effective potential, or explicit mapping to stellar pulsation dynamics is
supplied and tested.

## Gate P2: spherical external-shell gravity

Newton's shell theorem gives zero gravitational field everywhere inside an ideal spherical
shell. A shell lying wholly outside the photosphere cannot, by its own spherical gravity,
drive the photosphere's radial oscillation. A physical model must state and test a coupling
such as shell asymmetry, overlap, pressure, radiation, electromagnetic interaction, or mass
exchange.

## Gate P3: transparency and shell mass

A thin shell with mass `M_s`, characteristic radius `R_s`, and wavelength-dependent opacity
`kappa_lambda` has approximate optical depth

```text
tau_lambda = kappa_lambda M_s / (4 pi R_s^2).
```

The normalized DERD waveform contains no absolute radius or mass scale. Shell mass must be
constrained using external observables and a radiative-transfer model, not the four
normalized waveform dimensions alone.

## Promotion rule

A successful C17 descriptor benchmark may promote only a waveform-method claim. It cannot
promote radial-orbit, universal-shell, or shell-mass claims.
