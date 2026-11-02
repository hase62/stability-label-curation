"""Matched extended A/W/L fits; external outcomes/metrics are never opened here.

Only explicit CLI actions write files. Historical runs remain read-only. All
training, checkpoint and prediction outputs are exclusive new-run artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stdout
import csv
from fractions import Fraction
import gzip
import hashlib
import importlib.metadata
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
from types import SimpleNamespace
from typing import Any

from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as baseline
from . import bigmhc_el_positive_upweighting as prior
from . import bigmhc_fully_trained_auxiliary as reuse
from . import bigmhc_multiepoch as shared
from . import el_only_zero_shot_im as scoring
from . import el_positive_weighting_design as design
from . import el_stability_loss_adapter as binding
from .paths import resolve_paths

RUN = 'hla-extended-epoch-training-20261102'
BRANCH = 'task/hla-extended-epoch-validation'
CONFIG = 'configs/hla_extended_epoch_training.json'
PROTOCOL = 'docs/HLA_EXTENDED_EPOCH_PROTOCOL.md'
SCRIPT = 'src/stability_label_curation/hla_extended_epochs.py'


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return runner.raw.sha256_file(path)


def put(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def paths_config():
    p = resolve_paths()
    return p, read(p.repository_root / CONFIG), p.project_runs_dir / RUN


def reset(torch: Any, np: Any, seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def hashes(p, config: dict) -> dict:
    return {name: sha(p.repository_root / name) for name in config['scientific_files']}


def weights_for(train: list[dict], sidecar: Any) -> tuple[dict, list, dict]:
    """Preserve pilot formulas, using the established training-only rank domain."""
    groups = defaultdict(list)
    for row in train:
        if row['original_label'] == '1':
            score = sidecar.scores[row['source_row_id']]
            if (score.original_peptide, score.resolved_hla) != (row['peptide'], row['hla']):
                raise ValueError('Ambiguous Teacher binding')
            groups[row['hla']].append(row)
    assignments = {'W': {}, 'L': {}}
    ledger, summaries = [], {}
    for hla, rows in sorted(groups.items()):
        w = design.midrank_weights(sidecar.scores[r['source_row_id']].predicted_half_life_hours for r in rows)
        low = [min(Fraction(1), value) for value in w]
        if sum(w) != len(rows) or any(v <= 0 for v in low):
            raise ValueError('Invalid original intervention weights')
        summaries[hla] = {'positive_n': len(rows), 'W': prior.describe(w), 'L': prior.describe(low)}
        for row, genuine, lower in zip(rows, w, low, strict=True):
            identity = row['source_row_id']
            assignments['W'][identity] = binding.f32(genuine)
            assignments['L'][identity] = binding.f32(lower)
            ledger.append({'source_row_id': identity, 'peptide': row['peptide'], 'hla': hla,
                           'rank_exact': str(2*(genuine-1)+Fraction(1, 2)),
                           'W_exact': str(genuine), 'L_exact': str(lower),
                           'W_FP32': assignments['W'][identity], 'L_FP32': assignments['L'][identity]})
    return assignments, ledger, {'by_HLA': summaries, 'positive_coverage': len(ledger),
        'rank_reference': '63053_EL_training_positives_only_before_intervention',
        'negative_weight': 1, 'labels_changed': 0, 'rows_excluded': 0,
        'W': prior.describe([Fraction(r['W_exact']) for r in ledger]),
        'L': prior.describe([Fraction(r['L_exact']) for r in ledger])}


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as binary, gzip.GzipFile(fileobj=binary, mode='wb', mtime=0) as z:
        with io.TextIOWrapper(z, encoding='utf-8', newline='') as text:
            writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)


def load_rows(path: Path) -> list[dict]:
    with gzip.open(path, 'rt', newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if 'prepared_row_index' in row:
            row['prepared_row_index'] = int(row['prepared_row_index'])
    return rows


def assert_alignment(expected: list[str], actual: list[str]) -> None:
    if len(set(expected)) != len(expected) or expected != actual:
        raise ValueError('Missing, duplicate or reordered prediction source identity')


def audit() -> dict:
    """Read selected source records; never evaluate or regenerate old predictions."""
    p, c, d = paths_config()
    if d.exists():
        raise ValueError('Run exists; refusing to overwrite')
    d.mkdir(parents=True)
    evidence, pilots, curves = [], [], {}

    def source(path: Path, purpose: str) -> Any:
        if not path.exists():
            evidence.append({'source_path': str(path), 'purpose': purpose, 'status': 'NOT_FOUND'})
            return None
        evidence.append({'source_path': str(path), 'purpose': purpose, 'status': 'VERIFIED_LOCAL',
                         'size': path.stat().st_size, 'sha256': sha(path)})
        return read(path)

    for run, arms in [('task-2_17-abp-comparison', ['A', 'B', 'P']),
                      ('task-2_19-low-stability-alp-gpu', ['L', 'P']),
                      ('task-2_21-stability-auxiliary-gpu', ['S', 'P'])]:
        parent = p.project_runs_dir / run
        manifest = source(parent/'manifest.json', 'pilot Git provenance')
        for arm in arms:
            conf = source(parent/arm/'reports/training_configuration.json', 'actual pilot settings')
            item = {'run': run, 'arm': arm, 'configuration': conf,
                    'manifest': manifest, 'stages': {}, 'held_out_EL_validation': None,
                    'validation_gap': 'No held-out EL validation partition in pilot; EL_proxy uses IM dev383 labels.'}
            for stage in ('EL', 'IM'):
                record = source(parent/arm/f'reports/{stage.lower()}_stage_completed.json', 'completed pilot training')
                checkpoint = source(parent/arm/f'reports/{stage.lower()}_stage_checkpoint.json', 'pilot checkpoint identity')
                if record is None:
                    continue
                training = record['training']
                item['stages'][stage] = {'status': record['status'], 'epochs_configured': conf['epochs'][stage],
                    'completed_stage_receipt': True, 'checkpoint_receipt': checkpoint,
                    'loss': {key: value for key, value in training.items() if not isinstance(value, (dict, list))},
                    'optimizer_defaults': training.get('optimizer_defaults'),
                    'updated_parameters': training.get('updated_parameters'),
                    'step_loss_first': training['step_log'][0], 'step_loss_last': training['step_log'][-1],
                    'step_log_n': len(training['step_log'])}
            pilots.append(item)

    selected = {
        'task-2_23-el-multiepoch-baseline': ['EL_learning_curve', 'IM_from_EL_01_learning_curve',
             'IM_from_EL_10_learning_curve', 'final_all_IM_learning_curve', 'EL_epoch_selection', 'final_checkpoint'],
        'task-2_24-fully-trained-stability-auxiliary': ['scientific_configuration', 'cohort_binding',
             'S_EL_learning_curve', 'P_EL_learning_curve', 'S_IM_learning_curve', 'P_IM_learning_curve', 'completion'],
        'task-2_31-el-stability-positive-upweighting': ['scientific_configuration', 'cohort_binding',
             'W_EL_learning_curve', 'P_EL_learning_curve', 'training_completed'],
        'task-2_37-a02-measured-tm-direct-transfer': ['training_complete', 'technical_reload_repair'],
        'task-2_41b-low-stability-hard-filtering': [f'{arm}_training_completed' for arm in ['H', 'R1', 'R2', 'R3', 'R4', 'R5']],
    }
    for run, names in selected.items():
        for name in names:
            record = source(p.project_runs_dir/run/'reports'/f'{name}.json', 'long training/selection evidence')
            if record is None:
                continue
            if 'learning_curve' in name:
                curves[f'{run}/{name}'] = record
            elif run.endswith('hard-filtering'):
                curves[f'{run}/{name}'] = {k: record[k] for k in ['epochs', 'curve', 'status', 'seconds', 'checkpoint']}
            elif run.endswith('direct-transfer') and name == 'training_complete':
                # Keep fit histories/parameter policy, never copy individual data.
                curves[f'{run}/{name}'] = record
    for name in c['audit_code']:
        path = p.repository_root/name
        evidence.append({'source_path': str(path), 'purpose': 'audited implementation',
                         'status': 'VERIFIED_LOCAL', 'size': path.stat().st_size, 'sha256': sha(path)})
    put(d/'audit/pilot_evidence.json', pilots)
    put(d/'audit/long_training_evidence.json', curves)
    put(d/'audit/source_inventory.json', evidence)
    return {'status': 'AUDIT_COLLECTED', 'pilots': len(pilots), 'sources': len(evidence)}


def prepare() -> dict:
    """Authenticate population/weights, original A, runtime and seed initializations."""
    import numpy as np
    import torch
    p, c, d = paths_config()
    if (d/'reports/preflight.json').exists():
        raise ValueError('Preflight already frozen')
    old = prior.configuration(p)
    extended = read(p.repository_root/'configs/bigmhc_fully_trained_auxiliary_task2_24.json')
    old['inputs'].update({key: extended['inputs'][key] for key in ('IM', 'IM_provenance')})
    resolved = baseline.inputs(p, old)
    base, parent = prior.baseline_evidence(p, old)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    if sha(p.project_data_dir/'teacher-v0-recovered/checkpoints/teacher_model.json') != old['model_sha256']:
        raise ValueError('Teacher identity differs')
    train, val, cohort = prior.populations(resolved, sidecar)
    im = shared.original_rows(resolved)
    # source_locator is a nested authentication receipt, not a model input.
    for row in im:
        row.pop('source_locator', None)
    assignments, ledger, weight_proof = weights_for(train, sidecar)
    if len(ledger) != 63053:
        raise ValueError('Teacher training coverage changed')
    for stage, rows in [('EL_train', train), ('EL_validation', val), ('IM_train', im)]:
        write_rows(d/f'inputs/{stage}.csv.gz', rows)
    write_rows(d/'inputs/training_only_weights.csv.gz', ledger)
    put(d/'reports/weights.json', weight_proof)
    put(d/'reports/cohort.json', {**cohort, 'IM_rows': len(im), 'IM_classes': dict(Counter(r['original_label'] for r in im))})
    for name, spec in c['cohorts'].items():
        original = p.project_runs_dir/spec['path']
        if sha(original) != spec['sha256']:
            raise ValueError('Frozen external identities changed')
        rows = [json.loads(line) for line in original.read_text().splitlines()]
        if len(rows) != spec['n'] or len({r['source_id'] for r in rows}) != spec['n'] or any('label' in r or 'scores' in r for r in rows):
            raise ValueError('External identity population/allowlist failed')
        destination = d/f'cohorts/{name}_identities.jsonl'
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(original.read_bytes())
    runner.cuda_visibility()
    runner.seed_runtime(torch, np, old)
    device = runner.runtime_device(torch, old)
    runtime = {'platform': platform.platform(), 'versions': {n: importlib.metadata.version(n) for n in ('torch', 'numpy', 'pandas', 'psutil')}, 'device': runner.device_report(torch, device)}
    historical = read(base/'reports/execution_started.json')
    if any(runtime[k] != historical[k] for k in ['versions', 'device']):
        raise ValueError('Historical runtime compatibility failed')
    initializations = {}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        for seed in c['seeds']:
            reset(torch, np, seed)
            model = runner.on_device(BigMHC(), device)
            item = {'state': runner.state_hashes(model), 'RNG': binding.rng_identity(torch, np)}
            if seed == 42 and item != read(base/'reports/initial_EL_state.json'):
                # Historical receipt may include extra metadata, compare actual fields.
                ref = read(base/'reports/initial_EL_state.json')
                if any(item[k] != ref[k] for k in item):
                    raise ValueError('Seed42 historical initialization mismatch')
            initializations[str(seed)] = item
            del model
        # Reload both true historical checkpoints; never substitute EL for IM.
        final_im = read(base/'reports/final_checkpoint.json')
        for stage, relative, receipt in [('EL', parent['checkpoint'], parent), ('IM', 'checkpoints/final_all_IM', final_im)]:
            keys = list(initializations['42']['state'])
            path = base/relative
            files = runner.checkpoint_identity(path, keys)
            expected = c['A_checkpoint_map_sha256'][stage]
            if scoring.digest(files) != expected:
                raise ValueError('Historical A checkpoint directory identity mismatch')
            model = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
            state = runner.state_hashes(model)
            put(d/f'reports/A_42_{stage}_checkpoint.json', {'checkpoint': str(path), 'files': files, 'state': state,
                'state_keys': keys, 'epochs': 10 if stage == 'EL' else 20, 'reused': True, 'strict_reload': True,
                'source_receipt': str(base/('reports/EL_epoch_selection.json' if stage == 'EL' else 'reports/final_checkpoint.json'))})
            del model
    frozen_inputs = {str(f.relative_to(d)): sha(f) for folder in ('inputs', 'cohorts') for f in sorted((d/folder).iterdir()) if f.is_file()}
    put(d/'reports/initializations.json', initializations)
    put(d/'reports/preflight.json', {'status': 'PASS', 'config': c, 'runtime': runtime,
        'scientific_hashes': hashes(p, c), 'frozen_inputs': frozen_inputs,
        'authenticated_inputs': {key: {'path': str(path), 'sha256': sha(path)} for key, path in resolved.items()},
        'old_training_config': old, 'A_checkpoint': parent, 'label_changes': 0, 'external_outcomes_opened': False})
    return {'status': 'PASS', 'seeds': c['seeds'], 'weights': {m: weight_proof[m] for m in ('W', 'L')}, 'cohort': cohort}


def require():
    p, c, d = paths_config()
    proof = read(d/'reports/preflight.json')
    if proof['status'] != 'PASS' or proof['scientific_hashes'] != hashes(p, c):
        raise ValueError('Frozen scientific implementation changed')
    if git(p.repository_root, 'branch', '--show-current') != BRANCH or git(p.repository_root, 'status', '--porcelain'):
        raise ValueError('Clean committed isolated task branch required')
    for name, expected in proof['frozen_inputs'].items():
        if sha(d/name) != expected:
            raise ValueError('Frozen input changed: '+name)
    return p, c, d, proof


def wait_reference(d: Path, base: Path, seed: int, stage: str, epoch: int) -> dict:
    path = (base/f'reports/{"EL" if stage == "EL" else "final_all_IM"}_epoch_{epoch:02d}.json'
            if seed == 42 else d/f'reports/A_{seed}_{stage}_epoch_{epoch:02d}.json')
    while not path.exists():
        if (d/f'reports/A_{seed}_FAILED.json').exists():
            raise RuntimeError('Paired baseline failed; no approximation permitted')
        time.sleep(2)
    # Baseline reports are published by atomic rename after the whole epoch.
    return read(path)


def publish(path: Path, value: Any) -> None:
    temp = path.with_suffix('.pending')
    put(temp, value)
    if path.exists():
        raise ValueError('Refuse epoch overwrite')
    temp.rename(path)


def save_complete(torch, BigMHC, Dataset, model, encodings, rows, path: Path, device: str) -> dict:
    state = runner.state_hashes(model)
    keys = list(state)
    runner.reserve_checkpoint(path)
    runner.save_checkpoint(model, path, transfer=False, device=device)
    with shared.preserve_rng(torch, __import__('numpy')):
        probe = reuse.native_dataset(Dataset, encodings, rows[:16])
        before = runner.predict(torch, model, probe, 16, device)
        loaded = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
        after = runner.predict(torch, loaded, probe, 16, device)
        if before != after or runner.state_hashes(loaded) != state:
            raise ValueError('Final checkpoint strict reload failed')
        del loaded
    return {'checkpoint': str(path), 'state': state, 'state_keys': keys,
            'files': runner.checkpoint_identity(path, keys), 'strict_reload': True, 'probe_prediction_equal': True}


def train(arm: str, seed: int) -> dict:
    import numpy as np
    import torch
    p, c, d, proof = require()
    if arm not in ('A', 'W', 'L') or seed not in c['seeds'] or (arm == 'A' and seed == 42):
        raise ValueError('Unauthorized fit or baseline retraining')
    prefix = f'{arm}_{seed}'
    put(d/f'reports/{prefix}_started.json', {'status': 'STARTED', 'arm': arm, 'seed': seed,
        'commit': git(p.repository_root, 'rev-parse', 'HEAD'), 'scientific_hashes': proof['scientific_hashes'],
        'started_UTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    old = dict(proof['old_training_config'], seed=seed)
    resolved = {k: Path(v['path']) for k, v in proof['authenticated_inputs'].items()}
    runner.cuda_visibility()
    runner.seed_runtime(torch, np, old)
    device = runner.runtime_device(torch, old)
    encodings = reuse.encodings_for(torch, resolved['reference'])
    el, val, im = [load_rows(d/f'inputs/{name}.csv.gz') for name in ('EL_train', 'EL_validation', 'IM_train')]
    ledger = load_rows(d/'inputs/training_only_weights.csv.gz')
    adapter = None if arm == 'A' else SimpleNamespace(mode='B' if arm == 'W' else 'L', weights={r['source_row_id']: float(r[f'{arm}_FP32']) for r in ledger})
    base = p.project_runs_dir/'task-2_23-el-multiepoch-baseline'
    started = time.monotonic()
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        reset(torch, np, seed)
        model = runner.on_device(BigMHC(), device)
        expected = read(d/'reports/initializations.json')[str(seed)]
        if runner.state_hashes(model) != expected['state'] or binding.rng_identity(torch, np) != expected['RNG']:
            raise ValueError('Paired initial model/RNG mismatch')
        for stage, epochs, rows in [('EL', 10, el), ('IM', 20, im)]:
            if stage == 'IM':
                del model, optimizer, native
                model = runner.load_checkpoint(torch, BigMHC, Path(checkpoint['checkpoint']), checkpoint['state_keys'], device=device)
                if runner.state_hashes(model) != checkpoint['state']:
                    raise ValueError('Explicit EL-to-IM reload mismatch')
                reset(torch, np, seed)
            stage_initial = runner.state_hashes(model)
            if stage == 'EL' and adapter is not None:
                native = prior.WeightedDataset(reuse.native_dataset(Dataset, encodings, rows), rows, adapter)
            else:
                native = baseline.AuditedDataset(reuse.native_dataset(Dataset, encodings, rows), [r['prepared_row_index'] for r in rows])
            optimizer = torch.optim.AdamW([v for k, v in model.named_parameters() if stage == 'EL' or k in runner.TRANSFER], lr=old['learning_rate'])
            curve, cumulative = [], 0
            torch.cuda.reset_peak_memory_stats()
            for epoch in range(1, epochs+1):
                ref = wait_reference(d, base, seed, stage, epoch) if arm != 'A' else None
                before = binding.rng_identity(torch, np)
                if ref is not None and before != ref['RNG_before']:
                    raise ValueError('Paired pre-epoch RNG mismatch')
                start = time.monotonic()
                training = runner.train_epoch(torch, model, native, old, stage == 'IM', device,
                    loss_adapter=adapter if stage == 'EL' else None,
                    expected_batches=ref['sampled_batch_sha256'] if ref is not None else None, optimizer=optimizer)
                torch.cuda.synchronize()
                after = binding.rng_identity(torch, np)
                if ref is not None:
                    reuse.check_schedule(training, ref, before, after)
                cumulative += training['optimization_steps']
                steps = shared.optimizer_steps(optimizer)
                if len(steps) != (36 if stage == 'EL' else 4) or any(s != cumulative for s in steps):
                    raise ValueError('Persistent optimizer step mismatch')
                training.update(epoch=epoch, seed=seed, arm=arm, RNG_before=before, RNG_after=after,
                    cumulative_optimizer_steps=cumulative, training_seconds=time.monotonic()-start,
                    paired_reference=None if ref is None else 'A_same_seed', optimizer_state_steps=steps)
                publish(d/f'reports/{prefix}_{stage}_epoch_{epoch:02d}.json', training)
                with shared.preserve_rng(torch, np):
                    probabilities, bce = shared.evaluate(torch, model, reuse.native_dataset(Dataset, encodings, val if stage == 'EL' else im), device)
                metric = {'epoch': epoch, 'arm': arm, 'seed': seed, 'stage': stage,
                    'train_update_BCE': training['row_weighted_BCE_loss'], 'training_seconds': training['training_seconds'],
                    'validation_BCE': bce if stage == 'EL' else None,
                    'IM_training_eval_BCE': bce if stage == 'IM' else None,
                    'external_IM_metrics_computed': False}
                if stage == 'EL':
                    metric.update(baseline.el_metrics(val, probabilities))
                put(d/f'reports/{prefix}_{stage}_metrics_{epoch:02d}.json', metric)
                curve.append(metric)
                print('EPOCH_COMPLETE', prefix, stage, epoch, json.dumps(metric), flush=True)
            checkpoint = save_complete(torch, BigMHC, Dataset, model, encodings, rows,
                d/f'checkpoints/{prefix}_{stage}_epoch_{epochs:02d}', device)
            changed = [k for k, v in checkpoint['state'].items() if stage_initial[k] != v]
            if stage == 'IM' and set(changed) != set(runner.TRANSFER):
                raise ValueError('IM changed non-native transfer parameters')
            checkpoint.update(epochs=epochs, arm=arm, seed=seed, changed_parameters=changed,
                parent_EL=None if stage == 'EL' else str(d/f'checkpoints/{prefix}_EL_epoch_10'),
                peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_GPU_reserved_bytes=torch.cuda.max_memory_reserved(), optimizer_steps=cumulative)
            put(d/f'reports/{prefix}_{stage}_checkpoint.json', checkpoint)
            put(d/f'reports/{prefix}_{stage}_learning_curve.json', {'epochs': curve})
        del model, optimizer, native
    result = {'status': 'COMPLETE', 'EL_epochs': 10, 'IM_epochs': 20, 'seed': seed, 'arm': arm,
        'seconds': time.monotonic()-started, 'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    put(d/f'reports/{prefix}_completed.json', result)
    return result


def infer_one(arm: str, seed: int) -> dict:
    """Pure label-blind model forward pass. No outcome reader/metric invocation."""
    import numpy as np
    import torch
    p, c, d, proof = require()
    old = dict(proof['old_training_config'], seed=seed)
    runner.cuda_visibility()
    runner.seed_runtime(torch, np, old)
    device = runner.runtime_device(torch, old)
    resolved = {k: Path(v['path']) for k, v in proof['authenticated_inputs'].items()}
    encodings = reuse.encodings_for(torch, resolved['reference'])
    outputs = {}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        for stage in ('EL', 'IM'):
            checkpoint = read(d/f'reports/{arm}_{seed}_{stage}_checkpoint.json')
            path = Path(checkpoint['checkpoint'])
            if runner.checkpoint_identity(path, checkpoint['state_keys']) != checkpoint['files']:
                raise ValueError('Frozen checkpoint file integrity failed')
            model = runner.load_checkpoint(torch, BigMHC, path, checkpoint['state_keys'], device=device)
            if runner.state_hashes(model) != checkpoint['state']:
                raise ValueError('Loaded checkpoint tensor mismatch')
            model.eval()
            for cohort, spec in c['cohorts'].items():
                rows = [json.loads(line) for line in (d/f'cohorts/{cohort}_identities.jsonl').read_text().splitlines()]
                native = scoring.native_dataset(Dataset, torch, encodings, rows)
                native.makebats(16, shuffle=False, negfrac=None)
                predictions, emitted = [], []
                with torch.no_grad():
                    for index in range(len(native)):
                        batch = native[index]
                        logits, _ = model(batch.mhc.float().to(device), batch.pep.float().to(device))
                        ids = native.getbat(index, enc=False)['_source_id'].tolist()
                        emitted.extend(ids)
                        for identity, logit, prob in zip(ids, logits.cpu().tolist(), torch.sigmoid(logits).cpu().tolist(), strict=True):
                            if not math.isfinite(logit) or not math.isfinite(prob) or not 0 <= prob <= 1:
                                raise ValueError('Nonfinite/misoriented native score')
                            predictions.append({'source_id': identity, 'native_logit': logit, 'positive_probability': prob})
                assert_alignment([r['source_id'] for r in rows], emitted)
                output = d/f'predictions/{arm}_{seed}_{stage}_{cohort}.jsonl'
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('x') as stream:
                    for row in predictions:
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
                outputs[output.name] = {'path': str(output), 'n': len(predictions), 'sha256': sha(output),
                    'ordered_source_id_sha256': scoring.digest(emitted), 'checkpoint': checkpoint['checkpoint'],
                    'checkpoint_map_sha256': scoring.digest(checkpoint['files']), 'outcomes_accessed': False}
            del model
    put(d/f'reports/{arm}_{seed}_prediction_receipt.json', outputs)
    return outputs


def supervise() -> dict:
    """Durable worker pool; failure stops pending jobs, never retries a fit."""
    p, c, d, proof = require()
    if not (d/'reports/focused_tests.json').exists() or read(d/'reports/focused_tests.json')['status'] != 'PASS':
        raise ValueError('Passing focused checks required before training')
    commit = git(p.repository_root, 'rev-parse', 'HEAD')
    put(d/'reports/execution_started.json', {'status': 'RUNNING', 'commit': commit,
        'scientific_hashes': proof['scientific_hashes'], 'jobs': c['jobs'], 'maximum_concurrency': c['maximum_concurrency'],
        'started_UTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    pending, running, complete = list(c['jobs']), [], []
    failed = False
    while pending or running:
        while pending and len(running) < c['maximum_concurrency'] and not failed:
            arm, seed = pending.pop(0)
            log = (d/f'logs/{arm}_{seed}_worker.log').open('x')
            process = subprocess.Popen([sys.executable, '-m', 'stability_label_curation.hla_extended_epochs', 'fit-and-predict', '--arm', arm, '--seed', str(seed)],
                cwd=p.repository_root, stdout=log, stderr=subprocess.STDOUT)
            running.append((process, log, arm, seed))
        for entry in list(running):
            process, log, arm, seed = entry
            status = process.poll()
            if status is None:
                continue
            log.close()
            running.remove(entry)
            complete.append({'arm': arm, 'seed': seed, 'exit_code': status})
            if status:
                failed = True
        if failed and not running:
            break
        time.sleep(5)
    if not failed:
        # A42 is historical and never retrained; fresh label-blind score export.
        log = (d/'logs/A_42_prediction.log').open('x')
        with log, redirect_stdout(log):
            infer_one('A', 42)
    result = {'status': 'FAILED' if failed else 'COMPLETE', 'jobs': complete,
              'unstarted_jobs': pending, 'commit': commit, 'external_IM_evaluation': False}
    put(d/'reports/execution_completed.json', result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'prepare', 'supervise', 'fit-and-predict', 'predict'])
    parser.add_argument('--arm', choices=['A', 'W', 'L'])
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    if args.action in {'fit-and-predict', 'predict'}:
        try:
            if args.action == 'fit-and-predict':
                train(args.arm, args.seed)
            result = infer_one(args.arm, args.seed)
        except Exception as error:
            _, _, d = paths_config()
            put(d/f'reports/{args.arm}_{args.seed}_FAILED.json', {'error': repr(error)})
            raise
    else:
        result = {'audit': audit, 'prepare': prepare, 'supervise': supervise}[args.action]()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
