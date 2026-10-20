"""Task 2.25 identity gates. No outcomes, predictions, or training entry point.

This module deliberately stops at source schema inspection. A released pMHC row
locator is not evidence of an original experimental assay's identity.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import zipfile

from . import bigmhc_baseline_runner as runner
from . import bigmhc_v4_audit as source
from .paths import StoragePaths

RUN_ID = 'task-2_25-independent-neoepitope-evaluation'
PROTOCOL = 'docs/BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md'
PROTOCOL_SHA256 = 'cb386443d768fb168366299ae7125aeec7115dda4e81da2dce62d90b4b99d250'
MODEL_MAPS = {
    'A': 'b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0',
    'S': '9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a',
    'P': '01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b',
}
ARCHIVE_SHA256 = '0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa'


def file_map_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def authenticate_models(paths: StoragePaths) -> tuple[dict, dict]:
    """Authenticate only the frozen final IM models and shared inference inputs."""
    if runner.raw.sha256_file(paths.repository_root / PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError('Locked protocol identity changed')
    config = json.loads((paths.repository_root / 'configs/bigmhc_fully_trained_auxiliary_task2_24.json').read_text())
    previous = paths.project_runs_dir / 'task-2_24-fully-trained-stability-auxiliary'
    frozen_path = previous / 'reports/frozen_models.json'
    outputs = json.loads((previous / 'reports/output_manifest.json').read_text())
    if runner.raw.sha256_file(frozen_path) != outputs['reports/frozen_models.json']:
        raise ValueError('Model freeze receipt changed')
    frozen = json.loads(frozen_path.read_text())
    if (frozen['status'] != 'frozen' or frozen['sealed_benchmark_accessed']
            or frozen['internal_development_evaluation_executed']
            or frozen['protocol_sha256'] != PROTOCOL_SHA256
            or (frozen['EL_epochs'], frozen['IM_epochs']) != (10, 20)):
        raise ValueError('Invalid pre-benchmark scientific freeze')
    for name, digest in frozen['scientific_hashes'].items():
        if runner.raw.sha256_file(paths.repository_root / name) != digest:
            raise ValueError('Frozen scientific configuration/code changed: ' + name)
    baseline = paths.project_runs_dir / 'task-2_23-el-multiepoch-baseline'
    baseline_receipt = baseline / 'reports/final_checkpoint.json'
    if runner.raw.sha256_file(baseline_receipt) != config['baseline']['reports']['final_checkpoint.json']:
        raise ValueError('A final IM receipt changed')
    a = json.loads(baseline_receipt.read_text())
    if (a['selected_EL_epoch'], a['IM_epochs'], a['IM_rows']) != (10, 20, 3428):
        raise ValueError('A is not the frozen full-IM fit')
    keys = frozen['models']['S']['checkpoints']['IM']['state_keys']
    if len(keys) != 36 or any('auxiliary' in key for key in keys):
        raise ValueError('Expected plain 36-tensor IM backbone')
    models, receipt = {}, {}
    checkpoints = {'A': (baseline, a), **{
        arm: (previous, frozen['models'][arm]['checkpoints']['IM']) for arm in ('S', 'P')}}
    for arm, (root, checkpoint) in checkpoints.items():
        directory = root / checkpoint['checkpoint']
        actual = runner.checkpoint_identity(directory, keys)
        digest = file_map_digest(actual)
        if actual != checkpoint['files'] or digest != MODEL_MAPS[arm]:
            raise ValueError('Frozen final IM checkpoint mismatch: ' + arm)
        if set(checkpoint['state']) != set(keys) or not checkpoint['strict_reload_identical']:
            raise ValueError('Invalid frozen tensor/reload identity: ' + arm)
        if arm in ('S', 'P') and checkpoint['state_keys'] != keys:
            raise ValueError('Different native tensor ordering')
        models[arm] = {'directory': directory, 'keys': keys, 'state': checkpoint['state']}
        receipt[arm] = {'checkpoint': str(directory.relative_to(paths.project_runs_dir)),
                        'file_map_sha256': digest, 'files': actual,
                        'state': checkpoint['state'], 'EL_epochs': 10, 'IM_epochs': 20,
                        'full_IM_training_rows': 3428, 'auxiliary_head_loaded': False}
    files = {}
    for name in ('reference', *('source_' + s for s in runner.SOURCES)):
        item = config['inputs'][name]
        root = paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir
        path = root / item['relative_path']
        if runner.raw.sha256_file(path) != item['sha256']:
            raise ValueError('Shared inference input changed: ' + name)
        files[name] = path
    return {'protocol_sha256': PROTOCOL_SHA256, 'models': receipt,
            'all_arms_share_source_and_HLA_mapping': True,
            'shared_inference_inputs': {name: config['inputs'][name] for name in files},
            'previous_independent_benchmark_access': frozen['sealed_benchmark_accessed']}, {
                'models': models, 'files': files}


def source_header(archive: zipfile.ZipFile, member: str) -> list[str]:
    """Read exactly one physical header line; never iterate data records."""
    if member not in {'im_test.csv', 'datasets/im_test.csv'}:
        raise ValueError('Only the published neoepitope benchmark member is allowed')
    matches = [entry for entry in archive.infolist() if entry.filename == member]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous neoepitope source member')
    with archive.open(matches[0]) as stream:
        line = stream.readline(65537)
    if len(line) > 65536 or not line.endswith(b'\n'):
        raise ValueError('Unbounded or incomplete source header')
    columns = next(csv.reader([line.decode('utf-8-sig').rstrip('\r\n')], strict=True))
    if len(set(columns)) != len(columns) or not {'mhc', 'pep', 'tgt'} <= set(columns):
        raise ValueError('Unsupported source schema')
    return columns


def inspect_source_schema(paths: StoragePaths) -> dict:
    """Authenticate archive bytes, inspect inventory/header, leave outcomes sealed."""
    path = paths.project_data_dir / 'bigmhc_v4/datasets.zip'
    if path.stat().st_size != source.PUBLISHED_BYTES or runner.raw.sha256_file(path) != ARCHIVE_SHA256:
        raise ValueError('Exact authentic published source is required')
    with zipfile.ZipFile(path) as archive:
        _, inventory = source.archive_inventory(archive)
        candidates = [entry for entry in archive.infolist()
                      if Path(entry.filename).name == 'im_test.csv']
        if len(candidates) != 1:
            raise ValueError('Missing or ambiguous neoepitope source member')
        entry = candidates[0]
        columns = source_header(archive, entry.filename)
    return {'release_DOI': '10.17632/dvmz6pkzvb.4', 'archive_sha256': ARCHIVE_SHA256,
            'archive_bytes': path.stat().st_size, 'archive_inventory': inventory,
            'source_member': entry.filename, 'source_member_CRC32': f'{entry.CRC:08x}',
            'source_member_uncompressed_bytes': entry.file_size, 'header': columns,
            'data_records_read': 0, 'outcome_values_read': 0,
            'published_prediction_values_read': 0,
            'row_to_original_assay_crosswalk': 'not established by header inspection',
            'eligibility_frozen': False}
