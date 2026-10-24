#!/usr/bin/env python3
"""Verify saved Task2.37 identities/training/scores/uncertainty without refitting."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

from stability_label_curation import measured_tm_direct_transfer as study
from stability_label_curation.paths import resolve_paths


def training_checks(paths):
    import torch
    d,cfg,prepared=study.inputs(paths);_,training=study.require(paths,'training_complete')
    ref,_,keys=study.baseline(paths,cfg)
    assert len(training['fits'])==9 and set(training['fits'])==set(study.CONDITIONS)-{'A'}
    ready=json.loads((paths.repository_root/'configs/measured_tm_a02_direct_transfer_task2_37.ready.json').read_text())
    study.assert_sha(d/ready['relative_path'],ready['sha256'])
    rows=study.read_rows(d/'inputs/training.jsonl');assert len(rows)==12070
    assert Counter(r['kind'] for r in rows)=={'measured':710,'decoy':11360}
    assert all(r['hla']=='HLA-A*02:01' and r['sample_weight']==(16 if r['kind']=='measured' else 1) for r in rows)
    assert sum(r['sample_weight'] for r in rows)==22720
    assert all('Tm_C' not in r for r in rows if r['kind']=='decoy')
    changes={};observed_steps=0
    for seed in study.SEEDS:
        targets=json.loads((d/f'inputs/targets_{seed}.json').read_text())
        measured=[i for i,r in enumerate(rows) if r['kind']=='measured']
        assert Counter(targets['P'][i] for i in measured)==Counter(targets['T'][i] for i in measured)
        orders=json.loads((d/f'inputs/orders_{seed}.json').read_text())
        expected_indices=[];expected_sources=[]
        for order in orders:
            assert sorted(order)==list(range(12070))
            expected_indices.append(study.digest([order[i:i+64] for i in range(0,len(order),64)]))
            expected_sources.append(study.digest([[rows[j]['source_id'] for j in order[i:i+64]] for i in range(0,len(order),64)]))
        for arm in study.ADAPTED:
            name=f'{arm}_{seed}';fit=training['fits'][name]
            assert fit['initial_state']==ref['state'] and fit['updates']==3780 and fit['passes']==20
            assert fit['optimizer_internal_steps']==[3780,3780]
            assert [r['ordered_index_digest'] for r in fit['history']]==expected_indices
            assert [r['batch_source_order_digest'] for r in fit['history']]==expected_sources
            assert all(r['sample_weight_sum']==22720 and r['updates']==189 and r['only_output_gradients'] and r['all_modules_eval'] for r in fit['history'])
            assert {k for k in keys if fit['state'][k]!=ref['state'][k]}==set(study.OUTPUT_KEYS)
            assert fit['trainable_scalar_count']==415 and sum(fit['changed_scalar_counts'].values())==415
            path=d/fit['head_relative_path'];study.assert_sha(path,fit['head_sha256'])
            head=torch.load(path,map_location='cpu',weights_only=True);assert set(head)==set(study.OUTPUT_KEYS)
            for key,value in head.items():
                assert value.dtype==torch.float32 and bool(torch.isfinite(value).all())
                assert hashlib.sha256(value.contiguous().numpy().tobytes()).hexdigest()==fit['state'][key]
            assert study.digest(fit['state'])==fit['complete_state_digest']
            assert fit['strict_parent_plus_two_tensor_reload_equal']
            if name=='D_123':
                assert fit['recovered_completed_fit_without_new_optimizer_updates']
                assert fit['training_probe_bitwise_equal'] is None and fit['reconstructed_training_mode_probe_bitwise_equal']
            else:assert fit['training_probe_bitwise_equal']
            observed_steps+=fit['updates'];changes[name]=fit['changed_scalar_counts']
    repair=json.loads((d/'reports/technical_reload_repair.json').read_text())
    for name,expected in repair['preserved_artifacts'].items():study.assert_sha(d/name,expected)
    assert observed_steps==34020 and not repair['loss_optimizer_seed_order_targets_or_IM_inference_changed']
    return d,{'nine_fits':9,'passes_per_fit':20,'optimizer_updates':34020,'trainable_scalars':415,
        'only_final_two_keys_changed':True,'all_seed_matched_order_and_target_checks':True,
        'D_123_completed_fit_preserved_not_retrained':True,'changed_scalar_counts':changes}


def main():
    paths=resolve_paths();d,result=training_checks(paths)
    if len(sys.argv)>1 and sys.argv[1]=='training-only':
        print(json.dumps({'status':'PASS',**result},sort_keys=True));return
    _,completed=study.require(paths,'evaluation_complete');_,prediction=study.require(paths,'predictions_frozen')
    old,old_manifest=study.previous(paths,study.config(paths));pairs=0
    for dataset in study.data.COHORTS:
        identities=study.read_rows(d/f'inputs/{dataset}_identities.jsonl')
        joined=study.read_rows(d/f'evaluation/{dataset}_joined.jsonl')
        for condition in study.CONDITIONS:
            path=d/f'predictions/{dataset}_{condition}.jsonl'
            study.assert_sha(path,prediction['predictions'][dataset+'_'+condition]['sha256'])
            rows=study.read_rows(path);assert len(rows)==len(identities)
            extra=('raw_EL_logit','EL_probability') if condition=='A' else ('raw_logit','score')
            for r,identity,j in zip(rows,identities,joined,strict=True):
                assert {k:v for k,v in r.items() if k not in extra}==identity
                assert math.isfinite(r[extra[0]]) and math.isfinite(r[extra[1]]) and 0<=r[extra[1]]<=1
                assert j['scores'][condition]==r[extra[1]]
            ordered=sorted(rows,key=lambda r:r[extra[0]])
            assert all(a[extra[1]]<=b[extra[1]] for a,b in zip(ordered,ordered[1:]))
            pairs+=len(rows)
        study.assert_sha(d/f'predictions/{dataset}_A.jsonl',old_manifest[f'predictions/{dataset}_A.jsonl'])
    points=json.loads((d/'evaluation/point_metrics.json').read_text());draws_verified=0
    for name,field,count in [('IMPROVE_A02','patient_peptide_component',16),('IMPROVE_full','patient_peptide_component',38),('neoepitope','peptide_component',265)]:
        source=study.read_rows(d/f'evaluation/{"neoepitope" if name=="neoepitope" else "IMPROVE"}_joined.jsonl')
        if name=='IMPROVE_A02':source=[r for r in source if r['hla']=='HLA-A*02:01']
        sizes=Counter(r[field] for r in source);groups=sorted(sizes);assert len(groups)==count
        actual={pair:{metric:0 for metric in points[name]['seed_mean_paired_contrasts'][pair]} for pair in ('T-P','T-A','T-D')}
        with gzip.open(d/f'evaluation/{name}_paired_draws.jsonl.gz','rt') as stream:
            n=0
            for line in stream:
                row=json.loads(line);n+=1;weights=row['component_multiplicities'];assert len(weights)==count and sum(weights)==count
                assert row['n']==sum(sizes[g]*w for g,w in zip(groups,weights,strict=True))
                for pair,metrics in row['seed_mean_paired_contrasts'].items():
                    for metric,value in metrics.items():actual[pair][metric]+=value is not None
        assert n==10000;draws_verified+=n
        ci=json.loads((d/f'evaluation/{name}_paired_uncertainty.json').read_text())
        for pair,metrics in ci['confidence_intervals'].items():
            for metric,item in metrics.items():assert item['usable_draws']==actual[pair][metric] and item['invalid_draws']==10000-actual[pair][metric]
        for pair,other in [('T-P','P'),('T-A','A'),('T-D','D')]:
            for metric,value in points[name]['seed_mean_paired_contrasts'][pair].items():
                expected=math.fsum(points[name]['per_seed'][str(seed)]['T'][metric]-points[name]['per_seed'][str(seed)][other][metric] for seed in study.SEEDS)/3
                assert value==expected
    primary=points['IMPROVE_A02']['population'];assert (primary['n'],primary['positive'],primary['negative'])==(616,21,595)
    assert pairs==80550
    result.update(status='PASS',aligned_finite_logit_score_pairs=pairs,prediction_files=20,paired_draws_verified=draws_verified,
        metric_or_model_recomputation_performed=False,original_evaluation_identities_preserved=True,
        scientific_hashes=study.science(paths))
    target=d/'reports/completion_verification.json'
    if target.exists():assert json.loads(target.read_text())==result
    else:study.write_json(target,result)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
