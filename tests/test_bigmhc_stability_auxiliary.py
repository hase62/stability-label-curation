"""Authentic pinned BigMHC, small hidden width, synthetic CPU/CUDA observations only."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import bigmhc_baseline_compatibility as compatibility
from stability_label_curation import bigmhc_stability_auxiliary as aux
from stability_label_curation import bigmhc_auxiliary_experiment as experiment
from stability_label_curation import el_stability_loss_adapter as binding
from stability_label_curation.paths import resolve_paths

TEST_DEVICE = 'cpu'
HISTORICAL_A_COMPATIBILITY = {}


def scores_fixture():
    archive = 'a' * 64
    rows = []
    for i, (hla, score) in enumerate([('HLA-A*02:01', '0'), ('HLA-A*02:01', '-0.0'),
            ('HLA-A*02:01', '1'), ('HLA-A*02:01', '2'), ('HLA-B*08:01', '3'),
            ('HLA-B*08:01', '3'), ('HLA-B*08:01', '5')], 1):
        rows.append(binding.PositiveScore(str(i), str(i), binding.design.prior.pilot.row_id(archive, 'el_train.csv', i),
                    binding.design.prior.adapter.source_hash(['mhc', 'pep', 'tgt'], [hla, 'AAAAAAAAA', '1']),
                    hla, hla, 'AAAAAAAAA', '1', score))
    counts = dict(Counter(r.resolved_hla for r in rows))
    manifest = {'rows': len(rows), 'HLA_groups': len(counts), 'positive_counts_by_HLA': counts,
                'supported_HLA': list(counts), 'archive_sha256': archive}
    return binding.LossAdapter(rows, manifest, 'A')


def native_fixture(Dataset, sidecar):
    records, observations = [], []
    positives = list(sidecar.scores.values())
    for i in range(1, 408):
        positive = i <= len(positives)
        hla = positives[i - 1].resolved_hla if positive else 'HLA-A*02:01'
        peptide, label = 'AAAAAAAAA', str(int(positive))
        observations.append({'mhc': hla, 'pep': peptide, 'tgt': int(label), 'len': 9})
        records.append({'source_file': 'el_train.csv', 'row_index': str(i), 'source_line_number': str(i + 1),
            'source_row_id': binding.design.prior.pilot.row_id(sidecar.manifest['archive_sha256'], 'el_train.csv', i),
            'source_row_sha256': binding.design.prior.adapter.source_hash(['mhc', 'pep', 'tgt'], [hla, peptide, label]),
            'original_hla': hla, 'resolved_hla': hla, 'original_peptide': peptide, 'original_label': label,
            'derived_row_index': str(i), 'retained': '1'})
    # Deterministic synthetic 23-position one-hot HLA encodings, no scientific inputs.
    encodings = {}
    for j, hla in enumerate(sidecar.manifest['supported_HLA']):
        code = torch.zeros(414, dtype=torch.int8)
        code[torch.arange(23) * 18 + j] = 1
        encodings[hla] = code
    df = pd.DataFrame(observations).astype({'tgt': 'float32', 'len': 'int8'})
    return binding.IdentityDataset(Dataset(df, mhcenc=encodings), records, stage='EL', adapter=sidecar)


class TargetsTests(unittest.TestCase):
    def test_midrank_ties_binding_and_negative_rejection(self):
        base = scores_fixture()
        s = aux.Targets(base, 'S')
        self.assertEqual(list(s.exact.values()), [Fraction(1, 4), Fraction(1, 4), Fraction(5, 8), Fraction(7, 8),
                                                Fraction(1, 3), Fraction(1, 3), Fraction(5, 6)])
        identity = next(iter(base.scores))
        self.assertEqual(s.anchor([identity, 'negative'], [1, 0]), (0, .25))
        for ids, ys in [(['missing', 'negative'], [1, 0]), ([identity, identity], [1, 0]),
                         (['negative', identity], [0, 1]), ([identity, identity], [1, 1]),
                         (['negative'], [0])]:
            with self.subTest(ids=ids, ys=ys), self.assertRaises(ValueError):
                s.anchor(ids, ys)

    def test_permutation_exact_FP32_multisets_per_HLA_and_order_invariance(self):
        base = scores_fixture()
        state = binding.rng_identity(torch, np)
        s, p = aux.Targets(base, 'S'), aux.Targets(base, 'P')
        proof = aux.compare_targets(s, p)
        self.assertTrue(proof['per_HLA_exact_and_FP32_multisets_equal'])
        self.assertEqual(state, binding.rng_identity(torch, np))
        self.assertNotEqual(s.exact, p.exact)
        self.assertEqual(p.exact, aux.Targets(base, 'P').exact)
        for hla in base.manifest['supported_HLA']:
            ids = [i for i, r in base.scores.items() if r.resolved_hla == hla]
            self.assertEqual(sorted(s.exact[i] for i in ids), sorted(p.exact[i] for i in ids))
            ranks = [s.exact[i] for i in ids]
            forward = dict(zip(ids, aux.permute(ids, ranks, hla)))
            reverse = dict(zip(ids[::-1], aux.permute(ids[::-1], ranks[::-1], hla)))
            self.assertEqual(forward, reverse)
        p.values[next(iter(p.values))] = -1
        with self.assertRaises(ValueError):
            aux.compare_targets(s, p)

    def test_config_and_authorization_gates_preserve_legacy_identity(self):
        paths = resolve_paths()
        c = experiment.load_config(paths.repository_root / experiment.CONFIG, paths)
        self.assertEqual(binding.matched_config_identity(c), compatibility.SCIENTIFIC_IDENTITY)
        with self.assertRaisesRegex(ValueError, 'preparation only'):
            experiment.require_authorization(c)
        with patch.object(runner.runs, 'create_run') as create:
            with self.assertRaisesRegex(ValueError, 'preparation only'):
                experiment.execute(paths.repository_root / experiment.CONFIG, Path('/unused'), Path('/unused'), paths)
            create.assert_not_called()
        for mutate in (lambda d: d['auxiliary'].update(lambda_aux=.2),
                       lambda d: d['auxiliary'].update(head_seed=42),
                       lambda d: d.update(learning_rate=1e-4),
                       lambda d: d.update(condition='B')):
            changed = deepcopy(c)
            mutate(changed)
            with tempfile.TemporaryDirectory() as tmp:
                cp = Path(tmp).resolve() / 'config.json'
                cp.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    experiment.load_config(cp, paths)

    def test_CUDA_reuse_incompatibility_blocks_before_run_creation(self):
        paths = resolve_paths()
        config = experiment.load_config(paths.repository_root / experiment.CONFIG, paths)
        config['auxiliary']['training_authorized'] = True
        good = {'status': 'passed', 'device': 'cuda:0', 'source_sha256': {'current': 'hash'},
                'skipped': 0, 'tests': 12, 'historical_A_numeric_compatibility': {'reuse_compatible': True}}
        for change in ({'device': 'cpu'}, {'source_sha256': {}}, {'skipped': 1}, {'tests': 0},
                       {'historical_A_numeric_compatibility': {'reuse_compatible': False}}):
            gate = {**good, **change}
            with self.subTest(change=change), patch.object(experiment, 'load_config', return_value=config), patch.object(
                    experiment, 'source_identity', return_value={'current': 'hash'}), patch.object(
                    runner, 'cuda_visibility'), patch.object(runner.readers, '_json', return_value=gate), patch.object(
                    runner.runs, 'create_run') as create:
                with self.assertRaisesRegex(ValueError, 'synthetic CUDA gate'):
                    experiment.execute(Path('/unused'), Path('/unused'), Path('/unused'), paths)
                create.assert_not_called()

    def test_fixed_contrasts(self):
        metrics = {m: {s: {'AUPRC': v, 'AUROC': v} for s in ('IM', 'EL_proxy')}
                   for m, v in [('A', .25), ('S', .75), ('P', .5)]}
        result = experiment.contrasts(metrics)
        self.assertEqual(set(result), {'S-A', 'S-P', 'P-A'})
        self.assertEqual(result['S-P']['IM']['AUPRC'], .25)

    def test_legacy_source_contract_unchanged(self):
        self.assertEqual(compatibility.source_contract(resolve_paths())['worker_reviewed_substitutions'], 6)


class AuthenticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        cls.device = runner.runtime_device(torch, {'device': TEST_DEVICE})
        if cls.device != 'cpu':
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
        paths = resolve_paths()
        config = runner.readers._json(paths.repository_root / experiment.CONFIG)
        cls.files = {}
        # Read the four previously downloaded pinned source files only.
        for name in ('bigmhc', 'dataset', 'mhcuid', 'encseq'):
            spec = config['inputs']['source_' + name]
            path = paths.project_data_dir / spec['relative_path']
            if runner.raw.sha256_file(path) != spec['sha256']:
                raise ValueError('Pinned authentic source mismatch')
            cls.files['source_' + name] = path

    def seed(self):
        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)
        if self.device != 'cpu':
            torch.cuda.manual_seed_all(42)

    def model(self, BigMHC):
        # Same authentic code and all 36 tensors; width4 avoids full-size CPU training.
        return BigMHC(hidlen=4, layers=2).to(self.device)

    def inputs(self):
        generator = torch.Generator().manual_seed(123)
        mhc = torch.zeros(17, 414, device=self.device)
        mhc[:, torch.arange(23, device=self.device) * 18] = 1
        pep = torch.rand(17, 180, generator=generator).to(self.device)
        labels = torch.zeros(17, device=self.device)
        labels[0] = 1
        return mhc, pep, labels

    def test_native_BCE_values_gradients_updates_and_disabled_equivalence(self):
        with runner.pinned_modules(self.files) as (BigMHC, _):
            mhc, pep, labels = self.inputs()
            records = []
            for mode in ('native', 'disabled'):
                disabled = mode == 'disabled'
                self.seed()
                model = self.model(BigMHC)
                initial = runner.state_hashes(model)
                head = aux.AuxiliaryHead(torch, model, device=self.device) if disabled else None
                parameters = list(model.parameters()) + (list(head.head.parameters()) if head else [])
                optimizer = torch.optim.AdamW(parameters, lr=5e-5)
                optimizer.zero_grad()
                logits, _ = model(mhc, pep)
                if disabled:
                    loss, bce, mse = aux.losses(torch, logits, labels, coefficient=0)
                    self.assertIs(loss, bce)
                    self.assertIsNone(mse)
                    self.assertIsNone(head.features)
                else:
                    loss = torch.nn.BCEWithLogitsLoss()(logits, labels)
                loss.backward()
                gradients = {k: p.grad.detach().clone() for k, p in model.named_parameters()}
                optimizer.step()
                records.append((float(loss.detach()), gradients, runner.state_hashes(model), initial,
                                binding.rng_identity(torch, np)))
            for comparison in records[1:]:
                self.assertEqual(records[0][0], comparison[0])
                for key in records[0][1]:
                    self.assertTrue(torch.equal(records[0][1][key], comparison[1][key]), key)
                self.assertEqual(records[0][2:], comparison[2:])

    def test_historical_A_numeric_path_diagnostic(self):
        global HISTORICAL_A_COMPATIBILITY
        records = []
        with runner.pinned_modules(self.files) as (BigMHC, _):
            mhc, pep, labels = self.inputs()
            for mode in ('native', 'historical_unit_weight'):
                self.seed()
                model = self.model(BigMHC)
                optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
                logits, _ = model(mhc, pep)
                loss = (torch.nn.BCEWithLogitsLoss()(logits, labels) if mode == 'native' else
                        binding.weighted_bce(torch, logits, labels, [1.0] * len(labels)))
                loss.backward()
                gradients = {k: p.grad.detach().clone() for k, p in model.named_parameters()}
                optimizer.step()
                records.append((float(loss.detach()), gradients,
                                {k: p.detach().clone() for k, p in model.named_parameters()}))
        report = {'batch_rows': 17, 'loss_exactly_equal': records[0][0] == records[1][0],
                  'native_loss': records[0][0], 'historical_unit_weight_loss': records[1][0]}
        for index, name in ((1, 'gradients'), (2, 'AdamW_updated_tensors')):
            differences = [float((records[0][index][k] - records[1][index][k]).abs().max())
                           for k in records[0][index]]
            report[name + '_exactly_equal'] = all(v == 0 for v in differences)
            report[name + '_maximum_absolute_difference'] = max(differences)
            report[name + '_changed_tensor_count'] = sum(v != 0 for v in differences)
        report['reuse_compatible'] = all(report[k] for k in ('loss_exactly_equal',
            'gradients_exactly_equal', 'AdamW_updated_tensors_exactly_equal'))
        HISTORICAL_A_COMPATIBILITY = report
        # Mac records the CPU kernel discrepancy; CUDA reuse must prove exact agreement.
        if self.device != 'cpu':
            self.assertTrue(report['reuse_compatible'], str(report))

    def test_active_loss_original_BCE_denominator_and_auxiliary_gradient_flow(self):
        with runner.pinned_modules(self.files) as (BigMHC, _):
            self.seed()
            model = self.model(BigMHC)
            head = aux.AuxiliaryHead(torch, model, device=self.device)
            mhc, pep, labels = self.inputs()
            head.capture()
            logits, _ = model(mhc, pep)
            prediction = head.prediction(0)
            total, bce, mse = aux.losses(torch, logits, labels, prediction, .75)
            self.assertTrue(torch.equal(bce, torch.nn.BCEWithLogitsLoss()(logits, labels)))
            self.assertTrue(torch.equal(mse, (prediction - .75).square()))
            self.assertTrue(torch.equal(total, bce + .1 * mse))
            mse.backward(retain_graph=True)
            for component in (head.head, model.anchorBlock, model.lstm, model.condenser.att):
                self.assertTrue(any(p.grad is not None and p.grad.abs().sum() > 0 for p in component.parameters()))
            model.zero_grad()
            head.head.zero_grad()
            total.backward()
            self.assertEqual(sum(p.numel() for p in head.head.parameters()), 415)
            head.close()
            self.assertEqual(len(model.state_dict()), 36)
            with self.assertRaises(ValueError):
                head.prediction(0)

    def test_head_init_rng_isolation_identical_SP_and_original_classifier(self):
        with runner.pinned_modules(self.files) as (BigMHC, _):
            records = []
            for mode in ('S', 'P'):
                self.seed()
                model = self.model(BigMHC)
                initial = runner.state_hashes(model)
                boundary = binding.rng_identity(torch, np)
                head = aux.AuxiliaryHead(torch, model, device=self.device)
                self.assertEqual(boundary, binding.rng_identity(torch, np))
                self.assertEqual(initial, runner.state_hashes(model))
                records.append((initial, runner.state_hashes(head.head), boundary))
                self.assertFalse(any(k.startswith('aux') for k in model.state_dict()))
            self.assertEqual(records[0], records[1])
            mhc, pep, _ = self.inputs()
            model.eval()
            before = binding.rng_identity(torch, np)
            with torch.no_grad():
                original, _ = model(mhc, pep)
                head.capture()
                hooked, _ = model(mhc, pep)
                head.close()
            self.assertTrue(torch.equal(original, hooked))
            self.assertEqual(before, binding.rng_identity(torch, np))

    def test_native_full_epoch_SP_matching_and_preupdate_batch_rejection(self):
        with runner.pinned_modules(self.files) as (BigMHC, Dataset):
            sidecar = scores_fixture()
            config = {'batch_size': 16, 'learning_rate': 5e-5}
            self.seed()
            baseline_model = self.model(BigMHC)
            baseline_initial = runner.state_hashes(baseline_model)
            dataset = native_fixture(Dataset, sidecar)
            boundary = binding.rng_identity(torch, np)
            with patch('sys.stdout', new=io.StringIO()):
                expected = runner.train_epoch(torch, baseline_model, dataset, config, False, self.device)
            baseline_after = binding.rng_identity(torch, np)
            self.seed()
            disabled_model = self.model(BigMHC)
            disabled_head = aux.AuxiliaryHead(torch, disabled_model, device=self.device)
            with patch('sys.stdout', new=io.StringIO()):
                disabled = aux.train_el(torch, disabled_model, native_fixture(Dataset, sidecar), config, disabled_head,
                                        aux.Targets(sidecar, 'S'), expected, device=self.device, coefficient=0)
            self.assertEqual(runner.state_hashes(disabled_model), runner.state_hashes(baseline_model))
            self.assertEqual([s['BCE_loss'] for s in disabled['step_log']], [s['BCE_loss'] for s in expected['step_log']])
            self.assertEqual(baseline_after, binding.rng_identity(torch, np))
            records = []
            for mode in ('S', 'P'):
                self.seed()
                model = self.model(BigMHC)
                self.assertEqual(baseline_initial, runner.state_hashes(model))
                head = aux.AuxiliaryHead(torch, model, device=self.device)
                dataset = native_fixture(Dataset, sidecar)
                self.assertEqual(boundary, binding.rng_identity(torch, np))
                with patch('sys.stdout', new=io.StringIO()):
                    result = aux.train_el(torch, model, dataset, config, head, aux.Targets(sidecar, mode), expected, device=self.device)
                self.assertEqual(baseline_after, binding.rng_identity(torch, np))
                records.append(result['sampled_batch_sha256'])
                self.assertEqual(result['step_log'][0]['BCE_loss'], expected['step_log'][0]['BCE_loss'])
                self.assertEqual(result['optimization_steps'], 7)
                self.assertTrue(all(x['rows'] == 17 for x in result['step_log']))
            self.assertEqual(records[0], records[1])
            self.seed()
            model = self.model(BigMHC)
            head = aux.AuxiliaryHead(torch, model, device=self.device)
            bad = deepcopy(expected)
            bad['sampled_batch_sha256'][0] = 'wrong'
            initial = runner.state_hashes(model)
            with self.assertRaisesRegex(ValueError, 'before optimizer update'):
                aux.train_el(torch, model, native_fixture(Dataset, sidecar), config, head, aux.Targets(sidecar, 'S'), bad, device=self.device)
            self.assertEqual(initial, runner.state_hashes(model))
            self.assertIsNone(head.handle)

    def test_authentic_IM_transfer_and_auxiliary_checkpoint_separation(self):
        with runner.pinned_modules(self.files) as (BigMHC, Dataset):
            # runner.load_checkpoint uses default constructor; inject the same small authentic constructor.
            construct = lambda: self.model(BigMHC).cpu()
            self.seed()
            model = self.model(BigMHC)
            head = aux.AuxiliaryHead(torch, model, device=self.device)
            sidecar = scores_fixture()
            keys = list(model.state_dict())
            with tempfile.TemporaryDirectory() as tmp:
                el = Path(tmp).resolve() / 'el'
                el.mkdir()
                runner.save_checkpoint(model, el, transfer=False, device=self.device)
                self.assertEqual(len(runner.checkpoint_identity(el, keys)), 36)
                head_path = Path(tmp) / 'auxiliary_head.pt'
                torch.save(head.head.state_dict(), head_path)
                state = torch.load(head_path, map_location='cpu', weights_only=True)
                head.head.load_state_dict(state, strict=True)
                loaded = runner.load_checkpoint(torch, construct, el, keys, device=self.device)
                self.assertEqual(runner.state_hashes(loaded), runner.state_hashes(model))
                self.assertEqual(list(loaded.state_dict()), keys)
                before = runner.state_hashes(loaded)
                # Native IM batching and optimizer selection, no auxiliary adapter/head.
                dataset = native_fixture(Dataset, sidecar).native
                with patch('sys.stdout', new=io.StringIO()):
                    result = runner.train_epoch(torch, loaded, dataset, {'learning_rate': 5e-5, 'batch_size': 16}, True, self.device)
                self.assertEqual(result['updated_parameters'], list(runner.TRANSFER))
                changed = {k for k, v in runner.state_hashes(loaded).items() if v != before[k]}
                self.assertTrue(changed)
                self.assertFalse(changed - set(runner.TRANSFER))
                im = el / 'im'
                im.mkdir()
                runner.save_checkpoint(loaded, im, transfer=True, device=self.device)
                self.assertEqual(len(runner.overlay_identity(im, keys)), 4)
                lineage = {'state_keys': keys, 'EL_files': runner.checkpoint_identity(el, keys),
                           'IM_files': runner.overlay_identity(im, keys)}
                rebuilt = runner.load_checkpoint(torch, construct, im, keys, device=self.device, lineage=lineage)
                self.assertEqual(runner.state_hashes(loaded), runner.state_hashes(rebuilt))


if __name__ == '__main__':
    unittest.main()
