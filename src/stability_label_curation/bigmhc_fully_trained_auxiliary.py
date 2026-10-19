"""Task 2.24: fixed-duration S/P fits, authentic shared loops, no evaluation cohort.

Only explicit configured training inputs and Task 2.23 training receipts are read.
Import and path resolution do not write or import Torch.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import random
import subprocess
import time
from typing import Any

from . import bigmhc_baseline_runner as runner
from . import bigmhc_el_multiepoch as baseline
from . import bigmhc_multiepoch as shared
from . import bigmhc_stability_auxiliary as auxiliary
from . import el_stability_loss_adapter as binding
from .paths import StoragePaths, resolve_paths

RUN_ID = 'task-2_24-fully-trained-stability-auxiliary'
BRANCH = 'task/2.24-fully-trained-stability-auxiliary'
CONFIG = 'configs/bigmhc_fully_trained_auxiliary_task2_24.json'
PROTOCOL = 'docs/BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md'
BASE_COMMIT = 'db54ac57464b6ad18e1ce8a6fc23e6dea321cb59'


def read_config(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root / CONFIG).read_text())
    fixed = dict(task='2.24', EL_epochs=10, IM_epochs=20, seed=42, batch_size=16,
                 learning_rate=5e-5, device='cuda', num_workers=0, persistent_workers=False,
                 label_policy='original', stability_supervision=True,
                 rank_reference='EL_training_positives_only', evaluation_authorized=False)
    if any(config.get(k) != v for k, v in fixed.items()):
        raise ValueError('Frozen Task 2.24 configuration changed')
    expected = dict(head='linear_414_to_1_unbounded', head_seed=22042, lambda_aux=.1,
                    permutation_seed=42, protocol_version=auxiliary.VERSION,
                    representation='condenser.att:output', representation_width=414,
                    training_authorized=True)
    if config['auxiliary'] != expected or config['baseline']['commit'] != BASE_COMMIT:
        raise ValueError('Auxiliary protocol or baseline changed')
    expected_inputs = {'EL', 'IM', 'IM_provenance', 'experiment', 'reference', 'EL_split',
                       'positive_scores', 'positive_score_manifest', *('source_'+s for s in runner.SOURCES)}
    if set(config['inputs']) != expected_inputs:
        raise ValueError('Only fixed training inputs allowed; no evaluation input')
    return config


def scientific_hashes(paths: StoragePaths) -> dict[str, str]:
    names = [CONFIG, PROTOCOL, 'src/stability_label_curation/bigmhc_fully_trained_auxiliary.py',
             'src/stability_label_curation/bigmhc_stability_auxiliary.py',
             'src/stability_label_curation/bigmhc_baseline_runner.py',
             'src/stability_label_curation/bigmhc_el_multiepoch.py',
             'src/stability_label_curation/bigmhc_multiepoch.py',
             'src/stability_label_curation/el_stability_loss_adapter.py',
             'scripts/check_bigmhc_fully_trained_auxiliary.py',
             'scripts/run_bigmhc_fully_trained_auxiliary.py',
             'tests/test_bigmhc_fully_trained_auxiliary.py', 'tests/test_bigmhc_stability_auxiliary.py']
    return {n: runner.raw.sha256_file(paths.repository_root/n) for n in names}


def scientific_artifacts(directory: Path) -> dict[str, str]:
    """Logs are closed and authenticated separately after their owning stage exits."""
    return {name: digest for name, digest in shared.artifact_hashes(directory).items()
            if not name.startswith('logs/')}


def baseline_evidence(paths: StoragePaths, config: dict) -> tuple[Path, dict]:
    directory = paths.project_runs_dir/config['baseline']['run_id']
    documents = {}
    for name, digest in config['baseline']['reports'].items():
        path = directory/'reports'/name
        if runner.raw.sha256_file(path) != digest:
            raise ValueError('Task 2.23 training receipt changed: '+name)
        documents[name] = json.loads(path.read_text())
    final = documents['final_checkpoint.json']
    if (final['selected_EL_epoch'], final['IM_epochs'], final['IM_rows']) != (10, 20, 3428):
        raise ValueError('A does not have the required final-fit lineage')
    if not final['strict_reload_identical'] or not documents['completion.json']['status'] == 'completed':
        raise ValueError('A incomplete or reload failed')
    keys = list(documents['EL_epoch_01.json']['updated_parameters'])
    files = runner.checkpoint_identity(directory/final['checkpoint'], keys)
    # Canonical sorted JSON map convention documented by Task 2.23.
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if files != final['files'] or digest != config['baseline']['checkpoint_map_sha256']:
        raise ValueError('A final checkpoint identity failed')
    parent = final['EL_parent']
    if parent['epoch'] != 10 or runner.checkpoint_identity(directory/parent['checkpoint'], keys) != parent['files']:
        raise ValueError('A EL parent identity failed')
    if any(final['state'][k] != parent['state'][k] for k in keys if k not in runner.TRANSFER):
        raise ValueError('A transfer changed parameters outside the native four')
    a_config = json.loads((paths.repository_root/baseline.CONFIG).read_text())
    if (runner.raw.sha256_file(paths.repository_root/baseline.CONFIG)
            != documents['execution_started.json']['configuration_sha256']):
        raise ValueError('A scientific configuration changed')
    for key in ('seed', 'batch_size', 'learning_rate', 'device', 'cpu_threads', 'num_workers', 'persistent_workers', 'label_policy', 'precision'):
        if config[key] != a_config[key]:
            raise ValueError('Shared scientific setting differs: '+key)
    proof = {'decision': 'reuse_exact_Task2.23_A', 'A_checkpoint': str(directory/final['checkpoint']),
             'A_checkpoint_map_sha256': digest, 'EL_epoch': 10, 'IM_epoch': 20, 'IM_rows': 3428,
             'EL_parent': parent, 'strict_reload_identical': final['strict_reload_identical'],
             'historical_prediction_reload': final['prediction_reload'],
             'native_BCE_shared_implementation': True, 'no_A_retraining_or_scoring': True,
             'previous_686_rows_are_training_not_held_out': True,
             'training_receipt_hashes': config['baseline']['reports']}
    return directory, proof


def training_rows(resolved: dict[str, Path], sidecar: binding.LossAdapter) -> tuple[list[dict], list[dict], dict]:
    """Join the existing frozen manifest; never regenerate the split or copy data."""
    with resolved['reference'].open(newline='') as stream:
        allowed = {runner.data.canonical_hla(r[0]) for r in list(csv.reader(stream))[1:]}
    train, positive_ids, partitions = [], set(), Counter()
    identity_hash = hashlib.sha256()
    with gzip.open(resolved['EL_split'], 'rt', newline='') as stream:
        manifest = csv.DictReader(stream)
        for row, record in zip(runner.input_rows(resolved['EL'], allowed), manifest, strict=True):
            if (int(record['original_prepared_row_index']) != row['prepared_row_index']
                    or [record['HLA'], record['peptide'], record['original_label']]
                    != [row['hla'], row['peptide'], row['original_label']]
                    or record['partition'] not in {'train', 'validation', 'excluded'}):
                raise ValueError('Frozen EL source-coordinate/label join failure')
            partitions[record['partition']] += 1
            if record['partition'] != 'train':
                continue
            identity = record['source_row_id']
            if row['original_label'] == '1':
                score = sidecar.scores.get(identity)
                if score is None or any(getattr(score, k) != record[v] for k, v in {
                    'prepared_row_index': 'original_prepared_row_index', 'source_row_index': 'row_index',
                    'source_row_sha256': 'source_row_sha256', 'original_hla': 'original_hla',
                    'resolved_hla': 'HLA', 'original_peptide': 'peptide', 'original_label': 'original_label'}.items()):
                    raise ValueError('Training-only Teacher score binding failed')
                if identity in positive_ids:
                    raise ValueError('Duplicate positive binding')
                positive_ids.add(identity)
            elif identity in sidecar.scores:
                raise ValueError('Teacher score bound to negative')
            identity_hash.update(binding.digest(record).encode())
            row['source_row_id'] = identity
            train.append(row)
    classes = dict(Counter(r['original_label'] for r in train))
    if partitions != {'train': 1308196, 'validation': 145371, 'excluded': 11} or classes != {'1': 63053, '0': 1245143}:
        raise ValueError('EL partition population changed')
    im = shared.original_rows(resolved)
    proof = dict(partitions=dict(partitions), training_rows=len(train), training_classes=classes,
                 training_positive_bindings=len(positive_ids), HLA_groups=len({r['hla'] for r in train}),
                 IM_rows=len(im), IM_classes=dict(Counter(r['original_label'] for r in im)),
                 ordered_training_manifest_bindings_sha256=identity_hash.hexdigest(),
                 original_HLA_source_identity_labels_preserved=True,
                 rank_reference='EL_training_positives_only',
                 differs_from_Task2_21_full_positive_rank_reference=True,
                 validation_or_excluded_rows_restored=False, raw_inputs_copied=False)
    if len(im) != 3428 or proof['IM_classes'] != {'1': 955, '0': 2473}:
        raise ValueError('Full original IM population changed')
    return train, im, proof


class AuxiliaryDataset(baseline.AuditedDataset):
    """Task 2.23 batch fingerprints plus bound positive-anchor source identity."""
    def __init__(self, native: Any, rows: list[dict], sidecar: binding.LossAdapter):
        super().__init__(native, [r['prepared_row_index'] for r in rows])
        self.adapter = sidecar
        self.source_ids = {r['prepared_row_index']: r['source_row_id'] for r in rows}

    def __getitem__(self, index: int) -> Any:
        batch = super().__getitem__(index)
        frame = self.native.getbat(index, enc=False)
        batch.source_row_ids = [self.source_ids[int(i)] for i in frame['_prepared_index']]
        batch.source_labels = [int(y) for y in frame['tgt']]
        return batch


def native_dataset(Dataset: Any, encodings: dict, rows: list[dict]) -> Any:
    frame = Dataset.readPMHCs(io.StringIO(runner.csv_text(rows)), allele=0, pepcol=1,
                             tgtcol=2, hdrcnt=1, verbose=False)
    return Dataset(frame, mhcenc=encodings)


def encodings_for(torch: Any, path: Path) -> dict:
    with path.open(newline='') as stream:
        return {runner.data.canonical_hla(r[0]): torch.tensor([int(v) for v in r[1:]], dtype=torch.int8)
                for r in list(csv.reader(stream))[1:]}


def reset_rng(torch: Any, np: Any) -> None:
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)


def check_schedule(training: dict, reference: dict, before: dict, after: dict) -> None:
    binding.check_reference({'EL': reference}, stage='EL', training=training)
    if before != reference['RNG_before'] or after != reference['RNG_after']:
        raise ValueError('A/S/P scientific RNG boundary mismatch')


def sampler_preflight(torch: Any, np: Any, Dataset: Any, encodings: dict,
                      rows: list[dict], base: Path, stage: str, epochs: int, config: dict) -> dict:
    """All native batches, no model forward or training. CUDA RNG checked live later.

    Vectorized coordinate gathering avoids encoding ten million observations.
    The actual native makebats and DataLoader index order are executed unchanged.
    GPU forward dropout consumes CUDA RNG only; this gate checks other streams.
    """
    native = native_dataset(Dataset, encodings, rows)
    native.df['_prepared_index'] = [r['prepared_row_index'] for r in rows]
    evidence = []
    for epoch in range(1, epochs+1):
        ref = json.loads((base/f'reports/{stage}_epoch_{epoch:02d}.json').read_text())
        before = binding.rng_identity(torch, np)
        for key in ('python', 'numpy', 'torch_cpu'):
            if before[key] != ref['RNG_before'][key]:
                raise ValueError('Sampler preflight initial RNG mismatch: '+key)
        native.makebats(config['batch_size'], shuffle=True, negfrac=.99 if stage == 'EL' else None)
        coordinates = native.df['_prepared_index'].to_numpy()
        labels = native.df['tgt'].to_numpy()
        table = native.bats.obj
        groups = [g['dfidx'].to_numpy() for _, g in table.groupby('batidx', sort=True)]
        class Indices:
            def __len__(self):
                return len(groups)
            def __getitem__(self, index):
                return index
        loader = torch.utils.data.DataLoader(Indices(), batch_size=None, shuffle=True, num_workers=0)
        hashes, skipped = [], []
        for index in loader:
            selection = groups[index]
            pairs = [(int(i), int(y)) for i, y in zip(coordinates[selection], labels[selection], strict=True)]
            hashes.append(binding.digest(pairs))
            skipped.append(stage != 'EL' and not any(y for _, y in pairs))
        if hashes != ref['sampled_batch_sha256'] or skipped != ref['optimizer_skip_mask']:
            raise ValueError('Native sampling differs from A before scientific training')
        after = binding.rng_identity(torch, np)
        for key in ('python', 'numpy', 'torch_cpu'):
            if after[key] != ref['RNG_after'][key]:
                raise ValueError('Sampler preflight final RNG mismatch: '+key)
        evidence.append(dict(epoch=epoch, batches=len(hashes), batch_fingerprint=binding.digest(hashes),
                             skip_fingerprint=binding.digest(skipped), CPU_sampler_RNG_matches_A=True))
        print('preflight sampler', stage, epoch, 'passed', flush=True)
    return {'epochs': evidence, 'all_ordered_batches_match_A': True,
            'CUDA_forward_RNG_checked_during_scientific_training': True}


def preflight(paths: StoragePaths) -> dict:
    import importlib.metadata
    import platform
    import numpy as np
    import torch
    config = read_config(paths)
    directory = paths.project_runs_dir/RUN_ID
    if (directory/'reports/preflight.json').exists() or (directory/'reports/execution_started.json').exists():
        raise ValueError('Refuse completed preflight or already started scientific run')
    resolved = baseline.inputs(paths, config)
    base, compatibility = baseline_evidence(paths, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    el, im, cohort = training_rows(resolved, sidecar)
    ids = {r['source_row_id'] for r in el if r['original_label'] == '1'}
    s, p = (auxiliary.Targets(sidecar, mode, source_ids=ids) for mode in ('S', 'P'))
    targets = auxiliary.compare_targets(s, p)
    targets.update(minimum=str(min(s.exact.values())), maximum=str(max(s.exact.values())),
                   total_exact=str(sum(s.exact.values())),
                   changed_assignments=sum(s.exact[i] != p.exact[i] for i in ids),
                   fixed_or_tied_assignments=sum(s.exact[i] == p.exact[i] for i in ids))
    runner.cuda_visibility()
    device = runner.runtime_device(torch, config)
    runner.seed_runtime(torch, np, config)
    runtime = dict(platform=platform.platform(), versions={n: importlib.metadata.version(n) for n in ('torch', 'numpy', 'pandas', 'psutil')},
                   device=runner.device_report(torch, device))
    old_runtime = json.loads((base/'reports/execution_started.json').read_text())
    if runtime['versions'] != old_runtime['versions'] or runtime['device'] != old_runtime['device']:
        raise ValueError('A/S/P runtime or GPU mismatch')
    encodings = encodings_for(torch, resolved['reference'])
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        initial = json.loads((base/'reports/initial_EL_state.json').read_text())
        heads = []
        for mode in ('S', 'P'):
            reset_rng(torch, np)
            model = runner.on_device(BigMHC(), device)
            if runner.state_hashes(model) != initial['state'] or binding.rng_identity(torch, np) != initial['RNG']:
                raise ValueError('A/S/P backbone initialization mismatch')
            head = auxiliary.AuxiliaryHead(torch, model, device=device)
            if (binding.rng_identity(torch, np) != initial['RNG'] or runner.state_hashes(model) != initial['state']
                    or sum(v.numel() for v in head.head.parameters()) != 415):
                raise ValueError('Head initialization changed scientific RNG/backbone')
            heads.append(runner.state_hashes(head.head))
            del head, model
        if heads[0] != heads[1]:
            raise ValueError('S/P head initialization mismatch')
        # Recreate exact post-constructor RNG without advancing scientific models.
        reset_rng(torch, np)
        model = runner.on_device(BigMHC(), device)
        del model
        el_sampler = sampler_preflight(torch, np, Dataset, encodings, el, base, 'EL', 10, config)
        reset_rng(torch, np)
        im_sampler = sampler_preflight(torch, np, Dataset, encodings, im, base, 'final_all_IM', 20, config)
    directory.mkdir(mode=0o700, exist_ok=True)
    for sub in ('reports', 'logs', 'checkpoints'):
        (directory/sub).mkdir(mode=0o700, exist_ok=True)
    def write(name: str, doc: dict) -> None:
        path = directory/name
        if path.exists():
            if json.loads(path.read_text()) != doc:
                raise ValueError('Existing preparation receipt differs: '+name)
        else:
            runner.raw.write_report(path, doc, paths=paths)
    write('reports/baseline_compatibility.json', compatibility)
    write('reports/cohort_binding.json', cohort)
    write('reports/target_permutation.json', targets)
    write('reports/initialization.json', dict(backbone=initial, S_head=heads[0], P_head=heads[1],
                                             head_parameters=415, isolated_head_RNG=True))
    write('reports/sampler_preflight.json', dict(EL=el_sampler, IM=im_sampler))
    write('reports/scientific_configuration.json', config)
    proof = dict(status='passed', scientific_hashes=scientific_hashes(paths), runtime=runtime,
                 cohort=cohort, immutable_artifacts=scientific_artifacts(directory),
                 expensive_scientific_training_executed=False, sealed_benchmark_accessed=False)
    write('reports/preflight.json', proof)
    return {'status': 'passed', 'cohort': cohort}


def execute(paths: StoragePaths) -> dict:
    import resource
    import numpy as np
    import torch
    config = read_config(paths)
    directory = paths.project_runs_dir/RUN_ID
    proof = json.loads((directory/'reports/preflight.json').read_text())
    if proof['status'] != 'passed' or proof['scientific_hashes'] != scientific_hashes(paths):
        raise ValueError('Preflight failed or scientific source/protocol changed')
    for name, digest in proof['immutable_artifacts'].items():
        if runner.raw.sha256_file(directory/name) != digest:
            raise ValueError('Frozen preflight artifact changed')
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH:
        raise ValueError('Clean committed Task 2.24 branch required')
    if git('merge-base', BASE_COMMIT, 'HEAD') != BASE_COMMIT:
        raise ValueError('Task 2.24 must descend from exact approved base')
    gate = json.loads((directory/'reports/focused_tests.json').read_text())
    if (gate['status'] != 'passed' or gate['skipped'] or gate['device'] != 'cuda:0'
            or gate['scientific_hashes'] != scientific_hashes(paths)):
        raise ValueError('Current focused CUDA tests required before training')
    resolved = baseline.inputs(paths, config)
    base, _ = baseline_evidence(paths, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    el, im, cohort = training_rows(resolved, sidecar)
    if cohort != proof['cohort']:
        raise ValueError('Frozen training binding changed')
    ids = {r['source_row_id'] for r in el if r['original_label'] == '1'}
    targets = {m: auxiliary.Targets(sidecar, m, source_ids=ids) for m in ('S', 'P')}
    auxiliary.compare_targets(targets['S'], targets['P'])
    runner.cuda_visibility()
    device = runner.runtime_device(torch, config)
    runner.seed_runtime(torch, np, config)
    write = lambda name, doc: runner.raw.write_report(directory/name, doc, paths=paths)
    started = time.monotonic()
    write('reports/execution_started.json', dict(status='started', commit=git('rev-parse', 'HEAD'),
          scientific_hashes=scientific_hashes(paths), runtime=proof['runtime']))
    encodings = encodings_for(torch, resolved['reference'])
    initialization = json.loads((directory/'reports/initialization.json').read_text())
    results = {}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        def save_complete(model: Any, name: str, probe: list[dict]) -> dict:
            path = directory/name
            runner.reserve_checkpoint(path)
            runner.save_checkpoint(model, path, transfer=False, device=device)
            state, keys = runner.state_hashes(model), list(model.state_dict())
            with shared.preserve_rng(torch, np):
                before = runner.predict(torch, model, native_dataset(Dataset, encodings, probe), 16, device)
                loaded = runner.load_checkpoint(torch, BigMHC, path, keys, device=device)
                if runner.state_hashes(loaded) != state:
                    raise ValueError('Complete checkpoint reload differs')
                after = runner.predict(torch, loaded, native_dataset(Dataset, encodings, probe), 16, device)
                if before != after:
                    raise ValueError('Same-device checkpoint reload predictions differ')
                del loaded
            return dict(checkpoint=name, files=runner.checkpoint_identity(path, keys), state=state,
                        strict_reload_identical=True, probe_rows=len(probe), probe_is_training_data=True,
                        prediction_reload=runner.prediction_agreement(before, after, device))

        for mode in ('S', 'P'):
            reset_rng(torch, np)
            model = runner.on_device(BigMHC(), device)
            initial = runner.state_hashes(model)
            head = auxiliary.AuxiliaryHead(torch, model, device=device)
            if (initial != initialization['backbone']['state'] or runner.state_hashes(head.head) != initialization[mode+'_head']
                    or binding.rng_identity(torch, np) != initialization['backbone']['RNG']):
                raise ValueError('Scientific initial backbone/head/RNG differs from preflight')
            write(f'reports/{mode}_initialization.json', dict(backbone=initial, head=runner.state_hashes(head.head), RNG=binding.rng_identity(torch, np)))
            curves, checkpoints = {}, {}
            native = AuxiliaryDataset(native_dataset(Dataset, encodings, el), el, sidecar)
            optimizer = torch.optim.AdamW(list(model.parameters())+list(head.head.parameters()), lr=config['learning_rate'])
            for stage, epochs in (('EL', 10), ('IM', 20)):
                if stage == 'IM':
                    head.close()
                    del head, optimizer, model, native
                    parent = checkpoints['EL']
                    model = runner.load_checkpoint(torch, BigMHC, directory/parent['checkpoint'], parent['state_keys'], device=device)
                    if runner.state_hashes(model) != parent['state'] or hasattr(model, 'head'):
                        raise ValueError('IM failed plain authentic EL-backbone transfer')
                    reset_rng(torch, np)
                    native = baseline.AuditedDataset(native_dataset(Dataset, encodings, im), [r['prepared_row_index'] for r in im])
                    optimizer = torch.optim.AdamW([v for k, v in model.named_parameters() if k in runner.TRANSFER], lr=config['learning_rate'])
                stage_initial = runner.state_hashes(model)
                stage_started = time.monotonic()
                torch.cuda.reset_peak_memory_stats(0)
                write(f'reports/{mode}_{stage}_started.json', dict(status='started', epochs=epochs,
                      initial_state=stage_initial, RNG=binding.rng_identity(torch, np),
                      training_rows=len(el if stage == 'EL' else im), optimizer_defaults=optimizer.defaults,
                      auxiliary_head_present=stage == 'EL'))
                curve, cumulative = [], 0
                for epoch in range(1, epochs+1):
                    source_stage = 'EL' if stage == 'EL' else 'final_all_IM'
                    reference = json.loads((base/f'reports/{source_stage}_epoch_{epoch:02d}.json').read_text())
                    before = binding.rng_identity(torch, np)
                    if before != reference['RNG_before']:
                        raise ValueError('Scientific RNG differs before update')
                    epoch_started = time.monotonic()
                    if stage == 'EL':
                        training = auxiliary.train_el(torch, model, native, config, head, targets[mode], reference,
                                                       device=device, optimizer=optimizer)
                    else:
                        training = runner.train_epoch(torch, model, native, config, True, device,
                                                       expected_batches=reference['sampled_batch_sha256'], optimizer=optimizer)
                    torch.cuda.synchronize(0)
                    after = binding.rng_identity(torch, np)
                    check_schedule(training, reference, before, after)
                    cumulative += training['optimization_steps']
                    steps = shared.optimizer_steps(optimizer)
                    if len(steps) != (38 if stage == 'EL' else 4) or any(s != cumulative for s in steps):
                        raise ValueError('Persistent optimizer continuation failed')
                    training.update(epoch=epoch, cumulative_optimizer_steps=cumulative, optimizer_state_steps=steps,
                                    RNG_before=before, RNG_after=after, training_seconds=time.monotonic()-epoch_started,
                                    ordered_sampling_matches_A=True)
                    metric = dict(epoch=epoch, native_BCE=training['row_weighted_BCE_loss'],
                                  source_style_BCE=training.get('source_style_epoch_BCE_loss', training.get('source_style_epoch_loss')),
                                  auxiliary_MSE=training.get('mean_auxiliary_MSE'), total_loss=training.get('mean_total_loss'),
                                  optimizer_steps=training['optimization_steps'], cumulative_optimizer_steps=cumulative,
                                  training_seconds=training['training_seconds'],
                                  sampled_class_exposures=training['sampled_class_exposures'],
                                  sampling_fingerprint=binding.digest(training['sampled_batch_sha256']))
                    write(f'reports/{mode}_{stage}_epoch_{epoch:02d}.json', training)
                    write(f'reports/{mode}_{stage}_metrics_{epoch:02d}.json', metric)
                    curve.append(metric)
                    print(mode, stage, metric, flush=True)
                checkpoint = save_complete(model, f'checkpoints/{mode}_{stage}_epoch_{epochs:02d}', (el if stage == 'EL' else im)[:16])
                # Retain native ordered keys for the explicit EL-to-IM reload.
                checkpoint['state_keys'] = list(model.state_dict())
                if stage == 'EL':
                    head_path = directory/f'checkpoints/{mode}_auxiliary_head.pt'
                    with head_path.open('xb') as stream:
                        torch.save({k: v.detach().cpu() for k, v in head.head.state_dict().items()}, stream)
                    loaded = torch.load(head_path, map_location=device, weights_only=True)
                    if any(not torch.equal(loaded[k], v) for k, v in head.head.state_dict().items()):
                        raise ValueError('Auxiliary head strict reload failed')
                    checkpoint.update(auxiliary_head_file=str(head_path.relative_to(directory)),
                                      auxiliary_head_sha256=runner.raw.sha256_file(head_path),
                                      auxiliary_head_state=runner.state_hashes(head.head), auxiliary_head_reload_identical=True)
                state = runner.state_hashes(model)
                changed = [k for k in state if state[k] != stage_initial[k]]
                if stage == 'IM' and set(changed) != set(runner.TRANSFER):
                    raise ValueError('IM updated parameters beyond native four')
                if stage == 'EL' and (not changed or checkpoint['auxiliary_head_state'] == initialization[mode+'_head']):
                    raise ValueError('Auxiliary EL did not update backbone and head')
                checkpoints[stage], curves[stage] = checkpoint, curve
                write(f'reports/{mode}_{stage}_checkpoint.json', dict(checkpoint, parent=checkpoints.get('EL') if stage == 'IM' else None))
                write(f'reports/{mode}_{stage}_learning_curve.json', dict(epochs=curve))
                write(f'reports/{mode}_{stage}_completed.json', dict(status='completed', epochs=epochs,
                      optimizer_steps=cumulative, elapsed_seconds=time.monotonic()-stage_started,
                      changed_parameters=changed, auxiliary_head_excluded_from_IM=stage == 'IM',
                      peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated(0),
                      peak_GPU_reserved_bytes=torch.cuda.max_memory_reserved(0),
                      peak_host_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
            results[mode] = dict(checkpoints=checkpoints, curves=curves)
            del model, optimizer, native
    frozen = dict(status='frozen', A_reference='reports/baseline_compatibility.json', models=results,
                  scientific_hashes=scientific_hashes(paths), protocol_sha256=runner.raw.sha256_file(paths.repository_root/PROTOCOL),
                  EL_epochs=10, IM_epochs=20, sealed_benchmark_accessed=False,
                  internal_development_evaluation_executed=False, protocol_deviations=[],
                  elapsed_seconds=time.monotonic()-started, peak_host_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    write('reports/frozen_models.json', frozen)
    write('reports/completion.json', {k: v for k, v in frozen.items() if k != 'models'})
    write('reports/output_manifest.json', scientific_artifacts(directory))
    return {k: v for k, v in frozen.items() if k != 'models'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'execute'))
    args = parser.parse_args()
    paths = resolve_paths()
    try:
        result = preflight(paths) if args.action == 'preflight' else execute(paths)
    except Exception as exc:
        directory = paths.project_runs_dir/RUN_ID
        if (directory/'reports').is_dir():
            destination = directory/f'reports/{args.action}_failure_{time.time_ns()}.json'
            runner.raw.write_report(destination, dict(status='failed', action=args.action, error=repr(exc)), paths=paths)
        raise
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
