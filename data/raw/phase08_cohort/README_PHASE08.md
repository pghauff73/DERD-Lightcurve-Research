# Phase-08 local raw-input directory

The six `*.complete.dat` files in this directory are local, hash-verified inputs from the
frozen public GitHub mirror recorded in `data/manifests/phase08_cohort_sources.json`.
They are deliberately excluded from Git, repository manifests, patches, and release ZIPs
because the redistribution basis for the mirror has not been independently verified.

Retrieve them with:

```bash
PYTHONPATH=src python experiments/fetch_phase08_sources.py \
  --acknowledge-third-party-terms
```

The fetcher verifies Git blob SHA-1, SHA-256, byte count, and observation count before an
atomic write. Scientific reuse must preserve OGLE attribution and source provenance.
