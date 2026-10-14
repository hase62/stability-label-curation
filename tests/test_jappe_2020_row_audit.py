"""Synthetic OOXML field-semantic fixtures, independent of publisher workbooks."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import zipfile

from stability_label_curation import jappe_2020_sources as sources
from stability_label_curation import jappe_2020_row_audit as audit
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.__main__ import main
from stability_label_curation.paths import resolve_paths


def fixture(key,rows=None,*,inline=False):
    sheet,_,_,schema=audit.SCHEMAS[key];strings=[]
    def cell(coordinate,value,type):
        if value is None:return '<c r="'+coordinate+'"/>'
        if type=='text':
            if inline:return '<c r="'+coordinate+'" t="inlineStr"><is><t xml:space="preserve">'+escape(value)+'</t></is></c>'
            strings.append(value);return '<c r="'+coordinate+'" t="s"><v>'+str(len(strings)-1)+'</v></c>'
        return '<c r="'+coordinate+'"><v>'+escape(value)+'</v></c>'
    content='<row r="1">'+''.join(cell(chr(65+i)+'1',header,'text') for i,header in enumerate(schema))+'</row>'
    if rows is None:
        if key=='supplementary_data_5':rows=[(2,['ACDEFGHIK','40','44']),(3,['ACDEFGHIL','50','54']),(4,['ACDEFGHIM','60','64'])]
        else:rows=[(2,['ACDEFGHIK','40','0.5','0.003']),(4,['ACDEFGHIL','60','1','0.1'])]
    for number,values in rows:
        content+='<row r="'+str(number)+'">'+''.join(cell(chr(65+i)+str(number),value,'text' if i==0 else 'number') for i,value in enumerate(values))+'</row>'
    if key=='supplementary_data_4':content+='<row r="6">'+cell('E6',chr(0x200B),'text')+'</row>'
    worksheet='<worksheet xmlns="'+sources.MAIN+'"><dimension ref="A1:XFD1048576"/><sheetData>'+content+'</sheetData></worksheet>'
    rel=sources.REL;doc=sources.DOCREL
    parts={'[Content_Types].xml':'<Types/>','_rels/.rels':f'<Relationships xmlns="{rel}"><Relationship Id="root" Type="{doc}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':f'<workbook xmlns="{sources.MAIN}" xmlns:r="{doc}"><sheets><sheet name="{sheet}" sheetId="1" r:id="s1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{rel}"><Relationship Id="s1" Type="{doc}/worksheet" Target="worksheets/sheet1.xml"/>'+('' if inline else f'<Relationship Id="ss" Type="{doc}/sharedStrings" Target="sharedStrings.xml"/>')+'</Relationships>',
        'xl/worksheets/sheet1.xml':worksheet}
    if not inline:parts['xl/sharedStrings.xml']='<sst xmlns="'+sources.MAIN+'">'+''.join('<si><t xml:space="preserve">'+escape(text)+'</t></si>' for text in strings)+'</sst>'
    return archive_bytes(parts)


def archive_bytes(parts):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        for name,value in parts.items():archive.writestr(name,value)
    return data.getvalue()


class JappeRowAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True);self.files={}
        for key in sources.ARTIFACT_IDS:
            path=self.paths.project_data_dir/(key+('.pdf' if key=='descriptions' else '.xlsx'))
            path.write_bytes(b'%PDF-fixture\n%%EOF' if key=='descriptions' else fixture(key));self.files[key]=path
        self.hashes={key:raw.sha256_file(path) for key,path in self.files.items()}
        network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in unit tests'))
        network.start();self.addCleanup(network.stop)

    def result(self):return audit.audit(paths=self.paths,files=self.files,expected_sha256=self.hashes)

    def rewrite(self,key,payload):
        self.files[key].write_bytes(payload);self.hashes[key]=raw.sha256_file(self.files[key])

    def edit_sheet(self,key,operation):
        with zipfile.ZipFile(self.files[key]) as z:parts={name:z.read(name) for name in z.namelist()}
        text=parts['xl/worksheets/sheet1.xml'].decode();parts['xl/worksheets/sheet1.xml']=operation(text)
        self.rewrite(key,archive_bytes(parts))

    def cell(self,xml,strings=()):return audit.cell_record(ET.fromstring(xml),strings)

    def test_shared_string_preservation_and_physical_coordinates(self):
        structure,rows=audit.read_rows(self.files['supplementary_data_3'])
        self.assertEqual([r['row_number'] for r in rows],[1,2,4])
        cell=rows[1]['cells'][0];self.assertEqual(cell['coordinate'],'A2');self.assertEqual(cell['decoded_text'],'ACDEFGHIK')
        self.assertEqual(cell['explicit_storage_type'],'s');self.assertEqual(cell['stored_value_text'],'4')
        self.assertEqual(structure['sheets'][0]['declared_dimension'],'A1:XFD1048576')

    def test_inline_text_and_exact_headers(self):
        self.rewrite('supplementary_data_3',fixture('supplementary_data_3',inline=True))
        schemas=self.result().reports['jappe_row_schema.json']['sources']
        self.assertEqual(schemas[0]['columns'][0]['original_header_text'],'Ligand')
        self.assertEqual(schemas[0]['columns'][0]['header_coordinate'],'A1')

    def test_numeric_zero_missing_empty_blank_and_nonfinite(self):
        ns=sources.MAIN
        cases=[(None,'missing'),(f'<c xmlns="{ns}" r="B2"/>','empty'),
            (f'<c xmlns="{ns}" r="B2"><v/></c>','empty'),(f'<c xmlns="{ns}" r="B2"><v>0.00</v></c>','valid'),
            (f'<c xmlns="{ns}" r="B2"><v>NaN</v></c>','non_finite'),(f'<c xmlns="{ns}" r="B2"><v>Infinity</v></c>','non_finite'),
            (f'<c xmlns="{ns}" r="B2"><v>bad</v></c>','non_numeric'),(f'<c xmlns="{ns}" r="B2"><v> </v></c>','blank')]
        for xml,state in cases:
            with self.subTest(state=state):
                parsed=audit.parse_numeric(None if xml is None else self.cell(xml));self.assertEqual(parsed['state'],state)
        parsed=audit.parse_numeric(self.cell(f'<c xmlns="{ns}" r="B2"><v>0.00</v></c>'));self.assertEqual(parsed['numeric_decimal'],'0.00')

    def test_formula_cache_retained_without_measurement_use(self):
        cell=self.cell(f'<c xmlns="{sources.MAIN}" r="B2"><f>1+1</f><v>0.00</v></c>')
        parsed=audit.parse_numeric(cell);self.assertEqual(parsed['state'],'formula_not_evaluated')
        self.assertIsNone(parsed['numeric_decimal']);self.assertEqual(parsed['cached_numeric_decimal'],'0.00')
        self.assertEqual(cell['formula_text'],'1+1')

    def test_string_numeric_and_boolean_not_silently_used(self):
        for kind in ('str','b'):
            cell=self.cell(f'<c xmlns="{sources.MAIN}" r="B2" t="{kind}"><v>1</v></c>')
            parsed=audit.parse_numeric(cell);self.assertEqual(parsed['state'],'numeric_text_or_unsupported_storage');self.assertIsNone(parsed['numeric_decimal'])

    def test_unicode_space_and_format_characters_not_normalized(self):
        self.assertEqual(audit.text_state('\u200b'),'nonprinting');self.assertEqual(audit.text_state('\u00a0'),'blank')
        rows=self.result().rows;aux=next(r for r in rows if r['row_kind']=='auxiliary_only_row')
        self.assertEqual(aux['row_number'],6);self.assertEqual(aux['cells'][0]['decoded_text'],'\u200b')
        self.assertEqual(aux['auxiliary_or_unknown_cells'][0]['provenance_category'],'auxiliary_metadata')

    def test_mixed_field_categories_and_c_context_restriction(self):
        result=self.result();data=next(r for r in result.rows if r['artifact_id']=='supplementary_data_3' and r['row_kind']=='peptide_row')
        self.assertEqual([f['category'] for f in data['fields']],['publication_described_tm_measurement','tm_derived_transformation','predicted_binding_affinity'])
        c=next(r for r in result.rows if r['artifact_id']=='supplementary_data_5' and r['row_kind']=='peptide_row')
        self.assertEqual(c['hla_restriction'],'HLA-C*04:01');self.assertEqual([f['assay_context'] for f in c['fields']],['C1R-A*02:01','C1R-B*07:02'])
        self.assertTrue(all(f['row_assay_traceability']=='unverified' for f in c['fields']))

    def test_counts_lengths_and_duplicate_peptides(self):
        self.rewrite('supplementary_data_3',fixture('supplementary_data_3',[(2,['ACDEFGHIK','40','0','1']),(4,['ACDEFGHIK','41','1','2']),(5,['ACDEFGHI','42','1','3'])]))
        result=self.result();summary=result.reports['jappe_measurement_inventory.json']['sources'][0]
        self.assertEqual(summary['duplicate_peptide_keys'],{'ACDEFGHIK':[2,4]});self.assertEqual(summary['duplicate_extra_rows'],1)
        self.assertEqual(summary['distinct_original_peptide_strings'],2);self.assertEqual(summary['peptide_length_distribution'],{'8':1,'9':2})
        data=[r for r in result.rows if r['artifact_id']=='supplementary_data_3' and r['row_kind']=='peptide_row']
        self.assertIn('duplicate_peptide_key',data[0]['data_quality_flags']);self.assertEqual(data[0]['fields'][1]['provenance_category'],'tm_derived_transformation')
        self.assertEqual(summary['explicit_synthetic_training_targets_identified'],0)

    def test_invalid_peptide_retained_with_flags(self):
        self.rewrite('supplementary_data_3',fixture('supplementary_data_3',[(2,['AXxx','40','0','1'])]))
        row=next(r for r in self.result().rows if r['artifact_id']=='supplementary_data_3' and r['row_kind']=='peptide_row')
        self.assertFalse(row['valid_canonical_peptide_text']);self.assertEqual(row['original_peptide_text'],'AXxx');self.assertIn('noncanonical_peptide_text',row['data_quality_flags'])

    def test_zero_tm_flagged_for_plausibility_but_not_relabelled(self):
        self.rewrite('supplementary_data_3',fixture('supplementary_data_3',[(2,['ACDEFGHIK','0.00','0','0'])]))
        row=next(r for r in self.result().rows if r['artifact_id']=='supplementary_data_3' and r['row_kind']=='peptide_row')
        self.assertEqual(row['fields'][0]['numeric']['numeric_decimal'],'0.00')
        self.assertIn('outside_assay_temperature_range_37_73',row['fields'][0]['data_quality_flags'])
        self.assertEqual(row['fields'][0]['provenance_category'],'publication_described_tm_measurement')
        self.assertEqual(row['training_inclusion_status'],'not_assessed')

    def test_unmapped_numeric_zero_stays_unknown(self):
        self.edit_sheet('supplementary_data_3',lambda text:text.replace('<c r="A2"','<c r="E2"><v>0</v></c><c r="A2"'))
        result=self.result();row=next(r for r in result.rows if r['artifact_id']=='supplementary_data_3' and r['row_number']==2)
        self.assertEqual(row['auxiliary_or_unknown_cells'][0]['provenance_category'],'unknown')
        self.assertEqual(row['auxiliary_or_unknown_cells'][0]['source_cell']['stored_value_text'],'0')
        self.assertEqual(result.reports['jappe_row_schema.json']['sources'][0]['unmapped_columns'][0]['category'],'unknown')

    def test_numeric_tm_absent_peptide_is_unresolved_not_auxiliary(self):
        self.rewrite('supplementary_data_3',fixture('supplementary_data_3',[(2,[None,'40','0','1'])]))
        row=next(r for r in self.result().rows if r['artifact_id']=='supplementary_data_3' and r['row_number']==2)
        self.assertEqual(row['row_kind'],'unresolved_nonpeptide_row')

    def test_missing_vs_empty_tm_counts(self):
        self.edit_sheet('supplementary_data_3',lambda text:text.replace('<c r="B2"><v>40</v></c>','').replace('<c r="B4"><v>60</v></c>','<c r="B4"/>'))
        field=self.result().reports['jappe_measurement_inventory.json']['sources'][0]['numeric_fields']['Tm']
        self.assertEqual(field['numeric_states'],{'empty':1,'missing':1});self.assertEqual(field['valid_numeric_cell_count'],0)

    def test_header_missing_and_duplicate_header_rejected(self):
        key='supplementary_data_3'
        self.edit_sheet(key,lambda text:text.replace('r="A1"','r="A8"'))
        with self.assertRaises(ValueError):self.result()

    def test_wrong_exact_header_and_sheet_name_fail_clearly(self):
        key='supplementary_data_3'
        with zipfile.ZipFile(self.files[key]) as z:parts={name:z.read(name) for name in z.namelist()}
        parts['xl/sharedStrings.xml']=parts['xl/sharedStrings.xml'].replace(b'Ligand',b'ligand')
        self.rewrite(key,archive_bytes(parts))
        with self.assertRaisesRegex(ValueError,'headers'):self.result()

    def test_ambiguous_header_row_rejected(self):
        self.edit_sheet('supplementary_data_3',lambda text:text.replace('</sheetData>','<row r="5"><c r="A5" t="s"><v>0</v></c><c r="B5" t="s"><v>1</v></c><c r="C5" t="s"><v>2</v></c><c r="D5" t="s"><v>3</v></c></row></sheetData>'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.result()

    def test_c_pairs_partial_missingness(self):
        self.rewrite('supplementary_data_5',fixture('supplementary_data_5',[(2,['ACDEFGHIK','40','44']),(3,['ACDEFGHIL',None,'50']),(4,['ACDEFGHIM','60',None]),(5,['ACDEFGHIN',None,None])]))
        c=self.result().reports['jappe_hlac_context_audit.json']
        self.assertEqual(c['complete_pairs'],1);self.assertEqual(c['first_only_source_rows'],[4]);self.assertEqual(c['second_only_source_rows'],[3]);self.assertEqual(c['neither_valid_source_rows'],[5])
        self.assertEqual(c['distinct_context_numeric_fields'],4);self.assertIsNone(c['pearson_all_complete_pairs']['value'])

    def test_correlation_and_differences_no_outlier_removal(self):
        c=self.result().reports['jappe_hlac_context_audit.json']
        self.assertEqual(Decimal(c['pearson_all_complete_pairs']['value']),1)
        self.assertEqual(c['paired_differences_first_minus_second_Celsius']['median'],'-4')
        self.assertFalse(c['outliers_removed']);self.assertIn('not established',c['independent_replicate_status'])

    def test_pearson_centering_and_zero_variance(self):
        base=Decimal('1000000000000');x=[base+v for v in (Decimal(1),Decimal(2),Decimal(3))]
        self.assertEqual(Decimal(audit.pearson(x,x)['value']),1)
        self.assertIsNone(audit.pearson([Decimal(1)]*3,x)['value'])
        with self.assertRaises(ValueError):audit.pearson(x,[])

    def test_b_transformation_explicit_population_and_rounding(self):
        pairs=[(Decimal(40),Decimal('.5')),(Decimal(50),Decimal('.75')),(Decimal(60),Decimal(1))]
        result=audit.transformation_comparison(pairs,[p[0] for p in pairs],'B',round_to='.00001')
        self.assertEqual(result['counts_within_absolute_tolerance']['1e-12'],3)
        self.assertIn('empirical candidate',result['rounding'])
        wrong=audit.transformation_comparison(pairs,[Decimal(30),Decimal(70)],'B')
        self.assertGreater(Decimal(wrong['absolute_errors']['maximum']),0)

    def test_a_transformation_clip_and_median(self):
        pairs=[(Decimal(40),Decimal(0)),(Decimal(50),Decimal('.5')),(Decimal(60),Decimal(1))]
        result=audit.transformation_comparison(pairs,[p[0] for p in pairs],'A')
        self.assertEqual(result['absolute_errors']['maximum'],'0')
        self.assertEqual(audit.transformation_comparison([],[],'A')['status'],'not_computable_degenerate_or_missing_population')

    def test_no_synthetic_conversion_and_no_training_labels(self):
        result=self.result();self.assertEqual(result.reports['jappe_field_provenance.json']['explicit_synthetic_targets_identified'],0)
        self.assertTrue(all(r['training_inclusion_status']=='not_assessed' for r in result.rows))
        self.assertFalse(any(f['provenance_category']=='explicit_synthetic_training_target' for r in result.rows for f in r['fields']))

    def test_four_file_checksum_gate_before_any_xml_analysis(self):
        self.files['descriptions'].write_bytes(b'changed')
        with patch.object(audit,'read_rows',side_effect=AssertionError('Must gate all inputs first')):
            with self.assertRaisesRegex(ValueError,'checksum'):self.result()

    def test_fixture_hash_cannot_disable_production_identity_silently(self):
        with self.assertRaises(ValueError):audit.audit(paths=self.paths,expected_sha256=self.hashes)
        with self.assertRaises(ValueError):audit.audit(paths=self.paths,files=self.files,expected_sha256={'unknown':'0'*64})

    def test_changed_input_during_analysis_fails(self):
        reader=audit.read_rows
        def mutate(path):
            result=reader(path)
            self.files['descriptions'].write_bytes(b'changed')
            return result
        with patch.object(audit,'read_rows',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed'):self.result()

    def test_duplicate_coordinates_and_bad_row_reference_rejected(self):
        self.edit_sheet('supplementary_data_3',lambda text:text.replace('r="C2"','r="B2"'))
        with self.assertRaisesRegex(ValueError,'coordinate'):self.result()

    def test_declared_million_rows_not_expanded(self):
        result=self.result();self.assertEqual(len(result.rows),11)
        self.assertEqual(len(result.reports['jappe_row_schema.json']['structural_context']),3)

    def test_physical_row_and_cell_limits(self):
        with patch.object(audit,'MAX_PHYSICAL_ROWS',1),self.assertRaisesRegex(ValueError,'row inspection limit'):
            audit.read_rows(self.files['supplementary_data_3'])
        with patch.object(audit,'MAX_PHYSICAL_CELLS',1),self.assertRaisesRegex(ValueError,'cell inspection limit'):
            audit.read_rows(self.files['supplementary_data_3'])

    def test_formula_tm_cache_excluded_from_context_pair_count(self):
        self.edit_sheet('supplementary_data_5',lambda text:text.replace('<c r="B2"><v>40</v></c>','<c r="B2"><f>40</f><v>40</v></c>'))
        result=self.result();c=result.reports['jappe_hlac_context_audit.json']
        self.assertEqual(c['complete_pairs'],2);self.assertEqual(c['second_only_source_rows'],[2])
        field=next(r for r in result.rows if r['artifact_id']=='supplementary_data_5' and r['row_number']==2)['fields'][0]
        self.assertEqual(field['numeric']['cached_numeric_decimal'],'40');self.assertIsNone(field['numeric']['numeric_decimal'])

    def test_deterministic_reports_and_jsonl_and_input_immutability(self):
        before={k:p.read_bytes() for k,p in self.files.items()};a=self.result();b=self.result()
        self.assertEqual(raw.json_report(a.reports),raw.json_report(b.reports));self.assertEqual(audit.row_jsonl(a.rows),audit.row_jsonl(b.rows))
        self.assertEqual(before,{k:p.read_bytes() for k,p in self.files.items()})
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_cli_offline_read_only_with_explicit_fixture_hashes(self):
        args=['jappe2020','audit','--json']
        for key,path in self.files.items():args+=['--file',key+'='+str(path),'--expected-sha256',key+'='+self.hashes[key]]
        before=sorted(self.root.rglob('*'));out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(main(args,env=self.env),0)
        self.assertIn('jappe_hlac_context_audit.json',json.loads(out.getvalue()));self.assertEqual(before,sorted(self.root.rglob('*')))
        with redirect_stderr(io.StringIO()):self.assertEqual(main(['jappe2020','audit','--expected-sha256','bad'],env=self.env),1)

    def test_symlink_input_rejected(self):
        path=self.root/'alias.xlsx';path.symlink_to(self.files['supplementary_data_3'])
        with self.assertRaises(OSError):audit.read_rows(path)

    def test_evidence_duplicate_ids_and_hash_identity_validation(self):
        evidence=deepcopy(audit.load_evidence(paths=self.paths));evidence['evidence'].append(evidence['evidence'][0])
        path=self.root/'evidence.json';path.write_text(raw.json_report(evidence))
        with self.assertRaises(ValueError):audit.load_evidence(path)
        evidence['local_task15_reference_sha256']['descriptions']='not a digest';path.write_text(raw.json_report(evidence))
        with self.assertRaises(ValueError):audit.load_evidence(path)

    def test_reports_require_hashed_inputs_no_overwrite_and_verify_outputs(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=list(self.files.values()),allow_dirty=True)
        checks=audit.write_reports(result,run/'reports',paths=self.paths)
        for name,digest in checks['reports'].items():self.assertEqual(raw.sha256_file(run/'reports'/name),digest)
        lines=(run/'reports'/'jappe_rows.jsonl').read_text().splitlines();self.assertEqual(len(lines),len(result.rows))
        self.assertEqual(json.loads(lines[0])['row_kind'],'header')
        with self.assertRaises(FileExistsError):audit.write_reports(result,run/'reports',paths=self.paths)

    def test_report_paths_and_missing_inputs_fail(self):
        result=self.result()
        with self.assertRaises(ValueError):audit.write_reports(result,self.root/'reports',paths=self.paths)
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        with self.assertRaises(ValueError):audit.write_reports(result,run/'reports',paths=self.paths)

    def test_c359_not_fabricated_or_forced(self):
        result=self.result();c=result.reports['jappe_publication_reconciliation.json']['sources'][2]
        self.assertEqual(c['published_peptide_reference'],359);self.assertEqual(c['local_peptide_rows'],3);self.assertFalse(c['count_match'])
        self.assertIn('same population not established',c['scope'])


if __name__=='__main__':unittest.main()
