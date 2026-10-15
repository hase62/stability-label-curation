"""Small synthetic observations only; no real training inputs or network requests."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import stability_teacher as teacher
from stability_label_curation import observation_registry as registry
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import dtu2016_source_audit as dtu
from stability_label_curation import jappe_2020_row_audit as jappe
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main

HAS_TRAINING = importlib.util.find_spec('sklearn') is not None


def observation(line, peptide, allele='HLA-A*02:01', text='0.00', thermal=False):
    return registry.make_observation(source_id='jappe_2020' if thermal else 'netmhcstabpan_2016',
        sha256=dtu.TASK11_LOCAL_SHA256,
        locator={'kind':'text_line', 'artifact':'fixture/table.txt', 'line_number':line},
        allele=allele, peptide=peptide, text=text,
        measurement_type='thermal_melting_temperature' if thermal else 'kinetic_half_life',
        unit='degC' if thermal else 'hours', context='synthetic assay context', provenance={'fixture':True},
        origin=jappe.ROW_ORIGIN if thermal else dtu.ROW_PROVENANCE, flags=[], record_context={})


class TeacherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = resolve_paths({'CODEX_ROOT':self.temp.name})
        self.paths.project_data_dir.mkdir(parents=True)
        self.config = teacher.load_config(self.paths.repository_root / teacher.CONFIG)
        self.config.update(minimum_training_rows=2, minimum_validation_rows_descriptive=2, parent_evidence=[])
        generator = random.Random(7)
        peptides = ['AAAAAAAAA', 'CAAAAAAAA', 'CCAAAAAAA']
        peptides += [''.join(generator.choices(teacher.ALPHABET, k=9)) for _ in range(15)]
        self.rows = [observation(2+i*2+j, peptide, allele, '0.00' if i%5==0 else f'{i%5+j}.250')
                     for i, peptide in enumerate(peptides) for j,allele in enumerate(('HLA-A*02:01','HLA-B*07:02'))]
        self.path = self.paths.project_data_dir / 'registry.jsonl'
        self.save_registry(self.rows)
        self.partition = teacher.make_partition(self.rows, self.config)
        network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network in tests'))
        network.start();self.addCleanup(network.stop)

    def save_registry(self, rows):
        self.path.write_text(registry.jsonl(o.as_dict() for o in rows))
        self.config['registry_sha256'] = raw.sha256_file(self.path)
        selected = [o for o in rows if o.source_id=='netmhcstabpan_2016' and dtu.identifier_category(o.original_allele) in {'ordinary_hla_a','ordinary_hla_b'}]
        self.config['expected_population'] = {'observations':len(selected), 'alleles':len({o.original_allele for o in selected}),
            'zeros':sum(registry.decimal_value(o.original_measurement_text)==0 for o in selected)}

    def fitted(self):
        return teacher.fit(self.rows, self.partition, self.config)

    def training_run(self):
        config_path = self.paths.project_data_dir / 'config.json'
        config_path.write_text(raw.json_report(self.config))
        run = runs.create_run(paths=self.paths, kind='test', seed=self.config['seed'], config=config_path,
            inputs=[self.path], argv=['synthetic teacher train'], allow_dirty=True)
        result = teacher.train_run(out=run, config_path=config_path, registry_path=self.path, paths=self.paths)
        return run, config_path, result

    def test_ordinary_inclusion_and_C67S_Tm_exclusion(self):
        other = [observation(100,'ACDEFGHIK','HLA-B*14:01(C67S)'), observation(101,'ACDEFGHIK',text='45.0',thermal=True)]
        self.save_registry(self.rows+other)
        rows, report = teacher.load_population(self.path,self.config)
        self.assertEqual(len(rows),36);self.assertEqual(report['excluded_registry_records'],{'c67s_annotated_hla_b':1,'other_source_or_modality':1})

    def test_zero_text_and_origin_preserved(self):
        rows, report = teacher.load_population(self.path,self.config)
        zero = [o for o in rows if registry.decimal_value(o.original_measurement_text)==0]
        self.assertEqual(report['zeros'],len(zero));self.assertTrue(zero)
        self.assertTrue(all(o.original_measurement_text=='0.00' and o.row_origin_status==dtu.ROW_PROVENANCE for o in zero))
        self.assertIn('unresolved',report['zero_semantics'])

    def test_checksum_gate(self):
        self.path.write_text('changed')
        with self.assertRaisesRegex(ValueError,'SHA256'):teacher.load_population(self.path,self.config)

    def test_population_expectations_not_forced(self):
        self.config['expected_population']['observations']+=1
        with self.assertRaisesRegex(ValueError,'population mismatch'):teacher.load_population(self.path,self.config)

    def test_invalid_numeric_and_duplicate_ids_rejected(self):
        self.save_registry(self.rows+[self.rows[0]])
        with self.assertRaisesRegex(ValueError,'Duplicate'):teacher.load_population(self.path,self.config)
        item=self.rows[0].as_dict();item['original_measurement_text']='NaN'
        self.path.write_text(json.dumps(item)+'\n');self.config['registry_sha256']=raw.sha256_file(self.path)
        with self.assertRaises(ValueError):teacher.load_population(self.path,self.config)

    def test_negative_source_target_rejected(self):
        rows=[observation(900,'ACDEFGHIK',text='-0.1')]
        self.save_registry(rows)
        with self.assertRaisesRegex(ValueError,'Negative'):teacher.load_population(self.path,self.config)

    def test_encoding_and_position_order(self):
        features=teacher.encode_ninemer('ACDEFGHIK')
        self.assertEqual(len(features),180);self.assertEqual(sum(features),9)
        for i,residue in enumerate('ACDEFGHIK'):self.assertEqual(features[20*i+teacher.ALPHABET.index(residue)],1)

    def test_unsupported_sequence_characters_and_lengths(self):
        for peptide in ('ACDEFGHIX','acdefghik','ACDEFGHI','ACDEFGHIKL','ACDEFGHI\u200b'):
            with self.assertRaises(ValueError):teacher.encode_ninemer(peptide)

    def test_log_transform_inverse_and_prediction_floor(self):
        for hours in (0,0.01,1,20):self.assertAlmostEqual(teacher.inverse_log1p(math.log1p(hours)),hours)
        self.assertEqual(teacher.inverse_log1p(-2),0)
        with self.assertRaises(ValueError):teacher.inverse_log1p(float('nan'))

    def test_partition_global_identity_and_transitive_neighbors(self):
        audit=teacher.verify_partition(self.rows,self.partition)
        self.assertEqual(audit['exact_peptides_crossing'],0);self.assertEqual(audit['direct_one_mismatch_edges_crossing'],0)
        groups={a['observation_id']:a['partition'] for a in self.partition['assignments']}
        self.assertEqual(len({groups[o.observation_id] for o in self.rows[:6]}),1)
        self.assertEqual(sum(audit['partition_counts'].values()),36)

    def test_split_deterministic_independent_of_record_order(self):
        one={a['observation_id']:a['partition'] for a in self.partition['assignments']}
        two={a['observation_id']:a['partition'] for a in teacher.make_partition(list(reversed(self.rows)),self.config)['assignments']}
        self.assertEqual(one,two)

    def test_illegal_exact_and_neighbor_leakage_rejected(self):
        broken=deepcopy(self.partition)
        broken['assignments'][0]['partition']='validation' if broken['assignments'][1]['partition']=='train' else 'train'
        with self.assertRaisesRegex(ValueError,'leakage'):teacher.verify_partition(self.rows,broken)
        broken=deepcopy(self.partition)
        group=broken['assignments'][0]['partition']
        for entry in broken['assignments'][2:4]:entry['partition']='validation' if group=='train' else 'train'
        with self.assertRaisesRegex(ValueError,'leakage'):teacher.verify_partition(self.rows,broken)

    def test_one_component_fails_without_violating_constraints(self):
        with self.assertRaisesRegex(ValueError,'two nonempty'):teacher.make_partition(self.rows[:6],self.config)

    def test_split_missing_or_duplicate_identity_rejected(self):
        broken=deepcopy(self.partition);broken['assignments'].append(broken['assignments'][0])
        with self.assertRaises(ValueError):teacher.verify_partition(self.rows,broken)

    def test_metrics_ties_constants_and_empty_subgroups(self):
        self.assertEqual(teacher._ranks([2,1,1]),[3,1.5,1.5])
        m=teacher.metrics([0,1,2],[0,1,2]);self.assertEqual(m['mae_hours'],0);self.assertEqual(m['spearman_hours'],1)
        self.assertIsNone(teacher.metrics([0,0],[1,2])['pearson_hours'])
        self.assertIsNone(teacher.metrics([1,2,3],[0.1,0.1,0.1])['spearman_hours'])
        self.assertIsNone(teacher.metrics([],[])['mae_hours'])
        with self.assertRaises(ValueError):teacher.metrics([1],[float('nan')])

    def test_bad_config_rejected(self):
        p=self.paths.project_data_dir/'config.json'
        for change in ({'ridge_alpha':0},{'target_transform':'Tm'},{'minimum_training_rows':1},{'max_hamming_distance':2}):
            p.write_text(raw.json_report({**self.config,**change}))
            with self.assertRaises(ValueError):teacher.load_config(p)

    def test_import_has_no_training_dependency_or_filesystem_side_effect(self):
        listing=sorted(Path(self.temp.name).rglob('*'))
        subprocess.run([sys.executable,'-B','-c',"import sys;import stability_label_curation.stability_teacher;assert 'numpy' not in sys.modules;assert 'sklearn' not in sys.modules"],check=True)
        self.assertEqual(listing,sorted(Path(self.temp.name).rglob('*')))

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_deterministic_fitting_and_predictions(self):
        first,second=self.fitted(),self.fitted()
        self.assertEqual(raw.json_report(first.document),raw.json_report(second.document))
        result=first.predict_stability('ACDEFGHIK','HLA-A*02:01')
        self.assertEqual(result['model_status'],'ok');self.assertGreaterEqual(result['predicted_half_life_hours'],0)
        self.assertTrue(first.training_diagnostics['finite_weights_verified'])
        self.assertLess(max(first.training_diagnostics['ridge_stationarity_max_absolute_residual_by_allele'].values()),1e-6)

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_exact_HLA_no_fuzzy_or_construct_fallback(self):
        model=self.fitted()
        for allele in ('HLA-A02:01','HLA-A*99:99','HLA-B*14:01(C67S)'):
            result=model.predict_stability('ACDEFGHIK',allele)
            self.assertEqual(result['model_status'],'unsupported');self.assertIsNone(result['predicted_half_life_hours'])
        self.assertIsNone(model.predict_stability('TOOSHORT','HLA-A*02:01')['predicted_half_life_hours'])

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_sparse_model_explicitly_unsupported(self):
        self.config['minimum_training_rows']=100
        model=self.fitted();result=model.predict_stability('ACDEFGHIK','HLA-A*02:01')
        self.assertEqual(result['unsupported_reason'],'insufficient_training_support');self.assertIsNone(result['predicted_half_life_hours'])

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_training_only_allele_mean_and_subgroup_metrics(self):
        model=self.fitted();metrics=teacher.evaluate(model,self.rows,self.partition)
        ids={a['observation_id'] for a in self.partition['assignments'] if a['partition']=='train'}
        for allele,params in model.document['alleles'].items():
            values=[float(o.original_measurement_text) for o in self.rows if o.original_allele==allele and o.observation_id in ids]
            self.assertAlmostEqual(params['training_mean_hours'],sum(values)/len(values))
        r=metrics['results'];self.assertEqual(r['overall']['teacher']['n'],r['positive']['teacher']['n']+r['reported_zero']['teacher']['n'])
        self.assertEqual(r['overall']['teacher']['n'],r['overall']['training_allele_mean_log1p_baseline']['n'])

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_safe_JSON_reload_and_invalid_weights(self):
        model=self.fitted();path=self.paths.project_data_dir/'model.json';path.write_text(raw.json_report(model.document))
        loaded=teacher.load_model(path)
        self.assertEqual(model.predict_batch([('ACDEFGHIK','HLA-A*02:01')]),loaded.predict_batch([('ACDEFGHIK','HLA-A*02:01')]))
        bad=deepcopy(model.document);bad['alleles']['HLA-A*02:01']['coefficients']=['executable?']*180
        path.write_text(raw.json_report(bad))
        with self.assertRaises(ValueError):teacher.load_model(path)

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_run_artifacts_no_overwrite_and_original_registry_unchanged(self):
        before=self.path.read_bytes();run,config_path,result=self.training_run()
        self.assertTrue(result['reload_verified']);self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaises(FileExistsError):teacher.train_run(out=run,config_path=config_path,registry_path=self.path,paths=self.paths)
        receipt=json.loads((run/'reports/execution_verification.json').read_text())
        self.assertFalse(receipt['EL_IM_data_read_or_modified'])
        for name,checksum in receipt['report_sha256'].items():self.assertEqual(raw.sha256_file(run/'reports'/name),checksum)

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_read_only_evaluation_uses_saved_partition(self):
        run,_,_=self.training_run();model=run/'checkpoints/teacher_model.json';partition=run/'reports/teacher_train_val_partition.json'
        evaluation=runs.create_run(paths=self.paths,kind='test',inputs=[self.path,model,partition],argv=['fixture evaluate'],allow_dirty=True)
        before=(self.path.read_bytes(),model.read_bytes(),partition.read_bytes())
        result=teacher.evaluate_run(model_path=model,out=evaluation,registry_path=self.path,paths=self.paths)
        self.assertEqual(result,json.loads((run/'reports/teacher_validation_metrics.json').read_text()))
        self.assertEqual(before,(self.path.read_bytes(),model.read_bytes(),partition.read_bytes()))

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_inference_CLI_and_label_columns_rejected(self):
        run,_,_=self.training_run();model=run/'checkpoints/teacher_model.json'
        input_path=self.paths.project_data_dir/'inputs.csv';input_path.write_text('peptide,hla\nACDEFGHIK,HLA-A*02:01\nACDEFGHIX,HLA-A*02:01\n')
        prediction=runs.create_run(paths=self.paths,kind='test',inputs=[model,input_path],argv=['fixture predict'],allow_dirty=True)
        out=prediction/'predictions/smoke.csv'
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['teacher','predict','--model',str(model),'--input',str(input_path),'--out',str(out)],env={'CODEX_ROOT':self.temp.name}),0)
        records=list(csv.DictReader(io.StringIO(out.read_text())))
        self.assertEqual(records[1]['model_status'],'unsupported');self.assertEqual(records[1]['predicted_half_life_hours'],'')
        input_path.write_text('peptide,hla,tgt\nACDEFGHIK,HLA-A*02:01,1\n')
        prediction=runs.create_run(paths=self.paths,kind='test',inputs=[model,input_path],argv=['fixture forbidden labels'],allow_dirty=True)
        with self.assertRaisesRegex(ValueError,'no EL/IM labels'):
            teacher.predict_csv(model_path=model,input_path=input_path,out=prediction/'predictions/output.csv',paths=self.paths)

    def test_existing_CLI_commands_and_output_boundary(self):
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env={'CODEX_ROOT':self.temp.name}),0)
        with self.assertRaises(ValueError):teacher._run(self.paths.project_data_dir/'bad',self.paths)

    @unittest.skipUnless(HAS_TRAINING,'Use the pinned Teacher environment for fitting tests')
    def test_train_CLI_and_incomplete_model_rejection(self):
        cfg=self.paths.project_data_dir/'config.json';cfg.write_text(raw.json_report(self.config))
        run=runs.create_run(paths=self.paths,kind='test',seed=42,config=cfg,inputs=[self.path],argv=['fixture train'],allow_dirty=True)
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['teacher','train','--config',str(cfg),'--out',str(run),'--registry',str(self.path)],env={'CODEX_ROOT':self.temp.name}),0)
        malformed=self.paths.project_data_dir/'bad.json';malformed.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Incomplete'):teacher.load_model(malformed)


if __name__=='__main__':unittest.main()
