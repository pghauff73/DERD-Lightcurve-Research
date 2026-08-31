# DERD v0.5 release notes

## Added

- exact algebraic recovery of a geometric DERD candidate from complex harmonic roots and
  residues;
- weighted irregular-sampling Fourier extraction with coefficient uncertainty and SNR;
- constrained residue-phase, sign, root-domain, and higher-harmonic forecast gates;
- adapters for amplitude/phase feature catalogs with explicit sine/cosine conventions;
- cadence-aware synthetic positives, generic Fourier nulls, and phase-scrambled nulls;
- Bayesian-bootstrap score stability for the exposed 20-star pilot;
- IURMv1.1.1 minimum viable observation-count experiment;
- acquisition ranking that cannot be confused with astrophysical detection.

## Principal result

The 24-observation development cadence is insufficient for the harmonic proof test.  Its
cadence-aware synthetic holdout produced ROC AUC `0.4764` and balanced accuracy `0.5597`.
Under an optimistic uniform-phase design at the median observed noise ratio, the first
observation count passing the frozen robustness gates was `160` observations per star.

No existing pilot star passed the full SNR and stability qualification gate.  One object,
`OGLE-LMC-CEP-0010`, is retained only as a low-SNR acquisition priority.

## Scope

This release proves software and mathematical properties and produces a data-acquisition
requirement.  It does not promote C17 and does not support a physical shell or mass claim.
