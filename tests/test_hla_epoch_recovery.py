"""Focused IO/identity safeguards; real-model integration is the Phase1 gate."""
import hashlib
import inspect
import json
from pathlib import Path
import time
import unittest

from stability_label_curation import hla_epoch_recovery as r
from stability_label_curation import hla_recovery_export as e


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p,_,_,_=r.context()
        cls.root=p.project_runs_dir/f'hla-recovery-unit-tests-{time.time_ns()}'
        cls.root.mkdir()

    def case(self):
        path=self.root/self._testMethodName;path.mkdir();return path

    def test_sentinel_parent_and_exclusive_save(self):
        result=e.cpu_sentinel_tests(self.case()/'sentinel')
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['tests'],3)

    def test_no_marker_never_certifies_even_if_directory_exists(self):
        path=self.case();(path/'0_fake.lyr').write_bytes(b'not a model')
        with self.assertRaisesRegex(ValueError,'marker absent'):r.checkpoint_valid(path)

    def test_forbid_original_run_save_parent(self):
        _,_,_,old=r.context()
        with self.assertRaises(ValueError):r.ensure_parent(old/'checkpoints')
        self.assertFalse((old/'checkpoints').exists())

    def test_original_scientific_bytes_unchanged(self):
        p,_,_,_=r.context();proof=r.source_proof()
        self.assertEqual(r.science.hashes(p,proof['config']),proof['scientific_hashes'])

    def test_bindings_do_not_replace_scientific_train_or_infer(self):
        original=(r.science.paths_config,r.science.require,r.science.save_complete)
        train,infer=r.science.train,r.science.infer_one
        try:
            r.install_bindings()
            self.assertIs(r.science.train,train);self.assertIs(r.science.infer_one,infer)
        finally:r.science.paths_config,r.science.require,r.science.save_complete=original

    def test_isolated_storage_and_fixed_eight_fit_plan(self):
        _,c,d,old=r.context();self.assertNotEqual(d,old);self.assertFalse(d.is_relative_to(old))
        protocol=r.source_proof()['config'];self.assertEqual(protocol['seeds'],[42,123,456])
        self.assertEqual(len(protocol['jobs']),8);self.assertNotIn(['A',42],protocol['jobs'])
        self.assertEqual(protocol['maximum_concurrency'],c['maximum_concurrency'])

    def test_score_alignment_duplicates_missing_and_nonfinite(self):
        root=self.case();path=root/'scores.jsonl'
        def save(rows):path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
        rows=[{'source_id':k,'native_logit':0.,'positive_probability':.5} for k in ['a','b']]
        save(rows);self.assertEqual(e.validate_scores(path,['a','b'])['n'],2)
        for bad in [rows[::-1],rows[:1],[rows[0],rows[0]],[dict(rows[0],native_logit=float('nan')),rows[1]]]:
            save(bad)
            with self.assertRaises(ValueError):e.validate_scores(path,['a','b'])

    def test_no_outcome_access_in_fit_or_score_entry(self):
        self.assertNotIn('label_sources',inspect.getsource(r.worker))
        self.assertNotIn('label_sources',inspect.getsource(r.predict_subprocess))
        self.assertNotIn('label_sources',inspect.getsource(r.science.train))
        self.assertNotIn('outcomes.json',inspect.getsource(r.science.infer_one))

    def test_no_im_metrics_in_export(self):
        source=inspect.getsource(e.finish)
        for forbidden in ['development_metrics(', 'bootstrap(', 'average_precision_score(', 'roc_auc_score(']:
            self.assertNotIn(forbidden,source)


if __name__=='__main__':unittest.main()
