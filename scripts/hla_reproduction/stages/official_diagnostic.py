"""Pinned official 7-member EL/IM diagnostic; no optimization or fuzzy mapping."""
from common import *

def main():
 import torch,numpy as np
 validate_seal(training=True);acq=read(D/'preflight/official_acquisition.json');assert acq['status']=='PASS';root=Path(W['official_download_dir']);files={r['path']:r for r in acq['files']};cfg=context()['native_training_config'];runner.seed_runtime(torch,np,cfg);device=runner.runtime_device(torch,cfg)
 for name,r in files.items():assert sha(root/name)==r['sha256']
 local={name:root/('src/'+name.removeprefix('source_')+'.py') for name in ['source_mhcuid','source_encseq','source_dataset','source_bigmhc']};local.update(reference=root/'data/pseudoseqs.csv')
 cohorts={n:records(D/'cohorts'/f'{n}_identities.jsonl') for n in ['IMPROVE','Neo']};needed={r['hla'] for rr in cohorts.values() for r in rr};enc=scoring.encoding_map(torch,local['reference'],needed);mapping=[]
 oldenc=reuse.encodings_for(torch,resolved()['reference'])
 for h in sorted(needed):mapping.append({'canonical_HLA':h,'encoding_length':len(enc[h]),'official_encoding_SHA256':hashlib.sha256(enc[h].numpy().tobytes()).hexdigest(),'historical_encoding_SHA256':hashlib.sha256(oldenc[h].numpy().tobytes()).hexdigest(),'encoding_equal':bool(torch.equal(enc[h],oldenc[h])),'mapping':'EXACT_KEY; fuzzy mapping disabled'})
 csvout(D/'metrics/OFFICIAL_HLA_MAPPING.csv',mapping);outdir=D/'private/official_predictions';outdir.mkdir(exist_ok=True);member={n:{s:[] for s in ['EL','IM']} for n in cohorts};receipts=[]
 with runner.pinned_modules(local) as (BigMHC,Dataset):
  keys=list(BigMHC().state_dict())
  for batch in [512,1024,2048,4096,8192,16384,32768]:
   base=root/f'models/bat{batch}';basefiles=runner.checkpoint_identity(base,keys)
   for stage in ['EL','IM']:
    overlay={}
    if stage=='IM':overlay=runner.overlay_identity(base/'im',keys)
    if stage=='EL':model=runner.load_checkpoint(torch,BigMHC,base,keys,device=device)
    else:model=runner.load_checkpoint(torch,BigMHC,base/'im',keys,device=device,lineage={'state_keys':keys,'EL_files':basefiles,'IM_files':overlay})
    model.eval();before=runner.state_hashes(model)
    for n,rr in cohorts.items():
     data=scoring.native_dataset(Dataset,torch,enc,rr);data.makebats(16,shuffle=False,negfrac=None);out=[]
     with torch.no_grad():
      for i in range(len(data)):
       b=data[i];ids=data.getbat(i,enc=False)['_source_id'].tolist();logits,_=model(b.mhc.float().to(device),b.pep.float().to(device));out += [{'source_id':sid,'positive_probability':p} for sid,p in zip(ids,torch.sigmoid(logits).cpu().tolist(),strict=True)]
     native.assert_alignment([r['source_id'] for r in rr],[r['source_id'] for r in out]);p=outdir/f'bat{batch}_{stage}_{n}.jsonl'
     with p.open('x') as f:
      for row in out:f.write(json.dumps(row,sort_keys=True)+'\n')
     member[n][stage].append([r['positive_probability'] for r in out]);receipts.append({'batch_member':batch,'stage':stage,'cohort':n,'n':len(out),'prediction_sha256':sha(p),'base_checkpoint_map_SHA256':digest(basefiles),'overlay_map_SHA256':digest(overlay) if overlay else None,'source_commit':acq['commit'],'parameters_unchanged':runner.state_hashes(model)==before,'official_2023_byte_identity':'NOT_ESTABLISHED_BY_REPOSITORY_PROVENANCE_ALONE'})
    del model
    print('OFFICIAL_MEMBER_COMPLETE',batch,stage,flush=True)
  for n,rr in cohorts.items():
   for stage in ['EL','IM']:
    # FP32 torch.mean over member probabilities on same CUDA device, as official predict.py.
    stacked=torch.tensor(member[n][stage],dtype=torch.float32,device=device);avg=torch.mean(stacked,dim=0).cpu().tolist();assert len(avg)==len(rr) and all(math.isfinite(x) and 0<=x<=1 for x in avg);p=outdir/f'ensemble_{stage}_{n}.jsonl'
    with p.open('x') as f:
     for r,x in zip(rr,avg,strict=True):f.write(json.dumps({'source_id':r['source_id'],'positive_probability':x},sort_keys=True)+'\n')
    receipts.append({'stage':stage,'cohort':n,'n':len(avg),'prediction_sha256':sha(p),'aggregation':'FP32 torch.mean(member probabilities), NOT mean(member AP)','members':7})
 put(D/'receipts/OFFICIAL_PREDICTIONS_FROZEN.json',{'status':'COMPLETE','entries':receipts,'outcome_access':False,'no_fitting':True,'strict_tensor_only_load':True,'source_commit':acq['commit']})
 print('OFFICIAL_DIAGNOSTIC_INFERENCE_COMPLETE',flush=True)
if __name__=='__main__':commands();main()
