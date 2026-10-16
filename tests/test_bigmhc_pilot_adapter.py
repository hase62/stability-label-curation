"""Synthetic source rows, frozen score ledgers and sealed sentinel members; no training."""
from collections import defaultdict
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from stability_label_curation import bigmhc_pilot_adapter as adapter
from stability_label_curation import pseudolabel_pilot as pilot
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main

HLA = 'HLA-A*02:01'
OTHER = 'HLA-B*08:01'


class Writer:
    def __init__(self): self.rows = []
    def writerow(self, row): self.rows.append(deepcopy(row))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.paths = resolve_paths({'CODEX_ROOT': self.temp.name})
        self.paths.project_data_dir.mkdir(parents=True)
        self.reference = {HLA: [HLA], OTHER: [OTHER]}
        self.context = SimpleNamespace(archive_sha256='a'*64, model_sha256='b'*64,
            mapping={HLA:HLA, OTHER:OTHER},
            model=SimpleNamespace(document={'config':{},'alleles': {h: {'status':'trained'} for h in (HLA,OTHER)}}),
            neighbors=pilot.NeighborIndex({('AAAAAAAAA',HLA)}, {('AAAAAAAAA',HLA)}), provenance={'frozen':True})
        self.header = ['mhc','pep','tgt']
        self.fields = [HLA,'DDDDDDDDD','1']
        self.score = self.make_score(1,self.fields,0.5)
        self.net = patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Network forbidden'))
        self.net.start(); self.addCleanup(self.net.stop)

    def make_score(self,index,fields,hours,member='el_train.csv'):
        header = self.header + (['rand'] if member=='im_train.csv' else [])
        cat,action,label = pilot.category_and_action(fields[2],hours)
        score = {k:'0' for k in pilot.FIELDS}
        score.update(source_file=member,row_index=str(index),source_line_number=str(index+1),
            source_row_id=pilot.row_id(self.context.archive_sha256,member,index),
            source_row_sha256=adapter.source_hash(header,fields),original_hla=fields[0],original_peptide=fields[1],
            original_label=fields[2],resolved_hla=self.context.mapping.get(fields[0]),predicted_half_life_hours=str(hours),
            stability_category=cat,candidate_action=action,proposed_pseudolabel=label,
            model_status='ok',teacher_model_sha256=self.context.model_sha256,teacher_version=pilot.teacher.VERSION,rule_version=pilot.VERSION)
        return score

    def views(self,rows=None,scores=None,overrides=None,dev=('CCCCCCCCC',)):
        rows = rows if rows is not None else [self.fields]
        scores = scores if scores is not None else [self.score]
        overrides = overrides if overrides is not None else [self.score]
        writers = {p:Writer() for p in adapter.POLICIES}; ledger=Writer()
        result,_=adapter.train_views('el_train.csv',[(1,self.header),*((i+2,r) for i,r in enumerate(rows))],
            iter(scores),iter(overrides),self.context,self.reference,
            pilot.NeighborIndex({(p,OTHER) for p in dev},{(p,OTHER) for p in dev}),
            adapter.substitution_neighborhood(dev),writers,ledger)
        return result,writers,ledger

    def test_strict_source_join(self):
        adapter.check_score(self.score,'el_train.csv',1,2,self.header,self.fields,self.context)
        for field in ('source_file','source_row_sha256','original_hla','original_peptide','original_label','resolved_hla','teacher_model_sha256'):
            broken=dict(self.score);broken[field]='incorrect'
            with self.assertRaises(ValueError):adapter.check_score(broken,'el_train.csv',1,2,self.header,self.fields,self.context)

    def test_index_and_line_integrity(self):
        for index,line in ((2,2),(1,3)):
            with self.assertRaises(ValueError):adapter.check_score(self.score,'el_train.csv',index,line,self.header,self.fields,self.context)

    def test_original_and_low_only_views(self):
        result,writers,ledger=self.views()
        self.assertEqual([writers[p].rows[0]['tgt'] for p in adapter.POLICIES],['1','0','0'])
        self.assertEqual(ledger.rows[0]['original_label'],'1')
        self.assertEqual(result['retained_rows'],1)
        self.assertEqual(self.fields[2],'1')

    def test_high_can_be_selected_without_rescoring(self):
        fields=[HLA,'DDDDDDDDD','0'];s=self.make_score(1,fields,10)
        _,writers,_=self.views([fields],[s],[s])
        self.assertEqual([writers[p].rows[0]['tgt'] for p in adapter.POLICIES],['0','0','1'])

    def test_no_change_score_needs_no_override(self):
        s=self.make_score(1,self.fields,3)
        _,writers,_=self.views(scores=[s],overrides=[])
        self.assertTrue(all(w.rows[0]['tgt']=='1' for w in writers.values()))

    def test_missing_and_mismatched_override_rejected(self):
        with self.assertRaises(ValueError):self.views(overrides=[])
        s=dict(self.score);s['original_label']='0'
        with self.assertRaises(ValueError):self.views(overrides=[s])

    def test_duplicate_overrides_rejected(self):
        with self.assertRaises(ValueError):self.views(overrides=[self.score,self.score])

    def test_extra_score_rejected(self):
        with self.assertRaises(ValueError):self.views(scores=[self.score,self.score])

    def test_missing_score_rejected(self):
        with self.assertRaises(ValueError):self.views(scores=[],overrides=[])

    def test_cross_HLA_exact_purge(self):
        result,writers,ledger=self.views(dev=('DDDDDDDDD',))
        self.assertEqual(result['purged_exact'],1)
        self.assertTrue(all(not w.rows for w in writers.values()))
        self.assertEqual(ledger.rows[0]['original_label'],'1')

    def test_cross_HLA_one_mismatch_purge(self):
        result,_,_=self.views(dev=('CDDDDDDDD',))
        self.assertEqual(result['purged_one_mismatch_only'],1)

    def test_two_mismatches_retained(self):
        result,_,_=self.views(dev=('CCDDDDDDD',))
        self.assertEqual(result['retained_rows'],1)

    def test_independent_verification_disagreement_rejected(self):
        with self.assertRaises(ValueError):
            adapter.train_views('el_train.csv',[(1,self.header),(2,self.fields)],iter([self.score]),iter([self.score]),
                self.context,self.reference,pilot.NeighborIndex(set(),set()),{'DDDDDDDDD'},
                {p:Writer() for p in adapter.POLICIES},Writer())

    def test_teacher_fit_global_exposure_excludes_development(self):
        records=[(1,['mhc','pep','tgt','rand']),(2,[OTHER,'AAAAAAAAA','1','0']),
            (3,[OTHER,'CAAAAAAAA','0','0']),(4,[HLA,'DDDDDDDDD','1','0'])]
        w=Writer();l=Writer();r,pairs=adapter.development(records,self.context,self.reference,w,l)
        self.assertEqual(r['retained'],1)
        self.assertEqual(r['excluded_by_reason'],{'Teacher_fit_exact_peptide':1,'Teacher_fit_one_mismatch_peptide':1})
        self.assertEqual(pairs,{('DDDDDDDDD',HLA)})

    def test_development_selection_does_not_use_label(self):
        def run(label):
            return adapter.development([(1,['mhc','pep','tgt','rand']),(2,[HLA,'DDDDDDDDD',label,'0'])],
                self.context,self.reference,Writer(),Writer())[1]
        self.assertEqual(run('0'),run('1'))

    def test_no_automatic_rule_weakening(self):
        with self.assertRaises(ValueError):adapter.development([(1,['mhc','pep','tgt','rand']),
            (2,[OTHER,'AAAAAAAAA','1','0'])],self.context,self.reference,Writer(),Writer())

    def test_evaluation_overrides_forbidden(self):
        with self.assertRaises(ValueError):adapter.apply_override(self.score,self.score,'im_val.csv',self.context,'low_only',authorized=True)
        with self.assertRaises(ValueError):adapter.apply_override(self.score,self.score,'el_train.csv',self.context,'low_only',authorized=False)

    def test_unsupported_sequence_and_HLA(self):
        for peptide,hla,reason in [('AAAA',HLA,'unsupported_peptide_length'),('AAAAAAAAZ',HLA,'noncanonical_amino_acid'),
                                   ('AAAAAAAAA','HLA-A*99:99','unverified_or_unsupported_HLA')]:
            self.assertEqual(adapter.exclusion_reason(peptide,hla,self.context,self.reference),reason)

    def test_ambiguous_reference_rejected(self):
        self.reference[HLA].append('alternative')
        self.assertEqual(adapter.exclusion_reason('AAAAAAAAA',HLA,self.context,self.reference),'unresolved_or_ambiguous_reference')

    def test_mutant_not_mapped(self):
        self.assertEqual(adapter.exclusion_reason('AAAAAAAAA','HLA-B*08:01(C67S)',self.context,self.reference),'unverified_or_unsupported_HLA')

    def test_same_row_eligibility_across_conditions(self):
        result,writers,_=self.views()
        self.assertEqual({tuple((r['mhc'],r['pep']) for r in w.rows) for w in writers.values()},{((HLA,'DDDDDDDDD'),)})
        self.assertEqual(len(result['source_identity_order_sha256_all_views']),64)

    def test_nonfinite_prediction_rejected(self):
        s=dict(self.score);s['predicted_half_life_hours']='nan'
        with self.assertRaises(ValueError):self.views(scores=[s],overrides=[s])

    def test_deterministic_gzip_and_plain_hash_replay(self):
        for compressed in (False,True):
            p=self.paths.project_data_dir/('out.gz' if compressed else 'out.csv')
            with adapter.artifact_csv(p,['x'],compressed) as (w,s):w.writerow({'x':'value'})
            with adapter.artifact_csv(None,['x'],compressed) as (w,replay):w.writerow({'x':'value'})
            self.assertEqual(s.digest.hexdigest(),replay.digest.hexdigest())
            self.assertEqual(raw.sha256_file(p),s.digest.hexdigest())
            with self.assertRaises(FileExistsError):
                with adapter.artifact_csv(p,['x'],compressed):pass

    def test_duplicate_gzip_row_index(self):
        p=self.paths.project_data_dir/'scores.gz'
        with gzip.open(p,'wt',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=pilot.FIELDS);w.writeheader();w.writerows([self.score,self.score])
        with self.assertRaises(ValueError):list(adapter._csv_rows(p))

    def test_sealed_member_access_denied(self):
        for member in ('im_test.csv','el_test.csv','iedb.csv','manafest.csv','el_val.csv'):
            with self.assertRaises(ValueError):adapter._source_rows(None,member,{},[],{})

    def test_config_and_input_checksums(self):
        c=adapter.load_config(self.paths.repository_root/adapter.CONFIG)
        with self.assertRaises((ValueError,FileNotFoundError)):adapter.resolve_inputs(c,self.paths,{'archive':self.paths.project_data_dir/'absent.zip'})
        broken=deepcopy(c);broken['maximum_hamming_distance']=2
        p=self.paths.project_data_dir/'bad.json';p.write_text(raw.json_report(broken))
        with self.assertRaises(ValueError):adapter.load_config(p)

    def test_cli_help_and_compatibility(self):
        for command in ('pilot-prepare','teacher','pseudolabel','paths'):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as caught:main([command,'--help'])
            self.assertEqual(caught.exception.code,0)

    def test_readonly_failed_default_cli_preserves_source(self):
        snapshot=dict(self.score)
        with self.assertRaises(ValueError):adapter.apply_override(self.score,None,'im_test.csv',self.context,'original',authorized=False)
        self.assertEqual(snapshot,self.score)

    def test_independent_substitution_oracle(self):
        n=adapter.substitution_neighborhood({'AAAAAAAAA'})
        self.assertEqual(len(n),172)
        self.assertIn('CAAAAAAAA',n);self.assertNotIn('CCAAAAAAA',n)
        self.assertTrue(adapter.independent_exposed('CAAAAAAAA',{'AAAAAAAAA'}))

    def test_streaming_single_pass(self):
        class Once:
            def __iter__(s):
                if getattr(s,'used',False):raise AssertionError('Second pass')
                s.used=True;return iter([(1,self.header),(2,self.fields)])
        r,_=adapter.train_views('el_train.csv',Once(),iter([self.score]),iter([self.score]),self.context,self.reference,
            pilot.NeighborIndex(set(),set()),set(),{p:Writer() for p in adapter.POLICIES},Writer())
        self.assertEqual(r['retained_rows'],1)

    def test_complete_preparation_replay_and_input_integrity(self):
        directory=self.paths.project_data_dir
        texts={'el_train.csv':'mhc,pep,tgt\n'+HLA+',DDDDDDDDD,1\n'+HLA+',EEEEEEEEE,0\n'+HLA+',FFFFFFFFF,1\n'+HLA+',GGGGGGGGG,0\n'+OTHER+',CCCCCCCCC,1\n',
            'im_train.csv':'mhc,pep,tgt,rand\n'+OTHER+',DDDDDDDDD,1,0\n'+HLA+',FFFFFFFFF,1,0\n'+HLA+',GGGGGGGGG,0,0\n',
            'im_val.csv':'mhc,pep,tgt,rand\n'+HLA+',CCCCCCCCC,1,0\n'+OTHER+',AAAAAAAAA,0,0\n'}
        archive=directory/'archive.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name,text in texts.items():z.writestr(name,text)
            for name in ('el_val.csv','el_test.csv','im_test.csv','iedb.csv','manafest.csv'):z.writestr(name,b'SEALED\xff')
        self.context.archive_sha256=raw.sha256_file(archive)
        harmless=directory/'identity.json';harmless.write_text('{}')
        files={k:harmless for k in pilot.INPUTS};files['archive']=archive
        config=adapter.load_config(self.paths.repository_root/adapter.CONFIG)
        old=config['scoring_config']
        for name,path in files.items():
            old['inputs'][name]={'area':'data','relative_path':path.name,'sha256':raw.sha256_file(path)}
        for member in pilot.MEMBERS:
            old['members'][member]={'rows':len(texts[member].splitlines())-1,'sha256':hashlib.sha256(texts[member].encode()).hexdigest()}
        config['development_member']={'rows':2,'sha256':hashlib.sha256(texts['im_val.csv'].encode()).hexdigest()}
        score_artifacts={}
        for stage,member in (('el','el_train.csv'),('im','im_train.csv')):
            rows=list(csv.reader(io.StringIO(texts[member])))[1:]
            scores=[self.make_score(i,row,5.0 if row[1] in ('FFFFFFFFF','GGGGGGGGG') else 0.5 if row[2]=='1' else 10.0,member) for i,row in enumerate(rows,1)]
            for kind,relative in zip(('scores','overrides'),pilot.OUTPUTS[member]):
                f=directory/(stage+'_'+kind+'.gz');files[stage+'_'+kind]=f
                with adapter.artifact_csv(f,pilot.FIELDS,True) as (w,s):
                    for row in scores:
                        if kind=='scores' or row['candidate_action']!='no_change':w.writerow(row)
                score_artifacts[relative]={'sha256':raw.sha256_file(f)}
        summary={'artifacts':score_artifacts,'members':{m:{'by_original_HLA':{}} for m in pilot.MEMBERS}}
        files['scoring_summary']=directory/'summary.json';files['scoring_summary'].write_text(raw.json_report(summary))
        files['scoring_receipt']=directory/'receipt.json';files['scoring_receipt'].write_text(raw.json_report(
            {'report_sha256':{'pseudolabel_summary.json':raw.sha256_file(files['scoring_summary'])}}))
        files['teacher_metrics']=directory/'metrics.json';files['teacher_metrics'].write_text(raw.json_report({'results':{OTHER:{'n':3}}}))
        files['reference']=directory/'reference.csv'
        with files['reference'].open('w',newline='') as f:
            w=csv.writer(f);features=[(i,a) for i in range(30) for a in pilot.teacher.ALPHABET[:14 if i<29 else 8]]
            w.writerow(['mhc',*(str(i)+'_'+a for i,a in features)])
            for h in (HLA,OTHER):w.writerow([h,*(int(a=='A') for i,a in features)])
        for kind in ('dataset_code','cli_code'):
            f=directory/(kind+'.py');f.write_text('class Dataset:\n    pass\n');files[kind]=f
        files['teacher_receipt']=directory/'teacher-receipt.json'
        files['teacher_receipt'].write_text(raw.json_report({'report_sha256':{'teacher_validation_metrics.json':raw.sha256_file(files['teacher_metrics'])}}))
        old['inputs']['teacher_receipt']={'area':'data','relative_path':files['teacher_receipt'].name,'sha256':raw.sha256_file(files['teacher_receipt'])}
        for name in adapter.EXTRA:
            config['inputs'][name]={'area':'data','relative_path':files[name].name,'sha256':raw.sha256_file(files[name])}
        configpath=directory/'preparation.json';configpath.write_text(raw.json_report(config))
        _,inputs=adapter.resolve_inputs(config,self.paths,files)
        run=runs.create_run(paths=self.paths,kind='test',config=configpath,seed=42,
            inputs=[i['path'] for i in inputs],argv=['synthetic preparation'],allow_dirty=True)
        before={str(p):raw.sha256_file(p) for p in set(files.values())}
        real_open=zipfile.ZipFile.open
        def guarded_open(archive,name,*args,**kwargs):
            actual=name.filename if isinstance(name,zipfile.ZipInfo) else name
            if Path(actual).name not in adapter.ALLOWED:raise AssertionError('Sealed payload opened')
            return real_open(archive,name,*args,**kwargs)
        with patch.object(pilot,'load_context',return_value=self.context),patch.object(zipfile.ZipFile,'open',guarded_open),\
             patch.object(pilot.teacher,'load_population',return_value=([SimpleNamespace(original_allele=OTHER,parsed_measurement_decimal='0.00')],{})),\
             patch.object(pilot.teacher,'fit',side_effect=AssertionError('No fitting')),\
             patch.object(pilot.teacher.Teacher,'predict_stability',side_effect=AssertionError('No rescoring')):
            result=adapter.prepare(config_path=configpath,out=run,paths=self.paths,files=files)
            replay=adapter.prepare(config_path=configpath,out=run,paths=self.paths,files=files,verify_existing=True)
        self.assertEqual(result['artifacts'],replay['artifacts'])
        self.assertEqual(result['training']['el_train.csv']['retained_rows'],4)
        self.assertEqual(result['training']['el_train.csv']['purged_exact'],1)
        self.assertEqual(result['development']['retained'],1)
        self.assertEqual(before,{str(p):raw.sha256_file(p) for p in set(files.values())})
        self.assertTrue((run/'reports/pilot_experiment_manifest.json').exists())
        manifest=json.loads((run/'reports/pilot_experiment_manifest.json').read_text())
        self.assertEqual(set(manifest['conditions']),set('ABCD'))

    def test_loader_contract_rejects_invalid_labels(self):
        p=self.paths.project_data_dir/'input.csv';p.write_text('mhc,pep,tgt\n'+HLA+',AAAAAAAAA,2\n')
        with self.assertRaises(ValueError):adapter.loader_contract_smoke(p,self.reference)

    def test_symlink_output_and_parent_rejected(self):
        actual=self.paths.project_data_dir/'actual';actual.mkdir()
        linked=self.paths.project_data_dir/'linked';linked.symlink_to(actual,target_is_directory=True)
        with self.assertRaises(OSError):
            with adapter.artifact_csv(linked/'out.csv',['x']):pass
        target=actual/'existing';target.write_text('preserve')
        output=actual/'out';output.symlink_to(target)
        with self.assertRaises(FileExistsError):
            with adapter.artifact_csv(output,['x']):pass
        self.assertEqual(target.read_text(),'preserve')

    def test_failed_output_has_no_completed_file(self):
        p=self.paths.project_data_dir/'failed.csv'
        with self.assertRaises(RuntimeError):
            with adapter.artifact_csv(p,['x']) as (writer,sink):
                writer.writerow({'x':'unfinished'});raise RuntimeError('failure')
        self.assertFalse(p.exists())
        self.assertFalse(list(p.parent.glob('*.partial')))
