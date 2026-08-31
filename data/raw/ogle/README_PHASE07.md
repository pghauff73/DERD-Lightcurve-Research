# Phase-07 complete development source

`OGLE-LMC-CEP-0010.complete.dat` is deliberately not tracked or bundled because the
redistribution terms of the public mirror have not been verified.

Retrieve and verify the exact frozen development bytes with:

```bash
PYTHONPATH=src python experiments/fetch_phase07_source.py \
  --acknowledge-third-party-terms
```

The source manifest freezes the Git blob SHA-1, SHA-256, byte count, source commit,
and evidence role. The file is exposed development evidence only. It is not part of a
prospective sealed holdout and is not presented as an official OGLE authority copy.
