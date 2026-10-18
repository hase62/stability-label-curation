"""Synthetic source coordinates and tiny CPU loss/batch checks; no real training."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import importlib.util
import csv
import io
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability_label_curation import el_stability_loss_adapter as w
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths

HLA = 'HLA-A*02:01'
ARCHIVE = 'a' * 64


def positive(index, score=None, hla=HLA):
    peptide = 'AAAAAAAAA'
    return w.PositiveScore(str(index), str(index), w.design.prior.pilot.row_id(ARCHIVE, 'el_train.csv', index),
        w.design.prior.adapter.source_hash(['mhc','pep','tgt'], [hla,peptide,'1']), hla,hla,peptide,'1',
        str(index) if score is None else score)


def manifest(rows):
    counts = dict(sorted(Counter(r.resolved_hla for r in rows).items()))
    return {'schema_version':1,'version':w.VERSION,'protocol_version':w.design.VERSION,'fields':list(w.FIELDS),
        'rows':len(rows),'HLA_groups':len(counts),'positive_counts_by_HLA':counts,'supported_HLA':list(counts),
        'archive_sha256':ARCHIVE,'source_member':'el_train.csv','original_label':'1',
        'score_unit':'hours','score_scale':'untransformed_kinetic_half_life_hours'}


def ledger(total=272, positives=16, member='el_train.csv'):
    for index in range(1,total+1):
        label = '1' if index <= positives else '0'
        header=['mhc','pep','tgt']+(['rand'] if member=='im_train.csv' else [])
        fields=[HLA,'AAAAAAAAA',label]+(['0'] if member=='im_train.csv' else [])
        yield {'derived_row_index':str(index),'row_index':str(index),'source_line_number':str(index+1),
            'source_file':member,'source_row_id':w.design.prior.pilot.row_id(ARCHIVE,member,index),
            'source_row_sha256':w.design.prior.adapter.source_hash(header,fields),
            'original_hla':HLA,'resolved_hla':HLA,'original_peptide':'AAAAAAAAA','original_label':label}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.rows = [positive(i) for i in range(1,17)]
        self.manifest = manifest(self.rows)
        self.net = patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network'))
        self.net.start();self.addCleanup(self.net.stop)

    def test_mode_a_all_one(self):
        a=w.LossAdapter(self.rows,self.manifest,'A')
        self.assertEqual(set(a.weights.values()),{1.0})

    def test_protocol_b_and_p_exact_multiset_and_mean(self):
        b=w.LossAdapter(self.rows,self.manifest,'B'); p=w.LossAdapter(self.rows,self.manifest,'P')
        self.assertEqual(sorted(b.rational.values()),sorted(p.rational.values()))
        self.assertEqual(sum(b.rational.values()),16)
        self.assertEqual(sorted(b.weights.values()),sorted(p.weights.values()))
        self.assertLessEqual(abs(sum(b.weights.values())-16),16e-6)

    def test_ties_midrank(self):
        rows=[positive(1,'0'),positive(2,'0.0'),positive(3,'1'),positive(4,'1.00')]
        adapter=w.LossAdapter(rows,manifest(rows),'B')
        self.assertEqual(list(adapter.rational.values()),[Fraction(7,8)]*2+[Fraction(9,8)]*2)

    def test_singleton_and_two_positive_groups_not_excluded(self):
        for n in (1,2):
            rows=self.rows[:n]; adapter=w.LossAdapter(rows,manifest(rows),'B')
            self.assertEqual(len(adapter.weights),n)
            self.assertTrue(adapter.evidence['by_HLA'][HLA]['small_positive_group_below10'])
            self.assertEqual(sum(adapter.rational.values()),n)

    def test_all_tied_weights_are_unit(self):
        rows=[replace(r,predicted_half_life_hours='0') for r in self.rows]
        self.assertEqual(set(w.LossAdapter(rows,manifest(rows),'B').weights.values()),{1.0})

    def test_invalid_and_nonfinite_scores_fail_even_a(self):
        for score in ('NaN','Infinity','-1',''):
            rows=[positive(1,score)]
            with self.assertRaises(ValueError):w.LossAdapter(rows,manifest(rows),'A')

    def test_unsupported_hla_and_c67s_fail(self):
        for hla in ('HLA-A*99:99',HLA+'(C67S)'):
            rows=[replace(self.rows[0],resolved_hla=hla)]
            with self.assertRaises(ValueError):w.LossAdapter(rows,self.manifest,'B')

    def test_duplicate_and_missing_scores_fail(self):
        for rows in (self.rows[:-1],self.rows+[self.rows[-1]]):
            with self.assertRaises(ValueError):w.LossAdapter(rows,self.manifest,'A')

    def test_pair_identity_cannot_replace_row_identity(self):
        # All synthetic rows deliberately share peptide/HLA; each still has a unique source ID.
        a=w.LossAdapter(self.rows,self.manifest,'B')
        self.assertEqual(len(a.weights),16)
        with self.assertRaises(ValueError):a.validate_positive(self.rows[0].source_row_id,HLA,'AAAAAAAAA',2)

    def test_raw_source_hash_and_index_preserved(self):
        for row in (replace(self.rows[0],source_row_sha256='0'*64), replace(self.rows[0],source_row_index='99')):
            with self.assertRaises(ValueError):w.LossAdapter([row],manifest([row]),'B')

    def test_generation_does_not_change_global_rng_or_labels(self):
        state=random.getstate();before=deepcopy(self.rows)
        a=w.LossAdapter(self.rows,self.manifest,'P')
        self.assertEqual(state,random.getstate());self.assertEqual(self.rows,before)
        self.assertEqual(a.evidence,w.LossAdapter(self.rows,self.manifest,'P').evidence)

    def test_original_row_order_guard(self):
        with self.assertRaises(ValueError):w.LossAdapter(self.rows[::-1],self.manifest,'B')

    def write_fixture(self,root):
        path=root/'scores.csv.gz'
        with w.design.prior.adapter.artifact_csv(path,list(w.FIELDS),True) as (writer,sink):
            for row in self.rows:writer.writerow(asdict(row))
        doc={**self.manifest,'artifact':{'sha256':sink.digest.hexdigest(),'size_bytes':sink.size}}
        mp=root/'manifest.json';mp.write_text(w.raw.json_report(doc))
        return path,mp

    def test_sidecar_hash_readonly_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();path,mp=self.write_fixture(root)
            before={p.name:w.raw.sha256_file(p) for p in root.iterdir()}
            loaded=w.load_sidecar(path,mp,canonical=False)
            self.assertEqual(len(loaded.scores),16)
            self.assertEqual(before,{p.name:w.raw.sha256_file(p) for p in root.iterdir()})

    def test_canonical_count_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,mp=self.write_fixture(Path(tmp).resolve())
            with self.assertRaisesRegex(ValueError,'canonical population'):w.load_sidecar(path,mp)

    def test_tampered_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,mp=self.write_fixture(Path(tmp).resolve())
            with path.open('ab') as out:out.write(b'bad')
            with self.assertRaisesRegex(ValueError,'SHA256'):w.load_sidecar(path,mp,canonical=False)

    def test_wrong_units_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,mp=self.write_fixture(Path(tmp).resolve())
            doc=json.loads(mp.read_text());doc['score_unit']='degC';mp.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):w.load_sidecar(path,mp,canonical=False)

    def test_immutable_atomic_sidecar_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();path,mp=self.write_fixture(root);before=path.read_bytes()
            with self.assertRaises(FileExistsError):self.write_fixture(root)
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(any(p.name.endswith('.partial') for p in root.iterdir()))

    def test_runtime_a_b_p_schema_and_execution_block(self):
        c=runner.load_config(w.CONFIG)
        for mode in ('A','B','P'):
            spec=deepcopy(c['loss_adapter']);spec['mode']=mode
            if mode!='A':spec['matched_reference']={'area':'runs','relative_path':'future-A/reports/matched_state.json','sha256':None}
            w.validate_runtime_spec(spec,mode)
            with self.assertRaises(ValueError):w.require_training_authorization({'loss_adapter':spec})

    def test_unpinned_reference_and_protocol_changes_rejected(self):
        spec=runner.load_config(w.CONFIG)['loss_adapter']
        for key,value in [('strength','0.6'),('mode','B'),('protocol_version','unknown')]:
            altered={**spec,key:value}
            with self.assertRaises(ValueError):w.validate_runtime_spec(altered,'A')
        b={**spec,'mode':'B','training_authorized':True,
           'matched_reference':{'area':'runs','relative_path':'future-A/reports/matched_state.json','sha256':None}}
        with self.assertRaises(ValueError):w.validate_runtime_spec(b,'B')

    def test_no_adapter_legacy_runtime_unchanged(self):
        c=runner.load_config(runner.CONFIG);self.assertNotIn('loss_adapter',c)
        w.require_training_authorization(c)

    def test_engineering_config_cannot_start_worker_or_training(self):
        with (patch.object(runner,'resolve_inputs',side_effect=AssertionError('No data reads')),
              patch('subprocess.Popen',side_effect=AssertionError('No worker'))):
            with self.assertRaisesRegex(ValueError,'not authorized'):runner.run(config_path=w.CONFIG,out='unused')
            with self.assertRaisesRegex(ValueError,'not authorized'):runner.worker(config_path=w.CONFIG,out='unused')

    def test_matched_state_mismatches_fail(self):
        reference={'initial_tensor_sha256':{'x':'a'},'rng_before_EL':{'cpu':'a'}}
        with self.assertRaises(ValueError):w.check_reference(reference,initial={'x':'b'})
        with self.assertRaises(ValueError):w.check_reference(reference,rng={'cpu':'b'},stage='EL')
        w.check_reference(reference,initial={'x':'a'},rng={'cpu':'a'},stage='EL')

    def test_im_weighting_rejected_before_forward(self):
        with self.assertRaises(ValueError):runner.train_epoch(None,None,None,{},True,loss_adapter=object())

    def test_permutation_python_pin(self):
        m={**self.manifest,'permutation_python':'0.0.0'}
        with self.assertRaisesRegex(ValueError,'pinned Python'):w.LossAdapter(self.rows,m,'P')

    def test_portable_configuration_has_no_home_paths(self):
        c=runner.load_config(w.CONFIG)
        for spec in c['inputs'].values():
            self.assertFalse(Path(spec['relative_path']).is_absolute())
            self.assertNotIn('..',Path(spec['relative_path']).parts)
        self.assertEqual(set(c['inputs'])-runner.INPUTS,{'positive_scores','positive_score_manifest'})

    def test_matched_optimizer_or_skip_changes_rejected(self):
        original={'optimization_steps':1,'sampled_batch_sha256':['a'],'optimizer_defaults':{'lr':5e-5},
                  'updated_parameters':['x'],'optimizer_skip_mask':[False]}
        for key,value in [('optimization_steps',2),('optimizer_skip_mask',[True]),('sampled_batch_sha256',['b'])]:
            with self.assertRaises(ValueError):w.check_reference({'EL':original},stage='EL',training={**original,key:value})


HAS_RUNTIME=all(importlib.util.find_spec(m) for m in ('torch','numpy','pandas'))


@unittest.skipUnless(HAS_RUNTIME,'Existing CPU BigMHC runtime needed for synthetic tensor tests')
class TensorAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch, numpy, pandas
        cls.torch,cls.np,cls.pd=torch,numpy,pandas
        torch.set_num_threads(1)

    def setUp(self):
        self.rows=[positive(i) for i in range(1,17)]

    def native(self):
        torch,pd=self.torch,self.pd
        class Native:
            def __init__(self):
                self.df=pd.DataFrame({'mhc':[HLA]*272,'pep':['AAAAAAAAA']*272,'tgt':[1.0]*16+[0.0]*256,'len':[9]*272})
            def makebats(self,maxbat,shuffle=False,negfrac=None):
                if shuffle:self.df=self.df.sample(frac=1)
                self.df.reset_index(inplace=True,drop=True)
                pos=list(self.df.index[self.df.tgt==1]);neg=list(self.df.index[self.df.tgt==0])
                self.batches=[[p]+neg[j*16:(j+1)*16] for j,p in enumerate(pos)]
            def __len__(self):return len(self.batches)
            def getbat(self,index,enc=False):return self.df.iloc[self.batches[index]].copy()
            def __getitem__(self,index):
                frame=self.getbat(index)
                return SimpleNamespace(tgt=torch.tensor(frame.tgt.values),mhc=torch.ones((len(frame),2)),pep=torch.ones((len(frame),2)))
        return Native()

    def wrapped(self,mode='A'):
        a=w.LossAdapter(self.rows,manifest(self.rows),mode)
        return w.IdentityDataset(self.native(),ledger(),stage='EL',adapter=a)

    def test_noop_loss_gradients_and_adamw_update(self):
        torch=self.torch;torch.manual_seed(42)
        model=torch.nn.Linear(3,1);state=deepcopy(model.state_dict());x=torch.randn((17,3));t=torch.tensor([1.]+[0.]*16)
        saved=torch.get_rng_state().clone();results=[]
        for adapted in (False,True):
            model.load_state_dict(state);model.zero_grad(set_to_none=True);opt=torch.optim.AdamW(model.parameters(),lr=5e-5)
            out=model(x).squeeze(-1)
            loss=w.weighted_bce(torch,out,t,[1.]*17) if adapted else torch.nn.BCEWithLogitsLoss()(out,t)
            loss.backward();grad=[p.grad.clone() for p in model.parameters()];opt.step()
            results.append((loss.detach(),grad,deepcopy(model.state_dict())))
        self.assertTrue(torch.equal(saved,torch.get_rng_state()))
        self.assertTrue(torch.equal(results[0][0],results[1][0]))
        for a,b in zip(results[0][1],results[1][1]):torch.testing.assert_close(a,b,rtol=1e-6,atol=1e-7)
        for k in state:torch.testing.assert_close(results[0][2][k],results[1][2][k],rtol=1e-6,atol=1e-7)

    def test_denominator_is_17_not_sum_weights(self):
        torch=self.torch;x=torch.zeros(17,requires_grad=True);t=torch.tensor([1.]+[0.]*16);weights=[.875]+[1.]*16
        loss=w.weighted_bce(torch,x,t,weights)
        expected=torch.nn.functional.binary_cross_entropy_with_logits(x,t,reduction='none')*torch.tensor(weights)
        self.assertEqual(loss.item(),expected.mean().item())
        self.assertNotAlmostEqual(loss.item(),(expected.sum()/sum(weights)).item())
        loss.backward();self.assertAlmostEqual(x.grad[1].item(),.5/17,places=7)

    def test_weight_permutation_and_loss_no_rng_consumption(self):
        torch,np=self.torch,self.np;torch.manual_seed(42);np.random.seed(42);random.seed(42)
        before=w.rng_identity(torch,np);wrapper=self.wrapped('P')
        x=torch.zeros(17,requires_grad=True);t=torch.tensor([1.]+[0.]*16)
        w.weighted_bce(torch,x,t,[1.]*17).backward()
        self.assertEqual(before,w.rng_identity(torch,np))
        self.assertEqual(len(wrapper.adapter.weights),16)

    def test_native_17_layout_source_ids_and_collation(self):
        torch,np=self.torch,self.np
        schedules=[]
        for mode in ('A','B','P'):
            np.random.seed(42);torch.manual_seed(42);wrapped=self.wrapped(mode)
            wrapped.makebats(16,shuffle=True,negfrac=.99)
            batches=list(torch.utils.data.DataLoader(wrapped,batch_size=None,shuffle=True,num_workers=0))
            self.assertEqual(len(batches),16)
            self.assertTrue(all(len(b.tgt)==17 and b.tgt.sum()==1 for b in batches))
            self.assertTrue(all(b.EL_loss_weights[j]==1 for b in batches for j,label in enumerate(b.source_labels) if label==0))
            schedules.append([b.source_batch_sha256 for b in batches])
        self.assertEqual(schedules[0],schedules[1]);self.assertEqual(schedules[0],schedules[2])

    def test_wrapper_same_sampler_rng_and_tensors_as_legacy(self):
        torch,np=self.torch,self.np
        native=self.native();wrapped=self.wrapped('A')
        np.random.seed(42);native.makebats(16,shuffle=True,negfrac=.99);after=np.random.get_state()
        np.random.seed(42);wrapped.makebats(16,shuffle=True,negfrac=.99)
        self.assertEqual(after[0],np.random.get_state()[0]);self.assertTrue(np.array_equal(after[1],np.random.get_state()[1]))
        for i in range(16):
            a,b=native[i],wrapped[i]
            self.assertTrue(torch.equal(a.tgt,b.tgt));self.assertTrue(torch.equal(a.mhc,b.mhc));self.assertTrue(torch.equal(a.pep,b.pep))

    def test_mutated_or_misordered_source_values_fail(self):
        wrapper=self.wrapped('B');wrapper.makebats(16)
        wrapper.df.loc[0,'pep']='CAAAAAAAA'
        with self.assertRaises(ValueError):wrapper[0]

    def test_missing_native_positive_score_fails(self):
        rows=self.rows[:-1];a=w.LossAdapter(rows,manifest(rows),'A')
        with self.assertRaises(ValueError):w.IdentityDataset(self.native(),ledger(),stage='EL',adapter=a)

    def test_wrong_ledger_labels_fail(self):
        records=list(ledger());records[0]['original_label']='0'
        with self.assertRaises(ValueError):w.IdentityDataset(self.native(),records,stage='EL',adapter=w.LossAdapter(self.rows,manifest(self.rows),'A'))

    def test_im_identity_ledger_never_adds_weights(self):
        wrapper=w.IdentityDataset(self.native(),ledger(member='im_train.csv'),stage='IM',archive_sha256=ARCHIVE)
        wrapper.makebats(16)
        self.assertFalse(hasattr(wrapper[0],'EL_loss_weights'))

    def test_authentic_quoted_four_column_IM_fixture(self):
        # Hash parsed original strings, not CSV bytes or numerically coerced values.
        source='"mhc","pep","tgt","rand"\r\n"HLA-A*02:01","AAAAAAAAA","1","0"\r\n'
        header, fields = list(csv.reader(io.StringIO(source, newline=''), strict=True))
        self.assertEqual(json.dumps([header,fields],ensure_ascii=False,separators=(',',':')),
            '[["mhc","pep","tgt","rand"],["HLA-A*02:01","AAAAAAAAA","1","0"]]')
        records=list(ledger(member='im_train.csv'))
        records[0]['source_row_sha256']=w.design.prior.adapter.source_hash(header,fields)
        self.assertNotEqual(records[0]['source_row_sha256'],w.design.prior.adapter.source_hash(header[:3],fields[:3]))
        w.IdentityDataset(self.native(),records,stage='IM',archive_sha256=ARCHIVE)
        self.assertEqual({r['original_rand'] for r in records},{'0'})

    def test_IM_missing_modified_duplicate_and_formatting_rejected(self):
        records=list(ledger(member='im_train.csv'))
        cases=[records[:-1],records+[records[-1]],records[:1]+records,
               [dict(records[0],original_rand='1')]+records[1:],
               [dict(records[0],original_rand='0.0')]+records[1:],
               [dict(records[0],original_label='0')]+records[1:],
               [dict(records[0],source_row_sha256='0'*64)]+records[1:],
               [dict(records[0],prepared_row_index='99')]+records[1:],
               [dict(records[0],retained='0')]+records[1:],
               [dict(records[0],source_line_number='99')]+records[1:]]
        for case in cases:
            with self.subTest(first=case[0]),self.assertRaises(ValueError):
                w.IdentityDataset(self.native(),case,stage='IM',archive_sha256=ARCHIVE)

    def test_IM_literal_rand_recovered_only_by_complete_hash(self):
        for flag in ('0','1'):
            record=next(ledger(member='im_train.csv'))
            record['source_row_sha256']=w.design.prior.adapter.source_hash(
                ['mhc','pep','tgt','rand'],[HLA,'AAAAAAAAA','1',flag])
            header,fields=w.original_fields(record,'IM')
            self.assertEqual(fields[-1],flag)
            self.assertEqual(record['original_rand'],flag)
        record['source_row_sha256']=w.design.prior.adapter.source_hash(
            ['mhc','pep','tgt','rand'],[HLA,'AAAAAAAAA','1','0.0'])
        with self.assertRaises(ValueError):w.original_fields(record,'IM')

    def test_wrong_loss_shapes_or_negative_weight_fail(self):
        torch=self.torch
        for weights in ([1.], [1.,.9], [0.,1.], [float('nan'),1.]):
            with self.assertRaises(ValueError):w.weighted_bce(torch,torch.zeros(2),torch.tensor([1.,0.]),weights)

    def test_schedule_mismatch_rejected_before_forward_or_update(self):
        torch=self.torch
        class NeverForward(torch.nn.Module):
            def __init__(self):super().__init__();self.scalar=torch.nn.Parameter(torch.zeros(1))
            def forward(self,**kwargs):raise AssertionError('No forward allowed')
        model=NeverForward();wrapper=self.wrapped('A')
        with self.assertRaisesRegex(ValueError,'before optimizer update'):
            runner.train_epoch(torch,model,wrapper,{'learning_rate':5e-5,'batch_size':16},False,
                               loss_adapter=wrapper.adapter,expected_batches=['wrong']*16)
        self.assertIsNone(model.scalar.grad);self.assertEqual(model.scalar.item(),0)


if __name__=='__main__':unittest.main()
