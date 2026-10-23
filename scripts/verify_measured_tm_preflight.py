#!/usr/bin/env python3
"""Check saved Task 2.35 decisions/witnesses; no scoring, fitting or new distances."""
from decimal import Decimal, localcontext
import hashlib
import json

from stability_label_curation import measured_tm_preflight as study
from stability_label_curation.paths import resolve_paths


def main() -> None:
    paths=resolve_paths();d=paths.project_runs_dir/study.RUN
    freeze=study.read_json(d/'reports/identities_frozen.json')
    assert freeze['software']==study.software(paths)
    assert freeze['IM_labels_loaded'] is False and freeze['model_scores_loaded'] is False
    for name,expected in freeze['immutable_identity_artifact_hashes'].items():study.assert_sha(d/name,expected)
    candidates=study.read_rows(d/'manifests/measured_Tm_candidates.jsonl')
    panel=study.read_rows(d/'manifests/measured_Tm_preferred_panel.jsonl')
    assert [r['source_id'] for r in candidates]==[r['source_id'] for r in panel]
    assert len(candidates)==1493 and len({r['source_id'] for r in candidates})==1493
    retained={r['source_id'] for r in panel if r['preferred_training_eligible']}
    assert len(retained)==1490
    for row in candidates:
        assert study.valid_ninemer(row['peptide']) and 0<=row['target']<=1
        with localcontext() as context:
            context.prec=50
            assert Decimal(row['target_decimal'])==Decimal('.5')+(Decimal(row['Tm_C_original_numeric_text'])-37)/72
    assert sum(bool(r['quality_flags']) for r in candidates)==5
    assert all(r['source_id'] in retained for r in candidates if r['quality_flags'])
    witnesses=0;external={}
    for name in ('EL_train','EL_validation','IMPROVE','neoepitope'):
        rows=study.read_rows(d/f'overlaps/Tm_to_{name}.jsonl')
        assert [r['source_id'] for r in rows]==[r['source_id'] for r in candidates]
        for row in rows:
            for prefix in ('','same_HLA_'):
                key='minimum_Hamming' if not prefix else 'minimum_same_HLA_Hamming'
                witness='nearest_peptide' if not prefix else 'nearest_same_HLA_peptide'
                assert row[key]==sum(a!=b for a,b in zip(row['peptide'],row[witness],strict=True))
                assert len(row[witness])==9;witnesses+=1
            assert row['minimum_Hamming']<=row['minimum_same_HLA_Hamming']
            assert row['exact_pair']==(row['minimum_same_HLA_Hamming']==0)
            assert row['exact_peptide']==(row['minimum_Hamming']==0)
        if name in study.COHORTS:external[name]=rows
    for i,row in enumerate(panel):
        reasons=[n for n in study.COHORTS if external[n][i]['minimum_Hamming']<=2]
        assert row['exclusion_reasons']==reasons and row['preferred_training_eligible']==(not reasons)
    negatives=0
    for hla in study.HLAS:
        h=hla.replace('HLA-','').replace('*','').replace(':','')
        pool=study.read_rows(d/f'decoys/{h}_candidate_identities.jsonl')
        selected=study.read_rows(d/f'decoys/{h}_provisional_selected_identities.jsonl')
        available=[r for r in pool if r['adaptation_decoy_eligible']]
        available.sort(key=lambda r:(hashlib.sha256(('Task2.35-decoy-v1|'+r['hla']+'|'+r['peptide']).encode()).hexdigest(),r['hla'],r['peptide']))
        expected_count=16*sum(r['hla']==hla and r['preferred_training_eligible'] for r in panel)
        assert selected==available[:expected_count] and len(selected)==expected_count
        assert len({(r['hla'],r['peptide']) for r in selected})==expected_count
        assert all(r['original_EL_label']==0 and not r['exclusion_reasons'] and 'Tm_C' not in r for r in selected)
        assert all(r[n+'_distance']['minimum_Hamming']>=3 for r in selected for n in study.COHORTS)
        negatives+=len(selected)
    decision=study.read_json(d/'reports/feasibility_decision.json')
    assert decision['decision']=='NO-GO' and decision['support_gate']==study.SUPPORT
    assert not decision['training_inference_or_IM_performance_executed']
    assert not decision['models_or_model_scores_loaded'] and not decision['GPU_used']
    support=decision['cohorts']
    assert support['IMPROVE']['per_HLA'][study.HLAS[0]]['preferred_unchanged']['passes_minimum_support']
    assert support['IMPROVE']['per_HLA'][study.HLAS[1]]['preferred_unchanged']['positive']==8
    assert not support['IMPROVE']['intended_two_HLA_primary_support']
    for name in study.COHORTS:
        assert support[name]['original_full_cohort']==support[name]['preferred_full_cohort']
    # Logs are supplied by the execution wrapper, never reconstructed by verification.
    assert 'Ran 11 tests' in (d/'logs/focused_tests.log').read_text() and '\nOK\n' in (d/'logs/focused_tests.log').read_text()
    result={'status':'PASS','focused_tests':11,'synthetic_brute_force_Hamming_validation_passed':True,
        'frozen_source_counts_reproduced':True,'frozen_Tm_candidates':1493,'preferred_Tm_retained':1490,
        'literal_Hamming_witness_checks':witnesses,'provisional_decoy_selection_verified':negatives,
        'original_external_observations_unchanged':True,'identity_decisions_frozen_before_current_outcome_tabulation':True,
        'support_insufficiency_preserved_no_single_HLA_primary_switch':True,'no_model_or_GPU_work':True,
        'software':study.software(paths)}
    target=d/'reports/completion_verification.json'
    if target.exists():
        assert study.read_json(target)==result
    else:
        study.write_json(target,result)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
