#!/usr/bin/env python3
"""Focused read-only scientific checks on completed Task 2.31; no inference."""
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import gzip
import json
import math

from stability_label_curation.paths import resolve_paths
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import el_stability_loss_adapter as binding
from stability_label_curation.bigmhc_el_positive_upweighting import (
    RUN, baseline_evidence, configuration, scientific_hashes,
)
from stability_label_curation.replicate_stability_association import write_json


def main():
    paths = resolve_paths()
    config = configuration(paths)
    directory = paths.project_runs_dir/RUN
    proof = json.loads((directory/'reports/preflight.json').read_text())
    if proof['scientific_hashes'] != scientific_hashes(paths):
        raise ValueError('Scientific implementation differs from preflight')
    if json.loads((directory/'reports/evaluation_completed.json').read_text())['status'] != 'completed':
        raise ValueError('Final comparison must complete first')
    for name, digest in proof['frozen_artifact_sha256'].items():
        if runner.raw.sha256_file(directory/name) != digest:
            raise ValueError('Frozen preparation artifact changed: '+name)
    base, parent = baseline_evidence(paths, config)
    initial = json.loads((directory/'reports/initialization.json').read_text())
    native_keys = None
    for epoch in range(1, 11):
        reference = json.loads((base/f'reports/EL_epoch_{epoch:02d}.json').read_text())
        native_keys = reference['updated_parameters']
        for arm in ('W', 'P'):
            actual = json.loads((directory/f'reports/{arm}_EL_epoch_{epoch:02d}.json').read_text())
            binding.check_reference({'EL': reference}, stage='EL', training=actual)
            if (actual['RNG_before'] != reference['RNG_before'] or actual['RNG_after'] != reference['RNG_after']
                    or actual['cumulative_optimizer_steps'] != epoch*63053
                    or len(actual['optimizer_state_steps']) != 36
                    or set(actual['optimizer_state_steps']) != {epoch*63053}
                    or actual['sampled_class_exposures'] != {'1': 63053, '0': 1008848}
                    or actual['consumed_rows'] != 1071901
                    or any(v['rows'] != 17 or v['positives'] != 1 for v in actual['step_log'])):
                raise ValueError('Matched epoch schedule, optimizer or exposure differs')
    for arm in ('W', 'P'):
        if json.loads((directory/f'reports/{arm}_initialization.json').read_text()) != initial:
            raise ValueError('Initial parameters/RNG differ from A')
        checkpoint = json.loads((directory/f'reports/{arm}_final_EL_checkpoint.json').read_text())
        if (not checkpoint['strict_reload_equal'] or not checkpoint['probe_predictions_equal']
                or checkpoint['epoch'] != 10 or checkpoint['optimizer_steps'] != 630530
                or runner.checkpoint_identity(directory/checkpoint['checkpoint'], native_keys) != checkpoint['files']):
            raise ValueError('Final epoch-10 EL checkpoint identity/reload failed')
    with gzip.open(directory/'processed/training_positive_weights.csv.gz', 'rt', newline='') as stream:
        weights = list(csv.DictReader(stream))
    if len(weights) != 63053 or len({r['source_row_id'] for r in weights}) != 63053:
        raise ValueError('Weight coverage differs')
    by_hla = defaultdict(list)
    for row in weights:
        by_hla[row['HLA']].append(row)
        rank, weight = Fraction(row['training_percentile_exact']), Fraction(row['W_exact'])
        if weight != 1+Fraction(1, 2)*max(Fraction(), rank-Fraction(1, 2)) or not 1 <= weight <= Fraction(5, 4):
            raise ValueError('Fixed upweight function differs')
    for group in by_hla.values():
        if Counter(Fraction(r['W_exact']) for r in group) != Counter(Fraction(r['P_exact']) for r in group):
            raise ValueError('Within-HLA exact weight multiset changed')
        if Counter(r['W_FP32'] for r in group) != Counter(r['P_FP32'] for r in group):
            raise ValueError('Within-HLA FP32 weight multiset changed')
    with (base/'predictions/EL_epoch_10.csv').open(newline='') as stream:
        original = list(csv.DictReader(stream))
    for arm in ('A', 'W', 'P'):
        epochs = (10,) if arm == 'A' else range(1, 11)
        for epoch in epochs:
            with (directory/f'predictions/{arm}_EL_epoch_{epoch:02d}.csv').open(newline='') as stream:
                for expected, row in zip(original, csv.DictReader(stream), strict=True):
                    if any(expected[key] != row[key] for key in ('original_prepared_row_index', 'HLA', 'peptide', 'original_label')):
                        raise ValueError('Validation order or original labels changed')
                    if not math.isfinite(float(row['probability'])) or not 0 <= float(row['probability']) <= 1:
                        raise ValueError('Nonfinite validation prediction')
    result = {'status': 'PASS', 'matched_EL_training_epochs_verified': 20,
              'optimizer_steps_per_arm': 630530, 'matching_initial_tensors': 36,
              'training_positive_weights_verified': 63053, 'identical_HLA_weight_multisets': len(by_hla),
              'ordered_validation_prediction_files_verified': 21, 'observations_per_file': len(original),
              'original_labels_and_source_identities_preserved': True,
              'final_checkpoints_and_reload_receipts_verified': 2,
              'new_inference_or_training': False, 'scientific_hashes': scientific_hashes(paths)}
    write_json(directory/'reports/completion_verification.json', result)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
