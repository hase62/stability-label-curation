"""Frozen Task 2.41-B endpoints; no training or model loading in this module."""
from __future__ import annotations
from collections import Counter, defaultdict
import gzip,json,math,random
from pathlib import Path
from .third_party_evaluation import WeightedRanking

ARMS=('A','H','R1','R2','R3','R4','R5')
RANDOM=ARMS[2:]

def contrasts(arms: dict) -> dict:
    out={}
    for metric in ('AP','AUROC'):
        v={a:arms[a][metric] for a in ARMS}
        mean=sum(v[a] for a in RANDOM)/5 if all(v[a] is not None for a in RANDOM) else None
        pairs=[('H-A',v['H'],v['A']),('H-mean_R',v['H'],mean)]
        pairs += [(f'H-{r}',v['H'],v[r]) for r in RANDOM]+[(f'{r}-A',v[r],v['A']) for r in RANDOM]
        for name,a,b in pairs:out.setdefault(name,{})[metric]=a-b if a is not None and b is not None else None
    return out

def points(rows: list[dict]) -> dict:
    import numpy as np
    arms={a:WeightedRanking(rows,a).metrics(np.ones(len(rows),dtype=np.int64),top_k=True) for a in ARMS}
    p=sum(r['label'] for r in rows)
    return {'n':len(rows),'positive':p,'negative':len(rows)-p,'prevalence':p/len(rows) if rows else None,
            'components':len({r['patient_peptide_component'] for r in rows}),'arms':arms,'contrasts':contrasts(arms),
            'mean_random_AP':sum(arms[a]['AP'] for a in RANDOM)/5 if all(arms[a]['AP'] is not None for a in RANDOM) else None}

def paired_bootstrap(rows: list[dict], *, seed: int, draws: int, evidence: Path | None=None) -> dict:
    """Task 2.32 Random.randrange component sampling, common integer weights."""
    import numpy as np
    groups=sorted({r['patient_peptide_component'] for r in rows})
    if len(groups)<2:raise ValueError('Fewer than two dependence components')
    mapping={g:i for i,g in enumerate(groups)}
    indices=np.array([mapping[r['patient_peptide_component']] for r in rows],dtype=np.int64)
    rankings={a:WeightedRanking(rows,a) for a in ARMS};rng=random.Random(seed)
    samples=defaultdict(list);invalid=Counter();stream=gzip.open(evidence,'xt') if evidence else None
    try:
        for draw in range(draws):
            counts=np.bincount([rng.randrange(len(groups)) for _ in groups],minlength=len(groups));weights=counts[indices]
            arms={a:r.metrics(weights,top_k=False) for a,r in rankings.items()};differences=contrasts(arms)
            if arms['A']['AP'] is None:invalid['single_outcome_class']+=1
            for name,values in differences.items():
                for metric,v in values.items():
                    if v is not None:samples[(name,metric)].append(v)
            if stream:stream.write(json.dumps({'draw':draw+1,'component_multiplicities':counts.tolist(),'n':int(weights.sum()),'contrasts':differences},sort_keys=True,allow_nan=False)+'\n')
            if evidence and (draw+1)%1000==0:print('BOOTSTRAP',draw+1,flush=True)
    finally:
        if stream:stream.close()
    intervals={}
    for name,values in contrasts({a:r.metrics(np.ones(len(rows),dtype=np.int64),top_k=False) for a,r in rankings.items()}).items():
        intervals[name]={}
        for metric in values:
            data=samples[(name,metric)]
            intervals[name][metric]={'lower_95':float(np.quantile(data,.025)) if data else None,'upper_95':float(np.quantile(data,.975)) if data else None,
                                    'valid':len(data),'invalid':draws-len(data)}
    return {'attempts':draws,'seed':seed,'field':'patient_peptide_component','components':len(groups),'component_sizes':dict(Counter(r['patient_peptide_component'] for r in rows)),
            'invalid_reasons':dict(invalid),'intervals':intervals,'ranks_or_scores_recomputed':False,'random_control_mean_is_metric_mean_not_ensemble':True}

def class_diagnostics(labels,probabilities):
    out={}
    for y in (0,1):
        p=[v for label,v in zip(labels,probabilities,strict=True) if label==y]
        out[str(y)]={'n':len(p),'mean_probability':sum(p)/len(p) if p else None,
                     'Brier':sum((v-y)**2 for v in p)/len(p) if p else None,
                     'correct_fraction_at_fixed_0_5':sum((v>=.5)==bool(y) for v in p)/len(p) if p else None}
    return out

def valid_scores(identities,predictions):
    if len(identities)!=len(predictions) or len({r['source_id'] for r in identities})!=len(identities):raise ValueError('Duplicate/missing row identity')
    for row,p in zip(identities,predictions,strict=True):
        if {k:v for k,v in p.items() if k not in ('raw_EL_logit','EL_probability')}!=row:raise ValueError('Row identity/peptide/HLA alignment failed')
        if not math.isfinite(p['raw_EL_logit']) or not math.isfinite(p['EL_probability']) or not 0<=p['EL_probability']<=1:raise ValueError('Nonfinite/invalid score')

def join(identities,predictions,labels):
    if [r['source_id'] for r in identities]!=[r['source_id'] for r in labels]:raise ValueError('Original outcome association mismatch')
    for a in ARMS:valid_scores(identities,predictions[a])
    return [{**r,'label':int(y['label']),'scores':{a:predictions[a][i]['EL_probability'] for a in ARMS}} for i,(r,y) in enumerate(zip(identities,labels,strict=True))]
