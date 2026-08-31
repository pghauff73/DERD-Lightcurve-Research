# Phase 16: cross-version reproducibility graph

## Purpose

Phase 16 separates computational replay from astrophysical replication. The five-object cumulative ledger contains nine analysis-version nodes because several sources were processed in more than one phase. Without an explicit multiplicity guard, repeated analysis of the same observations could be mistaken for additional evidence.

## Reproducibility classes

The graph distinguishes:

1. **Exact scientific replay with metadata transport drift**: the same source and scientific configuration reproduce the scientific projection and signed harmonic exchange exactly; only path or human-readable labels differ.
2. **Configuration-sensitive scientific drift**: the same source is processed under different scientific coordinates and at least one coefficient, SNR, score, threshold, stage, or disposition changes.
3. **Single version**: one retained analysis version exists and no replay test is yet available.
4. **External independent replication**: a different observing source or external research group repeats the analysis. No such edge exists in the current graph.

## Result

The graph contains:

- five unique astronomical objects;
- nine analysis-version nodes;
- three exact scientific replay edges;
- one configuration-sensitive drift edge;
- one single-version object;
- zero external independent replications.

The evidence multiplicity guard blocks four potential duplicate denominator contributions. Each astronomical object contributes at most one denominator record regardless of how many software versions analyse the same source.

## Claim boundary

Phase 16 is a computational reproducibility and evidence-accounting result. It does not establish model truth, an internal stellar mechanism, a transparent outer shell, shell prevalence, or shell mass.
