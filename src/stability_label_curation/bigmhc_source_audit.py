"""Pinned, bounded BigMHC source acquisition and offline static inspection.

External Python is parsed as syntax, never imported, compiled for execution, or
run. Dataset and checkpoint payloads are outside this utility's allowlist.
"""
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import ssl
from typing import Any, Sequence
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from . import scientific_gate0_preflight as readers
from .paths import PROJECT_NAME, StoragePaths, resolve_paths

ALLOWLIST = ('README.md', 'LICENSE', 'src/train.py', 'src/predict.py', 'src/cli.py',
             'src/bigmhc.py', 'src/dataset.py', 'src/mhcenc.py', 'src/mhcuid.py', 'src/encseq.py')
FILE_CAP = 256 * 1024
TOTAL_CAP = 2 * 1024 * 1024
CONFIG = 'configs/bigmhc_source_evidence.json'
REPOSITORY = 'https://github.com/KarchinLab/bigmhc'


def validate_commit(commit: str) -> str:
    if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Full lowercase pinned Git commit required')
    return commit


def validate_source_path(path: str) -> str:
    if path not in ALLOWLIST:
        raise ValueError('Source path outside exact allowlist: ' + str(path))
    return path


def source_url(commit: str, path: str) -> str:
    return 'https://raw.githubusercontent.com/KarchinLab/bigmhc/' + validate_commit(commit) + '/' + validate_source_path(path)


def validate_source_url(url: str, commit: str, path: str) -> None:
    if url != source_url(commit, path):
        raise ValueError('URL must identify the exact pinned allowlisted HTTPS source')


class _SourceRedirect(HTTPRedirectHandler):
    def __init__(self, commit: str, path: str):
        super().__init__()
        self.commit, self.path = commit, path

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source_url(newurl, self.commit, self.path)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _publish_bytes(directory: Path, name: str, data: bytes) -> None:
    """Private bounded writer: no replacing files or traversing symlinks."""
    if not name or Path(name).name != name or name in {'.', '..'}:
        raise ValueError('Unsafe snapshot filename')
    with raw._directory(directory, create=True) as parent:
        partial = '.' + name + '.' + secrets.token_hex(12) + '.partial'
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(partial, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            os.fsync(parent)
        finally:
            os.unlink(partial, dir_fd=parent)


def fetch_sources(commit: str, files: Sequence[str], *, paths: StoragePaths | None = None,
                  timeout: float = 30, opener_factory=None) -> dict[str, Any]:
    """Explicit acquisition API, not used by the read-only audit command.

    Call only for metadata-confirmed existing paths. Per-file responses are
    bounded to 256 KiB in memory; combined bytes, including reused files, <=2 MiB.
    Atomic publication occurs after complete validation, never by replacement.
    """
    storage = resolve_paths() if paths is None else paths
    storage.validate()
    expected_project = storage.data_root / PROJECT_NAME
    if storage.project_data_dir != expected_project or expected_project.resolve() != expected_project:
        raise ValueError('Project data directory must not alias another project')
    validate_commit(commit)
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError('Finite connection/read timeout required')
    if not files or len(set(files)) != len(files):
        raise ValueError('Unique nonempty source allowlist required')
    for path in files:
        validate_source_path(path)
    root = storage.project_data_dir / 'bigmhc_source' / commit
    if root.resolve() != root:
        raise ValueError('Source snapshot symlink escape')
    total = 0
    receipts = []
    for path in files:
        target = root / path
        url = source_url(commit, path)
        receipt = {'path': path, 'source_url': url, 'publisher_sha256': None}
        with raw._directory(target.parent, create=True) as parent:
            try:
                os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                exists = False
            else:
                exists = True
            if exists:
                with raw._read_file(target) as stream:
                    data = stream.read(FILE_CAP + 1)
                receipt.update(acquisition='reused', final_url=None, retrieved_at_utc=None,
                               http_status=None, server_metadata=None,
                               limitation='Existing bytes identified; no new HTTP retrieval metadata or publisher checksum verification.')
            else:
                opener = (opener_factory(commit, path) if opener_factory else
                          build_opener(HTTPSHandler(context=ssl.create_default_context()), _SourceRedirect(commit, path)))
                with opener.open(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=timeout) as response:
                    validate_source_url(response.geturl(), commit, path)
                    if response.status != 200:
                        raise ValueError('Unexpected source HTTP status')
                    length = response.headers.get('Content-Length')
                    if length is not None and (not re.fullmatch('[0-9]+', length) or int(length) > min(FILE_CAP, TOTAL_CAP - total)):
                        raise ValueError('Source Content-Length exceeds per-file/aggregate cap or is invalid')
                    if response.headers.get('Content-Encoding', 'identity') not in ('', 'identity'):
                        raise ValueError('Refusing encoded source-byte transformation')
                    chunks = []
                    size = 0
                    while chunk := response.read(min(65536, FILE_CAP + 1 - size)):
                        size += len(chunk)
                        if size > FILE_CAP or total + size > TOTAL_CAP:
                            raise ValueError('Per-file/aggregate source byte cap exceeded')
                        chunks.append(chunk)
                    data = b''.join(chunks)
                    if length is not None and len(data) != int(length):
                        raise ValueError('Source Content-Length differs from actual bytes')
                    receipt.update(acquisition='downloaded', final_url=response.geturl(), http_status=response.status,
                        retrieved_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        server_metadata={'content_length': length, 'content_type': response.headers.get('Content-Type'),
                            'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified')})
            if not data or len(data) > FILE_CAP or total + len(data) > TOTAL_CAP:
                raise ValueError('Per-file/aggregate source byte cap exceeded')
            text = data.decode('utf-8-sig')
            if text.lstrip().lower().startswith(('<!doctype html', '<html', 'version https://git-lfs.github.com/spec/')):
                raise ValueError('HTML or LFS pointer is not original source content')
            if path.endswith('.py'):
                parse_source(text, path)
            if not exists:
                _publish_bytes(target.parent, target.name, data)
            receipt.update(byte_size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                           local_checksum_status='verified_over_local_bytes_not_publisher_checksum')
            total += len(data)
            receipts.append(receipt)
    return {'repository': REPOSITORY, 'commit': commit, 'files': receipts,
            'source_bytes': total, 'scope': 'Exact allowlisted source only; no repository clone, datasets, weights or external-code execution'}


def parse_source(text: str, filename: str = '<synthetic>') -> ast.Module:
    if len(text.encode('utf-8')) > FILE_CAP:
        raise ValueError('Source parse bound exceeded')
    try:
        tree = ast.parse(text, filename=filename)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ValueError('Invalid Python source: ' + filename) from error
    if sum(1 for _ in ast.walk(tree)) > 40000:
        raise ValueError('Source AST bound exceeded')
    return tree


def syntax_index(tree: ast.Module) -> dict[str, Any]:
    """Small AST inventory with scope hashes and call locations, not source copies."""
    scopes = {}
    stack = []
    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            stack.append(node.name)
            for child in node.body:
                self.visit(child)
            stack.pop()

        def visit_FunctionDef(self, node):
            stack.append(node.name)
            name = '.'.join(stack)
            scopes[name] = {'line': node.lineno, 'end_line': node.end_lineno,
                'ast_sha256': hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
                'calls': [], 'literal_returns': []}
            for child in node.body:
                self.visit(child)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            name = '.'.join(stack)
            if name in scopes:
                target = ast.unparse(node.func)
                scopes[name]['calls'].append({'target': target[:160], 'line': node.lineno,
                    'keywords': sorted(k.arg or '**dynamic' for k in node.keywords)})
            self.generic_visit(node)

        def visit_Return(self, node):
            name = '.'.join(stack)
            if name in scopes:
                try:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, (str, int, bool, float, list, tuple, type(None))):
                        json.dumps(value, allow_nan=False)
                        scopes[name]['literal_returns'].append(value)
                except (ValueError, TypeError, RecursionError):
                    pass
            self.generic_visit(node)
    Visitor().visit(tree)
    return dict(sorted(scopes.items()))


def _function(tree: ast.AST | None, name: str) -> ast.FunctionDef | None:
    if tree is None:
        return None
    parts = name.split('.')
    node = tree
    for part in parts:
        node = next((n for n in getattr(node, 'body', []) if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == part), None)
        if node is None:
            return None
    return node if isinstance(node, ast.FunctionDef) else None


def _calls(node: ast.AST | None, target: str) -> list[ast.Call]:
    return [] if node is None else [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == target]


def static_facts(trees: dict[str, ast.Module]) -> dict[str, Any]:
    """Extract critical literal/call/predicate facts without executing any source."""
    train = _function(trees.get('src/train.py'), 'train')
    layer_func = _function(trees.get('src/bigmhc.py'), 'BigMHC.tllayers')
    layers = None
    if layer_func is not None:
        returns = [n for n in layer_func.body if isinstance(n, ast.Return)]
        if len(returns) == 1:
            try:
                candidate = ast.literal_eval(returns[0].value)
                if isinstance(candidate, list) and candidate and all(isinstance(s, str) for s in candidate):
                    layers = candidate
            except (ValueError, TypeError):
                pass
    skip = ast.dump(ast.parse('args.transferlearn and not tgt.sum()', mode='eval').body)
    skip_nodes = [] if train is None else [n for n in ast.walk(train) if isinstance(n, ast.If)
        and ast.dump(n.test) == skip and len(n.body) == 1 and isinstance(n.body[0], ast.Continue)]
    fractions = []
    for call in _calls(train, 'data.dataset.makebats'):
        for kw in call.keywords:
            if kw.arg == 'negfrac' and isinstance(kw.value, ast.IfExp):
                if (ast.unparse(kw.value.test) == 'args.transferlearn'
                        and isinstance(kw.value.body, ast.Constant) and kw.value.body.value is None
                        and isinstance(kw.value.orelse, ast.Constant)):
                    fractions.append(kw.value.orelse.value)
    return {'loss_constructor_call_lines': [n.lineno for n in _calls(train, 'torch.nn.BCEWithLogitsLoss')],
            'optimizer_constructor_call_lines': [n.lineno for n in _calls(train, 'torch.optim.AdamW')],
            'transfer_parameter_names_literal': layers,
            'all_negative_transfer_continue_lines': [n.lineno for n in skip_nodes],
            'EL_negfrac_literal_in_transfer_conditional': fractions,
            'external_code_executed': False, 'weights_opened_or_loaded': False,
            'interpretation': 'Syntax facts alone are not runtime proof; reviewed findings require matching file and AST identities.'}


def batch_count_diagnostic(positives: int, negatives: int, maxbat: int, negfrac: float = 0.99) -> dict[str, Any]:
    """Independent arithmetic of the reviewed slice counts, on hypothetical counts.

    No source import, source execution, rows, assignments, or learning occurs.
    Floating-point rounding intentionally follows the reviewed Python expression.
    It describes main-process makebats, not verified worker consumption.
    """
    if (any(type(n) is not int or n < 0 for n in (positives, negatives))
            or type(maxbat) is not int or maxbat <= 0 or positives + negatives > 10**9
            or not isinstance(negfrac, (int, float)) or not math.isfinite(negfrac) or not 0 < negfrac < 1):
        raise ValueError('Invalid hypothetical binary class counts or fraction')
    total = positives + negatives
    if not total:
        return {'status': 'empty_group', 'planned_batches': 0, 'actual_consumption_verified': False}
    q = math.ceil(total / maxbat)
    p = math.ceil(positives / q)
    n = int(min(math.ceil(negatives / q), p / (1 - negfrac) - p))
    batches = math.ceil(positives / p) if p else 0
    consumed_neg = min(negatives, batches * n)
    max_size = (min(p, positives) + min(n, negatives)) if batches else 0
    return {'status': 'group_omitted_no_positives' if not positives else 'analytical_main_process_batch_counts',
            'positives': positives, 'negatives': negatives, 'desired_negative_fraction': negfrac,
            'nominal_batch_count': q, 'positive_step': p, 'negative_step': n, 'planned_batches': batches,
            'positive_row_references': positives, 'negative_row_references': consumed_neg,
            'omitted_negative_references': negatives - consumed_neg, 'maximum_planned_batch_size': max_size,
            'may_exceed_requested_maxbat': max_size > maxbat, 'sampling_with_replacement': False,
            'all_groups_without_positives_consequence': 'Dataset.makebats indexes self.bats[0]; IndexError if no group emitted any batch.',
            'actual_consumption_verified': False}


@dataclass(frozen=True)
class SourceAuditResult:
    reports: dict[str, dict[str, Any]]
    inputs: list[dict[str, str]]


def inspect(*, paths: StoragePaths | None = None, snapshot: str | Path | None = None,
            evidence_path: str | Path | None = None) -> SourceAuditResult:
    storage = resolve_paths() if paths is None else paths
    evidence = readers._json(evidence_path or storage.repository_root / CONFIG)
    if evidence.get('schema_version') != 1 or evidence.get('repository_url') != REPOSITORY:
        raise ValueError('Unsupported BigMHC source evidence schema')
    published = evidence['published_data']
    if published.get('status') != 'publisher_metadata_only_payloads_not_acquired':
        raise ValueError('This source-only audit cannot certify dataset payloads')
    for item in published['published_checksums']:
        if (not re.fullmatch('[a-f0-9]{64}', item['publisher_reported_sha256'])
                or item.get('local_sha256') is not None or item.get('downloaded') is not False):
            raise ValueError('Publisher claims must remain separate from unavailable local payload verification')
    commit = validate_commit(evidence['commit'])
    root = Path(snapshot).expanduser().absolute() if snapshot else storage.project_data_dir / 'bigmhc_source' / commit
    files = evidence.get('source_files', [])
    if not files or len({f['path'] for f in files}) != len(files):
        raise ValueError('Missing/duplicate pinned source entries')
    for entry in files:
        validate_source_path(entry['path'])
        validate_source_url(entry['source_url'], commit, entry['path'])
    metadata = evidence.get('metadata_files', [])
    if len({f['path'] for f in metadata}) != len(metadata) or any(f['path'] not in {'repository_tree.json', 'source_acquisition_receipt.json'} for f in metadata):
        raise ValueError('Unallowlisted metadata path')
    inputs = []
    contents = {}
    total = 0
    for entry in [*files, *metadata]:
        if not re.fullmatch('[a-f0-9]{64}', entry['sha256']) or type(entry['byte_size']) is not int or not 0 < entry['byte_size'] <= FILE_CAP:
            raise ValueError('Invalid pinned source/metadata identity')
        path = root / entry['path']
        with raw._read_file(path) as stream:
            data = stream.read(FILE_CAP + 1)
        if len(data) != entry['byte_size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Pinned snapshot byte identity mismatch: ' + entry['path'])
        if entry in files:
            total += len(data)
            if total > TOTAL_CAP:
                raise ValueError('Combined source cap exceeded')
        inputs.append({'path': str(path), 'sha256': entry['sha256']})
        contents[entry['path']] = data
    trees = {p: parse_source(b.decode('utf-8-sig'), p) for p, b in contents.items() if p.endswith('.py')}
    indices = {p: syntax_index(t) for p, t in trees.items()}
    schema = {p: {'required_functions': names, 'missing': [n for n in names if n not in indices.get(p, {})]}
              for p, names in evidence['expected_functions'].items()}
    findings = []
    for item in evidence['reviewed_findings']:
        if item['category'] not in {'training', 'transfer', 'allele', 'inference'}:
            raise ValueError('Unsupported source finding category')
        checks = []
        for scope in item['scopes']:
            validate_source_path(scope['path'])
            actual = indices.get(scope['path'], {}).get(scope['function'])
            source = contents.get(scope['path'])
            checks.append({'path': scope['path'], 'function': scope['function'],
                'matches_reviewed_source_and_AST': actual is not None and source is not None
                    and hashlib.sha256(source).hexdigest() == scope['source_sha256']
                    and actual['ast_sha256'] == scope['ast_sha256'],
                'line': None if actual is None else actual['line'], 'end_line': None if actual is None else actual['end_line']})
        verified = bool(checks) and all(c['matches_reviewed_source_and_AST'] for c in checks)
        findings.append({'id': item['id'], 'category': item['category'], 'claim': item['claim'],
                         'status': 'locally_verified_static_path' if verified else 'unresolved_changed_or_missing_source',
                         'evidence': checks, 'limitations': item['limitations']})
    model_metadata = {'status': 'unavailable', 'directories': [], 'weights_fetched': False,
                      'checkpoint_ancestry_verified': False, 'training_exposure_verified': False}
    tree_data = None
    if 'repository_tree.json' in contents:
        tree_data = json.loads(contents['repository_tree.json'], object_pairs_hook=dtu_unique)
        if tree_data.get('sha') != commit or tree_data.get('truncated') is not False:
            raise ValueError('Repository tree commit/coverage mismatch')
        blobs = {n['path']: n for n in tree_data['tree'] if n['type'] == 'blob'}
        for entry in files:
            path = entry['path']
            data = contents[path]
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if path not in blobs or blobs[path]['sha'] != blob or blobs[path]['size'] != len(data):
                raise ValueError('Pinned GitHub tree/source blob identity mismatch: ' + path)
        directories = []
        for node in tree_data['tree']:
            name = node['path']
            if node['type'] == 'tree' and name.startswith('models/'):
                entries = [b['path'] for b in blobs.values() if b['path'].rsplit('/', 1)[0] == name]
                directories.append({'path': name, 'listed_file_count': len(entries),
                                    'lyr_filename_count': sum(p.endswith('.lyr') for p in entries)})
        model_metadata.update(status='pinned_repository_filename_metadata_only', directories=sorted(directories, key=lambda x: x['path']))
    if 'source_acquisition_receipt.json' in contents:
        receipt = json.loads(contents['source_acquisition_receipt.json'], object_pairs_hook=dtu_unique)
        if receipt['commit'] != commit or receipt['repository'] != REPOSITORY:
            raise ValueError('Source receipt commit identity mismatch')
        captured = {f['path']: f for f in receipt['files']}
        for item in files:
            r = captured.get(item['path'], {})
            if r.get('sha256') != item['sha256'] or r.get('byte_size') != item['byte_size']:
                raise ValueError('Acquisition receipt/source identity mismatch')
            validate_source_url(r['source_url'], commit, item['path'])
            if r.get('final_url') is not None:
                validate_source_url(r['final_url'], commit, item['path'])
    else:
        receipt = {'status': 'unavailable; local bytes do not establish retrieval metadata'}
    by_category = {name: [f for f in findings if f['category'] == name] for name in ('training', 'transfer', 'allele', 'inference')}
    sampler_verified = any(f['id'] == 'EL_batch_sampling' and f['status'] == 'locally_verified_static_path' for f in findings)
    examples = [batch_count_diagnostic(p, n, b) for p, n, b in [(0, 100, 32), (5, 0, 32), (1, 9999, 32), (1, 9999, 32768), (1, 3, 2), (100, 9900, 32)]] if sampler_verified else []
    reports = {
        'bigmhc_source_inventory.json': {'schema_version': 1, 'repository': REPOSITORY, 'commit': commit,
            'snapshot_relative_path': 'bigmhc_source/' + commit, 'files': files, 'source_byte_count': total,
            'metadata_files': metadata, 'schema_checks': schema, 'AST_scopes': indices,
            'acquisition_receipt': receipt, 'source_code_executed': False, 'weight_or_dataset_payloads_acquired': False},
        'bigmhc_training_semantics.json': {'findings': by_category['training'], 'static_facts': static_facts(trees),
            'hypothetical_count_examples': examples, 'examples_are_observed_training_coverage': False,
            'fair_comparison_controls': evidence['fair_comparison_controls'], 'runtime_uncertainties': evidence['runtime_uncertainties'],
            'experimental_sampling_policy_selected': False},
        'bigmhc_transfer_lineage.json': {'findings': by_category['transfer'] + by_category['inference'],
            'model_directory_metadata': model_metadata, 'minimum_future_lineage_metadata': evidence['minimum_lineage_metadata'],
            'code_inheritance_is_verified_checkpoint_ancestry': False},
        'bigmhc_allele_mapping_risks.json': {'findings': by_category['allele'], 'future_adapter_recommendation': evidence['allele_adapter'],
            'coverage_of_72_DTU_alleles_verified': False, 'unknown_alleles_are_accepted_as_equivalent': False},
        'bigmhc_published_data_manifest.json': evidence['published_data'],
        'bigmhc_unresolved_exposure.json': {'limitations': evidence['unresolved_exposure'],
            'source_license': evidence['licenses'], 'publication_evidence': evidence['publication_evidence'],
            'runtime_findings_are_empirically_verified': False, 'checkpoint_exposure_cleared': False}}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Snapshot changed during source audit')
    return SourceAuditResult(reports, inputs)


def dtu_unique(pairs):
    """Duplicate-key rejection shared with the existing evidence infrastructure."""
    from .dtu2016_source_audit import _unique_json
    return _unique_json(pairs)


def write_reports(result: SourceAuditResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    directory = Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name != 'reports' or directory.parent.parent != storage.project_runs_dir:
        raise ValueError('Reports require an existing authorized project run reports directory')
    manifest = runs.load_manifest(directory.parent.name, paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Run must record every unchanged source/metadata input')
    names = [*result.reports, 'execution_verification.json']
    with raw._directory(directory) as parent:
        for name in names:
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError('Report already exists: ' + name)
    for name, doc in result.reports.items():
        raw.write_report(directory / name, doc, paths=storage)
    receipt = {'code_commit': manifest['git']['commit_sha'], 'input_artifacts': result.inputs,
        'reports': {name: raw.sha256_file(directory / name) for name in result.reports},
        'source_commit': result.reports['bigmhc_source_inventory.json']['commit'],
        'scope': 'Static source/evidence audit only; no external execution, data payloads, weights, corrections or training'}
    for item in result.inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Snapshot changed before completion receipt')
    raw.write_report(directory / 'execution_verification.json', receipt, paths=storage)
    return receipt
