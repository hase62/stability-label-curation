"""Recovery IO/certification/orchestration only; original science stays byte-exact.

Explicitly binds only paths_config, require and save_complete in the original
module. No scientific training, sampling, loss or prediction function is edited.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback
from typing import Any

from . import hla_extended_epochs as science
from .paths import resolve_paths

CONFIG = 'configs/hla_epoch_recovery.json'
MARKER = 'VERIFIED_CHECKPOINT.json'
_OWNED_PROCESSES: list[Any] = []


def utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return science.sha(path)


def put(path: Path, value: Any) -> None:
    """Exclusive, durable write; original files are never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def context():
    p = resolve_paths(); c = read(p.repository_root/CONFIG)
    if any(Path(c[k]).name != c[k] for k in ('recovery_run_id','source_run_id')):
        raise ValueError('Run IDs must be single path components')
    d = p.project_runs_dir/c['recovery_run_id']; old = p.project_runs_dir/c['source_run_id']
    if d == old or d.is_relative_to(old) or old.is_relative_to(d):
        raise ValueError('Recovery storage is not isolated')
    return p, c, d, old


def source_proof():
    p, c, d, old = context()
    path = old/'reports/preflight.json'
    if sha(path) != c['source_preflight_sha256']:
        raise ValueError('Original frozen preflight identity differs')
    return read(path)


def recovery_hashes() -> dict:
    p, c, _, _ = context()
    return {name: sha(p.repository_root/name) for name in c['implementation_files']}


def git(*args: str) -> str:
    p, _, _, _ = context()
    return science.git(p.repository_root, *args)


def check_code(*, clean: bool = True) -> None:
    p, c, d, old = context(); original = source_proof()
    if science.hashes(p, original['config']) != original['scientific_hashes']:
        raise ValueError('Original scientific files changed')
    if git('branch','--show-current') != c['branch'] or (clean and git('status','--porcelain')):
        raise ValueError('Clean committed recovery branch required')
    preparation = d/'reports/recovery_preparation.json'
    if preparation.exists() and read(preparation)['recovery_hashes'] != recovery_hashes():
        raise ValueError('Recovery implementation changed after preparation')


def scientific_paths_config():
    p, _, d, _ = context()
    return p, source_proof()['config'], d


def require():
    check_code()
    p, c, d, _ = context(); proof = read(d/'reports/preflight.json')
    if proof['status'] != 'PASS' or proof['recovery_hashes'] != recovery_hashes():
        raise ValueError('Recovery preflight gate failed')
    gate = read(d/'reports/phase1_save_gate.json')
    if gate['status'] != 'PASS' or sha(d/'reports/phase1_save_gate.json') != proof['phase1_gate_sha256']:
        raise ValueError('Actual-model save/reload gate is not authenticated')
    if read(d/'reports/focused_tests.json')['status'] != 'PASS':
        raise ValueError('Focused tests not passed')
    for name, expected in proof['frozen_inputs'].items():
        if sha(d/name) != expected:raise ValueError('Frozen recovery input changed: '+name)
    return p, proof['config'], d, proof


def install_bindings() -> None:
    """Only the IO/verification boundary is replaced, with explicit receipt."""
    science.paths_config = scientific_paths_config
    science.require = require
    science.save_complete = save_complete


def tree_inventory(root: Path) -> dict:
    return {str(f.relative_to(root)): {'size_bytes': f.stat().st_size, 'sha256': sha(f)}
            for f in sorted(root.rglob('*')) if f.is_file()}


def verify_old_run() -> None:
    _, _, d, old = context()
    if tree_inventory(old) != read(d/'reports/original_failed_run_inventory.json'):
        raise ValueError('Original failed run changed')


def ensure_parent(parent: Path) -> None:
    _, _, d, _ = context()
    if parent not in {d/'checkpoints', d/'preflight_save_e2e/checkpoints'}:
        raise ValueError('Save parent outside the isolated allowed storage')
    with science.runner.raw._directory(parent, create=True):pass


def checkpoint_valid(path: Path) -> dict:
    """File count alone never certifies a checkpoint."""
    marker_path = path/MARKER
    if not marker_path.is_file():raise ValueError('Unverified or partial checkpoint: marker absent')
    marker = read(marker_path)
    if marker['checkpoint'] != str(path) or marker['status'] != 'VERIFIED':
        raise ValueError('Checkpoint marker identity differs')
    actual = science.runner.checkpoint_identity(path, marker['state_keys'])
    if len(actual) != 36 or actual != marker['files']:
        raise ValueError('Checkpoint file integrity differs')
    expected_path = Path(marker['expected_state_receipt'])
    reload_path = Path(marker['strict_reload_receipt'])
    if sha(expected_path) != marker['expected_state_receipt_sha256'] or sha(reload_path) != marker['strict_reload_receipt_sha256']:
        raise ValueError('Checkpoint certification receipt changed')
    expected, loaded = read(expected_path), read(reload_path)
    if (loaded['status'] != 'PASS' or loaded['pid'] == loaded['requesting_pid']
            or loaded['state'] != expected['state'] or marker['state'] != expected['state']
            or loaded['files'] != actual or loaded['checkpoint'] != str(path)):
        raise ValueError('Independent strict reload certification failed')
    return marker


def strict_reload_child(directory: Path, expected_path: Path, output: Path) -> dict:
    """Fresh CPU process, authentic constructor and weights_only strict loader."""
    check_code()
    import numpy as np
    import torch
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('Reload verifier must be CPU-only')
    torch.set_num_threads(4); torch.set_num_interop_threads(1)
    expected = read(expected_path); original = source_proof()
    resolved = {k: Path(v['path']) for k,v in original['authenticated_inputs'].items()}
    files = science.runner.checkpoint_identity(directory, expected['state_keys'])
    with science.runner.pinned_modules(resolved) as (BigMHC, Dataset):
        model = science.runner.load_checkpoint(torch, BigMHC, directory, expected['state_keys'], device='cpu')
        state = science.runner.state_hashes(model)
        if state != expected['state'] or len(state) != 36:
            raise ValueError('All-parameter state hash differs after strict reload')
        del model
    result = {'status':'PASS','checkpoint':str(directory),'expected_state_receipt_sha256':sha(expected_path),
        'state':state,'files':files,'state_keys':expected['state_keys'],'pid':os.getpid(),
        'requesting_pid':expected['requesting_pid'],'device':'cpu','weights_only':True,
        'model_updates':0,'predictions_generated':False,'torch_version':torch.__version__,'UTC':utc()}
    put(output,result);return result


def invoke_reload(path: Path, expected: Path, output: Path) -> dict:
    p, _, _, _ = context(); env = os.environ.copy()
    env['CUDA_VISIBLE_DEVICES']='';env['PYTHONPATH']=str(p.repository_root/'src')
    log = output.with_suffix('.log')
    with log.open('x') as stream:
        subprocess.run([sys.executable,'-m','stability_label_curation.hla_epoch_recovery','verify-load',
            '--checkpoint',str(path),'--expected',str(expected),'--output',str(output)],
            cwd=p.repository_root,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True)
    result = read(output)
    if result['status'] != 'PASS' or result['pid'] == os.getpid():
        raise ValueError('Separate-process reload did not pass')
    return result


def save_complete(torch, BigMHC, Dataset, model, encodings, rows, path: Path, device: str) -> dict:
    """Storage-only replacement: parent creation, durable hashes, independent load.

    The original same-device 16-training-row equality probe is retained for fits.
    Phase1 passes rows=None, so it performs no model forward or training update.
    """
    import numpy as np
    _, _, d, _ = context()
    if path.parent not in {d/'checkpoints', d/'preflight_save_e2e/checkpoints'}:
        raise ValueError('Refuse checkpoint outside recovery run')
    ensure_parent(path.parent)
    before_rng = science.binding.rng_identity(torch,np)
    state, keys = science.runner.state_hashes(model), list(model.state_dict())
    expected = d/'reports/checkpoint_certification'/f'{path.name}_expected_state.json'
    output = d/'reports/checkpoint_certification'/f'{path.name}_strict_reload.json'
    put(expected,{'checkpoint':str(path),'state':state,'state_keys':keys,'requesting_pid':os.getpid(),
        'UTC':utc(),'recovery_hashes':recovery_hashes()})
    science.runner.reserve_checkpoint(path)
    science.runner.save_checkpoint(model,path,transfer=False,device=device)
    for filename in path.glob('*.lyr'):
        with filename.open('rb') as stream:os.fsync(stream.fileno())
    loaded = invoke_reload(path,expected,output)
    if loaded['state'] != state:raise ValueError('Independent reload differs from pre-save state')
    probe_equal = None
    if rows is not None:
        with science.shared.preserve_rng(torch,np):
            probe = science.reuse.native_dataset(Dataset,encodings,rows[:16])
            before = science.runner.predict(torch,model,probe,16,device)
            duplicate = science.runner.load_checkpoint(torch,BigMHC,path,keys,device=device)
            after = science.runner.predict(torch,duplicate,probe,16,device)
            if before != after or science.runner.state_hashes(duplicate) != state:
                raise ValueError('Original same-device probe/reload differs')
            del duplicate
        probe_equal = True
    files = science.runner.checkpoint_identity(path,keys)
    if files != loaded['files'] or science.binding.rng_identity(torch,np) != before_rng:
        raise ValueError('Saving changed files or scientific RNG')
    marker = {'status':'VERIFIED','checkpoint':str(path),'state':state,'state_keys':keys,'files':files,
        'expected_state_receipt':str(expected),'expected_state_receipt_sha256':sha(expected),
        'strict_reload_receipt':str(output),'strict_reload_receipt_sha256':sha(output),
        'same_device_training_probe_equal':probe_equal,'phase1_no_forward':rows is None,'UTC':utc()}
    put(path/MARKER,marker)
    with science.runner.raw._directory(path) as descriptor:os.fsync(descriptor)
    checkpoint_valid(path)
    return {'checkpoint':str(path),'state':state,'state_keys':keys,'files':files,
        'strict_reload':True,'strict_reload_subprocess':True,'probe_prediction_equal':probe_equal,
        'verified_marker_sha256':sha(path/MARKER),'strict_reload_receipt':str(output)}


def prepare() -> dict:
    """Authenticate/copy exact frozen inputs, then gate real-model CPU save/load."""
    check_code()
    p,c,d,old = context(); original = source_proof()
    if d.exists():raise ValueError('Recovery run exists; no overwrite/retry')
    tests_root=p.project_runs_dir/c['focused_test_run_id']
    tests=read(tests_root/'focused_tests.json')
    if (tests['status']!='PASS' or tests['failures'] or tests['errors'] or tests['skipped']
            or tests['recovery_hashes']!=recovery_hashes() or tests['log_sha256']!=sha(tests_root/'focused_tests.log')):
        raise ValueError('Current focused tests not authenticated')
    d.mkdir(mode=0o700)
    for name in ['reports','logs','inputs','cohorts','checkpoints','preflight_save_e2e/checkpoints']:
        with science.runner.raw._directory(d/name,create=True):pass
    shutil.copyfile(tests_root/'focused_tests.json',d/'reports/focused_tests.json')
    shutil.copyfile(tests_root/'focused_tests.log',d/'logs/focused_tests.log')
    if read(old/'reports/execution_completed.json')['status'] != 'FAILED':
        raise ValueError('Source is not the diagnosed failed run')
    put(d/'reports/original_failed_run_inventory.json',tree_inventory(old))
    put(d/'reports/recovery_preparation.json',{'UTC':utc(),'commit':git('rev-parse','HEAD'),
        'source_preflight_sha256':c['source_preflight_sha256'],'recovery_hashes':recovery_hashes(),
        'binding_replacements':['paths_config','require','save_complete'],
        'training_prediction_and_weight_functions_edited':False})
    for relative, expected in original['frozen_inputs'].items():
        if sha(old/relative) != expected:raise ValueError('Original frozen input changed')
        destination=d/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(old/relative,destination)
        if sha(destination) != expected:raise ValueError('Recovery input copy differs')
    for item in original['authenticated_inputs'].values():
        if sha(Path(item['path'])) != item['sha256']:raise ValueError('Original authenticated data/source changed')
    for name in ['initializations','initial_state_evidence','weights','cohort','scope_clarification','A_42_EL_checkpoint','A_42_IM_checkpoint']:
        shutil.copyfile(old/f'reports/{name}.json',d/f'reports/{name}.json')
    put(d/'reports/source_preflight_reference.json',{'path':str(old/'reports/preflight.json'),'sha256':c['source_preflight_sha256']})
    label_manifest=p.project_runs_dir/c['label_manifest']['path']
    if sha(label_manifest) != c['label_manifest']['sha256']:raise ValueError('Original outcome provenance receipt differs')
    # Authenticate byte identities only. No outcomes are parsed before score freeze.
    for spec in c['label_sources'].values():
        if sha(p.project_runs_dir/spec['path']) != spec['sha256']:raise ValueError('Frozen outcome bytes changed')
    phase1 = phase1_tests()
    if phase1['status'] != 'PASS':raise ValueError('CPU actual-model save gate failed')
    proof=dict(original)
    proof.update(status='PASS',storage_run_id=c['recovery_run_id'],recovery_hashes=recovery_hashes(),
        phase1_gate_sha256=sha(d/'reports/phase1_save_gate.json'),source_failed_run=str(old),
        source_failed_run_inventory_sha256=sha(d/'reports/original_failed_run_inventory.json'),
        source_preflight_sha256=c['source_preflight_sha256'],recovery_commit=git('rev-parse','HEAD'),
        evaluation_outcomes_parsed=False,scientific_functions_byte_identical=True)
    put(d/'reports/preflight.json',proof)
    verify_old_run()
    return {'status':'PASS','storage_run_id':c['recovery_run_id'],'phase1':phase1}


def phase1_tests() -> dict:
    """No optimizer, no trained model and no GPU computation."""
    import numpy as np
    import torch
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise ValueError('Phase1 must hide all GPUs')
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    p,c,d,old = context(); original=source_proof()
    resolved={k:Path(v['path']) for k,v in original['authenticated_inputs'].items()}
    from . import hla_recovery_export as export
    sentinel=export.cpu_sentinel_tests(d/'preflight_save_e2e/sentinel')
    comparisons={}
    with science.runner.pinned_modules(resolved) as (BigMHC,Dataset):
        science.reset(torch,np,42)
        model=BigMHC();state=science.runner.state_hashes(model)
        if state != read(d/'reports/initializations.json')['42']['state']:
            raise ValueError('Authentic epoch-zero initialization differs')
        el=save_complete(torch,BigMHC,Dataset,model,None,None,
            d/'preflight_save_e2e/checkpoints/EL_NO_UPDATES','cpu')
        del model
        model=science.runner.load_checkpoint(torch,BigMHC,el['checkpoint'],el['state_keys'],device='cpu')
        if science.runner.state_hashes(model) != state:raise ValueError('EL parent transfer-format load differs')
        im=save_complete(torch,BigMHC,Dataset,model,None,None,
            d/'preflight_save_e2e/checkpoints/IM_NO_UPDATES','cpu')
        del model
        for stage,receipt in [('EL',el),('IM',im)]:
            comparisons[stage]={'full_tensor_files':len(receipt['files']),'state_equal':receipt['state']==state,
                'separate_process_strict_reload':receipt['strict_reload_subprocess'],
                'file_map_sha256':science.scoring.digest(receipt['files']),'checkpoint':receipt['checkpoint']}
    rejected=export.incomplete_checkpoint_tests(d/'preflight_save_e2e',Path(el['checkpoint']))
    reused={}
    for stage in ['EL','IM']:
        metadata=read(d/f'reports/A_42_{stage}_checkpoint.json');directory=Path(metadata['checkpoint'])
        files=science.runner.checkpoint_identity(directory,metadata['state_keys'])
        if files!=metadata['files'] or science.scoring.digest(files)!=original['config']['A_checkpoint_map_sha256'][stage]:
            raise ValueError('Authenticated A42 checkpoint differs')
        expected=d/f'reports/checkpoint_certification/A42_REUSED_{stage}_expected.json'
        output=d/f'reports/checkpoint_certification/A42_REUSED_{stage}_strict_reload.json'
        put(expected,{'checkpoint':str(directory),'state':metadata['state'],'state_keys':metadata['state_keys'],'requesting_pid':os.getpid()})
        result=invoke_reload(directory,expected,output)
        if result['state']!=metadata['state']:raise ValueError('Reused A42 state differs')
        reused[stage]={'strict_reload':'PASS','receipt':str(output),'sha256':sha(output),'checkpoint_map_sha256':science.scoring.digest(files)}
    result={'status':'PASS','UTC':utc(),'actual_authentic_BigMHC':True,'CPU_only':True,
        'training_updates':0,'model_forward_passes':0,'EL_and_IM_save_paths':comparisons,
        'sentinel_tests':sentinel,'incomplete_checkpoint_rejection':rejected,'A42_reuse_reload':reused}
    put(d/'reports/phase1_save_gate.json',result);return result


def runtime_gate() -> dict:
    import importlib.metadata
    import torch
    _,_,d,proof=require()
    science.runner.cuda_visibility()
    current={'versions':{n:importlib.metadata.version(n) for n in proof['runtime']['versions']},
        'device':science.runner.device_report(torch,'cuda:0')}
    if any(current[k]!=proof['runtime'][k] for k in ['versions','device']):
        raise ValueError('Historical GPU/runtime compatibility failed')
    put(d/'reports/runtime_readiness.json',{'status':'PASS',**current,'model_updates':0,'UTC':utc()})
    return current


def validate_model_for_scoring(arm: str, seed: int) -> None:
    _,_,d,proof=require()
    for stage in ['EL','IM']:
        receipt=read(d/f'reports/{arm}_{seed}_{stage}_checkpoint.json')
        directory=Path(receipt['checkpoint'])
        if arm=='A' and seed==42:
            files=science.runner.checkpoint_identity(directory,receipt['state_keys'])
            if files!=receipt['files'] or science.scoring.digest(files)!=proof['config']['A_checkpoint_map_sha256'][stage]:
                raise ValueError('Reused baseline changed before inference')
        else:
            marker=checkpoint_valid(directory)
            if marker['state']!=receipt['state'] or marker['files']!=receipt['files']:
                raise ValueError('Fit receipt differs from verified checkpoint')


def predict_subprocess(arm: str, seed: int) -> None:
    p,_,d,_=context()
    with (d/f'logs/{arm}_{seed}_prediction.log').open('x') as stream:
        subprocess.run([sys.executable,'-m','stability_label_curation.hla_epoch_recovery','predict',
            '--arm',arm,'--seed',str(seed)],cwd=p.repository_root,stdout=stream,stderr=subprocess.STDOUT,check=True)


def worker(arm: str, seed: int) -> None:
    install_bindings();_,_,d,_=context()
    try:
        science.train(arm,seed)
        predict_subprocess(arm,seed)
    except BaseException as error:
        put(d/f'reports/{arm}_{seed}_execution_FAILED.json',{'arm':arm,'seed':seed,'error':repr(error),'UTC':utc(),
            'EL_epochs_completed':len(list((d/'reports').glob(f'{arm}_{seed}_EL_epoch_*.json'))),
            'IM_epochs_completed':len(list((d/'reports').glob(f'{arm}_{seed}_IM_epoch_*.json'))),
            'traceback':traceback.format_exc(),'automatic_retry':False})
        raise


def supervise() -> dict:
    install_bindings();p,c,d,_=context();_,protocol,_,proof=require()
    runtime_gate()
    jobs=[(a,int(s)) for a,s in protocol['jobs']]
    if len(jobs)!=8 or len(set(jobs))!=8 or ('A',42) in jobs:raise ValueError('Eight-fit plan differs')
    put(d/'reports/execution_started.json',{'UTC':utc(),'commit':git('rev-parse','HEAD'),
        'planned_jobs':jobs,'attempts_per_fit':1,'no_automatic_retry':True,'maximum_concurrency':c['maximum_concurrency'],
        'scientific_hashes':proof['scientific_hashes'],'recovery_hashes':proof['recovery_hashes']})
    pending=list(jobs);active=[];complete=[];failure=None;aborted=[]
    while pending or active:
        while pending and len(active)<c['maximum_concurrency'] and failure is None:
            arm,seed=pending.pop(0);log=(d/f'logs/{arm}_{seed}_worker.log').open('x')
            proc=subprocess.Popen([sys.executable,'-m','stability_label_curation.hla_epoch_recovery','worker',
                '--arm',arm,'--seed',str(seed)],cwd=p.repository_root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            _OWNED_PROCESSES.append(proc)
            active.append((proc,log,arm,seed))
        for item in list(active):
            proc,log,arm,seed=item;code=proc.poll()
            if code is None:continue
            log.close();active.remove(item)
            if code!=0:
                failure={'arm':arm,'seed':seed,'exit_code':code,'UTC':utc()}
                break
            if not (d/f'reports/{arm}_{seed}_completed.json').is_file() or not (d/f'reports/{arm}_{seed}_prediction_receipt.json').is_file():
                failure={'arm':arm,'seed':seed,'cause':'Missing completion/prediction receipt','UTC':utc()};break
            complete.append({'arm':arm,'seed':seed,'status':'COMPLETE'})
        if failure is not None:
            for proc,log,arm,seed in active:
                if proc.poll() is None:
                    if os.getpgid(proc.pid)!=proc.pid:raise RuntimeError('Owned process-group safety check failed')
                    os.killpg(proc.pid,signal.SIGTERM)
                aborted.append({'arm':arm,'seed':seed,'reason':'STOPPED_DUE_TO_PEER_FAILURE','pid':proc.pid})
            for proc,log,_,_ in active:
                proc.wait();log.close()
            active=[];break
        time.sleep(5)
    status='FAILED' if failure else 'COMPLETE'
    if not failure:
        predict_subprocess('A',42)
    result={'status':status,'jobs':complete,'failure':failure,'aborted_jobs':aborted,'unstarted_jobs':pending,
        'UTC':utc(),'source_failed_run_untouched':True,'automatic_retries':0,'IM_metrics_computed':False}
    put(d/'reports/execution_completed.json',result)
    from . import hla_recovery_export as export
    return export.finish(result)


def stop_owned_on_exception() -> None:
    for proc in _OWNED_PROCESSES:
        if proc.poll() is None:
            if os.getpgid(proc.pid)==proc.pid:os.killpg(proc.pid,signal.SIGTERM)
            else:proc.terminate()
    for proc in _OWNED_PROCESSES:
        if proc.poll() is None:proc.wait()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','verify-load','supervise','worker','predict'])
    parser.add_argument('--arm',choices=['A','W','L']);parser.add_argument('--seed',type=int)
    parser.add_argument('--checkpoint',type=Path);parser.add_argument('--expected',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.action=='prepare':result=prepare()
        elif args.action=='verify-load':result=strict_reload_child(args.checkpoint,args.expected,args.output)
        elif args.action=='supervise':result=supervise()
        elif args.action=='worker':worker(args.arm,args.seed);result={'status':'COMPLETE'}
        else:
            install_bindings();validate_model_for_scoring(args.arm,args.seed)
            result=science.infer_one(args.arm,args.seed)
    except BaseException as error:
        if args.action=='supervise':stop_owned_on_exception()
        _,_,d,_=context()
        put(d/f'reports/recovery_{args.action}_FAILED_{time.time_ns()}.json',{'UTC':utc(),'error':repr(error),
            'action':args.action,'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':main()
