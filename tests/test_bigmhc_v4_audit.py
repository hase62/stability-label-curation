"""Synthetic bounded archives; sealed members must never be opened."""
from contextlib import redirect_stdout,redirect_stderr
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from stability_label_curation import bigmhc_v4_audit as a
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.data_sources import load_manifest
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


class Response(io.BytesIO):
    status=200
    def __init__(self,data,url=a.FINAL_URL,headers=None):super().__init__(data);self.url=url;self.headers=headers or {}
    def geturl(self):return self.url


class SyntheticFixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True)
        self.archive=self.paths.project_data_dir/'fixture.zip';self.dtu=self.paths.project_data_dir/'dtu.txt'
        self.dtu.write_text('HLA Pep Thalf\nHLA-A*02:01 ACDEFGHIK 0.00\nHLA-B*07:02 LMNPQRSTV 2.00\nHLA-B*14:01(C67S) AAAAAAAAA 0.00\n')
        self.content={
            'el_train.csv':'mhc,pep,tgt\nHLA-A02:01,ACDEFGHIK,1\nHLA-A02:01,ACDEFGHIK,1\nHLA-A02:01,ACDEFGHIK,0\nHLA-B*07:02,LMNPQRSTV,0\n',
            'el_val.csv':'mhc,pep,tgt\nHLA-A02:01,ACDEFGHIK,1\n',
            'im_train.csv':'mhc,pep,tgt,rand\nHLA-A02:01,ACDEFGHIK,1,0\nHLA-B*07:02,LMNPQRSTV,0,1\n',
            'im_val.csv':'mhc,pep,tgt,rand\nHLA-B*07:02,LMNPQRSTV,0,0\n',
            'pseudoseqs.csv':'mhc,2_A,2_C,9_A,9_C\nHLA-A*02:01,1,0,1,0\nHLA-B*07:02,0,1,1,0\n',
            **{name:'SEALED DO NOT READ\n' for name in a.SEALED_MEMBERS},'summary.csv':'NOT NEEDED\n'}
        self.writezip()
        p=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in tests'))
        p.start();self.addCleanup(p.stop)
    def writezip(self):
        with zipfile.ZipFile(self.archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,text in self.content.items():z.writestr(name,text)
    def result(self,**kw):
        return a.inspect(paths=self.paths,archive=self.archive,dtu_path=self.dtu,
            expected_archive_sha256=raw.sha256_file(self.archive),expected_dtu_sha256=raw.sha256_file(self.dtu),**kw)


class AuditTests(SyntheticFixture, unittest.TestCase):
    def test_counts_and_binary_labels(self):
        files=self.result().reports['bigmhc_training_inventory.json']['files']
        self.assertEqual(files['el_train.csv']['total_rows'],4)
        self.assertEqual(files['el_train.csv']['label_counts'],{'0':2,'1':2})
        self.assertEqual(files['im_train.csv']['rand_flag_by_original_label'],[
            {'original_rand_flag':'0','original_label':'1','rows':1},{'original_rand_flag':'1','original_label':'0','rows':1}])
    def test_sealed_members_and_optional_summary_never_opened(self):
        original=zipfile.ZipFile.open
        def guarded(z,name,*args,**kwargs):
            actual=name.filename if isinstance(name,zipfile.ZipInfo) else name
            self.assertIn(actual,a.READABLE_MEMBERS)
            return original(z,name,*args,**kwargs)
        with patch.object(zipfile.ZipFile,'open',guarded),patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('Never whole-archive CRC')):
            result=self.result()
        self.assertEqual(result.reports['bigmhc_archive_inventory.json']['sealed_members_opened'],[])
        self.assertEqual(set(result.reports['bigmhc_archive_inventory.json']['opened_members']),set(a.READABLE_MEMBERS))
    def test_immutable_archive_gate_before_open(self):
        with patch.object(zipfile,'ZipFile',side_effect=AssertionError('Checksum first')):
            with self.assertRaisesRegex(ValueError,'SHA256'):
                a.inspect(paths=self.paths,archive=self.archive,dtu_path=self.dtu,expected_archive_sha256='a'*64)
    def test_DTU_checksum_gate(self):
        with self.assertRaisesRegex(ValueError,'SHA256'):
            a.inspect(paths=self.paths,archive=self.archive,dtu_path=self.dtu,
                expected_archive_sha256=raw.sha256_file(self.archive),expected_dtu_sha256='a'*64)
    def test_no_checksum_override_without_explicit_path(self):
        with self.assertRaises(ValueError):a.inspect(paths=self.paths,expected_archive_sha256='a'*64)
    def test_duplicate_and_conflicting_pair_counts(self):
        r=self.result().reports['bigmhc_training_inventory.json']
        d=r['duplicates']['el_train.csv'];self.assertEqual(d['distinct_raw_pair_keys'],2)
        self.assertEqual(d['repeated_raw_pair_keys'],1);self.assertEqual(d['conflicting_binary_label_keys'],1)
        self.assertEqual(d['same_pair_and_binary_label_extra_rows'],1)
        self.assertEqual(r['files']['el_train.csv']['exact_all_field_duplicate_extra_rows'],1)
    def test_pair_and_peptide_overlap_distinguished(self):
        r=self.result().reports['bigmhc_overlap_audit.json']
        self.assertEqual(r['sequence_overlap']['EL_IM_shared_distinct_peptides'],2)
        pair=next(x for x in r['raw_pair_overlap'] if x['left']=='el_train.csv' and x['right']=='im_train.csv')
        self.assertEqual(pair['shared_raw_pair_keys'],2);self.assertFalse(pair['same_label_task'])
        self.assertFalse(r['evaluation_overlap_assessed'])
    def test_DTU_compatibility_and_zero_not_relabelled(self):
        r=self.result().reports['bigmhc_dtu_compatibility.json']
        self.assertEqual(r['ordinary_DTU_rows'],2);self.assertEqual(r['C67S_rows_separate'],1)
        self.assertEqual(r['DTU_overlap']['el_train.csv']['strict_raw_pair_matches'],1)
        self.assertEqual(r['DTU_overlap']['el_train.csv']['notation_mapped_pair_matches'],2)
        self.assertEqual(r['DTU_overlap']['el_train.csv']['matched_DTU_reported_zero_keys'],1)
        self.assertFalse(r['DTU_overlap']['el_train.csv']['measurement_values_comparable'])
    def test_no_fuzzy_or_mutant_to_wild_type_mapping(self):
        self.assertEqual(a.canonical_hla('HLA-A02:01'),'HLA-A*02:01')
        for allele in ('HLA-B*14:01(C67S)','HLA-A*02:01:01','garbage','A0201'):
            self.assertIsNone(a.canonical_hla(allele))
    def test_peptide_lengths_and_current_teacher_scope(self):
        self.content['el_val.csv']+='HLA-A02:01,ACDEFGHIKL,0\n';self.writezip()
        s=self.result().reports['bigmhc_training_inventory.json']['files']['el_val.csv']
        self.assertEqual(s['peptide_length_counts'],{'10':1,'9':1})
        self.assertEqual(s['DTU_input_scope_counts']['ordinary_DTU_allele_ninemer_rows'],1)
        self.assertFalse(s['scope_counts_are_training_eligibility'])
    def test_reference_integrity_and_feature_dimension(self):
        r=self.result().reports['bigmhc_dtu_compatibility.json']['receptor_reference']
        self.assertEqual(r['rows'],2);self.assertEqual(r['feature_count'],4)
        self.assertFalse(r['model_default_414_features_match']);self.assertEqual(r['invalid_one_hot_rows'],0)
    def test_invalid_onehot_flagged(self):
        self.content['pseudoseqs.csv']=self.content['pseudoseqs.csv'].replace('1,0,1,0','1,1,1,0');self.writezip()
        self.assertEqual(self.result().reports['bigmhc_dtu_compatibility.json']['receptor_reference']['invalid_one_hot_rows'],1)
    def test_standalone_reference_when_archive_does_not_contain_it(self):
        text=self.content.pop('pseudoseqs.csv');self.writezip();p=self.paths.project_data_dir/'ref.csv';p.write_text(text)
        r=self.result(pseudoseqs_path=p,expected_reference_sha256=raw.sha256_file(p))
        self.assertEqual(len(r.inputs),3)
        self.assertNotIn('pseudoseqs.csv',r.reports['bigmhc_archive_inventory.json']['opened_members'])
    def test_missing_sealed_member_is_not_downloaded(self):
        del self.content['manafest.csv'];self.writezip()
        self.assertEqual(self.result().reports['bigmhc_archive_inventory.json']['sealed_member_status']['manafest.csv'],'absent_not_acquired')
    def test_malformed_numeric_and_noncanonical_flags(self):
        self.content['el_val.csv']+='HLA-A02:01,ACDEFGHIX,0\nHLA-A02:01,ACDEFGHIK,NaN\n';self.writezip()
        s=self.result().reports['bigmhc_training_inventory.json']['files']['el_val.csv']
        self.assertEqual(s['quality_flag_counts']['non_binary_or_nonfinite_label'],1)
        self.assertEqual(s['quality_flag_counts']['noncanonical_peptide_characters'],1)
    def test_unsafe_archive_paths_rejected(self):
        self.content['../escape.csv']='bad';self.writezip()
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.result()
    def test_missing_authorized_input_rejected(self):
        del self.content['el_train.csv'];self.writezip()
        with self.assertRaisesRegex(ValueError,'missing'):self.result()
    def test_symlink_archive_rejected(self):
        alias=self.root/'alias.zip';alias.symlink_to(self.archive)
        with self.assertRaises(OSError):a.inspect(paths=self.paths,archive=alias,dtu_path=self.dtu)
    def test_CRC_validation_only_on_authorized_members(self):
        data=bytearray(self.archive.read_bytes());index=data.index(b'PK\x01\x02')
        data[index+16]^=1;self.archive.write_bytes(data)
        with self.assertRaises(zipfile.BadZipFile):self.result()
    def test_reference_checksum_gate(self):
        text=self.content.pop('pseudoseqs.csv');self.writezip();p=self.root/'ref.csv';p.write_text(text)
        with self.assertRaisesRegex(ValueError,'SHA256'):
            self.result(pseudoseqs_path=p,expected_reference_sha256='0'*64)
    def test_report_directory_symlink_rejected(self):
        r=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        outside=self.root/'outside';outside.mkdir();alias=run/'elsewhere';alias.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):a.write_reports(r,alias,paths=self.paths)
        self.assertEqual(list(outside.iterdir()),[])
    def test_expansion_limit(self):
        with patch.object(a,'MEMBER_CAP',20),self.assertRaisesRegex(ValueError,'size cap'):self.result()
    def test_deterministic_read_only_and_original_labels(self):
        before=(self.archive.read_bytes(),self.dtu.read_bytes());listing=sorted(self.root.rglob('*'))
        one,two=self.result(),self.result()
        self.assertEqual(raw.json_report(one.reports),raw.json_report(two.reports))
        self.assertEqual(before,(self.archive.read_bytes(),self.dtu.read_bytes()))
        self.assertEqual(listing,sorted(self.root.rglob('*')))
        p=one.reports['bigmhc_provenance_and_blockers.json']
        self.assertEqual(set(p['future_conditions']),{'A','B','C','D'});self.assertFalse(p['corrections_created'])
    def test_CLI_and_old_commands(self):
        args=['bigmhc','data-audit','--json','--archive',str(self.archive),'--dtu',str(self.dtu),
            '--expected-archive-sha256',raw.sha256_file(self.archive),'--expected-dtu-sha256',raw.sha256_file(self.dtu)]
        out=io.StringIO()
        with redirect_stdout(out),redirect_stderr(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        self.assertIn('bigmhc_training_inventory.json',out.getvalue())
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)
    def test_report_safety_and_hashed_inputs(self):
        r=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=[i['path'] for i in r.inputs],allow_dirty=True)
        receipt=a.write_reports(r,run/'reports',paths=self.paths);self.assertEqual(len(receipt['report_sha256']),5)
        with self.assertRaises(FileExistsError):a.write_reports(r,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):a.write_reports(r,self.root/'reports',paths=self.paths)


class FetchTests(SyntheticFixture, unittest.TestCase):
    # Reuse synthetic archive generation, not scientific inputs.
    def perform(self,data=None,**kwargs):
        payload=self.archive.read_bytes() if data is None else data
        original=load_manifest(paths=self.paths).get('bigmhc_v4')
        registry=SimpleNamespace(get=lambda key:replace(original,expected_sha256=hashlib.sha256(payload).hexdigest()))
        response=Response(payload,**kwargs)
        client=SimpleNamespace(open=lambda request,timeout:response)
        with patch.object(a,'load_manifest',return_value=registry):return a.fetch(paths=self.paths,expected_size=len(payload),opener=client)
    def test_streamed_fetch_and_existing_preservation(self):
        receipt=self.perform();target=self.paths.project_data_dir/'bigmhc_v4/datasets.zip'
        self.assertEqual(receipt['local_sha256'],raw.sha256_file(target));before=target.read_bytes()
        self.assertEqual(self.perform()['acquisition'],'reused');self.assertEqual(target.read_bytes(),before)
    def test_URL_allowlist_rejects_other_payloads(self):
        for url in ('http://example.org/data','https://example.org/datasets.zip',a.REFERENCE_FINAL_URL):
            with self.assertRaises(ValueError):a.validate_download_url(url)
        with self.assertRaises(ValueError):a.fetch(paths=self.paths,artifact='manafest.csv')
    def test_bad_content_cleanup(self):
        with self.assertRaises(ValueError):self.perform(b'<html>error</html>')
        folder=self.paths.project_data_dir/'bigmhc_v4'
        self.assertEqual(list(folder.iterdir()),[])
    def test_size_limit_before_body_and_redirect_rejection(self):
        with self.assertRaisesRegex(ValueError,'Content-Length'):self.perform(headers={'Content-Length':str(a.ARCHIVE_CAP+1)})
        with self.assertRaisesRegex(ValueError,'allowlist'):self.perform(url='https://example.org/redirect')
    def test_wrong_existing_bytes_never_replaced(self):
        p=self.paths.project_data_dir/'bigmhc_v4';p.mkdir();target=p/'datasets.zip';target.write_bytes(b'existing')
        with self.assertRaisesRegex(ValueError,'preserved'):self.perform()
        self.assertEqual(target.read_bytes(),b'existing')
    def test_source_project_alias_rejected(self):
        other=self.root/'other';other.mkdir()
        # Existing project directory is a real fixture location; source target symlinks still fail closed.
        p=self.paths.project_data_dir/'bigmhc_v4';p.symlink_to(other,target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):self.perform()
        self.assertEqual(list(other.iterdir()),[])


if __name__=='__main__':unittest.main()
