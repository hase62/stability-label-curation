"""Portable BigMHC input handoff verification and single-device run creation.

Verification uses only the standard library and never transfers files or imports
Torch. Training delegates to the existing bounded original-label runner.
"""
from pathlib import Path

from . import bigmhc_baseline_runner as runner
from . import netmhcstabpan_2016 as raw
from . import scientific_gate0_preflight as readers
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/bigmhc_gpu_worker_v0.json'
TRANSFER_MANIFEST = 'configs/bigmhc_gpu_worker_transfer.json'
FORBIDDEN = ('low_only', 'low_and_high', 'overrides', 'el_test', 'im_test', 'iedb', 'manafest')


def verify_inputs(*, config_path: str | Path | None = None,
                  manifest_path: str | Path | None = None, paths: StoragePaths | None = None) -> dict:
    """Verify the exact portable allowlist, sizes, SHA256s and parent provenance."""
    paths = paths or resolve_paths()
    config_path = config_path or paths.repository_root / CONFIG
    manifest_path = manifest_path or paths.repository_root / TRANSFER_MANIFEST
    config = runner.load_config(config_path)
    document = readers._json(manifest_path)
    entries = document.get('inputs', {})
    if (document.get('schema_version') != 1 or document.get('source_commit') != runner.SOURCE_COMMIT
            or set(entries) != runner.INPUTS or document.get('input_count') != len(entries)):
        raise ValueError('Invalid GPU handoff manifest identity or allowlist')
    identities = []
    for name, entry in sorted(entries.items()):
        relative = entry.get('relative_path', '')
        runner.adapter.pilot.registry._relative(relative)
        if (any(word in relative.lower() for word in FORBIDDEN) or Path(relative).suffix.lower() == '.zip'
                or entry.get('area') not in {'data', 'runs'} or type(entry.get('size_bytes')) is not int
                or entry['size_bytes'] < 0):
            raise ValueError('Unsafe or forbidden GPU handoff input: ' + name)
        specification = {key: entry[key] for key in ('area', 'relative_path', 'sha256')}
        if specification != config['inputs'][name]:
            raise ValueError('Transfer manifest disagrees with pinned configuration: ' + name)
        root = paths.project_data_dir if entry['area'] == 'data' else paths.project_runs_dir
        path = root / relative
        # O_NOFOLLOW for all path components, using the project's existing reader.
        with raw._read_file(path) as stream:
            stream.seek(0, 2)
            size = stream.tell()
        if size != entry['size_bytes'] or raw.sha256_file(path) != entry['sha256']:
            raise ValueError('GPU handoff size/SHA256 mismatch: ' + name)
        identities.append({'input_id': name, **entry})
    total = sum(item['size_bytes'] for item in identities)
    if total != document.get('total_bytes'):
        raise ValueError('GPU handoff total byte count mismatch')
    runner.resolve_inputs(config, paths)  # Also authenticates original views and parent records.
    return {'schema_version': 1, 'status': 'verified', 'input_count': len(identities),
            'total_bytes': total, 'inputs': identities,
            'transfer_manifest_sha256': raw.sha256_file(manifest_path),
            'config_sha256': raw.sha256_file(config_path), 'source_commit': runner.SOURCE_COMMIT,
            'read_only': True, 'sealed_or_corrected_payloads_opened': []}


def execute(*, run_id: str, config_path: str | Path | None = None,
            manifest_path: str | Path | None = None, paths: StoragePaths | None = None) -> dict:
    """Explicitly create one committed run, then delegate to the bounded runner."""
    paths = paths or resolve_paths()
    config_path = Path(config_path or paths.repository_root / CONFIG).absolute()
    config = runner.load_config(config_path)
    if config['device'] == 'cuda':
        runner.cuda_visibility()
    verification = verify_inputs(config_path=config_path, manifest_path=manifest_path, paths=paths)
    _, inputs = runner.resolve_inputs(config, paths)
    directory = runner.runs.create_run(
        paths=paths, run_id=run_id, kind='bigmhc_worker_smoke', seed=config['seed'],
        config=config_path, inputs=[item['path'] for item in inputs],
        argv=['bigmhc-worker', 'run', '--run-id', run_id, '--config', str(config_path)],
        description='Original-label condition A; one explicit CPU/CUDA device; engineering smoke only',
    )
    raw.write_report(directory / 'reports/transfer_verification.json', verification, paths=paths)
    return runner.run(config_path=config_path, out=directory, paths=paths)
