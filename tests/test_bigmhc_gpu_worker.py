"""Lightweight device and handoff tests; no CUDA, source execution or training."""
from contextlib import nullcontext, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import bigmhc_gpu_worker as worker
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation.__main__ import main
from stability_label_curation.paths import resolve_paths


class GPUWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=resolve_paths({'CODEX_ROOT':self.temp.name})
        self.cpu=runner.load_config(self.paths.repository_root/runner.CONFIG)
        self.gpu=runner.load_config(self.paths.repository_root/worker.CONFIG)
        self.root=Path(self.temp.name).resolve()
        network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network'))
        network.start();self.addCleanup(network.stop)

    def config_file(self,c):
        f=self.root/'config.json';f.write_text(raw.json_report(c));return f

    def test_cpu_default_and_no_cuda_probe(self):
        c=deepcopy(self.cpu);del c['device']
        self.assertEqual(runner.load_config(self.config_file(c))['device'],'cpu')
        self.assertEqual(runner.runtime_device(SimpleNamespace(),c),'cpu')

    def test_cuda_config_preserves_approved_scientific_inputs_and_subset(self):
        for key in self.cpu:
            if key not in ('version','device'):self.assertEqual(self.cpu[key],self.gpu[key],key)
        self.assertEqual(self.gpu['device'],'cuda');self.assertEqual(self.gpu['seed'],42)
        self.assertEqual(self.gpu['rows_per_class'],{'EL':128,'IM':64})

    def test_explicit_single_gpu_selection(self):
        torch=Mock();torch.cuda.is_available.return_value=True;torch.cuda.device_count.return_value=1
        for gpu in ('0','1'):
            with patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':gpu}):
                self.assertEqual(runner.runtime_device(torch,self.gpu),'cuda:0')
        torch.cuda.set_device.assert_called_with(0);torch.cuda.reset_peak_memory_stats.assert_called_with(0)

    def test_cuda_unavailable_fails_without_fallback(self):
        torch=Mock();torch.cuda.is_available.return_value=False
        with patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'0'}),self.assertRaisesRegex(RuntimeError,'No CPU fallback'):
            runner.runtime_device(torch,self.gpu)
        torch.cuda.set_device.assert_not_called()

    def test_multiple_or_missing_gpu_selection_rejected(self):
        for value in ('','0,1','-1','all','０'):
            with self.assertRaises(ValueError):runner.cuda_visibility({'CUDA_VISIBLE_DEVICES':value})
        torch=Mock();torch.cuda.is_available.return_value=True;torch.cuda.device_count.return_value=2
        with patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'0'}),self.assertRaisesRegex(RuntimeError,'exactly one'):
            runner.runtime_device(torch,self.gpu)

    def test_unknown_device_rejected(self):
        for value in ('mps','auto','cuda:1',None):
            c=deepcopy(self.gpu);c['device']=value
            with self.assertRaises(ValueError):runner.load_config(self.config_file(c))

    def test_future_size_and_budget_are_explicit_not_smoke_defaults(self):
        c=deepcopy(self.gpu);c.update(rows_per_class={'EL':4096,'IM':512},wall_seconds=1800,memory_bytes=8*1024**3,batch_size=16)
        self.assertEqual(runner.load_config(self.config_file(c))['rows_per_class']['EL'],4096)
        c['wall_seconds']=1801
        with self.assertRaises(ValueError):runner.load_config(self.config_file(c))
        self.assertEqual(self.gpu['wall_seconds'],600)

    def test_original_only_and_corrected_paths_rejected_on_cuda(self):
        for key,value in (('condition','B'),('label_policy','low_and_high')):
            c=deepcopy(self.gpu);c[key]=value
            with self.assertRaises(ValueError):runner.load_config(self.config_file(c))
        c=deepcopy(self.gpu);c['inputs']['EL']['relative_path']='processed/el_train_low_only.csv'
        with self.assertRaises(ValueError):runner.load_config(self.config_file(c))

    def test_all_original_im_is_explicit_and_worker_only(self):
        c=deepcopy(self.gpu);c['rows_per_class']={'EL':4096,'IM':None}
        self.assertIsNone(runner.load_config(self.config_file(c))['rows_per_class']['IM'])
        c['expected_rows']['IM']=3427
        with self.assertRaises(ValueError):runner.load_config(self.config_file(c))
        c=deepcopy(self.cpu);c['rows_per_class']['IM']=None
        with self.assertRaises(ValueError):runner.load_config(self.config_file(c))
        c=deepcopy(self.gpu);c['rows_per_class']['EL']=None
        with self.assertRaises(ValueError):runner.load_config(self.config_file(c))

    def test_full_eligible_profile_retains_population_and_bounded_cuda(self):
        c=runner.load_config(self.paths.repository_root/'configs/bigmhc_gpu_baseline_task2_10.json')
        self.assertEqual(c['rows_per_class'],{'EL':None,'IM':None})
        self.assertEqual(c['inputs'],self.gpu['inputs'])
        for key,value in [('device','cpu'),('batch_size',8),('wall_seconds',7201),('memory_bytes',33*1024**3),
                          ('rows_per_class',{'EL':4096,'IM':None}),('expected_rows',{'EL':1453577,'IM':3428}),
                          ('expected_class_counts',{'EL':{'0':1383508,'1':70070},'IM':{'0':2473,'1':955}})]:
            bad=deepcopy(c);bad[key]=value
            with self.assertRaises(ValueError):runner.load_config(self.config_file(bad))

    def test_gpu_seed_and_deterministic_settings(self):
        torch=Mock();np=Mock()
        runner.seed_runtime(torch,np,self.gpu)
        torch.cuda.manual_seed_all.assert_called_once_with(42)
        torch.use_deterministic_algorithms.assert_called_once_with(True)
        self.assertFalse(torch.backends.cudnn.benchmark)
        self.assertTrue(torch.backends.cudnn.deterministic)
        self.assertFalse(torch.backends.cuda.matmul.allow_tf32)

    def test_gpu_diagnostics(self):
        torch=Mock();torch.version.cuda='fixture-runtime';torch.cuda.get_device_name.return_value='fixture GPU'
        torch.cuda.get_device_properties.return_value=SimpleNamespace(total_memory=24*1024**3)
        report=runner.device_report(torch,'cuda:0')
        self.assertEqual(report['GPU_name'],'fixture GPU')
        self.assertEqual(report['torch_CUDA_runtime'],'fixture-runtime')
        self.assertEqual(report['GPU_total_memory_bytes'],24*1024**3)

    def test_cpu_diagnostics_do_not_claim_cuda_execution(self):
        torch=SimpleNamespace(version=SimpleNamespace(cuda=None))
        self.assertIsNone(runner.device_report(torch,'cpu')['GPU_name'])

    def checkpoint_fixture(self):
        el=self.root/'el';el.mkdir();im=el/'im';im.mkdir()
        keys=['base',*runner.TRANSFER]
        for i,key in enumerate(keys):
            (el/f'{i}_{key}.lyr').write_bytes(('EL:'+key).encode())
            if key in runner.TRANSFER:(im/f'{i}_{key}.lyr').write_bytes(('IM:'+key).encode())
        lineage={'state_keys':keys,'EL_files':runner.checkpoint_identity(el,keys),'IM_files':runner.overlay_identity(im,keys)}
        return el,im,keys,lineage

    def loader(self):
        calls=[]
        def load(stream,**kwargs):
            calls.append(kwargs)
            return stream.read()
        model=Mock();model.cpu.return_value=model;model.to.return_value=model
        return SimpleNamespace(load=load,is_tensor=lambda v:isinstance(v,bytes)),Mock(return_value=model),model,calls

    def test_cross_device_load_always_stages_on_cpu(self):
        el,_,keys,_=self.checkpoint_fixture();torch,constructor,model,calls=self.loader()
        result=runner.load_checkpoint(torch,constructor,el,keys,device='cuda:0')
        self.assertIs(result,model);model.to.assert_called_once_with('cuda:0')
        self.assertTrue(all(c=={'map_location':'cpu','weights_only':True} for c in calls))
        self.assertEqual(model.load_state_dict.call_args.kwargs,{'strict':True})
        runner.load_checkpoint(torch,constructor,el,keys,device='cpu');model.cpu.assert_called_once()

    def test_transfer_load_inherits_exact_immediate_el_parent(self):
        el,im,keys,lineage=self.checkpoint_fixture();torch,constructor,model,_=self.loader()
        runner.load_checkpoint(torch,constructor,im,keys,lineage=lineage,device='cuda:0')
        state=model.load_state_dict.call_args.args[0]
        self.assertEqual(state['base'],b'EL:base')
        self.assertTrue(all(state[key]==('IM:'+key).encode() for key in runner.TRANSFER))
        (el/'0_base.lyr').write_bytes(b'tampered')
        with self.assertRaises(ValueError):runner.load_checkpoint(torch,constructor,im,keys,lineage=lineage)

    def test_missing_or_non_tensor_checkpoint_rejected(self):
        el,_,keys,_=self.checkpoint_fixture();torch,constructor,_,_=self.loader()
        torch.is_tensor=lambda v:False
        with self.assertRaisesRegex(ValueError,'non-tensor'):runner.load_checkpoint(torch,constructor,el,keys)
        (el/'0_base.lyr').unlink()
        with self.assertRaises(ValueError):runner.load_checkpoint(torch,constructor,el,keys)

    def test_checkpoint_save_is_native_cpu_staged_then_restored(self):
        model=Mock();model.cpu.return_value=model
        runner.save_checkpoint(model,self.root/'el',transfer=False,device='cuda:0')
        model.cpu.assert_called_once();model.save.assert_called_once_with(str(self.root/'el'),tl=False)
        model.to.assert_called_once_with('cuda:0')

    def test_checkpoint_save_failure_still_restores_device(self):
        model=Mock();model.cpu.return_value=model;model.save.side_effect=OSError('fixture failure')
        with self.assertRaises(OSError):runner.save_checkpoint(model,self.root/'el',transfer=True,device='cuda:0')
        model.to.assert_called_once_with('cuda:0')

    def test_inference_moves_inputs_and_model_and_returns_cpu_values(self):
        mhc=Mock();pep=Mock()
        for tensor in (mhc,pep):tensor.float.return_value=tensor;tensor.to.return_value=tensor;tensor.cpu.side_effect=AssertionError('No CPU inputs')
        batch=SimpleNamespace(mhc=mhc,pep=pep)
        class Dataset:
            df=[1,2]
            makebats=Mock()
            def __len__(self):return 1
            def __getitem__(self,index):return batch
        probabilities=Mock();probabilities.cpu.return_value.tolist.return_value=[.2,.8]
        torch=SimpleNamespace(no_grad=nullcontext,sigmoid=lambda out:probabilities)
        model=Mock(return_value=('logits',None));model.to.return_value=model;model.eval.return_value=model
        model.cpu.side_effect=AssertionError('No CPU model during CUDA inference')
        self.assertEqual(runner.predict(torch,model,Dataset(),8,'cuda:0'),[.2,.8])
        mhc.to.assert_called_with('cuda:0');pep.to.assert_called_with('cuda:0');model.to.assert_called_with('cuda:0')
        probabilities.cpu.assert_called_once()

    def test_training_moves_targets_and_features_and_preserves_loss_optimizer(self):
        tensors=[Mock() for _ in range(3)]
        for tensor in tensors:tensor.float.return_value=tensor;tensor.to.return_value=tensor;tensor.cpu.side_effect=AssertionError('No CPU training tensor')
        target,mhc,pep=tensors;target.sum.return_value=1
        target.__len__=lambda self:2
        batch=SimpleNamespace(tgt=target,mhc=mhc,pep=pep)
        class Loss:
            def backward(self):pass
            def detach(self):return .5
        loss_function=Mock(return_value=Loss());optimizer=Mock(defaults={'lr':5e-5})
        torch=Mock();torch.optim.AdamW.return_value=optimizer;torch.nn.BCEWithLogitsLoss.return_value=loss_function
        negative_target=Mock();negative_target.float.return_value=negative_target
        negative_target.to.return_value=negative_target;negative_target.sum.return_value=0
        negative_target.__len__=lambda self:3
        torch.utils.data.DataLoader.return_value=[batch,SimpleNamespace(tgt=negative_target)];torch.isfinite.return_value=True
        model=Mock(return_value=('logits',None));model.to.return_value=model;model.train.return_value=model
        model.named_parameters.return_value=[('base',1),*[(k,2) for k in runner.TRANSFER]]
        with redirect_stdout(io.StringIO()):report=runner.train_epoch(torch,model,Mock(),self.gpu,True,'cuda:0')
        self.assertEqual(report['optimization_steps'],1)
        self.assertEqual(report['updated_parameters'],list(runner.TRANSFER))
        self.assertEqual(report['optimizer_class_exposures'],{'1':1,'0':1})
        self.assertEqual(report['sampled_batch_instances'],5)
        self.assertEqual(report['sampled_class_exposures'],{'1':1,'0':4})
        self.assertEqual(report['skipped_rows'],3)
        self.assertEqual(report['all_negative_batches_skipped'],1)
        for tensor in tensors:tensor.to.assert_called_with('cuda:0')
        torch.optim.AdamW.assert_called_once_with([2]*4,lr=5e-5);loss_function.assert_called_once_with('logits',target)

    def handoff_fixture(self):
        c=deepcopy(self.gpu);entries={}
        for name,spec in c['inputs'].items():
            root=self.paths.project_data_dir if spec['area']=='data' else self.paths.project_runs_dir
            path=root/spec['relative_path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
            spec['sha256']=raw.sha256_file(path);entries[name]={**spec,'size_bytes':path.stat().st_size}
        doc={'schema_version':1,'source_commit':runner.SOURCE_COMMIT,'input_count':21,'inputs':entries,
             'total_bytes':sum(e['size_bytes'] for e in entries.values())}
        cp=self.config_file(c);mp=self.root/'transfer.json';mp.write_text(raw.json_report(doc))
        return cp,mp,doc

    def test_handoff_portable_complete_read_only_and_deterministic(self):
        cp,mp,_=self.handoff_fixture()
        before={str(p):raw.sha256_file(p) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(runner,'resolve_inputs',return_value=({},[])):
            a=worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)
            b=worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)
        self.assertEqual(raw.json_report(a),raw.json_report(b));self.assertEqual(a['input_count'],21)
        self.assertTrue(a['read_only']);self.assertEqual(a['sealed_or_corrected_payloads_opened'],[])
        self.assertFalse(self.paths.project_runs_dir.joinpath('new-run').exists())
        self.assertEqual(before,{str(p):raw.sha256_file(p) for p in self.root.rglob('*') if p.is_file()})
        self.assertTrue(all(not Path(e['relative_path']).is_absolute() for e in a['inputs']))

    def test_handoff_committed_inventory_is_exact_and_small(self):
        doc=json.loads((self.paths.repository_root/worker.TRANSFER_MANIFEST).read_text())
        self.assertEqual(doc['input_count'],21);self.assertEqual(doc['total_bytes'],207979774)
        self.assertEqual(set(doc['inputs']),runner.INPUTS)
        self.assertEqual(sum(e['size_bytes'] for e in doc['inputs'].values()),207979774)
        for name,e in doc['inputs'].items():
            self.assertEqual({k:e[k] for k in ('area','relative_path','sha256')},self.gpu['inputs'][name])
            self.assertFalse(any(word in e['relative_path'] for word in worker.FORBIDDEN))

    def test_handoff_manifest_tampering_rejected(self):
        cp,mp,doc=self.handoff_fixture()
        for key,value in (('source_commit','0'*40),('input_count',22),('total_bytes',1)):
            bad=deepcopy(doc);bad[key]=value;mp.write_text(raw.json_report(bad))
            with patch.object(runner,'resolve_inputs'),self.assertRaises(ValueError):worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)

    def test_handoff_bad_input_checksum_and_size_rejected(self):
        cp,mp,doc=self.handoff_fixture()
        for size,checksum in ((1,doc['inputs']['EL']['sha256']),(doc['inputs']['EL']['size_bytes'],'0'*64)):
            bad=deepcopy(doc);bad['inputs']['EL'].update(size_bytes=size,sha256=checksum);mp.write_text(raw.json_report(bad))
            with self.assertRaises(ValueError):worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)

    def test_handoff_changed_source_bytes_rejected(self):
        cp,mp,_=self.handoff_fixture();item=self.gpu['inputs']['source_bigmhc']
        (self.paths.project_data_dir/item['relative_path']).write_text('changed')
        with self.assertRaises(ValueError):worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)

    def test_handoff_unsafe_or_sealed_path_rejected_before_open(self):
        cp,mp,doc=self.handoff_fixture()
        for path in ('../escape','/tmp/escape','sealed/im_test.csv','datasets.zip','processed/el_train_low_only.csv'):
            bad=deepcopy(doc);bad['inputs']['EL']['relative_path']=path;mp.write_text(raw.json_report(bad))
            with self.assertRaises(ValueError):worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)

    def test_handoff_symlink_rejected(self):
        cp,mp,doc=self.handoff_fixture();e=doc['inputs']['EL'];path=self.paths.project_runs_dir/e['relative_path']
        path.unlink();target=self.root/'target';target.write_text('EL');path.symlink_to(target)
        with self.assertRaises(OSError):worker.verify_inputs(config_path=cp,manifest_path=mp,paths=self.paths)

    def test_cli_compatibility_and_read_only_dispatch(self):
        for name in ('bigmhc-smoke','bigmhc-worker','teacher','pilot-prepare'):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as e:main([name,'--help'])
            self.assertEqual(e.exception.code,0)
        with patch.object(worker,'verify_inputs',return_value={'status':'verified'}) as check,patch.object(worker,'execute') as execute,redirect_stdout(io.StringIO()):
            self.assertEqual(main(['bigmhc-worker','verify-inputs','--json']),0)
        check.assert_called_once();execute.assert_not_called()

    def test_launcher_preserves_single_bounded_worker_and_cublas_configuration(self):
        run=self.paths.project_runs_dir/'fake';(run/'logs').mkdir(parents=True);(run/'reports').mkdir()
        process=Mock(pid=123,returncode=0);process.poll.return_value=0
        psutil=SimpleNamespace(Process=lambda pid:Mock(),NoSuchProcess=ProcessLookupError)
        with patch.object(runner,'resolve_inputs',return_value=({},[])),patch.object(runner.teacher,'_run',return_value=(run,{})),\
             patch.dict('sys.modules',{'psutil':psutil}),patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'1'}),\
             patch.object(runner.subprocess,'Popen',return_value=process) as launch:
            result=runner.run(config_path=self.paths.repository_root/worker.CONFIG,out=run,paths=self.paths)
        env=launch.call_args.kwargs['env']
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'1');self.assertEqual(env['CUBLAS_WORKSPACE_CONFIG'],':4096:8')
        self.assertEqual(result['status'],'completed');launch.assert_called_once()

    def test_execute_verifies_before_creating_run(self):
        with patch.object(worker,'verify_inputs',side_effect=ValueError('missing input')),patch.object(runner.runs,'create_run') as create:
            with self.assertRaises(ValueError):worker.execute(run_id='not-created',config_path=self.paths.repository_root/runner.CONFIG,paths=self.paths)
        create.assert_not_called()

    def test_prediction_reload_tolerance_is_explicit_and_cpu_remains_exact(self):
        self.assertTrue(runner.prediction_agreement([.5],[.50000001],'cuda:0')['consistent'])
        self.assertFalse(runner.prediction_agreement([.5],[.50000001],'cuda:0')['exactly_identical'])
        with self.assertRaises(ValueError):runner.prediction_agreement([.5],[.50000001],'cpu')
        with self.assertRaises(ValueError):runner.prediction_agreement([.5],[.51],'cuda:0')
        with self.assertRaises(ValueError):runner.prediction_agreement([.5],[],'cuda:0')
        with self.assertRaises(ValueError):runner.prediction_agreement([.5],[float('nan')],'cuda:0')
