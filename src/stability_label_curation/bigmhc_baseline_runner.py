"""Bounded original-label BigMHC smoke runner; runtime dependencies are lazy."""
from collections import Counter
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import types
from typing import Mapping

from . import bigmhc_pilot_adapter as adapter
from . import bigmhc_v4_audit as data
from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from . import scientific_gate0_preflight as readers
from . import stability_teacher as teacher
from .paths import resolve_paths

CONFIG = 'configs/bigmhc_baseline_smoke_v0.json'
VERSION = 'bigmhc_baseline_smoke_v0'
WORKER_VERSION = 'bigmhc_gpu_worker_v0'
FULL_VERSION = 'bigmhc_gpu_full_eligible_v0'
WEIGHTED_VERSION = 'bigmhc_el_weighted_v1'
SOURCE_COMMIT = '199e890fa69a63646730bcecea0a520e08ca4f02'
VIEWS = {'EL':'processed/el_train_original.csv', 'IM':'processed/im_train_original.csv', 'development':'processed/im_development.csv'}
TRANSFER = ('condenser.att.weight','condenser.att.bias','condenser.out.weight','condenser.out.bias')
PROVENANCE_FIELDS = ('source_file','row_index','source_line_number','source_row_id','source_row_sha256',
                     'original_peptide','original_hla','resolved_hla','original_label','derived_row_index')
SOURCES = ('README','LICENSE','train','predict','cli','bigmhc','dataset','mhcenc','mhcuid','encseq')
INPUTS = {'EL','IM','development','EL_provenance','IM_provenance','development_provenance',
          'experiment','parent_receipt','parent_manifest','inventory','reference',*('source_'+n for n in SOURCES)}


def load_config(path):
    c=readers._json(path)
    c.setdefault('device','cpu')
    weighted=c.get('version')==WEIGHTED_VERSION
    full_profile=c.get('version') in (FULL_VERSION,WEIGHTED_VERSION)
    worker_profile=c.get('version') in (WORKER_VERSION,FULL_VERSION,WEIGHTED_VERSION)
    if weighted:
        from .el_stability_loss_adapter import validate_runtime_spec
        validate_runtime_spec(c.get('loss_adapter',{}),c.get('condition'))
    elif 'loss_adapter' in c:
        raise ValueError('Loss adapter requires its explicit versioned full-population profile')
    if full_profile and (c.get('device')!='cuda' or c.get('batch_size')!=16
            or c.get('rows_per_class')!={'EL':None,'IM':None}
            or c.get('expected_rows')!={'EL':1453578,'IM':3428}
            or c.get('expected_class_counts')!={'EL':{'0':1383509,'1':70069},'IM':{'0':2473,'1':955}}):
        raise ValueError('Full eligible Baseline A requires the complete frozen original populations and CUDA batch16')
    if (c.get('schema_version')!=1 or c.get('version') not in (VERSION,WORKER_VERSION,FULL_VERSION,WEIGHTED_VERSION)
            or c.get('condition') not in ({'A','B','P'} if weighted else {'A'})
            or c.get('label_policy')!='original' or c.get('source_commit')!=SOURCE_COMMIT
            or c.get('seed')!=42 or c.get('device') not in ('cpu','cuda') or c.get('num_workers')!=0
            or c.get('persistent_workers') is not False or c.get('epochs')!={'EL':1,'IM':1}
            or c.get('learning_rate')!=5e-5 or c.get('batch_size') not in (4,8,16)
            or set(c.get('inputs',{}))!=(INPUTS|{'positive_scores','positive_score_manifest'} if weighted else INPUTS)
            or type(c.get('cpu_threads')) is not int or not 1<=c['cpu_threads']<=4
            or type(c.get('wall_seconds')) is not int or not 60<=c['wall_seconds']<=(7200 if full_profile else 1800 if worker_profile else 600)
            or type(c.get('memory_bytes')) is not int or not 2*1024**3<=c['memory_bytes']<=(32 if full_profile else 8 if worker_profile else 6)*1024**3):
        raise ValueError('Only bounded CPU/CUDA original-label condition A is authorized')
    for stage,limit in (('EL',100000 if worker_profile else 1000),('IM',1714 if worker_profile else 256)):
        if full_profile:continue
        # Task 2.9: retain the complete original IM population, without balancing.
        if worker_profile and stage=='IM' and c['rows_per_class'][stage] is None:
            if c['expected_rows'][stage]!=3428:raise ValueError('All-original IM requires the frozen 3428-row population')
            continue
        if type(c['rows_per_class'][stage]) is not int or not 1<=c['rows_per_class'][stage]<=limit:
            raise ValueError('Subset smoke-size cap exceeded')
    for name,item in c['inputs'].items():
        adapter.pilot.registry._relative(item['relative_path'])
        if item['area'] not in {'data','runs'} or not adapter.pilot._sha(item['sha256']):
            raise ValueError('Invalid pinned runtime input')
        if 'low_only' in item['relative_path'] or 'low_and_high' in item['relative_path'] or 'overrides' in item['relative_path']:
            raise ValueError('Scientifically unapproved corrected input forbidden')
    return c


def resolve_inputs(config,paths,files:Mapping|None=None):
    overrides=files or {}
    if set(overrides)-set(config['inputs']):raise ValueError('Unknown runtime input override')
    result={};identities=[]
    for name,item in config['inputs'].items():
        root=paths.project_data_dir if item['area']=='data' else paths.project_runs_dir
        path=Path(overrides.get(name,root/item['relative_path'])).expanduser().absolute()
        if any(word in path.name for word in ('low_only','low_and_high','overrides')):
            raise ValueError('Corrected CSV/override input forbidden')
        if raw.sha256_file(path)!=item['sha256']:raise ValueError('Runtime input SHA256 mismatch: '+name)
        result[name]=path;identities.append({'path':str(path),'sha256':item['sha256']})
    experiment=readers._json(result['experiment']);receipt=readers._json(result['parent_receipt'])
    for stage,relative in VIEWS.items():
        if raw.sha256_file(result[stage])!=experiment['artifacts'][relative]['sha256']:
            raise ValueError('Original-view identity disagrees with authenticated parent manifest')
        key=relative.replace('_original.csv','_provenance.csv.gz').replace('im_development.csv','im_development_provenance.csv.gz')
        if raw.sha256_file(result[stage+'_provenance'])!=experiment['artifacts'][key]['sha256']:
            raise ValueError('Original-row provenance identity mismatch')
    if receipt['reports']['pilot_experiment_manifest.json']!=raw.sha256_file(result['experiment']):
        raise ValueError('Parent experiment receipt mismatch')
    parent=runs.validate_manifest(readers._json(result['parent_manifest']))
    if (receipt['code_commit']!=parent['git']['commit_sha']
            or receipt['reports']['pilot_training_inventory.json']!=raw.sha256_file(result['inventory'])):
        raise ValueError('Parent inventory or committed provenance mismatch')
    if config.get('loss_adapter') and config['loss_adapter']['matched_reference'] is not None:
        reference=config['loss_adapter']['matched_reference']
        path=paths.project_runs_dir/reference['relative_path']
        if raw.sha256_file(path)!=reference['sha256']:raise ValueError('Matched A reference SHA256 mismatch')
        result['matched_reference']=path;identities.append({'path':str(path),'sha256':reference['sha256']})
    return result,identities


def input_rows(path,allowed_hla):
    with raw._read_file(path) as stream,io.TextIOWrapper(stream,encoding='utf-8',newline='') as text:
        rows=csv.reader(text,strict=True)
        if next(rows)!=['mhc','pep','tgt']:raise ValueError('Original training-view schema changed')
        for index,fields in enumerate(rows,1):
            if (len(fields)!=3 or fields[0] not in allowed_hla or fields[2] not in {'0','1'} or len(fields[1])!=9
                    or any(a not in teacher.ALPHABET for a in fields[1])
                    or data.canonical_hla(fields[0])!=fields[0] or not fields[0].startswith(('HLA-A*','HLA-B*'))):
                raise ValueError('Unsupported or malformed original-label row')
            yield {'prepared_row_index':index,'hla':fields[0],'peptide':fields[1],'original_label':fields[2]}


def select_subset(rows,per_class: int | None,seed=42):
    """Original-label reservoir sample, or all original rows when per_class is None."""
    if per_class is None:
        selected=[dict(row) for row in rows]
        if len({r['prepared_row_index'] for r in selected})!=len(selected):
            raise ValueError('Duplicate selected row identity')
        return selected,dict(Counter(r['original_label'] for r in selected))
    rng=random.Random(seed);reservoir={'0':[],'1':[]};seen=Counter()
    for row in rows:
        label=row['original_label'];seen[label]+=1
        if len(reservoir[label])<per_class:reservoir[label].append(dict(row))
        else:
            position=rng.randrange(seen[label])
            if position<per_class:reservoir[label][position]=dict(row)
    if any(seen[label]<per_class for label in ('0','1')):raise ValueError('Insufficient original class support')
    selected=sorted(reservoir['0']+reservoir['1'],key=lambda r:r['prepared_row_index'])
    if len({r['prepared_row_index'] for r in selected})!=len(selected):raise ValueError('Duplicate selected row identity')
    return selected,dict(seen)


def attach_provenance(selected,path):
    """Selection is already frozen; read only original-coordinate fields of the ledger."""
    wanted={r['prepared_row_index']:r for r in selected};seen=set()
    import gzip
    with raw._read_file(path) as stream,gzip.GzipFile(fileobj=stream) as gz,io.TextIOWrapper(gz,encoding='utf-8',newline='') as text:
        for record in csv.DictReader(text,strict=True):
            coordinate=record['derived_row_index']
            if record['retained']!='1' or not coordinate or int(coordinate) not in wanted:continue
            index=int(coordinate);row=wanted[index]
            if (index in seen or [record['resolved_hla'],record['original_peptide'],record['original_label']]
                    !=[row['hla'],row['peptide'],row['original_label']]):raise ValueError('Original-row lineage join mismatch')
            row['source_locator']={key:record[key] for key in PROVENANCE_FIELDS}
            if record['source_file']=='im_train.csv':
                from .el_stability_loss_adapter import original_fields
                original_fields(record,'IM')
                row['source_locator']['original_rand']=record['original_rand']
            seen.add(index)
    if seen!=set(wanted):raise ValueError('Selected original-row lineage missing')


def verify_separation(training,development):
    dev={r['peptide'] for r in development};blocked=adapter.substitution_neighborhood(dev)
    violations=[r['prepared_row_index'] for r in training if r['peptide'] in blocked]
    if violations:raise ValueError('Exact/one-mismatch development exposure: '+str(violations[:10]))
    return {'rule':'Global canonical nine-mer Hamming distance<=1, across all HLA',
            'training_rows':len(training),'development_rows':len(development),'prohibited_matches':0}


def csv_text(rows):
    text=io.StringIO(newline='');writer=csv.writer(text,lineterminator='\n');writer.writerow(['mhc','pep','tgt'])
    writer.writerows((r['hla'],r['peptide'],r['original_label']) for r in rows)
    return text.getvalue()


@contextmanager
def pinned_modules(files):
    names=('mhcuid','encseq','dataset','bigmhc')
    if any(name in sys.modules for name in names):raise ValueError('External module-name collision')
    try:
        for name in names:
            path=files['source_'+name];module=types.ModuleType(name);module.__file__=str(path)
            sys.modules[name]=module
            with raw._read_file(path) as stream:code=compile(stream.read(),str(path),'exec')
            exec(code,module.__dict__)
        yield sys.modules['bigmhc'].BigMHC,sys.modules['dataset'].Dataset
    finally:
        for name in names:sys.modules.pop(name,None)


def seed_runtime(torch,np,config):
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed'])
    torch.set_num_threads(config['cpu_threads']);torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    if config.get('device','cpu')=='cuda':
        torch.cuda.manual_seed_all(config['seed'])
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.deterministic=True
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False


def cuda_visibility(environ=None):
    """Require selection of one physical GPU before the process imports Torch."""
    value=(os.environ if environ is None else environ).get('CUDA_VISIBLE_DEVICES','')
    if not value.isascii() or not value.isdecimal():
        raise ValueError('CUDA requires CUDA_VISIBLE_DEVICES set to one GPU index, for example 0 or 1')
    return value


def runtime_device(torch,config):
    """Explicit device; CUDA failure never falls back to CPU."""
    requested=config.get('device','cpu')
    if requested not in ('cpu','cuda'):raise ValueError('Device must be cpu or cuda')
    if requested=='cpu':return 'cpu'
    cuda_visibility()
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable; check the NVIDIA driver and CUDA-enabled PyTorch. No CPU fallback.')
    if torch.cuda.device_count()!=1:
        raise RuntimeError('CUDA worker requires exactly one visible GPU; set CUDA_VISIBLE_DEVICES=0 or 1')
    torch.cuda.set_device(0)
    torch.cuda.reset_peak_memory_stats(0)
    return 'cuda:0'


def device_report(torch,device):
    report={'device':device,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
            'torch_CUDA_runtime':torch.version.cuda,'GPU_name':None,'cudnn_version':None}
    if device!='cpu':
        report.update(GPU_name=torch.cuda.get_device_name(0),cudnn_version=torch.backends.cudnn.version(),
                      GPU_total_memory_bytes=torch.cuda.get_device_properties(0).total_memory)
    return report


def on_device(value,device):
    return value.cpu() if device=='cpu' else value.to(device)


def save_checkpoint(model,path,*,transfer,device='cpu'):
    """Native tensor filenames/overlay contract, staged on CPU for portability."""
    try:
        model.cpu().save(str(path),tl=transfer)
    finally:
        on_device(model,device)


def load_checkpoint(torch,BigMHC,path,keys,*,device='cpu',lineage=None):
    """Load authenticated tensor-only files on CPU, then select the runtime device.

    The four-file IM overlay inherits its immediate 36-file EL parent, as in
    pinned BigMHC.load; map_location is explicit even for CUDA-tagged tensors.
    """
    path=Path(path)
    if lineage is None:
        checkpoint_identity(path,keys)
        base=path;overlay={}
    else:
        base=path.parent;verify_parent(base,path,lineage)
        overlay=lineage['IM_files']
    state={}
    for index,key in enumerate(keys):
        name=f'{index}_{key}.lyr';source=(path if name in overlay else base)/name
        with raw._read_file(source) as stream:
            tensor=torch.load(stream,map_location='cpu',weights_only=True)
        if not torch.is_tensor(tensor):raise ValueError('Checkpoint contains a non-tensor value')
        state[key]=tensor
    model=BigMHC();model.load_state_dict(state,strict=True)
    return on_device(model,device)


def reserve_checkpoint(path):
    with raw._directory(path.parent) as parent:
        os.mkdir(path.name,0o700,dir_fd=parent)


def checkpoint_identity(path,keys):
    expected={f'{i}_{key}.lyr' for i,key in enumerate(keys)}
    if set(p.name for p in path.iterdir() if p.name.endswith('.lyr'))!=expected:
        raise ValueError('Missing or extra checkpoint tensors')
    return {name:raw.sha256_file(path/name) for name in sorted(expected)}


def overlay_identity(path,keys):
    expected={f'{i}_{key}.lyr' for i,key in enumerate(keys) if key in TRANSFER}
    if set(p.name for p in path.iterdir() if p.name.endswith('.lyr'))!=expected:raise ValueError('Invalid IM transfer overlay')
    return {name:raw.sha256_file(path/name) for name in sorted(expected)}


def verify_parent(el,im,lineage):
    if im.parent!=el or checkpoint_identity(el,lineage['state_keys'])!=lineage['EL_files']:
        raise ValueError('Transfer overlay does not resolve its authenticated immediate EL parent')
    if overlay_identity(im,lineage['state_keys'])!=lineage['IM_files']:raise ValueError('IM overlay changed')


def state_hashes(model):
    return {k:hashlib.sha256(v.detach().cpu().contiguous().numpy().tobytes()).hexdigest() for k,v in model.state_dict().items()}


def train_epoch(torch,model,dataset,config,transfer,device='cpu',*,loss_adapter=None,expected_batches=None):
    if transfer and loss_adapter is not None:raise ValueError('EL weights cannot modify IM transfer loss')
    on_device(model,device).train()
    parameters=[v for k,v in model.named_parameters() if not transfer or k in TRANSFER]
    optimizer=torch.optim.AdamW(parameters,lr=config['learning_rate']);lossf=torch.nn.BCEWithLogitsLoss()
    dataset.makebats(config['batch_size'],shuffle=True,negfrac=None if transfer else 0.99)
    loader=torch.utils.data.DataLoader(dataset,batch_size=None,shuffle=True,num_workers=0,persistent_workers=False)
    steps=[];skipped_log=[];skipped=0;rows=0;weighted=0.0;epoch_error=0.0
    audited=getattr(dataset,'source_identity_audit',False) is True;batch_hashes=[];skip_mask=[]
    for index,batch in enumerate(loader,1):
        if audited:
            batch_hashes.append(batch.source_batch_sha256)
            if expected_batches is not None and (index>len(expected_batches) or batch_hashes[-1]!=expected_batches[index-1]):
                raise ValueError('Matched sampled source-row sequence differs before optimizer update')
        target=on_device(batch.tgt.float(),device)
        n=len(target);positives=int(target.sum())
        if transfer and not positives:
            if audited:skip_mask.append(True)
            skipped+=1;skipped_log.append({'batch':index,'rows':n,'positives':0,'reason':'native IM all-negative batch skip'})
            continue
        optimizer.zero_grad()
        output,_=model(mhc=on_device(batch.mhc.float(),device),pep=on_device(batch.pep.float(),device))
        if loss_adapter is None:
            loss=lossf(output,target)
        else:
            from .el_stability_loss_adapter import weighted_bce
            if not audited or dataset.adapter is not loss_adapter:raise ValueError('Weighted loss requires authenticated sampled row identities')
            loss=weighted_bce(torch,output,target,batch.EL_loss_weights)
        if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
        loss.backward();optimizer.step();value=float(loss.detach())
        rows+=n;weighted+=value*n;epoch_error+=value/len(loader)
        steps.append({'batch':index,'rows':n,'positives':positives,'BCE_loss':value})
        if audited:skip_mask.append(False)
        print(('IM' if transfer else 'EL')+f' batch {index}/{len(loader)} loss {value:.6f}',flush=True)
    if expected_batches is not None and len(batch_hashes)!=len(expected_batches):raise ValueError('Matched sample count differs')
    if not steps:raise ValueError('No genuine optimization steps executed')
    positive_exposures=sum(step['positives'] for step in steps)
    skipped_rows=sum(batch['rows'] for batch in skipped_log)
    result={'optimization_steps':len(steps),'batches':len(loader),'all_negative_batches_skipped':skipped,
        'consumed_rows':rows,'row_weighted_BCE_loss':weighted/rows,'source_style_epoch_loss':epoch_error,
        'optimizer_class_exposures':{'1':positive_exposures,'0':rows-positive_exposures},
        'optimizer_positive_fraction':positive_exposures/rows,
        'sampled_batch_instances':rows+skipped_rows,
        'sampled_class_exposures':{'1':positive_exposures,'0':rows-positive_exposures+skipped_rows},
        'skipped_rows':skipped_rows,'skipped_batch_log':skipped_log,
        'requested_batch_size':config['batch_size'],'maximum_optimized_batch_rows':max(step['rows'] for step in steps),
        'sampling':'Pinned makebats(shuffle=True,negfrac='+('None' if transfer else '0.99')+'); no sampler changes',
        'step_log':steps,'optimizer_defaults':optimizer.defaults,'updated_parameters':[k for k,v in model.named_parameters() if not transfer or k in TRANSFER]}
    if audited:result.update(sampled_batch_sha256=batch_hashes,optimizer_skip_mask=skip_mask,
        loss_weight_mode=loss_adapter.mode if loss_adapter is not None else 'native_unweighted_IM')
    return result


def predict(torch,model,dataset,batch_size,device='cpu'):
    on_device(model,device).eval();dataset.makebats(batch_size,shuffle=False,negfrac=None)
    result=[]
    with torch.no_grad():
        for index in range(len(dataset)):
            batch=dataset[index];output,_=model(on_device(batch.mhc.float(),device),on_device(batch.pep.float(),device))
            probabilities=torch.sigmoid(output)
            result.extend((probabilities if device=='cpu' else probabilities.cpu()).tolist())
    if len(result)!=len(dataset.df) or any(not math.isfinite(v) or not 0<=v<=1 for v in result):
        raise ValueError('Invalid development inference coverage')
    return result


def prediction_agreement(before,after,device='cpu'):
    """Same-device reload check; CPU exact, CUDA explicit float32 tolerance."""
    relative,absolute=(0.0,0.0) if device=='cpu' else (1e-6,1e-7)
    if len(before)!=len(after) or any(not math.isfinite(v) for v in [*before,*after]):
        raise ValueError('Checkpoint prediction coverage/nonfinite mismatch')
    if any(not math.isclose(a,b,rel_tol=relative,abs_tol=absolute) for a,b in zip(before,after)):
        raise ValueError('Checkpoint prediction reload mismatch')
    return {'device':device,'relative_tolerance':relative,'absolute_tolerance':absolute,
            'maximum_absolute_difference':max((abs(a-b) for a,b in zip(before,after)),default=0.0),
            'exactly_identical':before==after,'consistent':True}


def write_predictions(path,rows,probabilities,paths):
    text=io.StringIO(newline='');fields=['development_row_index','source_row_id','original_hla','resolved_hla','peptide','original_label','probability']
    writer=csv.DictWriter(text,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for row,value in zip(rows,probabilities,strict=True):
        writer.writerow({'development_row_index':row['prepared_row_index'],'source_row_id':row['source_locator']['source_row_id'],
            'original_hla':row['source_locator']['original_hla'],'resolved_hla':row['hla'],'peptide':row['peptide'],
            'original_label':row['original_label'],'probability':repr(value)})
    raw.write_text_report(path,text.getvalue(),paths=paths)


def development_metrics(labels: list[int], probabilities: list[float]) -> dict:
    """Tie-aware rank AUROC and non-interpolated average precision (PR area)."""
    if (not labels or len(labels)!=len(probabilities) or any(type(v) is not int or v not in (0,1) for v in labels)
            or any(not math.isfinite(v) or not 0<=v<=1 for v in probabilities)):
        raise ValueError('Invalid development labels or probabilities')
    positives=sum(labels);negatives=len(labels)-positives
    if not positives or not negatives:raise ValueError('Development metrics require both original classes')
    groups={}
    for label,score in zip(labels,probabilities,strict=True):
        group=groups.setdefault(score,[0,0]);group[label]+=1
    tp=fp=0;concordant=0.0;average_precision=0.0
    for score in sorted(groups,reverse=True):
        negative,positive=groups[score]
        # Earlier positives outrank this group's negatives; ties receive half credit.
        concordant+=tp*negative+0.5*positive*negative
        tp+=positive;fp+=negative
        average_precision+=(positive/positives)*(tp/(tp+fp))
    return {'AUROC':concordant/(positives*negatives),'AUPRC':average_precision,
            'AUPRC_method':'Non-interpolated average precision; tied scores grouped',
            'observations':len(labels),'positives':positives,'negatives':negatives,
            'interpretation':'Preliminary frozen-development metrics; not independent external-test results; no model selection'}


def worker(*,config_path,out,paths=None,files=None):
    paths=paths or resolve_paths();config=load_config(config_path)
    adapted=config.get('loss_adapter') is not None
    if adapted:
        from . import el_stability_loss_adapter as weighting
        weighting.require_training_authorization(config)
    resolved,inputs=resolve_inputs(config,paths,files)
    if adapted:
        from .bigmhc_abp_experiment import arm_run
        directory,manifest=arm_run(out,paths,config)
    else:
        directory,manifest=teacher._run(out,paths)
    if adapted:
        from .bigmhc_abp_preflight import validate
        try:
            preflight=validate(config_path=config_path,paths=paths,files=files)
        except Exception as error:
            raw.write_report(directory/'reports/full_cohort_preflight.json',
                {'status':'failed','failure_reason':repr(error),'optimizer_steps':0},paths=paths)
            raise
        raw.write_report(directory/'reports/full_cohort_preflight.json',preflight,paths=paths)
    import torch
    device=runtime_device(torch,config)
    if (manifest['configuration']['file']!={'path':str(Path(config_path).absolute()),'sha256':raw.sha256_file(config_path)}
            or manifest['configuration']['random_seed']!=42
            or any(i not in manifest['data_provenance']['input_artifacts'] for i in inputs)):
        raise ValueError('Runtime run must record committed configuration, seed42 and all actual inputs')
    inventory=readers._json(resolved['inventory']);allowed=set().union(*(v['by_HLA'] for v in inventory.values()))
    selected={};subset_info={}
    for stage,member in (('EL','el_train.csv'),('IM','im_train.csv')):
        selected[stage],counts=select_subset(input_rows(resolved[stage],allowed),config['rows_per_class'][stage],42)
        if sum(counts.values())!=config['expected_rows'][stage] or counts!=inventory[member]['class_balances']['original']:
            raise ValueError('Original training population mismatch')
        if 'expected_class_counts' in config and counts!=config['expected_class_counts'][stage]:
            raise ValueError('Configured original class counts disagree with authenticated population')
        attach_provenance(selected[stage],resolved[stage+'_provenance'])
        raw.write_text_report(directory/f'processed/{stage.lower()}_original_smoke.csv',csv_text(selected[stage]),paths=paths)
        subset_info[stage]={'rows':selected[stage],'source_view_sha256':raw.sha256_file(resolved[stage]),'original_population_labels':counts,
                            'selected_rows':len(selected[stage]),'selected_class_counts':dict(Counter(r['original_label'] for r in selected[stage])),
                            'selection':('All prepared original rows in source order; original prevalence; no resampling'
                                if config['rows_per_class'][stage] is None else
                                'Uniform within-original-label reservoir sampling seed42; sorted prepared-view row order; no scores/development outcomes')}
        if config['version'] in (FULL_VERSION,WEIGHTED_VERSION):
            # Reuse the atomic streaming writer rather than building a multi-GB JSON string.
            relative=f'processed/{stage.lower()}_original_row_manifest.csv.gz'
            fields=['prepared_row_index','hla','peptide',*PROVENANCE_FIELDS]+(['original_rand'] if stage=='IM' else [])
            with adapter.artifact_csv(directory/relative,fields,True) as (writer,sink):
                for row in selected[stage]:
                    writer.writerow({key:row[key] for key in ('prepared_row_index','hla','peptide')} | row['source_locator'])
            subset_info[stage].pop('rows')
            subset_info[stage]['row_manifest']={'relative_path':relative,'sha256':sink.digest.hexdigest(),'size_bytes':sink.size}
    development=list(input_rows(resolved['development'],allowed))
    if (len(development)!=383 or Counter(r['original_label'] for r in development)!={'1':120,'0':263}
            or len({r['hla'] for r in development})!=31):raise ValueError('Frozen development cohort mismatch')
    attach_provenance(development,resolved['development_provenance'])
    leakage={stage:verify_separation(rows,development) for stage,rows in selected.items()}
    raw.write_report(directory/'reports/subset_manifest.json',subset_info,paths=paths)
    raw.write_report(directory/'reports/leakage_verification.json',leakage,paths=paths)
    import numpy as np
    import pandas as pd
    import psutil
    import platform
    import importlib.metadata
    seed_runtime(torch,np,config)
    environment={'python':sys.version,**device_report(torch,device),'seed':config['seed'],
        'code_commit':manifest['git']['commit_sha'],'source_commit':SOURCE_COMMIT,'runtime_configuration':config,'cpu_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),
        'versions':{name:importlib.metadata.version(name) for name in ('torch','numpy','pandas','psutil')},
        'all_installed_distributions':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'platform':platform.platform(),'machine':platform.machine(),'host_RAM_bytes':psutil.virtual_memory().total,
        'cpu_count':os.cpu_count(),'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}
    raw.write_report(directory/'reports/environment.json',environment,paths=paths)
    loss_adapter=weighting.runtime_adapter(config,resolved) if adapted else None
    matched_reference=readers._json(resolved['matched_reference']) if 'matched_reference' in resolved else None
    matched={}
    if adapted:
        matched={'schema_version':1,'version':weighting.VERSION,'configuration_identity':weighting.matched_config_identity(config),
                 'code_commit':manifest['git']['commit_sha'],'versions':environment['versions'],'device':device}
        if matched_reference is not None and any(matched[k]!=matched_reference[k] for k in matched):
            raise ValueError('Matched A code, runtime, device or configuration differs')
        raw.write_report(directory/'reports/loss_weight_invariants.json',loss_adapter.evidence,paths=paths)
    with raw._read_file(resolved['reference']) as stream,io.TextIOWrapper(stream,encoding='utf-8-sig',newline='') as text:
        reference_report,_,reference=data._reference(enumerate(csv.reader(text,strict=True),1))
    if (reference_report['feature_count']!=414 or reference_report['invalid_one_hot_rows']
            or reference_report['duplicate_identifier_count'] or reference_report['sanitized_UID_collision_groups']):
        raise ValueError('Invalid authentic receptor representation')
    needed={r['hla'] for rows in [*selected.values(),development] for r in rows}
    del selected,subset_info
    if any(len(reference.get(h,()))!=1 for h in needed):raise ValueError('Unsupported/ambiguous exact HLA reference')
    encodings={}
    with raw._read_file(resolved['reference']) as stream,io.TextIOWrapper(stream,encoding='utf-8-sig',newline='') as text:
        rows=csv.reader(text);next(rows)
        for row in rows:
            h=data.canonical_hla(row[0])
            if h in needed:encodings[h]=torch.tensor([int(v) for v in row[1:]],dtype=torch.int8)
    with pinned_modules(resolved) as (BigMHC,Dataset):
        def dataset(path):return Dataset(Dataset.readPMHCs(str(path),allele=0,pepcol=1,tgtcol=2,hdrcnt=1,verbose=False),mhcenc=encodings)
        def training_dataset(stage):
            native=dataset(directory/f'processed/{stage.lower()}_original_smoke.csv')
            if not adapted:return native
            return weighting.IdentityDataset(native,weighting.manifest_rows(directory/f'processed/{stage.lower()}_original_row_manifest.csv.gz'),
                stage=stage,adapter=loss_adapter if stage=='EL' else None,archive_sha256=loss_adapter.manifest['archive_sha256'])
        model=on_device(BigMHC(),device);keys=list(model.state_dict())
        if adapted and any(p.dtype!=torch.float32 for p in model.parameters()):raise ValueError('Matched experiment requires FP32 parameters')
        if len(keys)!=36 or tuple(BigMHC.tllayers())!=TRANSFER:raise ValueError('Unexpected authentic architecture state')
        architecture={'parameter_count':sum(v.numel() for v in model.parameters()),'state_tensors':len(keys),
                      'constructor':'Pinned BigMHC() defaults: mhclen414,minpep8,enclen20,hidlen1024,layers2','source_commit':SOURCE_COMMIT}
        print('Authentic architecture:',architecture,flush=True)
        initial=state_hashes(model)
        raw.write_report(directory/'reports/initial_el_state_identity.json',initial,paths=paths)
        if adapted:
            matched['initial_tensor_sha256']=initial
            matched['rng_before_EL']=weighting.rng_identity(torch,np)
            weighting.check_reference(matched_reference,initial=initial,rng=matched['rng_before_EL'],stage='EL')
        def stage_epoch(stage, current_model, transfer, **kwargs):
            # Separate immutable receipts survive a later stage/encoding/reload failure.
            raw.write_report(directory/f'reports/{stage.lower()}_stage_started.json',
                {'stage':stage,'status':'started','initial_state_tensor_sha256':state_hashes(current_model),
                 'code_commit':manifest['git']['commit_sha'], 'condition':config['condition']},paths=paths)
            if device!='cpu':
                torch.cuda.synchronize(0);torch.cuda.reset_peak_memory_stats(0)
            start=time.monotonic()
            try:
                training=train_epoch(torch,current_model,training_dataset(stage),config,transfer,device,**kwargs)
                if device!='cpu':torch.cuda.synchronize(0)
            except Exception as error:
                raw.write_report(directory/f'reports/{stage.lower()}_stage_failed.json',
                    {'stage':stage,'status':'failed','failure_reason':repr(error),
                     'elapsed_seconds':time.monotonic()-start},paths=paths)
                raise
            training['elapsed_seconds']=time.monotonic()-start
            training['GPU_memory']=({'peak_allocated_bytes':torch.cuda.max_memory_allocated(0),
                'peak_reserved_bytes':torch.cuda.max_memory_reserved(0)} if device!='cpu' else None)
            raw.write_report(directory/f'reports/{stage.lower()}_stage_completed.json',
                {'stage':stage,'status':'completed','training':training,
                 'state_tensor_sha256':state_hashes(current_model),
                 'ordered_sampled_batches_sha256':weighting.digest(training['sampled_batch_sha256']) if adapted else None,
                 'checkpoint_status':'pending; see separate stage checkpoint receipt'},paths=paths)
            return training
        el_training=stage_epoch('EL',model,False,
            **({'loss_adapter':loss_adapter,'expected_batches':matched_reference['EL']['sampled_batch_sha256'] if matched_reference else None} if adapted else {}))
        if adapted:
            weighting.check_reference(matched_reference,stage='EL',training=el_training)
            matched['EL']={k:el_training[k] for k in ('optimization_steps','sampled_batch_sha256','optimizer_defaults','updated_parameters','optimizer_skip_mask')}
        el_state=state_hashes(model)
        if el_state==initial:raise ValueError('EL model parameters did not change')
        dev=dataset(resolved['development']);el_predictions=predict(torch,model,dev,config['batch_size'],device)
        el=directory/'checkpoints/el';reserve_checkpoint(el);save_checkpoint(model,el,transfer=False,device=device)
        el_files=checkpoint_identity(el,keys)
        reloaded=load_checkpoint(torch,BigMHC,el,keys,device=device)
        if state_hashes(reloaded)!=el_state:raise ValueError('EL checkpoint state reload mismatch')
        el_agreement=prediction_agreement(el_predictions,predict(torch,reloaded,dev,config['batch_size'],device),device)
        raw.write_report(directory/'reports/el_stage_checkpoint.json',
            {'status':'verified','checkpoint':'checkpoints/el','files':el_files,
             'initial_state_tensor_sha256':initial,'state_tensor_sha256':el_state,
             'strict_reload_identical':True,'code_commit':manifest['git']['commit_sha']},paths=paths)
        del model
        if adapted:
            matched['rng_before_IM']=weighting.rng_identity(torch,np)
            weighting.check_reference(matched_reference,rng=matched['rng_before_IM'],stage='IM')
        im_training=stage_epoch('IM',reloaded,True,
            **({'expected_batches':matched_reference['IM']['sampled_batch_sha256'] if matched_reference else None} if adapted else {}))
        im_state=state_hashes(reloaded)
        if adapted:
            weighting.check_reference(matched_reference,stage='IM',training=im_training)
            matched['IM']={k:im_training[k] for k in ('optimization_steps','sampled_batch_sha256','optimizer_defaults','updated_parameters','optimizer_skip_mask')}
            if el_training['optimization_steps']!=70069 or im_training['optimization_steps']!=214:
                raise ValueError('Preregistered full-population optimizer-step count differs')
            raw.write_report(directory/'reports/matched_state.json',matched,paths=paths)
        changed=[k for k in keys if im_state[k]!=el_state[k]]
        if not changed or set(changed)-set(TRANSFER):raise ValueError('IM updated unauthorized model parameters')
        im_predictions=predict(torch,reloaded,dev,config['batch_size'],device)
        im=el/'im';reserve_checkpoint(im);save_checkpoint(reloaded,im,transfer=True,device=device);im_files=overlay_identity(im,keys)
        lineage={'state_keys':keys,'EL_files':el_files,'IM_files':im_files,'IM_parent_relative_path':'..',
            'EL_checkpoint':'checkpoints/el','IM_overlay':'checkpoints/el/im','changed_IM_parameters':changed,
            'initial_state_tensor_sha256':initial,'EL_state_tensor_sha256':el_state,'IM_state_tensor_sha256':im_state,
            'checkpoint_storage_device':'cpu','reload_device':device,
            'checkpoint_loading':'weights_only=True,map_location=cpu,strict state load then selected device',
            'EL_reload_identical':True,'IM_reload_identical':True,'unoptimized_encoder_weights_unchanged':True}
        verify_parent(el,im,lineage)
        raw.write_report(directory/'reports/im_stage_checkpoint.json',
            {'status':'verified','checkpoint':'checkpoints/el/im','parent':'checkpoints/el',
             'files':im_files,'parent_state_tensor_sha256':el_state,'state_tensor_sha256':im_state,
             'code_commit':manifest['git']['commit_sha']},paths=paths)
        del reloaded
        reconstructed=load_checkpoint(torch,BigMHC,im,keys,device=device,lineage=lineage)
        if state_hashes(reconstructed)!=im_state:raise ValueError('IM parent+overlay state reload mismatch')
        im_agreement=prediction_agreement(im_predictions,predict(torch,reconstructed,dev,config['batch_size'],device),device)
        lineage['prediction_reload_agreement']={'EL':el_agreement,'IM':im_agreement}
        verify_parent(el,im,lineage)
    if device!='cpu':
        torch.cuda.synchronize(0)
    gpu_memory={'peak_allocated_bytes':torch.cuda.max_memory_allocated(0),
                'peak_reserved_bytes':torch.cuda.max_memory_reserved(0)} if device!='cpu' else None
    if gpu_memory is not None:
        gpu_memory={key:max(gpu_memory[key],el_training['GPU_memory'][key],im_training['GPU_memory'][key])
                    for key in gpu_memory}
    write_predictions(directory/'predictions/el_development.csv',development,el_predictions,paths)
    write_predictions(directory/'predictions/im_development.csv',development,im_predictions,paths)
    metrics={name:development_metrics([int(r['original_label']) for r in development],probabilities)
             for name,probabilities in (('EL_proxy',el_predictions),('IM',im_predictions))}
    raw.write_report(directory/'reports/development_metrics.json',metrics,paths=paths)
    raw.write_report(directory/'reports/training_configuration.json',config,paths=paths)
    raw.write_report(directory/'reports/checkpoint_lineage.json',lineage,paths=paths)
    raw.write_report(directory/'reports/training_summary.json',{'architecture':architecture,'EL':el_training,'IM':im_training,
        'device':device,'GPU_memory':gpu_memory,'development_rows':383,'development_HLA':31,'prediction_reloads_bitwise_identical':el_agreement['exactly_identical'] and im_agreement['exactly_identical'],'condition':config['condition'],
        'interpretation':('Original labels; optional preregistered EL loss weighting; development cohort is not an independent external test; no correction evidence'
                          if adapted else 'Original-label condition A; development cohort is not an independent external test; no correction evidence'),
        'predictive_performance_metrics':metrics,
        'adaptations':['Bypass stock CLI seed1; seed Python/NumPy/Torch42 and deterministic algorithms on explicit device',
            'DataLoader num_workers0,persistent_workersFalse; no prefetch/worker state',
            'Strict validated dict receptor lookup; no fuzzy MHCEncoder fallback',
            'One epoch each; original makebats, loss, optimizer, transfer parameter list and all-negative IM skip preserved',
            'Native checkpoint saves staged on CPU; tensor-only map_location=cpu load then selected device']},paths=paths)
    for identity in inputs:
        if raw.sha256_file(identity['path'])!=identity['sha256']:raise ValueError('Immutable input changed')
    outputs={str(p.relative_to(directory)):raw.sha256_file(p) for area in ('processed','reports','predictions','checkpoints')
             for p in sorted((directory/area).rglob('*')) if p.is_file()}
    raw.write_report(directory/'reports/execution_verification.json',{'code_commit':manifest['git']['commit_sha'],
        'config_sha256':raw.sha256_file(config_path),'inputs':inputs,'outputs':outputs,'sealed_payloads_opened':[],
        'corrected_views_opened':[],'source_inputs_unchanged':True,'seed':42,'condition':config['condition'],
        'EL_full_checkpoint_tensors':len(el_files),'IM_overlay_tensors':len(im_files),
        'reload_predictions_identical':el_agreement['exactly_identical'] and im_agreement['exactly_identical'],
        'reload_predictions_consistent':True,'runtime_device':device,'GPU_memory':gpu_memory,
        'new_correction_rules_or_labels':False},paths=paths)
    return {'run':str(directory),'EL_steps':el_training['optimization_steps'],'IM_steps':im_training['optimization_steps'],
            'development_predictions_per_model':383,'checkpoint_reload_verified':True}


def run(*,config_path,out,paths=None,files=None):
    """Own one worker process, terminate only that process if the fixed budget is exceeded."""
    paths=paths or resolve_paths();config=load_config(config_path)
    if config.get('loss_adapter'):
        from .el_stability_loss_adapter import require_training_authorization
        require_training_authorization(config)
    resolve_inputs(config,paths,files)
    if config.get('loss_adapter'):
        from .bigmhc_abp_experiment import arm_run
        directory,_=arm_run(out,paths,config)
    else:
        directory,_=teacher._run(out,paths)
    import psutil
    command=[sys.executable,'-B','-m','stability_label_curation','bigmhc-smoke','--config',str(Path(config_path).absolute()),'--out',str(directory),'--worker']
    for name,path in (files or {}).items():command+=['--input',name+'='+str(path)]
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS=str(config['cpu_threads']),
        MKL_NUM_THREADS=str(config['cpu_threads']),TORCH_FORCE_WEIGHTS_ONLY_LOAD='1',PYTHONPATH=str(paths.repository_root/'src'))
    if config['device']=='cuda':
        cuda_visibility(environment)
        environment['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    start=time.monotonic();peak=0;blocker=None
    with raw._directory(directory/'logs') as fd,os.fdopen(os.open('training.log',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=fd),'wb') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=environment,cwd=paths.repository_root)
        try:
            monitored=psutil.Process(process.pid)
            while process.poll() is None:
                try:peak=max(peak,monitored.memory_info().rss)
                except psutil.NoSuchProcess:pass
                if time.monotonic()-start>config['wall_seconds']:blocker='wall_clock_budget_exceeded'
                if peak>config['memory_bytes']:blocker='worker_RSS_budget_exceeded'
                if blocker:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=5)
    result={'elapsed_seconds':time.monotonic()-start,'peak_worker_RSS_bytes':peak,'wall_budget_seconds':config['wall_seconds'],
        'RSS_budget_bytes':config['memory_bytes'],'worker_exit_code':process.returncode,'blocker':blocker,
        'status':'completed' if process.returncode==0 and blocker is None else 'failed'}
    raw.write_report(directory/'reports/resource_execution.json',result,paths=paths)
    if result['status']!='completed':raise RuntimeError('Bounded BigMHC smoke failed; inspect logs/training.log: '+str(result))
    return result
