"""Synthetic pinned Git/CSV fixtures only; never execute or download external code."""

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal, localcontext
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import spearmint_overlap_audit as audit
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.__main__ import main
from stability_label_curation.paths import resolve_paths


class TestSpearmintAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = {'CODEX_ROOT': str(self.root)}
        self.repository = Path(__file__).resolve().parents[1]
        self.paths = resolve_paths(self.env, repository_root=self.repository)
        self.checkout = self.paths.repos_root/'spearmint'; self.checkout.mkdir(parents=True)
        self.paths.project_data_dir.mkdir(parents=True)
        self.primary = self.paths.project_data_dir/'synthetic_dtu.txt'
        self.primary_payload = (b'HLA Pep Thalf\nHLA-A*99:01 ACDEFGHIK 1.80\n'
            b'HLA-A*99:01 ACDEFGHIL 0.00\nHLA-A*99:01 ACDEFGHIM 0.10\n'
            b'HLA-B*99:02 ACDEFGHIN 2.00\nHLA-B*99:03(C67S) ACDEFGHIP 0.00\n')
        self.primary.write_bytes(self.primary_payload)
        self.primary_sha = hashlib.sha256(self.primary_payload).hexdigest()
        self.columns = ['peptide_sequence','mhc_sequence','label','allele','assay','temperature_C']
        self.train = [['ACDEFGHIK','ACD','1.8','HLA-A*99:01','SPA','37.0'],
                      ['ACDEFGHIL','ACD','0.0','HLA-A*99:01','SPA','37.0']]
        self.val = [['ACDEFGHIN','EFG','2.0','HLA-B*99:02','SPA','37.0']]
        self.test = [['ACDEFGHIM','ACD','0.1','HLA-A*99:01','SPA','37.0']]
        self.references = [['HLA-A*99:01','ACD'],['HLA-B*99:02','EFG'],['HLA-B*99:03(C67S)','HIK']]
        self.evidence = deepcopy(audit.load_evidence(paths=self.paths))
        self.evidence['preprint']['claimed_rows']=7
        self.evidence['preprint']['claimed_alleles']=2
        self.evidence['preprint']['claimed_split_rows']={'train':2,'val':1,'test':1}
        self.evidence['items']=[]
        self.lock_path=self.root/'external.lock.json'; self.evidence_path=self.root/'evidence.json'
        self.git('init','-q');self.git('config','user.name','Synthetic Test');self.git('config','user.email','test@example.invalid')
        (self.checkout/'README.md').write_text('Synthetic source fixture.\n')
        self.refresh()
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network'))
        self.network.start();self.addCleanup(self.network.stop)

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.checkout),*args],text=True).strip()

    def write_csv(self,relative,header,rows):
        path=self.checkout/relative;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(header);writer.writerows(rows)

    def refresh(self):
        for name,rows in [('train',self.train),('val',self.val),('test',self.test)]:
            self.write_csv(self.evidence['splits'][name],self.columns,rows)
        self.write_csv(self.evidence['mapping_path'],['Allele','Full Sequence'],self.references)
        self.git('add','.');self.git('commit','-q','--allow-empty','-m','Synthetic pinned fixture')
        commit=self.git('rev-parse','HEAD');self.evidence['commit_sha']=commit
        files=[]
        for relative in ['README.md',*self.evidence['splits'].values(),self.evidence['mapping_path']]:
            path=self.checkout/relative
            files.append({'path':relative,'sha256':raw.sha256_file(path),'byte_size':path.stat().st_size,
                          'git_blob_sha':self.git('rev-parse','HEAD:'+relative)})
        self.lock={'repository_name':'spearmint','source_id':'spearmint_stability_audit',
            'url':'https://github.com/dhuvik/spearmint.git','commit_sha':commit,
            'branch_at_acquisition':self.git('branch','--show-current'),'accessed_at_utc':'2026-10-14T00:00:00Z',
            'checkout_relative_path':'spearmint','clone_strategy':'Synthetic local Git fixture','files':files}
        self.lock_path.write_text(raw.json_report({'schema_version':1,'repositories':[self.lock]}))
        self.evidence_path.write_text(raw.json_report(self.evidence))

    def result(self,**extra):
        return audit.audit(paths=self.paths,checkout=self.checkout,dtu_path=self.primary,
            expected_dtu_sha256=self.primary_sha,lock_path=self.lock_path,evidence_path=self.evidence_path,**extra)

    def snapshots(self):
        return audit.snapshot_stage2(paths=self.paths,checkout=self.checkout,locked=self.lock,evidence=self.evidence)

    def cli(self,extras=None):
        args=['spearmint','audit','--checkout',str(self.checkout),'--dtu',str(self.primary),
              '--expected-dtu-sha256',self.primary_sha,'--lock',str(self.lock_path),'--evidence',str(self.evidence_path)]+(extras or [])
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):status=main(args,env=self.env)
        return status,out.getvalue(),err.getvalue()

    def test_schema_and_split_counts(self):
        result=self.result();inventory=result.reports['stage2_split_inventory.json']
        self.assertEqual(inventory['splits']['train']['columns'],self.columns)
        self.assertEqual(result.summary()['split_counts'],{'train':2,'val':1,'test':1})
        self.assertEqual(inventory['total_rows'],4)
        self.assertEqual(inventory['splits']['train']['peptide_lengths'],{'9':2})
        self.assertEqual(inventory['splits']['train']['context_values']['assay'],{'SPA':2})

    def test_exact_strict_mapped_and_decimal_matches(self):
        summary=self.result().summary()
        for key in ['strict_raw_identifier_row_matches','mapped_identifier_row_matches','exact_decimal_measurement_matches']:
            self.assertEqual(summary[key],4)
        self.assertEqual(Decimal(summary['absolute_difference_hours']['maximum']),0)
        self.assertEqual(summary['exact_label_text_matches'],0)

    def test_stable_original_row_fields_and_order(self):
        rows=self.result().row_reports['dtu_stage2_overlap_rows.jsonl']
        self.assertEqual([r['split'] for r in rows],['train','train','val','test'])
        self.assertEqual(rows[0]['raw_fields']['label'],'1.8')
        self.assertEqual(rows[0]['dtu_half_life_text'],'1.80')
        self.assertEqual(rows[0]['source_line_start'],2)
        self.assertEqual(rows[0]['dtu_line_number'],2)
        self.assertEqual(self.primary.read_bytes(),self.primary_payload)

    def test_decimal_tolerance_counts(self):
        self.train[0][2]='1.8000000005';self.refresh()
        summary=self.result().summary()
        self.assertEqual(summary['tolerance_match_counts_hours']['0'],3)
        self.assertEqual(summary['tolerance_match_counts_hours']['0.000000000001'],3)
        self.assertEqual(summary['tolerance_match_counts_hours']['0.000000001'],4)
        self.assertEqual(Decimal(summary['absolute_difference_hours']['maximum']),Decimal('0.0000000005'))

    def test_verified_log1p_inverse_only_for_comparison(self):
        with localcontext() as ctx:
            ctx.prec=50
            for rows in (self.train,self.val,self.test):
                for row in rows:row[2]=str((Decimal(row[2])+1).ln())
        self.evidence['label_representation']='log1p_hours';self.refresh()
        result=self.result();summary=result.summary()
        self.assertEqual(summary['tolerance_match_counts_hours']['0.000000000001'],4)
        row=result.row_reports['dtu_stage2_overlap_rows.jsonl'][0]
        self.assertEqual(row['raw_label_text'],self.train[0][2])
        self.assertIn('precision_50',row['label_conversion'])

    def test_unverified_transformation_does_not_convert(self):
        self.evidence['label_interpretation_verified']=False;self.refresh()
        summary=self.result().summary()
        self.assertEqual(summary['numerically_incomparable_matched_rows'],4)
        self.assertEqual(summary['exact_decimal_measurement_matches'],0)

    def test_unknown_label_scale_remains_unresolved(self):
        self.evidence['label_representation']='unknown';self.refresh()
        self.assertEqual(self.result().summary()['numerically_incomparable_matched_rows'],4)

    def test_sequence_only_unique_reference_mapping(self):
        self.train[0][3]='';self.refresh()
        summary=self.result().summary()
        self.assertEqual(summary['strict_raw_identifier_row_matches'],3)
        self.assertEqual(summary['mapped_identifier_row_matches'],4)
        self.assertEqual(summary['unmapped_rows'],0)

    def test_ambiguous_sequence_mapping_retained_unmatched(self):
        self.train[0][3]='';self.references.append(['HLA-A*99:09','ACD']);self.refresh()
        result=self.result();self.assertEqual(result.summary()['unmapped_rows'],1)
        row=result.row_reports['stage2_unmatched_rows.jsonl'][0]
        self.assertEqual(row['mapping']['mapping_status'],'unresolved_ambiguous_sequence')
        self.assertEqual(row['raw_fields']['peptide_sequence'],'ACDEFGHIK')

    def test_explicit_name_disambiguates_identical_reference_sequences(self):
        self.references.append(['HLA-A*99:09','ACD']);self.refresh()
        result=self.result()
        self.assertEqual(result.summary()['mapped_identifier_row_matches'],4)
        receptor=result.row_reports['dtu_stage2_overlap_rows.jsonl'][0]['mapping']
        self.assertEqual(len(receptor['candidate_reference_identifiers']),2)
        self.assertEqual(receptor['mapped_identifier'],'HLA-A*99:01')

    def test_unmapped_receptor_and_sequence_mismatch(self):
        self.train[0][1]='YYY';self.refresh()
        result=self.result()
        self.assertEqual(result.summary()['strict_raw_identifier_row_matches'],4)
        self.assertEqual(result.summary()['mapped_identifier_row_matches'],3)
        self.assertIsNone(result.row_reports['stage2_unmatched_rows.jsonl'][0]['mapping']['mapped_identifier'])

    def test_c67s_never_maps_to_wild_type(self):
        self.test.append(['ACDEFGHIP','EFG','0.0','HLA-B*99:03(C67S)','SPA','37.0']);self.refresh()
        result=self.result();row=result.row_reports['stage2_unmatched_rows.jsonl'][0]
        self.assertEqual(row['mapping']['raw_allele'],'HLA-B*99:03(C67S)')
        self.assertIsNone(row['mapping']['mapped_identifier'])
        self.assertEqual(result.summary()['strict_raw_identifier_row_matches'],5)

    def test_exact_annotated_reference_identity_stays_annotated(self):
        self.test.append(['ACDEFGHIP','HIK','0.0','HLA-B*99:03(C67S)','SPA','37.0']);self.refresh()
        result=self.result();row=result.row_reports['dtu_stage2_overlap_rows.jsonl'][-1]
        self.assertEqual(row['mapping']['mapped_identifier'],'HLA-B*99:03(C67S)')
        self.assertEqual(result.summary()['dtu_absent_rows'],0)

    def test_zero_labels_are_not_synthetic_or_censoring_labels(self):
        result=self.result();summary=result.summary()
        self.assertEqual(summary['matched_dtu_zero_rows'],1)
        row=result.row_reports['dtu_stage2_overlap_rows.jsonl'][1]
        self.assertEqual(row['row_measurement_origin'],audit.ROW_ORIGIN)
        self.assertEqual(row['provenance_classification'],'dtu_matching_released_row_not_independent')
        self.assertNotIn(row['row_measurement_origin'],['synthetic','left_censored','confirmed_experimental'])

    def test_cross_split_and_within_split_duplicate_keys(self):
        self.train.append(list(self.train[0]));self.test.append(list(self.train[0]));self.refresh()
        summary=self.result().summary()
        self.assertEqual(summary['raw_duplicate_keys']['duplicate_key_groups'],1)
        self.assertEqual(summary['raw_duplicate_keys']['cross_split_duplicate_key_groups'],1)
        self.assertEqual(summary['raw_duplicate_keys']['within_split_duplicate_key_groups']['train'],1)
        self.assertEqual(summary['stage2_rows'],6)
        allele=next(a for a in summary['per_allele'] if a['raw_dtu_identifier']=='HLA-A*99:01')
        self.assertEqual(allele['stage2_rows_by_split'],{'train':3,'val':0,'test':2})

    def test_absent_and_unmatched_rows_retain_original_references(self):
        self.test.append(['ACDEFGHIQ','ACD','3.0','HLA-A*99:01','SPA','37.0']);self.refresh()
        result=self.result()
        self.assertEqual(result.summary()['stage2_unmatched_rows'],1)
        self.assertEqual(result.summary()['dtu_absent_rows'],1)
        self.assertEqual(result.row_reports['dtu_absent_rows.jsonl'][0]['source_line_number'],6)
        self.assertEqual(result.row_reports['stage2_unmatched_rows.jsonl'][0]['unmatched_reason'],'mapped_key_absent_from_dtu')

    def test_numeric_missing_nonfinite_invalid_rows_are_flagged_not_removed(self):
        for text in ('','NaN','Infinity','bad'):
            with self.subTest(text=text):
                self.train[0][2]=text;self.refresh();result=self.result()
                self.assertEqual(result.summary()['stage2_rows'],4)
                self.assertEqual(result.summary()['numerically_incomparable_matched_rows'],1)
                self.assertEqual(len(result.reports['stage2_split_inventory.json']['splits']['train']['malformed_rows']),1)

    def test_csv_physical_line_spans_and_quoted_values(self):
        path=self.root/'quoted.csv';path.write_bytes(b'peptide_sequence,mhc_sequence,label,allele\r\n"ACD","ACD\r\nEFG",1.8,HLA-A*99:01\r\n')
        rows,report=audit.read_split(path,'train',self.evidence['columns'])
        self.assertEqual((rows[0].line_start,rows[0].line_end),(2,3))
        self.assertEqual(rows[0].fields['mhc_sequence'],'ACD\r\nEFG')
        self.assertEqual(report['rows'],1)

    def test_schema_failures_and_malformed_column_count(self):
        path=self.root/'bad.csv'
        for payload in ('label,label\n1,2\n','x,y\n1,2\n'):
            path.write_text(payload)
            with self.assertRaises(ValueError):audit.read_split(path,'train',self.evidence['columns'])
        path.write_text('peptide_sequence,allele,label\nACD,HLA-A*99:01,1,EXTRA\n')
        rows,report=audit.read_split(path,'train',self.evidence['columns'])
        self.assertEqual(rows[0].raw_cells[-1],'EXTRA')
        self.assertEqual(report['malformed_rows'][0]['reason'],'column_count')

    def test_dtu_checksum_gate_runs_before_external_inspection(self):
        self.primary.write_bytes(b'changed')
        with patch.object(audit,'verify_checkout',side_effect=AssertionError('Must not inspect')),self.assertRaisesRegex(ValueError,'DTU checksum'):
            self.result()

    def test_stage2_checksum_and_dirty_checkout_gates(self):
        (self.checkout/self.evidence['splits']['train']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'clean working tree'):self.result()

    def test_explicit_override_must_match_pinned_bytes(self):
        path=self.root/'other.csv';path.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Pinned input checksum'):self.result(files={'train':path})

    def test_snapshot_exact_bytes_idempotence_no_overwrite(self):
        first=self.snapshots();second=self.snapshots()
        self.assertEqual(len(first['snapshots']),4)
        for entry in first['snapshots']:
            self.assertEqual(raw.sha256_file(entry['snapshot_path']),entry['sha256'])
        self.assertTrue(all(e['acquisition']=='existing_identical_snapshot_reused' for e in second['snapshots']))
        path=Path(first['snapshots'][0]['snapshot_path']);path.write_bytes(b'other bytes')
        with self.assertRaisesRegex(ValueError,'refusing replacement'):self.snapshots()
        self.assertEqual(path.read_bytes(),b'other bytes')

    def test_snapshot_failure_removes_only_own_pending_file(self):
        target=self.paths.project_data_dir/'spearmint_stage2'/self.evidence['splits']['train']
        with patch.object(audit.os,'link',side_effect=OSError('publication failure')),self.assertRaises(OSError):self.snapshots()
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()),[])

    def test_snapshot_symlink_escape_rejected(self):
        root=self.paths.project_data_dir/'spearmint_stage2';root.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):self.snapshots()
        self.assertFalse((self.root/'data'/'binding_stability').exists())

    def test_read_only_cli_offline_and_deterministic(self):
        before=sorted(self.root.rglob('*'))
        first=self.cli(['--json']);second=self.cli(['--json'])
        self.assertEqual(first,second);self.assertEqual(first[0],0,first[2])
        self.assertEqual(before,sorted(self.root.rglob('*')))
        self.assertEqual(self.git('status','--porcelain'),'')
        self.assertEqual(self.primary.read_bytes(),self.primary_payload)

    def test_no_external_code_execution(self):
        sentinel=self.root/'executed'
        (self.checkout/'malicious.py').write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).touch()\n')
        self.refresh();self.result()
        self.assertFalse(sentinel.exists())

    def test_published_discrepancy_is_not_repaired(self):
        summary=self.result().summary()
        self.assertEqual(summary['published_minus_released_rows'],3)
        self.assertEqual(summary['published_split_sum'],4)
        self.assertEqual(summary['stage2_rows'],4)

    def test_pinned_commit_mismatch_and_evidence_validation(self):
        document=deepcopy(self.evidence);document['label_representation']='model_prediction'
        with self.assertRaises(ValueError):audit.validate_evidence(document)
        document=deepcopy(self.evidence);document['splits']['train']='../escape.csv'
        with self.assertRaises(ValueError):audit.validate_evidence(document)
        self.evidence['commit_sha']='0'*40;self.evidence_path.write_text(raw.json_report(self.evidence))
        with self.assertRaisesRegex(ValueError,'commits differ'):self.result()

    def test_reproducible_report_generation_and_input_hashes(self):
        self.snapshots();result=self.result()
        run=runs.create_run(paths=self.paths,kind='source_overlap_audit',inputs=result.inputs,argv=['synthetic test'],allow_dirty=True)
        completion=audit.write_reports(result,run/'reports',paths=self.paths)
        for name,digest in completion['report_sha256'].items():self.assertEqual(raw.sha256_file(run/'reports'/name),digest)
        repeated=self.result()
        for name,rows in repeated.row_reports.items():self.assertEqual(audit._jsonl(rows),(run/'reports'/name).read_text())
        for name,report in repeated.reports.items():self.assertEqual(raw.json_report(report),(run/'reports'/name).read_text())
        with self.assertRaises(FileExistsError):audit.write_reports(result,run/'reports',paths=self.paths)

    def test_report_output_requires_explicit_hashed_inputs(self):
        self.snapshots();result=self.result()
        run=runs.create_run(paths=self.paths,kind='source_overlap_audit',argv=['synthetic test'],allow_dirty=True)
        with self.assertRaisesRegex(ValueError,'explicitly record'):audit.write_reports(result,run/'reports',paths=self.paths)
        self.assertEqual(list((run/'reports').iterdir()),[])

    def test_unsafe_report_destination_and_symlink(self):
        self.snapshots();result=self.result()
        with self.assertRaises(ValueError):audit.write_reports(result,self.root/'reports',paths=self.paths)
        run=runs.create_run(paths=self.paths,kind='source_overlap_audit',inputs=result.inputs,argv=['synthetic test'],allow_dirty=True)
        reports=run/'reports';reports.rmdir();reports.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):audit.write_reports(result,reports,paths=self.paths)

    def test_cli_checksum_override_requires_dtu(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['spearmint','audit','--expected-dtu-sha256',self.primary_sha],env=self.env),1)

    def test_existing_commands_preserved(self):
        for args in [['paths','--json'],['sources','validate'],['runs','list','--json'],
                     ['dtu2016','inspect','--input',str(self.primary),'--json']]:
            with self.subTest(args=args),redirect_stdout(io.StringIO()):self.assertEqual(main(args,env=self.env),0)


if __name__=='__main__':unittest.main()
