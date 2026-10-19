"""Run focused authentic CUDA synthetic gates; write receipts under project runs."""
import contextlib
import json
import sys
import unittest

from stability_label_curation import bigmhc_fully_trained_auxiliary as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths


def main() -> None:
    paths = resolve_paths()
    directory = paths.project_runs_dir/experiment.RUN_ID
    (directory/'logs').mkdir(parents=True, exist_ok=True)
    (directory/'reports').mkdir(exist_ok=True)
    sys.path.insert(0, str(paths.repository_root/'tests'))
    import test_bigmhc_stability_auxiliary as legacy
    import test_bigmhc_fully_trained_auxiliary as focused
    legacy.TEST_DEVICE = 'cuda'
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (legacy, focused))
    with (directory/'logs/focused_tests.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    proof = dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
                 tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                 skipped=len(result.skipped), device='cuda:0', scientific_hashes=experiment.scientific_hashes(paths),
                 log_sha256=runner.raw.sha256_file(directory/'logs/focused_tests.log'))
    runner.raw.write_report(directory/'reports/focused_tests.json', proof, paths=paths)
    print(json.dumps(proof, sort_keys=True))
    if proof['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
