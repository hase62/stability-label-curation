"""Verify Task 2.22 saved artifacts without training or inference."""
from collections import Counter
import csv
import json
from pathlib import Path

from stability_label_curation import bigmhc_multiepoch as multi
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths


def verify() -> dict:
    paths = resolve_paths()
    directory = paths.project_runs_dir / multi.RUN_ID
    read = lambda name: json.loads((directory / name).read_text())
    manifest = read('reports/output_manifest.json')
    for name, checksum in manifest.items():
        runner.adapter.pilot.registry._relative(name)
        if runner.raw.sha256_file(directory / name) != checksum:
            raise ValueError('Output identity changed: ' + name)
    completion = read('reports/completion.json')
    if completion['status'] != 'completed' or completion['internal_epochs'] != 60:
        raise ValueError('Incomplete scientific execution')
    with (directory / 'processed/split_manifest.csv').open(newline='') as stream:
        observations = list(csv.DictReader(stream))
    expected = {r['source_row_id']: (r['peptide'], r['HLA'], int(r['original_label'])) for r in observations}
    if len(expected) != 3428:
        raise ValueError('Manifest source-row coverage failure')
    left = [r for r in observations if r['partition'] == 'train']
    right = [r for r in observations if r['partition'] == 'validation']
    if ({r['peptide'] for r in left} & {r['peptide'] for r in right}
            or len(left) + len(right) != len(observations)):
        raise ValueError('Saved split overlap/coverage failure')
    learning = read('reports/learning_curve.json')['epochs']
    if [r['epoch'] for r in learning] != list(range(1, 61)):
        raise ValueError('Missing/reordered validation epochs')
    selection = read('reports/candidate_checkpoint_comparison.json')
    selected = multi.choose_epoch(learning)
    exposed = set(read('reports/peptide_EL_overlap.json')['matches'])
    strata = {}
    if selected != selection['selected_epoch'] or selected != completion['selected_epoch']:
        raise ValueError('Saved selection failure')
    for row in learning:
        epoch = row['epoch']
        with (directory / f'predictions/validation_epoch_{epoch:02d}.csv').open(newline='') as stream:
            predictions = list(csv.DictReader(stream))
        for prediction in predictions:
            source = prediction['source_row_id']
            if expected[source] != (prediction['peptide'], prediction['HLA'], int(prediction['original_label'])):
                raise ValueError('Prediction row/label/HLA identity failure')
        if Counter(r['source_row_id'] for r in predictions) != Counter(r['source_row_id'] for r in right):
            raise ValueError('Validation prediction coverage failure')
        metrics = runner.development_metrics([int(r['original_label']) for r in predictions],
                                              [float(r['probability']) for r in predictions])
        if row['validation_AP'] != metrics['AUPRC'] or row['validation_AUROC'] != metrics['AUROC']:
            raise ValueError('Saved metric recomputation failure')
        if epoch == selected:
            for name, exposure in (('EL_exposed_IM_novel', True), ('fully_training_unseen', False)):
                subset = [r for r in predictions if (r['peptide'] in exposed) == exposure]
                labels = [int(r['original_label']) for r in subset]
                values = {'observations': len(subset), 'positives': sum(labels),
                          'unique_peptides': len({r['peptide'] for r in subset})}
                if len(subset) >= 20 and set(labels) == {0, 1}:
                    metric = runner.development_metrics(labels, [float(r['probability']) for r in subset])
                    values.update(AP=metric['AUPRC'], AUROC=metric['AUROC'])
                else:
                    values['metrics'] = 'Not reported: fewer than 20 observations or only one class'
                strata[name] = values
    optimizer_summaries = {}
    for stage, count, part in (('internal', 60, left), ('final', selected, observations)):
        cumulative, skipped, seconds = 0, 0, 0.
        expected_ids = Counter(r['source_row_id'] for r in part)
        defaults = None
        previous_rng = None
        for epoch in range(1, count + 1):
            report = read(f'reports/{stage}_epoch_{epoch:02d}.json')
            if previous_rng is not None and report['RNG_before'] != previous_rng:
                raise ValueError('Evaluation/checkpoint work changed scientific RNG')
            previous_rng = report['RNG_after']
            batches = report['ordered_batches']
            if Counter(s for b in batches for s, _ in b['source_ids_and_labels']) != expected_ids:
                raise ValueError('Native sampled epoch coverage failure')
            hashes, mask = [], []
            for batch in batches:
                pairs = batch['source_ids_and_labels']
                if any(expected[source][2] != label for source, label in pairs):
                    raise ValueError('Sampled original label changed')
                digest = multi.identity.digest(pairs)
                if digest != batch['batch_sha256']:
                    raise ValueError('Batch source fingerprint failure')
                hashes.append(digest)
                mask.append(not any(label for _, label in pairs))
            cumulative += report['optimization_steps']
            skipped += report['all_negative_batches_skipped']
            seconds += report['training_seconds']
            if (hashes != report['sampled_batch_sha256'] or mask != report['optimizer_skip_mask']
                    or report['optimizer_state_steps'] != [cumulative]*4
                    or report['optimization_steps'] != len(mask)-sum(mask)
                    or set(report['updated_parameters']) != set(runner.TRANSFER)):
                raise ValueError('Native optimizer/sampling semantics failure')
            if defaults is not None and defaults != report['optimizer_defaults']:
                raise ValueError('Optimizer defaults changed')
            defaults = report['optimizer_defaults']
        finished = read(f'reports/{stage}_completed.json')
        if finished['optimizer_steps'] != cumulative or finished['optimizer_state_steps'] != [cumulative]*4:
            raise ValueError('Stage completion optimizer counts failure')
        optimizer_summaries[stage] = {'epochs': count, 'updates': cumulative,
            'skipped_batches': skipped, 'training_seconds': seconds,
            'stage_wall_seconds': finished['elapsed_seconds'],
            'GPU_peak_allocated_bytes': finished['peak_GPU_allocated_bytes'],
            'GPU_peak_reserved_bytes': finished['peak_GPU_reserved_bytes'],
            'peak_host_RSS_bytes': finished['peak_host_RSS_bytes'], 'optimizer_defaults': defaults}
    lineage = read('reports/checkpoint_lineage.json')
    if runner.checkpoint_identity(directory / lineage['final_complete_checkpoint'], lineage['state_keys']) != lineage['final_files']:
        raise ValueError('Complete checkpoint identity failure')
    parent = paths.project_runs_dir / lineage['EL_parent_runs_relative']
    if runner.checkpoint_identity(parent, lineage['state_keys']) != lineage['EL_parent_files']:
        raise ValueError('Historical EL parent changed')
    for checkpoint in selection['checkpoints']:
        if runner.overlay_identity(directory / checkpoint['checkpoint'], lineage['state_keys']) != checkpoint['files']:
            raise ValueError('Candidate checkpoint changed')
    if not all(lineage[k]['consistent'] for k in ('selected_reload', 'final_reload')):
        raise ValueError('Recorded reload inference failed')
    return {'status': 'verified', 'scientific_outputs_verified': len(manifest),
            'original_output_manifest_sha256': runner.raw.sha256_file(directory / 'reports/output_manifest.json'),
            'all_60_validation_metrics_recomputed': True, 'all_native_epoch_source_sequences_verified': True,
            'optimizer_summaries': optimizer_summaries, 'selected_epoch': selected,
            'selected_internal_exposure_strata': strata,
            'reload_evidence_verified': True, 'additional_training_or_inference': False,
            'verification_script_sha256': runner.raw.sha256_file(Path(__file__))}


if __name__ == '__main__':
    result = verify()
    paths = resolve_paths()
    runner.raw.write_report(paths.project_runs_dir / multi.RUN_ID / 'reports/completion_verification.json', result, paths=paths)
    print(json.dumps(result, indent=2))
