#!/usr/bin/env python3
"""Validate Task 2.32 saved evidence without model calls or metric reruns."""
from collections import Counter
import gzip
import json
import math
from stability_label_curation.paths import resolve_paths
from stability_label_curation import el_only_zero_shot_im as study
from stability_label_curation.replicate_stability_association import write_json, read_rows


def main():
    paths=resolve_paths();directory,config,proof=study.frozen_inputs(paths)
    _,completed=study.require(paths,'evaluation_completed')
    models,_,keys=study.authenticate_models(paths,config)
    repair=json.loads((directory/'reports/technical_io_repair.json').read_text())
    for name,expected in repair['completed_outputs_preserved'].items():
        study.assert_sha(directory/name,expected)
    prediction_receipt=json.loads((directory/'reports/predictions_frozen.json').read_text())
    points=json.loads((directory/'evaluation/point_metrics.json').read_text())
    predicted_rows=0
    for dataset in study.DATASETS:
        identities=read_rows(directory/f'cohorts/{dataset}_identities.jsonl')
        labels=read_rows(directory/f'cohorts/{dataset}_outcomes.jsonl')
        joined=read_rows(directory/f'evaluation/{dataset}_joined.jsonl')
        spec=config['cohorts'][dataset]
        assert len(identities)==len(labels)==len(joined)==spec['n']
        assert sum(r['label'] for r in labels)==spec['positives']
        assert points[dataset]==json.loads((directory/f'evaluation/{dataset}_point_metrics.json').read_text())
        for identity,label,row in zip(identities,labels,joined,strict=True):
            assert all(row[k]==v for k,v in identity.items())
            assert label['source_id']==identity['source_id'] and row['label']==label['label']
        for arm in study.ARMS:
            path=directory/f'predictions/{dataset}_{arm}.jsonl'
            study.assert_sha(path,prediction_receipt['predictions'][f'{dataset}_{arm}']['sha256'])
            predictions=read_rows(path);study.join_predictions(identities,predictions)
            for prediction,row in zip(predictions,joined,strict=True):
                assert math.isfinite(prediction['raw_EL_logit']) and 0<=prediction['EL_probability']<=1
                assert row['scores'][arm]==prediction['EL_probability']
            predicted_rows+=len(predictions)
        component='patient_peptide_component' if dataset=='IMPROVE' else 'peptide_component'
        groups=sorted({r[component] for r in joined});sizes=Counter(r[component] for r in joined)
        assert len(groups)==(38 if dataset=='IMPROVE' else 265)
        name='IMPROVE_patient_component_draws.jsonl.gz' if dataset=='IMPROVE' else 'neoepitope_peptide_draws.jsonl.gz'
        draws=0
        with gzip.open(directory/'evaluation'/name,'rt') as stream:
            for line in stream:
                draws+=1;row=json.loads(line);weights=row['component_multiplicities']
                assert len(weights)==len(groups) and sum(weights)==len(groups)
                assert row['n']==sum(n*sizes[group] for n,group in zip(weights,groups,strict=True))
                assert all(row['contrasts'][contrast]['prevalence']==0 for contrast,_,_ in study.PAIRINGS)
        assert draws==10000
    uncertainty=json.loads((directory/'evaluation/IMPROVE_paired_uncertainty.json').read_text())['study_peptide']
    assert uncertainty['components']==1 and uncertainty['draws_executed']==0 and uncertainty['confidence_intervals'] is None
    result={'status':'PASS','complete_EL_models_verified':3,'native_tensor_keys':len(keys),
            'frozen_cohorts_verified':2,'finite_aligned_study_logit_probability_pairs':predicted_rows,
            'prediction_passes':6,'completed_primary_points_and_predictions_preserved_across_IO_fix':True,
            'paired_component_draws_verified':20000,'study_component_interval_undefined':True,
            'model_inference_training_performance_or_bootstrap_repeated':False,
            'scientific_hashes':study.software_hashes(paths)}
    write_json(directory/'reports/completion_verification.json',result)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
