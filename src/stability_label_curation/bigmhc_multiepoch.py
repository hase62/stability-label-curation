"""Task 2.22: frozen peptide groups and native multi-epoch IM transfer only.

No historical-development or independent-test reader is used by this module.
Scientific artifacts are exclusive writes; a failed fit is never resumed/retried.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
import io
import json
import math
from pathlib import Path
import random
import subprocess
import time
from typing import Any, Iterator

from . import bigmhc_baseline_runner as runner
from . import bigmhc_baseline_compatibility as historical
from . import el_stability_loss_adapter as identity
from .paths import StoragePaths, resolve_paths

RUN_ID = 'task-2_22-peptide-disjoint-multiepoch-baseline'
CONFIG = 'configs/bigmhc_multiepoch_task2_22.json'
CANDIDATES = (1, 2, 5, 10, 20, 40, 60)
Row = dict[str, Any]


def grouped_split(rows: list[Row]) -> tuple[list[Row], list[Row]]:
    """One seed42 shuffle, one greedy pass toward 20% of each outcome class.

    Minimize sum of squared relative class-count errors. Never split groups,
    swap groups, search seeds, or use scores/HLA/development observations.
    """
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        sequence = row['peptide'].strip().upper()
        if not sequence or any(a not in runner.teacher.ALPHABET for a in sequence):
            raise ValueError('Invalid normalized peptide')
        groups[sequence].append(row)
    total = Counter(int(r['original_label']) for r in rows)
    if not total[0] or not total[1]:
        raise ValueError('Both classes required')
    targets = {k: total[k] * .2 for k in (0, 1)}
    peptides = sorted(groups)
    random.Random(42).shuffle(peptides)
    chosen: set[str] = set()
    counts: Counter[int] = Counter()
    def cost(c: Counter[int]) -> float:
        return sum(((c[k] - targets[k]) / targets[k]) ** 2 for k in (0, 1))
    for peptide in peptides:
        addition = Counter(int(r['original_label']) for r in groups[peptide])
        if cost(counts + addition) < cost(counts):
            chosen.add(peptide)
            counts.update(addition)
    train = [r for r in rows if r['peptide'].strip().upper() not in chosen]
    validation = [r for r in rows if r['peptide'].strip().upper() in chosen]
    verify_split(rows, train, validation)
    return train, validation


def partition_summary(rows: list[Row]) -> dict:
    return {'observations': len(rows), 'positives': sum(int(r['original_label']) for r in rows),
            'negatives': sum(1-int(r['original_label']) for r in rows),
            'positive_prevalence': sum(int(r['original_label']) for r in rows) / len(rows),
            'unique_peptides': len({r['peptide'].strip().upper() for r in rows}),
            'HLA': {h: {'observations': len(group),
                        'positives': sum(int(r['original_label']) for r in group)}
                    for h, group in sorted(_hla_groups(rows).items())}}


def _hla_groups(rows: list[Row]) -> dict[str, list[Row]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[row['hla']].append(row)
    return groups


def verify_split(original: list[Row], train: list[Row], validation: list[Row]) -> dict:
    sequence = lambda r: r['peptide'].strip().upper()
    overlap = {sequence(r) for r in train} & {sequence(r) for r in validation}
    pairs = {(sequence(r), r['hla']) for r in train} & {(sequence(r), r['hla']) for r in validation}
    ids = [r['prepared_row_index'] for r in original]
    combined = [r['prepared_row_index'] for r in train + validation]
    original_by_id = {r['prepared_row_index']: r for r in original}
    if (overlap or pairs or len(set(ids)) != len(ids) or Counter(ids) != Counter(combined)
            or any(original_by_id[r['prepared_row_index']] != r for r in train + validation)
            or any({int(r['original_label']) for r in part} != {0, 1} for part in (train, validation))):
        raise ValueError('Peptide split overlap, coverage, labels, provenance, or class failure')
    return {'exact_peptide_overlap': 0, 'peptide_HLA_overlap': 0,
            'both_classes_in_both_sets': True, 'each_original_observation_exactly_once': True,
            'original_labels_and_provenance_preserved': True,
            'train': partition_summary(train), 'validation': partition_summary(validation)}


def proximity(train: list[Row], validation: list[Row]) -> dict:
    training = sorted({r['peptide'] for r in train})
    records = []
    for peptide in sorted({r['peptide'] for r in validation}):
        distances = [(sum(a != b for a, b in zip(peptide, other)), other)
                     for other in training if len(other) == len(peptide)]
        minimum, nearest = min(distances)
        records.append({'validation_peptide': peptide, 'minimum_same_length_Hamming_distance': minimum,
                        'nearest_train_peptide_lexical_tiebreak': nearest,
                        'one_AA_train_neighbors': [other for distance, other in distances if distance == 1]})
    return {'method': 'Exact same-length Hamming distance across all HLA; descriptive only',
            'minimum_distance_histogram': dict(sorted(Counter(r['minimum_same_length_Hamming_distance'] for r in records).items())),
            'validation_peptides_with_one_AA_train_neighbor': sum(bool(r['one_AA_train_neighbors']) for r in records),
            'records': records}


def choose_epoch(curve: list[dict]) -> int:
    candidates = [r for r in curve if r['epoch'] in CANDIDATES]
    if sorted(r['epoch'] for r in candidates) != list(CANDIDATES):
        raise ValueError('All predefined candidates must be present exactly once')
    if any(not math.isfinite(r['validation_AP']) for r in candidates):
        raise ValueError('Nonfinite candidate AP')
    return max(candidates, key=lambda r: (r['validation_AP'], -r['epoch']))['epoch']


def csv_records(records: list[dict]) -> str:
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def read_config(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root / CONFIG).read_text())
    if (config['candidate_epochs'] != list(CANDIDATES) or config['max_IM_epochs'] != 60
            or config['seed'] != 42 or config['learning_rate'] != 5e-5 or config['batch_size'] != 16
            or config['label_policy'] != 'original' or config['device'] != 'cuda'
            or config['EL_training_epochs'] != 0 or config['stability_supervision'] is not False):
        raise ValueError('Task 2.22 frozen protocol changed')
    return config


def inputs(paths: StoragePaths, config: dict) -> tuple[dict[str, Path], dict, dict]:
    """Authenticate only named scientific inputs and historical EL evidence."""
    resolved = {}
    for name, spec in config['inputs'].items():
        runner.adapter.pilot.registry._relative(spec['relative_path'])
        root = paths.project_runs_dir if spec['area'] == 'runs' else paths.project_data_dir
        path = root / spec['relative_path']
        if runner.raw.sha256_file(path) != spec['sha256']:
            raise ValueError('Input SHA256 mismatch: ' + name)
        resolved[name] = path
    parent = paths.project_runs_dir / historical.BASELINE_RUN
    if runner.raw.sha256_file(parent / 'reports/matched_state.json') != historical.REFERENCE['sha256']:
        raise ValueError('Historical A evidence changed')
    matched = json.loads((parent / 'reports/matched_state.json').read_text())
    if matched['code_commit'] != historical.BASELINE_COMMIT:
        raise ValueError('Historical A commit mismatch')
    stage_path = parent / 'reports/el_stage_checkpoint.json'
    if runner.raw.sha256_file(stage_path) != config['EL_stage_receipt_sha256']:
        raise ValueError('Historical EL receipt changed')
    stage = json.loads(stage_path.read_text())
    if not stage['strict_reload_identical'] or stage['code_commit'] != historical.BASELINE_COMMIT:
        raise ValueError('Historical EL not verified')
    el = parent / 'checkpoints/el'
    # Exact directory membership and all 36 bytes are checked, without reading IM weights.
    keys = list(stage['state_tensor_sha256'])
    files = {p.name: runner.raw.sha256_file(p) for p in el.glob('*.lyr')}
    if len(keys) != 36 or files != stage['files']:
        raise ValueError('Historical EL tensors changed')
    receipt = json.loads((parent / 'reports/execution_verification.json').read_text())
    saved_path = parent / 'reports/training_configuration.json'
    if runner.raw.sha256_file(saved_path) != receipt['outputs']['reports/training_configuration.json']:
        raise ValueError('Historical training configuration changed')
    saved = json.loads(saved_path.read_text())
    if (saved['condition'] != 'A' or saved['label_policy'] != 'original'
            or saved['epochs']['EL'] != 1 or saved['loss_adapter']['mode'] != 'A'
            or any(saved['inputs'][k] != config['inputs'][k] for k in ('EL', 'IM', 'IM_provenance', 'reference'))):
        raise ValueError('Historical EL population or original-label lineage mismatch')
    resolved['EL_checkpoint'] = el
    return resolved, stage, matched


def original_rows(resolved: dict[str, Path]) -> list[Row]:
    with resolved['reference'].open(newline='') as stream:
        allowed = {runner.data.canonical_hla(r[0]) for r in list(csv.reader(stream))[1:]}
    rows = list(runner.input_rows(resolved['IM'], allowed))
    if len(rows) != 3428 or Counter(r['original_label'] for r in rows) != {'0': 2473, '1': 955}:
        raise ValueError('Original IM population mismatch')
    runner.attach_provenance(rows, resolved['IM_provenance'])
    if len({r['source_locator']['source_row_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate source-row identity')
    return rows


def preflight(paths: StoragePaths) -> dict:
    config = read_config(paths)
    resolved, stage, matched = inputs(paths, config)
    rows = original_rows(resolved)
    train, validation = grouped_split(rows)
    report = verify_split(rows, train, validation)
    val_peptides = {r['peptide'] for r in validation}
    matches: dict[str, list[dict]] = defaultdict(list)
    el_count = 0
    el_classes: Counter[str] = Counter()
    with resolved['EL'].open(newline='') as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            el_count += 1
            el_classes[row['tgt']] += 1
            if row['pep'] in val_peptides:
                matches[row['pep']].append({'EL_prepared_row_index': index, 'HLA': row['mhc'], 'original_label': row['tgt']})
    if el_count != 1453578 or el_classes != {'0': 1383509, '1': 70069}:
        raise ValueError('Original EL population mismatch')
    exposure = {'IM_novel_unique_peptides': len(val_peptides),
                'EL_exposed_IM_novel_unique_peptides': len(matches),
                'fully_training_unseen_unique_peptides': len(val_peptides - matches.keys()),
                'EL_exposed_validation_observations': sum(r['peptide'] in matches for r in validation),
                'fully_training_unseen_validation_observations': sum(r['peptide'] not in matches for r in validation),
                'matches': dict(sorted(matches.items())),
                'fully_training_unseen_peptides': sorted(val_peptides - matches.keys()),
                'EL_population': config['inputs']['EL'],
                'interpretation': 'EL exposure uses the original eligible population, not just stochastically consumed rows'}
    directory = paths.project_runs_dir / RUN_ID
    directory.mkdir(mode=0o700)  # Refuse existing runs; never overwrite a split.
    for name in ('reports', 'processed', 'predictions', 'checkpoints', 'logs'):
        (directory / name).mkdir(mode=0o700)
    write = lambda name, doc: runner.raw.write_report(directory / name, doc, paths=paths)
    write('reports/training_configuration.json', config)
    write('reports/split_verification.json', report)
    write('reports/peptide_EL_overlap.json', exposure)
    write('reports/sequence_proximity.json', proximity(train, validation))
    membership = []
    groups: dict[str, list[dict]] = defaultdict(list)
    for partition, part in (('train', train), ('validation', validation)):
        runner.raw.write_text_report(directory / f'processed/im_{partition}.csv', runner.csv_text(part), paths=paths)
        for row in part:
            record = {'partition': partition, 'original_prepared_row_index': row['prepared_row_index'],
                      'peptide': row['peptide'], 'HLA': row['hla'], 'original_label': row['original_label'],
                      **row['source_locator']}
            membership.append(record)
            groups[row['peptide']].append(record)
    runner.raw.write_text_report(directory / 'processed/split_manifest.csv', csv_records(membership), paths=paths)
    write('processed/peptide_groups.json', dict(sorted(groups.items())))
    preflight_report = {'status': 'passed', 'input_hashes': config['inputs'],
                        'EL_parent_receipt': config['EL_stage_receipt_sha256'],
                        'historical_A_commit': historical.BASELINE_COMMIT,
                        'historical_EL_files': stage['files'], 'historical_runtime_versions': matched['versions'],
                        'source_hashes': source_hashes(paths),
                        'split_artifact_sha256': artifact_hashes(directory),
                        'split': report, 'EL_overlap_counts': {k: v for k, v in exposure.items() if k.endswith(('peptides', 'observations')) and isinstance(v, int)}}
    write('reports/preflight.json', preflight_report)
    return preflight_report


def source_hashes(paths: StoragePaths) -> dict[str, str]:
    return {name: runner.raw.sha256_file(paths.repository_root / name) for name in
            (CONFIG, 'src/stability_label_curation/bigmhc_multiepoch.py',
             'src/stability_label_curation/bigmhc_baseline_runner.py')}


def artifact_hashes(directory: Path) -> dict[str, str]:
    return {str(p.relative_to(directory)): runner.raw.sha256_file(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


@contextmanager
def preserve_rng(torch: Any, np: Any) -> Iterator[None]:
    python, numpy, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state()
    cuda = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
    try:
        yield
    finally:
        random.setstate(python)
        np.random.set_state(numpy)
        torch.set_rng_state(cpu)
        if cuda is not None:
            torch.cuda.set_rng_state_all(cuda)


def evaluate(torch: Any, model: Any, dataset: Any, device: str) -> tuple[list[float], float]:
    """Deterministic source-order 9-mer inference; stable logit-space BCE."""
    model.eval()
    dataset.makebats(16, shuffle=False, negfrac=None)
    probabilities, total, observations = [], 0., 0
    with torch.no_grad():
        for index in range(len(dataset)):
            batch = dataset[index]
            logits, _ = model(batch.mhc.float().to(device), batch.pep.float().to(device))
            targets = batch.tgt.float().to(device)
            total += float(torch.nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='sum'))
            observations += len(targets)
            probabilities.extend(torch.sigmoid(logits).cpu().tolist())
    if observations != len(dataset.df) or not math.isfinite(total) or any(not math.isfinite(p) for p in probabilities):
        raise ValueError('Inference coverage/nonfinite failure')
    return probabilities, total / observations


def optimizer_steps(optimizer: Any) -> list[int]:
    return [int(state['step']) for state in optimizer.state.values() if 'step' in state]


def execute(paths: StoragePaths) -> dict:
    import importlib.metadata
    import platform
    import resource
    import sys
    import numpy as np
    import torch

    directory = paths.project_runs_dir / RUN_ID
    config = read_config(paths)
    proof = json.loads((directory / 'reports/preflight.json').read_text())
    if proof['status'] != 'passed' or proof['source_hashes'] != source_hashes(paths):
        raise ValueError('Preflight source changed')
    for name, checksum in proof['split_artifact_sha256'].items():
        if runner.raw.sha256_file(directory / name) != checksum:
            raise ValueError('Immutable split artifact changed')
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != 'task/2.22-peptide-disjoint-multiepoch-baseline':
        raise ValueError('Execution requires clean committed Task 2.22 branch')
    resolved, el_receipt, matched = inputs(paths, config)
    versions = {name: importlib.metadata.version(name) for name in ('torch', 'numpy', 'pandas', 'psutil')}
    if versions != matched['versions']:
        raise ValueError('Runtime differs from original A')
    runner.cuda_visibility()
    device = runner.runtime_device(torch, config)
    runner.seed_runtime(torch, np, config)
    rows = original_rows(resolved)
    train, validation = grouped_split(rows)
    if verify_split(rows, train, validation) != proof['split']:
        raise ValueError('Split regeneration mismatch')
    write = lambda name, doc: runner.raw.write_report(directory / name, doc, paths=paths)
    write('reports/execution_started.json', {'code_commit': git('rev-parse', 'HEAD'),
          'status': 'started', 'versions': versions, 'platform': platform.platform(), 'python': sys.version,
          'device': runner.device_report(torch, device), 'configuration_sha256': runner.raw.sha256_file(paths.repository_root / CONFIG),
          'preflight_sha256': runner.raw.sha256_file(directory / 'reports/preflight.json')})
    start = time.monotonic()
    with resolved['reference'].open(newline='') as stream:
        reference = list(csv.reader(stream))[1:]
    needed = {r['hla'] for r in rows}
    encodings = {runner.data.canonical_hla(r[0]): torch.tensor([int(v) for v in r[1:]], dtype=torch.int8)
                 for r in reference if runner.data.canonical_hla(r[0]) in needed}
    if set(encodings) != needed or any(len(v) != 414 for v in encodings.values()):
        raise ValueError('Exact HLA representation unavailable')
    archive = json.loads(resolved['experiment'].read_text())['archive_sha256']
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        def dataset(part: list[Row], audit: bool = False) -> Any:
            frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(part)), allele=0, pepcol=1, tgtcol=2, hdrcnt=1, verbose=False)
            native = Dataset(frame, mhcenc=encodings)
            if not audit:
                return native
            # Original prepared indices stay in split_manifest. The native subset
            # has a new contiguous coordinate required by IdentityDataset.
            records = [dict(r['source_locator'], derived_row_index=str(i)) for i, r in enumerate(part, 1)]
            return identity.IdentityDataset(native, records, stage='IM', archive_sha256=archive)

        # Loading creates a temporary BigMHC constructor; reset all scientific RNG
        # streams afterwards. Every fit starts from the same seed42 boundary.
        probe = BigMHC()
        keys = list(probe.state_dict())
        del probe
        if len(keys) != 36 or tuple(BigMHC.tllayers()) != runner.TRANSFER:
            raise ValueError('Unexpected architecture or transfer layers')
        if runner.checkpoint_identity(resolved['EL_checkpoint'], keys) != el_receipt['files']:
            raise ValueError('EL key order mismatch')
        def fresh() -> Any:
            model = runner.load_checkpoint(torch, BigMHC, resolved['EL_checkpoint'], keys, device=device)
            if runner.state_hashes(model) != el_receipt['state_tensor_sha256'] or any(p.dtype != torch.float32 for p in model.parameters()):
                raise ValueError('Original EL state or FP32 mismatch')
            random.seed(42); np.random.seed(42); torch.manual_seed(42); torch.cuda.manual_seed_all(42)
            return model

        model = fresh()
        with preserve_rng(torch, np):
            probe_probabilities, _ = evaluate(torch, model, dataset(train[:16]), device)
        write('reports/CUDA_preflight.json', {'status': 'passed', 'strict_EL_reload': True,
              'finite_inference_rows': len(probe_probabilities), 'FP32': True,
              'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
              'TF32_matmul': torch.backends.cuda.matmul.allow_tf32, 'TF32_cudnn': torch.backends.cudnn.allow_tf32})

        def fit(stage: str, part: list[Row], epochs: int, current: Any, validate: bool) -> tuple[list[dict], list[dict]]:
            native = dataset(part, audit=True)
            training_eval = dataset(part)
            validation_eval = dataset(validation) if validate else None
            optimizer = torch.optim.AdamW([v for k, v in current.named_parameters() if k in runner.TRANSFER], lr=5e-5)
            initial = runner.state_hashes(current)
            stage_start = time.monotonic()
            torch.cuda.reset_peak_memory_stats(0)
            write(f'reports/{stage}_started.json', {'epochs': epochs, 'observations': len(part), 'initial_state': initial,
                  'RNG': identity.rng_identity(torch, np), 'optimizer_defaults': optimizer.defaults})
            curve, checkpoints = [], []
            cumulative_steps = 0
            for epoch in range(1, epochs + 1):
                before_rng = identity.rng_identity(torch, np)
                torch.cuda.synchronize(0)
                epoch_start = time.monotonic()
                training = runner.train_epoch(torch, current, native, config, True, device, optimizer=optimizer)
                torch.cuda.synchronize(0)
                training_seconds = time.monotonic() - epoch_start
                cumulative_steps += training['optimization_steps']
                steps = optimizer_steps(optimizer)
                if len(steps) != 4 or any(s != cumulative_steps for s in steps):
                    raise ValueError('AdamW state did not persist across epochs')
                # Record complete ordered identities for both optimized/skipped batches.
                batches = []
                for batch in range(len(native)):
                    frame = native.native.getbat(batch, enc=False)
                    pairs = [(str(s), int(y)) for s, y in frame[[identity.IDENTITY, 'tgt']].itertuples(index=False, name=None)]
                    batches.append({'batch_sha256': identity.digest(pairs), 'source_ids_and_labels': pairs})
                by_hash = {b['batch_sha256']: b for b in batches}
                ordered = [by_hash[h] for h in training['sampled_batch_sha256']]
                exposed = [s for batch in ordered for s, _ in batch['source_ids_and_labels']]
                if Counter(exposed) != Counter(r['source_locator']['source_row_id'] for r in part):
                    raise ValueError('Native epoch omitted/duplicated original observations')
                training.update(epoch=epoch, cumulative_optimizer_steps=cumulative_steps,
                                optimizer_state_steps=steps, training_seconds=training_seconds,
                                RNG_before=before_rng, RNG_after=identity.rng_identity(torch, np), ordered_batches=ordered)
                with preserve_rng(torch, np):
                    _, train_bce = evaluate(torch, current, training_eval, device)
                    probabilities, val_bce = evaluate(torch, current, validation_eval, device) if validate else ([], None)
                row = {'epoch': epoch, 'train_update_BCE': training['row_weighted_BCE_loss'],
                       'train_eval_BCE': train_bce, 'validation_BCE': val_bce,
                       'optimization_steps': training['optimization_steps'], 'cumulative_steps': cumulative_steps,
                       'skipped_batches': training['all_negative_batches_skipped'], 'training_seconds': training_seconds}
                if validate:
                    metric = runner.development_metrics([int(r['original_label']) for r in validation], probabilities)
                    row.update(validation_AP=metric['AUPRC'], validation_AUROC=metric['AUROC'])
                    prediction_rows = [{'original_prepared_row_index': r['prepared_row_index'],
                        'source_row_id': r['source_locator']['source_row_id'], 'HLA': r['hla'], 'peptide': r['peptide'],
                        'original_label': r['original_label'], 'probability': repr(p)} for r, p in zip(validation, probabilities, strict=True)]
                    runner.raw.write_text_report(directory / f'predictions/validation_epoch_{epoch:02d}.csv', csv_records(prediction_rows), paths=paths)
                write(f'reports/{stage}_epoch_{epoch:02d}.json', training)
                write(f'reports/{stage}_metrics_{epoch:02d}.json', row)
                curve.append(row)
                if validate and epoch in CANDIDATES:
                    checkpoint = directory / f'checkpoints/internal_epoch_{epoch:02d}'
                    runner.reserve_checkpoint(checkpoint)
                    runner.save_checkpoint(current, checkpoint, transfer=True, device=device)
                    files = runner.overlay_identity(checkpoint, keys)
                    checkpoints.append({'epoch': epoch, 'checkpoint': str(checkpoint.relative_to(directory)),
                                        'files': files, 'state': runner.state_hashes(current)})
                print(stage, row, flush=True)
            torch.cuda.synchronize(0)
            state = runner.state_hashes(current)
            changed = [k for k in keys if state[k] != initial[k]]
            if set(changed) != set(runner.TRANSFER):
                raise ValueError('Unexpected transfer parameter changes')
            write(f'reports/{stage}_completed.json', {'status': 'completed', 'epochs': epochs,
                  'optimizer_steps': cumulative_steps, 'optimizer_state_steps': optimizer_steps(optimizer),
                  'changed_parameters': changed, 'state': state, 'elapsed_seconds': time.monotonic()-stage_start,
                  'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(0),
                  'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(0),
                  'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
            return curve, checkpoints

        curve, checkpoints = fit('internal', train, 60, model, True)
        selected = choose_epoch(curve)
        write('reports/learning_curve.json', {'epochs': curve})
        runner.raw.write_text_report(directory / 'reports/learning_curve.csv', csv_records(curve), paths=paths)
        chosen = next(c for c in checkpoints if c['epoch'] == selected)
        selection = {'selected_epoch': selected, 'criterion': 'Highest non-interpolated validation AP among [1,2,5,10,20,40,60]; exact ties earlier',
                     'candidates': [r for r in curve if r['epoch'] in CANDIDATES], 'checkpoints': checkpoints}
        write('reports/candidate_checkpoint_comparison.json', selection)
        # Freeze selection before final fit. Reload selected overlay against the
        # explicitly authenticated historical EL parent; no adjacent-parent assumption.
        with preserve_rng(torch, np):
            selected_model = runner.load_checkpoint(torch, BigMHC, resolved['EL_checkpoint'], keys, device=device)
            state = selected_model.state_dict()
            overlay = directory / chosen['checkpoint']
            if runner.overlay_identity(overlay, keys) != chosen['files']:
                raise ValueError('Selected overlay identity changed')
            for i, key in enumerate(keys):
                if key in runner.TRANSFER:
                    state[key] = torch.load(overlay / f'{i}_{key}.lyr', map_location=device, weights_only=True)
            selected_model.load_state_dict(state, strict=True)
            if runner.state_hashes(selected_model) != chosen['state']:
                raise ValueError('Selected checkpoint state reload failure')
            selected_predictions, _ = evaluate(torch, selected_model, dataset(validation), device)
            with (directory / f'predictions/validation_epoch_{selected:02d}.csv').open(newline='') as stream:
                saved_predictions = [float(r['probability']) for r in csv.DictReader(stream)]
            selected_agreement = runner.prediction_agreement(saved_predictions, selected_predictions, device)
            del selected_model, state
        del model
        write('reports/final_frozen_configuration.json', {'selected_epoch': selected, 'configuration': config,
              'selection_sha256': runner.raw.sha256_file(directory / 'reports/candidate_checkpoint_comparison.json'),
              'all_IM_rows': 3428, 'historical_development_used': False})
        final_model = fresh()
        final_curve, _ = fit('final', rows, selected, final_model, False)
        write('reports/final_learning_curve.json', {'epochs': final_curve})
        final_checkpoint = directory / 'checkpoints/final_all_IM'
        runner.reserve_checkpoint(final_checkpoint)
        runner.save_checkpoint(final_model, final_checkpoint, transfer=False, device=device)
        final_files = runner.checkpoint_identity(final_checkpoint, keys)
        final_state = runner.state_hashes(final_model)
        # Reload inference on a fixed first-16 training-row probe only. This has
        # no model-selection role and computes no historical/independent metrics.
        before, _ = evaluate(torch, final_model, dataset(rows[:16]), device)
        del final_model
        reloaded = runner.load_checkpoint(torch, BigMHC, final_checkpoint, keys, device=device)
        if runner.state_hashes(reloaded) != final_state:
            raise ValueError('Final complete checkpoint reload failure')
        after, _ = evaluate(torch, reloaded, dataset(rows[:16]), device)
        final_agreement = runner.prediction_agreement(before, after, device)
        write('reports/checkpoint_lineage.json', {'historical_A_commit': historical.BASELINE_COMMIT,
              'EL_parent_runs_relative': str(resolved['EL_checkpoint'].relative_to(paths.project_runs_dir)),
              'EL_parent_receipt_sha256': config['EL_stage_receipt_sha256'], 'EL_parent_files': el_receipt['files'],
              'EL_state': el_receipt['state_tensor_sha256'], 'selected_internal_checkpoint': chosen,
              'selected_epoch': selected, 'selected_reload': selected_agreement,
              'final_complete_checkpoint': 'checkpoints/final_all_IM', 'final_files': final_files,
              'final_state': final_state, 'final_reload': final_agreement, 'final_probe_probabilities': after,
              'state_keys': keys, 'IM_start': 'Original EL only, independent fresh transfer for internal and full-data fits',
              'IM_updated_parameters': list(runner.TRANSFER)})
    # Recheck external inputs/parent and immutable split after scientific execution.
    inputs(paths, config)
    for name, checksum in proof['split_artifact_sha256'].items():
        if runner.raw.sha256_file(directory / name) != checksum:
            raise ValueError('Split artifact changed during execution')
    completion = {'status': 'completed', 'selected_epoch': selected, 'internal_epochs': 60,
                  'final_epochs': selected, 'final_rows': 3428, 'elapsed_seconds': time.monotonic() - start,
                  'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                  'selected_reload': selected_agreement, 'final_reload': final_agreement,
                  'historical_development_accessed': False, 'sealed_benchmark_accessed': False,
                  'EL_retrained': False, 'stability_supervision': False, 'protocol_deviations': []}
    write('reports/completion.json', completion)
    write('reports/output_manifest.json', artifact_hashes(directory))
    return completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'execute'))
    args = parser.parse_args()
    paths = resolve_paths()
    print(json.dumps(preflight(paths) if args.action == 'preflight' else execute(paths), indent=2))


if __name__ == '__main__':
    main()
