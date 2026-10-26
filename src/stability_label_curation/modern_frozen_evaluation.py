"""Task 2.40 Stage B: sealed-score-only paired evaluation, never model inference."""
from __future__ import annotations
from collections import Counter
import gzip
import json
from pathlib import Path
import random
import sys
import time

from .modern_frozen_scoring import RUN,PARENT,COLUMNS,config,read_rows,write_rows,write_json,git,software_hashes,utc
from .modern_model_preflight import digest,verify_digest,object_hash
from .third_party_evaluation import WeightedRanking
from .bigmhc_independent_evaluation import quantile

CONTRASTS={'fusion_minus_EL_rank':('fusion_rank_50_50','mix_el_rank'),
           'native_stability_minus_native_EL':('spearmint_spa37_log1p_half_life','mix_el_native'),
           'stability_rank_minus_EL_rank':('stability_rank','mix_el_rank')}


class FrozenRanking(WeightedRanking):
    """Reuse authenticated AP/AUROC; apply Task239 fractional top-K ties."""
    def metrics(self,weights,*,top_k: bool=True) -> dict:
        import numpy as np
        result=super().metrics(weights,top_k=False)
        if not top_k:return result
        result.update(precision_at_10=None,precision_at_20=None)
        w=np.asarray(weights,dtype=np.int64)[self.order]
        if not len(w):return result
        group_n=np.add.reduceat(w,self.starts);group_p=np.add.reduceat(w*self.labels,self.starts)
        before=np.cumsum(group_n)-group_n
        for k in (10,20):
            if int(w.sum())>=k:
                take=np.minimum(group_n,np.maximum(0,k-before))
                fraction=np.divide(group_p,group_n,out=np.zeros(len(group_n),dtype=float),where=group_n>0)
                result['precision_at_'+str(k)]=float(np.sum(take*fraction)/k)
        return result


def rankings(rows: list[dict]) -> dict:
    return {c:FrozenRanking(rows,c) for c in COLUMNS}


def metrics(rows: list[dict]) -> dict:
    import numpy as np
    result={c:r.metrics(np.ones(len(rows),dtype=np.int64)) for c,r in rankings(rows).items()}
    contrasts={name:{m:result[a][m]-result[b][m] if result[a][m] is not None and result[b][m] is not None else None
                     for m in ('AP','AUROC','precision_at_10','precision_at_20')} for name,(a,b) in CONTRASTS.items()}
    positive=sum(r['label'] for r in rows)
    ap=result['mix_el_rank']['AP'];delta=contrasts['fusion_minus_EL_rank']['AP']
    return {'n':len(rows),'positive':positive,'negative':len(rows)-positive,
            'prevalence':positive/len(rows) if rows else None,'components':len({r['patient_peptide_component'] for r in rows}),
            'arms':result,'contrasts':contrasts,
            'primary_relative_AP_change_percent':100*delta/ap if ap is not None and ap>0 and delta is not None else None}


def bootstrap(rows: list[dict], units: list[str], *,draws: int,seed: int,evidence: Path | None=None) -> dict:
    import numpy as np
    if units!=sorted(set(units)):raise ValueError('Original dependence-unit list must be sorted and unique')
    if len(units)<2:return {'attempted':0,'requested':draws,'valid':0,'invalid_reasons':{'fewer_than_two_units':draws},'intervals':None}
    mapping={u:i for i,u in enumerate(units)}
    index=np.array([mapping[r['patient_peptide_component']] for r in rows],dtype=np.int64)
    outcomes=np.array([r['label'] for r in rows],dtype=np.int64)
    fixed=rankings(rows);rng=random.Random(seed);samples={n:{m:[] for m in ('AP','AUROC')} for n in CONTRASTS}
    invalid=Counter();valid=0
    stream=gzip.open(evidence,'xt') if evidence else None
    try:
        for draw in range(draws):
            chosen=rng.choices(units,k=len(units));counts=np.bincount([mapping[u] for u in chosen],minlength=len(units))
            weights=counts[index];n=int(weights.sum());positive=int(weights@outcomes)
            arms={c:rank.metrics(weights,top_k=False) for c,rank in fixed.items()}
            reason='empty' if n==0 else 'no_positive' if positive==0 else 'no_negative' if positive==n else None
            if reason:invalid[reason]+=1
            else:valid+=1
            contrasts={}
            for name,(a,b) in CONTRASTS.items():
                contrasts[name]={}
                for m in ('AP','AUROC'):
                    v=arms[a][m]-arms[b][m] if arms[a][m] is not None and arms[b][m] is not None else None
                    contrasts[name][m]=v
                    if v is not None:samples[name][m].append(v)
            if stream:stream.write(json.dumps({'draw':draw+1,'component_multiplicities':counts.tolist(),'n':n,'positive':positive,
                'invalid_reason':reason,'arms':{c:{m:arms[c][m] for m in ('AP','AUROC')} for c in COLUMNS},
                'contrasts':contrasts},sort_keys=True,allow_nan=False)+'\n')
            if evidence and (draw+1)%2000==0:print(evidence.name,draw+1,flush=True)
    finally:
        if stream:stream.close()
    return {'requested':draws,'attempted':draws,'valid':valid,'invalid':draws-valid,'invalid_reasons':dict(invalid),
        'seed':seed,'RNG':'random.Random.choices','units':units,'number_of_units':len(units),
        'component_sizes':dict(Counter(r['patient_peptide_component'] for r in rows)),
        'ranks_recomputed':False,'paired_same_draw_for_all_conditions':True,
        'intervals':{n:{m:{'lower_95':quantile(v,.025),'upper_95':quantile(v,.975),'valid':len(v),'invalid':draws-len(v)}
                          for m,v in values.items()} for n,values in samples.items()},
        'limitation':'Conditional component-resampling uncertainty, not 7788 independent biological experiments; prior exploratory cohort exposure'}


def gate() -> tuple:
    paths,repo,cfg=config();run=paths.project_runs_dir/RUN;parent=paths.project_runs_dir/PARENT
    public=repo/'configs/task240_prediction_seal.json'
    stamp=json.loads(public.read_text())
    precommit=git(repo,'log','-1','--format=%H','--','configs/task240_prediction_seal.json')
    if not precommit or git(repo,'show',precommit+':configs/task240_prediction_seal.json')!=public.read_text().strip():raise ValueError('Pre-evaluation seal is not committed')
    if git(repo,'status','--porcelain'):raise ValueError('Worktree must be clean at evaluation/verification')
    freeze=json.loads((run/'prediction_freeze.json').read_text());verify_digest(run/'prediction_freeze.json',stamp['prediction_freeze_sha256'])
    if freeze['status']!='SEALED_BEFORE_IM_OUTCOMES' or freeze['labels_accessed']:raise ValueError('Predictions not sealed label-blind')
    if software_hashes(repo,cfg)!=freeze['scientific_hashes']:raise ValueError('Scientific code/config changed after seal')
    for n,h in freeze['artifact_sha256'].items():verify_digest(run/n,h)
    verify_digest(parent/'final_receipt.json',cfg['parent_receipt_sha256'])
    scores=read_rows(run/'frozen_scores.jsonl');keys=[r['source_id'] for r in scores]
    if len(keys)!=7788 or len(set(keys))!=7788 or object_hash(keys)!=cfg['ordered_keys_sha256']:raise ValueError('Frozen scores identity mismatch')
    excluded=json.loads((run/'sensitivity_excluded_row_keys.json').read_text())
    if len(excluded)!=8 or object_hash(excluded)!=cfg['sensitivity_key_hash']:raise ValueError('Sensitivity identity mask mismatch')
    return paths,repo,cfg,run,scores,set(excluded),precommit


def load_outcomes(paths,cfg: dict,scores: list[dict]) -> list[dict]:
    spec=cfg['evaluation_outcomes'];root=paths.project_runs_dir/spec['run_id']
    verify_digest(root/spec['freeze'],spec['freeze_sha256'])
    source=json.loads((root/spec['freeze']).read_text())
    if source['immutable_artifact_hashes'][spec['outcomes']]!=spec['outcomes_sha256']:raise ValueError('Original label provenance binding differs')
    verify_digest(root/spec['outcomes'],spec['outcomes_sha256']);labels=read_rows(root/spec['outcomes'])
    if [r['source_id'] for r in labels]!=[r['source_id'] for r in scores]:raise ValueError('Outcome row association differs')
    if any(type(r['label']) is not int or r['label'] not in (0,1) for r in labels):raise ValueError('Invalid original outcome')
    joined=[{**r,'label':y['label'],'scores':{c:r[c] for c in COLUMNS}} for r,y in zip(scores,labels,strict=True)]
    if len(joined)!=7788 or sum(r['label'] for r in joined)!=227:raise ValueError('Frozen class counts differ')
    return joined


def populations(rows: list[dict], excluded: set[str]) -> dict:
    return {'full_IMPROVE':rows,'A0201':[r for r in rows if r['hla']=='HLA-A*02:01'],
            'training_neighbor_excluded':[r for r in rows if r['source_id'] not in excluded]}


def point_tables(rows: list[dict],excluded: set[str]) -> dict:
    sets=populations(rows,excluded)
    if len(sets['A0201'])!=616 or sum(r['label'] for r in sets['A0201'])!=21:raise ValueError('Frozen A0201 subgroup differs')
    return {'populations':{name:metrics(group) for name,group in sets.items()},
        'per_HLA':{a:metrics([r for r in rows if r['hla']==a]) for a in sorted({r['hla'] for r in rows})}}


def evaluate() -> None:
    paths,repo,cfg,run,scores,excluded,precommit=gate()
    if (run/'evaluation_started.json').exists():raise FileExistsError('One frozen evaluation already started; preserve results')
    write_json(run/'pre_evaluation_receipt.json',{'pre_evaluation_commit':precommit,'utc':utc(),
        'prediction_freeze_sha256':digest(run/'prediction_freeze.json'),'scientific_hashes':software_hashes(repo,cfg),
        'labels_opened':False})
    write_json(run/'evaluation_started.json',{'utc':utc(),'pre_evaluation_commit':precommit,'next_operation':'authenticate and open original IM outcome sidecar'})
    start=time.monotonic();joined=load_outcomes(paths,cfg,scores)
    points=point_tables(joined,excluded);write_json(run/'aggregate_metrics.json',points)
    sets=populations(joined,excluded);uncertainty={}
    full_units=sorted({r['patient_peptide_component'] for r in joined})
    a_units=sorted({r['patient_peptide_component'] for r in sets['A0201']})
    if len(full_units)!=38 or len(a_units)!=16:raise ValueError('Authentic dependence structure changed')
    for name,group in sets.items():
        units=a_units if name=='A0201' else full_units
        uncertainty[name]=bootstrap(group,units,draws=cfg['bootstrap_attempts'],seed=cfg['bootstrap_seed'],evidence=run/(name+'_bootstrap.jsonl.gz'))
        write_json(run/'paired_uncertainty.json',uncertainty)
    write_rows(run/'joined_scores_outcomes.jsonl',joined)
    write_json(run/'evaluation_complete.json',{'status':'COMPLETE','utc':utc(),'seconds':time.monotonic()-start,
        'pre_evaluation_commit':precommit,'prediction_freeze_sha256':digest(run/'prediction_freeze.json'),
        'original_outcomes_sha256':cfg['evaluation_outcomes']['outcomes_sha256'],
        'point_metrics_sha256':digest(run/'aggregate_metrics.json'),'uncertainty_sha256':digest(run/'paired_uncertainty.json'),
        'model_reruns':0,'ranks_recomputed':False,'training':False,'calibration':False})
    print('Frozen exploratory evaluation COMPLETE',flush=True)


def verify() -> None:
    paths,repo,cfg,run,scores,excluded,precommit=gate()
    complete=json.loads((run/'evaluation_complete.json').read_text())
    joined=load_outcomes(paths,cfg,scores);points=point_tables(joined,excluded)
    if points!=json.loads((run/'aggregate_metrics.json').read_text()):raise ValueError('Aggregate reproduction mismatch')
    uncertainty=json.loads((run/'paired_uncertainty.json').read_text())
    for name,report in uncertainty.items():
        rng=random.Random(cfg['bootstrap_seed']);units=report['units'];mapping={u:i for i,u in enumerate(units)}
        samples={n:{m:[] for m in ('AP','AUROC')} for n in CONTRASTS};attempts=0
        with gzip.open(run/(name+'_bootstrap.jsonl.gz'),'rt') as stream:
            for line in stream:
                d=json.loads(line);attempts+=1;counts=Counter(rng.choices(units,k=len(units)))
                if [counts[u] for u in units]!=d['component_multiplicities']:raise ValueError('Bootstrap RNG reproduction mismatch')
                for n in CONTRASTS:
                    for m in ('AP','AUROC'):
                        if d['contrasts'][n][m] is not None:samples[n][m].append(d['contrasts'][n][m])
        if attempts!=10000:raise ValueError('Wrong number of bootstrap attempts')
        for n in CONTRASTS:
            for m,v in samples[n].items():
                interval=report['intervals'][n][m]
                if (quantile(v,.025),quantile(v,.975),len(v))!=(interval['lower_95'],interval['upper_95'],interval['valid']):raise ValueError('Interval reproduction mismatch')
    write_json(run/'reproduction_verification.json',{'status':'PASS','utc':utc(),'aggregate_tables_exactly_equal':True,
        'bootstrap_draws_and_intervals_reproduced_from_saved_logs':True,'model_inference_repeated':False,
        'ranks_recomputed':False,'pre_evaluation_commit':precommit})
    print('Saved-score aggregate and interval reproduction PASS')
