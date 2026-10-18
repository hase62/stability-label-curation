"""Narrow Task 2.19 exception for the authenticated Task 2.17 unit-weight A."""
import ast
import inspect
from pathlib import Path
import subprocess

from . import bigmhc_baseline_runner as runner
from . import el_stability_loss_adapter as weights

BASELINE_COMMIT = '02313b20da218dbcacdbb2cbee5f5d435b258a18'
PROTOCOL_COMMIT = 'a7a41ea179233088cfae1d8d91826ef9527ce6d0'
BASELINE_RUN = 'task-2_17-abp-comparison/A'
REFERENCE = {'area': 'runs', 'relative_path': BASELINE_RUN + '/reports/matched_state.json',
             'sha256': 'bfcbdc71c98c732650214c7592e396e526094596329bd0e5aa016aa9823c5cb2'}
SCIENTIFIC_IDENTITY = 'fcc1d7b396d7ac4cecf47b2d123f8ec549074b3defb63fee0ffd79dfa4c416c1'

# These exact I/O/metadata substitutions are the only reviewed worker changes.
# Model construction, optimizer, epoch calls, checkpoints and evaluation stay byte-identical.
WORKER_SUBSTITUTIONS = (
 ("    adapted=config.get('loss_adapter') is not None\n", "    adapted=config.get('loss_adapter') is not None\n    reuse_inputs=adapted and config['loss_adapter']['protocol_version']=='el_low_stability_positive_v1'\n"),
 ("        raw.write_text_report(directory/f'processed/{stage.lower()}_original_smoke.csv',csv_text(selected[stage]),paths=paths)", "        if not reuse_inputs:\n            raw.write_text_report(directory/f'processed/{stage.lower()}_original_smoke.csv',csv_text(selected[stage]),paths=paths)"),
 ("        if config['version'] in (FULL_VERSION,WEIGHTED_VERSION):", "        if reuse_inputs:\n            subset_info[stage].pop('rows')\n            subset_info[stage]['existing_provenance_input']=config['inputs'][stage+'_provenance']\n        elif config['version'] in (FULL_VERSION,WEIGHTED_VERSION):"),
 ("        if matched_reference is not None and any(matched[k]!=matched_reference[k] for k in matched):\n            raise ValueError('Matched A code, runtime, device or configuration differs')", "        from .bigmhc_baseline_compatibility import check_metadata\n        compatibility=check_metadata(matched,matched_reference,config,paths)\n        if compatibility is not None:\n            raw.write_report(directory/'reports/baseline_compatibility.json',compatibility,paths=paths)"),
 ("            native=dataset(directory/f'processed/{stage.lower()}_original_smoke.csv')", "            native=dataset(resolved[stage] if reuse_inputs else directory/f'processed/{stage.lower()}_original_smoke.csv')"),
 ("            return weighting.IdentityDataset(native,weighting.manifest_rows(directory/f'processed/{stage.lower()}_original_row_manifest.csv.gz'),", "            records=(r for r in weighting.manifest_rows(resolved[stage+'_provenance']) if r['retained']=='1') if reuse_inputs else weighting.manifest_rows(directory/f'processed/{stage.lower()}_original_row_manifest.csv.gz')\n            return weighting.IdentityDataset(native,records,"),
)


def source_contract(paths) -> dict:
    """Check local committed historical source; no network or artifact scans."""
    unchanged = {
        'bigmhc_baseline_runner.py': ('train_epoch', 'seed_runtime', 'runtime_device',
            'pinned_modules', 'input_rows', 'attach_provenance', 'select_subset',
            'predict', 'load_checkpoint', 'save_checkpoint', 'prediction_agreement',
            'verify_parent', 'state_hashes', 'development_metrics'),
        'el_stability_loss_adapter.py': ('IdentityDataset', 'weighted_bce', 'rng_identity',
            'original_fields', 'row_binding', 'check_reference', 'matched_config_identity'),
    }
    evidence = {}
    for filename, names in unchanged.items():
        relative = 'src/stability_label_curation/' + filename
        old = subprocess.run(['git', 'show', BASELINE_COMMIT + ':' + relative],
            cwd=paths.repository_root, check=True, capture_output=True, text=True).stdout
        current = (paths.repository_root / relative).read_text()
        old_nodes = {n.name: n for n in ast.parse(old).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        new_nodes = {n.name: n for n in ast.parse(current).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        for name in names:
            before, after = ast.dump(old_nodes[name], include_attributes=False), ast.dump(new_nodes[name], include_attributes=False)
            if before != after:
                raise ValueError('Baseline scientific source changed: ' + filename + '/' + name)
            evidence[filename + ':' + name] = weights.digest(after)
        if filename == 'bigmhc_baseline_runner.py':
            expected = ast.get_source_segment(old, old_nodes['worker'])
            for before, after in WORKER_SUBSTITUTIONS:
                if expected.count(before) != 1:
                    raise ValueError('Reviewed worker substitution no longer unique')
                expected = expected.replace(before, after)
            if ast.dump(ast.parse(expected), include_attributes=False) != ast.dump(
                    ast.parse(inspect.getsource(runner.worker)), include_attributes=False):
                raise ValueError('Worker differs beyond reviewed I/O and metadata substitutions')
    return {'unchanged_scientific_AST_sha256': evidence, 'worker_reviewed_substitutions': len(WORKER_SUBSTITUTIONS),
            'current_source_sha256': {p.name: runner.raw.sha256_file(p) for p in
                (Path(runner.__file__), Path(weights.__file__), Path(__file__))}}


def validate_spec(config: dict) -> None:
    spec = config.get('baseline_reuse', {})
    if (config['loss_adapter']['protocol_version'] != weights.LOW_PROTOCOL or
            spec.get('commit') != BASELINE_COMMIT or spec.get('protocol_commit') != PROTOCOL_COMMIT or
            spec.get('reference') != REFERENCE or weights.matched_config_identity(config) != SCIENTIFIC_IDENTITY):
        raise ValueError('Baseline reuse is limited to the approved Task 2.19 scientific configuration')


def baseline_evidence(config: dict, paths) -> dict:
    from . import bigmhc_abp_experiment as experiment
    validate_spec(config)
    source = source_contract(paths)
    directory = paths.project_runs_dir / BASELINE_RUN
    if runner.raw.sha256_file(directory / 'reports/matched_state.json') != REFERENCE['sha256']:
        raise ValueError('Pinned baseline matched-state changed')
    manifest = runner.readers._json(directory / 'manifest.json')
    receipt = runner.readers._json(directory / 'reports/execution_verification.json')
    saved = runner.readers._json(directory / 'reports/training_configuration.json')
    matched = runner.readers._json(directory / 'reports/matched_state.json')
    if (manifest['git']['commit_sha'] != BASELINE_COMMIT or receipt['code_commit'] != BASELINE_COMMIT or
            matched['code_commit'] != BASELINE_COMMIT or saved['condition'] != 'A' or
            saved['loss_adapter']['mode'] != 'A' or
            weights.matched_config_identity(saved) != SCIENTIFIC_IDENTITY or
            matched['configuration_identity'] != SCIENTIFIC_IDENTITY):
        raise ValueError('Historical A lineage/configuration mismatch')
    verification = experiment.verify_artifacts(directory)
    initial = runner.readers._json(directory / 'reports/initial_el_state_identity.json')
    if len(initial) != 36 or initial != matched['initial_tensor_sha256']:
        raise ValueError('Historical A initial 36 tensors mismatch')
    for stage, steps, batches in (('EL', 70069, 70069), ('IM', 214, 215)):
        if matched[stage]['optimization_steps'] != steps or len(matched[stage]['sampled_batch_sha256']) != batches:
            raise ValueError('Historical A step/exposure mismatch')
    return {'status': 'verified', 'baseline_reused': True, 'baseline_run': BASELINE_RUN,
            'baseline_commit': BASELINE_COMMIT, 'reference': REFERENCE,
            'scientific_configuration_identity': SCIENTIFIC_IDENTITY,
            'initial_36_tensor_digest': weights.digest(initial), 'artifact_verification': verification,
            'source_contract': source, 'baseline_versions': matched['versions']}


def check_metadata(current: dict, reference: dict | None, config: dict, paths) -> dict | None:
    """Keep strict historical matching except one receipt-bound code_commit field."""
    if reference is None:
        return None
    if config['loss_adapter']['protocol_version'] != weights.LOW_PROTOCOL:
        if any(current[k] != reference[k] for k in current):
            raise ValueError('Matched A code, runtime, device or configuration differs')
        return None
    validate_spec(config)
    if config['loss_adapter']['matched_reference'] != REFERENCE or reference['code_commit'] != BASELINE_COMMIT:
        raise ValueError('Unreviewed historical baseline reference')
    if any(current[k] != reference[k] for k in current if k != 'code_commit'):
        raise ValueError('Matched A runtime, device or scientific configuration differs')
    spec = config['baseline_reuse']['compatibility_report']
    if not isinstance(spec, dict) or spec.get('area') != 'runs':
        raise ValueError('Missing reviewed baseline compatibility receipt')
    runner.adapter.pilot.registry._relative(spec['relative_path'])
    path = paths.project_runs_dir / spec['relative_path']
    if (spec['relative_path'] != 'task-2_19-low-stability-alp-gpu/reports/baseline_compatibility.json' or
            runner.raw.sha256_file(path) != spec['sha256']):
        raise ValueError('Baseline compatibility receipt binding mismatch')
    proof = runner.readers._json(path)
    if (proof['status'] != 'verified' or proof['baseline_commit'] != BASELINE_COMMIT or
            proof['reference'] != REFERENCE or proof['execution_commit'] != current['code_commit'] or
            proof['source_contract'] != source_contract(paths) or not proof['CUDA_unit_weight_equivalence']):
        raise ValueError('Baseline compatibility proof does not authenticate this execution')
    return proof
