"""Focused Task2.37 engineering checks; no real study optimization or IM metrics."""
import ast
from collections import Counter
from copy import deepcopy
import gzip
import inspect
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

import numpy as np
import torch

from stability_label_curation import measured_tm_direct_transfer as study
from stability_label_curation import measured_tm_direct_transfer_evaluation as evaluation
from stability_label_curation.paths import resolve_paths
from stability_label_curation.third_party_evaluation import WeightedRanking


def source_examples():
    return [{'source_id':str(i),'kind':'measured' if i<6 else 'decoy','target':(.6+i*.01) if i<6 else 0.,
             'target_decimal':str(.6+i*.01) if i<6 else '0'} for i in range(12)]


def statistic_examples():
    return [{'source_id':str(i),'peptide':'SEQUENCE'+str(i),'hla':'HLA-A*02:01','study_DOI':'','patient':'',
             'label':label,'scores':{c:score for c in study.CONDITIONS},'component':str(i//2)}
            for i,(score,label) in enumerate([(.8,1),(.8,0),(.3,1),(.1,0)])]


class Toy(torch.nn.Module):
    """Synthetic numerical fixture, not a scientific model variant."""
    def __init__(self):
        super().__init__();self.backbone=torch.nn.Sequential(torch.nn.Linear(2,414),torch.nn.BatchNorm1d(414),torch.nn.Dropout(.7))
        self.condenser=torch.nn.Module();self.condenser.out=torch.nn.Linear(414,1)
    def forward(self,x):return self.condenser.out(self.backbone(x)).squeeze(1)


class TargetAndLossTests(unittest.TestCase):
    def test_exact_seed_specific_multiset_and_no_negative_changes(self):
        rows=source_examples();before=deepcopy(rows);perms=[]
        for seed in study.SEEDS:
            targets,receipt=study.target_vectors(rows,seed);perms.append(receipt['assignments'])
            self.assertEqual(Counter(targets['T'][:6]),Counter(targets['P'][:6]))
            self.assertTrue(torch.equal(torch.sort(torch.tensor(targets['T'][:6])).values,torch.sort(torch.tensor(targets['P'][:6])).values))
            self.assertEqual(targets['D'][:6],[1.]*6)
            self.assertTrue(all(v[6:]==[0.]*6 for v in targets.values()))
        self.assertEqual(rows,before);self.assertEqual(len({json.dumps(x) for x in perms}),3)

    def test_independent_order_stream_exactly_once_per_pass_and_matched_arms(self):
        before=random.getstate();schedule=study.orders(12070,123)
        study.target_vectors(source_examples(),123)
        self.assertEqual(schedule,study.orders(12070,123));self.assertEqual(random.getstate(),before)
        self.assertTrue(all(sorted(order)==list(range(12070)) for order in schedule))
        self.assertTrue(all(len(order)//64+1==189 and len(order)%64==38 for order in schedule))
        self.assertNotEqual(schedule,study.orders(12070,456))

    def test_balanced_loss_sum_of_weights_and_exact_gradient(self):
        z=torch.tensor([2.,-1.,.7],dtype=torch.float64,requires_grad=True)
        y=torch.tensor([.6,0.,1.],dtype=torch.float64);weights=torch.tensor([16.,1.,16.],dtype=torch.float64)
        actual=study.balanced_loss(torch,z,y,weights)
        expected=sum(w*(max(v,0)-v*t+math.log1p(math.exp(-abs(v)))) for w,v,t in zip(weights.tolist(),z.tolist(),y.tolist()))/33
        self.assertAlmostEqual(float(actual.detach()),expected,places=12);actual.backward()
        self.assertTrue(torch.allclose(z.grad,weights*(torch.sigmoid(z.detach())-y)/33,rtol=0,atol=1e-14))
        self.assertNotAlmostEqual(float(actual.detach()),expected*33/3)

    def test_training_class_balance_by_source_kind_not_soft_target(self):
        cfg=study.config(resolve_paths());self.assertEqual(cfg['measured']*cfg['measured_weight'],cfg['decoys']*cfg['decoy_weight'])
        self.assertEqual(cfg['loss_denominator'],'sum_sample_weights');self.assertEqual(cfg['seeds'],[123,456,789])

    def test_score_orientation_sigmoid_is_higher_positive(self):
        scores=torch.sigmoid(torch.tensor([-3.,0.,3.]))
        self.assertTrue(bool(torch.all(scores[1:]>scores[:-1])))
        self.assertIn('scores=torch.sigmoid(z)',inspect.getsource(study.inference))


class FreezingAndIdentityTests(unittest.TestCase):
    def test_synthetic_output_only_gradients_parameters_and_BN_dropout_frozen(self):
        model=Toy();before=study.runner.state_hashes(model);freeze=study.freeze_output_only(model)
        self.assertEqual(freeze['trainable_scalar_count'],415)
        optimizer=torch.optim.AdamW([v for v in model.parameters() if v.requires_grad],lr=.001,weight_decay=.01)
        x=torch.tensor([[1.,2.],[2.,1.]]);loss=study.balanced_loss(torch,model(x),torch.tensor([.7,0.]),torch.tensor([16.,1.]))
        loss.backward();self.assertEqual({k for k,p in model.named_parameters() if p.grad is not None},set(study.OUTPUT_KEYS))
        optimizer.step();after=study.runner.state_hashes(model)
        self.assertEqual({k for k in before if before[k]!=after[k]},set(study.OUTPUT_KEYS))
        self.assertFalse(any(m.training for m in model.modules()))

    def test_two_tensor_checkpoint_strict_parent_reconstruction_and_integrity(self):
        model=Toy();state={k:v.detach().clone() for k,v in model.state_dict().items()}
        head={k:state[k]+.1 for k in study.OUTPUT_KEYS}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'output.pt';study.save_tensors(torch,path,head);expected=study.sha(path)
            study.assert_sha(path,expected);study.replace_output(torch,model,torch.load(path,weights_only=True))
            for k,v in model.state_dict().items():self.assertTrue(torch.equal(v,head[k] if k in head else state[k]))
            with self.assertRaises(ValueError):study.replace_output(torch,model,{'other':torch.tensor(1.)})
            with path.open('ab') as f:f.write(b'tampered')
            with self.assertRaises(ValueError):study.assert_sha(path,expected)

    def test_authentic_A_EL10_file_identity_no_model_loading(self):
        p=resolve_paths();cfg=study.config(p);model,files,keys=study.baseline(p,cfg)
        self.assertEqual(len(keys),36);self.assertTrue(model['directory'].endswith('/checkpoints/EL_epoch_10'))
        self.assertEqual(study.digest(model['files']),cfg['baseline_file_map_sha256'])
        self.assertEqual(set(files),set(cfg['inputs']))

    def test_identity_alignment_rejects_source_swap(self):
        rows=[{'source_id':'a','hla':'HLA-A*02:01','peptide':'AAAAAAAAA'},
              {'source_id':'b','hla':'HLA-A*02:01','peptide':'VVVVVVVVV'}]
        predictions=[{**r,'raw_EL_logit':0.,'EL_probability':.5} for r in rows]
        study.native.join_predictions(rows,predictions)
        with self.assertRaises(ValueError):study.native.join_predictions(rows,list(reversed(predictions)))

    def test_IM_outcomes_absent_from_training_and_no_selection_routines(self):
        source=inspect.getsource(study.train)
        self.assertNotIn('outcomes',source);self.assertNotIn('evaluation',source);self.assertNotIn('IM_train',source)
        self.assertNotIn('early_stop',source);self.assertNotIn('WeightedRanking',source)
        self.assertNotIn('scores',inspect.getsource(study.target_vectors))
        self.assertIn('range',inspect.getsource(study.orders))
        self.assertEqual(study.config(resolve_paths())['passes'],20)
        self.assertIn('torch.optim.AdamW',source)


class MetricAndResamplingTests(unittest.TestCase):
    def test_tied_AP_and_AUROC_hand_example(self):
        rows=statistic_examples();result=WeightedRanking(rows,'A').metrics(np.ones(4,dtype=np.int64),top_k=True)
        self.assertAlmostEqual(result['AP'],7/12);self.assertEqual(result['AUROC'],5/8);self.assertIsNone(result['precision_at_10'])

    def test_seed_mean_of_paired_differences_and_no_reduced_seed_average(self):
        values={'A':{'AP':.2}}
        for seed,p,t in zip(study.SEEDS,[.1,.9,.4],[.3,.5,.6]):
            values[f'P_{seed}']={'AP':p};values[f'T_{seed}']={'AP':t};values[f'D_{seed}']={'AP':.3}
        result=evaluation.summaries(values)
        self.assertAlmostEqual(result['seed_mean_paired_contrasts']['T-P']['AP'],0)
        self.assertAlmostEqual(result['seed_means']['T']['AP'],sum([.3,.5,.6])/3)
        values['T_123']['AP']=None
        self.assertIsNone(evaluation.summaries(values)['seed_mean_paired_contrasts']['T-P']['AP'])

    def test_paired_component_draws_evidence_and_determinism(self):
        rows=statistic_examples();rankings={c:WeightedRanking(rows,c) for c in study.CONDITIONS};before=random.getstate()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'draws.gz';actual=evaluation.bootstrap(rows,rankings,'component',237001,50,path)
            with gzip.open(path,'rt') as stream:draws=[json.loads(line) for line in stream]
            self.assertEqual(len(draws),50);self.assertTrue(all(sum(r['component_multiplicities'])==2 for r in draws))
            self.assertTrue(all(r['seed_mean_paired_contrasts']['T-P']['AP']==0 for r in draws))
        self.assertEqual(before,random.getstate());self.assertEqual(actual,evaluation.bootstrap(rows,rankings,'component',237001,50))
        self.assertTrue(actual['unreliable']);self.assertEqual(actual['confidence_intervals']['T-P']['AP']['lower_95'],0)

    def test_classless_invalid_replicates_and_one_component_undefined(self):
        rows=statistic_examples()
        for row in rows:row['label']=0
        rankings={c:WeightedRanking(rows,c) for c in study.CONDITIONS}
        result=evaluation.bootstrap(rows,rankings,'component',237001,20)
        self.assertEqual(result['confidence_intervals']['T-P']['AP']['invalid_draws'],20)
        self.assertIsNone(result['confidence_intervals']['T-P']['AP']['lower_95'])
        for row in rows:row['component']='one'
        self.assertEqual(evaluation.bootstrap(rows,rankings,'component',237001,20)['draws_executed'],0)

    def test_integer_cluster_multiplicity_matches_expanded_AP(self):
        rows=statistic_examples();weights=np.array([3,2,1,4]);actual=WeightedRanking(rows,'A').metrics(weights,top_k=True)
        expanded=[r for r,n in zip(rows,weights) for _ in range(n)]
        expected=WeightedRanking(expanded,'A').metrics(np.ones(len(expanded),dtype=np.int64),top_k=True)
        self.assertEqual(actual,expected)

    def test_stable_exclusive_serialization(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'receipt.json';value={'n':None,'full_precision':.12345678901234567}
            study.write_json(path,value);self.assertEqual(json.loads(path.read_text()),value)
            with self.assertRaises(FileExistsError):study.write_json(path,value)


if __name__=='__main__':unittest.main()
