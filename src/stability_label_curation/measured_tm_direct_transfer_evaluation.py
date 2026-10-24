"""Locked Task2.37 seed-averaged paired evaluation; never fits a model."""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip
import json
import math
from pathlib import Path
import random
from typing import Any

from . import measured_tm_direct_transfer as study
from .paths import StoragePaths
from .third_party_evaluation import WeightedRanking,tie_report
from .replicate_stability_association import quantile,write_rows,write_json,read_rows

PAIRS=(('T-P','P'),('T-A','A'),('T-D','D'))


def summaries(values: dict) -> dict:
    """Mean of seed-paired metric differences, never a score-vector ensemble."""
    metrics=list(values['A']);per_seed={};contrasts={};means={}
    for seed in study.SEEDS:
        per_seed[str(seed)]={a:values['A' if a=='A' else f'{a}_{seed}'] for a in ('A','D','P','T')}
        contrasts[str(seed)]={name:{metric:per_seed[str(seed)]['T'][metric]-per_seed[str(seed)][other][metric]
            if per_seed[str(seed)]['T'][metric] is not None and per_seed[str(seed)][other][metric] is not None else None
            for metric in metrics} for name,other in PAIRS}
    for arm in ('A','D','P','T'):
        means[arm]={m:math.fsum(per_seed[str(s)][arm][m] for s in study.SEEDS)/len(study.SEEDS)
            if all(per_seed[str(s)][arm][m] is not None for s in study.SEEDS) else None for m in metrics}
    averaged={pair:{m:math.fsum(contrasts[str(s)][pair][m] for s in study.SEEDS)/len(study.SEEDS)
        if all(contrasts[str(s)][pair][m] is not None for s in study.SEEDS) else None for m in metrics} for pair,_ in PAIRS}
    return {'per_seed':per_seed,'seed_means':means,'per_seed_contrasts':contrasts,'seed_mean_paired_contrasts':averaged}


def bootstrap(rows: list[dict], rankings: dict, field: str, seed: int, draws: int, evidence: Path | None=None) -> dict:
    import numpy as np
    groups=sorted({r[field] for r in rows});mapping={g:i for i,g in enumerate(groups)}
    if len(groups)<2:return {'components':len(groups),'draws_executed':0,'confidence_intervals':None,'reason':'Fewer than two dependence components'}
    coordinates=np.array([mapping[r[field]] for r in rows],dtype=np.int64)
    rng=random.Random(seed);samples={name:defaultdict(list) for name,_ in PAIRS};metric_names=None
    stream=gzip.open(evidence,'xt') if evidence else None
    try:
        for index in range(draws):
            counts=np.bincount([rng.randrange(len(groups)) for _ in groups],minlength=len(groups));weights=counts[coordinates]
            values={c:r.metrics(weights,top_k=True) for c,r in rankings.items()}
            metric_names=list(values['A']);contrasts=summaries(values)['seed_mean_paired_contrasts']
            for name,metrics in contrasts.items():
                for m,v in metrics.items():
                    if v is not None:samples[name][m].append(v)
            if stream:stream.write(json.dumps({'draw':index+1,'component_multiplicities':counts.tolist(),
                'n':int(weights.sum()),'seed_mean_paired_contrasts':contrasts},allow_nan=False)+'\n')
            if evidence and (index+1)%1000==0:print(evidence.stem,index+1,flush=True)
    finally:
        if stream:stream.close()
    return {'components':len(groups),'component_sizes':dict(Counter(r[field] for r in rows)),
        'positive_bearing_components':len({r[field] for r in rows if r['label']}),'field':field,'seed':seed,
        'draws_executed':draws,'requested_draws':draws,'seeds_are_biological_replicates':False,'unreliable':len(groups)<20,
        'confidence_intervals':{name:{m:{'lower_95':quantile(samples[name].get(m,[]),.025),
            'upper_95':quantile(samples[name].get(m,[]),.975),'usable_draws':len(samples[name].get(m,[])),
            'invalid_draws':draws-len(samples[name].get(m,[])),
            'unreliable':len(groups)<20 or len(samples[name].get(m,[]))<1000} for m in metric_names} for name,_ in PAIRS}}


def point(rows: list[dict],top_k: bool=True) -> dict:
    import numpy as np
    rankings={c:WeightedRanking(rows,c) for c in study.CONDITIONS}
    values={c:r.metrics(np.ones(len(rows),dtype=np.int64),top_k=top_k) for c,r in rankings.items()}
    positives=sum(r['label'] for r in rows)
    return {'population':{'n':len(rows),'positive':positives,'negative':len(rows)-positives,'prevalence':positives/len(rows),
        'unique_peptides':len({r['peptide'] for r in rows}),'HLAs':len({r['hla'] for r in rows}),
        'patient_peptide_components':len({r['patient_peptide_component'] for r in rows}) if 'patient_peptide_component' in rows[0] else None},
        'metrics_by_condition':values,**summaries(values)}


def evaluate(paths: StoragePaths) -> dict:
    d,cfg,_=study.inputs(paths);_,predicted=study.require(paths,'predictions_frozen')
    if predicted['status']!='ALL_TWENTY_PREDICTION_FILES_FROZEN':raise ValueError('All scores must be frozen before outcomes')
    for name,receipt in predicted['predictions'].items():study.assert_sha(d/f'predictions/{name}.jsonl',receipt['sha256'])
    d,start=study.begin(paths,'evaluation');old,manifest=study.previous(paths,cfg);joined={}
    for name in study.data.COHORTS:
        identities=read_rows(d/f'inputs/{name}_identities.jsonl');relative=f'cohorts/{name}_outcomes.jsonl'
        study.assert_sha(old/relative,manifest[relative]);outcomes=read_rows(old/relative)
        records=study.data.align_outcomes(identities,outcomes)
        if sum(r['label'] for r in records)!=study.data.COHORTS[name][1]:raise ValueError('Original cohort outcome balance differs')
        for r in records:r['scores']={};r['peptide_component']=r['peptide']
        for condition in study.CONDITIONS:
            predictions=read_rows(d/f'predictions/{name}_{condition}.jsonl')
            if len(predictions)!=len(identities):raise ValueError('Prediction count differs')
            for identity,row,p in zip(identities,records,predictions,strict=True):
                exclude=('raw_EL_logit','EL_probability') if condition=='A' else ('raw_logit','score')
                if {k:v for k,v in p.items() if k not in exclude}!=identity:raise ValueError('Source-row/peptide/HLA association differs')
                score=p['EL_probability' if condition=='A' else 'score']
                if not math.isfinite(score):raise ValueError('Nonfinite score')
                row['scores'][condition]=score
        joined[name]=records;write_rows(d/f'evaluation/{name}_joined.jsonl',records)
    subsets=json.loads((d/'inputs/evaluation_subsets.json').read_text())
    populations={'IMPROVE_full':joined['IMPROVE'],'neoepitope':joined['neoepitope']}
    for name,ids in subsets.items():
        source=joined['neoepitope' if name.startswith('neoepitope') else 'IMPROVE'];wanted=set(ids)
        populations[name]=[r for r in source if r['source_id'] in wanted]
    if (len(populations['IMPROVE_A02'])!=616 or sum(r['label'] for r in populations['IMPROVE_A02'])!=21
            or len({r['patient_peptide_component'] for r in populations['IMPROVE_A02']})!=16):raise ValueError('Frozen primary differs')
    results={name:point(rows) for name,rows in populations.items()}
    per_hla={}
    for name in ('IMPROVE','neoepitope'):
        per_hla[name]={}
        for hla in sorted({r['hla'] for r in joined[name]}):
            rows=[r for r in joined[name] if r['hla']==hla];positive=sum(r['label'] for r in rows)
            adequate=len(rows)>=20 and positive>=5 and len(rows)-positive>=5
            per_hla[name][hla]={'n':len(rows),'positive':positive,'negative':len(rows)-positive,'adequately_evaluable':adequate,
                'point':point(rows,top_k=False) if adequate else None}
    write_json(d/'evaluation/point_metrics.json',results);write_json(d/'evaluation/per_HLA_metrics.json',per_hla)
    diagnostics={name:{condition:tie_report(rows,condition,top_k=True) for condition in study.CONDITIONS} for name,rows in populations.items()}
    write_json(d/'evaluation/score_ties.json',diagnostics)
    uncertainty={}
    for name in ('IMPROVE_A02','IMPROVE_full','neoepitope'):
        rows=populations[name];rankings={c:WeightedRanking(rows,c) for c in study.CONDITIONS}
        field='peptide_component' if name=='neoepitope' else 'patient_peptide_component'
        uncertainty[name]=bootstrap(rows,rankings,field,cfg['bootstrap_seeds'][name],10000,d/f'evaluation/{name}_paired_draws.jsonl.gz')
        write_json(d/f'evaluation/{name}_paired_uncertainty.json',uncertainty[name])
    write_json(d/'evaluation/study_level_uncertainty.json',{'components':1,'confidence_intervals':None,'draws_executed':0,
        'reason':'Shared peptides connect contributing studies; no independent study-bootstrap interval'})
    result={'status':'COMPLETE','scientific_hashes':study.science(paths),'primary':'IMPROVE_A02 AP mean paired T-P',
        'all_nine_fits_and_scores_fixed_before_metrics':True,'seeds_selected':False,'no_ensemble_score':True,
        'no_IM_labels_used_for_training_or_selection':True,'resources':study.resources(start)}
    write_json(d/'reports/evaluation_complete.json',result)
    return {'status':'COMPLETE','points':{n:{'seed_means':v['seed_means'],'contrasts':v['seed_mean_paired_contrasts']} for n,v in results.items()},'resources':result['resources']}
