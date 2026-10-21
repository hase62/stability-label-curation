"""Once-only Task 2.30B external Teacher association; no model fitting.

Reuse only pure rank/serialization/dependence helpers from Task 2.29C.
No SHERPA observations or predictions are accessed. Imports do not write files.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from typing import Sequence

from .paths import StoragePaths, resolve_paths
from .monoallelic_replicate_rescue import sha256
from .replicate_stability_association import (
    bootstrap_availability, dependence_components, distribution_summary,
    doubled_ranks, permutation_control, rank_stratum, read_rows, spearman,
    write_json, write_rows,
)

CONFIG = 'configs/external_replicate_association_task2_30b.json'
RUN = 'task-2_30b-external-replicate-association'
IMPLEMENTATION = [CONFIG, 'src/stability_label_curation/external_replicate_association.py',
                  'src/stability_label_curation/replicate_stability_association.py',
                  'src/stability_label_curation/paths.py',
                  'src/stability_label_curation/monoallelic_replicate_rescue.py',
                  'tests/test_external_replicate_association.py',
                  'docs/EXTERNAL_REPLICATE_TASK2_30B_EXECUTION_SPEC.md',
                  'docs/EXTERNAL_REPLICATE_ASSOCIATION_TASK2_30B_PROTOCOL.md']


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence(start: float) -> dict:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {'completed_utc': now(), 'elapsed_seconds': time.monotonic()-start,
            'process_user_seconds': usage.ru_utime, 'process_system_seconds': usage.ru_stime,
            'peak_RSS_KiB': usage.ru_maxrss, 'python': sys.version,
            'platform': platform.platform(), 'execution_device': 'CPU', 'GPU_used': False}


def config_for(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    if (config['run_id'] != RUN or config['primary_n'] != 496 or config['sensitivity_n'] != 483
            or config['hla'] != 'HLA-A*02:01' or config['permutation_draws'] != 10000
            or config['permutation_seed'] != 228230 or config['training_authorized']
            or config['additional_covariates']):
        raise ValueError('Frozen scientific configuration differs')
    return config


def assert_matches(path: Path, expected: str) -> None:
    if sha256(path) != expected:
        raise ValueError('Authenticated input changed: '+str(path))


def validate_row(row: dict, ordered_runs: list[str]) -> None:
    from .stability_teacher import encode_ninemer
    encode_ninemer(row['peptide'])
    if row['hla'] != 'HLA-A*02:01' or row['raw_files'] != ordered_runs:
        raise ValueError('Peptide/HLA/run identity mismatch')
    flags = row['direct_detection']
    if len(flags) != 4 or any(v not in (0, 1) for v in flags) or not any(flags[:2]):
        raise ValueError('Not an index-clone direct-identification observation')
    if (row['biological_followup_direct_detection'] != int(any(flags[2:]))
            or row['followup_nested_technical_count'] != sum(flags[2:])
            or row['biological_clone_detection'] != [1, int(any(flags[2:]))]):
        raise ValueError('Nested technical consolidation differs')
    if [bool(ids) for ids in row['source_observation_ids_by_run']] != [bool(v) for v in flags]:
        raise ValueError('Direct source-evidence identity mismatch')
    available = [v for v in row['per_run_summed_direct_MS1_feature_intensity'][:2] if v is not None]
    if any(not math.isfinite(v) or v <= 0 for v in available):
        raise ValueError('Baseline intensity must be positive finite or missing')
    expected = math.fsum(available)/len(available) if available else None
    if (row['index_intensity_available_technical_measurements'] != len(available)
            or row['index_precursor_intensity'] != expected):
        raise ValueError('Baseline covariate is not the frozen index-only mean')


def align_predictions(rows: list[dict], predictions: list[dict]) -> None:
    if len(rows) != len(predictions) or len({r['source_identity'] for r in rows}) != len(rows):
        raise ValueError('Duplicate or missing prediction identities')
    for row, prediction in zip(rows, predictions):
        if any(row[key] != prediction[key] for key in ('source_identity', 'peptide', 'hla')):
            raise ValueError('Ordered peptide/HLA/source prediction alignment failed')
        if (prediction['model_status'] != 'ok' or prediction['resolved_hla'] != row['hla']
                or not all(math.isfinite(prediction[k]) and prediction[k] >= 0
                           for k in ('predicted_log1p_hours', 'predicted_half_life_hours'))
                or not math.isclose(math.expm1(prediction['predicted_log1p_hours']),
                                    prediction['predicted_half_life_hours'], rel_tol=1e-14, abs_tol=1e-14)):
            raise ValueError('Original Teacher output validity failed')


def ols(columns: list[list[float]], y: Sequence[float], names: list[str]) -> dict:
    """Small-design OLS by double-reorthogonalized MGS, no row-based inference."""
    if not columns or len(names) != len(columns) or any(len(c) != len(y) for c in columns):
        raise ValueError('Regression columns are unaligned')
    if not all(math.isfinite(v) for c in columns+[list(y)] for v in c):
        raise ValueError('Regression requires finite inputs')
    undefined = {'status': 'undefined', 'reason': 'rank-deficient design', 'coefficients': None,
                 'confidence_interval_95': None, 'p_value': None, 'design_columns': names}
    if len(y) < len(columns):
        return undefined
    p = len(columns)
    upper = [[0.0]*p for _ in range(p)]
    orthogonal: list[list[float]] = []
    for j, col in enumerate(columns):
        v = list(col)
        original_norm = math.sqrt(math.fsum(a*a for a in col))
        for _ in range(2):
            for i, q in enumerate(orthogonal):
                projection = math.fsum(a*b for a, b in zip(q, v))
                upper[i][j] += projection
                v = [a-projection*b for a, b in zip(v, q)]
        norm = math.sqrt(math.fsum(a*a for a in v))
        if norm <= 1e-12*max(original_norm, 1.0):
            return undefined
        upper[j][j] = norm
        orthogonal.append([a/norm for a in v])
    transformed = [math.fsum(a*b for a, b in zip(q, y)) for q in orthogonal]
    beta = [0.0]*p
    for i in reversed(range(p)):
        beta[i] = (transformed[i]-math.fsum(upper[i][j]*beta[j] for j in range(i+1, p)))/upper[i][i]
    if not all(math.isfinite(b) for b in beta):
        raise ValueError('Nonfinite regression solution')
    residual = [a-math.fsum(beta[j]*columns[j][i] for j in range(p)) for i, a in enumerate(y)]
    # Independent normal-equation check, diagnostics only (no inferential SE).
    errors = [abs(math.fsum(a*b for a, b in zip(c, residual))) for c in columns]
    return {'status': 'descriptive_point_estimate', 'coefficients': dict(zip(names, beta)),
            'design_columns': names, 'design_rank': p, 'normal_equation_max_absolute_error': max(errors),
            'confidence_interval_95': None, 'p_value': None,
            'uncertainty_reason': 'One independent clone-pair component; row-independent inference prohibited.'}


def regression_pair(rows: list[dict], scores: list[float]) -> dict:
    if not rows or len(rows) != len(scores):
        raise ValueError('Empty or unaligned regression population')
    n = len(rows)
    rank = [(r/2-.5)/n for r in doubled_ranks(scores)]
    y = [r['biological_followup_direct_detection'] for r in rows]
    intensity = [r['index_precursor_intensity'] for r in rows]
    available = [math.log2(v) for v in intensity if v is not None]
    missing = [float(v is None) for v in intensity]
    unadjusted = ols([[1.0]*n, rank], y, ['intercept', 'stability_percentile'])
    if not available:
        return {'n': n, 'unadjusted': unadjusted,
                'adjusted': {'status': 'undefined', 'reason': 'No baseline intensity', 'coefficients': None},
                'missing_n': n}
    center = math.fsum(available)/len(available)
    covariate = [math.log2(v)-center if v is not None else 0.0 for v in intensity]
    columns, names = [[1.0]*n, rank, covariate], ['intercept', 'stability_percentile', 'centered_log2_index_intensity']
    if len(set(missing)) > 1:
        columns.append(missing)
        names.append('missing_index_intensity')
    return {'n': n, 'positive_n': sum(y), 'negative_n': n-sum(y), 'missing_n': int(sum(missing)),
            'rank_scale': '(within-this-population average rank - 0.5)/N',
            'log2_intensity_center': center, 'unadjusted': unadjusted,
            'adjusted': ols(columns, y, names),
            'stability_effect_scale': 'Descriptive detection probability difference per full percentile-unit increase.'}


def prepare(paths: StoragePaths) -> dict:
    start = time.monotonic()
    config = config_for(paths)
    directory = paths.project_runs_dir/RUN
    if directory.exists():
        raise ValueError('Run already exists; refusing repeated preparation or overwrite')
    parent = paths.project_runs_dir/config['curation_run_id']
    freeze_path = parent/'reports/dataset_freeze.json'
    assert_matches(freeze_path, config['curation_freeze_sha256'])
    parent_freeze = json.loads(freeze_path.read_text())
    verified = 0
    for field, root in [('source_sha256', paths.project_data_dir/config['curation_source']),
                        ('derived_artifact_sha256', parent), ('implementation_sha256', paths.repository_root)]:
        for name, digest in parent_freeze[field].items():
            assert_matches(root/name, digest)
            verified += 1
    protocol = 'docs/EXTERNAL_REPLICATE_ASSOCIATION_TASK2_30B_PROTOCOL.md'
    assert_matches(paths.repository_root/protocol, parent_freeze['future_protocol_sha256'])
    rows = read_rows(parent/'manifests/future_primary_index_cohort.jsonl')
    union = read_rows(parent/'matrices/unmodified_9mer_four_run_matrix.jsonl')
    by_id = {r['source_identity']: r for r in union}
    sensitivity_ids = json.loads((parent/'manifests/future_sensitivity_source_identities.json').read_text())
    if len(rows) != 496 or len({r['peptide'] for r in rows}) != 496 or any(by_id[r['source_identity']] != r for r in rows):
        raise ValueError('Frozen primary identities differ')
    for row in rows:
        validate_row(row, config['ordered_runs'])
    sensitivity_set = set(sensitivity_ids)
    overlaps = read_rows(parent/'manifests/Teacher_sequence_overlap.jsonl')
    index_overlaps = [r for r in overlaps if r['primary_index_eligible']]
    expected_ids = [r['source_identity'] for r in rows if next(o for o in index_overlaps if o['source_identity'] == r['source_identity'])['future_fitting_exclusion_sensitivity_eligible']]
    if sensitivity_ids != expected_ids or len(sensitivity_ids) != 483:
        raise ValueError('Frozen fitting-neighbor sensitivity changed')
    populations = {'primary': [r['source_identity'] for r in rows], 'sensitivity': sensitivity_ids,
                   'complete_case': [r['source_identity'] for r in rows if r['index_precursor_intensity'] is not None],
                   'sensitivity_complete_case': [r['source_identity'] for r in rows if r['source_identity'] in sensitivity_set and r['index_precursor_intensity'] is not None]}
    if [len(v) for v in populations.values()] != [496, 483, 473, 460]:
        raise ValueError('Prespecified population counts differ')
    if Counter(r['biological_followup_direct_detection'] for r in rows) != {0: 130, 1: 366}:
        raise ValueError('Frozen outcome alignment differs')
    bundle = paths.project_data_dir/config['bundle_relative_path']
    handoff = json.loads(subprocess.run([sys.executable, '-I', '-B', str(bundle/'verify_handoff.py')], check=True, capture_output=True, text=True).stdout)
    if handoff['status'] != 'PASS' or handoff['model_sha256'] != config['model_sha256']:
        raise ValueError('Original Teacher verification failed')
    original_code_hashes = {}
    for line in (bundle/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name.startswith('src/stability_label_curation/'):
            assert_matches(paths.repository_root/name, digest)
            original_code_hashes[name] = digest
    from .stability_teacher import load_model
    model = load_model(bundle/'checkpoints/teacher_model.json')
    if model.document['alleles'][config['hla']]['status'] != 'trained':
        raise ValueError('Exact A*02:01 support absent')
    committed = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=paths.repository_root, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=paths.repository_root, text=True):
        raise ValueError('Commit pre-analysis implementation and specification before preparing')
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory/'manifests/scientific_configuration.json', config)
    write_rows(directory/'manifests/primary.jsonl', rows)
    write_json(directory/'manifests/populations.json', populations)
    write_rows(directory/'manifests/Teacher_primary_overlap.jsonl', index_overlaps)
    write_json(directory/'reports/Teacher_overlap_summary.json', json.loads((parent/'reports/Teacher_overlap_summary.json').read_text())['future_primary_index'])
    write_json(directory/'reports/Teacher_handoff_verification.json', handoff)
    write_json(directory/'reports/preflight.json', {
        'status': 'PASS', 'curation_inventory_files_verified': verified, 'ordered_input_n': len(rows),
        'primary_unique_peptides': len({r['peptide'] for r in rows}), 'hla': config['hla'],
        'population_sizes': {k: len(v) for k, v in populations.items()}, 'identical_source_rows_and_HLA': True,
        'index_only_intensity_verified': True, 'original_Teacher_code_sha256': original_code_hashes,
        'study_inference_calls': 0, 'study_associations_computed': False,
        'outcome_counts': dict(Counter(r['biological_followup_direct_detection'] for r in rows)),
        'nested_followup_counts': dict(Counter(r['followup_nested_technical_count'] for r in rows)),
        'execution': evidence(start)})
    manifest_names = ['manifests/scientific_configuration.json', 'manifests/primary.jsonl', 'manifests/populations.json', 'manifests/Teacher_primary_overlap.jsonl']
    freeze = {'frozen_utc': now(), 'implementation_commit': committed,
              'model_sha256': config['model_sha256'], 'parent_freeze_sha256': sha256(freeze_path),
              'implementation_sha256': {**original_code_hashes,
                  **{name: sha256(paths.repository_root/name) for name in IMPLEMENTATION}},
              'manifest_sha256': {name: sha256(directory/name) for name in manifest_names},
              'study_predictions_generated': False, 'study_association_results_inspected': False}
    write_json(directory/'manifests/pre_prediction_freeze.json', freeze)
    return freeze


def authenticated_run(paths: StoragePaths) -> tuple[Path, dict, list[dict]]:
    directory = paths.project_runs_dir/RUN
    freeze = json.loads((directory/'manifests/pre_prediction_freeze.json').read_text())
    for field, root in [('implementation_sha256', paths.repository_root), ('manifest_sha256', directory)]:
        for name, digest in freeze[field].items():
            assert_matches(root/name, digest)
    config = config_for(paths)
    assert_matches(paths.project_data_dir/config['bundle_relative_path']/'checkpoints/teacher_model.json', freeze['model_sha256'])
    return directory, config, read_rows(directory/'manifests/primary.jsonl')


def infer(paths: StoragePaths) -> dict:
    start = time.monotonic()
    directory, config, rows = authenticated_run(paths)
    write_json(directory/'logs/inference_started.json', {'started_utc': now(), 'expected_study_calls': 496})
    from .stability_teacher import load_model
    model = load_model(paths.project_data_dir/config['bundle_relative_path']/'checkpoints/teacher_model.json')
    predictions = []
    for index, row in enumerate(rows, 1):
        prediction = model.predict_stability(row['peptide'], row['hla'])
        predictions.append({**{k: row[k] for k in ('source_identity', 'peptide', 'hla')},
                            'frozen_row_1based': index, **prediction})
    align_predictions(rows, predictions)
    ranks = doubled_ranks([p['predicted_log1p_hours'] for p in predictions])
    for prediction, rank in zip(predictions, ranks):
        prediction['within_HLA_average_rank'] = rank/2
        prediction['within_HLA_percentile_rank'] = (rank/2-.5)/len(rows)
        prediction['prediction_valid'] = True
    write_rows(directory/'predictions/Teacher_primary.jsonl', predictions)
    report = {'status': 'PASS', 'study_inference_calls': len(predictions), 'finite_aligned_predictions': len(predictions),
              'clipped_zero_predictions': sum(p['log_prediction_clipped_to_zero'] for p in predictions),
              'distinct_deployed_values': len({p['predicted_log1p_hours'] for p in predictions}),
              'predictions_sha256': sha256(directory/'predictions/Teacher_primary.jsonl'),
              'source_manifest_sha256': sha256(directory/'manifests/primary.jsonl'),
              'half_life_hours': distribution_summary([p['predicted_half_life_hours'] for p in predictions]),
              'log1p_hours': distribution_summary([p['predicted_log1p_hours'] for p in predictions]),
              'execution': evidence(start)}
    write_json(directory/'reports/inference.json', report)
    return report


def analyze(paths: StoragePaths) -> dict:
    start = time.monotonic()
    directory, config, rows = authenticated_run(paths)
    receipt = json.loads((directory/'reports/inference.json').read_text())
    assert_matches(directory/'predictions/Teacher_primary.jsonl', receipt['predictions_sha256'])
    predictions = read_rows(directory/'predictions/Teacher_primary.jsonl')
    align_predictions(rows, predictions)
    write_json(directory/'logs/analysis_started.json', {'started_utc': now(), 'inference_completed_utc': receipt['execution']['completed_utc']})
    joined = [{**r, **p, 'group_id': 'MSV000099922:JY:DeltaBC:W6/32',
               'biological_samples': ['DeltaBC1', 'DeltaBC2']} for r, p in zip(rows, predictions)]
    populations = json.loads((directory/'manifests/populations.json').read_text())
    result = {'primary_method': 'Average-tie Spearman of clipped log1p stability versus binary clone detection',
              'source': 'MSV000099922', 'no_training_or_tuning': True, 'cohorts': {},
              'complete_case_companions': {}, 'all_predictions_fixed_before_association': True}
    for name in ('primary', 'sensitivity'):
        ids = set(populations[name])
        subset = [r for r in joined if r['source_identity'] in ids]
        scores = [r['predicted_log1p_hours'] for r in subset]
        y = [r['biological_followup_direct_detection'] for r in subset]
        components = dependence_components(subset)
        uncertainty = bootstrap_availability(components, config)
        negative_control, draws = permutation_control(scores, y, config['permutation_draws'], config['permutation_seed'])
        ranks = doubled_ranks(scores)
        strata = []
        for quartile in range(1, 5):
            items = [r for r, rank in zip(subset, ranks) if rank_stratum(rank/2, len(subset), config['quartile_upper_bounds']) == quartile]
            successes = sum(r['biological_followup_direct_detection'] for r in items)
            strata.append({'quartile': quartile, 'n': len(items), 'detected_n': successes,
                           'detection_rate': successes/len(items) if items else None})
        counts = {str(v): y.count(v) for v in (0, 1)}
        report = {'n': len(subset), 'outcome_counts': counts, 'detected_fraction': sum(y)/len(y),
                  'spearman_rho': spearman(scores, y), 'uncertainty': uncertainty,
                  'negative_control': negative_control, 'sparse_flag': len(y) < 30 or min(counts.values()) < 10,
                  'intensity_regression': regression_pair(subset, scores), 'rank_quartiles': strata,
                  'half_life_hours_by_outcome': {str(v): distribution_summary([r['predicted_half_life_hours'] for r in subset if r['biological_followup_direct_detection'] == v]) for v in (0, 1)},
                  'nested_followup_counts': dict(Counter(r['followup_nested_technical_count'] for r in subset)),
                  'followup_patterns': dict(Counter(''.join(map(str, r['direct_detection'][2:])) for r in subset)),
                  'index_intensity_by_outcome': {str(v): distribution_summary([r['index_precursor_intensity'] for r in subset if r['biological_followup_direct_detection'] == v and r['index_precursor_intensity'] is not None]) for v in (0, 1)},
                  'intensity_missing_outcome_counts': dict(Counter(r['biological_followup_direct_detection'] for r in subset if r['index_precursor_intensity'] is None)),
                  'intensity_available_outcome_counts': dict(Counter(r['biological_followup_direct_detection'] for r in subset if r['index_precursor_intensity'] is not None)),
                  'index_intensity_available_measurement_counts': dict(Counter(r['index_intensity_available_technical_measurements'] for r in subset))}
        result['cohorts'][name] = report
        companion_name = 'complete_case' if name == 'primary' else 'sensitivity_complete_case'
        companion_ids = set(populations[companion_name])
        complete = [r for r in subset if r['source_identity'] in companion_ids]
        result['complete_case_companions'][companion_name] = regression_pair(complete, [r['predicted_log1p_hours'] for r in complete])
        write_json(directory/f'resampling/{name}_components.json', components)
        write_rows(directory/f'resampling/{name}_score_permutations.jsonl', ({'draw_1based': i, 'rho': value} for i, value in enumerate(draws, 1)))
    result['execution'] = evidence(start)
    write_rows(directory/'observations/predictions_and_detection.jsonl', joined)
    write_json(directory/'reports/association_results.json', result)
    return result


def figures(paths: StoragePaths) -> dict:
    """Render saved new-study summaries only; no scoring/statistical tests."""
    start = time.monotonic()
    directory, _, _ = authenticated_run(paths)
    write_json(directory/'logs/figures_started.json', {'started_utc': now()})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    results = json.loads((directory/'reports/association_results.json').read_text())
    report = results['cohorts']['primary']
    rows = read_rows(directory/'observations/predictions_and_detection.jsonl')
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    data = [[r['predicted_half_life_hours'] for r in rows if r['biological_followup_direct_detection'] == v] for v in (0, 1)]
    axes[0].boxplot(data, tick_labels=['Not detected\nN=130', 'Detected\nN=366'], showfliers=False)
    axes[0].set_ylabel('Teacher-predicted half-life (hours)')
    axes[0].set_title('Follow-up biological clone')
    quartiles = report['rank_quartiles']
    axes[1].bar([q['quartile'] for q in quartiles], [q['detection_rate'] for q in quartiles], color='#297d8e')
    for q in quartiles:
        axes[1].text(q['quartile'], q['detection_rate']+.015, f"{q['detected_n']}/{q['n']}", ha='center', fontsize=9)
    axes[1].set_ylim(0, 1)
    axes[1].set_xticks([1, 2, 3, 4])
    axes[1].set_xlabel('Fixed stability-rank quartile (low to high)')
    axes[1].set_ylabel('Follow-up clone detection fraction')
    axes[1].set_title('Index-conditioned descriptive strata')
    descriptions = [('All 496: rank only', report['intensity_regression']['unadjusted']),
                    ('All 496: intensity adjusted', report['intensity_regression']['adjusted']),
                    ('Complete 473: rank only', results['complete_case_companions']['complete_case']['unadjusted']),
                    ('Complete 473: adjusted', results['complete_case_companions']['complete_case']['adjusted'])]
    beta = [r['coefficients']['stability_percentile'] for _, r in descriptions]
    axes[2].plot(beta, range(len(beta)), 'o', color='#90503b')
    axes[2].axvline(0, color='gray', linewidth=.7)
    axes[2].set_yticks(range(len(beta)), [n for n, _ in descriptions], fontsize=8)
    axes[2].invert_yaxis()
    axes[2].set_xlabel('Descriptive probability slope per rank unit')
    axes[2].set_title('No biological confidence intervals')
    fig.suptitle(f"External JY HLA-A*02:01: 496 index peptides, one clone pair; Spearman rho={report['spearman_rho']:.4f}", fontsize=11)
    fig.tight_layout()
    figure_dir = directory/'figures'
    figure_dir.mkdir(exist_ok=True)
    for suffix in ('png', 'pdf'):
        target = figure_dir/f'external_association.{suffix}'
        if target.exists():
            raise ValueError('Refusing figure overwrite')
        fig.savefig(target, dpi=180)
    plt.close(fig)
    receipt = {'matplotlib_version': matplotlib.__version__, 'execution': evidence(start),
               'figures_sha256': {str(p.relative_to(directory)): sha256(p) for p in figure_dir.glob('external_association.*')}}
    write_json(directory/'reports/figures.json', receipt)
    return receipt


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ('prepare', 'infer', 'analyze', 'figures'):
        raise SystemExit('Usage: python -m stability_label_curation.external_replicate_association prepare|infer|analyze|figures')
    result = globals()[sys.argv[1]](resolve_paths())
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
