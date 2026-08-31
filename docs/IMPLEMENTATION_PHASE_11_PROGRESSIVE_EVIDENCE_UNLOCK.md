# Phase 11: Progressive Evidence Unlock

## Purpose

Phase 10 correctly protected the fifteen-object 5+5+5 cohort with an all-or-nothing execution gate. That policy prevented incomplete family denominators from becoming population estimates, but it also prevented a scientifically ready individual target from being evaluated while unrelated source locks remained unavailable.

Phase 11 separates those two decisions:

1. **target-level execution**, which may proceed when one declared object has complete metadata and source locks;
2. **family and population aggregation**, which remains closed until every one of the fifteen frozen targets has a fresh, lock-bound result.

This is a progressive evidence frontier, not a relaxation of the scientific thresholds.

## Frozen denominator

The declared cohort remains unchanged:

- five classical Cepheids;
- five RR Lyrae stars;
- five Delta Scuti candidates;
- fifteen exposed-development objects in total.

No target is removed after an unfavourable result. No replacement identity may enter without a new sealed protocol.

## Progressive source receipt

`import_phase11_source_pack.py` accepts an arbitrary subset of the fifteen frozen raw files from a rights-reviewed local source pack. For every present file it verifies:

- repository and commit coordinates inherited from the cohort manifest;
- exact repository path;
- Git blob SHA-1;
- byte count;
- non-comment observation count;
- frozen SHA-256 when already available.

An absent file is recorded as pending. A present but mismatched file is a hard failure. Verified bytes are installed atomically into their declared local destinations.

The receipt uses the Phase-09-compatible header required by the existing source assessor and carries a separate Phase-11 receipt profile. This preserves backward-compatible verification without changing the meaning of the frozen source coordinates.

## Target-level execution rule

A target may execute only when:

\[
G_{\rm target}=G_{\rm metadata}\land G_{\rm source}.
\]

For each ready target, the unchanged Phase-08/Phase-07 evidence engine performs:

- simultaneous signed harmonics h1 through h8;
- HC3 coefficient covariance;
- h1 through h4 algebraic DERD recovery;
- h5 through h8 independent recurrence forecast;
- target-specific actual-cadence synthetic calibration;
- covariance propagation;
- source, SNR, structural, score and stability gates.

Every execution is bound to a canonical input-lock digest containing its identity, family, mode, period, metadata lock, source commit, Git blob, SHA-256, Phase-11 configuration and source-receipt digest.

## Denominator firewall

Target results may be reported individually. Family fractions and Wilson intervals remain suppressed unless:

\[
N_{\rm fresh}=15
\]

and each family has exactly five fresh results.

The firewall therefore permits learning from available evidence while preventing a partial denominator from masquerading as a prevalence estimate.

## First unlocked target

The first progressive source pack supplied `OGLE-LMC-CEP-0004`:

- 367 observations;
- 8,808 bytes;
- Git blob `12ba4fb6df56ade0f191307c1d7c0ebaa0f563dd`;
- SHA-256 `89e2be3447638bfaa07de72340d7fa89336a14ed00c67dc2e68e92a0b5122dae`.

The source and metadata gates pass, so the target is freshly evaluated. It reaches the recovery-harmonic stage but does not pass the frozen four-recovery-harmonic SNR gate. Harmonics h3 and h4 are below SNR 3, and the observed DERD score exceeds the target-specific compatibility threshold.

The result is an abstention for insufficient recovery-harmonic evidence, not a population rejection of DERD.

## OURD structure

Phase 11 represents the following as separate objects:

- sealed protocol;
- frozen cohort denominator;
- progressive source receipt;
- target-level readiness frontier;
- fresh waveform evidence;
- denominator firewall;
- claims C54 through C56.

Typed relations distinguish what unlocks target execution from what permits population aggregation.

## IURMv1.1.1 intervention

The active dimension is the number of cryptographically verified source locks:

\[
0\rightarrow1.
\]

Held constant are the cohort identities, metadata policy, harmonic extraction, calibration, covariance propagation, scientific thresholds and family denominator. This isolates the consequence of adding one valid source without allowing any compensating change elsewhere.

## EDOv1 contradiction policy

Phase 11 preserves:

- fourteen pending source locks;
- five pending authoritative Delta Scuti metadata locks;
- the negative recovery-harmonic result for the fresh target;
- the observed score above threshold;
- the incomplete population denominator;
- the exposed-development status of every identity.

No favourable result is required for an evidence object to be retained.

## Scientific boundary

The source paper proposes a normalized difference between two out-of-phase elliptical-radius functions and later advances separate hypotheses concerning internal radial motion and a transparent outer shell. Phase 11 tests only normalized waveform compatibility.

It does not establish:

- a unique stellar mechanism;
- literal internal Keplerian motion;
- a universal transparent outer shell;
- shell prevalence;
- shell mass or mass fraction.

Those claims require independent mechanism-sensitive and scale-sensitive observations.
