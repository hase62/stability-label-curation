"""Synthetic-only tests; never open benchmark or training artifacts."""
import io
import math
import random
import unittest

from stability_label_curation import bigmhc_independent_evaluation as evaluation
from stability_label_curation import bigmhc_baseline_runner as reference


def row(index, label, score, peptide=None):
    return {'source_id': f'im_test.csv:row:{index:012d}', 'row_index': index,
            'peptide': peptide or f'PEPTIDE{index:02d}', 'hla': 'HLA-A*02:01',
            'label': label, 'scores': {arm: score for arm in evaluation.ARMS},
            'cluster_id': peptide or f'PEPTIDE{index:02d}'}


class IdentityTests(unittest.TestCase):
    def test_projection_never_decodes_or_parses_sealed_tail(self):
        stream = io.BytesIO(b'mhc,pep,tgt,prediction\nHLA-A*02:01, syfpeithi ,\xff\xfeSEALED\n')
        result = evaluation.source_identities(stream)
        self.assertEqual(result[0]['peptide'], 'SYFPEITHI')
        self.assertEqual(result[0]['row_index'], 1)
        self.assertNotIn('tgt', result[0])
        self.assertNotIn('prediction', result[0])

    def test_original_repeated_pairs_are_retained(self):
        stream = io.BytesIO(b'mhc,pep,tgt\nHLA-A*02:01,SYFPEITHI,SEALED\nHLA-A*02:01,SYFPEITHI,SEALED\n')
        rows = evaluation.source_identities(stream)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['source_id'], rows[1]['source_id'])

    def test_global_sequence_overlap_and_secondary_eligibility(self):
        candidate = {'peptide': 'SYFPEITHI', 'hla': 'HLA-A*02:01',
                     'EL_train_peptide': True, 'IM_train_peptide': False}
        classified = evaluation.classify(candidate, {'HLA-A*02:01'})
        self.assertFalse(classified['primary'])
        self.assertTrue(classified['IM_novel'])
        self.assertTrue(classified['EL_exposed'])
        candidate['IM_train_peptide'] = True
        self.assertFalse(evaluation.classify(candidate, {'HLA-A*02:01'})['IM_novel'])

    def test_validity_and_hla_precede_overlaps(self):
        candidate = {'peptide': 'AX', 'hla': None, 'EL_train_peptide': True, 'IM_train_peptide': True}
        result = evaluation.classify(candidate, set())
        self.assertEqual(result['primary_first_exclusion'], 'invalid_or_non_ninemer')
        self.assertEqual(len(result['exclusion_flags']), 4)
        self.assertFalse(result['primary'])
        self.assertFalse(result['IM_novel'])


class MetricTests(unittest.TestCase):
    def test_exact_tie_grouped_ap(self):
        rows = [row(1, 1, .9), row(2, 0, .9), row(3, 1, .1)]
        result = evaluation.ranking_metrics(rows, 'A')
        self.assertAlmostEqual(result['AP'], 7/12)
        self.assertEqual(result['AUROC'], .25)

    def test_all_tied_scores_equal_prevalence_and_half_auc(self):
        result = evaluation.ranking_metrics([row(i, int(i < 2), .5) for i in range(5)], 'A')
        self.assertEqual(result, {'AP': .4, 'AUROC': .5})

    def test_metrics_against_existing_independent_implementation(self):
        rng = random.Random(7)
        for _ in range(30):
            labels = [0, 1] + [rng.randrange(2) for _ in range(18)]
            scores = [rng.choice([.1, .2, .5, .8]) for _ in labels]
            rows = [row(i, label, score) for i, (label, score) in enumerate(zip(labels, scores))]
            expected = reference.development_metrics(labels, scores)
            actual = evaluation.ranking_metrics(rows, 'A')
            self.assertAlmostEqual(actual['AP'], expected['AUPRC'])
            self.assertAlmostEqual(actual['AUROC'], expected['AUROC'])

    def test_top_k_ties_resolve_by_peptide_hla_source_locator(self):
        rows = [row(i, int(i < 10), .5, peptide='SYFPEITHI') for i in range(20)]
        rng = random.Random(9)
        rng.shuffle(rows)
        result = evaluation.ranking_metrics(rows, 'A', top_k=True)
        self.assertEqual(result['precision_at_10'], 1)
        self.assertEqual(result['precision_at_20'], .5)
        self.assertTrue(evaluation.tie_report(rows, 'A')['top_k_boundary']['10']['crosses_boundary'])

    def test_undefined_k_and_single_class(self):
        result = evaluation.ranking_metrics([row(1, 1, .8), row(2, 0, .2)], 'A', top_k=True)
        self.assertIsNone(result['precision_at_10'])
        self.assertIsNone(result['precision_at_20'])
        self.assertTrue(all(x is None for x in evaluation.ranking_metrics([row(1, 1, .5)], 'A', top_k=True).values()))

    def test_small_EL_exposure_subgroup_unavailable(self):
        rows = [row(1, 1, .8), row(2, 0, .2)]
        result = evaluation.endpoints(rows, 'EL_exposed')
        self.assertTrue(all(value is None for arm in result['arms'].values() for value in arm.values()))

    def test_contrast_signs(self):
        result = evaluation.contrasts({'A': {'AP': .25}, 'S': {'AP': .75}, 'P': {'AP': .5}})
        self.assertEqual(result, {'S-A': {'AP': .5}, 'S-P': {'AP': .25}, 'P-A': {'AP': .25}})

    def test_linear_quantiles(self):
        self.assertEqual(evaluation.quantile([3, 1, 4, 2], .5), 2.5)
        self.assertAlmostEqual(evaluation.quantile([0, 10], .025), .25)
        self.assertIsNone(evaluation.quantile([], .5))

    def test_bootstrap_pairs_arms_and_preserves_peptide_clusters(self):
        # Both rows in each peptide cluster must be sampled together: every
        # resample remains balanced; identical arms have exact zero contrasts.
        rows = [row(i, i % 2, i/10, peptide=f'CLUSTER{i//2}') for i in range(8)]
        cohorts = {'primary': rows, 'IM_novel': rows, 'EL_exposed': []}
        first = evaluation.paired_bootstrap(cohorts, draws=25)
        second = evaluation.paired_bootstrap(cohorts, draws=25)
        self.assertEqual(first, second)
        for cohort in ('primary', 'IM_novel'):
            interval = first['cohorts'][cohort]['contrasts']['S-A']['AP']
            self.assertEqual(interval['usable_draws'], 25)
            self.assertEqual(interval['lower_95'], 0)
            self.assertEqual(interval['upper_95'], 0)


if __name__ == '__main__':
    unittest.main()
