"""Focused extension safeguards; synthetic data only."""
import ast
from fractions import Fraction
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest

from stability_label_curation import hla_extended_epochs as m
from stability_label_curation import el_stability_loss_adapter as binding


class ExtensionTests(unittest.TestCase):
    def fixture(self):
        rows = [{'source_row_id': str(i), 'hla': 'HLA-A*02:01', 'peptide': 'AAAAAAAAA', 'original_label': str(int(i < 4))} for i in range(5)]
        scores = {str(i): SimpleNamespace(original_peptide='AAAAAAAAA', resolved_hla='HLA-A*02:01', predicted_half_life_hours=str(v)) for i, v in enumerate([1, 2, 2, 4])}
        return rows, SimpleNamespace(scores=scores)

    def test_original_formula_and_ties(self):
        rows, scores = self.fixture()
        weights, ledger, evidence = m.weights_for(rows, scores)
        self.assertEqual([Fraction(r['rank_exact']) for r in ledger], [Fraction(1, 8), Fraction(1, 2), Fraction(1, 2), Fraction(7, 8)])
        self.assertEqual([Fraction(r['W_exact']) for r in ledger], [Fraction(13, 16), Fraction(1), Fraction(1), Fraction(19, 16)])
        self.assertEqual(weights['L']['3'], 1)
        self.assertNotIn('4', weights['W'])
        self.assertEqual(evidence['labels_changed'], 0)

    def test_missing_binding_fails(self):
        rows, scores = self.fixture()
        scores.scores.pop('0')
        with self.assertRaises(KeyError):
            m.weights_for(rows, scores)

    def test_mismatched_binding_fails(self):
        rows, scores = self.fixture()
        rows[0]['hla'] = 'HLA-B*07:02'
        with self.assertRaises(ValueError):
            m.weights_for(rows, scores)

    def test_exact_row_alignment(self):
        m.assert_alignment(['a', 'b'], ['a', 'b'])
        for bad in [['b', 'a'], ['a'], ['a', 'a']]:
            with self.assertRaises(ValueError):
                m.assert_alignment(['a', 'b'], bad)

    def test_duplicate_expected_rejected(self):
        with self.assertRaises(ValueError):
            m.assert_alignment(['a', 'a'], ['a', 'a'])

    def test_no_external_outcome_or_metric_reader_in_scorer(self):
        source = inspect.getsource(m.infer_one)
        tree = ast.parse(source)
        calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertFalse(set(calls) & {'development_metrics', 'el_metrics', 'bootstrap', 'join_predictions'})
        self.assertNotIn('outcomes.json', source)
        self.assertNotIn('label', source.replace('label-blind', ''))

    def test_prescribed_seeds_and_final_epochs(self):
        import json
        conf = json.loads((Path(m.__file__).resolve().parents[2]/m.CONFIG).read_text())
        self.assertEqual(conf['seeds'], [42, 123, 456])
        self.assertEqual((conf['EL_epochs'], conf['IM_epochs']), (10, 20))
        self.assertNotIn(['A', 42], conf['jobs'])
        self.assertEqual(len(conf['jobs']), 8)

    def test_loss_native_row_denominator_and_unit_equality(self):
        import torch
        x = torch.tensor([.2, -.5, 1.], requires_grad=True)
        y = torch.tensor([1., 0., 0.])
        losses = torch.nn.functional.binary_cross_entropy_with_logits(x, y, reduction='none')
        actual = binding.weighted_bce(torch, x, y, [.8, 1, 1])
        self.assertTrue(torch.equal(actual, (losses*torch.tensor([.8, 1, 1])).mean()))
        self.assertNotEqual(float(actual.detach()), float((losses*torch.tensor([.8, 1, 1])).sum().detach()/2.8))
        native = torch.nn.functional.binary_cross_entropy_with_logits(x, y)
        unit = binding.weighted_bce(torch, x, y, [1, 1, 1])
        self.assertTrue(torch.equal(native, unit))
        self.assertTrue(torch.equal(torch.autograd.grad(native, x, retain_graph=True)[0], torch.autograd.grad(unit, x)[0]))

    def test_invalid_weights_rejected(self):
        import torch
        for weights in [[0, 1], [1, .9], [float('nan'), 1]]:
            with self.assertRaises(ValueError):
                binding.weighted_bce(torch, torch.tensor([0., 0.]), torch.tensor([1., 0.]), weights)


if __name__ == '__main__':
    unittest.main()
