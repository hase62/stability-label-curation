"""Focused synthetic Task 2.27 tests. Never access scientific artifacts."""
import gzip
import json
from pathlib import Path
import random
import tempfile
import unittest

import numpy as np

from stability_label_curation import third_party_evaluation as ev
from stability_label_curation.bigmhc_independent_evaluation import ranking_metrics


def row(i, label, score, component=None):
    return {'source_id': f'row:{i:012d}', 'peptide': f'PEPTIDE{i:02d}', 'hla': 'HLA-A*02:01',
            'study_DOI': 'study', 'patient': f'patient{i}', 'label': label,
            'scores': {arm: score for arm in ev.ARMS},
            'patient_peptide_component': component or f'cluster{i}',
            'study_peptide_component': 'one_study_component'}


class RankingTests(unittest.TestCase):
    def test_grouped_ties_and_prevalence(self):
        rows = [row(1, 1, .9), row(2, 0, .9), row(3, 1, .1)]
        actual = ev.WeightedRanking(rows, 'A').metrics([1]*3, top_k=True)
        self.assertAlmostEqual(actual['AP'], 7/12)
        self.assertEqual(actual['AUROC'], .25)
        self.assertEqual(actual['prevalence'], 2/3)
        self.assertAlmostEqual(actual['AP_minus_prevalence'], 7/12-2/3)
        self.assertAlmostEqual(actual['AP_over_prevalence'], (7/12)/(2/3))
        self.assertIsNone(actual['precision_at_10'])

    def test_weighted_metrics_match_brute_expansion_with_ties_and_zero_weights(self):
        rng = random.Random(19)
        for _ in range(80):
            rows = [row(i, rng.randrange(2), rng.choice([.1, .2, .5, .9])) for i in range(30)]
            weights = [rng.randrange(4) for r in rows]
            expanded = [r for r, w in zip(rows, weights) for _ in range(w)]
            expected = ranking_metrics(expanded, 'A', top_k=True)
            actual = ev.WeightedRanking(rows, 'A').metrics(weights, top_k=True)
            for metric, value in expected.items():
                if value is None:
                    self.assertIsNone(actual[metric])
                else:
                    self.assertAlmostEqual(actual[metric], value, places=14)

    def test_top_k_study_patient_source_tie_order(self):
        # All other keys equal: study precedes patient, which precedes source.
        rows = [dict(row(i, int(i < 10), .5), peptide='SYFPEITHI',
                     study_DOI='a' if i < 5 else 'b', patient=f'{i:02d}') for i in range(21)]
        rows[0]['source_id'] = 'zzz'
        rng = random.Random(9)
        rng.shuffle(rows)
        actual = ev.WeightedRanking(rows, 'A').metrics([1]*len(rows), top_k=True)
        self.assertEqual(actual['precision_at_10'], 1)
        self.assertEqual(actual['precision_at_20'], .5)
        tied = ev.tie_report(rows, 'A', top_k=True)
        self.assertTrue(tied['top_k_boundary']['10']['crosses_boundary'])
        ordered = sorted(rows, key=lambda r: ev.rank_key(r, 'A'))
        self.assertEqual(ordered[0]['source_id'], 'zzz')

    def test_all_ties_and_empty_or_single_class(self):
        rows = [row(i, int(i < 2), .5) for i in range(5)]
        actual = ev.WeightedRanking(rows, 'A').metrics([1]*5, top_k=False)
        self.assertEqual(actual['AP'], .4)
        self.assertEqual(actual['AUROC'], .5)
        for subset, weights in (([], []), (rows, [1, 1, 0, 0, 0]), (rows, [0]*5)):
            result = ev.WeightedRanking(subset, 'A').metrics(weights, top_k=True)
            for key in ('AP', 'AUROC', 'precision_at_10', 'precision_at_20', 'AP_over_prevalence'):
                self.assertIsNone(result[key])


class ResamplingTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row(i, i % 2, i/10, f'cluster{i//2}') for i in range(8)]
        self.cohorts = {t: self.rows for t in ev.ORDER}
        self.rankings = {t: {a: ev.WeightedRanking(self.rows, a) for a in ev.ARMS} for t in ev.ORDER}

    def test_paired_components_preserve_rows_and_multiplicities(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'draws.jsonl.gz'
            actual = ev.paired_bootstrap(self.cohorts, self.rankings, 'patient_peptide_component', 262742,
                                         draws=40, evidence=path)
            with gzip.open(path, 'rt') as stream:
                saved = [json.loads(line) for line in stream]
        expected_rng = random.Random(262742)
        brute = {t: [] for t in ev.ORDER}
        for draw in saved:
            for t in ev.ORDER:
                picked = [expected_rng.randrange(4) for _ in range(4)]
                counts = [picked.count(i) for i in range(4)]
                self.assertEqual(draw['cohorts'][str(t)]['component_multiplicities'], counts)
                self.assertEqual(draw['cohorts'][str(t)]['N'], 8)
                expanded = [r for r in self.rows for _ in range(counts[int(r['patient_peptide_component'][-1])])]
                brute[t].append(ranking_metrics(expanded, 'A')['AP'])
        for t in ev.ORDER:
            contrast = actual['cohorts'][t]['contrasts']['S-A']['AP']
            self.assertEqual(contrast['usable_draws'], 40)
            self.assertEqual(contrast['lower_95'], 0)
            self.assertEqual(contrast['upper_95'], 0)
            self.assertTrue(contrast['unreliable'])
            interval = actual['cohorts'][t]['arms']['A']['AP']
            self.assertAlmostEqual(interval['lower_95'], ev.quantile(brute[t], .025))
            self.assertAlmostEqual(interval['upper_95'], ev.quantile(brute[t], .975))

    def test_single_study_component_has_no_interval(self):
        result = ev.paired_bootstrap(self.cohorts, self.rankings, 'study_peptide_component', 262743, draws=10)
        for t in ev.ORDER:
            self.assertFalse(result['cohorts'][t]['intervals_available'])
            self.assertEqual(result['cohorts'][t]['arms'], {})
            self.assertEqual(result['cohorts'][t]['components'], 1)

    def test_undefined_draws_recorded_without_changing_clusters(self):
        rows = [row(1, 1, .8, 'a'), row(2, 0, .2, 'b')]
        cohorts = {t: rows for t in ev.ORDER}
        rankings = {t: {a: ev.WeightedRanking(rows, a) for a in ev.ARMS} for t in ev.ORDER}
        result = ev.paired_bootstrap(cohorts, rankings, 'patient_peptide_component', 262742, draws=100)
        for t in ev.ORDER:
            interval = result['cohorts'][t]['contrasts']['S-P']['AP']
            self.assertGreater(interval['undefined_draws'], 0)
            self.assertEqual(interval['usable_draws']+interval['undefined_draws'], 100)
            self.assertEqual(interval['lower_95'], 0)


if __name__ == '__main__':
    unittest.main()
