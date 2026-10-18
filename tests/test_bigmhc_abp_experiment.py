"""Execution gates only; synthetic evidence and no scientific training."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import bigmhc_abp_experiment as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import el_stability_loss_adapter as weights
from stability_label_curation.paths import resolve_paths


class ExperimentTests(unittest.TestCase):
    def test_explicit_configs_preserve_every_training_and_input_setting(self):
        base = runner.load_config(experiment.CONFIG)
        reference = {'area': 'runs', 'relative_path': experiment.RUN_ID + '/A/reports/matched_state.json',
                     'sha256': 'a' * 64}
        for mode in ('A', 'B', 'P'):
            c = experiment.arm_configuration(base, mode, None if mode == 'A' else reference)
            self.assertEqual(weights.matched_config_identity(c), weights.matched_config_identity(base))
            self.assertTrue(c['loss_adapter']['training_authorized'])
            self.assertEqual(c['condition'], mode)
        self.assertEqual(base['condition'], 'A')
        with self.assertRaises(ValueError):
            experiment.arm_configuration(base, 'B')

    def test_optimizer_defaults_survive_JSON_reference_and_reject_changes(self):
        training = {'optimization_steps': 1, 'sampled_batch_sha256': ['abc'],
                    'optimizer_defaults': {'betas': (0.9, 0.999), 'lr': 5e-5},
                    'updated_parameters': ['x'], 'optimizer_skip_mask': [False]}
        reference = {'EL': json.loads(json.dumps(training))}
        weights.check_reference(reference, stage='EL', training=training)
        changed = deepcopy(training)
        changed['optimizer_defaults']['lr'] = 1e-4
        with self.assertRaises(ValueError):
            weights.check_reference(reference, stage='EL', training=changed)

    def test_three_prespecified_contrasts(self):
        metrics = {mode: {stage: {'AUPRC': value, 'AUROC': value / 2}
                          for stage in ('IM', 'EL_proxy')}
                   for mode, value in (('A', 0.25), ('B', 0.75), ('P', 0.5))}
        result = experiment.metric_contrasts(metrics)
        self.assertEqual(result['B-A']['IM']['AUPRC'], 0.5)
        self.assertEqual(result['B-P']['IM']['AUPRC'], 0.25)
        self.assertEqual(result['P-A']['IM']['AUPRC'], 0.25)

    def test_noop_failure_prevents_run_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'noop.json'
            report.write_text(json.dumps({'device': 'cpu'}))
            with patch.object(runner.runs, 'create_run') as create, patch.object(runner, 'cuda_visibility'):
                with self.assertRaisesRegex(ValueError, 'no-op gate'):
                    experiment.execute(noop_report=report, test_log=Path(tmp) / 'never-read')
            create.assert_not_called()

    def test_nested_arm_cannot_escape_experiment_or_change_condition(self):
        paths = resolve_paths()
        for directory in (paths.project_runs_dir / experiment.RUN_ID / 'B',
                          paths.project_runs_dir / 'other' / 'A'):
            with self.assertRaisesRegex(ValueError, 'output directory'):
                experiment.arm_run(directory, paths, {'condition': 'A'})

    def test_historical_gate_checks_trajectory_and_scientific_configuration(self):
        config = runner.load_config(experiment.CONFIG)
        training = {key: 1 for key in ('optimization_steps', 'batches', 'optimizer_class_exposures',
                    'sampled_class_exposures', 'optimizer_defaults', 'updated_parameters',
                    'skipped_batch_log', 'sampling')}
        training['step_log'] = [{'batch': 1, 'rows': 17, 'positives': 1, 'BCE_loss': 0.5}]
        summary = {'architecture': {'state_tensors': 36}, 'EL': training, 'IM': training}
        current = deepcopy(summary)
        def read(path):
            if path.name == 'training_configuration.json': return config
            if path.name == 'initial_el_state_identity.json': return {'tensor': 'hash'}
            if path.name == 'training_summary.json':
                return current if path.parts[0] == 'current' else summary
            raise AssertionError(path)
        with patch.object(runner.readers, '_json', side_effect=read), patch.object(
                experiment, 'prediction_rows', return_value=[{'source_row_id': 'id', 'probability': '0.5'}]), patch.object(
                experiment, 'training_report', side_effect=lambda path: current if str(path)=='current' else summary):
            result = experiment.compare_historical(Path('current'), Path('historical'))
            self.assertEqual(result['EL_loss_maximum_absolute_difference'], 0)
            current['EL']['step_log'][0]['BCE_loss'] = 0.6
            with self.assertRaisesRegex(ValueError, 'loss trajectory'):
                experiment.compare_historical(Path('current'), Path('historical'))

    def report_fixture(self, directory, content):
        reports=directory/'reports';reports.mkdir(exist_ok=True)
        path=reports/'training_summary.json';path.write_bytes(content)
        (reports/'execution_verification.json').write_text(json.dumps({'outputs':{
            'reports/training_summary.json':runner.raw.sha256_file(path)}}))
        return path

    def test_receipt_authenticated_report_above_generic_8_MiB(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            content=json.dumps({'architecture':{},'EL':{},'IM':{},'padding':'x'*(8*1024*1024)}).encode()
            path=self.report_fixture(directory,content)
            with self.assertRaisesRegex(ValueError,'inspection bound'):runner.readers._json(path)
            self.assertEqual(experiment.training_report(directory)['EL'],{})
            with path.open('ab') as stream:stream.write(b' ')
            with self.assertRaisesRegex(ValueError,'SHA256'):experiment.training_report(directory)

    def test_training_report_malformed_duplicate_nonfinite_and_oversized_fail(self):
        for content in (b'{',b'[]',b'{"architecture":{},"EL":{},"EL":{},"IM":{}}',
                        b'{"architecture":{},"EL":{},"IM":{},"bad":NaN}', b'{}',
                        b' '*(32*1024*1024+1)):
            with self.subTest(prefix=content[:40]),tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp);self.report_fixture(directory,content)
                with self.assertRaises(ValueError):experiment.training_report(directory)

    def test_planned_ABP_configs_preserve_scientific_identity_and_reference_gate(self):
        from stability_label_curation.bigmhc_abp_preflight import planned_configurations
        base=runner.load_config(experiment.CONFIG)
        result=planned_configurations(base)
        for mode,c in result.items():
            self.assertEqual(weights.matched_config_identity(c),weights.matched_config_identity(base))
            weights.validate_runtime_spec(c['loss_adapter'],mode)
            if mode!='A':
                self.assertIsNone(c['loss_adapter']['matched_reference']['sha256'])
                with self.assertRaises(ValueError):weights.require_training_authorization(c)

    def test_worker_preflight_failure_occurs_before_model_optimizer_or_training(self):
        from stability_label_curation import bigmhc_abp_preflight as preflight
        config=runner.load_config(experiment.CONFIG)
        with patch.object(runner,'resolve_inputs',return_value=({},[])), patch.object(
                experiment,'arm_run',return_value=(Path('/unused'),{})), patch.object(
                preflight,'validate',side_effect=ValueError('full IM binding failed')), patch.object(
                runner.raw,'write_report') as write, patch.object(runner,'runtime_device') as device, patch.object(
                runner,'train_epoch') as train:
            with self.assertRaisesRegex(ValueError,'full IM binding'):
                runner.worker(config_path=experiment.CONFIG,out='/unused')
            device.assert_not_called();train.assert_not_called()
            self.assertEqual(write.call_args.args[1]['status'],'failed')

    def test_preflight_only_records_failure_without_launching_training(self):
        from stability_label_curation import bigmhc_abp_preflight as preflight
        with patch.object(preflight,'validate',side_effect=ValueError('bad history')),patch.object(
                runner.raw,'write_report') as write,patch.object(runner,'train_epoch') as train:
            with self.assertRaisesRegex(ValueError,'bad history'):
                preflight.record(config_path=Path(experiment.CONFIG),report=Path('/unused/report.json'))
            result=write.call_args.args[1]
            self.assertEqual(result['optimizer_initializations'],0)
            self.assertEqual(result['development_observations_scored'],0)
            train.assert_not_called()


if __name__ == '__main__':
    unittest.main()
