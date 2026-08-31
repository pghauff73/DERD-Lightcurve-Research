# DERD v1.7 final report: Phase 17 external-analysis anchor

## Decision

`PHASE17_EXTERNAL_ANALYSIS_ANCHOR_CONSISTENT_PARTIAL_SOURCE_OVERLAP_INDEPENDENT_ASTROPHYSICAL_REPLICATION_STILL_ABSENT`

## Implemented gate

Phase 17 adds a peer-reviewed external Fourier-analysis anchor for `OGLE-LMC-CEP-0002` and compares it with a locally reconstructed, provenance-verified 33-observation V-band subset. The comparison is performed in the published cosine-series coordinates `R21`, `phi21`, `R31`, and `phi31` with a deterministic 2,000-draw 60-percent subsample bootstrap.

## Result

| Quantity | Value |
|---|---:|
| Local period | 3.118132973858 d |
| Published period | 3.118121 d |
| Joint Mahalanobis statistic | 1.773349307 |
| Degrees of freedom | 4 |
| Joint p-value | 0.777354480 |
| Maximum absolute marginal z | 1.275490387 |
| Local reduced chi-square | 4.678320 |
| Classification | `EXTERNAL_ANALYSIS_CONSISTENT_PARTIAL_SOURCE_OVERLAP` |

The local and published Fourier-coordinate vectors are statistically consistent under the frozen joint test. The local fit's reduced chi-square exceeds one, so quoted photometric errors do not fully describe the observed scatter or three-harmonic model mismatch.

## Independence boundary

The external research group is independent of the DERD implementation. The observing source is not independent: both analyses use the OGLE survey family. The local mirror contains 33 measurements, while the external workflow excluded light curves with fewer than 50 observations, and the exact publication input bytes are unknown. The result is therefore an external methodological consistency edge, not an independent astrophysical replication.

## Evidence graph

| Dimension | Phase 16 | Phase 17 |
|---|---:|---:|
| Unique astronomical objects | 5 | 5 |
| Analysis-version nodes | 9 | 11 |
| External-analysis consistency edges | 0 | 1 |
| External independent astrophysical replications | 0 | 0 |
| Duplicate denominator increments prevented | 4 | 6 |

The astronomical denominator remains five. Population fractions and C17 promotion remain blocked.

## Research-framework integration

- **OURD:** distinguishes paper, published coordinate vector, local source, local estimate, joint audit, independence gate, graph edge, denominator guard, and physical-claim firewall.
- **IURMv1.1.1:** varies analysis-group independence and source completeness while keeping identity, passband, coordinate convention, harmonic order, and denominator policy fixed.
- **EDOv1:** preserves the consistency result alongside the limiting evidence: partial source, unknown exact publication bytes, same survey family, reduced chi-square above one, and no external DERD execution.

## Verification

- 232 unit and integration tests pass.
- Python compilation passes.
- 275 JSON files parse successfully at the final implementation checkpoint.
- The raw 33-row V-band file is excluded from the redistributable release.
- Physical mechanism, transparent-shell prevalence, and mass gates remain locked.

## Main artifacts

- `artifacts/phase17/PHASE17_RESULT.md`
- `artifacts/phase17/phase17_summary.json`
- `artifacts/phase17/phase17_external_analysis_audit.json`
- `artifacts/phase17/phase17_fourier_parameter_comparison.csv`
- `artifacts/phase17/phase17_reproducibility_graph.json`
- `artifacts/phase17/phase17_cumulative_ledger.json`
- `docs/IMPLEMENTATION_PHASE_17_EXTERNAL_ANALYSIS_ANCHOR.md`

## Next gate

The next promotion step requires either:

1. the exact 50-plus-observation source used by the external publication and an exact method replay; or
2. an independent observing source and an external group executing the frozen DERD protocol.

Only the second path can create the first independent astrophysical replication edge.
