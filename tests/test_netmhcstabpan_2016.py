"""Synthetic offline fixtures only; no live network in this suite."""

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import ssl
import unittest
from unittest.mock import patch
from urllib.request import Request

from stability_label_curation import netmhcstabpan_2016 as dtu
from stability_label_curation.__main__ import main
from stability_label_curation.data_sources import SourceRegistry, load_manifest
from stability_label_curation.paths import resolve_paths


class Response(io.BytesIO):
    def __init__(self, payload, *, status=200, headers=None, url=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}
        self.url = url or 'https://services.healthtech.dtu.dk/suppl/immunology/NetMHCstabpan-1.0/Stability.txt'
        self.read_sizes = []

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class TestDTU2016(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repository = Path(__file__).resolve().parents[1]
        self.env = {'CODEX_ROOT': str(self.root)}
        self.paths = resolve_paths(self.env, repository_root=self.repository)
        self.source = load_manifest(paths=self.paths).get(dtu.SOURCE_ID)
        self.local = self.root / 'fixture.txt'
        self.payload = b'HLA Pep Thalf\nHLA-A*02:01 ACDEFGHIK 0.00\nHLA-B*07:02 ACDEFGHIK 1.80\n'
        self.local.write_bytes(self.payload)
        self.network = patch.object(dtu, 'build_opener', side_effect=AssertionError('Network forbidden in normal tests'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def inspect(self, data=None):
        if data is not None:
            self.local.write_bytes(data)
        return dtu.inventory(self.local, source=self.source)

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args, env=self.env)
        return code, out.getvalue(), err.getvalue()

    def download(self, response):
        with patch.object(dtu, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            receipt = dtu.fetch(paths=self.paths)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, self.source.download_url)
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 30)
            return receipt

    def test_published_format_fields_and_line_numbers(self):
        records = list(dtu.iter_records(self.local))
        self.assertEqual(records[0], dtu.Record(2, 'HLA-A*02:01 ACDEFGHIK 0.00\n',
            'HLA-A*02:01', 'ACDEFGHIK', '0.00', Decimal('0.00'), None))
        self.assertEqual(records[1].source_line_number, 3)

    def test_whitespace_and_all_line_endings(self):
        report = self.inspect(b'HLA\tPep\tThalf\r\n\rHLA-A*02:01\tACD 1.20\rHLA-C*03:04   ACDE   2\n')
        self.assertEqual(report['total_lines'], 4)
        self.assertEqual(report['blank_line_count'], 1)
        self.assertEqual([r.source_line_number for r in dtu.iter_records(self.local)], [3, 4])
        self.assertEqual(report['header']['raw_text'], 'HLA\tPep\tThalf')

    def test_zero_positive_negative_preserved(self):
        report = self.inspect(self.payload + b'HLA-C*03:04 ACD -0.10\nHLA-C*03:04 ACE -0.00\n')
        self.assertEqual(report['half_life']['zero'], 2)
        self.assertEqual(report['half_life']['positive'], 1)
        self.assertEqual(report['half_life']['negative'], 1)
        self.assertEqual(report['half_life']['minimum'], '-0.10')
        self.assertEqual(report['half_life']['maximum'], '1.80')
        self.assertNotIn('synthetic', report['half_life'])

    def test_nonfinite_invalid_missing_numbers(self):
        values = ['NaN', 'Infinity', '-Inf', 'sNaN', 'oops', 'NA', '1_0', '１']
        data = 'HLA Pep Thalf\n' + ''.join(f'HLA-A*02:01 ACD {v}\n' for v in values) + 'HLA-A*02:01 ACD\n'
        report = self.inspect(data.encode())
        self.assertEqual(report['parsed_observation_count'], 8)
        self.assertEqual(report['half_life']['non_finite'], 4)
        self.assertEqual(report['half_life']['non_numeric'], 3)
        self.assertEqual(report['half_life']['missing'], 2)
        self.assertEqual(report['malformed_line_count'], 9)
        self.assertEqual([r['line'] for r in report['malformed_lines']], list(range(2, 11)))
        self.assertIsNone(report['half_life']['minimum'])

    def test_unrepresentable_decimal_is_flagged(self):
        record = dtu.parse_record('HLA-A*02:01 ACD 1e999999999999999999999999', 2)
        self.assertEqual(record.numeric_issue, 'non_numeric')

    def test_invalid_utf8_is_flagged_without_rewriting(self):
        payload = b'HLA Pep Thalf\nHLA-A*02:01 ACD\xff 1\n'
        report = self.inspect(payload)
        self.assertEqual(report['noncanonical_peptide_characters'], {'\udcff': [2]})
        self.assertEqual(self.local.read_bytes(), payload)
        json.loads(dtu.json_report(report))

    def test_malformed_columns(self):
        report = self.inspect(b'HLA Pep Thalf\nBAD\nHLA-A*02:01 ACD 1 EXTRA\n')
        self.assertEqual(report['malformed_line_count'], 2)
        self.assertEqual(report['parsed_observation_count'], 0)

    def test_header_mismatch_and_empty(self):
        report = self.inspect(b'HLA-A*02:01 ACD 1\n')
        self.assertFalse(report['header']['matches'])
        self.assertEqual(report['parsed_observation_count'], 1)
        report = self.inspect(b'')
        self.assertEqual(report['total_lines'], 0)
        self.assertIsNone(report['nine_mers']['fraction'])

    def test_length_distribution(self):
        report = self.inspect(self.payload + b'HLA-A*02:01 ACDEFGHI 2\nHLA-C*03:04 ACDEFGHIKL 3\n')
        self.assertEqual(report['counts_by_peptide_length'], {'8': 1, '9': 2, '10': 1})
        self.assertEqual(report['nine_mers'], {'count': 2, 'fraction': 0.5})

    def test_duplicates_and_numeric_conflicts(self):
        data = b'HLA Pep Thalf\nHLA-A*02:01 ACD 1.0\nHLA-A*02:01 ACD 1.0\nHLA-A*02:01\tACD\t1.00\nHLA-A*02:01 ACD 2\nHLA-B*07:02 ACD 0\n'
        report = self.inspect(data)
        self.assertEqual(report['parsed_observation_count'], 5)
        self.assertEqual(report['duplicate_key_count'], 1)
        self.assertEqual(report['exact_duplicate_record_groups'], 1)
        self.assertEqual(report['exact_duplicate_record_excess'], 1)
        self.assertEqual(report['identical_raw_line_groups'], 1)
        self.assertEqual(report['conflicting_repeat_key_count'], 1)
        self.assertEqual(report['conflicting_repeats'][0]['lines'], [2, 3, 4, 5])
        self.assertEqual(report['cross_allele_peptide_count'], 1)
        self.assertEqual(self.local.read_bytes(), data)

    def test_equivalent_decimals_not_conflicting(self):
        report = self.inspect(b'HLA Pep Thalf\nHLA-A*02:01 ACD 1\nHLA-A*02:01 ACD 1.00\n')
        self.assertEqual(report['duplicate_key_count'], 1)
        self.assertEqual(report['conflicting_repeat_key_count'], 0)
        self.assertEqual(report['exact_duplicate_record_groups'], 0)

    def test_loci_and_unexpected_alleles(self):
        report = self.inspect(self.payload + b'HLA-C*03:04 ACD 1\nH-2-Kb ACE 1\nHLA-A0201 ACF 1\n')
        self.assertEqual(report['counts_by_locus'], {'A': 1, 'B': 1, 'C': 1, 'other': 2})
        self.assertEqual(report['unexpected_alleles'], {'H-2-Kb': [5], 'HLA-A0201': [6]})
        self.assertEqual(dtu.classify_locus('HLA-A*02:01:01:02N'), 'A')

    def test_noncanonical_characters(self):
        report = self.inspect(b'HLA Pep Thalf\nHLA-A*02:01 AXBZJUOac* 1\n')
        self.assertEqual(set(report['noncanonical_peptide_characters']), set('XBZJUOac*'))

    def test_exact_checksum_and_deterministic_json(self):
        report = self.inspect()
        expected = hashlib.sha256(self.payload).hexdigest()
        self.assertEqual(dtu.sha256_file(self.local), expected)
        self.assertEqual(report['sha256'], expected)
        self.assertEqual(report['raw_byte_size'], len(self.payload))
        self.assertEqual(dtu.json_report(report), dtu.json_report(self.inspect()))
        self.assertNotIn('retrieved_at_utc', report)

    def test_offline_cli_and_no_writes(self):
        before = sorted(self.root.rglob('*'))
        status, out, err = self.cli(['dtu2016', 'inspect', '--input', str(self.local), '--json'])
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(json.loads(out)['parsed_observation_count'], 2)
        self.assertEqual(before, sorted(self.root.rglob('*')))

    def test_missing_default_input_does_not_download(self):
        self.assertEqual(self.cli(['dtu2016', 'inspect', '--json'])[0], 1)
        self.assertFalse(self.paths.project_data_dir.exists())

    def test_existing_artifact_identity_without_network(self):
        target = self.source.target_path(self.paths)
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing different bytes')
        receipt = dtu.fetch(paths=self.paths)
        self.assertEqual(target.read_bytes(), b'existing different bytes')
        self.assertEqual(receipt['acquisition'], 'existing_artifact_reused')
        self.assertEqual(receipt['local_sha256'], hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertIsNone(receipt['http_status'])
        self.assertIsNone(receipt['retrieved_at_utc'])
        self.assertIsNone(receipt['final_resolved_url'])

    def test_successful_mock_download_receipt_and_bounded_reads(self):
        response = Response(self.payload, headers={'Content-Length': str(len(self.payload)), 'ETag': 'test', 'Last-Modified': 'server-time'})
        receipt = self.download(response)
        self.assertEqual(receipt['acquisition'], 'downloaded')
        self.assertEqual(receipt['http_status'], 200)
        self.assertTrue(receipt['retrieved_at_utc'].endswith('Z'))
        self.assertEqual(receipt['local_sha256'], hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(receipt['publisher_checksum']['status'], 'not_available')
        self.assertEqual(receipt['server_metadata']['etag'], 'test')
        self.assertTrue(all(size == dtu.CHUNK_SIZE for size in response.read_sizes))
        target = self.source.target_path(self.paths)
        self.assertEqual(target.read_bytes(), self.payload)
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_tls_certificate_verification_is_enabled(self):
        with patch.object(dtu, 'build_opener') as opener:
            opener.return_value.open.return_value = Response(self.payload)
            dtu.fetch(paths=self.paths)
            handler = opener.call_args.args[1]
            self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(handler._context.check_hostname)

    def test_publisher_checksum_mismatch_preserves_no_final_file(self):
        registry = SourceRegistry(1, (replace(self.source, expected_sha256='0' * 64),))
        with patch.object(dtu, 'load_manifest', return_value=registry), self.assertRaises(ValueError):
            self.download(Response(self.payload))
        target = self.source.target_path(self.paths)
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()), [])

    def test_source_change_during_inventory_rejected(self):
        original = dtu.parse_record
        def mutate(line, number):
            self.local.write_bytes(self.payload + b'extra')
            return original(line, number)
        with patch.object(dtu, 'parse_record', side_effect=mutate), self.assertRaises(ValueError):
            self.inspect()

    def test_failed_download_cleanup(self):
        response = Response(self.payload)
        response.read = unittest.mock.Mock(side_effect=[b'partial', OSError('connection failed')])
        with self.assertRaises(OSError):
            self.download(response)
        target = self.source.target_path(self.paths)
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()), [])

    def test_content_length_mismatch_and_status(self):
        for response in [Response(self.payload, headers={'Content-Length': '999'}),
                         Response(self.payload, status=206), Response(self.payload, headers={'Content-Length': 'invalid'}),
                         Response(self.payload, headers={'Content-Encoding': 'gzip'})]:
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    self.download(response)
                self.assertFalse(self.source.target_path(self.paths).exists())
                self.assertEqual(list(self.source.target_path(self.paths).parent.iterdir()), [])

    def test_concurrent_existing_file_never_overwritten(self):
        target = self.source.target_path(self.paths)
        response = Response(self.payload)
        original_read = response.read
        def raced_read(size):
            target.write_bytes(b'other writer')
            return original_read(size)
        response.read = raced_read
        with self.assertRaises(FileExistsError):
            self.download(response)
        self.assertEqual(target.read_bytes(), b'other writer')
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_unsafe_target_paths(self):
        for relative in ['../outside/Stability.txt', '/outside/Stability.txt', 'x/../Stability.txt', 'x//Stability.txt', 'x\\Stability.txt']:
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                dtu._target(replace(self.source, target_relative_path=relative), self.paths)

    def test_artifact_and_parent_symlinks(self):
        target = self.source.target_path(self.paths)
        target.parent.mkdir(parents=True)
        target.symlink_to(self.local)
        with self.assertRaises(ValueError):
            dtu.fetch(paths=self.paths)
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(self.root)
        with self.assertRaises((ValueError, OSError)):
            dtu.fetch(paths=self.paths)
        self.assertEqual(self.local.read_bytes(), self.payload)

    def test_project_data_symlink_rejected(self):
        self.paths.data_root.mkdir()
        self.paths.project_data_dir.symlink_to(self.root)
        with self.assertRaises(ValueError):
            dtu.fetch(paths=self.paths)

    def test_input_symlink_rejected(self):
        link = self.root / 'linked.txt'
        link.symlink_to(self.local)
        with self.assertRaises(OSError):
            dtu.inventory(link, source=self.source)

    def test_https_and_redirect_guard(self):
        for url in ['http://services.healthtech.dtu.dk/a', 'https://example.org/a',
                    'https://user:secret@services.healthtech.dtu.dk/a', 'https://services.healthtech.dtu.dk:444/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                dtu._official_https(url)
        with self.assertRaises(ValueError):
            dtu._OfficialRedirects().redirect_request(Request(self.source.download_url), None, 302, '', {}, 'http://example.org')
        with self.assertRaises(ValueError):
            self.download(Response(self.payload, url='https://example.org/a'))

    def test_timeout_validation(self):
        for value in [0, -1, float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                dtu.fetch(paths=self.paths, timeout=value)

    def test_explicit_report_and_no_overwrite(self):
        directory = self.paths.project_runs_dir / 'fixture' / 'reports'
        directory.mkdir(parents=True)
        target = directory / 'inventory.json'
        status, out, err = self.cli(['dtu2016', 'inspect', '--input', str(self.local), '--report', str(target)])
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(target.read_text(), out)
        with self.assertRaises(FileExistsError):
            dtu.write_report(target, {'different': True}, paths=self.paths)
        self.assertEqual(target.read_text(), out)
        self.assertEqual(list(directory.iterdir()), [target])

    def test_unsafe_report_and_symlink(self):
        with self.assertRaises(ValueError):
            dtu.write_report(self.root / 'outside.json', {}, paths=self.paths)
        directory = self.paths.project_runs_dir / 'fixture' / 'reports'
        directory.mkdir(parents=True)
        link = directory / 'linked'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            dtu.write_report(link / 'escape.json', {}, paths=self.paths)
        with self.assertRaises(ValueError):
            dtu.write_report(directory / '..' / 'escape.json', {}, paths=self.paths)

    def test_published_expectations_are_not_local_measurements(self):
        report = self.inspect()
        self.assertEqual(report['published_expectations'], {'basis': 'published_expectation', 'observations': 28166, 'alleles': 75})
        self.assertEqual(report['expectation_checks'], {'observations_match': False, 'alleles_match': False})
        self.assertEqual(report['validation_status'], 'structural_anomalies_flagged')

    def test_existing_read_only_commands_preserved(self):
        for args in [['paths', '--json'], ['doctor'], ['sources', 'validate'], ['sources', 'list', '--json'], ['runs', 'list', '--json']]:
            with self.subTest(args=args):
                self.assertEqual(self.cli(args)[0], 0)


if __name__ == '__main__':
    unittest.main()
