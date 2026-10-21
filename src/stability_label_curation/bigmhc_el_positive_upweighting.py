"""Task 2.31: authentic matched ten-epoch EL positive upweighting, no IM work."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import csv
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from typing import Any

from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as baseline
from . import bigmhc_multiepoch as shared
from . import bigmhc_fully_trained_auxiliary as reuse
from . import el_stability_loss_adapter as binding
from . import el_positive_weighting_design as design
from .paths import StoragePaths, resolve_paths
from .replicate_stability_association import write_json, quantile

RUN = 'task-2_31-el-stability-positive-upweighting'
BRANCH = 'task/2.31-el-stability-positive-upweighting'
CONFIG = 'configs/bigmhc_el_positive_upweighting_task2_31.json'
PROTOCOL = 'docs/BIGMHC_EL_POSITIVE_UPWEIGHTING_TASK2_31_PROTOCOL.md'
BASE = '143aeea4189257eaa86b042f69559c2ec5dbadb6'


def scientific_hashes(paths: StoragePaths) -> dict[str, str]:
    names = [CONFIG, PROTOCOL, 'src/stability_label_curation/bigmhc_el_positive_upweighting.py',
             'tests/test_bigmhc_el_positive_upweighting.py']
    names += ['src/stability_label_curation/'+name+'.py' for name in
              ['bigmhc_baseline_runner', 'bigmhc_el_multiepoch', 'bigmhc_multiepoch',
               'bigmhc_fully_trained_auxiliary', 'el_stability_loss_adapter',
               'el_positive_weighting_design', 'third_party_evaluation', 'stability_teacher']]
    return {name: runner.raw.sha256_file(paths.repository_root/name) for name in names}


def configuration(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    if (config['EL_epochs'] != 10 or config['IM_training_authorized'] or config['coefficient'] != '0.5'
            or config['seed'] != 42 or config['batch_size'] != 16 or config['learning_rate'] != 5e-5
            or config['bootstrap_draws'] != 1000 or config['bootstrap_seed'] != 23142
            or any(k.startswith('IM') for k in config['inputs'])):
        raise ValueError('Frozen EL-only specification changed')
    return config


def populations(resolved: dict[str, Path], sidecar: binding.LossAdapter) -> tuple[list[dict], list[dict], dict]:
    """Use the original split manifest, source identities and labels; never resplit."""
    with resolved['reference'].open(newline='') as stream:
        allowed = {runner.data.canonical_hla(r[0]) for r in list(csv.reader(stream))[1:]}
    groups: dict[str, list[dict]] = {p: [] for p in ('train', 'validation', 'excluded')}
    identity_hash = hashlib.sha256()
    archive = sidecar.manifest['archive_sha256']
    with gzip.open(resolved['EL_split'], 'rt', newline='') as stream:
        for row, record in zip(runner.input_rows(resolved['EL'], allowed), csv.DictReader(stream), strict=True):
            if (int(record['original_prepared_row_index']) != row['prepared_row_index']
                    or [record['HLA'], record['peptide'], record['original_label']]
                    != [row['hla'], row['peptide'], row['original_label']]
                    or record['partition'] not in groups
                    or record['source_row_id'] != design.prior.pilot.row_id(archive, 'el_train.csv', int(record['row_index']))):
                raise ValueError('Frozen source/split identity mismatch')
            binding.original_fields(record, 'EL')
            row['source_row_id'] = record['source_row_id']
            if row['original_label'] == '1':
                score = sidecar.scores.get(row['source_row_id'])
                if score is None or any(getattr(score, key) != record[field] for key, field in {
                    'prepared_row_index': 'original_prepared_row_index', 'source_row_index': 'row_index',
                    'source_row_sha256': 'source_row_sha256', 'original_hla': 'original_hla',
                    'resolved_hla': 'HLA', 'original_peptide': 'peptide', 'original_label': 'original_label'}.items()):
                    raise ValueError('Teacher/source-row/peptide/HLA binding is ambiguous')
            elif row['source_row_id'] in sidecar.scores:
                raise ValueError('Teacher positive score attached to negative')
            groups[record['partition']].append(row)
            identity_hash.update(binding.digest(record).encode())
    expected = {'train': {'1': 63053, '0': 1245143}, 'validation': {'1': 7006, '0': 138365},
                'excluded': {'1': 10, '0': 1}}
    if {key: dict(Counter(r['original_label'] for r in rows)) for key, rows in groups.items()} != expected:
        raise ValueError('Frozen class populations changed')
    train, validation = groups['train'], groups['validation']
    train_peptides, validation_peptides = ({baseline.normalized(r) for r in part} for part in (train, validation))
    if train_peptides & validation_peptides:
        raise ValueError('EL validation peptides exposed to EL fitting')
    return train, validation, {'partition_classes': expected,
        'partitions': {k: len(v) for k, v in groups.items()},
        'unique_peptides_train': len(train_peptides), 'unique_peptides_validation': len(validation_peptides),
        'HLA_train': len({r['hla'] for r in train}), 'HLA_validation': len({r['hla'] for r in validation}),
        'peptide_overlap': 0, 'pair_overlap': 0,
        'source_manifest_binding_sha256': identity_hash.hexdigest(),
        'positive_score_bindings': 63053, 'rank_reference': 'training_positives_only',
        'labels_preserved': True, 'IM_payloads_opened': False}


def describe(values: list[Fraction]) -> dict:
    total = sum(values, Fraction())
    ordered = sorted(values)
    return {'n': len(values), 'minimum': float(ordered[0]), 'median': float((ordered[(len(values)-1)//2]+ordered[len(values)//2])/2),
            'mean': float(total/len(values)), 'maximum': float(ordered[-1]),
            'total': float(total), 'total_exact': str(total),
            'unit_weight_n': values.count(Fraction(1)), 'upweighted_n': sum(v > 1 for v in values),
            'downweighted_n': sum(v < 1 for v in values)}


def describe_ranks(values: list[Fraction]) -> dict:
    summary = describe(values)
    return {k: summary[k] for k in ('n', 'minimum', 'median', 'mean', 'maximum')}


class Weights:
    """Training-only ranks and exact per-HLA permutation, FP32 conversion once."""
    def __init__(self, train: list[dict], sidecar: binding.LossAdapter):
        groups = defaultdict(list)
        for row in train:
            if row['original_label'] == '1':
                groups[row['hla']].append(sidecar.scores[row['source_row_id']])
        self.weights = {'W': {}, 'P': {}}
        self.ledger, by_hla, all_weights, all_ranks = [], {}, [], []
        for hla, rows in sorted(groups.items()):
            ids = [r.source_row_id for r in rows]
            historical = design.midrank_weights(r.predicted_half_life_hours for r in rows)
            ranks = [2*(value-1)+Fraction(1, 2) for value in historical]
            w = [max(Fraction(1), value) for value in historical]
            p = design.permuted_weights(ids, w, hla, 42)
            if sorted(w) != sorted(p) or any(v < 1 or v > Fraction(5, 4) for v in w):
                raise ValueError('Weight/permutation invariants failed')
            for mode, values in [('W', w), ('P', p)]:
                self.weights[mode].update((identity, binding.f32(value)) for identity, value in zip(ids, values, strict=True))
            if sorted(self.weights['W'][i] for i in ids) != sorted(self.weights['P'][i] for i in ids):
                raise ValueError('FP32 permutation multiset differs')
            by_hla[hla] = {'weights': describe(w), 'ranks': describe_ranks(ranks),
                           'identical_exact_and_FP32_multisets': True,
                           'positive_FP32_mass': math.fsum(self.weights['W'][i] for i in ids),
                           'changed_assignments': sum(a != b for a, b in zip(w, p)),
                           'assignment_sha256': {m: binding.digest(sorted(zip(ids, map(str, vals)))) for m, vals in [('W', w), ('P', p)]}}
            all_weights.extend(w); all_ranks.extend(ranks)
            for row, rank, genuine, permuted in zip(rows, ranks, w, p, strict=True):
                self.ledger.append({'prepared_row_index': row.prepared_row_index, 'source_row_id': row.source_row_id,
                    'source_row_sha256': row.source_row_sha256, 'peptide': row.original_peptide, 'HLA': hla,
                    'Teacher_half_life_hours': row.predicted_half_life_hours, 'training_percentile_exact': str(rank),
                    'training_percentile': float(rank), 'W_exact': str(genuine), 'P_exact': str(permuted),
                    'W_FP32': self.weights['W'][row.source_row_id], 'P_FP32': self.weights['P'][row.source_row_id]})
        self.evidence = {'overall': describe(all_weights), 'ranks': describe_ranks(all_ranks), 'by_HLA': by_hla,
                         'per_HLA_mass_and_multiset_equal': True, 'negative_weight': 1.0,
                         'rank_reference_n': len(all_ranks), 'source_binding_coverage': len(self.ledger),
                         'permutation_stream': 'Historical domain-separated per-HLA seed42; global RNG untouched',
                         'labels_changed': 0, 'observations_removed': 0}


class WeightedDataset(baseline.AuditedDataset):
    def __init__(self, native: Any, rows: list[dict], adapter: Any):
        super().__init__(native, [r['prepared_row_index'] for r in rows])
        self.adapter = adapter
        native.df['_source_row_id'] = [r['source_row_id'] for r in rows]

    def __getitem__(self, index: int) -> Any:
        batch = super().__getitem__(index)
        frame = self.native.getbat(index, enc=False)
        weights = []
        for identity, label in frame[['_source_row_id', 'tgt']].itertuples(index=False, name=None):
            if float(label) not in (0, 1):
                raise ValueError('Original labels changed')
            if label == 1:
                if identity not in self.adapter.weights:
                    raise ValueError('Positive-anchor weight unavailable')
                weights.append(self.adapter.weights[identity])
            else:
                if identity in self.adapter.weights:
                    raise ValueError('Positive weight bound to negative')
                weights.append(1.0)
        if sum(batch.tgt.tolist()) != 1:
            raise ValueError('Native EL batch is not one-positive anchored')
        batch.EL_loss_weights = weights
        return batch


def baseline_evidence(paths: StoragePaths, config: dict) -> tuple[Path, dict]:
    directory = paths.project_runs_dir/config['baseline_run_id']
    for name, expected in config['baseline_receipts'].items():
        if runner.raw.sha256_file(directory/name) != expected:
            raise ValueError('Pinned A EL receipt/prediction changed: '+name)
    selection = json.loads((directory/'reports/EL_epoch_selection.json').read_text())
    parent = next(c for c in selection['checkpoint_lineage'] if c['epoch'] == 10)
    keys = json.loads((directory/'reports/EL_epoch_10.json').read_text())['updated_parameters']
    if parent['checkpoint'] != 'checkpoints/EL_epoch_10' or len(keys) != 36:
        raise ValueError('Wrong A EL checkpoint')
    if runner.checkpoint_identity(directory/parent['checkpoint'], keys) != parent['files']:
        raise ValueError('A EL checkpoint files changed')
    return directory, parent


def saved_A_predictions(directory: Path, validation: list[dict]) -> list[float]:
    with (directory/'predictions/EL_epoch_10.csv').open(newline='') as stream:
        predictions = []
        for record, row in zip(csv.DictReader(stream), validation, strict=True):
            if [int(record['original_prepared_row_index']), record['HLA'], record['peptide'], record['original_label']] != [row['prepared_row_index'], row['hla'], row['peptide'], row['original_label']]:
                raise ValueError('A saved validation prediction/source order differs')
            probability = float(record['probability'])
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError('A output invalid')
            predictions.append(probability)
    return predictions


def preflight(paths: StoragePaths) -> dict:
    import numpy as np
    import torch
    config = configuration(paths)
    directory = paths.project_runs_dir/RUN
    if directory.exists():
        raise ValueError('Task run already exists; refusing overwrite')
    resolved = baseline.inputs(paths, config)
    base, parent = baseline_evidence(paths, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    bundle = paths.project_data_dir/'teacher-v0-recovered'
    if (runner.raw.sha256_file(bundle/'checkpoints/teacher_model.json') != config['model_sha256']
            or sidecar.manifest['Teacher_model_sha256'] != config['model_sha256']):
        raise ValueError('Original Teacher/sidecar model binding differs')
    train, validation, cohort = populations(resolved, sidecar)
    weights = Weights(train, sidecar)
    if weights.evidence['source_binding_coverage'] != 63053:
        raise ValueError('Training positive score coverage differs')
    runner.cuda_visibility(); device = runner.runtime_device(torch, config)
    runner.seed_runtime(torch, np, config)
    runtime = {'platform': platform.platform(), 'versions': {n: importlib.metadata.version(n) for n in ('torch', 'numpy', 'pandas', 'psutil')}, 'device': runner.device_report(torch, device)}
    previous_runtime = json.loads((base/'reports/execution_started.json').read_text())
    if any(runtime[k] != previous_runtime[k] for k in ('versions', 'device')):
        raise ValueError('Runtime differs from historical A')
    encodings = reuse.encodings_for(torch, resolved['reference'])
    initial = json.loads((base/'reports/initial_EL_state.json').read_text())
    probabilities = saved_A_predictions(base, validation)
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        for mode in ('W', 'P'):
            reuse.reset_rng(torch, np)
            model = runner.on_device(BigMHC(), device)
            if runner.state_hashes(model) != initial['state'] or binding.rng_identity(torch, np) != initial['RNG']:
                raise ValueError('W/P original epoch-0 initialization/RNG differs from A')
            del model
        with shared.preserve_rng(torch, np):
            ordered_keys = json.loads((base/'reports/EL_epoch_10.json').read_text())['updated_parameters']
            model = runner.load_checkpoint(torch, BigMHC, base/parent['checkpoint'], ordered_keys, device=device)
            if runner.state_hashes(model) != parent['state']:
                raise ValueError('A strict EL reload differs')
            probe, _ = shared.evaluate(torch, model, reuse.native_dataset(Dataset, encodings, validation[:16]), device)
            if probe != probabilities[:16]:
                raise ValueError('A reuse incompatible; stop before training and implement authorized full scoring pathway')
            del model
        # Recreate original post-constructor RNG before all native sampler checks.
        reuse.reset_rng(torch, np)
        model = runner.on_device(BigMHC(), device); del model
        sampling = reuse.sampler_preflight(torch, np, Dataset, encodings, train, base, 'EL', 10, config)
    directory.mkdir(parents=True, exist_ok=False)
    for name in ('reports', 'logs', 'processed', 'checkpoints', 'predictions'):
        (directory/name).mkdir()
    write_json(directory/'reports/scientific_configuration.json', config)
    write_json(directory/'reports/cohort_binding.json', cohort)
    write_json(directory/'reports/weight_permutation.json', weights.evidence)
    write_json(directory/'reports/sampler_preflight.json', sampling)
    write_json(directory/'reports/initialization.json', initial)
    write_json(directory/'reports/A_EL_checkpoint.json', {**parent, 'runtime': runtime,
        'reused_validation_predictions': True, 'ordered_validation_rows_verified': len(probabilities),
        'same_batch_probe_bitwise_equal': True, 'probe_n': 16,
        'checkpoint_map_sha256': hashlib.sha256(json.dumps(parent['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()})
    with gzip.open(directory/'processed/training_positive_weights.csv.gz', 'xt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(weights.ledger[0])); writer.writeheader(); writer.writerows(weights.ledger)
    frozen_names = ['reports/scientific_configuration.json', 'reports/cohort_binding.json', 'reports/weight_permutation.json',
                    'reports/sampler_preflight.json', 'reports/initialization.json', 'reports/A_EL_checkpoint.json', 'processed/training_positive_weights.csv.gz']
    proof = {'status': 'passed', 'scientific_hashes': scientific_hashes(paths), 'runtime': runtime,
             'cohort': cohort, 'frozen_artifact_sha256': {name: runner.raw.sha256_file(directory/name) for name in frozen_names},
             'scientific_optimizer_updates': 0, 'A_retrained': False, 'Teacher_retrained': False}
    write_json(directory/'reports/preflight.json', proof)
    return {'status': 'passed', 'cohort': cohort, 'weights': weights.evidence['overall']}


def execute(paths: StoragePaths) -> dict:
    from types import SimpleNamespace
    import numpy as np
    import torch
    config = configuration(paths); directory = paths.project_runs_dir/RUN
    proof = json.loads((directory/'reports/preflight.json').read_text())
    if proof['status'] != 'passed' or proof['scientific_hashes'] != scientific_hashes(paths):
        raise ValueError('Scientific implementation/configuration changed after preflight')
    for name, expected in proof['frozen_artifact_sha256'].items():
        if runner.raw.sha256_file(directory/name) != expected:
            raise ValueError('Preflight artifact changed')
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH or git('merge-base', BASE, 'HEAD') != BASE:
        raise ValueError('Clean committed authorized Task 2.31 branch required')
    gate = json.loads((directory/'reports/focused_tests.json').read_text())
    if gate['status'] != 'passed' or gate['skipped'] or gate['scientific_hashes'] != scientific_hashes(paths):
        raise ValueError('Passing focused CUDA checks required')
    resolved = baseline.inputs(paths, config); base, parent = baseline_evidence(paths, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    train, validation, cohort = populations(resolved, sidecar)
    if cohort != proof['cohort']:
        raise ValueError('Cohort changed after preflight')
    weights = Weights(train, sidecar)
    if weights.evidence != json.loads((directory/'reports/weight_permutation.json').read_text()):
        raise ValueError('Weights changed after preflight')
    runner.cuda_visibility(); device = runner.runtime_device(torch, config); runner.seed_runtime(torch, np, config)
    encodings = reuse.encodings_for(torch, resolved['reference'])
    initial = json.loads((directory/'reports/initialization.json').read_text())
    started = time.monotonic()
    write_json(directory/'reports/execution_started.json', {'status': 'started', 'commit': git('rev-parse', 'HEAD'), 'scientific_hashes': scientific_hashes(paths), 'runtime': proof['runtime']})
    curves, finals = {}, {}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        for mode in ('W', 'P'):
            reuse.reset_rng(torch, np)
            model = runner.on_device(BigMHC(), device)
            if runner.state_hashes(model) != initial['state'] or binding.rng_identity(torch, np) != initial['RNG']:
                raise ValueError('Scientific initialization differs from A')
            write_json(directory/f'reports/{mode}_initialization.json', {'state': runner.state_hashes(model), 'RNG': binding.rng_identity(torch, np)})
            adapter = SimpleNamespace(mode=mode, weights=weights.weights[mode])
            native = WeightedDataset(reuse.native_dataset(Dataset, encodings, train), train, adapter)
            val_native = reuse.native_dataset(Dataset, encodings, validation)
            optimizer = torch.optim.AdamW(model.parameters(), lr=config['learning_rate'])
            curve, cumulative = [], 0
            stage_start = time.monotonic(); torch.cuda.reset_peak_memory_stats(0)
            for epoch in range(1, 11):
                reference = json.loads((base/f'reports/EL_epoch_{epoch:02d}.json').read_text())
                before = binding.rng_identity(torch, np)
                if before != reference['RNG_before']:
                    raise ValueError('Scientific pre-epoch RNG differs from historical A')
                epoch_start = time.monotonic()
                training = runner.train_epoch(torch, model, native, config, False, device,
                    loss_adapter=adapter, expected_batches=reference['sampled_batch_sha256'], optimizer=optimizer)
                torch.cuda.synchronize(0); training_seconds = time.monotonic()-epoch_start
                after = binding.rng_identity(torch, np)
                reuse.check_schedule(training, reference, before, after)
                cumulative += training['optimization_steps']; steps = shared.optimizer_steps(optimizer)
                if len(steps) != 36 or any(s != cumulative for s in steps):
                    raise ValueError('Persistent optimizer steps differ')
                training.update(epoch=epoch, cumulative_optimizer_steps=cumulative, optimizer_state_steps=steps,
                    RNG_before=before, RNG_after=after, training_seconds=training_seconds, matched_A_batches=True)
                with shared.preserve_rng(torch, np):
                    probabilities, bce = shared.evaluate(torch, model, val_native, device)
                metric = {**baseline.el_metrics(validation, probabilities), 'epoch': epoch,
                          'train_weighted_update_BCE': training['row_weighted_BCE_loss'], 'validation_BCE': bce,
                          'training_seconds': training_seconds, 'cumulative_optimizer_steps': cumulative}
                prediction_rows = [{'original_prepared_row_index': r['prepared_row_index'], 'HLA': r['hla'],
                    'peptide': r['peptide'], 'original_label': r['original_label'], 'source_row_id': r['source_row_id'],
                    'probability': repr(p)} for r, p in zip(validation, probabilities, strict=True)]
                runner.raw.write_text_report(directory/f'predictions/{mode}_EL_epoch_{epoch:02d}.csv', shared.csv_records(prediction_rows), paths=paths)
                write_json(directory/f'reports/{mode}_EL_epoch_{epoch:02d}.json', training)
                write_json(directory/f'reports/{mode}_EL_metrics_{epoch:02d}.json', metric)
                curve.append(metric)
                print('EPOCH_COMPLETE', mode, json.dumps(metric), flush=True)
            path = directory/f'checkpoints/{mode}_EL_epoch_10'
            runner.reserve_checkpoint(path); runner.save_checkpoint(model, path, transfer=False, device=device)
            state, keys = runner.state_hashes(model), list(model.state_dict())
            with shared.preserve_rng(torch, np):
                probe = reuse.native_dataset(Dataset, encodings, validation[:16])
                before_predictions, _ = shared.evaluate(torch, model, probe, device)
                loaded = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
                after_predictions, _ = shared.evaluate(torch, loaded, probe, device)
                if runner.state_hashes(loaded) != state or before_predictions != after_predictions:
                    raise ValueError('Final complete EL checkpoint reload differs')
                del loaded
            final = {'checkpoint': str(path.relative_to(directory)), 'files': runner.checkpoint_identity(path, keys),
                     'state': state, 'strict_reload_equal': True, 'probe_predictions_equal': True,
                     'epoch': 10, 'epochs_executed': 10, 'optimizer_steps': cumulative,
                     'elapsed_seconds': time.monotonic()-stage_start,
                     'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(0),
                     'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(0),
                     'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
            write_json(directory/f'reports/{mode}_final_EL_checkpoint.json', final)
            write_json(directory/f'reports/{mode}_EL_learning_curve.json', {'epochs': curve})
            curves[mode], finals[mode] = curve, final
            del model, optimizer, native, val_native
    report = {'status': 'training_completed', 'elapsed_seconds': time.monotonic()-started,
              'epochs_per_arm': 10, 'trained_arms': ['W', 'P'], 'baseline_retrained': False,
              'IM_training': False, 'Teacher_training': False, 'final_checkpoints': finals}
    write_json(directory/'reports/training_completed.json', report)
    return {'status': report['status'], 'elapsed_seconds': report['elapsed_seconds']}


def evaluate(paths: StoragePaths) -> dict:
    """Final epoch-10 paired developmental comparison; no new model inference."""
    import numpy as np
    from .third_party_evaluation import WeightedRanking
    from .replicate_stability_association import doubled_ranks
    config = configuration(paths); directory = paths.project_runs_dir/RUN
    proof = json.loads((directory/'reports/preflight.json').read_text())
    if proof['scientific_hashes'] != scientific_hashes(paths):
        raise ValueError('Analysis implementation changed after scientific preflight')
    complete = json.loads((directory/'reports/training_completed.json').read_text())
    if complete['status'] != 'training_completed':
        raise ValueError('Both ten-epoch EL fits must finish before comparison')
    write_json(directory/'reports/evaluation_started.json', {'status': 'started', 'seed': config['bootstrap_seed']})
    resolved = baseline.inputs(paths, config); base, _ = baseline_evidence(paths, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    train, validation, cohort = populations(resolved, sidecar)
    scores = {'A': saved_A_predictions(base, validation)}
    metrics, bces = {}, {'A': json.loads((base/'reports/EL_metrics_10.json').read_text())['validation_BCE']}
    for mode in ('W', 'P'):
        with (directory/f'predictions/{mode}_EL_epoch_10.csv').open(newline='') as stream:
            probabilities = []
            for record, row in zip(csv.DictReader(stream), validation, strict=True):
                if any(record[field] != str(row[key]) for field, key in [('original_prepared_row_index', 'prepared_row_index'), ('HLA', 'hla'), ('peptide', 'peptide'), ('original_label', 'original_label'), ('source_row_id', 'source_row_id')]):
                    raise ValueError('Frozen final prediction source order changed')
                probabilities.append(float(record['probability']))
        scores[mode] = probabilities
        bces[mode] = json.loads((directory/f'reports/{mode}_EL_metrics_10.json').read_text())['validation_BCE']
    grouped = defaultdict(list)
    for i, row in enumerate(validation):
        grouped[row['hla']].append(i)
    labels = [int(r['original_label']) for r in validation]
    for mode in ('A', 'W', 'P'):
        pooled = runner.development_metrics(labels, scores[mode])
        per_hla = {}
        for hla, indices in sorted(grouped.items()):
            y, p = [labels[i] for i in indices], [scores[mode][i] for i in indices]
            item = {'n': len(y), 'positive_n': sum(y), 'negative_n': len(y)-sum(y), 'AP': None, 'AUROC': None}
            if len(set(y)) == 2:
                values = runner.development_metrics(y, p)
                item.update(AP=values['AUPRC'], AUROC=values['AUROC'])
            per_hla[hla] = item
        ap_values = [v['AP'] for v in per_hla.values() if v['AP'] is not None]
        metrics[mode] = {'AP': pooled['AUPRC'], 'AUROC': pooled['AUROC'], 'BCE': bces[mode],
                         'macro_HLA_AP': math.fsum(ap_values)/len(ap_values), 'evaluable_HLAs': len(ap_values),
                         'n': len(labels), 'positive_n': sum(labels), 'negative_n': len(labels)-sum(labels),
                         'prevalence': sum(labels)/len(labels), 'per_HLA': per_hla}
    contrasts = {name: {metric: metrics[left][metric]-metrics[right][metric]
                       for metric in ('AP', 'AUROC', 'BCE', 'macro_HLA_AP')}
                 for name, left, right in [('W-A', 'W', 'A'), ('W-P', 'W', 'P'), ('P-A', 'P', 'A')]}
    consistency = {}
    for name, left, right in [('W-A', 'W', 'A'), ('W-P', 'W', 'P'), ('P-A', 'P', 'A')]:
        per_hla = {hla: {key: metrics[left]['per_HLA'][hla][key]-metrics[right]['per_HLA'][hla][key]
                         for key in ('AP', 'AUROC')} for hla in grouped if metrics[left]['per_HLA'][hla]['AP'] is not None}
        consistency[name] = {'per_HLA': per_hla, 'AP_wins': sum(v['AP'] > 0 for v in per_hla.values()),
                             'AP_ties': sum(v['AP'] == 0 for v in per_hla.values()),
                             'AP_losses': sum(v['AP'] < 0 for v in per_hla.values())}
    rank_references = defaultdict(list)
    for row in train:
        if row['original_label'] == '1':
            rank_references[row['hla']].append(Decimal(sidecar.scores[row['source_row_id']].predicted_half_life_hours))
    for values in rank_references.values():
        values.sort()
    strata = {'lower_training_reference_half': [], 'upper_training_reference_half': []}
    for i, row in enumerate(validation):
        if row['original_label'] == '1':
            reference = rank_references[row['hla']]
            value = Decimal(sidecar.scores[row['source_row_id']].predicted_half_life_hours)
            rank = Fraction(bisect_left(reference, value)+bisect_right(reference, value), 2*len(reference))
            strata['lower_training_reference_half' if rank <= Fraction(1, 2) else 'upper_training_reference_half'].append(i)
    diagnostics = {}
    for mode in scores:
        ranks = doubled_ranks(scores[mode])
        diagnostics[mode] = {name: {'n': len(indices),
            'mean_prediction_percentile': math.fsum((ranks[i]/2-.5)/len(labels) for i in indices)/len(indices),
            'mean_probability': math.fsum(scores[mode][i] for i in indices)/len(indices),
            'diagnostic_positive_probability_BCE': math.fsum(-math.log(max(scores[mode][i], 1e-15)) for i in indices)/len(indices)}
            for name, indices in strata.items()}
    write_json(directory/'reports/point_estimates.json', {'arms': metrics, 'contrasts': contrasts, 'per_HLA_consistency': consistency,
               'rank_stratum_diagnostics': diagnostics, 'diagnostic_probability_clipping_floor': 1e-15,
               'recall_at_fixed_FPR': None, 'recall_unavailable_reason': config['recall_at_fixed_FPR']})
    joined = [{**r, 'scores': {arm: scores[arm][i] for arm in scores}, 'label': labels[i],
               'study_DOI': '', 'patient': '', 'source_id': r['source_row_id']} for i, r in enumerate(validation)]
    # Empty study/patient strings are unavailable metadata used only by the
    # existing metric's deterministic tie-order key; no clusters are inferred from them.
    rankings = {arm: WeightedRanking(joined, arm) for arm in scores}
    peptide_ids = {key: i for i, key in enumerate(sorted({r['peptide'] for r in validation}))}
    row_groups = np.array([peptide_ids[r['peptide']] for r in validation], dtype=np.int64)
    unit_weights = np.ones(len(joined), dtype=np.int64)
    for arm, ranking in rankings.items():
        values = ranking.metrics(unit_weights, top_k=False)
        if abs(values['AP']-metrics[arm]['AP']) > 1e-12 or abs(values['AUROC']-metrics[arm]['AUROC']) > 1e-12:
            raise ValueError('Reused exact tied-score metric primitive disagrees')
    rng = np.random.default_rng(config['bootstrap_seed'])
    samples = {name: {'AP': [], 'AUROC': []} for name in contrasts}
    draw_records, start = [], time.monotonic()
    for draw in range(config['bootstrap_draws']):
        counts = np.bincount(rng.integers(0, len(peptide_ids), size=len(peptide_ids)), minlength=len(peptide_ids))
        multiplicities = counts[row_groups]
        values = {arm: ranking.metrics(multiplicities, top_k=False) for arm, ranking in rankings.items()}
        record = {'draw_1based': draw+1, 'n': int(multiplicities.sum()), 'contrasts': {}}
        for name, left, right in [('W-A', 'W', 'A'), ('W-P', 'W', 'P'), ('P-A', 'P', 'A')]:
            record['contrasts'][name] = {}
            for metric in ('AP', 'AUROC'):
                value = values[left][metric]-values[right][metric] if values[left][metric] is not None and values[right][metric] is not None else None
                record['contrasts'][name][metric] = value
                if value is not None:
                    samples[name][metric].append(value)
        draw_records.append(record)
        if (draw+1) % 100 == 0:
            print('paired peptide bootstrap', draw+1, flush=True)
    bootstrap = {'draws': config['bootstrap_draws'], 'seed': config['bootstrap_seed'], 'generator': 'numpy.default_rng',
                 'peptide_groups': len(peptide_ids), 'elapsed_seconds': time.monotonic()-start,
                 'contrasts': {name: {metric: {'lower_95': quantile(values, .025), 'upper_95': quantile(values, .975),
                  'usable_draws': len(values), 'undefined_draws': config['bootstrap_draws']-len(values)} for metric, values in item.items()} for name, item in samples.items()},
                 'interpretation': 'Exploratory paired internal-validation peptide-group intervals; not study/patient independence, independent testing, or across-training-seed uncertainty.'}
    write_json(directory/'reports/paired_peptide_bootstrap.json', bootstrap)
    write_json(directory/'reports/bootstrap_draws.json', draw_records)
    runner.raw.write_text_report(directory/'predictions/A_EL_epoch_10.csv', (base/'predictions/EL_epoch_10.csv').read_text(), paths=paths)
    write_json(directory/'reports/evaluation_completed.json', {'status': 'completed', 'arms': metrics,
               'contrasts': contrasts, 'all_epoch_selection_fixed_at_10': True, 'no_IM_training_or_benchmarks': True})
    return {'status': 'completed', 'contrasts': contrasts}


def main() -> None:
    paths = resolve_paths()
    if len(sys.argv) != 2 or sys.argv[1] not in ('preflight', 'execute', 'evaluate'):
        raise SystemExit('preflight | execute | evaluate')
    try:
        result = globals()[sys.argv[1]](paths)
    except Exception as exc:
        directory = paths.project_runs_dir/RUN
        if directory.exists():
            write_json(directory/f'reports/{sys.argv[1]}_failure_{time.time_ns()}.json', {'status': 'failed', 'error': repr(exc)})
        raise
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
