#!/usr/bin/env python3
"""Verify the frozen Phase-21 authoritative row receipt and metadata locks."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from derd.ogle_catalog_phase21 import validate_metadata_lock_manifest, validate_row_receipt


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.'); args=ap.parse_args()
    root=Path(args.root).resolve()
    receipt=json.loads((root/'data/manifests/phase21_authoritative_catalog_row_receipt.json').read_text())
    lock=json.loads((root/'data/manifests/phase21_delta_scuti_metadata_lock.json').read_text())
    rv,rb=validate_row_receipt(receipt); lv,lb=validate_metadata_lock_manifest(lock,receipt=receipt)
    result={'row_receipt_valid':rv,'row_receipt_blockers':list(rb),'metadata_lock_valid':lv,'metadata_lock_blockers':list(lb),'locked_count':lock['locked_count'],'unresolved_count':lock['unresolved_count']}
    print(json.dumps(result,indent=2))
    return 0 if rv and lv else 1

if __name__=='__main__': raise SystemExit(main())
