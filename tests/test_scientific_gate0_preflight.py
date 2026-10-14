"""Synthetic derived registries only; no original datasets or network required."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import scientific_gate0_preflight as gate
from stability_label_curation import observation_registry as registry
from stability_label_curation import dtu2016_source_audit as dtu
from stability_label_curation import jappe_2020_row_audit as jappe
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


class Gate0Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.env={'CODEX_ROOT':str(self.root)};self.paths=resolve_paths(self.env)
        self.paths.project_data_dir.mkdir(parents=True)
        self.files={key:self.paths.project_data_dir/(key+('.jsonl' if key in {'observations','aliases'} else '.json')) for key in gate.INPUT_IDS}
        self.config=deepcopy(gate.load_config(paths=self.paths));self.config_path=self.root/'fixture-config.json'
        self.rows=[]
        for number,(allele,pep,text) in enumerate([('HLA-A*02:01','ACDEFGHIK','0.00'),('HLA-A*02:01','ACDEFGHIL','0.10'),
                ('HLA-B*07:02','ACDEFGHIM','2.00'),('HLA-B*14:01(C67S)','ACDEFGHIN','0.00')],2):
            category=dtu.identifier_category(allele)
            self.rows.append(registry.make_observation(source_id='netmhcstabpan_2016',sha256='a'*64,
                locator={'kind':'text_line','artifact':'dtu/Stability.txt','line_number':number},allele=allele,peptide=pep,text=text,
                measurement_type='kinetic_half_life',unit='hours',context=registry.DTU_CONTEXT,
                provenance={'scope':'synthetic-fixture metadata'},origin=dtu.ROW_PROVENANCE,
                flags=['c67s_annotated_allele' if category=='c67s_annotated_hla_b' else category],record_context={}))
        for allele,pep,text,sheet,cell,context in [('HLA-A*02:01','ACDEFGHIL','44','A0201','B2','C1R-A*02:01'),
                ('HLA-B*07:02','ACDEFGHIM','55','B0702','B2','C1R-B*07:02'),
                ('HLA-C*04:01','ACDEFGHIK','42','C0401','B2','C1R-A*02:01'),
                ('HLA-C*04:01','ACDEFGHIK','46','C0401','C2','C1R-B*07:02')]:
            self.rows.append(registry.make_observation(source_id='jappe_2020',sha256='b'*64,
                locator={'kind':'workbook_cell','artifact':'jappe/fixture.xlsx','worksheet':sheet,'row_number':2,'cell_coordinate':cell},
                allele=allele,peptide=pep,text=text,measurement_type='thermal_melting_temperature',unit='degC',context=context,
                provenance={'scope':'synthetic-fixture metadata'},origin=jappe.ROW_ORIGIN,flags=[],record_context={}))
        self.aliases=[]
        for split,row in zip(('train','validation','test'),self.rows[:3]):
            self.aliases.append({'schema_version':1,'source_id':'spearmint_stability_audit','canonical_dtu_observation_id':row.observation_id,
                'original_peptide':row.original_peptide,'original_allele':row.original_allele,'original_measurement_text':row.original_measurement_text,
                'mapping_evidence':{'mapped_identifier':row.original_allele},'split':split,'half_life_agreement':'exact_decimal_hours',
                'measurement_type':'kinetic_half_life','measurement_unit':'hours','reference_sequence_length':181})
        self.files['observations'].write_text(registry.jsonl(self.rows));self.files['aliases'].write_text(registry.jsonl(self.aliases))
        counts={'dtu_observations':4,'dtu_alleles':3,'dtu_zero_values':2,'dtu_c67s_observations':1,'dtu_ordinary_observations':3,
            'jappe_by_allele':{'HLA-A*02:01':1,'HLA-B*07:02':1,'HLA-C*04:01':2},'jappe_C_unique_peptides':1,
            'jappe_observations':4,'total_observations':8,'aliases_by_split':{'train':1,'validation':1,'test':1},'total_aliases':3}
        self.validation={'observed_counts':counts,'expected_counts':deepcopy(counts),'repeated_combination_count':3}
        self.files['validation'].write_text(json.dumps(self.validation))
        lock=json.loads((self.paths.repository_root/registry.LOCK).read_text())
        self.files['lineage'].write_text(json.dumps({'sources':lock['source_lineage']}));self.files['evidence'].write_text(json.dumps({'lock':lock}))
        git={'repository_name':'stability-label-curation','commit_sha':self.config['parent_registry_commit'],'branch':'fixture',
            'working_tree_clean':True,'git_dirty':False,'working_tree_status':[]}
        with patch.object(runs,'capture_git_provenance',return_value=git):
            manifest=runs.build_manifest(paths=self.paths,run_id=self.config['parent_registry_run_id'],kind='synthetic_parent_fixture',
                argv=['fixture'],config=self.paths.repository_root/registry.LOCK)
        self.files['parent_manifest'].write_text(json.dumps(manifest))
        self.refresh()
        network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network during Gate 0'))
        network.start();self.addCleanup(network.stop)
    def refresh(self):
        for key,path in self.files.items():self.config['inputs'][key]['sha256']=raw.sha256_file(path)
        self.config_path.write_text(json.dumps(self.config))
    def result(self):return gate.inspect(paths=self.paths,files=self.files,config_path=self.config_path)
    def rewrite_rows(self,operation):
        rows=[json.loads(line) for line in self.files['observations'].read_text().splitlines()]
        operation(rows);self.files['observations'].write_text(registry.jsonl(rows));self.refresh()
    def test_exact_counts_and_alias_exclusion(self):
        coverage=self.result().reports['gate0_data_coverage.json'];self.assertEqual(coverage['verified_registry_counts']['total_observations'],8)
        self.assertEqual(coverage['new_independent_records_from_aliases'],0);self.assertEqual(coverage['verified_registry_counts']['total_aliases'],3)
    def test_zero_positive_counts_and_per_allele_fraction(self):
        zero=self.result().reports['gate0_zero_policy_comparison.json'];self.assertEqual(zero['summary']['records'],3)
        self.assertEqual(zero['summary']['zero_values'],1);self.assertEqual(zero['summary']['positive_values'],2)
        allele=next(r for r in zero['by_allele'] if r['original_allele']=='HLA-A*02:01');self.assertEqual(allele['zero_fraction'],'0.5')
        self.assertEqual(len(zero['high_zero_fraction_alleles']),1)
    def test_positive_quantiles_and_precision(self):
        zero=self.result().reports['gate0_zero_policy_comparison.json'];self.assertEqual(zero['positive_reported_decimal_scale_counts'],{'2':2})
        median=zero['summary']['positive_distribution_hours']['quantiles_hours']['p50'];self.assertEqual(Decimal(median),Decimal('1.05'))
        self.assertEqual(zero['lowest_ten_distinct_positive_values'][0]['original_text_counts'],{'0.10':1})
    def test_bin_boundaries_and_zero_distinction(self):
        bins=self.result().reports['gate0_zero_policy_comparison.json']['reported_half_life_bin_counts']
        self.assertEqual(bins['exact_zero'],1);self.assertEqual(bins['(0,0.1]'],1);self.assertEqual(bins['(1,2]'],1);self.assertEqual(sum(bins.values()),3)
    def test_zero_candidates_are_hypothetical_counts_only(self):
        comparison=self.result().reports['gate0_zero_policy_comparison.json']['candidate_policy_coverage']
        self.assertEqual(comparison['Z1']['potential_continuous_objective_records'],3)
        self.assertEqual(comparison['Z2']['potential_continuous_objective_records'],2)
        self.assertEqual(comparison['Z3']['potential_reporting_status_records'],3)
        self.assertTrue(all(v['status']=='decision_pending' for v in comparison.values()))
        self.assertFalse(any('observation_id' in json.dumps(v) for v in comparison.values()))
    def test_zero_semantics_unresolved(self):
        text=self.result().reports['gate0_zero_policy_comparison.json']['measurement_semantics'];self.assertTrue(text.startswith('Unresolved'))
        self.rewrite_rows(lambda rows:rows[0]['data_quality_flags'].remove('zero_semantics_unresolved'))
        with self.assertRaisesRegex(ValueError,'semantics'):self.result()
    def test_c67s_separate_and_no_mapping(self):
        comparison=self.result().reports['gate0_c67s_policy_comparison.json']
        self.assertEqual(comparison['C67S']['records'],1);self.assertEqual(comparison['C67S']['zero_fraction'],'1')
        self.assertEqual(comparison['by_original_construct'][0]['original_identifier'],'HLA-B*14:01(C67S)')
        self.assertFalse(comparison['wild_type_mapping_created']);self.assertEqual(comparison['candidate_coverage']['C3']['status'],'decision_pending')
    def test_modality_overlap_exact_keys(self):
        modality=self.result().reports['gate0_modality_overlap.json'];self.assertEqual(modality['exact_cross_modality_key_count'],2)
        self.assertEqual(modality['cross_modality_by_allele'],{'HLA-A*02:01':1,'HLA-B*07:02':1})
        self.assertEqual(modality['cross_modality_peptide_lengths'],{'9':2});self.assertFalse(modality['cross_modality_numeric_calibration_performed'])
    def test_c_context_ids_remain_separate(self):
        c=self.result().reports['gate0_modality_overlap.json']['C_contexts'];self.assertEqual(c['unique_peptides'],1)
        self.assertEqual(c['measurement_values'],2);self.assertEqual(c['distinct_observation_ids'],2);self.assertFalse(c['averaged'])
    def test_repeated_peptides_across_alleles_detected(self):
        reuse=self.result().reports['gate0_leakage_threat_model.json']['detected_registry_evidence']['exact_peptide_reuse_all_registry']
        self.assertEqual(reuse['peptides_on_multiple_HLA_identifiers'],1)
    def test_missing_immunogenicity_evidence_not_absence(self):
        threats=self.result().reports['gate0_leakage_threat_model.json'];self.assertFalse(threats['immunogenicity_leakage_absence_claimed'])
        self.assertTrue(any(t['assessment']=='requires_unacquired_immunogenicity_data' for t in threats['threats']))
        missing=self.result().reports['gate0_source_evidence.json']['unavailable_evidence'];self.assertEqual(missing['historical_original_table_overlap'],'unavailable_not_zero')
    def test_all_decisions_pending_no_split_generation(self):
        decisions=self.result().reports['gate0_decision_matrix.json'];self.assertEqual(decisions['approved_policies'],[])
        self.assertFalse(decisions['split_assignments_created']);self.assertFalse(decisions['training_authorized'])
        self.assertTrue(all(d['status']=='decision_pending' for d in decisions['user_required_decisions']))
        self.assertEqual(len(decisions['split_candidates']),5)
    def test_checksum_gate_before_parsing(self):
        self.files['observations'].write_text('changed')
        with patch.object(gate,'_jsonl',side_effect=AssertionError('Gate first')),self.assertRaisesRegex(ValueError,'checksum'):self.result()
    def test_all_six_derived_inputs_recorded(self):
        result=self.result();self.assertEqual(len(result.inputs),6)
        provenance=result.reports['gate0_source_evidence.json'];self.assertFalse(provenance['original_source_artifacts_read_or_rehashed_this_task'])
        self.assertEqual(provenance['parent_registry_run_id'],self.config['parent_registry_run_id'])
    def test_invalid_numeric_registry_rejected(self):
        self.rewrite_rows(lambda rows:rows[0].__setitem__('original_measurement_text','NaN'))
        with self.assertRaisesRegex(ValueError,'Invalid canonical'):self.result()
    def test_nonfinite_json_literal_rejected(self):
        self.files['observations'].write_text(self.files['observations'].read_text().replace('"source_record_context":{}','"source_record_context":{"unknown":NaN}',1));self.refresh()
        with self.assertRaisesRegex(ValueError,'Invalid registry JSONL'):self.result()
    def test_all_zero_allele_support_reported_without_policy_choice(self):
        self.rows[1]=registry.make_observation(source_id='netmhcstabpan_2016',sha256='a'*64,
            locator=self.rows[1].source_locator,allele=self.rows[1].original_allele,peptide=self.rows[1].original_peptide,
            text='0.00',measurement_type='kinetic_half_life',unit='hours',context=registry.DTU_CONTEXT,
            provenance={},origin=dtu.ROW_PROVENANCE,flags=['ordinary_hla_a'],record_context={})
        self.aliases[1]['original_measurement_text']='0.00'
        self.files['observations'].write_text(registry.jsonl(self.rows));self.files['aliases'].write_text(registry.jsonl(self.aliases))
        for key in ('observed_counts','expected_counts'):self.validation[key]['dtu_zero_values']=3
        self.files['validation'].write_text(json.dumps(self.validation));self.refresh()
        coverage=self.result().reports['gate0_zero_policy_comparison.json']['candidate_policy_coverage']
        self.assertEqual(coverage['Z2']['alleles_with_no_positive_support'],['HLA-A*02:01'])
        self.assertEqual(coverage['Z3']['reporting_status_supported_alleles'],2);self.assertEqual(coverage['Z3']['positive_objective_supported_alleles'],1)
    def test_unit_mismatch_registry_rejected(self):
        self.rewrite_rows(lambda rows:rows[0].__setitem__('measurement_unit','degC'))
        with self.assertRaises(ValueError):self.result()
    def test_duplicate_observation_ids_rejected(self):
        self.rewrite_rows(lambda rows:rows.append(deepcopy(rows[0])))
        with self.assertRaisesRegex(ValueError,'Duplicate registry'):self.result()
    def test_parent_count_mismatch_not_hidden(self):
        self.validation['observed_counts']['total_observations']=9;self.files['validation'].write_text(json.dumps(self.validation));self.refresh()
        with self.assertRaisesRegex(ValueError,'counts disagree'):self.result()
    def test_incomplete_alias_coverage_rejected(self):
        self.files['aliases'].write_text(registry.jsonl(self.aliases[:-1]));self.refresh()
        with self.assertRaisesRegex(ValueError,'coverage'):self.result()
    def test_duplicate_alias_or_mismatched_value_rejected(self):
        self.files['aliases'].write_text(registry.jsonl(self.aliases+[self.aliases[0]]));self.refresh()
        with self.assertRaisesRegex(ValueError,'duplicate SPEARMINT'):self.result()
        self.aliases[0]['original_measurement_text']='0.01';self.files['aliases'].write_text(registry.jsonl(self.aliases));self.refresh()
        with self.assertRaises(ValueError):self.result()
    def test_parent_lineage_inconsistency_fails(self):
        self.files['lineage'].write_text(json.dumps({'sources':[]}));self.refresh()
        with self.assertRaisesRegex(ValueError,'lineage'):self.result()
    def test_parent_not_canonical_rejected(self):
        parent=json.loads(self.files['parent_manifest'].read_text());parent['reproducibility']['canonical']=False
        self.files['parent_manifest'].write_text(json.dumps(parent));self.refresh()
        with self.assertRaises(ValueError):self.result()
    def test_determinism_and_no_modification_or_storage_creation(self):
        before={k:p.read_bytes() for k,p in self.files.items()};a,b=self.result(),self.result()
        self.assertEqual(raw.json_report(a.reports),raw.json_report(b.reports));self.assertEqual(before,{k:p.read_bytes() for k,p in self.files.items()})
        self.assertFalse(self.paths.project_runs_dir.exists())
    def test_default_cli_read_only_and_existing_commands(self):
        args=['gate0','inspect','--json','--registry',str(self.files['observations']),'--aliases',str(self.files['aliases']),'--config',str(self.config_path)]
        for key,path in self.files.items():
            if key not in {'observations','aliases'}:args+=['--input',key+'='+str(path)]
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        self.assertEqual(json.loads(output.getvalue())['gate0_data_coverage.json']['all_eligibility_decisions'],'decision_pending')
        self.assertFalse(self.paths.project_runs_dir.exists())
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)
    def test_safe_report_output_inputs_and_no_overwrite(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=list(self.files.values()),allow_dirty=True)
        receipt=gate.write_reports(result,run/'reports',paths=self.paths);self.assertEqual(len(receipt['reports']),7)
        self.assertFalse(any(p.suffix=='.jsonl' for p in (run/'reports').iterdir()))
        with self.assertRaises(FileExistsError):gate.write_reports(result,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):gate.write_reports(result,self.root/'reports',paths=self.paths)
    def test_unrecorded_inputs_refused(self):
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        with self.assertRaises(ValueError):gate.write_reports(self.result(),run/'reports',paths=self.paths)
    def test_missing_derived_input_reported(self):
        self.files['aliases'].unlink()
        with self.assertRaisesRegex(ValueError,'Missing required'):self.result()
    def test_zero_fraction_threshold_is_descriptive_config(self):
        self.config['high_zero_fraction_threshold']='0.75';self.refresh()
        self.assertEqual(self.result().reports['gate0_zero_policy_comparison.json']['high_zero_fraction_alleles'],[])
    def test_no_legal_permission_inferred(self):
        licenses=self.result().reports['gate0_source_evidence.json']['source_usage_uncertainties']
        self.assertTrue(all(not s['legal_determination_made'] and s['source_files_outside_Git'] for s in licenses))
    def test_user_study_guardrails_retained(self):
        text=' '.join(self.result().reports['gate0_decision_matrix.json']['downstream_user_prescribed_guardrails'])
        for term in ('same loss','binding-trained','No stability input','random-positive','multiple seeds','Frozen untouched'):
            self.assertIn(term,text)


if __name__=='__main__':unittest.main()
