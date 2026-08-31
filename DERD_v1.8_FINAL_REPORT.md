# DERD v1.8 final implementation report

Phase 18 reconstructs the external publication's stated OGLE-III plus OGLE-IV V-band input scope for `OGLE-LMC-CEP-0002`. The two official current files pass all frozen source checks and merge into 65 observations, exceeding the publication's minimum of 50.

The preregistered primary variant, `merged_ogleiii_iv_unweighted_free`, gives:

| Coordinate | Reconstructed | Published |
|---|---:|---:|
| R21 | 0.323348 | 0.314000 |
| phi21 | 4.227004 | 4.238000 |
| R31 | 0.120507 | 0.117000 |
| phi31 | 2.268295 | 2.283000 |

The joint Mahalanobis p-value is 0.941878 and the largest absolute marginal z-score is 0.806691. All six merged-source fixed/free and weighting variants pass the frozen joint and marginal consistency gates.

The achieved classification is:

```text
PUBLICATION_COMPATIBLE_RECONSTRUCTION_AUTHORITATIVE_INPUT_SCOPE_EXACT_CODE_AND_PUBLICATION_BYTE_IDENTITY_UNAVAILABLE
```

The result closes the measurement-count and source-scope gaps left by Phase 17. It does not establish byte-identical publication input, code-identical replay, an independent observing source, or independent astrophysical replication.

The cumulative astronomical denominator remains five and the C17 population gate remains closed.
