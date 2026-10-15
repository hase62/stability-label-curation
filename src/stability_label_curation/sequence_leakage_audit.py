"""Offline exposure diagnostics, never split assignments or label corrections.

The indexed aligned-window predicate is exact under its declared Hamming rule.
It is not an implementation of CD-HIT or a certificate of biological independence.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from . import dtu2016_source_audit as dtu
from . import netmhcstabpan_2016 as raw
from . import observation_registry as registry
from . import run_manifest as runs
from . import scientific_gate0_preflight as readers
from .paths import StoragePaths, resolve_paths

PROTOCOL = 'configs/phase2_el_im_protocol.json'
LITERATURE = 'configs/hard_split_literature_evidence.json'
AMINO_ACIDS = frozenset('ACDEFGHIKLMNPQRSTVWY')
MAX_RECORDS = 100000
MAX_WINDOWS = 50000
MAX_EDGES = 2000000
MAX_INDEX_ENTRIES = 2000000


@dataclass(frozen=True)
class SequenceRecord:
    """Unmodified input identity and optional exposure metadata; group is supplied."""
    record_id: str
    peptide: str
    allele: str
    group: str
    source_id: str
    label: str | None = None
    canonical_measurement_id: str | None = None
    study_id: str | None = None
    donor_id: str | None = None
    mutant_of: str | None = None
    negative_provenance: str | None = None
    checkpoint_exposure: str | None = None

    def __post_init__(self) -> None:
        for field in ('record_id', 'peptide', 'allele', 'group', 'source_id'):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or len(value) > 4096:
                raise ValueError('Required bounded sequence metadata: ' + field)
        if not re.fullmatch('[A-Z]+', self.peptide):
            raise ValueError('Peptide must be original uppercase letters; no automatic normalization')
        for field in ('label', 'canonical_measurement_id', 'study_id', 'donor_id',
                      'mutant_of', 'negative_provenance', 'checkpoint_exposure'):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value or len(value) > 4096):
                raise ValueError('Invalid optional exposure metadata: ' + field)


@dataclass(frozen=True)
class AlleleMapping:
    original: str
    mapped: str
    evidence: str
    status: str = 'verified'


def allele_mapping_table(mappings: Sequence[AlleleMapping]) -> dict[str, str]:
    """Explicit evidence is required; mutants and ambiguous mappings fail closed."""
    table = {}
    for item in mappings:
        if (item.status != 'verified' or not item.evidence.strip()
                or not item.original or not re.fullmatch(r'HLA-[ABC]\*\d{2,3}:\d{2,3}', item.mapped)
                or '(' in item.original or ')' in item.original):
            raise ValueError('Unsupported or construct-changing allele mapping')
        original_locus = re.match(r'HLA-([ABC])', item.original)
        if original_locus is None or original_locus.group(1) != item.mapped[4]:
            raise ValueError('Unverified HLA locus mapping')
        if item.original in table and table[item.original] != item.mapped:
            raise ValueError('Ambiguous allele mapping')
        table[item.original] = item.mapped
    return table


def windows(peptide: str, length: int = 9) -> tuple[str, ...]:
    """Only full contiguous windows; shorter peptides are separately reported."""
    if type(length) is not int or length != 9:
        raise ValueError('This focused audit supports 9-residue windows only')
    if not isinstance(peptide, str) or not re.fullmatch('[A-Z]+', peptide):
        raise ValueError('Invalid original peptide string')
    return tuple(peptide[i:i + length] for i in range(len(peptide) - length + 1))


def hamming(left: str, right: str) -> int:
    if len(left) != len(right) or not left:
        raise ValueError('Hamming distance requires equal, nonempty lengths')
    return sum(a != b for a, b in zip(left, right))


def indexed_edges(sequences: Sequence[str], max_mismatches: int = 1,
                  *, edge_cap: int = MAX_EDGES) -> list[tuple[str, str, int]]:
    """Complete distinct 9-mer edges via masked signatures, with finite bounds.

    For d<=2 every distance<=d pair shares a signature masking d positions.
    No all-pairs scan is used. Dense buckets still have quadratic output cost;
    fail rather than truncate if signature/edge limits are exceeded.
    """
    if type(max_mismatches) is not int or not 0 <= max_mismatches <= 2:
        raise ValueError('Diagnostic maximum mismatches must be 0, 1 or 2')
    if type(edge_cap) is not int or edge_cap < 0:
        raise ValueError('Invalid edge cap')
    nodes = sorted(set(sequences))
    if len(nodes) > MAX_WINDOWS or any(not re.fullmatch('[A-Z]{9}', p) for p in nodes):
        raise ValueError('Bound exceeded or invalid 9-mer node')
    masks = tuple(combinations(range(9), max_mismatches))
    if len(nodes) * len(masks) > MAX_INDEX_ENTRIES:
        raise ValueError('Signature index bound exceeded')
    buckets: dict[tuple[tuple[int, ...], str], list[str]] = defaultdict(list)
    edges: dict[tuple[str, str], int] = {}
    for peptide in nodes:
        for mask in masks:
            signature = (mask, ''.join(c for i, c in enumerate(peptide) if i not in mask))
            bucket = buckets[signature]
            for other in bucket:
                key = (other, peptide)
                if key not in edges:
                    distance = hamming(other, peptide)
                    if distance <= max_mismatches:
                        edges[key] = distance
                        if len(edges) > edge_cap:
                            raise ValueError('Edge bound exceeded; audit incomplete, no truncation accepted')
            bucket.append(peptide)
    return [(a, b, edges[a, b]) for a, b in sorted(edges)]


def connected_components(nodes: Sequence[str], edges: Sequence[tuple[str, str, int]]) -> list[tuple[str, ...]]:
    adjacency: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b, _ in edges:
        if a not in adjacency or b not in adjacency or a == b:
            raise ValueError('Invalid similarity graph endpoint')
        adjacency[a].add(b)
        adjacency[b].add(a)
    result = []
    visited = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        pending = [start]
        visited.add(start)
        component = []
        while pending:
            node = pending.pop()
            component.append(node)
            for neighbor in sorted(adjacency[node], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        result.append(tuple(sorted(component)))
    return sorted(result, key=lambda c: (-len(c), c))


def _matches(records: Sequence[SequenceRecord], key) -> dict[str, Any]:
    groups: dict[Any, list[SequenceRecord]] = defaultdict(list)
    for record in records:
        groups[key(record)].append(record)
    repeated = [group for _, group in sorted(groups.items()) if len(group) > 1]
    cross = [g for g in repeated if len({r.group for r in g}) > 1]
    def cross_pairs(group: list[SequenceRecord]) -> int:
        counts = Counter(r.group for r in group)
        return (len(group) ** 2 - sum(n ** 2 for n in counts.values())) // 2
    return {'distinct_keys': len(groups), 'repeated_keys': len(repeated),
            'same_key_record_pairs': sum(len(g) * (len(g) - 1) // 2 for g in repeated),
            'cross_group_keys': len(cross),
            'cross_group_record_pair_count': sum(cross_pairs(g) for g in cross),
            'label_conflicting_keys': sum(len({r.label for r in g if r.label is not None}) > 1 for g in repeated)}


def provenance_flags(records: Sequence[SequenceRecord]) -> dict[str, Any]:
    result = {}
    for field in ('source_id', 'canonical_measurement_id', 'study_id', 'donor_id'):
        groups: dict[str, set[str]] = defaultdict(set)
        for r in records:
            value = getattr(r, field)
            if value is not None:
                groups[value].add(r.group)
        result[field] = {'cross_group_shared_identifiers': sum(len(v) > 1 for v in groups.values()),
                         'unknown_records': sum(getattr(r, field) is None for r in records),
                         'interpretation': 'Shared identifier flags exposure; source-level sharing alone does not prove identical measurements.'}
    result['mutant_relationships'] = {'explicit_relationship_records': sum(r.mutant_of is not None for r in records),
                                     'unknown_records': sum(r.mutant_of is None for r in records),
                                     'relationships_inferred_from_similarity': False}
    result['negative_provenance'] = dict(sorted(Counter(r.negative_provenance or 'unknown' for r in records).items()))
    result['checkpoint_exposure'] = dict(sorted(Counter(r.checkpoint_exposure or 'unknown' for r in records).items()))
    result['unknown_is_no_leakage'] = False
    return result


def audit_records(records: Sequence[SequenceRecord], *, max_mismatches: int = 1,
                  mappings: Sequence[AlleleMapping] = ()) -> dict[str, Any]:
    """Audit supplied groups without constructing or altering any partition."""
    if len(records) > MAX_RECORDS or len({r.record_id for r in records}) != len(records):
        raise ValueError('Duplicate record IDs or input record bound exceeded')
    table = allele_mapping_table(mappings)
    peptide_records: dict[str, list[SequenceRecord]] = defaultdict(list)
    window_records: dict[str, set[str]] = defaultdict(set)
    window_groups: dict[str, set[str]] = defaultdict(set)
    occurrences = 0
    for r in records:
        peptide_records[r.peptide].append(r)
        for window in set(windows(r.peptide)):
            occurrences += 1
            if occurrences > MAX_INDEX_ENTRIES:
                raise ValueError('Window occurrence inspection bound exceeded')
            window_records[window].add(r.record_id)
            window_groups[window].add(r.group)
            if len(window_records) > MAX_WINDOWS:
                raise ValueError('Unique window bound exceeded')
    edges = indexed_edges(list(window_records), max_mismatches)
    # A window graph is a diagnostic; it must not silently merge two windows
    # from a long peptide into one component. Registry feasibility uses 9-mers.
    components = connected_components(list(window_records), edges)
    degrees = Counter({p: 0 for p in window_records})
    for a, b, _ in edges:
        degrees[a] += 1
        degrees[b] += 1
    by_id = {r.record_id: r for r in records}
    components_summary = []
    for number, component in enumerate(components, 1):
        ids = set().union(*(window_records[w] for w in component))
        allele_counts = Counter(by_id[i].allele for i in ids)
        components_summary.append({'component_rank': number, 'window_nodes': len(component),
                                   'input_records_touching_component': len(ids),
                                   'by_allele': dict(sorted(allele_counts.items()))})
    allele_components: dict[str, Counter] = defaultdict(Counter)
    for c in components_summary:
        for allele, count in c['by_allele'].items():
            allele_components[allele][c['component_rank']] = count
    reused = [p for p, group in peptide_records.items() if len({r.allele for r in group}) > 1]
    return {'schema_version': 1, 'status': 'diagnostic_only_no_split_rule_approved',
            'input_records': len(records), 'supplied_groups': sorted({r.group for r in records}),
            'unique_peptides': len(peptide_records),
            'peptides_reused_across_alleles': len(reused),
            'records_for_cross_allele_reused_peptides': sum(len(peptide_records[p]) for p in reused),
            'peptide_allele_multiplicity': dict(sorted(Counter(str(len({r.allele for r in group})) for group in peptide_records.values()).items())),
            'noncanonical_peptide_records': sum(not set(r.peptide) <= AMINO_ACIDS for r in records),
            'exact_peptide_identity': _matches(records, lambda r: r.peptide),
            'strict_pair_identity': _matches(records, lambda r: (r.allele, r.peptide)),
            'evidence_mapped_pair_identity': _matches(records, lambda r: (table.get(r.allele, r.allele), r.peptide)),
            'allele_mapping_evidence': [vars(m) for m in sorted(mappings, key=lambda m: (m.original, m.mapped, m.evidence))],
            'short_peptides': {'records': sum(len(r.peptide) < 9 for r in records),
                               'unique_sequences': sum(len(p) < 9 for p in peptide_records),
                               'handling': 'Included in full-sequence/pair identity; no padded or invented 9-mer; near-short similarity unavailable.'},
            'window_rule': {'length': 9, 'maximum_aligned_hamming_distance': max_mismatches,
                            'predicate': 'distance <= maximum; default <=1 equals fewer than two mismatches',
                            'implementation': 'Complete masked-position signature index on unique windows; no CD-HIT equivalence claim'},
            'unique_9mer_windows': len(window_records),
            'shared_exact_9mer_windows_across_groups': sum(len(g) > 1 for g in window_groups.values()),
            'distinct_window_direct_edges': len(edges),
            'direct_edge_distance_counts': dict(sorted(Counter(str(d) for _, _, d in edges).items())),
            'direct_edges_with_any_cross_group_occurrences': sum(any(x != y for x in window_groups[a] for y in window_groups[b]) for a, b, _ in edges),
            'direct_neighbor_count_distribution': dict(sorted(Counter(str(d) for d in degrees.values()).items())),
            'maximum_direct_neighbors': max(degrees.values(), default=0),
            'components': {'count': len(components),
                           'size_distribution': dict(sorted(Counter(str(len(c)) for c in components).items())),
                           'largest_window_component': len(components[0]) if components else 0,
                           'maximum_input_records_touching_one_component': max((c['input_records_touching_component'] for c in components_summary), default=0),
                           'all_components_by_size': components_summary,
                           'by_allele': {a: {'components_touched': len(c), 'maximum_records_in_one_component': max(c.values()),
                                             'records_with_9mer_windows': sum(r.allele == a and len(r.peptide) >= 9 for r in records)} for a, c in sorted(allele_components.items())},
                           'meaning': 'Transitive membership is not direct similarity; long peptides may touch multiple window components. No cluster assignment to folds exists.'},
            'provenance': provenance_flags(records),
            'limits': {'maximum_unique_windows': MAX_WINDOWS, 'maximum_direct_edges': MAX_EDGES,
                       'maximum_index_entries': MAX_INDEX_ENTRIES,
                       'scope': 'Exact uppercase strings, contiguous windows, aligned substitutions only; no indels, local alignment, anchor weighting, donor inference or complete antigen-family detection.'},
            'split_assignments_created': False, 'labels_modified': False,
            'independence_or_leakage_free_certificate': False}


def exposure_matrix() -> dict[str, Any]:
    roles = ['Teacher_train', 'Teacher_validation', 'EL_baseline_train', 'EL_corrected_train',
             'IM_transfer_train', 'final_assayed_IM_evaluation_candidates', 'affinity_comparator',
             'public_pretrained_checkpoints', 'artificial_negatives_and_decoys']
    guards = ['exact_peptide', 'peptide_HLA', 'near_peptide', 'study_donor',
              'label_derived_overlap', 'shared_experimental_observation', 'pretraining_exposure']
    pairs = []
    for a, b in combinations(roles, 2):
        same_design = {a, b} == {'EL_baseline_train', 'EL_corrected_train'}
        if same_design:
            action = 'Intentional matched original EL inputs; preserve lineage and isolate the future pseudolabel intervention.'
        elif 'final_assayed_IM_evaluation_candidates' in (a, b):
            action = 'Freeze candidates before development; audit direct and transitive Teacher/EL/IM/comparator/checkpoint exposure, with later approved exclusion or residual-risk rules.'
        elif 'public_pretrained_checkpoints' in (a, b):
            action = 'Obtain exact training history and transitive source identities; unknown history is not clearance; principal initialization must not already be IM-trained.'
        elif 'artificial_negatives_and_decoys' in (a, b):
            action = 'Track generation and reuse after splitting; constructed negatives are not assayed IM negatives and kinetic zeros are not decoy labels.'
        elif a.startswith('Teacher') and b.startswith('Teacher'):
            action = 'Candidate sequence/source grouping between Teacher training and validation; no shared canonical measurement or alias across folds.'
        elif a.startswith('Teacher') or b.startswith('Teacher'):
            action = 'Quantify cross-task sequence/source exposure and independent Teacher label provenance; overlap and independence require separate interpretation.'
        else:
            action = 'Audit intended transfer/comparator exposures separately from evaluation leakage; exact, near, provenance and label histories remain unknown.'
        pairs.append({'left': a, 'right': b, 'proposed_guards': guards,
                      'status': 'intentional_matched_shared_inputs_not_measured' if same_design else 'unknown_not_quantified',
                      'intended_action': action,
                      'availability': 'No EL/IM datasets or checkpoint histories acquired in this task.'})
    return {'roles': roles, 'pairs': pairs,
            'known_registry_lineage': 'SPEARMINT released Stage 2 rows alias DTU ordinary rows; no independent cohort.',
            'Teacher_EL_IM_risk': 'Teacher fitting or correction thresholds must not indirectly expose final evaluation sequences/labels during model selection; held-out Teacher groups need the same cross-task audit.',
            'metadata_unavailable': ['complete DTU row-study/donor/antigen tags', 'EL/IM source rows', 'checkpoint training histories'],
            'negative_controls': 'Distinguish assayed IM negatives, random EL decoys, pseudolabels and source-reported kinetic zeros; never substitute their meanings.',
            'actual_BigMHC_or_IM_overlap_quantified': False}


def rule_catalog() -> dict[str, Any]:
    return {'schema_version': 1, 'rules': [
        {'id': 'exact_peptide', 'unit': 'Original full peptide string, across HLA', 'does_not_cover': 'near sequences, study, donor, checkpoint'},
        {'id': 'exact_pair', 'unit': 'Original HLA plus peptide; optional explicit verified mapping', 'does_not_cover': 'same peptide on another HLA'},
        {'id': 'shared_9mer', 'unit': 'Any exact contiguous 9-residue windows including longer peptides', 'does_not_cover': 'short sequences and noncontiguous motifs'},
        {'id': 'aligned_9mer_hamming', 'unit': 'Configurable 0, 1 or 2 aligned mismatches', 'status': 'candidate_threshold_not_approved', 'does_not_cover': 'indels, structural equivalence, CD-HIT greedy clustering'},
        {'id': 'connected_components', 'unit': 'All transitive paths in declared window graph', 'does_not_cover': 'long-peptide membership consolidation, fold assignment or feasibility optimization'},
        {'id': 'provenance', 'unit': 'Explicit source/alias/study/donor/mutant/negative/checkpoint metadata', 'unknown_means': 'unavailable, not no leakage'}],
        'proposed_future_contract': ['Choose grouping scope and metric before splits', 'Group lineage-equivalent observations',
                                    'Audit again after preprocessing/augmentation/negative generation',
                                    'Report retained composition, direct crossing edges and maximum cross-fold similarity',
                                    'Keep test sequences/outcomes from model-selection decisions'],
        'approved_split_algorithm': None, 'approved_threshold': None}


@dataclass(frozen=True)
class LeakageResult:
    reports: dict[str, dict[str, Any]]
    inputs: list[dict[str, str]]


def inspect(*, paths: StoragePaths | None = None, registry_path: str | Path | None = None,
            config_path: str | Path | None = None, max_mismatches: int | None = None) -> LeakageResult:
    storage = resolve_paths() if paths is None else paths
    config = readers._json(config_path or storage.repository_root / PROTOCOL)
    if config.get('schema_version') != 1 or set(config.get('inputs', {})) != {'observations', 'parent_manifest', 'evidence'}:
        raise ValueError('Invalid protocol input configuration')
    runs.validate_run_id(config['parent_registry_run_id'])
    root = storage.project_runs_dir / config['parent_registry_run_id']
    input_paths = {}
    inputs = []
    for key, entry in config['inputs'].items():
        relative = registry._relative(entry['parent_relative_path'])
        if not re.fullmatch('[a-f0-9]{64}', entry['sha256']):
            raise ValueError('Invalid pinned input checksum')
        path = Path(registry_path).expanduser().absolute() if key == 'observations' and registry_path else root / relative
        checksum = raw.sha256_file(path)
        if checksum != entry['sha256']:
            raise ValueError('Pinned registry input checksum mismatch: ' + key)
        input_paths[key] = path
        inputs.append({'path': str(path), 'sha256': checksum})
    parent = readers._json(input_paths['parent_manifest'])
    runs.validate_manifest(parent)
    if (parent['run_id'] != config['parent_registry_run_id'] or parent['git']['commit_sha'] != config['parent_registry_commit']
            or not parent['reproducibility']['canonical']):
        raise ValueError('Parent registry run identity differs')
    evidence = readers._json(input_paths['evidence'])
    records = []
    ids = set()
    count = 0
    zero_count = 0
    for item in readers._jsonl(input_paths['observations'], 64 * 1024 * 1024):
        try:
            if not isinstance(item['data_quality_flags'], list) or any(not isinstance(f, str) for f in item['data_quality_flags']):
                raise ValueError('Invalid source quality flags')
            observation = registry.Observation(**item)
        except (TypeError, KeyError) as error:
            raise ValueError('Invalid canonical observation') from error
        value = registry.decimal_value(observation.original_measurement_text)
        if ('exact_zero' in observation.data_quality_flags) != (value == 0):
            raise ValueError('Registry zero flag disagrees with source value')
        if (observation.measurement_type == 'kinetic_half_life' and value == 0
                and 'zero_semantics_unresolved' not in observation.data_quality_flags):
            raise ValueError('Registry reported-zero semantics must remain unresolved')
        if observation.measurement_type != {'netmhcstabpan_2016': 'kinetic_half_life', 'jappe_2020': 'thermal_melting_temperature'}[observation.source_id]:
            raise ValueError('Registry source/modality mismatch')
        if observation.observation_id in ids:
            raise ValueError('Duplicate canonical observation ID')
        ids.add(observation.observation_id)
        count += 1
        if observation.source_id != 'netmhcstabpan_2016':
            continue
        if observation.measurement_type != 'kinetic_half_life' or observation.measurement_unit != 'hours':
            raise ValueError('DTU modality mismatch')
        if dtu.identifier_category(observation.original_allele) not in {'ordinary_hla_a', 'ordinary_hla_b'}:
            continue
        if len(observation.original_peptide) != 9:
            raise ValueError('Ordinary DTU nine-mer expectation fails')
        zero_count += registry.decimal_value(observation.original_measurement_text) == 0
        records.append(SequenceRecord(observation.observation_id, observation.original_peptide,
                                      observation.original_allele, 'ordinary_DTU_reference', observation.source_id,
                                      canonical_measurement_id=observation.observation_id))
    observed = {'ordinary_DTU_records': len(records), 'ordinary_DTU_alleles': len({r.allele for r in records}),
                'ordinary_DTU_zeros': zero_count}
    if observed != config['expected_reference_counts']:
        raise ValueError('Actual reference counts differ from explicit protocol expectations')
    if config['feasibility_rule']['window_length'] != 9:
        raise ValueError('Unsupported protocol window length')
    distance = config['feasibility_rule']['max_hamming_distance'] if max_mismatches is None else max_mismatches
    summary = audit_records(records, max_mismatches=distance)
    summary.update(reference_counts=observed, canonical_records_validated=count,
                   excluded_from_sequence_analysis='All C67S and Jappe Tm records; scientific registry unchanged.',
                   future_partition_feasibility='Components quantify indivisible groups if every declared edge must remain within a fold. Actual balancing, feasibility and thresholds remain undecided.',
                   cross_task_limits='Only one existing reference group supplied; cross-group zeros here do not quantify EL/IM or checkpoint exposure.')
    literature = readers._json(storage.repository_root / LITERATURE)
    if literature.get('schema_version') != 1 or len(literature.get('methods', [])) != 6:
        raise ValueError('Incomplete literature evidence register')
    reports = {'hard_split_literature_evidence.json': literature,
               'leakage_rule_catalog.json': rule_catalog(),
               'stability_sequence_neighborhood_summary.json': summary,
               'cross_task_exposure_matrix.json': exposure_matrix(),
               'phase2_pending_decisions.json': {'protocol_version': config['protocol_version'],
                    'decisions': config['decisions'], 'pending': config['pending_decisions'],
                    'performance_interpretation': config['performance_interpretation'],
                    'no_actual_splits_or_corrections': True},
               'source_evidence_link.json': {'parent_registry_run_id': parent['run_id'],
                    'parent_registry_commit': parent['git']['commit_sha'], 'direct_inputs': inputs,
                    'inherited_source_evidence': evidence,
                    'raw_scientific_source_artifacts_read': False,
                    'supplement_pdf_read': False,
                    'source_verification_limit': 'Derived registry bytes validated; original DTU/XLSX files not re-read or claimed as direct inputs.',
                    'repository_configuration_sha256': raw.sha256_file(config_path or storage.repository_root / PROTOCOL),
                    'literature_evidence_sha256': raw.sha256_file(storage.repository_root / LITERATURE)}}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Input changed during sequence audit')
    return LeakageResult(reports, inputs)


def write_reports(result: LeakageResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    directory = Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name != 'reports' or directory.parent.parent != storage.project_runs_dir:
        raise ValueError('Output requires an existing authorized project run reports directory')
    manifest = runs.load_manifest(directory.parent.name, paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Run must record every unchanged registry input')
    names = [*result.reports, 'execution_verification.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:
                os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError('Report already exists: ' + name)
    for name, document in result.reports.items():
        raw.write_report(directory / name, document, paths=storage)
    receipt = {'reports': {name: raw.sha256_file(directory / name) for name in result.reports},
               'inputs': result.inputs, 'code_commit': manifest['git']['commit_sha'],
               'parent_registry_run_id': result.reports['source_evidence_link.json']['parent_registry_run_id'],
               'completion': 'evidence_and_sequence_feasibility_only; no splits, labels or performance generated'}
    for item in result.inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Input changed before report completion')
    raw.write_report(directory / names[-1], receipt, paths=storage)
    return receipt
