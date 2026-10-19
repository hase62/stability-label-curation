"""Authenticate saved Task 2.24 training evidence; no model or benchmark scoring."""
from __future__ import annotations

import json
import math

from stability_label_curation import bigmhc_fully_trained_auxiliary as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import el_stability_loss_adapter as binding
from stability_label_curation.paths import resolve_paths


def verify() -> dict:
    paths = resolve_paths()
    directory = paths.project_runs_dir/experiment.RUN_ID
    read = lambda name: json.loads((directory/name).read_text())
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)
    config = experiment.read_config(paths)
    base, _ = experiment.baseline_evidence(paths, config)
    frozen = read('reports/frozen_models.json')
    require(frozen['status'] == 'frozen' and not frozen['sealed_benchmark_accessed'], 'Incomplete/invalid freeze')
    require(frozen['scientific_hashes'] == experiment.scientific_hashes(paths), 'Scientific code/protocol changed')
    require(frozen['protocol_sha256'] == runner.raw.sha256_file(paths.repository_root/experiment.PROTOCOL), 'Protocol changed')
    manifest = read('reports/output_manifest.json')
    for name, digest in manifest.items():
        require(runner.raw.sha256_file(directory/name) == digest, 'Changed output: '+name)
    preflight = read('reports/preflight.json')
    for name, digest in preflight['immutable_artifacts'].items():
        require(runner.raw.sha256_file(directory/name) == digest, 'Changed preflight evidence: '+name)
    require(preflight['scientific_hashes'] == frozen['scientific_hashes'], 'Preflight/source mismatch')
    gate = read('reports/focused_tests.json')
    require(gate['status'] == 'passed' and gate['skipped'] == 0 and gate['device'] == 'cuda:0', 'CUDA tests failed')
    require(gate['log_sha256'] == runner.raw.sha256_file(directory/'logs/focused_tests.log'), 'Test log changed')
    require(gate['scientific_hashes'] == frozen['scientific_hashes'], 'Tests/source mismatch')
    cohort = read('reports/cohort_binding.json')
    require(cohort == preflight['cohort'] and cohort['training_classes'] == {'0': 1245143, '1': 63053}, 'Cohort changed')
    permutation = read('reports/target_permutation.json')
    require(permutation['same_source_identities'] and permutation['per_HLA_exact_and_FP32_multisets_equal'], 'Target invariants failed')
    require(permutation['S']['positive_observations'] == permutation['P']['positive_observations'] == 63053, 'Target count changed')
    for hla, s in permutation['S']['by_HLA'].items():
        p = permutation['P']['by_HLA'][hla]
        for key in ('n', 'exact_multiset_sha256', 'FP32_multiset_sha256', 'mean_exact'):
            require(s[key] == p[key], 'Per-HLA multiset changed')
        require(s['mean_exact'] == '1/2', 'HLA mean changed')
    init = read('reports/initialization.json')
    require(init['S_head'] == init['P_head'] and init['head_parameters'] == 415, 'Head initialization changed')
    a_initial = json.loads((base/'reports/initial_EL_state.json').read_text())
    require(init['backbone'] == a_initial, 'Backbone initialization differs from A')
    step_counts, losses = {}, {}
    for mode in ('S', 'P'):
        initialized = read(f'reports/{mode}_initialization.json')
        require(initialized['backbone'] == init['backbone']['state'] and initialized['head'] == init[mode+'_head'], 'Scientific initialization changed')
        require(initialized['RNG'] == init['backbone']['RNG'], 'Head consumed scientific RNG')
        step_counts[mode], losses[mode] = {}, {}
        for stage, epochs in (('EL', 10), ('IM', 20)):
            prior, cumulative, metrics = None, 0, []
            for epoch in range(1, epochs+1):
                r = read(f'reports/{mode}_{stage}_epoch_{epoch:02d}.json')
                a_stage = 'EL' if stage == 'EL' else 'final_all_IM'
                a = json.loads((base/f'reports/{a_stage}_epoch_{epoch:02d}.json').read_text())
                experiment.check_schedule(r, a, r['RNG_before'], r['RNG_after'])
                if prior is not None:
                    require(prior == r['RNG_before'], 'RNG disturbed between epochs')
                prior = r['RNG_after']
                cumulative += r['optimization_steps']
                require(r['cumulative_optimizer_steps'] == cumulative, 'Optimizer counter reset')
                require(r['optimizer_state_steps'] == [cumulative]*(38 if stage == 'EL' else 4), 'Optimizer continuity failed')
                require(len(r['step_log']) == r['optimization_steps'], 'Incomplete loss trajectory')
                require(all(math.isfinite(s['BCE_loss']) for s in r['step_log']), 'Nonfinite BCE')
                row_bce = sum(s['BCE_loss']*s['rows'] for s in r['step_log'])/sum(s['rows'] for s in r['step_log'])
                require(row_bce == r['row_weighted_BCE_loss'], 'Saved native BCE differs')
                metric = read(f'reports/{mode}_{stage}_metrics_{epoch:02d}.json')
                require(metric['native_BCE'] == row_bce and metric['sampling_fingerprint'] == binding.digest(r['sampled_batch_sha256']), 'Metric receipt differs')
                if stage == 'EL':
                    require(all(s['rows'] == 17 and s['positives'] == 1 for s in r['step_log']), 'Native positive anchor changed')
                    mse = sum(s['auxiliary_MSE'] for s in r['step_log'])/len(r['step_log'])
                    require(mse == r['mean_auxiliary_MSE'] == metric['auxiliary_MSE'], 'Saved auxiliary MSE differs')
                    require(all(math.isfinite(s['auxiliary_MSE']) and s['auxiliary_MSE'] >= 0 for s in r['step_log']), 'Invalid auxiliary loss')
                    require(r['lambda_aux'] == .1 and r['BCE_denominator'] == 'all native batch rows', 'Objective changed')
                    require(r['auxiliary_gradient_evidence']['finite_head_gradient_checks'] == 63053, 'Missing scientific gradient checks')
                    require(all(n > 0 and math.isfinite(n) for n in r['auxiliary_gradient_evidence']['first_update_head_gradient_norms'].values()), 'No first head gradient')
                    require(r['optimization_steps'] == 63053 and r['sampled_class_exposures'] == {'1':63053, '0':1008848}, 'EL exposure changed')
                else:
                    require(r['updated_parameters'] == list(runner.TRANSFER), 'IM optimizer includes auxiliary/nontransfer tensors')
                metrics.append(metric)
                other = read(f'reports/{"P" if mode == "S" else "S"}_{stage}_epoch_{epoch:02d}.json')
                for key in ('sampled_batch_sha256', 'optimizer_skip_mask', 'RNG_before', 'RNG_after', 'optimizer_defaults'):
                    require(r[key] == other[key], 'S/P schedules differ')
            require(read(f'reports/{mode}_{stage}_learning_curve.json')['epochs'] == metrics, 'Learning curve differs')
            completed = read(f'reports/{mode}_{stage}_completed.json')
            require(completed['status'] == 'completed' and completed['epochs'] == epochs and completed['optimizer_steps'] == cumulative, 'Incomplete stage')
            checkpoint = frozen['models'][mode]['checkpoints'][stage]
            require(runner.checkpoint_identity(directory/checkpoint['checkpoint'], checkpoint['state_keys']) == checkpoint['files'], 'Checkpoint files changed')
            require(checkpoint['strict_reload_identical'] and checkpoint['prediction_reload']['maximum_absolute_difference'] == 0, 'Reload failed')
            require(checkpoint['probe_is_training_data'] and checkpoint['probe_rows'] == 16, 'Unexpected reload probe')
            if stage == 'EL':
                require(runner.raw.sha256_file(directory/checkpoint['auxiliary_head_file']) == checkpoint['auxiliary_head_sha256'], 'Head checkpoint changed')
                require(checkpoint['auxiliary_head_reload_identical'] and checkpoint['auxiliary_head_state'] != init[mode+'_head'], 'Head not trained/reloaded')
            else:
                parent = frozen['models'][mode]['checkpoints']['EL']
                require(set(completed['changed_parameters']) == set(runner.TRANSFER), 'IM update scope changed')
                require(all(checkpoint['state'][k] == parent['state'][k] for k in checkpoint['state'] if k not in runner.TRANSFER), 'IM parent lineage differs')
                require(read(f'reports/{mode}_IM_checkpoint.json')['parent'] == parent, 'IM parent receipt differs')
            step_counts[mode][stage] = cumulative
            losses[mode][stage] = metrics
    return dict(status='passed', authenticated_scientific_outputs=len(manifest), tests=gate['tests'],
                EL_epochs_per_arm=10, IM_epochs_per_arm=20, optimizer_steps=step_counts,
                all_A_SP_ordered_batches_and_RNG_match=True, all_saved_losses_recomputed=True,
                strict_checkpoint_reload_and_transfer_verified=True, sealed_benchmark_accessed=False,
                protocol_frozen=True, loss_histories=losses)


def main() -> None:
    print(json.dumps(verify(), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
