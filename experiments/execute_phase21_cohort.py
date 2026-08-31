#!/usr/bin/env python3
"""Execute the frozen Phase-21 15-object cohort after every input gate passes."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from derd.harmonic_exchange import write_harmonic_exchange
from derd.ogle_catalog import canonical_json_sha256
from derd.validation_phase07 import Phase07Config
from derd.validation_phase08 import Phase08Config, Phase08Target, assess_cohort
from derd.validation_phase09 import wilson_interval
from derd.validation_phase21 import assess_phase21


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.'); ap.add_argument('--fast',action='store_true'); args=ap.parse_args()
    root=Path(args.root).resolve()
    assessment=assess_phase21(root=root)
    if not assessment.execution_inputs_ready:
        raise SystemExit('Phase-21 execution inputs are not ready; inspect artifacts/phase21/phase21_summary.json')
    cohort=json.loads((root/'data/manifests/phase21_development_cohort.json').read_text())
    receipt=json.loads((root/'artifacts/phase21/phase21_source_acquisition_receipt.json').read_text())
    receipt_by_id={r['object_id']:r for r in receipt['targets']}
    readiness={r.object_id:r for r in assessment.targets}
    config=Phase07Config(synthetic_samples_per_class=96,propagation_draws=2048,observation_sweep_counts=(),observation_sweep_repetitions=1,minimum_observations=240,period_grid_count=101)
    if args.fast: config=replace(config,synthetic_samples_per_class=24,propagation_draws=256,period_grid_count=51)
    targets=[]
    for row in cohort['targets']:
        ready=readiness[row['object_id']]; receipt_row=receipt_by_id[row['object_id']]
        sha=row.get('source_sha256') or receipt_row.get('source_sha256')
        targets.append(Phase08Target(
            object_id=row['object_id'], family=row['family'], mode=ready.effective_mode,
            catalog_period_days=ready.effective_period_days,
            period_evidence_grade='EXTERNAL_CATALOG_PHASE21_AUTHORITATIVE' if row['family']=='delta_scuti' else row['period_evidence_grade'],
            source_relative_path=row['source_relative_path'], source_repository_path=row['source_repository_path'],
            source_git_blob_sha1=row['source_git_blob_sha1'], source_sha256=sha,
            source_byte_count=row['source_byte_count'], source_repository=row['source_repository'],
            source_commit=row['source_commit'], period_source='Phase21 authoritative metadata lock' if row['family']=='delta_scuti' else row['period_source'],
            evidence_role='exposed-development-only',
        ))
    result=assess_cohort(targets,root=root,config=Phase08Config(target_config=config,minimum_objects_per_family_for_population_inference=5,minimum_total_objects_for_population_inference=15))
    out=root/'artifacts/phase21/fresh_execution'; out.mkdir(parents=True,exist_ok=True)
    records=[]
    for item in result.targets:
        exchange=item.result.harmonic_fit.to_exchange(object_id=item.target.object_id,time_unit='day',value_unit='relative_flux',source_locator=item.target.source_locator,source_sha256=item.target.source_sha256,metadata={'phase':'21','family':item.target.family,'mode':item.target.mode,'physical_claim_scope':'waveform-only'})
        write_harmonic_exchange(out/f'{item.target.object_id}.json',exchange)
        records.append({'object_id':item.target.object_id,'family':item.target.family,'stage_reached':item.stage_reached,'disposition':item.disposition,'target_result':item.as_dict(include_controls=False)})
    families=[]
    for row in result.family_summary:
        n=int(row['object_count']); item=dict(row)
        for label,key in [('recovery','recovery_ready_count'),('forecast','forecast_measured_count'),('structural','structurally_compatible_count'),('qualified','qualified_count')]:
            k=int(row[key]); low,high=wilson_interval(k,n); item[f'{label}_fraction']=k/n; item[f'{label}_wilson95_low']=low; item[f'{label}_wilson95_high']=high
        families.append(item)
    payload={'implementation_id':'DERD-v2.1-phase21-authoritative-dsct-pilot','status':'COMPLETE_15_OBJECT_DEVELOPMENT_COHORT_EXECUTED','records':records,'family_outputs':families,'c17_promoted':False,'physical_claim_scope':'waveform-only development evidence'}
    payload['sha256_canonical_json']=canonical_json_sha256(payload)
    (root/'artifacts/phase21/phase21_fresh_results.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'records':len(records),'families':families,'sha256':payload['sha256_canonical_json']},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
