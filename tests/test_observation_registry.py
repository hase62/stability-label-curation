"""Synthetic immutable inputs exercise observation identity and strict lineage."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import observation_registry as registry
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import dtu2016_source_audit as dtu
from stability_label_curation import jappe_2020_row_audit as jappe
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main
from test_jappe_2020_row_audit import fixture


class ObservationRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True)
        self.files={key:self.paths.project_data_dir/(key+('.xlsx' if key.startswith('jappe_data') else '.txt')) for key in registry.INPUT_IDS}
        self.files['dtu'].write_text('HLA Pep Thalf\nHLA-A*02:01 ACDEFGHIK 0.00\nHLA-B*07:02 ACDEFGHIL 1.80\nHLA-A*01:01 ACDEFGHIM 2.00\nHLA-B*14:01(C67S) ACDEFGHIN 0.00\n')
        self.sequences={'HLA-A*02:01':'A'*181,'HLA-B*07:02':'C'*362,'HLA-A*01:01':'D'*365}
        with self.files['spearmint_mapping'].open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(['Allele','Full Sequence']);writer.writerows(self.sequences.items())
        for split,allele,peptide,label in [('train','HLA-A*02:01','ACDEFGHIK','0'),('val','HLA-B*07:02','ACDEFGHIL','1.8'),('test','HLA-A*01:01','ACDEFGHIM','2')]:
            with self.files['spearmint_'+split].open('w',newline='') as f:
                writer=csv.writer(f);writer.writerow(['peptide_sequence','mhc_sequence','label','allele','assay','temperature_C'])
                writer.writerow([peptide,self.sequences[allele],label,allele,'SPA','37.0'])
        for i in (3,4,5):self.files['jappe_data_'+str(i)].write_bytes(fixture('supplementary_data_'+str(i)))
        self.make_ledger()
        self.lock=deepcopy(registry.load_lock(paths=self.paths));self.lock_path=self.root/'fixture.lock.json'
        self.lock['expectations']={'dtu_observations':4,'dtu_alleles':4,'dtu_zero_values':2,'dtu_c67s_observations':1,'dtu_ordinary_observations':3,
            'jappe_by_allele':{'HLA-A*02:01':2,'HLA-B*07:02':2,'HLA-C*04:01':6},'jappe_C_unique_peptides':3,
            'jappe_observations':10,'total_observations':14,'aliases_by_split':{'train':1,'validation':1,'test':1},'total_aliases':3}
        self.refresh()
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in registry tests'));self.network.start();self.addCleanup(self.network.stop)
    def refresh(self):
        for entry in self.lock['artifacts']:entry['sha256']=raw.sha256_file(self.files[entry['input_id']])
        self.lock_path.write_text(json.dumps(self.lock))
    def result(self):return registry.build(paths=self.paths,files=self.files,lock_path=self.lock_path)
    def make_ledger(self):
        ledger=[]
        for i in (3,4,5):
            key='supplementary_data_'+str(i);sheet,allele,context,schema=jappe.SCHEMAS[key]
            structure,rows=jappe.read_rows(self.files['jappe_data_'+str(i)])
            for row in rows:
                cs={c['column']:c for c in row['cells']};pep=cs.get('A',{}).get('decoded_text')
                kind='header' if row['row_number']==1 else 'peptide_row' if pep else 'auxiliary_only_row'
                fields=[]
                for index,(header,(category,unit,field_context)) in enumerate(schema.items()):
                    if category=='peptide_sequence':continue
                    column=chr(65+index);cell=cs.get(column)
                    fields.append({'category':category,'unit':unit,'assay_context':field_context or context,'column':column,
                        'original_header_text':header,'expected_coordinate':column+str(row['row_number']),
                        'source_cell':cell,'numeric':jappe.parse_numeric(cell),'evidence_refs':['tm_definition','cell_contexts'],'data_quality_flags':[]})
                ledger.append({**row,'artifact_id':key,'source_sha256':structure['sha256'],'row_kind':kind,
                    'original_peptide_text':pep,'hla_restriction':allele,'fields':fields,'data_quality_flags':[],
                    'row_origin':jappe.ROW_ORIGIN})
        self.files['jappe_ledger'].write_text(jappe.row_jsonl(ledger))
    def edit_ledger(self,operation):
        rows=[json.loads(line) for line in self.files['jappe_ledger'].read_text().splitlines()]
        operation(rows);self.files['jappe_ledger'].write_text(jappe.row_jsonl(rows));self.refresh()
    def edit_split(self,split,operation):
        path=self.files['spearmint_'+split]
        with path.open(newline='') as f:rows=list(csv.reader(f))
        operation(rows)
        with path.open('w',newline='') as f:csv.writer(f).writerows(rows)
        self.refresh()
    def test_deterministic_ids_and_full_sha256(self):
        locator={'kind':'text_line','artifact':'source/table.txt','line_number':2}
        a=registry.observation_id('netmhcstabpan_2016','a'*64,locator)
        self.assertEqual(a,registry.observation_id('netmhcstabpan_2016','a'*64,locator));self.assertEqual(len(a),69)
    def test_collision_prevention_across_sources_and_artifacts(self):
        locator={'kind':'text_line','artifact':'table.txt','line_number':2}
        ids={registry.observation_id(source,sha,locator) for source in ('netmhcstabpan_2016','jappe_2020') for sha in ('a'*64,'b'*64)}
        self.assertEqual(len(ids),4)
    def test_same_key_different_rows_retains_distinct_identity(self):
        ids=[registry.observation_id('netmhcstabpan_2016','a'*64,{'kind':'text_line','artifact':'table.txt','line_number':n}) for n in (2,3)]
        self.assertNotEqual(*ids)
    def test_cell_identity_distinguishes_c_contexts(self):
        observations=[o for o in self.result().observations if o.original_allele=='HLA-C*04:01']
        pair=[o for o in observations if o.source_locator['row_number']==2]
        self.assertEqual(len(pair),2);self.assertNotEqual(pair[0].observation_id,pair[1].observation_id)
        self.assertEqual({o.assay_context for o in pair},{'C1R-A*02:01','C1R-B*07:02'})
    def test_original_numeric_text_and_decimal_precision(self):
        observations=self.result().observations
        self.assertEqual(observations[0].original_measurement_text,'0.00');self.assertEqual(observations[1].parsed_measurement_decimal,'1.80')
        value=registry.decimal_value('40.000000000000001');self.assertEqual(str(value),'40.000000000000001')
    def test_type_unit_separation_and_invalid_combinations(self):
        observation=self.result().observations[0]
        for type,unit in [('kinetic_half_life','degC'),('thermal_melting_temperature','hours'),('common_stability','hours'),('unknown',None)]:
            with self.subTest(type=type,unit=unit),self.assertRaises(ValueError):replace(observation,measurement_type=type,measurement_unit=unit)
        summary=self.result().reports['measurement_type_summary.json'];self.assertEqual(summary['kinetic_half_life']['unit'],'hours');self.assertEqual(summary['thermal_melting_temperature']['unit'],'degC')
    def test_dtu_zeros_preserved_unresolved_not_synthetic(self):
        zeros=[o for o in self.result().observations if o.source_id=='netmhcstabpan_2016' and 'exact_zero' in o.data_quality_flags]
        self.assertEqual(len(zeros),2);self.assertTrue(all(o.original_measurement_text=='0.00' and 'zero_semantics_unresolved' in o.data_quality_flags for o in zeros))
        self.assertTrue(all('synthetic' not in o.row_origin_status for o in zeros))
    def test_c67s_kept_without_wild_type_mapping(self):
        observation=next(o for o in self.result().observations if 'c67s_annotated_allele' in o.data_quality_flags)
        self.assertEqual(observation.original_allele,'HLA-B*14:01(C67S)');self.assertEqual(observation.measurement_unit,'hours')
    def test_conservative_origin_and_no_training_field(self):
        for observation in self.result().observations:
            self.assertIn('unverified',observation.row_origin_status)
            self.assertFalse(any('training' in field or 'eligib' in field for field in observation.as_dict()))
        with self.assertRaises(ValueError):replace(self.result().observations[0],row_origin_status='confirmed_experimental')
    def test_exact_alias_values_and_original_strings(self):
        aliases=self.result().aliases
        self.assertEqual([a['original_measurement_text'] for a in aliases],['0','1.8','2'])
        self.assertTrue(all(a['half_life_agreement']=='exact_decimal_hours' for a in aliases))
        self.assertEqual(aliases[0]['source_locator']['source_line_start'],2)
    def test_alias_counts_and_cross_split_coverage(self):
        result=self.result();ids={o.observation_id for o in result.observations}
        self.assertEqual(Counter(a['split'] for a in result.aliases),{'train':1,'validation':1,'test':1})
        self.assertEqual(len({a['canonical_dtu_observation_id'] for a in result.aliases}),3)
        self.assertTrue(all(a['canonical_dtu_observation_id'] in ids for a in result.aliases))
    def test_no_canonical_observations_from_spearmint(self):
        result=self.result();self.assertEqual(len(result.observations),14)
        self.assertEqual({o.source_id for o in result.observations},{'netmhcstabpan_2016','jappe_2020'})
    def test_unmatched_alias_fails(self):
        self.edit_split('train',lambda rows:rows[1].__setitem__(0,'ACDEFGHIA'))
        with self.assertRaisesRegex(ValueError,'Unmatched'):self.result()
    def test_ambiguous_dtu_key_fails_no_deduplication(self):
        with self.files['dtu'].open('a') as f:f.write('HLA-A*02:01 ACDEFGHIK 0.00\n')
        self.refresh()
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.result()
    def test_cross_split_duplicate_alias_fails(self):
        with self.files['spearmint_train'].open(newline='') as f:row=list(csv.reader(f))[1]
        self.edit_split('val',lambda rows:rows.__setitem__(1,row))
        with self.assertRaisesRegex(ValueError,'Duplicate alias'):self.result()
    def test_missing_alias_coverage_fails(self):
        self.edit_split('train',lambda rows:rows.pop())
        with self.assertRaisesRegex(ValueError,'coverage'):self.result()
    def test_numerical_mismatch_fails_without_tolerance(self):
        self.edit_split('val',lambda rows:rows[1].__setitem__(2,'1.800000000001'))
        with self.assertRaisesRegex(ValueError,'exactly'):self.result()
    def test_unresolved_sequence_mapping_fails(self):
        self.edit_split('train',lambda rows:rows[1].__setitem__(1,'ACDE'))
        with self.assertRaisesRegex(ValueError,'Unresolved'):self.result()
    def test_reference_181_residue_limitation_preserved(self):
        alias=self.result().aliases[0];self.assertEqual(alias['reference_sequence_length'],181)
        self.assertEqual(alias['original_fields']['mhc_sequence'],'A'*181)
        self.assertIn('181-residue',alias['limitations'][1])
    def test_transformed_and_prediction_fields_not_observations(self):
        result=self.result();thermal=[o for o in result.observations if o.measurement_type=='thermal_melting_temperature']
        self.assertEqual(len(thermal),10)
        self.assertTrue(all(o.source_record_context['selected_original_header'].startswith('Tm') for o in thermal))
        summary=result.reports['registry_validation_summary.json']['excluded_non_observation_field_counts'];self.assertEqual(summary,{'tm_derived_transformation':4,'predicted_binding_affinity':4})
        self.assertIn('tm_derived_transformation',[f['category'] for f in thermal[0].source_record_context['original_column_roles']])
    def test_false_transformed_field_role_rejected(self):
        def edit(rows):
            row=next(r for r in rows if r['row_kind']=='peptide_row' and r['artifact_id']=='supplementary_data_3')
            row['fields'][1]['category']='publication_described_tm_measurement';row['fields'][1]['unit']='degrees_Celsius'
        self.edit_ledger(edit)
        with self.assertRaisesRegex(ValueError,'role'):self.result()
    def test_c_context_values_not_averaged_or_restricted_to_ab(self):
        values=[o for o in self.result().observations if o.original_allele=='HLA-C*04:01' and o.source_locator['row_number']==2]
        self.assertEqual([o.original_measurement_text for o in values],['40','44'])
        self.assertTrue(all(o.measurement_unit=='degC' for o in values))
    def test_no_peak_area_or_fabricated_359_records(self):
        observations=self.result().observations
        self.assertEqual(sum(o.original_allele=='HLA-C*04:01' for o in observations),6)
        self.assertFalse(any('MOESM11' in o.source_locator['artifact'] for o in observations))
        matrix=self.result().reports['source_lineage_matrix.json']['sources'];self.assertTrue(any(s.get('row_overlap_status')=='full_C359_population_unrecovered' for s in matrix))
    def test_precise_source_locators(self):
        result=self.result();self.assertEqual(result.observations[0].source_locator['line_number'],2)
        c=next(o for o in result.observations if o.original_allele=='HLA-C*04:01')
        self.assertEqual(c.source_locator['worksheet'],'C0401');self.assertEqual(c.source_locator['cell_coordinate'],'B2')
    def test_same_peptide_allele_different_assays_retained(self):
        result=self.result();key=[o for o in result.observations if (o.original_allele,o.original_peptide)==('HLA-A*02:01','ACDEFGHIK')]
        self.assertEqual(len(key),2);self.assertEqual(len({o.measurement_type for o in key}),2)
        self.assertGreater(result.reports['registry_validation_summary.json']['repeated_combination_count'],0)
    def test_sha_gate_precedes_scientific_analysis(self):
        self.files['dtu'].write_text('changed')
        with patch.object(raw,'inventory',side_effect=AssertionError('Hash gate first')),self.assertRaisesRegex(ValueError,'checksum'):self.result()
    def test_each_required_input_is_hashed(self):
        result=self.result();self.assertEqual(len(result.inputs),9)
        self.assertEqual({i['sha256'] for i in result.inputs},{e['sha256'] for e in self.lock['artifacts']})
    def test_missing_input_error_and_no_storage_writes(self):
        self.files['spearmint_test'].unlink()
        with self.assertRaisesRegex(ValueError,'Missing required registry input: spearmint_test'):self.result()
        self.assertFalse(self.paths.project_runs_dir.exists())
    def test_invalid_nonfinite_values_rejected(self):
        for value in ('NaN','Infinity','-Infinity','NA','bad','1_0',''):
            with self.subTest(value=value),self.assertRaises(ValueError):registry.decimal_value(value)
    def test_invalid_dtu_value_reports_validation_failure(self):
        self.files['dtu'].write_text(self.files['dtu'].read_text().replace('1.80','NaN'));self.refresh()
        with self.assertRaisesRegex(ValueError,'validation failed'):self.result()
    def test_deterministic_outputs_and_unchanged_inputs(self):
        before={key:path.read_bytes() for key,path in self.files.items()};a,b=self.result(),self.result()
        self.assertEqual(registry.jsonl(a.observations),registry.jsonl(b.observations));self.assertEqual(registry.jsonl(a.aliases),registry.jsonl(b.aliases));self.assertEqual(raw.json_report(a.reports),raw.json_report(b.reports))
        self.assertEqual(before,{key:path.read_bytes() for key,path in self.files.items()});self.assertFalse(self.paths.project_runs_dir.exists())
    def test_cli_read_only_validation_and_compatibility(self):
        args=['registry','validate','--json','--lock',str(self.lock_path)]
        for key,path in self.files.items():args+=['--input',key+'='+str(path)]
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        self.assertEqual(json.loads(output.getvalue())['registry_validation_summary.json']['observed_counts']['total_observations'],14)
        self.assertFalse(self.paths.project_runs_dir.exists())
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)
    def test_safe_run_output_hashed_inputs_and_no_overwrite(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=list(self.files.values()),allow_dirty=True)
        receipt=registry.write_registry(result,run/'reports',paths=self.paths)
        self.assertEqual(len(receipt['reports']),6);self.assertEqual(len((run/'reports/canonical_observations.jsonl').read_text().splitlines()),14)
        with self.assertRaises(FileExistsError):registry.write_registry(result,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):registry.write_registry(result,self.root/'reports',paths=self.paths)
    def test_run_without_matching_inputs_refused(self):
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        with self.assertRaises(ValueError):registry.write_registry(self.result(),run/'reports',paths=self.paths)
    def test_output_symlink_escape_refused(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=list(self.files.values()),allow_dirty=True)
        (run/'reports/canonical_observations.jsonl').symlink_to(self.root/'escaped')
        with self.assertRaises(FileExistsError):registry.write_registry(result,run/'reports',paths=self.paths)
        self.assertFalse((self.root/'escaped').exists())
    def test_count_mismatch_not_forced(self):
        self.lock['expectations']['total_observations']=15;self.refresh()
        with self.assertRaisesRegex(ValueError,'count validation failed'):self.result()
    def test_original_raw_line_and_other_cells_retained(self):
        result=self.result();self.assertTrue(result.observations[0].source_record_context['original_source_line'].endswith('0.00\n'))
        thermal=next(o for o in result.observations if o.measurement_type=='thermal_melting_temperature')
        self.assertTrue(any(c['coordinate']=='C2' for c in thermal.source_record_context['original_cells']))
    def test_duplicate_tm_cell_and_invalid_context_refused(self):
        def edit(rows):
            row=next(r for r in rows if r['row_kind']=='peptide_row' and r['artifact_id']=='supplementary_data_5')
            row['fields'][0]['assay_context']='wild_type_HLA-A*02:01'
        self.edit_ledger(edit)
        with self.assertRaisesRegex(ValueError,'context'):self.result()
    def test_duplicate_measurement_cell_refused(self):
        def edit(rows):
            row=next(r for r in rows if r['row_kind']=='peptide_row' and r['artifact_id']=='supplementary_data_5')
            rows.append(deepcopy(row))
        self.edit_ledger(edit)
        with self.assertRaisesRegex(ValueError,'Duplicate approved Tm source cell'):self.result()
    def test_formula_cache_cannot_be_accepted_as_tm(self):
        def edit(rows):
            row=next(r for r in rows if r['row_kind']=='peptide_row' and r['artifact_id']=='supplementary_data_3')
            row['fields'][0]['source_cell']['formula_present']=True
        self.edit_ledger(edit)
        with self.assertRaisesRegex(ValueError,'numerical provenance'):self.result()
    def test_source_locator_rejects_absolute_or_traversal(self):
        for path in ('/private/tmp/table','../table','source/../table'):
            with self.subTest(path=path),self.assertRaises(ValueError):registry.observation_id('jappe_2020','a'*64,{'kind':'text_line','artifact':path,'line_number':1})
    def test_historical_and_secondary_sources_are_documentary(self):
        result=self.result();matrix=result.reports['source_lineage_matrix.json']['sources']
        self.assertEqual(next(s for s in matrix if s['registry_source_id']=='netmhcstab_2013')['row_overlap_status'],'unavailable_not_zero')
        self.assertTrue(any(s['registry_source_id']=='tlstab_reference' and s['role']=='secondary_derived_material_not_canonical_measurements' for s in matrix))
        self.assertEqual({o.source_id for o in result.observations},{'netmhcstabpan_2016','jappe_2020'})


if __name__=='__main__':unittest.main()
