"""Focused one-sided mathematics; synthetic inputs only."""
from fractions import Fraction as F
import random
import unittest
from unittest.mock import patch

from stability_label_curation import el_low_stability_design as design


class LowStabilityDesignTests(unittest.TestCase):
    def test_exact_clipping_retains_slope(self):
        self.assertEqual(design.low_weights(['1', '2', '3', '4']),
                         [F(13, 16), F(15, 16), F(1), F(1)])

    def test_numeric_ties_midpoint_and_sparse_groups(self):
        self.assertEqual(design.low_weights(['0', '-0.0', '1', '1.00']),
                         [F(7, 8), F(7, 8), F(1), F(1)])
        self.assertEqual(design.low_weights(['0']), [F(1)])
        self.assertEqual(design.low_weights(['2'] * 5), [F(1)] * 5)
        self.assertEqual(design.low_weights(['0', '1']), [F(7, 8), F(1)])
        self.assertEqual(design.low_weights(['0', '1', '2']), [F(5, 6), F(1), F(1)])

    def test_midpoint_straddling_tie_is_not_split(self):
        self.assertEqual(design.low_weights(['0', '1', '1', '1', '2']),
                         [F(4, 5), F(1), F(1), F(1), F(1)])

    def test_exact_totals_and_fixed_batch_denominator(self):
        report = design.summarize({'HLA-B*08:01': ['0', '1']}, {'HLA-B*08:01': 32})
        self.assertEqual(report['overall']['total_after_exact'], '15/8')
        self.assertEqual(report['overall']['reduction_exact'], '1/8')
        self.assertEqual(report['overall']['median'], 15 / 16)
        self.assertEqual(report['native_EL_epoch']['positive_coefficient_L_P'], float(F(15, 136)))
        self.assertEqual(report['native_EL_epoch']['negative_coefficient_all_arms'], 32 / 17)
        self.assertEqual(report['native_EL_epoch']['steps'], 2)

    def test_no_rng_or_permutation_use(self):
        state = random.getstate()
        with patch('stability_label_curation.el_positive_weighting_design.permuted_weights',
                   side_effect=AssertionError('No permutations during design')):
            report = design.summarize({'HLA-B*08:01': ['0', '1']}, {'HLA-B*08:01': 32})
        self.assertEqual(state, random.getstate())
        self.assertFalse(report['permutations_generated'])
        self.assertFalse(report['row_weights_exported'])

    def test_invalid_scores_and_empty_groups_fail(self):
        for scores in ([], ['NaN'], ['Infinity'], ['-1'], ['']):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                design.low_weights(scores)
        with self.assertRaises(ValueError):
            design.summarize({}, {})
        with self.assertRaises(ValueError):
            design.summarize({'HLA-B*08:01': ['1']}, {})


if __name__ == '__main__':
    unittest.main()
