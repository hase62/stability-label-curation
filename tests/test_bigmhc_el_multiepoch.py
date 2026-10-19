"""Task 2.23 grouping, exclusion, native sampler and matched-RNG contracts."""
from copy import deepcopy
import io
from contextlib import redirect_stdout
import random
import unittest

from stability_label_curation import bigmhc_el_multiepoch as el
from stability_label_curation import bigmhc_multiepoch as im
from stability_label_curation import bigmhc_baseline_runner as runner


class SplitTests(unittest.TestCase):
    def rows(self):
        alphabet = 'ACDEFGHIKLMNPQRSTVWY'
        return [{'prepared_row_index': i+1, 'peptide': 'AAAAAAA'+alphabet[i//20]+alphabet[i%20],
                 'hla': 'HLA-A*02:01', 'original_label': str(int(i%4==0))} for i in range(300)]

    def test_exclusion_grouping_provenance_and_anchors(self):
        rows = self.rows()
        rows += [dict(rows[0], prepared_row_index=301, hla='HLA-B*07:02'),
                 dict(rows[1], prepared_row_index=302, hla='HLA-B*08:01', original_label='1'),
                 dict(rows[2], prepared_row_index=303, hla='HLA-B*15:01', original_label='0'),
                 dict(rows[3], prepared_row_index=304, peptide=' '+rows[3]['peptide'].lower()+' ', hla='HLA-B*07:02')]
        before = deepcopy(rows)
        excluded = {rows[0]['peptide']}
        train, val, removed = el.split_el(rows, excluded)
        report = el.verify_el(rows, train, val, removed, excluded)
        self.assertEqual(rows, before)
        self.assertEqual((train,val,removed), el.split_el(rows, excluded))
        self.assertEqual(report['excluded_rows'], 2)
        self.assertEqual(report['exact_peptide_overlap'], 0)
        self.assertIn(302, [r['prepared_row_index'] for r in train])
        self.assertIn(303, [r['prepared_row_index'] for r in train])
        self.assertLess(abs(len(val)/(len(rows)-2)-.1), .02)
        for part in (train,val):
            self.assertIn(sum(r['prepared_row_index'] in (4,304) for r in part),(0,2))
        with self.assertRaises(ValueError):
            el.verify_el(rows, train[:-1], val, removed, excluded)

    def test_scores_cannot_change_membership(self):
        rows = self.rows()
        a = el.split_el(rows, set())
        b = el.split_el([dict(r, prediction=random.random()) for r in rows],set())
        self.assertEqual([[r['prepared_row_index'] for r in p] for p in a],
                         [[r['prepared_row_index'] for r in p] for p in b])

    def test_candidates_ties_and_missing(self):
        curve = [{'epoch':i,'validation_AP':.5 if i in (2,6) else .3} for i in range(1,11)]
        curve[2]['validation_AP']=1.
        self.assertEqual(el.choose_epoch(curve),2)
        with self.assertRaises(ValueError): el.choose_epoch(curve[:-1])
        curve[1]['validation_AP']=float('nan')
        with self.assertRaises(ValueError): el.choose_epoch(curve)

    def test_novelty_fails_before_evaluation(self):
        rows=self.rows()
        report=el.verify_novelty(rows[:80],rows[80:90],rows[90:100],rows[100:110])
        self.assertEqual(report['EL_train_peptide_overlap'],0)
        with self.assertRaises(ValueError):
            el.verify_novelty(rows[:80],rows[80:90],rows[90:101],rows[100:110])

    def test_tie_aware_pooled_and_macro_HLA_AP(self):
        rows=[{'hla':'A','original_label':v} for v in ('1','0','1','0')]
        rows += [{'hla':'B','original_label':'0'}]
        metric=el.el_metrics(rows,[.9,.9,.8,.1,.7])
        self.assertEqual(metric['evaluable_HLAs'],1)
        self.assertAlmostEqual(metric['macro_HLA_AP'],(0.5+2/3)/2)
        self.assertAlmostEqual(metric['validation_AP'],(0.5+2/3)/2)


class NativeELTests(unittest.TestCase):
    def test_identity_wrapper_leaves_native_batches_unchanged(self):
        import pandas as pd
        import torch
        from types import SimpleNamespace
        class Native:
            def __init__(self):
                self.df=pd.DataFrame({'tgt':[1.,0.,0.], 'pep':['A','B','C']})
            def makebats(self,*args,**kwargs): self.order=[2,0,1]
            def __len__(self): return 1
            def getbat(self,index,enc): return self.df.iloc[self.order].copy()
            def __getitem__(self,index):return SimpleNamespace(tgt=torch.tensor(self.getbat(index,False).tgt.tolist()))
        native=Native()
        wrapped=el.AuditedDataset(native,[7,11,19])
        wrapped.makebats(16,shuffle=True,negfrac=.99)
        batch=wrapped[0]
        self.assertEqual(batch.tgt.tolist(),[0.,1.,0.])
        self.assertEqual(batch.source_batch_sha256,im.identity.digest([(19,0),(7,1),(11,0)]))
        with self.assertRaises(ValueError):el.AuditedDataset(Native(),[7,7,19])

    def test_original_denominator_persistent_optimizer_and_eval_rng(self):
        import numpy as np
        import torch
        from types import SimpleNamespace
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__();self.linear=torch.nn.Linear(2,1);self.dropout=torch.nn.Dropout(.2)
            def forward(self,mhc,pep): return self.linear(self.dropout(mhc)).flatten(),None
        class Dataset:
            def makebats(self,maxbat,shuffle,negfrac):
                self.negfrac=negfrac
                self.order=np.random.permutation(2)
            def __len__(self):return 2
            def __getitem__(self,i):
                k=int(self.order[i]);n=3 if k else 2
                return SimpleNamespace(mhc=torch.ones(n,2),pep=torch.zeros(n),tgt=torch.tensor([1.]+[0.]*(n-1)))
        def reset(): random.seed(42);np.random.seed(42);torch.manual_seed(42)
        reset();native=Model();extended=Model();extended.load_state_dict(native.state_dict())
        reset();ds=Dataset();opt=torch.optim.AdamW(native.parameters(),lr=5e-5)
        for _ in range(2):
            native.train();ds.makebats(16,True,.99)
            for batch in torch.utils.data.DataLoader(ds,batch_size=None,shuffle=True,num_workers=0):
                opt.zero_grad();out,_=native(batch.mhc,batch.pep)
                torch.nn.functional.binary_cross_entropy_with_logits(out,batch.tgt).backward();opt.step()
        reset();ds=Dataset();opt2=torch.optim.AdamW(extended.parameters(),lr=5e-5)
        with redirect_stdout(io.StringIO()):
            for _ in range(2):
                report=runner.train_epoch(torch,extended,ds,{'batch_size':16,'learning_rate':5e-5},False,optimizer=opt2)
                self.assertEqual(ds.negfrac,.99)
                self.assertEqual(report['optimization_steps'],2)
                state=im.identity.rng_identity(torch,np)
                with im.preserve_rng(torch,np):
                    Model();np.random.random();random.random()
                self.assertEqual(state,im.identity.rng_identity(torch,np))
        self.assertTrue(all(torch.equal(v,extended.state_dict()[k]) for k,v in native.state_dict().items()))
        self.assertEqual(im.optimizer_steps(opt2),[4,4])


if __name__=='__main__':unittest.main()
