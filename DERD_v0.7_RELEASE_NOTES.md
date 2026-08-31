# DERD v0.7 release notes

Phase 07 implements the first raw-photometry to signed-harmonic forecast gate on a complete exposed development light curve.

## Added

- byte verification against a frozen Git blob;
- complete 372-observation OGLE-LMC-CEP-0010 evidence capsule;
- simultaneous signed eight-harmonic extraction;
- explicit intercept and coefficient-covariance ordering in the exchange format;
- HC3 covariance and Gaussian recurrence propagation;
- generic-harmonic period profiling separated from DERD scoring;
- actual-cadence synthetic calibration;
- a sustained, rather than pointwise, minimum-evidence rule;
- integrated source, coverage, SNR, structure, stability and calibration gates;
- claims C34 through C38.

## Evidence result

The integrated decision is `ABSTAIN_OR_REJECT_INSUFFICIENT_HARMONIC_EVIDENCE`. The first four harmonic SNRs are 182.895, 15.061, 3.821, 3.117; the forecast SNRs are 1.760, 1.336, 1.699, 0.832. The observed score 1.905220 exceeds threshold 1.470082, and only 12.60% of covariance draws remain below threshold.

The actual-cadence intervention's first pointwise pass is 120 observations, but its first sustained pass is 240 observations because 160 fails. MVHE-240 is target-specific and provisional.

## Scope

This release does not promote C17 or certify an internal orbit, transparent shell, shell prevalence or shell mass.
