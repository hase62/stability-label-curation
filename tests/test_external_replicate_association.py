"""Focused Task 2.30B checks; no new-study Teacher scoring or association tests."""
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest

from stability_label_curation.external_replicate_association import (
    CONFIG, align_predictions, config_for, ols, regression_pair, validate_row,
)
from stability_label_curation.monoallelic_replicate_rescue import sha256
from stability_label_curation.paths import resolve_paths
from stability_label_curation.replicate_stability_association import (
    bootstrap_availability, canonical_json, dependence_components, doubled_ranks,
    permutation_control, spearman, write_json,
)


class StatisticalTests(unittest.TestCase):
    def test_binary_ties_against_enumeration(self):
        x, y = [1, 1, 2, 3], [0, 0, 1, 1]
        self.assertEqual(doubled_ranks(x), [3, 3, 6, 8])
        self.assertAlmostEqual(spearman(x, y), 4/math.sqrt(18))
        expected = sum(spearman(v, y) >= spearman(x, y) for v in itertools.permutations(x))/24
        result, draws = permutation_control(x, y, 2000, 228230)
        self.assertAlmostEqual(result['p_one_sided_descriptive'], expected, delta=.03)
        self.assertEqual(result['p_one_sided_descriptive'], (1+result['greater_or_equal_draws'])/2001)
        self.assertEqual((result, draws), permutation_control(x, y, 2000, 228230))
        self.assertIsNone(spearman([1, 1], [0, 1]))

    def test_ols_known_full_rank_solution_and_normal_equations(self):
        x = [0, 1, 2, 3, 4, 5]
        z = [2, -1, 1, -1, 3, 0]
        missing = [0, 0, 0, 1, 1, 1]
        y = [2+.7*a-1.2*b+3*c for a, b, c in zip(x, z, missing)]
        result = ols([[1.0]*6, x, z, missing], y, ['intercept', 'rank', 'intensity', 'missing'])
        for actual, expected in zip(result['coefficients'].values(), [2, .7, -1.2, 3]):
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertLess(result['normal_equation_max_absolute_error'], 1e-11)
        self.assertIsNone(result['confidence_interval_95'])
        self.assertIsNone(result['p_value'])

    def test_rank_deficiency_and_nonfinite_fail_without_alternative_covariates(self):
        result = ols([[1.0]*4, [1, 2, 3, 4], [2, 4, 6, 8]], [0, 0, 1, 1], ['i', 'a', 'b'])
        self.assertEqual(result['status'], 'undefined')
        self.assertIsNone(result['coefficients'])
        with self.assertRaises(ValueError):
            ols([[1, 1], [1, math.nan]], [0, 1], ['i', 'r'])

    def test_missing_intensity_preserved_indicator_and_constant_omitted(self):
        rows = [{'index_precursor_intensity': v, 'biological_followup_direct_detection': y}
                for v, y in zip([2, 16, None, 4, 128, 8], [0, 1, 1, 0, 1, 1])]
        result = regression_pair(rows, [1, 1, 2, 3, 4, 5])
        self.assertEqual(result['n'], 6)
        self.assertEqual(result['missing_n'], 1)
        self.assertEqual(result['log2_intensity_center'], 3.4)
        self.assertIn('missing_index_intensity', result['adjusted']['coefficients'])
        complete = [r for r in rows if r['index_precursor_intensity'] is not None]
        result2 = regression_pair(complete, [1, 1, 3, 4, 5])
        self.assertEqual(result2['n'], 5)
        self.assertNotIn('missing_index_intensity', result2['adjusted']['coefficients'])
        self.assertEqual(result2['unadjusted']['design_columns'], ['intercept', 'stability_percentile'])

    def test_one_clone_pair_has_no_biological_interval(self):
        rows = [{'source_identity': str(i), 'group_id': 'pair1', 'peptide': str(i),
                 'biological_samples': ['clone1', 'clone2']} for i in range(5)]
        units = dependence_components(rows)
        result = bootstrap_availability(units, {'component_bootstrap_minimum_units': 2,
            'component_bootstrap_draws_if_estimable': 10000, 'component_bootstrap_seed': 228229})
        self.assertEqual(result['independent_units'], 1)
        self.assertEqual(result['draws_executed'], 0)
        self.assertIsNone(result['confidence_interval_95'])

    def test_stable_finite_serialization_and_no_overwrite(self):
        self.assertEqual(canonical_json({'b': None, 'a': .5}), '{"a": 0.5, "b": null}')
        with self.assertRaises(ValueError):
            canonical_json({'a': math.nan})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'result.json'
            write_json(path, {'undefined': None})
            self.assertIsNone(json.loads(path.read_text())['undefined'])
            with self.assertRaises(FileExistsError):
                write_json(path, {'overwrite': True})

    def test_alignment_detects_swapped_source_even_when_scores_finite(self):
        rows = [{'source_identity': str(i), 'peptide': p, 'hla': 'HLA-A*02:01'}
                for i, p in enumerate(['AAAAAAAAA', 'VVVVVVVVV'])]
        preds = [{**r, 'model_status': 'ok', 'resolved_hla': r['hla'],
                  'predicted_log1p_hours': 1., 'predicted_half_life_hours': math.expm1(1.)} for r in rows]
        align_predictions(rows, preds)
        with self.assertRaises(ValueError):
            align_predictions(rows, list(reversed(preds)))


class AuthenticatedInputTests(unittest.TestCase):
    def test_original_teacher_three_synthetic_smokes(self):
        from stability_label_curation import stability_teacher as teacher
        p = resolve_paths()
        config = config_for(p)
        bundle = p.project_data_dir/config['bundle_relative_path']
        self.assertEqual(sha256(bundle/'checkpoints/teacher_model.json'), config['model_sha256'])
        self.assertEqual(sha256(bundle/'src/stability_label_curation/stability_teacher.py'), sha256(p.repository_root/'src/stability_label_curation/stability_teacher.py'))
        model = teacher.load_model(bundle/'checkpoints/teacher_model.json')
        for row in json.loads((bundle/'dummy/expected.json').read_text())['predictions']:
            result = model.predict_stability(row['peptide'], 'HLA-A*02:01')
            self.assertEqual(result['model_status'], 'ok')
            for key in ('predicted_half_life_hours', 'predicted_log1p_hours'):
                self.assertAlmostEqual(result[key], row[key], delta=1e-12)

    def test_frozen_496_and_483_and_complete_case_identities(self):
        p = resolve_paths()
        config = config_for(p)
        parent = p.project_runs_dir/config['curation_run_id']
        path = parent/'manifests/future_primary_index_cohort.jsonl'
        self.assertEqual(sha256(path), '37d5247b7533243d4083142b9ec3dd4645eb8bcc344293908763cfb94bac5cd2')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        ids = json.loads((parent/'manifests/future_sensitivity_source_identities.json').read_text())
        self.assertEqual(len(rows), 496)
        self.assertEqual(len(set(ids)), 483)
        self.assertEqual(sum(r['index_precursor_intensity'] is not None for r in rows), 473)
        self.assertEqual(sum(r['source_identity'] in ids and r['index_precursor_intensity'] is not None for r in rows), 460)
        for row in rows:
            validate_row(row, config['ordered_runs'])
        altered = deepcopy(rows[0])
        altered['biological_followup_direct_detection'] = 1-altered['biological_followup_direct_detection']
        with self.assertRaises(ValueError):
            validate_row(altered, config['ordered_runs'])
        # Follow-up intensity cannot affect validation of the frozen index-only covariate.
        altered = deepcopy(rows[0])
        altered['per_run_summed_direct_MS1_feature_intensity'][2:] = [1e20, 1e20]
        validate_row(altered, config['ordered_runs'])
        altered['index_precursor_intensity'] *= 2
        with self.assertRaises(ValueError):
            validate_row(altered, config['ordered_runs'])


if __name__ == '__main__':
    unittest.main()
