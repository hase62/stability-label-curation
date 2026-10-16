"""Positive-first EL stability hypothesis audit; no training or label intervention."""
from array import array
from collections import Counter, defaultdict
import csv
import gzip
import io
import itertools
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import allele_stability_diagnostics as stats
from . import bigmhc_pilot_adapter as adapter
from . import bigmhc_source_audit as source_audit
from . import netmhcstabpan_2016 as raw
from . import pseudolabel_pilot as pilot
from . import scientific_gate0_preflight as readers
from . import stability_teacher as teacher
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/el_positive_stability_analysis_v0.json'
VERSION = 'el_positive_stability_hypothesis_v0'
INPUTS = {'el_scores', 'el_original', 'el_ledger', 'pilot_experiment', 'pilot_inventory', 'pilot_manifest',
          'pilot_receipt', 'registry', 'partition', 'teacher', 'teacher_manifest', 'teacher_metrics',
          'teacher_receipt', 'scoring_manifest', 'scoring_receipt', 'scoring_summary', 'mapping',
          'dataset_code', 'published_metadata'}
JOIN_FIELDS = ('source_file', 'row_index', 'source_line_number', 'source_row_id', 'source_row_sha256',
               'original_peptide', 'original_hla', 'resolved_hla', 'original_label', 'predicted_half_life_hours')
STRATA = ('exact_fit_peptide', 'one_mismatch_fit_only', 'outside_one_mismatch_fit')
REFERENCE_BINS = (0, 1, 2, 5, 10, 20, 50)
UNIDENTIFIABLE = ('The hypothesis that low-stability EL positives become negative in repeated '
                  'experiments cannot be directly tested with the currently available data.')


def load_config(path: str | Path) -> dict[str, Any]:
    config = readers._json(path)
    if (config.get('schema_version') != 1 or config.get('version') != VERSION
            or set(config.get('inputs', {})) != INPUTS
            or config.get('descriptive_reference_only', {}).get('historical_low_lt_hours') != 1.0
            or config['descriptive_reference_only'].get('historical_high_ge_hours') != 10.0):
        raise ValueError('Invalid positive-first analysis configuration')
    for item in config['inputs'].values():
        pilot.registry._relative(item['relative_path'])
        if item['area'] not in {'data', 'runs'} or not pilot._sha(item['sha256']):
            raise ValueError('Invalid analysis input identity')
        name = Path(item['relative_path']).name.lower()
        if any(token in name for token in ('low_only', 'low_and_high', 'overrides', 'el_test', 'im_test', 'iedb', 'manafest')):
            raise ValueError('Corrected/override or sealed input forbidden')
    return config


def resolve_inputs(config: dict, paths: StoragePaths, files: Mapping | None = None):
    overrides = files or {}
    if set(overrides) - INPUTS:
        raise ValueError('Unknown analysis input override')
    resolved, identities = {}, []
    for name, item in config['inputs'].items():
        root = paths.project_data_dir if item['area'] == 'data' else paths.project_runs_dir
        path = Path(overrides.get(name, root / item['relative_path'])).expanduser().absolute()
        if any(token in path.name.lower() for token in ('low_only', 'low_and_high', 'overrides', 'el_test', 'im_test', 'iedb', 'manafest')):
            raise ValueError('Forbidden analysis input')
        if raw.sha256_file(path) != item['sha256']:
            raise ValueError('Analysis input SHA256 mismatch: ' + name)
        resolved[name] = path
        identities.append({'path': str(path), 'sha256': item['sha256']})
    return resolved, identities


def verify_lineage(config: dict, files: dict) -> pilot.Context:
    """Verify frozen Teacher, scoring and preparation parents; never open the ZIP."""
    context = pilot.load_context(config['scoring_lineage'], files)
    for prefix in ('pilot', 'scoring'):
        manifest = pilot.runs.validate_manifest(readers._json(files[prefix + '_manifest']))
        receipt = readers._json(files[prefix + '_receipt'])
        if manifest['git']['commit_sha'] != receipt['code_commit']:
            raise ValueError('Parent code identity mismatch: ' + prefix)
    experiment = readers._json(files['pilot_experiment'])
    receipt = readers._json(files['pilot_receipt'])
    for key, relative in (('el_original', 'processed/el_train_original.csv'),
                          ('el_ledger', 'processed/el_train_provenance.csv.gz')):
        if experiment['artifacts'][relative]['sha256'] != raw.sha256_file(files[key]):
            raise ValueError('Original view/ledger parent identity mismatch')
    for name, key in (('pilot_experiment_manifest.json', 'pilot_experiment'),
                      ('pilot_training_inventory.json', 'pilot_inventory')):
        if receipt['reports'][name] != raw.sha256_file(files[key]):
            raise ValueError('Preparation report receipt mismatch')
    scoring = readers._json(files['scoring_receipt'])
    if (scoring['artifacts'][pilot.OUTPUTS['el_train.csv'][0]]['sha256'] != raw.sha256_file(files['el_scores'])
            or scoring['report_sha256']['pseudolabel_summary.json'] != raw.sha256_file(files['scoring_summary'])):
        raise ValueError('Scoring receipt mismatch')
    if readers._json(files['teacher_receipt'])['report_sha256']['teacher_validation_metrics.json'] != raw.sha256_file(files['teacher_metrics']):
        raise ValueError('Saved Teacher metric receipt mismatch')
    return context


def ledger_rows(path: Path):
    """Read provenance, not historical corrected CSV views or override artifacts."""
    with raw._read_file(path) as stream, gzip.GzipFile(fileobj=stream) as gz, io.TextIOWrapper(gz, encoding='utf-8', newline='') as text:
        rows = csv.DictReader(text, strict=True)
        if rows.fieldnames != adapter.LEDGER:
            raise ValueError('Preparation provenance schema changed')
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Malformed provenance record')
            yield {key: row[key] for key in (*JOIN_FIELDS, 'retained', 'exclusion_reason', 'derived_row_index')}


def original_rows(path: Path):
    with raw._read_file(path) as stream, io.TextIOWrapper(stream, encoding='utf-8', newline='') as text:
        rows = csv.reader(text, strict=True)
        if next(rows, None) != ['mhc', 'pep', 'tgt']:
            raise ValueError('Original EL schema changed; no corrected view accepted')
        for fields in rows:
            if len(fields) != 3 or fields[2] not in {'0', '1'}:
                raise ValueError('Invalid original EL record')
            yield fields


def aligned_scores(scores: Iterable[dict], ledger: Iterable[dict], originals: Iterable[list], context: pilot.Context,
                   audit: dict):
    """Three-way streaming join by immutable source coordinates/hash, never pair only."""
    originals = iter(originals)
    before, retained, removed, reasons, by_hla_removed = Counter(), Counter(), Counter(), Counter(), defaultdict(Counter)
    last = derived = 0
    for score, record in itertools.zip_longest(scores, ledger):
        if score is None or record is None:
            raise ValueError('Score/ledger row count mismatch')
        if any(score[key] != record[key] for key in JOIN_FIELDS):
            raise ValueError('Immutable score/ledger row join mismatch')
        index = int(score['row_index']); hla = score['resolved_hla']; label = score['original_label']
        peptide = score['original_peptide']
        if (score['source_file'] != 'el_train.csv' or index <= last or int(score['source_line_number']) != index + 1
                or score['source_row_id'] != pilot.row_id(context.archive_sha256, 'el_train.csv', index)
                or score['source_row_sha256'] != adapter.source_hash(['mhc', 'pep', 'tgt'], [score['original_hla'], peptide, label])
                or label not in {'0', '1'} or context.mapping.get(score['original_hla']) != hla
                or context.model.document['alleles'].get(hla, {}).get('status') != 'trained'
                or len(peptide) != 9 or any(a not in teacher.ALPHABET for a in peptide)
                or score['teacher_model_sha256'] != context.model_sha256 or score['teacher_version'] != teacher.VERSION
                or score['model_status'] != 'ok'):
            raise ValueError('Unsupported, unordered or unauthenticated EL score')
        last = index
        value = float(score['predicted_half_life_hours'])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Nonfinite/negative Teacher hours')
        if any(score[key] not in {'0', '1'} for key in pilot.EXPOSURES):
            raise ValueError('Unknown saved exposure flag')
        if score['teacher_fit_exact_peptide'] == '1' and score['teacher_fit_within_one_mismatch_peptide'] != '1':
            raise ValueError('Inconsistent exact/near exposure')
        before[label] += 1
        if record['retained'] == '0':
            if record['derived_row_index'] or record['exclusion_reason'] not in {'development_exact_peptide', 'development_one_mismatch_peptide'}:
                raise ValueError('Unexpected exclusion mechanism')
            removed[label] += 1; reasons[record['exclusion_reason']] += 1; by_hla_removed[hla][label] += 1
        elif record['retained'] == '1':
            derived += 1
            if int(record['derived_row_index']) != derived or record['exclusion_reason']:
                raise ValueError('Duplicate/missing prepared-row index')
            original = next(originals, None)
            if original != [hla, peptide, label]:
                raise ValueError('Original training-view identity/label mismatch')
            retained[label] += 1
            yield score
        else:
            raise ValueError('Unknown retention status')
    if next(originals, None) is not None:
        raise ValueError('Original training view has unmatched rows')
    audit.update(pre_purge_rows=sum(before.values()), pre_purge_labels=dict(sorted(before.items())),
                 retained_rows=sum(retained.values()), retained_labels=dict(sorted(retained.items())),
                 removed_rows=sum(removed.values()), removed_labels=dict(sorted(removed.items())),
                 removed_by_reason=dict(reasons), removed_by_HLA={h: dict(c) for h, c in sorted(by_hla_removed.items())},
                 join='Archive identity + member + original row index + raw-row hash + all original fields; contiguous derived index',
                 invalid_predictions=0, ambiguous_joins=0, labels_changed=0)


def describe(values: Iterable[float]) -> dict:
    ordered = sorted(values)
    if any(not math.isfinite(v) or v < 0 for v in ordered):
        raise ValueError('Invalid stability values')
    result = stats.describe(ordered)
    result['quantiles_hours'].update({f'p{p}': stats.quantile(ordered, p) for p in (1, 10, 90, 99)})
    result['predicted_zero_count'] = sum(v == 0 for v in ordered)
    result['historical_lt1_count'] = sum(v < 1 for v in ordered)
    result['historical_ge10_count'] = sum(v >= 10 for v in ordered)
    result['descriptive_bin_counts'] = {
        ('[0,1)' if edge==0 else f'[{edge},{REFERENCE_BINS[i+1]})' if i+1<len(REFERENCE_BINS) else '[50,infinity)'):
        sum(edge<=v and (i+1==len(REFERENCE_BINS) or v<REFERENCE_BINS[i+1]) for v in ordered)
        for i,edge in enumerate(REFERENCE_BINS)}
    result['ECDF_quantile_grid'] = [stats.quantile(ordered, p) for p in range(101)] if ordered else []
    return result


def describe_reported(values: Iterable[float]) -> dict:
    summary=describe(values)
    summary['source_reported_zero_count']=summary.pop('predicted_zero_count')
    return summary


def duplicates(encoded_keys: Mapping[tuple, int]) -> dict:
    # Low two bits retain observed labels; higher bits count source occurrences.
    return {'distinct_peptide_HLA_keys': len(encoded_keys),
            'duplicate_pair_groups': sum((value >> 2) > 1 for value in encoded_keys.values()),
            'extra_pair_records': sum((value >> 2) - 1 for value in encoded_keys.values()),
            'conflicting_label_keys': sum((value & 3) == 3 for value in encoded_keys.values()),
            'interpretation': 'Duplicate keys are repeated source records, not verified assay replicates'}


def summarize(records: Iterable[dict], supported: Iterable[str], measured_pairs: Mapping | None = None):
    values = {hla: {'1': array('d'), '0': array('d')} for hla in sorted(supported)}
    exposed = {hla: {s: {'1': array('d'), '0': array('d')} for s in STRATA} for hla in values}
    key_counts, positive_peptides, flags = {}, defaultdict(set), {'1': Counter(), '0': Counter()}
    measured_positive={'all':[], 'fitting_pair':[], 'heldout_pair':[]}
    for score in records:
        hla, label, peptide = score['resolved_hla'], score['original_label'], score['original_peptide']
        if hla not in values or label not in {'0', '1'}:
            raise ValueError('Unsupported summary HLA/label')
        value = float(score['predicted_half_life_hours'])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Invalid stored score')
        values[hla][label].append(value)
        stratum = ('exact_fit_peptide' if score['teacher_fit_exact_peptide'] == '1' else
                   'one_mismatch_fit_only' if score['teacher_fit_within_one_mismatch_peptide'] == '1' else 'outside_one_mismatch_fit')
        exposed[hla][stratum][label].append(value)
        flags[label].update(key for key in pilot.EXPOSURES if score[key] == '1')
        key = (hla, peptide)
        if measured_pairs is not None:
            if (key in measured_pairs) != (score['DTU_source_exact_pair']=='1'):
                raise ValueError('DTU pair-exposure flag disagrees with registry')
            if label=='1' and key in measured_pairs:
                pair=(measured_pairs[key],value)
                measured_positive['all'].append(pair)
                measured_positive['fitting_pair' if score['teacher_fit_exact_pair']=='1' else 'heldout_pair'].append(pair)
        key_counts[key] = ((key_counts.get(key, 0) >> 2) + 1) * 4 | (key_counts.get(key, 0) & 3) | (1 << int(label))
        if label == '1':
            positive_peptides[peptide].add(hla)
    # Complete the positive-only summaries before the decoy comparison.
    positive = {hla: describe(v['1']) for hla, v in values.items()}
    pooled_positive = describe(itertools.chain.from_iterable(v['1'] for v in values.values()))
    negative = {hla: describe(v['0']) for hla, v in values.items()}
    pooled_negative = describe(itertools.chain.from_iterable(v['0'] for v in values.values()))
    comparisons = {}
    for hla, v in values.items():
        auc = stats.roc_auc(v['1'], v['0'])
        comparisons[hla] = {'original_EL_label_association': auc,
            'by_Teacher_fitting_exposure': {s: stats.roc_auc(exposed[hla][s]['1'], exposed[hla][s]['0']) for s in STRATA},
            'pairwise_rank_error_half_credit_ties': 1-auc['ROC_AUC'] if auc['ROC_AUC'] is not None else None}
    repeat = duplicates(key_counts)
    repeat.update(positive_unique_peptides=len(positive_peptides),
        positive_peptides_seen_across_multiple_HLA=sum(len(h) > 1 for h in positive_peptides.values()),
        positive_pair_records=sum(len(h) for h in positive_peptides.values()))
    return {'positive': {'overall': pooled_positive, 'by_HLA': positive,
                'by_Teacher_fit_exposure': {s:describe(itertools.chain.from_iterable(exposed[h][s]['1'] for h in exposed)) for s in STRATA},
                'matched_DTU_key_measurements':{
                    'by_source_partition':{group:{'reported_hours':describe_reported(p[0] for p in pairs),
                        'predicted_hours':describe(p[1] for p in pairs),
                        'kinetic_prediction_metrics':teacher.metrics([p[0] for p in pairs],[p[1] for p in pairs])}
                        for group,pairs in measured_positive.items()},
                    'interpretation':'Exact peptide-HLA key correspondence to DTU measurements, not the same physical assay or repeated EL detection; source zero semantics unresolved'}},
            'secondary_negative': {'overall': pooled_negative, 'by_HLA': negative, 'label_origin': 'Constructed decoys; not verified nonpresentation'},
            'comparison': comparisons, 'duplicates': repeat,
            'fitting_exposure': {label: dict(sorted(c.items())) for label, c in flags.items()}}


def teacher_context(context, registry_path: Path, partition: dict, saved_metrics: dict) -> dict:
    """Audit existing fitted model on original held-out DTU rows; no fitting/EL rescoring."""
    population, _ = teacher.load_population(registry_path, context.model.document['config'])
    teacher.verify_partition(population, partition)
    assigned = {row['observation_id']: row['partition'] for row in partition['assignments']}
    fitting, validation, validation_pairs = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in population:
        hla = row.original_allele
        if context.model.document['alleles'][hla]['status'] != 'trained':
            continue
        truth = float(pilot.registry.decimal_value(row.original_measurement_text))
        if assigned[row.observation_id] == 'train':
            fitting[hla].append(truth)
        else:
            prediction = context.model.predict_stability(row.original_peptide, hla)['predicted_half_life_hours']
            validation[hla].append(truth); validation_pairs[hla].append((truth, prediction))
    all_pairs = [pair for pairs in validation_pairs.values() for pair in pairs]
    actual = teacher.metrics([p[0] for p in all_pairs], [p[1] for p in all_pairs])
    for name, value in actual.items():
        expected = saved_metrics['results']['overall']['teacher'][name]
        if isinstance(value, (int, float)) and (expected is None or not math.isclose(value, expected, rel_tol=1e-10, abs_tol=1e-10)):
            raise ValueError('Frozen Teacher held-out replay disagrees with saved metric: ' + name)
    def errors(pairs):
        truth, pred = [p[0] for p in pairs], [p[1] for p in pairs]
        return {**teacher.metrics(truth, pred), 'mean_prediction_minus_reported_hours':
                math.fsum(p - t for t, p in pairs)/len(pairs) if pairs else None,
                'median_reported_hours': stats.quantile(sorted(truth), 50),
                'median_predicted_hours': stats.quantile(sorted(pred), 50)}
    def regions(pairs):
        return {'all': errors(pairs), 'source_reported_zero': errors([p for p in pairs if p[0] == 0]),
                'reported_positive_lt_historical_1h': errors([p for p in pairs if 0 < p[0] < 1]),
                'prediction_lt_historical_1h': errors([p for p in pairs if p[1] < 1])}
    by_hla = {}
    for hla in stats.supported_alleles(context):
        train, valid = fitting[hla], validation[hla]
        by_hla[hla] = {'fitting_hours': describe_reported(train), 'validation_reported_hours': describe_reported(valid),
            'DTU_reported_hours':describe_reported([*train,*valid]),
            'saved_validation_metrics': saved_metrics['results'].get(hla, {}).get('teacher', {}),
            'heldout_error_regions': regions(validation_pairs[hla]),
            'validation_sparse_below10': len(valid) < 10,
            'absolute_calibration_for_EL': 'not_established', 'repeat_detection_calibration': 'unavailable'}
    return {'model_sha256': context.model_sha256, 'units': 'hours', 'higher_is_more_stable': True,
        'target': 'log1p(reported hours)', 'prediction': 'expm1(max(0,linear_log_prediction))',
        'zero_prediction_meaning': 'Nonnegative model floor; not measured instantaneous dissociation',
        'trained_models': len(by_hla), 'unsupported_models': {h: m['status'] for h, m in context.model.document['alleles'].items() if m['status'] != 'trained'},
        'saved_overall_validation': saved_metrics['results']['overall'], 'heldout_regions': regions(all_pairs), 'by_HLA': by_hla,
        'saved_metrics_reproduced': True, 'new_fitting_performed': False, 'EL_scores_recomputed': False,
        'limitations': ['Internal sequence-separated DTU validation, not external EL repeat detection',
                       'No calibrated prediction intervals or per-row uncertainty', 'Allele-specific Ridge intercepts/scales and no sequence interactions',
                       'Reported DTU zero mechanisms unresolved; source selection and EL domain shift remain',
                       'Low-range errors condition on recorded DTU values or a historical score region, not on observed EL false positives']}


def replicate_evidence(duplicate_report: dict, evidence: list[dict], metadata: Any) -> dict:
    return {'status': 'unidentifiable_from_available_release', 'statement': UNIDENTIFIABLE,
        'original_EL_columns': ['mhc', 'pep', 'tgt'], 'duplicate_inventory': duplicate_report,
        'available_lineage': ['Publisher member and source row index', 'Original row hash', 'Validated HLA', 'Frozen Teacher identity'],
        'missing': ['Study/publication-to-row linkage', 'Sample and cell-line identity', 'Technical and biological replicate IDs',
                    'Comparable repeated detection opportunities, including nondetections', 'Abundance/intensity and acquisition-depth/QC metadata',
                    'Proteomics identification/FDR evidence', 'Processing and detection conditions; HLA expression'],
        'underlying_studies': 'May contain replicates; whether a released pair is single-run, aggregated or repeated is not recoverable here',
        'source_stratified_stability_analysis': 'Unavailable: member identity el_train.csv does not identify the original study',
        'repeat_detection_probability': None, 'stability_repeat_detection_association': None,
        'metadata_scope': 'Publisher metadata is artifact-level; no per-observation experiment/run relation',
        'publisher_artifact_names': sorted(item['filename'] for item in metadata) if isinstance(metadata, list) else [],
        'evidence': evidence, 'additional_scientific_payloads_acquired': False}


def native_exposure(positives: int, negatives: int, batch_size: int = 16, negfrac: float = .99) -> dict:
    """Static pinned makebats arithmetic for one nine-mer group, not a training run."""
    if min(positives, negatives) < 0 or batch_size < 1 or not 0 < negfrac < 1:
        raise ValueError('Invalid native sampler count')
    groups = math.ceil((positives + negatives)/batch_size)
    pstep = math.ceil(positives/groups) if groups else 0
    nstep = int(min(math.ceil(negatives/groups), pstep/(1-negfrac)-pstep)) if groups else 0
    batches = math.ceil(positives/pstep) if pstep else 0
    return {'EL_optimizer_steps_if_all_native_batches_processed': batches, 'positive_rows_consumed': positives,
            'negative_rows_consumed': min(negatives, batches*nstep), 'negatives_omitted': max(0, negatives-batches*nstep),
            'positive_anchors_per_batch': pstep, 'nominal_negatives_per_batch': nstep,
            'not_a_matched_counterfactual': True}


def intervention_context(result: dict) -> dict:
    p, n = result['positive']['overall']['n'], result['secondary_negative']['overall']['n']
    low = result['positive']['overall']['historical_lt1_count']
    return {'selected_intervention': None, 'selected_cutoff': None, 'decision_status': 'scientific_approval_required',
        'historical_reference_only': 'Counts below the existing unapproved 1h reference illustrate exposure consequences; not proposed row selection',
        'baseline_original': native_exposure(p, n),
        'hypothetical_remove_historical_lt1_positive': native_exposure(p-low, n),
        'hypothetical_flip_historical_lt1_positive': native_exposure(p-low, n+low),
        'historical_reference_positive_count': low,
        'A_preserve': 'Maintains observed labels and authentic sampler; no evidence yet requires an intervention.',
        'B_remove': 'Assumes low scores identify less useful supervision; discards real MS observations and changes anchors/steps/negative exposure.',
        'C_reweight': 'Assumes lower stability should reduce positive gradient; no calibrated loss-weight interpretation is available. Not automatically preferable.',
        'D_soft_targets': 'Requires calibrated probabilities for an explicitly defined outcome. Hours/ranks are not presentation or repeat-detection probabilities.',
        'E_flip': 'Asserts opposite training target for observed positives; prediction discordance alone does not support this.',
        'next_experiment': {'type': 'blinded_repeat_detection_validation_before_curation',
            'data_gate': 'Obtain one small authenticated peptide-by-run panel with comparable detection opportunities and replicate hierarchy; no download authorized here',
            'outcome': 'For peptides positive in a prespecified index run, detection fraction in reserved comparable repeat runs; nondetection remains a detection event, not proof of absence',
            'predictor': 'Frozen Teacher score modeled continuously within HLA, with uncertainty/support and exposure checks; no new binary cutoff',
            'controls': 'HLA/study and available abundance/acquisition/QC covariates; distinguish technical from biological repeats; within-HLA score permutation; out-of-source sensitivity',
            'falsification': 'No lower repeat detection with lower scores, reversal, effect explained by abundance/depth or poor Teacher reliability; inadequate precision remains inconclusive',
            'training_experiment': 'No A/B/C/D intervention selected. Any later training trial needs separately approved outcome, effect size and intervention rule'},
        'future_training_contract': ['No unsupported-HLA substitution; original records/labels remain preserved',
            'Same EL/IM source identities and frozen IM labels; changes restricted to approved EL intervention',
            'Matched initial tensors, architecture, seed, IM procedure, evaluation and prespecified analysis',
            'Log actual positive/negative gradient contributions, anchors, consumed IDs, step counts and RNG draws',
            'Matched random or score-permuted intervention within HLA/support; source strata if recovered',
            'Rerun baseline and controls if schedule/sampler/exposure changes; Task2.10 is not automatically exactly matched',
            'No development-IM-guided threshold/weight search; predeclare one test and falsification before new outcomes']}


def inspect(*, config_path: str | Path, paths: StoragePaths | None = None, files: Mapping | None = None):
    paths = paths or resolve_paths()
    config = load_config(config_path); resolved, inputs = resolve_inputs(config, paths, files)
    context = verify_lineage(config, resolved)
    audit = {}
    records = aligned_scores(adapter._csv_rows(resolved['el_scores']), ledger_rows(resolved['el_ledger']),
                             original_rows(resolved['el_original']), context, audit)
    population,_=teacher.load_population(resolved['registry'],context.model.document['config'])
    measured={(row.original_allele,row.original_peptide):float(pilot.registry.decimal_value(row.original_measurement_text)) for row in population}
    result = summarize(records, stats.supported_alleles(context),measured)
    expected = config['expected']
    if (audit['pre_purge_rows'] != expected['pre_purge'] or audit['retained_rows'] != expected['retained']
            or audit['retained_labels'] != expected['retained_labels'] or audit['removed_rows'] != expected['removed']):
        raise ValueError('Actual EL population differs from approved expectations')
    inventory = readers._json(resolved['pilot_inventory'])['el_train.csv']
    for hla, group in inventory['by_HLA'].items():
        for label, report in (('1', result['positive']['by_HLA'][hla]), ('0', result['secondary_negative']['by_HLA'][hla])):
            if report['n'] != group['original'].get(label, 0):
                raise ValueError('Retained per-HLA counts disagree with preparation evidence')
    scored = readers._json(resolved['scoring_summary'])['members']['el_train.csv']
    if audit['pre_purge_labels'] != scored['eligible_original_label_counts']:
        raise ValueError('Pre-purge scoring count mismatch')
    reliability = teacher_context(context, resolved['registry'], readers._json(resolved['partition']), readers._json(resolved['teacher_metrics']))
    audit.update(valid_positive_predictions=result['positive']['overall']['n'], positive_prediction_coverage=1.0,
                 supported_HLA_models=len(stats.supported_alleles(context)), observed_EL_HLA=sum(v['n'] > 0 for v in result['positive']['by_HLA'].values()),
                 score_units='hours', primary_scope='Original EL positives first; negatives are secondary decoy context',
                 missing_source_study_linkage=True, parent_runs={'scores':'task-2_4-el-im-pseudolabel-pilot','cohort':'task-2_5-bigmhc-pilot-preparation','teacher':'task-2_3-first-stability-teacher'})
    reports = {'el_positive_stability.json': result['positive'], 'el_negative_context.json': result['secondary_negative'],
        'el_label_comparison.json': {'by_HLA': result['comparison'], 'fitting_exposure': result['fitting_exposure'],
            'interpretation':'Original training-label association, not repeat detection or independent validation; decoys are not measured absences'},
        'teacher_coverage_alignment.json': audit, 'teacher_reliability.json': reliability,
        'replicate_measurement_evidence.json': replicate_evidence(result['duplicates'], config['evidence_register'], readers._json(resolved['published_metadata'])),
        'curation_options_and_exposure.json': {**intervention_context(result),
            'baseline_A_reference':config['baseline_A_reference'], 'Task2_10_execution_artifacts_read':False}}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Immutable input changed during analysis')
    return reports, inputs


def table_text(distributions: dict, reliability: dict) -> str:
    out = io.StringIO(newline='')
    fields = ['HLA', 'n', 'p5_hours', 'p25_hours', 'median_hours', 'p75_hours', 'p95_hours', 'IQR_hours',
              'predicted_zero_count', 'historical_lt1_count', 'historical_lt1_fraction', 'historical_ge10_count',
              'Teacher_validation_n', 'Teacher_validation_Spearman', 'Teacher_validation_sparse_below10']
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n'); writer.writeheader()
    for hla, group in distributions['by_HLA'].items():
        context = reliability['by_HLA'][hla]; q = group['quantiles_hours']; saved = context['saved_validation_metrics']
        writer.writerow({'HLA': hla, 'n':group['n'], 'p5_hours':q['p5'], 'p25_hours':q['p25'], 'median_hours':q['p50'],
            'p75_hours':q['p75'], 'p95_hours':q['p95'], 'IQR_hours':group['IQR_hours'],
            'predicted_zero_count':group['predicted_zero_count'], 'historical_lt1_count':group['historical_lt1_count'],
            'historical_lt1_fraction':group['historical_LOW_lt1_fraction'], 'historical_ge10_count':group['historical_ge10_count'],
            'Teacher_validation_n':saved.get('n',0), 'Teacher_validation_Spearman':saved.get('spearman_hours'),
            'Teacher_validation_sparse_below10':context['validation_sparse_below10']})
    return out.getvalue()


def render_figures(reports: dict) -> dict[str, bytes]:
    """Standalone scientific SVGs; plotting library is optional and imported lazily."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    matplotlib.rcParams.update({'svg.hashsalt':VERSION, 'font.family':'DejaVu Sans', 'font.size':9})
    positive, negative = reports['el_positive_stability.json'], reports['el_negative_context.json']
    reliability = reports['teacher_reliability.json']['by_HLA']; comparison = reports['el_label_comparison.json']['by_HLA']
    figures = {}
    def finish(name, fig):
        fig.tight_layout(); stream = io.BytesIO()
        fig.savefig(stream, format='svg', metadata={'Date':None, 'Creator':VERSION})
        figures[name] = stream.getvalue()
        png=io.BytesIO();fig.savefig(png,format='png',dpi=130,metadata={'Software':VERSION})
        figures[name.removesuffix('.svg')+'.png']=png.getvalue();plt.close(fig)
    def axis(ax):
        right=max(ax.dataLim.x1,math.log1p(1))
        ticks = [t for t in (0,.5,1,2,5,10,20,50,100) if math.log1p(t)<=right*1.04]
        ax.set_xticks(np.log1p(ticks), [str(t) for t in ticks]);ax.set_xlim(-.02*right,right*1.04)
        ax.set_xlabel('Predicted half-life (hours; log1p display spacing)')
        ax.grid(axis='x', alpha=.2)
    def ecdf(ax, group, label, **kwargs):
        if group['n']:
            ax.plot(np.log1p(group['ECDF_quantile_grid']), np.linspace(0,1,101), label=label, **kwargs)
    observed = [(h,g) for h,g in positive['by_HLA'].items() if g['n']]
    fig, ax = plt.subplots(figsize=(12, max(6,len(observed)*.29)))
    labels=[]
    for y,(hla,g) in enumerate(observed):
        q=g['quantiles_hours']; r=reliability[hla]; saved=r['saved_validation_metrics']
        color='#b0b0b0' if r['validation_sparse_below10'] or g['n']<10 else '#0072b2'
        if hla=='HLA-B*08:01':color='#d55e00'
        ax.hlines(y,math.log1p(q['p5']),math.log1p(q['p95']),color=color)
        ax.hlines(y,math.log1p(q['p25']),math.log1p(q['p75']),color=color,linewidth=6)
        ax.plot(math.log1p(q['p50']),y,'|',color='black',markersize=8)
        rho=saved.get('spearman_hours');rho='NA' if rho is None else f'{rho:.2f}'
        labels.append(f"{hla}   EL+ n={g['n']}; val n={saved.get('n',0)}, ρ={rho}")
    ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis();axis(ax)
    ax.set_title('Original EL-positive predictions by HLA\nLines: p5–p95; thick bars: IQR; tick: median. Gray: <10 EL positives or DTU validation rows. No curation rule.')
    finish('positive_per_hla_distributions.svg',fig)
    fig, axes=plt.subplots(1,2,figsize=(12,4))
    ecdf(axes[0],positive['overall'],f"All EL positives (n={positive['overall']['n']})",color='#0072b2')
    axes[0].set_title('Primary EL-positive score distribution')
    hla='HLA-B*08:01'
    ecdf(axes[1],positive['by_HLA'][hla],'EL-positive predictions',color='#d55e00')
    ecdf(axes[1],reliability[hla]['fitting_hours'],'DTU fitting: reported hours',color='#009e73')
    ecdf(axes[1],reliability[hla]['validation_reported_hours'],'DTU validation: reported hours',color='#0072b2')
    axes[1].set_title('B*08:01: source scale versus predicted EL hours')
    for ax in axes:axis(ax);ax.set_ylabel('Cumulative fraction (quantile-grid display)');ax.legend(fontsize=8)
    axes[1].set_xlabel('Reported or predicted half-life (hours; log1p display spacing)')
    finish('positive_cdf_and_B0801_context.svg',fig)
    fig, axes=plt.subplots(2,2,figsize=(12,8))
    for ax,hla in zip(axes.flat,('HLA-A*02:01','HLA-B*07:02','HLA-B*08:01','HLA-B*35:08')):
        ecdf(ax,positive['by_HLA'][hla],f"MS EL+ (n={positive['by_HLA'][hla]['n']})",color='#0072b2')
        ecdf(ax,negative['by_HLA'][hla],f"Decoy EL0 (n={negative['by_HLA'][hla]['n']})",color='#d55e00')
        auc=comparison[hla]['original_EL_label_association']['ROC_AUC']
        ax.set_title(hla+f' — training-label association AUC {auc:.3f}' if auc is not None else hla+' — insufficient classes')
        axis(ax);ax.set_ylabel('Cumulative fraction');ax.legend(fontsize=8)
    fig.suptitle('Secondary decoy comparison: not repeat-detection or independent predictive performance')
    finish('secondary_decoy_comparison.svg',fig)
    return figures


def execute(*, config_path: str | Path, out: str | Path | None = None, paths: StoragePaths | None = None,
            files: Mapping | None = None, verify_existing: bool = False, figures: bool = True):
    paths = paths or resolve_paths()
    reports, inputs = inspect(config_path=config_path, paths=paths, files=files)
    if out is None:
        if verify_existing:
            raise ValueError('Replay requires an explicit existing run')
        return reports
    directory, manifest = teacher._run(out, paths)
    if (manifest['configuration']['file'] != {'path':str(Path(config_path).absolute()),'sha256':raw.sha256_file(config_path)}
            or any(item not in manifest['data_provenance']['input_artifacts'] for item in inputs)):
        raise ValueError('Run must record actual analysis inputs and configuration')
    content = {f'reports/{name}':raw.json_report(doc).encode() for name,doc in reports.items()}
    for label, name in (('el_positive_stability.json','positive_per_hla.csv'),('el_negative_context.json','secondary_negative_per_hla.csv')):
        content['reports/'+name] = table_text(reports[label], reports['teacher_reliability.json']).encode()
    if figures:
        content.update({'reports/'+name:blob for name,blob in render_figures(reports).items()})
    import hashlib
    hashes = {name:hashlib.sha256(blob).hexdigest() for name,blob in content.items()}
    if verify_existing:
        receipt=readers._json(directory/'reports/execution_verification.json')
        if receipt['outputs']!=hashes or any(raw.sha256_file(directory/name)!=sha for name,sha in hashes.items()):
            raise ValueError('Offline analysis outputs differ')
        return {'offline_deterministic_reproduction':True, 'outputs_verified':len(hashes)}
    for name,blob in content.items():
        if name.endswith('.png'):
            source_audit._publish_bytes(directory/'reports',Path(name).name,blob)
        else:
            raw.write_text_report(directory/name,blob.decode(),paths=paths)
    import importlib.metadata, sys
    versions={name:importlib.metadata.version(name) for name in ('matplotlib','numpy')} if figures else {}
    raw.write_report(directory/'reports/execution_verification.json',{'code_commit':manifest['git']['commit_sha'],
        'inputs':inputs,'outputs':hashes,'config_sha256':raw.sha256_file(config_path),'runtime':{'python':sys.version,'plotting_versions':versions},
        'source_inputs_unchanged':True,'source_labels_modified':False,'Teacher_refit':False,'BigMHC_training':False,
        'sealed_payloads_opened':[],'corrected_training_views_opened':[],'IM_development_outcomes_used':False,
        'EL_scores_recomputed':False,'repeat_detection_identifiable':False,'intervention_selected':False},paths=paths)
    return {'run':str(directory),'outputs':hashes,'alignment':reports['teacher_coverage_alignment.json']}
