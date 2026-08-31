# DERD v0.8 release notes

## Phase 08 multi-family cohort

DERD v0.8 extends the lossless Phase-07 harmonic-forecast gate from one Cepheid to six
exposed development objects spanning classical Cepheid, RR Lyrae, and Delta Scuti
families.

### Added

- `src/derd/validation_phase08.py` cohort and acquisition logic;
- target-specific deterministic calibration seeds;
- a six-object byte-frozen source manifest and rights-aware fetcher;
- six lossless harmonic-exchange records;
- family, target, harmonic-SNR, and acquisition evidence tables;
- a seven-stage evidence ladder and explicit period-provenance gate;
- separation of byte completeness from conservative data cleaning;
- Phase-09 prospective development protocol and cryptographic seal.

### Result

- 2,138 raw observations and 2,135 retained observations;
- 1 of 6 objects measures all four recovery harmonics at Wald SNR 3;
- 0 of 6 measures at least two forecast harmonics at Wald SNR 2;
- 0 of 6 passes all DERD structural constraints;
- 0 of 6 qualifies as a development harmonic forecast;
- C17 remains open and unpromoted.

### Scope

This is exposed development evidence. It is not a population estimate, a prospective
confirmation, or a certificate for internal orbital dynamics, a transparent shell, or
shell mass.
