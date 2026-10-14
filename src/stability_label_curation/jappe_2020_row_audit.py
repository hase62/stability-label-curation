"""Offline, lossless cell ledger and field-level Jappe provenance audit; no training export."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence
import unicodedata
from urllib.parse import urlsplit
import zipfile

from . import jappe_2020_sources as sources
from . import netmhcstabpan_2016 as raw
from . import dtu2016_source_audit as numeric
from . import run_manifest as runs
from .paths import StoragePaths, resolve_paths

EVIDENCE_CONFIG = 'configs/jappe_2020_row_evidence.json'
ROW_ORIGIN = 'publication_described_source_row_underlying_assay_traceability_unverified'
MAX_PHYSICAL_ROWS = 20000
MAX_PHYSICAL_CELLS = 100000
COMMON_HEADERS = {'Ligand':('peptide_sequence',None,None),
    'Tm':('publication_described_tm_measurement','degrees_Celsius',None),
    'Transformed Tm':('tm_derived_transformation','dimensionless',None),
    'Predicted binding affinity (NetMHCpan-4.0)':('predicted_binding_affinity','not_explicit_in_header',None)}
C_HEADERS = {'Ligand':COMMON_HEADERS['Ligand'],
    'Tm (A0201 data)':('paired_context_tm_measurement','degrees_Celsius','C1R-A*02:01'),
    'Tm (B0702 data)':('paired_context_tm_measurement','degrees_Celsius','C1R-B*07:02')}
SCHEMAS = {'supplementary_data_3':('A0201','HLA-A*02:01','C1R-A*02:01',COMMON_HEADERS),
    'supplementary_data_4':('B0702','HLA-B*07:02','C1R-B*07:02',COMMON_HEADERS),
    'supplementary_data_5':('C0401','HLA-C*04:01',None,C_HEADERS)}
TOLERANCES = ('1e-12','1e-9','1e-6','0.000005','0.00001','1e-3','0.01')


def load_evidence(path: str | Path | None = None, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    target = storage.repository_root/EVIDENCE_CONFIG if path is None else Path(path)
    with raw._read_file(target) as stream:
        evidence = json.load(stream,object_pairs_hook=numeric._unique_json)
    try:
        if (evidence['schema_version']!=1 or evidence['source_id']!=sources.SOURCE_ID
            or evidence['publication_doi']!='10.1038/s41467-020-20166-4'):
            raise ValueError('Invalid row evidence identity')
        if set(evidence['local_task15_reference_sha256']) != set(sources.ARTIFACT_IDS):
            raise ValueError('Evidence must pin all four inputs')
        for digest in evidence['local_task15_reference_sha256'].values():
            if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid local reference SHA256')
        ids = set()
        for item in evidence['evidence']:
            url = urlsplit(item['url'])
            if url.scheme!='https' or not url.hostname or url.username or url.password:
                raise ValueError('Evidence requires public HTTPS URLs')
            if item['evidence_id'] in ids:raise ValueError('Duplicate evidence ID')
            ids.add(item['evidence_id'])
            if any(not isinstance(item[k],str) or not item[k] for k in ('location','scope','statement','does_not_establish')):
                raise ValueError('Evidence location and limitations are required')
        if not {'tm_definition','cell_contexts','paired_c','counts','motif_equations','predictor_equation','synthetic_strategy','qc','publisher_descriptions'} <= ids:
            raise ValueError('Required source evidence is missing')
    except (KeyError,TypeError) as error:
        raise ValueError('Incomplete row evidence register') from error
    return evidence


def text_state(text: str | None) -> str:
    if text is None or text=='':return 'empty'
    if not text.strip():return 'blank'
    if all(c.isspace() or unicodedata.category(c)=='Cf' for c in text):return 'nonprinting'
    return 'text'


def cell_record(element: Any, strings: Sequence[str]) -> dict[str, Any]:
    """Preserve original fields, types, formulas and references before interpretation."""
    ns='{'+sources.MAIN+'}';kind=element.get('t','n');value=element.find(ns+'v')
    inline=element.find(ns+'is');formula=element.find(ns+'f');stored=None if value is None else value.text
    texts=[] if inline is None else [{'text':x.text,'attributes':dict(x.attrib)} for x in inline.iter(ns+'t')]
    decoded=stored;flags=[]
    if kind=='s':
        if stored is not None and re.fullmatch('[0-9]+',stored) and int(stored)<len(strings):decoded=strings[int(stored)]
        else:decoded=None;flags.append('invalid_shared_string_reference')
    elif kind=='inlineStr':decoded=''.join(x['text'] or '' for x in texts) if inline is not None else None
    unknown=[x.tag for x in element if x.tag not in {ns+'v',ns+'is',ns+'f'}]
    if unknown:flags.append('uninterpreted_cell_xml')
    return {'coordinate':element.get('r'),'attributes':dict(element.attrib),'explicit_storage_type':element.get('t'),
        'effective_storage_type':kind,'value_element_present':value is not None,'stored_value_text':stored,
        'inline_element_present':inline is not None,'inline_text_runs':texts,'decoded_text':decoded,
        'text_state':text_state(decoded),'formula_present':formula is not None,'formula_text':None if formula is None else formula.text,
        'formula_attributes':None if formula is None else dict(formula.attrib),'uninterpreted_children':unknown,'quality_flags':flags}


def parse_numeric(cell: dict[str, Any] | None) -> dict[str, Any]:
    if cell is None:return {'state':'missing','numeric_decimal':None,'cached_numeric_decimal':None}
    text=cell['decoded_text'];state=cell['text_state'];value=None
    if state=='text':
        try:
            parsed=raw.parse_record('x x '+(text or ''),1);value=parsed.half_life
            state=parsed.numeric_issue or 'valid'
        except ValueError:state='non_numeric'
        if value is not None and (len(value.as_tuple().digits)>128 or abs(value.as_tuple().exponent)>128):
            value=None;state='outside_numeric_inspection_bound'
    elif state=='nonprinting':state='nonprinting'
    if cell['quality_flags']:value=None;state='invalid_cell_structure'
    if cell['formula_present']:
        return {'state':'formula_not_evaluated','numeric_decimal':None,'cached_numeric_decimal':None if value is None else str(value)}
    if cell['effective_storage_type'] not in {'n'} and value is not None:
        return {'state':'numeric_text_or_unsupported_storage','numeric_decimal':None,'cached_numeric_decimal':None,'parsed_text_decimal':str(value)}
    return {'state':state,'numeric_decimal':None if value is None else str(value),'cached_numeric_decimal':None}


def read_rows(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reuse bounded package validation/mapping, traverse only physical XML rows."""
    structure=sources.workbook_inventory(path);rows=[]
    with raw._read_file(path) as stream,zipfile.ZipFile(stream) as archive:
        rels=sources._relationships(archive,sources._rels_part(structure['workbook_part']))
        strings=[]
        for rel in rels.values():
            if rel['Type']==sources.DOCREL+'/sharedStrings' and rel.get('TargetMode')!='External':
                root=sources._xml(archive,sources._part(structure['workbook_part'],rel['Target']))
                strings=[''.join(t.text or '' for t in x.iter('{'+sources.MAIN+'}t')) for x in root if x.tag=='{'+sources.MAIN+'}si']
        seen_rows=set();physical_cell_count=0
        for sheet in structure['sheets']:
            if sheet['status']!='structurally_inspected':raise ValueError('Unsupported worksheet structure')
            root=sources._xml(archive,sheet['worksheet_part']);data=root.find('{'+sources.MAIN+'}sheetData')
            if data is None:raise ValueError('Missing physical sheetData')
            for order,node in enumerate(data,1):
                if len(rows)>=MAX_PHYSICAL_ROWS:raise ValueError('Physical row inspection limit exceeded')
                if node.tag!='{'+sources.MAIN+'}row':raise ValueError('Unsupported child in sheetData')
                number=node.get('r')
                if not number or not re.fullmatch('[1-9][0-9]*',number) or int(number)>1048576:
                    raise ValueError('Invalid physical worksheet row reference')
                if (sheet['name'],number) in seen_rows:raise ValueError('Duplicate physical row reference')
                seen_rows.add((sheet['name'],number));cells=[];seen_cells=set()
                for element in node:
                    physical_cell_count+=1
                    if physical_cell_count>MAX_PHYSICAL_CELLS:raise ValueError('Physical cell inspection limit exceeded')
                    if element.tag!='{'+sources.MAIN+'}c':raise ValueError('Unsupported physical row child')
                    cell=cell_record(element,strings);ref=cell['coordinate']
                    match=re.fullmatch('([A-Z]+)([1-9][0-9]*)',ref or '')
                    if not match or int(match[2])!=int(number) or ref in seen_cells:
                        raise ValueError('Invalid, duplicate, or mismatched cell coordinate')
                    column=0
                    for char in match[1]:column=column*26+ord(char)-64
                    if column>16384:raise ValueError('Cell column exceeds Excel coordinate bound')
                    seen_cells.add(ref);cell['column']=match[1];cells.append(cell)
                rows.append({'worksheet':sheet['name'],'worksheet_part':sheet['worksheet_part'],'row_number':int(number),
                    'physical_xml_row_order':order,'row_attributes':dict(node.attrib),'cells':cells})
    if raw.sha256_file(path)!=structure['sha256']:raise ValueError('Source changed while reading physical cells')
    return structure,rows


def _value(field: dict[str, Any]) -> Decimal | None:
    text=field['numeric']['numeric_decimal'];return None if text is None else Decimal(text)


def distribution(values: Sequence[Decimal]) -> dict[str, Any]:
    if not values:return {'count':0,'minimum':None,'maximum':None,'median':None,'p05':None,'p95':None}
    return {'count':len(values),'minimum':str(min(values)),'maximum':str(max(values)),
        'median':str(numeric.quantile(values,50)),'p05':str(numeric.quantile(values,5)),'p95':str(numeric.quantile(values,95)),
        'quantile_convention':numeric.QUANTILE_CONVENTION,'exact_zero_count':sum(v==0 for v in values),
        'exact_one_count':sum(v==1 for v in values),
        'decimal_scale_counts':dict(sorted(Counter(str(-v.as_tuple().exponent) for v in values).items()))}


def pearson(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> dict[str, Any]:
    if len(xs)!=len(ys):raise ValueError('Paired arrays have different lengths')
    if len(xs)<2:return {'n':len(xs),'value':None,'reason':'fewer_than_two_complete_pairs'}
    with localcontext() as context:
        context.prec=50;mx=sum(xs)/len(xs);my=sum(ys)/len(ys)
        xx=sum((x-mx)**2 for x in xs);yy=sum((y-my)**2 for y in ys)
        if not xx or not yy:return {'n':len(xs),'value':None,'reason':'zero_variance'}
        r=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(xx*yy).sqrt()
        return {'n':len(xs),'value':str(r),'rounded_to_two_decimals':str(r.quantize(Decimal('.01'))),
            'method':'Two-pass centered sums, Decimal precision 50; all complete physical pairs; no outlier removal.'}


def transformation_comparison(pairs: Sequence[tuple[Decimal,Decimal]], population: Sequence[Decimal],
                              formula: str, *, round_to: str | None = None) -> dict[str, Any]:
    """Predeclared formula checks only; no fitting or rewriting published targets."""
    with localcontext() as context:
        context.prec=50
        if not pairs or not population or min(population)==max(population):
            return {'status':'not_computable_degenerate_or_missing_population','comparable_pairs':len(pairs)}
        lo,hi=min(population),max(population);median=numeric.quantile(population,50)
        errors=[];comparisons=[]
        for tm,target in pairs:
            u=(tm-lo)/(hi-lo)
            if formula=='A':expected=max(Decimal(0),min(Decimal(1),u+3*(u-(median-lo)/(hi-lo))))
            elif formula=='B':expected=Decimal('.5')*u+Decimal('.5')
            else:raise ValueError('Unknown transformation formula')
            if round_to is not None:expected=expected.quantize(Decimal(round_to),rounding=ROUND_HALF_EVEN)
            errors.append(abs(expected-target))
            comparisons.append({'comparable_pair_index':len(errors),'expected_decimal':str(expected),
                'original_target_decimal':str(target),'absolute_error':str(errors[-1])})
        return {'status':'numerically_compared','comparable_pairs':len(pairs),'population_count':len(population),
            'population_minimum':str(lo),'population_maximum':str(hi),'population_median':str(median),
            'rounding':'none' if round_to is None else 'Decimal HALF_EVEN to '+round_to+'; empirical candidate, not a documented publisher rule',
            'largest_error_examples':sorted(comparisons,key=lambda x:Decimal(x['absolute_error']),reverse=True)[:10],
            'absolute_errors':distribution(errors),'mean_absolute_error':str(sum(errors)/len(errors)),
            'counts_within_absolute_tolerance':{t:sum(error<=Decimal(t) for error in errors) for t in TOLERANCES}}


@dataclass
class AuditResult:
    reports: dict[str, dict[str, Any]]
    rows: list[dict[str, Any]]
    inputs: list[dict[str,str]]


def audit(*, paths: StoragePaths | None = None, files: dict[str,str | Path] | None = None,
          expected_sha256: dict[str,str] | None = None, evidence_path: str | Path | None = None) -> AuditResult:
    storage=resolve_paths() if paths is None else paths;document=sources.load_artifacts(paths=storage)
    evidence=load_evidence(evidence_path,paths=storage);overrides=files or {};expected=dict(evidence['local_task15_reference_sha256'])
    if any(k not in sources.ARTIFACT_IDS for k in overrides):raise ValueError('Unknown input override')
    for key,digest in (expected_sha256 or {}).items():
        if key not in overrides or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Fixture hash requires matching explicit file override')
        expected[key]=digest
    inputs=[];targets={}
    # Gate all four before any XML or scientific analysis.
    for entry in document['artifacts']:
        key=entry['artifact_id'];target=Path(overrides.get(key,storage.project_data_dir/sources.SOURCE_ID/entry['filename']))
        checksum=raw.sha256_file(target)
        if checksum!=expected[key]:raise ValueError('Immutable source checksum mismatch: '+key)
        targets[key]=target;inputs.append({'path':str(target.absolute()),'sha256':checksum})
    sources.validate_artifact(targets['descriptions'],'pdf')
    ledgers=[];schemas=[];summaries=[];structures=[];collections_by_id={};pairs_by_id={};pair_references={};population_by_id={}
    for key,(sheet_name,allele,assay_context,headers) in SCHEMAS.items():
        structure,physical=read_rows(targets[key]);structures.append({'artifact_id':key,'structure':structure})
        if [s['name'] for s in structure['sheets']]!=[sheet_name]:raise ValueError('Unexpected source sheet schema: '+key)
        candidates=[row for row in physical if set(headers)<= {c['decoded_text'] for c in row['cells'] if not c['formula_present']}]
        if len(candidates)!=1:raise ValueError('Missing or ambiguous exact source headers: '+key)
        header=candidates[0];mapped={};columns=[]
        for label,(category,unit,context) in headers.items():
            cells=[c for c in header['cells'] if c['decoded_text']==label and not c['formula_present']]
            if len(cells)!=1:raise ValueError('Ambiguous header field: '+label)
            cell=cells[0];references=['publisher_descriptions','cell_contexts']
            if category in {'publication_described_tm_measurement','paired_context_tm_measurement'}:references+=['tm_definition']
            if category=='paired_context_tm_measurement':references+=['paired_c']
            if category=='tm_derived_transformation':references+=['motif_equations','predictor_equation']
            semantic={'column':cell['column'],'header_coordinate':cell['coordinate'],'original_header_text':label,
                'category':category,'unit':unit,'assay_context':context or assay_context,'evidence_refs':references,
                'direct_header_evidence':{'coordinate':cell['coordinate'],'text':label,'artifact_sha256':structure['sha256']},
                'confidence':'exact_source_header_and_publication_context; underlying_assay_row_unverified'}
            mapped[cell['column']]=semantic;columns.append(semantic)
        ligand=next(c['column'] for c in columns if c['category']=='peptide_sequence');source_rows=[]
        for row in physical:
            cells={c['column']:c for c in row['cells']};pep_cell=cells.get(ligand);pep=None if pep_cell is None else pep_cell['decoded_text']
            if row['row_number']==header['row_number']:kind='header'
            elif pep_cell is not None and pep_cell['text_state']=='text' and not pep_cell['formula_present'] and not pep_cell['quality_flags'] and pep_cell['effective_storage_type'] in {'s','inlineStr','str'}:kind='peptide_row'
            elif not cells:kind='empty_physical_row'
            elif all(c['text_state'] in {'empty','blank','nonprinting'} and not c['formula_present'] and not c['quality_flags'] for c in cells.values()):kind='auxiliary_only_row'
            else:kind='unresolved_nonpeptide_row'
            flags=[];valid_peptide=kind=='peptide_row' and bool(re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',pep or ''))
            if kind=='peptide_row' and not valid_peptide:flags.append('noncanonical_peptide_text')
            if kind=='peptide_row' and not 8<=len(pep or '')<=11:flags.append('outside_published_peptide_length_range')
            fields=[]
            for column,meaning in mapped.items():
                if meaning['category']=='peptide_sequence':continue
                cell=cells.get(column);parsed=parse_numeric(cell);field_flags=[];value=parsed['numeric_decimal']
                if kind!='peptide_row':field_flags.append('not_a_peptide_row')
                if parsed['state']!='valid':field_flags.append(parsed['state'])
                if value is not None and meaning['unit']=='degrees_Celsius' and not Decimal(37)<=Decimal(value)<=Decimal(73):field_flags.append('outside_assay_temperature_range_37_73')
                if value is not None and meaning['category']=='tm_derived_transformation' and not 0<=Decimal(value)<=1:field_flags.append('outside_transformed_unit_interval')
                fields.append({**meaning,'expected_coordinate':column+str(row['row_number']),'source_cell':cell,'numeric':parsed,
                    'provenance_category':meaning['category'],'row_assay_traceability':'unverified','data_quality_flags':field_flags})
            extras=[]
            for column,cell in cells.items():
                if column not in mapped:
                    extras.append({'source_cell':cell,'provenance_category':'auxiliary_metadata' if cell['text_state'] in {'empty','blank','nonprinting'} and not cell['formula_present'] and not cell['quality_flags'] else 'unknown'})
            record={'artifact_id':key,'workbook_name':targets[key].name,'source_sha256':structure['sha256'],**row,
                'row_kind':kind,'original_peptide_text':pep,'valid_canonical_peptide_text':valid_peptide,'hla_restriction':allele,
                'assay_context':assay_context,'fields':fields,'auxiliary_or_unknown_cells':extras,'data_quality_flags':flags,
                'row_origin':ROW_ORIGIN,'training_inclusion_status':'not_assessed'}
            source_rows.append(record)
        data=[r for r in source_rows if r['row_kind']=='peptide_row'];by_peptide=defaultdict(list)
        for row in data:by_peptide[row['original_peptide_text']].append(row)
        duplicates={p:[r['row_number'] for r in rows] for p,rows in by_peptide.items() if len(rows)>1}
        for row in data:
            if row['original_peptide_text'] in duplicates:row['data_quality_flags'].append('duplicate_peptide_key')
        numeric_fields={}
        for column,meaning in mapped.items():
            if meaning['category']=='peptide_sequence':continue
            values=[];states=Counter();flagged=[]
            for row in data:
                field=next(f for f in row['fields'] if f['column']==column);states[field['numeric']['state']]+=1
                if _value(field) is not None:values.append(_value(field))
                if field['data_quality_flags']:flagged.append({'row_number':row['row_number'],'coordinate':field['expected_coordinate'],'flags':field['data_quality_flags']})
            numeric_fields[meaning['original_header_text']]={'category':meaning['category'],'unit':meaning['unit'],
                'assay_context':meaning['assay_context'],'numeric_states':dict(sorted(states.items())),
                'valid_numeric_cell_count':len(values),'distribution':distribution(values),'flagged_source_fields':flagged}
            if meaning['category']=='tm_derived_transformation':
                with localcontext() as context:
                    context.prec=270
                    numeric_fields[meaning['original_header_text']]['empirical_decimal_grid']={
                        'quantum':'0.00001','absolute_tolerance':'1e-12','tested_count':len(values),
                        'matching_count':sum(abs(v-v.quantize(Decimal('.00001'),rounding=ROUND_HALF_EVEN))<=Decimal('1e-12') for v in values),
                        'interpretation':'Numerical grid observation; not proof of publisher rounding or historical precision.'}
        summary={'artifact_id':key,'hla_restriction':allele,'physical_rows':len(physical),'row_kind_counts':dict(sorted(Counter(r['row_kind'] for r in source_rows).items())),
            'peptide_rows':len(data),'valid_canonical_peptide_rows':sum(r['valid_canonical_peptide_text'] for r in data),'distinct_original_peptide_strings':len(by_peptide),
            'canonical_peptide_rows_with_valid_tm':sum(r['valid_canonical_peptide_text'] and any(f['unit']=='degrees_Celsius' and _value(f) is not None for f in r['fields']) for r in data),
            'duplicate_peptide_keys':duplicates,'duplicate_extra_rows':sum(len(rows)-1 for rows in by_peptide.values()),
            'peptide_length_distribution':dict(sorted(Counter(str(len(r['original_peptide_text'])) for r in data).items())),
            'numeric_fields':numeric_fields,'row_origin':ROW_ORIGIN,'explicit_synthetic_training_targets_identified':0,
            'synthetic_absence_certified':False,'assay_temperature_plausibility_reference_Celsius':['37','73']}
        unmapped=[]
        for column in sorted({c['column'] for r in source_rows for c in r['cells']} - set(mapped)):
            contents=[c for r in source_rows for c in r['cells'] if c['column']==column]
            auxiliary=all(c['text_state'] in {'empty','blank','nonprinting'} and not c['formula_present'] and not c['quality_flags'] for c in contents)
            header_cell=next((c for c in header['cells'] if c['column']==column),None)
            unmapped.append({'column':column,'header_coordinate':None if header_cell is None else header_cell['coordinate'],
                'original_header_text':None if header_cell is None else header_cell['decoded_text'],
                'category':'auxiliary_metadata' if auxiliary else 'unknown','source_cell_references':[c['coordinate'] for c in contents],
                'evidence':'Direct inspection: blank/nonprinting/empty-only physical contents' if auxiliary else 'Unmapped content retained without scientific inference'})
        schemas.append({'artifact_id':key,'workbook_name':targets[key].name,'sha256':structure['sha256'],'worksheet':sheet_name,
            'header_row_number':header['row_number'],'columns':columns,'unmapped_columns':unmapped,
            'block_status':'one identified exact-header block; auxiliary/unmapped cells retained; no table-range expansion'})
        summaries.append(summary);ledgers.extend(source_rows);collections_by_id[key]=data
        tms=[_value(f) for row in data for f in row['fields'] if f['unit']=='degrees_Celsius' and _value(f) is not None]
        population_by_id[key]=tms
        if key!='supplementary_data_5':
            pairs=[];refs=[]
            for row in data:
                fs={f['category']:f for f in row['fields']};tm=_value(fs['publication_described_tm_measurement']);trans=_value(fs['tm_derived_transformation'])
                if tm is not None and trans is not None:
                    pairs.append((tm,trans));refs.append({'row_number':row['row_number'],
                        'tm_coordinate':fs['publication_described_tm_measurement']['expected_coordinate'],
                        'transformed_coordinate':fs['tm_derived_transformation']['expected_coordinate']})
            pairs_by_id[key]=pairs;pair_references[key]=refs
    transformed={};ab=population_by_id['supplementary_data_3']+population_by_id['supplementary_data_4'];all_values=ab+population_by_id['supplementary_data_5']
    for key,pairs in pairs_by_id.items():
        trials=[]
        for population_name,population in [('same_workbook_valid_tm_cells',population_by_id[key]),('pooled_acquired_A_B',ab),('pooled_acquired_A_B_and_both_C_contexts',all_values)]:
            for formula in ('A','B'):
                for rounding in (None,'0.00001'):
                    comparison=transformation_comparison(pairs,population,formula,round_to=rounding)
                    for example in comparison.get('largest_error_examples',[]):example.update(pair_references[key][example['comparable_pair_index']-1])
                    trials.append({'population_assumption':population_name,'formula':formula,**comparison})
        transformed[key]={'candidates':trials,'generating_procedure_status':'historical implementation unverified; numerical agreement is supporting evidence only',
            'population_limit':'Acquired C pairs are incomplete relative to Fig. 2e; pooled values are not a certified Tm_all population.',
            'rounding_limit':'No publisher rounding rule verified; 5-decimal HALF_EVEN is an explicit empirical candidate.'}
    c_rows=collections_by_id['supplementary_data_5'];xs=[];ys=[];complete=[];first_only=[];second_only=[];neither=[]
    for row in c_rows:
        x,y=[_value(f) for f in row['fields']]
        if x is not None and y is not None:xs.append(x);ys.append(y);complete.append(row['row_number'])
        elif x is not None:first_only.append(row['row_number'])
        elif y is not None:second_only.append(row['row_number'])
        else:neither.append(row['row_number'])
    with localcontext() as context:
        context.prec=50;differences=[x-y for x,y in zip(xs,ys)]
        difference_summary=distribution(differences)
        if differences:
            mean=sum(differences)/len(differences)
            difference_summary.update(mean=str(mean),population_standard_deviation=str((sum((d-mean)**2 for d in differences)/len(differences)).sqrt()))
    c_report={'hla_restriction':'HLA-C*04:01','context_order':['C1R-A*02:01','C1R-B*07:02'],'peptide_rows':len(c_rows),
        'valid_first_context':len(complete)+len(first_only),'valid_second_context':len(complete)+len(second_only),
        'complete_pairs':len(complete),'complete_pair_source_rows':complete,'first_only_source_rows':first_only,'second_only_source_rows':second_only,
        'neither_valid_source_rows':neither,'distinct_context_numeric_fields':2*len(complete)+len(first_only)+len(second_only),
        'paired_differences_first_minus_second_Celsius':difference_summary,'absolute_paired_differences_Celsius':distribution([abs(d) for d in differences]),
        'pearson_all_complete_pairs':pearson(xs,ys),'publication_pcc':'0.78','publication_outlier_removed_pcc':'0.87',
        'outliers_removed':False,'independent_replicate_status':'not established','same_analyzed_population_as_figure_2c':'Source citation, layout, and numerical agreement support correspondence; raw figure point identities not independently verified.',
        '359_reconciliation':'unresolved; Data 5 is cited for both-context comparison, while Fig. 2e is a broader distribution. No missing rows fabricated.',
        'evidence_refs':['cell_contexts','paired_c','counts','publisher_descriptions']}
    expected_counts=document['published_expectations'];reconcile=[]
    for s in summaries:
        expected_count=expected_counts[s['hla_restriction']]
        reconcile.append({'artifact_id':s['artifact_id'],'published_peptide_reference':expected_count,'local_peptide_rows':s['peptide_rows'],
            'local_unique_peptides':s['distinct_original_peptide_strings'],'local_canonical_peptides_with_numeric_tm':s['canonical_peptide_rows_with_valid_tm'],
            'count_match':s['canonical_peptide_rows_with_valid_tm']==expected_count,
            'scope':'A/B named dataset counts' if s['artifact_id']!='supplementary_data_5' else 'Paired C table versus broader Fig. 2e count; same population not established'})
    reports={'jappe_row_schema.json':{'sources':schemas,'structural_context':structures},
        'jappe_field_provenance.json':{'column_mappings':schemas,'underlying_ms_evidence_per_row':'not independently verified',
            'synthetic_strategy_evidence':'synthetic_strategy','explicit_synthetic_targets_identified':0,'training_eligibility':'not assessed'},
        'jappe_measurement_inventory.json':{'sources':summaries,'units_policy':'Tm Celsius, derived dimensionless, prediction header units unresolved; no kinetic conversion'},
        'jappe_transformation_audit.json':transformed,'jappe_hlac_context_audit.json':c_report,
        'jappe_publication_reconciliation.json':{'sources':reconcile,'C359_status':'not reconstructed from available paired table','later_artifact_candidate':evidence['later_artifact_candidate']},
        'jappe_evidence_register.json':evidence}
    for item in inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Input changed during audit')
    return AuditResult(reports,ledgers,inputs)


def row_jsonl(rows: Sequence[dict[str, Any]]) -> str:
    return ''.join(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def write_reports(result: AuditResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str,Any]:
    storage=resolve_paths() if paths is None else paths;directory=Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Reports require an existing project run reports directory')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record every unchanged hashed input')
    names=[*result.reports,'jappe_rows.jsonl','jappe_audit_checksums.json']
    with raw._directory(directory) as descriptor:
        for name in names:
            try:os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            except FileNotFoundError:continue
            raise FileExistsError('Audit report already exists: '+name)
    for name,document in result.reports.items():raw.write_report(directory/name,document,paths=storage)
    raw.write_text_report(directory/'jappe_rows.jsonl',row_jsonl(result.rows),paths=storage)
    checksums={'reports':{name:raw.sha256_file(directory/name) for name in names[:-1]},'inputs':result.inputs,
        'physical_rows_preserved':len(result.rows),'completion':'field_semantics_audit_complete; training_eligibility_not_assessed'}
    for item in result.inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Input changed before completion receipt')
    raw.write_report(directory/names[-1],checksums,paths=storage)
    return checksums
