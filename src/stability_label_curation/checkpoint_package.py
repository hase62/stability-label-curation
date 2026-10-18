"""Package manifest-selected checkpoint bytes; never import or execute ML code."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any, BinaryIO

from . import artifact_restore as restore
from . import netmhcstabpan_2016 as raw
from .paths import PROJECT_NAME, StoragePaths

PLAN = 'configs/bigmhc_windows_checkpoint_package.json'
Record = dict[str, Any]


def json_bytes(document: Record) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()


def mapping(relative_path: str, digest: str, size: int, *, area: str = 'runs') -> Record:
    restore.relative(relative_path)
    if area not in {'data', 'runs'} or not restore.sha(digest) or type(size) is not int or size < 0:
        raise ValueError('Invalid package file identity')
    return {'area': area, 'relative_path': relative_path, 'sha256': digest,
            'size_bytes': size, 'archive_path': f'codex/{area}/{PROJECT_NAME}/{relative_path}'}


def authenticated_json(record: Record, paths: StoragePaths) -> Record:
    """Read a small provenance document once, authenticated against retained evidence."""
    restore.relative(record['relative_path'])
    if record['area'] not in {'data', 'runs'} or not restore.sha(record['sha256']):
        raise ValueError('Invalid provenance reference')
    with raw._read_file(restore.destination(record, paths)) as source:
        blob = source.read(32 * 1024**2 + 1)
    if len(blob) > 32 * 1024**2 or hashlib.sha256(blob).hexdigest() != record['sha256']:
        raise ValueError('Provenance SHA256/size mismatch: ' + record['relative_path'])
    return json.loads(blob)


def select(plan: Record, paths: StoragePaths) -> Record:
    """Select only manifest-listed .lyr files and explicitly allowlisted metadata."""
    if plan.get('schema_version') != 1:
        raise ValueError('Invalid checkpoint package plan')
    inventory = authenticated_json(plan['inventory'], paths)
    indexed = {item['relative_path']: item for item in inventory['checkpoint_files']}
    checkpoints: list[Record] = []
    metadata: list[Record] = []
    runs: list[Record] = []
    for spec in plan['runs']:
        run = restore.relative(spec['relative_path'])
        evidence = inventory['runs'][run]['metadata']
        selected_metadata = {}
        for name in spec['metadata']:
            restore.relative(name)
            if not name.endswith('.json') or name.startswith('predictions/'):
                raise ValueError('Only explicit JSON provenance metadata may be packaged')
            identity = evidence[name]
            record = mapping(run + '/' + name, identity['sha256'], identity['size_bytes'])
            metadata.append(record)
            selected_metadata[name] = record
        manifest = authenticated_json(selected_metadata[spec['checkpoint_manifest']], paths)
        hashes = manifest[spec['checkpoint_map_key']]
        chosen = {name: digest for name, digest in hashes.items()
                  if name.startswith(spec['checkpoint_prefix'] + '/') and name.endswith('.lyr')}
        if len(chosen) != spec['expected_checkpoint_count']:
            raise ValueError('Unexpected checkpoint count in ' + run)
        for name, digest in sorted(chosen.items()):
            relative_path = run + '/' + restore.relative(name)
            previous = indexed[relative_path]
            if previous['sha256'] != digest:
                raise ValueError('Run manifest disagrees with checkpoint inventory')
            checkpoints.append(mapping(relative_path, digest, previous['size_bytes']))
        run_manifest = authenticated_json(selected_metadata['manifest.json'], paths)
        runs.append({'relative_path': run, 'run_id': run_manifest['run_id'],
                     'producing_commit': run_manifest['git']['commit_sha'],
                     'configuration': run_manifest['configuration'],
                     'checkpoint_manifest': selected_metadata[spec['checkpoint_manifest']],
                     'checkpoint_count': len(chosen)})
    if (len(checkpoints) != len(indexed)
            or {c['relative_path'] for c in checkpoints} != set(indexed)):
        raise ValueError('Package selection must cover the authenticated checkpoint inventory exactly')
    unique: dict[tuple[str, int], Record] = {}
    aliases: list[Record] = []
    for item in sorted(checkpoints, key=lambda m: m['relative_path']):
        key = (item['sha256'], item['size_bytes'])
        if key in unique:
            aliases.append({**item, 'source_archive_path': unique[key]['archive_path']})
        else:
            unique[key] = item
    if len(unique) != inventory['unique_checkpoint_hashes']:
        raise ValueError('Unique checkpoint count disagrees with authenticated inventory')
    # Confirm recorded duplicate groups rather than re-hashing alias source files.
    groups = {tuple(sorted(g['relative_paths'])): g['sha256']
              for g in inventory['local_duplicate_checkpoint_groups']}
    for alias in aliases:
        canonical = next(m for m in unique.values() if m['archive_path'] == alias['source_archive_path'])
        if groups.get(tuple(sorted((alias['relative_path'], canonical['relative_path'])))) != alias['sha256']:
            raise ValueError('Alias lacks retained duplicate-content evidence')
    if plan.get('alias_confirmation'):
        confirm = plan['alias_confirmation']
        record = next(m for m in metadata if m['relative_path'] == confirm['relative_path'])
        if authenticated_json(record, paths)[confirm['key']] is not True:
            raise ValueError('Historical alias verification is not affirmative')
    members = list(unique.values()) + metadata
    names = [m['archive_path'].casefold() for m in members + aliases]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate package destination')
    return {'schema_version': 1, 'project_name': PROJECT_NAME,
            'artifact_id': plan['artifact_id'], 'filename': plan['filename'],
            'selection_plan_sha256': hashlib.sha256(json_bytes(plan)).hexdigest(),
            'source_inventory': plan['inventory'], 'runs': runs,
            'members': members, 'aliases': aliases,
            'logical_checkpoint_count': len(checkpoints),
            'unique_checkpoint_count': len(unique),
            'unique_checkpoint_bytes': sum(m['size_bytes'] for m in unique.values()),
            'known_limitations': plan['known_limitations'],
            'training_executed': False, 'weights_deserialized': False,
            'external_publication': 'pending',
            'restore_command': 'python3 scripts/restore_artifacts.py restore ' + plan['artifact_id']}


class HashingReader:
    """Authenticate the exact stream consumed by tarfile, without a staging copy."""
    def __init__(self, source: BinaryIO):
        self.source = source
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        block = self.source.read(size)
        self.digest.update(block)
        self.size += len(block)
        return block


def add_file(bundle: tarfile.TarFile, member: Record, source: BinaryIO) -> None:
    info = tarfile.TarInfo(member['archive_path'])
    info.size = member['size_bytes']
    info.mode = 0o600
    reader = HashingReader(source)
    bundle.addfile(info, reader)
    if reader.size != member['size_bytes'] or reader.digest.hexdigest() != member['sha256']:
        raise ValueError('Packaged-file SHA256 mismatch: ' + member['relative_path'])


def package(plan: Record, paths: StoragePaths, *, registry_path: Path) -> Record:
    """Write one non-overwriting archive and its receipt, then register its identity."""
    registry = restore.read_json(registry_path)
    restore.load_registry(registry_path)
    if any(a['artifact_id'] == plan['artifact_id'] for a in registry['artifacts']):
        raise ValueError('Artifact already registered; existing packages are never replaced')
    filename = restore.relative(plan['filename'])
    if '/' in filename or not filename.endswith('.tar.gz'):
        raise ValueError('Expected a tar.gz basename')
    document = select(plan, paths)
    manifest_relative = 'artifacts/packages/' + filename.removesuffix('.tar.gz') + '.manifest.json'
    manifest_blob = json_bytes(document)
    manifest_member = mapping(manifest_relative, hashlib.sha256(manifest_blob).hexdigest(),
                              len(manifest_blob), area='data')
    members = document['members'] + [manifest_member]
    target = paths.project_data_dir / 'artifacts/packages' / filename
    sidecar = restore.destination(manifest_member, paths)
    receipt_path = target.with_name(filename + '.receipt.json')
    temporary = registry_path.with_name(registry_path.name + '.checkpoint-package.partial')
    if any(p.exists() or p.is_symlink() for p in (target, sidecar, receipt_path, temporary)):
        raise ValueError('Package, manifest or receipt already exists; preserved')
    artifact = {'artifact_id': plan['artifact_id'], 'version': '1', 'role': 'precomputed_output',
                'format': 'tar.gz', 'filename': filename, 'members': members,
                'aliases': document['aliases'], 'member_count': len(members),
                'expanded_size_bytes': sum(m['size_bytes'] for m in members),
                'exact_restoration': True, 'dependencies': [], 'regeneration_recipe': None,
                'producing_task': plan['producing_task'],
                'producing_commit': plan['approved_source_commit'],
                'locator': plan['locator'], 'external_publication': 'pending',
                'external_restoration_verified': False,
                'package_manifest': manifest_member,
                'unique_checkpoint_count': document['unique_checkpoint_count'],
                'logical_checkpoint_count': document['logical_checkpoint_count'],
                'known_limitations': document['known_limitations'],
                'local_package_relative_path': 'artifacts/packages/' + filename}
    with restore.atomic_destination(target) as output:
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=6) as gz:
            with tarfile.open(fileobj=gz, mode='w|', format=tarfile.GNU_FORMAT) as bundle:
                for member in document['members']:
                    with raw._read_file(restore.destination(member, paths)) as source:
                        before = os.fstat(source.fileno())
                        if not stat.S_ISREG(before.st_mode) or before.st_size != member['size_bytes']:
                            raise ValueError('Source is not the recorded regular file')
                        add_file(bundle, member, source)
                        after = os.fstat(source.fileno())
                        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                            raise ValueError('Source changed during packaging')
                add_file(bundle, manifest_member, io.BytesIO(manifest_blob))
    artifact['sha256'] = raw.sha256_file(target)
    artifact['size_bytes'] = target.stat().st_size
    if artifact['size_bytes'] > 2 * 1024**3:
        raise ValueError('Package exceeds restore transport bound; split the reviewed plan')
    receipt = {'schema_version': 1, 'artifact_id': plan['artifact_id'],
               'archive_relative_path': artifact['local_package_relative_path'],
               'sha256': artifact['sha256'], 'size_bytes': artifact['size_bytes'],
               'unique_checkpoint_count': document['unique_checkpoint_count'],
               'logical_checkpoint_count': document['logical_checkpoint_count'],
               'checkpoint_alias_count': len(document['aliases']),
               'all_stored_files_verified_while_packaging': True,
               'alias_evidence': 'Authenticated historical manifests and duplicate-content inventory; alias bytes not repackaged',
               'external_publication': 'pending', 'external_restoration_verified': False,
               'training_executed': False, 'original_checkpoints_modified': False}
    artifact['checksum_evidence'] = receipt
    with restore.atomic_destination(sidecar) as stream:
        stream.write(manifest_blob)
    with restore.atomic_destination(receipt_path) as stream:
        stream.write(json_bytes(receipt))
    registry['artifacts'].append(artifact)
    # Registry is the one intentionally edited Git file. Archives never enter Git.
    # Validate before replacing it, preserving the old registry on failure.
    stream = temporary.open('xb')
    try:
        with stream:
            stream.write(json_bytes(registry))
        restore.load_registry(temporary)
        os.replace(temporary, registry_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default=PLAN)
    parser.add_argument('--registry', default=restore.REGISTRY)
    parser.add_argument('--workspace-root')
    parser.add_argument('--dry-run', action='store_true', help='Manifest selection only; no writes or model reads')
    args = parser.parse_args(argv)
    try:
        paths = restore.storage(args.workspace_root)
        plan = restore.read_json(args.plan)
        report = select(plan, paths) if args.dry_run else package(plan, paths, registry_path=Path(args.registry))
        print(json_bytes(report).decode(), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as error:
        print(json_bytes({'success': False, 'error_type': type(error).__name__,
                          'error': str(error)}).decode(), end='')
        return 1
