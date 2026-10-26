#!/usr/bin/env python3
"""Allele-reference metadata only; never passes cohort peptides to a model."""
import csv,json,sys
from pathlib import Path
from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import verify_digest,mix_allele

def main() -> None:
    paths=resolve_paths();root=paths.project_data_dir/'modern_models_task2_39'
    run=paths.project_runs_dir/'task-2_39-modern-el-stability-z790-preflight'
    cfg=json.loads((Path(__file__).resolve().parents[1]/'configs/modern_models_task239.json').read_text())
    review=json.loads((run/'security_review.json').read_text())['mix']
    assert review['status']=='PASS'
    for rel,h in review['runtime_files'].items():verify_digest(root/rel,h)
    mix=root/'mix_release'/('MixMHCpred-'+cfg['mix']['revision'])
    sys.path.insert(0,str(mix/'code'))
    from MixMHCpred import distance_to_training
    support=json.loads((run/'mix_hla_support.json').read_text())
    with (mix/'lib/alleles_list.txt').open() as f:training=[r['Allele'] for r in csv.DictReader(f,delimiter='\t')]
    alleles=sorted(support)
    nearest,distance=distance_to_training(str(mix/'lib'),training,[mix_allele(a) for a in alleles])
    result={a:{**support[a],'nearest_reference':n,'native_allele_distance':float(d),'note':'upstream BLOSUM/pseudosequence reference distance; not peptide distance or evidence of training sequence non-exposure'} for a,n,d in zip(alleles,nearest,distance,strict=True)}
    (run/'mix_nearest_reference.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Reference metadata:',len(result),'alleles; no peptide scores computed')


if __name__ == '__main__':
    main()
