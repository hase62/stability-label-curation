"""Source metadata contract tests; fixtures contain metadata, never observations."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import socket
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from urllib import request

from stability_label_curation.__main__ import main
from stability_label_curation.data_sources import (
    ManifestValidationError, load_manifest, validate_manifest,
)
from stability_label_curation.paths import resolve_paths

MANIFEST = Path(__file__).resolve().parents[1] / 'configs/data_sources.toml'


class TestDataSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.paths = resolve_paths({}, home=self.base / 'home', repository_root=self.base / 'repo')
        self.fixture = {'schema_version': 1, 'sources': [{
            'source_id': 'test_source', 'title': 'Synthetic metadata fixture',
            'source_type': 'experimental_dataset', 'research_role': 'primary_kinetic_candidate',
            'species_scope': 'human_hla_i', 'measurement_type': 'kinetic_half_life',
            'provenance_status': 'row_audit_required', 'landing_url': 'https://example.org/source',
            'notes': 'Metadata fixture only; no scientific observations.',
        }]}

    def validate(self, field=None, value=None):
        document = deepcopy(self.fixture)
        if field is not None:
            document['sources'][0][field] = value
        return validate_manifest(document, paths=self.paths)

    def cli(self, args):
        out, err = StringIO(), StringIO()
        with patch('stability_label_curation.__main__.resolve_paths', return_value=self.paths), \
                redirect_stdout(out), redirect_stderr(err):
            status = main(args, env={})
        return status, out.getvalue(), err.getvalue()

    def test_committed_manifest(self):
        registry = load_manifest(MANIFEST, paths=self.paths)
        self.assertEqual(registry.schema_version, 1)
        self.assertEqual(len(registry.sources), 7)
        self.assertEqual(registry.get('netmhcstabpan_2016').expected_record_count, 28166)
        self.assertEqual(registry.get('netmhcstab_2013').expected_allele_count, 10)
        self.assertEqual(registry.get('jappe_2020').measurement_type, 'thermal_melting_temperature')
        self.assertEqual(registry.get('spearmint_stability_audit').research_role, 'audit_only')
        bigmhc = registry.get('bigmhc_v4')
        self.assertEqual(bigmhc.artifact_name, 'datasets.zip')
        self.assertEqual(bigmhc.expected_sha256, '0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa')
        self.assertIsNone(bigmhc.download_url)

    def test_unique_ids_and_duplicate_rejection(self):
        registry = load_manifest(MANIFEST, paths=self.paths)
        self.assertEqual(len({s.source_id for s in registry.sources}), 7)
        self.fixture['sources'].append(deepcopy(self.fixture['sources'][0]))
        with self.assertRaisesRegex(ManifestValidationError, 'duplicate source_id'):
            self.validate()

    def test_required_metadata_types(self):
        for field, value in [('title', ''), ('notes', 3), ('source_id', 'Unstable ID'),
                             ('landing_url', 'unknown'), ('columns', ['ok', 3]),
                             ('expected_record_count', True), ('title', 'unknown')]:
            with self.subTest(field=field, value=value), self.assertRaises(ManifestValidationError):
                self.validate(field, value)

    def test_missing_required_fields(self):
        for field in tuple(self.fixture['sources'][0]):
            document = deepcopy(self.fixture)
            del document['sources'][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(ManifestValidationError, 'missing required fields.*' + field):
                validate_manifest(document, paths=self.paths)

    def test_invalid_enums(self):
        for field in ['source_type', 'research_role', 'species_scope', 'measurement_type']:
            with self.subTest(field=field), self.assertRaisesRegex(ManifestValidationError, field):
                self.validate(field, 'unsupported')

    def test_unknown_provenance_status(self):
        with self.assertRaisesRegex(ManifestValidationError, 'provenance_status'):
            self.validate('provenance_status', 'guessed')
        self.assertEqual(self.validate('provenance_status', 'unknown').sources[0].provenance_status, 'unknown')
        self.validate('provenance_status', 'not_yet_verified')

    def test_incompatible_roles_and_measurements(self):
        for field, value in [('measurement_type', 'thermal_melting_temperature'),
                             ('measurement_type', 'synthetic'), ('measurement_type', 'prediction_only'),
                             ('source_type', 'model_reference'), ('source_type', 'synthetic_dataset'),
                             ('research_role', 'downstream_immunogenicity'), ('species_scope', 'mouse'),
                             ('species_scope', 'rat')]:
            with self.subTest(field=field, value=value), self.assertRaises(ManifestValidationError):
                self.validate(field, value)
        row = self.fixture['sources'][0]
        row.update(source_type='prediction_dataset', research_role='audit_only')
        with self.assertRaisesRegex(ManifestValidationError, 'prediction_only'):
            self.validate()
        row.update(source_type='synthetic_dataset')
        with self.assertRaisesRegex(ManifestValidationError, 'synthetic'):
            self.validate()
        row.update(source_type='model_reference')
        with self.assertRaisesRegex(ManifestValidationError, 'experimental'):
            self.validate()

    def test_malformed_sha256(self):
        for checksum in ['abc', 'g' * 64, 'a' * 63, 'a' * 65, 'not_yet_verified']:
            with self.subTest(checksum=checksum), self.assertRaises(ManifestValidationError):
                self.validate('expected_sha256', checksum)

    def test_artifact_evidence_required(self):
        for field, value in [('expected_sha256', 'a' * 64), ('download_url', 'https://example.org/file.txt')]:
            with self.subTest(field=field), self.assertRaisesRegex(ManifestValidationError, 'requires'):
                self.validate(field, value)
        row = self.fixture['sources'][0]
        row.update(artifact_name='file.txt', target_relative_path='source/file.txt',
                   expected_sha256='a' * 64, evidence_urls=[], verification_notes='Fixture evidence')
        with self.assertRaisesRegex(ManifestValidationError, 'nonempty evidence_urls'):
            self.validate()

    def test_path_traversal_rejection(self):
        for target in ['../file.txt', 'source/../../file.txt', 'source/../file.txt',
                       'source\\..\\file.txt', '.', 'source//file.txt', 'source/./file.txt']:
            with self.subTest(target=target), self.assertRaisesRegex(ManifestValidationError, 'target_relative_path'):
                self.validate('target_relative_path', target)

    def test_absolute_path_rejection(self):
        for target in ['/data/file.txt', 'C:/data/file.txt', 'C:\\data\\file.txt',
                       '\\\\server\\data\\file.txt', 'C:file.txt']:
            with self.subTest(target=target), self.assertRaisesRegex(ManifestValidationError, 'target_relative_path'):
                self.validate('target_relative_path', target)

    def test_target_storage_and_symlink_escape(self):
        row = self.fixture['sources'][0]
        row.update(artifact_name='file.txt', target_relative_path='source/file.txt')
        source = self.validate().get('test_source')
        self.assertEqual(source.target_path(self.paths), self.paths.project_data_dir / 'source/file.txt')
        self.paths.project_data_dir.mkdir(parents=True)
        outside = self.base / 'outside'
        outside.mkdir()
        (self.paths.project_data_dir / 'source').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ManifestValidationError, 'escapes project data storage'):
            self.validate()

    def test_deterministic_listing(self):
        document = tomllib.loads(MANIFEST.read_text())
        first = validate_manifest(document, paths=self.paths)
        document['sources'].reverse()
        second = validate_manifest(document, paths=self.paths)
        self.assertEqual(first.as_dict(), second.as_dict())
        ids = [source.source_id for source in first.list_sources()]
        self.assertEqual(ids, sorted(ids))

    def test_lookup(self):
        registry = load_manifest(MANIFEST, paths=self.paths)
        self.assertEqual(registry.get('netmhcstabpan_2016').columns, ('HLA', 'Pep', 'Thalf'))
        with self.assertRaisesRegex(ManifestValidationError, 'Unknown source_id'):
            registry.get('missing')

    def test_json_serialization(self):
        registry = load_manifest(MANIFEST, paths=self.paths)
        self.assertEqual(json.loads(json.dumps(registry.as_dict())), registry.as_dict())
        self.assertEqual(json.loads(json.dumps(registry.get('bigmhc_v4').as_dict())), registry.get('bigmhc_v4').as_dict())

    def test_cli_validation_success_and_failure(self):
        status, output, error = self.cli(['sources', 'validate', '--manifest', str(MANIFEST)])
        self.assertEqual((status, error), (0, ''))
        self.assertIn('7 sources validated', output)
        invalid = self.base / 'invalid.toml'
        invalid.write_text('schema_version = 1\n[[sources]]\nsource_id = "bad"\n')
        status, output, error = self.cli(['sources', '--manifest', str(invalid), 'validate'])
        self.assertEqual((status, output), (1, ''))
        self.assertIn('missing required fields', error)
        status, _, error = self.cli(['sources', 'validate', '--manifest', str(self.base / 'missing.toml')])
        self.assertEqual(status, 1)
        self.assertIn('missing.toml', error)

    def test_cli_list_and_show(self):
        status, output, error = self.cli(['sources', 'list', '--manifest', str(MANIFEST), '--json'])
        self.assertEqual((status, error), (0, ''))
        self.assertEqual(len(json.loads(output)['sources']), 7)
        status, output, error = self.cli(['sources', 'show', 'netmhcstabpan_2016', '--json', '--manifest', str(MANIFEST)])
        self.assertEqual((status, error), (0, ''))
        self.assertEqual(json.loads(output)['measurement_type'], 'kinetic_half_life')
        for command in [['list'], ['show', 'bigmhc_v4']]:
            status, output, error = self.cli(['sources', '--manifest', str(MANIFEST)] + command)
            self.assertEqual((status, error), (0, ''))
            self.assertIn('bigmhc_v4', output)
        status, _, error = self.cli(['sources', 'show', 'missing', '--manifest', str(MANIFEST)])
        self.assertEqual(status, 1)
        self.assertIn('Unknown source_id', error)

    def test_no_filesystem_modification(self):
        manifest = self.base / 'manifest.toml'
        manifest.write_bytes(MANIFEST.read_bytes())
        def snapshot():
            return {str(p): (p.stat().st_mode, p.stat().st_mtime_ns,
                            p.read_bytes() if p.is_file() else None) for p in self.base.rglob('*')}
        before = snapshot()
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected mkdir')), \
                patch.object(Path, 'write_text', side_effect=AssertionError('Unexpected write')), \
                patch.object(Path, 'write_bytes', side_effect=AssertionError('Unexpected write')):
            load_manifest(manifest, paths=self.paths)
            self.cli(['sources', 'validate', '--manifest', str(manifest)])
        self.assertEqual(before, snapshot())

    def test_no_network_dependency(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('Network access')), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('Network access')), \
                patch.object(request, 'urlopen', side_effect=AssertionError('Network access')):
            self.assertEqual(len(load_manifest(MANIFEST, paths=self.paths).sources), 7)
            self.assertEqual(self.cli(['sources', 'validate', '--manifest', str(MANIFEST)])[0], 0)

    def test_strict_schema_and_counts(self):
        for version in [0, 2, True, '1']:
            document = deepcopy(self.fixture)
            document['schema_version'] = version
            with self.subTest(version=version), self.assertRaisesRegex(ManifestValidationError, 'schema_version'):
                validate_manifest(document, paths=self.paths)
        with self.assertRaisesRegex(ManifestValidationError, 'unsupported fields'):
            self.validate('typo', 'bad')
        with self.assertRaisesRegex(ManifestValidationError, 'count_basis'):
            self.validate('expected_record_count', 12)
        for document in [{}, {'schema_version': 1, 'sources': []},
                         {'schema_version': 1, 'sources': ['bad']},
                         dict(self.fixture, extra='bad')]:
            with self.subTest(document=document), self.assertRaises(ManifestValidationError):
                validate_manifest(document, paths=self.paths)

    def test_url_doi_and_basename_validation(self):
        for field, value in [('landing_url', 'ftp://example.org/source'),
                             ('landing_url', 'https://user:password@example.org'),
                             ('landing_url', 'https://example.org:bad'),
                             ('publication_doi', 'invented'), ('target_relative_path', 'source/file.txt')]:
            with self.subTest(field=field), self.assertRaises(ManifestValidationError):
                self.validate(field, value)

    def test_default_manifest_resolution(self):
        paths = resolve_paths({}, home=self.base / 'home', repository_root=MANIFEST.parents[1])
        self.assertEqual(len(load_manifest(paths=paths).sources), 7)

    def test_malformed_toml(self):
        invalid = self.base / 'invalid.toml'
        invalid.write_text('schema_version = [')
        with self.assertRaisesRegex(ManifestValidationError, 'invalid.toml'):
            load_manifest(invalid, paths=self.paths)

    def test_existing_commands_preserved(self):
        status, output, error = self.cli(['paths', '--json'])
        self.assertEqual((status, error), (0, ''))
        self.assertEqual(json.loads(output), self.paths.as_dict())
        self.paths.repository_root.mkdir()
        self.assertEqual(self.cli(['doctor'])[0], 0)
        self.assertFalse(self.paths.project_data_dir.exists())
        self.assertEqual(self.cli(['init-storage'])[0], 0)
        self.assertTrue(self.paths.project_data_dir.is_dir())
        self.assertTrue(self.paths.project_runs_dir.is_dir())


if __name__ == '__main__':
    unittest.main()
