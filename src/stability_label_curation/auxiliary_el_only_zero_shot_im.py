"""Frozen Task 2.33 auxiliary EL classification evaluation; no learning calls.

Reuse Task 2.32 pure encoding/alignment helpers and its exact metric procedure.
Historical experiment implementations and artifacts remain unchanged.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time
from typing import Any

from .paths import StoragePaths, resolve_paths
from . import el_only_zero_shot_im as previous
from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as historical_EL
from .third_party_evaluation import WeightedRanking, rank_key
from .replicate_stability_association import read_rows, write_rows, write_json, quantile, distribution_summary

CONFIG = 'configs/bigmhc_auxiliary_el_only_zero_shot_im_task2_33.json'
PROTOCOL = 'docs/BIGMHC_AUXILIARY_EL_ONLY_ZERO_SHOT_IM_TASK2_33_PROTOCOL.md'
RUN = 'task-2_33-auxiliary-el-only-zero-shot-im'
BRANCH = 'task/2.33-auxiliary-el-only-zero-shot-im'
BASE = 'be644fd3a09a1f5a2cdd320f8f6be1fae7a08869'
ARMS = ('A', 'S', 'P')
DATASETS = ('IMPROVE', 'neoepitope')
PAIRINGS = (('S-A', 'S', 'A'), ('S-P', 'S', 'P'), ('P-A', 'P', 'A'))
utc, sha, assert_sha, digest, resources = previous.utc, previous.sha, previous.assert_sha, previous.digest, previous.resources
model_inputs, native_dataset, encoding_map, join_predictions = previous.model_inputs, previous.native_dataset, previous.encoding_map, previous.join_predictions


def configuration(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    if (config['run_id'] != RUN or config['training_authorized'] or config['batch_size'] != 16
            or config['bootstrap_draws'] != 10000 or config['score'] != 'native_FP32_sigmoid_EL_logit'
            or set(config['models']) != set(ARMS) or set(config['cohorts']) != set(DATASETS)
            or config['lambda_aux'] != .1 or not config['A_predictions_reused']):
        raise ValueError('Frozen evaluation configuration changed')
    for arm, spec in config['models'].items():
        expected = 'checkpoints/EL_epoch_10' if arm == 'A' else f'checkpoints/{arm}_EL_epoch_10'
        if spec['checkpoint'] != expected:
            raise ValueError('Only exact EL epoch-10 checkpoints; no IM weights or auxiliary heads')
    if any(key != 'reference' and not key.startswith('source_') for key in config['inputs']):
        raise ValueError('No training payload is an authorized inference input')
    return config


def software_hashes(paths: StoragePaths) -> dict:
    names = [CONFIG, PROTOCOL, 'src/stability_label_curation/auxiliary_el_only_zero_shot_im.py',
             'tests/test_auxiliary_el_only_zero_shot_im.py', 'src/stability_label_curation/el_only_zero_shot_im.py',
             'src/stability_label_curation/bigmhc_baseline_runner.py', 'src/stability_label_curation/third_party_evaluation.py',
             'src/stability_label_curation/replicate_stability_association.py', 'src/stability_label_curation/paths.py',
             'src/stability_label_curation/bigmhc_el_multiepoch.py',
             'configs/bigmhc_fully_trained_auxiliary_task2_24.json', 'configs/bigmhc_el_multiepoch_task2_23.json']
    return {name: sha(paths.repository_root/name) for name in names}


def begin(paths: StoragePaths, stage: str) -> tuple[Path, float]:
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH or git('merge-base', BASE, 'HEAD') != BASE:
        raise ValueError('Clean committed authorized Task 2.33 branch required')
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
        raise ValueError('Scientific implementation or protocol changed after freeze')
    return directory, receipt


def authenticated_report(parent: Path, manifest: dict, name: str) -> dict:
    path = parent/name
    assert_sha(path, manifest[name])
    return json.loads(path.read_text())


def parent_evidence(paths: StoragePaths, config: dict) -> tuple[Path, dict, Path, dict]:
    old = paths.project_runs_dir/config['previous_run']
    aux = paths.project_runs_dir/config['auxiliary_run']
    assert_sha(old/'reports/output_manifest.json', config['previous_manifest_sha256'])
    assert_sha(aux/'reports/output_manifest.json', config['auxiliary_manifest_sha256'])
    return old, json.loads((old/'reports/output_manifest.json').read_text())['files_sha256'], aux, json.loads((aux/'reports/output_manifest.json').read_text())


def authenticate_models(paths: StoragePaths, config: dict) -> tuple[dict, dict, list[str]]:
    old, old_manifest, aux, aux_manifest = parent_evidence(paths, config)
    baseline = authenticated_report(old, old_manifest, 'reports/EL_model_identities.json')
    keys = baseline['keys']
    if len(keys) != 36 or len(set(keys)) != 36:
        raise ValueError('Expected full original 36-tensor EL architecture')
    models = {}
    for arm, spec in config['models'].items():
        receipt = baseline['models']['A'] if arm == 'A' else authenticated_report(aux, aux_manifest, spec['receipt'])
        if arm != 'A' and (receipt['checkpoint'] != spec['checkpoint'] or receipt['state_keys'] != keys or not receipt['strict_reload_identical']):
            raise ValueError('Plain complete EL checkpoint lineage differs')
        directory = paths.project_runs_dir/spec['run_id']/spec['checkpoint']
        files = runner.checkpoint_identity(directory, keys)
        if files != receipt['files'] or digest(files) != spec['file_map_sha256']:
            raise ValueError('Exact EL epoch-10 checkpoint file map failed')
        models[arm] = {'directory': str(directory), 'files': files, 'state': receipt['state'],
                       'file_map_sha256': digest(files), 'epoch': 10, 'EL_only': True,
                       'transfer_overlay_loaded': False, 'auxiliary_head_loaded': False}
    files = historical_EL.inputs(paths, {'inputs': config['inputs']})
    return models, files, keys


def training_compatibility(paths: StoragePaths, config: dict) -> dict:
    """Targeted EL-only metadata checks; no training data or IM model access."""
    _, _, aux, manifest = parent_evidence(paths, config)
    historical = json.loads((paths.repository_root/'configs/bigmhc_fully_trained_auxiliary_task2_24.json').read_text())
    base_config = json.loads((paths.repository_root/'configs/bigmhc_el_multiepoch_task2_23.json').read_text())
    auxiliary = authenticated_report(aux, manifest, 'reports/scientific_configuration.json')
    cohort = authenticated_report(aux, manifest, 'reports/cohort_binding.json')
    if (auxiliary != historical or cohort['training_rows'] != 1308196 or cohort['training_classes'] != {'0': 1245143, '1': 63053}
            or cohort['partitions'] != {'train': 1308196, 'validation': 145371, 'excluded': 11}
            or cohort['ordered_training_manifest_bindings_sha256'] != 'e8c54a96e82a4add61790a7cbcfad993b33b252a2fc95331746fdd521f3ee12a'
            or cohort['rank_reference'] != 'EL_training_positives_only'):
        raise ValueError('Frozen fitting cohort/rank reference differs')
    if auxiliary['inputs']['EL_split'] != {
            'area': 'runs', 'relative_path': 'task-2_23-el-multiepoch-baseline/processed/el_split_manifest_v1.csv.gz',
            'sha256': '6b3a6a0c00f86c26e51b84a8df1dd7e81d545117baa871dabd0707edaf89ac00'}:
        raise ValueError('Original Task 2.23 fitting partition identity differs')
    for key in ('EL', *config['inputs']):
        if auxiliary['inputs'][key] != base_config['inputs'][key]:
            raise ValueError('A/S/P EL population, source implementation or HLA mapping mismatch: '+key)
        if key in config['inputs'] and config['inputs'][key] != auxiliary['inputs'][key]:
            raise ValueError('Evaluation transformation differs from fitting transformation')
    base = paths.project_runs_dir/historical['baseline']['run_id']
    def baseline(name):
        return authenticated_report(base, {'reports/'+k:v for k,v in historical['baseline']['reports'].items()}, 'reports/'+name)
    original_preflight = baseline('preflight.json')
    if original_preflight['immutable_artifacts']['processed/el_split_manifest_v1.csv.gz'] != auxiliary['inputs']['EL_split']['sha256']:
        raise ValueError('A/S/P authenticated partition receipt mismatch')
    initial = baseline('initial_EL_state.json')
    evidence = {}
    shared = ('sampled_batch_sha256','RNG_before','RNG_after','optimizer_defaults','updated_parameters',
              'optimization_steps','consumed_rows','requested_batch_size','maximum_optimized_batch_rows',
              'sampled_class_exposures','optimizer_class_exposures','optimizer_skip_mask')
    for arm in ('S','P'):
        initialization = authenticated_report(aux, manifest, f'reports/{arm}_initialization.json')
        completed = authenticated_report(aux, manifest, f'reports/{arm}_EL_completed.json')
        if (initialization['backbone'] != initial['state'] or initialization['RNG'] != initial['RNG']
                or completed['epochs'] != 10 or completed['optimizer_steps'] != 630530):
            raise ValueError('A/S/P initialization or ten-epoch schedule differs')
        evidence[arm] = []
    for epoch in range(1,11):
        reference = baseline(f'EL_epoch_{epoch:02d}.json')
        for arm in ('S','P'):
            actual = authenticated_report(aux, manifest, f'reports/{arm}_EL_epoch_{epoch:02d}.json')
            if (any(actual[k] != reference[k] for k in shared) or actual['lambda_aux'] != .1
                    or actual['BCE_denominator'] != 'all native batch rows' or not actual['ordered_sampling_matches_A']):
                raise ValueError('Matched EL sampling/schedule failed')
            evidence[arm].append({'epoch': epoch, 'sampled_batch_sha256': actual['sampled_batch_sha256'], 'RNG_matches_A': True,
                                  'native_BCE_denominator_unchanged': True, 'optimizer_defaults_match_A': True})
    return {'status': 'PASS', 'same_EL_population_encoding_preprocessing': True, 'same_initial_backbone': True,
            'EL_epochs': 10, 'seed': 42, 'lambda_aux': .1, 'training_cohort': cohort,
            'epoch_matching': evidence, 'no_IM_payload_or_weights_accessed': True}


def load_cohorts(paths: StoragePaths, config: dict) -> tuple[dict, dict, dict]:
    old, manifest, _, _ = parent_evidence(paths, config)
    identities, outcomes = {}, {}
    references = authenticated_report(old, manifest, 'reports/cohort_references.json')
    for name, spec in config['cohorts'].items():
        for kind, destination in [('identities',identities),('outcomes',outcomes)]:
            relative = f'cohorts/{name}_{kind}.jsonl'
            assert_sha(old/relative, manifest[relative])
            destination[name] = read_rows(old/relative)
        rows, labels = identities[name], outcomes[name]
        if (len(rows) != spec['n'] or len({r['source_id'] for r in rows}) != spec['n']
                or len({r['peptide'] for r in rows}) != spec['unique_peptides'] or len({r['hla'] for r in rows}) != spec['hla']
                or [r['source_id'] for r in rows] != [r['source_id'] for r in labels]
                or any(type(r['label']) is not int or r['label'] not in (0,1) for r in labels)
                or sum(r['label'] for r in labels) != spec['positives'] or references[name]['n'] != spec['n']):
            raise ValueError('Frozen Task 2.32 cohort identity/classes differ')
        if any(len(r['peptide']) != 9 or set(r['peptide'])-set('ACDEFGHIKLMNPQRSTVWY') for r in rows):
            raise ValueError('Frozen canonical 9-mer differs')
        if name == 'IMPROVE':
            if (len({r['patient_peptide_component'] for r in rows}) != 38 or len({r['study_peptide_component'] for r in rows}) != 1
                    or any(r['minimum_fitting_selection_distance'] < 3 for r in rows)
                    or len({(r['study_DOI'],r['patient']) for r in rows}) != 70 or len({r['study_DOI'] for r in rows}) != 3):
                raise ValueError('Frozen hard split/dependence identities differ')
        elif any(r['EL_train_peptide'] or r['IM_train_peptide'] or r['cluster_id'] != r['peptide'] for r in rows):
            raise ValueError('Neoepitope global exact disjointness differs')
    return identities, outcomes, references


def check_A_reuse(paths: StoragePaths, config: dict, cohorts: dict) -> dict:
    old, manifest, _, _ = parent_evidence(paths, config)
    prior = authenticated_report(old, manifest, 'reports/preflight.json')
    prior_config = authenticated_report(old, manifest, 'reports/scientific_configuration.json')
    frozen = authenticated_report(old, manifest, 'reports/predictions_frozen.json')
    repair = authenticated_report(old, manifest, 'reports/technical_io_repair.json')
    completion = authenticated_report(old, manifest, 'reports/completion_verification.json')
    if (frozen['scientific_hashes'] != repair['previous_scientific_hashes']
            or completion['scientific_hashes'] != repair['corrected_scientific_hashes']):
        raise ValueError('Historical narrow I/O-repair lineage differs')
    for key in ('inputs','batch_size','score','seed','cpu_threads','device'):
        if config[key] != prior_config[key]:
            raise ValueError('A native EL inference configuration differs: '+key)
    for name in ('src/stability_label_curation/el_only_zero_shot_im.py', 'src/stability_label_curation/bigmhc_baseline_runner.py',
                 'src/stability_label_curation/bigmhc_el_multiepoch.py', 'src/stability_label_curation/third_party_evaluation.py'):
        # bigmhc_el_multiepoch is transitively pinned by the unchanged approved base;
        # earlier Task 2.32 receipts explicitly hash the other three files.
        if name in completion['scientific_hashes']:
            assert_sha(paths.repository_root/name, completion['scientific_hashes'][name])
    receipts = {}
    for name, rows in cohorts.items():
        path = old/f'predictions/{name}_A.jsonl'
        assert_sha(path, manifest[f'predictions/{name}_A.jsonl'])
        assert_sha(path, frozen['predictions'][name+'_A']['sha256'])
        predictions = read_rows(path); join_predictions(rows, predictions)
        if any(not math.isfinite(r['raw_EL_logit']) or not math.isfinite(r['EL_probability']) or not 0<=r['EL_probability']<=1 for r in predictions):
            raise ValueError('Historical A output invalid')
        receipts[name] = {'sha256': sha(path), 'ordered_source_id_sha256': digest([r['source_id'] for r in rows]), 'n': len(rows)}
    return {'status': 'PASS', 'A_study_inference_repeated': False, 'predictions': receipts,
            'original_runtime': prior['runtime'], 'identical_native_preprocessing_score_and_batch_size': True}




def preflight(paths: StoragePaths) -> dict:
    directory, start = begin(paths, 'preflight')
    config = configuration(paths)
    models, files, keys = authenticate_models(paths, config)
    compatibility = training_compatibility(paths, config)
    cohorts, outcomes, references = load_cohorts(paths, config)
    reuse = check_A_reuse(paths, config, cohorts)
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
    write_json(directory/'reports/training_compatibility.json', compatibility)
    write_json(directory/'reports/A_reuse_compatibility.json', reuse)
    current_runtime = {'Torch': torch.__version__, 'NumPy': np.__version__, 'Python': platform.python_version()}
    if any(reuse['original_runtime'][k] != v for k,v in current_runtime.items()):
        raise ValueError('A runtime version differs')
    if smoke['A']['logit'] != authenticated_report(*parent_evidence(paths, config)[:2], 'reports/preflight.json')['synthetic_EL_smoke']['A']['logit']:
        raise ValueError('Original A synthetic logit changed')
    for name in DATASETS:
        write_rows(directory/f'cohorts/{name}_identities.jsonl', cohorts[name])
        write_rows(directory/f'cohorts/{name}_outcomes.jsonl', outcomes[name])
    write_json(directory/'reports/cohort_references.json', references)
    write_json(directory/'reports/EL_model_identities.json', {'models': models, 'keys': keys})
    write_json(directory/'reports/scientific_configuration.json', config)
    frozen = {str(f.relative_to(directory)): sha(f) for f in (directory/'cohorts').iterdir()}
    frozen.update({name: sha(directory/name) for name in ['reports/cohort_references.json', 'reports/EL_model_identities.json', 'reports/scientific_configuration.json', 'reports/training_compatibility.json', 'reports/A_reuse_compatibility.json']})
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
    check_A_reuse(paths, config, {name: read_rows(directory/f'cohorts/{name}_identities.jsonl') for name in DATASETS})
    cohorts = {name: read_rows(directory/f'cohorts/{name}_identities.jsonl') for name in DATASETS}
    import numpy as np
    import torch
    runner.seed_runtime(torch, np, config); device = runner.runtime_device(torch, config)
    encodings = encoding_map(torch, files['reference'], {r['hla'] for rows in cohorts.values() for r in rows})
    prediction_receipts = {}
    old = paths.project_runs_dir/config['previous_run']
    for name in DATASETS:
        source = old/f'predictions/{name}_A.jsonl'
        target = directory/f'predictions/{name}_A.jsonl'
        if target.exists():
            raise ValueError('Refuse prediction overwrite')
        shutil.copyfile(source, target)
        prediction_receipts[name+'_A'] = {'n': len(cohorts[name]), 'sha256': sha(target), 'reused_from_Task2_32': True,
            'ordered_source_id_sha256': digest([r['source_id'] for r in cohorts[name]]), 'finite_logits_and_probabilities': True}
    with runner.pinned_modules(files) as (BigMHC, Dataset):
        for arm in ('S', 'P'):
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
              'predictions': prediction_receipts, 'frozen_utc': utc(), 'IM_training_or_transfer': False, 'new_study_inference_passes': 4, 'reused_A_prediction_files': 2, 'auxiliary_head_loaded': False,
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


def evaluate(paths: StoragePaths) -> dict:
    import numpy as np
    directory, config, proof = frozen_inputs(paths)
    _, receipt = require(paths, 'predictions_frozen')
    if receipt['status'] != 'ALL_SIX_PREDICTION_FILES_FROZEN':
        raise ValueError('All predictions must be fixed before comparisons')
    for name, item in receipt['predictions'].items():
        assert_sha(directory/f'predictions/{name}.jsonl', item['sha256'])
    directory, start = begin(paths, 'evaluation')
    points, uncertainty = {}, {}
    for name in DATASETS:
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
    if len(sys.argv)!=2 or sys.argv[1] not in ('preflight','inference','evaluate'):
        raise SystemExit('preflight | inference | evaluate')
    paths = resolve_paths()
    try:
        result = globals()[sys.argv[1]](paths)
        print(json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
    except Exception as exc:
        directory = paths.project_runs_dir/RUN
        if directory.exists():
            write_json(directory/f'reports/{sys.argv[1]}_failure_{time.time_ns()}.json', {'error': repr(exc), 'status': 'FAILED'})
        raise


if __name__ == '__main__':
    main()
