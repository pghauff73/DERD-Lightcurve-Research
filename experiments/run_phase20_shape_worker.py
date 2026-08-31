#!/usr/bin/env python3
"""Isolated Phase-20 passband model-comparison worker."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from derd.harmonic_exchange import read_harmonic_exchange
from derd.validation_phase20 import compare_passband_shape_models


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--bootstrap-draws',type=int,default=64)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve()
    first=read_harmonic_exchange(root/'artifacts/phase14/harmonic_exchange/OGLE-LMC-CEP-0002.json')
    second=read_harmonic_exchange(root/'artifacts/phase20/harmonic_exchange/OGLE-LMC-CEP-0002_merged_v.json')
    result=compare_passband_shape_models(first,second,grid_size=256,bootstrap_draws=args.bootstrap_draws,seed=20260825)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result.as_dict(),indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    print(args.output)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
