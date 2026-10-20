"""Task 2.29A authentic monoallelic replicate feasibility and curation only.

No model prediction, learning, association or historical benchmark evaluation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import gzip
from datetime import datetime, timezone
import hashlib
import json
import platform
import re
import time
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlparse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from .paths import StoragePaths

SOURCE = 'monoallelic_replicate_rescue_task2_29a'
RUN = 'task-2_29a-monoallelic-replicate-rescue'
AA = frozenset('ACDEFGHIKLMNPQRSTVWY')


def canonical_hla(value: str) -> str:
    match = re.fullmatch(r'HLA-([AB])\*?(\d{2}):(\d{2})', value)
    if not match:
        raise ValueError(f'Not an exact two-field human HLA-A/B identity: {value}')
    return f'HLA-{match[1]}*{match[2]}:{match[3]}'


def json_lines(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def acquire(paths: StoragePaths, relative: str, url: str, *, maximum_bytes: int,
            expected_sha1: str | None = None, expected_bytes: int | None = None,
            byte_range: tuple[int, int] | None = None) -> Path:
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Relative source destination required')
    if Path(urlparse(url).path).suffix.lower() in ('.raw', '.mzml', '.mzxml', '.mgf'):
        raise ValueError('RAW and spectrum downloads are not authorized')
    target = paths.project_data_dir / SOURCE / relative
    receipt_path = target.with_name(target.name+'.provenance.json')
    if target.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['url'] != url or sha256(target) != receipt['sha256']:
            raise ValueError('Existing source identity differs')
        return target
    headers = {'User-Agent': 'stability-label-curation/Task2.29A'}
    if byte_range:
        headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        if byte_range and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(
                f'bytes {byte_range[0]}-{byte_range[1]}/')):
            raise ValueError('Server did not honor bounded feasibility read')
        length = response.headers.get('Content-Length')
        if length and int(length) > maximum_bytes:
            raise ValueError('Source exceeds explicit acquisition bound')
        data = response.read(maximum_bytes+1)
        if len(data) > maximum_bytes or (expected_bytes is not None and len(data) != expected_bytes):
            raise ValueError('Source size differs')
        if expected_sha1 and hashlib.sha1(data).hexdigest() != expected_sha1:
            raise ValueError('Original repository checksum differs')
        receipt = {'url': url, 'resolved_url': response.url, 'HTTP_status': response.status,
                   'HTTP_headers': dict(response.headers), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                   'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                   'repository_sha1_verified': expected_sha1, 'byte_range': byte_range}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    write_json(receipt_path, receipt)
    return target


def acquire_psm_table(paths: StoragePaths) -> Path:
    """Acquire only the gate-approved processed table, streaming to bounded disk."""
    gate = json.loads((paths.project_runs_dir / RUN / 'reports/immediate_feasibility_gate.json').read_text())
    if gate['status'] != 'GO_for_run_resolved_curation':
        raise ValueError('Run-resolved processed-data gate has not passed')
    filename = 'PMS_ions.mono-allelic.csv'
    root = paths.project_data_dir / SOURCE / 'PXD023064'
    metadata = next(r for r in json.loads((root / 'files_page_0.json').read_text()) if r['fileName'] == filename)
    url = next(r['value'] for r in metadata['publicFileLocations'] if r['value'].startswith('ftp:')).replace('ftp://', 'https://', 1)
    target = root / filename
    if target.exists():
        receipt = json.loads(target.with_name(filename+'.provenance.json').read_text())
        if sha256(target) != receipt['sha256']:
            raise ValueError('Original processed table changed')
        return target
    partial = root / (filename+'.part')
    initial = partial.stat().st_size if partial.exists() else 0
    if initial >= metadata['fileSizeBytes']:
        raise ValueError('Complete or oversized partial file requires explicit checksum review')
    started = time.monotonic()
    ranges = [(start, min(start+8*1024*1024, metadata['fileSizeBytes']))
              for start in range(initial, metadata['fileSizeBytes'], 8*1024*1024)]
    def fetch_range(bounds: tuple[int, int]) -> tuple[int, bytes, dict]:
        start, stop = bounds
        headers = {'User-Agent': 'stability-label-curation/Task2.29A', 'Range': f'bytes={start}-{stop-1}'}
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{stop-1}/{metadata["fileSizeBytes"]}':
                        raise ValueError('Server did not honor bounded processed-source range')
                    data = response.read(stop-start+1)
                    response_headers = dict(response.headers)
                if len(data) != stop-start:
                    raise ValueError('Incomplete processed source range')
                return start, data, response_headers
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
    total, range_receipts, etag = initial, [], None
    with partial.open('r+b' if initial else 'x+b') as stream, ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_range, bounds) for bounds in ranges]
        for future in as_completed(futures):
            start, data, response_headers = future.result()
            current_etag = response_headers.get('ETag')
            if etag is not None and current_etag != etag:
                raise ValueError('Original processed table changed between byte ranges')
            etag = current_etag
            stream.seek(start)
            stream.write(data)
            total += len(data)
            range_receipts.append({'start': start, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            print(f'Processed PSM acquisition: {total}/{metadata["fileSizeBytes"]} bytes', flush=True)
    sha1 = hashlib.sha1()
    with partial.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            sha1.update(chunk)
    if total != metadata['fileSizeBytes'] or sha1.hexdigest() != metadata['checksum']:
        raise ValueError('Original processed PSM repository checksum/size differs')
    partial.rename(target)
    write_json(target.with_name(filename+'.provenance.json'), {
        'url': url, 'HTTP_headers': response_headers, 'bytes': total,
        'sha256': sha256(target), 'repository_sha1_verified': sha1.hexdigest(),
        'retrieved_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.monotonic()-started, 'resumed_from_bytes': initial,
        'bounded_range_requests': sorted(range_receipts, key=lambda r: r['start']),
        'simultaneous_requests': 6,
        'content': 'Original processed fragment-ion PSM table; no RAW spectra downloaded'})
    return target


def xlsx_sheets(path: Path) -> dict[str, str]:
    """Original worksheet names -> ZIP member paths; no spreadsheet execution."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as archive:
        relationships = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(
            archive.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns):
            key = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = relationships[key]
            member = target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if '..' in Path(member).parts or member not in archive.namelist():
                raise ValueError('Unsafe/missing worksheet relationship')
            result[sheet.attrib['name']] = member
        return result


def xlsx_rows(path: Path, member: str) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield original Excel row numbers and column-letter values, preserving blanks."""
    prefix = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        with archive.open(member) as stream:
            for _, row in ET.iterparse(stream, events=('end',)):
                if row.tag != prefix+'row':
                    continue
                cells = {}
                for cell in row.findall(prefix+'c'):
                    column = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                    if cell.find(prefix+'f') is not None:
                        raise ValueError('Formula-valued source cells need explicit review')
                    value = cell.findtext(prefix+'v', '')
                    kind = cell.attrib.get('t')
                    if kind == 's':
                        value = strings[int(value)]
                    elif kind == 'inlineStr':
                        value = ''.join(cell.find(prefix+'is').itertext())
                    cells[column] = value
                yield int(row.attrib['r']), cells
                row.clear()


def source_metadata(root: Path) -> tuple[list[dict], list[dict], dict[tuple[str, str], list[int]]]:
    """Join author run assignments to SDRF, retaining the unprojected SDRF cells."""
    with (root / 'PXD023064_community_annotated.sdrf.tsv').open() as stream:
        reader = csv.reader(stream, delimiter='\t')
        header = next(reader)
        sdrf = {}
        for number, values in enumerate(reader, 2):
            row = dict(zip(header, values))
            raw = row['comment[data file]']
            if raw in sdrf or len(values) != len(header):
                raise ValueError('Ambiguous SDRF run identity')
            sdrf[raw] = (number, row, values)
    runs, exclusions = [], []
    path = root / 'metadata.xlsx'
    for number, cells in xlsx_rows(path, xlsx_sheets(path)['Sheet1']):
        raw, allele = cells.get('B', ''), cells.get('A', '')
        if number == 1 or not raw:
            continue
        sdrf_number, row, values = sdrf[raw]
        record = {'raw_file': raw, 'author_allele': allele, 'metadata_excel_row': number,
                  'sdrf_row': sdrf_number, 'sdrf_header': header, 'sdrf_values': values,
                  'biological_sample': row['source name'],
                  'biological_replicate': row['characteristics[biological replicate]'],
                  'technical_replicate': row['comment[technical replicate]'],
                  'dissociation_method_original': row['comment[dissociation method]']}
        if not allele.startswith('HLA-'):
            exclusions.append({**record, 'reason': 'null_control' if allele == 'Null' else 'tumor_not_monoallelic'})
            continue
        hla = canonical_hla(allele)
        if canonical_hla(row['characteristics[mhc typing]']) != hla or row['characteristics[cell line]'] != 'K562':
            raise ValueError('Author/SDRF experimental HLA identity mismatch')
        method = row['comment[dissociation method]']
        if 'MS:1000133' in method:
            method = 'CID'
        elif 'EThcD' in method or 'MS:1002631' in method:
            method = 'EThcD'
        else:
            raise ValueError(f'Unknown dissociation method: {method}')
        runs.append({**record, 'hla': hla, 'method': method})
    if len({r['raw_file'] for r in runs+exclusions}) != len(sdrf):
        raise ValueError('Run mapping is incomplete')
    accepted = defaultdict(list)
    path = root / 'peptides_filtered.xlsx'
    for number, cells in xlsx_rows(path, xlsx_sheets(path)['Mono-allelic peptides']):
        if number != 1 and cells.get('A'):
            accepted[(cells['A'], canonical_hla(cells['B']))].append(number)
    return runs, exclusions, dict(accepted)


def replicate_groups(runs: list[dict]) -> list[dict]:
    """Identity-only policy: one CID injection per biological unit; method-pure technical pairs."""
    groups = []
    cid_by_hla, same_sample, all_sample = defaultdict(list), defaultdict(list), defaultdict(list)
    for run in runs:
        all_sample[(run['hla'], run['biological_sample'])].append(run)
        same_sample[(run['hla'], run['biological_sample'], run['method'])].append(run)
        if run['method'] == 'CID' and run['technical_replicate'] == '1':
            cid_by_hla[run['hla']].append(run)
    for hla, units in sorted(cid_by_hla.items()):
        units.sort(key=lambda r: r['metadata_excel_row'])
        if len(units) >= 2:
            if len({r['biological_sample'] for r in units}) != len(units):
                raise ValueError('Repeated injection promoted to biological replicate')
            groups.append({'group_id': 'biological_'+hla, 'hla': hla, 'type': 'biological',
                           'primary_candidate': len(units) >= 3, 'method': 'CID',
                           'raw_files': [r['raw_file'] for r in units],
                           'biological_samples': [r['biological_sample'] for r in units]})
    for (hla, sample, method), units in sorted(same_sample.items()):
        units.sort(key=lambda r: r['metadata_excel_row'])
        if len(units) >= 2:
            groups.append({'group_id': 'technical_'+sample+'_'+method, 'hla': hla, 'type': 'technical',
                           'primary_candidate': False, 'method': method,
                           'raw_files': [r['raw_file'] for r in units], 'biological_samples': [sample]})
    for (hla, sample), units in sorted(all_sample.items()):
        if len({r['method'] for r in units}) > 1:
            groups.append({'group_id': 'method_comparison_'+sample, 'hla': hla,
                           'type': 'nonexchangeable_method_comparison', 'primary_candidate': False,
                           'method': 'CID_vs_EThcD', 'raw_files': [r['raw_file'] for r in units],
                           'biological_samples': [sample]})
    return groups


def freeze_design(paths: StoragePaths) -> Path:
    root = paths.project_data_dir / SOURCE / 'PXD023064'
    directory = paths.project_runs_dir / RUN
    runs, excluded, accepted = source_metadata(root)
    groups = replicate_groups(runs)
    primary = [g for g in groups if g['primary_candidate']]
    if len(runs) != 46 or len(accepted) != 47263 or len(primary) != 1 or primary[0]['raw_files'] != [
            'MSB37882A.raw', 'MSB33405A.raw', 'MSB35123A.raw']:
        raise ValueError('Reviewed source design differs')
    json_lines(directory / 'manifests/monoallelic_runs.jsonl', runs)
    json_lines(directory / 'manifests/excluded_runs.jsonl', excluded)
    write_json(directory / 'manifests/replicate_groups.json', groups)
    write_json(directory / 'manifests/design_freeze.json', {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'source': 'PXD023064',
        'source_sha256': {name: sha256(root/name) for name in (
            'metadata.xlsx', 'peptides_filtered.xlsx', 'PXD023064_community_annotated.sdrf.tsv')},
        'group_manifest_sha256': sha256(directory/'manifests/replicate_groups.json'),
        'policy': 'Published accepted peptide-HLA identities; per-run direct fragment-supported PSMs; canonical 9mers; chemical species separated.',
        'biological_selection': 'First CID injection (SDRF technical 1) per distinct biological sample in author metadata order.',
        'method_comparisons_are_replicates': False,
        'run_PSM_acceptance': 'Original supplementary code: group modified peptide/base/scan/raw/fileID; >=10 nonempty fragment-ion rows; <=2 peptide candidates per scan/raw/fileID. Also require released filtered peptide-HLA membership.',
        'chemical_policy': 'Unmodified: exact raw Peptide equals canonical pepSeq, no modification annotations, and no C (source fixed carbamidomethylation). All other canonical-base 9mer molecular species retained separately.',
        'primary_requirement': 'At least three comparable biological units; no post-score selection.',
        'scores_accessed': False, 'association_executed': False})
    return directory


def chemical_state(peptide: str, modified: str, annotations: set[str]) -> str:
    if len(peptide) != 9 or not set(peptide) <= AA:
        return 'not_canonical_9mer'
    if peptide == modified and annotations <= {'na', ''} and 'C' not in peptide:
        return 'unmodified'
    return 'modified_or_fixed_CAM'


def collect_psms(path: Path) -> tuple[dict[tuple, dict], Counter]:
    """Port only the released supplementary-code PSM grouping; retain row ranges."""
    psms, run_ions = {}, Counter()
    with path.open(newline='') as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            raw, scan, file_id = row['Source File'], row['scan'], row['fileID']
            if not raw or not scan or scan.split(':')[0] != file_id:
                raise ValueError('Unresolved original run/scan identity')
            peptide = row['pepSeq']
            if ''.join(c for c in row['Peptide'] if c.isupper()) != peptide or int(row['pepLen']) != len(peptide):
                raise ValueError('Modified/base peptide source identity mismatch')
            key = (raw, scan, file_id, row['Peptide'], peptide)
            if key not in psms:
                digest = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).hexdigest()
                psms[key] = {'psm_id': 'PXD023064:'+digest, 'raw_file': raw, 'scan': scan,
                             'file_id': file_id, 'modified_peptide': row['Peptide'], 'peptide': peptide,
                             'source_csv_row_ranges': [], 'ion_rows': 0, 'annotations': set(),
                             'protein': set(), 'RT': set(), 'precursor_mz': set(), 'charge': set()}
            psm = psms[key]
            ranges = psm['source_csv_row_ranges']
            if ranges and ranges[-1][1] == number-1:
                ranges[-1][1] = number
            else:
                ranges.append([number, number])
            psm['ion_rows'] += bool(row['ion'])
            for field, original in [('annotations', 'modification'), ('protein', 'protein'),
                                    ('RT', 'RT'), ('precursor_mz', 'm/z'), ('charge', 'z')]:
                psm[field].add(row[original])
            run_ions[raw] += 1
    candidates = Counter((key[0], key[1], key[2]) for key in psms)
    for key, psm in psms.items():
        psm['scan_peptide_candidates'] = candidates[key[:3]]
        psm['source_code_PSM_QC'] = psm['ion_rows'] >= 10 and psm['scan_peptide_candidates'] <= 2
        psm['chemical_state'] = chemical_state(psm['peptide'], psm['modified_peptide'], psm['annotations'])
        for field in ('annotations', 'protein', 'RT', 'precursor_mz', 'charge'):
            psm[field] = sorted(psm[field])
    return psms, run_ions


def matrix_rows(group: dict, detections: dict[tuple[str, str], dict[str, list[str]]],
                *, modified: bool = False) -> list[dict]:
    rows = []
    for (peptide, hla), by_run in sorted(detections.items()):
        if hla != group['hla'] or not any(raw in by_run for raw in group['raw_files']):
            continue
        states = [int(bool(by_run.get(raw))) for raw in group['raw_files']]
        comparable = group['type'] != 'nonexchangeable_method_comparison'
        rows.append({'group_id': group['group_id'], 'hla': hla,
                     'modified_peptide' if modified else 'peptide': peptide,
                     'group_type': group['type'], 'raw_files': group['raw_files'],
                     'direct_detection': states,
                     'source_psm_ids_by_run': [by_run.get(raw, []) for raw in group['raw_files']],
                     'n_available_replicates': len(states) if comparable else None,
                     'n_detected': sum(states) if comparable else None,
                     'detection_frequency': sum(states)/len(states) if comparable else None,
                     'index_detected': bool(states[0]),
                     'repeat_detection_frequency': sum(states[1:])/(len(states)-1) if comparable and states[0] else None,
                     'MBR_state': 'not_applicable_direct_PSM_export; no MBR-only calls inferred'})
    return rows


def curate(paths: StoragePaths) -> dict:
    started = time.monotonic()
    directory = paths.project_runs_dir / RUN
    root = paths.project_data_dir / SOURCE / 'PXD023064'
    if (directory/'reports/curation_summary.json').exists() or (directory/'observations/PSM_observations.jsonl').exists():
        raise ValueError('Existing curation must be preserved; refusing overwrite/re-execution')
    receipt = json.loads((root/'PMS_ions.mono-allelic.csv.provenance.json').read_text())
    if sha256(root/'PMS_ions.mono-allelic.csv') != receipt['sha256'] or receipt['repository_sha1_verified'] != '424881b5d4b2d62ed4199d73787015fab91395e2':
        raise ValueError('Unauthenticated original PSM table')
    design = json.loads((directory/'manifests/design_freeze.json').read_text())
    for name, expected in design['source_sha256'].items():
        if sha256(root/name) != expected:
            raise ValueError('Frozen source metadata changed')
    if sha256(directory/'manifests/replicate_groups.json') != design['group_manifest_sha256']:
        raise ValueError('Frozen groups changed')
    runs, excluded, accepted = source_metadata(root)
    groups = json.loads((directory/'manifests/replicate_groups.json').read_text())
    by_raw = {r['raw_file']: r for r in runs}
    psms, run_ions = collect_psms(root/'PMS_ions.mono-allelic.csv')
    if not set(by_raw) <= run_ions.keys() or set(run_ions)-set(by_raw)-{r['raw_file'] for r in excluded}:
        raise ValueError('Performed run/PSM source identity mismatch')
    unmodified, modified = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    reasons, run_counts = Counter(), defaultdict(Counter)
    for psm in psms.values():
        run = by_raw.get(psm['raw_file'])
        if not run:
            reason = 'null_control'
        elif psm['chemical_state'] == 'not_canonical_9mer':
            reason = 'not_canonical_9mer'
        elif not psm['source_code_PSM_QC']:
            reason = 'fails_published_per_PSM_QC'
        elif (psm['peptide'], run['hla']) not in accepted:
            reason = 'not_in_published_filtered_peptide_HLA_set'
        else:
            reason = psm['chemical_state']
            psm['hla'] = run['hla']
            psm['accepted_workbook_rows'] = accepted[(psm['peptide'], run['hla'])]
            target = unmodified if reason == 'unmodified' else modified
            target[(psm['peptide'] if reason == 'unmodified' else psm['modified_peptide'], run['hla'])][psm['raw_file']].append(psm['psm_id'])
        psm['curation_status'] = reason
        reasons[reason] += 1
        run_counts[psm['raw_file']][reason] += 1
    json_lines(directory/'observations/PSM_observations.jsonl', psms.values())
    group_summaries, all_rows, modified_rows = [], [], []
    for group in groups:
        rows = matrix_rows(group, unmodified)
        mod_rows = matrix_rows(group, modified, modified=True)
        all_rows.extend(rows)
        modified_rows.extend(mod_rows)
        group_summaries.append({**group, 'unmodified_9mer_union': len(rows),
                                'unmodified_index_9mers': sum(r['index_detected'] for r in rows),
                                'modified_9mer_molecular_species_union': len(mod_rows),
                                'detection_count_distribution': dict(sorted(Counter(r['n_detected'] for r in rows).items())) if group['type'] != 'nonexchangeable_method_comparison' else None,
                                'direct_9mer_counts_by_run': {raw: sum(r['direct_detection'][i] for r in rows) for i, raw in enumerate(group['raw_files'])}})
    json_lines(directory/'matrices/unmodified_9mer_group_matrices.jsonl', all_rows)
    json_lines(directory/'matrices/modified_9mer_group_matrices.jsonl', modified_rows)
    json_lines(directory/'matrices/all_monoallelic_unmodified_9mer_run_presence.jsonl', (
        {'peptide': peptide, 'hla': hla, 'raw_file_PSM_ids': dict(sorted(by_run.items()))}
        for (peptide, hla), by_run in sorted(unmodified.items())))
    primary_ids = {g['group_id'] for g in groups if g['primary_candidate']}
    json_lines(directory/'manifests/primary_biological_union.jsonl', (r for r in all_rows if r['group_id'] in primary_ids))
    json_lines(directory/'manifests/future_primary_index_cohort.jsonl', (r for r in all_rows if r['group_id'] in primary_ids and r['index_detected']))
    write_json(directory/'reports/group_summary.json', group_summaries)
    write_json(directory/'reports/run_summary.json', {
        raw: {'fragment_ion_rows': run_ions[raw], 'PSM_status_counts': dict(run_counts[raw]),
              'direct_unmodified_9mer_peptides': sum(raw in found for found in unmodified.values()),
              'direct_modified_9mer_species': sum(raw in found for found in modified.values())}
        for raw in sorted(run_ions)})
    summary = {'source_fragment_ion_rows': sum(run_ions.values()), 'source_PSM_groups': len(psms),
               'source_PSM_runs': len(run_ions), 'monoallelic_runs': len(runs),
               'monoallelic_biological_sample_identities': len({r['biological_sample'] for r in runs}),
               'source_alleles': sorted({r['hla'] for r in runs}),
               'published_filtered_peptide_HLA_pairs': len(accepted),
               'published_filtered_9mer_pairs': sum(len(p) == 9 and set(p) <= AA for p, h in accepted),
               'PSM_curation_status_counts': dict(reasons),
               'unmodified_9mer_peptide_HLA_pairs_all_runs': len(unmodified),
               'unmodified_9mer_distinct_peptides_all_runs': len({p for p, h in unmodified}),
               'modified_9mer_species_HLA_pairs_all_runs': len(modified),
               'comparable_group_peptide_rows': sum(len(matrix_rows(g, unmodified)) for g in groups if g['type'] != 'nonexchangeable_method_comparison'),
               'primary': [g for g in group_summaries if g['primary_candidate']],
               'groups_by_type': dict(Counter(g['type'] for g in groups)),
               'MBR': 'No transfer-only identifications used; every detection links to original run/scan fragment-ion PSM evidence. MBR setting not explicitly stated by authors.',
               'identification_confidence': 'Source reports 1% decoy PSM FDR, plus published per-PSM >=10 fragment-ion rows/<=2 peptide candidates and released final peptide-HLA membership. Individual PSM q values unavailable; cohort FDR not re-estimated.',
               'runtime_seconds': time.monotonic()-started, 'scores_accessed': False,
               'association_executed': False, 'training_executed': False}
    write_json(directory/'reports/curation_summary.json', summary)
    return summary


def teacher_and_exposure_feasibility(paths: StoragePaths) -> dict:
    """Read authenticated scope/restore metadata and sequence identities, never scores."""
    directory = paths.project_runs_dir / RUN
    runs, _, _ = source_metadata(paths.project_data_dir/SOURCE/'PXD023064')
    manifest = paths.project_runs_dir/'task-2_13-el-stability-weight-adapter/reports/positive_score_manifest.json'
    if sha256(manifest) != 'e79fb60b1c04f33889e9d3ecd6a7bd145255c156487cd4d4873a90c8ab715862':
        raise ValueError('Teacher support metadata identity changed')
    metadata = json.loads(manifest.read_text())
    teacher_sha = 'a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99'
    if metadata['Teacher_model_sha256'] != teacher_sha or len(metadata['supported_HLA']) != 67:
        raise ValueError('Frozen trained-allele scope differs')
    alleles = sorted({r['hla'] for r in runs})
    model = paths.project_runs_dir/'task-2_3-first-stability-teacher/checkpoints/teacher_model.json'
    fitting = paths.project_runs_dir/'task-2_3-first-stability-teacher/reports/teacher_train_val_partition.json'
    registry = paths.project_runs_dir/'task-1_8-canonical-observation-registry/reports/canonical_observations.jsonl'
    plan_path = paths.repository_root/'configs/artifact_reconstruction_plan.json'
    plan = next(g for g in json.loads(plan_path.read_text())['groups'] if g['group_id'] == 'runs:task-2_3-first-stability-teacher')
    restore_registry = paths.repository_root/'configs/artifact_registry.json'
    artifacts = json.loads(restore_registry.read_text())['artifacts']
    registered = [a['artifact_id'] for a in artifacts if 'teacher_model.json' in json.dumps(a)]
    package_manifest = paths.project_data_dir/'artifacts/packages/stability-label-curation-bigmHC-windows-checkpoints.manifest.json'
    support = {'expected_Teacher_sha256': teacher_sha,
               'scope': 'Exact human HLA-A/B per-allele 9mer ridge models; measured kinetic half-life, log1p hours. No family fallback.',
               'trained_models_in_authenticated_support_metadata': len(metadata['supported_HLA']),
               'support_metadata': {'area': 'runs', 'relative_path': str(manifest.relative_to(paths.project_runs_dir)), 'sha256': sha256(manifest)},
               'support_field_definition': 'el_stability_loss_adapter.py: supported_HLA enumerates every model with status trained, not only positive_counts_by_HLA (49 previously used groups).',
               'supported': [a for a in alleles if a in metadata['supported_HLA']],
               'unsupported_no_trained_exact_allele': [a for a in alleles if a not in metadata['supported_HLA']],
               'original_model_available': model.exists(), 'fitting_partition_available': fitting.exists(),
               'kinetic_registry_available': registry.exists(),
               'exact_Teacher_registered_artifact_ids': registered,
               'restore_registry_sha256': sha256(restore_registry), 'reconstruction_plan_sha256': sha256(plan_path),
               'registered_Teacher_reconstruction': {k: plan[k] for k in ('classification', 'exact_byte_backup', 'reason')},
               'reconstruction_requires_training': plan['recipe']['requires_training'],
               'local_checkpoint_package_manifest_sha256': sha256(package_manifest),
               'local_checkpoint_package_contains_Teacher': 'teacher_model.json' in package_manifest.read_text(),
               'restore_status': 'No exact-byte Teacher artifact in approved registry or established local checkpoint package. R2 recipe requires prohibited retraining; not executed.',
               'model_bytes_restored': False, 'score_values_opened': False, 'predictions_computed': False,
               'validation_strength': 'Support authenticates trained model availability by allele, not held-out accuracy. Original validation/fitting metadata still required before analysis.'}
    if model.exists() and sha256(model) != teacher_sha:
        raise ValueError('Unexpected Teacher checkpoint at frozen location')
    write_json(directory/'reports/Teacher_feasibility.json', support)
    # Use the existing authenticated fitting/selection identities, without opening labels or predictions.
    rows = [json.loads(line) for line in (directory/'matrices/all_monoallelic_unmodified_9mer_run_presence.jsonl').read_text().splitlines()]
    primary = [json.loads(line) for line in (directory/'manifests/primary_biological_union.jsonl').read_text().splitlines()]
    index = [r for r in primary if r['index_detected']]
    peptides = {r['peptide'] for r in rows}
    reference_dir = paths.project_runs_dir/'task-2_26-third-party-hard-split'
    freeze_path = reference_dir/'reports/benchmark_freeze.json'
    if sha256(freeze_path) != '20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557':
        raise ValueError('Training-reference identity receipt changed')
    reference_freeze = json.loads(freeze_path.read_text())
    references, flags = {}, {p: {} for p in peptides}
    for name in ('EL_fit', 'EL_selection', 'IM_fit', 'IM_historical_development', 'prior_Mendeley_published'):
        relative = f'references/{name}.txt.gz'
        file = reference_dir/relative
        if sha256(file) != reference_freeze['immutable_artifact_hashes'][relative]:
            raise ValueError('Training-reference sequence snapshot changed')
        with gzip.open(file, 'rt') as stream:
            overlaps = {p for line in stream if (p := line.strip()) in peptides}
        for peptide in peptides:
            flags[peptide][name] = peptide in overlaps
        references[name] = {'reference_sha256': sha256(file), 'distinct_peptides_overlapping': len(overlaps),
                            'peptide_HLA_pairs_overlapping': sum(r['peptide'] in overlaps for r in rows),
                            'primary_union_peptides_overlapping': sum(r['peptide'] in overlaps for r in primary),
                            'future_index_peptides_overlapping': sum(r['peptide'] in overlaps for r in index)}
    json_lines(directory/'manifests/sequence_exposure.jsonl', ({'peptide': p, 'reference_overlap': flags[p]} for p in sorted(flags)))
    write_json(directory/'reports/reference_overlap_summary.json', references)
    return support


def validate_curation(paths: StoragePaths) -> dict:
    """Check saved direct-identification links and chemical states, without re-curating."""
    directory = paths.project_runs_dir/RUN
    observations = {}
    original_rows, accepted_base_pairs = 0, set()
    with (directory/'observations/PSM_observations.jsonl').open() as stream:
        for line in stream:
            psm = json.loads(line)
            if psm['psm_id'] in observations:
                raise ValueError('Duplicate original PSM identity')
            original_rows += sum(b-a+1 for a, b in psm['source_csv_row_ranges'])
            if psm['curation_status'] in ('unmodified', 'modified_or_fixed_CAM'):
                if not psm['source_code_PSM_QC'] or not psm['accepted_workbook_rows']:
                    raise ValueError('Unsupported accepted identification')
                accepted_base_pairs.add((psm['peptide'], psm['hla']))
                observations[psm['psm_id']] = (psm['raw_file'], psm['peptide'], psm['modified_peptide'], psm['hla'], psm['chemical_state'])
    matrix_rows_checked, detection_cells, linked_ids = 0, 0, set()
    for filename, state in [('unmodified_9mer_group_matrices.jsonl', 'unmodified'),
                            ('modified_9mer_group_matrices.jsonl', 'modified_or_fixed_CAM')]:
        with (directory/'matrices'/filename).open() as stream:
            for line in stream:
                row = json.loads(line)
                matrix_rows_checked += 1
                if not len(row['raw_files']) == len(row['direct_detection']) == len(row['source_psm_ids_by_run']):
                    raise ValueError('Misaligned replicate states')
                for raw, direct, identifiers in zip(row['raw_files'], row['direct_detection'], row['source_psm_ids_by_run']):
                    if bool(identifiers) != bool(direct):
                        raise ValueError('Unsupported direct detection state')
                    detection_cells += direct
                    for identifier in identifiers:
                        evidence = observations[identifier]
                        sequence = evidence[1] if state == 'unmodified' else evidence[2]
                        if evidence[0] != raw or evidence[3:] != (row['hla'], state) or sequence != row.get('peptide', row.get('modified_peptide')):
                            raise ValueError('Matrix/original PSM run, allele or chemical identity mismatch')
                        linked_ids.add(identifier)
                if row['group_type'] == 'nonexchangeable_method_comparison':
                    if row['n_detected'] is not None or row['detection_frequency'] is not None:
                        raise ValueError('CID and EThcD incorrectly treated as replicates')
                elif row['n_detected'] != sum(row['direct_detection']) or row['n_available_replicates'] != len(row['raw_files']):
                    raise ValueError('Incorrect detection numerator/denominator')
    summary = json.loads((directory/'reports/curation_summary.json').read_text())
    if original_rows != summary['source_fragment_ion_rows']:
        raise ValueError('Original source row provenance not conserved')
    result = {'status': 'PASS', 'original_fragment_rows_conserved': original_rows,
              'matrix_rows_validated': matrix_rows_checked, 'direct_detection_cells': detection_cells,
              'linked_original_accepted_PSMs': len(linked_ids),
              'canonical_9mer_base_peptide_HLA_pairs_with_accepted_direct_PSMs': len(accepted_base_pairs),
              'scope': 'Saved source/run/HLA/chemical-state links and denominators; no new detections or scores computed.'}
    write_json(directory/'reports/curation_validation.json', result)
    return result


def finalize(paths: StoragePaths) -> dict:
    directory = paths.project_runs_dir/RUN
    summary = json.loads((directory/'reports/curation_summary.json').read_text())
    support = json.loads((directory/'reports/Teacher_feasibility.json').read_text())
    primary = [json.loads(line) for line in (directory/'manifests/primary_biological_union.jsonl').read_text().splitlines()]
    index = [r for r in primary if r['index_detected']]
    if len(primary) != 1536 or len(index) != 671 or {r['hla'] for r in primary} != {'HLA-A*02:01'}:
        raise ValueError('Reviewed primary cohort differs')
    for row in primary:
        if row['n_available_replicates'] != 3 or row['n_detected'] != sum(row['direct_detection']):
            raise ValueError('Detection numerator/denominator mismatch')
        if any(bool(ids) != bool(state) for ids, state in zip(row['source_psm_ids_by_run'], row['direct_detection'])):
            raise ValueError('Detection/source evidence mismatch')
    _, _, published = source_metadata(paths.project_data_dir/SOURCE/'PXD023064')
    observed_states = defaultdict(set)
    with (directory/'observations/PSM_observations.jsonl').open() as stream:
        for line in stream:
            psm = json.loads(line)
            if psm['curation_status'] in ('unmodified', 'modified_or_fixed_CAM'):
                observed_states[(psm['peptide'], psm['hla'])].add(psm['curation_status'])
    reconciliation = []
    for (peptide, hla), workbook_rows in sorted(published.items()):
        if len(peptide) == 9 and set(peptide) <= AA:
            states = observed_states[(peptide, hla)]
            reconciliation.append({'peptide': peptide, 'hla': hla, 'original_workbook_rows': workbook_rows,
                                   'direct_PSM_chemical_states': sorted(states),
                                   'unmodified_candidate': 'unmodified' in states,
                                   'reason': 'direct_unmodified_PSM' if 'unmodified' in states else
                                   'modified_only' if states else 'no_qualifying_run_PSM_under_released_code_QC'})
    json_lines(directory/'manifests/published_9mer_pair_reconciliation.jsonl', reconciliation)
    report = {'status': 'GO_dataset_constructed; NO_GO_association_execution_until_original_Teacher_and_fitting_validation_metadata_restored',
              'frozen_utc': datetime.now(timezone.utc).isoformat(),
              'approved_base_commit': '837e4eeed9f3debf1dd253f8a9a50c6b865892f9',
              'primary_union_peptides': len(primary), 'future_primary_index_peptides': len(index),
              'primary_hla': 'HLA-A*02:01', 'primary_biological_units': 3,
              'index_reserved_repeat_count_distribution': dict(sorted(Counter(sum(r['direct_detection'][1:]) for r in index).items())),
              'independent_biological_groups': 1, 'component_bootstrap_intervals_estimable': False,
              'all_monoallelic_unmodified_pairs': summary['unmodified_9mer_peptide_HLA_pairs_all_runs'],
              'supported_alleles': len(support['supported']),
              'published_9mer_pair_reconciliation': dict(Counter(r['reason'] for r in reconciliation)),
              'training': False, 'stability_predictions': False, 'association': False, 'A_S_P_inference': False,
              'RAW_downloads': False, 'fallback_source_needed': False,
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(), 'machine': platform.machine()},
              'source_hashes': {str(f.relative_to(paths.project_data_dir/SOURCE)): sha256(f)
                                for f in sorted((paths.project_data_dir/SOURCE).rglob('*')) if f.is_file()},
              'derived_artifact_sha256': {str(f.relative_to(directory)): sha256(f)
                                          for f in sorted(directory.rglob('*')) if f.is_file()},
              'implementation_sha256': {name: sha256(paths.repository_root/name) for name in (
                  'src/stability_label_curation/monoallelic_replicate_rescue.py',
                  'tests/test_monoallelic_replicate_rescue.py')}}
    write_json(directory/'reports/dataset_freeze.json', report)
    return report


def main() -> None:
    import argparse
    from .paths import resolve_paths
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze-design', 'curate', 'support', 'validate', 'finalize'))
    stage = parser.parse_args().stage
    action = {'freeze-design': freeze_design, 'curate': curate,
              'support': teacher_and_exposure_feasibility, 'validate': validate_curation, 'finalize': finalize}[stage]
    print(action(resolve_paths()))


if __name__ == '__main__':
    main()
