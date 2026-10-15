"""Synthetic frozen weights and tiny CSV archives; no model fitting or networking."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from stability_label_curation import pseudolabel_pilot as pilot
from stability_label_curation import stability_teacher as teacher
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation import observation_registry as registry
from stability_label_curation import dtu2016_source_audit as dtu
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


def observation(line, peptide, hla='HLA-A*02:01', value='1.00'):
    return registry.make_observation(source_id='netmhcstabpan_2016', sha256=dtu.TASK11_LOCAL_SHA256,
        locator={'kind':'text_line','artifact':'fixture.txt','line_number':line}, allele=hla, peptide=peptide,
        text=value, measurement_type='kinetic_half_life',unit='hours',context='synthetic',provenance={},
        origin=dtu.ROW_PROVENANCE, flags=[],record_context={})


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env={'CODEX_ROOT':self.temp.name};self.paths=resolve_paths(self.env)
        data=self.paths.project_data_dir;data.mkdir(parents=True)
        self.rows=[observation(2,'AAAAAAAAA'),observation(3,'CAAAAAAAA',value='2.00'),
                   observation(4,'DDDDDDDDD',value='10.0'),observation(5,'AAAAAAAAA','HLA-B*07:02','0.00')]
        self.files={'registry':data/'registry.jsonl','partition':data/'partition.json',
            'mapping':data/'mapping.json','teacher':data/'teacher.json','teacher_receipt':data/'receipt.json','archive':data/'fixture.zip'}
        self.files['registry'].write_text(registry.jsonl(o.as_dict() for o in self.rows))
        tc=teacher.load_config(self.paths.repository_root/teacher.CONFIG)
        tc.update(registry_sha256=raw.sha256_file(self.files['registry']),parent_evidence=[],
                  minimum_training_rows=2,expected_population={'observations':4,'alleles':2,'zeros':1})
        tcpath=data/'teacher-config.json';tcpath.write_text(raw.json_report(tc))
        parent=runs.create_run(paths=self.paths,kind='test',seed=42,config=tcpath,
            inputs=[self.files['registry']],argv=['synthetic parent'],allow_dirty=True)
        self.files['teacher_manifest']=parent/'manifest.json';manifest=runs.load_manifest(parent.name,paths=self.paths)
        partition={'assignments':[{'observation_id':o.observation_id,'partition':'validation' if i==2 else 'train','component_id':'fixture'} for i,o in enumerate(self.rows)]}
        self.files['partition'].write_text(raw.json_report(partition))
        coefficients=[0.0]*180
        for residue,hours in [('A',0.5),('C',1.0),('D',10.0),('E',20.0),('F',5.0)]:
            coefficients[teacher.ALPHABET.index(residue)]=math.log1p(hours)
        provenance={'code_commit':manifest['git']['commit_sha'],'config_sha256':raw.sha256_file(tcpath),
                    'inputs':manifest['data_provenance']['input_artifacts'],'partition_sha256':raw.sha256_file(self.files['partition'])}
        model={'schema_version':1,'teacher_version':teacher.VERSION,'alphabet':teacher.ALPHABET,'peptide_length':9,
            'measurement_type':'kinetic_half_life','measurement_unit':'hours','target_transform':'log1p_hours',
            'prediction_transform':'expm1(max(0,linear_log_prediction))','config':tc,'provenance':provenance,
            'alleles':{'HLA-A*02:01':{'status':'trained','training_rows':2,'training_mean_hours':1.5,
                'training_mean_log1p':1.0,'coefficients':coefficients,'intercept':0.0},
                'HLA-B*07:02':{'status':'insufficient_training_support','training_rows':1,'training_mean_hours':0.0,'training_mean_log1p':0.0}}}
        self.files['teacher'].write_text(raw.json_report(model))
        self.files['teacher_receipt'].write_text(raw.json_report({'model_sha256':raw.sha256_file(self.files['teacher']),
            'config_sha256':raw.sha256_file(tcpath),'input_artifacts':provenance['inputs'],
            'report_sha256':{'teacher_train_val_partition.json':provenance['partition_sha256']}}))
        self.files['mapping'].write_text(raw.json_report({'data_HLA_mapping':[
            {'original_HLA':h,'canonical_two_field_HLA':h,'unique_canonical_reference_match':True}
            for h in model['alleles']]}))
        self.csvs={'el_train.csv': 'mhc,pep,tgt\nHLA-A*02:01,AAAAAAAAA,1\nHLA-A*02:01,DDDDDDDDD,0\nHLA-A*02:01,CAAAAAAAA,1\nHLA-A*02:01,EAAAAAAAA,1\nHLA-A*02:01,FAAAAAAAA,0\nHLA-A*02:01,AAAAAAAA,1\nHLA-A*02:01,AAAAAAAAX,1\nHLA-B*07:02,AAAAAAAAA,1\nHLA-A*99:99,AAAAAAAAA,1\n',
            'im_train.csv':'mhc,pep,tgt,rand\nHLA-A*02:01,AAAAAAAAA,0,0\nHLA-A*02:01,DDDDDDDDD,1,0\nHLA-A*02:01,AAAAAAAAA,1,0\nHLA-A*02:01,EAAAAAAAA,0,0\n'}
        with zipfile.ZipFile(self.files['archive'],'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,text in self.csvs.items():z.writestr(name,text)
            for name in ('el_val.csv','im_val.csv','el_test.csv','im_test.csv','iedb.csv','manafest.csv','summary.csv'):
                z.writestr(name,b'UNAUTHORIZED PAYLOAD\xff')
        self.config=pilot.load_config(self.paths.repository_root/pilot.CONFIG)
        self.config.update(expected_trained_HLA_models=1,teacher_commit_sha=manifest['git']['commit_sha'])
        for name,path in self.files.items():
            area='runs' if path.is_relative_to(self.paths.project_runs_dir) else 'data'
            root=self.paths.project_runs_dir if area=='runs' else self.paths.project_data_dir
            self.config['inputs'][name]={'area':area,'relative_path':str(path.relative_to(root)),'sha256':raw.sha256_file(path)}
        self.config['members']={n:{'rows':len(list(csv.reader(io.StringIO(t))))-1,'sha256':hashlib.sha256(t.encode()).hexdigest()} for n,t in self.csvs.items()}
        self.configpath=data/'pilot-config.json';self.configpath.write_text(raw.json_report(self.config))
        _,inputs=pilot.resolve_inputs(self.config,self.paths,self.files)
        self.run=runs.create_run(paths=self.paths,kind='test',config=self.configpath,inputs=[i['path'] for i in inputs],argv=['fixture pilot'],allow_dirty=True)
        self.context=pilot.load_context(self.config,self.files)
        for target in ('urllib.request.OpenerDirector.open','stability_label_curation.stability_teacher.fit','stability_label_curation.bigmhc_v4_audit.inspect'):
            mocked=patch(target,side_effect=AssertionError('No network, fitting or broader data inspection'))
            mocked.start();self.addCleanup(mocked.stop)

    def execute(self,**kwargs):
        return pilot.pilot(config_path=self.configpath,out=self.run,paths=self.paths,files=self.files,**kwargs)

    def csv_output(self,member,override=False):
        path=self.run/pilot.OUTPUTS[member][int(override)]
        with gzip.open(path,'rt',newline='') as stream:return list(csv.DictReader(stream))

    def test_strict_threshold_boundaries_and_directions(self):
        self.assertEqual(pilot.category_and_action('1',math.nextafter(1.0,0)),('LOW','low_positive_to_negative','0'))
        self.assertEqual(pilot.category_and_action('1',1.0),('MID','no_change','1'))
        self.assertEqual(pilot.category_and_action('0',math.nextafter(10.0,0)),('MID','no_change','0'))
        self.assertEqual(pilot.category_and_action('0',10.0),('HIGH','high_negative_to_positive','1'))
        self.assertEqual(pilot.category_and_action('0',0.0),('LOW','no_change','0'))
        self.assertEqual(pilot.category_and_action('1',20),('HIGH','no_change','1'))

    def test_sparse_candidates_and_all_original_labels_preserved(self):
        before=self.files['archive'].read_bytes();result=self.execute()
        for member in pilot.MEMBERS:
            rows=self.csv_output(member,True);self.assertEqual(len(rows),2)
            self.assertEqual({r['candidate_action'] for r in rows},{'low_positive_to_negative','high_negative_to_positive'})
            self.assertTrue(all(r['original_label']!=r['proposed_pseudolabel'] for r in rows))
        self.assertEqual(result['members']['el_train.csv']['teacher_eligible_rows'],5)
        self.assertEqual(self.files['archive'].read_bytes(),before)

    def test_unsupported_reasons_and_no_fabricated_predictions(self):
        result=self.execute()['members']['el_train.csv']
        self.assertEqual(result['unsupported_by_reason'],{'unsupported_peptide_length':1,'noncanonical_amino_acid':1,
            'insufficient_training_support':1,'unverified_or_ambiguous_HLA':1})
        self.assertEqual(len(self.csv_output('el_train.csv')),5)

    def test_only_two_training_members_ever_opened(self):
        original=zipfile.ZipFile.open
        def guard(z,name,*args,**kwargs):
            self.assertIn(name.filename if isinstance(name,zipfile.ZipInfo) else name,pilot.MEMBERS)
            return original(z,name,*args,**kwargs)
        with patch.object(zipfile.ZipFile,'open',guard),patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('No whole-archive walk')):
            self.execute()
        summary=json.loads((self.run/'reports/pseudolabel_summary.json').read_text())
        self.assertEqual(summary['opened_members'],list(pilot.MEMBERS));self.assertEqual(summary['validation_or_test_members_opened'],[])

    def test_score_row_coordinates_and_field_checksum(self):
        self.execute();row=self.csv_output('el_train.csv')[0]
        self.assertEqual(row['row_index'],'1');self.assertEqual(row['source_line_number'],'2')
        self.assertEqual(row['source_row_id'],pilot.row_id(self.context.archive_sha256,'el_train.csv',1))
        source=list(csv.reader(io.StringIO(self.csvs['el_train.csv'])))
        expected=hashlib.sha256(json.dumps([source[0],source[1]],separators=(',',':')).encode()).hexdigest()
        self.assertEqual(row['source_row_sha256'],expected)

    def test_LOW_only_selection_needs_no_rescoring(self):
        self.execute();rows=self.csv_output('el_train.csv',True)
        self.assertEqual(sum(pilot.candidate_for_policy(r,'low_only') for r in rows),1)
        self.assertEqual(sum(pilot.candidate_for_policy(r,'low_and_high') for r in rows),2)

    def test_override_identity_duplicate_and_authorization_guards(self):
        self.execute();row=self.csv_output('el_train.csv',True)[0]
        guard=pilot.OverrideGuard('el_train.csv',self.context.archive_sha256,self.context.model_sha256)
        with self.assertRaises(ValueError):guard.check(row,set())
        guard.check(row,{row['source_row_id']})
        with self.assertRaises(ValueError):guard.check(row,{row['source_row_id']})
        with self.assertRaises(ValueError):pilot.OverrideGuard('im_val.csv',self.context.archive_sha256,self.context.model_sha256)

    def test_duplicate_physical_row_index_fails(self):
        row=['HLA-A*02:01','AAAAAAAAA','1'];records=[(1,['mhc','pep','tgt']),(2,row),(2,row)]
        class Writer:
            def writerow(self,row):pass
        with self.assertRaisesRegex(ValueError,'Duplicate row index'):
            pilot.score_stream('el_train.csv',records,self.context,Writer(),Writer())

    def test_identical_source_records_keep_distinct_row_ids(self):
        rows=[]
        class Writer:
            def writerow(self,row):rows.append(row)
        pilot.score_stream('el_train.csv',[(1,['mhc','pep','tgt']),(2,['HLA-A*02:01','AAAAAAAAA','1']),
            (3,['HLA-A*02:01','AAAAAAAAA','1'])],self.context,Writer(),io_sink())
        self.assertNotEqual(rows[0]['source_row_id'],rows[1]['source_row_id'])
        self.assertEqual(rows[0]['source_row_sha256'],rows[1]['source_row_sha256'])

    def test_stream_generator_with_constant_size_writer(self):
        class CounterWriter:
            def __init__(self):self.n=0
            def writerow(self,row):self.n+=1
        def source():
            yield 1,['mhc','pep','tgt']
            for index in range(1000):yield index+2,['HLA-A*02:01','AAAAAAAAA','1']
        writer=CounterWriter();result=pilot.score_stream('el_train.csv',source(),self.context,writer,io_sink())
        self.assertEqual(writer.n,1000);self.assertEqual(result['total_training_rows'],1000)

    def test_neighborhood_matches_distance_oracle(self):
        pairs=self.context.neighbors.fit_pairs
        for sequence in ('AAAAAAAAA','EAAAAAAAA','EEAAAAAAA','DDDDDDDDD'):
            result=self.context.neighbors.query(sequence,'HLA-A*02:01')
            expected=any(teacher_hla=='HLA-A*02:01' and sum(a!=b for a,b in zip(sequence,p))<=1 for p,teacher_hla in pairs)
            self.assertEqual(result['teacher_fit_within_one_mismatch_pair'],expected)

    def test_source_population_and_actual_fitted_exposure_differ(self):
        self.execute();rows=self.csv_output('el_train.csv')
        row=next(r for r in rows if r['original_peptide']=='DDDDDDDDD')
        self.assertEqual(row['DTU_source_exact_pair'],'1');self.assertEqual(row['teacher_fit_exact_pair'],'0')
        self.assertEqual(row['teacher_fit_within_one_mismatch_peptide'],'0')

    def test_strict_explicit_mapping_no_fuzzy_or_C67S(self):
        class Writer:
            def writerow(self,row):raise AssertionError('Unsupported rows have no predictions')
        result=pilot.score_stream('el_train.csv',[(1,['mhc','pep','tgt']),(2,['HLA-A02:01','AAAAAAAAA','1']),
            (3,['HLA-B*07:02(C67S)','AAAAAAAAA','1'])],self.context,Writer(),Writer())
        self.assertEqual(result['unsupported_by_reason'],{'unverified_or_ambiguous_HLA':2})

    def test_only_evidence_supported_notation_alias_is_accepted(self):
        doc=json.loads(self.files['mapping'].read_text())
        doc['data_HLA_mapping'].append({'original_HLA':'HLA-A02:01','canonical_two_field_HLA':'HLA-A*02:01','unique_canonical_reference_match':True})
        self.files['mapping'].write_text(raw.json_report(doc));context=pilot.load_context(self.config,self.files)
        self.assertEqual(context.mapping['HLA-A02:01'],'HLA-A*02:01')
        doc['data_HLA_mapping'].append({'original_HLA':'HLA-A02:01','canonical_two_field_HLA':'HLA-A*02:02','unique_canonical_reference_match':True})
        self.files['mapping'].write_text(raw.json_report(doc));context=pilot.load_context(self.config,self.files)
        self.assertNotIn('HLA-A02:01',context.mapping)

    def test_atomic_output_rejects_existing_or_symlink_target(self):
        path=self.run/'predictions/blocked.csv.gz';path.symlink_to(self.files['archive'])
        before=self.files['archive'].read_bytes()
        with self.assertRaises(FileExistsError):
            with pilot._csv_artifact(path):pass
        self.assertEqual(self.files['archive'].read_bytes(),before)

    def test_nonfinite_prediction_does_not_become_zero(self):
        with patch.object(teacher.Teacher,'predict_stability',return_value={'model_status':'ok','predicted_half_life_hours':float('nan')}):
            result=pilot.score_stream('el_train.csv',[(1,['mhc','pep','tgt']),(2,['HLA-A*02:01','AAAAAAAAA','1'])],self.context,io_sink(),io_sink())
        self.assertEqual(result['unsupported_by_reason'],{'nonfinite_or_negative_prediction':1});self.assertEqual(result['teacher_eligible_rows'],0)

    def test_frozen_model_checksum_gate(self):
        self.files['teacher'].write_text('{}')
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch: teacher'):self.execute()

    def test_teacher_receipt_lineage_gate(self):
        doc=json.loads(self.files['teacher_receipt'].read_text());doc['model_sha256']='0'*64
        self.files['teacher_receipt'].write_text(raw.json_report(doc))
        with self.assertRaisesRegex(ValueError,'lineage mismatch'):pilot.load_context(self.config,self.files)

    def test_deterministic_gzip_and_read_only_replay(self):
        self.execute();before={str(p):raw.sha256_file(p) for p in self.run.rglob('*') if p.is_file()}
        result=self.execute(verify_existing=True);self.assertTrue(result['verified_existing'])
        self.assertEqual(before,{str(p):raw.sha256_file(p) for p in self.run.rglob('*') if p.is_file()})
        data=(self.run/pilot.OUTPUTS['el_train.csv'][0]).read_bytes();self.assertEqual(data[4:8],b'\0'*4)

    def test_no_silent_overwrite(self):
        self.execute()
        with self.assertRaises(FileExistsError):self.execute()

    def test_failed_member_verification_cleans_only_own_partials(self):
        config=deepcopy(self.config);config['members']['el_train.csv']['rows']+=1
        self.configpath.write_text(raw.json_report(config))
        self.run=runs.create_run(paths=self.paths,kind='test',config=self.configpath,inputs=list(self.files.values()),argv=['fixture failure'],allow_dirty=True)
        with self.assertRaisesRegex(ValueError,'identity/count differs'):self.execute()
        self.assertEqual(list((self.run/'predictions').iterdir()),[]);self.assertEqual(list((self.run/'processed').iterdir()),[])

    def test_fixed_rules_not_optimized_and_large_fraction_flagged(self):
        result=self.execute()['members']['el_train.csv']
        self.assertEqual(len(result['large_change_warnings']),2)
        changed=deepcopy(self.config);changed['low_hours_exclusive']=2.0
        self.configpath.write_text(raw.json_report(changed))
        with self.assertRaises(ValueError):pilot.load_config(self.configpath)

    def test_machine_readable_four_condition_plan(self):
        plan=pilot.experiment_plan(self.context)
        self.assertEqual(set(plan['conditions']),set('ABCD'));self.assertIsNone(plan['conditions']['A']['EL_overrides'])
        self.assertIsNotNone(plan['conditions']['D']['IM_overrides']);self.assertFalse(plan['overrides_applied_to_source_data'])

    def test_pilot_CLI_and_existing_commands(self):
        args=['pseudolabel','pilot','--config',str(self.configpath),'--out',str(self.run)]
        for key,path in self.files.items():args+=['--input',key+'='+str(path)]
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):self.assertEqual(main(args,env=self.env),0)
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)


def io_sink():
    class Sink:
        def writerow(self,row):pass
    return Sink()


if __name__=='__main__':unittest.main()
