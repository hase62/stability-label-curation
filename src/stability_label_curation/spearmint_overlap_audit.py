"""Read-only SPEARMINT Stage 2/DTU overlap evidence; never execute external code."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
import csv
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
from typing import Any

from . import netmhcstabpan_2016 as raw
from . import dtu2016_source_audit as dtu
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import PROJECT_NAME, StoragePaths, resolve_paths

LOCK_PATH = 'configs/external_repositories.lock.json'
EVIDENCE_PATH = 'configs/spearmint_stage2_evidence.json'
SPLITS = ('train', 'val', 'test')
TOLERANCES = ('0', '0.000000000001', '0.000000001', '0.000001', '0.01')
ROW_ORIGIN = 'published_raw_stability_table_row_origin_unverified'


def _relative(value: str) -> str:
    if (not isinstance(value, str) or PurePosixPath(value).is_absolute() or '\\' in value
            or ':' in value or any(part in {'', '.', '..'} for part in value.split('/'))):
        raise ValueError('Unsafe repository-relative path')
    return value


def _json(path: str | Path) -> dict[str, Any]:
    with raw._read_file(path) as stream:
        return json.load(stream, object_pairs_hook=dtu._unique_json)


def validate_evidence(evidence: Any) -> dict[str, Any]:
    fields = {'schema_version', 'source_id', 'commit_sha', 'columns', 'splits', 'mapping_path',
              'label_representation', 'label_interpretation_verified', 'label_evidence', 'preprint', 'items', 'limitations'}
    if not isinstance(evidence, dict) or set(evidence) != fields or type(evidence['schema_version']) is not int or evidence['schema_version'] != 1:
        raise ValueError('Invalid Stage 2 evidence schema')
    if evidence['source_id'] != 'spearmint_stability_audit' or not re.fullmatch(r'[a-f0-9]{40}', evidence['commit_sha']):
        raise ValueError('Invalid evidence source/commit')
    if evidence['label_representation'] not in {'hours', 'log1p_hours', 'unknown'} or type(evidence['label_interpretation_verified']) is not bool:
        raise ValueError('Invalid label interpretation evidence')
    if not isinstance(evidence['label_evidence'], str) or not evidence['label_evidence'].strip():
        raise ValueError('Label interpretation requires evidence')
    if not isinstance(evidence['columns'], dict) or set(evidence['columns']) != {'peptide', 'sequence', 'label', 'allele'}:
        raise ValueError('Invalid evidence columns')
    if not all(isinstance(v, str) and v for v in evidence['columns'].values()) or len(set(evidence['columns'].values())) != 4:
        raise ValueError('Invalid or duplicated column names')
    if not isinstance(evidence['splits'], dict) or set(evidence['splits']) != set(SPLITS):
        raise ValueError('Required splits are train, val, test')
    for value in [*evidence['splits'].values(), evidence['mapping_path']]:
        _relative(value)
    if not isinstance(evidence['items'], list) or not isinstance(evidence['limitations'], list):
        raise ValueError('Invalid evidence items/limitations')
    for item in evidence['items']:
        if not isinstance(item, dict) or set(item) != {'path', 'lines', 'scope', 'statement'} or not all(isinstance(v, str) and v for v in item.values()):
            raise ValueError('Invalid source-code evidence item')
        _relative(item['path'])
    preprint = evidence['preprint']
    if not isinstance(preprint, dict) or preprint.get('doi') != '10.64898/2026.06.28.735023':
        raise ValueError('Invalid preprint reference')
    if (type(preprint.get('claimed_rows')) is not int or preprint['claimed_rows'] <= 0
            or type(preprint.get('claimed_alleles')) is not int or preprint['claimed_alleles'] <= 0
            or set(preprint.get('claimed_split_rows', {})) != set(SPLITS)
            or any(type(x) is not int or x < 0 for x in preprint['claimed_split_rows'].values())):
        raise ValueError('Invalid published expectations')
    return evidence


def load_evidence(path: str | Path | None = None, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    return validate_evidence(_json(path or storage.repository_root / EVIDENCE_PATH))


def load_lock(path: str | Path | None = None, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    document = _json(path or storage.repository_root / LOCK_PATH)
    if set(document) != {'schema_version', 'repositories'} or document['schema_version'] != 1 or not isinstance(document['repositories'], list):
        raise ValueError('Invalid external repository lockfile')
    entries = [r for r in document['repositories'] if isinstance(r, dict) and r.get('repository_name') == 'spearmint']
    if len(entries) != 1:
        raise ValueError('Exactly one SPEARMINT lock entry required')
    locked = entries[0]
    if not re.fullmatch(r'[a-f0-9]{40}', locked.get('commit_sha', '')) or locked.get('url') != 'https://github.com/dhuvik/spearmint.git':
        raise ValueError('Invalid pinned SPEARMINT commit/URL')
    _relative(locked['checkout_relative_path'])
    seen = set()
    for entry in locked['files']:
        relative = _relative(entry['path'])
        if relative in seen or not re.fullmatch(r'[a-f0-9]{64}', entry['sha256']) or type(entry['byte_size']) is not int or entry['byte_size'] < 0:
            raise ValueError('Invalid pinned file identity')
        seen.add(relative)
        if not re.fullmatch(r'[a-f0-9]{40}', entry['git_blob_sha']):
            raise ValueError('Invalid Git blob identity')
    return locked


def _git(checkout: Path, *args: str, optional: bool = False) -> str:
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
        '-C', str(checkout), *args], capture_output=True, text=True, env=environment, timeout=30)
    if result.returncode and not (optional and result.returncode == 1):
        raise ValueError(f'Read-only Git inspection failed: {result.stderr.strip()}')
    return result.stdout.strip()


def verify_checkout(checkout: str | Path, locked: dict[str, Any]) -> dict[str, Any]:
    location = Path(checkout).expanduser().absolute()
    # No-follow traversal; never fetch, checkout, run hooks, or import external modules.
    with raw._directory(location):
        pass
    commit = _git(location, 'rev-parse', 'HEAD')
    status = _git(location, 'status', '--porcelain=v1', '--untracked-files=all')
    if commit != locked['commit_sha'] or status:
        raise ValueError('External checkout must match pinned commit and have a clean working tree')
    tree = _git(location, 'ls-tree', '-r', '--name-only', 'HEAD').splitlines()
    for file in locked['files']:
        path = location / file['path']
        if raw.sha256_file(path) != file['sha256'] or path.stat().st_size != file['byte_size']:
            raise ValueError(f'Pinned external file differs or is unavailable: {file["path"]}')
        if _git(location, 'rev-parse', 'HEAD:' + file['path']) != file['git_blob_sha']:
            raise ValueError('Pinned file Git blob differs')
    return {'url': locked['url'], 'commit_sha': commit,
        'branch': _git(location, 'symbolic-ref', '--short', '-q', 'HEAD', optional=True) or None,
        'working_tree_clean': True, 'working_tree_status': status, 'accessed_at_utc': locked['accessed_at_utc'],
        'checkout_path': str(location), 'tracked_paths': tree, 'clone_strategy': locked['clone_strategy'],
        'git_lfs': 'Required inputs verified as CSV payloads, not LFS pointers; unrelated sparse blobs are unmaterialized.',
        'read_only_inspection': True}


def snapshot_stage2(*, paths: StoragePaths | None = None, checkout: str | Path | None = None,
                    locked: dict[str, Any] | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit local copy acquisition, no network; atomic nonreplacing exact-byte snapshots."""
    storage = resolve_paths() if paths is None else paths
    lock = load_lock(paths=storage) if locked is None else locked
    register = load_evidence(paths=storage) if evidence is None else validate_evidence(evidence)
    external = Path(checkout) if checkout is not None else storage.repos_root / lock['checkout_relative_path']
    verify_checkout(external, lock)
    storage.validate()
    root = storage.data_root / PROJECT_NAME
    if root != storage.project_data_dir or root.resolve() != root:
        raise ValueError('Project data directory must not be a symlink')
    records = []
    metadata = {item['path']: item for item in lock['files']}
    for relative in [*(register['splits'][s] for s in SPLITS), register['mapping_path']]:
        expected = metadata[relative]
        target = root / 'spearmint_stage2' / relative
        with raw._directory(target.parent, create=True) as parent:
            try:
                os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                exists = False
            else:
                exists = True
            if exists:
                if raw.sha256_file(target) != expected['sha256']:
                    raise ValueError(f'Existing snapshot has different bytes; refusing replacement: {target}')
                acquisition = 'existing_identical_snapshot_reused'
            else:
                pending = f'.{target.name}.{secrets.token_hex(12)}.partial'
                descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                try:
                    with os.fdopen(descriptor, 'wb') as output, raw._read_file(external / relative) as source:
                        while chunk := source.read(raw.CHUNK_SIZE):
                            output.write(chunk)
                        output.flush(); os.fsync(output.fileno())
                    if raw.sha256_file(target.parent / pending) != expected['sha256']:
                        raise ValueError('External input changed during snapshot acquisition')
                    os.link(pending, target.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    os.fsync(parent)
                finally:
                    os.unlink(pending, dir_fd=parent)
                acquisition = 'copied_exact_pinned_checkout_bytes'
        records.append({'repository_relative_path': relative, 'snapshot_path': str(target),
            'sha256': expected['sha256'], 'byte_size': expected['byte_size'], 'acquisition': acquisition})
    return {'source_id': register['source_id'], 'external_commit_sha': lock['commit_sha'], 'snapshots': records}


@dataclass(frozen=True)
class StageRow:
    split: str
    source_file: str
    record_number: int
    line_start: int
    line_end: int
    fields: dict[str, str]
    raw_cells: tuple[str, ...]
    numeric_value: Decimal | None
    numeric_issue: str | None

    def reference(self) -> dict[str, Any]:
        return {'split': self.split, 'source_file': self.source_file, 'record_number': self.record_number,
                'source_line_start': self.line_start, 'source_line_end': self.line_end}


def read_split(path: str | Path, split: str, columns: dict[str, str]) -> tuple[list[StageRow], dict[str, Any]]:
    """CSV fields remain literal; physical line spans trace multiline/quoted records."""
    target = Path(path).absolute()
    checksum = raw.sha256_file(target)
    rows = []; blanks = 0; malformed = []
    with raw._read_file(target) as stream, io.TextIOWrapper(stream, encoding='utf-8', newline='') as text:
        reader = csv.reader(text, strict=True)
        header = next(reader, None)
        if not header or len(set(header)) != len(header) or any(not h for h in header):
            raise ValueError('Missing, empty, or duplicate CSV header')
        if not {columns['peptide'], columns['label']}.issubset(header) or not ({columns['allele'], columns['sequence']} & set(header)):
            raise ValueError('CSV needs peptide, label, and a receptor representation')
        previous = reader.line_num
        for cells in reader:
            start = previous + 1; previous = reader.line_num
            if not cells:
                blanks += 1; continue
            fields = {name: cells[i] if i < len(cells) else '' for i, name in enumerate(header)}
            label = fields[columns['label']]
            try:
                parsed = raw.parse_record('X P ' + label, start)
                value, issue = parsed.half_life, parsed.numeric_issue
            except ValueError:
                value, issue = None, 'missing' if not label else 'non_numeric'
            if len(cells) != len(header):
                issue = 'column_count'; value = None
            if issue:
                malformed.append({'line': start, 'reason': issue})
            rows.append(StageRow(split, str(target), len(rows) + 1, start, reader.line_num,
                                 fields, tuple(cells), value, issue))
    if raw.sha256_file(target) != checksum:
        raise ValueError('Stage 2 input changed during inventory')
    peptides = [r.fields[columns['peptide']] for r in rows]
    sequences = [r.fields.get(columns['sequence'], '') for r in rows]
    alleles = [r.fields.get(columns['allele'], '') for r in rows]
    kinds = {name: dict(sorted(Counter('missing' if not r.fields[name] else
        'finite_decimal' if _number(r.fields[name]) is not None else 'text' for r in rows).items())) for name in header}
    report = {'path': str(target), 'sha256': checksum, 'byte_size': target.stat().st_size,
        'columns': header, 'observed_value_types': kinds, 'rows': len(rows), 'blank_lines': blanks,
        'malformed_rows': malformed, 'distinct_raw_peptides': len(set(peptides)),
        'peptide_lengths': dict(sorted(Counter(str(len(p)) for p in peptides).items())),
        'distinct_raw_alleles': len(set(alleles) - {''}), 'distinct_raw_mhc_sequences': len(set(sequences) - {''}),
        'mhc_sequence_lengths': dict(sorted(Counter(str(len(s)) for s in sequences if s).items())),
        'zero_labels': sum(r.numeric_value == 0 for r in rows),
        'positive_labels': sum(r.numeric_value is not None and r.numeric_value > 0 for r in rows),
        'negative_labels': sum(r.numeric_value is not None and r.numeric_value < 0 for r in rows),
        'numeric_issues': dict(sorted(Counter(r.numeric_issue for r in rows if r.numeric_issue).items())),
        'missing_fields': {name: sum(not r.fields[name] for r in rows) for name in header},
        'noncanonical_peptide_characters': sorted(set(''.join(peptides)) - raw.CANONICAL_AMINO_ACIDS),
        'noncanonical_mhc_characters': sorted(set(''.join(sequences)) - raw.CANONICAL_AMINO_ACIDS),
        'context_values': {name: dict(sorted(Counter(r.fields[name] for r in rows).items()))
                           for name in ('assay', 'temperature_C') if name in header}}
    return rows, report


def _number(text: str) -> Decimal | None:
    try:
        return raw.parse_record('X P ' + text, 1).half_life
    except ValueError:
        return None


def read_mapping(path: str | Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_allele: dict[str, set[str]] = defaultdict(set)
    by_sequence: dict[str, set[str]] = defaultdict(set)
    with raw._read_file(path) as stream, io.TextIOWrapper(stream, encoding='utf-8', newline='') as text:
        reader = csv.DictReader(text)
        if reader.fieldnames != ['Allele', 'Full Sequence']:
            raise ValueError('Expected pinned Allele/Full Sequence reference schema')
        for row in reader:
            if set(row) != {'Allele', 'Full Sequence'} or not row['Allele'] or not row['Full Sequence']:
                raise ValueError('Malformed receptor reference row')
            by_allele[row['Allele']].add(row['Full Sequence'])
            by_sequence[row['Full Sequence']].add(row['Allele'])
    return dict(by_allele), dict(by_sequence)


def map_receptor(row: StageRow, columns: dict[str, str], by_allele: dict[str, set[str]],
                 by_sequence: dict[str, set[str]], evidence_source: str) -> dict[str, Any]:
    allele = row.fields.get(columns['allele'], '')
    sequence = row.fields.get(columns['sequence'], '')
    candidates = sorted(by_sequence.get(sequence, set())) if sequence else []
    target = None
    if allele:
        if dtu.identifier_category(allele) == 'unexpected':
            status = 'unresolved_unrecognized_identifier'
        elif sequence and sequence in by_allele.get(allele, set()):
            status = 'verified_explicit_identifier_and_exact_reference_sequence'; target = allele
        elif not sequence:
            status = 'supported_explicit_identifier_sequence_unavailable'; target = allele
        else:
            status = 'unresolved_explicit_identifier_sequence_mismatch'
    elif len(candidates) == 1 and dtu.identifier_category(candidates[0]) != 'unexpected':
        status = 'verified_unique_exact_reference_sequence'; target = candidates[0]
    else:
        status = 'unresolved_ambiguous_sequence' if candidates else 'unresolved_unmapped_sequence'
    return {'raw_allele': allele, 'raw_mhc_sequence': sequence, 'mapped_identifier': target,
        'mapping_status': status, 'candidate_reference_identifiers': candidates,
        'rule': 'Literal identifier plus exact pinned sequence, or unique exact sequence-only lookup; no similarity/name normalization or mutant-to-wild-type mapping.',
        'evidence_source': evidence_source,
        'limitation': 'Reference identity supports the released representation, not equivalence of experimental biological material.'}


def label_hours(row: StageRow, evidence: dict[str, Any]) -> tuple[Decimal | None, str]:
    if row.numeric_issue or row.numeric_value is None:
        return None, row.numeric_issue or 'invalid_numeric'
    if not evidence['label_interpretation_verified']:
        return None, 'unverified_label_interpretation'
    representation = evidence['label_representation']
    if representation == 'hours':
        return row.numeric_value, 'verified_hours_no_conversion'
    if representation == 'log1p_hours':
        try:
            if abs(row.numeric_value) > 1000:
                return None, 'inverse_transform_out_of_controlled_range'
            with localcontext() as context:
                context.prec = 50
                return row.numeric_value.exp() - 1, 'verified_log1p_inverse_decimal_precision_50'
        except DecimalException:
            return None, 'inverse_transform_failed'
    return None, 'unknown_label_representation'


def _jsonl(rows: Sequence[dict[str, Any]]) -> str:
    return ''.join(json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n' for row in rows)


def _duplicates(groups: Mapping[tuple[str, str], Sequence[StageRow]]) -> dict[str, Any]:
    repeated = [{'receptor': key[0], 'peptide': key[1], 'rows': [r.reference() for r in rows]}
                for key, rows in sorted(groups.items()) if len(rows) > 1]
    cross = [g for g in repeated if len({r['split'] for r in g['rows']}) > 1]
    within = {split: sum(sum(r.split == split for r in rows) > 1 for rows in groups.values()) for split in SPLITS}
    return {'duplicate_key_groups': len(repeated), 'within_split_duplicate_key_groups': within,
            'cross_split_duplicate_key_groups': len(cross), 'repeated_keys': repeated}


@dataclass(frozen=True)
class OverlapResult:
    reports: dict[str, dict[str, Any]]
    row_reports: dict[str, list[dict[str, Any]]]
    inputs: tuple[Path, ...]

    def summary(self) -> dict[str, Any]:
        return self.reports['dtu_stage2_overlap_summary.json']


def audit(*, paths: StoragePaths | None = None, checkout: str | Path | None = None,
          files: Mapping[str, str | Path] | None = None, mapping: str | Path | None = None,
          dtu_path: str | Path | None = None, expected_dtu_sha256: str = dtu.TASK11_LOCAL_SHA256,
          lock_path: str | Path | None = None, evidence_path: str | Path | None = None) -> OverlapResult:
    storage = resolve_paths() if paths is None else paths
    source = load_manifest(paths=storage).get(raw.SOURCE_ID)
    primary = Path(dtu_path) if dtu_path is not None else source.target_path(storage)
    if not re.fullmatch(r'[a-f0-9]{64}', expected_dtu_sha256) or raw.sha256_file(primary) != expected_dtu_sha256:
        raise ValueError('Immutable DTU checksum mismatch; no row analysis performed')
    locked = load_lock(lock_path, paths=storage); evidence = load_evidence(evidence_path, paths=storage)
    if evidence['commit_sha'] != locked['commit_sha']:
        raise ValueError('Evidence and external lock commits differ')
    external = Path(checkout) if checkout is not None else storage.repos_root / locked['checkout_relative_path']
    repository = verify_checkout(external, locked)
    metadata = {item['path']: item for item in locked['files']}
    selected: dict[str, Path] = {}
    supplied = {} if files is None else dict(files)
    if set(supplied) - set(SPLITS):
        raise ValueError('Unknown split override')
    for split in SPLITS:
        relative = evidence['splits'][split]
        snapshot = storage.project_data_dir / 'spearmint_stage2' / relative
        selected[split] = Path(supplied[split]) if split in supplied else snapshot if snapshot.exists() else external / relative
    relative = evidence['mapping_path']
    snapshot = storage.project_data_dir / 'spearmint_stage2' / relative
    reference = Path(mapping) if mapping is not None else snapshot if snapshot.exists() else external / relative
    for relative, selected_path in [*((evidence['splits'][s], selected[s]) for s in SPLITS), (relative, reference)]:
        if relative not in metadata or raw.sha256_file(selected_path) != metadata[relative]['sha256']:
            raise ValueError(f'Pinned input checksum mismatch: {selected_path}')
    structure = raw.inventory(primary, source=source)
    if not structure['header']['matches'] or structure['malformed_line_count'] or structure['duplicate_key_count']:
        raise ValueError('DTU requires finite three-column rows and unique raw keys')
    dtu_rows = tuple(raw.iter_records(primary)); primary_keys = {(r.hla, r.peptide): r for r in dtu_rows}
    by_allele, by_sequence = read_mapping(reference)
    rows = []; inventories = {}
    for split in SPLITS:
        split_rows, report = read_split(selected[split], split, evidence['columns'])
        rows.extend(split_rows); inventories[split] = report
    mappings = {}; raw_keys: dict[tuple[str, str], list[StageRow]] = defaultdict(list)
    mapped_keys: dict[tuple[str, str], list[StageRow]] = defaultdict(list)
    peptide_splits: dict[str, set[str]] = defaultdict(set)
    matches = []; unmatched = []; differences = []; strict_count = mapped_count = exact = raw_text_equal = incomparable = 0
    tolerance_counts = Counter({t: 0 for t in TOLERANCES}); zero_matches = positive_matches = 0
    matched_keys = set(); mapped_identifiers = set(); mapping_statuses = Counter(); subset_counts = defaultdict(Counter)
    columns = evidence['columns']
    for row in rows:
        allele = row.fields.get(columns['allele'], ''); sequence = row.fields.get(columns['sequence'], '')
        peptide = row.fields[columns['peptide']]
        receptor_key = (allele, sequence)
        if receptor_key not in mappings:
            mappings[receptor_key] = map_receptor(row, columns, by_allele, by_sequence, str(reference))
        receptor = mappings[receptor_key]
        mapped = receptor['mapped_identifier']; mapping_statuses[receptor['mapping_status']] += 1
        if mapped:
            mapped_identifiers.add(mapped); mapped_keys[mapped, peptide].append(row)
        raw_keys[allele or sequence, peptide].append(row); peptide_splits[peptide].add(row.split)
        strict = primary_keys.get((allele, peptide)) if allele else None
        joined = primary_keys.get((mapped, peptide)) if mapped else None
        strict_count += strict is not None; mapped_count += joined is not None
        value, conversion = label_hours(row, evidence)
        details = {**row.reference(), 'raw_fields': row.fields, 'raw_cells': list(row.raw_cells),
            'raw_label_text': row.fields[columns['label']], 'raw_label_decimal': str(row.numeric_value) if row.numeric_value is not None else None,
            'numeric_issue': row.numeric_issue, 'mapping': receptor, 'strict_raw_key_match': strict is not None,
            'mapped_key_match': joined is not None, 'comparison_hours_decimal': str(value) if value is not None else None,
            'label_conversion': conversion, 'row_measurement_origin': ROW_ORIGIN,
            'strict_dtu_line_number': strict.source_line_number if strict else None,
            'strict_dtu_half_life_text': strict.half_life_text if strict else None,
            'dtu_line_number': joined.source_line_number if joined else None,
            'dtu_half_life_text': joined.half_life_text if joined else None}
        if joined:
            matched_keys.add((joined.hla, joined.peptide))
            zero_matches += joined.half_life == 0; positive_matches += joined.half_life > 0
            if value is not None:
                with localcontext() as context:
                    context.prec = 60
                    delta = abs(value - joined.half_life)
                differences.append(delta); exact += delta == 0
                raw_text_equal += row.fields[columns['label']] == joined.half_life_text
                within = [t for t in TOLERANCES if delta <= Decimal(t)]
                tolerance_counts.update(within)
                details.update(absolute_difference_hours=str(delta), tolerance_matches_hours=within,
                    provenance_classification='dtu_matching_released_row_not_independent' if delta == 0 else 'matched_key_value_disagrees_origin_unverified')
            else:
                incomparable += 1; details.update(absolute_difference_hours=None,
                    provenance_classification='matched_key_label_interpretation_unresolved')
            matches.append(details)
        else:
            reason = 'unmapped_or_ambiguous_receptor' if mapped is None else 'mapped_key_absent_from_dtu'
            details.update(unmatched_reason=reason, provenance_classification='unmatched_row_origin_unverified')
            unmatched.append(details)
        subset_counts[row.split][details['provenance_classification']] += 1
    absent = [r for r in dtu_rows if (r.hla, r.peptide) not in matched_keys]
    per_allele = []
    for hla in sorted({r.hla for r in dtu_rows} | mapped_identifiers):
        originals = [r for r in dtu_rows if r.hla == hla]
        included = [r for r in originals if (r.hla, r.peptide) in matched_keys]
        per_allele.append({'raw_dtu_identifier': hla, 'category': dtu.identifier_category(hla),
            'dtu_rows': len(originals), 'dtu_keys_in_stage2': len(included), 'dtu_keys_absent_from_stage2': len(originals)-len(included),
            'stage2_rows_by_split': {s: sum(1 for (a, p), rs in mapped_keys.items() if a == hla for r in rs if r.split == s) for s in SPLITS},
            'included_dtu_zeros': sum(r.half_life == 0 for r in included),
            'absent_dtu_source_lines': [r.source_line_number for r in originals if (r.hla, r.peptide) not in matched_keys]})
    # Stable exact comparisons use Decimal strings; never label rounding as measurement provenance.
    ordinary_count = sum(dtu.identifier_category(r.hla).startswith('ordinary_') for r in dtu_rows)
    claim = evidence['preprint']
    summary = {'source_id': evidence['source_id'], 'external_commit_sha': locked['commit_sha'],
        'dtu_sha256': expected_dtu_sha256, 'dtu_rows': len(dtu_rows), 'dtu_identifiers': len({r.hla for r in dtu_rows}),
        'dtu_ordinary_rows': ordinary_count, 'stage2_rows': len(rows),
        'split_counts': {s: inventories[s]['rows'] for s in SPLITS},
        'split_zero_positive_counts': {s: {k: inventories[s][k] for k in ('zero_labels','positive_labels')} for s in SPLITS},
        'distinct_stage2_raw_alleles': len({r.fields.get(columns['allele'], '') for r in rows} - {''}),
        'mapped_identifiers': len(mapped_identifiers), 'unmapped_rows': sum(x['mapped_identifier'] is None for x in (mappings[(r.fields.get(columns['allele'], ''),r.fields.get(columns['sequence'], ''))] for r in rows)),
        'mapping_status_row_counts': dict(sorted(mapping_statuses.items())),
        'strict_raw_identifier_row_matches': strict_count, 'mapped_identifier_row_matches': mapped_count,
        'unique_dtu_keys_matched': len(matched_keys), 'exact_decimal_measurement_matches': exact,
        'exact_label_text_matches': raw_text_equal, 'numerically_incomparable_matched_rows': incomparable,
        'tolerance_match_counts_hours': dict(tolerance_counts),
        'absolute_difference_hours': {'count':len(differences),'maximum':str(max(differences)) if differences else None,
            'median':dtu._decimal_text(dtu.quantile(differences,50)), 'p95':dtu._decimal_text(dtu.quantile(differences,95)),
            'distribution':dict(sorted(Counter(str(x) for x in differences).items()))},
        'matched_dtu_zero_rows': zero_matches, 'matched_dtu_positive_rows': positive_matches,
        'stage2_unmatched_rows': len(unmatched), 'dtu_absent_rows':len(absent),
        'dtu_absent_categories':dict(sorted(Counter(dtu.identifier_category(r.hla) for r in absent).items())),
        'raw_duplicate_keys':_duplicates(raw_keys), 'mapped_duplicate_keys':_duplicates(mapped_keys),
        'exact_peptides_shared_between_splits':sum(len(s)>1 for s in peptide_splits.values()),
        'per_allele':per_allele, 'label_representation':evidence['label_representation'],
        'published_expectations':{'rows':claim['claimed_rows'],'alleles':claim['claimed_alleles'],'split_rows':claim['claimed_split_rows']},
        'published_minus_released_rows':claim['claimed_rows']-len(rows),
        'published_split_sum':sum(claim['claimed_split_rows'].values()),
        'discrepancy_interpretation':'Released rows/counts compared without repair. Aggregate discrepancy is not evidence of independent measurements; earlier processing-stage explanation requires unavailable preparation evidence.',
        'provenance_classification_by_split':{s:dict(sorted(subset_counts[s].items())) for s in SPLITS},
        'limitations':evidence['limitations']}
    inputs = (primary.absolute(), *(selected[s].absolute() for s in SPLITS), reference.absolute())
    for f in inputs:
        expected = expected_dtu_sha256 if f == primary.absolute() else next(inventories[s]['sha256'] for s in SPLITS if f == selected[s].absolute()) if f in [selected[s].absolute() for s in SPLITS] else metadata[evidence['mapping_path']]['sha256']
        if raw.sha256_file(f) != expected:
            raise ValueError('Audit input changed while comparing rows')
    if verify_checkout(external, locked) != repository:
        raise ValueError('External checkout changed during audit')
    return OverlapResult({'spearmint_source_inventory.json':{**repository,'locked_files':locked['files'],
            'input_files':[{'path':str(f),'sha256':raw.sha256_file(f),'byte_size':f.stat().st_size} for f in inputs]},
        'stage2_split_inventory.json':{'splits':inventories,'total_rows':len(rows),'distinct_raw_peptides':len(peptide_splits)},
        'allele_mapping_evidence.json':{'reference_path':str(reference),'reference_sha256':raw.sha256_file(reference),
            'mappings':[mappings[key] for key in sorted(mappings)]},
        'dtu_stage2_overlap_summary.json':summary,'stage2_provenance_evidence.json':evidence},
        {'dtu_stage2_overlap_rows.jsonl':matches,'stage2_unmatched_rows.jsonl':unmatched,
         'dtu_absent_rows.jsonl':[{'source_line_number':r.source_line_number,'hla':r.hla,'peptide':r.peptide,
            'half_life_text':r.half_life_text,'category':dtu.identifier_category(r.hla),'row_origin':ROW_ORIGIN} for r in absent]},inputs)


def write_reports(result: OverlapResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    directory = Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name != 'reports' or directory.parent.parent != storage.project_runs_dir:
        raise ValueError('Output must be an existing project run reports directory')
    manifest = runs.load_manifest(directory.parent.name, paths=storage)
    for entry in result.reports['spearmint_source_inventory.json']['input_files']:
        if {'path':entry['path'],'sha256':entry['sha256']} not in manifest['data_provenance']['input_artifacts']:
            raise ValueError('Run must explicitly record every audit input')
        if raw.sha256_file(entry['path']) != entry['sha256']:
            raise ValueError('Audit input changed before report writing')
    names = [*result.reports, *result.row_reports, 'overlap_report_checksums.json']
    with raw._directory(directory) as fd:
        for name in names:
            try: os.stat(name,dir_fd=fd,follow_symlinks=False)
            except FileNotFoundError: continue
            raise FileExistsError(f'Output already exists: {name}')
    for name, report in result.reports.items():raw.write_report(directory/name,report,paths=storage)
    for name, rows in result.row_reports.items():raw.write_text_report(directory/name,_jsonl(rows),paths=storage)
    for entry in result.reports['spearmint_source_inventory.json']['input_files']:
        if raw.sha256_file(entry['path']) != entry['sha256']:raise ValueError('Audit input changed during report writing')
    completion={'completion':'all_overlap_reports_written','external_commit_sha':result.summary()['external_commit_sha'],
        'input_files':result.reports['spearmint_source_inventory.json']['input_files'],
        'report_sha256':{name:raw.sha256_file(directory/name) for name in names[:-1]}}
    raw.write_report(directory/names[-1],completion,paths=storage)
    return completion
