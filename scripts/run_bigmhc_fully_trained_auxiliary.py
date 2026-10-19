"""Capture Task 2.24 stage logs and read-only GPU telemetry in run storage."""
import contextlib
import json
import subprocess
import sys
import threading
import time

from stability_label_curation import bigmhc_fully_trained_auxiliary as experiment
from stability_label_curation.paths import resolve_paths


def main() -> None:
    if sys.argv[1:] not in (['preflight'], ['execute']):
        raise SystemExit('Expected preflight or execute')
    action = sys.argv[1]
    paths = resolve_paths()
    directory = paths.project_runs_dir/experiment.RUN_ID
    (directory/'logs').mkdir(parents=True, exist_ok=True)
    stopped = threading.Event()

    def monitor() -> None:
        with (directory/f'logs/{action}_gpu.jsonl').open('x') as log:
            while not stopped.is_set():
                result = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,utilization.gpu,memory.used,power.draw,temperature.gpu',
                                         '--format=csv,noheader,nounits'], text=True, capture_output=True, check=False)
                log.write(json.dumps(dict(utc_unix=time.time(), returncode=result.returncode,
                                          csv=result.stdout.strip(), error=result.stderr.strip()))+'\n')
                log.flush()
                stopped.wait(30)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        with (directory/f'logs/{action}.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            # Main retains immutable failure receipts as well as full tracebacks.
            experiment.main()
    finally:
        stopped.set()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
