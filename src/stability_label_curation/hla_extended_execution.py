"""Infrastructure-only orchestration: separate training and prediction processes.

The frozen scientific hla_extended_epochs module is unchanged. Adopt already
running fits, preserve their training, and recover only the known pre-inference
PyTorch interop-initialization failure. No failed training is retried.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import hla_extended_epochs as science


def alive(pid: int) -> bool:
    path = Path('/proc')/str(pid)/'stat'
    try:
        return path.read_text().split(') ', 1)[1].split()[0] != 'Z'
    except FileNotFoundError:
        return False


def known_inference_setup_failure(record: dict) -> bool:
    return record.get('error') == "RuntimeError('Error: cannot set number of interop threads after parallel work has started or set_num_interop_threads called')"


def predict(arm: str, seed: int) -> None:
    p, _, d = science.paths_config()
    log = d/f'logs/{arm}_{seed}_fresh_prediction.log'
    with log.open('x') as stream:
        subprocess.run([sys.executable, '-m', 'stability_label_curation.hla_extended_epochs', 'predict',
            '--arm', arm, '--seed', str(seed)], cwd=p.repository_root, stdout=stream,
            stderr=subprocess.STDOUT, check=True)


def worker(arm: str, seed: int) -> None:
    _, _, d = science.paths_config()
    try:
        science.train(arm, seed)
        predict(arm, seed)
    except Exception as error:
        science.put(d/f'reports/{arm}_{seed}_execution_FAILED.json', {'error': repr(error),
            'training_completion_exists': (d/f'reports/{arm}_{seed}_completed.json').exists()})
        raise


def supervise(adopt: list[dict]) -> dict:
    p, c, d, proof = science.require()
    prior = science.read(d/'reports/execution_started.json')
    if prior['scientific_hashes'] != proof['scientific_hashes']:
        raise ValueError('Scientific source/configuration changed')
    if not adopt or len({(x['arm'], x['seed']) for x in adopt}) != len(adopt):
        raise ValueError('Invalid adoption mapping')
    for item in adopt:
        cmd = (Path('/proc')/str(item['pid'])/'cmdline').read_bytes().decode().split('\x00')
        if (not alive(item['pid']) or 'fit-and-predict' not in cmd
                or cmd[cmd.index('--arm')+1] != item['arm'] or int(cmd[cmd.index('--seed')+1]) != item['seed']):
            raise ValueError('Original active worker identity differs')
    adopted = {(x['arm'], x['seed']) for x in adopt}
    pending = [(arm, seed) for arm, seed in c['jobs'] if (arm, seed) not in adopted]
    active = [dict(item, process=None, log=None) for item in adopt]
    receipt = {'commit': science.git(p.repository_root, 'rev-parse', 'HEAD'),
        'scientific_module_sha256': science.sha(p.repository_root/science.SCRIPT),
        'orchestrator_sha256': science.sha(Path(__file__)), 'adopted_running_fits': adopt,
        'original_supervisor_pid': science.read(d/'reports/supervisor_launch.json')['pid'],
        'training_retry_authorized': False, 'inference_process_policy': 'fresh_process_per_fit',
        'scientific_conditions_changed': False, 'external_IM_results_accessed': False,
        'reason': 'Interop setter cannot be called twice in one Python process; inference fails before model loading.'}
    science.put(d/'reports/fresh_process_execution_started.json', receipt)
    completed, recovered, failed = [], [], False
    while active or pending:
        while pending and len(active) < c['maximum_concurrency'] and not failed:
            arm, seed = pending.pop(0)
            log = (d/f'logs/{arm}_{seed}_worker.log').open('x')
            process = subprocess.Popen([sys.executable, '-m', 'stability_label_curation.hla_extended_execution', 'worker',
                '--arm', arm, '--seed', str(seed)], cwd=p.repository_root, stdout=log, stderr=subprocess.STDOUT)
            active.append({'arm': arm, 'seed': seed, 'pid': process.pid, 'process': process, 'log': log})
        for item in list(active):
            process = item['process']
            if (process.poll() is None if process is not None else alive(item['pid'])):
                continue
            arm, seed = item['arm'], item['seed']
            if item['log'] is not None:
                item['log'].close()
            complete = d/f'reports/{arm}_{seed}_completed.json'
            failure = d/f'reports/{arm}_{seed}_FAILED.json'
            try:
                if process is None:
                    if not complete.exists() or not failure.exists() or not known_inference_setup_failure(science.read(failure)):
                        raise RuntimeError('Adopted worker failed outside the known post-training setup path')
                    # No model is loaded or score is written by the failed setter.
                    if list((d/'predictions').glob(f'{arm}_{seed}_*.jsonl')) if (d/'predictions').exists() else False:
                        raise RuntimeError('Unexpected partial prediction; no silent re-inference')
                    predict(arm, seed)
                    recovered.append({'arm': arm, 'seed': seed, 'failure_preserved': str(failure),
                        'training_repeated': False, 'model_prediction_attempts_before_fresh_process': 0})
                elif process.returncode != 0:
                    raise RuntimeError(f'Fresh-process worker exit code {process.returncode}')
                if not complete.exists() or not (d/f'reports/{arm}_{seed}_prediction_receipt.json').exists():
                    raise RuntimeError('Completion/prediction receipt missing')
                completed.append({'arm': arm, 'seed': seed, 'training_complete': True, 'predictions_complete': True})
            except Exception as error:
                failed = True
                science.put(d/f'reports/{arm}_{seed}_orchestration_FAILED.json', {'error': repr(error)})
            active.remove(item)
        if failed and not active:
            break
        time.sleep(5)
    if not failed:
        predict('A', 42)
    result = {'status': 'FAILED' if failed else 'COMPLETE', 'jobs': completed,
        'unstarted_jobs': pending, 'post_training_inference_setup_recoveries': recovered,
        'scientific_conditions_changed': False, 'training_repeated': False,
        'external_IM_evaluation': False, 'execution_commit': receipt['commit']}
    science.put(d/'reports/execution_completed.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['worker', 'supervise'])
    parser.add_argument('--arm', choices=['A', 'W', 'L'])
    parser.add_argument('--seed', type=int)
    parser.add_argument('--adopt-manifest')
    args = parser.parse_args()
    if args.action == 'worker':
        worker(args.arm, args.seed)
    else:
        print(json.dumps(supervise(science.read(Path(args.adopt_manifest))), sort_keys=True))


if __name__ == '__main__':
    main()
