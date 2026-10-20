"""Focused synthetic curation and exact distance tests, with brute-force oracle."""
import csv
import io
import random
import unittest

from stability_label_curation import sequence_hamming as hamming
from stability_label_curation import third_party_hard_split as task


def config():
    return {'source_commit': 'a'*40, 'member': 'screen.tsv', 'source_DOI': 'test-publication',
            'response_mapping': {'yes': 1, '1': 1, 'no': 0, '0': 0},
            'study_DOIs': {'study': 'test-study'}, 'assay': 'experimentally folded pMHC multimer'}


def original(identity='obs1', peptide='SYFPEITHI', response='yes', patient='p1'):
    return {'identity': identity, 'Mut_peptide': peptide, 'HLA_allele': 'HLA-A02:01',
            'response': response, 'Patient': patient, 'Sample': 'sample1', 'cohort': 'study',
            'validation': 'Sufficient', 'Predicted_core': 'AAAAAAAAA'}


def parse(raw):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(raw[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(raw)
    return task.parse_source(stream.getvalue().encode(), config())


class ExactHammingTests(unittest.TestCase):
    def test_packed_distance_equals_unweighted_brute_force(self):
        rng = random.Random(26)
        for _ in range(200):
            left, right = (''.join(rng.choices(hamming.AMINO_ACIDS, k=9)) for _ in range(2))
            self.assertEqual(hamming.decode(hamming.encode(left)), left)
            self.assertEqual(hamming.packed_distance(hamming.encode(left), hamming.encode(right)),
                             sum(a != b for a, b in zip(left, right)))

    def test_index_matches_small_brute_force_including_witnesses(self):
        rng = random.Random(2626)
        for alphabet in ('ACDE', hamming.AMINO_ACIDS):
            reference = {''.join(rng.choices(alphabet, k=9)) for _ in range(180)}
            index = hamming.NearestNineIndex(reference)
            for _ in range(80):
                query = ''.join(rng.choices(alphabet, k=9))
                distance, witness = index.nearest(query)
                expected = min(sum(a != b for a, b in zip(query, r)) for r in reference)
                self.assertEqual(distance, expected)
                self.assertIn(witness, reference)
                self.assertEqual(distance, sum(a != b for a, b in zip(query, witness)))

    def test_zero_through_nine_are_exact_not_capped(self):
        for changes in range(10):
            reference = 'C'*changes + 'A'*(9-changes)
            distance, witness = hamming.NearestNineIndex([reference]).nearest('A'*9)
            self.assertEqual((distance, witness), (changes, reference))

    def test_four_mismatches_spanning_all_blocks_need_fallback(self):
        index = hamming.NearestNineIndex(['CACACACAA'])
        self.assertEqual(index.nearest('AAAAAAAAA')[0], 4)
        self.assertEqual(index.full_scan_queries, 1)

    def test_three_mismatches_spanning_short_blocks_are_found(self):
        index = hamming.NearestNineIndex(['CACACAAAA'])
        self.assertEqual(index.nearest('AAAAAAAAA')[0], 3)
        self.assertEqual(index.full_scan_queries, 0)

    def test_empty_invalid_and_duplicate_references(self):
        self.assertEqual(hamming.NearestNineIndex([]).nearest('AAAAAAAAA'), (None, None))
        index = hamming.NearestNineIndex(['SYFPEITHI', 'SYFPEITHI'])
        self.assertEqual(len(index.codes), 1)
        with self.assertRaises(ValueError):
            index.nearest('AXXXXXXXX')
        with self.assertRaises(ValueError):
            hamming.NearestNineIndex(['AAAAAAAAAA'])


class SourceCurationTests(unittest.TestCase):
    def test_original_assayed_peptide_is_not_replaced_by_predicted_core(self):
        row = parse([original(peptide='SYFPEITHIA')])[0]
        self.assertEqual(row['peptide'], 'SYFPEITHIA')
        self.assertIn('invalid_or_non_ninemer_assayed_peptide', task.compatible(row, {'HLA-A*02:01'}, set()))

    def test_original_outcome_mapping_and_hla_preserved(self):
        rows = parse([original(response='yes'), original('obs2', response='0')])
        self.assertEqual([r['label'] for r in rows], [1, 0])
        self.assertEqual(rows[0]['raw_response'], 'yes')
        self.assertEqual(rows[0]['hla'], 'HLA-A*02:01')
        self.assertEqual(rows[0]['source_line_number'], 2)
        self.assertEqual(rows[1]['source_row_index'], 2)
        self.assertNotEqual(rows[0]['source_id'], rows[1]['source_id'])

    def test_different_patient_outcomes_are_distinct_not_conflicting_copies(self):
        rows = parse([original(), original('obs2', response='no', patient='p2')])
        self.assertEqual(task.conflict_ids(rows), set())
        self.assertEqual(task.describe(rows)['N'], 2)
        self.assertEqual(task.describe(rows)['unique_pairs'], 1)
        self.assertEqual(task.duplicate_diagnostics(rows)['pair']['mixed_outcome_groups'], 1)

    def test_same_original_identity_conflicts_quarantine_both_labels(self):
        rows = parse([original(), original(response='no')])
        conflicts = task.conflict_ids(rows)
        self.assertEqual(conflicts, {'obs1'})
        self.assertTrue(all('conflicting_original_observation_identity' in task.compatible(r, {'HLA-A*02:01'}, conflicts) for r in rows))

    def test_missing_response_and_unsupported_hla_are_not_repaired(self):
        row = parse([original(response='unknown')])[0]
        reasons = task.compatible(row, set(), set())
        self.assertIn('ambiguous_experimental_outcome', reasons)
        self.assertIn('unsupported_or_ambiguous_exact_HLA', reasons)
        self.assertIsNone(row['label'])

    def test_thresholds_nested_with_same_prior_benchmark_exact_exclusion(self):
        rows = [{'minimum_fitting_selection_distance': d,
                 'exact_prior_published_benchmark_peptide': excluded, 'label': label}
                for d, excluded, label in [(1, False, 1), (2, False, 0), (3, True, 1), (3, False, 1), (4, False, 0)]]
        self.assertEqual([len(task.select_threshold(rows, k)) for k in [2, 3, 4]], [3, 2, 1])
        for row in rows:
            row['label'] = 1-row['label']
        self.assertEqual([len(task.select_threshold(rows, k)) for k in [2, 3, 4]], [3, 2, 1])

    def test_patient_and_shared_peptide_dependencies_form_connected_components(self):
        rows = [{'peptide': 'AAAAAAAAA', 'patient': 'p1', 'study_DOI': 's1'},
                {'peptide': 'CCCCCCCCC', 'patient': 'p1', 'study_DOI': 's1'},
                {'peptide': 'CCCCCCCCC', 'patient': 'p2', 'study_DOI': 's2'},
                {'peptide': 'DDDDDDDDD', 'patient': 'p3', 'study_DOI': 's2'}]
        patient = task.components(rows, 'patient')
        self.assertEqual(len(set(patient[:3])), 1)
        self.assertNotEqual(patient[0], patient[3])
        self.assertEqual(len(set(task.components(rows, 'study'))), 1)


if __name__ == '__main__':
    unittest.main()
