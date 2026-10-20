"""Focused frozen-cohort, original-model and tie-aware statistical checks."""
import itertools
import json
import math
import random
import unittest

from stability_label_curation.paths import resolve_paths
from stability_label_curation.monoallelic_replicate_rescue import sha256
from stability_label_curation.replicate_stability_association import (
    CONFIG, bootstrap_availability, canonical_json, dependence_components,
    doubled_ranks, intensity_adjustment, nearest_hamming, permutation_control,
    quantile, rank_stratum, spearman,
)


class RankTests(unittest.TestCase):
    def test_tied_ordinal_spearman_against_hand_calculation(self):
        self.assertEqual(doubled_ranks([1, 1, 2, 3]), [3, 3, 6, 8])
        self.assertEqual(doubled_ranks([0, 1, 1, 2]), [2, 5, 5, 8])
        self.assertAlmostEqual(spearman([1, 1, 2, 3], [0, 1, 1, 2]), 5/6)
        self.assertEqual(spearman([1, 1, 2, 3], [0, 1, 1, 2]), spearman([1, 1, 2, 3], [0, .5, .5, 1]))

    def test_constant_empty_or_singleton_is_undefined(self):
        for x, y in [([], []), ([1], [2]), ([1, 1], [0, 1]), ([1, 2], [0, 0])]:
            self.assertIsNone(spearman(x, y))
        report, draws = permutation_control([1, 1], [0, 1], 10, 1)
        self.assertEqual(report['undefined_draws'], 10)
        self.assertEqual(draws, [])

    def test_nonfinite_and_misaligned_fail(self):
        with self.assertRaises(ValueError):
            doubled_ranks([1, math.nan])
        with self.assertRaises(ValueError):
            spearman([1, 2], [1])

    def test_one_sided_permutation_includes_ties_and_plus_one(self):
        x, y = [1, 1, 2, 2], [0, 0, 2, 2]
        observed = spearman(x, y)
        exact = sum(spearman(p, y) >= observed for p in itertools.permutations(x))/math.factorial(4)
        self.assertEqual(exact, 1/6)
        result, draws = permutation_control(x, y, 2000, 228230)
        self.assertEqual(result['p_one_sided_descriptive'], (1+sum(v >= observed for v in draws))/2001)
        self.assertAlmostEqual(result['p_one_sided_descriptive'], exact, delta=.03)
        self.assertEqual((result, draws), permutation_control(x, y, 2000, 228230))

    def test_quartiles_keep_ties_together(self):
        ranks = doubled_ranks([0, 0, 0, 1, 2, 3, 4, 5])
        strata = [rank_stratum(r/2, 8, [.25, .5, .75, 1]) for r in ranks]
        self.assertEqual(strata[:3], [1, 1, 1])
        self.assertEqual(quantile([1, 3], .25), 1.5)

    def test_stable_json_rejects_nan_and_sorts_keys(self):
        self.assertEqual(canonical_json({'b': None, 'a': .5}), canonical_json({'a': .5, 'b': None}))
        self.assertIsNone(json.loads(canonical_json({'undefined': None}))['undefined'])
        with self.assertRaises(ValueError):
            canonical_json({'x': math.nan})


class DesignTests(unittest.TestCase):
    def test_hamming_search_against_brute_force(self):
        rng = random.Random(229)
        references = sorted({''.join(rng.choices('ACDE', k=9)) for _ in range(45)})
        for query in references[:5]+['ACDEACDEA', 'AAAAAAAAA', 'EEEEEEEEE']:
            distances = [(sum(a != b for a, b in zip(query, r)), r) for r in references]
            expected, witness = min(distances)
            self.assertEqual(nearest_hamming(query, references), (expected, witness))

    def test_one_group_is_one_component_not_671_independent_units(self):
        rows = [{'source_identity': str(i), 'group_id': 'g', 'peptide': str(i),
                 'biological_samples': ['s1', 's2', 's3']} for i in range(10)]
        units = dependence_components(rows)
        self.assertEqual(len(units), 1)
        config = {'component_bootstrap_minimum_units': 2, 'component_bootstrap_draws_if_estimable': 10000,
                  'component_bootstrap_seed': 228229}
        result = bootstrap_availability(units, config)
        self.assertIsNone(result['confidence_interval_95'])
        self.assertEqual(result['draws_executed'], 0)
        self.assertFalse(result['peptide_independent_bootstrap_substituted'])

    def test_shared_peptide_connects_other_groups(self):
        rows = [{'source_identity': 'a', 'group_id': 'g1', 'peptide': 'p', 'biological_samples': ['s1']},
                {'source_identity': 'b', 'group_id': 'g2', 'peptide': 'p', 'biological_samples': ['s2']}]
        self.assertEqual(len(dependence_components(rows)), 1)

    def test_missing_intensity_is_not_imputed_as_abundance(self):
        result = intensity_adjustment([{'index_precursor_intensity': None}]*3)
        self.assertEqual(result['missing_precursor_intensity'], 3)
        self.assertFalse(result['regression_fitted'])
        self.assertIsNone(result['coefficient'])
        with self.assertRaises(ValueError):
            intensity_adjustment([{'index_precursor_intensity': 123}])


class AuthenticatedInputTests(unittest.TestCase):
    def test_original_teacher_synthetic_smoke(self):
        from stability_label_curation import stability_teacher as teacher
        p = resolve_paths()
        bundle = p.project_data_dir/'teacher-v0-recovered'
        config = json.loads((p.repository_root/CONFIG).read_text())
        self.assertEqual(sha256(bundle/'checkpoints/teacher_model.json'), config['model_sha256'])
        self.assertEqual(sha256(bundle/'src/stability_label_curation/stability_teacher.py'), sha256(p.repository_root/'src/stability_label_curation/stability_teacher.py'))
        model = teacher.load_model(bundle/'checkpoints/teacher_model.json')
        expected = json.loads((bundle/'dummy/expected.json').read_text())
        for row in expected['predictions']:
            value = model.predict_stability(row['peptide'], 'HLA-A*02:01')
            self.assertEqual(value['model_status'], 'ok')
            self.assertAlmostEqual(value['predicted_half_life_hours'], row['predicted_half_life_hours'], delta=1e-12)

    def test_frozen_index_identity_and_followup_count(self):
        p = resolve_paths()
        config = json.loads((p.repository_root/CONFIG).read_text())
        path = p.project_runs_dir/config['curation_run_id']/'manifests/future_primary_index_cohort.jsonl'
        self.assertEqual(sha256(path), config['index_cohort_sha256'])
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len({(r['peptide'], r['hla']) for r in rows}), 671)
        for row in rows:
            self.assertEqual(row['raw_files'], config['ordered_runs'])
            self.assertEqual(row['direct_detection'][0], 1)
            self.assertEqual(sum(row['direct_detection'][1:])/2, row['repeat_detection_frequency'])


if __name__ == '__main__':
    unittest.main()
