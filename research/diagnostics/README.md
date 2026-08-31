# Phase-02 first-pass diagnostic

The first complete run allowed BIC to choose Fourier orders 1–5 without a conditioning
or bounded-extrapolation gate. On the 19-point training subsets, some high-order weighted
design matrices produced very large coefficients and catastrophic predictions inside the
held-out phase block. The raw result is retained here rather than overwritten.

The corrected Phase-02 run adds a training-only Fourier stability gate. It does not inspect
held-out values. Raw BIC remains reported as a diagnostic, while the stable-BIC baseline
rejects candidates with an ill-conditioned weighted design or a dense-cycle prediction
span exceeding three times the training-target span.
