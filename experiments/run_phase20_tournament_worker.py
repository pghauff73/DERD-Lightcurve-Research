#!/usr/bin/env python3
"""Isolated Phase-20 synthetic mechanism-tournament worker."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from derd.validation_phase20 import run_mechanism_tournament


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=int,default=30)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run_mechanism_tournament(cases_per_family=args.cases,sample_count=128,holdout_count=24,noise_sigma=0.012,seed=20260825)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result.as_dict(include_records=True),indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    print(args.output)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
