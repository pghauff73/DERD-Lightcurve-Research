# Phase 16 result: cross-version reproducibility graph

Decision: `PHASE16_REPRODUCIBILITY_GRAPH_SEALED_POPULATION_GATE_CLOSED`

## Graph summary

- Unique astronomical objects: **5**
- Analysis-version nodes: **9**
- Exact scientific replay edges: **3**
- Configuration-sensitive drift edges: **1**
- Single-version objects: **1**
- External independent replications: **0**
- Duplicate analysis inflation prevented: **4**

## Edge classifications

- `OGLE-LMC-CEP-0002`: `phase08` → `phase14` = `EXACT_SCIENTIFIC_REPLAY_METADATA_TRANSPORT_DRIFT`
- `OGLE-LMC-CEP-0010`: `phase07` → `phase08` = `CONFIGURATION_SENSITIVE_SCIENTIFIC_DRIFT`
- `OGLE-LMC-RRLYR-00001`: `phase08` → `phase12` = `EXACT_SCIENTIFIC_REPLAY_METADATA_TRANSPORT_DRIFT`
- `OGLE-LMC-RRLYR-00004`: `phase08` → `phase13` = `EXACT_SCIENTIFIC_REPLAY_METADATA_TRANSPORT_DRIFT`

## Multiplicity rule

Each astronomical object contributes at most one denominator record, regardless of how many software phases analyse the same source bytes.

Family fractions and population claims remain suppressed because the frozen 15-object denominator is incomplete.
