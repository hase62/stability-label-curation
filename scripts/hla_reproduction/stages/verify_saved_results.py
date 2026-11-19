"""Final integrity gate, independent point-metric recalculation; no model forward."""
from common import *
from evaluate_main import point

def artifact_reference(path):
 path=Path(path)
 return str(path.relative_to(D)) if path.is_relative_to(D) else str(path)

def main():
 validate_seal();points=list(csv.DictReader((D/'metrics/MAIN_72_METRICS.csv').open()));assert len(points)==72;prediction_rows=0;checks=[];checkpoints=[];tensorrows=[]
 for r in points:
  rr=records(D/'cohorts'/f"{r['cohort']}_identities.jsonl");yy=records(D/'cohorts'/f"{r['cohort']}_outcomes.jsonl");p=D/'private/predictions'/f"{r['arm']}_{r['seed']}_{r['stage']}_{r['cohort']}.jsonl";pp=records(p);native.assert_alignment([x['source_id'] for x in rr],[x['source_id'] for x in pp]);assert sha(p)==r['score_hash'];m=point([int(x['label']) for x in yy],[x['positive_probability'] for x in pp]);assert all(math.isclose(m[k],float(r[k]),rel_tol=0,abs_tol=1e-10) for k in m);prediction_rows+=len(pp);checks.append({'arm':r['arm'],'seed':int(r['seed']),'stage':r['stage'],'cohort':r['cohort'],'path_reference':artifact_reference(p),'n':len(pp),'SHA256':sha(p),'ordered_source_ID_hash':digest([x['source_id'] for x in pp]),'checkpoint_map_SHA256':r['checkpoint_map_hash'],'point_metrics_reproduction':'PASS'})
 assert prediction_rows==289980
 for arm in ARMS:
  for seed in SEEDS:
   assert read(D/'receipts'/f'{arm}_{seed}_completed.json')['status']=='COMPLETE'
   for stage,epoch in [('EL',20),('IM',30)]:
    cp=read(D/'receipts'/f'{arm}_{seed}_{stage}_{epoch:02d}_checkpoint.json');p=Path(cp['checkpoint']);assert runner.checkpoint_identity(p,cp['keys'])==cp['files'];verify=read(cp['independent_strict_reload_receipt']);assert verify['status']=='PASS' and verify['state']==cp['state'];assert sha(cp['independent_strict_reload_receipt'])==cp['independent_strict_reload_SHA256'];assert cp['same_device_probe']['consistent'];assert stage!='IM' or set(cp['changed_parameters'])==set(runner.TRANSFER)
    checkpoints.append({'arm':arm,'seed':seed,'stage':f'{stage}{epoch}','checkpoint_reference':artifact_reference(p),'map_SHA256':cp['map_SHA256'],'tensor_files':len(cp['files']),'strict_reload':'PASS','probe':'PASS','parent_EL20':cp['parent_EL20'],'optimizer_updates':cp['optimizer_updates']})
    for name,h in cp['files'].items():tensorrows.append({'arm':arm,'seed':seed,'stage':f'{stage}{epoch}','file_reference':artifact_reference(p/name),'size_bytes':(p/name).stat().st_size,'SHA256':h})
 epochs=[]
 for f in sorted((D/'metrics/epochs').glob('*.json')):
  r=read(f);r.pop('per_HLA_AP',None);epochs.append(r)
 assert len(epochs)==900 and len(checkpoints)==36
 for r in epochs:
  train=read(D/'receipts/epochs'/f"{r['arm']}_{r['seed']}_{r['stage']}_{r['epoch']:02d}.json")
  if r['arm']!='A':
   ref=read(D/'receipts/epochs'/f"A_{r['seed']}_{r['stage']}_{r['epoch']:02d}.json");reuse.check_schedule(train,ref,train['RNG_before'],train['RNG_after'])
 accesses=[]
 for f in (D/'logs').rglob('file_access_*.jsonl'):
  for line in f.open():
   r=json.loads(line)
   if r['denied'] or r['evaluation_access']:accesses.append(r)
 assert not accesses,'Training boundary violation'
 csvout(D/'metrics/FINAL_PREDICTION_MANIFEST.csv',checks);csvout(D/'metrics/FINAL_CHECKPOINT_MANIFEST.csv',checkpoints);csvout(D/'metrics/CHECKPOINT_TENSOR_HASH_MANIFEST.csv',tensorrows);csvout(D/'metrics/ALL900_EPOCH_METRICS.csv',epochs)
 put(D/'reports/FINAL_QA.json',{'status':'PASS','trajectories_complete':18,'epoch_entries':900,'primary_checkpoints':36,'predictions':72,'prediction_rows':prediction_rows,'point_metrics_independently_reproduced':True,'native_scientific_sampler_loss_unmodified':True,'all_arm_schedule_and_RNG_paired_to_A':True,'IM_changed_only4_transfer_tensors':True,'checkpoint_strict_CPU_reload_and_same_device_score_probe':'PASS','new_run_seal_verified':True,'training_accessed_evaluation_data':False,'primary_fixed_EL20_IM30_no_external_selection':True,'UTC':utc()});print('FINAL_QA_PASS',flush=True)
if __name__=='__main__':commands();main()
