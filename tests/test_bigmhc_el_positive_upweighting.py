"""Focused Task 2.31 identity, training-only ranking and loss checks."""
from fractions import Fraction
import json
import random
from types import SimpleNamespace
import unittest

from stability_label_curation.bigmhc_el_positive_upweighting import Weights, configuration
from stability_label_curation.el_stability_loss_adapter import PositiveScore, weighted_bce
from stability_label_curation.paths import resolve_paths
from stability_label_curation import bigmhc_baseline_runner as runner


def example():
    scores = {}
    rows = []
    for i, (hla, value) in enumerate([('HLA-A*02:01', '1'), ('HLA-A*02:01', '1.00'),
        ('HLA-A*02:01', '2'), ('HLA-A*02:01', '3'), ('HLA-B*07:02', '0'), ('HLA-B*07:02', '-0.0')], 1):
        identity = str(i)
        scores[identity] = PositiveScore(str(i), str(i), identity, 'synthetic', hla, hla, 'AAAAAAAAA', '1', value)
        rows.append({'source_row_id': identity, 'hla': hla, 'original_label': '1'})
    # An unreferenced validation score must never contribute to training ranks.
    scores['validation_only'] = PositiveScore('7', '7', 'validation_only', 'synthetic', 'HLA-A*02:01', 'HLA-A*02:01', 'VVVVVVVVV', '1', '100000')
    rows.append({'source_row_id': 'negative', 'hla': 'HLA-A*02:01', 'original_label': '0'})
    return rows, SimpleNamespace(scores=scores)


class WeightTests(unittest.TestCase):
    def test_exact_formula_ties_training_only_and_negative_not_weighted(self):
        rows, sidecar = example()
        weights = Weights(rows, sidecar)
        exact = {r['source_row_id']: Fraction(r['W_exact']) for r in weights.ledger}
        self.assertEqual(exact, {'1': Fraction(1), '2': Fraction(1), '3': Fraction(17, 16), '4': Fraction(19, 16), '5': Fraction(1), '6': Fraction(1)})
        self.assertNotIn('validation_only', weights.weights['W'])
        self.assertNotIn('negative', weights.weights['W'])
        self.assertEqual(weights.evidence['overall']['downweighted_n'], 0)
        self.assertEqual(weights.evidence['source_binding_coverage'], 6)
        self.assertEqual(weights.evidence['ranks']['mean'], .5)

    def test_per_HLA_multisets_masses_and_global_rng_preserved(self):
        rows, sidecar = example()
        before = random.getstate()
        w = Weights(rows, sidecar)
        self.assertEqual(before, random.getstate())
        for hla in ('HLA-A*02:01', 'HLA-B*07:02'):
            ids = [r['source_row_id'] for r in rows if r['hla'] == hla and r['original_label'] == '1']
            genuine, permuted = ([w.weights[m][i] for i in ids] for m in ('W', 'P'))
            self.assertEqual(sorted(genuine), sorted(permuted))
            self.assertEqual(sum(genuine), sum(permuted))
        self.assertEqual(w.weights, Weights(rows, sidecar).weights)

    def test_nonfinite_and_missing_scores_fail(self):
        rows, sidecar = example()
        sidecar.scores.pop('1')
        with self.assertRaises(KeyError):
            Weights(rows, sidecar)
        rows, sidecar = example()
        score = sidecar.scores['1']
        sidecar.scores['1'] = PositiveScore(**{**score.__dict__, 'predicted_half_life_hours': 'NaN'})
        with self.assertRaises(ValueError):
            Weights(rows, sidecar)

    def test_authorized_configuration_EL_only(self):
        config = configuration(resolve_paths())
        self.assertFalse(config['IM_training_authorized'])
        self.assertEqual(config['EL_epochs'], 10)
        self.assertFalse(any(k.startswith('IM') for k in config['inputs']))


class CUDALossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('Task 2.31 focused tests require CUDA; no silent skip')
        cls.torch = torch

    def test_native_noop_loss_and_gradients(self):
        t = self.torch
        x = t.tensor([-.3, .1, 2.0], device='cuda', requires_grad=True)
        y = t.tensor([1., 0., 0.], device='cuda')
        native = t.nn.functional.binary_cross_entropy_with_logits(x, y)
        gradient = t.autograd.grad(native, x)[0]
        adapted = weighted_bce(t, x, y, [1, 1, 1])
        self.assertTrue(t.equal(native, adapted))
        self.assertTrue(t.equal(gradient, t.autograd.grad(adapted, x)[0]))

    def test_positive_anchor_only_and_original_batch_denominator(self):
        t = self.torch
        x = t.tensor([0., -.4, .7], device='cuda', requires_grad=True)
        y = t.tensor([1., 0., 0.], device='cuda')
        loss = weighted_bce(t, x, y, [1.25, 1, 1])
        individual = t.nn.functional.binary_cross_entropy_with_logits(x, y, reduction='none')
        self.assertTrue(t.equal(loss, (individual*t.tensor([1.25, 1, 1], device='cuda')).sum()/3))
        native_grad = (t.sigmoid(x)-y)/3
        gradient = t.autograd.grad(loss, x)[0]
        self.assertTrue(t.equal(gradient[1:], native_grad[1:]))
        self.assertAlmostEqual(float(gradient[0]), float(native_grad[0]*1.25), places=7)
        with self.assertRaises(ValueError):
            weighted_bce(t, x, y, [1.25, 1.1, 1])

    def test_existing_exact_cluster_metric_matches_expanded_rows_with_ties(self):
        import numpy as np
        from stability_label_curation.third_party_evaluation import WeightedRanking
        rows = [{'scores': {'W': score}, 'label': label, 'peptide': str(i), 'hla': 'A',
                 'study_DOI': '', 'patient': '', 'source_id': str(i)}
                for i, (score, label) in enumerate([(.8, 1), (.8, 0), (.3, 1), (.1, 0)])]
        multiplicities = np.array([2, 1, 0, 3])
        ranking = WeightedRanking(rows, 'W')
        actual = ranking.metrics(multiplicities, top_k=False)
        expanded = [r for r, n in zip(rows, multiplicities) for _ in range(n)]
        expected = runner.development_metrics([r['label'] for r in expanded], [r['scores']['W'] for r in expanded])
        self.assertAlmostEqual(actual['AP'], expected['AUPRC'])
        self.assertAlmostEqual(actual['AUROC'], expected['AUROC'])


if __name__ == '__main__':
    unittest.main()
