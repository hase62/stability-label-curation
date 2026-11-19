"""Authentic model storage and actual native dataset/loss integration, zero updates."""
from common import *
from storage import certify
from types import SimpleNamespace
import importlib.metadata,platform

def main():
 import numpy as np,torch
 commands();cfg=dict(context()['native_training_config']);runner.seed_runtime(torch,np,cfg);device=runner.runtime_device(torch,cfg);enc=reuse.encodings_for(torch,resolved()['reference']);el=rows('EL_train');im=rows('IM_train');val=rows('EL_validation');mapping=[]
 # Saving paths must exist, but checkpoint reservation path itself must not preexist.
 (D/'preflight/save_test').mkdir(parents=True,exist_ok=True)
 with runner.pinned_modules(resolved()) as (BigMHC,Dataset):
  assert tuple(BigMHC.tllayers())==runner.TRANSFER
  native.reset(torch,np,42);model=BigMHC();initial=runner.state_hashes(model);keys=list(initial);assert len(keys)==36
  for stage in ['EL','IM']:
   cert=certify(torch,np,BigMHC,Dataset,model,enc,None,D/'preflight/save_test'/f'ACTUAL_MODEL_{stage}_path_test','cpu');assert cert['state']==initial
  partial=D/'preflight/save_test/INCOMPLETE';partial.mkdir()
  try:runner.checkpoint_identity(partial,keys)
  except ValueError:pass
  else:raise AssertionError('Incomplete checkpoint was accepted')
  del model
  initializations={}
  for seed in SEEDS:
   native.reset(torch,np,seed);model=runner.on_device(BigMHC(),device);initializations[str(seed)]={'state':runner.state_hashes(model),'RNG':binding.rng_identity(torch,np)};del model
  put(D/'preflight/initializations.json',initializations)
  # Real input integration, same source sampling+labels+negative weights; no model updates.
  control=native.load_rows(D/'controls_private/positive_control_weights_seed42.csv.gz');ref=None;test_rows=[]
  for arm in ARMS:
   native.reset(torch,np,42);adapter=SimpleNamespace(mode=arm,weights={r['source_row_id']:float(r[arm+'_FP32']) for r in control})
   dataset=prior.WeightedDataset(reuse.native_dataset(Dataset,enc,el),el,adapter);dataset.makebats(16,shuffle=True,negfrac=.99);arr=[]
   for idx in [0,1,2]:
    b=dataset[idx];arr.append({'batch_sha256':b.source_batch_sha256,'labels':b.tgt.tolist(),'mhc_sha256':hashlib.sha256(b.mhc.numpy().tobytes()).hexdigest(),'pep_sha256':hashlib.sha256(b.pep.numpy().tobytes()).hexdigest()});assert len(b.tgt)==17 and int(b.tgt.sum())==1
    loss=binding.weighted_bce(torch,torch.zeros(len(b.tgt)),b.tgt.float(),b.EL_loss_weights);independent=torch.tensor(math.log(2)*math.fsum(b.EL_loss_weights)/len(b.tgt));assert torch.allclose(loss,independent,rtol=1e-6,atol=1e-7)
    assert all(w==1 for w,y in zip(b.EL_loss_weights,b.tgt.tolist()) if y==0)
   if ref is None:ref=arr
   assert arr==ref;test_rows.append({'arm':arm,'same3_native_real_batches':True,'actual_batch_rows':17,'positive_per_batch':1,'mean_weighted_BCE_correct':True,'negative_weight':1,'optimizer_updates':0});del dataset,adapter
  csvout(D/'preflight/NATIVE_CONTROL_INTEGRATION.csv',test_rows)
 put(D/'preflight/model_storage_and_integration_gate.json',{'status':'PASS','actual_BigMHC_EL_and_IM_save_independent_strict_CPU_reload':'PASS','partial_checkpoint_rejected':True,'real_EL_batches_all6_arms_aligned':True,'native_weighted_loss_mean_batch_rows':'PASS','optimizer_updates':0,'initializations_saved':True,'native_TRANSFER':runner.TRANSFER,'runtime':{'python':sys.version,'torch':torch.__version__,'numpy':np.__version__,'pandas':importlib.metadata.version('pandas'),'platform':platform.platform(),'device':runner.device_report(torch,device),'deterministic':torch.are_deterministic_algorithms_enabled(),'TF32_matmul':torch.backends.cuda.matmul.allow_tf32,'TF32_cudnn':torch.backends.cudnn.allow_tf32}})
 print('ACTUAL_MODEL_STORAGE_AND_NATIVE_INTEGRATION_PASS',flush=True)
if __name__=='__main__':main()
