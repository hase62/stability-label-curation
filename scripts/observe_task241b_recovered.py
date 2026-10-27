"""Observe existing fits after daemon recovery; never launch training/inference.

The original parent monitor was lost, while all six existing workers and the
completion runner survived. Attach only to authenticated existing PID commands.
Completion requires all original final-fit receipts and checkpoint hashes.
"""
from __future__ import annotations
import argparse,json,os,time
from pathlib import Path
from stability_label_curation.low_stability_hard_filter import ARMS,require,read_json,write_json,runner

def command(pid: int) -> list[str]:
    try:return [s.decode() for s in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if s]
    except FileNotFoundError:return []

def main():
    parser=argparse.ArgumentParser();parser.add_argument('workers',nargs=6);args=parser.parse_args()
    p,c,d,proof=require();pids={a:int(pid) for a,pid in (s.split(':') for s in args.workers)}
    if set(pids)!=set(ARMS):raise ValueError('Exact six original workers required')
    if (d/'reports/supervisor_completed.json').exists():raise ValueError('Supervisor already completed')
    cmds={}
    for arm,pid in pids.items():
        cmds[arm]=command(pid)
        if cmds[arm][1:]!=['-m','stability_label_curation.low_stability_hard_filter','train',arm]:raise ValueError('Not the existing requested worker')
    receipt=d/'reports/supervisor_recovery.json'
    if receipt.exists():raise ValueError('Recovery observer already recorded')
    write_json(receipt,{'reason':'Codex daemon restarted; parent monitor lost; six original workers and completion process survived',
        'worker_PIDs':pids,'commands':cmds,'new_fits_launched':0,'scientific_configuration_changed':False,'observed_unix_time':time.time()})
    while True:
        complete={a:(d/f'reports/{a}_training_completed.json').exists() for a in ARMS}
        missing=[a for a in ARMS if not complete[a] and not command(pids[a])]
        if missing:
            write_json(d/'reports/supervisor_completed.json',{'status':'FAILED','seconds':time.time()-(d/'reports/supervisor_started.json').stat().st_mtime,
                'missing_final_receipts_for_exited_workers':missing,'recovered_observer':True,'no_retries':True})
            raise RuntimeError('Original worker exited without final-fit receipt: '+str(missing))
        if all(complete.values()):
            for arm in ARMS:
                r=read_json(d/f'reports/{arm}_training_completed.json')
                if r['status']!='COMPLETE' or r['epochs']!=10 or not r['strict_reload'] or r['optimizer_steps']!=10*proof['summary']['retained_positive']:raise ValueError('Invalid final-fit receipt')
                if r['scientific_hashes']!=proof['scientific_hashes'] or len(r['keys'])!=36:raise ValueError('Scientific configuration/model mismatch')
                if runner.checkpoint_identity(d/r['checkpoint'],r['keys'])!=r['files']:raise ValueError('Final checkpoint file hash mismatch')
            write_json(d/'reports/supervisor_completed.json',{'status':'PASS','seconds':time.time()-(d/'reports/supervisor_started.json').stat().st_mtime,
                'duration_basis':'wall clock from original supervisor-start receipt mtime','recovered_observer':True,
                'codes':{a:None for a in ARMS},'exit_codes_unavailable_after_parent_loss':True,'all_six_original_final_receipts_and_checkpoint_hashes_verified':True,
                'new_fits_launched':0,'scientific_configuration_changed':False})
            print('ORIGINAL_SIX_FITS_COMPLETE_VERIFIED',flush=True);return
        print(json.dumps({'complete':complete,'original_workers_observed':True}),flush=True);time.sleep(30)

if __name__=='__main__':main()
