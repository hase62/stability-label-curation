"""Task 2.20 preparation and future bounded S/P execution; never trains on import."""
from copy import deepcopy
import csv
import io
import os
from pathlib import Path
import subprocess
import sys
import time

from . import bigmhc_baseline_runner as runner
from . import bigmhc_baseline_compatibility as baseline
from . import bigmhc_stability_auxiliary as aux
from . import el_stability_loss_adapter as binding
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/bigmhc_stability_auxiliary_task2_20.json'
RUN_ID = 'task-2_21-stability-auxiliary-gpu'
LEGACY_CONFIG = 'configs/bigmhc_low_stability_task2_19.json'


def load_config(path: Path, paths: StoragePaths) -> dict:
    c = runner.readers._json(path)
    expected = runner.readers._json(paths.repository_root / CONFIG)
    # Only arm and explicit future authorization can vary in an execution config.
    normalized = deepcopy(c)
    normalized['condition'] = 'S'
    normalized['auxiliary']['training_authorized'] = False
    canonical = deepcopy(expected)
    canonical['condition'] = 'S'
    canonical['auxiliary']['training_authorized'] = False
    fixed = {'lambda_aux': 0.1, 'representation': 'condenser.att:output', 'representation_width': 414,
             'head': 'linear_414_to_1_unbounded', 'head_seed': aux.HEAD_SEED, 'permutation_seed': 42,
             'training_authorized': False, 'protocol_version': aux.VERSION}
    if (normalized != canonical or c['schema_version'] != 1 or c['version'] != 'bigmhc_stability_auxiliary_v1'
            or c['condition'] not in {'S', 'P'} or normalized['auxiliary'] != fixed
            or type(c['auxiliary']['training_authorized']) is not bool
            or c['baseline_reuse'] != {'commit': baseline.BASELINE_COMMIT, 'reference': baseline.REFERENCE}
            or binding.matched_config_identity(c) != baseline.SCIENTIFIC_IDENTITY):
        raise ValueError('Task 2.20 configuration differs from the prespecified experiment')
    return c


def require_authorization(config: dict) -> None:
    if config['auxiliary']['training_authorized'] is not True:
        raise ValueError('Task 2.20 authorizes preparation only; GPU training requires separate authorization')


def source_identity(paths: StoragePaths) -> dict:
    return {p.name: runner.raw.sha256_file(p) for p in (
        Path(__file__), Path(aux.__file__), Path(runner.__file__), Path(binding.__file__),
        paths.repository_root / CONFIG, paths.repository_root / 'tests/test_bigmhc_stability_auxiliary.py')}


def contrasts(metrics: dict) -> dict:
    return {a + '-' + b: {stage: {key: metrics[a][stage][key] - metrics[b][stage][key]
            for key in ('AUPRC', 'AUROC')} for stage in ('IM', 'EL_proxy')}
            for a, b in (('S', 'A'), ('S', 'P'), ('P', 'A'))}


def worker(config_path: Path, directory: Path, paths: StoragePaths) -> dict:
    """Separate process per arm: identical seed/init/sampler and own EL→IM parent."""
    import numpy as np
    import torch
    import importlib.metadata
    import resource
    config = load_config(config_path, paths)
    require_authorization(config)
    if directory != paths.project_runs_dir / RUN_ID / config['condition']:
        raise ValueError('Unexpected auxiliary arm destination')
    parent = directory.parent
    manifest = runner.runs.validate_manifest(runner.readers._json(directory / 'manifest.json'))
    parent_manifest = runner.runs.validate_manifest(runner.readers._json(parent / 'manifest.json'))
    if (manifest['git'] != parent_manifest['git'] or not manifest['git']['working_tree_clean']
            or runner.runs.capture_git_provenance(paths.repository_root) != manifest['git']
            or manifest['configuration']['file'] != {'path': str(config_path), 'sha256': runner.raw.sha256_file(config_path)}):
        raise ValueError('Auxiliary worker committed configuration lineage mismatch')
    proof = runner.readers._json(parent / 'reports/baseline_compatibility.json')
    if proof['source_sha256'] != source_identity(paths) or proof['execution_commit'] != manifest['git']['commit_sha']:
        raise ValueError('Auxiliary compatibility proof belongs to different source')
    resolved, inputs = runner.resolve_inputs(config, paths)
    proof_path = parent / 'reports/baseline_compatibility.json'
    proof_identity = {'path': str(proof_path), 'sha256': runner.raw.sha256_file(proof_path)}
    if any(i not in manifest['data_provenance']['input_artifacts'] for i in [*inputs, proof_identity]):
        raise ValueError('Worker input/compatibility receipt differs from its manifest')
    ref_path = paths.project_runs_dir / baseline.REFERENCE['relative_path']
    if runner.raw.sha256_file(ref_path) != baseline.REFERENCE['sha256']:
        raise ValueError('Historical A reference changed')
    reference = runner.readers._json(ref_path)
    device = runner.runtime_device(torch, config)
    versions = {n: importlib.metadata.version(n) for n in ('torch', 'numpy', 'pandas', 'psutil')}
    if versions != reference['versions'] or device != reference['device']:
        raise ValueError('Runtime differs from reused A; compatibility must be resolved before training')
    runner.seed_runtime(torch, np, config)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    targets = aux.Targets(sidecar, config['condition'])
    write = lambda relative, doc: runner.raw.write_report(directory / relative, doc, paths=paths)
    write('reports/auxiliary_target_invariants.json', targets.evidence)
    write('reports/environment.json', {**runner.device_report(torch, device), 'versions': versions,
          'platform': sys.platform, 'source_commit': runner.SOURCE_COMMIT, 'FP32': True,
          'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(), 'configuration': config})
    inventory = runner.readers._json(resolved['inventory'])
    allowed = set().union(*(v['by_HLA'] for v in inventory.values()))
    encodings = {}
    with runner.raw._read_file(resolved['reference']) as stream, io.TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
        rows = csv.reader(text)
        next(rows)
        for row in rows:
            hla = runner.data.canonical_hla(row[0])
            if hla in allowed:
                encodings[hla] = torch.tensor([int(v) for v in row[1:]], dtype=torch.int8)
    development = list(runner.input_rows(resolved['development'], allowed))
    if len(development) != 383:
        raise ValueError('Frozen development cohort changed')
    runner.attach_provenance(development, resolved['development_provenance'])
    matched = {'initial_tensor_sha256': {}, 'versions': versions, 'device': device,
               'configuration_identity': binding.matched_config_identity(config), 'code_commit': manifest['git']['commit_sha']}
    with runner.pinned_modules(resolved) as (BigMHC, Dataset):
        def dataset(stage: str, audited: bool = True):
            native = Dataset(Dataset.readPMHCs(str(resolved[stage]), allele=0, pepcol=1, tgtcol=2, hdrcnt=1, verbose=False), mhcenc=encodings)
            if not audited:
                return native
            records = (r for r in binding.manifest_rows(resolved[stage + '_provenance']) if r['retained'] == '1')
            return binding.IdentityDataset(native, records, stage=stage, adapter=sidecar if stage == 'EL' else None,
                                           archive_sha256=sidecar.manifest['archive_sha256'])
        model = runner.on_device(BigMHC(), device)
        keys = list(model.state_dict())
        if len(keys) != 36 or tuple(BigMHC.tllayers()) != runner.TRANSFER or any(p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError('Authentic FP32 architecture changed')
        initial = runner.state_hashes(model)
        binding.check_reference(reference, initial=initial)
        head = aux.AuxiliaryHead(torch, model, device=device)
        head_initial = runner.state_hashes(head.head)
        if config['condition'] == 'P' and head_initial != runner.readers._json(parent / 'S/reports/initial_auxiliary_state_identity.json'):
            raise ValueError('S/P auxiliary initialization mismatch')
        write('reports/initial_auxiliary_state_identity.json', head_initial)
        write('reports/initial_el_state_identity.json', initial)
        matched['initial_tensor_sha256'] = initial
        architecture = {'backbone_parameters': sum(p.numel() for p in model.parameters()), 'state_tensors': 36,
                        'auxiliary_parameters': sum(p.numel() for p in head.head.parameters()),
                        'representation': 'condenser.att output before original HLA mask/out', 'width': 414}
        if architecture['auxiliary_parameters'] != 415:
            raise ValueError('Auxiliary head architecture changed')
        def stage(stage_name, current, operation):
            boundary = binding.rng_identity(torch, np)
            binding.check_reference(reference, stage=stage_name, rng=boundary)
            matched['rng_before_' + stage_name] = boundary
            write(f'reports/{stage_name.lower()}_stage_started.json', {'status': 'started', 'RNG_boundary': boundary,
                  'state_tensor_sha256': runner.state_hashes(current), 'condition': config['condition']})
            torch.cuda.synchronize(0)
            torch.cuda.reset_peak_memory_stats(0)
            started = time.monotonic()
            try:
                result = operation()
                torch.cuda.synchronize(0)
                binding.check_reference(reference, stage=stage_name, training=result)
            except Exception as error:
                write(f'reports/{stage_name.lower()}_stage_failed.json', {'status': 'failed', 'reason': repr(error)})
                raise
            result.update(elapsed_seconds=time.monotonic() - started,
                          peak_host_RSS_bytes_through_stage=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                          GPU_memory={'peak_allocated_bytes': torch.cuda.max_memory_allocated(0),
                                      'peak_reserved_bytes': torch.cuda.max_memory_reserved(0)})
            matched[stage_name] = {k: result[k] for k in ('optimization_steps', 'sampled_batch_sha256', 'optimizer_defaults', 'updated_parameters', 'optimizer_skip_mask')}
            write(f'reports/{stage_name.lower()}_stage_completed.json', {'status': 'completed', 'training': result,
                  'ordered_batch_sha256': binding.digest(result['sampled_batch_sha256']), 'state_tensor_sha256': runner.state_hashes(current)})
            return result
        # Dataset construction consumes no RNG, matching the original runner's order.
        el_training = stage('EL', model, lambda: aux.train_el(torch, model, dataset('EL'), config, head, targets, reference['EL'], device=device))
        el_state = runner.state_hashes(model)
        head_final = runner.state_hashes(head.head)
        if head_final == head_initial or el_state == initial:
            raise ValueError('EL backbone/auxiliary head did not update')
        # Independent tensor-only auxiliary checkpoint, never added to BigMHC state.
        head_path = directory / 'checkpoints/auxiliary_head.pt'
        with head_path.open('xb') as stream:
            torch.save({k: v.detach().cpu() for k, v in head.head.state_dict().items()}, stream)
        with runner.raw._read_file(head_path) as stream:
            state = torch.load(stream, map_location='cpu', weights_only=True)
        head.head.load_state_dict(state, strict=True)
        if runner.state_hashes(head.head) != head_final:
            raise ValueError('Auxiliary head checkpoint reload mismatch')
        auxiliary_lineage = {'checkpoint': 'checkpoints/auxiliary_head.pt', 'sha256': runner.raw.sha256_file(head_path),
                             'initial_tensor_sha256': head_initial, 'trained_tensor_sha256': head_final,
                             'EL_parent_state_sha256': el_state, 'head_seed': aux.HEAD_SEED,
                             'target_assignment': targets.evidence, 'excluded_from_IM': True, 'strict_reload_identical': True}
        write('reports/auxiliary_checkpoint_lineage.json', auxiliary_lineage)
        dev = dataset('development', audited=False)
        el_predictions = runner.predict(torch, model, dev, config['batch_size'], device)
        el = directory / 'checkpoints/el'
        runner.reserve_checkpoint(el)
        runner.save_checkpoint(model, el, transfer=False, device=device)
        el_files = runner.checkpoint_identity(el, keys)
        reloaded = runner.load_checkpoint(torch, BigMHC, el, keys, device=device)
        if runner.state_hashes(reloaded) != el_state:
            raise ValueError('Authentic EL reload mismatch')
        el_agreement = runner.prediction_agreement(el_predictions, runner.predict(torch, reloaded, dev, config['batch_size'], device), device)
        write('reports/el_stage_checkpoint.json', {'status': 'verified', 'files': el_files, 'auxiliary': auxiliary_lineage})
        runner.write_predictions(directory / 'predictions/el_development.csv', development, el_predictions, paths)
        del head, model
        # Only the strict authentic 36-tensor model reaches IM; original 4-parameter mapping.
        im_training = stage('IM', reloaded, lambda: runner.train_epoch(torch, reloaded, dataset('IM'), config, True, device,
                            expected_batches=reference['IM']['sampled_batch_sha256']))
        im_state = runner.state_hashes(reloaded)
        changed = [k for k in keys if im_state[k] != el_state[k]]
        if not changed or set(changed) - set(runner.TRANSFER):
            raise ValueError('IM transfer changed unauthorized parameters')
        im_predictions = runner.predict(torch, reloaded, dev, config['batch_size'], device)
        im = el / 'im'
        runner.reserve_checkpoint(im)
        runner.save_checkpoint(reloaded, im, transfer=True, device=device)
        lineage = {'state_keys': keys, 'EL_files': el_files, 'IM_files': runner.overlay_identity(im, keys),
                   'changed_IM_parameters': changed, 'EL_reload_identical': True, 'IM_reload_identical': True,
                   'auxiliary_head_excluded_from_IM': True, 'auxiliary_lineage': auxiliary_lineage,
                   'initial_state_tensor_sha256': initial, 'EL_state_tensor_sha256': el_state,
                   'IM_state_tensor_sha256': im_state, 'IM_parent_relative_path': '..',
                   'checkpoint_loading': 'weights_only=True,map_location=cpu,strict authentic state load'}
        runner.verify_parent(el, im, lineage)
        reconstructed = runner.load_checkpoint(torch, BigMHC, im, keys, device=device, lineage=lineage)
        if runner.state_hashes(reconstructed) != im_state:
            raise ValueError('IM overlay reload mismatch')
        im_agreement = runner.prediction_agreement(im_predictions, runner.predict(torch, reconstructed, dev, config['batch_size'], device), device)
        write('reports/im_stage_checkpoint.json', {'status': 'verified', 'files': lineage['IM_files'], 'parent': 'checkpoints/el'})
        lineage['prediction_reload_agreement'] = {'EL': el_agreement, 'IM': im_agreement}
    runner.write_predictions(directory / 'predictions/im_development.csv', development, im_predictions, paths)
    metrics = {stage: runner.development_metrics([int(r['original_label']) for r in development], probabilities)
               for stage, probabilities in (('EL_proxy', el_predictions), ('IM', im_predictions))}
    write('reports/development_metrics.json', metrics)
    write('reports/checkpoint_lineage.json', lineage)
    write('reports/training_configuration.json', config)
    write('reports/matched_state.json', matched)
    write('reports/training_summary.json', {'architecture': architecture, 'EL': el_training, 'IM': im_training,
          'condition': config['condition'], 'metrics': metrics, 'auxiliary_targets': targets.evidence,
          'interpretation': 'Third exploratory development evaluation; Teacher kinetic-stability estimates, no label-reliability inference'})
    for item in inputs:
        if runner.raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Immutable input changed')
    outputs = {str(p.relative_to(directory)): runner.raw.sha256_file(p) for area in ('reports', 'predictions', 'checkpoints')
               for p in sorted((directory / area).rglob('*')) if p.is_file()}
    write('reports/execution_verification.json', {'code_commit': manifest['git']['commit_sha'], 'outputs': outputs,
          'reload_predictions_consistent': True, 'sealed_payloads_opened': [], 'inputs': inputs})
    return metrics


def bounded_worker(config_path: Path, directory: Path, paths: StoragePaths) -> dict:
    """Same 3600s/32GiB limits, own child only; no automatic retries."""
    import psutil
    config = load_config(config_path, paths)
    require_authorization(config)
    command = [sys.executable, '-B', '-m', 'stability_label_curation.bigmhc_auxiliary_experiment', '--worker', '--config', str(config_path), '--out', str(directory)]
    env = dict(os.environ, PYTHONPATH=str(paths.repository_root / 'src'), PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', TORCH_FORCE_WEIGHTS_ONLY_LOAD='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    runner.cuda_visibility(env)
    start, peak, blocker = time.monotonic(), 0, None
    with (directory / 'logs/training.log').open('xb') as log:
        process = subprocess.Popen(command, cwd=paths.repository_root, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            monitored = psutil.Process(process.pid)
            while process.poll() is None:
                try:
                    peak = max(peak, monitored.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if time.monotonic() - start > config['wall_seconds']:
                    blocker = 'wall_clock_budget_exceeded'
                if peak > config['memory_bytes']:
                    blocker = 'worker_RSS_budget_exceeded'
                if blocker:
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    result = {'status': 'completed' if process.returncode == 0 and blocker is None else 'failed',
              'worker_exit_code': process.returncode, 'blocker': blocker, 'elapsed_seconds': time.monotonic() - start,
              'peak_worker_RSS_bytes': peak, 'wall_budget_seconds': config['wall_seconds'], 'RSS_budget_bytes': config['memory_bytes']}
    runner.raw.write_report(directory / 'reports/resource_execution.json', result, paths=paths)
    if result['status'] != 'completed':
        raise RuntimeError('Auxiliary worker failed; inspect retained logs')
    return result


def execute(config_path: Path, gate_report: Path, test_log: Path, paths: StoragePaths) -> dict:
    config = load_config(config_path, paths)
    require_authorization(config)  # First: shipped preparation config cannot train/create runs.
    runner.cuda_visibility()
    gate = runner.readers._json(gate_report)
    if (gate.get('status') != 'passed' or gate.get('device') != 'cuda:0'
            or gate.get('source_sha256') != source_identity(paths) or gate.get('skipped') != 0
            or gate.get('tests', 0) < 12
            or gate.get('historical_A_numeric_compatibility', {}).get('reuse_compatible') is not True):
        raise ValueError('Current authentic synthetic CUDA gate required before scientific execution')
    tests = test_log.read_text()
    if '\nOK' not in tests or '\nFAILED' in tests or 'skipped=' in tests:
        raise ValueError('Passing focused tests required')
    # Existing full-cohort validation is read-only and scores no new development rows.
    from .bigmhc_abp_preflight import validate
    preflight = validate(config_path=paths.repository_root / LEGACY_CONFIG, paths=paths)
    resolved, inputs = runner.resolve_inputs(config, paths)
    sidecar = binding.load_sidecar(resolved['positive_scores'], resolved['positive_score_manifest'])
    target_proof = aux.compare_targets(aux.Targets(sidecar, 'S'), aux.Targets(sidecar, 'P'))
    parent = runner.runs.create_run(paths=paths, run_id=RUN_ID, kind='bigmhc_stability_auxiliary', seed=42,
        config=config_path, inputs=[i['path'] for i in inputs] + [paths.project_runs_dir / baseline.REFERENCE['relative_path']],
        argv=['bigmhc_auxiliary_experiment'],
        description='Task 2.20 fixed S/P auxiliary supervision, reused Task 2.17 A')
    write = lambda relative, doc: runner.raw.write_report(parent / relative, doc, paths=paths)
    write('reports/input_preflight.json', preflight)
    write('reports/target_permutation.json', target_proof)
    write('reports/synthetic_cuda_gate.json', gate)
    runner.raw.write_text_report(parent / 'logs/pretraining_tests.log', tests, paths=paths)
    write('reports/baseline_compatibility.json', {'execution_commit': runner.readers._json(parent / 'manifest.json')['git']['commit_sha'],
          'source_sha256': source_identity(paths), 'historical': preflight['historical'], 'reference': baseline.REFERENCE,
          'no_auxiliary_effect_equivalence': gate, 'baseline_retraining_required': False})
    a_directory = paths.project_runs_dir / baseline.BASELINE_RUN
    metrics = {'A': runner.readers._json(a_directory / 'reports/development_metrics.json')}
    completed = []
    try:
        for mode in ('S', 'P'):
            arm_config = deepcopy(config)
            arm_config['condition'] = mode
            cp = parent / f'reports/configuration_{mode}.json'
            write(f'reports/configuration_{mode}.json', arm_config)
            arm = parent / mode
            arm.mkdir()
            for name in runner.runs.RUN_SUBDIRECTORIES:
                (arm / name).mkdir()
            manifest = runner.runs.build_manifest(paths=paths, run_id=mode, kind='bigmhc_stability_auxiliary_arm', seed=42,
                config=cp, inputs=[i['path'] for i in inputs] + [parent / 'reports/baseline_compatibility.json'],
                argv=['bigmhc_auxiliary_experiment', mode], description=f'Task 2.20 {mode}; original BCE plus auxiliary MSE')
            runner.raw.write_report(arm / 'manifest.json', manifest, paths=paths)
            bounded_worker(cp, arm, paths)
            from .bigmhc_abp_experiment import verify_artifacts
            write(f'reports/verification_{mode}.json', verify_artifacts(arm))
            metrics[mode] = runner.readers._json(arm / 'reports/development_metrics.json')
            completed.append(mode)
        result = {'status': 'completed', 'A_reused_from': baseline.BASELINE_RUN, 'metrics': metrics,
                  'paired_differences': contrasts(metrics), 'exploratory_evaluation_number': 3, 'sealed_tests_opened': []}
        write('reports/asp_results.json', result)
        return result
    except Exception as error:
        write('reports/experiment_blocker.json', {'status': 'stopped', 'reason': repr(error), 'completed_arms': completed})
        raise
    finally:
        write('reports/output_manifest.json', {'sha256': {str(p.relative_to(parent)): runner.raw.sha256_file(p)
              for p in sorted(parent.rglob('*')) if p.is_file()}})


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('synthetic', 'run'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--gate-report', type=Path)
    parser.add_argument('--test-log', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--out', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    paths = resolve_paths()
    cp = (args.config or paths.repository_root / CONFIG).absolute()
    if args.worker:
        if args.out is None:
            parser.error('--worker requires --out')
        worker(cp, args.out.absolute(), paths)
    elif args.action == 'synthetic':
        if args.report is None:
            parser.error('synthetic requires --report under resolved project runs storage')
        # Tests load only pinned source + synthetic data, never scientific CSVs.
        import unittest
        import importlib.util
        spec = importlib.util.spec_from_file_location('auxiliary_tests', paths.repository_root / 'tests/test_bigmhc_stability_auxiliary.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.TEST_DEVICE = args.device
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        historical = module.HISTORICAL_A_COMPATIBILITY
        passed = (result.wasSuccessful() and not result.skipped and result.testsRun >= 12
                  and (args.device == 'cpu' or historical.get('reuse_compatible') is True))
        report = {'status': 'passed' if passed else 'failed',
                  'device': 'cuda:0' if args.device == 'cuda' else 'cpu', 'tests': result.testsRun,
                  'skipped': len(result.skipped), 'source_sha256': source_identity(paths),
                  'historical_A_numeric_compatibility': historical}
        runner.raw.write_report(args.report, report, paths=paths)
        if report['status'] != 'passed':
            raise SystemExit(1)
    elif args.action == 'run':
        if args.gate_report is None or args.test_log is None:
            parser.error('run requires --gate-report and --test-log')
        execute(cp, args.gate_report, args.test_log, paths)
    else:
        parser.error('choose synthetic or run')


if __name__ == '__main__':
    main()
