# Phase-02 observational source manifest

## Official scientific source

The target identifiers, period concepts, and three-column photometry format are from the
OGLE Collection of Variable Stars, LMC classical Cepheid collection. The official format
states that I/V photometry files contain `HJD-2450000`, magnitude, and magnitude
uncertainty. Publications using OGLE data must acknowledge the OGLE project and cite the
appropriate collection paper.

Official collection landing page:

- `https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/cep/`

## Executable mirrors frozen for this shakedown

Photometric rows were transcribed from the public GitHub mirror:

- repository: `bksim/OutlierDetection`
- commit: `55836b58345b9507bfbd98c5fabbac82c83605e3`
- directory: `Cluster/cep/phot/I/`

Periods and pulsation-mode labels were cross-checked against:

- repository: `dubbatee/ScienceExtensionCode`
- commit: `2d5f05d5c20d8c4c1c1e8811d502398232f14316`
- file: `Finalised SciX/lmccephdata.csv`

## Evidence boundary

This package contains the first 24 observations for each of 20 targets, not the complete
OGLE light curves. It is an engineering shakedown of parsers, leakage controls, fitting,
and reporting. It is not a confirmatory population sample and must not be described as a
complete OGLE benchmark.

## Phase-07 complete exposed-development source

Phase 07 uses the complete public-mirror file for `OGLE-LMC-CEP-0010`, frozen by Git blob SHA-1 and SHA-256 in `phase07_complete_development_source.json`. The source has 372 observations and is used only as exposed development evidence.

The mirror redistribution terms have not been verified. The raw bytes are therefore fetched locally after explicit acknowledgement and are not included in the release bundle. Exact mirror provenance is not presented as an independent check against the official OGLE authority copy.

## Phase-08 multi-family development cohort

Phase 08 uses six complete files from the same frozen public GitHub mirror at commit
`55836b58345b9507bfbd98c5fabbac82c83605e3`, with two objects each from the mirror's
classical-Cepheid, RR-Lyrae, and Delta-Scuti directories. Every local input is verified by
Git blob SHA-1, SHA-256, byte count, and observation count.

Official collection context and file-format authority:

- Classical Cepheids: `https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/cep/`
- RR Lyrae: `https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/rrlyr/`
- Delta Scuti: `https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/dsct/`

Raw mirror bytes are not distributed in the release. The frozen source manifest and
rights-aware retrieval program are supplied instead. Delta Scuti periods in this tranche
remain legacy feature-table diagnostics and are excluded from claim-grade object counts.
