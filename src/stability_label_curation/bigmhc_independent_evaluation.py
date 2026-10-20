"""One frozen, researcher-amended Task 2.25R A/S/P evaluation.

Stages are exclusive immutable writes: identity eligibility, inference without
outcomes, then outcome association/point estimates/one paired cluster bootstrap.
No training, selection, downloads, calibration or similarity exclusions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import random
import resource
import subprocess
import time
from typing import Any, Iterable
import zipfile

from . import bigmhc_independent_preflight as gates
from . import bigmhc_baseline_runner as runner
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/bigmhc_independent_task2_25R.json'
COHORTS = ('primary', 'IM_novel', 'EL_exposed')
ARMS = ('A', 'S', 'P')
CONTRASTS = (('S-A', 'S', 'A'), ('S-P', 'S', 'P'), ('P-A', 'P', 'A'))
ALPHABET = frozenset('ACDEFGHIKLMNPQRSTVWY')


def normalize(peptide: str) -> str:
    return peptide.strip().upper()


def valid_ninemer(peptide: str) -> bool:
    return len(peptide) == 9 and set(peptide) <= ALPHABET


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def write_rows(path: Path, rows: Iterable[dict]) -> None:
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def read_rows(path: Path) -> list[dict]:
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def git(paths: StoragePaths, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()


def context(paths: StoragePaths) -> tuple[Path, dict]:
    config = json.loads((paths.repository_root / CONFIG).read_text())
    if (config['task'] != '2.25R' or config['training_authorized'] or not config['evaluation_authorized']
            or config['bootstrap_draws'] != 10000 or config['bootstrap_seed'] != 24242
            or config['top_k'] != [10, 20] or config['source_member'] != 'im_test.csv'
            or config['bootstrap_cohort_order'] != list(COHORTS)):
        raise ValueError('Frozen amended configuration changed')
    if git(paths, 'branch', '--show-current') != 'task/2.25-independent-neoepitope-evaluation':
        raise ValueError('Wrong task branch')
    subprocess.run(['git', 'merge-base', '--is-ancestor', config['amendment_commit'], 'HEAD'], cwd=paths.repository_root, check=True)
    committed = subprocess.check_output(['git', 'show', config['amendment_commit'] + ':' + gates.PROTOCOL], cwd=paths.repository_root)
    if hashlib.sha256(committed).hexdigest() != config['protocol_sha256']:
        raise ValueError('Amendment was not committed exactly')
    if runner.raw.sha256_file(paths.repository_root / gates.PROTOCOL) != config['protocol_sha256']:
        raise ValueError('Amended protocol changed')
    return paths.project_runs_dir / gates.RUN_ID / 'resumed', config


def software_hashes(paths: StoragePaths) -> dict[str, str]:
    return {name: runner.raw.sha256_file(paths.repository_root / name) for name in (
        CONFIG, gates.PROTOCOL, 'src/stability_label_curation/bigmhc_independent_evaluation.py',
        'src/stability_label_curation/bigmhc_independent_preflight.py',
        'tests/test_bigmhc_independent_evaluation.py')}


def begin(paths: StoragePaths, stage: str, directory: Path, config: dict) -> float:
    if git(paths, 'status', '--porcelain'):
        raise ValueError('Execution requires a clean committed worktree')
    write_json(directory / 'reports' / (stage + '_started.json'), {
        'started_utc': datetime.now(timezone.utc).isoformat(), 'commit': git(paths, 'rev-parse', 'HEAD'),
        'amendment_commit': config['amendment_commit'], 'configuration': config,
        'scientific_hashes': software_hashes(paths), 'training_authorized': False})
    return time.monotonic()


def source_identities(stream: Any) -> list[dict]:
    """Project only the first two CSV fields; discard the opaque outcome tail.

    The exact release uses simple unquoted HLA/peptide fields and one line per
    row. No tgt/predictor token is parsed, decoded, returned or inspected here.
    """
    header = stream.readline().decode('utf-8-sig').rstrip('\r\n').split(',')
    if header[:3] != ['mhc', 'pep', 'tgt']:
        raise ValueError('Identity projection requires exact published prefix')
    result = []
    for index, line in enumerate(stream, 1):
        first, separator, rest = line.partition(b',')
        second, separator2, _opaque_tail = rest.partition(b',')
        if not separator or not separator2 or b'"' in first + second or b'\r' in first + second:
            raise ValueError('Unsupported identity prefix; no outcome-based repair')
        raw_hla, raw_peptide = first.decode('utf-8'), second.decode('utf-8')
        result.append({'row_index': index, 'source_line_number': index + 1,
                       'source_id': f'im_test.csv:row:{index:012d}',
                       'raw_hla': raw_hla, 'raw_peptide': raw_peptide,
                       'hla': runner.data.canonical_hla(raw_hla.strip()), 'peptide': normalize(raw_peptide)})
    return result


def classify(row: dict, supported: set[str]) -> dict:
    """All flags and sequential exclusions are independent of outcomes/scores."""
    flags = []
    if not valid_ninemer(row['peptide']):
        flags.append('invalid_or_non_ninemer')
    if row['hla'] not in supported:
        flags.append('unsupported_or_ambiguous_HLA')
    if row['EL_train_peptide']:
        flags.append('EL_training_peptide_overlap')
    if row['IM_train_peptide']:
        flags.append('IM_training_peptide_overlap')
    common = valid_ninemer(row['peptide']) and row['hla'] in supported
    return dict(row, exclusion_flags=flags, primary_first_exclusion=flags[0] if flags else None,
                primary=common and not row['EL_train_peptide'] and not row['IM_train_peptide'],
                IM_novel=common and not row['IM_train_peptide'],
                EL_exposed=common and not row['IM_train_peptide'] and row['EL_train_peptide'],
                cluster_id=row['peptide'])


def population(rows: list[dict], *, outcomes: bool = False) -> dict:
    peptides = Counter(r['peptide'] for r in rows)
    pairs = Counter((r['peptide'], r['hla']) for r in rows)
    result = {'N': len(rows), 'unique_peptides': len(peptides), 'unique_pairs': len(pairs),
              'peptide_clusters': len(peptides), 'duplicate_peptide_excess_rows': sum(n-1 for n in peptides.values()),
              'duplicate_pair_excess_rows': sum(n-1 for n in pairs.values()),
              'repeated_peptide_groups': sum(n > 1 for n in peptides.values()),
              'repeated_pair_groups': sum(n > 1 for n in pairs.values()),
              'HLA_counts': dict(sorted(Counter(r['hla'] or r['raw_hla'] for r in rows).items())),
              'assay_count': None, 'patient_count': None,
              'assay_and_patient_identifiers_unavailable': True}
    if outcomes:
        p = sum(r['label'] for r in rows)
        result.update(positive=p, negative=len(rows)-p, prevalence=p/len(rows) if rows else None,
                      random_ranking_AP_baseline=p/len(rows) if rows else None,
                      very_limited=len(rows) < 20 or min(p, len(rows)-p) < 5,
                      cluster_uncertainty_unreliable=len(peptides) < 20)
    return result


def eligibility(paths: StoragePaths) -> dict:
    directory, config = context(paths)
    directory.mkdir(exist_ok=False)
    for name in ('reports', 'cohorts', 'predictions', 'logs'):
        (directory / name).mkdir()
    started = begin(paths, 'eligibility', directory, config)
    models, _ = gates.authenticate_models(paths, amendment_sha256=config['protocol_sha256'])
    write_json(directory / 'reports/frozen_models.json', models)
    schema = gates.inspect_source_schema(paths)
    write_json(directory / 'reports/source_identity.json', schema)
    # Preserve exact amendment bytes, original blocked-stage receipts stay untouched.
    with (directory / 'reports/protocol_amended.md').open('x') as stream:
        stream.write((paths.repository_root / gates.PROTOCOL).read_text())
    with zipfile.ZipFile(paths.project_data_dir / 'bigmhc_v4/datasets.zip') as archive:
        with archive.open(config['source_member']) as stream:
            rows = source_identities(stream)
    candidates = {r['peptide'] for r in rows}
    train_config = json.loads((paths.repository_root / 'configs/bigmhc_fully_trained_auxiliary_task2_24.json').read_text())
    resolved, input_hashes = {}, {}
    for name in ('EL', 'EL_split', 'IM', 'reference'):
        item = train_config['inputs'][name]
        path = (paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir) / item['relative_path']
        if runner.raw.sha256_file(path) != item['sha256']:
            raise ValueError('Actual training inventory hash mismatch: ' + name)
        resolved[name] = path
        input_hashes[name] = item
    with resolved['reference'].open(newline='') as stream:
        reference, _, mapping = runner.data._reference(enumerate(csv.reader(stream, strict=True), 1))
    if (reference['feature_count'] != 414 or reference['invalid_one_hot_rows']
            or reference['duplicate_identifier_count'] or reference['sanitized_UID_collision_groups']):
        raise ValueError('Invalid exact HLA mapping')
    supported = {hla for hla, names in mapping.items() if len(names) == 1}
    exposure: dict[str, set] = defaultdict(set)
    partitions, classes, unique_train = Counter(), Counter(), set()
    with gzip.open(resolved['EL_split'], 'rt', newline='') as ledger, resolved['EL'].open(newline='') as stream:
        original = csv.DictReader(stream)
        for index, (record, original_row) in enumerate(zip(csv.DictReader(ledger), original, strict=True), 1):
            peptide, hla = normalize(record['peptide']), record['HLA']
            if (int(record['original_prepared_row_index']) != index
                    or (peptide, hla, record['original_label']) !=
                    (normalize(original_row['pep']), original_row['mhc'], original_row['tgt'])):
                raise ValueError('Actual EL training manifest join failed')
            partition = record['partition']
            partitions[partition] += 1
            if partition == 'train':
                unique_train.add(peptide)
                classes[record['original_label']] += 1
            if peptide in candidates:
                exposure['EL_' + partition + '_peptide'].add(peptide)
                exposure['EL_' + partition + '_pair'].add((peptide, hla))
                if record['original_label'] == '1':
                    exposure['EL_' + partition + '_positive_peptide'].add(peptide)
    if (partitions != {'train': 1308196, 'validation': 145371, 'excluded': 11}
            or len(unique_train) != 1122528 or classes != {'1': 63053, '0': 1245143}):
        raise ValueError('Actual EL population differs from frozen population')
    im_rows = 0
    with resolved['IM'].open(newline='') as stream:
        for record in csv.DictReader(stream):
            im_rows += 1
            peptide = normalize(record['pep'])
            if peptide in candidates:
                exposure['IM_train_peptide'].add(peptide)
                exposure['IM_train_pair'].add((peptide, record['mhc']))
    if im_rows != 3428:
        raise ValueError('Full original IM population changed')
    # Descriptive historical development exposure only; never used for eligibility.
    historical_config = json.loads((paths.repository_root / 'configs/bigmhc_gpu_baseline_task2_10.json').read_text())
    item = historical_config['inputs']['development']
    path = paths.project_runs_dir / item['relative_path']
    if runner.raw.sha256_file(path) != item['sha256']:
        raise ValueError('Historical identity inventory changed')
    input_hashes['historical_development'] = item
    with path.open(newline='') as stream:
        for record in csv.DictReader(stream):
            peptide = normalize(record['pep'])
            if peptide in candidates:
                exposure['development_peptide'].add(peptide)
                exposure['development_pair'].add((peptide, record['mhc']))
    flags = [f'{stage}_{unit}' for stage in ('EL_train', 'EL_validation', 'EL_excluded', 'IM_train', 'development')
             for unit in ('peptide', 'pair')]
    for row in rows:
        for flag in flags:
            row[flag] = (row['peptide'] if flag.endswith('_peptide') else (row['peptide'], row['hla'])) in exposure[flag]
        row['EL_train_positive_peptide'] = row['peptide'] in exposure['EL_train_positive_peptide']
        row['full_EL_peptide'] = any(row[k + '_peptide'] for k in ('EL_train', 'EL_validation', 'EL_excluded'))
        row['full_EL_pair'] = any(row[k + '_pair'] for k in ('EL_train', 'EL_validation', 'EL_excluded'))
    rows = [classify(row, supported) for row in rows]
    write_rows(directory / 'cohorts/all_source_identities.jsonl', rows)
    write_rows(directory / 'cohorts/exclusions.jsonl', (r for r in rows if not r['primary']))
    for cohort in COHORTS:
        write_rows(directory / f'cohorts/{cohort}.jsonl', (r for r in rows if r[cohort]))
    summary = {'status': 'eligibility_frozen_without_outcomes', 'source': population(rows),
               'valid_canonical_ninemers': sum(valid_ninemer(r['peptide']) for r in rows),
               'nine_residue_length_rows': sum(len(r['peptide']) == 9 for r in rows),
               'cohorts': {c: population([r for r in rows if r[c]]) for c in COHORTS},
               'primary_sequential_exclusions': dict(Counter(r['primary_first_exclusion'] for r in rows if not r['primary'])),
               'overlapping_exclusion_counts': dict(Counter(f for r in rows for f in r['exclusion_flags'])),
               'overlaps_all_source': {f: {'observations': sum(r[f] for r in rows),
                   'unique_peptides': len({r['peptide'] for r in rows if r[f]}),
                   'unique_pairs': len({(r['peptide'], r['hla']) for r in rows if r[f]})}
                   for f in flags + ['full_EL_peptide', 'full_EL_pair', 'EL_train_positive_peptide']},
               'actual_training_inventory': {'EL_partitions': dict(partitions), 'EL_train_unique_peptides': len(unique_train),
                                            'EL_train_classes': dict(classes), 'IM_rows': im_rows, 'inputs': input_hashes},
               'unsupported_HLAs': dict(Counter(r['raw_hla'] for r in rows if r['hla'] not in supported)),
               'Teacher_fit_source_exposure': 'Not established; EL-train-positive prediction-input overlap reported separately',
               'patient_and_original_assay_provenance': 'Unavailable; explicitly approved released-row amendment',
               'bootstrap_clusters': 'canonical peptide; no patient identifiers',
               'elapsed_seconds': time.monotonic() - started, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
               'outcomes_opened': False, 'predictions_generated': False, 'scientific_hashes': software_hashes(paths)}
    summary['manifest_hashes'] = {str(f.relative_to(directory)): runner.raw.sha256_file(f) for f in sorted((directory / 'cohorts').iterdir())}
    write_json(directory / 'reports/eligibility_frozen.json', summary)
    return summary


def frozen_cohorts(paths: StoragePaths, directory: Path) -> tuple[list[dict], dict]:
    frozen = json.loads((directory / 'reports/eligibility_frozen.json').read_text())
    if frozen['scientific_hashes'] != software_hashes(paths):
        raise ValueError('Scientific code/config changed after eligibility freeze')
    for name, expected in frozen['manifest_hashes'].items():
        if runner.raw.sha256_file(directory / name) != expected:
            raise ValueError('Frozen eligible identities changed')
    return read_rows(directory / 'cohorts/IM_novel.jsonl'), frozen


def predictions(paths: StoragePaths) -> dict:
    directory, config = context(paths)
    rows, frozen = frozen_cohorts(paths, directory)
    tests = json.loads((directory / 'reports/focused_tests.json').read_text())
    if tests['status'] != 'passed' or tests['skips'] or tests['scientific_hashes'] != software_hashes(paths):
        raise ValueError('Focused tests missing or changed')
    started = begin(paths, 'inference', directory, config)
    receipt, context_models = gates.authenticate_models(paths, amendment_sha256=config['protocol_sha256'])
    import numpy as np
    import torch
    runner.seed_runtime(torch, np, config)
    device = runner.runtime_device(torch, config)
    encodings = {}
    needed = {r['hla'] for r in rows}
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
        raise ValueError('Missing exact HLA mapping')
    arms = {}
    with runner.pinned_modules(context_models['files']) as (BigMHC, Dataset):
        for arm in ARMS:
            arm_started = time.monotonic()
            identity = context_models['models'][arm]
            model = runner.load_checkpoint(torch, BigMHC, identity['directory'], identity['keys'], device=device)
            if runner.state_hashes(model) != identity['state']:
                raise ValueError('Strict checkpoint reload failed: ' + arm)
            if any(t.dtype != torch.float32 for t in model.state_dict().values()) or any(m._forward_hooks for m in model.modules()):
                raise ValueError('Expected FP32 plain IM backbone without hooks')
            input_rows = [{'hla': r['hla'], 'peptide': r['peptide'], 'original_label': '0'} for r in rows]
            frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(input_rows)), allele=0, pepcol=1, tgtcol=2, hdrcnt=1, verbose=False)
            if list(frame['pep']) != [r['peptide'] for r in rows]:
                raise ValueError('Native input transformation reordered peptide identities')
            frame['_source_row_index'] = [r['row_index'] for r in rows]
            native = Dataset(frame, mhcenc=encodings)
            torch.cuda.synchronize()
            scores = runner.predict(torch, model, native, config['batch_size'], device)
            torch.cuda.synchronize()
            emitted = [int(index) for b in range(len(native)) for index in native.getbat(b, enc=False)['_source_row_index']]
            if emitted != [r['row_index'] for r in rows] or len(scores) != len(rows):
                raise ValueError('Native prediction/source association mismatch')
            if any(not isinstance(s, float) or not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
                raise ValueError('Nonfinite or malformed FP32 probability')
            if runner.state_hashes(model) != identity['state']:
                raise ValueError('Inference modified checkpoint tensors')
            predicted = [dict(r, probability=s) for r, s in zip(rows, scores, strict=True)]
            write_rows(directory / f'predictions/{arm}.jsonl', predicted)
            arms[arm] = {'N': len(rows), 'primary_N': sum(r['primary'] for r in rows),
                         'ordered_source_ids_sha256': digest([r['source_id'] for r in rows]),
                         'input_identity_sha256': digest([(r['hla'], r['peptide']) for r in rows]),
                         'strict_reload_identical': True, 'parameters_unchanged_after_inference': True,
                         'checkpoint_map_sha256': receipt['models'][arm]['file_map_sha256'],
                         'prediction_sha256': runner.raw.sha256_file(directory / f'predictions/{arm}.jsonl'),
                         'native_batches': len(native), 'elapsed_seconds': time.monotonic()-arm_started,
                         'finite_FP32_probabilities': True, 'auxiliary_head_loaded': False}
            write_json(directory / f'reports/{arm}_inference.json', arms[arm])
            del model
    result = {'status': 'all_predictions_frozen_before_outcomes', 'arms': arms,
              'eligibility_manifest_hashes': frozen['manifest_hashes'],
              'runtime': {'Python': platform.python_version(), 'platform': platform.platform(),
                          'Torch': torch.__version__, 'NumPy': np.__version__, **runner.device_report(torch, device),
                          'deterministic': torch.are_deterministic_algorithms_enabled(),
                          'TF32_matmul': torch.backends.cuda.matmul.allow_tf32, 'TF32_cudnn': torch.backends.cudnn.allow_tf32,
                          'autocast_enabled': torch.is_autocast_enabled(), 'cpu_threads': torch.get_num_threads()},
              'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(),
              'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(),
              'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'elapsed_seconds': time.monotonic()-started, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
              'scientific_hashes': software_hashes(paths), 'outcomes_opened': False,
              'training_executed': False, 'target_field': 'constant zero placeholder; never used for eval-mode prediction'}
    write_json(directory / 'reports/predictions_frozen.json', result)
    return result


def ranking_metrics(rows: list[dict], arm: str, *, top_k: bool = False) -> dict:
    """Non-interpolated tie-grouped AP and half-credit tie AUROC."""
    p = sum(r['label'] for r in rows)
    n = len(rows)-p
    endpoints = {'AP': None, 'AUROC': None}
    if top_k:
        endpoints.update(precision_at_10=None, precision_at_20=None)
    # Frozen protocol: either class absent -> counts, no discriminative comparison.
    if not p or not n:
        return endpoints
    ordered = sorted(rows, key=lambda r: (-r['scores'][arm], r['peptide'], r['hla'], r['source_id']))
    tp = fp = 0
    ap = concordant = 0.0
    i = 0
    while i < len(ordered):
        j = i+1
        while j < len(ordered) and ordered[j]['scores'][arm] == ordered[i]['scores'][arm]:
            j += 1
        positive = sum(r['label'] for r in ordered[i:j])
        negative = j-i-positive
        concordant += positive * (n-fp-negative + negative/2)
        tp += positive
        fp += negative
        ap += (positive/p) * (tp/(tp+fp))
        i = j
    endpoints.update(AP=ap, AUROC=concordant/(p*n))
    if top_k:
        for k in (10, 20):
            if len(rows) >= k:
                endpoints['precision_at_' + str(k)] = sum(r['label'] for r in ordered[:k])/k
    return endpoints


def contrasts(arms: dict[str, dict]) -> dict:
    return {name: {metric: arms[left][metric]-arms[right][metric]
                   if arms[left][metric] is not None and arms[right][metric] is not None else None
                   for metric in arms[left]} for name, left, right in CONTRASTS}


def endpoints(rows: list[dict], cohort: str) -> dict:
    if cohort == 'EL_exposed' and (len(rows) < 20 or len({r['label'] for r in rows}) < 2):
        arms = {arm: {'AP': None, 'AUROC': None} for arm in ARMS}
    else:
        arms = {arm: ranking_metrics(rows, arm, top_k=cohort == 'primary') for arm in ARMS}
    return {'arms': arms, 'contrasts': contrasts(arms)}


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = (len(values)-1)*q
    lower = math.floor(index)
    fraction = index-lower
    return values[lower] + fraction*(values[min(lower+1, len(values)-1)]-values[lower])


def paired_bootstrap(cohorts: dict[str, list[dict]], *, draws: int = 10000, seed: int = 24242) -> dict:
    """One fixed analysis; paired peptide clusters, fixed cluster count per cohort."""
    groups = {}
    for name, rows in cohorts.items():
        clusters: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            clusters[row['cluster_id']].append(row)
        groups[name] = [clusters[k] for k in sorted(clusters)]
    samples: dict[str, dict] = {c: defaultdict(list) for c in COHORTS}
    rng = random.Random(seed)
    for _ in range(draws):
        for name in COHORTS:
            clusters = groups[name]
            resampled = [row for _ in clusters for row in clusters[rng.randrange(len(clusters))]] if clusters else []
            if name == 'EL_exposed' and len(cohorts[name]) < 20:
                resampled = []
            values = endpoints(resampled, name)
            for kind in ('arms', 'contrasts'):
                for arm, metrics in values[kind].items():
                    for metric, value in metrics.items():
                        key = (kind, arm, metric)
                        if key not in samples[name]:
                            samples[name][key] = []
                        if value is not None:
                            samples[name][key].append(value)
    result = {}
    for name in COHORTS:
        result[name] = {'clusters': len(groups[name]), 'arms': {}, 'contrasts': {}}
        for (kind, arm, metric), values in samples[name].items():
            result[name][kind].setdefault(arm, {})[metric] = {
                'lower_95': quantile(values, .025), 'upper_95': quantile(values, .975),
                'usable_draws': len(values), 'undefined_draws': draws-len(values),
                'unreliable': len(values) < 1000 or len(groups[name]) < 20}
    return {'draws': draws, 'seed': seed, 'cluster_rule': 'shared canonical peptide; patient dependence unmeasured',
            'cohort_order': list(COHORTS), 'resampling': 'fixed number of clusters per cohort, same rows for all arms/endpoints',
            'cohorts': result}


def tie_report(rows: list[dict], arm: str) -> dict:
    counts = Counter(r['scores'][arm] for r in rows)
    ordered = sorted(rows, key=lambda r: (-r['scores'][arm], r['peptide'], r['hla'], r['source_id']))
    boundary = {}
    for k in (10, 20):
        if len(rows) < k:
            boundary[str(k)] = {'defined': False}
        else:
            score = ordered[k-1]['scores'][arm]
            boundary[str(k)] = {'defined': True, 'score': score, 'tie_group_size': counts[score],
                                'crosses_boundary': len(rows) > k and ordered[k]['scores'][arm] == score}
    return {'tied_score_groups': sum(v > 1 for v in counts.values()),
            'observations_in_ties': sum(v for v in counts.values() if v > 1), 'top_k_boundary': boundary}


def evaluate(paths: StoragePaths) -> dict:
    directory, config = context(paths)
    rows, frozen = frozen_cohorts(paths, directory)
    prediction_receipt = json.loads((directory / 'reports/predictions_frozen.json').read_text())
    if prediction_receipt['scientific_hashes'] != software_hashes(paths) or prediction_receipt['outcomes_opened']:
        raise ValueError('Invalid prediction freeze')
    for arm in ARMS:
        path = directory / f'predictions/{arm}.jsonl'
        if runner.raw.sha256_file(path) != prediction_receipt['arms'][arm]['prediction_sha256']:
            raise ValueError('Predictions changed before outcome association')
        predictions_arm = read_rows(path)
        if [r['source_id'] for r in predictions_arm] != [r['source_id'] for r in rows]:
            raise ValueError('Ordered arm identities differ')
        for row, predicted in zip(rows, predictions_arm, strict=True):
            if {k: v for k, v in predicted.items() if k != 'probability'} != row:
                # Other arms add in-memory scores below; compare frozen identity fields only.
                if {k: v for k, v in predicted.items() if k != 'probability'} != {k: v for k, v in row.items() if k != 'scores'}:
                    raise ValueError('Prediction identity association differs')
            row.setdefault('scores', {})[arm] = predicted['probability']
    started = begin(paths, 'evaluation', directory, config)
    if runner.raw.sha256_file(paths.project_data_dir / 'bigmhc_v4/datasets.zip') != gates.ARCHIVE_SHA256:
        raise ValueError('Benchmark archive changed')
    wanted = {r['row_index']: r for r in rows}
    seen, excluded, evaluable = set(), [], []
    # First access to tgt values, after all eligibility and all arm predictions frozen.
    with zipfile.ZipFile(paths.project_data_dir / 'bigmhc_v4/datasets.zip') as archive:
        with archive.open(config['source_member']) as binary, io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as text:
            reader = csv.reader(text, strict=True)
            header = next(reader)
            if header[:3] != ['mhc', 'pep', 'tgt']:
                raise ValueError('Outcome source schema changed')
            for index, fields in enumerate(reader, 1):
                if index not in wanted:
                    continue
                row = wanted[index]
                if fields[:2] != [row['raw_hla'], row['raw_peptide']]:
                    raise ValueError('Original outcome row identity differs')
                seen.add(index)
                label = fields[2].strip()
                if label not in ('0', '1'):
                    excluded.append({'source_id': row['source_id'], 'reason': 'missing_or_ambiguous_binary_outcome'})
                else:
                    evaluable.append(dict(row, label=int(label)))
    if seen != set(wanted):
        raise ValueError('Missing original source outcome rows')
    write_rows(directory / 'cohorts/outcome_quality_exclusions.jsonl', excluded)
    write_rows(directory / 'predictions/associated_outcomes.jsonl', evaluable)
    cohorts = {c: [r for r in evaluable if r[c]] for c in COHORTS}
    points = {c: {'population': population(group, outcomes=True), **endpoints(group, c),
                  'score_ties': {a: tie_report(group, a) for a in ARMS}}
              for c, group in cohorts.items()}
    write_json(directory / 'reports/metrics.json', points)
    uncertainty = paired_bootstrap(cohorts, draws=config['bootstrap_draws'], seed=config['bootstrap_seed'])
    write_json(directory / 'reports/bootstrap.json', uncertainty)
    result = {'status': 'completed_one_time_frozen_evaluation', 'cohorts': points,
              'outcome_quality_exclusions': excluded, 'bootstrap': 'reports/bootstrap.json',
              'first_outcome_access_after_all_predictions_frozen': True,
              'amendment_commit': config['amendment_commit'], 'eligibility_manifest_hashes': frozen['manifest_hashes'],
              'evaluation_commit': git(paths, 'rev-parse', 'HEAD'), 'scientific_hashes': software_hashes(paths),
              'elapsed_seconds': time.monotonic()-started,
              'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'completed_utc': datetime.now(timezone.utc).isoformat(),
              'training_executed': False, 'tuning_or_selection_executed': False,
              'outcome_based_eligibility_changes': False, 'assay_level_independence_verified': False}
    write_json(directory / 'reports/completion.json', result)
    write_json(directory / 'reports/output_manifest.json', {
        str(f.relative_to(directory)): runner.raw.sha256_file(f) for f in sorted(directory.rglob('*'))
        if f.is_file() and f.parts[-2] != 'logs'})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('eligibility', 'predictions', 'evaluate'))
    args = parser.parse_args()
    result = {'eligibility': eligibility, 'predictions': predictions, 'evaluate': evaluate}[args.stage](resolve_paths())
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
