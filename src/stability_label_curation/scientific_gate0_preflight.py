"""Offline aggregate Gate 0 evidence; no eligibility masks, splits or training."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import observation_registry as registry
from . import dtu2016_source_audit as dtu
from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

CONFIG = 'configs/gate0_preflight.json'
INPUT_IDS = ('observations','aliases','validation','lineage','evidence','parent_manifest')
LABELS = ('confirmed_evidence','quantitative_observation','scientific_hypothesis','candidate_recommendation','decision_pending')


def _nonfinite_json(value: str):
    raise ValueError('Non-finite JSON literal: '+value)


def _json(path: str | Path) -> dict[str, Any]:
    with raw._read_file(path) as stream:
        if os.fstat(stream.fileno()).st_size>8*1024*1024:raise ValueError('JSON evidence inspection bound exceeded')
        return json.load(stream,object_pairs_hook=dtu._unique_json,parse_constant=_nonfinite_json)


def load_config(path: str | Path | None = None, *, paths: StoragePaths) -> dict[str, Any]:
    config=_json(path or paths.repository_root/CONFIG)
    if config.get('schema_version')!=1 or set(config.get('inputs',{}))!=set(INPUT_IDS):raise ValueError('Invalid Gate 0 configuration')
    runs.validate_run_id(config['parent_registry_run_id'])
    for item in config['inputs'].values():
        registry._relative(item['parent_relative_path'])
        if len(item['sha256'])!=64 or any(c not in '0123456789abcdef' for c in item['sha256']):raise ValueError('Invalid input checksum')
    threshold=registry.decimal_value(config['high_zero_fraction_threshold'])
    if not 0<=threshold<=1:raise ValueError('Invalid descriptive zero fraction threshold')
    bounds=[registry.decimal_value(x) for x in config['half_life_positive_bin_upper_bounds_hours']]
    if not bounds or bounds!=sorted(set(bounds)) or bounds[0]<=0:raise ValueError('Positive bins must be strictly increasing')
    if any(type(p) is not int or not 0<=p<=100 for p in config['positive_quantiles_percent']):raise ValueError('Invalid quantile configuration')
    for item in config['repository_evidence']:
        target=paths.repository_root/registry._relative(item['relative_path'])
        if raw.sha256_file(target)!=item['sha256']:raise ValueError('Repository evidence identity differs: '+item['relative_path'])
    return config


def _jsonl(path: Path, cap: int):
    with raw._read_file(path) as stream:
        if os.fstat(stream.fileno()).st_size>cap:raise ValueError('Registry/lineage inspection byte bound exceeded')
        for number,line in enumerate(stream,1):
            if number>100000 or len(line)>65536:raise ValueError('Registry/lineage record inspection bound exceeded')
            try:
                item=json.loads(line,object_pairs_hook=dtu._unique_json,parse_constant=_nonfinite_json)
                if not isinstance(item,dict):raise ValueError('Expected a JSON object')
            except (ValueError,TypeError) as error:raise ValueError(f'Invalid registry JSONL at line {number}') from error
            yield item


def _fraction(n: int, total: int) -> str | None:
    with localcontext() as context:
        context.prec=50
        return str(Decimal(n)/total) if total else None


def _quantiles(values: Sequence[Decimal], config: dict[str, Any]) -> dict[str, Any]:
    return {'positive_values':len(values),'minimum':str(min(values)) if values else None,'maximum':str(max(values)) if values else None,
        'quantiles_hours':{'p'+str(p):None if not values else str(dtu.quantile(values,p)) for p in config['positive_quantiles_percent']},
        'convention':config['quantile_convention']}


def _group(rows: Sequence[registry.Observation], config: dict[str, Any]) -> dict[str, Any]:
    values=[registry.decimal_value(o.original_measurement_text) for o in rows]
    zero=sum(v==0 for v in values);positive=[v for v in values if v>0]
    return {'records':len(rows),'allele_identifiers':len({o.original_allele for o in rows}),
        'zero_values':zero,'positive_values':len(positive),'negative_values':sum(v<0 for v in values),
        'zero_fraction':_fraction(zero,len(rows)), 'positive_distribution_hours':_quantiles(positive,config)}


def zero_analysis(rows: Sequence[registry.Observation], config: dict[str, Any]) -> dict[str, Any]:
    by_allele=defaultdict(list)
    for row in rows:by_allele[row.original_allele].append(row)
    total=len(rows);positive_total=sum(registry.decimal_value(o.original_measurement_text)>0 for o in rows)
    table=[];threshold=Decimal(config['high_zero_fraction_threshold'])
    for allele,group in sorted(by_allele.items()):
        item={'original_allele':allele,**_group(group,config)}
        before=_fraction(item['records'],total);after=_fraction(item['positive_values'],positive_total)
        with localcontext() as context:
            context.prec=50;change=None if before is None or after is None else str(100*(Decimal(after)-Decimal(before)))
        item.update(high_zero_fraction=Decimal(item['zero_fraction'])>=threshold,
            Z1_allele_share=before,Z2_positive_only_allele_share=after,Z2_minus_Z1_share_percentage_points=change,
            hypothetical_Z2_removed_count=item['zero_values'],hypothetical_Z2_retained_fraction=_fraction(item['positive_values'],item['records']))
        table.append(item)
    value_texts=defaultdict(Counter);precision=Counter();bins=Counter({'negative':0,'exact_zero':0})
    upper=config['half_life_positive_bin_upper_bounds_hours'];bin_names=[];lower='0'
    for bound in upper:bin_names.append('('+lower+','+bound+']');lower=bound
    bin_names.append('('+lower+',infinity)')
    for name in bin_names:bins[name]=0
    for row in rows:
        value=registry.decimal_value(row.original_measurement_text)
        if value>0:
            value_texts[value][row.original_measurement_text]+=1
            precision[str(-value.as_tuple().exponent)]+=1
            index=next((i for i,b in enumerate(upper) if value<=Decimal(b)),len(upper));bins[bin_names[index]]+=1
        else:bins['exact_zero' if value==0 else 'negative']+=1
    high=[r for r in table if r['high_zero_fraction']]
    zero=sum(r['zero_values'] for r in table);positive_alleles=sum(r['positive_values']>0 for r in table)
    coverage={'Z1':{'candidate':'Reported-zero-inclusive regression','status':'decision_pending','all_reported_value_count':total,
        'potential_continuous_objective_records':total,'allele_identifiers':len(table)},
        'Z2':{'candidate':'Positive-only regression','status':'decision_pending','potential_continuous_objective_records':positive_total,
        'reported_zeros_not_used_for_continuous_objective':zero,'positive_supported_alleles':positive_alleles,
        'alleles_with_no_positive_support':[r['original_allele'] for r in table if not r['positive_values']]},
        'Z3':{'candidate':'Separate reported-zero status and positive-value objectives','status':'decision_pending',
        'potential_reporting_status_records':total,'reported_zero_status_count':zero,'potential_positive_continuous_records':positive_total,
        'reporting_status_supported_alleles':len(table),'positive_objective_supported_alleles':positive_alleles,
        'not_a_censored_likelihood':'Detection/quantification thresholds and censoring mechanisms are unverified.'}}
    return {'evidence_label':'quantitative_observation','cohort':'Literal ordinary HLA-A/B DTU identifiers; descriptive partition, not approved eligibility',
        'summary':_group(rows,config),'by_HLA_locus':{locus:_group([o for o in rows if dtu.identifier_category(o.original_allele)=='ordinary_hla_'+locus.lower()],config) for locus in ('A','B')},'by_allele':table,'high_zero_fraction_threshold':str(threshold),'high_zero_fraction_alleles':high,
        'positive_reported_decimal_scale_counts':dict(sorted(precision.items())),
        'lowest_ten_distinct_positive_values':[{'hours':str(v),'count':sum(value_texts[v].values()),'original_text_counts':dict(sorted(value_texts[v].items()))} for v in sorted(value_texts)[:10]],
        'reported_half_life_bin_counts':dict(bins),'bin_convention':config['bin_convention'],
        'zero_original_text_counts':dict(sorted(Counter(o.original_measurement_text for o in rows if registry.decimal_value(o.original_measurement_text)==0).items())),
        'candidate_policy_coverage':coverage,
        'alleles_below_descriptive_positive_sample_counts':{str(n):[r['original_allele'] for r in table if r['positive_values']<n] for n in config['minimum_support_descriptive_counts']},
        'measurement_semantics':'Unresolved; zero is only a source-reported numeric value. No synthetic, physical-zero, missing or left-censored designation.',
        'scientific_hypothesis':'Positive-only selection may bias measurable/stable complexes and allele composition; computed count changes do not establish the mechanism.'}


def _peptide_reuse(rows: Sequence[registry.Observation]) -> dict[str, Any]:
    alleles=defaultdict(set);counts=Counter()
    for row in rows:alleles[row.original_peptide].add(row.original_allele);counts[row.original_peptide]+=1
    repeated=[p for p,a in alleles.items() if len(a)>1]
    return {'unique_peptide_strings':len(alleles),'peptides_on_multiple_HLA_identifiers':len(repeated),
        'measurement_records_for_these_peptides':sum(counts[p] for p in repeated),
        'maximum_HLA_identifiers_per_peptide':max((len(a) for a in alleles.values()),default=0),
        'meaning':'Exact sequence reuse is detectable; homology, common donor/study or independence cannot be inferred.'}


def _designs() -> dict[str, Any]:
    zero=[('Z1','Preserves all ordinary rows and low reported values; simple reported-target baseline.',
        'Unknown zero generation may distort continuous targets.'),
        ('Z2','Avoids assigning ambiguous zeros precise continuous targets.',
        'Removes reported-zero ordinary rows; allele shares and measurable-stability selection can change.'),
        ('Z3','Separates reporting status from continuous positive values without interpreting physical zero.',
        'Needs additional objectives and calibration; reporting mechanism remains unknown; no formal censoring assertion.')]
    constructs=[('C1','Ordinary-identifier primary scope, preserving C67S in the registry.',
        'Define a wild-type prediction goal and acknowledge ordinary identifiers do not individually prove material identity.'),
        ('C2','Separate construct-specific analyses for the three literal C67S identifiers.',
        'Need construct interpretation, assay conditions and sufficient positive support; limited construct generalization.'),
        ('C3','Potential combined training only with explicit construct representation.',
        'Missing authenticated mutant sequences/residue indexing, modification purpose, biological equivalence limits, assay and zero-generation evidence.')]
    splits=[{'id':'S1','candidate':'Random peptide-HLA pairs','prevents':'Exact pair crossing only if all same-key records and aliases are grouped.',
        'does_not_prevent':'Same peptide on other alleles, homologs, shared study/donor, pretrained exposure.',
        'metadata':'Pair keys plus assay/context identity and lineage groups','support':'Current registry has keys; balance after eligibility is undecided.',
        'generalization':'Mainly interpolation; candidate simple reference.'},
        {'id':'S2','candidate':'Exact-peptide-disjoint','prevents':'Identical peptides across alleles, modalities, contexts and aliases when grouping globally.',
        'does_not_prevent':'Homologs, antigen families, shared studies/donors or checkpoint exposure.',
        'metadata':'Original peptide strings and provenance groups','support':'Exact strings available; allele balance/rare positives and final coverage require later planning.',
        'generalization':'Unseen exact peptides, not proven unseen peptide families.'},
        {'id':'S3','candidate':'Sequence-similarity cluster-disjoint','prevents':'Defined similarity-neighbor crossing according to the selected metric/threshold.',
        'does_not_prevent':'Unrecognized biological families, unrelated shared studies/donors or pretrained exposure.',
        'metadata':'Peptides, predeclared alignment/distance, threshold, clustering/transitivity and grouping rules.',
        'support':'Sequences available; clusters/counts not constructed. Short 8–11-mers and allele imbalance constrain sizes.',
        'generalization':'New groups under that similarity definition; not universal antigen independence.'},
        {'id':'S4','candidate':'Allele-stratified evaluation','prevents':'Can avoid losing supported alleles and measure per-allele performance; stratification alone prevents no sequence leakage.',
        'does_not_prevent':'Identical/similar peptide leakage unless combined with S2/S3.',
        'metadata':'Allele counts, post-policy positives/zeros, grouping and minimum-support rules.',
        'support':'Current per-allele counts available; C constructs have few positives; unseen-allele holdout is a different protocol.',
        'generalization':'Within-known-allele estimates; unseen-allele generalization only with a separately declared allele holdout.'},
        {'id':'S5','candidate':'Source-study-disjoint','prevents':'Identified study/donor/assay reuse when complete group metadata are available.',
        'does_not_prevent':'Shared peptides/families or checkpoint exposure without extra controls.',
        'metadata':'Individual study, assay, donor, antigen and raw-measurement identities.',
        'support':'Not defensibly supported now: DTU study incorporation lacks row tags; Jappe is a different modality, not an interchangeable kinetic test.',
        'generalization':'New studies only if independence and sample support are established.'}]
    pending=[{'id':i,'status':'decision_pending','decision':text} for i,text in [
        ('D1','Select Z1/Z2/Z3 and predeclare zero-policy sensitivities, target interpretation and metrics; no censoring likelihood without evidence.'),
        ('D2','Select ordinary/construct scope C1/C2/C3 and define molecular evidence required for construct inclusion.'),
        ('D3','Choose kinetic-primary and/or separately modeled thermal directions; retain distinct units and C contexts.'),
        ('D4','Choose validation protocol, grouping scope, similarity metric/threshold and allele support rules before constructing splits.'),
        ('D5','Define external immunogenicity freeze timing and binding-checkpoint exposure audit before model selection.'),
        ('D6','Predeclare later questionable-positive holding-out criterion, matched random-removal strata, affinity-only and affinity-conditioned controls.'),
        ('D7','Select primary metrics/aggregation, multiple seeds, paired comparisons and dependence-aware uncertainty intervals.'),
        ('D8','Clarify permitted source/checkpoint use and redistribution; missing license information grants no inferred permission.')]]
    guardrails=['Unchanged immunogenicity evaluator architecture and same loss across conditions.',
        'Common binding-trained initialization; no checkpoint exposed to original immunogenicity training labels without a provenance resolution.',
        'Only filtering/holding out questionable positive training examples; no positive-to-negative relabeling.',
        'No stability input features to the immunogenicity evaluator.',
        'Frozen untouched external tests before labeler/evaluator hyperparameter selection if those tests could influence development.',
        'Matched random-positive removal and affinity-only controls; affinity-conditioned stability is a separately predeclared secondary analysis.',
        'Paired evaluations, multiple seeds, uncertainty intervals and a specified primary metric; no external-test-driven threshold selection.']
    return {'zero_candidates':[{'id':i,'status':'decision_pending','advantages':a,'risks':r} for i,a,r in zero],
        'construct_candidates':[{'id':i,'status':'decision_pending','proposal':a,'required_evidence_or_risks':r} for i,a,r in constructs],
        'split_candidates':[{**s,'status':'decision_pending'} for s in splits],
        'candidate_recommendations':[
            {'evidence_label':'candidate_recommendation','status':'decision_pending','proposal':'For review: Z1 reported-value baseline with Z2 sensitivity; assess Z3 separately after defining reporting-status interpretation.'},
            {'evidence_label':'candidate_recommendation','status':'decision_pending','proposal':'For review: C1 primary ordinary-identifier scope and C2 construct-specific evidence; C3 requires molecular/assay evidence before adoption.'},
            {'evidence_label':'candidate_recommendation','status':'decision_pending','proposal':'For review: exact-peptide-disjoint kinetic validation with random-pair reference; cluster-disjoint sensitivity only after metric/threshold/support decisions. Allele strata report known-allele support.'},
            {'evidence_label':'candidate_recommendation','status':'decision_pending','proposal':'For review: separate thermal model or orthogonal signal; no conversion or pooled regression target.'},
            {'evidence_label':'candidate_recommendation','status':'decision_pending','proposal':'For review: immunogenicity primary paired delta AUPRC, AUROC secondary; kinetic MAE in hours and RMSE secondary if continuous objective adopted. Aggregation, seeds and dependence-aware intervals must be locked before testing.'}],
        'user_required_decisions':pending,'downstream_user_prescribed_guardrails':guardrails,
        'eligibility_decisions': 'decision_pending','approved_policies':[], 'split_assignments_created':False,'training_authorized':False}


def _threats(detected: dict[str, Any]) -> dict[str, Any]:
    rows=[('exact_pair','detectable_using_registry','Repeated same-key methods/contexts and alias targets are identifiable.',
        'Group equivalent provenance and all same-key contexts before any future split.'),
        ('exact_peptide_across_HLA','detectable_using_registry','Peptide strings recur on different HLA identifiers.',
        'Group exact peptide across alleles/modalities and lineage representations for future validation.'),
        ('SPEARMINT_DTU_reuse','confirmed_evidence','All released aliases reuse ordinary DTU records; no independent Stage 2 cohort.',
        'Count canonical observations once; never use alias partitions as independent external tests.'),
        ('sequence_similarity','not_assessed_definition_pending','Peptides are available, but similarity metric/threshold/family definitions are not approved.',
        'Predeclare similarity clustering and sensitivity thresholds; no clusters made in this task.'),
        ('original_study_or_antigen_family','metadata_unavailable','DTU incorporated prior study data; row-level study/antigen lineage is incomplete.',
        'Acquire/verify row tags later; do not treat publication-level source IDs as study independence.'),
        ('wild_type_mutant_peptides','metadata_unavailable','C67S denotes HLA constructs; it does not identify wild-type/mutant peptide relationships.',
        'Use authenticated reference peptide/variant and antigen metadata later; do not guess from sequence edits.'),
        ('donor_assay_antigen','metadata_unavailable','Individual donors, replicate/assay IDs and source antigen identities are not complete in this registry.',
        'Group authenticated donor/study/antigen relationships when available.'),
        ('immunogenicity_overlap','requires_unacquired_immunogenicity_data','No external immunogenicity corpus is read here; overlaps are unknown, not absent.',
        'Audit exact and similar peptide-HLA/peptide overlaps before external freeze and model selection.'),
        ('immunogenicity_pretrained_exposure','checkpoint_provenance_unavailable','Checkpoint training-label provenance has not been audited here.',
        'Common binding-trained checkpoint with audited exposure; no immunogenicity-label-contaminated initialization.'),
        ('evaluation_exposure_during_selection','future_process_risk','External peptides/labels could influence labeler thresholds or evaluator hyperparameters.',
        'Freeze external tests before any selection they could influence; use inner development data only.'),
        ('pretrained_stability_reuse','predictor_provenance_required','Published predictors may have trained on these measurements; checkpoint-specific membership is not audited.',
        'Audit training membership before using predictions or weights; avoid claiming external validation on reused measurements.')]
    return {'evidence_label':'quantitative_observation','detected_registry_evidence':detected,
        'threats':[{'id':i,'assessment':a,'evidence_or_limit':e,'proposed_control':c,'control_status':'decision_pending'} for i,a,e,c in rows],
        'immunogenicity_leakage_absence_claimed':False,'similarity_clusters_computed':False,'external_tests_frozen':False}


@dataclass
class PreflightResult:
    reports: dict[str,dict[str,Any]]
    inputs: list[dict[str,str]]


def inspect(*, paths: StoragePaths | None = None, files: Mapping[str,str | Path] | None = None,
            config_path: str | Path | None = None) -> PreflightResult:
    storage=resolve_paths() if paths is None else paths;config=load_config(config_path,paths=storage);supplied=dict(files or {})
    if set(supplied)-set(INPUT_IDS):raise ValueError('Unknown Gate 0 input override')
    parent=storage.project_runs_dir/config['parent_registry_run_id'];targets={};inputs=[]
    for key in INPUT_IDS:
        item=config['inputs'][key];path=Path(supplied.get(key,parent/item['parent_relative_path'])).expanduser().absolute()
        try:checksum=raw.sha256_file(path)
        except FileNotFoundError as error:raise ValueError('Missing required parent registry input: '+key) from error
        if checksum!=item['sha256']:raise ValueError('Parent registry input checksum mismatch: '+key)
        targets[key]=path;inputs.append({'path':str(path),'sha256':checksum})
    validation=_json(targets['validation']);lineage=_json(targets['lineage']);evidence=_json(targets['evidence']);manifest=_json(targets['parent_manifest'])
    runs.validate_manifest(manifest)
    if manifest['run_id']!=config['parent_registry_run_id'] or manifest['git']['commit_sha']!=config['parent_registry_commit'] or not manifest['reproducibility']['canonical']:
        raise ValueError('Parent canonical run identity differs')
    config_sha=next(e['sha256'] for e in config['repository_evidence'] if e['relative_path']==registry.LOCK)
    if manifest['configuration']['file']['sha256']!=config_sha:raise ValueError('Parent registry lock identity differs')
    if lineage['sources']!=evidence['lock']['source_lineage']:raise ValueError('Parent lineage evidence is inconsistent')
    observations=[];by_id={}
    for item in _jsonl(targets['observations'],64*1024*1024):
        try:
            if not isinstance(item['data_quality_flags'],list) or any(not isinstance(f,str) for f in item['data_quality_flags']):raise ValueError('Invalid quality flags')
            item['data_quality_flags']=tuple(item['data_quality_flags']);row=registry.Observation(**item)
        except (KeyError,TypeError,ValueError) as error:raise ValueError('Invalid canonical observation schema/value/provenance') from error
        if row.observation_id in by_id:raise ValueError('Duplicate registry observation ID')
        value=registry.decimal_value(row.original_measurement_text)
        if ('exact_zero' in row.data_quality_flags)!=(value==0):raise ValueError('Zero flag disagrees with source-reported value')
        if row.measurement_type=='kinetic_half_life' and value==0 and 'zero_semantics_unresolved' not in row.data_quality_flags:raise ValueError('DTU zero semantics must stay unresolved')
        if row.measurement_type=='kinetic_half_life' and row.source_id!='netmhcstabpan_2016':raise ValueError('Unexpected kinetic observation source')
        if row.measurement_type=='thermal_melting_temperature' and row.source_id!='jappe_2020':raise ValueError('Unexpected thermal observation source')
        by_id[row.observation_id]=row;observations.append(row)
    kinetic=[o for o in observations if o.measurement_type=='kinetic_half_life'];thermal=[o for o in observations if o.measurement_type=='thermal_melting_temperature']
    ordinary=[o for o in kinetic if dtu.identifier_category(o.original_allele) in {'ordinary_hla_a','ordinary_hla_b'}]
    constructs=[o for o in kinetic if dtu.identifier_category(o.original_allele)=='c67s_annotated_hla_b']
    ordinary_ids={o.observation_id for o in ordinary}
    alias_ids=set();alias_splits=Counter();alias_peptide_splits=defaultdict(set);alias_sequence_lengths=Counter()
    for alias in _jsonl(targets['aliases'],128*1024*1024):
        try:
            target=by_id[alias['canonical_dtu_observation_id']]
            if (alias['schema_version']!=1 or alias['source_id']!='spearmint_stability_audit'
                or target.source_id!='netmhcstabpan_2016' or target.observation_id not in ordinary_ids
                or alias['split'] not in {'train','validation','test'}
                or alias['original_peptide']!=target.original_peptide
                or alias['mapping_evidence']['mapped_identifier']!=target.original_allele
                or registry.decimal_value(alias['original_measurement_text'])!=registry.decimal_value(target.original_measurement_text)
                or alias['half_life_agreement']!='exact_decimal_hours'
                or alias['measurement_type']!='kinetic_half_life' or alias['measurement_unit']!='hours'
                or (alias['original_allele'] and alias['original_allele']!=target.original_allele)):
                raise ValueError('Alias relationship does not reproduce exact DTU lineage')
            if target.observation_id in alias_ids:raise ValueError('Duplicate alias target across/within released splits')
            alias_ids.add(target.observation_id);alias_splits[alias['split']]+=1
            alias_peptide_splits[alias['original_peptide']].add(alias['split']);alias_sequence_lengths[str(alias['reference_sequence_length'])]+=1
        except (KeyError,TypeError,ValueError) as error:raise ValueError('Invalid/unmatched/duplicate SPEARMINT alias') from error
    if alias_ids!=ordinary_ids:raise ValueError('Incomplete ordinary-DTU alias coverage')
    c_rows=[o for o in thermal if o.original_allele=='HLA-C*04:01'];c_groups=defaultdict(list)
    for o in c_rows:c_groups[o.original_peptide].append(o)
    if any(len(g)!=2 or {o.assay_context for o in g}!={'C1R-A*02:01','C1R-B*07:02'} for g in c_groups.values()):raise ValueError('HLA-C context pairs are inconsistent')
    combinations=defaultdict(list)
    for o in observations:combinations[(o.original_allele,o.original_peptide)].append(o)
    repeated=[g for g in combinations.values() if len({(o.measurement_type,o.assay_context) for o in g})>1]
    cross=[(k,g) for k,g in sorted(combinations.items()) if {o.measurement_type for o in g}==set(registry.TYPE_UNITS)]
    observed={'dtu_observations':len(kinetic),'dtu_alleles':len({o.original_allele for o in kinetic}),
        'dtu_zero_values':sum(registry.decimal_value(o.original_measurement_text)==0 for o in kinetic),
        'dtu_c67s_observations':len(constructs),'dtu_ordinary_observations':len(ordinary),
        'jappe_by_allele':dict(sorted(Counter(o.original_allele for o in thermal).items())),
        'jappe_C_unique_peptides':len(c_groups),'jappe_observations':len(thermal),'total_observations':len(observations),
        'aliases_by_split':dict(sorted(alias_splits.items())),'total_aliases':len(alias_ids)}
    if observed!=validation['observed_counts'] or observed!=validation['expected_counts'] or len(repeated)!=validation['repeated_combination_count']:
        raise ValueError('Computed registry counts disagree with parent validation evidence')
    zero=zero_analysis(ordinary,config);by_construct=defaultdict(list)
    for o in constructs:by_construct[o.original_allele].append(o)
    designs=_designs()
    c_report={'evidence_label':'quantitative_observation','ordinary':_group(ordinary,config),'C67S':_group(constructs,config),
        'by_original_construct':[{'original_identifier':a,**_group(g,config)} for a,g in sorted(by_construct.items())],
        'candidate_coverage':{'C1':{'status':'decision_pending','potential_primary_records':len(ordinary),'ordinary_identifiers':len({o.original_allele for o in ordinary}),'C67S_records_stay_in_registry':len(constructs)},
        'C2':{'status':'decision_pending','separate_construct_records':len(constructs),'construct_identifiers':len(by_construct)},
        'C3':{'status':'decision_pending','potential_combined_records':len(kinetic),'distinct_identifiers':len({o.original_allele for o in kinetic}),'required_representation':'Authenticated explicit mutant construct sequence and interpretation; unavailable'}},
        'candidate_designs':designs['construct_candidates'],'wild_type_mapping_created':False,
        'generalization_limit':'Mutant-to-wild-type mapping could misattribute altered binding/groove behavior; source construct purpose and biological equivalence are unverified.'}
    modality={'evidence_label':'quantitative_observation','type_units':registry.TYPE_UNITS,'exact_cross_modality_key_count':len(cross),
        'cross_modality_by_allele':dict(sorted(Counter(k[0] for k,g in cross).items())),
        'cross_modality_peptide_lengths':dict(sorted(Counter(str(len(k[1])) for k,g in cross).items())),
        'peptide_lengths_by_modality':{t:dict(sorted(Counter(str(len(o.original_peptide)) for o in observations if o.measurement_type==t).items())) for t in registry.TYPE_UNITS},
        'cross_modality_pairs':[{'original_allele':k[0],'original_peptide':k[1],'observation_ids':[o.observation_id for o in g],
            'reported_contexts':[{'measurement_type':o.measurement_type,'assay_context':o.assay_context} for o in g]} for k,g in cross],
        'C_contexts':{'unique_peptides':len(c_groups),'measurement_values':len(c_rows),'distinct_observation_ids':len({o.observation_id for o in c_rows}),
            'records_by_context':dict(sorted(Counter(o.assay_context for o in c_rows).items())),'averaged':False,'independent_replicates_established':False},
        'context_ambiguity':'DTU per-row conditions and assay-material identity are unverified; thermal C1R contexts differ from kinetic dissociation assays.',
        'scientific_hypothesis':'A small two-source exact-overlap subset cannot establish a population-wide Tm-to-half-life relationship.',
        'future_directions':['Primary kinetic labeler candidate from DTU hours.','Separate thermal model or orthogonal signal from Jappe Celsius.'],
        'cross_modality_numeric_calibration_performed':False}
    detected={'same_pair_distinct_methods_or_contexts':len(repeated),'exact_cross_modality_pairs':len(cross),'paired_C_keys':len(c_groups),
        'identical_DTU_SPEARMINT_observation_aliases':len(alias_ids),
        'exact_peptide_reuse_all_registry':_peptide_reuse(observations),'exact_peptide_reuse_ordinary_DTU':_peptide_reuse(ordinary),
        'released_alias_peptides_crossing_splits':sum(len(s)>1 for s in alias_peptide_splits.values()),
        'released_split_limit':'Exact disjointness here does not certify similarity disjointness or independent experiments; splits not adopted.'}
    source_registry=load_manifest(paths=storage);licenses=[]
    for source_id in ('netmhcstabpan_2016','spearmint_stability_audit','jappe_2020','netmhcstab_2013','tlstab_reference'):
        source=source_registry.get(source_id)
        licenses.append({'source_id':source_id,'registry_license_statement':source.license,
            'verified_terms_scope':'Article CC BY 4.0 with third-party exceptions; artifact/underlying-resource scope not independently certified.' if source_id=='jappe_2020' else 'Dataset redistribution/license unresolved in captured audit; public availability is not permission evidence.',
            'original_dataset_provenance':source.title,'exact_row_experimental_origin_established':False,
            'source_files_outside_Git':True,'legal_determination_made':False})
    coverage={'evidence_label':'quantitative_observation','verified_registry_counts':observed,'ordinary_DTU':_group(ordinary,config),'C67S_DTU':_group(constructs,config),
        'source_and_measurement_counts':dict(sorted(Counter(o.source_id+' / '+o.measurement_type for o in observations).items())),
        'row_origin_status_counts':dict(sorted(Counter(o.row_origin_status for o in observations).items())),
        'SPEARMINT_alias_sequence_lengths':dict(sorted(alias_sequence_lengths.items())),
        'record_count_interpretation':'Measurement-value records and derived aliases, not independent experiments or training-eligible samples.',
        'new_independent_records_from_aliases':0,'all_eligibility_decisions':'decision_pending'}
    provenance={'parent_registry_run_id':manifest['run_id'],'parent_registry_code_commit':manifest['git']['commit_sha'],
        'direct_inputs_read':[{'input_id':k,'parent_relative_path':config['inputs'][k]['parent_relative_path'],'sha256':config['inputs'][k]['sha256']} for k in INPUT_IDS],
        'inherited_source_evidence_manifest':evidence,'source_lineage':lineage,
        'original_source_artifacts_read_or_rehashed_this_task':False,
        'direct_relationship_limit':'Only derived registry/report/manifest files are inputs; source relationships are inherited, not new raw-input verification.',
        'source_usage_uncertainties':licenses,'confirmed_evidence_scope':'Previously captured publication, source-audit and user-design evidence; no new source retrieval.',
        'unavailable_evidence':{'individual_measurement_traces':'unavailable','zero_generation_mechanism':'unresolved','C67S_molecular_purpose':'unresolved',
            'historical_original_table_overlap':'unavailable_not_zero','C359_complete_population':'unavailable_not_zero',
            'donor_study_antigen_row_tags':'incomplete_or_unavailable','immunogenicity_dataset_overlap':'not_assessed_data_not_acquired','pretrained_checkpoint_exposure':'not_audited'},
        'label_vocabulary':LABELS,'configuration':config}
    reports={'gate0_data_coverage.json':coverage,'gate0_zero_policy_comparison.json':zero,'gate0_c67s_policy_comparison.json':c_report,
        'gate0_modality_overlap.json':modality,'gate0_leakage_threat_model.json':_threats(detected),
        'gate0_decision_matrix.json':designs,'gate0_source_evidence.json':provenance}
    for item in inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Parent registry input changed during preflight')
    return PreflightResult(reports,inputs)


def write_reports(result: PreflightResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage=resolve_paths() if paths is None else paths;directory=Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Dossier output requires an existing project run reports directory')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record every unchanged derived input')
    names=[*result.reports,'gate0_report_checksums.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            except FileNotFoundError:continue
            raise FileExistsError('Gate 0 report already exists: '+name)
    for name,document in result.reports.items():raw.write_report(directory/name,document,paths=storage)
    receipt={'reports':{name:raw.sha256_file(directory/name) for name in result.reports},'inputs':result.inputs,
        'parent_registry_run_id':result.reports['gate0_source_evidence.json']['parent_registry_run_id'],
        'completion':'aggregate_dossier_complete; all_eligibility_decisions_pending'}
    for item in result.inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Parent input changed before completion receipt')
    raw.write_report(directory/names[-1],receipt,paths=storage)
    return receipt
