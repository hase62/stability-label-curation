"""Synthetic figure workbooks and mocked publisher responses; offline by default."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
from xml.sax.saxutils import escape
import zipfile

from stability_label_curation import jappe_2020_figure_audit as audit
from stability_label_curation import jappe_2020_sources as sources
from stability_label_curation import jappe_2020_row_audit as cells
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


def fixture(*, formula=False, bad_header=False, extra_sheet=False):
    ns,rel,doc=sources.MAIN,sources.REL,sources.DOCREL
    parts={'[Content_Types].xml':'<Types/>','_rels/.rels':f'<Relationships xmlns="{rel}"><Relationship Id="r" Type="{doc}/officeDocument" Target="xl/workbook.xml"/></Relationships>'}
    sheets=[];relationships=[]
    names=list(audit.SCHEMAS)+(['Unknown Figure 2e'] if extra_sheet else [])
    def c(ref,text,numeric=False):
        if text is None:return f'<c r="{ref}"/>'
        return f'<c r="{ref}"><v>{text}</v></c>' if numeric else f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
    def row(n,values):return f'<row r="{n}">'+''.join(c(chr(65+i)+str(n),v,k) for i,(v,k) in enumerate(values))+'</row>'
    for i,name in enumerate(names,1):
        sheets.append(f'<sheet name="{name}" sheetId="{i}" r:id="s{i}"/>')
        relationships.append(f'<Relationship Id="s{i}" Type="{doc}/worksheet" Target="worksheets/sheet{i}.xml"/>')
        peak=name.startswith('Suppl Fig 3');kinetic=name=='Suppl Fig 4'
        content=row(1,[(name+' source block',False)])+'<row r="2"/>'
        if peak:
            content+=row(3,[('Temperature',False),('37',True),(None,False),(None,False)])
            content+=row(4,[('Peptide',False),('Replicate 1 ',False),('Replicate 2 ',False),('Replicate 3 ',False)])
            content+=row(5,[('ACDEFGHIK',False),('0.00',True),('2',True),('3',True)])
            if name.endswith('3c'):content+='<row r="22">'+c('OL22','1',True)+c('OM22','2',True)+'</row>'
            if name.endswith('3b'):content+='<row r="18">'+c('QE18','\u200b')+'</row>'
        elif name in audit.SCHEMAS:
            header=['Peptide','t1/2','Tm'] if kinetic else ['Peptide','Tm','Median peak area at 37℃']
            if bad_header and name.endswith('5a'):header[1]='guessed Tm'
            content+=row(3,[(s,False) for s in header])
            content+=row(4,[('ACDEFGHIK',False),('1' if kinetic else '40.000004',True),('40' if kinetic else '100',True)])
            if formula and name.endswith('5a'):
                content=content.replace('<c r="B4"><v>40.000004</v></c>','<c r="B4"><f>40+1</f><v>41</v></c>')
        else:content+=row(3,[('aggregate',False),('359',True)])
        parts[f'xl/worksheets/sheet{i}.xml']=f'<worksheet xmlns="{ns}"><dimension ref="A1:XFD1048576"/><sheetData>{content}</sheetData></worksheet>'
    parts['xl/workbook.xml']=f'<workbook xmlns="{ns}" xmlns:r="{doc}"><sheets>'+''.join(sheets)+'</sheets></workbook>'
    parts['xl/_rels/workbook.xml.rels']=f'<Relationships xmlns="{rel}">'+''.join(relationships)+'</Relationships>'
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for name,content in parts.items():z.writestr(name,content)
    return buffer.getvalue()


class Response(io.BytesIO):
    status=200
    def __init__(self,body,url):
        super().__init__(body);self.url=url;self.headers={'Content-Length':str(len(body)),'Content-Type':'application/octet-stream'};self.read_sizes=[]
    def geturl(self):return self.url
    def read(self,n=-1):self.read_sizes.append(n);return super().read(n)


class FigureAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True)
        self.source=self.paths.project_data_dir/'fixture.xlsx';self.source.write_bytes(fixture())
        self.ledger=self.paths.project_data_dir/'approved.jsonl'
        records=[]
        for key in ('supplementary_data_3','supplementary_data_4','supplementary_data_5'):
            records.append({'artifact_id':key,'row_kind':'peptide_row','row_number':2,'original_peptide_text':'ACDEFGHIK',
                'fields':[{'category':'publication_described_tm_measurement','numeric':{'numeric_decimal':'40'}}]})
        self.ledger.write_text(cells.row_jsonl(records))
        self.context=self.paths.project_data_dir/'context.json';self.context.write_text(json.dumps({'peptide_rows':1,'complete_pairs':1,'pearson_all_complete_pairs':{'value':None}}))
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in ordinary tests'));self.network.start();self.addCleanup(self.network.stop)
        self.hashes={'source_data':raw.sha256_file(self.source),'approved_ledger':raw.sha256_file(self.ledger),'approved_context_report':raw.sha256_file(self.context)}
    def result(self,**kwargs):return audit.audit(paths=self.paths,source_path=self.source,ledger_path=self.ledger,context_report_path=self.context,expected_sha256=self.hashes,**kwargs)
    def refresh(self):self.hashes['source_data']=raw.sha256_file(self.source)
    def mocked_fetch(self,*,payload=None,length=None,final=None):
        responses=[]
        html=f'<a href="{audit.URL}">Source Data (download XLSX)</a>'.encode()
        class Opener:
            def open(inner,request,timeout):
                is_article=request.full_url.startswith(audit.ARTICLE)
                response=Response(html if is_article else (payload if payload is not None else fixture()),request.full_url)
                if not is_article:
                    if length is not None:response.headers['Content-Length']=length
                    if final:response.url=final
                responses.append(response);return response
        with patch.object(audit,'build_opener',return_value=Opener()),patch.object(sources,'build_opener',return_value=Opener()):
            result=audit.fetch(paths=self.paths)
        return result,responses
    def test_exact_publisher_link_and_label(self):
        link=audit.verify_link(f'<a href="{audit.URL}"> Source Data (download XLSX) </a>')
        self.assertEqual(link['source_hyperlink_url'],audit.URL)
    def test_wrong_artifact_or_label_rejected(self):
        for html in ('<a href="'+audit.URL+'">Other data</a>', '<a href="'+audit.URL.replace('MOESM11','MOESM12')+'">Source Data</a>', '<a href="'+audit.URL+'?token=x">Source Data</a>'):
            with self.subTest(html=html),self.assertRaises(ValueError):audit.verify_link(html)
    def test_article_redirect_cannot_escape(self):
        redirect=audit.ArticleRedirects()
        for url in ('http://www.nature.com/articles/s41467-020-20166-4','https://evil.example/data','https://www.nature.com/other'):
            with self.subTest(url=url),self.assertRaises(ValueError):redirect.redirect_request(Request(audit.ARTICLE),None,302,'',{},url)
    def test_official_cookie_variant_valid(self):
        audit.validate_article_url(audit.ARTICLE+'?error=cookies_not_supported')
    def test_artifact_redirect_wrong_host_rejected_before_read(self):
        with self.assertRaises(ValueError):self.mocked_fetch(final='https://evil.example/data')
        self.assertFalse((self.paths.project_data_dir/'jappe_2020'/audit.FILENAME).exists())
    def test_timeout_bound(self):
        for timeout in (0,-1,float('nan'),float('inf'),121):
            with self.subTest(timeout=timeout),self.assertRaises(ValueError):audit.fetch(paths=self.paths,timeout=timeout)
    def test_successful_atomic_fetch_sha_and_only_authorized_requests(self):
        receipt,responses=self.mocked_fetch()
        target=self.paths.project_data_dir/'jappe_2020'/audit.FILENAME
        self.assertEqual(target.read_bytes(),fixture());self.assertEqual(receipt['local_sha256'],raw.sha256_file(target))
        self.assertEqual(len(responses),2);self.assertEqual(receipt['artifact_byte_limit'],5*1024*1024)
        self.assertFalse(any(p.name.endswith('.partial') for p in target.parent.iterdir()))
    def test_existing_preservation_without_artifact_request(self):
        target=self.paths.project_data_dir/'jappe_2020'/audit.FILENAME;target.parent.mkdir();target.write_bytes(fixture())
        receipt,responses=self.mocked_fetch();self.assertEqual(receipt['acquisition'],'existing_artifact_reused');self.assertEqual(len(responses),1)
        self.assertEqual(target.read_bytes(),fixture())
    def test_early_five_mib_content_length_rejection_and_cleanup(self):
        with self.assertRaises(ValueError):self.mocked_fetch(length=str(audit.MAX_BYTES+1))
        self.assertEqual(list((self.paths.project_data_dir/'jappe_2020').iterdir()),[])
    def test_invalid_content_cleanup(self):
        with self.assertRaises((ValueError,zipfile.BadZipFile)):self.mocked_fetch(payload=b'<html>Error</html>')
        self.assertEqual(list((self.paths.project_data_dir/'jappe_2020').iterdir()),[])
    def test_existing_symlink_not_replaced(self):
        target=self.paths.project_data_dir/'jappe_2020'/audit.FILENAME;target.parent.mkdir();target.symlink_to(self.source)
        with self.assertRaises(ValueError):self.mocked_fetch()
        self.assertTrue(target.is_symlink())
    def test_existing_over_cap_not_replaced(self):
        target=self.paths.project_data_dir/'jappe_2020'/audit.FILENAME;target.parent.mkdir();target.write_bytes(b'x'*(audit.MAX_BYTES+1))
        with self.assertRaises(ValueError):self.mocked_fetch()
        self.assertEqual(target.stat().st_size,audit.MAX_BYTES+1)
    def test_sheet_order_physical_dimensions_and_semantics(self):
        result=self.result();blocks=result.reports['jappe_figure_source_inventory.json']['worksheet_blocks']
        self.assertEqual([b['worksheet'] for b in blocks],list(audit.SCHEMAS))
        self.assertEqual(blocks[0]['peptide_identifiable_rows'],1);self.assertEqual(blocks[0]['declared_dimension'],'A1:XFD1048576')
        self.assertEqual(blocks[0]['column_semantics']['B']['temperature_Celsius_text'],'37')
        self.assertEqual(blocks[2]['column_semantics']['B']['assay_context'],'C1R-A*02:01')
    def test_peak_area_zero_not_synthetic_or_zero_tm(self):
        row=next(r for r in self.result().rows if r['worksheet']=='Suppl Fig 3c' and r['original_peptide_text'])
        field=row['scientific_fields'][0];self.assertEqual(field['numeric']['numeric_decimal'],'0.00')
        self.assertEqual(field['category'],'chromatographic_peak_area');self.assertEqual(row['training_inclusion_status'],'not_assessed')
    def test_no_fig2_values_invented_from_other_sheets(self):
        report=self.result().reports['jappe_figure_population_reconciliation.json']
        self.assertEqual(report['source_data_figure_2e_c_values_recovered'],0)
        self.assertFalse(report['figure_2d_e']['full_C_distribution_reproduced'])
        self.assertFalse(report['figure_2_source_block_identified'])
    def test_approved_correlation_reused_without_calculation(self):
        with patch.object(cells,'pearson',side_effect=AssertionError('Task 1.6 not rerun')):
            report=self.result().reports['jappe_figure_population_reconciliation.json']
        self.assertEqual(report['figure_2c']['approved_task16_result_reused_without_reanalysis']['complete_pairs'],1)
    def test_strict_c_overlap_no_tm_comparison(self):
        report=self.result().reports['jappe_figure_value_comparison.json']['Suppl Fig 3c']
        self.assertEqual(report['matched_unique_peptides'],1);self.assertEqual(report['measurement_comparisons'],[])
    def test_decimal_precision_comparison(self):
        report=self.result().reports['jappe_figure_value_comparison.json']['Suppl Fig 5a']
        self.assertEqual(report['absolute_tm_errors_Celsius']['maximum'],'0.000004')
        self.assertEqual(report['counts_within_absolute_tm_tolerance']['1e-5'],1)
        self.assertEqual(report['counts_within_absolute_tm_tolerance']['0'],0)
    def test_unknown_far_cells_preserved(self):
        row=next(r for r in self.result().rows if r['worksheet']=='Suppl Fig 3c' and r['row_number']==22)
        self.assertEqual(row['row_kind'],'unresolved_physical_row');self.assertEqual([c['coordinate'] for c in row['cells']],['OL22','OM22'])
        self.assertEqual(row['scientific_fields'],[])
    def test_invisible_auxiliary_cell_preserved(self):
        row=next(r for r in self.result().rows if r['worksheet']=='Suppl Fig 3b' and r['row_number']==18)
        self.assertEqual(row['row_kind'],'auxiliary_physical_row');self.assertEqual(row['cells'][0]['decoded_text'],'\u200b')
    def test_missing_or_invalid_header_fails(self):
        self.source.write_bytes(fixture(bad_header=True));self.refresh()
        with self.assertRaises(ValueError):self.result()
    def test_formula_cache_not_a_measurement(self):
        self.source.write_bytes(fixture(formula=True));self.refresh()
        report=self.result().reports['jappe_figure_value_comparison.json']['Suppl Fig 5a']
        self.assertEqual(report['matched_unique_peptides'],1);self.assertEqual(report['measurement_comparisons'],[])
    def test_unknown_sheet_retained_not_assumed_distribution(self):
        self.source.write_bytes(fixture(extra_sheet=True));self.refresh()
        result=self.result();report=result.reports['jappe_figure_population_reconciliation.json']
        self.assertEqual(report['unrecognized_sheets_requiring_review'],['Unknown Figure 2e'])
        self.assertEqual(report['source_data_figure_2e_c_values_recovered'],0)
        self.assertTrue(any(r['worksheet']=='Unknown Figure 2e' for r in result.rows))
    def test_checksum_gate_before_any_xml(self):
        self.source.write_bytes(b'changed')
        with patch.object(cells,'read_rows',side_effect=AssertionError('Must gate first')),self.assertRaises(ValueError):self.result()
    def test_fixture_hash_requires_explicit_path(self):
        with self.assertRaises(ValueError):audit.audit(paths=self.paths,expected_sha256={'source_data':'a'*64})
    def test_all_used_input_checksums_retained(self):
        result=self.result();self.assertEqual(len(result.inputs),3)
        self.assertEqual({r['sha256'] for r in result.inputs},set(self.hashes.values()))
    def test_deterministic_offline_read_only(self):
        before=[p.read_bytes() for p in (self.source,self.ledger,self.context)]
        a,b=self.result(),self.result();self.assertEqual(raw.json_report(a.reports),raw.json_report(b.reports));self.assertEqual(cells.row_jsonl(a.rows),cells.row_jsonl(b.rows))
        self.assertEqual(before,[p.read_bytes() for p in (self.source,self.ledger,self.context)]);self.assertFalse(self.paths.project_runs_dir.exists())
    def test_malformed_xlsx_rejected_after_valid_hash(self):
        self.source.write_bytes(b'not XLSX');self.refresh()
        with self.assertRaises((ValueError,zipfile.BadZipFile)):self.result()
    def test_evidence_registry_and_publisher_checksum_validation(self):
        evidence=audit.load_evidence(paths=self.paths);evidence['publisher_sha256']='a'*64
        p=self.root/'evidence.json';p.write_text(json.dumps(evidence))
        with self.assertRaises(ValueError):self.result(evidence_path=p)
    def test_safe_reports_require_all_hashed_inputs_and_no_overwrite(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=[self.source,self.ledger,self.context],allow_dirty=True)
        checks=audit.write_reports(result,run/'reports',paths=self.paths);self.assertEqual(checks['physical_rows_preserved'],len(result.rows))
        with self.assertRaises(FileExistsError):audit.write_reports(result,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):audit.write_reports(result,self.root/'reports',paths=self.paths)
    def test_run_without_inputs_refused(self):
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        with self.assertRaises(ValueError):audit.write_reports(self.result(),run/'reports',paths=self.paths)
    def test_cli_read_only_fixture_overrides_and_old_command(self):
        args=['jappe2020','figure-audit','--json','--source-data',str(self.source),'--approved-ledger',str(self.ledger),'--approved-context-report',str(self.context)]
        for key,digest in self.hashes.items():args+=['--expected-sha256',key+'='+digest]
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        self.assertIn('jappe_figure_source_inventory.json',json.loads(output.getvalue()));self.assertFalse(self.paths.project_runs_dir.exists())
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)
    def test_unmatched_and_duplicate_reference_are_reported(self):
        approved=[json.loads(line) for line in self.ledger.read_text().splitlines()];approved.append(deepcopy(approved[0]));self.ledger.write_text(cells.row_jsonl(approved));self.hashes['approved_ledger']=raw.sha256_file(self.ledger)
        report=self.result().reports['jappe_figure_value_comparison.json']['Suppl Fig 5a'];self.assertEqual(report['ambiguous_row_numbers'],[4]);self.assertEqual(report['matched_unique_peptides'],0)
        approved[1]['original_peptide_text']='ACDEFGHIL';self.ledger.write_text(cells.row_jsonl(approved));self.hashes['approved_ledger']=raw.sha256_file(self.ledger)
        report=self.result().reports['jappe_figure_value_comparison.json']['Suppl Fig 5b'];self.assertEqual(report['source_unmatched_row_numbers'],[4])


if __name__=='__main__':unittest.main()
