"""Frozen-score evaluation only; native weighted rank kernel + independent sklearn."""
from common import *
import statistics
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
from stability_label_curation.third_party_evaluation import WeightedRanking
from stability_label_curation.replicate_stability_association import quantile

def fractional_precision(y,p,k):
 if len(y)<k:return None
 groups=defaultdict(list)
 for label,score in zip(y,p,strict=True):groups[score].append(label)
 seen=0;hits=0.
 for score in sorted(groups,reverse=True):
  labels=groups[score];take=min(len(labels),k-seen);hits+=sum(labels)*take/len(labels);seen+=take
  if seen==k:return hits/k

def point(y,p):
 if len(set(y))!=2:return {'AP':None,'AUROC':None,'PPV10':fractional_precision(y,p,10),'PPV20':fractional_precision(y,p,20)}
 native_m=runner.development_metrics(list(map(int,y)),list(map(float,p)));a=float(average_precision_score(y,p));u=float(roc_auc_score(y,p));assert math.isclose(a,native_m['AUPRC'],rel_tol=0,abs_tol=1e-10) and math.isclose(u,native_m['AUROC'],rel_tol=0,abs_tol=1e-10)
 return {'AP':a,'AUROC':u,'PPV10':fractional_precision(y,p,10),'PPV20':fractional_precision(y,p,20)}

def frozen_cohort(name):
 spec=context()['cohorts'][name];rr=records(D/'cohorts'/f'{name}_identities.jsonl');yy=records(D/'cohorts'/f'{name}_outcomes.jsonl');assert sha(D/'cohorts'/f'{name}_identities.jsonl')==spec['identity_sha256'] and sha(D/'cohorts'/f'{name}_outcomes.jsonl')==spec['outcome_sha256'];native.assert_alignment([r['source_id'] for r in rr],[r['source_id'] for r in yy]);return rr,[int(r['label']) for r in yy]

def group_bootstrap(rr,y,vectors,cohort,mode):
 """Same authentic integer-multiplicity kernel and Python Random component draws."""
 field='patient_peptide_component' if cohort=='IMPROVE' else 'cluster_id';groups=sorted({r[field] for r in rr});lookup={g:i for i,g in enumerate(groups)};indices=np.array([lookup[r[field]] for r in rr],dtype=np.int64);ranks={}
 for key,p in vectors.items():
  fake=[{'scores':{'fixed':float(score)},'label':int(label),'peptide':r['peptide'],'hla':r['hla'],'study_DOI':r.get('study_DOI') or '', 'patient':r.get('patient') or '', 'source_id':r['source_id']} for r,label,score in zip(rr,y,p,strict=True)];ranks[key]=WeightedRanking(fake,'fixed')
 rng=random.Random(262742);samples=defaultdict(list);reasons=Counter();private=D/'private/bootstrap';private.mkdir(exist_ok=True);log=gzip.open(private/f'{cohort}_{mode}_draw_multiplicities.jsonl.gz','xt')
 try:
  for draw in range(10000):
   counts=np.bincount([rng.randrange(len(groups)) for _ in groups],minlength=len(groups));weights=counts[indices];pm={key:ranking.metrics(weights,top_k=False) for key,ranking in ranks.items()}
   if any(m['AP'] is None for m in pm.values()):reasons['single_class_or_empty']+=1
   for stage in ['EL20','IM30']:
    for contrast,left,right in CONTRASTS:
     for metric in ['AP','AUROC']:
      values=[pm[left,seed,stage][metric]-pm[right,seed,stage][metric] for seed in SEEDS if pm[left,seed,stage][metric] is not None and pm[right,seed,stage][metric] is not None]
      if len(values)==3:samples[stage,contrast,metric].append(statistics.mean(values))
   log.write(json.dumps({'draw':draw+1,'counts':counts.tolist()},separators=(',',':'))+'\n')
   if (draw+1)%1000==0:print('BOOTSTRAP',cohort,mode,draw+1,flush=True)
 finally:log.close()
 ci=[]
 for stage in ['EL20','IM30']:
  for contrast,left,right in CONTRASTS:
   for metric in ['AP','AUROC']:
    a=samples[stage,contrast,metric];ci.append({'cohort':cohort,'population':mode,'stage':stage,'contrast':contrast,'metric':metric,'lower_95':quantile(a,.025),'upper_95':quantile(a,.975),'attempts':10000,'valid_draws':len(a),'invalid_draws':10000-len(a),'component_n':len(groups),'seed':262742,'unit':field,'method':'native integer-multiplicity paired component bootstrap; percentile95; same draws all36 scores; seed-mean differences','quantile':'linear interpolation on sorted values, index=(n-1)*q','interpretation':'conditional fixed-model exploratory; no future seed/patient distribution uncertainty'})
 meta={'cohort':cohort,'population':mode,'components':len(groups),'attempts':10000,'invalid_reasons':dict(reasons),'seed':262742,'draws_shared_all36_conditions':True,'score_transform_recomputed':False,'private_draw_sha256':sha(private/f'{cohort}_{mode}_draw_multiplicities.jsonl.gz')};return ci,meta

def summarize_points(points,population):
 means=[];contrasts=[];meancontr=[]
 for cohort in sorted({r['cohort'] for r in points}):
  for stage in ['EL20','IM30']:
   for arm in ARMS:
    group=[r for r in points if r['cohort']==cohort and r['stage']==stage and r['arm']==arm];assert len(group)==3
    out={'cohort':cohort,'population':population,'stage':stage,'arm':arm,'n':group[0]['n'],'positive':group[0]['positive'],'prevalence':group[0]['positive']/group[0]['n'],'summary_type':'arithmetic mean metrics; NOT score ensemble'}
    for metric in ['AP','AUROC','PPV10','PPV20']:
     vals=[r[metric] for r in sorted(group,key=lambda r:r['seed'])];out.update({metric+'_mean':statistics.mean(vals),metric+'_SD':statistics.stdev(vals),metric+'_min':min(vals),metric+'_max':max(vals),metric+'_seed42':next(r[metric] for r in group if r['seed']==42),metric+'_seed123':next(r[metric] for r in group if r['seed']==123),metric+'_seed456':next(r[metric] for r in group if r['seed']==456)})
    means.append(out)
   for name,left,right in CONTRASTS:
    rows=[]
    for seed in SEEDS:
     a=next(r for r in points if r['cohort']==cohort and r['stage']==stage and r['arm']==left and r['seed']==seed);b=next(r for r in points if r['cohort']==cohort and r['stage']==stage and r['arm']==right and r['seed']==seed);row={'cohort':cohort,'population':population,'stage':stage,'contrast':name,'seed':seed,**{'delta_'+k:a[k]-b[k] for k in ['AP','AUROC','PPV10','PPV20']}};contrasts.append(row);rows.append(row)
    meancontr.append({'cohort':cohort,'population':population,'stage':stage,'contrast':name,**{'mean_delta_'+k:statistics.mean(r['delta_'+k] for r in rows) for k in ['AP','AUROC','PPV10','PPV20']},'aggregation':'mean paired seed-specific metric differences'})
 return means,contrasts,meancontr

def official_evaluate():
 if not (D/'receipts/OFFICIAL_PREDICTIONS_FROZEN.json').exists():return []
 out=[]
 for n in ['IMPROVE','Neo']:
  rr,y=frozen_cohort(n)
  for stage in ['EL','IM']:
   pp=records(D/'private/official_predictions'/f'ensemble_{stage}_{n}.jsonl');native.assert_alignment([r['source_id'] for r in rr],[r['source_id'] for r in pp]);out.append({'cohort':n,'stage':stage,'n':len(rr),'positive':sum(y),'ensemble_members':7,'aggregation':'mean probability then metric',**point(y,[r['positive_probability'] for r in pp]),'score_sha256':sha(D/'private/official_predictions'/f'ensemble_{stage}_{n}.jsonl'),'checkpoint_revision':read(D/'preflight/official_acquisition.json')['commit'],'training_exposure':'see official source exposure audit; not presumed independent'})
 csvout(D/'metrics/OFFICIAL_ENSEMBLE_METRICS.csv',out);return out

def evaluate():
 commands();validate_seal();freeze={};points=[];filtered=[];allci=[];metadata=[];frozen={};byhla=[]
 for arm in ARMS:
  for seed in SEEDS:
   receipt=read(D/'receipts'/f'{arm}_{seed}_predictions_frozen.json');assert len(receipt)==4;freeze[f'{arm}_{seed}']=receipt
 # Seal all72 native score files before external metric computation.
 for key,rec in freeze.items():
  for name,v in rec.items():assert sha(D/'private/predictions'/name)==v['sha256']
 put(D/'receipts/ALL72_PREDICTIONS_FROZEN.json',{'UTC':utc(),'conditions':freeze,'n_files':72,'expected_prediction_rows':289980,'training_complete18':True})
 for cohort in ['IMPROVE','Neo']:
  rr,y=frozen_cohort(cohort);vectors={}
  for arm in ARMS:
   for seed in SEEDS:
    for stage,epoch in [('EL',20),('IM',30)]:
     path=D/'private/predictions'/f'{arm}_{seed}_{stage}{epoch}_{cohort}.jsonl';pp=records(path);native.assert_alignment([r['source_id'] for r in rr],[r['source_id'] for r in pp]);scores=[r['positive_probability'] for r in pp];vectors[arm,seed,f'{stage}{epoch}']=scores
     cp=read(D/'receipts'/f'{arm}_{seed}_{stage}_{epoch:02d}_checkpoint.json');row={'arm':arm,'seed':seed,'stage':f'{stage}{epoch}','cohort':cohort,'n':len(y),'positive':sum(y),'negative':len(y)-sum(y),'prevalence':sum(y)/len(y),**point(y,scores),'score_hash':sha(path),'checkpoint_map_hash':cp['map_SHA256']};points.append(row)
     for hla in sorted({r['hla'] for r in rr}):
      idx=[i for i,r in enumerate(rr) if r['hla']==hla];yy=[y[i] for i in idx];p=[scores[i] for i in idx];byhla.append({'cohort':cohort,'stage':f'{stage}{epoch}','arm':arm,'seed':seed,'hla':hla,'n':len(idx),'positive':sum(yy),**point(yy,p),'status':'DEFINED' if len(set(yy))==2 else 'UNDEFINED_SINGLE_CLASS'})
  ci,meta=group_bootstrap(rr,y,vectors,cohort,'full');allci+=ci;metadata.append(meta)
  if cohort=='IMPROVE':
   c=Counter(r['patient_peptide_component'] for r in rr);largest=sorted(c,key=lambda k:(-c[k],k))[0];assert len(c)==38 and c[largest]==2475;keep=[i for i,r in enumerate(rr) if r['patient_peptide_component']!=largest];assert len(keep)==5313 and sum(y[i] for i in keep)==165
   subrr=[rr[i] for i in keep];suby=[y[i] for i in keep];subvectors={k:[p[i] for i in keep] for k,p in vectors.items()}
   for (arm,seed,stage),p in subvectors.items():filtered.append({'arm':arm,'seed':seed,'stage':stage,'cohort':cohort,'n':len(suby),'positive':sum(suby),'negative':len(suby)-sum(suby),'prevalence':sum(suby)/len(suby),**point(suby,p)})
   ci,meta=group_bootstrap(subrr,suby,subvectors,cohort,'largest_component_excluded');allci+=ci;metadata.append(meta)
 assert len(points)==72;means,contrasts,meancontr=summarize_points(points,'full');assert (len(means),len(contrasts),len(meancontr))==(24,60,20)
 csvout(D/'metrics/MAIN_72_METRICS.csv',points);csvout(D/'metrics/MAIN_ABSOLUTE_METRIC_MEANS.csv',means);csvout(D/'metrics/MAIN_60_SEED_CONTRASTS.csv',contrasts);csvout(D/'metrics/MAIN_20_MEAN_CONTRASTS.csv',meancontr);csvout(D/'metrics/MAIN_CONDITIONAL_CI.csv',[r for r in allci if r['population']=='full']);csvout(D/'metrics/ALL_HLA_DESCRIPTIVE_METRICS.csv',byhla)
 csvout(D/'metrics/LARGEST_COMPONENT_EXCLUDED_METRICS.csv',filtered);fm,fc,fd=summarize_points(filtered,'largest_component_excluded');csvout(D/'metrics/LARGEST_COMPONENT_EXCLUDED_MEANS.csv',fm);csvout(D/'metrics/LARGEST_COMPONENT_EXCLUDED_SEED_CONTRASTS.csv',fc);csvout(D/'metrics/LARGEST_COMPONENT_EXCLUDED_MEAN_CONTRASTS.csv',fd);csvout(D/'metrics/LARGEST_COMPONENT_EXCLUDED_CI.csv',[r for r in allci if r['population']!='full']);put(D/'metrics/BOOTSTRAP_METADATA.json',{'entries':metadata,'metrics_kernel':'native WeightedRanking.metrics AP/AUROC; top-k=False; point independent sklearn checked1e-10','topk_definition':'fractional tie group expected precision; intentionally replaces historical row-order top-k behavior per NEW contract','resampling':'same Python Random262742 sorted authentic component IDs; same draw across all36 within cohort; 10000 attempts, no replacement of invalid draws','seeds_are_not_biological_replicates':True})
 official_evaluate();put(D/'reports/evaluation_completed.json',{'status':'COMPLETE','UTC':utc(),'main_conditions':72,'seed_contrasts':60,'seed_mean_contrasts':20,'main_AP_CIs':20,'main_AUROC_CIs':20,'source_seal_SHA256':sha(D/'preflight/PRETRAINING_PROTOCOL_SEAL.json')});print('MAIN_EVALUATION_COMPLETE',flush=True)
if __name__=='__main__':evaluate()
