"""Versioned observation identities and lossless, offline source consolidation.

Measurement-value records are not independent experiments or training decisions.
SPEARMINT partitions annotate lineage; they never add canonical observations.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Literal, Mapping, TypedDict

from . import netmhcstabpan_2016 as raw
from . import dtu2016_source_audit as dtu
from . import jappe_2020_row_audit as jappe
from . import spearmint_overlap_audit as spearmint
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

SCHEMA_VERSION = 1
LOCK = 'configs/observation_registry.lock.json'
INPUT_IDS = ('dtu','spearmint_train','spearmint_val','spearmint_test','spearmint_mapping',
             'jappe_data_3','jappe_data_4','jappe_data_5','jappe_ledger')
TYPE_UNITS = {'kinetic_half_life':'hours','thermal_melting_temperature':'degC'}
DTU_CONTEXT = 'SPA_dissociation_dataset_context; individual_row_conditions_unverified'


class DtuLocator(TypedDict):
    kind: Literal['text_line']
    artifact: str
    line_number: int


class JappeLocator(TypedDict):
    kind: Literal['workbook_cell']
    artifact: str
    worksheet: str
    row_number: int
    cell_coordinate: str


def _relative(value: str) -> str:
    if not isinstance(value,str):raise ValueError('Portable provenance path must be text')
    path=PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value or str(path)!=value:
        raise ValueError('Unsafe portable provenance path')
    return value


def observation_id(source_id: str, sha256: str, locator: Mapping[str, Any]) -> str:
    """Full SHA256 identity over immutable source and exact coordinates, never a join key."""
    if not isinstance(sha256,str) or not re.fullmatch('[a-f0-9]{64}',sha256):raise ValueError('Invalid source checksum')
    if not isinstance(source_id,str) or not re.fullmatch('[a-z][a-z0-9_]*',source_id):raise ValueError('Invalid source ID')
    _relative(locator.get('artifact',''))
    if locator.get('kind')=='text_line':
        if set(locator)!={'kind','artifact','line_number'} or type(locator['line_number']) is not int or locator['line_number']<1:
            raise ValueError('Invalid source line locator')
    elif locator.get('kind')=='workbook_cell':
        if (set(locator)!={'kind','artifact','worksheet','row_number','cell_coordinate'}
            or not isinstance(locator['worksheet'],str) or not locator['worksheet']
            or type(locator['row_number']) is not int or locator['row_number']<1
            or not re.fullmatch('[A-Z]+'+str(locator['row_number']),locator['cell_coordinate'])):
            raise ValueError('Invalid source cell locator')
    else:raise ValueError('Missing supported source locator')
    identity={'identity_schema_version':1,'source_id':source_id,'source_artifact_sha256':sha256,'source_locator':dict(locator)}
    return 'obs1_'+hashlib.sha256(raw.json_report(identity).encode('utf-8')).hexdigest()


def decimal_value(text: str) -> Decimal:
    try:record=raw.parse_record('X P '+text,1)
    except ValueError as error:raise ValueError('Invalid measurement text') from error
    if record.half_life is None or record.numeric_issue or not record.half_life.is_finite():
        raise ValueError('Missing, non-numeric or non-finite measurement: '+text)
    if len(record.half_life.as_tuple().digits)>128 or abs(record.half_life.as_tuple().exponent)>128:
        raise ValueError('Measurement exceeds numeric inspection bounds')
    return record.half_life


@dataclass(frozen=True)
class Observation:
    schema_version: int
    observation_id: str
    source_id: str
    source_artifact_sha256: str
    source_locator: DtuLocator | JappeLocator
    original_allele: str
    original_peptide: str
    original_measurement_text: str
    parsed_measurement_decimal: str
    measurement_type: Literal['kinetic_half_life','thermal_melting_temperature']
    measurement_unit: Literal['hours','degC']
    assay_context: str
    published_source_provenance: dict[str, Any]
    row_origin_status: str
    data_quality_flags: tuple[str, ...]
    source_record_context: dict[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version!=SCHEMA_VERSION:raise ValueError('Unsupported observation schema')
        if self.measurement_type not in TYPE_UNITS or TYPE_UNITS[self.measurement_type]!=self.measurement_unit:raise ValueError('Incompatible measurement type/unit')
        if self.observation_id!=observation_id(self.source_id,self.source_artifact_sha256,self.source_locator):raise ValueError('Observation ID does not match immutable provenance')
        if decimal_value(self.original_measurement_text)!=decimal_value(self.parsed_measurement_decimal):raise ValueError('Original and parsed measurement disagree')
        if not self.original_allele or not self.original_peptide or not self.assay_context or not self.row_origin_status:
            raise ValueError('Required observation provenance is missing')
        if self.row_origin_status != {'netmhcstabpan_2016':dtu.ROW_PROVENANCE,'jappe_2020':jappe.ROW_ORIGIN}.get(self.source_id):
            raise ValueError('Observation origin must remain conservative and unverified')

    def as_dict(self) -> dict[str, Any]:return asdict(self)


def make_observation(*,source_id: str,sha256: str,locator: DtuLocator | JappeLocator,
    allele: str,peptide: str,text: str,measurement_type: str,unit: str,context: str,
    provenance: dict[str, Any],origin: str,flags: list[str],record_context: dict[str, Any]) -> Observation:
    value=decimal_value(text);flags=list(flags)
    if value==0:
        flags.append('exact_zero')
        if measurement_type=='kinetic_half_life':flags.append('zero_semantics_unresolved')
    if value<0:flags.append('negative_reported_value')
    if not re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',peptide):flags.append('noncanonical_peptide_text')
    return Observation(SCHEMA_VERSION,observation_id(source_id,sha256,locator),source_id,sha256,locator,
        allele,peptide,text,str(value),measurement_type,unit,context,provenance,origin,tuple(sorted(set(flags))),record_context)


def load_lock(path: str | Path | None = None, *, paths: StoragePaths) -> dict[str, Any]:
    with raw._read_file(path or paths.repository_root/LOCK) as stream:lock=json.load(stream,object_pairs_hook=dtu._unique_json)
    if lock.get('schema_version')!=1 or lock.get('observation_schema_version')!=SCHEMA_VERSION:raise ValueError('Unsupported registry lock')
    entries=lock.get('artifacts',[])
    if len(entries)!=len(INPUT_IDS) or {e['input_id'] for e in entries}!=set(INPUT_IDS):raise ValueError('Registry lock requires exactly the nine used inputs')
    for entry in entries:
        _relative(entry['relative_path'])
        if entry['storage_area'] not in {'data','runs'} or not re.fullmatch('[a-f0-9]{64}',entry['sha256']):raise ValueError('Invalid locked input identity')
    required_expectations={'dtu_observations','dtu_alleles','dtu_zero_values','dtu_c67s_observations','dtu_ordinary_observations',
        'jappe_by_allele','jappe_C_unique_peptides','jappe_observations','total_observations','aliases_by_split','total_aliases'}
    if set(lock.get('expectations',{}))!=required_expectations:raise ValueError('Registry validation expectations must be explicit and complete')
    registry=load_manifest(paths=paths)
    for entry in lock['source_lineage']:
        registry.get(entry['registry_source_id'])
        if 'measurement_type' in entry and TYPE_UNITS.get(entry['measurement_type'])!=entry['measurement_unit']:
            raise ValueError('Locked measurement type/unit mismatch')
    evidence={}
    for entry in lock['evidence_files']:
        relative=_relative(entry['relative_path']);target=paths.repository_root/relative
        if raw.sha256_file(target)!=entry['sha256']:raise ValueError('Committed evidence checksum mismatch: '+relative)
        if relative.endswith('.json'):
            with raw._read_file(target) as stream:evidence[relative]=json.load(stream,object_pairs_hook=dtu._unique_json)
    external=evidence['configs/external_repositories.lock.json']
    actual={r['repository_name']:r['commit_sha'] for r in external['repositories']}
    if lock['external_repository_commits']!={k:actual[k] for k in lock['external_repository_commits']}:
        raise ValueError('External provenance commits differ from existing lock')
    stage=evidence['configs/spearmint_stage2_evidence.json']
    if stage['commit_sha']!=actual['spearmint'] or stage['label_representation']!='hours' or not stage['label_interpretation_verified']:
        raise ValueError('Released Stage 2 labels must have verified unchanged hours')
    return lock


@dataclass
class RegistryResult:
    observations: list[Observation]
    aliases: list[dict[str, Any]]
    reports: dict[str, dict[str, Any]]
    inputs: list[dict[str, str]]


def _approved_rows(path: Path):
    with raw._read_file(path) as stream:
        if os.fstat(stream.fileno()).st_size>20*1024*1024:raise ValueError('Approved Jappe ledger exceeds bound')
        for index,line in enumerate(stream,1):
            if index>20000 or len(line)>65536:raise ValueError('Approved Jappe ledger record bound exceeded')
            yield json.loads(line,object_pairs_hook=dtu._unique_json)


def _provenance(source, refs: list[str], designation: str) -> dict[str, Any]:
    return {'registry_source_id':source.source_id,'publication_doi':source.publication_doi,
        'designation':designation,'scope':'publication/dataset-level; underlying individual measurement trace unverified','evidence_refs':refs}


def _aliases(rows: list[spearmint.StageRow], observations: list[Observation], *, columns: dict[str,str],
    mappings: tuple[dict[str,set[str]],dict[str,set[str]]], checksums: dict[str,str], artifact_paths: dict[str,str],
    mapping_sha256: str, external_commit: str) -> list[dict[str,Any]]:
    keys=defaultdict(list)
    for observation in observations:
        if observation.source_id=='netmhcstabpan_2016':keys[(observation.original_allele,observation.original_peptide)].append(observation)
    aliases=[];seen=set()
    for row in rows:
        mapping=spearmint.map_receptor(row,columns,*mappings,'pinned SPEARMINT receptor reference SHA256 '+mapping_sha256)
        if mapping['mapped_identifier'] is None:raise ValueError('Unresolved Stage 2 mapping at '+str(row.reference()))
        key=(mapping['mapped_identifier'],row.fields[columns['peptide']]);matches=keys.get(key,[])
        if len(matches)!=1:raise ValueError('Unmatched or ambiguous Stage 2 alias at '+str(row.reference()))
        observation=matches[0]
        if dtu.identifier_category(observation.original_allele) not in {'ordinary_hla_a','ordinary_hla_b'}:
            raise ValueError('Stage 2 ordinary-subset lineage cannot include C67S or unexpected identifiers')
        if row.numeric_issue or row.numeric_value is None or row.numeric_value!=Decimal(observation.parsed_measurement_decimal):
            raise ValueError('Stage 2 half-life does not agree exactly with DTU at '+str(row.reference()))
        if observation.observation_id in seen:raise ValueError('Duplicate alias within/across released splits')
        seen.add(observation.observation_id)
        split='validation' if row.split=='val' else row.split
        aliases.append({'schema_version':1,'source_id':'spearmint_stability_audit','source_file':artifact_paths['spearmint_'+row.split],
            'source_file_sha256':checksums['spearmint_'+row.split],
            'source_locator':{'csv_record_number':row.record_number,'source_line_start':row.line_start,'source_line_end':row.line_end},
            'split':split,'original_released_split_name':row.split,'original_peptide':row.fields[columns['peptide']],
            'original_allele':row.fields.get(columns['allele'],''),'original_measurement_text':row.fields[columns['label']],
            'original_fields':row.fields,'original_csv_cells':list(row.raw_cells),
            'measurement_type':'kinetic_half_life','measurement_unit':'hours','canonical_dtu_observation_id':observation.observation_id,
            'half_life_agreement':'exact_decimal_hours','mapping_evidence':mapping,'external_repository_commit':external_commit,
            'receptor_reference_sha256':mapping_sha256,'reference_sequence_length':len(row.fields.get(columns['sequence'],'')),
            'provenance_status':'derived_exact_DTU_representation_not_independent_experimental_source',
            'limitations':['Released split is not an independent external cohort.','Reference sequence completeness and upstream version remain unresolved; 181-residue strings are retained.']})
    ordinary={o.observation_id for o in observations if o.source_id=='netmhcstabpan_2016' and dtu.identifier_category(o.original_allele) in {'ordinary_hla_a','ordinary_hla_b'}}
    if seen!=ordinary:raise ValueError('Stage 2 alias coverage is not exactly the complete ordinary DTU subset')
    return aliases


def build(*, paths: StoragePaths | None = None, files: Mapping[str,str | Path] | None = None,
          lock_path: str | Path | None = None) -> RegistryResult:
    storage=resolve_paths() if paths is None else paths;lock=load_lock(lock_path,paths=storage)
    supplied=dict(files or {})
    if set(supplied)-set(INPUT_IDS):raise ValueError('Unknown registry input override')
    targets={};checksums={};inputs=[];metadata={e['input_id']:e for e in lock['artifacts']}
    # All required raw bytes and the approved ledger are gated before any row analysis.
    for key in INPUT_IDS:
        entry=metadata[key];root=storage.project_data_dir if entry['storage_area']=='data' else storage.project_runs_dir
        target=Path(supplied.get(key,root/entry['relative_path'])).expanduser().absolute()
        try:checksum=raw.sha256_file(target)
        except FileNotFoundError as error:raise ValueError('Missing required registry input: '+key) from error
        if checksum!=entry['sha256']:raise ValueError('Immutable registry input checksum mismatch: '+key)
        targets[key]=target;checksums[key]=checksum;inputs.append({'path':str(target),'sha256':checksum})
    registry=load_manifest(paths=storage);observations=[]
    primary=registry.get(raw.SOURCE_ID);structure=raw.inventory(targets['dtu'],source=primary)
    if not structure['header']['matches'] or structure['malformed_line_count']:
        raise ValueError('DTU header or numerical/structural row validation failed: '+raw.json_report(structure['malformed_lines']))
    for record in raw.iter_records(targets['dtu']):
        category=dtu.identifier_category(record.hla)
        flags=['c67s_annotated_allele' if category=='c67s_annotated_hla_b' else category]
        observations.append(make_observation(source_id=primary.source_id,sha256=checksums['dtu'],
            locator={'kind':'text_line','artifact':metadata['dtu']['relative_path'],'line_number':record.source_line_number},
            allele=record.hla,peptide=record.peptide,text=record.half_life_text,measurement_type='kinetic_half_life',unit='hours',context=DTU_CONTEXT,
            provenance=_provenance(primary,['configs/netmhcstabpan_2016_evidence.json'],'dataset_level_experimental_kinetic_stability'),
            origin=dtu.ROW_PROVENANCE,flags=flags,record_context={'original_source_line':record.raw_line}))
    jappe_source=registry.get('jappe_2020');seen_cells=set();auxiliary=Counter();associated=Counter()
    for row in _approved_rows(targets['jappe_ledger']):
        if row.get('row_kind')!='peptide_row':
            auxiliary[row.get('row_kind','unknown')]+=1;continue
        key=row.get('artifact_id');input_key={'supplementary_data_3':'jappe_data_3','supplementary_data_4':'jappe_data_4','supplementary_data_5':'jappe_data_5'}.get(key)
        if input_key is None or row.get('source_sha256')!=checksums[input_key]:raise ValueError('Approved Jappe row does not identify the immutable workbook')
        sheet,allele,context,schema=jappe.SCHEMAS[key]
        if row.get('worksheet')!=sheet or row.get('hla_restriction')!=allele:raise ValueError('Approved Jappe worksheet/restriction mismatch')
        candidates=0
        for field in row['fields']:
            role=field['category']
            if role not in {'publication_described_tm_measurement','paired_context_tm_measurement'}:
                associated[role]+=1;continue
            candidates+=1;cell=field.get('source_cell');parsed=jappe.parse_numeric(cell)
            coord=field['expected_coordinate'];identity=(input_key,sheet,coord)
            if identity in seen_cells:raise ValueError('Duplicate approved Tm source cell')
            seen_cells.add(identity)
            meaning=schema.get(field['original_header_text'])
            if not meaning or meaning[0]!=role or field['column']!=chr(65+list(schema).index(field['original_header_text'])):
                raise ValueError('Approved field role does not match the exact source header schema')
            expected_context=meaning[2] or context
            if (not cell or cell['coordinate']!=coord or coord!=field['column']+str(row['row_number'])
                or field['unit']!='degrees_Celsius' or field['assay_context']!=expected_context
                or parsed['state']!='valid' or field['numeric']['state']!='valid'
                or parsed['numeric_decimal']!=field['numeric']['numeric_decimal']):
                raise ValueError('Approved Tm cell, units, context or numerical provenance is invalid')
            observations.append(make_observation(source_id=jappe_source.source_id,sha256=checksums[input_key],
                locator={'kind':'workbook_cell','artifact':metadata[input_key]['relative_path'],'worksheet':sheet,'row_number':row['row_number'],'cell_coordinate':coord},
                allele=row['hla_restriction'],peptide=row['original_peptide_text'],text=cell['stored_value_text'],measurement_type='thermal_melting_temperature',unit='degC',
                context=field['assay_context'],provenance=_provenance(jappe_source,field['evidence_refs'],'publication_described_thermal_measurement_candidate'),
                origin=jappe.ROW_ORIGIN,flags=[*row['data_quality_flags'],*field['data_quality_flags']],
                record_context={'approved_ledger_sha256':checksums['jappe_ledger'],'approved_artifact_id':key,
                    'original_cells':row['cells'],'original_column_roles':[{'column':f['column'],'category':f['category']} for f in row['fields']],
                    'selected_original_header':field['original_header_text'],'approved_row_origin':row['row_origin']}))
        if candidates!=(2 if key=='supplementary_data_5' else 1):raise ValueError('Approved Jappe row has an unexpected number of raw Tm fields')
    evidence=spearmint.load_evidence(paths=storage);mapping=spearmint.read_mapping(targets['spearmint_mapping']);stage_rows=[]
    split_reports={}
    for split in spearmint.SPLITS:
        rows,report=spearmint.read_split(targets['spearmint_'+split],split,evidence['columns'])
        if report['malformed_rows'] or report['blank_lines']:raise ValueError('Invalid Stage 2 split structure')
        stage_rows.extend(rows);split_reports[split]=report
    aliases=_aliases(stage_rows,observations,columns=evidence['columns'],mappings=mapping,checksums=checksums,
        artifact_paths={key:entry['relative_path'] for key,entry in metadata.items()},mapping_sha256=checksums['spearmint_mapping'],external_commit=lock['external_repository_commits']['spearmint'])
    ids=[o.observation_id for o in observations]
    if len(ids)!=len(set(ids)):raise ValueError('Registry observation ID collision')
    kinetic=[o for o in observations if o.measurement_type=='kinetic_half_life'];thermal=[o for o in observations if o.measurement_type=='thermal_melting_temperature']
    c_rows=[o for o in thermal if o.original_allele=='HLA-C*04:01']
    observed={'dtu_observations':len(kinetic),'dtu_alleles':len({o.original_allele for o in kinetic}),
        'dtu_zero_values':sum('exact_zero' in o.data_quality_flags for o in kinetic),
        'dtu_c67s_observations':sum('c67s_annotated_allele' in o.data_quality_flags for o in kinetic),
        'dtu_ordinary_observations':sum(dtu.identifier_category(o.original_allele) in {'ordinary_hla_a','ordinary_hla_b'} for o in kinetic),
        'jappe_by_allele':dict(sorted(Counter(o.original_allele for o in thermal).items())),
        'jappe_C_unique_peptides':len({o.original_peptide for o in c_rows}),
        'jappe_observations':len(thermal),'total_observations':len(observations),
        'aliases_by_split':dict(sorted(Counter(a['split'] for a in aliases).items())),'total_aliases':len(aliases)}
    discrepancies={key:{'expected':value,'observed':observed.get(key)} for key,value in lock['expectations'].items() if observed.get(key)!=value}
    if discrepancies:raise ValueError('Registry count validation failed: '+raw.json_report(discrepancies))
    combinations=defaultdict(list)
    for observation in observations:combinations[(observation.original_allele,observation.original_peptide)].append(observation)
    repeated=[]
    for (allele,peptide),group in sorted(combinations.items()):
        distinct={(o.measurement_type,o.assay_context) for o in group}
        if len(distinct)>1:repeated.append({'original_allele':allele,'original_peptide':peptide,
            'observation_ids':[o.observation_id for o in group],'measurement_types_and_contexts':[{'measurement_type':t,'assay_context':c} for t,c in sorted(distinct)],
            'interpretation':'Distinct reported methods/contexts; experimental independence is not established; no aggregation.'})
    def counts(group):
        return {'records':len(group),'by_allele':dict(sorted(Counter(o.original_allele for o in group).items())),
            'by_assay_context':dict(sorted(Counter(o.assay_context for o in group).items())),
            'exact_zero_values':sum('exact_zero' in o.data_quality_flags for o in group),
            'zero_fraction':str(Decimal(sum('exact_zero' in o.data_quality_flags for o in group))/len(group)) if group else None,
            'by_allele_and_context':[{'original_allele':a,'assay_context':c,'records':n} for (a,c),n in sorted(Counter((o.original_allele,o.assay_context) for o in group).items())]}
    summary={'schema_version':SCHEMA_VERSION,'validation_status':'passed','observed_counts':observed,'expected_counts':lock['expectations'],
        'count_discrepancies':discrepancies,'unique_observation_ids':len(set(ids)),'missing_source_locators':0,'invalid_or_nonfinite_values':0,
        'aliases_complete':True,'alias_zero_values_by_split':dict(sorted(Counter(a['split'] for a in aliases if decimal_value(a['original_measurement_text'])==0).items())),
        'independent_experiment_count':None,'training_eligibility_status':'not_assessed','unmatched_aliases':0,'ambiguous_aliases':0,'duplicate_alias_assignments':0,
        'by_source':{s:counts([o for o in observations if o.source_id==s]) for s in sorted({o.source_id for o in observations})},
        'row_origin_status_counts':dict(sorted(Counter(o.row_origin_status for o in observations).items())),
        'data_quality_flag_counts':dict(sorted(Counter(f for o in observations for f in o.data_quality_flags).items())),
        'same_peptide_allele_across_distinct_method_or_context':repeated,'repeated_combination_count':len(repeated),
        'excluded_non_observation_field_counts':dict(sorted(associated.items())),'approved_non_observation_rows_retained_in_source_ledger':dict(sorted(auxiliary.items())),
        'observation_count_meaning':'Measurement-value records; independent experiment and training-eligibility counts are not established.'}
    source_evidence={'lock':lock,'input_artifacts':[{'input_id':key,'storage_area':metadata[key]['storage_area'],
        'relative_path':metadata[key]['relative_path'],'sha256':checksums[key]} for key in INPUT_IDS],
        'registry_source_ids':[s.source_id for s in registry.list_sources()],
        'SPEARMINT_reference_limitations':evidence['limitations'],
        'stage2_sequence_lengths':{s:split_reports[s]['mhc_sequence_lengths'] for s in spearmint.SPLITS},
        'not_read_this_task':['Historical original table unavailable','TLStab secondary CSV not an original measured input','Jappe Figure Source Data evidence captured in committed register only; workbook not read'],
        'publisher_checksum_status':'No local identity is represented as a publisher-provided checksum.'}
    reports={'registry_validation_summary.json':summary,'source_lineage_matrix.json':{'sources':lock['source_lineage'],'policy':lock['scientific_policy']},
        'measurement_type_summary.json':{t:{'unit':TYPE_UNITS[t],**counts([o for o in observations if o.measurement_type==t])} for t in TYPE_UNITS},
        'source_evidence_manifest.json':source_evidence}
    for item in inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Registry input changed during consolidation')
    return RegistryResult(observations,aliases,reports,inputs)


def jsonl(records) -> str:
    return ''.join(json.dumps(record.as_dict() if isinstance(record,Observation) else record,ensure_ascii=False,
        sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for record in records)


def write_registry(result: RegistryResult, output_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage=resolve_paths() if paths is None else paths;directory=Path(output_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Registry output requires an existing project run reports directory')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record all unchanged hashed registry inputs')
    payloads={name:raw.json_report(document) for name,document in result.reports.items()}
    payloads['canonical_observations.jsonl']=jsonl(result.observations);payloads['spearmint_stage2_aliases.jsonl']=jsonl(result.aliases)
    names=[*payloads,'registry_report_checksums.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            except FileNotFoundError:continue
            raise FileExistsError('Registry output already exists: '+name)
    for name,text in payloads.items():raw.write_text_report(directory/name,text,paths=storage)
    receipt={'reports':{name:raw.sha256_file(directory/name) for name in payloads},'inputs':result.inputs,'completion':'registry_complete; training_eligibility_not_assessed'}
    for item in result.inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Registry input changed before completion receipt')
    raw.write_report(directory/names[-1],receipt,paths=storage)
    return receipt
