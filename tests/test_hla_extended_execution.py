import unittest
from unittest.mock import patch
from types import SimpleNamespace
from stability_label_curation import hla_extended_execution as e


class ProcessTests(unittest.TestCase):
    def test_only_exact_known_setup_error_recoverable(self):
        expected="RuntimeError('Error: cannot set number of interop threads after parallel work has started or set_num_interop_threads called')"
        self.assertTrue(e.known_inference_setup_failure({'error':expected}))
        self.assertFalse(e.known_inference_setup_failure({'error':'CUDA OOM'}))
        self.assertFalse(e.known_inference_setup_failure({}))

    def test_prediction_is_fresh_process(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'logs').mkdir()
            with patch.object(e.science,'paths_config',return_value=(SimpleNamespace(repository_root=root),{},root)), patch.object(e.subprocess,'run') as call:
                e.predict('W',123)
            argv=call.call_args.args[0]
            self.assertEqual(argv[1:4],['-m','stability_label_curation.hla_extended_epochs','predict'])
            self.assertEqual(argv[-4:],['--arm','W','--seed','123'])
            self.assertTrue(call.call_args.kwargs['check'])


if __name__=='__main__':unittest.main()
