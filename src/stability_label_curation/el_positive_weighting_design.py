"""Aggregate-only preregistration feasibility; never trains or exports row weights."""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import random
import re
from pathlib import Path
from typing import Iterable

from . import el_positive_stability_analysis as prior
from . import netmhcstabpan_2016 as raw
from . import scientific_gate0_preflight as readers
from .paths import resolve_paths

VERSION = 'el_positive_weighting_preregistration_v1'
CONFIG = 'configs/el_positive_weighting_protocol_v1.json'
PARENT_FILES = {'manifest': 'manifest.json', 'receipt': 'reports/execution_verification.json',
                'alignment': 'reports/teacher_coverage_alignment.json',
                'reliability': 'reports/teacher_reliability.json'}
PARENT_RUN = 'task-2_11-el-positive-reproducibility'


def midrank_weights(scores: Iterable[str]) -> list[Fraction]:
    """r=(strictly below + tied/2)/n; exact arithmetic, numeric-text ties."""
    values = []
    for text in scores:
        try:
            value = Decimal(text)
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError('Invalid Teacher score') from error
        if not value.is_finite() or value < 0:
            raise ValueError('Nonfinite or negative Teacher score')
        values.append(value)
    if not values:
        raise ValueError('No positive scores')
    counts = Counter(values)
    below, n, lookup = 0, len(values), {}
    for value, tied in sorted(counts.items()):
        lookup[value] = Fraction(3 * n + 2 * below + tied, 4 * n)
        below += tied
    result = [lookup[value] for value in values]
    if sum(result) != n:
        raise ValueError('Positive weight conservation failed')
    return result


def permuted_weights(ids: list[str], weights: list[Fraction], hla: str, seed: int = 42) -> list[Fraction]:
    """Independent HLA RNG, canonical source-ID order, no global RNG mutation."""
    if len(ids) != len(weights) or len(set(ids)) != len(ids) or not ids:
        raise ValueError('Missing, duplicate or mismatched positive identities')
    if any(not identity for identity in ids) or not hla:
        raise ValueError('Missing source/HLA identity')
    order = sorted(range(len(ids)), key=ids.__getitem__)
    material = f'{VERSION}\0permutation\0{seed}\0{hla}'.encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(material).digest(), 'big'))
    shuffled = [weights[i] for i in order]
    # Explicit Fisher-Yates; pin Python runtime for randrange reproducibility.
    for j in range(len(shuffled) - 1, 0, -1):
        k = rng.randrange(j + 1)
        shuffled[j], shuffled[k] = shuffled[k], shuffled[j]
    result = list(weights)
    for i, weight in zip(order, shuffled):
        result[i] = weight
    if sorted(result) != sorted(weights) or sum(result) != sum(weights):
        raise ValueError('Permutation altered the weight distribution')
    return result


def describe_weights(weights: list[Fraction]) -> dict:
    ordered = sorted(weights)
    n = len(ordered)
    if not n or sum(weights) != n:
        raise ValueError('Invalid positive weight distribution')
    def quantile(p):
        position = Fraction(n - 1) * p
        lo = position.numerator // position.denominator
        hi = min(lo + 1, n - 1)
        return float(ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo))
    squares = sum(w * w for w in weights)
    return {'n': n, 'min': float(ordered[0]), 'p05': quantile(Fraction(1, 20)),
            'p25': quantile(Fraction(1, 4)), 'median': quantile(Fraction(1, 2)),
            'p75': quantile(Fraction(3, 4)), 'p95': quantile(Fraction(19, 20)),
            'max': float(ordered[-1]), 'mean_exact': str(sum(weights) / n),
            'total_weight_exact': str(sum(weights)), 'sum_squared_weights': float(squares),
            'weight_ESS': float(Fraction(n * n) / squares),
            'below_one': sum(w < 1 for w in weights), 'equal_one': weights.count(Fraction(1)),
            'above_one': sum(w > 1 for w in weights)}


def summarize(records: Iterable[dict], *, seed: int = 42) -> dict:
    """Hold positives only; negatives counted with unit weight, no label changes."""
    groups, counts, last, seen = defaultdict(list), defaultdict(Counter), 0, set()
    for record in records:
        hla, label = record['resolved_hla'], record['original_label']
        index = int(record['row_index'])
        if (label not in {'0', '1'} or index <= last or not re.fullmatch(r'HLA-[AB]\*\d{2}:\d{2}', hla)
                or not record['source_row_id']):
            raise ValueError('Unordered, unsupported or invalid original EL record')
        last = index
        counts[hla][label] += 1
        if label == '1':
            if record['source_row_id'] in seen:
                raise ValueError('Duplicate positive identity, including across HLA')
            seen.add(record['source_row_id'])
            groups[hla].append((record['source_row_id'], record['predicted_half_life_hours']))
    if not groups or set(groups) != set(counts):
        raise ValueError('No positives in an observed HLA; protocol amendment required')
    by_hla, all_weights, assignment_hashes = {}, [], {}
    for hla, entries in sorted(groups.items()):
        ids, scores = map(list, zip(*entries))
        weights = midrank_weights(scores)
        permutation = permuted_weights(ids, weights, hla, seed)
        all_weights.extend(weights)
        ties = Counter(Decimal(s) for s in scores)
        by_hla[hla] = {**describe_weights(weights), 'original_negative_count': counts[hla]['0'],
            'negative_loss_weight': 1, 'unique_score_values': len(ties),
            'observations_in_tied_groups': sum(n for n in ties.values() if n > 1),
            'largest_tie_group': max(ties.values()), 'small_positive_group_below10': len(ids) < 10,
            'permutation_same_multiset_and_sum': True,
            'permutation_unchanged_assignments': sum(a == b for a, b in zip(weights, permutation))}
        # Only aggregate hashes leave memory; no individual learning weights are exported.
        for arm, assigned in (('B', weights), ('P', permutation)):
            lines = ''.join(f'{identity}\t{weight}\n' for identity, weight in sorted(zip(ids, assigned)))
            assignment_hashes[f'{hla}:{arm}'] = hashlib.sha256(lines.encode()).hexdigest()
    negatives = sum(c['0'] for c in counts.values())
    return {'version': VERSION, 'status': 'design_only_training_approval_pending',
        'overall_positive_weights': describe_weights(all_weights), 'by_HLA': by_hla,
        'original_negative_count': negatives, 'negative_loss_weight': 1,
        'positive_score_coverage': 1.0, 'observed_HLA': len(by_hla),
        'permutation_assignment_sha256_by_HLA': assignment_hashes,
        'row_weights_exported': False, 'labels_modified': False}


def load_inputs(config_path: str | Path, paths=None):
    paths = paths or resolve_paths()
    config = readers._json(config_path)
    if (config.get('version') != VERSION or config.get('schema_version') != 1
            or config.get('strength') != '0.5' or config.get('seed') != 42
            or config.get('training_approval') != 'decision_pending'):
        raise ValueError('Invalid preregistration configuration')
    base = config['parent_analysis_configuration']
    prior.pilot.registry._relative(base['relative_path'])
    previous_path = paths.repository_root / base['relative_path']
    if raw.sha256_file(previous_path) != base['sha256']:
        raise ValueError('Parent analysis configuration SHA256 mismatch')
    previous = prior.load_config(previous_path)
    files, inputs = prior.resolve_inputs(previous, paths)
    documents = {}
    if set(config['parent_evidence']) != set(PARENT_FILES):
        raise ValueError('Unexpected parent evidence inventory')
    for key, item in config['parent_evidence'].items():
        prior.pilot.registry._relative(item['relative_path'])
        if item['relative_path'] != PARENT_RUN + '/' + PARENT_FILES[key]:
            raise ValueError('Only approved Task2.11 aggregate evidence may be read')
        path = paths.project_runs_dir / item['relative_path']
        if raw.sha256_file(path) != item['sha256']:
            raise ValueError('Parent evidence SHA256 mismatch: ' + key)
        inputs.append({'path': str(path), 'sha256': item['sha256']})
        documents[key] = readers._json(path)
    manifest = prior.pilot.runs.validate_manifest(documents['manifest'])
    if (manifest['git']['commit_sha'] != config['parent_code_commit']
            or documents['receipt']['code_commit'] != config['parent_code_commit']
            or documents['receipt']['config_sha256'] != base['sha256']):
        raise ValueError('Parent analysis code/configuration mismatch')
    for key in ('alignment', 'reliability'):
        filename = Path(config['parent_evidence'][key]['relative_path']).name
        if documents['receipt']['outputs']['reports/' + filename] != config['parent_evidence'][key]['sha256']:
            raise ValueError('Parent evidence receipt mismatch')
    return config, previous, files, inputs, documents


def inspect(config_path: str | Path, *, paths=None):
    config, previous, files, inputs, documents = load_inputs(config_path, paths)
    context = prior.verify_lineage(previous, files)
    alignment = {}
    rows = prior.aligned_scores(prior.adapter._csv_rows(files['el_scores']), prior.ledger_rows(files['el_ledger']),
                                prior.original_rows(files['el_original']), context, alignment)
    result = summarize(rows, seed=config['seed'])
    for key in ('retained_rows', 'retained_labels', 'pre_purge_rows', 'removed_rows'):
        if alignment[key] != documents['alignment'][key]:
            raise ValueError('Population differs from approved Task2.11 evidence')
    if (result['overall_positive_weights']['n'] != 70069 or result['original_negative_count'] != 1383509
            or result['observed_HLA'] != 49):
        raise ValueError('Preregistered population mismatch; do not silently change eligibility')
    n = result['overall_positive_weights']['n']
    result['nominal_native_sampler'] = {'positive_anchors': n, 'negatives_per_batch': 16,
        'batch_rows': 17, 'optimizer_steps': n, 'sampled_negative_rows': 16 * n,
        'unsampled_negative_rows': result['original_negative_count'] - 16 * n,
        'epoch_positive_coefficient_sum': n / 17, 'epoch_negative_coefficient_sum': 16 * n / 17,
        'interpretation': 'Static current-population expectation, not executed sampling or gradient norms'}
    reliability = documents['reliability']['by_HLA']
    for hla, group in result['by_HLA'].items():
        saved = reliability[hla]['saved_validation_metrics']
        group['Teacher_validation_n'] = saved.get('n', 0)
        group['Teacher_validation_Spearman'] = saved.get('spearman_hours')
        group['Teacher_validation_sparse_below10'] = reliability[hla]['validation_sparse_below10']
    result['alignment'] = alignment
    result['parent_run_id'] = documents['manifest']['run_id']
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Input changed during design analysis')
    return result, inputs


def execute(config_path: str | Path, *, out: str | Path | None = None, verify_existing=False, paths=None):
    """Read-only by default; output only aggregates inside one existing project run."""
    paths = paths or resolve_paths()
    result, inputs = inspect(config_path, paths=paths)
    if out is None:
        if verify_existing:
            raise ValueError('Replay requires an explicit run')
        return result
    directory, manifest = prior.teacher._run(out, paths)
    if (manifest['configuration']['file'] != {'path': str(Path(config_path).absolute()), 'sha256': raw.sha256_file(config_path)}
            or manifest['configuration']['random_seed'] != 42
            or any(item not in manifest['data_provenance']['input_artifacts'] for item in inputs)):
        raise ValueError('Run must record actual inputs, seed and protocol configuration')
    content = raw.json_report(result)
    digest = hashlib.sha256(content.encode()).hexdigest()
    report = directory / 'reports/weighting_design_feasibility.json'
    if verify_existing:
        receipt = readers._json(directory / 'reports/execution_verification.json')
        if receipt['output_sha256'] != digest or raw.sha256_file(report) != digest:
            raise ValueError('Offline feasibility reproduction differs')
        return {'offline_deterministic_reproduction': True, 'output_sha256': digest}
    raw.write_text_report(report, content, paths=paths)
    raw.write_report(directory / 'reports/execution_verification.json', {
        'code_commit': manifest['git']['commit_sha'], 'inputs': inputs, 'output_sha256': digest,
        'parent_run_id': result['parent_run_id'], 'all_inputs_unchanged': True,
        'training_approval': 'decision_pending', 'training_performed': False,
        'row_weights_exported': False, 'labels_modified': False, 'EL_scores_recomputed': False,
        'IM_development_outcomes_read': False, 'sealed_payloads_opened': [],
        'corrected_training_views_opened': [], 'configuration_sha256': raw.sha256_file(config_path),
        'permutation_runtime': __import__('sys').version}, paths=paths)
    return {'run': str(directory), 'positive_count': result['overall_positive_weights']['n'],
            'output_sha256': digest}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=CONFIG)
    parser.add_argument('--out')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    print(raw.json_report(execute(args.config, out=args.out, verify_existing=args.verify_existing)), end='')
