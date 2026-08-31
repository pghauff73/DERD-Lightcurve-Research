# DERD v1.7, Phase 17 external-analysis anchor

## Added

- a frozen peer-reviewed OGLE V-band Fourier anchor for `OGLE-LMC-CEP-0002`;
- simultaneous weighted three-harmonic magnitude fitting in the external cosine convention;
- deterministic 60%-subsample bootstrap covariance with period refitting;
- joint Mahalanobis and marginal-z consistency gates;
- explicit separation of research-group independence, observing-source independence, exact byte identity, and source completeness;
- an extended reproducibility graph with one external-analysis consistency edge;
- a denominator guard preventing the publication and local reanalysis from creating additional astronomical objects.

## Evidence result

The local 33-point V-band estimate is jointly consistent with the published `R21`, `phi21`, `R31`, and `phi31` coordinates. The edge is classified as `EXTERNAL_ANALYSIS_CONSISTENT_PARTIAL_SOURCE_OVERLAP` because the local source does not meet the publication's minimum measurement count, the exact publication input bytes are unknown, and both analyses use the OGLE survey family.

## Scope

This release validates Fourier-coordinate transport and an external methodological anchor. It is not an independent astrophysical replication and does not support a unique internal mechanism, transparent-shell prevalence, or shell mass.
