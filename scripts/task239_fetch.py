#!/usr/bin/env python3
"""Acquire only the pinned Task 2.39 public artifacts; never execute installers.

Model archives remain external and are not redistributed. Existing files must
match the frozen registry. Archive extraction is separate and rejects links and
path traversal. No datasets with IM outcomes or upstream downstream results are
requested by this script.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--include-weights',action='store_true');args=parser.parse_args()
    paths=resolve_paths();root=paths.project_data_dir/'modern_models_task2_39'
    cfg=json.loads((Path(__file__).resolve().parents[1]/'configs/modern_models_task239.json').read_text())
    mix=cfg['mix']['revision'];s=cfg['spearmint'];hf=s['revision'];gh=s['source_revision'];ipd=cfg['ipd']['revision']
    jobs={'mix_v3.0.tar.gz':(f'https://codeload.github.com/GfellerLab/MixMHCpred/tar.gz/{mix}',cfg['mix']['archive_sha256']),
          'ipd_imgt_3.64.0/hla_prot.fasta':(f'https://raw.githubusercontent.com/ANHIG/IMGTHLA/{ipd}/fasta/hla_prot.fasta',cfg['ipd']['sha256'])}
    for rel,sha in cfg['file_sha256'].items():
        if rel.startswith('spearmint_source/'):
            name=rel.removeprefix('spearmint_source/')
            if name.startswith(('s2_','s3_')):
                stage,split=name.split('_');folder='binding_stability' if stage=='s2' else 'stage3_assay_conditioning';name=f'data/{folder}/{split}'
            url=f'https://raw.githubusercontent.com/dhuvik/spearmint/{gh}/{name}'
        elif rel.startswith('spearmint_stage3/'):
            url=f'https://huggingface.co/dkarthikeyan1/spearmint/resolve/{hf}/{Path(rel).name}'
        else:
            url=cfg['metadata_urls'][rel]
        jobs[rel]=(url,sha)
    if args.include_weights:
        jobs[f'spearmint_stage3/{hf}/model.safetensors']=(f'https://huggingface.co/dkarthikeyan1/spearmint/resolve/{hf}/model.safetensors',s['weights_sha256'])
    for rel,(url,sha) in jobs.items():
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            with urllib.request.urlopen(url,timeout=180) as response,p.open('xb') as f:
                while block:=response.read(4*1024*1024):f.write(block)
        if digest(p)!=sha:raise ValueError('Do not overwrite mismatched artifact: '+rel)
        p.with_name(p.name+'.provenance.json').write_text(json.dumps({'url':url,'sha256':sha,'bytes':p.stat().st_size},indent=2)+'\n')
        print('verified',rel)
    dest=root/'mix_release'
    if not (dest/('MixMHCpred-'+mix)).exists():
        dest.mkdir(exist_ok=True)
        with tarfile.open(root/'mix_v3.0.tar.gz') as archive:
            if any(m.issym() or m.islnk() or '..' in Path(m.name).parts for m in archive.getmembers()):raise ValueError('Unsafe archive member')
            archive.extractall(dest,filter='data')


if __name__=='__main__':main()
