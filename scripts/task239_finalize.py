#!/usr/bin/env python3
"""Finalize private receipts from existing preflight artifacts; no model calls."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import digest, object_hash


def main() -> None:
    paths=resolve_paths();repo=Path(__file__).resolve().parents[1]
    run=paths.project_runs_dir/'task-2_39-modern-el-stability-z790-preflight'
    config=repo/'configs/modern_models_task239.json';cfg=json.loads(config.read_text())
    keys=json.loads((run/'common_coverage_row_keys.json').read_text())
    if len(keys)!=7788 or object_hash(keys)!=cfg['cohort']['ordered_keys_sha256']:
        raise ValueError('Common coverage changed')
    for file in ['coverage.jsonl','exposure_flags.jsonl']+[f'{s}_{p}_overlap.jsonl' for s in ['s2','s3'] for p in ['train','val','test']]:
        rows=[json.loads(line) for line in (run/file).read_text().splitlines()]
        if [r['source_id'] for r in rows]!=keys:raise ValueError('Artifact row alignment mismatch: '+file)
    smoke={m:json.loads((run/(m+'_public_smoke.json')).read_text()) for m in ['mix','spearmint']}
    if any(v['status']!='PASS' or not v['public_only'] for v in smoke.values()):raise ValueError('Smoke gate failed')
    access=json.loads((run/'scientific_file_access.json').read_text())
    if access['historical_reads']!=[cfg['cohort']['relative_path']]:raise ValueError('Unexpected historical file read')
    summary=json.loads((run/'coverage_summary.json').read_text())
    if summary['cohort_predictions_generated'] or summary['outcome_columns_accessed']:raise ValueError('Scope violation')
    for source,dest in [(config,run/'frozen_configuration.json'),
                        (repo/'configs/task239_input_output_contracts.json',run/'frozen_input_output_contracts.json'),
                        (repo/'docs/FROZEN_MIX_SPEARMINT_EVALUATION_PROTOCOL_TASK2_39.md',run/'frozen_evaluation_protocol.md')]:
        dest.write_bytes(source.read_bytes())
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    branch=git('branch','--show-current')
    if branch!='task/2.39-modern-el-stability-z790-preflight':raise ValueError('Wrong task branch')
    # Check the untouched historical worktree without switching or modifying it.
    historical=paths.repos_root/'stability-label-curation'
    original_head=subprocess.check_output(['git','-C',str(historical),'rev-parse','HEAD'],text=True).strip()
    original_status=subprocess.check_output(['git','-C',str(historical),'status','--porcelain'],text=True).strip()
    if original_head!=cfg['base_commit'] or original_status:raise ValueError('Historical worktree changed')
    receipt={'task':'2.39','utc':datetime.now(timezone.utc).isoformat(),'branch':branch,
        'base_commit':cfg['base_commit'],'final_commit':git('rev-parse','HEAD'),
        'worktree_status':git('status','--porcelain'),
        'historical_worktree':{'head':original_head,'clean':not original_status},
        'model_pins':{'mix':cfg['mix'],'spearmint':cfg['spearmint']},
        'configuration_sha256':digest(config),
        'configuration_files': {p.name: digest(p) for p in sorted((repo/'configs').glob('*task239*')) if p.is_file()},
        'protocol_sha256':digest(repo/'docs/FROZEN_MIX_SPEARMINT_EVALUATION_PROTOCOL_TASK2_39.md'),
        'common_coverage_rows':len(keys),'ordered_keys_sha256':object_hash(keys),
        'common_coverage_row_keys_file':'common_coverage_row_keys.json',
        'mac_byte_verification':False,'security_status':{'mix':'PASS','spearmint':'PASS'},
        'technical_decision':'GO for separately requested exploratory Task 2.40; no untouched/leakage-free ancestry claim',
        'unresolved':['MINT Stage1 BA complete identities','MINT PPI complete identities','MixMHCpred EL complete training identities','complete S2/S3 study/donor linkage','upstream IM-blind model-selection history','Mac artifact byte-equivalence'],
        'tests':json.loads((run/'focused_tests.json').read_text()),
        'reproducibility':json.loads((run/'reproducibility_check.json').read_text()),
        'benchmark_inference':False,'IM_outcome_access':False,'IM_metrics':False,
        'training_or_tuning':False,'Task240_started':False,
        'artifact_sha256':{p.name:digest(p) for p in sorted(run.iterdir()) if p.is_file() and p.name!='final_receipt.json'}}
    (run/'final_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print('Receipt finalized; common coverage 7788, historical worktree clean, no IM inference')


if __name__=='__main__':main()
