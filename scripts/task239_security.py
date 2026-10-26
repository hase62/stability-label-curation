#!/usr/bin/env python3
"""Record source review and reject unauthenticated or unsafe weight paths.

Run after task239_preflight.py and the documented manual source review. This is
an execution gate, not a claim that arbitrary remote code can be made safe by hashes.
"""
import json
from pathlib import Path
import pickletools
import subprocess
import sys

from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import digest, verify_digest


def main():
    paths=resolve_paths();root=paths.project_data_dir/'modern_models_task2_39'
    run=paths.project_runs_dir/'task-2_39-modern-el-stability-z790-preflight'
    cfg=json.loads((Path(__file__).resolve().parents[1]/'configs/modern_models_task239.json').read_text())
    mix=root/'mix_release'/('MixMHCpred-'+cfg['mix']['revision'])
    hf=root/'spearmint_stage3'/cfg['spearmint']['revision']
    inventory=json.loads((run/'mix_artifact_inventory.json').read_text())
    for row in inventory:verify_digest(mix/row['path'],row['sha256'])
    for rel,sha in cfg['file_sha256'].items():verify_digest(root/rel,sha)
    verify_digest(hf/'model.safetensors',cfg['spearmint']['weights_sha256'])
    # Inspection is non-executing: parse NPY header and pickle instructions.
    # The official Mix release contains object-array numpy weights. Only the
    # observed NumPy reconstruction globals are admitted, with no STACK_GLOBAL,
    # extension codes, object constructors or persistent IDs.
    allowed={'numpy.core.multiarray _reconstruct','numpy ndarray','numpy dtype','numpy.core.multiarray scalar'}
    object_files=[]
    import ast,struct
    for p in sorted(mix.rglob('*.npy')):
        with p.open('rb') as f:
            if f.read(6)!=b'\x93NUMPY':raise ValueError('Not NPY')
            version=tuple(f.read(2));n=struct.unpack('<H' if version==(1,0) else '<I',f.read(2 if version==(1,0) else 4))[0]
            header=ast.literal_eval(f.read(n).decode('latin1'))
            if 'O' not in str(header['descr']):continue
            globals_seen=[]
            for opcode,arg,pos in pickletools.genops(f.read()):
                if opcode.name=='GLOBAL':
                    if arg not in allowed:raise ValueError('Unsafe numpy pickle global')
                    globals_seen.append(arg)
                if opcode.name in {'STACK_GLOBAL','INST','OBJ','NEWOBJ','NEWOBJ_EX','EXT1','EXT2','EXT4','PERSID','BINPERSID'}:
                    raise ValueError('Unexpected pickle opcode')
            object_files.append({'file':str(p.relative_to(mix)),'sha256':digest(p),'globals':sorted(set(globals_seen))})
    if len(object_files)!=9:raise ValueError('Unexpected official Mix object weights inventory')
    if (hf/'pytorch_model.bin').exists():raise ValueError('Pickle SPEARMINT path prohibited')
    result={
      'mix':{'status':'PASS','revision':cfg['mix']['revision'],
        'runtime_files':{str((mix/r['path']).relative_to(root)):r['sha256'] for r in inventory},
        'object_npy_review':object_files,
        'license':'academic non-commercial research only; no redistribution; commercial use requires separate license',
        'manual_review':'Reviewed launcher, install_packages, main.py, MixMHCpred.py and panPredictor.py. No installer/setup_path execution; -a only, -m 0, no -s eval/MAFFT path. New output files only. Pinned official object NPY files scanned before NumPy load; only NumPy reconstruction globals. No PRIME or system modifications.'},
      'spearmint':{'status':'PASS','revision':cfg['spearmint']['revision'],
        'runtime_files':{str(p.relative_to(root)):digest(p) for p in hf.iterdir() if p.is_file() and not p.name.endswith('.provenance.json')},
        'license':'MIT',
        'manual_review':'Reviewed both pinned Python files, imports, config, tokenizer, model constructor/forward and explicit from_pretrained. Self-contained ESM2/MINT tensor code; no shell/eval/exec in executed path. Upstream has snapshot_download and pickle fallback branches; existing absolute local snapshot + verified safetensors required; wrapper blocks both branches and sets HF/Transformers offline before load. No downloaded environment scripts run.'},
      'public_only_smoke_gate':True,'benchmark_inference_authorized':False,
      'limitations':'Static review is not a formal proof. Artifact pins and explicit local paths prevent moving remote code. Mix license is limited to intended academic non-commercial research; no redistribution rights inferred.'}
    (run/'security_review.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Security source/weight gates PASS; benchmark inference remains forbidden')


if __name__=='__main__':main()
