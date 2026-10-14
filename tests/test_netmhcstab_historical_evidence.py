"""Offline evidence-only tests with synthetic score fixtures; no historical rows invented."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import netmhcstab_historical_evidence as audit
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


class HistoricalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = {'CODEX_ROOT':str(self.root)}
        self.paths = resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True)
        self.evidence = deepcopy(audit.load_evidence(paths=self.paths))
        self.dtu = self.paths.project_data_dir/'dtu.txt'
        self.dtu.write_bytes(b'HLA Pep Thalf\nHLA-A*99:01 ACDEFGHIK 0.00\n')
        self.dtu_hash = raw.sha256_file(self.dtu)
        self.secondary = self.paths.project_data_dir/'score.csv'
        self.fixture(b'allele,peptide,measurement_value\r\nHLA-A*99:01,ACDEFGHIK,0.00\r\nHLA-B*99:02(C67S),ACDEFGHIL,0.5\r\nHLA-B*99:02,ACDEFGHIM,0.50\r\n')
        self.evidence_path = self.root/'evidence.json'
        self.save()
        network = patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in tests'))
        network.start(); self.addCleanup(network.stop)

    def fixture(self,payload):
        self.secondary.write_bytes(payload)
        self.evidence['tlstab']['secondary_artifact'].update(sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),git_blob_sha=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest())

    def save(self):
        self.evidence_path.write_text(raw.json_report(self.evidence))

    def result(self,secondary=True):
        self.save()
        return audit.audit(paths=self.paths,evidence_path=self.evidence_path,dtu_path=self.dtu,
            expected_dtu_sha256=self.dtu_hash,secondary_path=self.secondary if secondary else None)

    def inventory(self):
        return self.result()['artifact_discovery_report.json']['secondary_artifact']

    def test_publication_arithmetic_and_non_recovery(self):
        report=self.result()['published_count_comparison.json']
        self.assertEqual(report['published_table_sum'],5509)
        self.assertEqual(report['published_alleles'],10)
        self.assertIsNone(report['original_locally_observed_rows'])

    def test_no_missing_data_zero_overlap(self):
        report=self.result()['conditional_row_overlap_summary.json']
        self.assertIsNone(report['strict_key_overlap'])
        self.assertIn('not_computed',report['status'])
        self.assertFalse(report['spearmint_independent_input'])

    def test_schema_and_allele_partition(self):
        report=self.inventory()
        self.assertEqual(report['row_count'],3)
        self.assertEqual(report['total_physical_lines'],4)
        self.assertEqual(report['allele_count'],3)
        self.assertEqual(report['peptide_length_distribution'],{'9':3})
        self.assertIn('HLA-B*99:02(C67S)',report['counts_by_original_allele'])
        self.assertIn('HLA-B*99:02',report['counts_by_original_allele'])

    def test_zero_text_and_origin_remain_unresolved(self):
        report=self.inventory()
        self.assertEqual(report['zero_text_representations'],{'0.00':1})
        self.assertEqual(report['zero_source_lines'],[2])
        self.assertEqual(report['row_origin'],'secondary_reprocessed_row_origin_unverified')
        self.assertIn('unresolved',report['zero_semantics'])

    def test_invalid_numeric_and_malformed_flags(self):
        self.fixture(b'allele,peptide,measurement_value\nA,P,NaN\nB,Q,Infinity\nC,R,NA\nD,S,\nE,T,wat\nF,U,-1\nG,V,2\nwrong\n')
        report=self.inventory()
        self.assertEqual(report['malformed_source_lines'],[9])
        self.assertEqual(report['numeric_counts']['non_finite'],2)
        self.assertEqual(report['numeric_counts']['missing'],2)
        self.assertEqual(report['numeric_counts']['non_numeric'],1)
        self.assertEqual(report['numeric_counts']['outside_unit_interval'],2)

    def test_duplicates_formatting_and_conflicts(self):
        self.fixture(b'allele,peptide,measurement_value\nA,P,0.50\nA,P,0.5\nB,Q,0\nB,Q,0.1\n')
        report=self.inventory()
        self.assertEqual(report['duplicate_keys'],2)
        self.assertEqual(report['duplicate_extra_rows'],2)
        self.assertEqual(report['conflicting_valid_score_keys'],1)
        self.assertEqual(report['duplicate_source_lines'],[[2,3],[4,5]])

    def test_bad_schema_rejected(self):
        self.fixture(b'allele,peptide,hours\nA,P,1\n')
        with self.assertRaisesRegex(ValueError,'schema'): self.inventory()

    def test_checksum_gate(self):
        self.secondary.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'checksum'): self.inventory()

    def test_git_blob_identity_gate(self):
        self.evidence['tlstab']['secondary_artifact']['git_blob_sha']='0'*40
        with self.assertRaisesRegex(ValueError,'Git blob'): self.inventory()

    def test_size_gate(self):
        self.evidence['tlstab']['secondary_artifact']['byte_size']+=1
        with self.assertRaisesRegex(ValueError,'size'): self.inventory()

    def test_dtu_identity_gate_before_secondary_analysis(self):
        self.dtu.write_bytes(b'changed')
        with patch.object(audit,'secondary_inventory',side_effect=AssertionError('Must not analyze')):
            with self.assertRaisesRegex(ValueError,'DTU checksum'): self.result()

    def test_no_input_mutation_and_deterministic_reports(self):
        inputs=[p.read_bytes() for p in (self.dtu,self.secondary)]
        first=raw.json_report(self.result());second=raw.json_report(self.result())
        self.assertEqual(first,second)
        self.assertEqual(inputs,[p.read_bytes() for p in (self.dtu,self.secondary)])
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_missing_secondary_is_not_observation_count_zero(self):
        report=self.result(secondary=False)['tlstab_discrepancy_assessment.json']
        self.assertIsNone(report['secondary_observed_rows'])

    def test_secondary_not_equivalent_to_original(self):
        report=self.result()['tlstab_discrepancy_assessment.json']
        self.assertEqual(report['published_count_difference'],789)
        self.assertFalse(report['source_equivalence_established'])
        self.assertEqual(report['secondary_observed_rows'],3)

    def test_evidence_count_arithmetic_gate(self):
        self.evidence['publication']['table_1_counts']['HLA-A*01:01']+=1
        with self.assertRaisesRegex(ValueError,'arithmetic'): self.result()

    def test_evidence_row_recovery_claim_rejected(self):
        self.evidence['historical_source_recovered']=True
        with self.assertRaisesRegex(ValueError,'cannot certify'): self.result()

    def test_secondary_primary_upgrade_rejected(self):
        self.evidence['tlstab']['secondary_artifact']['classification']='authoritative_measured_source'
        with self.assertRaisesRegex(ValueError,'cannot replace'): self.result()

    def test_duplicate_evidence_ids_rejected(self):
        self.evidence['evidence'].append(deepcopy(self.evidence['evidence'][0]))
        with self.assertRaisesRegex(ValueError,'unique'): self.result()

    def test_duplicate_json_keys_rejected(self):
        self.evidence_path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError): audit.load_evidence(self.evidence_path)

    def test_evidence_limits_required(self):
        self.evidence['evidence'][0]['does_not_establish']=''
        with self.assertRaisesRegex(ValueError,'limits'): self.result()

    def test_unsafe_url_and_artifact_path(self):
        for key,value in [('source_url','http://example.com/data'),('source_url','https://u:p@example.com/data'),('relative_path','../escape'),('relative_path','/escape')]:
            with self.subTest(value=value):
                evidence=deepcopy(self.evidence);evidence['tlstab']['secondary_artifact'][key]=value
                with self.assertRaises(ValueError): audit.validate_evidence(evidence)

    def test_unknown_evidence_scope_rejected(self):
        self.evidence['evidence'][0]['scope']='individual_confirmed_experimental_rows'
        with self.assertRaisesRegex(ValueError,'scope'): self.result()

    def test_symlink_input_refused(self):
        alias=self.paths.project_data_dir/'alias.csv';alias.symlink_to(self.secondary)
        with self.assertRaises(OSError): audit.secondary_inventory(alias,self.evidence['tlstab']['secondary_artifact'])

    def test_cli_read_only_offline(self):
        before=sorted(self.root.rglob('*'));out=io.StringIO()
        with redirect_stdout(out):
            code=main(['historical','audit','--json','--evidence',str(self.evidence_path),
                '--dtu',str(self.dtu),'--expected-dtu-sha256',self.dtu_hash,'--secondary',str(self.secondary)],env=self.env)
        self.assertEqual(code,0);self.assertEqual(before,sorted(self.root.rglob('*')))
        self.assertIn('conditional_row_overlap_summary.json',json.loads(out.getvalue()))

    def test_cli_hash_override_requires_explicit_input(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['historical','audit','--expected-dtu-sha256',self.dtu_hash],env=self.env),1)

    def test_report_publication_requires_explicit_hashed_inputs(self):
        target=runs.create_run(paths=self.paths,kind='test',argv=['offline-fixture'],allow_dirty=True,inputs=[self.dtu])
        with self.assertRaisesRegex(ValueError,'each unchanged explicit input'):
            audit.write_reports(self.result(),target/'reports',paths=self.paths)

    def test_reports_written_once_with_checksums(self):
        target=runs.create_run(paths=self.paths,kind='test',argv=['offline-fixture'],allow_dirty=True,inputs=[self.dtu,self.secondary])
        report=self.result();output=audit.write_reports(report,target/'reports',paths=self.paths)
        for name,digest in output['reports'].items():
            self.assertEqual(raw.sha256_file(target/'reports'/name),digest)
        self.assertIn('not_computed',output['completion'])
        with self.assertRaises(FileExistsError):audit.write_reports(report,target/'reports',paths=self.paths)
        self.assertFalse(any((target/'reports').glob('*.jsonl')))

    def test_outside_run_report_destination_rejected(self):
        with self.assertRaises(ValueError):audit.write_reports(self.result(),self.root/'reports',paths=self.paths)

    def test_changed_input_prevents_report_publication(self):
        target=runs.create_run(paths=self.paths,kind='test',argv=['offline-fixture'],allow_dirty=True,inputs=[self.dtu,self.secondary])
        report=self.result();self.dtu.write_bytes(b'changed')
        with self.assertRaises(ValueError):audit.write_reports(report,target/'reports',paths=self.paths)
        self.assertFalse((target/'reports'/'historical_report_checksums.json').exists())

    def test_unknown_schema_and_bad_commit(self):
        for field in ['schema','commit','time']:
            evidence=deepcopy(self.evidence)
            if field=='schema':evidence['schema_version']=2
            if field=='commit':evidence['tlstab']['external_commit']='main'
            if field=='time':evidence['accessed_at_utc']='2026-10-14T12:00:00+09:00'
            with self.subTest(field=field),self.assertRaises(ValueError):audit.validate_evidence(evidence)


if __name__=='__main__':unittest.main()
