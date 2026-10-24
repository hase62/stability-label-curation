"""Task 2.37 frozen measured-Tm output-only adaptation and scoring.

Training can read only measured/EL-decoy sidecars and identity-only encoded inputs.
Experimental IM outcomes are read solely by the separately invoked evaluation.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal, localcontext
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time
from typing import Any

from .paths import StoragePaths, resolve_paths
from . import measured_tm_preflight as data
from . import el_only_zero_shot_im as native
from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as historical
from .sequence_hamming import NearestNineIndex, valid_ninemer
from .replicate_stability_association import read_rows, write_rows, write_json

RUN='task-2_37-a02-measured-tm-direct-transfer'
BRANCH='task/2.37-a02-measured-tm-direct-transfer'
BASE='f8e972ef340dab4d697c66debb7c61cb3dc19183'
CONFIG='configs/measured_tm_a02_direct_transfer_task2_37.json'
PROTOCOL='docs/MEASURED_TM_A02_DIRECT_TRANSFER_TASK2_37_PROTOCOL.md'
SEEDS=(123,456,789)
ADAPTED=('D','P','T')
OUTPUT_KEYS=('condenser.out.weight','condenser.out.bias')
CONDITIONS=('A',)+tuple(f'{a}_{seed}' for seed in SEEDS for a in ADAPTED)
sha,assert_sha,digest,utc,resources=native.sha,native.assert_sha,native.digest,native.utc,native.resources


def config(paths: StoragePaths) -> dict:
    value=json.loads((paths.repository_root/CONFIG).read_text())
    fixed={'run_id':RUN,'seeds':list(SEEDS),'measured':710,'decoys':11360,'passes':20,'batch_size':64,
           'measured_weight':16,'decoy_weight':1,'loss_denominator':'sum_sample_weights','include_neoepitope':True,
           'learned_feature_cache':False,'evaluation_batch_size':16,'bootstrap_draws':10000,'HLA':'HLA-A*02:01'}
    if any(value.get(k)!=v for k,v in fixed.items()) or value['optimizer']!={'lr':.001,'weight_decay':.01,'betas':[.9,.999],'eps':1e-8,'amsgrad':False,'foreach':False,'fused':False}:
        raise ValueError('Prespecified experimental settings changed')
    return value


def science(paths: StoragePaths) -> dict:
    files=[CONFIG,PROTOCOL,'src/stability_label_curation/measured_tm_direct_transfer.py',
        'src/stability_label_curation/measured_tm_direct_transfer_evaluation.py','tests/test_measured_tm_direct_transfer.py',
        'src/stability_label_curation/el_only_zero_shot_im.py','src/stability_label_curation/bigmhc_baseline_runner.py',
        'src/stability_label_curation/bigmhc_el_multiepoch.py','src/stability_label_curation/third_party_evaluation.py',
        'src/stability_label_curation/sequence_hamming.py','src/stability_label_curation/paths.py',
        'src/stability_label_curation/replicate_stability_association.py']
    return {f:sha(paths.repository_root/f) for f in files}


def begin(paths: StoragePaths, stage: str) -> tuple[Path,float]:
    git=lambda *args:subprocess.check_output(['git',*args],cwd=paths.repository_root,text=True).strip()
    if git('branch','--show-current')!=BRANCH or git('status','--porcelain') or git('merge-base',BASE,'HEAD')!=BASE:
        raise ValueError('Clean committed authorized Task2.37 branch required')
    directory=paths.project_runs_dir/RUN
    if stage=='prepare':directory.mkdir(parents=True,exist_ok=False)
    for name in ('reports','inputs','checkpoints','predictions','evaluation','logs'):
        (directory/name).mkdir(parents=True,exist_ok=True)
    write_json(directory/f'reports/{stage}_started.json',{'utc':utc(),'commit':git('rev-parse','HEAD'),'scientific_hashes':science(paths)})
    return directory,time.monotonic()


def require(paths: StoragePaths, name: str) -> tuple[Path,dict]:
    d=paths.project_runs_dir/RUN;value=json.loads((d/f'reports/{name}.json').read_text())
    if value['scientific_hashes']!=science(paths):
        repair=json.loads((d/'reports/technical_reload_repair.json').read_text())
        if (value['scientific_hashes']!=repair['previous_scientific_hashes']
                or science(paths)!=repair['corrected_scientific_hashes']):
            raise ValueError('Code differs from the recorded checkpoint-metadata repair')
    return d,value


def previous(paths: StoragePaths,cfg: dict) -> tuple[Path,dict]:
    old=paths.project_runs_dir/'task-2_32-el-only-zero-shot-im'
    assert_sha(old/'reports/output_manifest.json',cfg['task2_32_manifest_sha256'])
    return old,json.loads((old/'reports/output_manifest.json').read_text())['files_sha256']


def authenticated_json(root: Path, manifest: dict, relative: str) -> dict:
    assert_sha(root/relative,manifest[relative]);return json.loads((root/relative).read_text())


def baseline(paths: StoragePaths,cfg: dict) -> tuple[dict,dict,list[str]]:
    old,manifest=previous(paths,cfg)
    receipt=authenticated_json(old,manifest,'reports/EL_model_identities.json')
    keys=receipt['keys'];model=receipt['models']['A']
    directory=paths.project_runs_dir/'task-2_23-el-multiepoch-baseline/checkpoints/EL_epoch_10'
    files=runner.checkpoint_identity(directory,keys)
    if len(keys)!=36 or files!=model['files'] or digest(files)!=cfg['baseline_file_map_sha256']:
        raise ValueError('Authentic complete EL10 A checkpoint mismatch')
    source=historical.inputs(paths,{'inputs':cfg['inputs']})
    return {**model,'directory':str(directory)},source,keys


def target_vectors(rows: list[dict], seed: int) -> tuple[dict,dict]:
    measured=[i for i,r in enumerate(rows) if r['kind']=='measured']
    actual=[r['target'] if r['kind']=='measured' else 0. for r in rows]
    shuffled=list(measured);random.Random(2370000+seed).shuffle(shuffled)
    permuted=list(actual)
    for destination,origin in zip(measured,shuffled,strict=True):permuted[destination]=actual[origin]
    if Counter(actual[i] for i in measured)!=Counter(permuted[i] for i in measured):raise ValueError('Positive multiset changed')
    vectors={'D':[1. if r['kind']=='measured' else 0. for r in rows],'P':permuted,'T':actual}
    assignments=[{'destination_source_id':rows[i]['source_id'],'origin_source_id':rows[j]['source_id'],
                  'target_decimal':rows[j]['target_decimal'],'target':actual[j]} for i,j in zip(measured,shuffled,strict=True)]
    return vectors,{'seed':seed,'permutation_seed':2370000+seed,'assignments':assignments,
                    'multiset_preserved':True,'changed_assignments':sum(i!=j for i,j in zip(measured,shuffled)),
                    'changed_target_values':sum(actual[i]!=actual[j] for i,j in zip(measured,shuffled))}


def orders(n: int,seed: int,passes: int=20) -> list[list[int]]:
    rng=random.Random(seed);values=list(range(n));result=[]
    for _ in range(passes):rng.shuffle(values);result.append(list(values))
    return result


def prepare(paths: StoragePaths) -> dict:
    d,start=begin(paths,'prepare');cfg=config(paths);model,_,keys=baseline(paths,cfg)
    old=paths.project_runs_dir/'task-2_35-measured-tm-eligibility-preflight'
    assert_sha(old/'reports/output_manifest.json',cfg['task2_35_manifest_sha256'])
    hashes=json.loads((old/'reports/output_manifest.json').read_text())['files_sha256']
    def rows(relative):assert_sha(old/relative,hashes[relative]);return read_rows(old/relative)
    raw=rows('manifests/measured_Tm_preferred_panel.jsonl')
    measured=[r for r in raw if r['hla']==cfg['HLA'] and r['preferred_training_eligible']]
    selected=rows('decoys/A0201_provisional_selected_identities.jsonl')
    pool=rows('decoys/A0201_candidate_identities.jsonl')
    all_tm=rows('manifests/source_measurements_all_lengths.jsonl')
    if len(measured)!=710 or len(selected)!=11360 or sum(r['hla']==cfg['HLA'] for r in raw)!=711:
        raise ValueError('Fixed A0201 population differs')
    expected=sorted([r for r in pool if r['adaptation_decoy_eligible']],key=lambda r:(hashlib.sha256(('Task2.35-decoy-v1|'+r['hla']+'|'+r['peptide']).encode()).hexdigest(),r['hla'],r['peptide']))[:11360]
    if selected!=expected:raise ValueError('Provisional decoys need Task2.35 deterministic replacement before training')
    wanted={r['source_id']:r for r in selected};found=set();positive=set()
    split=paths.project_runs_dir/'task-2_23-el-multiepoch-baseline/processed/el_split_manifest_v1.csv.gz'
    assert_sha(split,'6b3a6a0c00f86c26e51b84a8df1dd7e81d545117baa871dabd0707edaf89ac00')
    with gzip.open(split,'rt',newline='') as stream:
        for row in csv.DictReader(stream):
            if row['original_label']=='1':positive.add(row['peptide'])
            if row['source_row_id'] not in wanted:continue
            current=wanted[row['source_row_id']]
            if (row['partition']!='train' or row['original_label']!='0' or row['peptide']!=current['peptide']
                    or row['HLA']!=current['hla'] or row['source_row_sha256']!=current['source_row_sha256']):
                raise ValueError('Authenticated EL-negative binding mismatch')
            found.add(row['source_row_id'])
    if found!=set(wanted):raise ValueError('Selected EL-negative provenance missing')
    measured_sequences={r['peptide'] for r in all_tm}
    blocked_sequences=positive|measured_sequences
    for row in selected:
        if (row['hla']!=cfg['HLA'] or not valid_ninemer(row['peptide']) or row['peptide'] in blocked_sequences
                or row['exclusion_reasons'] or not row['adaptation_decoy_eligible']):raise ValueError('Ineligible provisional negative: stop before training')
    training=[]
    for row in measured:
        with localcontext() as ctx:
            ctx.prec=50;derived=Decimal('.5')+(Decimal(row['Tm_C_original_numeric_text'])-37)/72
        if Decimal(row['target_decimal'])!=derived or not 0<=float(derived)<=1:raise ValueError('Authentic target binding differs')
        training.append({**row,'kind':'measured','sample_weight':16.})
    training.extend({**r,'kind':'decoy','target':0.,'sample_weight':1.} for r in selected)
    training.sort(key=lambda r:r['source_id'])
    if len(training)!=12070 or len({r['source_id'] for r in training})!=12070 or len({r['peptide'] for r in training})!=12070:
        raise ValueError('Training identity cardinality differs')
    cohorts,refs=data.cohort_identities(paths)
    external,external_manifest=previous(paths,cfg)
    outcome_hashes={}
    for name in cohorts:
        relative=f'cohorts/{name}_outcomes.jsonl'
        assert_sha(external/relative,external_manifest[relative])
        outcome_hashes[name]=external_manifest[relative]
    leakage={}
    for name,cohort in cohorts.items():
        index=NearestNineIndex(r['peptide'] for r in cohort);pairs={(r['hla'],r['peptide']) for r in cohort};witnesses=[]
        for row in training:
            distance,witness=index.nearest(row['peptide']);pair=(row['hla'],row['peptide']) in pairs
            if pair or distance is None or distance<3:raise ValueError('Unresolved adaptation/evaluation leakage')
            witnesses.append({'source_id':row['source_id'],'peptide':row['peptide'],'hla':row['hla'],'exact_pair':pair,
                              'minimum_Hamming':distance,'nearest_evaluation_peptide':witness})
        write_rows(d/f'inputs/leakage_to_{name}.jsonl',witnesses)
        leakage[name]={'exact_pair':0,'exact_peptide':0,'distance_le_2':0,'minimum_distance':min(r['minimum_Hamming'] for r in witnesses),'index':index.evidence()}
        write_rows(d/f'inputs/{name}_identities.jsonl',cohort)
    primary=[r['source_id'] for r in cohorts['IMPROVE'] if r['hla']==cfg['HLA']]
    if len(primary)!=616 or len({r['patient_peptide_component'] for r in cohorts['IMPROVE'] if r['source_id'] in set(primary)})!=16:
        raise ValueError('Prespecified primary identities/components differ')
    write_json(d/'inputs/evaluation_subsets.json',{'IMPROVE_A02':primary,
        'IMPROVE_B07':[r['source_id'] for r in cohorts['IMPROVE'] if r['hla']=='HLA-B*07:02'],
        'IMPROVE_other':[r['source_id'] for r in cohorts['IMPROVE'] if r['hla'] not in ('HLA-A*02:01','HLA-B*07:02')],
        'neoepitope_A02':[r['source_id'] for r in cohorts['neoepitope'] if r['hla']==cfg['HLA']]})
    write_rows(d/'inputs/training.jsonl',training)
    seed_receipts={}
    for seed in SEEDS:
        vectors,permutation=target_vectors(training,seed);schedule=orders(len(training),seed)
        write_json(d/f'inputs/targets_{seed}.json',vectors);write_json(d/f'inputs/permutation_{seed}.json',permutation)
        write_json(d/f'inputs/orders_{seed}.json',schedule)
        seed_receipts[str(seed)]={'permutation_sha256':sha(d/f'inputs/permutation_{seed}.json'),
            'targets_sha256':sha(d/f'inputs/targets_{seed}.json'),'schedule_sha256':sha(d/f'inputs/orders_{seed}.json'),
            'ordered_batch_index_hashes':[digest([order[i:i+64] for i in range(0,len(order),64)]) for order in schedule]}
    write_json(d/'reports/baseline_identity.json',{'model':model,'keys':keys})
    write_json(d/'reports/scientific_configuration.json',cfg)
    frozen={str(f.relative_to(d)):sha(f) for f in (d/'inputs').iterdir()}
    frozen.update({rel:sha(d/rel) for rel in ['reports/baseline_identity.json','reports/scientific_configuration.json']})
    result={'status':'PASS','scientific_hashes':science(paths),'frozen_inputs':frozen,'source_counts':{'measured':710,'decoys':11360,'total':12070},
        'measured_flagged_minima':sum(bool(r['quality_flags']) for r in measured),'leakage':leakage,'cohorts':refs,
        'seeds':seed_receipts,'negative_replacements':0,'IM_outcome_values_read':False,'outcome_bytes_authenticated':outcome_hashes,
        'two_HLA_NO_GO_unchanged':True,'resources':resources(start)}
    write_json(d/'reports/prepared.json',result);return result


def inputs(paths: StoragePaths) -> tuple[Path,dict,dict]:
    d,receipt=require(paths,'prepared')
    for name,expected in receipt['frozen_inputs'].items():assert_sha(d/name,expected)
    return d,config(paths),receipt


def freeze_output_only(model: Any) -> dict:
    model.eval()
    for key,value in model.named_parameters():value.requires_grad_(key in OUTPUT_KEYS);value.grad=None
    names=[k for k,v in model.named_parameters() if v.requires_grad]
    count=sum(v.numel() for v in model.parameters() if v.requires_grad)
    if set(names)!=set(OUTPUT_KEYS) or count!=415 or any(module.training for module in model.modules()):
        raise ValueError('Final-output-only freeze failed')
    return {'trainable_keys':names,'trainable_scalar_count':count,'all_modules_eval':True}


def balanced_loss(torch: Any, logits: Any, targets: Any, weights: Any) -> Any:
    losses=torch.nn.functional.binary_cross_entropy_with_logits(logits,targets,reduction='none')
    return (losses*weights).sum()/weights.sum()


def encode_inputs(torch: Any,Dataset: Any,encodings: dict,rows: list[dict],batch_size: int) -> dict:
    dataset=native.native_dataset(Dataset,torch,encodings,rows);dataset.makebats(batch_size,shuffle=False,negfrac=None)
    mhc=[];pep=[];emitted=[]
    for index in range(len(dataset)):
        batch=dataset[index];mhc.append(batch.mhc.float());pep.append(batch.pep.float())
        emitted.extend(dataset.getbat(index,enc=False)['_source_id'].tolist())
    if emitted!=[r['source_id'] for r in rows]:raise ValueError('Native input encoding/source order differs')
    return {'mhc':torch.cat(mhc),'pep':torch.cat(pep)}


def save_tensors(torch: Any,path: Path,value: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:torch.save(value,stream)


def replace_output(torch: Any,model: Any,head: dict) -> None:
    if set(head)!=set(OUTPUT_KEYS):raise ValueError('Only two final output tensors allowed')
    state=dict(model.state_dict())
    for key,value in head.items():
        if value.shape!=state[key].shape or value.dtype!=torch.float32 or not torch.isfinite(value).all():
            raise ValueError('Invalid adapted output tensor')
        state[key]=value
    model.load_state_dict(state,strict=True)


def runtime(torch: Any,np: Any,cfg: dict) -> str:
    runner.seed_runtime(torch,np,cfg);return runner.runtime_device(torch,cfg)


def preflight(paths: StoragePaths) -> dict:
    d,cfg,_=inputs(paths);d,start=begin(paths,'preflight');model_ref,files,keys=baseline(paths,cfg)
    import torch
    import numpy as np
    device=runtime(torch,np,cfg)
    rows=read_rows(d/'inputs/training.jsonl');cohorts={n:read_rows(d/f'inputs/{n}_identities.jsonl') for n in data.COHORTS}
    enc=native.encoding_map(torch,files['reference'],{r['hla'] for group in [rows,*cohorts.values()] for r in group})
    encoded={};probes=[]
    with runner.pinned_modules(files) as (BigMHC,Dataset):
        model=runner.load_checkpoint(torch,BigMHC,model_ref['directory'],keys,device=device,lineage=None)
        if runner.state_hashes(model)!=model_ref['state']:raise ValueError('Exact baseline reload differs')
        freezing=freeze_output_only(model)
        encoded['training']=encode_inputs(torch,Dataset,enc,rows,64)
        for name,group in cohorts.items():encoded[name]=encode_inputs(torch,Dataset,enc,group,16)
        for indices in [list(range(64)),list(range(100,164)),list(range(len(rows)-38,len(rows)))]:
            native_data=native.native_dataset(Dataset,torch,enc,[rows[i] for i in indices]);native_data.makebats(64,shuffle=False,negfrac=None)
            batch=native_data[0];mhc=encoded['training']['mhc'][indices].to(device);pep=encoded['training']['pep'][indices].to(device)
            if not torch.equal(batch.mhc.float().to(device),mhc) or not torch.equal(batch.pep.float().to(device),pep):raise ValueError('Cached encoding differs')
            with torch.no_grad():original,_=model(batch.mhc.float().to(device),batch.pep.float().to(device));copied,_=model(mhc,pep)
            if not torch.equal(original,copied):raise ValueError('Native forward/encoded input logits differ')
            probes.append({'n':len(indices),'bitwise_input_and_forward_equal':True})
        indices=list(range(64));targets=torch.tensor([rows[i]['target'] for i in indices],device=device);weights=torch.tensor([rows[i]['sample_weight'] for i in indices],device=device)
        logits,_=model(encoded['training']['mhc'][indices].to(device),encoded['training']['pep'][indices].to(device))
        loss=balanced_loss(torch,logits,targets,weights);loss.backward()
        gradients={k:v.grad is not None for k,v in model.named_parameters()}
        if {k for k,v in gradients.items() if v}!=set(OUTPUT_KEYS) or not all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None):
            raise ValueError('Frozen gradient flow failed')
        if runner.state_hashes(model)!=model_ref['state']:raise ValueError('Preflight modified A')
        synthetic=[{'source_id':'synthetic','peptide':'AAAAAAAAA','hla':cfg['HLA']}]
        probe=encode_inputs(torch,Dataset,enc,synthetic,16)
        with torch.no_grad():z,_=model(probe['mhc'].to(device),probe['pep'].to(device))
        old,manifest=previous(paths,cfg);prior=authenticated_json(old,manifest,'reports/preflight.json')
        if float(z[0])!=prior['synthetic_EL_smoke']['A']['logit']:raise ValueError('A synthetic consistency failed')
        for name,group in cohorts.items():
            path=old/f'predictions/{name}_A.jsonl';assert_sha(path,manifest[f'predictions/{name}_A.jsonl'])
            native.join_predictions(group,read_rows(path))
        prior_cfg=authenticated_json(old,manifest,'reports/scientific_configuration.json')
        if prior_cfg['inputs']!=cfg['inputs'] or prior_cfg['batch_size']!=cfg['evaluation_batch_size']:raise ValueError('A prediction pathway differs')
        for key,value in [('Torch',torch.__version__),('NumPy',np.__version__),('Python',platform.python_version())]:
            if prior['runtime'][key]!=value:raise ValueError('A runtime compatibility differs')
    for name,value in encoded.items():save_tensors(torch,d/f'inputs/{name}_encoded.pt',value)
    result={'status':'PASS','scientific_hashes':science(paths),'freeze':freezing,'gradients_only_output':True,'preflight_optimizer_steps':0,
        'native_encoded_forward_probes':probes,'baseline_synthetic_logit':float(z[0]),'A_predictions_reusable':True,
        'learned_feature_cache':False,'encoded_input_hashes':{name:sha(d/f'inputs/{name}_encoded.pt') for name in encoded},
        'runtime':{'Python':platform.python_version(),'Torch':torch.__version__,'NumPy':np.__version__,**runner.device_report(torch,device)},
        'resources':resources(start)}
    write_json(d/'reports/preflight.json',result);return result


def train(paths: StoragePaths, *, resume: bool=False) -> dict:
    d,cfg,_=inputs(paths);_,check=require(paths,'preflight')
    tests=json.loads((d/('reports/focused_tests_reloadfix.json' if resume else 'reports/focused_tests.json')).read_text())
    if tests['status']!='PASS' or tests['scientific_hashes']!=science(paths):raise ValueError('Focused tests missing/stale')
    assert_sha(d/'inputs/training_encoded.pt',check['encoded_input_hashes']['training'])
    repair=None
    if resume:
        repair=json.loads((d/'reports/technical_reload_repair.json').read_text())
        for name,expected in repair['preserved_artifacts'].items():assert_sha(d/name,expected)
    d,start=begin(paths,'train_resumed' if resume else 'train');ref,files,keys=baseline(paths,cfg)
    import torch
    import numpy as np
    device=runtime(torch,np,cfg)
    encoded=torch.load(d/'inputs/training_encoded.pt',map_location=device,weights_only=True)
    rows=read_rows(d/'inputs/training.jsonl');weights=torch.tensor([r['sample_weight'] for r in rows],dtype=torch.float32,device=device)
    completed={}
    with runner.pinned_modules(files) as (BigMHC,_):
        for seed in SEEDS:
            targets=json.loads((d/f'inputs/targets_{seed}.json').read_text());schedule=json.loads((d/f'inputs/orders_{seed}.json').read_text())
            for arm in ADAPTED:
                label=f'{arm}_{seed}'
                if repair and label==repair['recovered_fit']:
                    recovered=json.loads((d/f'checkpoints/{label}/identity.json').read_text())
                    assert_sha(d/recovered['head_relative_path'],recovered['head_sha256'])
                    if recovered['initial_state']!=ref['state'] or recovered['updates']!=3780:
                        raise ValueError('Recovered completed fit does not match the frozen experiment')
                    completed[label]=recovered
                    print('preserved completed fit without retraining',label,flush=True)
                    continue
                random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
                model=runner.load_checkpoint(torch,BigMHC,ref['directory'],keys,device=device,lineage=None);freeze_output_only(model)
                initial=runner.state_hashes(model)
                if initial!=ref['state']:raise ValueError('D/P/T common initialization mismatch')
                initial_output={k:v.detach().clone() for k,v in model.state_dict().items() if k in OUTPUT_KEYS}
                optimizer=torch.optim.AdamW([v for v in model.parameters() if v.requires_grad],**{**cfg['optimizer'],'betas':tuple(cfg['optimizer']['betas'])})
                y=torch.tensor(targets[arm],dtype=torch.float32,device=device);history=[];fit_start=time.monotonic();steps=0
                for epoch,order in enumerate(schedule,1):
                    losses=[];numerator=[];denominator=[]
                    for offset in range(0,len(order),64):
                        ids=torch.tensor(order[offset:offset+64],dtype=torch.int64,device=device)
                        optimizer.zero_grad(set_to_none=True)
                        logits,_=model(encoded['mhc'][ids],encoded['pep'][ids])
                        loss=balanced_loss(torch,logits,y[ids],weights[ids]);loss.backward();optimizer.step();steps+=1
                        losses.append(loss.detach());total_weight=weights[ids].sum();numerator.append(loss.detach()*total_weight);denominator.append(total_weight)
                    values=torch.stack(losses);num=torch.stack(numerator).sum();den=torch.stack(denominator).sum()
                    if (not torch.isfinite(values).all() or any(p.grad is not None for k,p in model.named_parameters() if k not in OUTPUT_KEYS)
                            or any(m.training for m in model.modules()) or float(den)!=22720):raise ValueError('Native loss/frozen/exposure check failed')
                    record={'pass':epoch,'updates':len(losses),'cumulative_updates':steps,'mean_batch_balanced_BCE':float(values.mean()),
                        'pass_weighted_BCE':float(num/den),'weighted_loss_numerator':float(num),'sample_weight_sum':float(den),
                        'batch_source_order_digest':digest([[rows[i]['source_id'] for i in order[j:j+64]] for j in range(0,len(order),64)]),
                        'ordered_index_digest':digest([order[j:j+64] for j in range(0,len(order),64)]),
                        'only_output_gradients':True,'all_modules_eval':True,'measured_exposures':710,'decoy_exposures':11360}
                    history.append(record);write_json(d/f'reports/{label}_pass_{epoch:02d}.json',record)
                    print(label,'pass',epoch,'loss',record['pass_weighted_BCE'],flush=True)
                state=runner.state_hashes(model);changed=[k for k in keys if state[k]!=initial[k]]
                if set(changed)!=set(OUTPUT_KEYS) or steps!=3780:raise ValueError('Forbidden parameter change/update count')
                internal_steps=[int(v['step'].item()) for v in optimizer.state.values()]
                if len(internal_steps)!=2 or any(n!=steps for n in internal_steps):
                    raise ValueError('Persistent AdamW step continuity failed')
                head={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if k in OUTPUT_KEYS}
                path=d/f'checkpoints/{label}/output.pt';save_tensors(torch,path,head)
                with torch.no_grad():before,_=model(encoded['mhc'][:16],encoded['pep'][:16])
                restored=runner.load_checkpoint(torch,BigMHC,ref['directory'],keys,device=device,lineage=None)
                replace_output(torch,restored,torch.load(path,map_location=device,weights_only=True));freeze_output_only(restored)
                with torch.no_grad():after,_=restored(encoded['mhc'][:16],encoded['pep'][:16])
                if runner.state_hashes(restored)!=state or not torch.equal(before,after):raise ValueError('Adapted checkpoint reload mismatch')
                scalar_changes={k:int(torch.count_nonzero(initial_output[k].cpu()!=head[k])) for k in OUTPUT_KEYS}
                receipt={'arm':arm,'seed':seed,'status':'COMPLETE','passes':20,'updates':steps,'rows':12070,
                    'parent_EL_file_map_sha256':cfg['baseline_file_map_sha256'],'initial_state':initial,'state':state,
                    'changed_keys':changed,'changed_scalar_counts':scalar_changes,'trainable_scalar_count':415,
                    'head_relative_path':str(path.relative_to(d)),'head_sha256':sha(path),'complete_state_digest':digest(state),
                    'strict_parent_plus_two_tensor_reload_equal':True,'training_probe_bitwise_equal':True,
                    'optimizer_defaults':optimizer.defaults,'optimizer_internal_steps':internal_steps,
                    'history':history,'seconds':time.monotonic()-fit_start,
                    'training_inputs_sha256':sha(d/'inputs/training.jsonl'),'targets_sha256':sha(d/f'inputs/targets_{seed}.json')}
                write_json(d/f'checkpoints/{label}/identity.json',receipt);completed[label]=receipt
                del optimizer,model,restored,initial_output
    result={'status':'ALL_NINE_FITS_COMPLETE','scientific_hashes':science(paths),'fits':completed,'A_unchanged':True,
        'IM_labels_read':False,'all_epochs_final_20_no_selection':True,'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),
        'peak_GPU_reserved_bytes':torch.cuda.max_memory_reserved(),'resources':resources(start)}
    write_json(d/'reports/training_complete.json',result);return {k:v for k,v in result.items() if k!='fits'}


def inference(paths: StoragePaths) -> dict:
    d,cfg,_=inputs(paths);_,trained=require(paths,'training_complete');_,check=require(paths,'preflight');d,start=begin(paths,'inference')
    ref,files,keys=baseline(paths,cfg);old,manifest=previous(paths,cfg)
    import torch
    import numpy as np
    device=runtime(torch,np,cfg);receipt={}
    cohorts={n:read_rows(d/f'inputs/{n}_identities.jsonl') for n in data.COHORTS};encoded={}
    for name,rows in cohorts.items():
        assert_sha(d/f'inputs/{name}_encoded.pt',check['encoded_input_hashes'][name])
        encoded[name]=torch.load(d/f'inputs/{name}_encoded.pt',map_location=device,weights_only=True)
        source=old/f'predictions/{name}_A.jsonl';assert_sha(source,manifest[f'predictions/{name}_A.jsonl']);native.join_predictions(rows,read_rows(source))
        target=d/f'predictions/{name}_A.jsonl'
        if target.exists():raise ValueError('Refuse A prediction overwrite')
        shutil.copyfile(source,target);receipt[name+'_A']={'sha256':sha(target),'n':len(rows),'reused_A':True,'score_field':'EL_probability'}
    with runner.pinned_modules(files) as (BigMHC,_):
        for label,fit in trained['fits'].items():
            path=d/fit['head_relative_path'];assert_sha(path,fit['head_sha256'])
            model=runner.load_checkpoint(torch,BigMHC,ref['directory'],keys,device=device,lineage=None)
            replace_output(torch,model,torch.load(path,map_location=device,weights_only=True));model.eval()
            if runner.state_hashes(model)!=fit['state']:raise ValueError('Adapted model state differs')
            for name,rows in cohorts.items():
                predicted=[]
                with torch.no_grad():
                    for offset in range(0,len(rows),16):
                        z,_=model(encoded[name]['mhc'][offset:offset+16],encoded[name]['pep'][offset:offset+16]);scores=torch.sigmoid(z)
                        for identity,logit,score in zip(rows[offset:offset+16],z.cpu().tolist(),scores.cpu().tolist(),strict=True):
                            if not math.isfinite(logit) or not math.isfinite(score) or not 0<=score<=1:raise ValueError('Nonfinite adapted score')
                            predicted.append({**identity,'raw_logit':logit,'score':score})
                if any({k:v for k,v in p.items() if k not in ('raw_logit','score')}!=r for r,p in zip(rows,predicted,strict=True)):
                    raise ValueError('Adapted prediction/source alignment failed')
                path=d/f'predictions/{name}_{label}.jsonl';write_rows(path,predicted)
                receipt[name+'_'+label]={'sha256':sha(path),'n':len(rows),'reused_A':False,'score_field':'score',
                    'semantics':'adapted ligand/thermostability-derived discrimination score; not calibrated EL/IM probability'}
                print('frozen predictions',name,label,len(rows),flush=True)
            if runner.state_hashes(model)!=fit['state']:raise ValueError('Scoring changed model parameters')
            del model
    result={'status':'ALL_TWENTY_PREDICTION_FILES_FROZEN','scientific_hashes':science(paths),'predictions':receipt,
        'frozen_utc':utc(),'all_models_unchanged_during_inference':True,'higher_score_is_positive':True,'IM_outcome_values_read':False,
        'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),'resources':resources(start)}
    write_json(d/'reports/predictions_frozen.json',result);return result


def main() -> None:
    if len(sys.argv)!=2 or sys.argv[1] not in ('prepare','preflight','train','resume-train','inference','evaluate'):
        raise SystemExit('prepare | preflight | train | resume-train | inference | evaluate')
    paths=resolve_paths()
    try:
        if sys.argv[1]=='evaluate':
            from .measured_tm_direct_transfer_evaluation import evaluate
            result=evaluate(paths)
        elif sys.argv[1]=='resume-train':result=train(paths,resume=True)
        else:result=globals()[sys.argv[1]](paths)
        print(json.dumps(result,allow_nan=False,sort_keys=True),flush=True)
    except Exception as exc:
        d=paths.project_runs_dir/RUN
        if d.exists():write_json(d/f'reports/{sys.argv[1]}_failure_{time.time_ns()}.json',{'utc':utc(),'error':repr(exc),'scientific_hashes':science(paths)})
        raise


if __name__=='__main__':main()
