"""Task 2.19 invariants, narrow reuse rejection, and unchanged legacy behavior."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from stability_label_curation import bigmhc_abp_experiment as experiment
from stability_label_curation import bigmhc_abp_preflight as preflight
from stability_label_curation import bigmhc_baseline_compatibility as compatibility
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import el_stability_loss_adapter as weights
from stability_label_curation.paths import resolve_paths


def fixture():
    hla, archive = 'HLA-B*08:01', 'a'*64
    rows = []
    for i, score in enumerate(['0', '-0.0', '1', '2', '3'], 1):
        rows.append(weights.PositiveScore(str(i), str(i),
            weights.design.prior.pilot.row_id(archive, 'el_train.csv', i),
            weights.design.prior.adapter.source_hash(['mhc','pep','tgt'], [hla,'AAAAAAAAA','1']),
            hla, hla, 'AAAAAAAAA', '1', score))
    manifest = dict(rows=len(rows), HLA_groups=1, positive_counts_by_HLA={hla:len(rows)},
                    supported_HLA=[hla], archive_sha256=archive)
    return rows, manifest


class LowStabilityTests(unittest.TestCase):
    def test_exact_one_sided_weights_ties_and_permutation(self):
        rows, manifest = fixture()
        state = random.getstate()
        adapters = {m:weights.LossAdapter(rows,manifest,m,protocol_version=weights.LOW_PROTOCOL)
                    for m in ('A','L','P')}
        self.assertEqual(state,random.getstate())
        self.assertEqual(list(adapters['L'].rational.values()),
                         [Fraction(17,20),Fraction(17,20),Fraction(1),Fraction(1),Fraction(1)])
        self.assertEqual(set(adapters['A'].weights.values()),{1})
        self.assertEqual(sorted(adapters['L'].rational.values()),sorted(adapters['P'].rational.values()))
        self.assertEqual(sorted(adapters['L'].weights.values()),sorted(adapters['P'].weights.values()))
        self.assertEqual(adapters['L'].evidence['by_HLA'],adapters['P'].evidence['by_HLA'])
        self.assertLess(sum(adapters['L'].rational.values()),len(rows))
        legacy=weights.LossAdapter(rows,manifest,'P')
        self.assertEqual(sum(legacy.rational.values()),len(rows))
        self.assertGreater(max(legacy.weights.values()),1)

    def test_protocols_cannot_mix_conditions_or_unknown_versions(self):
        rows,manifest=fixture()
        for mode,version in [('L',weights.design.VERSION),('B',weights.LOW_PROTOCOL),('A','unknown')]:
            with self.subTest(mode=mode,version=version),self.assertRaises(ValueError):
                weights.LossAdapter(rows,manifest,mode,protocol_version=version)

    def test_ALP_plans_preserve_scientific_config_and_baseline(self):
        base=runner.load_config(experiment.LOW_CONFIG)
        plans=preflight.planned_configurations(base)
        self.assertEqual(set(plans),{'A','L','P'})
        for mode,config in plans.items():
            self.assertEqual(weights.matched_config_identity(config),compatibility.SCIENTIFIC_IDENTITY)
            if mode!='A':
                self.assertEqual(config['loss_adapter']['matched_reference'],compatibility.REFERENCE)
                with self.assertRaises(ValueError):weights.require_training_authorization(config)
        for field,value in [('strength','0.6'),('seed',43),('mode','B')]:
            config=deepcopy(base);config['loss_adapter'][field]=value
            with self.assertRaises(ValueError):weights.validate_runtime_spec(config['loss_adapter'],config['condition'])

    def test_three_frozen_ALP_contrasts(self):
        metrics={m:{s:{'AUPRC':v,'AUROC':v} for s in ('IM','EL_proxy')}
                 for m,v in [('A',.25),('L',.75),('P',.5)]}
        result=experiment.metric_contrasts(metrics)
        self.assertEqual(set(result),{'L-A','L-P','P-A'})
        self.assertEqual(result['L-A']['IM']['AUPRC'],.5)
        self.assertEqual(result['L-P']['IM']['AUPRC'],.25)

    def test_source_contract_pins_original_training_and_reviewed_worker_diff(self):
        paths=resolve_paths()
        result=compatibility.source_contract(paths)
        self.assertEqual(result['worker_reviewed_substitutions'],6)
        self.assertIn('bigmhc_baseline_runner.py:train_epoch',result['unchanged_scientific_AST_sha256'])
        with patch.object(compatibility.inspect,'getsource',return_value='def worker():\n    pass\n'):
            with self.assertRaisesRegex(ValueError,'beyond reviewed'):
                compatibility.source_contract(paths)

    def test_reuse_rejects_other_baselines_data_or_scientific_settings(self):
        base=runner.load_config(experiment.LOW_CONFIG)
        compatibility.validate_spec(base)
        for change in ('commit','reference','protocol_commit','seed','optimizer','data'):
            c=deepcopy(base)
            if change in ('commit','protocol_commit'):c['baseline_reuse'][change]='a'*40
            if change=='reference':c['baseline_reuse']['reference']['sha256']='b'*64
            if change=='seed':c['seed']=43
            if change=='optimizer':c['learning_rate']=1e-4
            if change=='data':c['inputs']['EL']['sha256']='c'*64
            with self.subTest(change=change),self.assertRaises(ValueError):compatibility.validate_spec(c)

    def test_legacy_metadata_remains_strict_and_low_requires_receipt(self):
        old=runner.load_config(experiment.CONFIG)
        current={'code_commit':'new','versions':{'torch':'same'},'configuration_identity':'id'}
        reference={**current,'code_commit':compatibility.BASELINE_COMMIT}
        with self.assertRaisesRegex(ValueError,'Matched A code'):
            compatibility.check_metadata(current,reference,old,resolve_paths())
        low=experiment.arm_configuration(runner.load_config(experiment.LOW_CONFIG),'L',compatibility.REFERENCE)
        with self.assertRaisesRegex(ValueError,'Missing reviewed'):
            compatibility.check_metadata(current,reference,low,resolve_paths())
        changed={**current,'versions':{'torch':'different'}}
        with self.assertRaisesRegex(ValueError,'runtime'):
            compatibility.check_metadata(changed,reference,low,resolve_paths())

    def test_sampling_rng_optimizer_and_initial_rejections_remain(self):
        with self.assertRaisesRegex(ValueError,'initial'):
            weights.check_reference({'initial_tensor_sha256':{'x':'a'}},initial={'x':'b'})
        with self.assertRaisesRegex(ValueError,'RNG'):
            weights.check_reference({'rng_before_EL':{'x':'a'}},rng={'x':'b'},stage='EL')
        training=dict(optimization_steps=1,sampled_batch_sha256=['a'],optimizer_defaults={'lr':5e-5},
                      updated_parameters=['x'],optimizer_skip_mask=[False])
        for key,value in [('optimization_steps',2),('sampled_batch_sha256',['b']),
                          ('optimizer_defaults',{'lr':1e-4}),('updated_parameters',['y']),
                          ('optimizer_skip_mask',[True])]:
            altered={**training,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):
                weights.check_reference({'EL':training},stage='EL',training=altered)

    def test_low_arm_cannot_escape_or_train_fourth_condition(self):
        paths=resolve_paths()
        for condition in ('A','B','other'):
            config=runner.load_config(experiment.LOW_CONFIG);config['condition']=condition
            with self.assertRaisesRegex(ValueError,'output directory'):
                experiment.arm_run(paths.project_runs_dir/experiment.LOW_RUN_ID/condition,paths,config)

    def test_cuda_noop_failure_prevents_ALP_run_creation(self):
        with patch.object(runner.readers,'_json',return_value={'device':'cpu'}),patch.object(
                runner,'load_config',return_value={}),patch.object(runner,'cuda_visibility'),patch.object(
                runner.runs,'create_run') as create:
            with self.assertRaisesRegex(ValueError,'no-op'):
                experiment.execute_low(noop_report=Path('/unused'),test_log=Path('/unused'),paths=resolve_paths())
            create.assert_not_called()


if __name__=='__main__':
    unittest.main()
