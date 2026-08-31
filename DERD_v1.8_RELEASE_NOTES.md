# DERD v1.8 release notes

## Phase 18: exact external-input-scope reconstruction

### Added

- verified official current OGLE-III and OGLE-IV V-band source manifests;
- a 65-observation chronological input merge;
- corrected external-method contract distinguishing K2 bootstrap uncertainty from OGLE `curve_fit` covariance;
- an 18-variant source, weighting and period method lattice;
- analytic covariance propagation for `R21`, `phi21`, `R31`, and `phi31`;
- publication-vector joint and marginal consistency tests;
- external-input reconstruction node and denominator guard in the reproducibility graph;
- claims C85 through C90;
- Phase-18 source retriever, runner, tests, plots and release manifests.

### Result

The preregistered merged, unweighted, free-period reconstruction uses 65 observations and is jointly consistent with the published vector. All six merged-source method variants pass the frozen joint and marginal gates.

Exact publication source-byte identity and exact code replay remain unavailable because the article publishes neither hashes nor analysis source code and does not fully specify `curve_fit` weighting.

### Scope

This release is an external Fourier-input and provenance reconstruction. It does not promote C17, identify a unique internal mechanism, certify a transparent shell, or constrain shell mass.
