"""Verify saved Task 2.25R evidence without inference or metric recomputation."""
from datetime import datetime, timezone
import json
import math
import subprocess

from stability_label_curation import bigmhc_independent_evaluation as evaluation
from stability_label_curation import bigmhc_independent_preflight as gates
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths


def verify() -> dict:
    paths = resolve_paths()
    directory, config = evaluation.context(paths)
    root = directory.parent
    read = lambda name: json.loads((directory / 'reports' / name).read_text())
    output = read('output_manifest.json')
    for name, expected in output.items():
        if runner.raw.sha256_file(directory / name) != expected:
            raise ValueError('Changed evaluation artifact: ' + name)
    prior = json.loads((root / 'reports/finalization_manifest.json').read_text())
    for name, expected in prior['run_artifacts'].items():
        if runner.raw.sha256_file(root / name) != expected:
            raise ValueError('Changed historical blocker artifact: ' + name)
    preserved = paths.repository_root / 'docs/BIGMHC_INDEPENDENT_NEOEPITOPE_TASK2_25_BLOCKED.md'
    if runner.raw.sha256_file(preserved) != prior['repository_files']['docs/BIGMHC_INDEPENDENT_NEOEPITOPE_TASK2_25.md']:
        raise ValueError('Original blocker report was not preserved exactly')
    secondary, frozen = evaluation.frozen_cohorts(paths, directory)
    primary = evaluation.read_rows(directory / 'cohorts/primary.jsonl')
    if [r for r in secondary if r['primary']] != primary:
        raise ValueError('Primary is not the fixed secondary subset')
    if any(r['EL_train_peptide'] or r['IM_train_peptide'] for r in primary):
        raise ValueError('Primary sequence-disjointness flag failed')
    if any(r['IM_train_peptide'] for r in secondary):
        raise ValueError('Secondary IM disjointness flag failed')
    if [r['row_index'] for r in secondary] != sorted(r['row_index'] for r in secondary):
        raise ValueError('Original source ordering was not preserved')
    for arm in evaluation.ARMS:
        predicted = evaluation.read_rows(directory / f'predictions/{arm}.jsonl')
        if [{k: v for k, v in row.items() if k != 'probability'} for row in predicted] != secondary:
            raise ValueError('Prediction identities differ across arms')
        if any(not math.isfinite(row['probability']) or not 0 <= row['probability'] <= 1 for row in predicted):
            raise ValueError('Invalid saved probability')
    models, _ = gates.authenticate_models(paths, amendment_sha256=config['protocol_sha256'])
    if runner.raw.sha256_file(paths.project_data_dir / 'bigmhc_v4/datasets.zip') != gates.ARCHIVE_SHA256:
        raise ValueError('Published source archive changed')
    commit_time = subprocess.check_output(['git', 'show', '-s', '--format=%cI', config['amendment_commit']],
                                          cwd=paths.repository_root, text=True).strip()
    times = [commit_time, read('eligibility_started.json')['started_utc'], frozen['frozen_utc'],
             read('inference_started.json')['started_utc'], read('predictions_frozen.json')['frozen_utc'],
             read('evaluation_started.json')['started_utc'], read('completion.json')['completed_utc']]
    parsed = [datetime.fromisoformat(t) for t in times]
    if parsed != sorted(parsed):
        raise ValueError('Amendment/identity/prediction/outcome order failed')
    complete = read('completion.json')
    if complete['status'] != 'completed_one_time_frozen_evaluation' or complete['outcome_based_eligibility_changes']:
        raise ValueError('Incomplete or revised evaluation')
    if read('class_distributions.json') != {name: value['population'] for name, value in complete['cohorts'].items()}:
        raise ValueError('Class distribution copy differs')
    if read('contrasts.json') != {name: value['contrasts'] for name, value in complete['cohorts'].items()}:
        raise ValueError('Contrast copy differs')
    if read('focused_tests.json')['status'] != 'passed':
        raise ValueError('Focused tests failed')
    return {'status': 'passed', 'authenticated_evaluation_outputs': len(output),
            'historical_blocker_artifacts_preserved': len(prior['run_artifacts']),
            'historical_blocker_document_preserved': True,
            'models': {a: value['file_map_sha256'] for a, value in models['models'].items()},
            'amendment_before_eligibility_predictions_and_outcomes': True,
            'frozen_primary_subset_and_identical_ordered_arm_ids': True,
            'primary_EL_IM_sequence_disjointness_flags': True,
            'secondary_IM_sequence_disjointness_flags': True,
            'primary_N': len(primary), 'secondary_N': len(secondary),
            'finite_saved_probabilities': True, 'model_inference_executed': False,
            'metrics_or_bootstrap_recomputed': False,
            'verified_utc': datetime.now(timezone.utc).isoformat()}


if __name__ == '__main__':
    result = verify()
    directory, _ = evaluation.context(resolve_paths())
    evaluation.write_json(directory / 'reports/completion_verification.json', result)
    print(json.dumps(result, indent=2))
