"""Offline source-audit tests: small synthetic rows, never a real-source excerpt."""

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import dtu2016_source_audit as audit
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.__main__ import main
from stability_label_curation.paths import resolve_paths


class TestSourceAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = {'CODEX_ROOT': str(self.root)}
        self.repository = Path(__file__).resolve().parents[1]
        self.paths = resolve_paths(self.env, repository_root=self.repository)
        self.paths.project_data_dir.mkdir(parents=True)
        self.path = self.paths.project_data_dir / 'synthetic.txt'
        self.payload = (b'HLA\tPep\tThalf\r\n'
            b'HLA-A*99:01 ACDEFGHIK 0.00\r\n\r\n'
            b'HLA-A*99:01 ACDEFGHIL -0.0\r\n'
            b'HLA-A*99:01 ACDEFGHIM 1.00\r\n'
            b'HLA-B*99:02 ACDEFGHIN 0e0\r\n'
            b'HLA-B*99:02 ACDEFGHIP 2\r\n'
            b'HLA-B*99:02 ACDEFGHIQ 6.00\r\n'
            b'HLA-B*99:03(C67S) ACDEFGHIR 0.00\r\n'
            b'HLA-B*99:03(C67S) ACDEFGHIS 0.125\r\n')
        self.path.write_bytes(self.payload)
        self.checksum = hashlib.sha256(self.payload).hexdigest()
        self.evidence = deepcopy(audit.load_evidence(paths=self.paths))
        self.evidence['table_ii']['coverage'] = 'partial'
        self.evidence['table_ii']['entries'] = [
            {'publication_identifier': published, 'raw_identifier': hla, 'count': count,
             'p05_text': '0', 'p95_text': '5'} for hla,published,count in (
                ('HLA-A*99:01','HLA-A*99:01',3),
                ('HLA-B*99:02','HLA-B*99:02',3),
                ('HLA-B*99:03(C67S)','HLA-B*99:03 (C67S)',2))]
        self.evidence_path = self.root / 'evidence.json'
        self.evidence_path.write_text(raw.json_report(self.evidence))
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def result(self, payload=None):
        if payload is not None:
            self.path.write_bytes(payload)
        return audit.audit(self.path, paths=self.paths,
            expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(), evidence=self.evidence)

    def zero(self, result=None):
        return (result or self.result()).reports['zero_value_audit.json']

    def cli(self, extras=None):
        arguments = ['dtu2016','audit','--input',str(self.path),'--expected-sha256',self.checksum,
                     '--evidence',str(self.evidence_path)] + (extras or [])
        out,err = io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            status = main(arguments,env=self.env)
        return status,out.getvalue(),err.getvalue()

    def create_run(self, *, include_input=True):
        return runs.create_run(paths=self.paths, kind='data_audit', argv=['synthetic test'],
            inputs=[self.path] if include_input else [], allow_dirty=True)

    def test_zero_text_and_source_line_preservation(self):
        report = self.zero()
        self.assertEqual(report['zero_count'],4)
        self.assertEqual(report['zero_text_representations'],{'0.00':2,'-0.0':1,'0e0':1})
        self.assertEqual(report['zero_source_lines'],[2,4,6,9])
        self.assertEqual(report['zero_fraction'],{'numerator':4,'denominator':8,'decimal':'0.5'})

    def test_zero_fractions_and_positive_distributions_by_allele(self):
        alleles = {x['hla']:x for x in self.zero()['alleles']}
        self.assertEqual(alleles['HLA-A*99:01']['zero_fraction']['numerator'],2)
        self.assertEqual(alleles['HLA-A*99:01']['positive_count'],1)
        b = alleles['HLA-B*99:02']['positive_half_life']
        self.assertEqual(b['minimum'],'2')
        self.assertEqual(Decimal(b['median']),Decimal('4'))
        self.assertEqual(Decimal(b['p95']),Decimal('5.80'))
        self.assertEqual(Decimal(b['p99']),Decimal('5.96'))

    def test_group_and_partition_totals(self):
        result = self.result()
        report = self.zero(result)
        self.assertEqual(report['groups']['ordinary_hla_a']['rows'],3)
        self.assertEqual(report['groups']['ordinary_hla_b']['zero'],1)
        self.assertEqual(report['groups']['c67s_annotated_hla_b']['positive'],1)
        context = result.reports['allele_context_audit.json']
        self.assertEqual(context['ordinary_partition'],{'identifiers':2,'rows':6})
        self.assertEqual(context['c67s_partition'],{'identifiers':1,'rows':2})
        self.assertEqual(sum(x['rows'] for x in report['groups'].values()),8)

    def test_c67s_classification_never_maps_to_wild_type(self):
        hla='HLA-B*99:03(C67S)'
        self.assertEqual(audit.identifier_category(hla),'c67s_annotated_hla_b')
        self.assertEqual(audit.identifier_category('HLA-B*99:03'),'ordinary_hla_b')
        flags=[json.loads(line) for line in audit.row_flags_jsonl(self.result().records).splitlines()]
        self.assertEqual(flags[-1]['hla'],hla)
        self.assertNotIn('wild_type',flags[-1])

    def test_unexpected_identifiers_and_peptide_lengths_retained(self):
        report=self.result(self.payload+b'HLA-C*99:01 AX* 1\n').reports['allele_context_audit.json']
        self.assertEqual(report['unexpected_partition'],{'identifiers':1,'rows':1})
        self.assertEqual(report['task11_inventory']['counts_by_peptide_length']['3'],1)
        self.assertEqual(report['total_rows'],9)

    def test_non_destructive_jsonl_original_order_and_full_raw_line(self):
        result=self.result()
        text=audit.row_flags_jsonl(result.records)
        self.assertEqual(text,audit.row_flags_jsonl(result.records))
        rows=[json.loads(line) for line in text.splitlines()]
        self.assertEqual([r['source_line_number'] for r in rows],[2,4,5,6,7,8,9,10])
        self.assertEqual(rows[0]['raw_line'],self.payload.decode().splitlines(keepends=True)[1])
        self.assertEqual(rows[0]['half_life_text'],'0.00')
        self.assertEqual(rows[0]['half_life_hours_decimal'],'0.00')
        self.assertEqual(self.path.read_bytes(),self.payload)

    def test_all_row_origins_remain_unverified(self):
        rows=[json.loads(line) for line in audit.row_flags_jsonl(self.result().records).splitlines()]
        self.assertEqual({row['provenance_status'] for row in rows},{audit.ROW_PROVENANCE})
        self.assertTrue(rows[0]['exact_zero'])
        self.assertFalse(rows[2]['exact_zero'])
        self.assertTrue(all(row['provenance_status'] not in {'synthetic','confirmed_experimental','left_censored'} for row in rows))

    def test_decimal_precision_and_smallest_positive_values(self):
        report=self.zero()
        self.assertEqual(report['smallest_positive_values'][0]['half_life_hours_decimal'],'0.125')
        self.assertEqual(report['positive_reported_decimal_places'],{'0':1,'2':2,'3':1})

    def test_positive_only_empty_singleton_and_even_sample(self):
        self.assertIsNone(audit.quantile([],50))
        self.assertEqual(audit.quantile([Decimal('7')],95),Decimal('7'))
        self.assertEqual(audit.quantile([Decimal('1'),Decimal('3')],50),Decimal('2'))
        report=self.zero(self.result(b'HLA Pep Thalf\nHLA-A*99:01 ACD 0\n'))
        self.assertEqual(report['positive_half_life']['count'],0)
        self.assertIsNone(report['positive_half_life']['median'])

    def test_high_zero_fraction_is_descriptive_and_threshold_inclusive(self):
        report=self.zero()
        self.assertEqual({x['hla'] for x in report['high_zero_fraction_alleles']},{'HLA-A*99:01','HLA-B*99:03(C67S)'})
        self.assertIn('not a statistical test',report['high_zero_fraction_rule'])
        self.assertEqual(report['observation_count'],8)

    def test_negative_values_retained_as_anomaly(self):
        result=self.result(self.payload+b'HLA-A*99:01 ACDE -1.00\n')
        self.assertEqual(self.zero(result)['groups']['ordinary_hla_a']['negative'],1)
        self.assertEqual(len(result.records),9)

    def test_repeated_keys_are_not_aggregated_or_removed(self):
        result=self.result(self.payload+self.payload.splitlines(keepends=True)[1])
        self.assertEqual(len(result.records),9)
        self.assertEqual(result.reports['allele_context_audit.json']['task11_inventory']['duplicate_key_count'],1)
        self.assertEqual(self.zero(result)['zero_count'],5)

    def test_checksum_gate_precedes_inventory(self):
        with patch.object(raw,'inventory',side_effect=AssertionError('Must not analyze')),self.assertRaisesRegex(ValueError,'checksum mismatch'):
            audit.audit(self.path,paths=self.paths,evidence=self.evidence)
        self.assertEqual(self.path.read_bytes(),self.payload)

    def test_invalid_checksum_format(self):
        with self.assertRaises(ValueError):
            audit.audit(self.path,paths=self.paths,expected_sha256='bad',evidence=self.evidence)

    def test_malformed_and_nonfinite_input_rejected(self):
        for line in [b'HLA-A*99:01 ACD\n',b'HLA-A*99:01 ACD nan\n',b'HLA-A*99:01 ACD Inf\n',
                     b'HLA-A*99:01 ACD bad\n',b'HLA-A*99:01 ACD NA\n']:
            with self.subTest(line=line),self.assertRaisesRegex(ValueError,'structural validation'):
                self.result(self.payload+line)

    def test_header_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            self.result(b'HLA-A*99:01 ACD 1\n')

    def test_evidence_register_valid_and_strict(self):
        self.assertEqual(audit.validate_evidence(self.evidence),self.evidence)
        for key,value in [('schema_version',2),('source_id','other'),('publication_doi','10.1234/other'),
                          ('verified_at_utc','2026-99-99T00:00:00Z')]:
            document=deepcopy(self.evidence);document[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):audit.validate_evidence(document)
        document=deepcopy(self.evidence);document['unrecognized']=True
        with self.assertRaises(ValueError):audit.validate_evidence(document)

    def test_evidence_rejects_unsupported_status_mapping_and_bad_checksum(self):
        for mutation in ('status','mapping','hash','url'):
            document=deepcopy(self.evidence)
            if mutation=='status':document['items'][0]['status']='confirmed_experimental'
            if mutation=='mapping':document['table_ii']['entries'][-1]['raw_identifier']='HLA-B*99:03'
            if mutation=='hash':document['snapshots'][0]['sha256']='bad'
            if mutation=='url':document['snapshots'][0]['url']='http://example.org'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):audit.validate_evidence(document)

    def test_duplicate_evidence_json_keys_rejected(self):
        self.evidence_path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError):audit.load_evidence(self.evidence_path,paths=self.paths)

    def test_publication_partial_coverage_is_not_claimed_complete(self):
        report=self.result().reports['publication_reconciliation.json']
        self.assertEqual(report['matching_count_entries'],3)
        self.assertEqual(report['count_discrepancies'],[])
        self.assertFalse(report['all_counts_reconciled'])

    def test_count_discrepancy_missing_and_extra_identifiers_reported(self):
        self.evidence['table_ii']['entries'][0]['count']=4
        self.evidence['table_ii']['entries'].pop(1)
        self.evidence['table_ii']['entries'].append({'publication_identifier':'HLA-A*99:09',
            'raw_identifier':'HLA-A*99:09','count':2,'p05_text':'0','p95_text':'1'})
        report=self.result().reports['publication_reconciliation.json']
        self.assertEqual(len(report['count_discrepancies']),3)
        self.assertFalse(report['all_counts_reconciled'])
        self.assertEqual(len(self.result().records),8)

    def test_percentile_comparison_is_exploratory(self):
        report=self.result().reports['publication_reconciliation.json']
        b=next(x for x in report['comparison'] if x['raw_identifier']=='HLA-B*99:02')
        self.assertEqual(Decimal(b['percentiles']['p95']['observed_type7']),Decimal('5.60'))
        self.assertIn('no row correction',b['percentiles']['p95']['interpretation'])
        self.assertIn('Type 7',report['quantile_convention'])

    def test_table_ii_html_extraction_explicit_typography_mapping(self):
        html='<section id="T2"><table><tr><td>X</td><td>HLA-A*99:01</td><td>3</td><td>5</td><td>0</td><td>Y</td><td>HLA-B*99:03 (C67S)</td><td>2</td><td>1</td><td>0</td></tr></table></section>'
        entries=audit.extract_table_ii(html)
        self.assertEqual(len(entries),2)
        self.assertEqual(entries[1]['publication_identifier'],'HLA-B*99:03 (C67S)')
        self.assertEqual(entries[1]['raw_identifier'],'HLA-B*99:03(C67S)')

    def test_ambiguous_or_missing_publication_table_rejected(self):
        for html in ['<table></table>','<section id="T2"><tr><td>HLA-A*99:01</td><td>3</td></tr></section>']:
            with self.subTest(html=html),self.assertRaises(ValueError):audit.extract_table_ii(html)

    def test_publication_snapshot_replay_and_checksum_gate(self):
        payload=b'<section id="T2"><table><tr><td>X</td><td>HLA-A*99:01</td><td>3</td><td>5</td><td>0</td><td></td><td></td><td></td><td></td><td></td></tr></table></section>'
        path=self.root/'publication.html';path.write_bytes(payload)
        evidence=deepcopy(self.evidence)
        evidence['table_ii']['entries']=audit.extract_table_ii(payload.decode())
        snapshot=next(x for x in evidence['snapshots'] if x['filename']=='publication_article.html')
        snapshot['sha256']=hashlib.sha256(payload).hexdigest();snapshot['byte_size']=len(payload)
        self.assertEqual(audit.verify_publication_snapshot(path,evidence),evidence['table_ii']['entries'])
        path.write_bytes(payload+b'changed')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):audit.verify_publication_snapshot(path,evidence)

    def test_publication_snapshot_table_disagreement_is_rejected(self):
        payload=b'<section id="T2"><table><tr><td>X</td><td>HLA-A*99:01</td><td>4</td><td>5</td><td>0</td><td></td><td></td><td></td><td></td><td></td></tr></table></section>'
        path=self.root/'publication.html';path.write_bytes(payload)
        evidence=deepcopy(self.evidence)
        snapshot=next(x for x in evidence['snapshots'] if x['filename']=='publication_article.html')
        snapshot['sha256']=hashlib.sha256(payload).hexdigest();snapshot['byte_size']=len(payload)
        with self.assertRaisesRegex(ValueError,'differs from evidence'):audit.verify_publication_snapshot(path,evidence)

    def test_offline_read_only_cli_and_deterministic_reports(self):
        before=sorted(self.root.rglob('*'))
        first=self.cli(['--json']);second=self.cli(['--json'])
        self.assertEqual(first,second)
        self.assertEqual(first[0],0,first[2])
        self.assertEqual(before,sorted(self.root.rglob('*')))
        self.assertEqual(self.path.read_bytes(),self.payload)
        self.assertEqual(json.loads(first[1])['zero_value_audit.json']['zero_count'],4)

    def test_checksum_override_requires_explicit_input(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['dtu2016','audit','--expected-sha256',self.checksum],env=self.env),1)

    def test_cli_wrong_checksum_has_clear_failure(self):
        self.path.write_bytes(self.payload+b'bad')
        status,out,err=self.cli()
        self.assertEqual(status,1)
        self.assertEqual(out,'')
        self.assertIn('checksum mismatch',err)

    def test_explicit_run_reports_hashes_and_no_overwrite(self):
        result=self.result();run=self.create_run()
        receipt=audit.write_audit(result,run/'reports',paths=self.paths)
        self.assertEqual(receipt['row_count'],8)
        for name,digest in receipt['reports'].items():
            self.assertEqual(raw.sha256_file(run/'reports'/name),digest)
        self.assertEqual((run/'reports'/'row_flags.jsonl').read_text(),audit.row_flags_jsonl(result.records))
        with self.assertRaises(FileExistsError):audit.write_audit(result,run/'reports',paths=self.paths)
        self.assertEqual(self.path.read_bytes(),self.payload)

    def test_reports_require_explicit_matching_manifest_input(self):
        result=self.result();run=self.create_run(include_input=False)
        with self.assertRaisesRegex(ValueError,'explicitly record'):audit.write_audit(result,run/'reports',paths=self.paths)
        self.assertEqual(list((run/'reports').iterdir()),[])

    def test_raw_changed_before_report_write_rejected(self):
        result=self.result();run=self.create_run()
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed before'):audit.write_audit(result,run/'reports',paths=self.paths)
        self.assertEqual(list((run/'reports').iterdir()),[])

    def test_unsafe_report_destination(self):
        with self.assertRaises(ValueError):audit.write_audit(self.result(),self.root/'reports',paths=self.paths)

    def test_reports_directory_symlink_rejected(self):
        result=self.result();run=self.create_run()
        reports=run/'reports'
        reports.rmdir()
        reports.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):audit.write_audit(result,reports,paths=self.paths)
        self.assertFalse((self.root/'zero_value_audit.json').exists())

    def test_cli_writes_complete_reports_only_when_requested(self):
        run=self.create_run()
        status,out,err=self.cli(['--reports-dir',str(run/'reports')])
        self.assertEqual(status,0,err)
        self.assertEqual(json.loads(out)['zero_count'],4)
        names={path.name for path in (run/'reports').iterdir()}
        self.assertEqual(names,{'zero_value_audit.json','allele_context_audit.json',
            'publication_reconciliation.json','evidence_register.json','row_flags.jsonl','audit_report_checksums.json'})

    def test_existing_cli_compatibility(self):
        for args in [['paths','--json'],['sources','validate'],['sources','list','--json'],['runs','list','--json']]:
            with self.subTest(args=args),redirect_stdout(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['dtu2016','inspect','--input',str(self.path),'--json'],env=self.env),0)


if __name__=='__main__':
    unittest.main()
