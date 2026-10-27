"""Task 2.41-B: physical positive-row filtering and authentic matched EL fits.

Imports/path resolution never write. Teacher ranks are read from the immutable
Task 2.31 ledger, never refitted/recomputed after filtering. No IM labels enter
preflight/training/inference.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import ast,csv,gzip,hashlib,io,json,math,os,platform,random,resource,subprocess,sys,time
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from .paths import resolve_paths
from . import bigmhc_el_positive_upweighting as prior
from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as baseline
from . import bigmhc_multiepoch as shared
from . import bigmhc_fully_trained_auxiliary as reuse
from . import el_stability_loss_adapter as binding
from .modern_model_preflight import digest,verify_digest,object_hash

RUN='task-2_41b-low-stability-hard-filtering'
BRANCH='task/2.41b-low-stability-hard-filtering'
CONFIG='configs/low_stability_hard_filter_task241b.json'
ARMS=('H','R1','R2','R3','R4','R5')
ALL=('A',)+ARMS
FIELDS=('prepared_row_index','source_row_id','hla','peptide','original_label')


def write_json(p: Path,v: Any) -> None:
    p.write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n')

def read_json(p: Path):return json.loads(p.read_text())

def git(repo: Path,*args: str) -> str:return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()

def setup():
    p=resolve_paths();c=read_json(p.repository_root/CONFIG);d=p.project_runs_dir/RUN
    return p,c,d

def scientific_hashes(p,c):return {name:digest(p.repository_root/name) for name in c['scientific_files']}

def stratum(row):return row['hla'],len(row['peptide'])


def select_exclusions(rows: list[dict], ranks: dict[str,Fraction], seeds: list[int]) -> tuple[dict,dict]:
    """R selection receives only eligible identities/strata and H's quotas, no scores."""
    if len({r['source_row_id'] for r in rows})!=len(rows):raise ValueError('Duplicate training identity')
    eligible=[r for r in rows if r['original_label']=='1' and r['source_row_id'] in ranks]
    groups=defaultdict(list)
    for r in eligible:groups[r['hla']].append(r)
    hard=[]
    for hla,group in sorted(groups.items()):
        hard.extend(r['source_row_id'] for r in sorted(group,key=lambda r:(ranks[r['source_row_id']],r['source_row_id']))[:len(group)//10])
    lookup={r['source_row_id']:r for r in rows};quota=Counter(stratum(lookup[i]) for i in hard)
    selections={'H':sorted(hard)}
    for i,seed in enumerate(seeds,1):selections[f'R{i}']=random_exclusions(eligible,quota,seed)
    original=Counter(stratum(r) for r in rows if r['original_label']=='1')
    for arm,ids in selections.items():
        if len(ids)!=len(set(ids)) or Counter(stratum(lookup[i]) for i in ids)!=quota:raise ValueError('Matched exclusion quota failed')
        if any(lookup[i]['original_label']!='1' or i not in ranks for i in ids):raise ValueError('Negative/missing-score exclusion prohibited')
        if any(original[s]-quota[s]<=0 for s in original):raise ValueError('An entire positive stratum disappears; stop without changing rule')
    return selections,{'eligible_positive':len(eligible),'missing_or_outside_positive':sum(r['original_label']=='1' for r in rows)-len(eligible),
        'excluded':len(hard),'excluded_fraction_of_all_positives':len(hard)/sum(r['original_label']=='1' for r in rows),
        'by_stratum':{f'{h}|{n}':{'original_positive':original[(h,n)],'excluded':quota[(h,n)],'remaining_positive':original[(h,n)]-quota[(h,n)]} for h,n in sorted(original)},
        'negative_excluded':0,'labels_changed':0,'rank_reference':'immutable unfiltered Task2.31 training positives','ranks_recomputed':False}


def random_exclusions(eligible: list[dict],quota: Counter,seed: int) -> list[str]:
    groups=defaultdict(list)
    for r in eligible:groups[stratum(r)].append(r['source_row_id'])
    rng=random.Random(seed);out=[]
    for s in sorted(groups):out.extend(rng.sample(sorted(groups[s]),quota[s]))
    return sorted(out)


def save_rows(path: Path,rows) -> None:
    with path.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=1,mtime=0) as gz,io.TextIOWrapper(gz,newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
        for row in rows:writer.writerow({k:row[k] for k in FIELDS})


def load_rows(path: Path) -> list[dict]:
    with gzip.open(path,'rt',newline='') as f:
        out=list(csv.DictReader(f))
    for r in out:r['prepared_row_index']=int(r['prepared_row_index'])
    return out


def row_fingerprints(rows):
    all_rows=hashlib.sha256();negatives=hashlib.sha256();counts=Counter()
    for r in rows:
        line=('\t'.join(str(r[k]) for k in FIELDS)+'\n').encode();all_rows.update(line)
        counts[str(r['original_label'])]+=1
        if str(r['original_label'])=='0':negatives.update(line)
    return {'ordered_rows_sha256':all_rows.hexdigest(),'ordered_negative_rows_sha256':negatives.hexdigest(),'classes':dict(counts)}


def load_parent(p,c):
    old=prior.configuration(p)
    source=p.project_runs_dir/'task-2_31-el-stability-positive-upweighting'
    verify_digest(source/'reports/output_manifest.json',c['task231_output_manifest_sha256'])
    manifest=read_json(source/'reports/output_manifest.json')['files_sha256']
    ledger=source/'processed/training_positive_weights.csv.gz'
    verify_digest(ledger,manifest['processed/training_positive_weights.csv.gz'])
    resolved=baseline.inputs(p,old)
    sidecar=binding.load_sidecar(resolved['positive_scores'],resolved['positive_score_manifest'])
    verify_digest(p.project_data_dir/'teacher-v0-recovered/checkpoints/teacher_model.json',old['model_sha256'])
    train,val,cohort=prior.populations(resolved,sidecar)
    with gzip.open(ledger,'rt',newline='') as f:records={r['source_row_id']:r for r in csv.DictReader(f)}
    for r in train:
        if r['original_label']=='1':
            x=records.get(r['source_row_id'])
            if not x or (x['peptide'],x['HLA'],int(x['prepared_row_index']))!=(r['peptide'],r['hla'],r['prepared_row_index']):raise ValueError('Frozen rank/source identity binding failed')
    if len(records)!=63053:raise ValueError('Frozen rank ledger coverage failed')
    base,checkpoint=prior.baseline_evidence(p,old)
    return old,resolved,base,checkpoint,train,val,cohort,records


def provenance_compatibility(p,c):
    """AST equality of the exact reused optimization/sampling/validation functions."""
    ref=c['training_reference_commit'];out={}
    checks={'src/stability_label_curation/bigmhc_baseline_runner.py':['train_epoch','seed_runtime','predict','save_checkpoint'],
            'src/stability_label_curation/bigmhc_multiepoch.py':['evaluate','preserve_rng'],
            'src/stability_label_curation/bigmhc_fully_trained_auxiliary.py':['native_dataset','encodings_for','reset_rng'],
            'src/stability_label_curation/bigmhc_el_multiepoch.py':['AuditedDataset']}
    for filename,names in checks.items():
        historical=subprocess.check_output(['git','-C',str(p.repository_root),'show',ref+':'+filename],text=True)
        def select(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names}
        if select(historical)!=select((p.repository_root/filename).read_text()):raise ValueError('Historical scientific function mismatch: '+filename)
        out[filename]=names
    return out


def preflight():
    import numpy as np,torch
    p,c,d=setup()
    if d.exists():raise FileExistsError('New task directory required')
    if git(p.repository_root,'status','--porcelain'):raise ValueError('Commit before preflight')
    compatibility=provenance_compatibility(p,c)
    old,resolved,base,checkpoint,train,val,cohort,records=load_parent(p,c)
    if object_hash(checkpoint['files'])!='d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1':raise ValueError('Wrong historical A EL checkpoint')
    ranks={i:Fraction(v['training_percentile_exact']) for i,v in records.items()}
    if any(not 0<=r<=1 for r in ranks.values()):raise ValueError('Frozen rank range invalid')
    selections,summary=select_exclusions(train,ranks,c['selection_seeds'])
    counts=Counter(r['original_label'] for r in train);kept_positive=counts['1']-summary['excluded']
    if (len(train),counts['1'],counts['0'],len(val))!=(1308196,63053,1245143,145371):raise ValueError('Original scientific cohort mismatch')
    runner.cuda_visibility();runner.seed_runtime(torch,np,old);device=runner.runtime_device(torch,old)
    runtime={'versions':{n:__import__('importlib.metadata',fromlist=['version']).version(n) for n in ('torch','numpy','pandas','psutil')},'device':runner.device_report(torch,device),'platform':platform.platform()}
    expected=read_json(base/'reports/execution_started.json')
    if any(runtime[k]!=expected[k] for k in ('versions','device')):raise ValueError('Historical baseline environment mismatch')
    initial=read_json(base/'reports/initial_EL_state.json');enc=reuse.encodings_for(torch,resolved['reference'])
    A_val=prior.saved_A_predictions(base,val)
    cohort32=p.project_runs_dir/'task-2_32-el-only-zero-shot-im'
    verify_digest(cohort32/'cohorts/IMPROVE_identities.jsonl',c['IM_identities_sha256'])
    identities=[json.loads(s) for s in (cohort32/'cohorts/IMPROVE_identities.jsonl').read_text().splitlines()]
    frozen=read_json(cohort32/'reports/predictions_frozen.json')['predictions']['IMPROVE_A']
    verify_digest(cohort32/'predictions/IMPROVE_A.jsonl',frozen['sha256'])
    A_im=[json.loads(s) for s in (cohort32/'predictions/IMPROVE_A.jsonl').read_text().splitlines()]
    if len(identities)!=7788 or [r['source_id'] for r in identities]!=[r['source_id'] for r in A_im]:raise ValueError('A IM predictions incompatible')
    from .el_only_zero_shot_im import native_dataset,encoding_map
    with runner.pinned_modules(resolved) as (BigMHC,Dataset):
        reuse.reset_rng(torch,np);model=runner.on_device(BigMHC(),device)
        if runner.state_hashes(model)!=initial['state'] or binding.rng_identity(torch,np)!=initial['RNG']:raise ValueError('Historical epoch-0 initialization differs')
        del model
        with shared.preserve_rng(torch,np):
            keys=read_json(base/'reports/EL_epoch_10.json')['updated_parameters']
            model=runner.load_checkpoint(torch,BigMHC,base/checkpoint['checkpoint'],keys,device=device,lineage=None)
            if runner.state_hashes(model)!=checkpoint['state']:raise ValueError('A EL checkpoint reload differs')
            probe,_=shared.evaluate(torch,model,reuse.native_dataset(Dataset,enc,val[:16]),device)
            if probe!=A_val[:16]:raise ValueError('A EL saved prediction pathway incompatible')
            encIM=encoding_map(torch,resolved['reference'],{r['hla'] for r in identities})
            batchset=native_dataset(Dataset,torch,encIM,identities[:16]);batchset.makebats(16,shuffle=False,negfrac=None)
            with torch.no_grad():
                batch=batchset[0];logits,_=model(batch.mhc.float().to(device),batch.pep.float().to(device));probs=torch.sigmoid(logits).cpu().tolist()
            if probs!=[r['EL_probability'] for r in A_im[:16]] or logits.cpu().tolist()!=[r['raw_EL_logit'] for r in A_im[:16]]:raise ValueError('A zero-shot sigmoid/logit pathway incompatible')
            del model
    d.mkdir();[(d/n).mkdir() for n in ['inputs','reports','logs','checkpoints','predictions','evaluation']]
    save_rows(d/'inputs/validation.csv.gz',val)
    fingerprints={};negative_hash=row_fingerprints(train)['ordered_negative_rows_sha256']
    for arm,ids in selections.items():
        excluded=set(ids);save_rows(d/f'inputs/{arm}_train.csv.gz',(r for r in train if r['source_row_id'] not in excluded))
        save_rows(d/f'inputs/{arm}_excluded.csv.gz',(r for r in train if r['source_row_id'] in excluded))
        expected=row_fingerprints(r for r in train if r['source_row_id'] not in excluded)
        with gzip.open(d/f'inputs/{arm}_train.csv.gz','rt',newline='') as stream:actual=row_fingerprints(csv.DictReader(stream))
        if expected!=actual or actual['ordered_negative_rows_sha256']!=negative_hash:raise ValueError('Materialized row-level/negative/label integrity failed')
        fingerprints[arm]=actual
    groups=defaultdict(list)
    for x in records.values():groups[x['HLA']].append(Decimal(x['Teacher_half_life_hours']))
    stab={a:{'n':len(v),'min_hours':float(min(v)),'max_hours':float(max(v)),'median_hours':float(sorted(v)[len(v)//2]),'removed':sum(1 for i in selections['H'] if records[i]['HLA']==a)} for a,v in groups.items()}
    write_json(d/'reports/stability_distribution.json',stab)
    write_json(d/'inputs/initialization.json',initial);write_json(d/'inputs/A_checkpoint.json',checkpoint)
    write_json(d/'inputs/IM_identities.json',identities)
    # Copy only authenticated label-free A scores, not prior metric/outcome files.
    write_json(d/'inputs/A_IM_predictions.json',A_im);write_json(d/'inputs/A_EL_probabilities.json',A_val)
    summary.update(original_positive=63053,original_negative=1245143,retained_positive=kept_positive,retained_negative=1245143,
        retained_total=len(train)-summary['excluded'],cohort=cohort,Teacher_score_coverage=63053,Teacher_checkpoint_sha256=old['model_sha256'],
        A_reused=True,A_checkpoint_map_sha256=hashlib.sha256(json.dumps(checkpoint['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        baseline_initialization_and_EL_IM_probe_bitwise_compatible=True,original_native_function_AST_equal=compatibility,
        no_IM_labels_opened=True,training_stability_weighting=False,validation_fixed=True,EL_validation_n=len(val))
    write_json(d/'reports/preflight_summary.json',summary)
    write_json(d/'reports/row_integrity.json',fingerprints)
    write_json(d/'reports/runtime.json',runtime)
    write_json(d/'reports/preflight.json',{'status':'PASS','scientific_hashes':scientific_hashes(p,c),
        'input_sha256':{str(f.relative_to(d)):digest(f) for f in (d/'inputs').iterdir() if f.is_file()},'summary':summary})
    print(json.dumps({k:summary[k] for k in ['excluded','excluded_fraction_of_all_positives','retained_positive','retained_negative','retained_total','no_IM_labels_opened']},indent=2),flush=True)


def require():
    p,c,d=setup();proof=read_json(d/'reports/preflight.json')
    if proof['status']!='PASS' or proof['scientific_hashes']!=scientific_hashes(p,c):raise ValueError('Scientific configuration changed after preflight')
    ready=read_json(p.repository_root/'configs/low_stability_hard_filter_task241b.ready.json')
    verify_digest(d/'reports/preflight.json',ready['preflight_sha256'])
    if git(p.repository_root,'status','--porcelain') or git(p.repository_root,'branch','--show-current')!=BRANCH:raise ValueError('Clean authorized branch required')
    return p,c,d,proof


def train(arm: str):
    import numpy as np,torch
    p,c,d,proof=require()
    if arm not in ARMS or (d/f'reports/{arm}_started.json').exists():raise ValueError('Unplanned/repeated fit')
    old=prior.configuration(p);resolved=baseline.inputs(p,old)
    for name in [f'inputs/{arm}_train.csv.gz','inputs/validation.csv.gz','inputs/initialization.json']:
        verify_digest(d/name,proof['input_sha256'][name])
    rows=load_rows(d/f'inputs/{arm}_train.csv.gz');val=load_rows(d/'inputs/validation.csv.gz')
    runner.cuda_visibility();runner.seed_runtime(torch,np,old);device=runner.runtime_device(torch,old);enc=reuse.encodings_for(torch,resolved['reference'])
    initial=read_json(d/'inputs/initialization.json');start=time.monotonic()
    write_json(d/f'reports/{arm}_started.json',{'commit':git(p.repository_root,'rev-parse','HEAD'),'arm':arm,'training_seed':42,'IM_training':False,'rows':len(rows),'scientific_hashes':scientific_hashes(p,c)})
    with runner.pinned_modules(resolved) as (BigMHC,Dataset):
        reuse.reset_rng(torch,np);model=runner.on_device(BigMHC(),device)
        if runner.state_hashes(model)!=initial['state'] or binding.rng_identity(torch,np)!=initial['RNG']:raise ValueError('Initial backbone/RNG mismatch')
        native=baseline.AuditedDataset(reuse.native_dataset(Dataset,enc,rows),[r['prepared_row_index'] for r in rows])
        val_native=reuse.native_dataset(Dataset,enc,val)
        optimizer=torch.optim.AdamW(model.parameters(),lr=old['learning_rate']);cumulative=0;curve=[];torch.cuda.reset_peak_memory_stats()
        for epoch in range(1,11):
            before=binding.rng_identity(torch,np);epoch_start=time.monotonic()
            training=runner.train_epoch(torch,model,native,old,False,device,loss_adapter=None,optimizer=optimizer)
            after=binding.rng_identity(torch,np);cumulative+=training['optimization_steps']
            expected=proof['summary']['retained_positive']
            if training['optimization_steps']!=expected or training['optimizer_class_exposures']!={'1':expected,'0':16*expected}:raise ValueError('Native positive-anchor sampling counts differ')
            if len(shared.optimizer_steps(optimizer))!=36 or any(s!=cumulative for s in shared.optimizer_steps(optimizer)):raise ValueError('Optimizer continuity failed')
            with shared.preserve_rng(torch,np):prob,bce=shared.evaluate(torch,model,val_native,device)
            metric={**baseline.el_metrics(val,prob),'validation_BCE':bce,'epoch':epoch,'arm':arm,'cumulative_optimizer_steps':cumulative,'epoch_seconds':time.monotonic()-epoch_start}
            training.update(epoch=epoch,RNG_before=before,RNG_after=after,cumulative_optimizer_steps=cumulative)
            write_json(d/f'reports/{arm}_EL_epoch_{epoch:02d}.json',training)
            write_json(d/f'reports/{arm}_EL_metrics_{epoch:02d}.json',metric);curve.append(metric)
            if epoch==10:write_json(d/f'predictions/{arm}_EL_validation.json',prob)
            print('EPOCH_COMPLETE',arm,epoch,'AP',metric['validation_AP'],'AUROC',metric['validation_AUROC'],flush=True)
        path=d/f'checkpoints/{arm}_EL_epoch_10';runner.reserve_checkpoint(path);runner.save_checkpoint(model,path,transfer=False,device=device)
        state=runner.state_hashes(model);keys=list(model.state_dict())
        with shared.preserve_rng(torch,np):
            loaded=runner.load_checkpoint(torch,BigMHC,path,keys,device=device,lineage=None)
            if runner.state_hashes(loaded)!=state:raise ValueError('Strict EL reload state mismatch')
            probe=reuse.native_dataset(Dataset,enc,val[:16]);a,_=shared.evaluate(torch,model,probe,device);b,_=shared.evaluate(torch,loaded,probe,device)
            if a!=b:raise ValueError('Reload prediction mismatch')
        write_json(d/f'reports/{arm}_training_completed.json',{'status':'COMPLETE','arm':arm,'epochs':10,'checkpoint':str(path.relative_to(d)),'files':runner.checkpoint_identity(path,keys),'state':state,'keys':keys,'strict_reload':True,
            'optimizer_steps':cumulative,'curve':curve,'seconds':time.monotonic()-start,'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_GPU_reserved_bytes':torch.cuda.max_memory_reserved(),
            'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'label_changes':0,'stability_weighting':False,'auxiliary_loss':False,'IM_training':False,'scientific_hashes':scientific_hashes(p,c)})
    print('FIT_COMPLETE',arm,flush=True)


def infer():
    """All models fixed first; no outcome source/config is opened here."""
    import numpy as np,torch
    from .el_only_zero_shot_im import native_dataset,encoding_map
    from .hard_filter_evaluation import valid_scores
    p,c,d,proof=require();start=time.monotonic()
    if (d/'reports/predictions_frozen.json').exists():raise ValueError('Predictions already frozen')
    for arm in ARMS:
        if not (d/f'reports/{arm}_training_completed.json').exists():raise ValueError('All six fits must complete before scoring')
    old=prior.configuration(p);resolved=baseline.inputs(p,old)
    for name in ['inputs/IM_identities.json','inputs/A_IM_predictions.json']:
        verify_digest(d/name,proof['input_sha256'][name])
    rows=read_json(d/'inputs/IM_identities.json');A=read_json(d/'inputs/A_IM_predictions.json');valid_scores(rows,A)
    receipts={'A':{'path':'inputs/A_IM_predictions.json','sha256':digest(d/'inputs/A_IM_predictions.json'),'reused':True,'n':len(A)}}
    runner.cuda_visibility();runner.seed_runtime(torch,np,old);device=runner.runtime_device(torch,old)
    enc=encoding_map(torch,resolved['reference'],{r['hla'] for r in rows})
    with runner.pinned_modules(resolved) as (BigMHC,Dataset):
        for arm in ARMS:
            receipt=read_json(d/f'reports/{arm}_training_completed.json');path=d/receipt['checkpoint']
            if runner.checkpoint_identity(path,receipt['keys'])!=receipt['files']:raise ValueError('Final checkpoint file identity differs')
            model=runner.load_checkpoint(torch,BigMHC,path,receipt['keys'],device=device,lineage=None);model.eval()
            if runner.state_hashes(model)!=receipt['state']:raise ValueError('Final checkpoint reload differs')
            native=native_dataset(Dataset,torch,enc,rows);native.makebats(16,shuffle=False,negfrac=None);out=[]
            with torch.no_grad():
                for i in range(len(native)):
                    b=native[i];logits,_=model(b.mhc.float().to(device),b.pep.float().to(device));probs=torch.sigmoid(logits)
                    ids=native.getbat(i,enc=False)['_source_id'].tolist()
                    out.extend({'source_id':k,'raw_EL_logit':z,'EL_probability':q} for k,z,q in zip(ids,logits.cpu().tolist(),probs.cpu().tolist(),strict=True))
            if [r['source_id'] for r in rows]!=[r['source_id'] for r in out]:raise ValueError('Native inference emitted wrong order')
            result=[{**r,**v} for r,v in zip(rows,out,strict=True)];valid_scores(rows,result)
            if runner.state_hashes(model)!=receipt['state']:raise ValueError('Inference changed checkpoint')
            output=d/f'predictions/{arm}_IMPROVE.json'
            if output.exists():raise FileExistsError(output)
            write_json(output,result);receipts[arm]={'path':str(output.relative_to(d)),'sha256':digest(output),'n':len(result),'reused':False}
            del model
    write_json(d/'reports/predictions_frozen.json',{'status':'PASS','predictions':receipts,'ordered_source_id_sha256':object_hash([r['source_id'] for r in rows]),
        'scientific_hashes':scientific_hashes(p,c),'IM_labels_opened':False,'score':'native_FP32_sigmoid_EL_logit','seconds':time.monotonic()-start})
    print('ALL_PREDICTIONS_FROZEN',flush=True)


def evaluate(*, reproduce=False):
    """The only entry point authorized to open IM outcomes, after score freeze."""
    import numpy as np
    from .hard_filter_evaluation import join,points,paired_bootstrap,class_diagnostics
    p,c,d,proof=require();frozen=read_json(d/'reports/predictions_frozen.json')
    if frozen['status']!='PASS' or frozen['scientific_hashes']!=scientific_hashes(p,c):raise ValueError('Frozen prediction gate failed')
    for r in frozen['predictions'].values():verify_digest(d/r['path'],r['sha256'])
    snapshot=read_json(d/'inputs/IM_identities.json');predictions={a:read_json(d/r['path']) for a,r in frozen['predictions'].items()}
    source=c['IM_outcomes'];path=p.project_runs_dir/source['run_id']/source['relative_path'];verify_digest(path,source['sha256'])
    labels=[json.loads(line) for line in path.read_text().splitlines()];rows=join(snapshot,predictions,labels)
    if (len(rows),sum(r['label'] for r in rows),len({r['patient_peptide_component'] for r in rows}))!=(7788,227,38):raise ValueError('Frozen outcome/class/component mismatch')
    result=points(rows)
    per_hla={h:points([r for r in rows if r['hla']==h]) for h in sorted({r['hla'] for r in rows})}
    val=load_rows(d/'inputs/validation.csv.gz');yp=[int(r['original_label']) for r in val];EL={}
    base=p.project_runs_dir/prior.configuration(p)['baseline_run_id']
    for a in ALL:
        probabilities=read_json(d/'inputs/A_EL_probabilities.json' if a=='A' else d/f'predictions/{a}_EL_validation.json')
        if len(probabilities)!=len(val) or any(not math.isfinite(v) or not 0<=v<=1 for v in probabilities):raise ValueError('EL validation integrity failed')
        source_metric=read_json(base/'reports/EL_metrics_10.json' if a=='A' else d/f'reports/{a}_EL_metrics_10.json')
        EL[a]={**baseline.el_metrics(val,probabilities),'validation_BCE':source_metric['validation_BCE'],'classes':class_diagnostics(yp,probabilities)}
    diagnostic={};H=read_json(d/'predictions/H_EL_validation.json');A=read_json(d/'inputs/A_EL_probabilities.json')
    for h,quota in proof['summary']['by_stratum'].items():
        hla,length=h.split('|');index=[i for i,r in enumerate(val) if r['hla']==hla and len(r['peptide'])==int(length) and r['original_label']=='1']
        im_index=[i for i,r in enumerate(snapshot) if r['hla']==hla and len(r['peptide'])==int(length)]
        diagnostic[h]={**quota,'EL_validation_positive_n':len(index),'mean_EL_positive_probability_change_H_minus_A':sum(H[i]-A[i] for i in index)/len(index) if index else None,
            'IM_identity_n':len(im_index),'mean_IM_probability_change_H_minus_A':sum(predictions['H'][i]['EL_probability']-predictions['A'][i]['EL_probability'] for i in im_index)/len(im_index) if im_index else None}
    aggregate={'IMPROVE':result,'IMPROVE_per_HLA':per_hla,'EL_validation':EL,'exclusion_prediction_diagnostics':diagnostic}
    dest=d/'evaluation/aggregate.json'
    if reproduce:
        if aggregate!=read_json(dest):raise ValueError('Saved-score aggregate reproduction mismatch')
        write_json(d/'reports/reproduction.json',{'status':'PASS','models_rerun':False,'aggregate_sha256':digest(dest),'score_receipt_sha256':digest(d/'reports/predictions_frozen.json')})
        print('AGGREGATE_REPRODUCTION_PASS',flush=True);return
    if dest.exists() or (d/'reports/evaluation_started.json').exists():raise ValueError('Evaluation already started')
    write_json(d/'reports/evaluation_started.json',{'pre_evaluation_commit':git(p.repository_root,'rev-parse','HEAD'),'prediction_receipt_sha256':digest(d/'reports/predictions_frozen.json'),'outcome_sha256':digest(path)})
    write_json(dest,aggregate)
    uncertainty=paired_bootstrap(rows,seed=c['bootstrap_seed'],draws=c['bootstrap_attempts'],evidence=d/'evaluation/paired_component_draws.jsonl.gz')
    write_json(d/'evaluation/paired_intervals.json',uncertainty)
    write_json(d/'reports/evaluation_completed.json',{'status':'COMPLETE','aggregate_sha256':digest(dest),'intervals_sha256':digest(d/'evaluation/paired_intervals.json'),
        'scientific_hashes':scientific_hashes(p,c),'IM_fitting':False,'model_selection':False})
    print(json.dumps({'IMPROVE':result},indent=2),flush=True)


def supervise():
    """Independent processes preserve each arm's original RNG/runtime policy."""
    p,c,d,proof=require()
    if (d/'reports/supervisor_started.json').exists():raise ValueError('Supervisor already started')
    if c['max_concurrent_fits']!=6:raise ValueError('Frozen execution concurrency differs')
    started=time.monotonic();children={};logs={}
    write_json(d/'reports/supervisor_started.json',{'commit':git(p.repository_root,'rev-parse','HEAD'),'concurrency':6,'independent_processes':True,'CPU_threads_per_fit':4})
    for a in ARMS:
        logs[a]=(d/f'logs/{a}_training.log').open('xb')
        children[a]=subprocess.Popen([sys.executable,'-m','stability_label_curation.low_stability_hard_filter','train',a],stdout=logs[a],stderr=subprocess.STDOUT)
    try:
        while any(child.poll() is None for child in children.values()):
            status={a:{'returncode':child.poll(),'completed_epochs':len(list((d/'reports').glob(a+'_EL_metrics_*.json')))} for a,child in children.items()}
            print(json.dumps({'elapsed_seconds':time.monotonic()-started,'arms':status}),flush=True)
            if any(child.poll() not in (None,0) for child in children.values()):
                # Preserve other authorized fits; do not restart or alter conditions.
                write_json(d/'reports/worker_failure.json',status)
            time.sleep(30)
        codes={a:child.returncode for a,child in children.items()}
        write_json(d/'reports/supervisor_completed.json',{'codes':codes,'seconds':time.monotonic()-started,'status':'PASS' if all(v==0 for v in codes.values()) else 'FAILED'})
        if any(codes.values()):raise RuntimeError('Worker failure: '+str(codes))
    finally:
        for log in logs.values():log.close()


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','train','supervise','infer','evaluate','reproduce']);parser.add_argument('arm',nargs='?',choices=ARMS)
    args=parser.parse_args()
    if args.action=='train':train(args.arm)
    elif args.action=='reproduce':evaluate(reproduce=True)
    else:globals()[args.action]()

if __name__=='__main__':main()
