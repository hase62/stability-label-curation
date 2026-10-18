"""One exclusive, bounded preregistered A/B/P execution; no tuning or retries."""
from collections import defaultdict
from copy import deepcopy
import csv
import json
import hashlib
from pathlib import Path
import time

from . import bigmhc_baseline_runner as runner
from . import bigmhc_gpu_worker as gpu
from . import el_stability_loss_adapter as weights
from .paths import StoragePaths, resolve_paths

RUN_ID = 'task-2_17-abp-comparison'
LEGACY_RUN_ID = 'task-2_14b-abp-gpu-experiment'
STARTING_MAIN = '2ae58c234924c602863e470dd6873f14f45d0cfb'
CONFIG = 'configs/bigmhc_abp_task2_14b.json'
HISTORICAL = 'task-2_10-full-eligible-baseline-a'
COMMON_FIELDS = ('seed', 'epochs', 'batch_size', 'learning_rate', 'device', 'cpu_threads',
                 'num_workers', 'persistent_workers', 'label_policy', 'rows_per_class',
                 'expected_rows', 'expected_class_counts', 'source_commit')


def arm_run(out: str | Path, paths: StoragePaths, config: dict) -> tuple[Path, dict]:
    """Authenticate nested arm evidence; retain existing standalone adapter runs."""
    directory = Path(out).absolute()
    if directory.parent == paths.project_runs_dir:
        return runner.teacher._run(directory, paths)
    if (directory.parent.parent != paths.project_runs_dir
            or not any(directory.parent.name == prefix or directory.parent.name.startswith(prefix + '-')
                       for prefix in (RUN_ID, LEGACY_RUN_ID))
            or directory.name != config['condition'] or directory.name not in {'A', 'B', 'P'}):
        raise ValueError('Unexpected matched arm output directory')
    _, parent = runner.teacher._run(directory.parent, paths)
    if parent['run_kind'] != 'bigmhc_matched_abp_experiment':
        raise ValueError('Unexpected matched experiment manifest')
    manifest = runner.runs.validate_manifest(runner.readers._json(directory / 'manifest.json'))
    if manifest['git'] != parent['git'] or manifest['run_id'] != directory.name:
        raise ValueError('Matched arm committed lineage differs from experiment')
    return directory, manifest


def arm_configuration(base: dict, mode: str, reference: dict | None = None) -> dict:
    result = deepcopy(base)
    result['condition'] = result['loss_adapter']['mode'] = mode
    result['loss_adapter']['matched_reference'] = reference
    weights.validate_runtime_spec(result['loss_adapter'], mode)
    return result


def verify_artifacts(directory: Path) -> dict:
    """Verify all worker-authenticated bytes, checkpoint lineage and saved scores."""
    read = runner.readers._json
    receipt = read(directory / 'reports/execution_verification.json')
    resource = read(directory / 'reports/resource_execution.json')
    if resource['status'] != 'completed' or not receipt['reload_predictions_consistent']:
        raise ValueError('Worker or checkpoint reload failed')
    for relative, expected in receipt['outputs'].items():
        runner.adapter.pilot.registry._relative(relative)
        if runner.raw.sha256_file(directory / relative) != expected:
            raise ValueError('Saved output hash mismatch: ' + relative)
    metrics = read(directory / 'reports/development_metrics.json')
    for name, filename in (('IM', 'im'), ('EL_proxy', 'el')):
        rows = prediction_rows(directory, filename)
        actual = runner.development_metrics([int(r['original_label']) for r in rows],
                                            [float(r['probability']) for r in rows])
        if len(rows) != 383 or actual != metrics[name]:
            raise ValueError('Saved prediction/metric inconsistency')
    lineage = read(directory / 'reports/checkpoint_lineage.json')
    if not lineage['EL_reload_identical'] or not lineage['IM_reload_identical']:
        raise ValueError('Checkpoint tensors changed after reload')
    runner.verify_parent(directory / 'checkpoints/el', directory / 'checkpoints/el/im', lineage)
    runner.runs.validate_manifest(read(directory / 'manifest.json'))
    return {'worker_outputs_verified': len(receipt['outputs']), 'metrics_recomputed': True,
            'checkpoint_reload_verified': True}


def prediction_rows(directory: Path, stage: str) -> list[dict]:
    with (directory / f'predictions/{stage}_development.csv').open(newline='') as stream:
        return list(csv.DictReader(stream))


def training_report(directory: Path) -> dict:
    """Bounded exception for receipt-authenticated internal training summaries.

    The complete step trajectory is required by compare_historical. A compact
    summary cannot implement that gate; a streaming JSON parser would add a new
    parser/dependency. Keep the generic evidence reader's 8 MiB bound intact.
    """
    receipt = runner.readers._json(directory / 'reports/execution_verification.json')
    expected = receipt['outputs']['reports/training_summary.json']
    if not runner.adapter.pilot._sha(expected):
        raise ValueError('Invalid training report receipt hash')
    with runner.raw._read_file(directory / 'reports/training_summary.json') as stream:
        content = stream.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024:
        raise ValueError('Internal training report 32 MiB bound exceeded')
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError('Internal training report receipt SHA256 mismatch')
    result = json.loads(content, object_pairs_hook=runner.readers.dtu._unique_json,
                        parse_constant=runner.readers._nonfinite_json)
    if not isinstance(result, dict) or not all(k in result for k in ('architecture', 'EL', 'IM')):
        raise ValueError('Malformed internal training report')
    return result


def compare_historical(current: Path, historical: Path) -> dict:
    """Gate B/P on unchanged scientific configuration, exposures and A trajectory.

    Before inspecting A, bound FP32 reduction differences by rtol=1e-5,
    atol=1e-7 for step losses and rtol=1e-5, atol=1e-6 for probabilities.
    Larger differences require investigation and stop this launcher.
    """
    read = runner.readers._json
    old = read(historical / 'reports/training_configuration.json')
    new = read(current / 'reports/training_configuration.json')
    if any(old[k] != new[k] for k in COMMON_FIELDS):
        raise ValueError('Historical A scientific configuration mismatch')
    if any(new['inputs'][k] != spec for k, spec in old['inputs'].items()):
        raise ValueError('Historical A input population differs')
    for filename in ('initial_el_state_identity.json',):
        if read(current / 'reports' / filename) != read(historical / 'reports' / filename):
            raise ValueError('Historical A initial tensors differ')
    a = training_report(current)
    h = training_report(historical)
    if a['architecture'] != h['architecture']:
        raise ValueError('Historical A architecture differs')
    result = {'initial_tensors_identical': True, 'scientific_configuration_identical': True,
              'loss_tolerance': {'rtol': 1e-5, 'atol': 1e-7},
              'probability_tolerance': {'rtol': 1e-5, 'atol': 1e-6}}
    for stage in ('EL', 'IM'):
        for key in ('optimization_steps', 'batches', 'optimizer_class_exposures', 'sampled_class_exposures',
                    'optimizer_defaults', 'updated_parameters', 'skipped_batch_log', 'sampling'):
            if a[stage][key] != h[stage][key]:
                raise ValueError('Historical A sampling/optimizer mismatch: ' + stage + '/' + key)
        differences = []
        for x, y in zip(a[stage]['step_log'], h[stage]['step_log'], strict=True):
            if any(x[k] != y[k] for k in ('batch', 'rows', 'positives')):
                raise ValueError('Historical A batch exposure differs')
            delta = abs(x['BCE_loss'] - y['BCE_loss'])
            if delta > 1e-7 + 1e-5 * abs(y['BCE_loss']):
                raise ValueError('Historical A loss trajectory differs beyond FP32 tolerance')
            differences.append(delta)
        result[stage + '_loss_maximum_absolute_difference'] = max(differences)
    for stage in ('el', 'im'):
        maximum = 0.0
        for x, y in zip(prediction_rows(current, stage), prediction_rows(historical, stage), strict=True):
            if {k: v for k, v in x.items() if k != 'probability'} != {k: v for k, v in y.items() if k != 'probability'}:
                raise ValueError('Historical development cohort differs')
            delta = abs(float(x['probability']) - float(y['probability']))
            if delta > 1e-6 + 1e-5 * abs(float(y['probability'])):
                raise ValueError('Historical A predictions differ beyond FP32 tolerance')
            maximum = max(maximum, delta)
        result[stage + '_prediction_maximum_absolute_difference'] = maximum
    return result


def metric_contrasts(metrics: dict) -> dict:
    return {contrast: {stage: {metric: metrics[left][stage][metric] - metrics[right][stage][metric]
                              for metric in ('AUPRC', 'AUROC')}
                       for stage in ('IM', 'EL_proxy')}
            for contrast, left, right in (('B-A', 'B', 'A'), ('B-P', 'B', 'P'), ('P-A', 'P', 'A'))}


def per_hla_metrics(directory: Path) -> dict:
    result = {}
    for stage in ('el', 'im'):
        groups = defaultdict(list)
        for row in prediction_rows(directory, stage):
            groups[row['resolved_hla']].append(row)
        result[stage] = {}
        for hla, rows in sorted(groups.items()):
            labels = [int(row['original_label']) for row in rows]
            positive = sum(labels)
            item = {'n': len(rows), 'positives': positive, 'negatives': len(rows) - positive,
                    'prevalence': positive / len(rows)}
            if min(positive, len(rows) - positive) >= 5:
                item['metrics'] = runner.development_metrics(labels, [float(row['probability']) for row in rows])
            else:
                item.update(metrics=None, reason='Fewer than five positives or five negatives')
            result[stage][hla] = item
    return result


def execute(*, noop_report: Path, test_log: Path, paths: StoragePaths | None = None, run_id: str = RUN_ID) -> dict:
    paths = paths or resolve_paths()
    config_path = paths.repository_root / CONFIG
    base = runner.load_config(config_path)
    runner.runs.validate_run_id(run_id)
    if not any(run_id == prefix or run_id.startswith(prefix + '-') for prefix in (RUN_ID, LEGACY_RUN_ID)):
        raise ValueError('Matched experiment run ID must use an approved Task 2.14B/2.17 prefix')
    runner.cuda_visibility()
    noop = runner.readers._json(noop_report)
    required = ('loss_exactly_equal', 'gradients_exactly_equal', 'AdamW_updates_identical',
                'native_encoded_tensors_and_labels_identical', 'model_sampler_RNG_states_identical',
                'source_row_identity_collation_verified')
    if (noop['device'] != 'cuda:0' or any(noop[k] is not True for k in required)
            or noop['gradient_maximum_absolute_difference'] != 0):
        raise ValueError('CUDA no-op gate failed; full training prohibited')
    if (noop['adapter_source_sha256'] != runner.raw.sha256_file(Path(weights.__file__))
            or noop['runner_source_sha256'] != runner.raw.sha256_file(Path(runner.__file__))):
        raise ValueError('CUDA no-op evidence belongs to different source bytes')
    tests = test_log.read_text()
    if '\nOK' not in tests or '\nFAILED' in tests:
        raise ValueError('Full test suite must pass before training')
    from .bigmhc_abp_preflight import validate
    preflight = validate(config_path=config_path, paths=paths)
    verification = preflight['input_verification']
    files, inputs = runner.resolve_inputs(base, paths)
    sidecar = weights.runtime_adapter(base, files)
    historical = paths.project_runs_dir / HISTORICAL
    historical_verification = verify_artifacts(historical)
    parent = runner.runs.create_run(paths=paths, run_id=run_id, kind='bigmhc_matched_abp_experiment',
        seed=42, config=config_path, inputs=[item['path'] for item in inputs],
        argv=['bigmhc_abp_experiment'], description='Task 2.17; fresh single-seed A/B/P; frozen development only')
    def write(path: Path, value: dict) -> None:
        runner.raw.write_report(path, value, paths=paths)
    write(parent / 'reports/cuda_noop_equivalence.json', noop)
    runner.raw.write_text_report(parent / 'logs/pretraining_tests.log', tests, paths=paths)
    write(parent / 'reports/input_preflight.json', {'verification': verification,
        'full_cohort_preflight': preflight,
        'sidecar': sidecar.evidence, 'historical_artifacts': historical_verification,
        'starting_GitHub_main': STARTING_MAIN})
    metrics, evidence, reference = {}, {}, None
    started = time.monotonic()
    try:
        for mode in ('A', 'B', 'P'):
            remaining = 10800 - (time.monotonic() - started)
            if remaining < 60:
                raise RuntimeError('Total GPU experiment budget exhausted')
            config = arm_configuration(base, mode, reference)
            config['wall_seconds'] = min(base['wall_seconds'], int(remaining))
            cp = parent / 'reports' / f'configuration_{mode}.json'
            write(cp, config)
            resolved, identities = runner.resolve_inputs(config, paths)
            manifest = runner.runs.build_manifest(paths=paths, run_id=mode, kind='bigmhc_matched_arm',
                seed=42, config=cp, inputs=[item['path'] for item in identities],
                argv=['bigmhc_abp_experiment', mode], description=f'Task 2.17 mode {mode}; original labels')
            arm = parent / mode
            arm.mkdir()
            for name in runner.runs.RUN_SUBDIRECTORIES:
                (arm / name).mkdir()
            write(arm / 'manifest.json', manifest)
            print(f'Starting arm {mode}; remaining total budget {remaining:.0f}s', flush=True)
            runner.run(config_path=cp, out=arm, paths=paths)
            evidence[mode] = verify_artifacts(arm)
            matched = runner.readers._json(arm / 'reports/matched_state.json')
            fingerprints = {
                'initial_36_tensor_digest': weights.digest(matched['initial_tensor_sha256']),
                'sequence_definition': 'SHA256 of ordered native batch source-ID/original-label digests; batch boundaries retained',
                'stages': {stage: {
                    'ordered_exposure_digest': weights.digest(matched[stage]['sampled_batch_sha256']),
                    'batches': len(matched[stage]['sampled_batch_sha256']),
                    'optimizer_steps': matched[stage]['optimization_steps'],
                    'skip_mask_digest': weights.digest(matched[stage]['optimizer_skip_mask']),
                    'RNG_boundary': matched['rng_before_' + stage]}
                    for stage in ('EL', 'IM')}}
            write(arm / 'reports/exposure_fingerprints.json', fingerprints)
            write(arm / 'reports/per_HLA_development_metrics.json', per_hla_metrics(arm))
            metrics[mode] = runner.readers._json(arm / 'reports/development_metrics.json')
            if mode == 'A':
                comparison = compare_historical(arm, historical)
                write(parent / 'reports/matched_A_vs_task2_10.json', comparison)
                relative = f'{run_id}/A/reports/matched_state.json'
                reference = {'area': 'runs', 'relative_path': relative,
                             'sha256': runner.raw.sha256_file(paths.project_runs_dir / relative)}
            print(f'Completed arm {mode}; saved artifacts verified', flush=True)
        result = {'status': 'completed', 'metrics': metrics, 'paired_differences': metric_contrasts(metrics),
                  'artifact_verification': evidence, 'elapsed_seconds': time.monotonic() - started,
                  'total_budget_seconds': 10800, 'sealed_tests_opened': [],
                  'interpretation': 'One exploratory seed and one fixed permutation; no significance or label-error inference'}
        write(parent / 'reports/abp_results.json', result)
    except Exception as error:
        write(parent / 'reports/experiment_blocker.json', {'status': 'stopped', 'error': repr(error),
              'completed_arms': list(metrics), 'elapsed_seconds': time.monotonic() - started})
        raise
    finally:
        outputs = {str(p.relative_to(parent)): runner.raw.sha256_file(p)
                   for p in sorted(parent.rglob('*')) if p.is_file()}
        write(parent / 'reports/output_manifest.json', {'sha256': outputs})
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--noop-report', type=Path)
    parser.add_argument('--test-log', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--preflight-report', type=Path)
    parser.add_argument('--config', type=Path, default=Path(CONFIG))
    parser.add_argument('--run-id', default=RUN_ID, help='Use a fresh suffixed ID for any separately authorized retry')
    args = parser.parse_args()
    if args.preflight_only:
        if args.preflight_report is None:
            parser.error('--preflight-only requires --preflight-report')
        from .bigmhc_abp_preflight import record
        result = record(config_path=args.config, report=args.preflight_report)
    else:
        if args.noop_report is None or args.test_log is None:
            parser.error('training requires --noop-report and --test-log')
        result = execute(noop_report=args.noop_report, test_log=args.test_log, run_id=args.run_id)
    print(json.dumps(result, indent=2))
