"""Frozen-score training views and provisional global sequence-hard development cohort."""
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
import ast
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import secrets
from typing import Any, Mapping
import zipfile

from . import pseudolabel_pilot as pilot
from . import bigmhc_v4_audit as data
from . import stability_teacher as teacher
from . import netmhcstabpan_2016 as raw
from . import scientific_gate0_preflight as readers
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/bigmhc_pilot_v0.json'
VERSION = 'bigmhc_pilot_v0'
POLICIES = ('original', 'low_only', 'low_and_high')
ALLOWED = (*pilot.MEMBERS, 'im_val.csv')
EXTRA = {'reference', 'el_scores', 'im_scores', 'el_overrides', 'im_overrides',
         'scoring_receipt', 'scoring_summary', 'teacher_metrics', 'dataset_code', 'cli_code'}
LEDGER = ['source_file', 'row_index', 'source_line_number', 'source_row_id', 'source_row_sha256',
          'original_peptide', 'original_hla', 'resolved_hla', 'original_label', 'predicted_half_life_hours',
          'candidate_action', 'retained', 'exclusion_reason', 'derived_row_index', 'low_only_label', 'low_and_high_label']


def load_config(path: str | Path) -> dict[str, Any]:
    config = readers._json(path)
    if (config.get('schema_version') != 1 or config.get('version') != VERSION or config.get('seed') != 42
            or config.get('maximum_hamming_distance') != 1 or set(config.get('inputs', {})) != EXTRA
            or config.get('extreme_shift_fraction') != 0.9 or not pilot._sha(config.get('bigmhc_commit'), 40)):
        raise ValueError('Invalid frozen pilot-preparation configuration')
    for item in config['inputs'].values():
        pilot.registry._relative(item['relative_path'])
        if item['area'] not in {'data', 'runs'} or not pilot._sha(item['sha256']):
            raise ValueError('Invalid immutable input identity')
    if not pilot._sha(config['development_member']['sha256']):
        raise ValueError('Invalid development member identity')
    return config


def resolve_inputs(config, paths, files=None):
    overrides = files or {}
    if set(overrides) - (EXTRA | pilot.INPUTS):
        raise ValueError('Unknown pilot input override')
    result, identities = pilot.resolve_inputs(config['scoring_config'], paths,
        {k: v for k, v in overrides.items() if k in pilot.INPUTS})
    for name, item in config['inputs'].items():
        root = paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir
        path = Path(overrides.get(name, root / item['relative_path'])).expanduser().absolute()
        if raw.sha256_file(path) != item['sha256']:
            raise ValueError('Pilot preparation SHA256 mismatch: ' + name)
        result[name] = path
        identities.append({'path': str(path), 'sha256': item['sha256']})
    return result, identities


def exclusion_reason(peptide: str, hla: str, context: pilot.Context, reference: Mapping) -> str | None:
    if len(peptide) != 9:
        return 'unsupported_peptide_length'
    if any(c not in teacher.ALPHABET for c in peptide):
        return 'noncanonical_amino_acid'
    resolved = context.mapping.get(hla)
    if resolved is None or data.canonical_hla(hla) != resolved or not resolved.startswith(('HLA-A*', 'HLA-B*')):
        return 'unverified_or_unsupported_HLA'
    model = context.model.document['alleles'].get(resolved)
    if model is None or model['status'] != 'trained':
        return 'Teacher_unsupported_or_sparse_HLA'
    if len(reference.get(resolved, ())) != 1:
        return 'unresolved_or_ambiguous_reference'
    return None


def source_hash(header, fields):
    return hashlib.sha256(json.dumps([header, fields], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def check_score(score, member, index, line, header, fields, context):
    """Join immutable original fields, coordinates, model and candidate semantics."""
    if (score['source_file'] != member or int(score['row_index']) != index
            or int(score['source_line_number']) != line
            or score['source_row_id'] != pilot.row_id(context.archive_sha256, member, index)
            or score['source_row_sha256'] != source_hash(header, fields)
            or [score['original_hla'], score['original_peptide'], score['original_label']] != fields[:3]
            or score['resolved_hla'] != context.mapping.get(fields[0])
            or score['teacher_model_sha256'] != context.model_sha256 or score['model_status'] != 'ok'
            or score['teacher_version'] != teacher.VERSION or score['rule_version'] != pilot.VERSION):
        raise ValueError('Source-row/score join mismatch')
    category, action, proposed = pilot.category_and_action(fields[2], float(score['predicted_half_life_hours']))
    if (score['stability_category'], score['candidate_action'], score['proposed_pseudolabel']) != (category, action, proposed):
        raise ValueError('Saved candidate disagrees with frozen thresholds')


def apply_override(score, override, member, context, policy, *, authorized):
    if member not in pilot.MEMBERS or policy not in POLICIES:
        raise ValueError('Training-only override policy required')
    if score['candidate_action'] != 'no_change':
        if override != score:
            raise ValueError('Missing or altered sparse override')
        pilot.OverrideGuard(member, context.archive_sha256, context.model_sha256).check(
            override, {score['source_row_id']})
    elif override is not None:
        raise ValueError('Unexpected sparse override')
    if not authorized:
        raise ValueError('Overrides forbidden for purged/development rows')
    return (score['proposed_pseudolabel'] if policy != 'original'
            and pilot.candidate_for_policy(score, policy) else score['original_label'])


def substitution_neighborhood(peptides):
    """Independent complete distance <=1 membership oracle for small dev cohorts."""
    neighbors = set(peptides)
    for peptide in sorted(peptides):
        for i in range(9):
            for residue in teacher.ALPHABET:
                neighbors.add(peptide[:i] + residue + peptide[i+1:])
    return neighbors


def independent_exposed(peptide, fitting_peptides):
    return peptide in fitting_peptides or any(
        peptide[:i] + a + peptide[i+1:] in fitting_peptides for i in range(9) for a in teacher.ALPHABET)


def _csv_rows(path):
    with raw._read_file(path) as stream, gzip.GzipFile(fileobj=stream, mode='rb') as compressed:
        with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as text:
            rows = csv.DictReader(text, strict=True)
            if rows.fieldnames != pilot.FIELDS:
                raise ValueError('Saved score/override schema changed')
            last = 0
            for row in rows:
                index = int(row['row_index'])
                if index <= last or None in row or any(v is None for v in row.values()):
                    raise ValueError('Duplicate/unordered or malformed score/override row')
                last = index
                yield row


@contextmanager
def artifact_csv(path, fields, compressed=False):
    """Exclusive atomic publication or bounded-memory byte-identical hash replay."""
    with ExitStack() as stack:
        parent = partial = stream = None
        if path is not None:
            parent = stack.enter_context(raw._directory(path.parent))
            try:
                os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError('Existing pilot artifact preserved')
            partial = '.' + path.name + '.' + secrets.token_hex(12) + '.partial'
            stream = stack.enter_context(os.fdopen(os.open(partial, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY,
                                                         0o600, dir_fd=parent), 'wb'))
        sink = pilot._HashSink(stream)
        try:
            if compressed:
                output = stack.enter_context(gzip.GzipFile(filename='', mode='wb', fileobj=sink, mtime=0, compresslevel=6))
            else:
                # TextIOWrapper requires IOBase; the gzip level-zero path is not used for plain CSV.
                class Wrapper(io.RawIOBase):
                    def writable(self): return True
                    def write(self, value): return sink.write(value)
                output = Wrapper()
            with io.TextIOWrapper(output, encoding='utf-8', newline='') as text:
                writer = csv.DictWriter(text, fieldnames=fields, lineterminator='\n')
                writer.writeheader()
                yield writer, sink
            # The text wrapper finishes the gzip footer before publication; the
            # plain RawIOBase wrapper closes without closing the sink's file.
            if stream is not None:
                stream.flush(); os.fsync(stream.fileno())
                os.link(partial, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
        finally:
            if partial is not None:
                os.unlink(partial, dir_fd=parent)


def _source_rows(archive, member, members, opened, identities):
    if member not in ALLOWED:
        raise ValueError('Sealed or unauthorized payload requested')
    return data._rows(archive, members[member], member, opened, identities)


def development(records, context, reference, writer, ledger):
    iterator = iter(records)
    _, header = next(iterator)
    if header != ['mhc', 'pep', 'tgt', 'rand']:
        raise ValueError('Development CSV schema changed')
    result = {'total': 0, 'excluded_by_reason': Counter(), 'retained': 0, 'retained_labels': Counter(),
              'by_HLA': Counter(), 'independent_teacher_separation_violations': 0}
    retained = set()
    for index, (line, fields) in enumerate(iterator, 1):
        if len(fields) != 4 or fields[2] not in {'0', '1'}:
            raise ValueError('Malformed development source row')
        hla, peptide, label = fields[:3]
        reason = exclusion_reason(peptide, hla, context, reference)
        exposure = context.neighbors.query(peptide, context.mapping.get(hla, '')) if reason is None else {}
        if exposure.get('teacher_fit_exact_peptide'):
            reason = 'Teacher_fit_exact_peptide'
        elif exposure.get('teacher_fit_within_one_mismatch_peptide'):
            reason = 'Teacher_fit_one_mismatch_peptide'
        result['total'] += 1
        if reason is None:
            if independent_exposed(peptide, context.neighbors.fit_peptides):
                raise ValueError('Independent Teacher/development separation failure')
            retained.add((peptide, context.mapping[hla]))
            writer.writerow(dict(zip(('mhc', 'pep', 'tgt'), (context.mapping[hla], peptide, label))))
            result['retained'] += 1
            result['retained_labels'][label] += 1
            result['by_HLA'][context.mapping[hla]] += 1
        else:
            result['excluded_by_reason'][reason] += 1
        ledger.writerow({'source_file': 'im_val.csv', 'row_index': index, 'source_line_number': line,
            'source_row_id': 'development_' + hashlib.sha256(f'{context.archive_sha256}\0im_val.csv\0{index}'.encode()).hexdigest(),
            'source_row_sha256': source_hash(header, fields), 'original_peptide': peptide, 'original_hla': hla,
            'resolved_hla': context.mapping.get(hla, ''), 'original_label': label, 'retained': int(reason is None),
            'exclusion_reason': reason or '', 'derived_row_index': result['retained'] if reason is None else ''})
    result['unique_retained_peptides'] = len({p for p, _ in retained})
    if not retained:
        raise ValueError('No eligible sequence-separated development observations; do not weaken rules')
    return result, retained


def _new_group():
    return {'original': Counter(), 'low_only': Counter(), 'low_and_high': Counter(), 'purged': Counter(),
            'actions': Counter(), 'eligible_before_purge': 0}


def train_views(member, records, scores, overrides, context, reference, dev_index, independent_neighbors,
                writers, ledger):
    iterator = iter(records); _, header = next(iterator)
    if header != ['mhc', 'pep', 'tgt'] + (['rand'] if member == 'im_train.csv' else []):
        raise ValueError('Training schema changed')
    scores, overrides = iter(scores), iter(overrides)
    score, override = next(scores, None), next(overrides, None)
    total = eligible = kept = exact_purge = near_purge = 0
    excluded = Counter(); groups = defaultdict(_new_group); identity_hash = hashlib.sha256()
    b08_predictions = []  # Only the small focused positive-label group, not all EL predictions.
    for index, (line, fields) in enumerate(iterator, 1):
        total += 1
        if len(fields) != len(header) or fields[2] not in {'0', '1'}:
            raise ValueError('Malformed training row')
        hla, peptide, label = fields[:3]
        reason = exclusion_reason(peptide, hla, context, reference)
        if score is not None and int(score['row_index']) < index:
            raise ValueError('Unmatched saved score')
        current = score is not None and int(score['row_index']) == index
        if not current:
            if reason is None:
                raise ValueError('Eligible source row lacks saved score; do not silently rescore/drop')
            excluded[reason] += 1
            if override is not None and int(override['row_index']) <= index:
                raise ValueError('Override without eligible saved score')
            continue
        if reason is not None:
            raise ValueError('Saved eligibility disagrees with frozen pilot eligibility')
        check_score(score, member, index, line, header, fields, context)
        if override is not None and int(override['row_index']) < index:
            raise ValueError('Unmatched sparse override')
        matched_override = override if override is not None and int(override['row_index']) == index else None
        # Validate every candidate, including ones subsequently purged; apply only to retained training views.
        if (score['candidate_action'] != 'no_change' and matched_override != score
                or score['candidate_action'] == 'no_change' and matched_override is not None):
            raise ValueError('Missing, mismatched or extra sparse override')
        group = groups[score['resolved_hla']]; group['eligible_before_purge'] += 1
        if score['resolved_hla'] == 'HLA-B*08:01' and label == '1':
            b08_predictions.append(float(score['predicted_half_life_hours']))
        eligible += 1
        exposure = dev_index.query(peptide, score['resolved_hla'])
        purged = exposure['teacher_fit_within_one_mismatch_peptide']
        if purged != (peptide in independent_neighbors):
            raise ValueError('Independent substitution/index purge disagreement')
        reason = ('development_exact_peptide' if exposure['teacher_fit_exact_peptide'] else
                  'development_one_mismatch_peptide') if purged else ''
        labels = {}
        if purged:
            group['purged'][label] += 1
            exact_purge += int(exposure['teacher_fit_exact_peptide'])
            near_purge += int(not exposure['teacher_fit_exact_peptide'])
        else:
            kept += 1
            identity_hash.update((score['source_row_id'] + '\n').encode())
            for policy in POLICIES:
                labels[policy] = apply_override(score, matched_override, member, context, policy, authorized=True)
                writers[policy].writerow({'mhc': score['resolved_hla'], 'pep': peptide, 'tgt': labels[policy]})
                group[policy][labels[policy]] += 1
            group['actions'][score['candidate_action']] += 1
        ledger.writerow({**{k: score[k] for k in LEDGER if k in score}, 'retained': int(not purged),
            'exclusion_reason': reason, 'derived_row_index': kept if not purged else '',
            'low_only_label': labels.get('low_only', ''), 'low_and_high_label': labels.get('low_and_high', '')})
        if matched_override is not None:
            override = next(overrides, None)
        score = next(scores, None)
    if score is not None or override is not None:
        raise ValueError('Unconsumed/unmatched score or override')
    balances = {p: {v: sum(g[p][v] for g in groups.values()) for v in ('0', '1')} for p in POLICIES}
    return {'total_source_rows': total, 'eligible_before_purge': eligible, 'unsupported_by_reason': excluded,
        'retained_rows': kept, 'purged_exact': exact_purge, 'purged_one_mismatch_only': near_purge,
        'class_balances': balances, 'by_HLA': dict(sorted(groups.items())),
        'source_identity_order_sha256_all_views': identity_hash.hexdigest(),
        'positive_anchored_nine_mer_group_usable': {p: balances[p]['1'] > 0 and balances[p]['0'] > 0 for p in POLICIES},
        'independent_remaining_development_neighbors': 0}, b08_predictions


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {'n': 0}
    return {'n': len(ordered), 'min': ordered[0], 'max': ordered[-1], 'mean': sum(ordered) / len(ordered),
        'reported_zero_count': sum(v == 0 for v in ordered),
        'fraction_below_one_hour': sum(v < 1 for v in ordered) / len(ordered),
        'quantiles_linear_interpolation': {str(q): ordered[int((len(ordered)-1)*q)] +
            (ordered[min(int((len(ordered)-1)*q)+1, len(ordered)-1)]-ordered[int((len(ordered)-1)*q)]) *
            (((len(ordered)-1)*q) % 1) for q in (0.25, 0.5, 0.75, 0.95)}}


def loader_contract_smoke(path, reference):
    """Check a bounded sample using the pinned loader's positional CSV contract."""
    count = 0
    with raw._read_file(path) as stream, io.TextIOWrapper(stream, encoding='utf-8', newline='') as text:
        rows = csv.reader(text, strict=True)
        if next(rows) != ['mhc', 'pep', 'tgt']:
            raise ValueError('Training-input header mismatch')
        for row in rows:
            if (len(row) != 3 or len(reference.get(row[0], ())) != 1 or len(row[1]) != 9
                    or any(a not in teacher.ALPHABET for a in row[1]) or row[2] not in {'0', '1'}):
                raise ValueError('Training-input positional loader contract failed')
            float(row[2])
            count += 1
            if count == 128:
                break
    return {'checked_rows': count, 'maximum_rows': 128, 'status': 'positional_contract_passed',
            'external_loader_executed': False}


def diagnostic(files, context, config, results, b08_predictions):
    population, _ = teacher.load_population(files['registry'], context.model.document['config'])
    values = [float(o.parsed_measurement_decimal) for o in population if o.original_allele == 'HLA-B*08:01']
    previous = readers._json(files['scoring_summary'])
    warnings = []
    for stage, member in (('EL', 'el_train.csv'), ('IM', 'im_train.csv')):
        for hla, group in results[member]['by_HLA'].items():
            for direction, old, new in (('LOW_positive_to_negative', '1', 'low_only'),
                                         ('HIGH_negative_to_positive', '0', 'low_and_high')):
                count = (group['original']['1'] - group['low_only']['1'] if old == '1' else
                         group['low_and_high']['1'] - group['low_only']['1'])
                denom = group['original'][old]
                if denom and count / denom >= 0.2:
                    warnings.append({'stage': stage, 'HLA': hla, 'direction': direction, 'candidates': count,
                        'original_class_rows': denom, 'fraction': count / denom,
                        'extreme_shift': count / denom >= config['extreme_shift_fraction'],
                        'review_before_training': True})
    return {'HLA': 'HLA-B*08:01', 'ordinary_DTU_hours': distribution(values),
        'ordinary_DTU_zero_fraction': sum(v == 0 for v in values) / len(values) if values else None,
        'saved_Teacher_validation_metrics': readers._json(files['teacher_metrics'])['results'].get('HLA-B*08:01'),
        'saved_scores_positive_training_predictions_before_purge': {m: distribution(v) for m, v in b08_predictions.items()},
        'original_Task24_B08_groups': {m: r['by_original_HLA'].get('HLA-B*08:01') for m, r in previous['members'].items()},
        'validated_mapping': {k: v for k, v in context.mapping.items() if v == 'HLA-B*08:01'},
        'large_shift_groups_after_purge': warnings,
        'interpretation': 'Low predictions do not establish that experimentally observed positives are wrong; fixed thresholds unchanged; no groups discarded',
        'decision_required': 'Review extreme allele/direction shifts before using candidate labels in actual training'}


def prepare(*, config_path: str | Path, out: str | Path, paths: StoragePaths | None = None,
            files: Mapping | None = None, verify_existing: bool = False) -> dict[str, Any]:
    paths = paths or resolve_paths(); config = load_config(config_path)
    resolved, inputs = resolve_inputs(config, paths, files)
    directory, manifest = teacher._run(out, paths)
    if (manifest['configuration']['file'] != {'path': str(Path(config_path).absolute()), 'sha256': raw.sha256_file(config_path)}
            or manifest['configuration']['random_seed'] != 42
            or any(i not in manifest['data_provenance']['input_artifacts'] for i in inputs)):
        raise ValueError('Run must record configuration, seed42 and all actual inputs')
    context = pilot.load_context(config['scoring_config'], resolved)
    previous = readers._json(resolved['scoring_receipt'])
    summary = readers._json(resolved['scoring_summary'])
    teacher_receipt = readers._json(resolved['teacher_receipt'])
    if teacher_receipt['report_sha256']['teacher_validation_metrics.json'] != raw.sha256_file(resolved['teacher_metrics']):
        raise ValueError('Teacher saved metric identity disagrees with frozen receipt')
    if previous['report_sha256']['pseudolabel_summary.json'] != raw.sha256_file(resolved['scoring_summary']):
        raise ValueError('Parent scoring receipt/summary mismatch')
    for stage in ('el', 'im'):
        for kind, relative in zip(('scores', 'overrides'), pilot.OUTPUTS[stage + '_train.csv']):
            if summary['artifacts'][relative]['sha256'] != raw.sha256_file(resolved[stage + '_' + kind]):
                raise ValueError('Parent artifact receipt mismatch')
    with raw._read_file(resolved['reference']) as stream, io.TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
        reference_report, _, reference = data._reference(enumerate(csv.reader(text, strict=True), 1))
    if (reference_report['invalid_one_hot_rows'] or reference_report['duplicate_identifier_count']
            or reference_report['sanitized_UID_collision_groups'] or reference_report['feature_count'] != 414):
        raise ValueError('Invalid or incompatible pinned receptor reference')
    dataset_tree = ast.parse(resolved['dataset_code'].read_text())
    cli_tree = ast.parse(resolved['cli_code'].read_text())
    source_contract = {'dataset_AST_valid': isinstance(dataset_tree, ast.Module), 'cli_AST_valid': isinstance(cli_tree, ast.Module),
        'source_commit': config['bigmhc_commit'],
        'format': 'UTF8 CSV header mhc,pep,tgt; positional columns 0,1,2; skip one header; canonical uppercase peptide; binary float-compatible target',
        'validation': 'Standard-library positional CSV/414-feature contract checked; external BigMHC modules not imported or executed',
        'full_BigMHC_loader_executed': False, 'remaining_dependency': 'BigMHC-compatible PyTorch and pandas environment; seed42 plumbing (pinned CLI hardcodes1); explicit EL-to-IM parent checkpoint handling',
        'positive_anchored_grouping': 'Pinned Dataset batches group by peptide length, not allele; no sampler redesign/equalization'}
    artifacts = {}; opened = []; identities = {}; results = {}; b08_predictions = {}
    with ExitStack() as stack:
        def writer(relative, fields, compressed=False):
            w, sink = stack.enter_context(artifact_csv(None if verify_existing else directory / relative, fields, compressed))
            artifacts[relative] = sink
            return w
        dev_writer = writer('processed/im_development.csv', ['mhc', 'pep', 'tgt'])
        dev_ledger = writer('processed/im_development_provenance.csv.gz', LEDGER, True)
        views = {m: {p: writer(f'processed/{m[:-4]}_{p}.csv', ['mhc', 'pep', 'tgt']) for p in POLICIES}
                 for m in pilot.MEMBERS}
        ledgers = {m: writer(f'processed/{m[:-4]}_provenance.csv.gz', LEDGER, True) for m in pilot.MEMBERS}
        with raw._read_file(resolved['archive']) as stream, zipfile.ZipFile(stream) as archive:
            members, _ = data.archive_inventory(archive)
            dev, retained = development(_source_rows(archive, 'im_val.csv', members, opened, identities),
                context, reference, dev_writer, dev_ledger)
            if (dev['total'] != config['development_member']['rows']
                    or identities['im_val.csv']['sha256'] != config['development_member']['sha256']):
                raise ValueError('Development member identity/count mismatch')
            dev_index = pilot.NeighborIndex(retained, retained)
            independent = substitution_neighborhood({p for p, _ in retained})
            for stage, member in (('el', 'el_train.csv'), ('im', 'im_train.csv')):
                results[member], b08_predictions[member] = train_views(member,
                    _source_rows(archive, member, members, opened, identities), _csv_rows(resolved[stage + '_scores']),
                    _csv_rows(resolved[stage + '_overrides']), context, reference, dev_index, independent, views[member], ledgers[member])
                if (results[member]['total_source_rows'] != config['scoring_config']['members'][member]['rows']
                        or identities[member]['sha256'] != config['scoring_config']['members'][member]['sha256']):
                    raise ValueError('Training member identity/count mismatch')
                if not all(results[member]['positive_anchored_nine_mer_group_usable'].values()):
                    raise ValueError('Unusable empty-class nine-mer training view; do not silently change pilot rules')
    hashes = {k: {'sha256': v.digest.hexdigest(), 'bytes': v.size} for k, v in artifacts.items()}
    sanity = diagnostic(resolved, context, config, results, b08_predictions)
    conditions = {c: {'EL': f'processed/el_train_{el}.csv', 'IM': f'processed/im_train_{im}.csv',
                     'development': 'processed/im_development.csv', 'seed': 42,
                     'EL_rows': results['el_train.csv']['retained_rows'],
                     'IM_rows': results['im_train.csv']['retained_rows'],
                     'EL_class_balance': results['el_train.csv']['class_balances'][el],
                     'IM_class_balance': results['im_train.csv']['class_balances'][im]}
                  for c, el, im in (('A', 'original', 'original'), ('B', 'low_and_high', 'original'),
                                    ('C', 'original', 'low_and_high'), ('D', 'low_and_high', 'low_and_high'))}
    reports = {'pilot_training_inventory.json': results, 'pilot_development_inventory.json': dev,
        'pilot_leakage_audit.json': {'rule': 'Global canonical nine-mer Hamming distance <=1 across all HLA identifiers',
            'Teacher_fit_source': context.provenance, 'development_unique_peptides': len({p for p, _ in retained}),
            'development_to_fitted_Teacher_violations': 0, 'retained_training_to_development_violations': 0,
            'independent_check': 'Explicit canonical substitution membership; independent of masked-position index',
            'independent_development_neighborhood_size': len(independent), 'study_donor_independence': 'unknown',
            'labels_or_performance_used_for_selection': False, 'opened_archive_members': opened,
            'sealed_payloads_opened': [], 'source_member_identities': identities},
        'pilot_B0801_sanity.json': sanity, 'pilot_training_contract.json': source_contract,
        'pilot_experiment_manifest.json': {'version': VERSION, 'conditions': conditions, 'default_policy': 'low_and_high',
            'policies': POLICIES, 'identical_source_rows_across_conditions': True, 'artifacts': hashes,
            'archive_sha256': context.archive_sha256, 'reference_sha256': config['inputs']['reference']['sha256'],
            'thresholds_hours': {'LOW_strictly_below': 1.0, 'HIGH_at_least': 10.0},
            'teacher_sha256': context.model_sha256, 'review_required_before_corrected_training':
                [w for w in sanity['large_shift_groups_after_purge'] if w['extreme_shift']],
            'status': 'data_prepared_models_not_trained; extreme-shift scientific review pending',
            'development_status': 'Provisional sequence-hard development evaluation; not an independent final external test',
            'original_labels_preserved_in': '*_provenance.csv.gz plus immutable publisher archive',
            'warnings': ['Pseudolabels are exploratory modeling targets, not corrected biological truth',
                         'Equal epochs need not mean equal data exposure; sampler controls deferred']}}
    # JSON round-trip turns Counters/tuples into ordinary deterministic report data.
    reports = json.loads(json.dumps(reports, allow_nan=False))
    for identity in inputs:
        if raw.sha256_file(identity['path']) != identity['sha256']:
            raise ValueError('Original input changed during preparation')
    for name, identity in hashes.items():
        if raw.sha256_file(directory / name) != identity['sha256']:
            raise ValueError('Generated artifact/replay mismatch: ' + name)
    reports['pilot_training_contract.json']['bounded_CSV_smoke_checks'] = {
        name: loader_contract_smoke(directory / name, reference) for name in hashes if name.endswith('.csv')}
    for name, report in reports.items():
        if verify_existing:
            with raw._read_file(directory / 'reports' / name) as stream:
                if stream.read() != raw.json_report(report).encode():
                    raise ValueError('Non-deterministic report: ' + name)
        else:
            raw.write_report(directory / 'reports' / name, report, paths=paths)
    receipt = {'code_commit': manifest['git']['commit_sha'], 'inputs': inputs, 'artifacts': hashes,
        'config_sha256': raw.sha256_file(config_path), 'reports': {n: raw.sha256_file(directory / 'reports' / n) for n in reports},
        'teacher_retrained': False, 'full_dataset_rescored': False, 'models_trained': False,
        'source_data_modified': False, 'opened_archive_members': opened}
    if not verify_existing:
        raw.write_report(directory / 'reports/execution_verification.json', receipt, paths=paths)
    elif readers._json(directory / 'reports/execution_verification.json') != receipt:
        raise ValueError('Execution receipt replay mismatch')
    return {'run': str(directory), 'verified_existing': verify_existing, 'training': results, 'development': dev,
            'artifacts': hashes, 'review_required': sanity['decision_required']}
