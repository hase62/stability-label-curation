"""Pilot per-HLA Ridge Teacher. Training is optional; JSON inference is stdlib-only."""
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
import random
import re
import sys
import warnings
from typing import Any, Sequence

from . import dtu2016_source_audit as dtu
from . import netmhcstabpan_2016 as raw
from . import observation_registry as registry
from . import scientific_gate0_preflight as gate0
from . import sequence_leakage_audit as leakage
from . import run_manifest as runs
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/stability_teacher_v0.json'
ALPHABET = 'ACDEFGHIKLMNPQRSTVWY'
VERSION = 'stability_teacher_v0'


def load_config(path: str | Path) -> dict[str, Any]:
    config = gate0._json(path)
    required = {'schema_version', 'teacher_version', 'seed', 'ridge_alpha', 'ridge_solver', 'minimum_training_rows',
                'minimum_validation_rows_descriptive', 'validation_fraction', 'max_hamming_distance', 'target_transform',
                'parent_registry_run_id', 'registry_relative_path', 'registry_sha256', 'dtu_artifact_sha256',
                'parent_evidence', 'expected_population'}
    if not required <= config.keys():
        raise ValueError('Incomplete Teacher configuration')
    if (config['schema_version'] != 1 or config['teacher_version'] != VERSION
            or config['target_transform'] != 'log1p_hours' or config['ridge_solver'] != 'cholesky'
            or type(config['seed']) is not int or config['max_hamming_distance'] != 1
            or not 0 < config['validation_fraction'] < 1
            or not math.isfinite(config['ridge_alpha']) or config['ridge_alpha'] <= 0
            or type(config['minimum_training_rows']) is not int or config['minimum_training_rows'] < 2
            or type(config['minimum_validation_rows_descriptive']) is not int
            or config['minimum_validation_rows_descriptive'] < 2):
        raise ValueError('Invalid fixed pilot Teacher configuration')
    runs.validate_run_id(config['parent_registry_run_id'])
    registry._relative(config['registry_relative_path'])
    for checksum in (config['registry_sha256'], config['dtu_artifact_sha256']):
        if not re.fullmatch('[a-f0-9]{64}', checksum):
            raise ValueError('Invalid input checksum')
    for item in config['parent_evidence']:
        registry._relative(item['relative_path'])
        if not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('Invalid parent evidence checksum')
    return config


def load_population(path: Path, config: dict[str, Any]) -> tuple[list[registry.Observation], dict[str, Any]]:
    """Validate immutable registry bytes; select only explicitly authorized DTU rows."""
    if raw.sha256_file(path) != config['registry_sha256']:
        raise ValueError('Canonical registry SHA256 mismatch')
    selected, seen, excluded = [], set(), Counter()
    for item in gate0._jsonl(path, 64 * 1024 * 1024):
        observation = registry.Observation(**item)
        if observation.observation_id in seen:
            raise ValueError('Duplicate registry observation ID')
        seen.add(observation.observation_id)
        if observation.source_id != 'netmhcstabpan_2016':
            excluded['other_source_or_modality'] += 1
            continue
        if (observation.source_artifact_sha256 != config['dtu_artifact_sha256']
                or observation.measurement_type != 'kinetic_half_life' or observation.measurement_unit != 'hours'):
            raise ValueError('DTU source identity or measurement type/unit mismatch')
        category = dtu.identifier_category(observation.original_allele)
        if category not in {'ordinary_hla_a', 'ordinary_hla_b'}:
            excluded[category] += 1
            continue
        encode_ninemer(observation.original_peptide)
        if registry.decimal_value(observation.original_measurement_text) < 0:
            raise ValueError('Negative half-life in Teacher population')
        selected.append(observation)
    counts = {'observations': len(selected), 'alleles': len({o.original_allele for o in selected}),
              'zeros': sum(registry.decimal_value(o.original_measurement_text) == 0 for o in selected)}
    if counts != config['expected_population']:
        raise ValueError(f'Teacher population mismatch: observed {counts}, expected {config["expected_population"]}')
    if raw.sha256_file(path) != config['registry_sha256']:
        raise ValueError('Registry changed during reading')
    return selected, {**counts, 'positive_values': counts['observations'] - counts['zeros'],
                      'excluded_registry_records': dict(sorted(excluded.items())),
                      'zero_semantics': 'Source-reported numerical zero; underlying mechanism unresolved'}


def encode_ninemer(peptide: str) -> tuple[float, ...]:
    if not isinstance(peptide, str) or len(peptide) != 9:
        raise ValueError('unsupported_peptide_length')
    if any(c not in ALPHABET for c in peptide):
        raise ValueError('noncanonical_amino_acid')
    features = [0.0] * 180
    for position, residue in enumerate(peptide):
        features[position * 20 + ALPHABET.index(residue)] = 1.0
    return tuple(features)


def inverse_log1p(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError('Nonfinite model output')
    return math.expm1(max(0.0, value))


def make_partition(rows: Sequence[registry.Observation], config: dict[str, Any]) -> dict[str, Any]:
    peptides = sorted({o.original_peptide for o in rows})
    edges = leakage.indexed_edges(peptides, 1)
    components = leakage.connected_components(peptides, edges)
    multiplicity = Counter(o.original_peptide for o in rows)
    order = list(components)
    random.Random(config['seed']).shuffle(order)
    target = round(len(rows) * config['validation_fraction'])
    peptide_assignment, component_ids, count = {}, {}, 0
    for component in order:
        weight = sum(multiplicity[p] for p in component)
        group = 'validation' if abs(count + weight - target) < abs(count - target) else 'train'
        if group == 'validation':
            count += weight
        component_id = 'cmp_' + hashlib.sha256('\n'.join(component).encode('ascii')).hexdigest()
        for peptide in component:
            peptide_assignment[peptide], component_ids[peptide] = group, component_id
    assignments = [{'observation_id': o.observation_id, 'partition': peptide_assignment[o.original_peptide],
                    'component_id': component_ids[o.original_peptide]} for o in rows]
    if len({a['partition'] for a in assignments}) != 2:
        raise ValueError('Component constraints cannot produce two nonempty partitions')
    return {'schema_version': 1, 'seed': config['seed'], 'target_validation_fraction': config['validation_fraction'],
            'rule': 'Global peptide components under aligned nine-mer Hamming distance <=1; no allele separation within a peptide',
            'algorithm': 'Seeded shuffle of deterministic components; greedily add whole components only when closer to target observation count',
            'status': 'provisional_pilot_not_final_D4_approval', 'assignments': assignments,
            'unique_peptides': len(peptides), 'components': len(components), 'direct_one_mismatch_edges': len(edges),
            'component_peptide_size_distribution': dict(sorted(Counter(str(len(c)) for c in components).items())),
            'largest_component_peptides': max(map(len, components), default=0)}


def verify_partition(rows: Sequence[registry.Observation], partition: dict[str, Any]) -> dict[str, Any]:
    assignments = partition['assignments']
    by_id = {a['observation_id']: a['partition'] for a in assignments}
    if (len(by_id) != len(assignments) or set(by_id) != {o.observation_id for o in rows}
            or set(by_id.values()) != {'train', 'validation'}):
        raise ValueError('Partition must assign each authorized observation exactly once')
    groups = defaultdict(set)
    for row in rows:
        groups[row.original_peptide].add(by_id[row.observation_id])
    exact = sum(len(g) > 1 for g in groups.values())
    # Independently rebuild the complete neighbor index from assigned observations.
    edges = leakage.indexed_edges(list(groups), 1)
    near = sum(groups[a] != groups[b] for a, b, _ in edges)
    if exact or near:
        raise ValueError('Prohibited exact or one-mismatch cross-partition leakage')
    counts = Counter(by_id.values())
    return {'rule': 'Exact peptide identity and aligned nine-mer Hamming distance <=1, globally across HLA',
            'exact_peptides_crossing': exact, 'direct_one_mismatch_edges_crossing': near,
            'complete_indexed_edges_checked': len(edges), 'partition_counts': dict(sorted(counts.items())),
            'validation_fraction': counts['validation'] / len(rows),
            'limitations': 'Does not establish study/donor, antigen-family, indel or external EL/IM independence',
            'independent_IM_evaluation_claim': False}


@dataclass(frozen=True)
class Teacher:
    """Replaceable downstream interface; inference never needs sklearn or pickle."""
    document: dict[str, Any]
    training_diagnostics: dict[str, Any] | None = None

    def predict_stability(self, peptide: str, hla: str) -> dict[str, Any]:
        result = {'predicted_half_life_hours': None, 'predicted_log1p_hours': None,
                  'model_status': 'unsupported', 'resolved_hla': None, 'teacher_version': VERSION,
                  'unsupported_reason': None}
        try:
            features = encode_ninemer(peptide)
        except ValueError as error:
            return {**result, 'unsupported_reason': str(error)}
        if not isinstance(hla, str) or hla not in self.document['alleles']:
            return {**result, 'unsupported_reason': 'unsupported_exact_HLA_identifier'}
        model = self.document['alleles'][hla]
        result['resolved_hla'] = hla
        if model['status'] != 'trained':
            return {**result, 'unsupported_reason': model['status']}
        value = model['intercept'] + math.fsum(w * f for w, f in zip(model['coefficients'], features))
        try:
            hours = inverse_log1p(value)
        except (ValueError, OverflowError):
            return {**result, 'unsupported_reason': 'numerical_prediction_failure'}
        return {**result, 'predicted_half_life_hours': hours, 'predicted_log1p_hours': max(0.0, value),
                'model_status': 'ok', 'log_prediction_clipped_to_zero': value < 0}

    def predict_batch(self, records: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
        return [self.predict_stability(peptide, hla) for peptide, hla in records]


def fit(rows: Sequence[registry.Observation], partition: dict[str, Any], config: dict[str, Any],
        *, provenance: dict[str, Any] | None = None) -> Teacher:
    try:
        import numpy as np
        import sklearn
        import scipy
        from sklearn.linear_model import Ridge
        from threadpoolctl import threadpool_limits
    except ImportError as error:
        raise RuntimeError('Teacher training requires the isolated configs/requirements-teacher-v0.txt environment') from error
    verify_partition(rows, partition)
    groups = {a['observation_id']: a['partition'] for a in partition['assignments']}
    by_allele = defaultdict(list)
    for row in rows:
        by_allele[row.original_allele].append(row)
    models, warning_counts, residual_checks = {}, Counter(), {}
    with threadpool_limits(limits=1):
        for allele, group in sorted(by_allele.items()):
            training = [o for o in group if groups[o.observation_id] == 'train']
            hours = [float(registry.decimal_value(o.original_measurement_text)) for o in training]
            targets = [math.log1p(v) for v in hours]
            model = {'training_rows': len(training), 'status': 'insufficient_training_support',
                     'training_mean_hours': math.fsum(hours) / len(hours) if hours else None,
                     'training_mean_log1p': math.fsum(targets) / len(targets) if targets else None}
            if len(training) >= config['minimum_training_rows']:
                x = np.array([encode_ninemer(o.original_peptide) for o in training], dtype=np.float64)
                estimator = Ridge(alpha=config['ridge_alpha'], fit_intercept=True, solver='cholesky')
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter('always', RuntimeWarning)
                    estimator.fit(x, np.array(targets, dtype=np.float64))
                warning_counts.update(str(w.message) for w in captured)
                if not np.isfinite(estimator.coef_).all() or not math.isfinite(float(estimator.intercept_)):
                    raise ValueError('Nonfinite fitted Ridge weights')
                # Independent non-BLAS reduction checks the solved Ridge objective.
                residual = np.einsum('ij,j->i', x, estimator.coef_, optimize=False) + estimator.intercept_ - targets
                gradient = np.einsum('ij,i->j', x, residual, optimize=False) + config['ridge_alpha'] * estimator.coef_
                check = max(float(np.max(np.abs(gradient))), abs(float(np.sum(residual))))
                if not math.isfinite(check) or check > 1e-6 * max(1.0, max(targets)):
                    raise ValueError('Ridge stationarity verification failed')
                residual_checks[allele] = check
                model.update(status='trained', intercept=float(estimator.intercept_), coefficients=estimator.coef_.tolist())
            models[allele] = model
    return Teacher({'schema_version': 1, 'teacher_version': VERSION, 'alphabet': ALPHABET, 'peptide_length': 9,
                    'measurement_type': 'kinetic_half_life', 'measurement_unit': 'hours',
                    'target_transform': 'log1p_hours', 'prediction_transform': 'expm1(max(0,linear_log_prediction))',
                    'config': config, 'provenance': provenance or {}, 'alleles': models,
                    'runtime': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
                                'scikit_learn': sklearn.__version__, 'linear_algebra_threads_during_fit': 1},
                    'zero_semantics': 'Source-reported zeros retained; physical and reporting mechanisms unresolved'},
                   {'captured_training_warning_counts': dict(sorted(warning_counts.items())),
                    'finite_weights_verified': True, 'ridge_stationarity_max_absolute_residual_by_allele': residual_checks,
                    'stationarity_check': 'Non-BLAS einsum reduction; X.T @ (Xw+b-y)+alpha*w and sum(Xw+b-y) near zero',
                    'backend_warning_reference': 'https://github.com/numpy/numpy/issues/28687',
                    'warning_interpretation': 'Record observed warnings; finite weights and independent stationarity checks gate acceptance'})


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2 or min(left) == max(left) or min(right) == max(right):
        return None
    xmean, ymean = math.fsum(left) / len(left), math.fsum(right) / len(right)
    x, y = [v - xmean for v in left], [v - ymean for v in right]
    xx, yy = math.fsum(v * v for v in x), math.fsum(v * v for v in y)
    return None if xx == 0 or yy == 0 else max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(x, y)) / math.sqrt(xx * yy)))


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks, start = [0.0] * len(values), 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for index in order[start:end]:
            ranks[index] = (start + 1 + end) / 2
        start = end
    return ranks


def metrics(truth: Sequence[float], predictions: Sequence[float]) -> dict[str, Any]:
    if len(truth) != len(predictions) or any(not math.isfinite(v) or v < 0 for v in (*truth, *predictions)):
        raise ValueError('Invalid nonnegative paired regression values')
    n = len(truth)
    logs, predlogs = [math.log1p(v) for v in truth], [math.log1p(v) for v in predictions]
    return {'n': n, 'mae_log1p_hours': math.fsum(abs(a - b) for a, b in zip(logs, predlogs)) / n if n else None,
            'mae_hours': math.fsum(abs(a - b) for a, b in zip(truth, predictions)) / n if n else None,
            'spearman_hours': _pearson(_ranks(truth), _ranks(predictions)),
            'pearson_hours': _pearson(truth, predictions), 'pearson_log1p_hours': _pearson(logs, predlogs),
            'undefined_correlation_meaning': 'null when fewer than two values or either sequence is constant; average ranks for ties'}


def evaluate(teacher: Teacher, rows: Sequence[registry.Observation], partition: dict[str, Any]) -> dict[str, Any]:
    verify_partition(rows, partition)
    validation = {a['observation_id'] for a in partition['assignments'] if a['partition'] == 'validation'}
    group_values = defaultdict(list)
    unsupported, clipped = Counter(), 0
    for row in rows:
        if row.observation_id not in validation:
            continue
        prediction = teacher.predict_stability(row.original_peptide, row.original_allele)
        if prediction['model_status'] != 'ok':
            unsupported[prediction['unsupported_reason']] += 1
            continue
        source = float(registry.decimal_value(row.original_measurement_text))
        model = teacher.document['alleles'][row.original_allele]
        values = (source, prediction['predicted_half_life_hours'], inverse_log1p(model['training_mean_log1p']), model['training_mean_hours'])
        for group in ('overall', 'reported_zero' if source == 0 else 'positive', row.original_allele):
            group_values[group].append(values)
        clipped += int(prediction['log_prediction_clipped_to_zero'])
    result = {}
    for group in ['overall', 'positive', 'reported_zero', *sorted(teacher.document['alleles'])]:
        pairs = group_values[group]
        truth = [p[0] for p in pairs]
        result[group] = {name: metrics(truth, [p[index] for p in pairs]) for name, index in
                         (('teacher', 1), ('training_allele_mean_log1p_baseline', 2), ('training_allele_mean_hours_baseline', 3))}
    return {'validation_rows': len(validation), 'scored_rows': len(group_values['overall']),
            'unsupported_validation_rows': dict(sorted(unsupported.items())), 'log_predictions_clipped_to_zero': clipped,
            'results': result, 'baseline_comparison': 'Same scored validation rows; means computed exclusively from the training partition in the named space',
            'validation_tuning_performed': False}


def load_model(path: str | Path) -> Teacher:
    if Path(path).stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Model JSON byte cap exceeded')
    document = gate0._json(path)
    required = {'schema_version', 'teacher_version', 'alphabet', 'peptide_length', 'measurement_type',
                'measurement_unit', 'target_transform', 'prediction_transform', 'alleles', 'config', 'provenance'}
    if not required <= document.keys() or not isinstance(document['alleles'], dict):
        raise ValueError('Incomplete Teacher JSON schema')
    if (document['schema_version'] != 1 or document['teacher_version'] != VERSION or document['alphabet'] != ALPHABET
            or document['peptide_length'] != 9 or document['measurement_type'] != 'kinetic_half_life'
            or document['measurement_unit'] != 'hours' or document['target_transform'] != 'log1p_hours'
            or document['prediction_transform'] != 'expm1(max(0,linear_log_prediction))' or len(document['alleles']) > 1000):
        raise ValueError('Unsupported Teacher JSON schema')
    for allele, model in document['alleles'].items():
        if not isinstance(model, dict) or not {'status', 'training_rows', 'training_mean_hours', 'training_mean_log1p'} <= model.keys():
            raise ValueError('Incomplete allele model')
        if dtu.identifier_category(allele) not in {'ordinary_hla_a', 'ordinary_hla_b'}:
            raise ValueError('Model contains unsupported HLA identifier')
        if model['status'] not in {'trained', 'insufficient_training_support'} or type(model['training_rows']) is not int or model['training_rows'] < 0:
            raise ValueError('Invalid model support status')
        for key in ('training_mean_hours', 'training_mean_log1p'):
            if model[key] is not None and (not math.isfinite(model[key]) or model[key] < 0):
                raise ValueError('Invalid training baseline')
        if model['status'] == 'trained' and (not {'coefficients', 'intercept'} <= model.keys()
                or model['training_rows'] < 2 or model['training_mean_hours'] is None or model['training_mean_log1p'] is None
                or not isinstance(model['coefficients'], list) or len(model['coefficients']) != 180
                or not all(type(v) in (int, float) and math.isfinite(v) for v in [model['intercept'], *model['coefficients']])):
            raise ValueError('Invalid finite numeric model coefficients')
    return Teacher(document)


def _inputs(config: dict[str, Any], paths: StoragePaths, registry_path: str | Path | None = None):
    parent = paths.project_runs_dir / config['parent_registry_run_id']
    path = Path(registry_path).absolute() if registry_path else parent / config['registry_relative_path']
    inputs = [{'path': str(path), 'sha256': config['registry_sha256']}]
    inputs += [{'path': str(parent / item['relative_path']), 'sha256': item['sha256']} for item in config['parent_evidence']]
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Teacher input SHA256 mismatch: ' + Path(item['path']).name)
    return path, inputs


def _run(path: str | Path, paths: StoragePaths):
    directory = Path(path).expanduser().absolute()
    if '..' in directory.parts or directory.parent != paths.project_runs_dir:
        raise ValueError('Output must be an existing project run directory')
    manifest = runs.load_manifest(directory.name, paths=paths)
    if manifest['git'] != runs.capture_git_provenance(paths.repository_root, allow_dirty=manifest['git']['git_dirty']):
        raise ValueError('Output run must record the current committed code and working-tree state')
    return directory, manifest


def train_run(*, out: str | Path, config_path: str | Path, paths: StoragePaths | None = None,
              registry_path: str | Path | None = None) -> dict[str, Any]:
    storage = paths or resolve_paths()
    config = load_config(config_path)
    path, inputs = _inputs(config, storage, registry_path)
    directory, manifest = _run(out, storage)
    if (manifest['configuration']['file'] != {'path': str(Path(config_path).absolute()), 'sha256': raw.sha256_file(config_path)}
            or manifest['configuration']['random_seed'] != config['seed']
            or any(item not in manifest['data_provenance']['input_artifacts'] for item in inputs)):
        raise ValueError('Run must record the actual configuration, seed and all registry inputs')
    model_path = directory / 'checkpoints/teacher_model.json'
    names = ['teacher_train_val_partition.json', 'teacher_validation_metrics.json', 'teacher_allele_coverage.json',
             'teacher_leakage_audit.json', 'teacher_training_diagnostics.json', 'execution_verification.json']
    if model_path.exists() or any((directory / 'reports' / name).exists() for name in names):
        raise FileExistsError('Existing Teacher artifacts preserved; no silent retraining or overwrite')
    rows, population = load_population(path, config)
    partition = make_partition(rows, config)
    audit = verify_partition(rows, partition)
    provenance = {'code_commit': manifest['git']['commit_sha'], 'inputs': inputs, 'parent_registry_run_id': config['parent_registry_run_id'],
                  'config_sha256': raw.sha256_file(config_path),
                  'partition_sha256': hashlib.sha256(raw.json_report(partition).encode('utf-8')).hexdigest()}
    teacher = fit(rows, partition, config, provenance=provenance)
    validation = evaluate(teacher, rows, partition)
    groups = {a['observation_id']: a['partition'] for a in partition['assignments']}
    coverage = {}
    for allele, model in teacher.document['alleles'].items():
        group = [o for o in rows if o.original_allele == allele]
        counts = Counter(groups[o.observation_id] for o in group)
        coverage[allele] = {'train': counts['train'], 'validation': counts['validation'], 'model_status': model['status'],
                           'validation_support': 'sparse' if counts['validation'] < config['minimum_validation_rows_descriptive'] else 'descriptive_metrics_available',
                           'reported_zeros_by_partition': dict(Counter(groups[o.observation_id] for o in group if registry.decimal_value(o.original_measurement_text) == 0))}
    reports = {'teacher_train_val_partition.json': partition, 'teacher_validation_metrics.json': validation,
               'teacher_allele_coverage.json': {'population': population, 'by_allele': coverage}, 'teacher_leakage_audit.json': audit,
               'teacher_training_diagnostics.json': teacher.training_diagnostics}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Immutable Teacher input changed')
    raw.write_report(model_path, teacher.document, paths=storage)
    reloaded = load_model(model_path)
    same = teacher.predict_batch([(o.original_peptide, o.original_allele) for o in rows]) == reloaded.predict_batch([(o.original_peptide, o.original_allele) for o in rows])
    if not same:
        raise ValueError('Saved Teacher reload prediction mismatch')
    for name, report in reports.items():
        raw.write_report(directory / 'reports' / name, report, paths=storage)
    receipt = {'code_commit': manifest['git']['commit_sha'], 'seed': config['seed'], 'input_artifacts': inputs,
               'model_sha256': raw.sha256_file(model_path), 'config_sha256': raw.sha256_file(config_path),
               'report_sha256': {name: raw.sha256_file(directory / 'reports' / name) for name in reports},
               'model_reload_predictions_identical': same, 'reload_checked_observations': len(rows),
               'EL_IM_data_read_or_modified': False, 'provisional_pilot_only': True}
    raw.write_report(directory / 'reports/execution_verification.json', receipt, paths=storage)
    return {'run': str(directory), 'model': str(model_path), 'population': population, 'split': audit,
            'validation': validation['results']['overall'], 'reload_verified': same}


def evaluate_run(*, model_path: str | Path, out: str | Path, paths: StoragePaths | None = None,
                 registry_path: str | Path | None = None, partition_path: str | Path | None = None) -> dict[str, Any]:
    storage = paths or resolve_paths()
    teacher = load_model(model_path)
    config = teacher.document['config']
    path, inputs = _inputs(config, storage, registry_path)
    directory, manifest = _run(out, storage)
    artifact = Path(partition_path) if partition_path else Path(model_path).parent.parent / 'reports/teacher_train_val_partition.json'
    if raw.sha256_file(artifact) != teacher.document['provenance']['partition_sha256']:
        raise ValueError('Saved split SHA256 mismatch')
    required = [*inputs, {'path': str(Path(model_path).absolute()), 'sha256': raw.sha256_file(model_path)},
                {'path': str(artifact.absolute()), 'sha256': raw.sha256_file(artifact)}]
    if any(item not in manifest['data_provenance']['input_artifacts'] for item in required):
        raise ValueError('Evaluation run must hash registry, model, saved split and parent evidence')
    rows, _ = load_population(path, config)
    result = evaluate(teacher, rows, gate0._json(artifact))
    raw.write_report(directory / 'reports/teacher_validation_metrics.json', result, paths=storage)
    return result


def predict_csv(*, model_path: str | Path, input_path: str | Path, out: str | Path,
                paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = paths or resolve_paths()
    target = Path(out).expanduser().absolute()
    if target.parent.name != 'predictions':
        raise ValueError('Prediction output must be in an existing run predictions directory')
    _, manifest = _run(target.parent.parent, storage)
    required = [{'path': str(Path(p).absolute()), 'sha256': raw.sha256_file(p)} for p in (model_path, input_path)]
    if any(item not in manifest['data_provenance']['input_artifacts'] for item in required):
        raise ValueError('Prediction run must hash model and input CSV')
    teacher = load_model(model_path)
    output, count = io.StringIO(newline=''), 0
    fields = ['peptide', 'hla', 'predicted_half_life_hours', 'model_status', 'resolved_hla', 'teacher_version', 'unsupported_reason']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    with raw._read_file(input_path) as stream:
        if stream.seek(0, 2) > 10 * 1024 * 1024:
            raise ValueError('Inference input byte cap exceeded')
        stream.seek(0)
        with io.TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
            reader = csv.DictReader(text)
            if reader.fieldnames != ['peptide', 'hla']:
                raise ValueError('Inference accepts only peptide,hla columns; no EL/IM labels')
            for row in reader:
                count += 1
                if count > 100000 or None in row or any(v is None for v in row.values()):
                    raise ValueError('Inference row bound or malformed row')
                result = teacher.predict_stability(row['peptide'], row['hla'])
                writer.writerow({**row, **{k: result[k] for k in fields[2:]}})
    for item in required:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Immutable inference input changed')
    raw.write_text_report(target, output.getvalue(), paths=storage)
    return {'predictions': str(target), 'rows': count, 'sha256': raw.sha256_file(target), 'labels_read_or_modified': False}
