"""New-run durable native tensor checkpoints and complete epoch-boundary resume state."""
from common import *

def strict_child(path,expected,output):
 import torch
 torch.set_num_threads(4);torch.set_num_interop_threads(1)
 e=read(expected);files=runner.checkpoint_identity(path,e['keys'])
 with runner.pinned_modules(resolved()) as (BigMHC,Dataset):
  model=runner.load_checkpoint(torch,BigMHC,path,e['keys'],device='cpu');state=runner.state_hashes(model)
 assert state==e['state'] and files==e['files'] and os.getpid()!=e['requesting_pid']
 put(output,{'status':'PASS','state':state,'files':files,'checkpoint':str(path),'PID':os.getpid(),'requested_by':e['requesting_pid'],'weights_only':True,'strict':True,'GPU':False})

def certify(torch,np,BigMHC,Dataset,model,enc,probe,path,device):
 assert path.is_relative_to(D/'checkpoints') or path.is_relative_to(D/'preflight/save_test')
 path.parent.mkdir(parents=True,exist_ok=True);before=binding.rng_identity(torch,np);state=runner.state_hashes(model);keys=list(model.state_dict());runner.reserve_checkpoint(path);runner.save_checkpoint(model,path,transfer=False,device=device);files=runner.checkpoint_identity(path,keys)
 for f in path.glob('*.lyr'):
  with f.open('rb') as s:os.fsync(s.fileno())
 expected=D/'receipts/checkpoints'/f'{path.name}_expected.json';out=D/'receipts/checkpoints'/f'{path.name}_strict_CPU_reload.json'
 put(expected,{'state':state,'keys':keys,'files':files,'requesting_pid':os.getpid(),'checkpoint':str(path)})
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
 with (D/'logs'/f'{path.name}_strict_reload.log').open('x') as log:subprocess.run([sys.executable,str(D/'scripts/storage.py'),'verify',str(path),str(expected),str(out)],env=env,cwd=D,stdout=log,stderr=subprocess.STDOUT,check=True)
 result=read(out);assert result['status']=='PASS'
 agreement=None
 if probe:
  with shared.preserve_rng(torch,np):
   beforep=runner.predict(torch,model,reuse.native_dataset(Dataset,enc,probe),16,device);duplicate=runner.load_checkpoint(torch,BigMHC,path,keys,device=device);afterp=runner.predict(torch,duplicate,reuse.native_dataset(Dataset,enc,probe),16,device);agreement=runner.prediction_agreement(beforep,afterp,device);assert runner.state_hashes(duplicate)==state;del duplicate
 assert binding.rng_identity(torch,np)==before and runner.checkpoint_identity(path,keys)==files
 receipt={'status':'VERIFIED','state':state,'keys':keys,'files':files,'map_SHA256':digest(files),'checkpoint':str(path),'independent_strict_reload_receipt':str(out),'independent_strict_reload_SHA256':sha(out),'same_device_probe':agreement,'RNG_preserved':True}
 put(path/'VERIFIED_CHECKPOINT.json',receipt);return receipt

def cpu_tree(v):
 import torch
 if torch.is_tensor(v):return v.detach().cpu().clone()
 if isinstance(v,dict):return {k:cpu_tree(x) for k,x in v.items()}
 if isinstance(v,list):return [cpu_tree(x) for x in v]
 if isinstance(v,tuple):return tuple(cpu_tree(x) for x in v)
 return v

def save_resume(torch,np,model,optimizer,dataset,prefix,stage,epoch,cumulative,metric_sha,train_sha):
 folder=D/'resume'/prefix;folder.mkdir(exist_ok=True);slot=epoch%2;path=folder/f'{stage}_slot{slot}.pt';temp=path.with_suffix('.pending');rng_np=np.random.get_state();order=dataset.native.df['_prepared_index'].tolist()
 payload={'format':1,'prefix':prefix,'stage':stage,'completed_epoch':epoch,'cumulative_steps':cumulative,'model':cpu_tree(model.state_dict()),'gradients':{k:None if p.grad is None else cpu_tree(p.grad) for k,p in model.named_parameters()},'optimizer':cpu_tree(optimizer.state_dict()),'prepared_index_order':torch.tensor(order,dtype=torch.int64),'Python_RNG':random.getstate(),'NumPy_RNG':[rng_np[0],rng_np[1].tolist(),rng_np[2],rng_np[3],rng_np[4]],'torch_CPU_RNG':torch.get_rng_state(),'torch_CUDA_RNG':torch.cuda.get_rng_state_all(),'metric_SHA256':metric_sha,'epoch_training_SHA256':train_sha,'source_seal_SHA256':sha(D/'preflight/PRETRAINING_PROTOCOL_SEAL.json')}
 assert not temp.exists()
 with temp.open('xb') as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
 h=sha(temp);os.replace(temp,path)
 generation={'status':'COMPLETE_EPOCH_RESUME','prefix':prefix,'stage':stage,'completed_epoch':epoch,'path':str(path),'sha256':h,'optimizer_steps':cumulative,'dataset_order_hash':digest(order),'model_state_hashes':runner.state_hashes(model),'RNG_identity':binding.rng_identity(torch,np),'source_seal_SHA256':payload['source_seal_SHA256'],'slot_retention':'two rotating epoch-boundary slots per stage; older slot bytes atomically replaced inside this NEW run only','metric_SHA256':metric_sha,'epoch_training_SHA256':train_sha}
 put(D/'receipts/resume_generations'/f'{prefix}_{stage}_{epoch:02d}.json',generation);atomic(folder/f'{stage}_latest.json',generation)
 return generation

if __name__=='__main__':
 if sys.argv[1]=='verify':strict_child(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]))
