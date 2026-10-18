"""Small opaque fixtures exercise packaging and the existing authenticated restorer."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability_label_curation import artifact_restore as restore
from stability_label_curation import checkpoint_package as package


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


class Response(io.BytesIO):
    def __init__(self, blob):
        super().__init__(blob)
        self.status = 200
        self.headers = {'Content-Length': str(len(blob)), 'Content-Type': 'application/gzip'}

    def geturl(self):
        return 'https://www.dropbox.com/fixture'


class CheckpointPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.paths = restore.storage(self.root / 'original')
        self.registry = self.root / 'registry.json'
        self.registry.write_bytes(package.json_bytes({'schema_version': 1,
                                  'project_name': 'stability-label-curation', 'artifacts': []}))
        self.long_name = '12_' + 'long_layer_name.' * 8 + 'weight.lyr'
        files = [('run-a/checkpoints/el/' + self.long_name, b'opaque weights'),
                 ('run-a/checkpoints/el/im/overlay.lyr', b'opaque IM'),
                 ('run-b/A/checkpoints/el/' + self.long_name, b'opaque weights')]
        self.checkpoints = [self.write(name, blob) for name, blob in files]
        inventory = {'schema_version': 1, 'checkpoint_files': self.checkpoints,
                     'unique_checkpoint_hashes': 2, 'runs': {},
                     'local_duplicate_checkpoint_groups': [
                         {'relative_paths': [files[0][0], files[2][0]], 'sha256': sha(files[0][1])}]}
        specs = []
        for run, prefix, count in [('run-a', 'checkpoints', 2), ('run-b', 'A/checkpoints', 1)]:
            selected = {m['relative_path'][len(run)+1:]: m['sha256']
                        for m in self.checkpoints if m['relative_path'].startswith(run + '/')}
            selected['predictions/excluded.csv'] = sha(b'excluded')
            docs = {'manifest.json': {'run_id': run, 'git': {'commit_sha': 'a' * 40},
                                     'configuration': {'random_seed': 42}},
                    'reports/outputs.json': {'outputs': selected, 'identical': True}}
            metadata = {}
            for name, doc in docs.items():
                item = self.write(run + '/' + name, package.json_bytes(doc))
                metadata[name] = {k: item[k] for k in ('sha256', 'size_bytes')}
            inventory['runs'][run] = {'metadata': metadata}
            specs.append({'relative_path': run, 'metadata': list(docs),
                          'checkpoint_manifest': 'reports/outputs.json', 'checkpoint_map_key': 'outputs',
                          'checkpoint_prefix': prefix, 'expected_checkpoint_count': count})
        self.inventory = self.write('audit/reports/checkpoints.json', package.json_bytes(inventory))
        self.plan = {'schema_version': 1, 'artifact_id': 'fixture-checkpoints',
                     'filename': 'fixture-checkpoints.tar.gz', 'producing_task': 'fixture',
                     'approved_source_commit': 'a' * 40,
                     'inventory': self.inventory, 'runs': specs,
                     'alias_confirmation': {'relative_path': 'run-b/reports/outputs.json', 'key': 'identical'},
                     'known_limitations': ['Interrupted optimizer/RNG state unavailable'],
                     'locator': {'environment_variable': 'SLC_FIXTURE_CHECKPOINT_URL',
                                 'allowed_hosts': ['www.dropbox.com']}}
        self.originals = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                          for p in self.paths.project_runs_dir.rglob('*') if p.is_file()}
        self.net = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No real network'))
        self.net.start()
        self.addCleanup(self.net.stop)

    def write(self, name, blob):
        record = package.mapping(name, sha(blob), len(blob))
        path = restore.destination(record, self.paths)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return record

    def build(self):
        receipt = package.package(self.plan, self.paths, registry_path=self.registry)
        artifact = restore.load_registry(self.registry)['fixture-checkpoints']
        return receipt, artifact

    def assert_originals_unchanged(self):
        for path, (blob, mtime) in self.originals.items():
            self.assertEqual(path.read_bytes(), blob)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_selection_uses_manifests_without_opening_models(self):
        original = package.raw._read_file
        def read(path):
            self.assertNotEqual(Path(path).suffix, '.lyr')
            return original(path)
        with patch.object(package.raw, '_read_file', side_effect=read):
            selected = package.select(self.plan, self.paths)
        self.assertEqual(selected['unique_checkpoint_count'], 2)
        self.assertEqual(selected['logical_checkpoint_count'], 3)
        self.assertEqual(len(selected['aliases']), 1)
        self.assertFalse(self.paths.project_data_dir.exists())

    def test_package_exact_bytes_long_names_and_portable_restore_with_alias(self):
        receipt, artifact = self.build()
        archive = self.paths.project_data_dir / receipt['archive_relative_path']
        self.assertEqual(sha(archive.read_bytes()), receipt['sha256'])
        self.assertEqual(archive.stat().st_size, receipt['size_bytes'])
        self.assertEqual(artifact['external_publication'], 'pending')
        self.assertNotIn('url', artifact['locator'])
        with tarfile.open(archive) as bundle:
            entries = bundle.getmembers()
            self.assertTrue(all(m.isreg() and not m.pax_headers for m in entries))
            self.assertEqual(sum(m.name.endswith('.lyr') for m in entries), 2)
            self.assertFalse(any('predictions/' in m.name for m in entries))
            for member in artifact['members']:
                self.assertEqual(sha(bundle.extractfile(member['archive_path']).read()), member['sha256'])
            embedded = json.load(bundle.extractfile(artifact['package_manifest']['archive_path']))
            self.assertEqual(embedded['aliases'], artifact['aliases'])
        clean = restore.storage(self.root / 'recovered')
        opener = SimpleNamespace(open=lambda *a, **k: Response(archive.read_bytes()))
        with patch.dict('os.environ', {'SLC_FIXTURE_CHECKPOINT_URL': 'https://www.dropbox.com/fixture'}):
            result = restore.restore(artifact, clean, opener=opener)
        self.assertTrue(result['status']['complete'])
        self.assertEqual(len(result['published']), len(artifact['members']) + 1)
        for member in self.checkpoints:
            self.assertEqual(restore.file_status(restore.destination(member, clean), member), 'verified')
        alias = artifact['aliases'][0]
        canonical = next(m for m in artifact['members'] if m['archive_path'] == alias['source_archive_path'])
        a, c = restore.destination(alias, clean), restore.destination(canonical, clean)
        self.assertNotEqual(a.stat().st_ino, c.stat().st_ino)
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(restore.restore(artifact, clean)['action'], 'all_destinations_reused')
            a.unlink()  # Only a disposable synthetic restored alias.
            self.assertTrue(restore.restore(artifact, clean)['status']['complete'])
        self.assert_originals_unchanged()

    def test_existing_local_package_restores_all_aliases_without_network(self):
        receipt, artifact = self.build()
        source = self.paths.project_data_dir / receipt['archive_relative_path']
        clean = restore.storage(self.root / 'local-package-recovery')
        local = restore.package_path(artifact, clean)
        local.parent.mkdir(parents=True); local.write_bytes(source.read_bytes())
        with patch.dict('os.environ', {}, clear=True):
            result = restore.restore(artifact, clean, opener=SimpleNamespace(
                open=lambda *a, **k: self.fail('Existing package must not be downloaded')))
        self.assertTrue(result['status']['complete'])
        self.assertEqual(result['download']['bytes_downloaded'], 0)
        self.assertFalse(restore.cache_path(artifact, clean).exists())
        for member in restore.restoration_members(artifact):
            self.assertEqual(restore.file_status(restore.destination(member, clean), member), 'verified')
        self.assert_originals_unchanged()

    def test_authenticated_inventory_and_manifest_disagreements_rejected(self):
        bad = deepcopy(self.plan)
        bad['inventory']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Provenance'):
            package.select(bad, self.paths)
        inventory = json.loads(restore.destination(self.inventory, self.paths).read_bytes())
        inventory['checkpoint_files'][0]['sha256'] = '0' * 64
        bad['inventory'] = self.write(self.inventory['relative_path'], package.json_bytes(inventory))
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            package.select(bad, self.paths)

    def test_unsafe_provenance_reference_rejected_before_read(self):
        for relative in ('../outside', '/absolute', 'a\\b'):
            bad = deepcopy(self.plan)
            bad['inventory']['relative_path'] = relative
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'Unsafe'):
                package.select(bad, self.paths)

    def test_missing_alias_evidence_or_wrong_counts_rejected(self):
        bad = deepcopy(self.plan)
        bad['runs'][0]['expected_checkpoint_count'] = 7
        with self.assertRaisesRegex(ValueError, 'count'):
            package.select(bad, self.paths)
        inventory = json.loads(restore.destination(self.inventory, self.paths).read_bytes())
        inventory['local_duplicate_checkpoint_groups'] = []
        bad = deepcopy(self.plan)
        bad['inventory'] = self.write(self.inventory['relative_path'], package.json_bytes(inventory))
        with self.assertRaisesRegex(ValueError, 'Alias lacks'):
            package.select(bad, self.paths)

    def test_corrupted_checkpoint_never_published_or_registered(self):
        path = restore.destination(self.checkpoints[0], self.paths)
        path.write_bytes(b'X' * self.checkpoints[0]['size_bytes'])
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.build()
        self.assertEqual(json.loads(self.registry.read_text())['artifacts'], [])
        self.assertFalse(list(self.paths.project_data_dir.rglob('*.partial')))
        self.assertFalse(list(self.paths.project_data_dir.rglob('*.tar.gz')))

    def test_symlink_checkpoint_rejected(self):
        path = restore.destination(self.checkpoints[0], self.paths)
        outside = self.root / 'outside'
        outside.write_bytes(path.read_bytes())
        path.unlink()  # Replace only our synthetic fixture with a test symlink.
        path.symlink_to(outside)
        with self.assertRaises(OSError):
            self.build()
        self.assertFalse(list(self.paths.project_data_dir.rglob('*.tar.gz')))

    def test_package_rerun_preserves_existing_archive_and_registry(self):
        receipt, artifact = self.build()
        before = self.registry.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already registered'):
            self.build()
        self.assertEqual(self.registry.read_bytes(), before)
        self.assert_originals_unchanged()
        self.assertEqual(restore.file_status(self.paths.project_data_dir / receipt['archive_relative_path'], artifact), 'verified')

    def test_unrelated_registry_temporary_file_is_preserved(self):
        temporary = self.registry.with_name(self.registry.name + '.checkpoint-package.partial')
        temporary.write_bytes(b'pre-existing unrelated file')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.build()
        self.assertEqual(temporary.read_bytes(), b'pre-existing unrelated file')
        self.assertFalse(self.paths.project_data_dir.exists())
        self.assert_originals_unchanged()

    def test_identical_fixture_inputs_produce_identical_archive(self):
        first, artifact = self.build()
        other = restore.storage(self.root / 'same-inputs')
        for path, (blob, _) in self.originals.items():
            target = other.project_runs_dir / path.relative_to(self.paths.project_runs_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        registry = self.root / 'other-registry.json'
        registry.write_bytes(package.json_bytes({'schema_version': 1,
                             'project_name': 'stability-label-curation', 'artifacts': []}))
        second = package.package(self.plan, other, registry_path=registry)
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['size_bytes'], second['size_bytes'])

    def test_transport_accepts_combined_package_size_but_rejects_above_bound(self):
        _, artifact = self.build()
        for size, accepted in [(600 * 1024**2, True), (2 * 1024**3 + 1, False)]:
            modified = {**artifact, 'size_bytes': size}
            self.registry.write_bytes(package.json_bytes({'schema_version': 1,
                                      'project_name': 'stability-label-curation', 'artifacts': [modified]}))
            if accepted:
                self.assertEqual(restore.load_registry(self.registry)[artifact['artifact_id']]['size_bytes'], size)
            else:
                with self.assertRaisesRegex(ValueError, 'identity'):
                    restore.load_registry(self.registry)

    def test_alias_collision_rejected_before_fetch(self):
        _, artifact = self.build()
        clean = restore.storage(self.root / 'recovered')
        alias = artifact['aliases'][0]
        path = restore.destination(alias, clean)
        path.parent.mkdir(parents=True)
        path.write_bytes(b'collision')
        with self.assertRaisesRegex(ValueError, 'wrong-hash'):
            restore.restore(artifact, clean)
        self.assertEqual(path.read_bytes(), b'collision')

    def test_invalid_alias_references_hashes_destinations_and_cycles(self):
        _, artifact = self.build()
        for update in ({'source_archive_path': 'missing'}, {'sha256': '0' * 64},
                       {'size_bytes': 100}, {'relative_path': '../escape'},
                       {'source_archive_path': artifact['aliases'][0]['archive_path']},
                       {'relative_path': artifact['members'][0]['relative_path'],
                        'archive_path': artifact['members'][0]['archive_path']}):
            broken = deepcopy(artifact)
            broken['aliases'][0].update(update)
            self.registry.write_bytes(package.json_bytes({'schema_version': 1,
                                      'project_name': 'stability-label-curation', 'artifacts': [broken]}))
            with self.subTest(update=update), self.assertRaises(ValueError):
                restore.load_registry(self.registry)

    def test_pending_locator_fails_cleanly_without_writes(self):
        _, artifact = self.build()
        clean = restore.storage(self.root / 'missing-locator')
        with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(ValueError, 'Authorized locator'):
            restore.restore(artifact, clean)
        self.assertFalse(clean.codex_root.exists())

    def test_cli_dryrun_creates_no_data_directories(self):
        plan = self.root / 'plan.json'
        plan.write_bytes(package.json_bytes(self.plan))
        out = io.StringIO()
        with redirect_stdout(out):
            code = package.main(['--dry-run', '--plan', str(plan),
                                 '--workspace-root', str(self.paths.codex_root)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['unique_checkpoint_count'], 2)
        self.assertFalse(self.paths.project_data_dir.exists())


if __name__ == '__main__':
    unittest.main()
