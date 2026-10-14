"""Offline, checksum-gated measurement-semantics audit; no training eligibility labels."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

TASK11_LOCAL_SHA256 = '5f2c6e82d198705a66974b4e42a0ed1412124c4b1e8f7033c7cd43bbdac07f67'
ROW_PROVENANCE = 'published_raw_stability_table_row_origin_unverified'
EVIDENCE_CONFIG = 'configs/netmhcstabpan_2016_evidence.json'
C67S_PATTERN = re.compile(r'HLA-B\*[0-9]{2,3}:[0-9]{2,3}\(C67S\)')
QUANTILE_CONVENTION = 'Type 7: h=(n-1)*p; linear interpolation, Decimal arithmetic; p50 is the median.'


def identifier_category(hla: str) -> str:
    if C67S_PATTERN.fullmatch(hla):
        return 'c67s_annotated_hla_b'
    if raw.ALLELE_PATTERN.fullmatch(hla) and raw.classify_locus(hla) in {'A', 'B'}:
        return 'ordinary_hla_' + raw.classify_locus(hla).lower()
    return 'unexpected'


def quantile(values: Sequence[Decimal], percent: int) -> Decimal | None:
    if not values:
        return None
    if percent < 0 or percent > 100:
        raise ValueError('Percent must be in [0, 100]')
    ordered = sorted(values)
    numerator = (len(ordered) - 1) * percent
    index, remainder = divmod(numerator, 100)
    with localcontext() as context:
        context.prec = 50
        return ordered[index] if remainder == 0 else (
            ordered[index] + (ordered[index + 1] - ordered[index]) * Decimal(remainder) / 100)


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _fraction(count: int, total: int) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 28
        return {'numerator': count, 'denominator': total,
                'decimal': str(Decimal(count) / total) if total else None}


def _distribution(values: Sequence[Decimal]) -> dict[str, Any]:
    return {'count': len(values), 'minimum': _decimal_text(min(values)) if values else None,
            'median': _decimal_text(quantile(values, 50)),
            'p95': _decimal_text(quantile(values, 95)), 'p99': _decimal_text(quantile(values, 99)),
            'maximum': _decimal_text(max(values)) if values else None,
            'unit': 'hours', 'quantile_convention': QUANTILE_CONVENTION}


class _TableII(HTMLParser):
    """Extract the two five-column blocks only inside the article's T2 section."""
    def __init__(self) -> None:
        super().__init__()
        self.section_depth = 0
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.rows: list[list[str]] = []
        self.found = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'section':
            if self.section_depth:
                self.section_depth += 1
            elif dict(attrs).get('id') == 'T2':
                self.section_depth = 1
                self.found += 1
        if not self.section_depth:
            return
        if tag == 'tr':
            self.row = []
        if tag in {'td', 'th'} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {'td', 'th'} and self.cell is not None and self.row is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == 'section' and self.section_depth:
            self.section_depth -= 1


def extract_table_ii(html: str) -> list[dict[str, Any]]:
    """Keep publication typography; the one annotation-space mapping is explicit."""
    parser = _TableII()
    parser.feed(html)
    if parser.found != 1:
        raise ValueError('Expected exactly one publication T2 section')
    entries = []
    for cells in parser.rows:
        if not any(cell.startswith('HLA-') for cell in cells):
            continue
        if len(cells) != 10:
            raise ValueError('Ambiguous Table II row: expected two five-column blocks')
        for offset in (0, 5):
            group, published, count, p95, p05 = cells[offset:offset + 5]
            if not published:
                if any((count, p95, p05)):
                    raise ValueError('Table II block has values without identifier')
                continue
            # Publication-to-raw comparison mapping only. Raw row identifiers never change.
            hla = published.replace(' (C67S)', '(C67S)')
            if identifier_category(hla) == 'unexpected' or not count.isascii() or not count.isdigit():
                raise ValueError('Unrecognized publication identifier/count')
            if any(not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', x) for x in (p95, p05)):
                raise ValueError('Invalid publication percentile text')
            entries.append({'publication_identifier': published, 'raw_identifier': hla,
                'count': int(count), 'p05_text': p05, 'p95_text': p95})
    if not entries or len({entry['raw_identifier'] for entry in entries}) != len(entries):
        raise ValueError('Empty or duplicate Table II entries')
    return sorted(entries, key=lambda entry: entry['raw_identifier'])


def _unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate evidence key: {key}')
        result[key] = value
    return result


def validate_evidence(document: Any) -> dict[str, Any]:
    required = {'schema_version', 'source_id', 'publication_doi', 'verified_at_utc',
                'snapshots', 'items', 'table_ii', 'limitations'}
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError('Invalid evidence-register fields')
    if (type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['source_id'] != raw.SOURCE_ID or document['publication_doi'] != '10.4049/jimmunol.1600582'):
        raise ValueError('Invalid evidence version/source/DOI')
    if not isinstance(document['verified_at_utc'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z', document['verified_at_utc']):
        raise ValueError('Invalid evidence verification timestamp')
    datetime.fromisoformat(document['verified_at_utc'])
    if not isinstance(document['limitations'], list) or not all(isinstance(x, str) and x for x in document['limitations']):
        raise ValueError('Invalid evidence limitations')
    snapshots = document['snapshots']
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError('Evidence snapshots required')
    names = set()
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or set(snapshot) != {'filename', 'url', 'sha256', 'byte_size'}:
            raise ValueError('Invalid evidence snapshot fields')
        name = snapshot['filename']
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.html', name) or name in names:
            raise ValueError('Unsafe or duplicate evidence snapshot name')
        names.add(name)
        if not isinstance(snapshot['url'], str):
            raise ValueError('Invalid evidence URL')
        url = urlsplit(snapshot['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or any(x.isspace() for x in snapshot['url']):
            raise ValueError('Invalid evidence URL')
        if not isinstance(snapshot['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', snapshot['sha256']):
            raise ValueError('Invalid snapshot checksum')
        if type(snapshot['byte_size']) is not int or snapshot['byte_size'] <= 0:
            raise ValueError('Invalid snapshot byte size')
    items = document['items']
    if not isinstance(items, list) or not items:
        raise ValueError('Evidence items required')
    identifiers = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'id', 'url', 'location', 'scope', 'status', 'statement', 'does_not_establish'}:
            raise ValueError('Invalid evidence item fields')
        if not all(isinstance(x, str) and x.strip() for x in item.values()):
            raise ValueError('Evidence item fields must be nonempty text')
        if item['id'] in identifiers or item['scope'] not in {'dataset', 'assay', 'preprocessing', 'model_training', 'individual_rows', 'publication_table'}:
            raise ValueError('Duplicate evidence item or invalid scope')
        identifiers.add(item['id'])
        if item['status'] not in {'verified_statement', 'unresolved_after_main_article_review'}:
            raise ValueError('Invalid evidence status')
        url = urlsplit(item['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or any(c.isspace() for c in item['url']):
            raise ValueError('Invalid evidence item URL')
    table = document['table_ii']
    if not isinstance(table, dict) or set(table) != {'location', 'extraction', 'coverage', 'entries'}:
        raise ValueError('Invalid Table II evidence')
    if table['coverage'] not in {'complete', 'partial'} or not all(isinstance(table[k], str) and table[k] for k in ('location', 'extraction')):
        raise ValueError('Invalid Table II coverage/location')
    entries = table['entries']
    if not isinstance(entries, list) or not entries:
        raise ValueError('No Table II entries')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'publication_identifier', 'raw_identifier', 'count', 'p05_text', 'p95_text'}:
            raise ValueError('Invalid Table II entry')
        if not isinstance(entry['publication_identifier'], str) or not isinstance(entry['raw_identifier'], str):
            raise ValueError('Invalid Table II identifier type')
        if entry['raw_identifier'] != entry['publication_identifier'].replace(' (C67S)', '(C67S)'):
            raise ValueError('Unsupported publication identifier mapping')
        if identifier_category(entry['raw_identifier']) == 'unexpected' or entry['raw_identifier'] in seen:
            raise ValueError('Invalid or duplicate Table II identifier')
        seen.add(entry['raw_identifier'])
        if type(entry['count']) is not int or entry['count'] <= 0:
            raise ValueError('Invalid Table II count')
        if any(not isinstance(entry[k], str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', entry[k]) for k in ('p05_text', 'p95_text')):
            raise ValueError('Invalid Table II percentile')
    return document


def load_evidence(path: str | Path | None = None, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    target = storage.repository_root / EVIDENCE_CONFIG if path is None else Path(path)
    with raw._read_file(target) as stream:
        return validate_evidence(json.load(stream, object_pairs_hook=_unique_json))


def verify_publication_snapshot(path: str | Path, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Offline replay of the captured article's Table II, gated by snapshot bytes."""
    register = validate_evidence(evidence)
    snapshot = next((item for item in register['snapshots']
                     if item['filename'] == 'publication_article.html'), None)
    if snapshot is None:
        raise ValueError('No captured publication article reference')
    if raw.sha256_file(path) != snapshot['sha256']:
        raise ValueError('Publication snapshot checksum mismatch')
    with raw._read_file(path) as stream:
        payload = stream.read(snapshot['byte_size'] + 1)
    if len(payload) != snapshot['byte_size']:
        raise ValueError('Publication snapshot size mismatch')
    entries = extract_table_ii(payload.decode('utf-8'))
    if entries != sorted(register['table_ii']['entries'], key=lambda item: item['raw_identifier']):
        raise ValueError('Captured publication Table II differs from evidence register')
    return entries


def row_flag(row: raw.Record) -> dict[str, Any]:
    if row.numeric_issue or row.half_life is None:
        raise ValueError(f'Invalid half-life on source line {row.source_line_number}')
    return {'source_line_number': row.source_line_number, 'raw_line': row.raw_line,
            'hla': row.hla, 'peptide': row.peptide, 'half_life_text': row.half_life_text,
            'half_life_hours_decimal': str(row.half_life), 'exact_zero': row.half_life == 0,
            'identifier_category': identifier_category(row.hla), 'provenance_status': ROW_PROVENANCE}


def row_flags_jsonl(records: Sequence[raw.Record]) -> str:
    return ''.join(json.dumps(row_flag(row), sort_keys=True, ensure_ascii=True, allow_nan=False,
                              separators=(',', ':')) + '\n' for row in records)


def reconcile(by_allele: Mapping[str, Sequence[raw.Record]], evidence: dict[str, Any]) -> dict[str, Any]:
    entries = {entry['raw_identifier']: entry for entry in evidence['table_ii']['entries']}
    comparison = []
    for hla in sorted(set(by_allele) | set(entries)):
        rows = by_allele.get(hla, ())
        entry = entries.get(hla)
        values = [row.half_life for row in rows if row.half_life is not None]
        matches = entry is not None and hla in by_allele and len(rows) == entry['count']
        percentiles = {}
        if entry:
            for percent, key in ((5, 'p05'), (95, 'p95')):
                observed = quantile(values, percent)
                published = Decimal(entry[key + '_text'])
                percentiles[key] = {'observed_type7': _decimal_text(observed),
                    'published_text': entry[key + '_text'],
                    'difference_hours': _decimal_text(observed - published) if observed is not None else None,
                    'interpretation': 'exploratory; publication rounding/interpolation method not specified; no row correction'}
        comparison.append({'raw_identifier': hla, 'publication_identifier': entry['publication_identifier'] if entry else None,
            'observed_count': len(rows), 'published_count': entry['count'] if entry else None,
            'count_matches': matches, 'percentiles': percentiles})
    return {'coverage': evidence['table_ii']['coverage'], 'location': evidence['table_ii']['location'],
        'publication_allotype_count': len(entries), 'observed_allotype_count': len(by_allele),
        'publication_observation_count': sum(entry['count'] for entry in entries.values()),
        'observed_observation_count': sum(len(rows) for rows in by_allele.values()),
        'matching_count_entries': sum(row['count_matches'] for row in comparison),
        'count_discrepancies': [row for row in comparison if not row['count_matches']],
        'all_counts_reconciled': evidence['table_ii']['coverage'] == 'complete' and all(row['count_matches'] for row in comparison),
        'quantile_convention': QUANTILE_CONVENTION,
        'identifier_mapping': 'Only the publication space before (C67S) is bridged for comparison; raw identifiers unchanged.',
        'comparison': comparison}


@dataclass(frozen=True)
class AuditResult:
    reports: dict[str, dict[str, Any]]
    records: tuple[raw.Record, ...]

    def summary(self) -> dict[str, Any]:
        zero = self.reports['zero_value_audit.json']
        context = self.reports['allele_context_audit.json']
        comparison = self.reports['publication_reconciliation.json']
        return {'source_id': raw.SOURCE_ID, 'raw_sha256': zero['raw_sha256'],
            'observation_count': len(self.records), 'zero_count': zero['zero_count'],
            'zero_fraction': zero['zero_fraction'], 'zero_text_representations': zero['zero_text_representations'],
            'groups': zero['groups'], 'ordinary_partition': context['ordinary_partition'],
            'c67s_partition': context['c67s_partition'],
            'c67s_alleles': [{key: allele[key] for key in ('hla', 'rows', 'zero_count', 'positive_count',
                             'zero_fraction', 'positive_half_life')} for allele in context['c67s_alleles']],
            'high_zero_fraction_alleles': zero['high_zero_fraction_alleles'],
            'smallest_positive_values': zero['smallest_positive_values'],
            'all_publication_counts_reconciled': comparison['all_counts_reconciled'],
            'matching_table_entries': comparison['matching_count_entries'],
            'row_provenance_status': ROW_PROVENANCE,
            'zero_semantics': 'unresolved; no missing/synthetic/censoring or physical-zero interpretation assigned'}


def audit(path: str | Path | None = None, *, paths: StoragePaths | None = None,
          expected_sha256: str = TASK11_LOCAL_SHA256, evidence: dict[str, Any] | None = None) -> AuditResult:
    """Read-only audit. Reject changed bytes and malformed numbers before summaries."""
    storage = resolve_paths() if paths is None else paths
    source = load_manifest(paths=storage).get(raw.SOURCE_ID)
    target = source.target_path(storage) if path is None else Path(path)
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_sha256):
        raise ValueError('Expected SHA256 must be 64 lowercase hexadecimal characters')
    checksum = raw.sha256_file(target)
    if checksum != expected_sha256:
        raise ValueError(f'Raw checksum mismatch: expected {expected_sha256}; observed {checksum}. No analysis performed.')
    register = load_evidence(paths=storage) if evidence is None else validate_evidence(evidence)
    structure = raw.inventory(target, source=source)
    if structure['sha256'] != checksum or not structure['header']['matches'] or structure['malformed_line_count']:
        raise ValueError('Raw structural validation failed; audit requires matching header and finite three-column records')
    records = tuple(raw.iter_records(target))
    if len(records) != structure['parsed_observation_count'] or raw.sha256_file(target) != checksum:
        raise ValueError('Raw input changed during audit')
    by_allele: dict[str, list[raw.Record]] = defaultdict(list)
    for row in records:
        by_allele[row.hla].append(row)
    allele_summaries = []
    groups = {category: {'allele_count': 0, 'rows': 0, 'zero': 0, 'positive': 0, 'negative': 0}
              for category in ('ordinary_hla_a', 'ordinary_hla_b', 'c67s_annotated_hla_b', 'unexpected')}
    for hla, rows in sorted(by_allele.items()):
        category = identifier_category(hla)
        positive = [row.half_life for row in rows if row.half_life is not None and row.half_life > 0]
        zeros = [row.source_line_number for row in rows if row.half_life == 0]
        negatives = sum(row.half_life is not None and row.half_life < 0 for row in rows)
        summary = {'hla': hla, 'identifier_category': category, 'rows': len(rows),
            'zero_count': len(zeros), 'zero_fraction': _fraction(len(zeros), len(rows)),
            'positive_count': len(positive), 'negative_count': negatives, 'zero_source_lines': zeros,
            'zero_text_representations': dict(sorted(Counter(row.half_life_text for row in rows if row.half_life == 0).items())),
            'positive_half_life': _distribution(positive)}
        allele_summaries.append(summary)
        group = groups[category]
        group['allele_count'] += 1
        for key, count in [('rows', len(rows)), ('zero', len(zeros)), ('positive', len(positive)), ('negative', negatives)]:
            group[key] += count
    for group in groups.values():
        group['zero_fraction'] = _fraction(group['zero'], group['rows'])
    positive_rows = [row for row in records if row.half_life is not None and row.half_life > 0]
    positive_counts = Counter(row.half_life for row in positive_rows)
    small = [{'half_life_hours_decimal': str(value), 'count': positive_counts[value],
              'text_representations': dict(sorted(Counter(row.half_life_text for row in positive_rows if row.half_life == value).items()))}
             for value in sorted(positive_counts)[:10]]
    zeros = [row for row in records if row.half_life == 0]
    high = [{'hla': summary['hla'], 'rows': summary['rows'], 'zero_count': summary['zero_count'],
             'zero_fraction': summary['zero_fraction']} for summary in allele_summaries
            if 2 * summary['zero_count'] >= summary['rows']]
    high.sort(key=lambda item: (-Fraction(item['zero_count'], item['rows']), item['hla']))
    common = {'source_id': source.source_id, 'raw_path': str(target.absolute()), 'raw_sha256': checksum}
    zero_report = {**common, 'observation_count': len(records), 'zero_count': len(zeros),
        'zero_fraction': _fraction(len(zeros), len(records)),
        'zero_text_representations': dict(sorted(Counter(row.half_life_text for row in zeros).items())),
        'zero_source_lines': [row.source_line_number for row in zeros],
        'groups': groups, 'alleles': allele_summaries, 'smallest_positive_values': small,
        'positive_reported_decimal_places': dict(sorted(Counter(str(max(0, -row.half_life.as_tuple().exponent)) for row in positive_rows).items())),
        'precision_interpretation': 'Textual decimal places only; not established assay precision, rounding rule, or detection limit.',
        'positive_half_life': _distribution([row.half_life for row in positive_rows]),
        'high_zero_fraction_rule': 'Descriptive flag: exact-zero fraction >= 0.5; not a statistical test or eligibility filter.',
        'high_zero_fraction_alleles': high,
        'zero_semantics': 'unresolved; numeric zero alone establishes none of physical zero, synthetic origin, missingness, rounding, or censoring',
        'limits_evidence_ids': ['zero_reporting_limits', 'c67s_explanation']}
    ordinary = [summary for summary in allele_summaries if summary['identifier_category'].startswith('ordinary_')]
    annotated = [summary for summary in allele_summaries if summary['identifier_category'] == 'c67s_annotated_hla_b']
    context = {**common, 'total_original_identifiers': len(by_allele), 'total_rows': len(records),
        'ordinary_partition': {'identifiers': len(ordinary), 'rows': sum(x['rows'] for x in ordinary)},
        'c67s_partition': {'identifiers': len(annotated), 'rows': sum(x['rows'] for x in annotated)},
        'unexpected_partition': {'identifiers': groups['unexpected']['allele_count'], 'rows': groups['unexpected']['rows']},
        'c67s_alleles': annotated, 'group_totals': groups,
        'interpretation': 'Descriptive partitions only. No raw identifiers changed; no wild-type equivalence or training exclusion approved.',
        'task11_inventory': structure}
    return AuditResult({'zero_value_audit.json': zero_report, 'allele_context_audit.json': context,
        'publication_reconciliation.json': {**common, **reconcile(by_allele, register)},
        'evidence_register.json': register}, records)


def write_audit(result: AuditResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    """Explicit reports only, in an existing valid run; completion record published last."""
    storage = resolve_paths() if paths is None else paths
    directory = Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name != 'reports' or directory.parent.parent != storage.project_runs_dir:
        raise ValueError('Reports directory must be an existing project run /reports directory')
    manifest = runs.load_manifest(directory.parent.name, paths=storage)
    source_report = result.reports['zero_value_audit.json']
    expected_input = {'path': source_report['raw_path'], 'sha256': source_report['raw_sha256']}
    if expected_input not in manifest['data_provenance']['input_artifacts']:
        raise ValueError('Run manifest must explicitly record this raw input and checksum')
    if raw.sha256_file(source_report['raw_path']) != source_report['raw_sha256']:
        raise ValueError('Raw file changed before audit report publication')
    names = [*result.reports, 'row_flags.jsonl', 'audit_report_checksums.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:
                os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError(f'Audit output already exists: {name}')
    for name, report in result.reports.items():
        raw.write_report(directory / name, report, paths=storage)
    raw.write_text_report(directory / 'row_flags.jsonl', row_flags_jsonl(result.records), paths=storage)
    checksums = {'source_id': raw.SOURCE_ID, 'raw_sha256': result.reports['zero_value_audit.json']['raw_sha256'],
        'row_count': len(result.records), 'completion': 'all_audit_reports_written',
        'reports': {name: raw.sha256_file(directory / name) for name in names[:-1]}}
    if raw.sha256_file(source_report['raw_path']) != source_report['raw_sha256']:
        raise ValueError('Raw file changed during audit report publication; no completion record written')
    raw.write_report(directory / names[-1], checksums, paths=storage)
    return checksums
