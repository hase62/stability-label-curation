"""Synthetic replicate curation tests; no source/model data are read."""
import csv
from pathlib import Path
import tempfile
import unittest

from stability_label_curation import replicate_immunopeptidomics as c


def observation(states):
    return {'source_id': 'original:1', 'peptide': 'SYFPEITHI', 'identifications': states}


class DetectionTests(unittest.TestCase):
    def group(self, units):
        return {'group_id': 'sample:group', 'sample': 'sample', 'replicate_type': 'preparation',
                'condition': 'untreated', 'n_available_replicates': len(units),
                'instrument_diagnostic': False, 'repeat_comparison_available': len(units) >= 2,
                'units': [{'unit_id': str(i), 'experiments': unit} for i, unit in enumerate(units)]}

    def test_direct_and_transfer_are_distinct_and_absence_not_dropped(self):
        row = observation({'a': 'direct_msms', 'b': 'transferred', 'c': 'not_identified'})
        result, summary = c.detection_matrix([row], self.group([['a'], ['b'], ['c']]))
        self.assertEqual(result[0]['n_available_replicates'], 3)
        self.assertEqual(result[0]['n_detected_direct'], 1)
        self.assertEqual(result[0]['n_detected_including_transfer'], 2)
        self.assertEqual(result[0]['direct_detection_frequency'], 1/3)
        self.assertEqual(summary['direct_count_distribution_direct_union'], {1: 1})

    def test_transfer_only_union_retained_and_marked_outside_direct_union(self):
        result, summary = c.detection_matrix([observation({'a': 'transferred', 'b': 'not_identified'})], self.group([['a'], ['b']]))
        self.assertEqual(len(result), 1)
        self.assertEqual(summary['reported_union_peptides'], 1)
        self.assertEqual(summary['direct_union_peptides'], 0)
        self.assertFalse(result[0]['direct_union_member'])

    def test_nested_instrument_runs_do_not_become_preparation_replicates(self):
        row = observation({'a1': 'direct_msms', 'a2': 'direct_msms', 'b1': 'transferred', 'b2': 'not_identified'})
        result, _ = c.detection_matrix([row], self.group([['a1', 'a2'], ['b1', 'b2']]))
        self.assertEqual(result[0]['n_available_replicates'], 2)
        self.assertEqual(result[0]['n_detected_direct'], 1)
        self.assertEqual(result[0]['n_detected_including_transfer'], 2)
        self.assertIsNone(result[0]['allele_specific_restriction'])

    def test_no_reported_identification_has_no_union_membership(self):
        result, _ = c.detection_matrix([observation({'a': 'not_identified'})], self.group([['a']]))
        self.assertEqual(result, [])


class SourceTests(unittest.TestCase):
    def parse(self, data):
        config = {'identification_states': {'': 'not_identified', 'By MS/MS': 'direct_msms', 'By matching': 'transferred'}}
        columns = ['Sequence', 'Length', 'Reverse', 'Potential contaminant', 'PEP', 'Score', 'id',
                   'Identification type HLApI_1', 'Identification type HLApII_1', 'Intensity HLApI_1']
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'peptides.txt'
            with path.open('w', newline='') as stream:
                writer = csv.writer(stream, delimiter='\t')
                writer.writerow(columns)
                writer.writerows(data)
            return c.read_peptides(path, 'block', ['HLApI_1', 'HLApII_1'], config)

    def test_class_II_and_flags_never_create_class_I_detections(self):
        rows, report = self.parse([
            ['SYFPEITHI', 9, '', '', '.03', '80', '0', 'By MS/MS', '', '0'],
            ['AAAAAAAAA', 9, '', '', '.01', '50', '1', '', 'By MS/MS', '1000000'],
            ['CCCCCCCCC', 9, '+', '', '.01', '50', '2', 'By MS/MS', '', '1000'],
            ['DDDDDDDDD', 9, '', '+', '.01', '50', '3', 'By MS/MS', '', '1000'],
            ['EEEEEEEE', 8, '', '', '.01', '50', '4', 'By MS/MS', '', '1000']])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['identifications'], {'HLApI_1': 'direct_msms'})
        self.assertEqual(rows[0]['PEP_original'], '.03')  # PEP is not silently used as an FDR threshold.
        self.assertEqual(rows[0]['intensities_original'], {'HLApI_1': '0'})
        self.assertEqual(report['row_counts']['no_class_I_identification'], 1)
        self.assertEqual(report['row_counts']['reverse'], 1)
        self.assertEqual(report['row_counts']['contaminant'], 1)

    def test_unknown_identification_state_fails(self):
        with self.assertRaises(KeyError):
            self.parse([['SYFPEITHI', 9, '', '', '.01', '50', '0', 'UNKNOWN', '', '100']])

    def test_duplicate_base_sequence_not_silently_collapsed(self):
        r = ['SYFPEITHI', 9, '', '', '.01', '50', '0', 'By MS/MS', '', '100']
        with self.assertRaises(ValueError):
            self.parse([r, r])

    def test_class_I_recognition_excludes_class_II(self):
        self.assertTrue(c.is_class_i('HLApI_JY_1'))
        self.assertTrue(c.is_class_i('HLAIp_JY_1'))
        self.assertFalse(c.is_class_i('HLApII_JY_1'))
        self.assertFalse(c.is_class_i('HLAIIp_JY_1'))

    def test_acquisition_rejects_raw_before_network(self):
        with self.assertRaises(ValueError):
            c.acquire(None, 'test.raw', 'https://example.org/test.raw')


if __name__ == '__main__':
    unittest.main()
