"""Focused Task 2.33: no benchmark prediction/performance calculation."""
import ast
from copy import deepcopy
import inspect
import math
import random
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from stability_label_curation import auxiliary_el_only_zero_shot_im as study
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths
from stability_label_curation.third_party_evaluation import WeightedRanking


def examples():
    return [{'source_id': str(i), 'peptide': 'PEPTIDE'+str(i), 'hla': 'HLA-A*02:01',
             'study_DOI': '', 'patient': '', 'label': label,
             'scores': {arm: score for arm in study.ARMS}, 'component': str(i//2)}
            for i, (score, label) in enumerate([(.8, 1), (.8, 0), (.3, 1), (.1, 0)])]


class StatisticalTests(unittest.TestCase):
    def test_cluster_evidence_file_writes_all_draws_with_same_paired_rows(self):
        rows = examples(); rankings = {a: WeightedRanking(rows, a) for a in study.ARMS}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'draws.jsonl.gz'
            result = study.bootstrap(rows, rankings, 'component', 262742, 12, path)
            with gzip.open(path, 'rt') as stream:
                draws = [json.loads(line) for line in stream]
            self.assertEqual(result['draws_executed'], 12)
            self.assertEqual(len(draws), 12)
            self.assertTrue(all(sum(d['component_multiplicities']) == 2 for d in draws))
            self.assertTrue(all(d['contrasts']['S-A']['prevalence'] == 0 for d in draws))

    def test_exact_tied_AP_AUROC_matches_hand_example(self):
        rows = examples()
        actual = WeightedRanking(rows, 'S').metrics(np.ones(4, dtype=np.int64), top_k=True)
        self.assertAlmostEqual(actual['AP'], 7/12)
        self.assertEqual(actual['AUROC'], 5/8)
        self.assertIsNone(actual['precision_at_10'])
        self.assertIsNone(actual['precision_at_20'])

    def test_integer_multiplicity_matches_literal_expanded_ties_and_topK(self):
        rows = examples(); counts = np.array([8, 3, 2, 9])
        actual = WeightedRanking(rows, 'A').metrics(counts, top_k=True)
        expanded = [r for r, n in zip(rows, counts) for _ in range(n)]
        values = runner.development_metrics([r['label'] for r in expanded], [r['scores']['A'] for r in expanded])
        self.assertAlmostEqual(actual['AP'], values['AUPRC'])
        self.assertAlmostEqual(actual['AUROC'], values['AUROC'])
        expanded.sort(key=lambda r: study.rank_key(r, 'A'))
        self.assertEqual(actual['precision_at_10'], sum(r['label'] for r in expanded[:10])/10)
        self.assertEqual(actual['precision_at_20'], sum(r['label'] for r in expanded[:20])/20)

    def test_paired_cluster_resampling_zero_contrasts_deterministic_local_rng(self):
        rows = examples(); rankings = {a: WeightedRanking(rows, a) for a in study.ARMS}
        before = random.getstate()
        actual = study.bootstrap(rows, rankings, 'component', 262742, 200)
        self.assertEqual(random.getstate(), before)
        self.assertEqual(actual, study.bootstrap(rows, rankings, 'component', 262742, 200))
        for endpoint in actual['confidence_intervals']['S-A'].values():
            if endpoint['usable_draws']:
                self.assertEqual(endpoint['lower_95'], 0)
                self.assertEqual(endpoint['upper_95'], 0)
        self.assertTrue(actual['unreliable'])

    def test_one_dependence_component_undefined_no_fake_study_bootstrap(self):
        rows = examples()
        for row in rows:
            row['component'] = 'shared-study-peptide-component'
        result = study.bootstrap(rows, {a: WeightedRanking(rows, a) for a in study.ARMS}, 'component', 262743, 10000)
        self.assertEqual(result['components'], 1)
        self.assertEqual(result['draws_executed'], 0)
        self.assertIsNone(result['confidence_intervals'])

    def test_classless_metrics_and_contrast_signs(self):
        rows = examples()
        for row in rows:
            row['label'] = 0
        values = WeightedRanking(rows, 'A').metrics(np.ones(4, dtype=np.int64), top_k=True)
        self.assertIsNone(values['AP']); self.assertIsNone(values['AUROC'])
        self.assertIsNone(values['AP_over_prevalence'])
        result = study.paired_contrasts({'A': {'AP': .1}, 'S': {'AP': .3}, 'P': {'AP': .2}})
        self.assertAlmostEqual(result['S-A']['AP'], .2)
        self.assertAlmostEqual(result['S-P']['AP'], .1)
        self.assertAlmostEqual(result['P-A']['AP'], .1)


class SafeguardTests(unittest.TestCase):
    def test_outcomes_not_native_inputs_and_duplicate_observations_retained(self):
        rows = [{'source_id': 'first', 'peptide': 'AAAAAAAAA', 'hla': 'HLA-A*02:01', 'label': 1},
                {'source_id': 'second', 'peptide': 'AAAAAAAAA', 'hla': 'HLA-A*02:01', 'label': 0}]
        inputs = study.model_inputs(rows)
        self.assertEqual(len(inputs), 2)
        self.assertEqual([r['original_label'] for r in inputs], ['0', '0'])
        self.assertTrue(all(set(r)=={'hla','peptide','original_label'} for r in inputs))

    def test_source_HLA_order_swap_fails(self):
        rows = [{'source_id': 'first', 'peptide': 'AAAAAAAAA', 'hla': 'HLA-A*02:01'},
                {'source_id': 'second', 'peptide': 'VVVVVVVVV', 'hla': 'HLA-B*07:02'}]
        predictions = [{**r, 'raw_EL_logit': 0., 'EL_probability': .5} for r in rows]
        study.join_predictions(rows, predictions)
        with self.assertRaises(ValueError):
            study.join_predictions(rows, list(reversed(predictions)))

    def test_no_optimizer_training_calibration_or_transfer_calls(self):
        tree = ast.parse(inspect.getsource(study))
        calls = {getattr(n.func, 'attr', getattr(n.func, 'id', '')) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        self.assertFalse(calls & {'AdamW', 'SGD', 'fit', 'train_epoch', 'backward', 'step', 'runtime_adapter'})
        config = study.configuration(resolve_paths())
        self.assertEqual(config['models']['A']['checkpoint'], 'checkpoints/EL_epoch_10')
        self.assertEqual(config['models']['S']['checkpoint'], 'checkpoints/S_EL_epoch_10')
        self.assertEqual(config['models']['P']['checkpoint'], 'checkpoints/P_EL_epoch_10')
        self.assertFalse(config['training_authorized'])

    def test_authentic_frozen_model_and_cohort_bindings_without_scoring(self):
        paths = resolve_paths(); config = study.configuration(paths)
        models, files, keys = study.authenticate_models(paths, config)
        self.assertEqual(len(keys), 36)
        self.assertEqual(set(models), set(study.ARMS))
        self.assertTrue(all(m['EL_only'] and not m['transfer_overlay_loaded'] for m in models.values()))
        self.assertEqual(set(files), set(config['inputs']))
        self.assertEqual(study.training_compatibility(paths,config)['status'], 'PASS')
        cohorts, outcomes, _ = study.load_cohorts(paths, config)
        self.assertEqual({n:len(r) for n,r in cohorts.items()}, {'IMPROVE':7788,'neoepitope':267})
        self.assertEqual(study.check_A_reuse(paths,config,cohorts)['status'],'PASS')

    def test_stable_serialization_and_no_overwrite(self):
        value = {'a': 0.12345678901234567, 'undefined': None}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'receipt.json'
            study.write_json(target, value)
            self.assertEqual(json.loads(target.read_text()), value)
            with self.assertRaises(FileExistsError):
                study.write_json(target, value)

    def test_EL_only_classification_path_does_not_install_auxiliary_head(self):
        text = inspect.getsource(study.inference)
        self.assertIn("for arm in ('S', 'P')", text)
        self.assertIn('lineage=None', text)
        self.assertIn('torch.sigmoid(logits)', text)
        self.assertNotIn('AuxiliaryHead(', text)
        self.assertNotIn('register_forward_hook', text)
        self.assertFalse(study.configuration(resolve_paths())['training_authorized'])



if __name__ == '__main__':
    unittest.main()
