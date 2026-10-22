"""Frozen Task 2.32 direct EL-only immunogenicity evaluation, no learning calls."""
from __future__ import annotations

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
import sys
import time
import zipfile
from typing import Any

from .paths import StoragePaths, resolve_paths
from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as historical_EL
from .third_party_evaluation import WeightedRanking, rank_key
from .replicate_stability_association import read_rows, write_rows, write_json, quantile, distribution_summary

CONFIG = 'configs/bigmhc_el_only_zero_shot_im_task2_32.json'
PROTOCOL = 'docs/BIGMHC_EL_ONLY_ZERO_SHOT_IM_TASK2_32_PROTOCOL.md'
RUN = 'task-2_32-el-only-zero-shot-im'
BRANCH = 'task/2.32-el-only-zero-shot-im'
BASE = 'e6cdb4a2d49848a672131e76cd5614fb7574789f'
ARMS = ('A', 'W', 'P')
DATASETS = ('IMPROVE', 'neoepitope')
PAIRINGS = (('W-A', 'W', 'A'), ('W-P', 'W', 'P'), ('P-A', 'P', 'A'))


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return runner.raw.sha256_file(path)


def assert_sha(path: Path, expected: str) -> None:
    if sha(path) != expected:
        raise ValueError('Frozen input identity differs: '+str(path))


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def configuration(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    if (config['run_id'] != RUN or config['training_authorized'] or config['batch_size'] != 16
            or config['bootstrap_draws'] != 10000 or config['score'] != 'native_FP32_sigmoid_EL_logit'
            or set(config['models']) != set(ARMS) or set(config['cohorts']) != set(DATASETS)):
        raise ValueError('Frozen evaluation configuration changed')
    for arm, spec in config['models'].items():
        expected = 'checkpoints/EL_epoch_10' if arm == 'A' else f'checkpoints/{arm}_EL_epoch_10'
        if spec['checkpoint'] != expected:
            raise ValueError('Only exact EL epoch-10 checkpoint paths allowed; no IM overlays')
    if any(key != 'reference' and not key.startswith('source_') for key in config['inputs']):
        raise ValueError('No training payload is an authorized inference input')
    return config


def software_hashes(paths: StoragePaths) -> dict:
    names = [CONFIG, PROTOCOL, 'src/stability_label_curation/el_only_zero_shot_im.py',
             'tests/test_el_only_zero_shot_im.py', 'src/stability_label_curation/bigmhc_baseline_runner.py',
             'src/stability_label_curation/third_party_evaluation.py',
             'src/stability_label_curation/replicate_stability_association.py', 'src/stability_label_curation/paths.py']
    return {name: sha(paths.repository_root/name) for name in names}


def begin(paths: StoragePaths, stage: str) -> tuple[Path, float]:
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH or git('merge-base', BASE, 'HEAD') != BASE:
        raise ValueError('Clean committed authorized Task 2.32 branch required')
    directory = paths.project_runs_dir/RUN
    if stage == 'preflight':
        directory.mkdir(parents=True, exist_ok=False)
    write_json(directory/f'reports/{stage}_started.json', {'utc': utc(), 'implementation_commit': git('rev-parse', 'HEAD'),
               'scientific_hashes': software_hashes(paths), 'training_authorized': False})
    return directory, time.monotonic()


def require(paths: StoragePaths, name: str) -> tuple[Path, dict]:
    directory = paths.project_runs_dir/RUN
    receipt = json.loads((directory/f'reports/{name}.json').read_text())
    if receipt['scientific_hashes'] != software_hashes(paths):
        repair_path = directory/'reports/technical_io_repair.json'
        if not repair_path.exists():
            raise ValueError('Scientific code/protocol changed after freeze')
        repair = json.loads(repair_path.read_text())
        if (receipt['scientific_hashes'] != repair['previous_scientific_hashes']
                or software_hashes(paths) != repair['corrected_scientific_hashes']):
            raise ValueError('Code differs from the narrowly recorded I/O repair')
    return directory, receipt


def resources(started: float) -> dict:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {'completed_utc': utc(), 'elapsed_seconds': time.monotonic()-started,
            'peak_host_RSS_bytes': usage.ru_maxrss*1024, 'user_seconds': usage.ru_utime,
            'system_seconds': usage.ru_stime}


def authenticate_models(paths: StoragePaths, config: dict) -> tuple[dict, dict, list[str]]:
    previous = paths.project_runs_dir/config['EL_run_id']
    manifest_file = previous/'reports/output_manifest.json'
    assert_sha(manifest_file, config['EL_output_manifest_sha256'])
    manifest = json.loads(manifest_file.read_text())['files_sha256']
    key_path = paths.project_runs_dir/config['keys_relative_path']
    assert_sha(key_path, manifest[str(key_path.relative_to(previous))])
    keys = json.loads(key_path.read_text())['updated_parameters']
    if len(keys) != 36 or len(set(keys)) != 36:
        raise ValueError('Expected full original 36-tensor EL architecture')
    models = {}
    for arm, spec in config['models'].items():
        receipt_file = previous/spec['receipt']
        assert_sha(receipt_file, manifest[spec['receipt']])
        receipt = json.loads(receipt_file.read_text())
        if receipt['checkpoint'] != spec['checkpoint'] or receipt.get('epoch') != 10:
            raise ValueError('EL lineage/epoch differs')
        directory = paths.project_runs_dir/spec['run_id']/spec['checkpoint']
        files = runner.checkpoint_identity(directory, keys)
        if files != receipt['files'] or digest(files) != spec['file_map_sha256']:
            raise ValueError('Exact EL checkpoint file map failed')
        models[arm] = {'directory': str(directory), 'files': files, 'state': receipt['state'],
                       'file_map_sha256': digest(files), 'epoch': 10, 'EL_only': True,
                       'transfer_overlay_loaded': False}
    files = historical_EL.inputs(paths, {'inputs': config['inputs']})
    return models, files, keys


def compact_identity(row: dict, dataset: str) -> dict:
    keys = ['source_id', 'peptide', 'hla', 'raw_hla', 'raw_peptide', 'source_row_index', 'row_index',
            'source_line_number', 'source_row_sha256', 'patient', 'study', 'study_DOI',
            'sample', 'original_observation_id', 'publication_DOI', 'assay', 'HLA_association',
            'patient_peptide_component', 'study_peptide_component', 'cluster_id',
            'minimum_fitting_selection_distance', 'EL_train_peptide', 'IM_train_peptide', 'EL_validation_peptide']
    result = {k: row[k] for k in keys if k in row}
    result.update(dataset=dataset)
    # Empty fields are explicitly unavailable tie-key metadata, not invented IDs.
    result.setdefault('patient', '')
    result.setdefault('study_DOI', '')
    result.setdefault('study', '')
    return result


def load_cohorts(paths: StoragePaths, config: dict) -> tuple[dict, dict, dict]:
    identities, outcomes, references = {}, {}, {}
    for name, spec in config['cohorts'].items():
        parent = paths.project_runs_dir/spec['run_id']
        assert_sha(parent/spec['freeze'], spec['freeze_sha256'])
        assert_sha(parent/spec['identities'], spec['identities_sha256'])
        rows = read_rows(parent/spec['identities'])
        if (len(rows) != spec['n'] or len({r['source_id'] for r in rows}) != spec['n']
                or len({r['peptide'] for r in rows}) != spec['unique_peptides']
                or len({r['hla'] for r in rows}) != spec['hla']):
            raise ValueError('Frozen cohort counts differ')
        for row in rows:
            if (len(row['peptide']) != 9 or set(row['peptide'])-set('ACDEFGHIKLMNPQRSTVWY')
                    or row['peptide'] != row['raw_peptide'].strip().upper()):
                raise ValueError('Frozen canonical sequence identity differs')
        if name == 'IMPROVE':
            freeze = json.loads((parent/spec['freeze']).read_text())
            for kind in ('identities', 'outcomes'):
                if freeze['immutable_artifact_hashes'][spec[kind]] != spec[kind+'_sha256']:
                    raise ValueError('IMPROVE curation receipt binding differs')
            assert_sha(parent/spec['outcomes'], spec['outcomes_sha256'])
            labels = read_rows(parent/spec['outcomes'])
            if (any(r['minimum_fitting_selection_distance'] < 3 or r['exact_prior_published_benchmark_peptide'] for r in rows)
                    or len({r['patient_peptide_component'] for r in rows}) != 38
                    or len({r['study_peptide_component'] for r in rows}) != 1
                    or len({(r['study_DOI'], r['patient']) for r in rows}) != 70
                    or len({r['study_DOI'] for r in rows}) != 3):
                raise ValueError('Frozen hard split/dependence identities differ')
        else:
            freeze = json.loads((parent/spec['freeze']).read_text())
            if freeze['manifest_hashes'][spec['identities']] != spec['identities_sha256']:
                raise ValueError('Neoepitope eligibility receipt binding differs')
            if any(not r['primary'] or r['EL_train_peptide'] or r['IM_train_peptide'] or r['cluster_id'] != r['peptide'] for r in rows):
                raise ValueError('Globally unseen primary cohort differs')
            source = paths.project_data_dir/config['neoepitope_source']['relative_path']
            assert_sha(source, config['neoepitope_source']['sha256'])
            wanted = {r['row_index']: r for r in rows}
            labels = []
            with zipfile.ZipFile(source) as archive, archive.open(config['neoepitope_source']['member']) as binary:
                with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as stream:
                    reader = csv.reader(stream, strict=True)
                    if next(reader)[:3] != ['mhc', 'pep', 'tgt']:
                        raise ValueError('Published outcome source schema differs')
                    for index, fields in enumerate(reader, 1):
                        if index not in wanted:
                            continue
                        row = wanted[index]
                        hla, peptide, label = fields[:3]  # Published score columns never used.
                        if [hla, peptide] != [row['raw_hla'], row['raw_peptide']] or label.strip() not in ('0', '1'):
                            raise ValueError('Original outcome source association differs')
                        labels.append({'source_id': row['source_id'], 'label': int(label.strip())})
        if ([r['source_id'] for r in rows] != [r['source_id'] for r in labels]
                or any(type(r['label']) is not int or r['label'] not in (0, 1) for r in labels)
                or sum(r['label'] for r in labels) != spec['positives']):
            raise ValueError('Frozen outcome availability or class counts differ')
        identities[name], outcomes[name] = [compact_identity(r, name) for r in rows], labels
        references[name] = {**spec, 'ordered_source_id_sha256': digest([r['source_id'] for r in rows]),
                            'original_rows_preserved': True, 'eligibility_regenerated': False}
    return identities, outcomes, references


def model_inputs(rows: list[dict]) -> list[dict]:
    return [{'hla': r['hla'], 'peptide': r['peptide'], 'original_label': '0'} for r in rows]


def native_dataset(Dataset: Any, torch: Any, encodings: dict, rows: list[dict]) -> Any:
    frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(model_inputs(rows))), allele=0, pepcol=1,
                             tgtcol=2, hdrcnt=1, verbose=False)
    if list(frame['pep']) != [r['peptide'] for r in rows] or list(frame['mhc']) != [r['hla'] for r in rows]:
        raise ValueError('Native input normalization changed ordered source identities')
    frame['_source_id'] = [r['source_id'] for r in rows]
    return Dataset(frame, mhcenc=encodings)


def encoding_map(torch: Any, reference: Path, needed: set[str]) -> dict:
    encodings = {}
    with reference.open(newline='') as stream:
        reader = csv.reader(stream); next(reader)
        for record in reader:
            hla = runner.data.canonical_hla(record[0])
            if hla in needed:
                if hla in encodings or len(record[1:]) != 414:
                    raise ValueError('Ambiguous or incompatible exact HLA input')
                encodings[hla] = torch.tensor([int(v) for v in record[1:]], dtype=torch.int8)
    if set(encodings) != needed:
        raise ValueError('Missing exact frozen HLA encoding')
    return encodings


def preflight(paths: StoragePaths) -> dict:
    directory, start = begin(paths, 'preflight')
    config = configuration(paths)
    models, files, keys = authenticate_models(paths, config)
    cohorts, outcomes, references = load_cohorts(paths, config)
    import numpy as np
    import torch
    runner.cuda_visibility(); runner.seed_runtime(torch, np, config)
    device = runner.runtime_device(torch, config)
    encodings = encoding_map(torch, files['reference'], {r['hla'] for rows in cohorts.values() for r in rows}|{'HLA-A*02:01'})
    smoke = {}
    with runner.pinned_modules(files) as (BigMHC, Dataset):
        for arm in ARMS:
            model = runner.load_checkpoint(torch, BigMHC, models[arm]['directory'], keys, device=device, lineage=None)
            if (runner.state_hashes(model) != models[arm]['state'] or list(model.state_dict()) != keys
                    or any(v.dtype != torch.float32 for v in model.state_dict().values())
                    or any(m._forward_hooks for m in model.modules())):
                raise ValueError('Exact plain FP32 EL checkpoint reload failed')
            model.eval()
            synthetic = [{'source_id': 'synthetic_preflight', 'peptide': 'AAAAAAAAA', 'hla': 'HLA-A*02:01'}]
            native = native_dataset(Dataset, torch, encodings, synthetic)
            native.makebats(16, shuffle=False, negfrac=None)
            batch = native[0]
            with torch.no_grad():
                logits, _ = model(batch.mhc.float().to(device), batch.pep.float().to(device))
                probability = torch.sigmoid(logits)
            if not torch.isfinite(logits).all() or not torch.isfinite(probability).all():
                raise ValueError('Synthetic original EL forward is nonfinite')
            smoke[arm] = {'strict_reload_equal': True, 'logit': float(logits[0]), 'probability': float(probability[0]), 'synthetic_only': True}
            del model
    for name in DATASETS:
        write_rows(directory/f'cohorts/{name}_identities.jsonl', cohorts[name])
        write_rows(directory/f'cohorts/{name}_outcomes.jsonl', outcomes[name])
    write_json(directory/'reports/cohort_references.json', references)
    write_json(directory/'reports/EL_model_identities.json', {'models': models, 'keys': keys})
    write_json(directory/'reports/scientific_configuration.json', config)
    frozen = {str(f.relative_to(directory)): sha(f) for f in (directory/'cohorts').iterdir()}
    frozen.update({name: sha(directory/name) for name in ['reports/cohort_references.json', 'reports/EL_model_identities.json', 'reports/scientific_configuration.json']})
    proof = {'status': 'PASS', 'scientific_hashes': software_hashes(paths), 'frozen_artifacts': frozen,
             'synthetic_EL_smoke': smoke, 'cohorts': {name: {'n': len(rows), 'positive': sum(r['label'] for r in outcomes[name])} for name, rows in cohorts.items()},
             'HLA_encodings': len(encodings), 'IM_weights_or_transfer_loaded': False, 'training_executed': False,
             'runtime': {'Python': platform.python_version(), 'platform': platform.platform(), 'Torch': torch.__version__,
                         'NumPy': np.__version__, **runner.device_report(torch, device),
                         'deterministic': torch.are_deterministic_algorithms_enabled(),
                         'TF32_matmul': torch.backends.cuda.matmul.allow_tf32, 'TF32_cudnn': torch.backends.cudnn.allow_tf32,
                         'autocast': torch.is_autocast_enabled()}, 'resources': resources(start)}
    write_json(directory/'reports/preflight.json', proof)
    return {'status': 'PASS', 'cohorts': proof['cohorts'], 'EL_models': list(models)}


def frozen_inputs(paths: StoragePaths) -> tuple[Path, dict, dict]:
    directory, proof = require(paths, 'preflight')
    for name, expected in proof['frozen_artifacts'].items():
        assert_sha(directory/name, expected)
    config = configuration(paths)
    return directory, config, proof


def inference(paths: StoragePaths) -> dict:
    directory, config, proof = frozen_inputs(paths)
    tests = json.loads((directory/'reports/focused_tests.json').read_text())
    if tests['status'] != 'PASS' or tests['skipped'] or tests['scientific_hashes'] != software_hashes(paths):
        raise ValueError('Focused checks missing or stale')
    directory, start = begin(paths, 'inference')
    models, files, keys = authenticate_models(paths, config)
    cohorts = {name: read_rows(directory/f'cohorts/{name}_identities.jsonl') for name in DATASETS}
    import numpy as np
    import torch
    runner.seed_runtime(torch, np, config); device = runner.runtime_device(torch, config)
    encodings = encoding_map(torch, files['reference'], {r['hla'] for rows in cohorts.values() for r in rows})
    prediction_receipts = {}
    with runner.pinned_modules(files) as (BigMHC, Dataset):
        for arm in ARMS:
            model = runner.load_checkpoint(torch, BigMHC, models[arm]['directory'], keys, device=device, lineage=None)
            if runner.state_hashes(model) != models[arm]['state']:
                raise ValueError('EL tensor identity differs')
            model.eval()
            for name in DATASETS:
                rows, predicted, emitted = cohorts[name], [], []
                native = native_dataset(Dataset, torch, encodings, rows)
                native.makebats(16, shuffle=False, negfrac=None)
                with torch.no_grad():
                    for index in range(len(native)):
                        batch = native[index]
                        logits, _ = model(batch.mhc.float().to(device), batch.pep.float().to(device))
                        probabilities = torch.sigmoid(logits)
                        identities = native.getbat(index, enc=False)['_source_id'].tolist()
                        emitted.extend(identities)
                        for identity, logit, probability in zip(identities, logits.cpu().tolist(), probabilities.cpu().tolist(), strict=True):
                            if not math.isfinite(logit) or not math.isfinite(probability) or not 0 <= probability <= 1:
                                raise ValueError('Nonfinite raw/probability EL output')
                            predicted.append({'source_id': identity, 'raw_EL_logit': logit, 'EL_probability': probability})
                if emitted != [r['source_id'] for r in rows] or len(predicted) != len(rows):
                    raise ValueError('Native emitted prediction alignment failed')
                path = directory/f'predictions/{name}_{arm}.jsonl'
                write_rows(path, ({**row, **prediction} for row, prediction in zip(rows, predicted, strict=True)))
                prediction_receipts[f'{name}_{arm}'] = {'n': len(predicted), 'sha256': sha(path),
                    'ordered_source_id_sha256': digest(emitted), 'native_batches': len(native),
                    'finite_logits_and_probabilities': True}
                print('frozen', name, arm, len(predicted), flush=True)
            if runner.state_hashes(model) != models[arm]['state']:
                raise ValueError('Inference changed frozen EL parameters')
            del model
    result = {'status': 'ALL_SIX_PREDICTION_FILES_FROZEN', 'scientific_hashes': software_hashes(paths),
              'predictions': prediction_receipts, 'frozen_utc': utc(), 'IM_training_or_transfer': False,
              'raw_logit_and_native_sigmoid_saved': True, 'parameters_unchanged': True,
              'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(),
              'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(), 'resources': resources(start)}
    write_json(directory/'reports/predictions_frozen.json', result)
    return result


def paired_contrasts(arms: dict) -> dict:
    return {name: {metric: arms[a][metric]-arms[b][metric] if arms[a][metric] is not None and arms[b][metric] is not None else None for metric in arms[a]} for name, a, b in PAIRINGS}


def bootstrap(rows: list[dict], rankings: dict, field: str, seed: int, draws: int, evidence: Path | None = None) -> dict:
    import numpy as np
    groups = sorted({r[field] for r in rows})
    if len(groups) < 2:
        return {'confidence_intervals': None, 'reason': 'Fewer than two independent dependence components',
                'components': len(groups), 'draws_executed': 0, 'requested_draws': draws, 'seed': seed, 'unreliable': True}
    mapping = {group: i for i, group in enumerate(groups)}
    indices = np.array([mapping[r[field]] for r in rows], dtype=np.int64)
    rng, samples = random.Random(seed), {name: defaultdict(list) for name, _, _ in PAIRINGS}
    log = gzip.open(evidence, 'xt') if evidence else None
    try:
        for draw in range(draws):
            counts = np.bincount([rng.randrange(len(groups)) for _ in groups], minlength=len(groups))
            weights = counts[indices]
            arms = {arm: rankings[arm].metrics(weights, top_k=True) for arm in ARMS}
            contrasts = paired_contrasts(arms)
            for name, metrics in contrasts.items():
                for metric, value in metrics.items():
                    if value is not None:
                        samples[name][metric].append(value)
            if log:
                log.write(json.dumps({'draw': draw+1, 'component_multiplicities': counts.tolist(),
                                     'n': int(weights.sum()), 'contrasts': contrasts}, allow_nan=False)+'\n')
            if evidence and (draw+1) % 1000 == 0:
                print(field, draw+1, flush=True)
    finally:
        if log:
            log.close()
    metric_names = list(next(iter(rankings.values())).metrics(np.ones(len(rows), dtype=np.int64), top_k=True))
    return {'components': len(groups), 'component_sizes': dict(Counter(r[field] for r in rows)),
            'draws_executed': draws, 'seed': seed, 'field': field,
            'confidence_intervals': {name: {metric: {'lower_95': quantile(values.get(metric, []), .025),
                'upper_95': quantile(values.get(metric, []), .975), 'usable_draws': len(values.get(metric, [])),
                'undefined_draws': draws-len(values.get(metric, [])), 'unreliable': len(groups)<20 or len(values.get(metric, []))<1000}
                for metric in metric_names} for name, values in samples.items()}, 'unreliable': len(groups)<20}


def join_predictions(rows: list[dict], predictions: list[dict]) -> None:
    if len(rows) != len(predictions):
        raise ValueError('Prediction count mismatch')
    for row, prediction in zip(rows, predictions, strict=True):
        if {k: v for k, v in prediction.items() if k not in ('raw_EL_logit', 'EL_probability')} != row:
            raise ValueError('Prediction/source-row/HLA identity mismatch')


def evaluate(paths: StoragePaths, *, resume_after_io_failure: bool = False) -> dict:
    import numpy as np
    directory, config, proof = frozen_inputs(paths)
    _, receipt = require(paths, 'predictions_frozen')
    if receipt['status'] != 'ALL_SIX_PREDICTION_FILES_FROZEN':
        raise ValueError('All predictions must be fixed before comparisons')
    for name, item in receipt['predictions'].items():
        assert_sha(directory/f'predictions/{name}.jsonl', item['sha256'])
    if resume_after_io_failure:
        repair = json.loads((directory/'reports/technical_io_repair.json').read_text())
        for name, expected in repair['completed_outputs_preserved'].items():
            assert_sha(directory/name, expected)
        if (directory/'evaluation/IMPROVE_patient_component_draws.jsonl.gz').exists():
            raise ValueError('Resampling already started; this repair cannot repeat it')
    directory, start = begin(paths, 'evaluation_resumed' if resume_after_io_failure else 'evaluation')
    points, uncertainty = {}, {}
    for name in DATASETS:
        if resume_after_io_failure and name == 'IMPROVE':
            # The first attempt saved these points before its first bootstrap draw.
            # Reuse them unchanged; never rescore or recalculate the primary points.
            points[name] = json.loads((directory/'evaluation/IMPROVE_point_metrics.json').read_text())
            joined = read_rows(directory/'evaluation/IMPROVE_joined.jsonl')
            rankings = {arm: WeightedRanking(joined, arm) for arm in ARMS}
            uncertainty[name] = {'patient_peptide': bootstrap(joined, rankings, 'patient_peptide_component', config['patient_component_seed'], config['bootstrap_draws'], directory/'evaluation/IMPROVE_patient_component_draws.jsonl.gz'),
                                 'study_peptide': bootstrap(joined, rankings, 'study_peptide_component', config['study_component_seed'], config['bootstrap_draws'])}
            write_json(directory/f'evaluation/{name}_paired_uncertainty.json', uncertainty[name])
            continue
        identities = read_rows(directory/f'cohorts/{name}_identities.jsonl')
        labels = read_rows(directory/f'cohorts/{name}_outcomes.jsonl')
        if [r['source_id'] for r in identities] != [r['source_id'] for r in labels]:
            raise ValueError('Original outcome association differs')
        score_maps, diagnostics = {}, {}
        for arm in ARMS:
            predictions = read_rows(directory/f'predictions/{name}_{arm}.jsonl')
            join_predictions(identities, predictions)
            score_maps[arm] = [r['EL_probability'] for r in predictions]
            probabilities = score_maps[arm]
            groups = Counter(probabilities)
            ordered = sorted(range(len(identities)), key=lambda i: (-probabilities[i], identities[i]['peptide'], identities[i]['hla'], identities[i]['study_DOI'], identities[i]['patient'], identities[i]['source_id']))
            diagnostics[arm] = {'EL_probability': distribution_summary(probabilities),
                'raw_EL_logit': distribution_summary([r['raw_EL_logit'] for r in predictions]),
                'probability_zero_n': probabilities.count(0.0), 'probability_one_n': probabilities.count(1.0),
                'tied_score_groups': sum(v>1 for v in groups.values()), 'observations_in_ties': sum(v for v in groups.values() if v>1),
                'topK_boundary_ties': {str(k): {'score': probabilities[ordered[k-1]], 'group_size': groups[probabilities[ordered[k-1]]],
                    'crosses_boundary': len(ordered)>k and probabilities[ordered[k]]==probabilities[ordered[k-1]]} if len(ordered)>=k else None for k in (10, 20)}}
        joined = [{**r, 'label': label['label'], 'scores': {arm: score_maps[arm][i] for arm in ARMS},
                   'peptide_component': r['peptide']} for i, (r, label) in enumerate(zip(identities, labels, strict=True))]
        rankings = {arm: WeightedRanking(joined, arm) for arm in ARMS}
        arms = {arm: ranking.metrics(np.ones(len(joined), dtype=np.int64), top_k=True) for arm, ranking in rankings.items()}
        y_count = sum(r['label'] for r in joined)
        hla_metrics, groups = {}, defaultdict(list)
        for row in joined:
            groups[row['hla']].append(row)
        for hla, group in sorted(groups.items()):
            positive = sum(r['label'] for r in group)
            adequate = len(group)>=config['per_HLA_min_n'] and positive>=config['per_HLA_min_positive'] and len(group)-positive>=config['per_HLA_min_negative']
            values = {arm: WeightedRanking(group, arm).metrics(np.ones(len(group), dtype=np.int64), top_k=False) for arm in ARMS} if adequate else {arm: {'AP': None, 'AUROC': None} for arm in ARMS}
            hla_metrics[hla] = {'n': len(group), 'positive': positive, 'negative': len(group)-positive,
                                'adequately_evaluable': adequate, 'arms': values, 'contrasts': paired_contrasts(values)}
        population = {'n': len(joined), 'positive': y_count, 'negative': len(joined)-y_count,
                      'prevalence': y_count/len(joined), 'unique_peptides': len({r['peptide'] for r in joined}),
                      'unique_pairs': len({(r['peptide'],r['hla']) for r in joined}), 'HLAs': len(groups),
                      'patients': config['cohorts'][name]['patients'], 'studies': config['cohorts'][name]['studies'],
                      'HLA_counts': dict(Counter(r['hla'] for r in joined))}
        if name == 'IMPROVE':
            population['study_composition'] = {study: {'n': sum(r['study_DOI']==study for r in joined),
                'positive': sum(r['label'] for r in joined if r['study_DOI']==study),
                'patients': len({r['patient'] for r in joined if r['study_DOI']==study})} for study in sorted({r['study_DOI'] for r in joined})}
            population['patient_composition'] = {digest([study,patient]): {'study_DOI': study, 'patient': patient,
                'n': sum(r['study_DOI']==study and r['patient']==patient for r in joined),
                'positive': sum(r['label'] for r in joined if r['study_DOI']==study and r['patient']==patient)}
                for study,patient in sorted({(r['study_DOI'],r['patient']) for r in joined})}
        points[name] = {'population': population, 'arms': arms, 'contrasts': paired_contrasts(arms),
                        'per_HLA': hla_metrics, 'score_diagnostics': diagnostics,
                        'random_ranking_AP_reference': y_count/len(joined)}
        write_rows(directory/f'evaluation/{name}_joined.jsonl', joined)
        write_json(directory/f'evaluation/{name}_point_metrics.json', points[name])
        if name == 'IMPROVE':
            uncertainty[name] = {'patient_peptide': bootstrap(joined, rankings, 'patient_peptide_component', config['patient_component_seed'], config['bootstrap_draws'], directory/'evaluation/IMPROVE_patient_component_draws.jsonl.gz'),
                                 'study_peptide': bootstrap(joined, rankings, 'study_peptide_component', config['study_component_seed'], config['bootstrap_draws'])}
        else:
            uncertainty[name] = {'peptide': bootstrap(joined, rankings, 'peptide_component', config['peptide_cluster_seed'], config['bootstrap_draws'], directory/'evaluation/neoepitope_peptide_draws.jsonl.gz')}
        write_json(directory/f'evaluation/{name}_paired_uncertainty.json', uncertainty[name])
    write_json(directory/'evaluation/point_metrics.json', points)
    result = {'status': 'COMPLETE', 'scientific_hashes': software_hashes(paths), 'primary': 'IMPROVE AP',
              'no_training_tuning_or_cohort_changes': True, 'previously_untouched_blind_test': False,
              'all_predictions_fixed_before_comparisons': True, 'resources': resources(start)}
    write_json(directory/'reports/evaluation_completed.json', result)
    return {'status': 'COMPLETE', 'points': {name: {'arms': p['arms'], 'contrasts': p['contrasts']} for name, p in points.items()}, 'resources': result['resources']}


def main() -> None:
    if len(sys.argv)!=2 or sys.argv[1] not in ('preflight','inference','evaluate','resume-evaluation'):
        raise SystemExit('preflight | inference | evaluate | resume-evaluation')
    paths = resolve_paths()
    try:
        result = evaluate(paths, resume_after_io_failure=True) if sys.argv[1] == 'resume-evaluation' else globals()[sys.argv[1]](paths)
        print(json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
    except Exception as exc:
        directory = paths.project_runs_dir/RUN
        if directory.exists():
            write_json(directory/f'reports/{sys.argv[1]}_failure_{time.time_ns()}.json', {'error': repr(exc), 'status': 'FAILED'})
        raise


if __name__ == '__main__':
    main()
