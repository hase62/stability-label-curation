"""Lightweight synthetic CSV/checkpoint contracts; real network training is canonical-only."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
import gzip
import io
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main

HLA='HLA-A*02:01'


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=resolve_paths({'CODEX_ROOT':self.temp.name});self.data=self.paths.project_data_dir;self.data.mkdir(parents=True)
        self.config=runner.load_config(self.paths.repository_root/runner.CONFIG)
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network in unit tests'))
        self.network.start();self.addCleanup(self.network.stop)

    def row(self,index,label='1',peptide='AAAAAAAAA',hla=HLA):
        return {'prepared_row_index':index,'hla':hla,'peptide':peptide,'original_label':label}

    def config_fails(self,key,value):
        c=deepcopy(self.config);c[key]=value;f=self.data/'bad.json';f.write_text(raw.json_report(c))
        with self.assertRaises(ValueError):runner.load_config(f)

    def test_only_original_condition_A(self):
        for key,value in [('condition','B'),('label_policy','low_only'),('label_policy','low_and_high')]:self.config_fails(key,value)

    def test_corrected_input_paths_rejected(self):
        c=deepcopy(self.config);c['inputs']['EL']['relative_path']='run/el_train_low_and_high.csv'
        f=self.data/'bad.json';f.write_text(raw.json_report(c))
        with self.assertRaises(ValueError):runner.load_config(f)
        with self.assertRaises(ValueError):runner.resolve_inputs(self.config,self.paths,{'EL':self.data/'el_train_low_only.csv'})

    def test_unsafe_runtime_configuration(self):
        for k,v in [('device','mps'),('num_workers',2),('persistent_workers',True),('cpu_threads',128),('wall_seconds',999999),
                    ('memory_bytes',128*1024**3),('batch_size',1024),('seed',1),('epochs',{'EL':10,'IM':1})]:self.config_fails(k,v)

    def test_subset_limit(self):
        self.config_fails('rows_per_class',{'EL':1001,'IM':64})

    def test_deterministic_stratified_selection(self):
        rows=[self.row(i,str(i%2)) for i in range(1,101)]
        a,c=runner.select_subset(iter(rows),5,42);b,_=runner.select_subset(iter(rows),5,42)
        self.assertEqual(a,b);self.assertEqual(c,{'1':50,'0':50})
        self.assertEqual(sum(r['original_label']=='1' for r in a),5)
        self.assertEqual([r['prepared_row_index'] for r in a],sorted(r['prepared_row_index'] for r in a))
        self.assertEqual(rows[0]['original_label'],'1')

    def test_subset_ignores_predictions_and_development_outcomes(self):
        rows=[self.row(i,str(i%2)) for i in range(1,101)];a,_=runner.select_subset(rows,5)
        changed=[dict(r,predicted_stability_hours=i,proposed_label='0',development_outcome=1) for i,r in enumerate(rows)]
        b,_=runner.select_subset(changed,5)
        self.assertEqual([r['prepared_row_index'] for r in a],[r['prepared_row_index'] for r in b])

    def test_insufficient_class_support(self):
        with self.assertRaises(ValueError):runner.select_subset([self.row(1)],1)

    def test_duplicate_identity_guard(self):
        with self.assertRaises(ValueError):runner.select_subset([self.row(1,'1'),self.row(1,'0')],1)

    def test_strict_HLA_and_sequence_validation(self):
        p=self.data/'el_train_original.csv'
        for h,pep,target in [(HLA,'AAAAAAAAA','2'),('HLA-A*99:99','AAAAAAAAA','1'),(HLA+'(C67S)','AAAAAAAAA','1'),
                             (HLA,'AAAAAAAAX','1'),(HLA,'AAAAAAAA','1')]:
            p.write_text(f'mhc,pep,tgt\n{h},{pep},{target}\n')
            with self.assertRaises(ValueError):list(runner.input_rows(p,{HLA}))

    def test_valid_original_rows_preserved(self):
        p=self.data/'el_train_original.csv';p.write_text('mhc,pep,tgt\n'+HLA+',AAAAAAAAA,1\n')
        before=raw.sha256_file(p);rows=list(runner.input_rows(p,{HLA}))
        self.assertEqual(rows,[self.row(1)]);self.assertEqual(raw.sha256_file(p),before)
        self.assertEqual(runner.csv_text(rows),'mhc,pep,tgt\n'+HLA+',AAAAAAAAA,1\n')

    def test_global_exact_and_one_mismatch_separation(self):
        dev=[self.row(1,peptide='AAAAAAAAA',hla='HLA-B*08:01')]
        for peptide in ('AAAAAAAAA','CAAAAAAAA'):
            with self.assertRaises(ValueError):runner.verify_separation([self.row(1,peptide=peptide)],dev)
        self.assertEqual(runner.verify_separation([self.row(1,peptide='CCAAAAAAA')],dev)['prohibited_matches'],0)

    def test_source_SHA_gate_before_execution(self):
        p=self.data/'tampered';p.write_text('changed')
        with self.assertRaises(ValueError):runner.resolve_inputs(self.config,self.paths,{name:p for name in self.config['inputs']})

    def test_pinned_source_revision_required(self):self.config_fails('source_commit','a'*40)

    def test_fixed_runtime_seed(self):
        events=[]
        torch=SimpleNamespace(**{name:lambda value,n=name:events.append((n,value)) for name in
            ('manual_seed','set_num_threads','set_num_interop_threads','use_deterministic_algorithms')})
        np=SimpleNamespace(random=SimpleNamespace(seed=lambda value:events.append(('numpy_seed',value))))
        runner.seed_runtime(torch,np,self.config);first=random.random()
        runner.seed_runtime(torch,np,self.config)
        self.assertEqual(first,random.random());self.assertIn(('manual_seed',42),events);self.assertIn(('set_num_interop_threads',1),events)

    def test_safe_exclusive_checkpoint_storage(self):
        parent=self.data/'checkpoints';parent.mkdir();el=parent/'el';runner.reserve_checkpoint(el)
        keys=['base',*runner.TRANSFER]
        for i,k in enumerate(keys):(el/f'{i}_{k}.lyr').write_bytes(k.encode())
        identity=runner.checkpoint_identity(el,keys)
        self.assertEqual(len(identity),5)
        with self.assertRaises(FileExistsError):runner.reserve_checkpoint(el)
        (el/'extra.lyr').write_text('extra')
        with self.assertRaises(ValueError):runner.checkpoint_identity(el,keys)

    def checkpoint_fixture(self):
        el=self.data/'el';el.mkdir();im=el/'im';im.mkdir();keys=['base',*runner.TRANSFER]
        for i,k in enumerate(keys):(el/f'{i}_{k}.lyr').write_bytes(('EL'+k).encode())
        for i,k in enumerate(keys):
            if k in runner.TRANSFER:(im/f'{i}_{k}.lyr').write_bytes(('IM'+k).encode())
        lineage={'state_keys':keys,'EL_files':runner.checkpoint_identity(el,keys),'IM_files':runner.overlay_identity(im,keys)}
        return el,im,lineage

    def test_IM_overlay_parent_and_tensors(self):
        el,im,lineage=self.checkpoint_fixture();runner.verify_parent(el,im,lineage)
        self.assertEqual(len(lineage['IM_files']),4)
        (el/'0_base.lyr').write_bytes(b'changed-parent')
        with self.assertRaises(ValueError):runner.verify_parent(el,im,lineage)

    def test_invalid_overlay_ancestry_rejected(self):
        el,im,lineage=self.checkpoint_fixture()
        with self.assertRaises(ValueError):runner.verify_parent(self.data/'other',im,lineage)
        (im/next(iter(lineage['IM_files']))).write_bytes(b'changed-overlay')
        with self.assertRaises(ValueError):runner.verify_parent(el,im,lineage)

    def test_symlink_checkpoint_rejected(self):
        target=self.data/'tensor';target.write_text('preserve');el=self.data/'el';el.mkdir();(el/'0_base.lyr').symlink_to(target)
        with self.assertRaises(OSError):runner.checkpoint_identity(el,['base'])

    def test_original_lineage_join(self):
        p=self.data/'provenance.csv.gz';rows=[self.row(3)]
        fields=['retained',*runner.PROVENANCE_FIELDS]
        rec=dict.fromkeys(fields,'');rec.update(retained='1',derived_row_index='3',resolved_hla=HLA,original_peptide='AAAAAAAAA',
            original_hla=HLA,original_label='1',source_file='el_train.csv',row_index='123',source_row_id='immutable-row-123')
        with gzip.open(p,'wt',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(rec)
        runner.attach_provenance(rows,p);self.assertEqual(rows[0]['source_locator']['source_row_id'],'immutable-row-123')
        with self.assertRaises(ValueError):runner.attach_provenance([self.row(4)],p)

    def test_development_prediction_identity_and_reload_contract(self):
        run=self.paths.project_runs_dir/'test';(run/'predictions').mkdir(parents=True)
        row=self.row(3);row['source_locator']={'source_row_id':'imval-original-17','original_hla':HLA}
        target=run/'predictions/el.csv';runner.write_predictions(target,[row],[0.125],self.paths)
        with target.open() as f:record=next(csv.DictReader(f))
        self.assertEqual(record['source_row_id'],'imval-original-17');self.assertEqual(record['original_label'],'1')
        self.assertEqual(record['development_row_index'],'3');self.assertEqual(record['probability'],'0.125')
        with self.assertRaises(FileExistsError):runner.write_predictions(target,[row],[0.25],self.paths)

    def test_runtime_imports_are_lazy_and_old_CLI_preserved(self):
        for command in ('bigmhc-smoke','pilot-prepare','teacher','allele-diagnostics'):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as e:main([command,'--help'])
            self.assertEqual(e.exception.code,0)

    def test_no_archive_or_sealed_payload_inputs(self):
        values=[item['relative_path'] for item in self.config['inputs'].values()]
        self.assertFalse(any(v.endswith(('.zip','el_test.csv','im_test.csv','iedb.csv','manafest.csv')) for v in values))

    def test_inference_reload_values_and_invalid_prediction_rejection(self):
        from contextlib import nullcontext
        class Tensor:
            def float(self):return self
            def cpu(self):return self
        class Dataset:
            df=[0,1]
            def makebats(self,*args,**kwargs):self.settings=kwargs
            def __len__(self):return 1
            def __getitem__(self,index):return SimpleNamespace(mhc=Tensor(),pep=Tensor())
        class Model:
            def __init__(self,values):self.values=values;self.evaluation=False
            def cpu(self):return self
            def eval(self):self.evaluation=True;return self
            def __call__(self,*args,**kwargs):return self.values,None
        torch=SimpleNamespace(no_grad=nullcontext,sigmoid=lambda out:SimpleNamespace(tolist=lambda:out))
        model=Model([.2,.8]);dataset=Dataset()
        self.assertEqual(runner.predict(torch,model,dataset,8),runner.predict(torch,Model(list(model.values)),dataset,8))
        self.assertTrue(model.evaluation);self.assertFalse(dataset.settings['shuffle'])
        with self.assertRaises(ValueError):runner.predict(torch,Model([float('nan'),.8]),dataset,8)
        with self.assertRaises(ValueError):runner.predict(torch,Model([.5]),dataset,8)

    def test_memory_budget_terminates_only_owned_worker(self):
        run=self.paths.project_runs_dir/'fake';(run/'logs').mkdir(parents=True);(run/'reports').mkdir()
        class Process:
            pid=123;returncode=None;terminated=False
            def poll(self):return self.returncode
            def terminate(self):self.terminated=True;self.returncode=-15
            def wait(self,timeout=None):return self.returncode
        process=Process()
        psutil=SimpleNamespace(Process=lambda pid:SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=7*1024**3)),NoSuchProcess=ProcessLookupError)
        with patch.object(runner,'resolve_inputs',return_value=({},[])),patch.object(runner.teacher,'_run',return_value=(run,{})),\
             patch.dict('sys.modules',{'psutil':psutil}),patch.object(runner.subprocess,'Popen',return_value=process):
            with self.assertRaises(RuntimeError):runner.run(config_path=self.paths.repository_root/runner.CONFIG,out=run,paths=self.paths)
        self.assertTrue(process.terminated)
        result=runner.readers._json(run/'reports/resource_execution.json')
        self.assertEqual(result['blocker'],'worker_RSS_budget_exceeded')
        self.assertEqual(result['status'],'failed')
