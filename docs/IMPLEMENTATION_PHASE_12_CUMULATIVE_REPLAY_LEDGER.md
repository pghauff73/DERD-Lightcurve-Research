# Phase 12 implementation: cumulative replay ledger

## 1. Purpose

Phase 11 allowed each target to execute as soon as its own metadata and source locks passed, while retaining a fifteen-object population firewall. Phase 12 makes that workflow cumulative. A verified result no longer disappears from progress merely because third-party raw bytes are removed from the redistributable release after execution.

The phase adds four independent guarantees:

1. **prior-record retention:** prior evidence is counted only after all record and artifact digests verify;
2. **incremental execution:** only ready targets absent from the ledger are executed;
3. **replay fidelity:** a fresh target is compared with any inherited Phase-08 scientific record;
4. **denominator integrity:** two verified records do not authorize fifteen-object population outputs.

## 2. Cumulative record structure

Each target record binds:

```text
object identity
+ declared identity
+ family
+ canonical input lock
+ input-lock SHA-256
+ complete scientific result
+ result SHA-256
+ signed-harmonic exchange path
+ exchange SHA-256
+ stage and disposition
+ NOT_A_PHYSICAL_CLAIM_CERTIFICATE
+ origin summary and origin summary SHA-256
```

The ledger rejects a duplicate identity unless its input-lock, result, and exchange digests are identical. Conflicting duplicates are hard failures.

## 3. Parent-chain verification

The Phase-12 protocol seal binds the Phase-11 summary SHA-256. Prior Phase-11 records are loaded only when:

- the prior implementation identifier is exact;
- the prior protocol is valid;
- the input-lock digest matches its canonical object;
- the result digest matches its canonical object;
- the harmonic-exchange artifact exists and matches its file digest;
- target identity, family, stage, disposition, and certificate agree.

The resulting parent-chain SHA-256 is retained in every cumulative ledger release.

## 4. Incremental source receipt

`import_phase12_source_pack.py` carries prior verified source history forward and adds newly verified source locks. New bytes must match the frozen:

```text
byte count
observation count
Git blob SHA-1
SHA-256
```

Raw photometry is installed atomically for execution and is excluded from the redistributable release. Historical source locks may remain in the receipt even when the local raw file is absent.

## 5. Scientific replay projection

A full record hash is intentionally sensitive to all metadata. A separate scientific projection removes only two transport labels:

- `source_relative_path`;
- the human-readable `period_source` label.

The harmonic-exchange projection similarly permits phase/release labels and the human period-source label to change. Coefficients, covariance, scores, thresholds, SNR values, stages, dispositions, periods, modes, and all scientific arrays remain exact-match dimensions.

Any scientific drift changes the gate decision to `PHASE12_SCIENTIFIC_REPLAY_DRIFT_DETECTED` when replay matching is required.

## 6. Frozen scientific coordinates

Phase 12 inherits the Phase-11 coordinates unchanged:

```text
synthetic samples per class = 96
covariance propagation draws = 2048
period grid points = 101
minimum observations = 240
recovery harmonics = h1-h4, each SNR >= 3
forecast harmonics = h5-h8, at least two SNR >= 2
```

The active IURMv1.1.1 dimension is therefore one newly verified source and execution, while the scientific model, thresholds, cohort identities, and denominator remain frozen.

## 7. First cumulative update

The prior ledger contains `OGLE-LMC-CEP-0004`. Phase 12 adds `OGLE-LMC-RRLYR-00001`, producing two unique records.

The new target reaches `FORECAST_HARMONICS` because h1-h4 all pass SNR 3. It stops with `ABSTAIN_INSUFFICIENT_MEASURED_FORECAST_HARMONICS` because no pair among h5-h8 reaches SNR 2. Its score also remains above its target-specific threshold and no covariance draw passes the complete structural constraints.

The fresh scientific projection and harmonic exchange exactly reproduce the inherited Phase-08 result. The full record differs only in the permitted local source path and human period-source label.

## 8. Population firewall

The frozen denominator remains:

```text
5 classical Cepheids
5 RR Lyrae stars
5 Delta Scuti stars
```

Family fractions, Wilson intervals, and cross-family comparisons remain suppressed until all fifteen identities have one unique verified cumulative record. The present coverage is one Cepheid, one RR Lyrae, and zero Delta Scuti targets.

## 9. Scientific boundary

The ledger contains normalized waveform evidence. It does not identify a unique stellar mechanism or establish a transparent shell, shell prevalence, stellar mass, shell mass, or a mass fraction. Those claims require independent mechanism-sensitive and scale-sensitive observables.
