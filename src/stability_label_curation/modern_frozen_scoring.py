"""Task 2.40 Stage A: outcome-inaccessible frozen local inference and sealing.

No evaluation/metric/outcome module is imported. All scientific historical reads
are allowlisted Task 2.39 artifacts; other project data/run reads are denied.
"""
from __future__ import annotations
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from collections import Counter

from .paths import resolve_paths
from .modern_model_preflight import (
    IDENTITY_FIELDS, digest, object_hash, verify_digest, valid_ninemer, mix_allele,
    parse_mix, assay_contract, fixed_fusion,
)

RUN='task-2_40-frozen-el-stability-im-evaluation'
PARENT='task-2_39-modern-el-stability-z790-preflight'
COLUMNS=('mix_el_native','spearmint_spa37_log1p_half_life','mix_el_rank','stability_rank','fusion_rank_50_50')


def utc() -> str:return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')

def write_rows(path: Path, rows: list[dict]) -> None:
    with path.open('x') as stream:
        for row in rows:stream.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')

def read_rows(path: Path) -> list[dict]:
    with path.open() as stream:return [json.loads(line) for line in stream]

def git(repo: Path,*args: str) -> str:
    return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()

def config() -> tuple:
    paths=resolve_paths();repo=paths.repository_root
    cfg=json.loads((repo/'configs/modern_frozen_im_task240.json').read_text())
    return paths,repo,cfg


def access_guard(paths, allowed: set[Path], audit: set[str]):
    run=paths.project_runs_dir/RUN;model=paths.project_data_dir/'modern_models_task2_39'
    def guard(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes)):return
        path=Path(args[0]).resolve()
        if path.is_relative_to(paths.project_runs_dir):
            if not path.is_relative_to(run) and path not in allowed:
                raise PermissionError('Stage A denies non-allowlisted historical scientific files')
            audit.add(str(path.relative_to(paths.project_runs_dir)))
        if path.is_relative_to(paths.project_data_dir) and not path.is_relative_to(model):
            raise PermissionError('Stage A denies other biological data')
    return guard


def context() -> tuple:
    paths,repo,cfg=config();parent=paths.project_runs_dir/PARENT;run=paths.project_runs_dir/RUN
    receipt_path=parent/'final_receipt.json'
    allowed={receipt_path}|{parent/n for n in cfg['parent_artifacts']}
    accessed=set();sys.addaudithook(access_guard(paths,allowed,accessed))
    verify_digest(receipt_path,cfg['parent_receipt_sha256'])
    receipt=json.loads(receipt_path.read_text())
    if receipt['final_commit']!=cfg['base_commit']:raise ValueError('Wrong parent commit')
    for n,h in cfg['parent_artifacts'].items():
        if receipt['artifact_sha256'][n]!=h:raise ValueError('Parent receipt binding mismatch')
        verify_digest(parent/n,h)
    rows=read_rows(parent/'IMPROVE_label_blind_identities.jsonl')
    keys=json.loads((parent/'common_coverage_row_keys.json').read_text())
    if (len(rows)!=7788 or [r['source_id'] for r in rows]!=keys or len(set(keys))!=7788
        or object_hash(keys)!=cfg['ordered_keys_sha256']):raise ValueError('Frozen identity alignment/count failed')
    for r in rows:
        if set(r)-(IDENTITY_FIELDS|{'peptide_length'}) or not valid_ninemer(r['peptide']):raise ValueError('Identity schema/input failed')
    if len({r['hla'] for r in rows})!=36 or len({r['patient_peptide_component'] for r in rows})!=38:raise ValueError('Coverage/components mismatch')
    seqs=json.loads((parent/'hla_full_length_references.json').read_text())
    for a in {r['hla'] for r in rows}:
        entry=seqs[a]
        if not entry['eligible'] or len(entry['sequence'])!=entry['length']:raise ValueError('Missing full HLA')
        import hashlib
        if hashlib.sha256(entry['sequence'].encode()).hexdigest()!=entry['sha256']:raise ValueError('Full HLA checksum mismatch')
    run.mkdir(parents=True,exist_ok=True)
    return paths,repo,cfg,parent,run,rows,seqs,accessed


def software_hashes(repo: Path,cfg: dict) -> dict:
    return {n:digest(repo/n) for n in cfg['scientific_files']}


def check_environment(repo: Path, model: str, old: dict) -> dict:
    key='mixmhcpred' if model=='mix' else 'spearmint'
    lock=repo/f'configs/task239_{key}.lock.txt';verify_digest(lock,old['dependency_locks'][key])
    versions={}
    for line in lock.read_text().splitlines():
        name,version=line.split('==',1);actual=importlib.metadata.version(name)
        if actual!=version:raise ValueError('Dependency drift: '+name)
        versions[name]=actual
    return {'python':sys.version,'prefix':sys.prefix,'packages':versions,'lock_sha256':digest(lock)}


def authenticate_model(paths,repo: Path,parent: Path,model: str) -> tuple:
    root=paths.project_data_dir/'modern_models_task2_39'
    old=json.loads((repo/'configs/modern_models_task239.json').read_text())
    security=json.loads((parent/'security_review.json').read_text())[model]
    if security['status']!='PASS':raise ValueError('Parent security gate failed')
    env=check_environment(repo,model,old)
    for rel,h in security['runtime_files'].items():verify_digest(root/rel,h)
    if model=='mix':verify_digest(root/'mix_v3.0.tar.gz',old['mix']['archive_sha256'])
    else:
        hf=root/'spearmint_stage3'/old['spearmint']['revision']
        verify_digest(hf/'model.safetensors',old['spearmint']['weights_sha256'])
        if (hf/'pytorch_model.bin').exists():raise ValueError('Forbidden pickle path')
    return root,old,env


def prepare() -> None:
    paths,repo,cfg,parent,run,rows,seqs,accessed=context()
    if git(repo,'status','--porcelain'):raise ValueError('Commit scientific implementation before scoring')
    flags=read_rows(parent/'exposure_flags.jsonl')
    excluded=sensitivity_exclusions(rows,flags)
    write_json(run/'sensitivity_excluded_row_keys.json',excluded)
    write_json(run/'input_receipt.json',{'utc':utc(),'code_commit':git(repo,'rev-parse','HEAD'),
        'identity_sha256':cfg['parent_artifacts']['IMPROVE_label_blind_identities.jsonl'],
        'common_coverage_sha256':cfg['parent_artifacts']['common_coverage_row_keys.json'],
        'ordered_keys_sha256':object_hash([r['source_id'] for r in rows]),'rows':len(rows),'HLA':len(seqs),
        'components':38,'sensitivity_exclusions':len(excluded),'sensitivity_keys_sha256':object_hash(excluded),
        'scientific_hashes':software_hashes(repo,cfg),'IM_outcomes_accessed':False})
    print('Input preflight PASS: 7788 rows, 36 HLA, 38 components, fixed eight-row sensitivity')


def sensitivity_exclusions(rows: list[dict],flags: list[dict],expected: int=8) -> list[str]:
    if [r['source_id'] for r in flags]!=[r['source_id'] for r in rows]:raise ValueError('Exposure flag alignment mismatch')
    result=[r['source_id'] for r in flags if any(r['exposure'][s]['min_hamming'] is not None
             and r['exposure'][s]['min_hamming']<=2 for s in ('s2_train','s3_train'))]
    if len(result)!=expected:raise ValueError('Wrong prespecified neighbor exclusion count')
    return result


def integrity(rows: list[dict],predictions: list[dict],column: str) -> None:
    keys=[r['source_id'] for r in rows]
    if len(keys)!=len(set(keys)) or [r['source_id'] for r in predictions]!=keys:raise ValueError('Duplicate/missing/reordered predictions')
    for r,p in zip(rows,predictions,strict=True):
        if r['peptide']!=p['peptide'] or r['hla']!=p['hla'] or not math.isfinite(p[column]):raise ValueError('Prediction mapping/finite gate failed')


def predict(model_name: str) -> None:
    paths,repo,cfg,parent,run,rows,seqs,accessed=context()
    if git(repo,'status','--porcelain'):raise ValueError('Dirty scientific worktree before prediction')
    inp=json.loads((run/'input_receipt.json').read_text())
    if inp['scientific_hashes']!=software_hashes(repo,cfg):raise ValueError('Scientific implementation changed')
    marker=run/f'{model_name}_started.json';out=run/f'{model_name}_native.jsonl'
    if marker.exists() or out.exists():raise FileExistsError('One-time model invocation already started; preserve evidence')
    root,old,env=authenticate_model(paths,repo,parent,model_name)
    write_json(marker,{'utc':utc(),'code_commit':git(repo,'rev-parse','HEAD'),'label_access':False})
    start=time.monotonic();details={};predictions=[]
    if model_name=='mix':
        mix=root/'mix_release'/('MixMHCpred-'+old['mix']['revision'])
        process_env={**os.environ,'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH']}
        by_id={}
        for a in sorted({r['hla'] for r in rows}):
            subset=[r for r in rows if r['hla']==a];name=mix_allele(a)
            file=run/f'mix_{name}_input.txt';file.write_text(''.join(r['peptide']+'\n' for r in subset))
            output=run/f'mix_{name}_output.tsv'
            if output.exists():raise FileExistsError(output.name)
            cmd=['bash',str(mix/'MixMHCpred'),'-i',str(file),'-o',str(output),'-a',name,'-m','0']
            c=subprocess.run(cmd,env=process_env,text=True,capture_output=True,check=True)
            (run/f'mix_{name}.log').write_text(c.stdout+c.stderr)
            result=parse_mix(output.read_text(),[r['peptide'] for r in subset],a)
            for r,p in zip(subset,result,strict=True):
                by_id[r['source_id']]={'source_id':r['source_id'],'peptide':r['peptide'],'hla':a,
                    'mix_el_native':p['native_score'],'published_percentile_rank':p['published_percentile_rank'],
                    'selected_column':p['selected_column']}
            print('Mix',a,len(subset),'PASS',flush=True)
        predictions=[by_id[r['source_id']] for r in rows];column='mix_el_native'
        details={'designated_HLA_only':True,'groups':36,'negative_score_values_retained':True}
    else:
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        import torch
        hf=root/'spearmint_stage3'/old['spearmint']['revision'];sys.path.insert(0,str(hf))
        import modeling_spearmint as upstream
        def forbidden(*args,**kwargs):raise RuntimeError('Remote snapshot/pickle fallback forbidden')
        upstream.torch_load=forbidden
        import huggingface_hub
        huggingface_hub.snapshot_download=forbidden
        torch.manual_seed(239);torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        tokenizer=upstream.SpearmintTokenizer();assay,temp=assay_contract(tokenizer.ASSAY_TYPES)
        model=upstream.SpearmintForStabilityPrediction.from_pretrained(str(hf),local_files_only=True).to('cuda').eval()
        assay_contract(model.config.assay_types)
        model.requires_grad_(False)
        versions_before=[p._version for p in model.parameters()]
        if any(m.training for m in model.modules()) or any(p.requires_grad for p in model.parameters()):raise ValueError('Model evaluation/frozen gate')
        max_difference=0.0
        for begin in range(0,len(rows),4):
            batch=rows[begin:begin+4]
            items=tokenizer.prepare_batch([r['peptide'] for r in batch],[seqs[r['hla']]['sequence'] for r in batch],
                                         assays=['SPA']*len(batch),temperatures_c=[37.0]*len(batch))
            if items[2].tolist()!=[assay]*len(batch) or items[3].tolist()!=[temp]*len(batch):raise ValueError('Assay/temperature drift')
            for i,r in enumerate(batch):
                first=len(r['peptide'])+2;total=first+len(seqs[r['hla']]['sequence'])+2
                if (items[1][i,:first].tolist()!=[0]*first or
                    items[1][i,first:total].tolist()!=[1]*(total-first) or
                    int(items[0][i,0])!=model.esm.cls_idx or
                    int(items[0][i,first-1])!=model.esm.eos_idx or
                    int(items[0][i,first])!=model.esm.cls_idx or
                    int(items[0][i,total-1])!=model.esm.eos_idx):
                    raise ValueError('Original chain/token representation mismatch')
            with torch.inference_mode():scores=model(*(x.cuda() for x in items))['logits'].detach().cpu().flatten()
            if not torch.isfinite(scores).all() or len(scores)!=len(batch):raise ValueError('SPEARMINT finite/alignment gate')
            # Fixed first four original rows, chosen before any outcomes, as a
            # permitted label-blind single/batch reproducibility subset.
            if begin==0:
                with torch.inference_mode():repeat=model(*(x.cuda() for x in items))['logits'].detach().cpu().flatten()
                if not torch.equal(scores,repeat):raise ValueError('Non-deterministic fixed batch')
                for r,value in zip(batch,scores,strict=True):
                    single=tokenizer.prepare_input(r['peptide'],seqs[r['hla']]['sequence'],assay='SPA',temperature_c=37.0)
                    with torch.inference_mode():one=model(single[0].unsqueeze(0).cuda(),single[1].unsqueeze(0).cuda(),single[2].cuda(),single[3].cuda())['logits'].detach().cpu().flatten()[0]
                    torch.testing.assert_close(value,one,atol=old['smoke']['single_batch_atol'],rtol=old['smoke']['single_batch_rtol'])
                    max_difference=max(max_difference,float(abs(value-one)))
            for r,s in zip(batch,scores.tolist(),strict=True):
                predictions.append({'source_id':r['source_id'],'peptide':r['peptide'],'hla':r['hla'],'spearmint_spa37_log1p_half_life':s})
            if begin%400==0:print('SPEARMINT',begin+len(batch),'/',len(rows),flush=True)
        if versions_before!=[p._version for p in model.parameters()]:raise ValueError('Model parameter mutation detected')
        verify_digest(hf/'model.safetensors',old['spearmint']['weights_sha256'])
        column='spearmint_spa37_log1p_half_life'
        details={'assay':'SPA','assay_index':assay,'temperature_C':temp,'batch_size':4,'precision':'FP32',
                 'eval_mode':True,'requires_grad':False,'parameter_versions_unchanged':True,'repeat_batch_identical':True,
                 'single_batch_max_difference_first_four':max_difference,'device':torch.cuda.get_device_name(),
                 'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_GPU_reserved_bytes':torch.cuda.max_memory_reserved()}
    integrity(rows,predictions,column);write_rows(out,predictions)
    write_json(run/f'{model_name}_execution.json',{'status':'PASS','utc':utc(),'rows':len(predictions),'failed':0,
        'output_sha256':digest(out),'score_column':column,'orientation':'higher','seconds':time.monotonic()-start,
        'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'CPU_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime,
        'environment':env,'details':details,'scientific_files_accessed':sorted(accessed),'outcomes_accessed':False,
        'scientific_hashes':software_hashes(repo,cfg)})
    print(model_name,'prediction freeze',len(predictions),'PASS',flush=True)


def seal() -> None:
    paths,repo,cfg,parent,run,rows,seqs,accessed=context()
    if (run/'prediction_freeze.json').exists():raise FileExistsError('Predictions already sealed')
    a=read_rows(run/'mix_native.jsonl');b=read_rows(run/'spearmint_native.jsonl')
    integrity(rows,a,COLUMNS[0]);integrity(rows,b,COLUMNS[1])
    for name in ['mix','spearmint']:
        receipt=json.loads((run/f'{name}_execution.json').read_text())
        verify_digest(run/f'{name}_native.jsonl',receipt['output_sha256'])
        if receipt['scientific_hashes']!=software_hashes(repo,cfg):raise ValueError('Scientific code drift')
    el,st,fusion=fixed_fusion([r[COLUMNS[0]] for r in a],[r[COLUMNS[1]] for r in b],[r['hla'] for r in rows])
    table=[{**r,COLUMNS[0]:x[COLUMNS[0]],COLUMNS[1]:y[COLUMNS[1]],COLUMNS[2]:e,COLUMNS[3]:s,COLUMNS[4]:f}
           for r,x,y,e,s,f in zip(rows,a,b,el,st,fusion,strict=True)]
    write_rows(run/'frozen_scores.jsonl',table)
    write_rows(run/'rank_scores.jsonl',[{'source_id':r['source_id'],COLUMNS[2]:r[COLUMNS[2]],COLUMNS[3]:r[COLUMNS[3]]} for r in table])
    write_rows(run/'fusion_scores.jsonl',[{'source_id':r['source_id'],COLUMNS[4]:r[COLUMNS[4]]} for r in table])
    write_json(run/'label_free_score_relationships.json',score_relationships(table))
    excluded=json.loads((run/'sensitivity_excluded_row_keys.json').read_text())
    if excluded!=sensitivity_exclusions(rows,read_rows(parent/'exposure_flags.jsonl')):raise ValueError('Sensitivity mask drift')
    artifacts=['mix_native.jsonl','spearmint_native.jsonl','rank_scores.jsonl','fusion_scores.jsonl','frozen_scores.jsonl','sensitivity_excluded_row_keys.json','input_receipt.json','mix_execution.json','spearmint_execution.json','label_free_score_relationships.json']
    old=json.loads((repo/'configs/modern_models_task239.json').read_text())
    write_json(run/'prediction_freeze.json',{'status':'SEALED_BEFORE_IM_OUTCOMES','utc':utc(),
        'score_code_commit':git(repo,'rev-parse','HEAD'),'rows':len(table),'failed_predictions':0,
        'identity_manifest_sha256':cfg['parent_artifacts']['IMPROVE_label_blind_identities.jsonl'],
        'common_manifest_sha256':cfg['parent_artifacts']['common_coverage_row_keys.json'],
        'ordered_keys_sha256':object_hash([r['source_id'] for r in table]),
        'HLA_reference_file_sha256':cfg['parent_artifacts']['hla_full_length_references.json'],
        'HLA_sequence_hashes':{a:v['sha256'] for a,v in seqs.items()},'model_artifacts':{'mix':old['mix'],'spearmint':old['spearmint']},
        'columns':COLUMNS,'direction':'higher','fusion':[0.5,0.5],'ranks':'Task239 unchanged within-HLA observation-weighted midrank',
        'artifact_sha256':{n:digest(run/n) for n in artifacts},'scientific_hashes':software_hashes(repo,cfg),
        'labels_accessed':False,'outcome_access_permitted_only_after_pre_evaluation_commit':True})
    print('All 7788 native/rank/fusion rows SEALED; outcomes remain inaccessible')


def score_relationships(rows: list[dict]) -> dict:
    """Diagnostic only: never changes any frozen predictor or uses outcomes."""
    import numpy as np
    from .modern_model_preflight import within_hla_percentiles
    def ranks(values):
        count=Counter(values);lookup={};less=0
        for value,n in sorted(count.items()):lookup[value]=(less+0.5*n)/len(values);less+=n
        return [lookup[v] for v in values]
    def corr(a,b):
        if len(a)<2 or np.std(a)==0 or np.std(b)==0:return None
        return float(np.corrcoef(a,b)[0,1])
    def summarize(values):
        return {'minimum':min(values),'maximum':max(values),'mean':float(np.mean(values)),
                'quantiles':dict(zip(['0','10','25','50','75','90','100'],np.percentile(values,[0,10,25,50,75,90,100]).tolist()))}
    fusion_percentiles=within_hla_percentiles([r[COLUMNS[4]] for r in rows],[r['hla'] for r in rows])
    changes=[f-r[COLUMNS[2]] for f,r in zip(fusion_percentiles,rows,strict=True)]
    return {'labels_used':False,'overall_native_score_Spearman':corr(ranks([r[COLUMNS[0]] for r in rows]),ranks([r[COLUMNS[1]] for r in rows])),
        'pooled_within_HLA_rank_correlation':corr([r[COLUMNS[2]] for r in rows],[r[COLUMNS[3]] for r in rows]),
        'per_HLA_rank_correlation':{a:corr([r[COLUMNS[2]] for r in rows if r['hla']==a],[r[COLUMNS[3]] for r in rows if r['hla']==a]) for a in sorted({r['hla'] for r in rows})},
        'native_score_distributions':{c:summarize([r[c] for r in rows]) for c in COLUMNS[:2]},
        'fusion_induced_within_HLA_percentile_changes':{**summarize(changes),'increased':sum(x>0 for x in changes),'decreased':sum(x<0 for x in changes),'unchanged':sum(x==0 for x in changes)},
        'diagnostic_only':'Fusion percentile re-ranking characterizes displacement only; evaluation uses original arithmetic-mean fusion, never this diagnostic.'}
