#!/usr/bin/env python3
"""Fixed public peptides only. This command has no cohort path/input argument."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import (
    SMOKE_HLAS, SMOKE_PEPTIDES, assay_contract, digest, mix_allele, parse_mix, verify_digest,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('model', choices=['mix', 'spearmint'])
    args = parser.parse_args()
    paths = resolve_paths()
    root = paths.project_data_dir / 'modern_models_task2_39'
    run = paths.project_runs_dir / 'task-2_39-modern-el-stability-z790-preflight'
    cfg = json.loads((Path(__file__).resolve().parents[1]/'configs/modern_models_task239.json').read_text())
    # Isolated environment must retain its captured dependency resolution.
    import importlib.metadata
    lock_name = 'mixmhcpred' if args.model == 'mix' else 'spearmint'
    lock = Path(__file__).resolve().parents[1] / f'configs/task239_{lock_name}.lock.txt'
    verify_digest(lock, cfg['dependency_locks'][lock_name])
    for line in lock.read_text().splitlines():
        name, version = line.split('==', 1)
        if importlib.metadata.version(name) != version:
            raise ValueError('Runtime lock mismatch: ' + name)
    security = json.loads((run/'security_review.json').read_text())
    if security[args.model]['status'] != 'PASS':
        raise ValueError('Security gate not passed')
    for rel, sha in security[args.model]['runtime_files'].items():
        verify_digest(root/rel, sha)
    output = run/(args.model+'_public_smoke.json')
    if output.exists():
        raise FileExistsError('Preserve previous smoke evidence; no overwrite')
    started = time.monotonic()
    pairs = [(p,a) for a in SMOKE_HLAS for p in SMOKE_PEPTIDES]
    records = []
    details = {}
    if args.model == 'mix':
        mix = root/'mix_release'/('MixMHCpred-'+cfg['mix']['revision'])
        inp = run/'public_smoke_peptides.txt'
        if inp.exists() and inp.read_text() != '\n'.join(SMOKE_PEPTIDES)+'\n':
            raise ValueError('Public peptide file mismatch')
        inp.write_text('\n'.join(SMOKE_PEPTIDES)+'\n')
        env = dict(os.environ, PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'])
        details['version'] = subprocess.check_output(['bash',str(mix/'MixMHCpred'),'--help'],env=env,text=True).splitlines()[0]
        if details['version'] != 'MixMHCpred3.0':
            raise ValueError('Wrong executable version')
        for a in SMOKE_HLAS:
            results = []
            headers = []
            # Also multi-allele invocation to exercise best-allele disagreement safely.
            for suffix, alleles in [('first',mix_allele(a)),('repeat',mix_allele(a)),
                                    ('multi','A0201,B0702')]:
                out = run/f'mix_public_{mix_allele(a)}_{suffix}.tsv'
                if out.exists():
                    raise FileExistsError(out.name)
                cmd=['bash',str(mix/'MixMHCpred'),'-i',str(inp),'-o',str(out),'-a',alleles,'-m','0']
                cp=subprocess.run(cmd,env=env,text=True,capture_output=True,check=True)
                (run/f'mix_public_{mix_allele(a)}_{suffix}.log').write_text(cp.stdout+cp.stderr)
                text=out.read_text()
                headers.append([s for s in text.splitlines() if s.startswith('#')])
                results.append(parse_mix(text,SMOKE_PEPTIDES,a))
            if results[0] != results[1] or results[0] != results[2]:
                raise ValueError('Mix repeat/batched designated-HLA mismatch')
            records.extend(results[0])
            details[a]={'headers':headers, 'repeat_identical':True,'multi_HLA_designated_column_identical':True}
            for i,p in enumerate(SMOKE_PEPTIDES):
                single_in = run/f'public_single_{mix_allele(a)}_{i}.txt'
                single_in.write_text(p+'\n')
                single_out = run/f'mix_public_single_{mix_allele(a)}_{i}.tsv'
                if single_out.exists():
                    raise FileExistsError(single_out.name)
                cp=subprocess.run(['bash',str(mix/'MixMHCpred'),'-i',str(single_in),'-o',str(single_out),'-a',mix_allele(a),'-m','0'],env=env,text=True,capture_output=True,check=True)
                if parse_mix(single_out.read_text(),[p],a)[0] != results[0][i]:
                    raise ValueError('Mix single/batch difference')
        details['single_batch_identical']=True
    else:
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1')
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
        import torch
        import transformers
        import safetensors
        hf=root/'spearmint_stage3'/cfg['spearmint']['revision']
        verify_digest(hf/'model.safetensors',cfg['spearmint']['weights_sha256'])
        if (hf/'pytorch_model.bin').exists():
            raise ValueError('Pickle path forbidden')
        # Keep function signature intact for inspected upstream compatibility check,
        # then forbid pickle and remote snapshot paths before loading any weights.
        sys.path.insert(0,str(hf))
        import modeling_spearmint as upstream
        def forbidden(*args,**kwargs):
            raise RuntimeError('Network/pickle load prohibited in Task 2.39')
        upstream.torch_load=forbidden
        import huggingface_hub
        huggingface_hub.snapshot_download=forbidden
        torch.manual_seed(239)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
        torch.set_num_threads(4)
        tokenizer=upstream.SpearmintTokenizer()
        assay_idx,temp=assay_contract(tokenizer.ASSAY_TYPES)
        model=upstream.SpearmintForStabilityPrediction.from_pretrained(str(hf),local_files_only=True).to('cuda').eval()
        if model.training or any(m.training for m in model.modules()):
            raise ValueError('Evaluation mode not set')
        seqs=json.loads((run/'hla_full_length_references.json').read_text())
        peptides=[p for p,a in pairs];mhcs=[seqs[a]['sequence'] for p,a in pairs]
        def forward(items):
            with torch.inference_mode():
                return model(*(x.cuda() for x in items))['logits'].detach().cpu().flatten()
        inputs=tokenizer.prepare_batch(peptides,mhcs,assays=['SPA']*4,temperatures_c=[37.0]*4)
        if inputs[2].tolist()!=[assay_idx]*4 or inputs[3].tolist()!=[temp]*4:
            raise ValueError('Assay/temperature mapping mismatch')
        batch=forward(inputs);repeat=forward(inputs)
        if not torch.isfinite(batch).all() or not torch.equal(batch,repeat):
            raise ValueError('Nonfinite/nondeterministic public predictions')
        single=[]
        for p,a in pairs:
            items=tokenizer.prepare_input(p,seqs[a]['sequence'],assay='SPA',temperature_c=37.0)
            single.append(forward((items[0].unsqueeze(0),items[1].unsqueeze(0),items[2],items[3]))[0])
        single=torch.stack(single)
        torch.testing.assert_close(batch,single,atol=cfg['smoke']['single_batch_atol'],rtol=cfg['smoke']['single_batch_rtol'])
        records=[{'peptide':p,'hla':a,'log1p_half_life_hours':float(x),'single':float(y)} for (p,a),x,y in zip(pairs,batch,single,strict=True)]
        details={'assay':'SPA','assay_idx':assay_idx,'temperature_C':temp,'eval_mode':True,
                 'repeat_identical':True,'single_batch_max_abs_difference':float((batch-single).abs().max()),
                 'torch':torch.__version__,'transformers':transformers.__version__,
                 'safetensors':safetensors.__version__,'device':torch.cuda.get_device_name(),
                 'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),
                 'peak_GPU_reserved_bytes':torch.cuda.max_memory_reserved(),
                 'tokenizer_sha256':digest(hf/'modeling_spearmint.py'),
                 'chain_lengths':[len(s) for s in mhcs]}
    output.write_text(json.dumps({'status':'PASS','public_only':True,'model':args.model,
                     'records':records,'details':details,'seconds':time.monotonic()-started},indent=2,allow_nan=False)+'\n')
    print(output.name,'PASS',time.monotonic()-started)


if __name__=='__main__':
    main()
