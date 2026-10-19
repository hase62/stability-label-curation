"""Task 2.23 bounded EL selection and fixed-epoch IM development comparison.

Never reads historical development or independent benchmark data. EL starts
from BigMHC() defaults; every IM fit starts from an explicit new EL checkpoint.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import io
import json
import math
from pathlib import Path
import random
import subprocess
import time
from typing import Any

from . import bigmhc_baseline_runner as runner
from . import bigmhc_multiepoch as previous
from .paths import StoragePaths, resolve_paths

RUN_ID = 'task-2_23-el-multiepoch-baseline'
CONFIG = 'configs/bigmhc_el_multiepoch_task2_23.json'
CANDIDATES = (1, 2, 4, 6, 8, 10)
BRANCH = 'task/2.23-el-multiepoch-baseline'
Row = dict[str, Any]


def normalized(row: Row) -> str:
    peptide = row['peptide'].strip().upper()
    if len(peptide) != 9 or any(a not in runner.teacher.ALPHABET for a in peptide):
        raise ValueError('Invalid peptide')
    return peptide


def split_el(rows: list[Row], excluded: set[str]) -> tuple[list[Row], list[Row], list[Row]]:
    """One fixed shuffle and greedy pass, no predictions, no seed search.

    Reserve one whole lexical-first group per HLA and positive-bearing HLA.
    This guarantees training representation/positive anchors where available.
    """
    groups: dict[str, list[Row]] = defaultdict(list)
    removed = []
    for row in rows:
        peptide = normalized(row)
        if peptide in excluded:
            removed.append(row)
        else:
            groups[peptide].append(row)
    first, anchors = {}, {}
    for peptide in sorted(groups):
        for row in groups[peptide]:
            first.setdefault(row['hla'], peptide)
            if int(row['original_label']):
                anchors.setdefault(row['hla'], peptide)
    reserved = set(first.values()) | set(anchors.values())
    total = Counter(int(r['original_label']) for g in groups.values() for r in g)
    if not total[0] or not total[1]:
        raise ValueError('Both EL classes required')
    target = {k: total[k] * .1 for k in (0, 1)}
    def cost(count: Counter[int]) -> float:
        return sum(((count[k] - target[k]) / target[k])**2 for k in (0, 1))
    peptides = sorted(groups)
    random.Random(42).shuffle(peptides)
    chosen, counts = set(), Counter()
    for peptide in peptides:
        if peptide in reserved:
            continue
        addition = Counter(int(r['original_label']) for r in groups[peptide])
        if cost(counts + addition) < cost(counts):
            chosen.add(peptide)
            counts.update(addition)
    outside_training = excluded | chosen
    train = [r for r in rows if normalized(r) not in outside_training]
    validation = [r for r in rows if normalized(r) in chosen]
    return train, validation, removed


def verify_el(rows: list[Row], train: list[Row], validation: list[Row], removed: list[Row], excluded: set[str]) -> dict:
    kept = [r for r in rows if normalized(r) not in excluded]
    report = previous.verify_split(kept, train, validation)
    ids = lambda part: Counter(r['prepared_row_index'] for r in part)
    if ids(rows) != ids(train + validation + removed) or any(normalized(r) not in excluded for r in removed):
        raise ValueError('EL exclusion/coverage failure')
    if {normalized(r) for r in train + validation} & excluded:
        raise ValueError('IM validation leaked into EL')
    all_hla, train_hla = previous._hla_groups(kept), previous._hla_groups(train)
    exceptions = []
    val_hla = previous._hla_groups(validation)
    for hla, group in sorted(all_hla.items()):
        positive = sum(int(r['original_label']) for r in group)
        if hla not in train_hla or (positive and not any(int(r['original_label']) for r in train_hla[hla])):
            raise ValueError('Missing training HLA/positive anchor')
        classes = {int(r['original_label']) for r in val_hla.get(hla, [])}
        if not positive or classes != {0, 1}:
            exceptions.append({'HLA': hla, 'remaining_rows': len(group), 'remaining_positives': positive,
                               'validation_classes': sorted(classes),
                               'reason': 'No original positive anchor' if not positive else 'Grouped validation lacks both classes'})
    report.update(excluded_rows=len(removed), excluded_classes=dict(Counter(r['original_label'] for r in removed)),
                  excluded_unique_peptides=len({normalized(r) for r in removed}),
                  IM_validation_peptides_in_EL=0, rare_HLA_exceptions=exceptions)
    return report


def choose_epoch(curve: list[dict]) -> int:
    candidates = [r for r in curve if r['epoch'] in CANDIDATES]
    if sorted(r['epoch'] for r in candidates) != list(CANDIDATES):
        raise ValueError('Missing/duplicate fixed candidate')
    if any(not math.isfinite(r['validation_AP']) for r in candidates):
        raise ValueError('Nonfinite AP')
    return max(candidates, key=lambda r: (r['validation_AP'], -r['epoch']))['epoch']


def load_config(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root / CONFIG).read_text())
    expected = {'candidate_epochs': list(CANDIDATES), 'max_EL_epochs': 10, 'IM_epochs': 20,
                'seed': 42, 'batch_size': 16, 'learning_rate': 5e-5, 'device': 'cuda',
                'stability_supervision': False, 'label_policy': 'original'}
    if any(config[k] != v for k, v in expected.items()):
        raise ValueError('Frozen protocol changed')
    return config


def inputs(paths: StoragePaths, config: dict) -> dict[str, Path]:
    resolved = {}
    for name, spec in config['inputs'].items():
        runner.adapter.pilot.registry._relative(spec['relative_path'])
        root = paths.project_runs_dir if spec['area'] == 'runs' else paths.project_data_dir
        path = root / spec['relative_path']
        if runner.raw.sha256_file(path) != spec['sha256']:
            raise ValueError('Input identity mismatch: ' + name)
        resolved[name] = path
    return resolved


def im_rows(resolved: dict[str, Path]) -> tuple[list[Row], list[Row], list[Row]]:
    rows = previous.original_rows(resolved)
    with resolved['IM_split'].open(newline='') as stream:
        manifest = list(csv.DictReader(stream))
    membership = {int(r['original_prepared_row_index']): r for r in manifest}
    if len(membership) != 3428 or len(manifest) != 3428:
        raise ValueError('IM split membership changed')
    train, validation = [], []
    for row in rows:
        record = membership[row['prepared_row_index']]
        if [record['peptide'], record['HLA'], record['original_label'], record['source_row_id']] != [row['peptide'], row['hla'], row['original_label'], row['source_locator']['source_row_id']]:
            raise ValueError('IM source-row mismatch')
        {'train': train, 'validation': validation}[record['partition']].append(row)
    report = previous.verify_split(rows, train, validation)
    expected = json.loads(resolved['IM_split_receipt'].read_text())['split']
    if report != expected or len(train) != 2742 or len(validation) != 686 or len({r['peptide'] for r in validation}) != 665:
        raise ValueError('Task 2.22 IM split changed')
    return rows, train, validation


def el_rows(resolved: dict[str, Path]) -> list[Row]:
    with resolved['reference'].open(newline='') as stream:
        allowed = {runner.data.canonical_hla(r[0]) for r in list(csv.reader(stream))[1:]}
    rows = list(runner.input_rows(resolved['EL'], allowed))
    if len(rows) != 1453578 or Counter(r['original_label'] for r in rows) != {'0': 1383509, '1': 70069}:
        raise ValueError('Original EL population mismatch')
    return rows


def source_hashes(paths: StoragePaths) -> dict:
    return {name: runner.raw.sha256_file(paths.repository_root / name) for name in
            (CONFIG, 'src/stability_label_curation/bigmhc_el_multiepoch.py',
             'src/stability_label_curation/bigmhc_baseline_runner.py', 'src/stability_label_curation/bigmhc_multiepoch.py')}


def preflight(paths: StoragePaths) -> dict:
    import shutil
    config = load_config(paths)
    resolved = inputs(paths, config)
    _, im_train, im_val = im_rows(resolved)
    excluded = {normalized(r) for r in im_val}
    rows = el_rows(resolved)
    train, validation, removed = split_el(rows, excluded)
    report = verify_el(rows, train, validation, removed, excluded)
    if abs(len(validation) / (len(train)+len(validation)) - .1) > .005:
        raise ValueError('EL row balance failed')
    directory = paths.project_runs_dir / RUN_ID
    if shutil.disk_usage(directory.parent).free < 5_000_000_000:
        raise ValueError('Insufficient candidate checkpoint storage')
    if (directory/'reports/preflight.json').exists() or (directory/'reports/execution_started.json').exists():
        raise ValueError('Refuse completed preflight or started scientific run')
    directory.mkdir(mode=0o700, exist_ok=True)
    for name in ('reports', 'processed', 'predictions', 'checkpoints', 'logs'):
        (directory/name).mkdir(mode=0o700, exist_ok=True)
    def write(name: str, doc: dict) -> None:
        destination = directory/name
        if destination.exists():
            if json.loads(destination.read_text()) != doc:
                raise ValueError('Existing frozen preflight evidence differs: ' + name)
        else:
            runner.raw.write_report(destination, doc, paths=paths)
    write('reports/training_configuration.json', config)
    write('processed/IM_validation_exclusion.json', {'rule': 'All 665 normalized IM-validation peptides across HLA and labels; no scores used', 'peptides': sorted(excluded)})
    partitions = {r['prepared_row_index']: part for part, group in [('train', train), ('validation', validation), ('excluded', removed)] for r in group}
    archive = json.loads(resolved['experiment'].read_text())['archive_sha256']
    # One compact provenance manifest; do not copy either original dataset.
    manifest_path = directory/'processed/el_split_manifest_v1.csv.gz'
    with gzip.open(resolved['EL_provenance'], 'rt', newline='') as source, manifest_path.open('xb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed, io.TextIOWrapper(compressed, newline='') as target:
            fields = list(dict.fromkeys(['partition', 'original_prepared_row_index', 'peptide', 'HLA', 'original_label', *runner.PROVENANCE_FIELDS]))
            writer = csv.DictWriter(target, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            count = 0
            for record in csv.DictReader(source):
                if record['retained'] != '1':
                    continue
                count += 1
                row = rows[count-1]
                if (int(record['derived_row_index']) != count or [record['resolved_hla'], record['original_peptide'], record['original_label']] != [row['hla'], row['peptide'], row['original_label']]
                    or record['source_row_id'] != runner.adapter.pilot.row_id(archive, 'el_train.csv', int(record['row_index']))):
                    raise ValueError('EL provenance join failure')
                previous.identity.original_fields(record, 'EL')
                writer.writerow(dict(partition=partitions[count], original_prepared_row_index=count,
                                     peptide=row['peptide'], HLA=row['hla'],
                                     **{k: record[k] for k in runner.PROVENANCE_FIELDS}))
            if count != len(rows):
                raise ValueError('EL manifest coverage failure')
    write('reports/split_verification.json', report)
    novelty = verify_novelty(train, validation, im_train, im_val)
    write('reports/training_unseen_verification.json', novelty)
    proof = {'status': 'passed', 'source_hashes': source_hashes(paths), 'split': report,
             'input_hashes': config['inputs'], 'immutable_artifacts': previous.artifact_hashes(directory)}
    write('reports/preflight.json', proof)
    return {'status': 'passed', 'split': report, 'novelty': novelty}


def verify_novelty(el_train: list[Row], el_val: list[Row], im_train: list[Row], im_val: list[Row]) -> dict:
    sequences = {normalized(r) for r in im_val}
    pairs = {(normalized(r), r['hla']) for r in im_val}
    result = {'validation_rows': len(im_val), 'validation_unique_peptides': len(sequences)}
    for name, part in [('EL_train', el_train), ('EL_validation', el_val), ('IM_train', im_train)]:
        result[name+'_peptide_overlap'] = len(sequences & {normalized(r) for r in part})
        result[name+'_pair_overlap'] = len(pairs & {(normalized(r), r['hla']) for r in part})
    if any(v for k, v in result.items() if k.endswith('overlap')):
        raise ValueError('Validation sequence leakage')
    return result


class AuditedDataset:
    """Native sampler/encoder delegation, with immutable prepared-row coordinates.

    Coordinates refer to the authenticated source ledger and split manifest.
    Identity columns never enter model inputs or sampler decisions.
    """
    source_identity_audit = True
    def __init__(self, native: Any, indices: list[int]):
        if len(indices) != len(native.df) or len(set(indices)) != len(indices):
            raise ValueError('Dataset identity coverage failure')
        self.native = native
        native.df['_prepared_index'] = indices

    def makebats(self, *args: Any, **kwargs: Any) -> None:
        self.native.makebats(*args, **kwargs)

    def __len__(self) -> int:
        return len(self.native)

    def __getitem__(self, index: int) -> Any:
        batch = self.native[index]
        frame = self.native.getbat(index, enc=False)
        pairs = [(int(i), int(y)) for i, y in frame[['_prepared_index', 'tgt']].itertuples(index=False, name=None)]
        if batch.tgt.tolist() != [y for _, y in pairs]:
            raise ValueError('Batch label order failure')
        batch.source_batch_sha256 = previous.identity.digest(pairs)
        return batch


def el_metrics(rows: list[Row], probabilities: list[float]) -> dict:
    pooled = runner.development_metrics([int(r['original_label']) for r in rows], probabilities)
    groups: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row, p in zip(rows, probabilities, strict=True):
        groups[row['hla']].append((int(row['original_label']), p))
    per_hla = {}
    for hla, pairs in sorted(groups.items()):
        labels, scores = zip(*pairs)
        if set(labels) == {0, 1}:
            per_hla[hla] = runner.development_metrics(list(labels), list(scores))['AUPRC']
    return {'validation_AP': pooled['AUPRC'], 'validation_AUROC': pooled['AUROC'],
            'macro_HLA_AP': sum(per_hla.values())/len(per_hla), 'evaluable_HLAs': len(per_hla), 'per_HLA_AP': per_hla}


def execute(paths: StoragePaths) -> dict:
    import importlib.metadata
    import platform
    import resource
    import numpy as np
    import torch

    config = load_config(paths)
    directory = paths.project_runs_dir/RUN_ID
    proof = json.loads((directory/'reports/preflight.json').read_text())
    if proof['status'] != 'passed' or proof['source_hashes'] != source_hashes(paths):
        raise ValueError('Preflight code changed')
    for name, digest in proof['immutable_artifacts'].items():
        if runner.raw.sha256_file(directory/name) != digest:
            raise ValueError('Frozen split artifact changed')
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH:
        raise ValueError('Clean committed Task 2.23 branch required')
    resolved = inputs(paths, config)
    all_im, im_train, im_val = im_rows(resolved)
    rows = el_rows(resolved)
    el_train, el_val, removed = split_el(rows, {normalized(r) for r in im_val})
    if verify_el(rows, el_train, el_val, removed, {normalized(r) for r in im_val}) != proof['split']:
        raise ValueError('EL split regeneration differs')
    write = lambda name, doc: runner.raw.write_report(directory/name, doc, paths=paths)
    runner.cuda_visibility()
    device = runner.runtime_device(torch, config)
    runner.seed_runtime(torch, np, config)
    start = time.monotonic()
    write('reports/execution_started.json', {'status': 'started', 'code_commit': git('rev-parse', 'HEAD'),
          'platform': platform.platform(), 'versions': {n: importlib.metadata.version(n) for n in ('torch','numpy','pandas','psutil')},
          'device': runner.device_report(torch, device), 'configuration_sha256': runner.raw.sha256_file(paths.repository_root/CONFIG)})
    with resolved['reference'].open(newline='') as stream:
        encodings = {runner.data.canonical_hla(r[0]): torch.tensor([int(v) for v in r[1:]], dtype=torch.int8) for r in list(csv.reader(stream))[1:]}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        def dataset(part: list[Row], audit: bool = False) -> Any:
            frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(part)), allele=0, pepcol=1, tgtcol=2, hdrcnt=1, verbose=False)
            native = Dataset(frame, mhcenc=encodings)
            return AuditedDataset(native, [r['prepared_row_index'] for r in part]) if audit else native

        # Fresh authentic constructor once, no historical/public checkpoint load.
        model = runner.on_device(BigMHC(), device)
        keys = list(model.state_dict())
        if len(keys) != 36 or tuple(BigMHC.tllayers()) != runner.TRANSFER or any(p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError('Architecture/FP32 failure')
        initial = runner.state_hashes(model)
        write('reports/initial_EL_state.json', {'state': initial, 'RNG': previous.identity.rng_identity(torch, np)})
        with previous.preserve_rng(torch, np):
            probabilities, _ = previous.evaluate(torch, model, dataset(el_val[:16]), device)
        write('reports/CUDA_preflight.json', {'status': 'passed', 'finite_inference_rows': len(probabilities), 'FP32': True,
              'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
              'TF32_matmul': torch.backends.cuda.matmul.allow_tf32, 'TF32_cudnn': torch.backends.cudnn.allow_tf32})

        def save_complete(current: Any, relative: str) -> dict:
            path = directory/relative
            runner.reserve_checkpoint(path)
            runner.save_checkpoint(current, path, transfer=False, device=device)
            state = runner.state_hashes(current)
            with previous.preserve_rng(torch, np):
                loaded = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
                if runner.state_hashes(loaded) != state:
                    raise ValueError('Strict complete checkpoint reload failure')
                del loaded
            return {'checkpoint': relative, 'files': runner.checkpoint_identity(path, keys), 'state': state, 'strict_reload_identical': True}

        def fit(stage: str, current: Any, part: list[Row], validation: list[Row] | None, epochs: int,
                transfer: bool, expected: list[dict] | None = None) -> tuple[list[dict], list[dict], list[dict]]:
            native, train_eval = dataset(part, True), dataset(part)
            val_eval = dataset(validation) if validation else None
            optimizer = torch.optim.AdamW([v for k,v in current.named_parameters() if not transfer or k in runner.TRANSFER], lr=config['learning_rate'])
            initial_state = runner.state_hashes(current)
            stage_start = time.monotonic()
            torch.cuda.reset_peak_memory_stats(0)
            write(f'reports/{stage}_started.json', {'initial_state': initial_state, 'RNG': previous.identity.rng_identity(torch, np), 'epochs': epochs,
                  'training_rows': len(part), 'optimizer_defaults': optimizer.defaults, 'configuration_sha256': runner.raw.sha256_file(paths.repository_root/CONFIG)})
            curve, checkpoints, schedules = [], [], []
            cumulative = 0
            for epoch in range(1, epochs+1):
                before = previous.identity.rng_identity(torch, np)
                epoch_start = time.monotonic()
                training = runner.train_epoch(torch, current, native, config, transfer, device, optimizer=optimizer,
                                              expected_batches=expected[epoch-1]['batch_hashes'] if expected else None)
                torch.cuda.synchronize(0)
                seconds = time.monotonic()-epoch_start
                cumulative += training['optimization_steps']
                steps = previous.optimizer_steps(optimizer)
                if len(steps) != (4 if transfer else 36) or any(s != cumulative for s in steps):
                    raise ValueError('Optimizer continuation failure')
                schedule = {'batch_hashes': training['sampled_batch_sha256'], 'skip_mask': training['optimizer_skip_mask'], 'RNG_before': before,
                            'RNG_after': previous.identity.rng_identity(torch, np)}
                if expected and schedule != expected[epoch-1]:
                    raise ValueError('Matched IM RNG/sampler schedule failure')
                schedules.append(schedule)
                training.update(epoch=epoch, cumulative_optimizer_steps=cumulative, optimizer_state_steps=steps, training_seconds=seconds,
                                RNG_before=before, RNG_after=schedule['RNG_after'])
                with previous.preserve_rng(torch, np):
                    _, train_bce = previous.evaluate(torch, current, train_eval, device)
                    probabilities, val_bce = previous.evaluate(torch, current, val_eval, device) if validation else ([], None)
                metric = {'epoch': epoch, 'train_update_BCE': training['row_weighted_BCE_loss'], 'train_eval_BCE': train_bce,
                          'validation_BCE': val_bce, 'training_seconds': seconds, 'optimization_steps': training['optimization_steps'],
                          'cumulative_steps': cumulative, 'skipped_batches': training['all_negative_batches_skipped']}
                if validation:
                    if not transfer:
                        metric.update(el_metrics(validation, probabilities))
                    else:
                        values = runner.development_metrics([int(r['original_label']) for r in validation], probabilities)
                        metric.update(validation_AP=values['AUPRC'], validation_AUROC=values['AUROC'])
                    # EL scores every epoch; IM metrics are developmental and never select EL.
                    prediction_rows = [{'original_prepared_row_index':r['prepared_row_index'], 'HLA':r['hla'], 'peptide':r['peptide'],
                                        'original_label':r['original_label'], 'probability':repr(p)} for r,p in zip(validation, probabilities, strict=True)]
                    if not transfer or epoch == epochs:
                        runner.raw.write_text_report(directory/f'predictions/{stage}_epoch_{epoch:02d}.csv', previous.csv_records(prediction_rows), paths=paths)
                write(f'reports/{stage}_epoch_{epoch:02d}.json', training)
                write(f'reports/{stage}_metrics_{epoch:02d}.json', metric)
                curve.append(metric)
                if not transfer and epoch in CANDIDATES:
                    checkpoints.append(dict(epoch=epoch, **save_complete(current, f'checkpoints/EL_epoch_{epoch:02d}')))
                print(stage, metric, flush=True)
            state = runner.state_hashes(current)
            changed = [k for k in keys if state[k] != initial_state[k]]
            if (transfer and set(changed) != set(runner.TRANSFER)) or (not transfer and not changed):
                raise ValueError('Unexpected updated parameters')
            write(f'reports/{stage}_learning_curve.json', {'epochs': curve})
            write(f'reports/{stage}_completed.json', {'status': 'completed', 'epochs': epochs, 'elapsed_seconds': time.monotonic()-stage_start,
                  'optimizer_steps': cumulative, 'state': state, 'changed_parameters': changed,
                  'peak_GPU_allocated_bytes': torch.cuda.max_memory_allocated(0), 'peak_GPU_reserved_bytes': torch.cuda.max_memory_reserved(0),
                  'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
            return curve, checkpoints, schedules

        curve, candidates, _ = fit('EL', model, el_train, el_val, 10, False)
        selected = choose_epoch(curve)
        selection = {'selected_epoch': selected, 'criterion': config['selection'], 'candidates': [r for r in curve if r['epoch'] in CANDIDATES],
                     'checkpoint_lineage': candidates, 'EL_validation_refit': False, 'IM_used_for_selection': False}
        write('reports/EL_epoch_selection.json', selection)
        del model
        # Freeze the selection and verify novelty before any IM evaluation.
        write('reports/pre_IM_training_unseen_verification.json', verify_novelty(el_train, el_val, im_train, im_val))
        def fresh(epoch: int) -> Any:
            chosen = next(c for c in candidates if c['epoch'] == epoch)
            path = directory/chosen['checkpoint']
            if runner.checkpoint_identity(path, keys) != chosen['files']:
                raise ValueError('EL candidate identity changed')
            loaded = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
            if runner.state_hashes(loaded) != chosen['state']:
                raise ValueError('EL candidate reload failure')
            random.seed(42); np.random.seed(42); torch.manual_seed(42); torch.cuda.manual_seed_all(42)
            return loaded
        comparison = {}
        schedules = None
        for epoch in dict.fromkeys((1, selected)):
            model = fresh(epoch)
            stage = f'IM_from_EL_{epoch:02d}'
            im_curve, _, observed = fit(stage, model, im_train, im_val, 20, True, schedules)
            if schedules is None:
                schedules = observed
            checkpoint = save_complete(model, f'checkpoints/{stage}_epoch_20')
            comparison[str(epoch)] = {'EL_epoch': epoch, 'IM_epoch': 20, 'metrics': im_curve[-1], 'checkpoint': checkpoint}
            del model
        write('reports/IM_comparison.json', {'selected_EL_epoch': selected, 'matched_schedules': True, 'results': comparison,
              'shared_result_if_epoch1_selected': selected == 1, 'evaluation': 'Exploratory development; IM duration previously selected on this validation cohort'})
        write('reports/final_frozen_configuration.json', {'selected_EL_epoch': selected, 'IM_epochs': 20, 'IM_rows': 3428,
              'EL_selection_sha256': runner.raw.sha256_file(directory/'reports/EL_epoch_selection.json'), 'EL_validation_refit': False})
        model = fresh(selected)
        final_curve, _, _ = fit('final_all_IM', model, all_im, None, 20, True)
        final = save_complete(model, 'checkpoints/final_all_IM')
        with previous.preserve_rng(torch, np):
            before, _ = previous.evaluate(torch, model, dataset(all_im[:16]), device)
            del model
            loaded = runner.load_checkpoint(torch, BigMHC, directory/final['checkpoint'], keys, device=device)
            after, _ = previous.evaluate(torch, loaded, dataset(all_im[:16]), device)
            final['prediction_reload'] = runner.prediction_agreement(before, after, device)
        write('reports/final_checkpoint.json', dict(final, selected_EL_epoch=selected, IM_epochs=20, IM_rows=3428,
              final_training_losses=final_curve[-1], EL_validation_refit=False, EL_parent=next(c for c in candidates if c['epoch']==selected)))
    completion = {'status': 'completed', 'selected_EL_epoch': selected, 'EL_epochs': 10, 'IM_epochs': 20,
                  'elapsed_seconds': time.monotonic()-start, 'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  'stability_supervision': False, 'independent_test_accessed': False, 'protocol_deviations': []}
    write('reports/completion.json', completion)
    write('reports/output_manifest.json', previous.artifact_hashes(directory))
    return completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'execute'))
    args = parser.parse_args()
    paths = resolve_paths()
    try:
        result = preflight(paths) if args.action == 'preflight' else execute(paths)
    except Exception as error:
        directory = paths.project_runs_dir / RUN_ID
        if directory.exists():
            runner.raw.write_report(directory / f'reports/{args.action}_failure.json',
                                    {'status': 'failed', 'error': repr(error)}, paths=paths)
        raise
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
