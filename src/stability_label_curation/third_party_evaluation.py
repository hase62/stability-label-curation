"""One-time Task 2.27 inference and locked paired component evaluation.

No curation, training, model selection, downloads or historical rescoring.
NumPy/Torch are imported only by explicitly invoked runtime operations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

from . import bigmhc_baseline_runner as runner
from . import bigmhc_independent_preflight as gates
from .bigmhc_independent_evaluation import (
    ARMS, contrasts, digest, git, quantile, read_rows, write_json, write_rows,
)
from .paths import StoragePaths, resolve_paths

BASE = 'ee57cb89a3311b1bc7b736d69770be192085c5d1'
BRANCH = 'task/2.27-third-party-hard-split-evaluation'
RUN = 'task-2_27-third-party-hard-split-evaluation'
PREVIOUS = 'task-2_26-third-party-hard-split'
PROTOCOL = 'docs/BIGMHC_THIRD_PARTY_EVALUATION_TASK2_27_PROTOCOL.md'
PROTOCOL_SHA = '6139b8a850224781d71768949f6a138ebdfdc111547222cd4ba1c935649df0c9'
FREEZE_SHA = '20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557'
AMENDMENT_SHA = '794f6cb4a68e8f0cae9d9fba9cc706872141ed1a12c5a5badaf616716903c2f4'
ORDER = (3, 2, 4)
EXPECTED = {3: (7788, 227, 38, 1), 2: (9303, 266, 28, 1), 4: (892, 29, 65, 2)}
RUNTIME = {'seed': 42, 'device': 'cuda', 'cpu_threads': 4, 'batch_size': 16}
DRAW_COUNT = 10000


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def software_hashes(paths: StoragePaths) -> dict[str, str]:
    return {name: runner.raw.sha256_file(paths.repository_root / name) for name in (
        PROTOCOL, 'src/stability_label_curation/third_party_evaluation.py',
        'tests/test_third_party_evaluation.py',
        'src/stability_label_curation/bigmhc_baseline_runner.py',
        'src/stability_label_curation/bigmhc_independent_preflight.py',
        'src/stability_label_curation/bigmhc_independent_evaluation.py',
        'src/stability_label_curation/paths.py')}


def context(paths: StoragePaths) -> Path:
    if git(paths, 'branch', '--show-current') != BRANCH:
        raise ValueError('Wrong authorized branch')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'],
                   cwd=paths.repository_root, check=True)
    if runner.raw.sha256_file(paths.repository_root / PROTOCOL) != PROTOCOL_SHA:
        raise ValueError('Locked protocol changed')
    return paths.project_runs_dir / RUN


def begin(paths: StoragePaths, stage: str) -> tuple[Path, float]:
    directory = context(paths)
    if git(paths, 'status', '--porcelain'):
        raise ValueError('Execution requires clean committed implementation')
    for name in ('reports', 'predictions', 'evaluation', 'logs'):
        (directory / name).mkdir(parents=True, exist_ok=True)
    write_json(directory / f'reports/{stage}_started.json', {
        'utc': utc(), 'commit': git(paths, 'rev-parse', 'HEAD'),
        'scientific_hashes': software_hashes(paths), 'stage': stage,
        'training_authorized': False, 'runtime_configuration': RUNTIME,
        'protocol': PROTOCOL, 'protocol_sha256': PROTOCOL_SHA})
    return directory, time.monotonic()


def authenticated_identities(paths: StoragePaths) -> tuple[dict[int, list[dict]], dict]:
    """Reuse frozen witnesses and verify only receipts and consumed identities.

    Hashing outcome bytes does not parse/open their outcome values. Those are
    parsed only in evaluate(), after the three prediction files are frozen.
    """
    previous = paths.project_runs_dir / PREVIOUS
    freeze_path = previous / 'reports/benchmark_freeze.json'
    if runner.raw.sha256_file(freeze_path) != FREEZE_SHA:
        raise ValueError('Task 2.26 benchmark freeze changed')
    freeze = json.loads(freeze_path.read_text())
    final = json.loads((previous / 'reports/finalization_manifest.json').read_text())
    if final['commit'] != BASE or final['benchmark_freeze_sha256'] != FREEZE_SHA:
        raise ValueError('Wrong Task 2.26 finalization')
    for name in (PROTOCOL, 'configs/third_party_hard_split_task2_26.json'):
        if runner.raw.sha256_file(paths.repository_root / name) != final['repository_files'][name]:
            raise ValueError('Frozen protocol/configuration changed: ' + name)
    verification_name = 'reports/completion_verification.json'
    if runner.raw.sha256_file(previous / verification_name) != final['run_artifacts'][verification_name]:
        raise ValueError('Saved curation verification changed')
    verification = json.loads((previous / verification_name).read_text())
    if verification['status'] != 'passed' or not verification['dependence_components_verified']:
        raise ValueError('Curation verification not passed')
    hashes, cohorts = {}, {}
    for threshold in ORDER:
        for suffix in ('identities', 'outcomes'):
            name = f'cohorts/hamming_ge_{threshold}_{suffix}.jsonl'
            actual = runner.raw.sha256_file(previous / name)
            if actual != freeze['immutable_artifact_hashes'][name] or actual != final['run_artifacts'][name]:
                raise ValueError('Frozen cohort changed: ' + name)
            hashes[name] = actual
        rows = read_rows(previous / f'cohorts/hamming_ge_{threshold}_identities.jsonl')
        n, _, patient_count, study_count = EXPECTED[threshold]
        if len(rows) != n or len({r['source_id'] for r in rows}) != n:
            raise ValueError('Cohort counts or unique source IDs changed')
        if [r['source_row_index'] for r in rows] != sorted(r['source_row_index'] for r in rows):
            raise ValueError('Original source order changed')
        for row in rows:
            if ('label' in row or 'raw_response' in row or len(row['peptide']) != 9
                    or not set(row['peptide']) <= set('ACDEFGHIKLMNPQRSTVWY')
                    or row['source_line_number'] != row['source_row_index']+1
                    or row['minimum_fitting_selection_distance'] < threshold
                    or row['exact_prior_published_benchmark_peptide']):
                raise ValueError('Frozen identity/eligibility invariant failed')
        for field, count in (('patient_peptide_component', patient_count), ('study_peptide_component', study_count)):
            if len({r[field] for r in rows}) != count:
                raise ValueError('Frozen dependence component count changed')
        cohorts[threshold] = rows
    union = {r['source_id']: r for r in cohorts[2]}
    for threshold in ORDER:
        # Threshold-specific connected components are intentionally different.
        for row in cohorts[threshold]:
            other = union[row['source_id']]
            if {k: v for k, v in row.items() if not k.endswith('_component')} != {
                    k: v for k, v in other.items() if not k.endswith('_component')}:
                raise ValueError('Nested cohort source/HLA/patient identity mismatch')
    return cohorts, {'benchmark_freeze_sha256': FREEZE_SHA, 'consumed_cohort_hashes': hashes,
                     'curation_verification_sha256': final['run_artifacts'][verification_name],
                     'curation_witness_checks_reused': verification['valid_nearest_reference_witnesses'],
                     'outcome_values_read': False, 'cohort_N': {t: len(r) for t, r in cohorts.items()}}


def preflight(paths: StoragePaths) -> dict:
    directory, started = begin(paths, 'preflight')
    command = [sys.executable, '-m', 'unittest', '-v',
               'tests.test_third_party_evaluation',
               'tests.test_bigmhc_independent_evaluation.MetricTests']
    tests = subprocess.run(command, cwd=paths.repository_root, capture_output=True, text=True)
    with (directory / 'logs/focused_tests.log').open('x') as stream:
        stream.write(tests.stdout + tests.stderr)
    if tests.returncode or 'skipped=' in tests.stderr:
        raise ValueError('Focused tests failed or skipped; see saved log')
    cohorts, receipt = authenticated_identities(paths)
    models, _ = gates.authenticate_models(paths, amendment_sha256=AMENDMENT_SHA)
    write_json(directory / 'reports/frozen_models.json', models)
    result = dict(receipt, status='passed_identity_and_synthetic_tests', utc=utc(),
                  scientific_hashes=software_hashes(paths), tests_command=command,
                  test_log_sha256=runner.raw.sha256_file(directory / 'logs/focused_tests.log'),
                  model_file_maps={a: models['models'][a]['file_map_sha256'] for a in ARMS},
                  cohort_orders={t: digest([r['source_id'] for r in rows]) for t, rows in cohorts.items()},
                  checkpoint_reload='required within the single inference pass before forward',
                  no_previous_IMPROVE_predictions_used=True,
                  bootstrap={'draws': DRAW_COUNT, 'patient_seed': 262742, 'study_seed': 262743,
                             'cohort_order': ORDER, 'component_order': 'lexicographically sorted frozen IDs',
                             'rng_for_single_component': 'draw normally in fixed order; no interval computed',
                             'implementation': 'integer observation multiplicities, equivalent to expanded rows'},
                  elapsed_seconds=time.monotonic()-started)
    write_json(directory / 'reports/preflight.json', result)
    return result


def require_receipt(paths: StoragePaths, directory: Path, name: str) -> dict:
    receipt = json.loads((directory / f'reports/{name}.json').read_text())
    if receipt['scientific_hashes'] != software_hashes(paths):
        raise ValueError('Scientific software changed after stage freeze')
    return receipt


def prediction_identity(row: dict) -> dict:
    return {key: row[key] for key in ('source_id', 'source_row_index', 'source_line_number',
            'source_row_sha256', 'original_observation_id', 'peptide', 'hla', 'study_DOI', 'patient')}


def inference(paths: StoragePaths) -> dict:
    directory = context(paths)
    require_receipt(paths, directory, 'preflight')
    cohorts, cohort_receipt = authenticated_identities(paths)
    rows = cohorts[2]
    directory, started = begin(paths, 'inference')
    models_receipt, context_models = gates.authenticate_models(paths, amendment_sha256=AMENDMENT_SHA)
    import numpy as np
    import torch
    runner.seed_runtime(torch, np, RUNTIME)
    device = runner.runtime_device(torch, RUNTIME)
    needed, encodings = {r['hla'] for r in rows}, {}
    with context_models['files']['reference'].open(newline='') as stream:
        reference = csv.reader(stream)
        next(reference)
        for record in reference:
            hla = runner.data.canonical_hla(record[0])
            if hla in needed:
                if hla in encodings:
                    raise ValueError('Ambiguous exact HLA mapping')
                encodings[hla] = torch.tensor([int(x) for x in record[1:]], dtype=torch.int8)
    if set(encodings) != needed:
        raise ValueError('Missing exact HLA encoding')
    arms = {}
    with runner.pinned_modules(context_models['files']) as (BigMHC, Dataset):
        for arm in ARMS:
            print(f'{utc()} loading {arm}; {len(rows)} immutable union rows', flush=True)
            arm_started = time.monotonic()
            identity = context_models['models'][arm]
            model = runner.load_checkpoint(torch, BigMHC, identity['directory'], identity['keys'], device=device)
            if runner.state_hashes(model) != identity['state']:
                raise ValueError('Strict checkpoint tensor reload failed')
            if any(t.dtype != torch.float32 for t in model.state_dict().values()) or any(
                    m._forward_hooks for m in model.modules()):
                raise ValueError('Expected FP32 native IM model without auxiliary hooks')
            inputs = [{'hla': r['hla'], 'peptide': r['peptide'], 'original_label': '0'} for r in rows]
            frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(inputs)), allele=0, pepcol=1,
                                     tgtcol=2, hdrcnt=1, verbose=False)
            if list(frame['pep']) != [r['peptide'] for r in rows] or list(frame['mhc']) != [r['hla'] for r in rows]:
                raise ValueError('Native transformation changed ordered peptide/HLA identities')
            frame['_source_row_index'] = [r['source_row_index'] for r in rows]
            native = Dataset(frame, mhcenc=encodings)
            torch.cuda.synchronize()
            scores = runner.predict(torch, model, native, 16, device)
            torch.cuda.synchronize()
            emitted = [int(i) for b in range(len(native)) for i in native.getbat(b, enc=False)['_source_row_index']]
            if emitted != [r['source_row_index'] for r in rows] or len(scores) != len(rows):
                raise ValueError('Prediction/source row alignment failed')
            if not all(isinstance(s, float) and np.isfinite(s) and 0 <= s <= 1 for s in scores):
                raise ValueError('Missing/nonfinite/out-of-range probabilities')
            if runner.state_hashes(model) != identity['state']:
                raise ValueError('Inference changed backbone tensors')
            output = directory / f'predictions/{arm}.jsonl'
            write_rows(output, (dict(prediction_identity(r), probability=s) for r, s in zip(rows, scores, strict=True)))
            arms[arm] = {'N': len(rows), 'ordered_source_ids_sha256': digest([r['source_id'] for r in rows]),
                         'input_identity_sha256': digest([(r['hla'], r['peptide']) for r in rows]),
                         'prediction_sha256': runner.raw.sha256_file(output), 'native_batches': len(native),
                         'strict_reload_identical': True, 'parameters_unchanged': True,
                         'checkpoint_map_sha256': models_receipt['models'][arm]['file_map_sha256'],
                         'auxiliary_head_loaded': False, 'finite_FP32_probabilities': True,
                         'elapsed_seconds': time.monotonic()-arm_started}
            write_json(directory / f'reports/{arm}_inference.json', arms[arm])
            print(f'{utc()} frozen {arm} in {arms[arm]["elapsed_seconds"]:.3f}s', flush=True)
            del model
    result = {'status': 'all_predictions_frozen_before_outcomes', 'arms': arms,
              'cohort_reference': cohort_receipt, 'frozen_utc': utc(),
              'scientific_hashes': software_hashes(paths), 'outcomes_opened': False,
              'training_executed': False, 'target_field': 'constant zero placeholder',
              'HLA_coverage': len(encodings), 'runtime_configuration': RUNTIME,
              'runtime': {'Python': platform.python_version(), 'platform': platform.platform(),
                          'Torch': torch.__version__, 'NumPy': np.__version__,
                          **runner.device_report(torch, device),
                          'deterministic': torch.are_deterministic_algorithms_enabled(),
                          'TF32_matmul': torch.backends.cuda.matmul.allow_tf32,
                          'TF32_cudnn': torch.backends.cudnn.allow_tf32,
                          'autocast_enabled': torch.is_autocast_enabled(), 'cpu_threads': torch.get_num_threads()},
              'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(),
              'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(),
              'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              'elapsed_seconds': time.monotonic()-started}
    write_json(directory / 'reports/predictions_frozen.json', result)
    return result


def rank_key(row: dict, arm: str) -> tuple:
    return (-row['scores'][arm], row['peptide'], row['hla'], row['study_DOI'], row['patient'], row['source_id'])


class WeightedRanking:
    """Exact integer row multiplicities implement the expanded cluster sample.

    Fixed score groups retain all exact ties. Zero-weight rows/groups contribute
    nothing. Top-K consumes repeated rows in the frozen deterministic ordering.
    """
    def __init__(self, rows: list[dict], arm: str):
        import numpy as np
        self.order = np.array(sorted(range(len(rows)), key=lambda i: rank_key(rows[i], arm)), dtype=np.int64)
        scores = np.array([rows[i]['scores'][arm] for i in self.order], dtype=np.float64)
        self.labels = np.array([rows[i]['label'] for i in self.order], dtype=np.int64)
        self.starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1])+1] if len(rows) else np.array([], dtype=np.int64)

    def metrics(self, weights, *, top_k: bool) -> dict:
        import numpy as np
        weights = np.asarray(weights, dtype=np.int64)[self.order]
        n_all = int(weights.sum())
        positives = int((weights*self.labels).sum())
        negatives = n_all-positives
        prevalence = positives/n_all if n_all else None
        result = {'AP': None, 'AUROC': None, 'prevalence': prevalence,
                  'AP_minus_prevalence': None, 'AP_over_prevalence': None}
        if top_k:
            result.update(precision_at_10=None, precision_at_20=None)
        if not positives or not negatives:
            return result
        group_n = np.add.reduceat(weights, self.starts)
        group_p = np.add.reduceat(weights*self.labels, self.starts)
        tp = np.cumsum(group_p)
        seen = np.cumsum(group_n)
        active = group_p > 0
        ap = float(np.sum((group_p[active]/positives)*(tp[active]/seen[active])))
        group_neg = group_n-group_p
        fp = seen-tp
        auc = float(np.sum(group_p*(negatives-fp+group_neg/2))/(positives*negatives))
        result.update(AP=ap, AUROC=auc, AP_minus_prevalence=ap-prevalence, AP_over_prevalence=ap/prevalence)
        if top_k:
            before = np.cumsum(weights)-weights
            for k in (10, 20):
                if n_all >= k:
                    taken = np.minimum(weights, np.maximum(0, k-before))
                    result['precision_at_'+str(k)] = float((taken*self.labels).sum()/k)
        return result


def values(rankings: dict[str, WeightedRanking], weights, threshold: int) -> dict:
    arms = {a: rankings[a].metrics(weights, top_k=threshold == 3) for a in ARMS}
    return {'arms': arms, 'contrasts': contrasts(arms)}


def tie_report(rows: list[dict], arm: str, *, top_k: bool) -> dict:
    groups = Counter(r['scores'][arm] for r in rows)
    result = {'tied_score_groups': sum(n > 1 for n in groups.values()),
              'observations_in_ties': sum(n for n in groups.values() if n > 1)}
    if top_k:
        ordered = sorted(rows, key=lambda r: rank_key(r, arm))
        result['top_k_boundary'] = {str(k): {'score': ordered[k-1]['scores'][arm],
            'tie_group_size': groups[ordered[k-1]['scores'][arm]],
            'crosses_boundary': len(rows) > k and ordered[k]['scores'][arm] == ordered[k-1]['scores'][arm]}
            if len(rows) >= k else {'defined': False} for k in (10, 20)}
    return result


def paired_bootstrap(cohorts: dict[int, list[dict]], rankings: dict[int, dict[str, WeightedRanking]],
                     field: str, seed: int, *, draws: int = DRAW_COUNT, evidence: Path | None = None) -> dict:
    """Prescribed paired components; no interval for fewer than two units.

    Draw-major/cohort-minor Random.randrange calls include single-unit cohorts,
    preserving the fixed RNG order even when their intervals are unavailable.
    """
    import numpy as np
    rng = random.Random(seed)
    prepared, samples = {}, {t: defaultdict(list) for t in ORDER}
    for threshold in ORDER:
        ids = sorted({r[field] for r in cohorts[threshold]})
        indices = {key: i for i, key in enumerate(ids)}
        prepared[threshold] = (ids, np.array([indices[r[field]] for r in cohorts[threshold]], dtype=np.int64))
    stream = gzip.open(evidence, 'xt') if evidence else None
    try:
        for draw in range(draws):
            evidence_row = {'draw': draw, 'cohorts': {}}
            for threshold in ORDER:
                ids, indices = prepared[threshold]
                picked = [rng.randrange(len(ids)) for _ in ids]
                counts = np.bincount(picked, minlength=len(ids))
                weights = counts[indices]
                evidence_row['cohorts'][threshold] = {'component_multiplicities': counts.tolist(),
                                                      'N': int(weights.sum())}
                if len(ids) < 2:
                    continue
                metrics = values(rankings[threshold], weights, threshold)
                for kind in ('arms', 'contrasts'):
                    for arm, endpoints in metrics[kind].items():
                        for metric, value in endpoints.items():
                            key = (kind, arm, metric)
                            samples[threshold][key]  # retain undefined endpoint metadata
                            if value is not None:
                                samples[threshold][key].append(value)
            if stream:
                stream.write(json.dumps(evidence_row, separators=(',', ':'))+'\n')
            if (draw+1) % 1000 == 0:
                print(f'{utc()} {field}: {draw+1}/{draws} paired draws', flush=True)
    finally:
        if stream:
            stream.close()
    result = {}
    for threshold in ORDER:
        ids, _ = prepared[threshold]
        result[threshold] = {'components': len(ids), 'component_order': ids,
                             'arms': {}, 'contrasts': {},
                             'intervals_available': len(ids) >= 2,
                             'reason': 'fewer than two independent components' if len(ids) < 2 else None}
        for (kind, arm, metric), sample in samples[threshold].items():
            result[threshold][kind].setdefault(arm, {})[metric] = {
                'lower_95': quantile(sample, .025), 'upper_95': quantile(sample, .975),
                'usable_draws': len(sample), 'undefined_draws': draws-len(sample),
                'unreliable': len(ids) < 20 or len(sample) < 1000}
    return {'draws': draws, 'seed': seed, 'field': field, 'cohort_order': ORDER,
            'resampling': 'fixed number of frozen components with replacement; paired integer row multiplicities',
            'percentiles': 'linear interpolation at (n-1)q; q=.025/.975', 'cohorts': result}


def evaluate(paths: StoragePaths) -> dict:
    directory = context(paths)
    receipt = require_receipt(paths, directory, 'predictions_frozen')
    if receipt['outcomes_opened'] or receipt['status'] != 'all_predictions_frozen_before_outcomes':
        raise ValueError('Predictions not frozen before outcomes')
    cohorts, cohort_receipt = authenticated_identities(paths)
    score_maps = {}
    for arm in ARMS:
        path = directory / f'predictions/{arm}.jsonl'
        if runner.raw.sha256_file(path) != receipt['arms'][arm]['prediction_sha256']:
            raise ValueError('Predictions changed')
        rows = read_rows(path)
        if [{k: v for k, v in r.items() if k != 'probability'} for r in rows] != [prediction_identity(r) for r in cohorts[2]]:
            raise ValueError('Frozen prediction/source identity mismatch')
        score_maps[arm] = {r['source_id']: r['probability'] for r in rows}
    directory, started = begin(paths, 'evaluation')
    write_json(directory / 'reports/outcome_association_started.json', {
        'utc': utc(), 'predictions_frozen_utc': receipt['frozen_utc'],
        'all_prediction_hashes_verified': True, 'cohort_reference': cohort_receipt})
    from .third_party_hard_split import describe
    import numpy as np
    point, rankings = {}, {}
    for threshold in ORDER:
        outcomes = read_rows(paths.project_runs_dir / PREVIOUS / f'cohorts/hamming_ge_{threshold}_outcomes.jsonl')
        rows = cohorts[threshold]
        if [r['source_id'] for r in rows] != [r['source_id'] for r in outcomes]:
            raise ValueError('Frozen outcome association differs')
        for row, outcome in zip(rows, outcomes, strict=True):
            if outcome['label'] not in (0, 1) or outcome['raw_response'].lower() not in ('yes', 'no', '0', '1'):
                raise ValueError('Nonbinary frozen outcome')
            row.update(label=outcome['label'], raw_response=outcome['raw_response'],
                       scores={a: score_maps[a][row['source_id']] for a in ARMS})
        if sum(r['label'] for r in rows) != EXPECTED[threshold][1]:
            raise ValueError('Frozen class counts changed')
        rankings[threshold] = {a: WeightedRanking(rows, a) for a in ARMS}
        point[threshold] = dict(values(rankings[threshold], np.ones(len(rows), dtype=np.int64), threshold),
                                population=describe(rows),
                                random_ranking_AP_reference=sum(r['label'] for r in rows)/len(rows),
                                very_limited=len(rows) < 20 or min(sum(r['label'] for r in rows), sum(1-r['label'] for r in rows)) < 5,
                                ties={a: tie_report(rows, a, top_k=threshold == 3) for a in ARMS})
        # Compact joined evidence retains all frozen source/cluster associations.
        write_rows(directory / f'evaluation/hamming_ge_{threshold}_joined.jsonl', (
            dict(prediction_identity(r), label=r['label'], raw_response=r['raw_response'], scores=r['scores'],
                 patient_peptide_component=r['patient_peptide_component'],
                 study_peptide_component=r['study_peptide_component']) for r in rows))
    write_json(directory / 'evaluation/point_metrics.json', point)
    patient = paired_bootstrap(cohorts, rankings, 'patient_peptide_component', 262742,
                              evidence=directory / 'evaluation/patient_component_draws.jsonl.gz')
    write_json(directory / 'evaluation/patient_peptide_uncertainty.json', patient)
    study = paired_bootstrap(cohorts, rankings, 'study_peptide_component', 262743,
                            evidence=directory / 'evaluation/study_component_draws.jsonl.gz')
    write_json(directory / 'evaluation/study_peptide_uncertainty.json', study)
    result = {'status': 'single_frozen_evaluation_complete', 'utc': utc(),
              'scientific_hashes': software_hashes(paths), 'primary_threshold': 3,
              'draws_per_analysis': DRAW_COUNT, 'outcomes_joined_after_all_predictions_frozen': True,
              'training_executed': False, 'tuning_executed': False, 'cohort_changes': False,
              'elapsed_seconds': time.monotonic()-started,
              'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              'output_hashes': {str(p.relative_to(directory)): runner.raw.sha256_file(p)
                                for p in sorted((directory / 'evaluation').iterdir())}}
    write_json(directory / 'reports/evaluation_complete.json', result)
    return result


def verify(paths: StoragePaths) -> dict:
    """Focused evidence verification only; never repeat scores or metrics."""
    directory = context(paths)
    completion = require_receipt(paths, directory, 'evaluation_complete')
    inference_receipt = require_receipt(paths, directory, 'predictions_frozen')
    cohorts, _ = authenticated_identities(paths)
    for name, expected in completion['output_hashes'].items():
        if runner.raw.sha256_file(directory / name) != expected:
            raise ValueError('Evaluation output changed')
    for arm in ARMS:
        if runner.raw.sha256_file(directory / f'predictions/{arm}.jsonl') != inference_receipt['arms'][arm]['prediction_sha256']:
            raise ValueError('Prediction changed')
    associated = json.loads((directory / 'reports/outcome_association_started.json').read_text())
    if associated['utc'] <= inference_receipt['frozen_utc']:
        raise ValueError('Outcome/prediction chronology failed')
    models, _ = gates.authenticate_models(paths, amendment_sha256=AMENDMENT_SHA)
    metrics = json.loads((directory / 'evaluation/point_metrics.json').read_text())
    for threshold, identities in cohorts.items():
        joined = read_rows(directory / f'evaluation/hamming_ge_{threshold}_joined.jsonl')
        if [prediction_identity(r) for r in joined] != [prediction_identity(r) for r in identities]:
            raise ValueError('Saved joined row identities changed')
        if metrics[str(threshold)]['population']['N'] != len(identities):
            raise ValueError('Population metadata mismatch')
    result = {'status': 'passed', 'utc': utc(), 'no_inference_or_metrics_repeated': True,
              'frozen_model_maps_preserved': {a: models['models'][a]['file_map_sha256'] for a in ARMS},
              'ordered_cohorts_and_prediction_hashes_preserved': True,
              'all_predictions_preceded_outcome_join': True, 'scientific_hashes': software_hashes(paths)}
    write_json(directory / 'reports/completion_verification.json', result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('preflight', 'inference', 'evaluate', 'verify'))
    args = parser.parse_args()
    result = globals()[args.stage](resolve_paths())
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
