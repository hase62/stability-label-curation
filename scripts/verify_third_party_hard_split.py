"""Focused read-only Task 2.26 checks; no model inference/performance calculation."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json

from stability_label_curation import third_party_hard_split as task
from stability_label_curation import bigmhc_independent_preflight as models
from stability_label_curation.sequence_hamming import valid_ninemer
from stability_label_curation.paths import resolve_paths


def read_rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def verify():
    paths = resolve_paths()
    directory = paths.project_runs_dir / task.RUN_ID
    read = lambda name: json.loads((directory / 'reports' / name).read_text())
    frozen = read('benchmark_freeze.json')
    if frozen['scientific_hashes'] != task.science_hashes(paths):
        raise ValueError('Frozen curator, thresholds or protocol changed')
    for name, expected in frozen['immutable_artifact_hashes'].items():
        if task.sha(directory / name) != expected:
            raise ValueError('Frozen artifact changed: ' + name)
    references = read('reference_freeze.json')
    sets = {}
    for name, metadata in references['sets'].items():
        path = directory / metadata['relative_path']
        if task.sha(path) != metadata['sha256']:
            raise ValueError('Frozen reference changed: ' + name)
        with gzip.open(path, 'rt') as stream:
            sequences = [line.strip() for line in stream]
        if sequences != sorted(set(sequences)) or not all(valid_ninemer(s) for s in sequences):
            raise ValueError('Invalid reference sequence inventory')
        if (len(sequences) != metadata['unique_canonical_ninemers'] or
                hashlib.sha256(''.join(s+'\n' for s in sequences).encode()).hexdigest() != metadata['ordered_sequence_content_sha256']):
            raise ValueError('Reference census/content differs')
        sets[name] = set(sequences)
    if not sets['IM_epoch_selection'] <= sets['IM_fit']:
        raise ValueError('Former IM selection population not part of final fitting set')
    witness_count = 0
    for record in read_rows(directory / 'similarity/unique_peptide_distances.jsonl'):
        for name, result in record['references'].items():
            witness = result['nearest_reference']
            if witness not in sets[name] or sum(a != b for a, b in zip(record['peptide'], witness)) != result['distance']:
                raise ValueError('Invalid exact Hamming witness')
            witness_count += 1
    candidates = read_rows(directory / 'similarity/candidate_distances_and_exclusions.jsonl')
    if len({r['source_id'] for r in candidates}) != len(candidates):
        raise ValueError('Original observation IDs lost or collapsed')
    union = set().union(*(sets[name] for name in task.REFERENCE_NAMES[:5]))
    population_counts = {}
    for threshold in (2, 3, 4):
        selected = read_rows(directory / f'cohorts/hamming_ge_{threshold}.jsonl')
        expected = task.select_threshold(candidates, threshold)
        if [r['source_id'] for r in selected] != [r['source_id'] for r in expected]:
            raise ValueError('Original row order/threshold rule differs')
        identities = read_rows(directory / f'cohorts/hamming_ge_{threshold}_identities.jsonl')
        outcomes = read_rows(directory / f'cohorts/hamming_ge_{threshold}_outcomes.jsonl')
        if identities != [{k: v for k, v in row.items() if k not in ('label', 'raw_response')} for row in selected]:
            raise ValueError('Identity-only future input differs')
        if outcomes != [{'source_id': row['source_id'], 'label': row['label'], 'raw_response': row['raw_response']} for row in selected]:
            raise ValueError('Original outcome association differs')
        if any(row['peptide'] in sets['prior_Mendeley_published'] for row in selected):
            raise ValueError('Prior benchmark exact peptide exposure retained')
        if any(row['peptide'] in union for row in selected):
            raise ValueError('Exact fitting/selection overlap retained')
        for unit in ('patient', 'study'):
            if [row[unit+'_peptide_component'] for row in selected] != task.components(selected, unit):
                raise ValueError('Frozen dependence components differ')
        recorded = frozen['thresholds'][str(threshold)]['population']
        if (len(selected), sum(r['label'] == 1 for r in selected), sum(r['label'] == 0 for r in selected)) != (
                recorded['N'], recorded['positive'], recorded['negative']):
            raise ValueError('Class census differs')
        population_counts[str(threshold)] = recorded['N']
    tests = read('focused_tests.json')
    if tests['status'] != 'passed' or tests['scientific_hashes'] != task.science_hashes(paths):
        raise ValueError('Focused tests missing or changed')
    config = json.loads((paths.repository_root / 'configs/bigmhc_independent_task2_25R.json').read_text())
    receipt, _ = models.authenticate_models(paths, amendment_sha256=config['protocol_sha256'])
    if any(frozen[k] for k in ('torch_imported', 'models_loaded', 'A_S_P_inference_executed',
                               'model_performance_computed', 'training_executed', 'prior_prediction_or_metric_files_opened')):
        raise ValueError('Out-of-scope scientific operation recorded')
    return {'status': 'passed', 'authenticated_frozen_outputs': len(frozen['immutable_artifact_hashes']),
            'frozen_reference_sets': len(sets), 'valid_nearest_reference_witnesses': witness_count,
            'candidate_observations': len(candidates), 'threshold_counts': population_counts,
            'original_row_order_and_outcomes_verified': True, 'dependence_components_verified': True,
            'model_file_maps_preserved': {a: r['file_map_sha256'] for a, r in receipt['models'].items()},
            'model_inference_or_performance_executed': False, 'prior_predictions_or_metrics_opened': False,
            'verified_utc': datetime.now(timezone.utc).isoformat()}


if __name__ == '__main__':
    result = verify()
    paths = resolve_paths()
    task.write_json(paths.project_runs_dir / task.RUN_ID / 'reports/completion_verification.json', result)
    print(json.dumps(result, indent=2))
