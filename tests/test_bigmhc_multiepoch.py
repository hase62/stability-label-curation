"""Focused group integrity, selection and native optimizer continuation tests."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import random
import unittest

from stability_label_curation import bigmhc_multiepoch as multi
from stability_label_curation import bigmhc_baseline_runner as runner


class SplitTests(unittest.TestCase):
    def rows(self):
        alphabet = 'ACDEFGHIKLMNPQRSTVWY'
        return [{'prepared_row_index': i+1, 'peptide': 'AAAAAAA'+alphabet[i//20]+alphabet[i%20],
                 'hla': 'HLA-A*02:01', 'original_label': str(i%3 == 0 and 1 or 0),
                 'source_locator': {'source_row_id': str(i+1)}} for i in range(180)]

    def test_grouping_across_HLA_mixed_labels_and_provenance(self):
        rows = self.rows()
        rows.append(dict(rows[0], prepared_row_index=181, hla='HLA-B*07:02', original_label='0', source_locator={'source_row_id': '181'}))
        before = deepcopy(rows)
        train, validation = multi.grouped_split(rows)
        self.assertEqual((train, validation), multi.grouped_split(rows))
        self.assertEqual(rows, before)
        report = multi.verify_split(rows, train, validation)
        self.assertEqual(report['exact_peptide_overlap'], 0)
        self.assertEqual(report['peptide_HLA_overlap'], 0)
        self.assertLess(abs(len(validation)/len(rows)-.2), .02)
        self.assertLess(abs(report['validation']['positive_prevalence']-1/3), .03)

    def test_normalization_keeps_variants_together(self):
        rows = self.rows()
        rows.append(dict(rows[0], prepared_row_index=181, peptide=' '+rows[0]['peptide'].lower()+' '))
        train, validation = multi.grouped_split(rows)
        for part in (train, validation):
            self.assertIn(sum(r['prepared_row_index'] in (1, 181) for r in part), (0, 2))

    def test_coverage_corruption_rejected(self):
        rows = self.rows()
        train, validation = multi.grouped_split(rows)
        for bad in (train[:-1], train + [train[0]], train + [validation[0]]):
            with self.assertRaises(ValueError):
                multi.verify_split(rows, bad, validation)
        altered = deepcopy(train)
        altered[0]['original_label'] = str(1-int(altered[0]['original_label']))
        with self.assertRaises(ValueError):
            multi.verify_split(rows, altered, validation)

    def test_scores_cannot_change_split(self):
        rows = self.rows()
        original = multi.grouped_split(rows)
        altered = multi.grouped_split([dict(r, probability=random.random()) for r in rows])
        self.assertEqual([[r['prepared_row_index'] for r in p] for p in original],
                         [[r['prepared_row_index'] for r in p] for p in altered])

    def test_fixed_candidates_and_early_exact_ties(self):
        curve = [{'epoch': i, 'validation_AP': .4 if i in (2, 40) else .3} for i in range(1, 61)]
        curve[2]['validation_AP'] = .99  # Noncandidate epoch 3 cannot win.
        self.assertEqual(multi.choose_epoch(curve), 2)
        with self.assertRaises(ValueError):
            multi.choose_epoch(curve[:-1])

    def test_sequence_neighbor_report(self):
        report = multi.proximity([{'peptide': 'AAAAAAAAA'}, {'peptide': 'CCCCCCCCC'}],
                                 [{'peptide': 'AAAAAAAAC'}, {'peptide': 'DDDDDDDDD'}])
        self.assertEqual(report['minimum_distance_histogram'], {1: 1, 9: 1})
        self.assertEqual(report['validation_peptides_with_one_AA_train_neighbor'], 1)


class OptimizerTests(unittest.TestCase):
    def test_two_native_epochs_match_persistent_runner_with_validation(self):
        import numpy as np
        import torch
        from types import SimpleNamespace
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.condenser = torch.nn.Module()
                self.condenser.att = torch.nn.Linear(2, 2)
                self.condenser.out = torch.nn.Linear(2, 1)
                self.dropout = torch.nn.Dropout(.2)
            def forward(self, mhc, pep):
                return self.condenser.out(self.dropout(torch.tanh(self.condenser.att(mhc)))).flatten(), None
        class Dataset:
            def makebats(self, maxbat, shuffle, negfrac):
                self.order = np.random.permutation(3) if shuffle else range(3)
            def __len__(self): return 3
            def __getitem__(self, index):
                k = int(self.order[index])
                return SimpleNamespace(mhc=torch.tensor([[.1+k,.2], [.4,.8]]), pep=torch.zeros(2),
                                       tgt=torch.tensor([1,0] if k != 1 else [0,0]))
        def reset():
            random.seed(42); np.random.seed(42); torch.manual_seed(42)
        reset()
        initial = Model().state_dict()
        native, extended = Model(), Model()
        native.load_state_dict(initial); extended.load_state_dict(initial)
        reset()
        opt = torch.optim.AdamW(native.parameters(), lr=5e-5)
        ds = Dataset()
        loader = torch.utils.data.DataLoader(ds, batch_size=None, shuffle=True, num_workers=0, persistent_workers=False)
        for _ in range(2):
            native.train(); ds.makebats(16, shuffle=True, negfrac=None)
            for batch in loader:
                if not batch.tgt.sum(): continue
                opt.zero_grad()
                output, _ = native(batch.mhc, batch.pep)
                torch.nn.functional.binary_cross_entropy_with_logits(output, batch.tgt.float()).backward()
                opt.step()
        reset()
        opt2 = torch.optim.AdamW(extended.parameters(), lr=5e-5)
        ds2 = Dataset()
        with redirect_stdout(io.StringIO()):
            for _ in range(2):
                report = runner.train_epoch(torch, extended, ds2, {'learning_rate':5e-5,'batch_size':16}, True, optimizer=opt2)
                self.assertEqual(report['optimization_steps'], 2)
                self.assertEqual(report['all_negative_batches_skipped'], 1)
                before = multi.identity.rng_identity(torch, np)
                with multi.preserve_rng(torch, np):
                    Model(); np.random.random(); random.random()
                self.assertEqual(before, multi.identity.rng_identity(torch, np))
        self.assertTrue(all(torch.equal(native.state_dict()[k], v) for k, v in extended.state_dict().items()))
        self.assertEqual(multi.optimizer_steps(opt2), [4]*4)
        wrong = torch.optim.AdamW(reversed(list(extended.parameters())), lr=5e-5)
        with self.assertRaises(ValueError):
            runner.train_epoch(torch, extended, ds2, {'learning_rate':5e-5,'batch_size':16}, True, optimizer=wrong)


if __name__ == '__main__':
    unittest.main()
