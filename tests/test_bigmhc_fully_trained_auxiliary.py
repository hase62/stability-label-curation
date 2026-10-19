"""Focused partition-only targets and authentic persistent multi-epoch contracts."""
from copy import deepcopy
from fractions import Fraction
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

import test_bigmhc_stability_auxiliary as legacy
from stability_label_curation import bigmhc_fully_trained_auxiliary as experiment
from stability_label_curation import bigmhc_stability_auxiliary as auxiliary
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import bigmhc_el_multiepoch as baseline
from stability_label_curation import bigmhc_multiepoch as shared
from stability_label_curation import el_stability_loss_adapter as binding
from stability_label_curation.paths import resolve_paths


class PartitionTests(unittest.TestCase):
    def test_training_only_rank_reference_and_permutation(self):
        sidecar = legacy.scores_fixture()
        ids = set(list(sidecar.scores)[:3])
        boundary = binding.rng_identity(torch, np)
        s, p = (auxiliary.Targets(sidecar, m, source_ids=ids) for m in ('S', 'P'))
        self.assertEqual(list(s.exact.values()), [Fraction(1, 3), Fraction(1, 3), Fraction(5, 6)])
        self.assertEqual(s.evidence['rank_reference_population'], 'EL_training_positives_only')
        self.assertEqual(s.evidence['positive_observations'], 3)
        self.assertTrue(auxiliary.compare_targets(s, p)['per_HLA_exact_and_FP32_multisets_equal'])
        self.assertEqual(boundary, binding.rng_identity(torch, np))
        self.assertEqual(p.exact, auxiliary.Targets(sidecar, 'P', source_ids=ids).exact)
        for bad in (set(), {'unknown'}):
            with self.assertRaises(ValueError):
                auxiliary.Targets(sidecar, 'S', source_ids=bad)
        with self.assertRaises(ValueError):
            s.anchor([list(sidecar.scores)[-1]], [1])

    def test_configuration_fails_on_scientific_change_or_evaluation_input(self):
        paths = resolve_paths()
        original = experiment.read_config(paths)
        mutations = [lambda c: c.update(EL_epochs=11), lambda c: c.update(IM_epochs=19),
                     lambda c: c.update(evaluation_authorized=True),
                     lambda c: c.update(rank_reference='full_positive_cohort'),
                     lambda c: c['auxiliary'].update(lambda_aux=.2),
                     lambda c: c['inputs'].update(development={})]
        for mutate in mutations:
            c = deepcopy(original)
            mutate(c)
            with patch.object(experiment.json, 'loads', return_value=c), self.assertRaises(ValueError):
                experiment.read_config(paths)


class MultiepochTests(unittest.TestCase):
    setUpClass = classmethod(legacy.AuthenticTests.setUpClass.__func__)
    seed = legacy.AuthenticTests.seed
    model = legacy.AuthenticTests.model

    def test_ten_EL_twenty_IM_persistence_sampling_RNG_and_transfer(self):
        sidecar = legacy.scores_fixture()
        c = {'batch_size': 16, 'learning_rate': 5e-5}
        with runner.pinned_modules(self.files) as (BigMHC, Dataset), tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory/'reports').mkdir()
            fixture = legacy.native_fixture(Dataset, sidecar)
            rows = [dict(prepared_row_index=i, source_row_id=identity, hla=str(h), peptide=str(p), original_label=str(int(y)))
                    for i, (identity, h, p, y) in enumerate(fixture.native.df[[binding.IDENTITY, 'mhc', 'pep', 'tgt']].itertuples(index=False, name=None), 1)]
            encodings = fixture.native.mhcenc
            self.seed()
            model = self.model(BigMHC)
            native = baseline.AuditedDataset(experiment.native_dataset(Dataset, encodings, rows), list(range(1, len(rows)+1)))
            optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
            expected = []
            with patch('sys.stdout', new=io.StringIO()):
                for epoch in range(1, 11):
                    before = binding.rng_identity(torch, np)
                    r = runner.train_epoch(torch, model, native, c, False, self.device, optimizer=optimizer)
                    r.update(RNG_before=before, RNG_after=binding.rng_identity(torch, np))
                    expected.append(r)
                    self.assertEqual(shared.optimizer_steps(optimizer), [7*epoch]*36)
                    (directory/f'reports/EL_epoch_{epoch:02d}.json').write_text(json.dumps(r))
            final_baseline = runner.state_hashes(model)
            for mode, coefficient in [('S', 0), ('S', .1), ('P', .1)]:
                self.seed()
                current = self.model(BigMHC)
                head = auxiliary.AuxiliaryHead(torch, current, device=self.device)
                native = experiment.AuxiliaryDataset(experiment.native_dataset(Dataset, encodings, rows), rows, sidecar)
                optimizer = torch.optim.AdamW(list(current.parameters())+list(head.head.parameters()), lr=5e-5)
                with patch('sys.stdout', new=io.StringIO()):
                    for epoch, ref in enumerate(expected, 1):
                        before = binding.rng_identity(torch, np)
                        r = auxiliary.train_el(torch, current, native, c, head, auxiliary.Targets(sidecar, mode), ref,
                                               device=self.device, coefficient=coefficient, optimizer=optimizer)
                        experiment.check_schedule(r, ref, before, binding.rng_identity(torch, np))
                        self.assertEqual(shared.optimizer_steps(optimizer), [7*epoch]*(38 if coefficient else 36))
                if coefficient == 0:
                    self.assertEqual(final_baseline, runner.state_hashes(current))
                bad_optimizer = torch.optim.AdamW(current.parameters(), lr=5e-5)
                with self.assertRaisesRegex(ValueError, 'parameter order'):
                    auxiliary.train_el(torch, current, native, c, head, auxiliary.Targets(sidecar, mode), expected[0],
                                       device=self.device, optimizer=bad_optimizer)
                self.assertIsNone(head.handle)
            self.seed()
            construct = lambda: BigMHC(hidlen=4, layers=2)
            model = self.model(BigMHC)
            del model
            with patch('sys.stdout', new=io.StringIO()):
                proof = experiment.sampler_preflight(torch, np, Dataset, encodings, rows, directory, 'EL', 10, c)
            self.assertTrue(proof['all_ordered_batches_match_A'])
            # Fresh plain EL reload, no auxiliary head; native IM optimizer persists.
            checkpoint = directory/'EL'
            checkpoint.mkdir()
            runner.save_checkpoint(current, checkpoint, transfer=False, device=self.device)
            model = runner.load_checkpoint(torch, construct, checkpoint, list(current.state_dict()), device=self.device)
            self.assertEqual(runner.state_hashes(model), runner.state_hashes(current))
            self.assertEqual(len(model.state_dict()), 36)
            before_transfer = runner.state_hashes(model)
            self.seed()
            native = baseline.AuditedDataset(experiment.native_dataset(Dataset, encodings, rows), list(range(1, len(rows)+1)))
            optimizer = torch.optim.AdamW([v for k,v in model.named_parameters() if k in runner.TRANSFER], lr=5e-5)
            cumulative = 0
            with patch('sys.stdout', new=io.StringIO()):
                for epoch in range(1, 21):
                    before = binding.rng_identity(torch, np)
                    r = runner.train_epoch(torch, model, native, c, True, self.device, optimizer=optimizer)
                    cumulative += r['optimization_steps']
                    self.assertEqual(shared.optimizer_steps(optimizer), [cumulative]*4)
                    r.update(RNG_before=before, RNG_after=binding.rng_identity(torch, np))
                    (directory/f'reports/final_all_IM_epoch_{epoch:02d}.json').write_text(json.dumps(r))
                self.seed()
                proof = experiment.sampler_preflight(torch, np, Dataset, encodings, rows, directory, 'final_all_IM', 20, c)
            self.assertTrue(proof['all_ordered_batches_match_A'])
            self.assertEqual({k for k,v in runner.state_hashes(model).items() if v != before_transfer[k]}, set(runner.TRANSFER))


if __name__ == '__main__':
    unittest.main()
