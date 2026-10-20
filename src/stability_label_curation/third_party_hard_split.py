"""Task 2.26 IMPROVE curation/reference freeze; no model loading or inference.

All thresholds/row policies are fixed in Git. Source labels only support the
authorized experimental compatibility checks and descriptive cohort counts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from typing import Any
import zipfile

from . import bigmhc_baseline_runner as runner
from . import bigmhc_independent_preflight as models
from .sequence_hamming import NearestNineIndex, valid_ninemer
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/third_party_hard_split_task2_26.json'
PROTOCOL = 'docs/BIGMHC_THIRD_PARTY_EVALUATION_TASK2_27_PROTOCOL.md'
RUN_ID = 'task-2_26-third-party-hard-split'
REFERENCE_NAMES = ('EL_fit', 'IM_fit', 'EL_selection', 'IM_epoch_selection',
                   'IM_historical_development', 'prior_Mendeley_published', 'prior_Mendeley_evaluated')


def sha(path: Path) -> str:
    return runner.raw.sha256_file(path)


def write_json(path: Path, value: Any) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def write_rows(path: Path, rows: list[dict]) -> None:
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def normalized(sequence: str) -> str:
    return sequence.strip().upper()


def git(paths: StoragePaths, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()


def science_hashes(paths: StoragePaths) -> dict[str, str]:
    return {name: sha(paths.repository_root / name) for name in (
        CONFIG, PROTOCOL, 'src/stability_label_curation/third_party_hard_split.py',
        'src/stability_label_curation/sequence_hamming.py', 'tests/test_third_party_hard_split.py')}


def parse_source(data: bytes, config: dict) -> list[dict]:
    """Use assayed Mut_peptide and original response, never predicted cores/ranks."""
    lines = data.splitlines(keepends=True)
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), delimiter='\t')
    required = {'identity', 'Patient', 'Sample', 'cohort', 'Mut_peptide', 'HLA_allele', 'response', 'validation'}
    if not required <= set(reader.fieldnames or ()):
        raise ValueError('Missing original experimental fields')
    rows = []
    for index, raw in enumerate(reader, 1):
        if reader.line_num != index+1 or None in raw:
            raise ValueError('Ambiguous source row boundaries or malformed TSV')
        response = raw['response'].strip().lower()
        label = config['response_mapping'].get(response)
        peptide = normalized(raw['Mut_peptide'])
        hla = runner.data.canonical_hla(raw['HLA_allele'].strip())
        study = config['study_DOIs'].get(raw['cohort'])
        mutation_fields = [raw.get(k, '') for k in ('Gene_ID', 'Genomic_Position', 'Amino_Acid_Change')]
        family = hashlib.sha256(json.dumps(mutation_fields).encode()).hexdigest() if all(
            x not in ('', 'NA') for x in mutation_fields) else None
        rows.append({'source_id': f"IMPROVE:{config['source_commit']}:{config['member']}:row:{index:012d}",
                     'source_row_index': index, 'source_line_number': index+1,
                     'source_row_sha256': hashlib.sha256(lines[index]).hexdigest(),
                     'original_observation_id': raw['identity'], 'patient': raw['Patient'], 'sample': raw['Sample'],
                     'study': raw['cohort'], 'study_DOI': study, 'publication_DOI': config['source_DOI'],
                     'raw_peptide': raw['Mut_peptide'], 'peptide': peptide,
                     'raw_hla': raw['HLA_allele'], 'hla': hla,
                     'raw_response': raw['response'], 'label': label,
                     'validation': raw['validation'], 'assay': config['assay'],
                     'tested_sequence_field': 'Mut_peptide', 'HLA_association': 'authors released experimentally folded pMHC multimer',
                     'wild_type_peptide': raw.get('Norm_peptide'), 'gene_id': raw.get('Gene_ID'),
                     'gene_symbol': raw.get('Gene_Symbol'), 'genomic_position': raw.get('Genomic_Position'),
                     'amino_acid_change': raw.get('Amino_Acid_Change'), 'mutation_consequence': raw.get('Mutation_Consequence'),
                     'possible_mutation_family': family})
    if len(lines) != len(rows)+1:
        raise ValueError('Unexpected extra physical source rows')
    return rows


def conflict_ids(rows: list[dict]) -> set[str]:
    definitions: dict[str, set] = defaultdict(set)
    for row in rows:
        definitions[row['original_observation_id']].add((row['peptide'], row['hla'], row['patient'], row['study'], row['label']))
    return {key for key, values in definitions.items() if len(values) > 1}


def compatible(row: dict, supported: set[str], conflicts: set[str]) -> list[str]:
    reasons = []
    if not valid_ninemer(row['peptide']):
        reasons.append('invalid_or_non_ninemer_assayed_peptide')
    if row['hla'] not in supported:
        reasons.append('unsupported_or_ambiguous_exact_HLA')
    if row['label'] not in (0, 1):
        reasons.append('ambiguous_experimental_outcome')
    if row['validation'] != 'Sufficient':
        reasons.append('not_in_authors_sufficiently_validated_screen')
    if not row['original_observation_id'] or not row['study_DOI']:
        reasons.append('missing_original_observation_or_study_identity')
    if row['original_observation_id'] in conflicts:
        reasons.append('conflicting_original_observation_identity')
    return reasons


def describe(rows: list[dict]) -> dict:
    positive = sum(r['label'] == 1 for r in rows)
    negative = sum(r['label'] == 0 for r in rows)
    studies = {}
    for study in sorted({r['study'] for r in rows}):
        group = [r for r in rows if r['study'] == study]
        p = sum(r['label'] == 1 for r in group)
        studies[study] = {'N': len(group), 'positive': p, 'negative': sum(r['label'] == 0 for r in group),
                          'patients': len({r['patient'] for r in group if r['patient']}),
                          'study_DOI': group[0]['study_DOI']}
    patients = {}
    for key in sorted({(r['study'], r['patient']) for r in rows}):
        group = [r for r in rows if (r['study'], r['patient']) == key]
        patients['|'.join(key)] = {'N': len(group), 'positive': sum(r['label'] == 1 for r in group),
                                   'negative': sum(r['label'] == 0 for r in group)}
    return {'N': len(rows), 'positive': positive, 'negative': negative,
            'ambiguous_outcomes': len(rows)-positive-negative,
            'prevalence': positive/len(rows) if rows and positive+negative == len(rows) else None,
            'unique_peptides': len({r['peptide'] for r in rows}),
            'unique_pairs': len({(r['peptide'], r['hla']) for r in rows}),
            'unique_HLAs': len({r['hla'] for r in rows if r['hla']}),
            'HLA_counts': dict(sorted(Counter(r['hla'] or r['raw_hla'] for r in rows).items())),
            'patients': len(patients), 'studies': studies, 'patient_counts': patients,
            'source_sample_identifiers': len({(r['study'], r['sample']) for r in rows})}


def duplicate_diagnostics(rows: list[dict]) -> dict:
    def groups(keys: tuple[str, ...]) -> list[list[dict]]:
        result: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
            result[tuple(row[k] for k in keys)].append(row)
        return list(result.values())
    result = {}
    for name, keys in [('original_ID', ('original_observation_id',)), ('peptide', ('peptide',)),
                       ('pair', ('peptide', 'hla')), ('patient_pair', ('study', 'patient', 'peptide', 'hla'))]:
        grouping = groups(keys)
        result[name] = {'repeated_groups': sum(len(g) > 1 for g in grouping),
                        'excess_rows': sum(len(g)-1 for g in grouping),
                        'mixed_outcome_groups': sum(len({r['label'] for r in g}) > 1 for g in grouping)}
    families: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row['possible_mutation_family']:
            families[row['possible_mutation_family']].append(row)
    result['possible_mutation_families'] = {
        'families': len(families), 'with_multiple_sequences': sum(len({r['peptide'] for r in g}) > 1 for g in families.values()),
        'with_multiple_patients': sum(len({(r['study'], r['patient']) for r in g}) > 1 for g in families.values()),
        'definition': 'same raw gene ID/genomic position/amino-acid change; no chromosome/build harmonization, descriptive only'}
    result['conflicting_original_IDs'] = sorted(conflict_ids(rows))
    result['handling'] = 'all released rows retained except whole conflicting-original-ID groups; different-patient responses are not contradictions'
    return result


def components(rows: list[dict], unit: str) -> list[str]:
    """Identity-only connected components: shared peptide OR patient/study."""
    parents = list(range(len(rows)))
    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    def join(left: int, right: int) -> None:
        a, b = root(left), root(right)
        parents[max(a, b)] = min(a, b)
    seen = {}
    for index, row in enumerate(rows):
        material = ('patient', row['study_DOI'], row['patient']) if unit == 'patient' else ('study', row['study_DOI'])
        keys = [('peptide', row['peptide']), material]
        for key in keys:
            if key in seen:
                join(index, seen[key])
            else:
                seen[key] = index
    return [f'{unit}_peptide_component_{root(i):012d}' for i in range(len(rows))]


def save_sequences(path: Path, sequences: set[str]) -> None:
    with path.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed:
        for sequence in sorted(sequences):
            compressed.write((sequence + '\n').encode('ascii'))


def build_references(paths: StoragePaths, directory: Path, candidates: list[dict]) -> tuple[dict, dict, dict, dict]:
    config = json.loads((paths.repository_root / 'configs/bigmhc_fully_trained_auxiliary_task2_24.json').read_text())
    previous = json.loads((paths.repository_root / 'configs/bigmhc_el_multiepoch_task2_23.json').read_text())
    historical = json.loads((paths.repository_root / 'configs/bigmhc_gpu_baseline_task2_10.json').read_text())
    inputs = {name: config['inputs'][name] for name in ('EL', 'EL_split', 'IM')}
    inputs['IM_epoch_split'] = previous['inputs']['IM_split']
    inputs['historical_development'] = historical['inputs']['development']
    resolved, identities = {}, {}
    for name, item in inputs.items():
        path = (paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir) / item['relative_path']
        if sha(path) != item['sha256']:
            raise ValueError('Actual reference input hash mismatch: ' + name)
        resolved[name] = path
        identities[name] = item
    sets = {name: set() for name in REFERENCE_NAMES}
    pair_hits = {name: set() for name in REFERENCE_NAMES}
    query_peptides = {r['peptide'] for r in candidates}
    query_cores = {c for r in candidates for c in (r['peptide'][:8], r['peptide'][1:])}
    core_hits = {name: set() for name in REFERENCE_NAMES}
    row_counts = Counter()
    def add(name: str, peptide: str, hla: str) -> None:
        peptide = normalized(peptide)
        row_counts[name] += 1
        if not valid_ninemer(peptide):
            return
        sets[name].add(peptide)
        if peptide in query_peptides:
            pair_hits[name].add((peptide, hla))
        for core in (peptide[:8], peptide[1:]):
            if core in query_cores:
                core_hits[name].add(core)
    partition_counts = Counter()
    with gzip.open(resolved['EL_split'], 'rt', newline='') as manifest, resolved['EL'].open(newline='') as view:
        for index, (row, original) in enumerate(zip(csv.DictReader(manifest), csv.DictReader(view), strict=True), 1):
            if (int(row['original_prepared_row_index']) != index or
                    (normalized(row['peptide']), row['HLA']) != (normalized(original['pep']), original['mhc'])):
                raise ValueError('EL source identity/partition join differs')
            partition_counts[row['partition']] += 1
            name = {'train': 'EL_fit', 'validation': 'EL_selection', 'excluded': None}[row['partition']]
            if name:
                add(name, row['peptide'], row['HLA'])
    if partition_counts != {'train': 1308196, 'validation': 145371, 'excluded': 11} or len(sets['EL_fit']) != 1122528:
        raise ValueError('EL scientific reference population changed')
    with resolved['IM'].open(newline='') as stream:
        for row in csv.DictReader(stream):
            add('IM_fit', row['pep'], row['mhc'])
    im_partitions = Counter()
    with resolved['IM_epoch_split'].open(newline='') as stream:
        for row in csv.DictReader(stream):
            im_partitions[row['partition']] += 1
            if row['partition'] == 'validation':
                add('IM_epoch_selection', row['peptide'], row['HLA'])
    with resolved['historical_development'].open(newline='') as stream:
        for row in csv.DictReader(stream):
            add('IM_historical_development', row['pep'], row['mhc'])
    if row_counts['IM_fit'] != 3428 or row_counts['IM_historical_development'] != 383 or im_partitions != {'train': 2742, 'validation': 686}:
        raise ValueError('IM fitting/selection/development reference census changed')
    prior = paths.project_runs_dir / 'task-2_25-independent-neoepitope-evaluation/resumed'
    frozen = json.loads((prior / 'reports/eligibility_frozen.json').read_text())
    # Read only original benchmark identities, never any Task 2.25 predictions or metrics.
    for name, file in [('prior_Mendeley_published', 'all_source_identities.jsonl'),
                       ('prior_Mendeley_evaluated', 'IM_novel.jsonl')]:
        relative = 'cohorts/' + file
        if sha(prior / relative) != frozen['manifest_hashes'][relative]:
            raise ValueError('Prior benchmark identity manifest changed')
        identities[name] = {'area': 'runs', 'relative_path': str((prior / relative).relative_to(paths.project_runs_dir)),
                            'sha256': frozen['manifest_hashes'][relative]}
        with (prior / relative).open() as stream:
            for line in stream:
                row = json.loads(line)
                add(name, row['peptide'], row['hla'])
    if row_counts['prior_Mendeley_published'] != 937 or row_counts['prior_Mendeley_evaluated'] != 275:
        raise ValueError('Prior benchmark source census changed')
    roles = {'EL_fit': 'actual_model_fitting', 'IM_fit': 'actual_model_fitting',
             'EL_selection': 'EL_epoch_selection', 'IM_epoch_selection': 'IM_epoch_selection_also_in_final_IM_fit',
             'IM_historical_development': 'historical_development_and_selection',
             'prior_Mendeley_published': 'previously_used_external_source_not_training',
             'prior_Mendeley_evaluated': 'actually_scored_external_subset_not_training'}
    report = {'inputs': identities, 'EL_partition_counts': dict(partition_counts), 'IM_old_split_counts': dict(im_partitions), 'sets': {}}
    for name, sequences in sets.items():
        file = directory / f'references/{name}.txt.gz'
        save_sequences(file, sequences)
        report['sets'][name] = {'role': roles[name], 'observations_in_source': row_counts[name],
                               'unique_canonical_ninemers': len(sequences),
                               'relative_path': str(file.relative_to(directory)), 'sha256': sha(file),
                               'ordered_sequence_content_sha256': hashlib.sha256(''.join(s+'\n' for s in sorted(sequences)).encode()).hexdigest()}
    report['selection_IM_is_subset_of_fitting_IM'] = sets['IM_epoch_selection'] <= sets['IM_fit']
    report['fitting_union_unique_sequences'] = len(sets['EL_fit'] | sets['IM_fit'])
    report['fitting_selection_union_unique_sequences'] = len(set().union(*(sets[name] for name in REFERENCE_NAMES[:5])))
    write_json(directory / 'reports/reference_freeze.json', report)
    return sets, pair_hits, core_hits, report


def select_threshold(rows: list[dict], threshold: int) -> list[dict]:
    return [row for row in rows if row['minimum_fitting_selection_distance'] >= threshold
            and not row['exact_prior_published_benchmark_peptide']]


def build(paths: StoragePaths) -> dict:
    start = time.monotonic()
    config = json.loads((paths.repository_root / CONFIG).read_text())
    if (config['primary_minimum_hamming'] != 3 or config['diagnostic_minimum_hamming'] != [2, 3, 4]
            or any(config[k] for k in ('training_authorized', 'model_inference_authorized', 'model_performance_authorized'))):
        raise ValueError('Only source curation with the fixed hard split is authorized')
    if git(paths, 'branch', '--show-current') != 'task/2.26-third-party-hard-split' or git(paths, 'status', '--porcelain'):
        raise ValueError('Curation requires the clean committed task branch')
    subprocess.run(['git', 'merge-base', '--is-ancestor', config['base_commit'], 'HEAD'], cwd=paths.repository_root, check=True)
    directory = paths.project_runs_dir / RUN_ID
    write_json(directory / 'reports/curation_started.json', {'commit': git(paths, 'rev-parse', 'HEAD'),
               'started_utc': datetime.now(timezone.utc).isoformat(), 'configuration': config,
               'scientific_hashes': science_hashes(paths), 'inference_authorized': False})
    for name in ('cohorts', 'references', 'similarity'):
        (directory / name).mkdir(exist_ok=False)
    archive = paths.project_data_dir / config['archive_relative_path']
    if archive.stat().st_size != config['archive_bytes'] or sha(archive) != config['archive_sha256']:
        raise ValueError('Authentic pinned IMPROVE archive required')
    with archive.open('rb') as stream:
        git_blob = hashlib.sha1(b'blob '+str(config['archive_bytes']).encode()+b'\0')
        while chunk := stream.read(1024*1024):
            git_blob.update(chunk)
    if git_blob.hexdigest() != config['archive_git_blob_sha1']:
        raise ValueError('Archive differs from pinned Git blob')
    with zipfile.ZipFile(archive) as zipped:
        entries = [i for i in zipped.infolist() if i.filename == config['member']]
        if len(entries) != 1 or entries[0].file_size > 8*1024*1024:
            raise ValueError('Missing/ambiguous or unbounded screened member')
        data = zipped.read(entries[0])
    if hashlib.sha256(data).hexdigest() != config['member_sha256']:
        raise ValueError('Original screened member changed')
    rows = parse_source(data, config)
    crosscheck = paths.project_data_dir / config['crosscheck_relative_path']
    raw_crosscheck = crosscheck.read_bytes()
    if hashlib.sha1(b'blob '+str(len(raw_crosscheck)).encode()+b'\0'+raw_crosscheck).hexdigest() != config['crosscheck_git_blob_sha1']:
        raise ValueError('Released independent in-house table changed')
    check = list(csv.DictReader(io.StringIO(raw_crosscheck.decode()), delimiter='\t'))
    if len(rows) != 17520 or len(check) != len(rows):
        raise ValueError('Original screened population truncated or changed')
    for row, other in zip(rows, check, strict=True):
        if (row['raw_peptide'], row['raw_hla'], row['label']) != (other['Mut_peptide'], other['HLA_allele'], int(other['response'])):
            raise ValueError('Patient-annotated source differs from released in-house screen table')
    model_config = json.loads((paths.repository_root / 'configs/bigmhc_independent_task2_25R.json').read_text())
    model_receipt, context = models.authenticate_models(paths, amendment_sha256=model_config['protocol_sha256'])
    write_json(directory / 'reports/frozen_models.json', model_receipt)
    with context['files']['reference'].open(newline='') as stream:
        reference, _, mapping = runner.data._reference(enumerate(csv.reader(stream), 1))
    if (reference['feature_count'] != 414 or reference['invalid_one_hot_rows'] or reference['duplicate_identifier_count']
            or reference['sanitized_UID_collision_groups']):
        raise ValueError('Invalid frozen exact HLA mapping')
    supported = {hla for hla, names in mapping.items() if len(names) == 1}
    conflicts = conflict_ids(rows)
    for row in rows:
        row['compatibility_exclusions'] = compatible(row, supported, conflicts)
    candidates = [r for r in rows if not r['compatibility_exclusions']]
    write_rows(directory / 'cohorts/source_observations.jsonl', rows)
    write_rows(directory / 'cohorts/candidate_9mers.jsonl', candidates)
    write_rows(directory / 'cohorts/compatibility_exclusions.jsonl', [r for r in rows if r['compatibility_exclusions']])
    source_report = {'source': describe(rows), 'candidates': describe(candidates),
                     'first_exclusions': dict(Counter(r['compatibility_exclusions'][0] for r in rows if r['compatibility_exclusions'])),
                     'all_exclusion_flags': dict(Counter(reason for r in rows for reason in r['compatibility_exclusions'])),
                     'unsupported_HLAs': dict(Counter(r['raw_hla'] for r in rows if r['hla'] not in supported)),
                     'source_duplicates': duplicate_diagnostics(rows), 'candidate_duplicates': duplicate_diagnostics(candidates),
                     'crosscheck_rows_identical_in_order': True, 'prediction_generated_labels_used': False,
                     'long_peptides_converted_to_cores': False, 'HLA_inferred_from_genotype': False,
                     'source_member': config['member'], 'source_member_sha256': config['member_sha256'],
                     'assay': config['assay'], 'per_sample_barcode_counts_available': False,
                     'source_negative_interpretation': 'authors sufficiently validated screened pMHC, no recognition in tested patient materials; not synthetic or untested negatives',
                     'patient_overlap_with_training_or_Mendeley': 'unresolved: reference sources do not expose comparable patient identifiers',
                     'publication_overlap_with_training_or_Mendeley': 'original IMPROVE studies identified; no complete upstream study crosswalk in BigMHC prepared views/Mendeley release; shared origin cannot be ruled out'}
    write_json(directory / 'reports/source_compatibility.json', source_report)
    print('Source curated:', len(rows), 'rows;', len(candidates), 'compatible exact 9-mers', flush=True)
    reference_sets, pair_hits, core_hits, reference_report = build_references(paths, directory, candidates)
    reference_HLAs = {name: defaultdict(set) for name in REFERENCE_NAMES}
    for name in REFERENCE_NAMES:
        for peptide, hla in pair_hits[name]:
            reference_HLAs[name][peptide].add(hla)
    print('Actual fitting/selection/prior-benchmark reference sets frozen', flush=True)
    queries = sorted({r['peptide'] for r in candidates})
    distances: dict[str, dict] = {q: {} for q in queries}
    search_evidence = {}
    for name in REFERENCE_NAMES:
        started = time.monotonic()
        index = NearestNineIndex(reference_sets[name])
        for number, query in enumerate(queries, 1):
            distance, nearest = index.nearest(query)
            distances[query][name] = {'distance': distance, 'nearest_reference': nearest}
            if number % 2000 == 0:
                print(name, number, '/', len(queries), 'queries', flush=True)
        search_evidence[name] = dict(index.evidence(), elapsed_seconds=time.monotonic()-started)
        print(name, 'done:', search_evidence[name], flush=True)
        del index
    write_rows(directory / 'similarity/unique_peptide_distances.jsonl', [dict(peptide=q, references=distances[q]) for q in queries])
    unions = config['reference_union']
    for row in candidates:
        row['reference_distances'] = distances[row['peptide']]
        row['minimum_fitting_distance'] = min(distances[row['peptide']][n]['distance'] for n in ('EL_fit', 'IM_fit'))
        row['minimum_selection_distance'] = min(distances[row['peptide']][n]['distance'] for n in ('EL_selection', 'IM_epoch_selection', 'IM_historical_development'))
        row['minimum_fitting_selection_distance'] = min(distances[row['peptide']][n]['distance'] for n in unions)
        row['exact_prior_published_benchmark_peptide'] = row['peptide'] in reference_sets['prior_Mendeley_published']
        row['exact_prior_evaluated_benchmark_peptide'] = row['peptide'] in reference_sets['prior_Mendeley_evaluated']
        row['exact_pair_overlap'] = {n: (row['peptide'], row['hla']) in pair_hits[n] for n in REFERENCE_NAMES}
        row['identical_peptide_other_HLAs'] = {n: sorted(reference_HLAs[n][row['peptide']] - {row['hla']}) for n in REFERENCE_NAMES}
        row['shared_contiguous_eightmer_core'] = {n: any(core in core_hits[n] for core in (row['peptide'][:8], row['peptide'][1:])) for n in REFERENCE_NAMES}
        row['primary_exclusions'] = (['fitting_or_selection_Hamming_below_3'] if row['minimum_fitting_selection_distance'] < 3 else []) + (
            ['exact_prior_published_benchmark_peptide'] if row['exact_prior_published_benchmark_peptide'] else [])
    write_rows(directory / 'similarity/candidate_distances_and_exclusions.jsonl', candidates)
    write_rows(directory / 'similarity/primary_exclusions.jsonl', [r for r in candidates if r['primary_exclusions']])
    thresholds = {}
    for threshold in config['diagnostic_minimum_hamming']:
        selected = select_threshold(candidates, threshold)
        patient_clusters, study_clusters = components(selected, 'patient'), components(selected, 'study')
        selected = [dict(r, patient_peptide_component=pc, study_peptide_component=sc)
                    for r, pc, sc in zip(selected, patient_clusters, study_clusters, strict=True)]
        prefix = directory / f'cohorts/hamming_ge_{threshold}'
        write_rows(prefix.with_suffix('.jsonl'), selected)
        write_rows(prefix.with_name(prefix.name+'_identities.jsonl'), [{k: v for k, v in row.items() if k not in ('label', 'raw_response')} for row in selected])
        write_rows(prefix.with_name(prefix.name+'_outcomes.jsonl'), [{'source_id': row['source_id'], 'label': row['label'], 'raw_response': row['raw_response']} for row in selected])
        thresholds[str(threshold)] = {
            'primary': threshold == 3, 'population': describe(selected),
            'patient_peptide_components': len(set(patient_clusters)), 'study_peptide_components': len(set(study_clusters)),
            'patient_component_sizes': dict(Counter(patient_clusters)), 'study_component_sizes': dict(Counter(study_clusters)),
            'duplicates': duplicate_diagnostics(selected),
            'minimum_distance_distribution': dict(sorted(Counter(r['minimum_fitting_selection_distance'] for r in selected).items())),
            'distance_to_prior_benchmark_distribution': dict(sorted(Counter(r['reference_distances']['prior_Mendeley_published']['distance'] for r in selected).items())),
            'shared_eightmer_core_observations_by_reference': {n: sum(r['shared_contiguous_eightmer_core'][n] for r in selected) for n in REFERENCE_NAMES}}
    overlap = {name: {'exact_peptide_observations': sum(r['reference_distances'][name]['distance'] == 0 for r in candidates),
                       'exact_unique_peptides': len({r['peptide'] for r in candidates if r['reference_distances'][name]['distance'] == 0}),
                       'exact_pair_observations': sum(r['exact_pair_overlap'][name] for r in candidates),
                       'same_peptide_different_HLA_observations': sum(bool(r['identical_peptide_other_HLAs'][name]) for r in candidates),
                       'peptide_overlap_without_exact_pair': sum(r['reference_distances'][name]['distance'] == 0 and not r['exact_pair_overlap'][name] for r in candidates),
                       'minimum_distance_distribution': dict(sorted(Counter(r['reference_distances'][name]['distance'] for r in candidates).items()))}
               for name in REFERENCE_NAMES}
    write_json(directory / 'reports/overlap_assessment.json', overlap)
    write_json(directory / 'reports/search_execution.json', search_evidence)
    write_json(directory / 'reports/threshold_populations.json', thresholds)
    primary = thresholds['3']['population']
    result = {'status': 'benchmark_frozen_ready_for_separately_authorized_Task2.27' if primary['positive'] and primary['negative'] else 'benchmark_frozen_class_diversity_limited',
              'source': source_report['source'], 'candidates': source_report['candidates'], 'thresholds': thresholds,
              'candidate_union_distance_distribution': dict(sorted(Counter(r['minimum_fitting_selection_distance'] for r in candidates).items())),
              'primary_candidate_exclusions': dict(Counter(reason for r in candidates for reason in r['primary_exclusions'])),
              'primary_sequential_exclusions': {
                  'Hamming_below_3': sum(r['minimum_fitting_selection_distance'] < 3 for r in candidates),
                  'prior_benchmark_exact_after_distance': sum(r['minimum_fitting_selection_distance'] >= 3 and r['exact_prior_published_benchmark_peptide'] for r in candidates)},
              'scientific_hashes': science_hashes(paths), 'frozen_utc': datetime.now(timezone.utc).isoformat(),
              'execution_commit': git(paths, 'rev-parse', 'HEAD'), 'elapsed_seconds': time.monotonic()-start,
              'peak_host_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              'runtime': {'Python': platform.python_version(), 'platform': platform.platform()},
              'torch_imported': 'torch' in sys.modules, 'models_loaded': False,
              'A_S_P_inference_executed': False, 'model_performance_computed': False, 'training_executed': False,
              'prior_prediction_or_metric_files_opened': False,
              'fitting_selection_union_unique_sequences': reference_report['fitting_selection_union_unique_sequences']}
    result['immutable_artifact_hashes'] = {str(file.relative_to(directory)): sha(file) for file in sorted(directory.rglob('*'))
                                          if file.is_file() and 'logs' not in file.relative_to(directory).parts}
    write_json(directory / 'reports/benchmark_freeze.json', result)
    return {'status': result['status'], 'source_N': len(rows), 'candidate_N': len(candidates),
            'thresholds': {n: {k: v for k, v in value['population'].items() if k in ('N', 'positive', 'negative', 'prevalence', 'unique_peptides', 'unique_HLAs', 'patients')}
                           for n, value in thresholds.items()}, 'elapsed_seconds': result['elapsed_seconds']}


if __name__ == '__main__':
    print(json.dumps(build(resolve_paths()), indent=2))
