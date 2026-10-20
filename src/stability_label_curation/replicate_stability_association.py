"""Frozen Task 2.29C Teacher inference and within-HLA detection association.

No fitting, calibration, dataset reconstruction or historical benchmark analysis.
Imports and path resolution have no filesystem side effects.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence

from .paths import StoragePaths, resolve_paths
from .monoallelic_replicate_rescue import SOURCE as CURATION_SOURCE, canonical_hla, sha256

CONFIG = 'configs/replicate_stability_association_task2_29c.json'
RUN = 'task-2_29c-stability-replicate-association'


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n')


def write_rows(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(canonical_json(row)+'\n')


def read_rows(path: Path) -> list[dict]:
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def load_config(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    if (config['run_id'] != RUN or config['primary_n'] != 671 or config['hla'] != 'HLA-A*02:01'
            or config['permutation_draws'] != 10000 or config['permutation_seed'] != 228230
            or config['component_bootstrap_seed'] != 228229 or config['additional_conditions']):
        raise ValueError('Frozen scientific configuration differs')
    return config


def doubled_ranks(values: Sequence[float]) -> list[int]:
    """Twice the average 1-based rank; exact integers preserve ordinal ties."""
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Ranks require finite values')
    order = sorted(range(len(values)), key=values.__getitem__)
    result, start = [0]*len(values), 0
    while start < len(order):
        end = start+1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for index in order[start:end]:
            result[index] = start+end+1
        start = end
    return result


def rank_terms(x: Sequence[float], y: Sequence[float]) -> tuple[list[int], list[int], float]:
    if len(x) != len(y):
        raise ValueError('Unaligned association inputs')
    center = len(x)+1
    a = [r-center for r in doubled_ranks(x)]
    b = [r-center for r in doubled_ranks(y)]
    denominator = math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
    return a, b, denominator


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    a, b, denominator = rank_terms(x, y)
    return sum(u*v for u, v in zip(a, b))/denominator if denominator else None


def permutation_control(x: Sequence[float], y: Sequence[float], draws: int, seed: int) -> tuple[dict, list[float]]:
    a, b, denominator = rank_terms(x, y)
    if not denominator:
        return {'p_one_sided_descriptive': None, 'usable_draws': 0, 'undefined_draws': draws,
                'reason': 'empty, singleton or constant predictor/outcome'}, []
    observed = sum(u*v for u, v in zip(a, b))
    permuted = list(a)
    rng, exceedances, distribution = random.Random(seed), 0, []
    for _ in range(draws):
        rng.shuffle(permuted)
        value = sum(u*v for u, v in zip(permuted, b))
        exceedances += value >= observed
        distribution.append(value/denominator)
    return {'p_one_sided_descriptive': (1+exceedances)/(1+draws),
            'usable_draws': draws, 'undefined_draws': 0, 'greater_or_equal_draws': exceedances,
            'draws': draws, 'seed': seed, 'direction': 'greater_or_equal',
            'integer_doubled_rank_comparisons': True,
            'interpretation': 'Exchangeability-dependent negative control; not biological-population significance.'}, distribution


def quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered)-1)*q
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)


def distribution_summary(values: Sequence[float]) -> dict:
    return {'n': len(values), 'minimum': min(values) if values else None,
            'q25': quantile(values, .25), 'median': quantile(values, .5),
            'q75': quantile(values, .75), 'maximum': max(values) if values else None,
            'mean': math.fsum(values)/len(values) if values else None}


def nearest_hamming(peptide: str, references: Sequence[str]) -> tuple[int | None, str | None]:
    best, witness = len(peptide)+1, None
    for reference in references:
        if len(reference) != len(peptide):
            raise ValueError('Hamming reference length mismatch')
        distance = 0
        for a, b in zip(peptide, reference):
            distance += a != b
            if distance >= best:
                break
        if distance < best:
            best, witness = distance, reference
            if not best:
                break
    return (best, witness) if witness is not None else (None, None)


def dependence_components(rows: list[dict]) -> list[dict]:
    """Identity-only union-find over shared sample, group or exact peptide."""
    parents = list(range(len(rows)))
    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        tokens = [('group', row['group_id']), ('peptide', row['peptide'])]
        tokens += [('sample', s) for s in row['biological_samples']]
        for token in tokens:
            if token in seen:
                parents[find(i)] = find(seen[token])
            else:
                seen[token] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row['source_identity'])
    return [{'component_id': f'component_{n+1}', 'source_identities': identities,
             'observations': len(identities)} for n, identities in enumerate(groups.values())]


def bootstrap_availability(components: list[dict], config: dict) -> dict:
    if len(components) >= config['component_bootstrap_minimum_units']:
        raise ValueError('Unexpected multi-component cohort: do not silently redesign frozen analysis')
    return {'confidence_interval_95': None, 'independent_units': len(components),
            'component_sizes': [c['observations'] for c in components],
            'draws_executed': 0, 'draws_prespecified_if_estimable': config['component_bootstrap_draws_if_estimable'],
            'seed': config['component_bootstrap_seed'], 'undefined_reason': 'Fewer than two independent biological components.',
            'peptide_independent_bootstrap_substituted': False}


def intensity_adjustment(rows: Sequence[dict]) -> dict:
    if any(r['index_precursor_intensity'] is not None for r in rows):
        raise ValueError('Unexpected new precursor quantitation requires a pre-analysis specification')
    return {'status': 'unavailable', 'n': len(rows), 'missing_precursor_intensity': len(rows),
            'coefficient': None, 'confidence_interval_95': None,
            'reason': 'No matched index precursor abundance. Fragment-ion intensity is not this covariate.',
            'regression_fitted': False, 'substitute_covariates_used': False}


def _identity(row: dict, row_number: int, cohort_hash: str) -> str:
    return hashlib.sha256(canonical_json({'cohort_sha256': cohort_hash,
        'original_manifest_row_1based': row_number, 'peptide': row['peptide'], 'hla': row['hla'],
        'group_id': row['group_id'], 'index_PSMs': row['source_psm_ids_by_run'][0]}).encode()).hexdigest()


def prepare(paths: StoragePaths) -> dict:
    """Authenticate and freeze inputs/overlap before any real Teacher predictions."""
    start = time.monotonic()
    config = load_config(paths)
    directory, bundle = paths.project_runs_dir/RUN, paths.project_data_dir/config['bundle_relative_path']
    if directory.exists():
        raise ValueError('Task run already exists; refusing overwrite or repeated preparation')
    parent = paths.project_runs_dir/config['curation_run_id']
    freeze_path = parent/'reports/dataset_freeze.json'
    if sha256(freeze_path) != config['curation_freeze_sha256']:
        raise ValueError('Frozen source receipt changed')
    freeze = json.loads(freeze_path.read_text())
    curation_files_verified = 0
    for key, root in [('source_hashes', paths.project_data_dir/CURATION_SOURCE),
                      ('derived_artifact_sha256', parent), ('implementation_sha256', paths.repository_root)]:
        for name, expected in freeze[key].items():
            if sha256(root/name) != expected:
                raise ValueError('Curation inventory changed: '+name)
            curation_files_verified += 1
    needed = ['manifests/future_primary_index_cohort.jsonl', 'manifests/primary_biological_union.jsonl',
              'manifests/replicate_groups.json', 'manifests/monoallelic_runs.jsonl']
    for name in needed:
        if sha256(parent/name) != freeze['derived_artifact_sha256'][name]:
            raise ValueError('Frozen cohort/run mapping changed: '+name)
    for name, pin in [('future_primary_index_cohort.jsonl', 'index_cohort_sha256'),
                      ('primary_biological_union.jsonl', 'union_cohort_sha256')]:
        if sha256(parent/'manifests'/name) != config[pin]:
            raise ValueError('Primary/union identity differs')
    verified = subprocess.run([sys.executable, '-I', '-B', str(bundle/'verify_handoff.py')],
                              check=True, capture_output=True, text=True)
    handoff = json.loads(verified.stdout)
    if handoff['status'] != 'PASS' or handoff['model_sha256'] != config['model_sha256']:
        raise ValueError('Original Teacher handoff did not pass')
    code_hashes = {}
    for line in (bundle/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name.startswith('src/stability_label_curation/'):
            if sha256(paths.repository_root/name) != digest:
                raise ValueError('Repository inference code differs from original bundle: '+name)
            code_hashes[name] = digest
    from . import stability_teacher as teacher
    model = teacher.load_model(bundle/'checkpoints/teacher_model.json')
    if sha256(bundle/'provenance/teacher/teacher_train_val_partition.json') != config['Teacher_partition_sha256']:
        raise ValueError('Teacher fitting partition changed')
    primary = read_rows(parent/'manifests/future_primary_index_cohort.jsonl')
    union = read_rows(parent/'manifests/primary_biological_union.jsonl')
    if len(primary) != config['primary_n'] or len(union) != config['union_n']:
        raise ValueError('Frozen sample counts differ')
    union_identities = {(r['peptide'], r['hla']): r for r in union}
    if len(union_identities) != len(union) or any(union_identities.get((r['peptide'], r['hla'])) != r for r in primary):
        raise ValueError('Index cohort is not the unchanged subset of the frozen union')
    groups = json.loads((parent/'manifests/replicate_groups.json').read_text())
    group = next(g for g in groups if g['primary_candidate'])
    mappings = {r['raw_file']: r for r in read_rows(parent/'manifests/monoallelic_runs.jsonl')}
    if [mappings[raw]['biological_sample'] for raw in config['ordered_runs']] != group['biological_samples']:
        raise ValueError('Frozen biological sample/run alignment differs')
    identities = {}
    for split, expected in [('train', 21625), ('validation', 5406)]:
        with (bundle/f'identities/{split}.csv').open() as stream:
            identities[split] = list(csv.DictReader(stream))
        if len(identities[split]) != expected:
            raise ValueError('Teacher identity counts differ')
    pair_sets = {split: {(r['peptide'], r['hla']) for r in records} for split, records in identities.items()}
    peptide_sets = {split: {r['peptide'] for r in records} for split, records in identities.items()}
    fitting_all = sorted(peptide_sets['train'])
    fitting_hla = sorted({r['peptide'] for r in identities['train'] if r['hla'] == config['hla']})
    prepared, overlap, seen = [], [], set()
    for number, row in enumerate(primary, 1):
        pair = (row['peptide'], row['hla'])
        if pair in seen or canonical_hla(row['hla']) != config['hla'] or row['raw_files'] != config['ordered_runs']:
            raise ValueError('Duplicate, HLA or ordered run mismatch')
        seen.add(pair)
        teacher.encode_ninemer(row['peptide'])  # Input validation only; no prediction.
        if model.document['alleles'][row['hla']]['status'] != 'trained':
            raise ValueError('Unsupported original Teacher input')
        states = row['direct_detection']
        if len(states) != 3 or states[0] != 1 or any(type(s) is not int or s not in (0, 1) for s in states):
            raise ValueError('Incorrect index or direct detection states')
        if any(bool(s) != bool(ids) for s, ids in zip(states, row['source_psm_ids_by_run'])):
            raise ValueError('Detection/source observation mismatch')
        repeat_count = states[1]+states[2]
        if row['repeat_detection_frequency'] != repeat_count/2:
            raise ValueError('Frozen follow-up endpoint mismatch')
        original_id = _identity(row, number, config['index_cohort_sha256'])
        d_hla, w_hla = nearest_hamming(row['peptide'], fitting_hla)
        d_all, w_all = nearest_hamming(row['peptide'], fitting_all)
        exposure = {'source_identity': original_id, 'peptide': row['peptide'], 'hla': row['hla'],
                    'training_exact_peptide_HLA': pair in pair_sets['train'],
                    'validation_exact_peptide_HLA': pair in pair_sets['validation'],
                    'training_exact_peptide_any_HLA': row['peptide'] in peptide_sets['train'],
                    'validation_exact_peptide_any_HLA': row['peptide'] in peptide_sets['validation'],
                    'A0201_training_minimum_Hamming': d_hla, 'A0201_training_witness': w_hla,
                    'any_HLA_training_minimum_Hamming': d_all, 'any_HLA_training_witness': w_all,
                    'exposure_excluded_sensitivity_eligible': d_all is not None and d_all >= 2}
        overlap.append(exposure)
        prepared.append({**row, 'source_identity': original_id, 'original_manifest_row_1based': number,
                         'biological_samples': group['biological_samples'],
                         'followup_1_direct': states[1], 'followup_2_direct': states[2],
                         'repeat_detection_count': repeat_count, 'repeat_detection_frequency': repeat_count/2,
                         'index_precursor_intensity': None, 'index_individual_q_value': None,
                         'Teacher_exposure': exposure, 'input_accepted': True})
    if Counter(r['repeat_detection_count'] for r in prepared) != {0: 99, 1: 207, 2: 365}:
        raise ValueError('Frozen outcome counts differ')
    components = dependence_components(prepared)
    bootstrap = bootstrap_availability(components, config)
    overlap_summary = {'n': len(overlap), 'normalization_or_identity_problems': 0,
                       'Teacher_training_rows': len(identities['train']), 'Teacher_validation_rows': len(identities['validation']),
                       'unique_all_HLA_fitting_peptides': len(fitting_all), 'unique_A0201_fitting_peptides': len(fitting_hla),
                       'exact_overlaps': {name: sum(r[name] for r in overlap) for name in (
                           'training_exact_peptide_HLA', 'validation_exact_peptide_HLA',
                           'training_exact_peptide_any_HLA', 'validation_exact_peptide_any_HLA')},
                       'distance_counts': {name: dict(Counter('>=3' if r[name] >= 3 else str(r[name]) for r in overlap))
                                           for name in ('A0201_training_minimum_Hamming', 'any_HLA_training_minimum_Hamming')},
                       'exposure_excluded_sensitivity_n': sum(r['exposure_excluded_sensitivity_eligible'] for r in overlap)}
    write_json(directory/'preflight/handoff_verification.json', handoff)
    write_json(directory/'preflight/Teacher_overlap_summary.json', overlap_summary)
    write_rows(directory/'preflight/Teacher_overlap.jsonl', overlap)
    write_rows(directory/'frozen/primary_cohort.jsonl', prepared)
    write_json(directory/'frozen/sensitivity_source_identities.json', [r['source_identity'] for r in prepared if r['Teacher_exposure']['exposure_excluded_sensitivity_eligible']])
    write_json(directory/'frozen/dependence_components.json', components)
    write_json(directory/'frozen/config.json', config)
    metadata = {'created_utc': datetime.now(timezone.utc).isoformat(), 'phase': 'pre_prediction',
                'implementation_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=paths.repository_root,
                                                       capture_output=True, text=True, check=True).stdout.strip(),
                'model_sha256': config['model_sha256'], 'inference_code_sha256': code_hashes,
                'cohort_sha256': config['index_cohort_sha256'], 'cohort_n': len(prepared),
                'curation_inventory_files_verified': curation_files_verified,
                'union_n': len(union), 'outcome_counts': dict(Counter(r['repeat_detection_count'] for r in prepared)),
                'all_inputs_accepted_without_prediction': True, 'bootstrap': bootstrap,
                'intensity_adjustment': intensity_adjustment(prepared),
                'original_A0201_kinetic_validation': json.loads((bundle/'provenance/teacher/teacher_validation_metrics.json').read_text())['results']['HLA-A*02:01'],
                'runtime_seconds': time.monotonic()-start,
                'input_hashes': {str(path.relative_to(paths.codex_root)): sha256(path) for path in (
                    bundle/'checkpoints/teacher_model.json', bundle/'identities/train.csv', bundle/'identities/validation.csv',
                    bundle/'provenance/teacher/teacher_train_val_partition.json', bundle/'provenance/handoff.json',
                    paths.repository_root/CONFIG, paths.repository_root/'docs/REPLICATE_STABILITY_TASK2_29C_EXECUTION_SPEC.md',
                    paths.repository_root/'docs/REPLICATE_STABILITY_ASSOCIATION_TASK2_29_PROTOCOL.md',
                    paths.repository_root/'docs/REPLICATE_STABILITY_ASSOCIATION_TASK2_29A_AMENDMENT.md',
                    paths.repository_root/'src/stability_label_curation/replicate_stability_association.py',
                    paths.repository_root/'tests/test_replicate_stability_association.py')},
                'immutable_artifact_hashes': {str(f.relative_to(directory)): sha256(f) for f in sorted(directory.rglob('*')) if f.is_file()},
                'SHERPA_predictions_generated': False, 'associations_computed': False,
                'runtime': {'python': sys.version, 'platform': platform.platform()}}
    write_json(directory/'preflight/analysis_freeze.json', metadata)
    return {'status': 'PASS', 'overlap': overlap_summary, 'bootstrap': bootstrap}


def _check_freeze(paths: StoragePaths) -> tuple[Path, dict, dict]:
    config = load_config(paths)
    directory = paths.project_runs_dir/RUN
    freeze = json.loads((directory/'preflight/analysis_freeze.json').read_text())
    for name, expected in freeze['immutable_artifact_hashes'].items():
        if sha256(directory/name) != expected:
            raise ValueError('Pre-prediction artifact changed: '+name)
    for name, expected in freeze['input_hashes'].items():
        if sha256(paths.codex_root/name) != expected:
            raise ValueError('Pre-prediction input changed: '+name)
    if config != json.loads((directory/'frozen/config.json').read_text()):
        raise ValueError('Frozen scientific configuration changed')
    return directory, config, freeze


def rank_stratum(rank: float, n: int, upper_bounds: Sequence[float]) -> int:
    percentile = (rank-.5)/n
    return next(i+1 for i, bound in enumerate(upper_bounds) if percentile <= bound)


def infer(paths: StoragePaths) -> dict:
    start = time.monotonic()
    directory, config, _ = _check_freeze(paths)
    write_json(directory/'predictions/inference_started.json', {
        'started_utc': datetime.now(timezone.utc).isoformat(), 'planned_unique_pair_calls': 671,
        'model_sha256': config['model_sha256']})  # Exclusive sentinel prevents rescoring.
    from . import stability_teacher as teacher
    model = teacher.load_model(paths.project_data_dir/config['bundle_relative_path']/'checkpoints/teacher_model.json')
    rows = read_rows(directory/'frozen/primary_cohort.jsonl')
    predictions = []
    for row in rows:
        prediction = model.predict_stability(row['peptide'], row['hla'])  # Exactly once per frozen pair.
        if prediction['model_status'] != 'ok' or prediction['resolved_hla'] != row['hla']:
            raise ValueError('Original Teacher did not accept a frozen input')
        log_value, hours = prediction['predicted_log1p_hours'], prediction['predicted_half_life_hours']
        if not all(math.isfinite(v) and v >= 0 for v in (log_value, hours)) or math.expm1(log_value) != hours:
            raise ValueError('Nonfinite prediction or original inverse-transform mismatch')
        predictions.append({'source_identity': row['source_identity'],
                            'original_manifest_row_1based': row['original_manifest_row_1based'],
                            'peptide': row['peptide'], 'hla': row['hla'], 'input_accepted': True,
                            'output_valid': True, **prediction})
    ranks = doubled_ranks([p['predicted_log1p_hours'] for p in predictions])
    for p, rank in zip(predictions, ranks):
        p['within_HLA_stability_average_rank'] = rank/2
        p['prespecified_rank_quartile'] = rank_stratum(rank/2, len(rows), config['descriptive_rank_strata']['upper_bounds'])
    output = directory/'predictions/Teacher_predictions.jsonl'
    write_rows(output, predictions)
    summary = {'status': 'PASS', 'unique_pair_model_calls': len(predictions),
               'all_predictions_finite_and_aligned': True,
               'model_sha256': config['model_sha256'], 'prediction_sha256': sha256(output),
               'pre_analysis_freeze_sha256': sha256(directory/'preflight/analysis_freeze.json'),
               'clipped_predictions': sum(p['log_prediction_clipped_to_zero'] for p in predictions),
               'zero_hour_predictions': sum(p['predicted_half_life_hours'] == 0 for p in predictions),
               'distinct_log_predictions': len({p['predicted_log1p_hours'] for p in predictions}),
               'half_life_hours': distribution_summary([p['predicted_half_life_hours'] for p in predictions]),
               'log1p_half_life_hours': distribution_summary([p['predicted_log1p_hours'] for p in predictions]),
               'finished_utc': datetime.now(timezone.utc).isoformat(), 'runtime_seconds': time.monotonic()-start,
               'association_computed': False, 'training': False}
    write_json(directory/'predictions/inference_receipt.json', summary)
    return summary


def descriptive_summary(rows: list[dict]) -> dict:
    def describe(subset: list[dict]) -> dict:
        n = len(subset)
        return {'n': n, 'repeat_count_distribution': dict(Counter(r['repeat_detection_count'] for r in subset)),
                'mean_repeat_detection_frequency': math.fsum(r['repeat_detection_frequency'] for r in subset)/n if n else None,
                'followup_1_detection_rate': sum(r['followup_1_direct'] for r in subset)/n if n else None,
                'followup_2_detection_rate': sum(r['followup_2_direct'] for r in subset)/n if n else None,
                'half_life_hours': distribution_summary([r['predicted_half_life_hours'] for r in subset]),
                'log1p_half_life_hours': distribution_summary([r['predicted_log1p_hours'] for r in subset])}
    return {'overall': describe(rows),
            'by_repeat_count': {str(k): describe([r for r in rows if r['repeat_detection_count'] == k]) for k in range(3)},
            'by_followup_pattern': {f'{a}{b}': describe([r for r in rows if (r['followup_1_direct'], r['followup_2_direct']) == (a, b)]) for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))},
            'by_rank_quartile': {str(k): describe([r for r in rows if r['prespecified_rank_quartile'] == k]) for k in range(1, 5)},
            'by_global_fitting_exposure': {
                'exact_or_one_substitution': describe([r for r in rows if not r['Teacher_exposure']['exposure_excluded_sensitivity_eligible']]),
                'minimum_distance_ge2': describe([r for r in rows if r['Teacher_exposure']['exposure_excluded_sensitivity_eligible']])}}


def analyze(paths: StoragePaths) -> dict:
    start = time.monotonic()
    directory, config, freeze = _check_freeze(paths)
    receipt = json.loads((directory/'predictions/inference_receipt.json').read_text())
    prediction_file = directory/'predictions/Teacher_predictions.jsonl'
    if sha256(prediction_file) != receipt['prediction_sha256'] or sha256(directory/'preflight/analysis_freeze.json') != receipt['pre_analysis_freeze_sha256']:
        raise ValueError('Saved predictions or analysis freeze changed')
    rows = read_rows(directory/'frozen/primary_cohort.jsonl')
    predictions = read_rows(prediction_file)
    if len(rows) != len(predictions) or len(rows) != 671:
        raise ValueError('Prediction/cohort count mismatch')
    joined = []
    for row, prediction in zip(rows, predictions):
        if any(row[k] != prediction[k] for k in ('source_identity', 'peptide', 'hla', 'original_manifest_row_1based')):
            raise ValueError('Prediction/source identity misalignment')
        joined.append({**row, **prediction})
    sensitivity_ids = json.loads((directory/'frozen/sensitivity_source_identities.json').read_text())
    sensitivity = [r for r in joined if r['source_identity'] in set(sensitivity_ids)]
    if [r['source_identity'] for r in sensitivity] != sensitivity_ids:
        raise ValueError('Sensitivity identities differ from pre-prediction freeze')
    write_json(directory/'statistics/analysis_started.json', {
        'started_utc': datetime.now(timezone.utc).isoformat(), 'pre_analysis_freeze_sha256': receipt['pre_analysis_freeze_sha256'],
        'prediction_sha256': receipt['prediction_sha256']})
    results = {}
    for name, cohort in [('primary', joined), ('fitting_exposure_excluded_sensitivity', sensitivity)]:
        x = [r['predicted_log1p_hours'] for r in cohort]
        y = [r['repeat_detection_frequency'] for r in cohort]
        observed = spearman(x, y)
        if observed != spearman(x, [r['repeat_detection_count'] for r in cohort]):
            raise ValueError('Count/frequency rank correlation should be identical')
        control, distribution = permutation_control(x, y, config['permutation_draws'], config['permutation_seed'])
        components = dependence_components(cohort)
        results[name] = {'n': len(cohort), 'hla': config['hla'], 'biological_groups': 1,
                         'outcome_counts': dict(Counter(r['repeat_detection_count'] for r in cohort)),
                         'spearman_rho': observed, 'bootstrap': bootstrap_availability(components, config),
                         'negative_control': control, 'distinct_stability_values': len(set(x)),
                         'distinct_outcome_values': len(set(y)), 'sparse_n_lt30': len(cohort) < 30,
                         'source_identity_sha256': hashlib.sha256(canonical_json([r['source_identity'] for r in cohort]).encode()).hexdigest()}
        write_json(directory/f'statistics/{name}_permutation_distribution.json', distribution)
    description = descriptive_summary(joined)
    write_rows(directory/'observations/predictions_and_repeat_detections.jsonl', joined)
    write_json(directory/'statistics/descriptive_results.json', description)
    results['index_intensity_adjustment'] = intensity_adjustment(joined)
    results['interpretation_limits'] = {'independent_systems': 1, 'independent_studies': 1,
        'peptide_independence_assumed_for_CI': False, 'permutation_requires_exchangeability': True,
        'abundance_adjustment_available': False, 'sample_level_population_inference_supported': False}
    results['execution'] = {'completed_utc': datetime.now(timezone.utc).isoformat(),
                            'analysis_runtime_seconds': time.monotonic()-start,
                            'process_peak_RSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'training': False, 'tuning': False, 'alternative_conditions': False,
                            'inference_calls_in_analysis': 0}
    write_json(directory/'statistics/association_results.json', results)
    return results


def figures(paths: StoragePaths) -> dict:
    """Standard matplotlib export from saved results only; no inference or testing."""
    import os
    directory = paths.project_runs_dir/RUN
    destination = directory/'figures'
    destination.mkdir(exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str(destination/'matplotlib_config')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    description = json.loads((directory/'statistics/descriptive_results.json').read_text())
    statistics = json.loads((directory/'statistics/association_results.json').read_text())
    rows = read_rows(directory/'observations/predictions_and_repeat_detections.jsonl')
    null = json.loads((directory/'statistics/primary_permutation_distribution.json').read_text())
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    groups = [[r['predicted_log1p_hours'] for r in rows if r['repeat_detection_count'] == count] for count in range(3)]
    axes[0, 0].boxplot(groups, tick_labels=[f'{c}\n(n={len(g)})' for c, g in enumerate(groups)], showfliers=True)
    axes[0, 0].set(xlabel='Follow-up direct detection count', ylabel='Predicted log1p(half-life / hours)', title='A. Stability by repeat count')
    quartiles = description['by_rank_quartile']
    bottom = [0.0]*4
    for count, color in zip(range(3), ['#aaaaaa', '#dfad44', '#428b74']):
        heights = [quartiles[str(q)]['repeat_count_distribution'].get(str(count), 0)/quartiles[str(q)]['n']
                   if quartiles[str(q)]['n'] else 0 for q in range(1, 5)]
        axes[0, 1].bar(range(1, 5), heights, bottom=bottom, label=str(count), color=color)
        bottom = [a+b for a, b in zip(bottom, heights)]
    axes[0, 1].set(xlabel='Stability rank quartile (low to high)', ylabel='Fraction of index peptides', title='B. Prespecified quartile descriptions', xticks=range(1, 5))
    axes[0, 1].legend(title='Repeat count', frameon=False)
    for key, label, style in [('followup_1_detection_rate', 'MSB33405A', 'o-'), ('followup_2_detection_rate', 'MSB35123A', 's--')]:
        axes[1, 0].plot(range(1, 5), [quartiles[str(q)][key] for q in range(1, 5)], style, label=label)
    axes[1, 0].set(xlabel='Stability rank quartile (low to high)', ylabel='Direct detection fraction', title='C. Separate biological follow-ups', xticks=range(1, 5), ylim=(0, 1))
    axes[1, 0].legend(frameon=False)
    axes[1, 1].hist(null, bins=40, color='#a8bed2', edgecolor='white')
    rho = statistics['primary']['spearman_rho']
    if rho is not None:
        axes[1, 1].axvline(rho, color='#a23b37', label=f'Observed rho={rho:.4f}')
    else:
        axes[1, 1].text(.5, .5, 'Association undefined', transform=axes[1, 1].transAxes)
    axes[1, 1].set(xlabel='Permuted Spearman rho', ylabel='Draw count', title='D. Descriptive permutation control')
    axes[1, 1].legend(frameon=False)
    fig.suptitle('SHERPA HLA-A*02:01: 671 fixed index peptides; one biological group\nNo independent biological confidence interval; no abundance adjustment', fontsize=12)
    for extension in ('png', 'pdf'):
        fig.savefig(destination/f'stability_repeat_detection.{extension}', dpi=180)
    plt.close(fig)
    metadata = {'matplotlib': matplotlib.__version__, 'python': sys.version,
                'input_results_sha256': sha256(directory/'statistics/association_results.json'),
                'outputs': {f.name: sha256(f) for f in sorted(destination.glob('stability_repeat_detection.*'))},
                'new_inference_or_statistical_tests': False}
    write_json(destination/'figure_metadata.json', metadata)
    return metadata


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'infer', 'analyze', 'figures'))
    stage = parser.parse_args().stage
    action = {'prepare': prepare, 'infer': infer, 'analyze': analyze, 'figures': figures}[stage]
    print(json.dumps(action(resolve_paths()), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
