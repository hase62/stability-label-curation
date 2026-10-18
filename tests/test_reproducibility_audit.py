"""Inventory tests inspect synthetic metadata only, never scientific observations."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from stability_label_curation import reproducibility_audit as audit
from stability_label_curation.paths import resolve_paths


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.paths=resolve_paths({'CODEX_ROOT':str(self.root/'workspace')},repository_root=self.root/'repo')
        self.paths.repository_root.mkdir()
        self.plan=self.root/'plan.json'
        self.plan.write_text(json.dumps({'groups':[{'group_id':'runs:windows-only','classification':'GAP','Windows_verification_pending':True}]}))
        self.registry=patch.object(audit.restore,'load_registry',return_value={})
        self.registry.start();self.addCleanup(self.registry.stop)

    def write(self,area,relative,blob=b'opaque scientific bytes'):
        root=self.paths.project_data_dir if area=='data' else self.paths.project_runs_dir
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob)
        return p

    def inspect(self):return audit.inspect(paths=self.paths,plan_path=self.plan)

    def test_missing_roots_read_only_and_unknown_windows(self):
        first=self.inspect();second=self.inspect()
        self.assertEqual(first,second);self.assertFalse(self.paths.project_data_dir.exists())
        g=first['artifact_inventory.json']['groups'][0]
        self.assertEqual(g['classification'],'GAP');self.assertEqual(g['local_availability'],'absent_on_Mac')

    def test_opaque_files_hashed_not_interpreted(self):
        blob=b'not a valid ZIP; sealed outcomes remain opaque'
        self.write('data','bigmhc_v4/datasets.zip',blob)
        doc=self.inspect()['artifact_inventory.json']
        self.assertEqual(doc['hashed_regular_files'],1)
        self.assertEqual(doc['file_records'][0]['sha256'],hashlib.sha256(blob).hexdigest())
        self.assertEqual(doc['scientific_rows_parsed'],0);self.assertEqual(doc['sealed_zip_members_opened'],[])

    def test_environment_is_metadata_only_and_audit_excluded(self):
        self.write('data','environments/runtime/library.bin')
        self.write('data','artifacts/cache/new.bin')
        self.write('runs',audit.RUN_ID+'/reports/new.json')
        doc=self.inspect()['artifact_inventory.json']
        self.assertEqual(doc['hashed_regular_files'],0)
        self.assertEqual(doc['physical_totals']['data_files'],1)

    def test_symlinks_not_followed(self):
        p=self.write('data','source/value')
        (p.parent/'link').symlink_to(p)
        doc=self.inspect()['artifact_inventory.json']
        self.assertEqual(doc['hashed_regular_files'],1)
        self.assertEqual(len(doc['symlink_or_special_metadata']),1)

    def test_snapshot_detects_changed_input(self):
        p=self.write('data','source/value')
        doc=self.inspect()['artifact_inventory.json']
        self.assertEqual(audit.verify_snapshot(doc,self.paths)['historical_file_hashes_preserved'],1)
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):audit.verify_snapshot(doc,self.paths)

    def test_portable_historical_evidence_no_host_path_use(self):
        for prefix in ('/Users/old/codex','/home/old/codex'):
            result=audit.portable_record({'path':prefix+'/runs/stability-label-curation/parent/reports/x','sha256':'a'*64})
            self.assertEqual(result,{'area':'runs','relative_path':'parent/reports/x','sha256':'a'*64})
        self.assertEqual(audit.portable_record({'path':'unrecognized','sha256':'a'*64})['area'],'unresolved')

    def test_duplicate_content_report_has_no_deletion(self):
        self.write('data','source/a');self.write('runs','parent/reports/b')
        report=self.inspect()['duplicate_content_inventory.json']
        self.assertEqual(len(report['groups']),1)
        self.assertFalse(report['files_removed_or_deduplicated'])
        self.assertEqual(len(list(self.paths.project_runs_dir.rglob('b'))),1)

    def test_registered_payload_subset_coverage(self):
        p=self.write('runs','parent/checkpoints/model.json',b'weights')
        member={'area':'runs','relative_path':'parent/checkpoints/model.json','sha256':hashlib.sha256(b'weights').hexdigest(),'size_bytes':7}
        self.plan.write_text(json.dumps({'groups':[{'group_id':'payload:bundle','classification':'R1','artifact_ids':['bundle']}]}))
        with patch.object(audit.restore,'load_registry',return_value={'bundle':{'members':[member]}}):
            reports=self.inspect()
        payload=next(g for g in reports['artifact_inventory.json']['groups'] if g['group_id']=='payload:bundle')
        self.assertEqual(payload['local_file_count'],1)
        self.assertTrue(payload['complete_exact_byte_directory_recovery'])
        self.assertEqual(reports['checkpoint_recovery_coverage.json']['exact_download_covered_files'],1)
        self.assertTrue(p.exists())

    def test_unpublished_local_package_is_not_external_backup_coverage(self):
        self.write('runs','parent/checkpoints/weights.lyr',b'weights')
        member={'area':'runs','relative_path':'parent/checkpoints/weights.lyr',
                'sha256':hashlib.sha256(b'weights').hexdigest(),'size_bytes':7}
        artifact={'members':[member],'external_publication':'pending'}
        with patch.object(audit.restore,'load_registry',return_value={'pending':artifact}):
            report=self.inspect()['checkpoint_recovery_coverage.json']
        self.assertEqual(report['exact_download_covered_files'],0)

    def test_published_alias_counts_as_external_backup_destination(self):
        self.write('runs','alias/checkpoints/weights.lyr',b'weights')
        alias={'area':'runs','relative_path':'alias/checkpoints/weights.lyr',
               'sha256':hashlib.sha256(b'weights').hexdigest(),'size_bytes':7}
        with patch.object(audit.restore,'load_registry',return_value={'published':{'members':[],'aliases':[alias]}}):
            report=self.inspect()['checkpoint_recovery_coverage.json']
        self.assertEqual(report['exact_download_covered_files'],1)
