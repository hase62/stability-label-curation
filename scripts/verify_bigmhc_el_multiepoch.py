"""Read-only focused verification of Task 2.23 execution evidence.

Only this experiment's outputs are read; no new model evaluation is performed.
"""
from __future__ import annotations

import csv
import json

from stability_label_curation import bigmhc_el_multiepoch as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths


def main() -> None:
    directory = resolve_paths().project_runs_dir / experiment.RUN_ID
    read = lambda name: json.loads((directory / name).read_text())
    completion = read('reports/completion.json')
    if completion['status'] != 'completed' or completion['EL_epochs'] != 10:
        raise ValueError('Incomplete bounded run')
    manifest = read('reports/output_manifest.json')
    for name, checksum in manifest.items():
        if runner.raw.sha256_file(directory / name) != checksum:
            raise ValueError('Changed output: '+name)
    proof = read('reports/preflight.json')
    for name, checksum in proof['immutable_artifacts'].items():
        if runner.raw.sha256_file(directory / name) != checksum:
            raise ValueError('Changed frozen split: '+name)
    selection = read('reports/EL_epoch_selection.json')
    curve = read('reports/EL_learning_curve.json')['epochs']
    if [r['epoch'] for r in curve] != list(range(1,11)) or experiment.choose_epoch(curve) != selection['selected_epoch']:
        raise ValueError('EL selection/curve failure')
    for row in curve:
        with (directory / f"predictions/EL_epoch_{row['epoch']:02d}.csv").open(newline='') as stream:
            predictions = list(csv.DictReader(stream))
        original = [{'hla':r['HLA'], 'original_label':r['original_label']} for r in predictions]
        recomputed = experiment.el_metrics(original, [float(r['probability']) for r in predictions])
        if any(row[k] != v for k,v in recomputed.items()):
            raise ValueError('Saved EL metric disagreement')
    comparison = read('reports/IM_comparison.json')
    selected = selection['selected_epoch']
    all_stages = ['EL', *[f'IM_from_EL_{e:02d}' for e in dict.fromkeys((1, selected))], 'final_all_IM']
    for stage in all_stages:
        epochs = 10 if stage == 'EL' else 20
        prior = None
        cumulative = 0
        for epoch in range(1, epochs+1):
            report = read(f'reports/{stage}_epoch_{epoch:02d}.json')
            if prior is not None and prior != report['RNG_before']:
                raise ValueError('Scientific RNG disturbed between epochs')
            prior = report['RNG_after']
            cumulative += report['optimization_steps']
            if any(n != cumulative for n in report['optimizer_state_steps']):
                raise ValueError('Optimizer persistence failure')
    if selected != 1:
        for epoch in range(1,21):
            first = read(f'reports/IM_from_EL_01_epoch_{epoch:02d}.json')
            chosen = read(f'reports/IM_from_EL_{selected:02d}_epoch_{epoch:02d}.json')
            for key in ('sampled_batch_sha256','optimizer_skip_mask','RNG_before','RNG_after'):
                if first[key] != chosen[key]:
                    raise ValueError('Unmatched IM schedules')
    for epoch, result in comparison['results'].items():
        with (directory / f'predictions/IM_from_EL_{int(epoch):02d}_epoch_20.csv').open(newline='') as stream:
            predictions = list(csv.DictReader(stream))
        recomputed = runner.development_metrics([int(r['original_label']) for r in predictions], [float(r['probability']) for r in predictions])
        if (len(predictions) != 686 or result['metrics']['validation_AP'] != recomputed['AUPRC']
                or result['metrics']['validation_AUROC'] != recomputed['AUROC']):
            raise ValueError('IM metric/population mismatch')
    final = read('reports/final_checkpoint.json')
    keys = [name.split('_',1)[1][:-4] for name in sorted(final['files'], key=lambda name: int(name.split('_',1)[0]))]
    if runner.checkpoint_identity(directory/final['checkpoint'], keys) != final['files']:
        raise ValueError('Final complete checkpoint file identity mismatch')
    if not final['strict_reload_identical'] or final['prediction_reload']['maximum_absolute_difference'] != 0:
        raise ValueError('Final reload failed')
    print(json.dumps({'status':'passed', 'verified_outputs':len(manifest), 'EL_epochs':10, 'IM_stages':len(all_stages)-1,
                      'selected_EL_epoch':selected, 'all_saved_EL_and_IM_AP_AUROC_recomputed':True,
                      'RNG_continuity_and_matched_schedules':True, 'sealed_test_accessed':False}, indent=2))


if __name__ == '__main__':
    main()
