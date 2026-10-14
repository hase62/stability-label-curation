"""Synthetic OOXML and mocked responses only; never fetch publisher files in tests."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
import zipfile

from stability_label_curation import jappe_2020_sources as jappe
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


def workbook(*, hidden=False, extra='', target='worksheets/sheet1.xml', root='xl/workbook.xml', shared=True):
    ns=jappe.MAIN; rel=jappe.REL; doc=jappe.DOCREL
    parts={'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        '_rels/.rels':f'<Relationships xmlns="{rel}"><Relationship Id="r1" Type="{doc}/officeDocument" Target="{root}"/></Relationships>',
        root:f'<workbook xmlns="{ns}" xmlns:r="{doc}"><sheets><sheet name="Fixture" sheetId="1" r:id="r1"/><sheet name="Auxiliary" sheetId="2" r:id="r2" state="{("hidden" if hidden else "visible")}"/></sheets><definedNames/></workbook>',
        jappe._rels_part(root):f'<Relationships xmlns="{rel}"><Relationship Id="r1" Type="{doc}/worksheet" Target="{target}"/><Relationship Id="r2" Type="{doc}/worksheet" Target="worksheets/sheet2.xml"/>'+ (f'<Relationship Id="s" Type="{doc}/sharedStrings" Target="sharedStrings.xml"/>' if shared else '')+'</Relationships>',
        jappe._part(root,target):f'<worksheet xmlns="{ns}"><dimension ref="A1:XFD999999"/><sheetData><row r="1"><c r="A1" t="{("s" if shared else "inlineStr")}">'+ ('<v>0</v>' if shared else '<is><t>Peptide</t></is>')+'</c><c r="C1" t="inlineStr"><is><t>Tm target</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>ACDEFGHIK</t></is></c><c r="C2"><f>1+1</f><v>123.00</v></c></row><row r="3"/><row r="5"><c r="A5"><v>0</v></c><c r="C5" t="e"><v>#N/A</v></c></row></sheetData><mergeCells><mergeCell ref="A1:B1"/></mergeCells>'+extra+'</worksheet>',
        jappe._part(root,'worksheets/sheet2.xml'):f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>unknown auxiliary</t></is></c></row></sheetData></worksheet>'}
    if shared:parts[jappe._part(root,'sharedStrings.xml')]=f'<sst xmlns="{ns}" count="1" uniqueCount="1"><si><t xml:space="preserve"> Peptide </t></si></sst>'
    return zip_payload(parts)


def zip_payload(parts):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_STORED) as z:
        for name,value in parts.items():z.writestr(name,value)
    return data.getvalue()


class Response(io.BytesIO):
    status=200
    def __init__(self,payload,url,*,length=True,content_type='application/octet-stream',fail=False,final=None):
        super().__init__(payload);self.url=final or url;self.headers={'Content-Type':content_type,'ETag':'fixture-etag','Last-Modified':'fixture-date'}
        if length:self.headers['Content-Length']=str(len(payload))
        self.read_sizes=[];self.fail=fail
    def geturl(self):return self.url
    def read(self,size=-1):
        self.read_sizes.append(size)
        if self.fail and len(self.read_sizes)>1:raise OSError('fixture failed response')
        return super().read(min(size,64) if self.fail else size)


class JappeSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.payload=workbook();self.xlsx=self.root/'fixture.xlsx';self.xlsx.write_bytes(self.payload)
        self.pdf=self.root/'description.pdf';self.pdf.write_bytes(b'%PDF-1.7\nfixture only\n%%EOF\n')
        self.manifest=jappe.load_artifacts(paths=self.paths);self.entries={e['artifact_id']:e for e in self.manifest['artifacts']}
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Unexpected network'))
        self.network.start();self.addCleanup(self.network.stop)

    def mocked_fetch(self,*,selected=None,responses=None,**kwargs):
        selected=selected or ['supplementary_data_3'];made=[]
        def open(request,timeout):
            identifier=next(k for k,e in self.entries.items() if e['source_hyperlink_url']==request.full_url)
            body=self.pdf.read_bytes() if identifier=='descriptions' else self.payload
            response=Response(body,request.full_url,**(responses or {}));made.append(response)
            self.assertEqual(request.get_header('Accept-encoding'),'identity')
            self.assertGreater(timeout,0)
            return response
        class Opener:pass
        opener=Opener();opener.open=open
        with patch.object(jappe,'build_opener',return_value=opener):
            return jappe.fetch(paths=self.paths,artifacts=selected,**kwargs),made

    def destination(self,id='supplementary_data_3'):
        return self.paths.project_data_dir/'jappe_2020'/self.entries[id]['filename']

    def test_publisher_manifest_registry_agreement_and_four_only(self):
        self.assertEqual(set(self.entries),set(jappe.ARTIFACT_IDS))
        self.assertTrue(all(x['publisher_sha256'] is None for x in self.entries.values()))

    def test_allowlist_rejects_other_artifacts_without_requests(self):
        for ids in (['supplementary_data_6'],['supplementary_data_3','supplementary_data_3'],[]):
            with self.subTest(ids=ids),self.assertRaises(ValueError):jappe.fetch(paths=self.paths,artifacts=ids)
        self.assertFalse(self.paths.project_data_dir.exists())

    def test_timeout_limits(self):
        for value in (0,-1,float('inf'),float('nan'),121):
            with self.subTest(value=value),self.assertRaises(ValueError):jappe.fetch(paths=self.paths,timeout=value)

    def test_streamed_acquisition_exact_bytes_and_sha(self):
        result,made=self.mocked_fetch();self.assertFalse(result['errors'])
        self.assertEqual(self.destination().read_bytes(),self.payload)
        r=result['artifacts'][0];self.assertEqual(r['local_sha256'],hashlib.sha256(self.payload).hexdigest())
        self.assertIsNone(r['publisher_sha256']);self.assertEqual(r['acquisition'],'downloaded')
        self.assertEqual(r['server_metadata']['etag'],'fixture-etag')
        self.assertTrue(all(0<size<=65536 for size in made[0].read_sizes))
        self.assertFalse(list(self.destination().parent.glob('*.partial')))

    def test_existing_regular_file_reused_offline_and_not_replaced(self):
        self.destination().parent.mkdir(parents=True);other=workbook(hidden=True);self.destination().write_bytes(other)
        result=jappe.fetch(paths=self.paths,artifacts=['supplementary_data_3'])
        self.assertFalse(result['errors']);self.assertEqual(self.destination().read_bytes(),other)
        r=result['artifacts'][0];self.assertEqual(r['acquisition'],'existing_artifact_reused');self.assertIsNone(r['http_status'])
        self.assertEqual(r['local_sha256'],hashlib.sha256(other).hexdigest())

    def test_existing_invalid_bytes_preserved(self):
        self.destination().parent.mkdir(parents=True);self.destination().write_bytes(b'existing different bytes')
        result=jappe.fetch(paths=self.paths,artifacts=['supplementary_data_3'])
        self.assertTrue(result['errors']);self.assertEqual(self.destination().read_bytes(),b'existing different bytes')

    def test_failed_response_cleanup(self):
        result,_=self.mocked_fetch(responses={'fail':True})
        self.assertTrue(result['errors']);self.assertFalse(self.destination().exists())
        self.assertEqual(list(self.destination().parent.iterdir()),[])

    def test_invalid_download_not_published(self):
        for body in (b'<html>error</html>',b'not a zip',zip_payload({'not_workbook.xml':'hello'})):
            self.payload=body;result,_=self.mocked_fetch()
            self.assertTrue(result['errors']);self.assertFalse(self.destination().exists())
            self.assertEqual(list(self.destination().parent.iterdir()),[])

    def test_html_content_type_rejected_before_body(self):
        result,made=self.mocked_fetch(responses={'content_type':'text/html'})
        self.assertTrue(result['errors']);self.assertEqual(made[0].read_sizes,[])

    def test_content_length_cap_rejected_before_body(self):
        with patch.object(jappe,'MAX_ARTIFACT_BYTES',len(self.payload)-1):result,made=self.mocked_fetch()
        self.assertTrue(result['errors']);self.assertEqual(made[0].read_sizes,[])

    def test_unknown_length_streaming_cap_and_cleanup(self):
        limit=len(self.payload)-1
        with patch.object(jappe,'MAX_ARTIFACT_BYTES',limit):result,made=self.mocked_fetch(responses={'length':False})
        self.assertTrue(result['errors']);self.assertEqual(result['downloaded_bytes_this_invocation'],limit)
        self.assertFalse(self.destination().exists())

    def test_cumulative_task_limit(self):
        with patch.object(jappe,'MAX_TASK_BYTES',2*len(self.payload)):
            result,made=self.mocked_fetch(selected=list(jappe.ARTIFACT_IDS))
        self.assertEqual(len(result['artifacts']),2);self.assertEqual(len(result['errors']),2)
        self.assertEqual(result['downloaded_bytes_this_invocation'],2*len(self.payload));self.assertEqual(len(made),2)

    def test_invalid_content_length_and_mismatch(self):
        for length in ('invalid',str(len(self.payload)+1)):
            def opener_factory(*args):
                class Opener:
                    def open(inner,request,timeout):
                        response=Response(self.payload,request.full_url);response.headers['Content-Length']=length;return response
                return Opener()
            with patch.object(jappe,'build_opener',side_effect=opener_factory):result=jappe.fetch(paths=self.paths,artifacts=['supplementary_data_3'])
            self.assertTrue(result['errors']);self.assertFalse(self.destination().exists())

    def test_downgrade_credentials_wrong_artifact_and_host_rejected(self):
        entry=self.entries['supplementary_data_3'];url=entry['source_hyperlink_url']
        bad=[url.replace('https:','http:'),url.replace('media.springernature.com','evil.example'),
             url.replace('MOESM6','MOESM9'),url.replace('https://','https://user:secret@'),url+'?token=secret',url+'#fragment']
        for value in bad:
            with self.subTest(url=value),self.assertRaises(ValueError):jappe.allowed_url(value,entry['filename'])

    def test_redirect_validated_before_following(self):
        entry=self.entries['supplementary_data_3'];url=entry['source_hyperlink_url'];redirect=jappe._Redirects(entry['filename'])
        with self.assertRaises(ValueError):redirect.redirect_request(Request(url),None,302,'',{},'https://evil.example/data')
        official=url.replace('media.springernature.com/original/springer-static','static-content.springer-cdn.com')
        self.assertEqual(redirect.redirect_request(Request(url),None,302,'',{},official).full_url,official)

    def test_unverified_final_response_url_rejected(self):
        result,made=self.mocked_fetch(responses={'final':'https://evil.example/data'})
        self.assertTrue(result['errors']);self.assertEqual(made[0].read_sizes,[])

    def test_racing_destination_not_overwritten(self):
        original_link=os.link
        def race(src,dst,**kwargs):
            self.destination().write_bytes(b'concurrent artifact');return original_link(src,dst,**kwargs)
        with patch.object(jappe.os,'link',side_effect=race):result,_=self.mocked_fetch()
        self.assertTrue(result['errors']);self.assertEqual(self.destination().read_bytes(),b'concurrent artifact')
        self.assertEqual(list(self.destination().parent.iterdir()),[self.destination()])

    def test_symlink_artifact_preserved(self):
        self.destination().parent.mkdir(parents=True);self.destination().symlink_to(self.xlsx)
        result=jappe.fetch(paths=self.paths,artifacts=['supplementary_data_3'])
        self.assertTrue(result['errors']);self.assertTrue(self.destination().is_symlink())

    def test_source_directory_symlink_escape_refused(self):
        self.paths.project_data_dir.mkdir(parents=True);(self.paths.project_data_dir/'jappe_2020').symlink_to(self.root)
        result=jappe.fetch(paths=self.paths,artifacts=['supplementary_data_3'])
        self.assertTrue(result['errors']);self.assertFalse((self.root/self.entries['supplementary_data_3']['filename']).exists())

    def test_invalid_data_root_rejected(self):
        bad=replace(self.paths,project_data_dir=self.paths.project_data_dir/'../other')
        with self.assertRaises(ValueError):jappe.fetch(paths=bad,artifacts=['supplementary_data_3'])

    def test_zip_crc_failure(self):
        changed=self.payload.replace(b'123.00',b'124.00');self.xlsx.write_bytes(changed)
        with self.assertRaises((ValueError,zipfile.BadZipFile)):jappe.workbook_inventory(self.xlsx)

    def test_zip_traversal_member_rejected(self):
        self.xlsx.write_bytes(zip_payload({'../escape':'x','[Content_Types].xml':'x','_rels/.rels':'x'}))
        with self.assertRaises(ValueError):jappe.workbook_inventory(self.xlsx)

    def test_zip_expansion_limits(self):
        with patch.object(jappe,'MAX_UNCOMPRESSED_BYTES',1),self.assertRaises(ValueError):jappe.workbook_inventory(self.xlsx)
        with patch.object(jappe,'MAX_ZIP_ENTRIES',1),self.assertRaises(ValueError):jappe.workbook_inventory(self.xlsx)

    def test_sheet_order_visibility_relationships_and_shared_strings(self):
        self.xlsx.write_bytes(workbook(hidden=True));report=jappe.workbook_inventory(self.xlsx)
        self.assertEqual([s['name'] for s in report['sheets']],['Fixture','Auxiliary'])
        self.assertEqual(report['sheets'][1]['visibility'],'hidden');self.assertEqual(report['sheets'][0]['worksheet_part'],'xl/worksheets/sheet1.xml')
        self.assertTrue(report['shared_strings']['present'])
        self.assertEqual(report['sheets'][0]['candidate_header_text_rows'][0]['text_cells'][0]['resolved_shared_string_text'],' Peptide ')

    def test_alternate_workbook_part_and_parent_relative_resolution(self):
        self.xlsx.write_bytes(workbook(root='custom/book.xml',target='../custom/worksheets/sheet1.xml'))
        self.assertEqual(jappe.workbook_inventory(self.xlsx)['workbook_part'],'custom/book.xml')
        self.assertEqual(jappe._part('xl/workbook.xml','/xl/worksheets/sheet1.xml'),'xl/worksheets/sheet1.xml')
        for target in ('../../escape','https://evil.example/sheet.xml','file:///tmp/sheet.xml'):
            with self.subTest(target=target),self.assertRaises(ValueError):jappe._part('xl/workbook.xml',target)

    def test_dimensions_counts_blocks_and_formula_cache_not_evaluated(self):
        sheet=jappe.workbook_inventory(self.xlsx)['sheets'][0]
        self.assertEqual(sheet['declared_dimension'],'A1:XFD999999')
        self.assertEqual(sheet['physical_row_elements'],4);self.assertEqual(sheet['populated_row_elements'],3)
        self.assertEqual(sheet['physical_cell_elements'],6);self.assertEqual(sheet['formula_cell_count'],1)
        self.assertEqual(sheet['formula_cell_samples'][0]['stored_value_text'],'123.00')
        self.assertEqual(sheet['formula_cell_samples'][0]['formula_text'],'1+1')
        self.assertTrue(sheet['multiple_block_indications']['separated_column_ranges'])
        self.assertTrue(sheet['multiple_block_indications']['separated_row_ranges'])
        self.assertIsNone(sheet['scientific_row_count'])

    def test_no_shared_strings_and_unknown_xml_reported(self):
        self.xlsx.write_bytes(workbook(shared=False,extra='<mystery xmlns="urn:unsupported"/><autoFilter ref="A1:C2"/>'))
        report=jappe.workbook_inventory(self.xlsx);self.assertFalse(report['shared_strings']['present'])
        unknown=report['sheets'][0]['uninterpreted_or_unsupported_xml_structures']
        self.assertIn('{urn:unsupported}mystery',unknown);self.assertIn('{'+jappe.MAIN+'}autoFilter',unknown)

    def test_invalid_workbook_and_xml_entity_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.payload)) as z:parts={name:z.read(name) for name in z.namelist()}
        for content in (b'<invalid/>',b'<workbook',b'<!DOCTYPE x [<!ENTITY x "unsafe">]><x/>'):
            parts['xl/workbook.xml']=content;self.xlsx.write_bytes(zip_payload(parts))
            with self.assertRaises(ValueError):jappe.workbook_inventory(self.xlsx)

    def test_missing_sheet_part_and_relationship(self):
        with zipfile.ZipFile(io.BytesIO(self.payload)) as z:parts={name:z.read(name) for name in z.namelist()}
        del parts['xl/worksheets/sheet1.xml'];self.xlsx.write_bytes(zip_payload(parts))
        with self.assertRaisesRegex(ValueError,'missing'):jappe.workbook_inventory(self.xlsx)

    def test_pdf_minimal_validation_and_html_rejection(self):
        self.assertIn('pdf_validation',jappe.validate_artifact(self.pdf,'pdf'))
        self.pdf.write_bytes(b'<html>404</html>')
        with self.assertRaises(ValueError):jappe.validate_artifact(self.pdf,'pdf')

    def test_deterministic_read_only_inventory_with_local_overrides(self):
        overrides={id:self.pdf if id=='descriptions' else self.xlsx for id in jappe.ARTIFACT_IDS}
        before=sorted(self.root.rglob('*'));payload=self.xlsx.read_bytes()
        first=jappe.inventory(paths=self.paths,files=overrides);second=jappe.inventory(paths=self.paths,files=overrides)
        self.assertEqual(raw.json_report(first),raw.json_report(second));self.assertEqual(payload,self.xlsx.read_bytes())
        self.assertEqual(before,sorted(self.root.rglob('*')));self.assertIsNone(first['verified_scientific_observation_counts'])

    def test_inventory_symlink_refused(self):
        alias=self.root/'alias.xlsx';alias.symlink_to(self.xlsx)
        with self.assertRaises(OSError):jappe.workbook_inventory(alias)

    def test_unknown_local_override_refused(self):
        with self.assertRaises(ValueError):jappe.inventory(paths=self.paths,files={'unrelated':self.xlsx})

    def test_cli_inventory_offline_and_command_compatibility(self):
        arguments=['jappe2020','inventory','--json']
        for id in jappe.ARTIFACT_IDS:arguments+=['--file',id+'='+str(self.pdf if id=='descriptions' else self.xlsx)]
        out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(main(arguments,env=self.env),0)
        self.assertEqual(len(json.loads(out.getvalue())['artifacts']),4)
        for args in (['paths','--json'],['sources','validate'],['runs','list','--json']):
            with redirect_stdout(io.StringIO()):self.assertEqual(main(args,env=self.env),0)

    def test_cli_failure_and_invalid_override(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['jappe2020','inventory','--file','wrong'],env=self.env),1)
        with patch.object(jappe,'fetch',return_value={'errors':[{'error':'fixture'}]}),redirect_stdout(io.StringIO()):
            self.assertEqual(main(['jappe2020','fetch'],env=self.env),1)

    def test_report_publication_requires_hashed_inputs_and_no_overwrite(self):
        self.paths.project_data_dir.mkdir(parents=True)
        x=self.paths.project_data_dir/'fixture.xlsx';x.write_bytes(self.xlsx.read_bytes())
        p=self.paths.project_data_dir/'fixture.pdf';p.write_bytes(self.pdf.read_bytes())
        overrides={id:p if id=='descriptions' else x for id in jappe.ARTIFACT_IDS}
        document=jappe.inventory(paths=self.paths,files=overrides)
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True,inputs=[x,p])
        jappe.write_inventory(document,run/'reports',paths=self.paths)
        with self.assertRaises(FileExistsError):jappe.write_inventory(document,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):jappe.write_inventory(document,self.root/'reports',paths=self.paths)
        x.write_bytes(b'changed')
        with self.assertRaises(ValueError):jappe.write_inventory(document,run/'reports',paths=self.paths)

    def test_report_missing_run_input_rejected(self):
        self.paths.project_data_dir.mkdir(parents=True)
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        document=jappe.inventory(paths=self.paths,files={id:self.pdf if id=='descriptions' else self.xlsx for id in jappe.ARTIFACT_IDS})
        with self.assertRaises(ValueError):jappe.write_inventory(document,run/'reports',paths=self.paths)

    def test_tls_verification_context(self):
        with patch.object(jappe,'HTTPSHandler',wraps=jappe.HTTPSHandler) as handler:
            self.mocked_fetch()
        context=handler.call_args.kwargs['context']
        self.assertTrue(context.check_hostname);self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)


if __name__=='__main__':unittest.main()
