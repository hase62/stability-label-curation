"""Training-label associations from frozen scores; no correction or model fitting."""
from array import array
from collections import Counter, defaultdict
from decimal import Decimal
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import bigmhc_pilot_adapter as adapter
from . import pseudolabel_pilot as pilot
from . import stability_teacher as teacher
from . import dtu2016_source_audit as dtu
from . import netmhcstabpan_2016 as raw
from . import scientific_gate0_preflight as readers
from . import run_manifest as runs
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/allele_stability_diagnostics_v0.json'
VERSION = 'allele_stability_diagnostics_v0'
STRATA = ('all', 'exact_fit_peptide', 'one_mismatch_fit_only', 'outside_one_mismatch_fit')
STATUS = 'scientifically_unapproved_for_corrected_BigMHC_training'
INPUTS = {'teacher', 'teacher_manifest', 'teacher_receipt', 'partition', 'registry', 'mapping',
          'teacher_metrics', 'el_scores', 'im_scores', 'scoring_summary', 'scoring_receipt',
          'pilot_manifest', 'pilot_receipt', 'pilot_inventory', 'pilot_experiment', 'pilot_B0801'}


def load_config(path: str | Path) -> dict[str, Any]:
    config = readers._json(path)
    if (config.get('schema_version') != 1 or config.get('version') != VERSION
            or config.get('corrected_training_status') != STATUS
            or set(config.get('inputs', {})) != INPUTS
            or type(config.get('auc_minimum_per_class')) is not int or config['auc_minimum_per_class'] < 1):
        raise ValueError('Invalid diagnostic configuration or scientific status')
    for item in config['inputs'].values():
        pilot.registry._relative(item['relative_path'])
        if item['area'] not in {'runs', 'data'} or not pilot._sha(item['sha256']):
            raise ValueError('Invalid portable input checksum')
    return config


def resolve_inputs(config, paths: StoragePaths, files: Mapping | None = None):
    overrides = files or {}
    if set(overrides) - set(config['inputs']):
        raise ValueError('Unknown diagnostic input override')
    resolved, identities = {}, []
    for name, item in config['inputs'].items():
        root = paths.project_runs_dir if item['area'] == 'runs' else paths.project_data_dir
        path = Path(overrides.get(name, root / item['relative_path'])).expanduser().absolute()
        if raw.sha256_file(path) != item['sha256']:
            raise ValueError('Diagnostic input SHA256 mismatch: ' + name)
        resolved[name] = path
        identities.append({'path': str(path), 'sha256': item['sha256']})
    return resolved, identities


def quantile(ordered: Sequence[float], percent: int) -> float | None:
    """Sorted finite values, Type 7 empirical quantile; no fitted distribution."""
    if not 0 <= percent <= 100:
        raise ValueError('Invalid quantile percentage')
    if not ordered:
        return None
    index, remainder = divmod((len(ordered)-1)*percent, 100)
    return ordered[index] if not remainder else ordered[index] + (ordered[index+1]-ordered[index])*remainder/100


def describe(ordered: Sequence[float]) -> dict[str, Any]:
    n = len(ordered)
    return {'n': n, 'minimum_hours': ordered[0] if n else None, 'maximum_hours': ordered[-1] if n else None,
        'quantiles_hours': {f'p{p}': quantile(ordered, p) for p in (5, 25, 50, 75, 95)},
        'IQR_hours': quantile(ordered, 75)-quantile(ordered, 25) if n else None,
        'historical_LOW_lt1_fraction': sum(v < 1 for v in ordered)/n if n else None,
        'historical_HIGH_ge10_fraction': sum(v >= 10 for v in ordered)/n if n else None,
        'strictly_gt10_fraction': sum(v > 10 for v in ordered)/n if n else None}


def roc_auc(positive: Sequence[float], negative: Sequence[float], minimum_per_class: int = 5) -> dict[str, Any]:
    """Mann–Whitney concordance; ties receive half credit; higher predicts original label1."""
    if minimum_per_class < 1 or any(not math.isfinite(v) for group in (positive,negative) for v in group):
        raise ValueError('Invalid AUC input')
    p, n = len(positive), len(negative)
    reason = 'missing_class' if not p or not n else 'insufficient_class_support' if min(p,n) < minimum_per_class else None
    result = {'positive_rows': p, 'negative_rows': n, 'ROC_AUC': None,
              'status': reason or 'descriptive_training_association', 'minimum_per_class': minimum_per_class}
    if reason:
        return result
    positives, negatives = sorted(positive), sorted(negative)
    left = right = i = 0; concordance = 0.0
    while i < p:
        value = positives[i]; end = i+1
        while end < p and positives[end] == value:
            end += 1
        while left < n and negatives[left] < value:
            left += 1
        right = left
        while right < n and negatives[right] == value:
            right += 1
        concordance += (end-i)*(left + (right-left)/2)
        left = right; i = end
    result['ROC_AUC'] = concordance / (p*n)
    return result


def supported_alleles(context: pilot.Context) -> list[str]:
    return sorted(h for h, m in context.model.document['alleles'].items() if m['status'] == 'trained')


def summarize_scores(records, member: str, context: pilot.Context, minimum_per_class: int = 5):
    if member not in pilot.MEMBERS:
        raise ValueError('Only authenticated training score members are allowed')
    supported = supported_alleles(context)
    values = {h: {s: {'0': array('d'), '1': array('d')} for s in STRATA} for h in supported}
    counts = Counter(); labels = Counter(); actions = defaultdict(Counter); exposure = Counter()
    last = 0
    for row in records:
        hla = row['resolved_hla']; label = row['original_label']; index = int(row['row_index'])
        if (hla not in values or context.mapping.get(row['original_hla']) != hla or label not in {'0','1'}
                or row['source_file'] != member or index <= last
                or row['source_row_id'] != pilot.row_id(context.archive_sha256, member, index)
                or not pilot._sha(row['source_row_sha256']) or row['rule_version'] != pilot.VERSION
                or row['teacher_model_sha256'] != context.model_sha256 or row['teacher_version'] != teacher.VERSION
                or row['model_status'] != 'ok' or len(row['original_peptide']) != 9
                or any(a not in teacher.ALPHABET for a in row['original_peptide'])):
            raise ValueError('Changed, unsupported or unauthenticated score row')
        last = index
        hours = float(row['predicted_half_life_hours'])
        if not math.isfinite(hours) or hours < 0:
            raise ValueError('Invalid saved prediction')
        if any(row[key] not in {'0','1'} for key in pilot.EXPOSURES):
            raise ValueError('Invalid frozen exposure flags')
        exact = row['teacher_fit_exact_peptide'] == '1'
        near = row['teacher_fit_within_one_mismatch_peptide'] == '1'
        if exact and not near:
            raise ValueError('Inconsistent exact/near Teacher exposure')
        stratum = 'exact_fit_peptide' if exact else 'one_mismatch_fit_only' if near else 'outside_one_mismatch_fit'
        values[hla]['all'][label].append(hours); values[hla][stratum][label].append(hours)
        if row['candidate_action'] not in {'no_change','low_positive_to_negative','high_negative_to_positive'}:
            raise ValueError('Unknown historical action')
        if pilot.category_and_action(label,hours) != (row['stability_category'],row['candidate_action'],row['proposed_pseudolabel']):
            raise ValueError('Changed historical candidate semantics')
        actions[hla][row['candidate_action']] += 1; counts[hla] += 1; labels[label] += 1
        exposure.update(k for k in pilot.EXPOSURES if row[k] == '1')
    distributions, associations = {}, {}
    for hla in supported:
        distributions[hla] = {label: describe(sorted(values[hla]['all'][label])) for label in ('0','1')}
        associations[hla] = {s: roc_auc(values[hla][s]['1'], values[hla][s]['0'], minimum_per_class) for s in STRATA}
    return distributions, associations, {'rows':sum(counts.values()), 'labels':dict(labels),
        'by_HLA':dict(counts), 'historical_actions':{h:dict(c) for h,c in actions.items()}, 'exposure':dict(exposure)}


def dtu_context(population, context, metrics, partition):
    groups = defaultdict(list)
    assignment = {r['observation_id']:r['partition'] for r in partition['assignments']}
    for row in population:
        groups[row.original_allele].append(row)
    result = {}
    for hla in supported_alleles(context):
        rows = groups[hla]; values = [Decimal(r.original_measurement_text) for r in rows]
        saved = metrics['results'].get(hla, {}).get('teacher', {})
        result[hla] = {'ordinary_DTU_observations':len(rows), 'reported_zero_count':sum(v == 0 for v in values),
            'reported_zero_fraction':sum(v == 0 for v in values)/len(values) if values else None,
            'measured_quantiles_hours_decimal': {f'p{p}':str(dtu.quantile(values,p)) if values else None for p in (0,5,25,50,75,95,100)},
            'actual_fitting_observations':sum(assignment[r.observation_id] == 'train' for r in rows),
            'saved_validation_n':saved.get('n',0), 'saved_validation_Spearman':saved.get('spearman_hours'),
            'saved_validation_MAE_hours':saved.get('mae_hours'), 'validation_sparse_below10': saved.get('n',0) < 10}
    return {'by_HLA':result, 'ordinary_DTU_population_rows':len(population),
        'unsupported_models':{h:m['status'] for h,m in sorted(context.model.document['alleles'].items()) if m['status'] != 'trained'},
        'zero_semantics':'Source-reported zero; individual measurement/reporting origin unresolved',
        'row_origin':'Published raw stability-table rows; no individually verified underlying assay trace',
        'quantile_convention':dtu.QUANTILE_CONVENTION, 'validation_metrics':'Previously saved Task2.3 held-out metrics; no new model evaluation'}


def correction_shifts(summary, inventory, experiment):
    result = {}
    for member in pilot.MEMBERS:
        before = summary['members'][member]['by_original_HLA']
        after = inventory[member]['by_HLA']
        result[member] = {'Task24_scored_population':{}, 'Task25_retained_population':{}}
        for hla, group in sorted(before.items()):
            if not group['teacher_eligible_rows']:
                continue
            labels = group['eligible_original_label_counts']; changes = group['candidate_counts']
            low, high = changes['low_positive_to_negative'], changes['high_negative_to_positive']
            result[member]['Task24_scored_population'][hla] = _shift(labels,low,high)
        for hla, group in sorted(after.items()):
            low = group['actions'].get('low_positive_to_negative',0); high=group['actions'].get('high_negative_to_positive',0)
            shift = _shift(group['original'],low,high)
            if any(shift['proposed_LOW_HIGH'][label] != group['low_and_high'].get(label,0) for label in ('0','1')):
                raise ValueError('Historical proposed class counts disagree')
            result[member]['Task25_retained_population'][hla] = shift
    historical = {name:identity for name,identity in experiment['artifacts'].items()
                  if name.endswith(('_low_only.csv','_low_and_high.csv'))}
    return {'training_use_status':STATUS, 'supersedes':'Task2.5 pending-review status; historical input files remain byte-for-byte unchanged',
        'historical_corrected_views':{name:{**identity,'training_use_status':STATUS} for name,identity in historical.items()},
        'conditions_B_C_D_corrected_training':'not_approved', 'new_threshold_or_method_selected':False,
        'by_member':result}


def _shift(labels, low, high):
    positive, negative = labels.get('1',0), labels.get('0',0)
    if not 0 <= low <= positive or not 0 <= high <= negative:
        raise ValueError('Impossible historical candidate counts')
    return {'original':{'1':positive,'0':negative},'positive_to_negative':low,'negative_to_positive':high,
        'proposed_LOW_HIGH':{'1':positive-low+high,'0':negative+low-high},
        'fraction_original_positives_changed':low/positive if positive else None,
        'all_original_positives_changed':bool(positive and low == positive),
        'majority_original_positives_changed':bool(positive and low > positive/2)}


def strategy_assessment():
    return {'training_use_status':STATUS, 'selected_method':None, 'selected_cutoff':None, 'decision_status':'scientific_review_required',
        'A_allele_relative':{'assumption':'Within-allele stability ranks carry relevant biological information; a common absolute scale is unnecessary',
            'reference':'Prespecified allele-specific DTU or representative deployment distribution, with support and out-of-domain calibration',
            'missing_evidence':'Calibration, robustness, measurement origin and evidence linking relative kinetic stability to presentation and T-cell response'},
        'B_remove_or_downweight':{'assumption':'Stability discordance identifies less useful supervision; withholding or reducing its influence improves learning',
            'reference':'Task-specific discordance/confidence reference and prespecified matched-control design',
            'missing_evidence':'Whether removed examples are noisy rather than valid low-stability biology; selection bias and sensitivity to allele/sample support'},
        'C_binary_flip':{'assumption':'Teacher disagreement supports the opposite binary target rather than uncertainty or another biological mechanism',
            'reference':'Task- and allele-aware calibration against appropriate original outcomes and Teacher uncertainty',
            'missing_evidence':'Directional error probabilities, domain-shift robustness and evidence for replacing the original supervised target'},
        'EL_to_IM_limit':'Distinguishing observed EL ligands from constructed decoys does not establish T-cell response discrimination; experimental IM negatives and EL decoys differ in provenance and selection',
        'interpretation':'AUCs are descriptive training-set associations; no association or discordance proves original experimental labels wrong; stability does not measure TCR recognition',
        'causal_explanations':'Allele scale, Teacher error, source selection and biology remain potentially overlapping explanations; no causal attribution established'}


def inspect(*, config_path: str | Path, paths: StoragePaths | None = None, files: Mapping | None = None):
    paths = paths or resolve_paths(); config = load_config(config_path)
    resolved, inputs = resolve_inputs(config,paths,files)
    context = pilot.load_context(config['scoring_config'], resolved)
    scoring_receipt=readers._json(resolved['scoring_receipt']); summary=readers._json(resolved['scoring_summary'])
    receipt=readers._json(resolved['teacher_receipt']); metrics=readers._json(resolved['teacher_metrics'])
    if (scoring_receipt['report_sha256']['pseudolabel_summary.json'] != raw.sha256_file(resolved['scoring_summary'])
            or receipt['report_sha256']['teacher_validation_metrics.json'] != raw.sha256_file(resolved['teacher_metrics'])):
        raise ValueError('Parent report receipt mismatch')
    pilot_manifest=runs.validate_manifest(readers._json(resolved['pilot_manifest']))
    pilot_receipt=readers._json(resolved['pilot_receipt'])
    for name,key in [('pilot_training_inventory.json','pilot_inventory'),('pilot_experiment_manifest.json','pilot_experiment'),('pilot_B0801_sanity.json','pilot_B0801')]:
        if pilot_receipt['reports'][name] != raw.sha256_file(resolved[key]):
            raise ValueError('Task2.5 report receipt mismatch')
    if pilot_receipt['code_commit'] != pilot_manifest['git']['commit_sha']:
        raise ValueError('Parent pilot commit mismatch')
    distributions, associations, verified_counts = {}, {}, {}
    for stage,member in (('EL','el_train.csv'),('IM','im_train.csv')):
        key=stage.lower()+'_scores'; identity=raw.sha256_file(resolved[key])
        if scoring_receipt['artifacts'][pilot.OUTPUTS[member][0]]['sha256'] != identity:
            raise ValueError('Frozen score receipt mismatch')
        distributions[stage],associations[stage],counts=summarize_scores(adapter._csv_rows(resolved[key]),member,context,config['auc_minimum_per_class'])
        expected=summary['members'][member]
        if (counts['rows'] != expected['teacher_eligible_rows'] or counts['labels'] != expected['eligible_original_label_counts']
                or any(counts['exposure'].get(k,0) != expected['source_exposure_scored_rows'][k] for k in pilot.EXPOSURES)):
            raise ValueError('Saved score aggregate mismatch')
        verified_counts[stage]=counts
    population,_=teacher.load_population(resolved['registry'],context.model.document['config'])
    reports={'allele_stability_distributions.json':{'by_task':distributions, 'verified_counts':verified_counts,
            'scope':'All supported Task2.4 training scores before Task2.5 purging; absent classes/HLAs retained with n0 and null summaries',
            'quantiles':'Type7 linear interpolation on parsed stored float64 hours; p25–p75 are the IQR endpoints',
            'labels':{'EL1':'Publisher-observed eluted-ligand positive; no claim of T-cell immunogenicity',
                      'EL0':'Publisher constructed-negative/decoy label; no per-row experimentally verified absence claim',
                      'IM':'Original publisher IM training labels; assay-level row provenance remains limited'},
            'historical_thresholds':'LOW<1h, HIGH>=10h; scientifically unapproved; strict >10 also reported for clarity'},
        'allele_label_discrimination.json':{'by_task':associations,'interpretation':'Descriptive training-set associations only; not independent performance or evidence of incorrect experimental labels',
            'exposure_scope':'Exact/one-mismatch peptide exposure across any HLA to actual Teacher fitting rows; excludes Teacher validation-only membership; no donor/study clearance',
            'minimum_per_class':config['auc_minimum_per_class'],'ties':'Mann–Whitney concordance, half credit for equal predictions; no uncertainty interval or model selection'},
        'dtu_allele_context.json':dtu_context(population,context,metrics,readers._json(resolved['partition'])),
        'historical_correction_shift_summary.json':correction_shifts(summary,readers._json(resolved['pilot_inventory']),readers._json(resolved['pilot_experiment'])),
        'correction_strategy_assessment.json':strategy_assessment()}
    for item in inputs:
        if raw.sha256_file(item['path']) != item['sha256']:
            raise ValueError('Original diagnostic input changed')
    return reports,inputs,{'parent_preparation_run_id':pilot_manifest['run_id'],
        'parent_preparation_commit':pilot_manifest['git']['commit_sha'],'source_payloads_opened':[],
        'Teacher_refitted_or_rescored':False,'development_outcomes_used':False,'new_overrides_or_training_views_generated':False}


def execute(*, config_path, out=None, paths: StoragePaths | None = None, files=None, verify_existing=False):
    paths=paths or resolve_paths()
    directory=manifest=None
    if out is not None:
        directory,manifest=teacher._run(out,paths)
    elif verify_existing:
        raise ValueError('Replay requires an explicit existing run')
    reports,inputs,provenance=inspect(config_path=config_path,paths=paths,files=files)
    if directory is not None:
        if (manifest['configuration']['file'] != {'path':str(Path(config_path).absolute()),'sha256':raw.sha256_file(config_path)}
                or any(i not in manifest['data_provenance']['input_artifacts'] for i in inputs)):
            raise ValueError('Run must record actual diagnostic configuration and inputs')
        receipt={'code_commit':manifest['git']['commit_sha'],'inputs':inputs,'config_sha256':raw.sha256_file(config_path),
            'report_sha256':{},**provenance}
        for name,report in reports.items():
            if verify_existing:
                with raw._read_file(directory/'reports'/name) as stream:
                    if stream.read()!=raw.json_report(report).encode():raise ValueError('Diagnostic replay mismatch')
            else:
                raw.write_report(directory/'reports'/name,report,paths=paths)
            receipt['report_sha256'][name]=raw.sha256_file(directory/'reports'/name)
        if verify_existing:
            if readers._json(directory/'reports/execution_verification.json')!=receipt:raise ValueError('Receipt replay mismatch')
        else:
            raw.write_report(directory/'reports/execution_verification.json',receipt,paths=paths)
    return reports
