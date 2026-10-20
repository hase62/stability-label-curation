"""Explicit model reload or header-only source inspection for Task 2.25."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import platform
import resource
import subprocess
import time

from stability_label_curation import bigmhc_independent_preflight as gates
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('models', 'source-schema'))
    args = parser.parse_args()
    started = time.monotonic()
    paths = resolve_paths()
    directory = paths.project_runs_dir / gates.RUN_ID
    destination = directory / 'reports' / (args.stage.replace('-', '_') + '.json')
    if destination.exists():
        raise FileExistsError('Preserve existing stage receipt: ' + str(destination))
    receipt, context = gates.authenticate_models(paths)
    if args.stage == 'models':
        import numpy as np
        import torch
        runner.seed_runtime(torch, np, {'seed': 42, 'cpu_threads': 4, 'device': 'cuda'})
        device = runner.runtime_device(torch, {'device': 'cuda'})
        receipt['runtime'] = {'Python': platform.python_version(), 'platform': platform.platform(),
                              'Torch': torch.__version__, 'NumPy': np.__version__,
                              **runner.device_report(torch, device),
                              'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
                              'matmul_TF32': torch.backends.cuda.matmul.allow_tf32,
                              'cudnn_TF32': torch.backends.cudnn.allow_tf32,
                              'autocast_enabled': torch.is_autocast_enabled(), 'CPU_threads': torch.get_num_threads()}
        with runner.pinned_modules(context['files']) as (BigMHC, _):
            for arm, identity in context['models'].items():
                model = runner.load_checkpoint(torch, BigMHC, identity['directory'], identity['keys'], device=device)
                model.eval()
                if runner.state_hashes(model) != identity['state']:
                    raise ValueError('Reloaded tensor identity differs: ' + arm)
                if any(t.dtype != torch.float32 for t in model.state_dict().values()):
                    raise ValueError('Expected FP32 checkpoint')
                if any(m._forward_hooks for m in model.modules()):
                    raise ValueError('Unexpected forward hook')
                receipt['models'][arm]['strict_CUDA_tensor_reload_identical'] = True
                receipt['models'][arm]['eval_mode'] = not model.training
                del model
        torch.cuda.synchronize()
        receipt['peak_GPU_allocated_bytes'] = torch.cuda.max_memory_allocated()
        receipt['peak_GPU_reserved_bytes'] = torch.cuda.max_memory_reserved()
        receipt['forward_passes'] = 0
    else:
        prior = json.loads((directory / 'reports/models.json').read_text())
        if prior['protocol_sha256'] != receipt['protocol_sha256']:
            raise ValueError('Previous model gate differs')
        receipt = gates.inspect_source_schema(paths)
    receipt.update(stage=args.stage, completed_utc=datetime.now(timezone.utc).isoformat(),
                   elapsed_seconds=time.monotonic() - started,
                   peak_host_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                   git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   git_branch=subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
                   training_executed=False, inference_executed=False, outcomes_opened=False)
    receipt['implementation_sha256'] = {
        name: runner.raw.sha256_file(paths.repository_root / name) for name in (
            'src/stability_label_curation/bigmhc_independent_preflight.py',
            'scripts/preflight_bigmhc_independent.py')}
    with destination.open('x') as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('models', 'shared_inference_inputs')}, indent=2))


if __name__ == '__main__':
    main()
