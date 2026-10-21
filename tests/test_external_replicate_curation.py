"""Focused Task 2.30A acquisition, identification and nested-replicate tests."""
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from stability_label_curation.paths import resolve_paths
from stability_label_curation.external_replicate_curation import (
    FTPSRanges, acquire, build_matrices, direct_identification,
    extract_processed_member, positive_intensity, tsv_rows, zip_inventory,
)


class AcquisitionTests(unittest.TestCase):
    def test_raw_payloads_rejected_before_network(self):
        for url in ['https://example.org/a.raw', 'https://example.org/download?file=a%2ERAW', 'https://example.org/a.mzML']:
            with patch('urllib.request.urlopen') as network:
                with self.assertRaises(ValueError):
                    acquire(resolve_paths(), 'forbidden.bin', url)
                network.assert_not_called()

    def test_remote_ranges_cache_and_budget_without_network(self):
        reader = FTPSRanges(host='example.org', user='u', password='unused', remote='/a.zip', size=1000, byte_budget=10)
        reader.cache[(100, 20)] = bytes(range(20))
        reader.seek(105)
        self.assertEqual(reader.read(4), bytes(range(5, 9)))
        self.assertEqual(reader.received, 0)
        reader.seek(-1, 2)
        with self.assertRaises(ValueError):
            reader.seek(-1001, 2)
        reader.seek(0)
        with patch('ftplib.FTP_TLS') as network:
            with self.assertRaises(ValueError):
                reader.read()
            network.assert_not_called()

    def test_zip_index_does_not_read_raw_payload(self):
        class Tracked(io.BytesIO):
            consumed = 0
            def read(self, n=-1):
                value = super().read(n)
                self.consumed += len(value)
                return value
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as z:
            z.writestr('large.raw', b'R'*100000)
            z.writestr('processed/evidence.txt', b'id\tSequence\n1\tAAAAAAAAA\n')
        tracked = Tracked(buffer.getvalue())
        inventory = zip_inventory(tracked)
        self.assertEqual(len(inventory), 2)
        self.assertLess(tracked.consumed, 1000)

    def test_only_selected_processed_member_extracted_and_crc_checked(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('processed/evidence.txt', b'original evidence')
            archive.writestr('file.raw', b'RAW')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'evidence.txt'
            receipt = extract_processed_member(io.BytesIO(buffer.getvalue()), 'processed/evidence.txt', target)
            self.assertEqual(target.read_bytes(), b'original evidence')
            self.assertEqual(receipt['bytes'], 17)
            with self.assertRaises(ValueError):
                extract_processed_member(io.BytesIO(buffer.getvalue()), 'file.raw', Path(directory)/'bad')
        damaged = bytearray(buffer.getvalue())
        start = damaged.index(b'original evidence')
        damaged[start] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'bad.txt'
            with self.assertRaises(zipfile.BadZipFile):
                extract_processed_member(io.BytesIO(damaged), 'processed/evidence.txt', target)
            self.assertFalse(target.exists())

    def test_BOM_and_original_table_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'summary.txt'
            target.write_text('\ufeffRaw.file\tExperiment\nr1\tDBC1 w6/32 Exp1\n')
            self.assertEqual(tsv_rows(target), [{'Raw.file': 'r1', 'Experiment': 'DBC1 w6/32 Exp1'}])


class IdentificationTests(unittest.TestCase):
    def test_minimum_Hamming_and_witness_against_brute_force(self):
        from stability_label_curation.replicate_stability_association import nearest_hamming
        references = ['AAAAAAAAA', 'AAAAAAAAV', 'VVVVVVVVV']
        for peptide in ['AAAAAAAAA', 'AAAAAAAVV', 'AAAAAAVVV', 'LLLLLLLLL']:
            expected = min((sum(a != b for a, b in zip(peptide, r)), r) for r in references)
            self.assertEqual(nearest_hamming(peptide, references), expected)

    def test_direct_and_second_peptide_require_msms_evidence(self):
        allowed = ['MSMS', 'MULTI-MSMS', 'MULTI-SECPEP']
        for kind in allowed:
            self.assertTrue(direct_identification({'Type': kind, 'MS/MS count': '2', 'MS/MS IDs': '3;4'}, allowed))
        self.assertFalse(direct_identification({'Type': 'MULTI-MATCH', 'MS/MS count': '0', 'MS/MS IDs': ''}, allowed))
        for row in [{'Type': 'MULTI-SECPEP', 'MS/MS count': '0', 'MS/MS IDs': ''},
                    {'Type': 'MULTI-MATCH', 'MS/MS count': '1', 'MS/MS IDs': '4'},
                    {'Type': 'unknown', 'MS/MS count': '1', 'MS/MS IDs': '4'}]:
            with self.assertRaises(ValueError):
                direct_identification(row, allowed)

    def test_missing_or_zero_intensity_never_imputed_as_abundance(self):
        for value in ['', 'NA', '0', '-1', 'NaN', 'inf']:
            self.assertIsNone(positive_intensity(value))
        self.assertEqual(positive_intensity('2.5e5'), 250000)


class NestedReplicateTests(unittest.TestCase):
    def setUp(self):
        self.runs = [{'raw_file': raw} for raw in ['index1', 'index2', 'follow1', 'follow2']]

    def observation(self, identity, raw, intensity, *, peptide='AAAAAAAAA', unmodified=True):
        return {'source_observation_id': identity, 'raw_file': raw, 'sequence': peptide,
                'modified_sequence': '_'+peptide+'_' if unmodified else '_(Acetyl)'+peptide+'_',
                'accepted_source_direct': True, 'unmodified_canonical_9mer': unmodified,
                'positive_MS1_feature_intensity': intensity}

    def test_technical_measurements_do_not_become_biological_replicates(self):
        observations = [self.observation(str(i), raw, 10) for i, raw in enumerate(['index1', 'index2'])]
        rows, _ = build_matrices(observations, self.runs)
        self.assertEqual(rows[0]['n_technical_detections'], 2)
        self.assertEqual(rows[0]['n_biological_clone_detections'], 1)
        self.assertEqual(rows[0]['biological_followup_direct_detection'], 0)

    def test_index_intensity_uses_only_index_features_once(self):
        observations = [self.observation('a', 'index1', 10), self.observation('b', 'index1', 20),
                        self.observation('c', 'index2', 50), self.observation('d', 'follow1', 900000),
                        self.observation('e', 'follow2', 800000)]
        rows, _ = build_matrices(observations, self.runs)
        self.assertEqual(rows[0]['index_precursor_intensity'], 40)
        self.assertEqual(rows[0]['source_observation_ids_by_run'][0], ['a', 'b'])
        self.assertEqual(rows[0]['followup_nested_technical_count'], 2)
        self.assertEqual(rows[0]['biological_followup_direct_detection'], 1)

    def test_missing_intensity_retains_detected_index_peptide(self):
        rows, _ = build_matrices([self.observation('a', 'index2', None)], self.runs)
        self.assertTrue(rows[0]['primary_index_eligible'])
        self.assertIsNone(rows[0]['index_precursor_intensity'])
        self.assertEqual(rows[0]['direct_detection'], [0, 1, 0, 0])

    def test_modified_only_and_followup_only_are_not_index_primary(self):
        observations = [self.observation('a', 'index1', 10, unmodified=False),
                        self.observation('b', 'follow1', 20, peptide='VVVVVVVVV')]
        rows, molecular = build_matrices(observations, self.runs)
        self.assertEqual(len(molecular), 2)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['primary_index_eligible'])


if __name__ == '__main__':
    unittest.main()
