"""Task 2.30A bounded source/processed-data feasibility; no model predictions."""
from __future__ import annotations

from collections import Counter
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import ftplib
import io
import json
import math
from pathlib import Path
import ssl
import time
from urllib.parse import unquote
import urllib.request
import zipfile

from .paths import StoragePaths
from .monoallelic_replicate_rescue import sha256, write_json, xlsx_rows, xlsx_sheets

SOURCE = 'external_biological_replicates_task2_30a'
RUN = 'task-2_30a-external-biological-replicate-curation'
CONFIG = 'configs/external_biological_replicates_task2_30a.json'
AA = frozenset('ACDEFGHIKLMNPQRSTVWY')


def acquire(paths: StoragePaths, relative: str, url: str, maximum_bytes: int = 10_000_000) -> Path:
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Relative source destination required')
    lower = unquote(url).lower()
    if any(ext in lower for ext in ('.raw', '.mzml', '.mzxml', '.mgf', '.wiff', '.d.zip')):
        raise ValueError('RAW/spectrum acquisition is outside Task 2.30A')
    target = paths.project_data_dir/SOURCE/relative
    receipt_path = target.with_name(target.name+'.provenance.json')
    if target.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['url'] != url or sha256(target) != receipt['sha256']:
            raise ValueError('Existing source identity differs')
        return target
    with urllib.request.urlopen(urllib.request.Request(url, headers={
            'User-Agent': 'stability-label-curation/Task2.30A'}), timeout=45) as response:
        length = response.headers.get('Content-Length')
        if length and int(length) > maximum_bytes:
            raise ValueError('Source exceeds explicit bounded acquisition size')
        payload = response.read(maximum_bytes+1)
        if len(payload) > maximum_bytes:
            raise ValueError('Source exceeds bounded acquisition size')
        receipt = {'url': url, 'resolved_url': response.url, 'HTTP_status': response.status,
                   'HTTP_headers': dict(response.headers), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                   'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                   'maximum_bytes': maximum_bytes}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(payload)
    write_json(receipt_path, receipt)
    return target


class FTPSRanges(io.RawIOBase):
    """Bounded random reads of one archive; never download the whole archive.

    A fresh data/control connection per range avoids reusing an aborted FTP
    transfer. No commands change remote files. Credentials stay out of receipts.
    """
    def __init__(self, *, host: str, user: str, password: str, remote: str,
                 size: int, byte_budget: int = 20_000_000):
        self.host, self.user, self.password, self.remote = host, user, password, remote
        self.size, self.position, self.byte_budget = size, 0, byte_budget
        self.ranges: list[dict] = []
        self.received = 0
        self.cache: dict[tuple[int, int], bytes] = {}

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        position = offset if whence == 0 else self.position+offset if whence == 1 else self.size+offset if whence == 2 else -1
        if position < 0 or position > self.size:
            raise ValueError('Out-of-range archive seek')
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        count = self.size-self.position if size < 0 else min(size, self.size-self.position)
        if (self.position, count) in self.cache:
            data = self.cache[(self.position, count)]
            self.position += count
            return data
        for (start, length), payload in self.cache.items():
            if start <= self.position and self.position+count <= start+length:
                data = payload[self.position-start:self.position-start+count]
                self.position += count
                return data
        if count+self.received > self.byte_budget:
            raise ValueError('Explicit remote archive byte budget exceeded')
        if not count:
            return b''
        started, start, data = time.monotonic(), self.position, bytearray()
        ftp = ftplib.FTP_TLS(self.host, timeout=40, context=ssl.create_default_context())
        try:
            ftp.login(self.user, self.password)
            ftp.prot_p()
            ftp.voidcmd('TYPE I')
            with ftp.transfercmd('RETR '+self.remote, rest=start) as channel:
                while len(data) < count:
                    block = channel.recv(min(65536, count-len(data)))
                    if not block:
                        raise ValueError('Short remote archive range')
                    data.extend(block)
        finally:
            ftp.close()
        self.position += count
        self.received += count
        self.ranges.append({'start': start, 'bytes': count, 'sha256': hashlib.sha256(data).hexdigest(),
                            'elapsed_seconds': time.monotonic()-started})
        payload = bytes(data)
        self.cache[(start, count)] = payload
        return payload


def zip_inventory(reader: io.RawIOBase) -> list[dict]:
    """Read only the original ZIP index, including ZIP64 for >4 GB deposits."""
    with zipfile.ZipFile(reader) as archive:
        return [{'name': r.filename, 'uncompressed_bytes': r.file_size,
                 'compressed_bytes': r.compress_size, 'CRC32': f'{r.CRC:08x}',
                 'header_offset': r.header_offset, 'encrypted': bool(r.flag_bits & 1)}
                for r in archive.infolist()]


def extract_processed_member(reader: io.RawIOBase, member: str, destination: Path,
                             maximum_bytes: int = 50_000_000) -> dict:
    name = Path(member)
    if name.suffix.lower() not in ('.txt', '.xml', '.tsv', '.csv', '.json', '.xlsx') or '..' in name.parts:
        raise ValueError('Only explicitly selected processed tables or metadata may be acquired')
    with zipfile.ZipFile(reader) as archive:
        info = archive.getinfo(member)
        if info.file_size > maximum_bytes or info.flag_bits & 1:
            raise ValueError('Selected processed file is too large or encrypted')
        reader.seek(info.header_offset)
        reader.read(512)  # Cache local header/name/extra fields in one bounded read.
        with archive.open(info) as stream:
            payload = stream.read(maximum_bytes+1)
        if len(payload) != info.file_size:
            raise ValueError('Selected processed member size mismatch')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(payload)
    return {'original_member': member, 'bytes': len(payload), 'sha256': sha256(destination),
            'ZIP_CRC32_verified_by_zipfile': f'{info.CRC:08x}'}


def tsv_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def json_lines(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False)+'\n')


def positive_intensity(value: str) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def direct_identification(row: dict, allowed_types: list[str]) -> bool:
    count = int(row['MS/MS count'])
    identifiers = row['MS/MS IDs'].strip()
    if row['Type'] in ('MATCH', 'MULTI-MATCH', 'ISO-MATCH'):
        if count or identifiers:
            raise ValueError('Transfer-only label conflicts with original MS/MS evidence')
        return False
    if row['Type'] not in allowed_types:
        raise ValueError('Unrecognized source evidence type')
    if count <= 0 or not identifiers:
        raise ValueError('Direct identification lacks original per-run MS/MS evidence')
    return True


def freeze_design(paths: StoragePaths) -> dict:
    config = json.loads((paths.repository_root/CONFIG).read_text())
    directory = paths.project_runs_dir/RUN
    if directory.exists():
        raise ValueError('Existing Task 2.30A run must be preserved')
    root = paths.project_data_dir/SOURCE
    mapping = root/'MSV000099922/Mappingfile.xlsx'
    sheet = next(iter(xlsx_sheets(mapping).values()))
    cells = list(xlsx_rows(mapping, sheet))
    original_mapping = {r['A']: (n, r) for n, r in cells[1:] if r.get('A')}
    raw_inventory = {name.removesuffix('.raw') for name, _ in json.loads((root/'MSV000099922/listing_raw.json').read_text())['entries']}
    run_manifest = []
    for planned in config['ordered_runs']:
        raw = planned['raw_file']
        number, source = original_mapping[raw]
        if raw not in raw_inventory or source['B'] != f"ΔBC{planned['clone'][-1]}_w6/32_{planned['technical']}":
            raise ValueError('Original source run/clone/condition mapping differs')
        summary = tsv_rows(root/f"MSV000099922/processed/{planned['technical']}/summary.txt")
        matching = [r for r in summary if r['Raw.file'] == raw]
        if len(matching) != 1 or matching[0]['Experiment'] != f"DBC{planned['clone'][-1]} w6/32 {planned['technical']}":
            raise ValueError('Author mapping and processed run summary disagree')
        params = tsv_rows(root/f"MSV000099922/processed/{planned['technical']}/parameters.txt")
        selected = {r['Parameter']: r['Value'] for r in params}
        if selected['Match between runs'] != 'False' or matching[0]['Fixed.modifications'] != 'NA':
            raise ValueError('Unexpected identification transfer or fixed-modification settings')
        run_manifest.append({**planned, 'hla': config['hla'], 'condition': config['condition'],
                             'original_mapping_row': number, 'original_mapping_cells': source,
                             'original_processed_summary': matching[0],
                             'source_parameters': {k: selected[k] for k in ('Version', 'PSM FDR', 'Protein FDR', 'Site FDR', 'Match between runs')}})
    json_lines(directory/'manifests/run_identities.jsonl', run_manifest)
    write_json(directory/'manifests/design_freeze.json', {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'config': config,
        'config_sha256': sha256(paths.repository_root/CONFIG),
        'run_manifest_sha256': sha256(directory/'manifests/run_identities.jsonl'),
        'source_hashes': {str(f.relative_to(root)): sha256(f) for f in sorted(root.rglob('*')) if f.is_file()},
        'gate': 'GO: original run-specific MS/MS evidence, raw-to-clone crosswalk, chemical states, confidence and MS1 feature intensity available.',
        'documented_limitations': ['Only two independent edited clones; technical replicates nested.',
             'Paper protein FDR 0.01 differs from processed parameter Protein FDR = 1; preserve discrepancy.',
             'Actual variable modifications include protein N-terminal acetylation as well as methionine oxidation.',
             'Joint source searches include additional unmapped runs; never infer their genotype or add them.'],
        'Teacher_predictions_computed': False, 'stability_associations_computed': False})
    return {'status': 'GO_for_curation', 'runs': run_manifest}


def build_matrices(observations: list[dict], runs: list[dict]) -> tuple[list[dict], list[dict]]:
    """One detection per original run, retaining every contributing evidence ID."""
    unmodified, molecular = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for row in observations:
        if row['accepted_source_direct']:
            molecular[(row['sequence'], row['modified_sequence'])][row['raw_file']].append(row)
            if row['unmodified_canonical_9mer']:
                unmodified[row['sequence']][row['raw_file']].append(row)
    raw_order = [r['raw_file'] for r in runs]
    molecular_rows = [{'sequence': peptide, 'modified_sequence': species, 'length': len(peptide),
                       'raw_files': raw_order, 'direct_detection': [int(bool(found.get(raw))) for raw in raw_order],
                       'source_observation_ids_by_run': [[r['source_observation_id'] for r in found.get(raw, [])] for raw in raw_order]}
                      for (peptide, species), found in sorted(molecular.items())]
    rows = []
    for peptide, found in sorted(unmodified.items()):
        states = [int(bool(found.get(raw))) for raw in raw_order]
        intensities = []
        for raw in raw_order:
            positive = [r['positive_MS1_feature_intensity'] for r in found.get(raw, []) if r['positive_MS1_feature_intensity'] is not None]
            intensities.append(math.fsum(positive) if positive else None)
        index_available = [value for value in intensities[:2] if value is not None]
        source_identity = hashlib.sha256(json.dumps({'accession': 'MSV000099922', 'hla': 'HLA-A*02:01', 'peptide': peptide,
                                                    'ordered_runs': raw_order}, sort_keys=True).encode()).hexdigest()
        rows.append({'source_identity': source_identity, 'peptide': peptide, 'hla': 'HLA-A*02:01',
                     'raw_files': raw_order, 'direct_detection': states,
                     'source_observation_ids_by_run': [[r['source_observation_id'] for r in found.get(raw, [])] for raw in raw_order],
                     'n_available_technical_measurements': 4, 'n_technical_detections': sum(states),
                     'biological_clone_detection': [int(any(states[:2])), int(any(states[2:]))],
                     'n_available_biological_clones': 2,
                     'n_biological_clone_detections': int(any(states[:2]))+int(any(states[2:])),
                     'primary_index_eligible': bool(any(states[:2])),
                     'biological_followup_direct_detection': int(any(states[2:])),
                     'followup_nested_technical_count': sum(states[2:]),
                     'per_run_summed_direct_MS1_feature_intensity': intensities,
                     'index_precursor_intensity': math.fsum(index_available)/len(index_available) if index_available else None,
                     'index_intensity_available_technical_measurements': len(index_available),
                     'index_intensity_semantics': 'Mean available positive per-run summed MS1 feature areas in index clone only; arbitrary instrument units.'})
    return rows, molecular_rows


def curate(paths: StoragePaths) -> dict:
    started = time.monotonic()
    root, directory = paths.project_data_dir/SOURCE, paths.project_runs_dir/RUN
    freeze = json.loads((directory/'manifests/design_freeze.json').read_text())
    config = freeze['config']
    if sha256(paths.repository_root/CONFIG) != freeze['config_sha256']:
        raise ValueError('Frozen design configuration changed')
    for name, expected in freeze['source_hashes'].items():
        if sha256(root/name) != expected:
            raise ValueError('Frozen original source changed: '+name)
    if (directory/'observations/evidence.jsonl').exists():
        raise ValueError('Existing curation must not be rerun')
    runs = [json.loads(line) for line in (directory/'manifests/run_identities.jsonl').read_text().splitlines()]
    mapping = {r['raw_file']: r for r in runs}
    workbook = root/'publication/mmc1.xlsx'
    published = list(xlsx_rows(workbook, xlsx_sheets(workbook)['Peptides']))
    accepted_by_raw, workbook_ids = {r['raw_file']: set() for r in runs}, defaultdict(list)
    for number, cells in published[1:]:
        for run in runs:
            value = cells.get(run['published_count_column'])
            if value and float(value) > 0:
                accepted_by_raw[run['raw_file']].add(cells['A'])
                workbook_ids[(cells['A'], run['raw_file'])].append(number)
    observations, excluded, all_types, source_n, seen = [], Counter(), Counter(), {}, set()
    source_direct_sequences = {raw: set() for raw in mapping}
    for exp in ('Exp1', 'Exp2'):
        source = root/f'MSV000099922/processed/{exp}/evidence.txt'
        source_digest = sha256(source)
        source_rows = tsv_rows(source)
        source_n[exp] = len(source_rows)
        for number, row in enumerate(source_rows, 2):
            raw = row['Raw file']
            if raw not in mapping:
                excluded['outside_frozen_edited_W632_runs'] += 1
                continue
            if mapping[raw]['technical'] != exp:
                raise ValueError('Evidence run belongs to a different original search/technical group')
            identifier = f'MSV000099922:{exp}:evidence:{row["id"]}'
            if identifier in seen:
                raise ValueError('Duplicate evidence-feature ID; do not double-count intensity')
            seen.add(identifier)
            direct = direct_identification(row, config['direct_types'])
            all_types[row['Type']] += 1
            if row['Reverse'] not in ('', '+') or row['Potential contaminant'] not in ('', '+'):
                raise ValueError('Unrecognized source reverse/contaminant flag')
            valid_source = direct and row['Reverse'] != '+' and row['Potential contaminant'] != '+'
            peptide = row['Sequence']
            if int(row['Length']) != len(peptide):
                raise ValueError('Original peptide length/sequence mismatch')
            if valid_source and 8 <= len(peptide) <= 15:
                source_direct_sequences[raw].add(peptide)
            accepted = valid_source and peptide in accepted_by_raw[raw]
            canonical9 = len(peptide) == 9 and set(peptide) <= AA
            unmodified = row['Modifications'] == 'Unmodified' and row['Modified sequence'] == '_'+peptide+'_'
            observations.append({'source_observation_id': identifier, 'source_search': exp,
                'original_evidence_row_1based': number, 'original_evidence_id': row['id'],
                'source_evidence_sha256': source_digest,
                'raw_file': raw, 'original_experiment_label': row['Experiment'],
                'clone': mapping[raw]['clone'], 'condition': config['condition'], 'hla': config['hla'],
                'sequence': peptide, 'modified_sequence': row['Modified sequence'], 'modifications': row['Modifications'],
                'direct_MS_MS': direct, 'accepted_source_direct': accepted,
                'unmodified_canonical_9mer': accepted and canonical9 and unmodified,
                'published_workbook_rows': workbook_ids[(peptide, raw)],
                'positive_MS1_feature_intensity': positive_intensity(row['Intensity']),
                'original_fields': row})
            if not accepted:
                excluded['reverse_or_contaminant_or_outside_published_source_set'] += 1
            elif not canonical9:
                excluded['accepted_noncanonical_or_not_9mer'] += 1
            elif not unmodified:
                excluded['accepted_modified_9mer_feature'] += 1
            else:
                excluded['retained_unmodified_9mer_feature'] += 1
    reconciliation = {raw: {'published_peptides': len(accepted_by_raw[raw]),
                            'original_direct_filtered_peptides': len(source_direct_sequences[raw]),
                            'published_missing_from_direct_evidence': len(accepted_by_raw[raw]-source_direct_sequences[raw]),
                            'direct_not_in_published': len(source_direct_sequences[raw]-accepted_by_raw[raw])} for raw in mapping}
    if any(r['published_missing_from_direct_evidence'] or r['direct_not_in_published'] for r in reconciliation.values()):
        raise ValueError('Run-resolved original evidence and published accepted peptide sets do not reconcile')
    rows, molecular = build_matrices(observations, runs)
    primary = [r for r in rows if r['primary_index_eligible']]
    json_lines(directory/'observations/evidence.jsonl', observations)
    json_lines(directory/'matrices/full_direct_molecular_species.jsonl', molecular)
    json_lines(directory/'matrices/unmodified_9mer_four_run_matrix.jsonl', rows)
    json_lines(directory/'manifests/future_primary_index_cohort.jsonl', primary)
    write_json(directory/'reports/published_run_reconciliation.json', reconciliation)
    summary = {'source_evidence_rows': source_n, 'selected_evidence_rows': len(observations),
        'source_selected_evidence_types': dict(all_types), 'evidence_status_counts': dict(excluded),
        'published_workbook_peptide_rows': len(published)-1,
        'full_condition_direct_base_peptide_union': len({r['sequence'] for r in molecular}),
        'full_condition_direct_molecular_species_union': len(molecular),
        'unmodified_canonical_9mer_union': len(rows), 'primary_index_n': len(primary),
        'source_alleles': [config['hla']], 'biological_clones': 2, 'technical_measurements_per_clone': 2,
        'technical_detection_distribution_in_union': dict(Counter(r['n_technical_detections'] for r in rows)),
        'biological_detection_distribution_in_union': dict(Counter(r['n_biological_clone_detections'] for r in rows)),
        'primary_biological_followup_distribution': dict(Counter(r['biological_followup_direct_detection'] for r in primary)),
        'primary_followup_nested_technical_count_distribution': dict(Counter(r['followup_nested_technical_count'] for r in primary)),
        'unmodified_9mers_by_original_run': {raw: sum(r['direct_detection'][i] for r in rows) for i, raw in enumerate(mapping)},
        'index_intensity_missing': sum(r['index_precursor_intensity'] is None for r in primary),
        'index_intensity_available_technical_count_distribution': dict(Counter(r['index_intensity_available_technical_measurements'] for r in primary)),
        'run_available': {raw: any(r['raw_file'] == raw for r in observations) for raw in mapping},
        'minimum_coefficient_n': 2, 'primary_sparse_n_lt30': len(primary) < 30,
        'primary_minor_class_lt10': min(Counter(r['biological_followup_direct_detection'] for r in primary).values(), default=0) < 10,
        'original_processed_MBR': False, 'study_predictions_or_associations': False,
        'runtime_seconds': time.monotonic()-started}
    write_json(directory/'reports/curation_summary.json', summary)
    return summary


def teacher_overlap(paths: StoragePaths) -> dict:
    """Authenticate only model/support and sequence references. Never call inference."""
    from . import stability_teacher as teacher
    from .replicate_stability_association import nearest_hamming  # Pure sequence search only.
    directory = paths.project_runs_dir/RUN
    bundle = paths.project_data_dir/'teacher-v0-recovered'
    model_hash = 'a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99'
    model_path = bundle/'checkpoints/teacher_model.json'
    if sha256(model_path) != model_hash:
        raise ValueError('Original Teacher checkpoint identity differs')
    hashes = dict(line.split('  ', 1)[::-1] for line in (bundle/'SHA256SUMS').read_text().splitlines())
    inputs = ['identities/train.csv', 'identities/validation.csv', 'src/stability_label_curation/stability_teacher.py',
              'provenance/teacher/teacher_train_val_partition.json']
    for name in inputs:
        if sha256(bundle/name) != hashes[name]:
            raise ValueError('Authenticated Teacher reference changed')
    if sha256(paths.repository_root/'src/stability_label_curation/stability_teacher.py') != hashes['src/stability_label_curation/stability_teacher.py']:
        raise ValueError('Model-loading implementation differs from recovered original')
    model = teacher.load_model(model_path)
    if model.document['alleles']['HLA-A*02:01']['status'] != 'trained':
        raise ValueError('No exact trained A0201 model')
    references = {}
    for split, expected, hla_expected in [('train', 21625, 830), ('validation', 5406, 193)]:
        with (bundle/f'identities/{split}.csv').open() as stream:
            pairs = [(r['peptide'], r['hla']) for r in csv.DictReader(stream)]
        if len(pairs) != expected or sum(h == 'HLA-A*02:01' for p, h in pairs) != hla_expected:
            raise ValueError('Teacher reference partition population differs')
        references[split] = {'pairs': set(pairs), 'any_HLA': sorted({p for p, h in pairs}),
                             'A0201': sorted({p for p, h in pairs if h == 'HLA-A*02:01'})}
    matrix = [json.loads(line) for line in (directory/'matrices/unmodified_9mer_four_run_matrix.jsonl').read_text().splitlines()]
    overlap = []
    for row in matrix:
        peptide = row['peptide']
        teacher.encode_ninemer(peptide)  # Preprocessing acceptance, no model score.
        record = {'source_identity': row['source_identity'], 'peptide': peptide, 'hla': row['hla'],
                  'primary_index_eligible': row['primary_index_eligible']}
        for split in ('train', 'validation'):
            record[split+'_exact_peptide_HLA'] = (peptide, row['hla']) in references[split]['pairs']
            record[split+'_exact_peptide_any_HLA'] = peptide in references[split]['any_HLA']
            for scope in ('A0201', 'any_HLA'):
                distance, witness = nearest_hamming(peptide, references[split][scope])
                record[f'{split}_{scope}_minimum_Hamming'] = distance
                record[f'{split}_{scope}_nearest_sequence'] = witness
        record['future_fitting_exclusion_sensitivity_eligible'] = record['train_any_HLA_minimum_Hamming'] >= 2
        overlap.append(record)
    def summarize(records: list[dict]) -> dict:
        exact = {name: sum(r[name] for r in records) for name in (
            'train_exact_peptide_HLA', 'validation_exact_peptide_HLA',
            'train_exact_peptide_any_HLA', 'validation_exact_peptide_any_HLA')}
        distances = {f'{split}_{scope}': dict(Counter(str(r[f'{split}_{scope}_minimum_Hamming']) if r[f'{split}_{scope}_minimum_Hamming'] < 3 else '>=3' for r in records))
                     for split in ('train', 'validation') for scope in ('A0201', 'any_HLA')}
        return {'n': len(records), 'exact_overlaps': exact, 'minimum_Hamming_counts': distances,
                'future_fitting_excluded_sensitivity_n': sum(r['future_fitting_exclusion_sensitivity_eligible'] for r in records)}
    index = [r for r in overlap if r['primary_index_eligible']]
    json_lines(directory/'manifests/Teacher_sequence_overlap.jsonl', overlap)
    write_json(directory/'manifests/future_sensitivity_source_identities.json', [r['source_identity'] for r in index if r['future_fitting_exclusion_sensitivity_eligible']])
    summary = {'model_sha256': model_hash, 'HLA_A0201_status': 'trained',
               'A0201_training_rows': 830, 'A0201_validation_rows': 193,
               'reference_hashes': {name: hashes[name] for name in inputs},
               'unmodified_9mer_union': summarize(overlap), 'future_primary_index': summarize(index),
               'all_candidate_inputs_accepted': True, 'identity_normalization_problems': 0,
               'Teacher_inference_calls': 0, 'Teacher_predictions_computed': False,
               'stability_associations_computed': False,
               'meaning': 'Kinetic-label exposure is separate from MS-outcome exposure; validation flags never silently become training exposure.'}
    write_json(directory/'reports/Teacher_overlap_summary.json', summary)
    return summary


def unrestricted_processed_union(paths: StoragePaths) -> dict:
    """Preserve original direct IDs outside the paper's 8–15-mer study range too.

    This is a completeness view, not another primary eligibility condition or
    a claim that longer/background sequences are established A0201 ligands.
    """
    directory = paths.project_runs_dir/RUN
    config = json.loads((paths.repository_root/CONFIG).read_text())
    runs = [r['raw_file'] for r in config['ordered_runs']]
    found = defaultdict(lambda: defaultdict(list))
    with (directory/'observations/evidence.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            source = row['original_fields']
            if row['direct_MS_MS'] and source['Reverse'] != '+' and source['Potential contaminant'] != '+':
                found[(row['sequence'], row['modified_sequence'])][row['raw_file']].append(row['source_observation_id'])
    records = [{'sequence': peptide, 'modified_sequence': species, 'length': len(peptide),
                'raw_files': runs, 'direct_detection': [int(bool(by_run.get(raw))) for raw in runs],
                'source_observation_ids_by_run': [by_run.get(raw, []) for raw in runs]}
               for (peptide, species), by_run in sorted(found.items())]
    json_lines(directory/'matrices/unrestricted_processed_direct_molecular_species.jsonl', records)
    summary = {'base_sequence_union_all_processed_lengths': len({p for p, species in found}),
               'molecular_species_union_all_processed_lengths': len(records),
               'base_sequence_length_distribution': dict(Counter(len(p) for p in {p for p, species in found})),
               'scope': 'Original direct nonreverse/noncontaminant IDs at all processed lengths; source 8–15-mer study and fixed primary manifests remain unchanged.',
               'Teacher_predictions_or_associations': False}
    write_json(directory/'reports/unrestricted_processed_union_summary.json', summary)
    return summary


def validate(paths: StoragePaths) -> dict:
    directory = paths.project_runs_dir/RUN
    read = lambda name: [json.loads(line) for line in (directory/name).read_text().splitlines()]
    evidence = read('observations/evidence.jsonl')
    original = {r['source_observation_id']: r for r in evidence}
    if len(original) != len(evidence):
        raise ValueError('Original evidence IDs were collapsed or duplicated')
    peptide_tables = {}
    for exp in ('Exp1', 'Exp2'):
        peptide_tables[exp] = {r['id']: r['Sequence'] for r in tsv_rows(
            paths.project_data_dir/SOURCE/f'MSV000099922/processed/{exp}/peptides.txt')}
    for row in evidence:
        if peptide_tables[row['source_search']][row['original_fields']['Peptide ID']] != row['sequence']:
            raise ValueError('Original evidence/peptide-table cross-reference differs')
    matrix = read('matrices/unmodified_9mer_four_run_matrix.jsonl')
    primary = read('manifests/future_primary_index_cohort.jsonl')
    if primary != [r for r in matrix if r['primary_index_eligible']]:
        raise ValueError('Index identities no longer match the metadata-defined index clone')
    cells = 0
    for row in matrix:
        for raw, state, identifiers in zip(row['raw_files'], row['direct_detection'], row['source_observation_ids_by_run']):
            if state != int(bool(identifiers)):
                raise ValueError('Detection state has no original evidence')
            for identifier in identifiers:
                source = original[identifier]
                if not source['unmodified_canonical_9mer'] or source['raw_file'] != raw or source['sequence'] != row['peptide']:
                    raise ValueError('Peptide/chemical state/run/source mismatch')
            cells += state
        if row['biological_followup_direct_detection'] != int(any(row['direct_detection'][2:])):
            raise ValueError('Technical measurements incorrectly became biological observations')
    result = {'status': 'PASS', 'original_evidence_rows_preserved': len(evidence),
              'unmodified_9mer_union_rows': len(matrix), 'primary_index_rows': len(primary),
              'direct_detection_cells_validated': cells,
              'original_peptide_table_links_validated': len(evidence),
              'Teacher_predictions_or_stability_associations': False}
    write_json(directory/'reports/curation_validation.json', result)
    return result


def main() -> None:
    import argparse
    from .paths import resolve_paths
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze-design', 'curate', 'teacher-overlap', 'processed-union', 'validate'))
    actions = {'freeze-design': freeze_design, 'curate': curate, 'teacher-overlap': teacher_overlap,
               'processed-union': unrestricted_processed_union, 'validate': validate}
    result = actions[parser.parse_args().stage](resolve_paths())
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
