"""Focused tests of the outcome-sealing and frozen-identity gates."""
import io
import unittest
import zipfile

from stability_label_curation import bigmhc_independent_preflight as gates


class SourceHeaderTests(unittest.TestCase):
    def archive(self, name, data):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(name, data)
        return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))

    def test_reads_only_header_despite_malformed_outcome_records(self):
        with self.archive('datasets/im_test.csv', b'mhc,pep,tgt,score\n"malformed SEALED data') as archive:
            self.assertEqual(gates.source_header(archive, 'datasets/im_test.csv'), ['mhc', 'pep', 'tgt', 'score'])

    def test_other_benchmark_member_is_forbidden(self):
        with self.archive('iedb.csv', b'mhc,pep,tgt\n') as archive:
            with self.assertRaises(ValueError):
                gates.source_header(archive, 'iedb.csv')

    def test_missing_member_stops(self):
        with self.archive('im_test.csv', b'mhc,pep,tgt\n') as archive:
            with self.assertRaises(ValueError):
                gates.source_header(archive, 'datasets/im_test.csv')

    def test_ambiguous_header_stops_before_rows(self):
        with self.archive('im_test.csv', b'mhc,pep,tgt,tgt\nSEALED\n') as archive:
            with self.assertRaises(ValueError):
                gates.source_header(archive, 'im_test.csv')

    def test_unbounded_header_stops(self):
        with self.archive('im_test.csv', b'mhc,pep,tgt,' + b'x' * 65536 + b'\nSEALED\n') as archive:
            with self.assertRaises(ValueError):
                gates.source_header(archive, 'im_test.csv')

    def test_file_map_hash_is_order_invariant_and_identity_sensitive(self):
        self.assertEqual(gates.file_map_digest({'a': '1', 'b': '2'}),
                         gates.file_map_digest({'b': '2', 'a': '1'}))
        self.assertNotEqual(gates.file_map_digest({'a': '1'}), gates.file_map_digest({'a': '2'}))


if __name__ == '__main__':
    unittest.main()
