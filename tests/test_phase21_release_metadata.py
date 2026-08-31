from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_phase21_protocol_and_seal_match():
    protocol=json.loads((ROOT/'research/preregistration/phase21_authoritative_dsct_pilot_protocol.json').read_text())
    seal=json.loads((ROOT/'research/preregistration/phase21_authoritative_dsct_pilot_protocol.seal.json').read_text())
    assert protocol['protocol_id']==seal['protocol_id']
    assert protocol['sha256_canonical_json']==seal['sha256_canonical_json']


def test_phase21_result_files_exist():
    required=[
        'artifacts/phase21/PHASE21_RESULT.md',
        'artifacts/phase21/phase21_summary.json',
        'artifacts/phase21/phase21_target_readiness.csv',
        'artifacts/phase21/phase21_family_coverage.csv',
        'artifacts/phase21/phase21_blockers.csv',
        'artifacts/phase21/phase21_period_coordinate_corrections.csv',
        'artifacts/phase21/phase21_execution_ledger.json',
        'artifacts/phase21/phase21_execution_ledger.seal.json',
    ]
    assert all((ROOT/path).is_file() for path in required)
