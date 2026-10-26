#!/usr/bin/env python3
"""Capture isolated runtime locks and hardware evidence without cohort access."""
import json
from pathlib import Path
import platform
import subprocess
from stability_label_curation.paths import resolve_paths

def main() -> None:
    paths=resolve_paths();root=paths.project_data_dir/'modern_models_task2_39'
    run=paths.project_runs_dir/'task-2_39-modern-el-stability-z790-preflight'
    repo=Path(__file__).resolve().parents[1]
    probe="""import sys,platform,importlib.metadata as m,json
    versions={}
    for d in m.distributions():
     name=d.metadata['Name'].lower().replace('_','-')
     versions.setdefault(name,d.version)
    print(json.dumps({'python':sys.version,'platform':platform.platform(),'packages':versions,'prefix':sys.prefix},sort_keys=True))
    """
    receipt={'kernel':platform.release(),'platform':platform.platform(),
             'distribution':Path('/etc/os-release').read_text(),
             'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.free','--format=csv,noheader'],text=True).strip(),
             'nvidia_smi':subprocess.check_output(['nvidia-smi'],text=True),
             'hardware_changes':False,'shared_environment_modified':False,'environments':{}}
    for model in ['mixmhcpred','spearmint']:
     python=root/('env_'+model)/'bin/python'
     data=json.loads(subprocess.check_output([str(python),'-c',probe],text=True))
     receipt['environments'][model]=data
     (repo/'configs'/f'task239_{model}.lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in sorted(data['packages'].items()))+'\n')
     if model=='spearmint':
      result=subprocess.check_output([str(python),'-c',"import torch,json; print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),'cuda_available':torch.cuda.is_available(),'torch_path':torch.__file__}))"],text=True)
      receipt['cuda_runtime']=json.loads(result)
    (run/'environment.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(receipt['gpu']);print(receipt['cuda_runtime'])


if __name__ == '__main__':
    main()
