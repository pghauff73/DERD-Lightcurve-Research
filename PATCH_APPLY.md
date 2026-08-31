# Apply the DERD v1.4 incremental patch

The v1.4 patch adds the Phase-14 period-coordinate robustness ledger to a clean DERD v1.3 research tree. It does not include third-party complete photometry or authoritative catalogue bytes.

```bash
git apply --check lightcurve-trainer-DERD-v1.4-from-v1.3.patch
git apply lightcurve-trainer-DERD-v1.4-from-v1.3.patch
python -m pip install -e '.[test,research]'
PYTHONPATH=src:. python -m pytest
PYTHONPATH=src:. python experiments/verify_manifest.py --manifest research/CODE_MANIFEST_SHA256.txt
PYTHONPATH=src:. python experiments/verify_manifest.py
```

To reproduce the selected target and coordinate audit, obtain the rights-reviewed file identified by `data/manifests/phase14_acquisition_order.json`, then run:

```bash
PYTHONPATH=src:. python experiments/import_phase14_source_pack.py \
  --root . \
  --input-dir /path/to/source-pack \
  --acknowledge-ogle-attribution

PYTHONPATH=src:. python experiments/run_phase14.py \
  --root . \
  --receipt artifacts/phase14/phase14_source_acquisition_receipt.json \
  --output artifacts/phase14 \
  --execute-ready
```

The raw source is installed locally for computation and must be removed before building a redistributable bundle. The patch is incremental from v1.3. Use the complete v1.4 bundle when no clean v1.3 tree is available.
