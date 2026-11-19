"""Independent EL20→IM30 wrapper. Delegates native model/sampler/loss/update functions."""
from common import *
from types import SimpleNamespace
from storage import certify,save_resume
import argparse,traceback

def do_fit(arm,seed):
 import torch,numpy as np
 assert arm in ARMS and seed in SEEDS
 log=train_boundary();seal=validate_seal(training=True);cfg=dict(context()['native_training_config'],seed=seed);cfg.update(EL_epochs=20,IM_epochs=30,IM_training_authorized=True)
 runner.cuda_visibility();runner.seed_runtime(torch,np,cfg);device=runner.runtime_device(torch,cfg);enc=reuse.encodings_for(torch,resolved()['reference']);el,val,im=[rows(n) for n in ['EL_train','EL_validation','IM_train']]
 ledger=native.load_rows(D/'controls_private'/f'positive_control_weights_seed{seed}.csv.gz');adapter=None if arm=='A' else SimpleNamespace(mode=arm,weights={r['source_row_id']:float(r[arm+'_FP32']) for r in ledger});prefix=f'{arm}_{seed}'
 put(D/'receipts'/f'{prefix}_started.json',{'status':'RUNNING','UTC':utc(),'arm':arm,'seed':seed,'fresh_EL':True,'seal_SHA256':sha(D/'preflight/PRETRAINING_PROTOCOL_SEAL.json'),'EL_epochs':20,'IM_epochs':30,'external_outcome_access':False})
 start=time.monotonic();parent=None
 with runner.pinned_modules(resolved()) as (BigMHC,Dataset):
  native.reset(torch,np,seed);model=runner.on_device(BigMHC(),device);initial=runner.state_hashes(model);rng_initial=binding.rng_identity(torch,np)
  expected=read(D/'preflight/initializations.json')[str(seed)];assert initial==expected['state'] and rng_initial==expected['RNG']
  put(D/'receipts'/f'{prefix}_initialization.json',{'state':initial,'RNG':rng_initial,'same_paired_seed_as_A':True})
  for stage,maxepoch,rr in [('EL',20,el),('IM',30,im)]:
   if stage=='IM':
    del model,optimizer,dataset
    model=runner.load_checkpoint(torch,BigMHC,Path(parent['checkpoint']),parent['keys'],device=device);assert runner.state_hashes(model)==parent['state'];native.reset(torch,np,seed)
   stage_initial=runner.state_hashes(model);dataset=prior.WeightedDataset(reuse.native_dataset(Dataset,enc,rr),rr,adapter) if stage=='EL' and adapter is not None else baseline.AuditedDataset(reuse.native_dataset(Dataset,enc,rr),[r['prepared_row_index'] for r in rr])
   optimizer=torch.optim.AdamW([p for n,p in model.named_parameters() if stage=='EL' or n in runner.TRANSFER],lr=5e-5,betas=(.9,.999),eps=1e-8,weight_decay=.01)
   optnames=[n for n,p in model.named_parameters() if any(p is q for group in optimizer.param_groups for q in group['params'])]
   assert len(optnames)==(36 if stage=='EL' else 4)
   if stage=='IM':assert tuple(optnames)==runner.TRANSFER
   put(D/'receipts'/f'{prefix}_{stage}_optimizer.json',{'parameter_names':optnames,'requires_grad_names':[n for n,p in model.named_parameters() if p.requires_grad],'defaults':optimizer.defaults,'reset_between_stages':True,'scheduler':None,'initial_state_empty':not bool(optimizer.state),'stage_initial_state':stage_initial})
   cumulative=0;curve=[];torch.cuda.reset_peak_memory_stats()
   for epoch in range(1,maxepoch+1):
    reference=None
    if arm!='A':reference=read(D/'receipts/epochs'/f'A_{seed}_{stage}_{epoch:02d}.json')
    before=binding.rng_identity(torch,np)
    if reference:assert before==reference['RNG_before'],'Paired pre-epoch RNG mismatch'
    t=time.monotonic()
    training=runner.train_epoch(torch,model,dataset,cfg,stage=='IM',device,loss_adapter=adapter if stage=='EL' else None,expected_batches=reference['sampled_batch_sha256'] if reference else None,optimizer=optimizer)
    torch.cuda.synchronize();after=binding.rng_identity(torch,np)
    if reference:reuse.check_schedule(training,reference,before,after)
    cumulative+=training['optimization_steps'];steps=shared.optimizer_steps(optimizer);assert len(steps)==len(optnames) and all(s==cumulative for s in steps)
    training.update(epoch=epoch,stage=stage,arm=arm,seed=seed,RNG_before=before,RNG_after=after,cumulative_optimizer_steps=cumulative,optimizer_state_steps=steps,training_seconds=time.monotonic()-t,paired_reference=None if arm=='A' else f'A_{seed}',actual_device=device,seal_SHA256=sha(D/'preflight/PRETRAINING_PROTOCOL_SEAL.json'))
    training_file=D/'receipts/epochs'/f'{prefix}_{stage}_{epoch:02d}.json';put(training_file,training)
    with shared.preserve_rng(torch,np):prob,bce=shared.evaluate(torch,model,reuse.native_dataset(Dataset,enc,val if stage=='EL' else im),device)
    assert binding.rng_identity(torch,np)==after
    metric={'arm':arm,'seed':seed,'stage':stage,'epoch':epoch,'train_update_BCE':training['row_weighted_BCE_loss'],'validation_BCE':bce if stage=='EL' else None,'IM_full_fit_BCE':bce if stage=='IM' else None,'optimization_steps':training['optimization_steps'],'cumulative_optimizer_steps':cumulative,'all_negative_batches_skipped':training['all_negative_batches_skipped'],'sampled_rows':training['sampled_batch_instances'],'sampled_class_exposures':training['sampled_class_exposures'],'training_seconds':training['training_seconds'],'elapsed_fit_seconds':time.monotonic()-start,'GPU_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'GPU_peak_reserved_bytes':torch.cuda.max_memory_reserved(),'external_IM_metrics_computed':False}
    if stage=='EL':metric.update(baseline.el_metrics(val,prob))
    mf=D/'metrics/epochs'/f'{prefix}_{stage}_{epoch:02d}.json';put(mf,metric);curve.append(metric)
    if epoch==maxepoch or stage=='IM' and epoch==20:
     cp=certify(torch,np,BigMHC,Dataset,model,enc,rr[:16],D/'checkpoints'/f'{prefix}_{stage}_epoch_{epoch:02d}',device);changed=[n for n,h in cp['state'].items() if stage_initial[n]!=h]
     if stage=='IM':assert set(changed)==set(runner.TRANSFER),'IM changed unauthorized tensors'
     cp.update(arm=arm,seed=seed,stage=stage,epoch=epoch,changed_parameters=changed,parent_EL20=parent['checkpoint'] if parent and stage=='IM' else None,optimizer_updates=cumulative,primary_endpoint=epoch==maxepoch)
     put(D/'receipts'/f'{prefix}_{stage}_{epoch:02d}_checkpoint.json',cp)
    generation=save_resume(torch,np,model,optimizer,dataset,prefix,stage,epoch,cumulative,sha(mf),sha(training_file));atomic(D/'reports/current_progress.json',{'status':'RUNNING','arm':arm,'seed':seed,'stage':stage,'completed_epoch':epoch,'resume':generation['path'],'UTC':utc(),'metric':metric})
    print('EPOCH_COMPLETE',prefix,stage,epoch,json.dumps(metric),flush=True)
   parent=cp;put(D/'receipts'/f'{prefix}_{stage}_learning_curve.json',{'epochs':curve})
  del model,optimizer,dataset
 put(D/'receipts'/f'{prefix}_completed.json',{'status':'COMPLETE','arm':arm,'seed':seed,'EL_epochs':20,'IM_epochs':30,'seconds':time.monotonic()-start,'external_IM_used_for_training':False,'UTC':utc()})

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--arm',choices=ARMS,required=True);a.add_argument('--seed',type=int,choices=SEEDS,required=True);x=a.parse_args();commands()
 try:do_fit(x.arm,x.seed)
 except BaseException as e:
  put(D/'receipts'/f'{x.arm}_{x.seed}_FAILED.json',{'status':'FAILED','UTC':utc(),'error':repr(e),'traceback':traceback.format_exc(),'no_auto_retry':True});raise
