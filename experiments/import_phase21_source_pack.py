#!/usr/bin/env python3
"""Import a rights-reviewed Phase-21 source pack and freeze exact source locks.

The source pack may be a directory or ZIP containing files named either
``OBJECT_ID.dat`` or ``OBJECT_ID.complete.dat``.  Accepted files are copied
atomically to the paths frozen in the Phase-21 cohort manifest.  The receipt is
safe to redistribute; the third-party source bytes are not.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from derd.harmonic_extraction import git_blob_sha1_file
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase09 import count_observations


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('source_pack')
    ap.add_argument('--root',default='.')
    ap.add_argument('--acknowledge-rights-and-attribution',action='store_true')
    args=ap.parse_args()
    if not args.acknowledge_rights_and_attribution:
        raise SystemExit('explicit --acknowledge-rights-and-attribution is required')
    root=Path(args.root).resolve()
    cohort=json.loads((root/'data/manifests/phase21_development_cohort.json').read_text())
    source=Path(args.source_pack).resolve()
    with tempfile.TemporaryDirectory(prefix='phase21-source-') as td:
        stage=Path(td)
        if source.is_dir():
            for p in source.rglob('*'):
                if p.is_file(): shutil.copy2(p, stage/p.name)
        elif zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as z: z.extractall(stage)
        else:
            raise SystemExit('source pack must be a directory or ZIP')
        candidates={p.name:p for p in stage.rglob('*') if p.is_file()}
        records=[]
        for row in cohort['targets']:
            oid=row['object_id']
            candidate=None
            for name in (f'{oid}.complete.dat',f'{oid}.dat'):
                if name in candidates: candidate=candidates[name]; break
            rec={
                'object_id':oid,
                'source_repository':row['source_repository'],
                'source_commit':row['source_commit'],
                'source_repository_path':row['source_repository_path'],
                'source_git_blob_sha1':row['source_git_blob_sha1'],
                'source_byte_count':row['source_byte_count'],
                'source_observation_count':row['source_observation_count'],
                'source_sha256':None,
                'status':'PENDING_SOURCE_BYTES',
            }
            if candidate is not None:
                actual_sha=sha256(candidate)
                checks={
                    'bytes':candidate.stat().st_size==int(row['source_byte_count']),
                    'observations':count_observations(candidate)==int(row['source_observation_count']),
                    'git_blob':git_blob_sha1_file(candidate)==row['source_git_blob_sha1'],
                    'manifest_sha':row.get('source_sha256') in (None,'') or actual_sha==row.get('source_sha256'),
                }
                rec['checks']=checks
                rec['source_sha256']=actual_sha
                if all(checks.values()):
                    dest=root/row['source_relative_path']; dest.parent.mkdir(parents=True,exist_ok=True)
                    temp=dest.with_suffix(dest.suffix+'.tmp')
                    shutil.copyfile(candidate,temp); temp.replace(dest)
                    rec['status']='VERIFIED_AND_FROZEN'
                else:
                    rec['status']='REJECTED_SOURCE_COORDINATE_MISMATCH'
            rec['record_sha256']=canonical_json_sha256(rec)
            records.append(rec)
    receipt={
        'receipt_id':'DERD-PHASE21-SOURCE-ACQUISITION-RECEIPT-1.0',
        'cohort_manifest_sha256':cohort['sha256_canonical_json'],
        'rights_and_attribution_acknowledged':True,
        'targets':records,
        'verified_count':sum(r['status']=='VERIFIED_AND_FROZEN' for r in records),
    }
    receipt['sha256_canonical_json']=canonical_json_sha256(receipt)
    out=root/'artifacts/phase21/phase21_source_acquisition_receipt.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'receipt':str(out),'verified_count':receipt['verified_count']},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
