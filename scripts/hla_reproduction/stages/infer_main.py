"""Separate label-blind inference process for frozen EL20/IM30 checkpoints."""
from common import *
import argparse

def infer(arm,seed):
 import numpy as np,torch
 validate_seal(training=True);cfg=dict(context()['native_training_config'],seed=seed);runner.seed_runtime(torch,np,cfg);device=runner.runtime_device(torch,cfg);enc=reuse.encodings_for(torch,resolved()['reference']);outputs={}
 with runner.pinned_modules(resolved()) as (BigMHC,Dataset):
  for stage,epoch in [('EL',20),('IM',30)]:
   cp=read(D/'receipts'/f'{arm}_{seed}_{stage}_{epoch:02d}_checkpoint.json');path=Path(cp['checkpoint']);assert runner.checkpoint_identity(path,cp['keys'])==cp['files'];model=runner.load_checkpoint(torch,BigMHC,path,cp['keys'],device=device);assert runner.state_hashes(model)==cp['state'];model.eval()
   for cohort in ['IMPROVE','Neo']:
    rr=records(D/'cohorts'/f'{cohort}_identities.jsonl');data=scoring.native_dataset(Dataset,torch,enc,rr);data.makebats(16,shuffle=False,negfrac=None);output=[]
    with torch.no_grad():
     for idx in range(len(data)):
      b=data[idx];ids=data.getbat(idx,enc=False)['_source_id'].tolist();logits,_=model(b.mhc.float().to(device),b.pep.float().to(device));probs=torch.sigmoid(logits)
      output += [{'source_id':sid,'native_logit':logit,'positive_probability':prob} for sid,logit,prob in zip(ids,logits.cpu().tolist(),probs.cpu().tolist(),strict=True)]
    native.assert_alignment([r['source_id'] for r in rr],[r['source_id'] for r in output]);assert all(math.isfinite(r['native_logit']) and 0<=r['positive_probability']<=1 for r in output);assert runner.state_hashes(model)==cp['state']
    out=D/'private/predictions'/f'{arm}_{seed}_{stage}{epoch}_{cohort}.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:
     for r in output:f.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n')
    outputs[out.name]={'sha256':sha(out),'n':len(output),'ordered_source_ID_hash':digest([r['source_id'] for r in output]),'checkpoint_map_SHA256':cp['map_SHA256'],'outcomes_accessed':False}
   del model
 put(D/'receipts'/f'{arm}_{seed}_predictions_frozen.json',outputs);print('FOUR_PREDICTIONS_FROZEN',arm,seed,flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--arm',choices=ARMS,required=True);a.add_argument('--seed',type=int,choices=SEEDS,required=True);args=a.parse_args();commands();infer(args.arm,args.seed)
