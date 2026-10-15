"""Streaming, reversible training-row candidates; never applied to publisher labels."""
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import secrets
import sys
from typing import Any, Iterable, Mapping
import zipfile
import zlib

from . import bigmhc_v4_audit as bigmhc
from . import stability_teacher as teacher
from . import netmhcstabpan_2016 as raw
from . import observation_registry as registry
from . import scientific_gate0_preflight as readers
from . import sequence_leakage_audit as leakage
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/pseudolabel_pilot_v0.json'
VERSION = 'pseudolabel_pilot_v0'
MEMBERS = ('el_train.csv', 'im_train.csv')
INPUTS = {'archive', 'teacher', 'teacher_manifest', 'teacher_receipt', 'partition', 'registry', 'mapping'}
EXPOSURES = ('teacher_fit_exact_peptide', 'teacher_fit_exact_pair', 'teacher_fit_within_one_mismatch_peptide',
             'teacher_fit_within_one_mismatch_pair', 'DTU_source_exact_peptide', 'DTU_source_exact_pair')
FIELDS = ['source_file', 'row_index', 'source_line_number', 'source_row_id', 'source_row_sha256',
          'original_peptide', 'original_hla', 'resolved_hla', 'original_label', 'predicted_half_life_hours',
          'stability_category', 'proposed_pseudolabel', 'candidate_action', 'model_status',
          'teacher_version', 'teacher_model_sha256', 'rule_version', *EXPOSURES]
OUTPUTS = {member: (f'predictions/{member[:-4]}_teacher_scores.csv.gz',
                    f'processed/{member[:-4]}_pseudolabel_overrides.csv.gz') for member in MEMBERS}
BINS = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0)


def load_config(path: str | Path) -> dict[str, Any]:
    config = readers._json(path)
    if (config.get('schema_version') != 1 or config.get('rule_version') != VERSION
            or config.get('low_hours_exclusive') != 1.0 or config.get('high_hours_inclusive') != 10.0
            or config.get('large_class_change_fraction_warning') != 0.2
            or set(config.get('inputs', {})) != INPUTS or set(config.get('members', {})) != set(MEMBERS)):
        raise ValueError('Invalid fixed exploratory pilot configuration')
    for item in config['inputs'].values():
        registry._relative(item['relative_path'])
        if item['area'] not in {'data', 'runs'} or not _sha(item['sha256']):
            raise ValueError('Invalid portable input identity')
    if not _sha(config['teacher_commit_sha'], 40) or type(config['expected_trained_HLA_models']) is not int:
        raise ValueError('Invalid Teacher identity')
    for item in config['members'].values():
        if not _sha(item['sha256']) or type(item['rows']) is not int or not 0 <= item['rows'] <= 20000000:
            raise ValueError('Invalid authorized member expectation')
    return config


def _sha(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def resolve_inputs(config: dict[str, Any], paths: StoragePaths, files: Mapping[str, str | Path] | None = None):
    overrides = files or {}
    if set(overrides) - INPUTS:
        raise ValueError('Unknown pilot input override')
    if 'archive' not in overrides:
        source = load_manifest(paths=paths).get('bigmhc_v4')
        item = config['inputs']['archive']
        if item != {'area': 'data', 'relative_path': source.target_relative_path, 'sha256': source.expected_sha256}:
            raise ValueError('Archive identity must agree with the authoritative source registry')
    resolved, inputs = {}, []
    for name, item in config['inputs'].items():
        root = paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir
        path = Path(overrides[name]).expanduser().absolute() if name in overrides else root / item['relative_path']
        if raw.sha256_file(path) != item['sha256']:
            raise ValueError('Pilot input SHA256 mismatch: ' + name)
        resolved[name] = path
        inputs.append({'path': str(path), 'sha256': item['sha256']})
    return resolved, inputs


def category_and_action(label: str, hours: float) -> tuple[str, str, str]:
    if label not in {'0', '1'} or not math.isfinite(hours) or hours < 0:
        raise ValueError('Invalid binary source label or nonnegative prediction')
    category = 'LOW' if hours < 1.0 else 'HIGH' if hours >= 10.0 else 'MID'
    action = 'low_positive_to_negative' if category == 'LOW' and label == '1' else (
        'high_negative_to_positive' if category == 'HIGH' and label == '0' else 'no_change')
    proposed = '0' if action == 'low_positive_to_negative' else '1' if action == 'high_negative_to_positive' else label
    return category, action, proposed


def candidate_for_policy(candidate: Mapping[str, Any], policy: str) -> bool:
    """Filter saved candidates without rescoring; never edits a label or assigns a split."""
    if policy not in {'low_only', 'low_and_high'} or candidate['source_file'] not in MEMBERS:
        raise ValueError('Only authorized training members and supported rule policies are selectable')
    _, action, proposed = category_and_action(candidate['original_label'], float(candidate['predicted_half_life_hours']))
    if candidate['candidate_action'] != action or candidate['proposed_pseudolabel'] != proposed:
        raise ValueError('Candidate action disagrees with frozen rules')
    return action == 'low_positive_to_negative' or (policy == 'low_and_high' and action == 'high_negative_to_positive')


class OverrideGuard:
    """Future adapters must additionally supply their explicitly authorized row IDs."""
    def __init__(self, member: str, archive_sha256: str, model_sha256: str):
        if member not in MEMBERS:
            raise ValueError('Overrides are forbidden outside the two training members')
        self.member, self.archive, self.model, self.last = member, archive_sha256, model_sha256, 0

    def check(self, candidate: Mapping[str, Any], authorized_row_ids: set[str]) -> None:
        index = int(candidate['row_index'])
        if (candidate['source_file'] != self.member or index <= self.last or candidate['rule_version'] != VERSION
                or candidate['teacher_model_sha256'] != self.model
                or candidate['source_row_id'] != row_id(self.archive, self.member, index)
                or candidate['source_row_id'] not in authorized_row_ids):
            raise ValueError('Duplicate, unordered, unauthenticated or unauthorized training-row override')
        if not candidate_for_policy(candidate, 'low_and_high'):
            raise ValueError('Override does not change its original label')
        self.last = index


def row_id(archive_sha: str, member: str, index: int) -> str:
    if member not in MEMBERS or type(index) is not int or index < 1:
        raise ValueError('Invalid training-row coordinate')
    return 'bmhc_' + hashlib.sha256(f'{archive_sha}\0{member}\0{index}'.encode('utf-8')).hexdigest()


class NeighborIndex:
    """The Task 2.0 masked-position predicate, queried against a small fixed source."""
    def __init__(self, fit_pairs: set[tuple[str, str]], source_pairs: set[tuple[str, str]]):
        self.fit_pairs, self.source_pairs = fit_pairs, source_pairs
        self.fit_peptides = {p for p, _ in fit_pairs}
        self.source_peptides = {p for p, _ in source_pairs}
        if len(self.source_peptides) > leakage.MAX_WINDOWS:
            raise ValueError('Source neighborhood index bound exceeded')
        self.signatures = defaultdict(set)
        for peptide, hla in sorted(fit_pairs):
            for position in range(9):
                self.signatures[position, peptide[:position] + peptide[position+1:]].add(hla)

    def query(self, peptide: str, hla: str) -> dict[str, bool]:
        any_neighbor = pair_neighbor = False
        for position in range(9):
            alleles = self.signatures.get((position, peptide[:position] + peptide[position+1:]), ())
            any_neighbor |= bool(alleles)
            pair_neighbor |= hla in alleles
        return dict(zip(EXPOSURES, (peptide in self.fit_peptides, (peptide, hla) in self.fit_pairs,
            any_neighbor, pair_neighbor, peptide in self.source_peptides, (peptide, hla) in self.source_pairs)))


@dataclass
class Context:
    model: teacher.Teacher
    mapping: dict[str, str]
    neighbors: NeighborIndex
    model_sha256: str
    archive_sha256: str
    provenance: dict[str, Any]


def load_context(config: dict[str, Any], files: dict[str, Path]) -> Context:
    model = teacher.load_model(files['teacher'])
    manifest = runs.validate_manifest(readers._json(files['teacher_manifest']))
    receipt = readers._json(files['teacher_receipt'])
    model_sha = config['inputs']['teacher']['sha256']
    provenance = model.document['provenance']
    if (receipt['model_sha256'] != model_sha or manifest['git']['commit_sha'] != config['teacher_commit_sha']
            or provenance['code_commit'] != manifest['git']['commit_sha']
            or receipt['config_sha256'] != manifest['configuration']['file']['sha256']
            or provenance['config_sha256'] != receipt['config_sha256']
            or provenance['inputs'] != receipt['input_artifacts']
            or any(item not in manifest['data_provenance']['input_artifacts'] for item in provenance['inputs'])
            or config['inputs']['registry']['sha256'] not in {item['sha256'] for item in provenance['inputs']}
            or model.document['config']['registry_sha256'] != config['inputs']['registry']['sha256']
            or provenance['partition_sha256'] != config['inputs']['partition']['sha256']
            or receipt['report_sha256']['teacher_train_val_partition.json'] != provenance['partition_sha256']):
        raise ValueError('Frozen Teacher output receipt/manifest lineage mismatch')
    trained = {h for h, m in model.document['alleles'].items() if m['status'] == 'trained'}
    if len(trained) != config['expected_trained_HLA_models']:
        raise ValueError('Frozen Teacher supported-model count differs')
    mapping, candidates = {}, defaultdict(list)
    evidence = readers._json(files['mapping'])
    for item in evidence['data_HLA_mapping']:
        candidates[item['original_HLA']].append(item)
    for original, entries in candidates.items():
        resolved = entries[0]['canonical_two_field_HLA']
        if (resolved is None or bigmhc.canonical_hla(original) != resolved
                or any(not e['unique_canonical_reference_match'] or e['canonical_two_field_HLA'] != resolved for e in entries)):
            continue
        mapping[original] = resolved
    rows, _ = teacher.load_population(files['registry'], model.document['config'])
    partition = readers._json(files['partition'])
    teacher.verify_partition(rows, partition)
    groups = {a['observation_id']: a['partition'] for a in partition['assignments']}
    fit_rows = [o for o in rows if groups[o.observation_id] == 'train' and o.original_allele in trained]
    if Counter(o.original_allele for o in fit_rows) != {h: model.document['alleles'][h]['training_rows'] for h in trained}:
        raise ValueError('Actual fitted source rows differ from model support metadata')
    fit_pairs = {(o.original_peptide, o.original_allele) for o in fit_rows}
    source_pairs = {(o.original_peptide, o.original_allele) for o in rows}
    return Context(model, mapping, NeighborIndex(fit_pairs, source_pairs), model_sha,
        config['inputs']['archive']['sha256'], {'fitted_training_observations': len(fit_rows),
        'ordinary_DTU_source_observations': len(rows), 'fitted_HLA_models': len(trained),
        'neighbor_rule': 'Aligned canonical nine-mer Hamming distance <=1, including exact identity; no indel or fragment search',
        'overlap_scope': 'Counts among scored BigMHC training rows; both any-HLA peptide and same-HLA pair exposure',
        'warning': 'Teacher-source exposure is not independent evidence; no exposure-based exclusion or final split is applied'})


class _HashSink:
    def __init__(self, stream=None):
        self.stream, self.digest, self.size = stream, hashlib.sha256(), 0

    def write(self, data):
        if self.stream is not None:
            self.stream.write(data)
        self.digest.update(data)
        self.size += len(data)
        return len(data)

    def flush(self):
        if self.stream is not None:
            self.stream.flush()

    def tell(self):
        return self.size


@contextmanager
def _csv_artifact(path: Path | None):
    """Atomic nonreplacing gzip publication, or a bounded-memory hash-only replay."""
    with ExitStack() as stack:
        parent = stream = partial = None
        if path is not None:
            parent = stack.enter_context(raw._directory(path.parent))
            try:
                os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError('Existing scoring artifact preserved: ' + path.name)
            partial = '.' + path.name + '.' + secrets.token_hex(12) + '.partial'
            descriptor = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            stream = stack.enter_context(os.fdopen(descriptor, 'wb'))
        sink = _HashSink(stream)
        try:
            with gzip.GzipFile(filename='', mode='wb', fileobj=sink, compresslevel=6, mtime=0) as compressed:
                with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as text:
                    writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator='\n')
                    writer.writeheader()
                    yield writer, sink
            if stream is not None:
                stream.flush(); os.fsync(stream.fileno())
                os.link(partial, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
        finally:
            if partial is not None:
                os.unlink(partial, dir_fd=parent)


def _new_stats():
    return {'total': 0, 'eligible': 0, 'labels': Counter(), 'eligible_labels': Counter(), 'unsupported': Counter(),
            'categories': Counter(), 'actions': Counter(), 'exposure': Counter(), 'candidate_exposure': Counter(),
            'bins': Counter(), 'sum_hours': 0.0, 'min_hours': None, 'max_hours': None}


def _finish(stats):
    low, high = (stats['actions'][a] for a in ('low_positive_to_negative', 'high_negative_to_positive'))
    def fraction(n, denominator):
        return None if denominator == 0 else n / denominator
    return {'total_training_rows': stats['total'], 'teacher_eligible_rows': stats['eligible'],
        'original_label_counts': dict(sorted(stats['labels'].items())),
        'eligible_original_label_counts': dict(sorted(stats['eligible_labels'].items())),
        'unsupported_by_reason': dict(sorted(stats['unsupported'].items())),
        'eligible_original_label_by_stability_category': dict(sorted(stats['categories'].items())),
        'candidate_counts': {'low_positive_to_negative': low, 'high_negative_to_positive': high, 'total': low + high},
        'candidate_fractions': {'LOW_of_eligible_original_positives': fraction(low, stats['eligible_labels']['1']),
            'HIGH_of_eligible_original_negatives': fraction(high, stats['eligible_labels']['0']),
            'total_of_eligible': fraction(low + high, stats['eligible']), 'total_of_all_training_rows': fraction(low + high, stats['total'])},
        'prediction_distribution_hours': {'minimum': stats['min_hours'], 'maximum': stats['max_hours'],
            'mean': fraction(stats['sum_hours'], stats['eligible']),
            'bin_counts': {name: stats['bins'][name] for name in ('[0,1)', '[1,2)', '[2,5)', '[5,10)', '[10,20)', '[20,50)', '[50,infinity)')}},
        'source_exposure_scored_rows': {name: stats['exposure'][name] for name in EXPOSURES},
        'source_exposure_candidate_rows': {name: stats['candidate_exposure'][name] for name in EXPOSURES}}


def score_stream(member: str, records: Iterable[tuple[int, list[str]]], context: Context, score_writer, override_writer):
    if member not in MEMBERS:
        raise ValueError('Only training members may be scored')
    iterator = iter(records)
    try:
        previous_line, header = next(iterator)
    except StopIteration:
        raise ValueError('Empty training CSV')
    expected = ['mhc', 'pep', 'tgt'] + (['rand'] if member == 'im_train.csv' else [])
    if header != expected:
        raise ValueError('Training member schema changed')
    if type(previous_line) is not int or previous_line < 1:
        raise ValueError('Invalid source header line')
    total, by_hla = _new_stats(), defaultdict(_new_stats)
    for index, (line, fields) in enumerate(iterator, 1):
        if line <= previous_line or len(fields) != len(header) or index > 20000000:
            raise ValueError('Duplicate row index, malformed CSV or streaming row cap exceeded')
        previous_line = line
        hla, peptide, label = fields[:3]
        if label not in {'0', '1'} or not hla or len(hla) > 128 or not peptide or len(peptide) > 100:
            raise ValueError('Invalid immutable training row; no silent dropping or label normalization')
        if len(by_hla) > 1000:
            raise ValueError('HLA aggregate bound exceeded')
        groups = (total, by_hla[hla])
        for stats in groups:
            stats['total'] += 1; stats['labels'][label] += 1
        resolved = context.mapping.get(hla)
        reason = 'unsupported_peptide_length' if len(peptide) != 9 else (
            'noncanonical_amino_acid' if any(c not in teacher.ALPHABET for c in peptide) else (
            'unverified_or_ambiguous_HLA' if resolved is None else None))
        prediction = None
        if reason is None:
            try:
                prediction = context.model.predict_stability(peptide, resolved)
                reason = prediction['unsupported_reason'] if prediction['model_status'] != 'ok' else None
                if reason is None and (not isinstance(prediction['predicted_half_life_hours'], (int, float))
                        or not math.isfinite(prediction['predicted_half_life_hours']) or prediction['predicted_half_life_hours'] < 0):
                    reason = 'nonfinite_or_negative_prediction'
            except (ValueError, ArithmeticError):
                reason = 'numerical_prediction_failure'
        if reason is not None:
            for stats in groups:
                stats['unsupported'][reason] += 1
            continue
        hours = prediction['predicted_half_life_hours']
        category, action, proposed = category_and_action(label, hours)
        exposure = context.neighbors.query(peptide, resolved)
        row_hash = hashlib.sha256(json.dumps([header, fields], ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
        output = dict(zip(FIELDS[:9], (member, index, line, row_id(context.archive_sha256, member, index), row_hash,
                                     peptide, hla, resolved, label)))
        output.update(predicted_half_life_hours=repr(hours), stability_category=category, proposed_pseudolabel=proposed,
            candidate_action=action, model_status='ok', teacher_version=teacher.VERSION,
            teacher_model_sha256=context.model_sha256, rule_version=VERSION, **{k: int(v) for k, v in exposure.items()})
        score_writer.writerow(output)
        if action != 'no_change':
            override_writer.writerow(output)
        bin_index = sum(hours >= bound for bound in BINS)
        bin_name = ('[0,1)', '[1,2)', '[2,5)', '[5,10)', '[10,20)', '[20,50)', '[50,infinity)')[bin_index]
        for stats in groups:
            stats['eligible'] += 1; stats['eligible_labels'][label] += 1
            stats['categories'][label + '/' + category] += 1; stats['actions'][action] += 1
            stats['exposure'].update(k for k, value in exposure.items() if value)
            if action != 'no_change':
                stats['candidate_exposure'].update(k for k, value in exposure.items() if value)
            stats['bins'][bin_name] += 1; stats['sum_hours'] += hours
            stats['min_hours'] = hours if stats['min_hours'] is None else min(stats['min_hours'], hours)
            stats['max_hours'] = hours if stats['max_hours'] is None else max(stats['max_hours'], hours)
    result = _finish(total)
    result.update(source_header=header, scored_HLA_identifiers=sum(s['eligible'] > 0 for s in by_hla.values()),
        by_original_HLA={hla: _finish(stats) for hla, stats in sorted(by_hla.items())},
        large_change_warnings=[name for name in ('LOW_of_eligible_original_positives', 'HIGH_of_eligible_original_negatives')
                               if result['candidate_fractions'][name] is not None and result['candidate_fractions'][name] >= 0.2],
        unsupported_reason_precedence='Length, canonical residues, verified mapping, Teacher support, finite prediction; reasons are mutually exclusive')
    assert result['total_training_rows'] == result['teacher_eligible_rows'] + sum(result['unsupported_by_reason'].values())
    return result


def experiment_plan(context: Context) -> dict[str, Any]:
    return {'schema_version': 1, 'rule_version': VERSION, 'teacher_model_sha256': context.model_sha256,
        'archive_sha256': context.archive_sha256, 'thresholds_hours': {'LOW_strictly_below': 1.0, 'HIGH_at_least': 10.0},
        'default_policy': 'low_and_high', 'available_policies': ['low_only', 'low_and_high'],
        'conditions': {name: {'EL_overrides': OUTPUTS['el_train.csv'][1] if el else None,
                              'IM_overrides': OUTPUTS['im_train.csv'][1] if im else None}
                       for name, el, im in (('A', False, False), ('B', True, False), ('C', False, True), ('D', True, True))},
        'future_adapter_contract': ['Require an explicitly authorized training-row ID set from the subsequently established split protocol',
            'Verify archive/member identity, row index, original-field row hash, original label and frozen Teacher identity before application',
            'No override for validation, test, unsupported or unauthorized rows; absence defaults to original label',
            'Keep original labels and candidate reasons; these are modeling pseudolabels, not verified biological truth'],
        'experiments_trained': False, 'overrides_applied_to_source_data': False}


def pilot(*, config_path: str | Path, out: str | Path, paths: StoragePaths | None = None,
          files: Mapping[str, str | Path] | None = None, verify_existing: bool = False) -> dict[str, Any]:
    storage = paths or resolve_paths()
    config = load_config(config_path)
    resolved, inputs = resolve_inputs(config, storage, files)
    directory, manifest = teacher._run(out, storage)
    if (manifest['configuration']['file'] != {'path': str(Path(config_path).absolute()), 'sha256': raw.sha256_file(config_path)}
            or any(item not in manifest['data_provenance']['input_artifacts'] for item in inputs)):
        raise ValueError('Pilot run must record actual configuration and all unchanged inputs')
    context = load_context(config, resolved)
    report_paths = ('pseudolabel_summary.json', 'pseudolabel_experiment_plan.json', 'execution_verification.json')
    if not verify_existing and any((directory / 'reports' / name).exists() for name in report_paths):
        raise FileExistsError('Existing pilot reports preserved')
    results, identities, opened, artifacts = {}, {}, [], {}
    with raw._read_file(resolved['archive']) as stream, zipfile.ZipFile(stream) as archive, ExitStack() as stack:
        if resolved['archive'].stat().st_size > bigmhc.ARCHIVE_CAP:
            raise ValueError('Archive byte cap exceeded')
        members, _ = bigmhc.archive_inventory(archive)  # Central-directory metadata only.
        writers = {}
        for member in MEMBERS:
            writers[member] = []
            for relative in OUTPUTS[member]:
                writer, sink = stack.enter_context(_csv_artifact(None if verify_existing else directory / relative))
                writers[member].append(writer); artifacts[relative] = sink
        for member in MEMBERS:
            records = bigmhc._rows(archive, members[member], member, opened, identities)
            results[member] = score_stream(member, records, context, *writers[member])
            if (identities[member]['sha256'] != config['members'][member]['sha256']
                    or results[member]['total_training_rows'] != config['members'][member]['rows']):
                raise ValueError('Actual authorized CSV identity/count differs from locked input')
        for item in inputs:
            if raw.sha256_file(item['path']) != item['sha256']:
                raise ValueError('Immutable scoring input changed')
    hashes = {name: {'sha256': sink.digest.hexdigest(), 'bytes': sink.size} for name, sink in artifacts.items()}
    summary = {'schema_version': 1, 'rule_version': VERSION, 'inputs': inputs, 'source_member_identities': identities,
        'opened_members': opened, 'validation_or_test_members_opened': [], 'members': results, 'artifacts': hashes,
        'source_exposure_provenance': context.provenance,
        'prediction_distribution_convention': 'Exact streamed counts in fixed left-closed/right-open hour bins; min/max/mean; no sampled quantiles',
        'reproducibility': {'python': sys.version, 'zlib': zlib.ZLIB_VERSION, 'gzip_mtime': 0, 'gzip_filename': '', 'compression_level': 6},
        'large_change_warning_convention': 'Flag >=20% of an eligible original class; exploratory warning only, never adjusts thresholds',
        'interpretation': 'Provisional training pseudolabel candidates; no claimed accuracy improvement, source-label edits or model-performance evaluation'}
    documents = {'pseudolabel_summary.json': summary, 'pseudolabel_experiment_plan.json': experiment_plan(context)}
    for relative, identity in hashes.items():
        if raw.sha256_file(directory / relative) != identity['sha256']:
            raise ValueError('Scoring artifact differs from deterministic stream: ' + relative)
    if verify_existing:
        for name, document in documents.items():
            with raw._read_file(directory / 'reports' / name) as stream:
                if stream.read() != raw.json_report(document).encode('utf-8'):
                    raise ValueError('Offline aggregate replay differs: ' + name)
    else:
        for name, document in documents.items():
            raw.write_report(directory / 'reports' / name, document, paths=storage)
        raw.write_report(directory / 'reports/execution_verification.json', {
            'code_commit': manifest['git']['commit_sha'], 'inputs': inputs, 'config_sha256': raw.sha256_file(config_path),
            'artifacts': hashes, 'report_sha256': {name: raw.sha256_file(directory / 'reports' / name) for name in documents},
            'teacher_frozen': True, 'source_labels_modified': False, 'threshold_optimization_performed': False,
            'members_opened': opened, 'scope': 'Training-row scoring and reversible candidates only'}, paths=storage)
    return {'run': str(directory), 'verified_existing': verify_existing, 'artifacts': hashes,
            'members': {name: {key: value for key, value in result.items() if key != 'by_original_HLA'} for name, result in results.items()}}
