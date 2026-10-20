"""Task 2.28 processed-source acquisition and replicate detection curation.

No spectra processing, model loading, stability prediction or association tests.
All external inputs and generated artifacts use resolved project storage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import gzip
import math
from pathlib import Path
import platform
import resource
import subprocess
import time
import urllib.request
from urllib.parse import urlparse
import zipfile

from .paths import StoragePaths, resolve_paths

RUN = 'task-2_28-replicate-el-detection-curation'
SOURCE = 'replicate_immunopeptidomics_task2_28'
ALPHABET = frozenset('ACDEFGHIKLMNPQRSTVWY')
CONFIG = 'configs/replicate_immunopeptidomics_task2_28.json'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def acquire(paths: StoragePaths, relative: str, url: str, *, maximum_bytes: int = 20_000_000) -> Path:
    """Bounded original-source download with immutable URL/HTTP/hash receipt."""
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Source destination must be relative')
    if Path(urlparse(url).path).suffix.lower() in ('.raw', '.mzml', '.mzxml'):
        raise ValueError('MS raw/spectra acquisition is outside this task')
    target = paths.project_data_dir / SOURCE / relative
    receipt_path = target.with_name(target.name+'.provenance.json')
    if target.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['url'] != url or receipt['sha256'] != sha256(target):
            raise ValueError('Existing source identity differs')
        return target
    request = urllib.request.Request(url, headers={'User-Agent': 'stability-label-curation/Task2.28 (scientific data curation)'})
    with urllib.request.urlopen(request, timeout=45) as response:
        length = response.headers.get('Content-Length')
        if length and int(length) > maximum_bytes:
            raise ValueError('Source exceeds explicit acquisition bound')
        data = response.read(maximum_bytes+1)
        if len(data) > maximum_bytes:
            raise ValueError('Source exceeds explicit acquisition bound')
        receipt = {'url': url, 'resolved_url': response.url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                   'HTTP_status': response.status, 'HTTP_headers': dict(response.headers),
                   'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    write_json(receipt_path, receipt)
    return target


class RangeZip(io.RawIOBase):
    """Read only selected original ZIP members; retain every HTTP byte range.

    Responses must honor exact ranges and fixed archive size/ETag. zipfile checks
    member CRC32. A declared whole-archive checksum is not claimed verified when
    only ranges are acquired. No archive member is executed or auto-extracted.
    """
    def __init__(self, paths: StoragePaths, relative: str, url: str, size: int):
        self.paths, self.relative, self.url, self.size = paths, relative, url, size
        self.position = 0
        self.cache_start, self.cache = 0, b''
        self.etag: str | None = None

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        self.position = offset if whence == 0 else self.position+offset if whence == 1 else self.size+offset
        if self.position < 0:
            raise ValueError('Negative ZIP seek')
        return self.position

    def read(self, size: int = -1) -> bytes:
        size = min(self.size-self.position, self.size if size < 0 else size)
        if size <= 0:
            return b''
        start, end = self.position, self.position+size
        if not (self.cache_start <= start and end <= self.cache_start+len(self.cache)):
            stop = min(self.size, start+max(size, 65536))
            if stop-start > 160_000_000:
                raise ValueError('Selected compressed member exceeds acquisition bound')
            path = self.paths.project_data_dir / SOURCE / self.relative / f'bytes_{start}_{stop-1}.bin'
            receipt_path = path.with_name(path.name+'.provenance.json')
            if path.exists():
                receipt = json.loads(receipt_path.read_text())
                if receipt['url'] != self.url or sha256(path) != receipt['sha256']:
                    raise ValueError('Cached original range changed')
                data = path.read_bytes()
            else:
                request = urllib.request.Request(self.url, headers={'Range': f'bytes={start}-{stop-1}',
                            'User-Agent': 'stability-label-curation/Task2.28'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{stop-1}/{self.size}':
                        raise ValueError('Server did not honor bounded source range')
                    data = response.read(stop-start+1)
                    receipt = {'url': self.url, 'HTTP_status': 206, 'HTTP_headers': dict(response.headers),
                               'start': start, 'stop_exclusive': stop, 'archive_bytes': self.size,
                               'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                               'retrieved_utc': datetime.now(timezone.utc).isoformat()}
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream:
                    stream.write(data)
                write_json(receipt_path, receipt)
            if len(data) != stop-start:
                raise ValueError('Incomplete original ZIP range')
            etag = receipt['HTTP_headers'].get('ETag')
            if self.etag is not None and etag != self.etag:
                raise ValueError('Archive changed between ranges')
            self.etag = etag
            self.cache_start, self.cache = start, data
        result = self.cache[start-self.cache_start:end-self.cache_start]
        self.position = end
        return result


def acquire_member(paths: StoragePaths, archive: zipfile.ZipFile, member: str,
                   relative: str, *, archive_url: str) -> Path:
    target = paths.project_data_dir / SOURCE / relative
    if target.exists():
        receipt = json.loads(target.with_name(target.name+'.provenance.json').read_text())
        if receipt['member'] != member or receipt['sha256'] != sha256(target):
            raise ValueError('Selected member identity changed')
        return target
    info = archive.getinfo(member)
    if info.file_size > 2_000_000_000:
        raise ValueError('Selected expanded member too large')
    # zipfile verifies CRC32 before returning the member's complete content.
    data = archive.read(member)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    write_json(target.with_name(target.name+'.provenance.json'), {
        'archive_url': archive_url, 'member': member, 'member_CRC32': f'{info.CRC:08x}',
        'member_header_offset': info.header_offset, 'compressed_bytes': info.compress_size,
        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'CRC32_verified': True,
        'whole_archive_checksum_verified': False})
    return target


def tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t', strict=True))


def is_class_i(experiment: str) -> bool:
    return experiment.startswith(('HLApI_', 'HLAIp_', 'UWB1289_'))


def make_groups(designs: dict[str, list[dict[str, str]]]) -> list[dict]:
    """Published design, independent of peptide detections or predicted scores."""
    groups = []

    def add(block: str, name: str, sample: str, condition: str, replicate_type: str,
            units: list[list[str]], input_amount: str, *, diagnostic: bool = False) -> None:
        mapping = {r['Experiment']: r['Name']+'.raw' for r in designs[block]}
        if len(mapping) != len(designs[block]):
            raise ValueError('One original run per experiment expected')
        experiments = [e for unit in units for e in unit]
        if len(set(experiments)) != len(experiments) or not all(is_class_i(e) and e in mapping for e in experiments):
            raise ValueError('Missing, repeated or class-II group experiment')
        groups.append({'group_id': 'PXD006939:'+name, 'block': block, 'sample': sample,
                       'condition': condition, 'replicate_type': replicate_type,
                       'input_amount': input_amount, 'instrument_diagnostic': diagnostic,
                       'units': [{'unit_id': str(i), 'experiments': es, 'raw_files': [mapping[e] for e in es]}
                                 for i, es in enumerate(units, 1)],
                       'n_available_replicates': len(units), 'repeat_comparison_available': len(units) >= 2})

    for sample in ('CD165', 'CM647', 'JY', 'PD42', 'RA957', 'TIL1', 'TIL3'):
        prefix = 'HLApI_'+('CD165spike' if sample == 'CD165' else sample)+'_'
        units = [[prefix+str(i)] for i in (1, 2, 3)]
        # RA957 separators are part of the original experiment names.
        if sample == 'RA957':
            units = [[prefix+str(i)+'_'+suffix for suffix in ('R1', 'R2')] for i in (1, 2, 3)]
        add('plates_1_2', 'plate1_'+sample, sample,
            'baseline; published heavy-standard spike protocol' if sample == 'CD165' else 'baseline',
            'preparation aliquots of pooled lysate', units, '1e8 cells per preparation; 1/3 eluate per injection')
        if sample == 'RA957':
            for i, unit in enumerate(units, 1):
                add('plates_1_2', f'plate1_RA957_instrument_{i}', sample, 'baseline; same preparation '+str(i),
                    'instrument reinjection', [[e] for e in unit], 'same eluate; 1/3 per injection', diagnostic=True)
    for sample, n, amount in [('3830-NJF', 3, '0.7-1 g section; 1/3 injected'),
                               ('3849-BR', 2, '0.7-1 g section; 1/3 injected'),
                               ('3865-DM', 1, '1.39 g section; 1/3 injected'),
                               ('3912-BAM', 1, '1.47 g section; 1/3 injected')]:
        add('plates_1_2', 'plate2_'+sample, sample, 'untreated primary meningioma; same patient',
            'biological tissue sections with preparation variation',
            [['HLApI_'+sample+'_'+str(i)] for i in range(1, n+1)], amount)
    # 1e8 uses the same three RAW files as plate1 CD165; retain the source view,
    # but do not manufacture three additional measurements from reprocessing.
    for amount in ('1e7', '3e7', '5e7', '7e7'):
        add('plate_3_class_I', 'plate3_CD165_'+amount, 'CD165', 'baseline; cell input '+amount,
            'preparation aliquots at fixed cell input',
            [['HLApI_CD165_'+amount+'_'+str(i)] for i in (1, 2, 3)], amount+' cells; 1/3 injected')
    for condition in ('ctrl', 'IFNg'):
        add('plate_4_separate', 'plate4_UWB1289_'+condition, 'UWB1.289',
            'untreated' if condition == 'ctrl' else 'IFNg 24h; 100 IU/ml',
            'biological cell pellets processed in parallel',
            [['UWB1289_'+condition+'_'+str(i)] for i in (1, 2, 3, 4)], '1.5e8 cells; 1/2 injected')
    add('interplate', 'interplate_JY', 'JY', 'baseline; preparation dates 2017-04-21/05-09/05-16',
        'between-day preparation/batch; independent culture status not established',
        [[r['Experiment']] for r in designs['interplate'] if is_class_i(r['Experiment'])],
        '1e8 cells; 1/3 injected')
    return groups


def read_peptides(path: Path, block: str, experiments: list[str], config: dict) -> tuple[list[dict], dict]:
    """Retain source evidence and explicit states, never infer IDs from intensity."""
    result, reasons, states = [], Counter(), Counter()
    seen = set()
    with path.open(newline='') as stream:
        columns = next(csv.reader([next(stream)], delimiter='\t', strict=True))
        required = {'Sequence', 'Length', 'Reverse', 'Potential contaminant', 'PEP', 'Score', 'id'}
        if not required <= set(columns) or len(columns) != len(set(columns)):
            raise ValueError('Missing/ambiguous MaxQuant peptide fields')
        if {c.removeprefix('Identification type ') for c in columns if c.startswith('Identification type ')} != set(experiments):
            raise ValueError('Identification columns do not match original run design')
        for index, line in enumerate(stream, 1):
            cells = next(csv.reader([line], delimiter='\t', strict=True))
            if len(cells) != len(columns):
                raise ValueError('Malformed physical peptide source row')
            raw = dict(zip(columns, cells, strict=True))
            sequence = raw['Sequence'].strip().upper()
            reasons['source_rows'] += 1
            reason = ('reverse' if raw['Reverse'] == '+' else 'contaminant' if raw['Potential contaminant'] == '+'
                      else 'invalid_or_non_9mer' if len(sequence) != 9 or not set(sequence) <= ALPHABET else None)
            if reason:
                reasons[reason] += 1
                continue
            if int(raw['Length']) != len(sequence) or sequence in seen:
                raise ValueError('Inconsistent length or duplicate base sequence in source view')
            seen.add(sequence)
            identifications = {e: config['identification_states'][raw['Identification type '+e]] for e in experiments}
            selected = {e: v for e, v in identifications.items() if is_class_i(e)}
            if not any(v != 'not_identified' for v in selected.values()):
                reasons['no_class_I_identification'] += 1
                continue
            for value in selected.values():
                states[value] += 1
            result.append({'source_id': f'PXD006939:{block}:peptides.txt:row:{index}:id:{raw["id"]}',
                           'block': block, 'source_row_index': index, 'source_line_number': index+1,
                           'source_row_sha256': hashlib.sha256(line.encode()).hexdigest(),
                           'original_peptide': raw['Sequence'], 'peptide': sequence,
                           'source_peptide_id': raw['id'], 'PEP_original': raw['PEP'], 'score_original': raw['Score'],
                           'proteins_original': raw.get('Proteins'), 'gene_names_original': raw.get('Gene names'),
                           'modification_peptide_IDs_original': raw.get('Mod. peptide IDs'),
                           'evidence_IDs_original': raw.get('Evidence IDs'), 'MSMS_IDs_original': raw.get('MS/MS IDs'),
                           'identifications': selected,
                           'intensities_original': {e: raw['Intensity '+e] for e in selected},
                           'allele_specific_restriction': None,
                           'chemical_modification_state': 'base sequence; modification states aggregated by source'})
    return result, {'row_counts': dict(reasons), 'retained_9mer_rows': len(result), 'class_I_state_counts': dict(states)}


def detection_matrix(rows: list[dict], group: dict) -> tuple[list[dict], dict]:
    result = []
    for row in rows:
        units = []
        for unit in group['units']:
            states = [row['identifications'][e] for e in unit['experiments']]
            direct, any_identified = 'direct_msms' in states, any(s != 'not_identified' for s in states)
            units.append({'unit_id': unit['unit_id'], 'direct_msms': int(direct),
                          'transfer_only': int(any_identified and not direct),
                          'any_identification': int(any_identified), 'original_states': states})
        direct, any_id = sum(u['direct_msms'] for u in units), sum(u['any_identification'] for u in units)
        if not any_id:
            continue
        denominator = len(units)
        result.append({'group_id': group['group_id'], 'sample': group['sample'], 'peptide': row['peptide'],
                       'source_id': row['source_id'], 'n_available_replicates': denominator,
                       'n_detected_direct': direct, 'n_detected_including_transfer': any_id,
                       'direct_detection_frequency': direct/denominator,
                       'reported_detection_frequency': any_id/denominator,
                       'direct_union_member': direct > 0, 'units': units,
                       'allele_specific_restriction': None})
    return result, {'group_id': group['group_id'], 'sample': group['sample'],
                    'replicate_type': group['replicate_type'], 'condition': group['condition'],
                    'n_available_replicates': group['n_available_replicates'],
                    'instrument_diagnostic': group['instrument_diagnostic'],
                    'repeat_comparison_available': group['repeat_comparison_available'],
                    'reported_union_peptides': len(result),
                    'direct_union_peptides': sum(r['direct_union_member'] for r in result),
                    'direct_count_distribution_reported_union': dict(sorted(Counter(r['n_detected_direct'] for r in result).items())),
                    'direct_count_distribution_direct_union': dict(sorted(Counter(r['n_detected_direct'] for r in result if r['direct_union_member']).items())),
                    'including_transfer_count_distribution': dict(sorted(Counter(r['n_detected_including_transfer'] for r in result).items()))}


def write_gzip_rows(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as file, gzip.GzipFile(fileobj=file, mode='wb', mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, sort_keys=True, allow_nan=False)+'\n').encode())


def curate(paths: StoragePaths) -> dict:
    started = time.monotonic()
    config = json.loads((paths.repository_root / CONFIG).read_text())
    if config['task'] != '2.28' or any(config[k] for k in ('association_authorized', 'training_authorized', 'stability_predictions_authorized')):
        raise ValueError('Invalid task scope')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=paths.repository_root, text=True).strip()
    if branch != 'task/2.28-replicate-el-detection-curation':
        raise ValueError('Wrong task branch')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=paths.repository_root):
        raise ValueError('Commit curation implementation and configuration first')
    directory = paths.project_runs_dir / RUN
    write_json(directory / 'reports/curation_started.json', {'utc': datetime.now(timezone.utc).isoformat(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=paths.repository_root, text=True).strip(),
               'configuration_sha256': sha256(paths.repository_root / CONFIG),
               'code_sha256': sha256(Path(__file__)), 'training': False, 'prediction': False, 'association': False})
    source_dir = paths.project_data_dir / SOURCE / 'PXD006939/search_members'
    designs = {b: tsv(source_dir / b / 'experimentalDesignTemplate.txt') for b in config['member_roots']}
    groups = make_groups(designs)
    source_files = {}
    for block in designs:
        for name in ('experimentalDesignTemplate.txt', 'parameters.txt', 'summary.txt', 'peptides.txt'):
            file = source_dir / block / name
            receipt = json.loads(file.with_name(file.name+'.provenance.json').read_text())
            if sha256(file) != receipt['sha256'] or not receipt['CRC32_verified']:
                raise ValueError('Original selected ZIP member changed')
            source_files[str(file.relative_to(paths.project_data_dir))] = receipt
    mapping = {g['sample']: config['sample_HLA_genotype'][g['sample']] for g in groups}
    for group in groups:
        group['HLA_genotype_candidates'] = mapping[group['sample']]
        group['HLA_attribution'] = 'multi-HLA genotype; no peptide-specific restriction assigned'
        group['allele_specific_stability_eligible'] = False
    write_json(directory / 'reports/replicate_groups.json', groups)
    run_inventory, processing = [], {}
    repository_files = set()
    for file in sorted((paths.project_data_dir / SOURCE / 'PXD006939').glob('files_page_*.json')):
        if file.name.endswith('.provenance.json'):
            continue
        repository_files.update(r['fileName'] for r in json.loads(file.read_text()))
    for block, design in designs.items():
        summary = {r['Raw file']: r for r in tsv(source_dir / block / 'summary.txt') if r['Raw file']}
        parameter_rows = tsv(source_dir / block / 'parameters.txt')
        processing[block] = {r['Parameter']: r['Value'] for r in parameter_rows}
        if processing[block]['PSM FDR'] != '0.01' or processing[block]['Match between runs'] != 'True':
            raise ValueError('Unexpected original FDR/transfer configuration; do not guess')
        for row in design:
            if not is_class_i(row['Experiment']):
                continue
            original = row['Name']+'.raw'
            matched = summary[row['Name']]
            if matched['Experiment'] != row['Experiment'] or int(matched['MS/MS']) <= 0:
                raise ValueError('Unavailable/misaligned source acquisition opportunity')
            run_inventory.append({'block': block, 'experiment': row['Experiment'],
                'original_search_raw_file': original, 'exact_repository_filename_match': original in repository_files,
                'original_summary': matched, 'original_design': row})
    write_json(directory / 'reports/run_inventory.json', run_inventory)
    write_json(directory / 'reports/original_processing_parameters.json', processing)
    counts, summaries, all_rows = {}, [], {}
    for block, design in designs.items():
        rows, counts[block] = read_peptides(source_dir / block / 'peptides.txt', block,
                                           [r['Experiment'] for r in design], config)
        all_rows[block] = rows
        write_gzip_rows(directory / f'observations/{block}_9mers.jsonl.gz', rows)
        for group in [g for g in groups if g['block'] == block]:
            matrix, summary = detection_matrix(rows, group)
            slug = group['group_id'].split(':', 1)[1]
            write_gzip_rows(directory / f'matrices/{slug}.jsonl.gz', matrix)
            summaries.append(summary)
    raw_views = defaultdict(list)
    for block, design in designs.items():
        for row in design:
            if is_class_i(row['Experiment']):
                raw_views[row['Name']+'.raw'].append({'block': block, 'experiment': row['Experiment']})
    write_json(directory / 'reports/run_views_and_reuse.json', {
        'unique_class_I_raw_runs': len(raw_views), 'raw_run_views': dict(raw_views),
        'reused_raw_runs': {k: v for k, v in raw_views.items() if len(v) > 1},
        'policy': 'plate3 1e8 is the same RAW measurements as plate1 CD165; retained reprocessing view, not added measurements'})
    write_json(directory / 'reports/source_parser_counts.json', counts)
    write_json(directory / 'reports/detection_distributions.json', summaries)
    result = {'status': 'replicate_detection_curated; allele_specific_association_not_ready',
              'utc': datetime.now(timezone.utc).isoformat(), 'source_files': source_files,
              'groups': len(groups), 'noninstrument_base_groups': sum(not g['instrument_diagnostic'] for g in groups),
              'comparable_base_groups': sum(not g['instrument_diagnostic'] and g['repeat_comparison_available'] for g in groups),
              'samples': len(mapping), 'distinct_class_I_9mer_sequences_all_views': len({r['peptide'] for rows in all_rows.values() for r in rows}),
              'unique_class_I_raw_runs': len(raw_views), 'allele_specific_stability_observations': 0,
              'training_executed': False, 'predictions_executed': False, 'association_executed': False,
              'elapsed_seconds': time.monotonic()-started, 'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              'runtime': {'Python': platform.python_version(), 'platform': platform.platform()},
              'outputs': {str(f.relative_to(directory)): sha256(f) for folder in ('observations', 'matrices')
                          for f in sorted((directory / folder).iterdir())}}
    write_json(directory / 'reports/curation_complete.json', result)
    return result


def gzip_rows(path: Path) -> list[dict]:
    with gzip.open(path, 'rt') as stream:
        return [json.loads(line) for line in stream]


def assess(paths: StoragePaths) -> dict:
    """Sequence exposure and metadata support only; never read prediction scores."""
    directory = paths.project_runs_dir / RUN
    complete = json.loads((directory / 'reports/curation_complete.json').read_text())
    for name, expected in complete['outputs'].items():
        if sha256(directory / name) != expected:
            raise ValueError('Curated detection artifact changed')
    config = json.loads((paths.repository_root / CONFIG).read_text())
    groups = json.loads((directory / 'reports/replicate_groups.json').read_text())
    matrix_rows = {g['group_id']: gzip_rows(directory / 'matrices' / (g['group_id'].split(':', 1)[1]+'.jsonl.gz')) for g in groups}
    base_rows = [r for g in groups if not g['instrument_diagnostic'] for r in matrix_rows[g['group_id']]]
    comparable = [r for g in groups if not g['instrument_diagnostic'] and g['repeat_comparison_available'] for r in matrix_rows[g['group_id']]]
    peptides = {r['peptide'] for r in base_rows}
    exposures = {p: {} for p in peptides}
    reference_dir = paths.project_runs_dir / 'task-2_26-third-party-hard-split'
    freeze = json.loads((reference_dir / 'reports/benchmark_freeze.json').read_text())
    if sha256(reference_dir / 'reports/benchmark_freeze.json') != '20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557':
        raise ValueError('Actual fitting/selection reference receipt changed')
    references = {}
    for reference in ('EL_fit', 'EL_selection', 'IM_fit', 'IM_historical_development', 'prior_Mendeley_published'):
        name = f'references/{reference}.txt.gz'
        file = reference_dir / name
        if sha256(file) != freeze['immutable_artifact_hashes'][name]:
            raise ValueError('Frozen sequence exposure reference changed')
        with gzip.open(file, 'rt') as stream:
            overlap = {line.strip() for line in stream if line.strip() in peptides}
        for peptide in peptides:
            exposures[peptide][reference] = peptide in overlap
        references[reference] = {'sha256': sha256(file), 'unique_sequence_overlap': len(overlap),
            'base_group_peptide_rows_overlapping': sum(r['peptide'] in overlap for r in base_rows),
            'comparable_base_group_peptide_rows_overlapping': sum(r['peptide'] in overlap for r in comparable),
            'interpretation': 'exact sequence exposure; no peptide-specific HLA restriction inferred'}
    write_gzip_rows(directory / 'reports/peptide_sequence_exposure.jsonl.gz',
                    (dict(peptide=p, reference_overlap=exposures[p]) for p in sorted(peptides)))
    write_json(directory / 'reports/reference_overlap_summary.json', references)
    # The deployed JSON is absent on this machine. An authenticated existing
    # metadata receipt documents support for 49 canonical A/B alleles, without
    # reading any saved stability score values or assuming it lists all models.
    parent_config = json.loads((paths.repository_root / 'configs/bigmhc_fully_trained_auxiliary_task2_24.json').read_text())
    receipt_item = parent_config['inputs']['positive_score_manifest']
    receipt_file = paths.project_runs_dir / receipt_item['relative_path']
    if sha256(receipt_file) != receipt_item['sha256']:
        raise ValueError('Existing Teacher support metadata changed')
    support_receipt = json.loads(receipt_file.read_text())
    known = set(support_receipt['positive_counts_by_HLA'])
    model_item = json.loads((paths.repository_root / 'configs/el_positive_stability_analysis_v0.json').read_text())['inputs']['teacher']
    model_path = paths.project_runs_dir / model_item['relative_path']
    if model_path.exists() and sha256(model_path) != model_item['sha256']:
        raise ValueError('Teacher model identity differs')
    alleles = sorted({a for values in config['sample_HLA_genotype'].values() for a in values})
    statuses = {a: 'documented_supported_by_frozen_receipt' if a in known else
                'outside_Teacher_HLA_A_B_scope' if a.startswith('HLA-C') else
                'not_determined_from_available_support_receipt' for a in alleles}
    support = {'Teacher_expected_identity': model_item, 'Teacher_file_available': model_path.exists(),
               'support_metadata_relative_path': receipt_item['relative_path'], 'support_metadata_sha256': receipt_item['sha256'],
               'documented_supported_alleles': len(known), 'candidate_allele_status': statuses,
               'candidate_unique_alleles': len(alleles), 'candidate_status_counts': dict(Counter(statuses.values())),
               'sample_HLA_genotypes': config['sample_HLA_genotype'],
               'measured_peptide_specific_HLA_observations': 0, 'primary_within_HLA_stability_observations': 0,
               'model_retrained_or_predictions_run': False,
               'reason': 'All curated samples are multi-HLA; genotype does not establish restriction. Frozen Teacher JSON is absent on this machine.'}
    write_json(directory / 'reports/HLA_and_Teacher_compatibility.json', support)
    run_views = json.loads((directory / 'reports/run_views_and_reuse.json').read_text())
    other_files = set()
    for file in sorted((paths.project_data_dir / SOURCE / 'PXD013831').glob('files_page_*.json')):
        if not file.name.endswith('.provenance.json'):
            other_files.update(r['fileName'] for r in json.loads(file.read_text()))
    inventory = json.loads((directory / 'reports/run_inventory.json').read_text())
    repo_files = set()
    for file in sorted((paths.project_data_dir / SOURCE / 'PXD006939').glob('files_page_*.json')):
        if not file.name.endswith('.provenance.json'):
            repo_files.update(r['fileName'] for r in json.loads(file.read_text()))
    alignment = []
    for raw_file, views in run_views['raw_run_views'].items():
        alias = raw_file.replace('CD165spike_', 'CD165_')
        alignment.append({'original_search_raw_file': raw_file, 'search_views': views,
            'exact_PRIDE_filename_match': raw_file in repo_files,
            'declared_name_alias': alias if raw_file not in repo_files and alias in repo_files else None,
            'alias_basis': 'Original Table S2/search design uses CD165spike; deposited RAW names omit spike; no RAW bytes compared',
            'exact_filename_also_in_PXD013831': raw_file in other_files})
    write_json(directory / 'reports/repository_run_name_alignment.json', alignment)
    result = {'status': 'detection_reproducibility_feasible; primary_allele_specific_stability_association_blocked',
              'base_group_peptide_rows': len(base_rows), 'base_unique_peptides': len(peptides),
              'comparable_base_group_peptide_rows': len(comparable),
              'comparable_base_unique_peptides': len({r['peptide'] for r in comparable}),
              'direct_detection_counts_comparable_base_groups': dict(sorted(Counter(r['n_detected_direct'] for r in comparable).items())),
              'unique_class_I_runs': len(run_views['raw_run_views']),
              'class_I_runs_with_exact_PRIDE_names': sum(r['exact_PRIDE_filename_match'] for r in alignment),
              'source_run_name_aliases': sum(r['declared_name_alias'] is not None for r in alignment),
              'exact_source_run_names_shared_with_PXD013831': sum(r['exact_filename_also_in_PXD013831'] for r in alignment),
              'class_I_search_views_with_MSMS_counts': sum(r['original_summary']['MS/MS Identified'] != '' for r in inventory),
              'reference_overlaps': references, 'Teacher_support_status': support['candidate_status_counts'],
              'Teacher_available_on_this_machine': model_path.exists(), 'allele_specific_eligible': 0,
              'predictions_or_association_executed': False}
    write_json(directory / 'reports/technical_feasibility.json', result)
    return result


def verify_and_complete(paths: StoragePaths) -> dict:
    """Focused source-to-matrix checks and clearly separate alternative views."""
    directory = paths.project_runs_dir / RUN
    config = json.loads((paths.repository_root / CONFIG).read_text())
    complete = json.loads((directory / 'reports/curation_complete.json').read_text())
    groups = json.loads((directory / 'reports/replicate_groups.json').read_text())
    summaries = {r['group_id']: r for r in json.loads((directory / 'reports/detection_distributions.json').read_text())}
    checked = 0
    for block in config['member_roots']:
        source = gzip_rows(directory / f'observations/{block}_9mers.jsonl.gz')
        by_id = {r['source_id']: r for r in source}
        for group in [g for g in groups if g['block'] == block]:
            file = directory / 'matrices' / (group['group_id'].split(':', 1)[1]+'.jsonl.gz')
            matrix = gzip_rows(file)
            experiments = [e for unit in group['units'] for e in unit['experiments']]
            expected = [r['source_id'] for r in source if any(r['identifications'][e] != 'not_identified' for e in experiments)]
            if [r['source_id'] for r in matrix] != expected:
                raise ValueError('Incomplete or reordered peptide union')
            for row in matrix:
                original = by_id[row['source_id']]
                if row['peptide'] != original['peptide'] or row['n_available_replicates'] != len(group['units']):
                    raise ValueError('Source association/denominator mismatch')
                direct, reported = [], []
                for unit in group['units']:
                    states = [original['identifications'][e] for e in unit['experiments']]
                    direct.append(int('direct_msms' in states))
                    reported.append(int(any(s != 'not_identified' for s in states)))
                if ([r['direct_msms'] for r in row['units']] != direct or
                        [r['any_identification'] for r in row['units']] != reported or
                        row['n_detected_direct'] != sum(direct) or row['n_detected_including_transfer'] != sum(reported) or
                        row['allele_specific_restriction'] is not None):
                    raise ValueError('Detection state, attribution or nested unit mismatch')
            if dict(Counter(str(r['n_detected_direct']) for r in matrix if r['direct_union_member'])) != summaries[group['group_id']]['direct_count_distribution_direct_union']:
                raise ValueError('Saved count distribution mismatch')
            checked += len(matrix)
        if block == 'plate_3_class_I':
            design = tsv(paths.project_data_dir / SOURCE / 'PXD006939/search_members/plate_3_class_I/experimentalDesignTemplate.txt')
            mapping = {r['Experiment']: r['Name']+'.raw' for r in design}
            alternate = {'group_id': 'PXD006939:plate3_CD165_1e8_reprocessed_view', 'sample': 'CD165',
                         'condition': 'same RAW files as plate1 CD165; alternative search view',
                         'replicate_type': 'reprocessing view, not additional measurements',
                         'n_available_replicates': 3, 'instrument_diagnostic': False,
                         'repeat_comparison_available': True,
                         'excluded_from_base_group_totals': True,
                         'units': [{'unit_id': str(i), 'experiments': ['HLApI_CD165_1e8_'+str(i)],
                                    'raw_files': [mapping['HLApI_CD165_1e8_'+str(i)]]} for i in (1, 2, 3)]}
            matrix, summary = detection_matrix(source, alternate)
            write_gzip_rows(directory / 'alternative_views/CD165_1e8_reprocessed_view.jsonl.gz', matrix)
            write_json(directory / 'reports/alternative_reprocessing_view.json', {'group': alternate, 'summary': summary})
    # Explicit chemical-identity warning for spiked preparations; original light
    # counterparts are also reported, so these are flags, not fabricated labels.
    spike = ['RYKEENNDHL', 'TEYDSRVKA', 'KQAEIVKRL', 'IYTSSVNRL', 'SEVTFALHSA', 'QEVDRIKEA',
             'LEKQDWEHA', 'KVKDDVDKL', 'REYDGNIRQA', 'AERDFIHTA', 'KEWDEFQKA', 'QVISQAAVVHA',
             'AESYYRHAA', 'SQAPAVNTL', 'KLKGKEAEL']
    cd165 = gzip_rows(directory / 'matrices/plate1_CD165.jsonl.gz')
    write_json(directory / 'reports/synthetic_standard_annotations.json', {
        'source': 'original Supplemental Table S3; heavy and endogenous light counterparts',
        'Table_S3_source_sha256': sha256(paths.project_data_dir / SOURCE / 'PXD006939/Table_S3.pdf'),
        'standard_sequences': spike, 'canonical_9mer_standard_sequences': [p for p in spike if len(p) == 9],
        'plate1_CD165_9mer_sequences_matching_standards': [r['peptide'] for r in cd165 if r['peptide'] in spike],
        'applies_to': ['PXD006939:plate1_CD165', 'PXD006939:plate3_CD165_1e8_reprocessed_view'],
        'chemical_identity': 'Base sequence cannot distinguish spiked heavy and endogenous light identifications; retain raw source and flag, do not relabel.'})
    for name, expected in complete['outputs'].items():
        if sha256(directory / name) != expected:
            raise ValueError('Original curated outputs changed during completion')
    result = {'status': 'passed', 'matrix_peptide_group_rows_checked': checked,
              'original_21_matrices_preserved': True, 'alternative_reprocessing_view_saved_separately': True,
              'original_order_complete_union_and_denominators_verified': True,
              'HLA_I_only_and_no_inferred_restriction': True,
              'stability_predictions_or_association_executed': False,
              'code_sha256': sha256(Path(__file__)), 'configuration_sha256': sha256(paths.repository_root / CONFIG),
              'utc': datetime.now(timezone.utc).isoformat()}
    write_json(directory / 'reports/completion_verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('curate', 'assess', 'verify_and_complete'))
    arguments = parser.parse_args()
    print(json.dumps(globals()[arguments.stage](resolve_paths()), indent=2))
