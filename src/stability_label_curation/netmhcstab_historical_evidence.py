"""Offline historical evidence audit; no original-table parser or row-overlap claim."""

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import urlsplit

from . import netmhcstabpan_2016 as raw
from . import dtu2016_source_audit as context
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

EVIDENCE_CONFIG = 'configs/netmhcstab_2013_evidence.json'
SCOPES = {'publication', 'dataset', 'model_training', 'preprocessing', 'artifact_discovery'}


def _https(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError('Evidence URL must be a string')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Evidence requires public HTTPS URLs without credentials')


def _digest(value: Any, length: int = 64) -> None:
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{' + str(length) + '}', value):
        raise ValueError('Invalid pinned checksum or commit identity')


def validate_evidence(document: dict[str, Any]) -> dict[str, Any]:
    """Validate captured evidence, not scientific truth; conditional gate stays closed."""
    try:
        if document['schema_version'] != 1 or document['source_id'] != 'netmhcstab_2013':
            raise ValueError('Unsupported historical evidence schema/source')
        if document['historical_source_recovered'] is not False:
            raise ValueError('This evidence-only implementation cannot certify a recovered original table')
        stamp = datetime.fromisoformat(document['accessed_at_utc'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('Access time must be UTC')
        publication = document['publication']
        if publication['doi'] != '10.1111/imm.12160' or publication['count_basis'] != 'published_expectation':
            raise ValueError('Historical publication identity/count basis mismatch')
        counts = publication['table_1_counts']
        if not counts or any(not raw.ALLELE_PATTERN.fullmatch(k) or type(v) is not int or v <= 0 for k,v in counts.items()):
            raise ValueError('Invalid published allele/count entries')
        if sum(counts.values()) != publication['expected_rows'] or len(counts) != publication['expected_alleles']:
            raise ValueError('Published Table 1 arithmetic mismatch')
        _https(publication['url'])
        seen = set()
        for item in document['evidence']:
            if not item['evidence_id'] or item['evidence_id'] in seen:
                raise ValueError('Evidence IDs must be unique and nonempty')
            seen.add(item['evidence_id'])
            _https(item['url'])
            if item['status'] not in {'confirmed', 'unresolved'} or item['scope'] not in SCOPES:
                raise ValueError('Invalid evidence status/scope')
            if any(not isinstance(item[k], str) or not item[k].strip() for k in ('location','statement','does_not_establish')):
                raise ValueError('Evidence must preserve location and limits')
        if not seen:
            raise ValueError('Empty evidence register')
        for item in document['discovery']:
            _https(item['url'])
        tls = document['tlstab']
        _https(tls['url']); _digest(tls['external_commit'], 40)
        if tls['count_basis'] != 'published_expectation' or type(tls['expected_rows']) is not int or tls['expected_rows'] <= 0:
            raise ValueError('Invalid TLStab published expectation')
        artifact = tls['secondary_artifact']
        target = PurePosixPath(artifact['relative_path'])
        if target.is_absolute() or '..' in target.parts or str(target) != artifact['relative_path']:
            raise ValueError('Unsafe artifact relative path')
        if artifact['classification'] != 'secondary_reprocessed_source':
            raise ValueError('Secondary release cannot replace the original source')
        _digest(artifact['sha256']); _digest(artifact['git_blob_sha'], 40)
        _https(artifact['source_url']); _https(artifact['final_url'])
        if type(artifact['byte_size']) is not int or artifact['byte_size'] < 0:
            raise ValueError('Invalid artifact size')
        if artifact['publisher_verified_checksum'] is not None:
            raise ValueError('No publisher checksum has been established for this evidence')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Incomplete or invalid historical evidence register') from error
    return document


def load_evidence(path: str | Path | None = None, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    target = storage.repository_root / EVIDENCE_CONFIG if path is None else Path(path)
    with raw._read_file(target) as stream:
        value = json.load(stream, object_pairs_hook=context._unique_json)
    if not isinstance(value, dict):
        raise ValueError('Evidence must be a JSON object')
    return validate_evidence(value)


def secondary_inventory(path: str | Path, artifact: dict[str, Any]) -> dict[str, Any]:
    """Actual released three-column score CSV, kept separate from historical measurements."""
    checksum = raw.sha256_file(path)
    if checksum != artifact['sha256']:
        raise ValueError('Secondary artifact checksum mismatch; no inventory performed')
    alleles: Counter[str] = Counter(); lengths: Counter[int] = Counter(); numeric: Counter[str] = Counter({k:0 for k in ('zero','positive','negative','missing','non_numeric','non_finite','outside_unit_interval')})
    keys: dict[tuple[str, str], list[tuple[int, str, Decimal | None]]] = defaultdict(list)
    malformed = []; zero_lines = []; zero_text: Counter[str] = Counter(); count = 0
    with raw._read_file(path) as stream:
        size = os.fstat(stream.fileno()).st_size
        blob = hashlib.sha1(b'blob ' + str(size).encode() + b'\0')
        while block := stream.read(raw.CHUNK_SIZE):
            blob.update(block)
        if size != artifact['byte_size'] or blob.hexdigest() != artifact['git_blob_sha']:
            raise ValueError('Secondary artifact size or pinned Git blob mismatch')
        stream.seek(0)
        with io.TextIOWrapper(stream, encoding='utf-8', newline='') as text:
            reader = csv.reader(text)
            columns = next(reader, None)
            if columns != ['allele','peptide','measurement_value']:
                raise ValueError('Unexpected released secondary CSV schema')
            for cells in reader:
                line = reader.line_num
                count += 1
                if len(cells) != 3 or not cells[0] or not cells[1]:
                    malformed.append(line); continue
                allele, peptide, value_text = cells
                alleles[allele] += 1; lengths[len(peptide)] += 1
                try:
                    parsed = raw.parse_record('x x ' + value_text, line)
                    value, issue = parsed.half_life, parsed.numeric_issue
                except ValueError:
                    value, issue = None, 'missing' if not value_text else 'non_numeric'
                numeric[issue or ('zero' if value == 0 else 'positive' if value > 0 else 'negative')] += 1
                if value == 0:
                    zero_lines.append(line); zero_text[value_text] += 1
                if value is not None and not 0 <= value <= 1:
                    numeric['outside_unit_interval'] += 1
                keys[allele,peptide].append((line,value_text,value))
    if raw.sha256_file(path) != checksum:
        raise ValueError('Secondary input changed during inventory')
    duplicates = [rows for rows in keys.values() if len(rows) > 1]
    return {'path':str(Path(path).absolute()), 'sha256':checksum, 'byte_size':size,
            'git_blob_sha':blob.hexdigest(), 'classification':artifact['classification'],
            'columns':columns, 'row_count':count, 'total_physical_lines':reader.line_num,
            'header_record_count':1, 'allele_count':len(alleles),
            'counts_by_original_allele':dict(sorted(alleles.items())),
            'peptide_length_distribution':{str(k):v for k,v in sorted(lengths.items())},
            'malformed_source_lines':malformed, 'numeric_counts':dict(sorted(numeric.items())),
            'zero_source_lines':zero_lines, 'zero_text_representations':dict(sorted(zero_text.items())),
            'duplicate_keys':len(duplicates), 'duplicate_extra_rows':sum(len(rows)-1 for rows in duplicates),
            'conflicting_valid_score_keys':sum(len({value for _,_,value in rows if value is not None}) > 1 for rows in duplicates),
            'duplicate_source_lines':[ [line for line,_,_ in rows] for rows in duplicates],
            'measurement_representation':artifact['measurement_representation'],
            'row_origin':'secondary_reprocessed_row_origin_unverified',
            'zero_semantics':'unresolved; no measured/synthetic/missing/censored designation assigned'}


def audit(*, paths: StoragePaths | None = None, evidence_path: str | Path | None = None,
          dtu_path: str | Path | None = None, expected_dtu_sha256: str = context.TASK11_LOCAL_SHA256,
          secondary_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Read-only, offline evidence audit with checksum-gated optional secondary inventory."""
    storage = resolve_paths() if paths is None else paths
    evidence = load_evidence(evidence_path, paths=storage)
    target = load_manifest(paths=storage).get(raw.SOURCE_ID).target_path(storage) if dtu_path is None else Path(dtu_path)
    _digest(expected_dtu_sha256)
    if raw.sha256_file(target) != expected_dtu_sha256:
        raise ValueError('Immutable DTU checksum mismatch; no analysis performed')
    inputs = [{'path':str(target.absolute()),'sha256':expected_dtu_sha256}]
    artifact = evidence['tlstab']['secondary_artifact']
    secondary = storage.project_data_dir / artifact['relative_path'] if secondary_path is None else Path(secondary_path)
    inventory: dict[str, Any] = {'status':'not_locally_available', 'row_count':None}
    if secondary_path is not None or secondary.exists() or secondary.is_symlink():
        inventory = {'status':'inventoried', **secondary_inventory(secondary,artifact)}
        inputs.append({'path':inventory['path'],'sha256':inventory['sha256']})
    table = evidence['publication']
    observed = inventory['row_count']
    reports = {'historical_source_evidence_register.json':evidence,
        'artifact_discovery_report.json':{'historical_source_recovered':False,'sources_examined':evidence['discovery'],
            'access_limitations':evidence['access_limitations'],'acquisition_deviation':evidence['acquisition_deviation'],
            'inputs_read':inputs,'secondary_artifact':inventory,'external_commit':evidence['tlstab']['external_commit']},
        'published_count_comparison.json':{'original_table_1_counts':table['table_1_counts'],
            'published_rows':table['expected_rows'],'published_alleles':table['expected_alleles'],
            'published_table_sum':sum(table['table_1_counts'].values()),'count_basis':'published_expectation',
            'original_locally_observed_rows':None,'original_row_count_reconciliation':'not_possible_without_original_table'},
        'tlstab_discrepancy_assessment.json':{'original_published_rows':table['expected_rows'],
            'tlstab_published_rows':evidence['tlstab']['expected_rows'],'published_count_difference':evidence['tlstab']['expected_rows']-table['expected_rows'],
            'secondary_observed_rows':observed,'secondary_minus_original_published':None if observed is None else observed-table['expected_rows'],
            'secondary_minus_tlstab_published':None if observed is None else observed-evidence['tlstab']['expected_rows'],
            'secondary_total_physical_lines':inventory.get('total_physical_lines'),
            'header_counting_hypothesis':'A matching physical line count does not verify that the publication included a header in its reported record count.',
            'explanation_status':'unresolved; original table and versioned IEDB export/assay lineage unavailable',
            'secondary_per_allele_counts':inventory.get('counts_by_original_allele'),
            'known_processing_evidence_ids':['secondary_processing','secondary_score','secondary_duplicates'],
            'source_equivalence_established':False},
        'conditional_row_overlap_summary.json':{'status':'not_computed_original_measurement_table_not_recovered',
            'strict_key_overlap':None,'numerical_agreement':None,'zero_value_overlap':None,
            'historical_rows_absent_from_dtu':None,'dtu_rows_absent_from_historical':None,
            'dtu_identity':inputs[0],'reason':'An author-released secondary score table is not an adequately authenticated original measurement table.',
            'spearmint_independent_input':False,'training_eligibility_decisions':'deferred'}}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Input changed during evidence audit')
    return reports


def write_reports(reports: dict[str, dict[str, Any]], reports_dir: str | Path,
                  *, paths: StoragePaths | None = None) -> dict[str, Any]:
    """Explicit non-overwriting reports in one existing run with matching hashed inputs."""
    storage = resolve_paths() if paths is None else paths
    directory = Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name != 'reports' or directory.parent.parent != storage.project_runs_dir:
        raise ValueError('Reports must be in an existing project run reports directory')
    manifest = runs.load_manifest(directory.parent.name, paths=storage)
    inputs = reports['artifact_discovery_report.json']['inputs_read']
    for item in inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Run must record each unchanged explicit input')
    names = [*reports, 'historical_report_checksums.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:
                os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError('Audit output already exists: ' + name)
    for name, document in reports.items():
        raw.write_report(directory/name,document,paths=storage)
    checksums = {'reports':{name:raw.sha256_file(directory/name) for name in reports},
                 'completion':'evidence_audit_only; historical_row_overlap_not_computed','inputs':inputs}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Input changed before completion record')
    raw.write_report(directory/names[-1],checksums,paths=storage)
    return checksums
