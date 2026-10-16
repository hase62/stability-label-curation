"""Synthetic design mathematics and isolation; no models, outcomes or network."""
from copy import deepcopy
from fractions import Fraction as F
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import el_positive_weighting_design as design
from stability_label_curation.paths import resolve_paths

HLA = 'HLA-B*08:01'


class WeightingDesignTests(unittest.TestCase):
    def records(self):
        return [dict(row_index=str(i), source_row_id=f'id-{i}', resolved_hla=h,
                     original_label=label, predicted_half_life_hours=score)
                for i, (h, label, score) in enumerate([
                    (HLA, '1', '0'), (HLA, '1', '1'), (HLA, '0', '2'),
                    ('HLA-A*02:01', '1', '5'), ('HLA-A*02:01', '0', '6')], 1)]

    def test_unique_midrank_equation_and_endpoints(self):
        self.assertEqual(design.midrank_weights(['1', '2', '3', '4']), [F(13,16), F(15,16), F(17,16), F(19,16)])

    def test_numeric_text_ties(self):
        self.assertEqual(design.midrank_weights(['0', '-0.0', '1', '1.00']), [F(7,8)] * 2 + [F(9,8)] * 2)

    def test_ties_and_exact_mean_conservation(self):
        for values in (['1', '1', '5'], ['0'] * 23 + ['1'] * 9, [str(i) for i in range(101)]):
            weights = design.midrank_weights(values)
            self.assertEqual(sum(weights), len(values))
            self.assertTrue(all(F(3,4) < w < F(5,4) for w in weights))

    def test_singleton(self):
        self.assertEqual(design.midrank_weights(['0']), [F(1)])

    def test_all_tied(self):
        self.assertEqual(design.midrank_weights(['5'] * 4), [F(1)] * 4)

    def test_two_sparse_positives(self):
        self.assertEqual(design.midrank_weights(['0','0.1']), [F(7,8), F(9,8)])

    def test_nonfinite_and_missing_scores_fail(self):
        for value in ('NaN', 'Infinity', '-0.1', '', 'missing', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                design.midrank_weights([value])

    def test_empty_population_fails(self):
        with self.assertRaises(ValueError): design.midrank_weights([])

    def test_decimal_precision_not_float_tie(self):
        self.assertNotEqual(*design.midrank_weights(['1.00000000000000000000001','1.00000000000000000000002']))

    def test_permutation_preserves_multiset_and_sum(self):
        weights = design.midrank_weights([str(i) for i in range(15)])
        ids = [f'id{i}' for i in range(15)]
        result = design.permuted_weights(ids, weights, HLA)
        self.assertEqual(sorted(result), sorted(weights)); self.assertEqual(sum(result), 15)

    def test_local_rng_does_not_advance_global_random(self):
        state = random.getstate()
        design.permuted_weights(['b','a'], [F(7,8),F(9,8)], HLA)
        self.assertEqual(state, random.getstate())

    def test_permutation_stable_after_input_reordering(self):
        ids = ['a','c','b','d']; weights = design.midrank_weights(['1','2','3','4'])
        a = dict(zip(ids, design.permuted_weights(ids, weights, HLA)))
        b = dict(zip(ids[::-1], design.permuted_weights(ids[::-1], weights[::-1], HLA)))
        self.assertEqual(a, b)

    def test_rng_domain_separated_by_hla(self):
        weights = design.midrank_weights([str(i) for i in range(20)])
        ids = [f'id{i}' for i in range(20)]
        self.assertNotEqual(design.permuted_weights(ids, weights, HLA),
                            design.permuted_weights(ids, weights, 'HLA-A*02:01'))

    def test_duplicate_or_missing_identity_rejected(self):
        for ids in (['a','a'], ['a'], ['a','']):
            with self.assertRaises(ValueError): design.permuted_weights(ids, [F(1),F(1)], HLA)

    def test_summary_counts_original_labels_unchanged(self):
        records = self.records(); before = deepcopy(records)
        report = design.summarize(iter(records))
        self.assertEqual(records, before)
        self.assertEqual(report['overall_positive_weights']['n'], 3)
        self.assertEqual(report['overall_positive_weights']['total_weight_exact'], '3')
        self.assertEqual(report['original_negative_count'], 2)
        self.assertEqual(report['negative_loss_weight'], 1)

    def test_per_hla_mean_and_sparse_flag(self):
        report = design.summarize(self.records())
        for group in report['by_HLA'].values():
            self.assertEqual(group['mean_exact'], '1'); self.assertTrue(group['small_positive_group_below10'])

    def test_no_individual_weights_or_labels_exported(self):
        report = design.summarize(self.records())
        self.assertFalse(report['row_weights_exported']); self.assertFalse(report['labels_modified'])
        self.assertNotIn('rows', report); self.assertNotIn('id-1', json.dumps(report))
        self.assertEqual(report['status'], 'design_only_training_approval_pending')

    def test_order_and_mutant_safeguards(self):
        for mode in ('duplicate', 'reverse', 'mutant', 'unknown', 'label'):
            records = self.records()
            if mode == 'duplicate': records[1]['row_index'] = '1'
            if mode == 'reverse': records.reverse()
            if mode == 'mutant': records[0]['resolved_hla'] = 'HLA-B*08:01(C67S)'
            if mode == 'unknown': records[0]['resolved_hla'] = 'unknown'
            if mode == 'label': records[0]['original_label'] = '0.5'
            with self.subTest(mode=mode), self.assertRaises(ValueError): design.summarize(records)

    def test_missing_positive_hla_fails_closed(self):
        records = self.records(); records[0]['resolved_hla'] = 'HLA-A*01:01'; records[0]['original_label'] = '0'
        with self.assertRaises(ValueError): design.summarize(records)

    def test_weight_ess(self):
        result = design.describe_weights([F(7,8), F(9,8)])
        self.assertAlmostEqual(result['weight_ESS'], 128/65)
        self.assertEqual(result['mean_exact'], '1')

    def test_unit_weights_noop_arithmetic(self):
        losses = [F(2), F(3), F(5)]
        self.assertEqual(sum(w*l for w,l in zip([1]*3,losses))/3, sum(losses)/3)
        # Fixed denominator preserves negative coefficients; weight-sum division would not.
        self.assertEqual((F(7,8)*2 + 16*3)/17, F(199,68))

    def test_deterministic_aggregate_json_no_network(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network')):
            self.assertEqual(design.raw.json_report(design.summarize(self.records())),
                             design.raw.json_report(design.summarize(self.records())))

    def test_default_execute_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = resolve_paths({'CODEX_ROOT': tmp})
            with patch.object(design, 'inspect', return_value=({'design': True}, [])):
                self.assertEqual(design.execute('fixture.json', paths=paths), {'design': True})
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_replay_requires_run(self):
        with patch.object(design, 'inspect', return_value=({}, [])):
            with self.assertRaises(ValueError): design.execute('fixture.json', verify_existing=True)

    def test_configuration_rejects_unapproved_changed_strength(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp).resolve()/'config.json'
            config.write_text(json.dumps({'version': design.VERSION, 'schema_version':1, 'strength':'0.6',
                                         'seed':42, 'training_approval':'decision_pending'}))
            with self.assertRaises(ValueError): design.load_inputs(config)

    def test_parent_configuration_sha_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); repo = root/'repo'; repo.mkdir()
            (repo/'parent.json').write_text('{}')
            config = repo/'config.json'
            config.write_text(json.dumps({'version': design.VERSION, 'schema_version':1, 'strength':'0.5',
                'seed':42, 'training_approval':'decision_pending',
                'parent_analysis_configuration': {'relative_path':'parent.json','sha256':'0'*64}}))
            paths = resolve_paths({'CODEX_ROOT':str(root/'storage')}, repository_root=repo)
            before = (repo/'parent.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'SHA256'): design.load_inputs(config, paths)
            self.assertEqual((repo/'parent.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
