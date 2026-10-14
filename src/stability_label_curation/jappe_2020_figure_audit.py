"""Bounded publisher Source Data acquisition and offline figure provenance audit."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import ssl
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from . import jappe_2020_sources as sources
from . import jappe_2020_row_audit as cells
from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

FILENAME = '41467_2020_20166_MOESM11_ESM.xlsx'
URL = 'https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/' + FILENAME
ARTICLE = 'https://www.nature.com/articles/s41467-020-20166-4'
MAX_BYTES = 5 * 1024 * 1024
CONFIG = 'configs/jappe_2020_figure_evidence.json'


class ArticleRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_article_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_article_url(url: str) -> None:
    p = urlsplit(url)
    if (p.scheme != 'https' or p.hostname != 'www.nature.com' or p.port not in {None, 443}
        or p.path != '/articles/s41467-020-20166-4' or p.username or p.password or p.fragment
        or any(c.isspace() for c in url)):
        raise ValueError('Article request escaped the official page')


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.current = None
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.current = [dict(attrs).get('href', ''), '']
    def handle_data(self, data):
        if self.current is not None: self.current[1] += data
    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.links.append(self.current); self.current = None


def verify_link(html: str, final_article_url: str = ARTICLE) -> dict[str, Any]:
    validate_article_url(final_article_url)
    parser = Links(); parser.feed(html)
    matches = [(urljoin(final_article_url, href), ' '.join(label.split()))
               for href, label in parser.links if FILENAME in href]
    if not matches or any(url != URL or 'source data' not in label.lower() for url, label in matches):
        raise ValueError('Official Source Data hyperlink is missing or does not match the authorized artifact')
    sources.allowed_url(URL, FILENAME)
    return {'official_article_url': ARTICLE, 'resolved_article_url': final_article_url,
            'source_hyperlink_url': URL, 'anchor_labels': sorted(set(label for _, label in matches)),
            'verification': 'exact authorized link and Source Data anchor in official article HTML'}


def fetch(*, paths: StoragePaths | None = None, timeout: float = 30) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    registry = load_manifest(paths=storage).get('jappe_2020')
    if registry.landing_url != ARTICLE: raise ValueError('Registry article mismatch')
    if not math.isfinite(timeout) or not 0 < timeout <= 120: raise ValueError('Timeout must be finite, 0–120 seconds')
    opener = build_opener(ArticleRedirects(), HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(ARTICLE + '?error=cookies_not_supported', headers={'Accept-Encoding': 'identity'}), timeout=timeout) as response:
        validate_article_url(response.geturl())
        if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Expected HTTP 200 identity article response')
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024: raise ValueError('Article HTML exceeds bounded link inspection')
        link = verify_link(body.decode('utf-8'), response.geturl())
    entry = {'artifact_id': 'figure_source_data', 'filename': FILENAME, 'format': 'xlsx',
             'source_hyperlink_url': URL, 'role': 'Publisher figure Source Data; cell-level provenance requires audit'}
    receipt = sources._fetch_one(entry, {'official_article_url': ARTICLE}, storage, timeout, [0], max_artifact_bytes=MAX_BYTES)
    receipt['official_link_verification'] = link
    receipt['artifact_byte_limit'] = MAX_BYTES
    return receipt


# Exact observed headers; no guessed Figure 2 table format is implemented.
SCHEMAS = {
    'Suppl Fig 3a': ('HLA-A*02:01', 'C1R-A*02:01', 'peak_area'),
    'Suppl Fig 3b': ('HLA-B*07:02', 'C1R-B*07:02', 'peak_area'),
    'Suppl Fig 3c': ('HLA-C*04:01', 'C1R-A*02:01', 'peak_area'),
    'Suppl Fig 4': ('HLA-A*02:01', 'C1R-A*02:01', 'kinetic_and_thermal'),
    'Suppl Fig 5a': ('HLA-A*02:01', 'C1R-A*02:01', 'tm_and_peak_area'),
    'Suppl Fig 5b': ('HLA-B*07:02', 'C1R-B*07:02', 'tm_and_peak_area'),
}
ARTIFACT_FOR_ALLELE = {'HLA-A*02:01': 'supplementary_data_3', 'HLA-B*07:02': 'supplementary_data_4', 'HLA-C*04:01': 'supplementary_data_5'}


def load_evidence(path: str | Path | None = None, *, paths: StoragePaths) -> dict[str, Any]:
    with raw._read_file(path or paths.repository_root / CONFIG) as stream:
        evidence = json.load(stream)
    source = load_manifest(paths=paths).get('jappe_2020')
    if (evidence.get('schema_version') != 1 or evidence.get('source_id') != source.source_id
        or evidence.get('publication_doi') != source.publication_doi or evidence.get('official_article_url') != source.landing_url
        or evidence.get('filename') != FILENAME or evidence.get('source_hyperlink_url') != URL
        or evidence.get('publisher_sha256') is not None):
        raise ValueError('Evidence does not agree with authorized source metadata')
    for digest in [evidence.get('local_source_data_sha256'), *[evidence['approved_task16'].get(k) for k in ('ledger_sha256', 'hlac_report_sha256')]]:
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest): raise ValueError('Invalid local checksum evidence')
    seen = set()
    for item in evidence.get('evidence', []):
        if (item.get('id') in seen or item.get('url') != ARTICLE
            or not all(isinstance(item.get(k), str) and item[k] for k in ('id','location','statement','scope','does_not_establish'))):
            raise ValueError('Invalid or duplicate evidence item')
        seen.add(item['id'])
    if not {'source_data_link','paired_c','fig2_distribution','peak_areas','supp5'} <= seen:
        raise ValueError('Required evidence missing')
    return evidence


def _read_approved_ledger(path: Path) -> list[dict[str, Any]]:
    records = []
    with raw._read_file(path) as stream:
        if stream.seek(0, 2) > 20 * 1024 * 1024: raise ValueError('Approved ledger exceeds inspection bound')
        stream.seek(0)
        for line in stream:
            if len(line) > 65536 or len(records) >= 10000: raise ValueError('Approved ledger record bound exceeded')
            row = json.loads(line)
            if not isinstance(row, dict) or not all(k in row for k in ('artifact_id','row_kind','row_number','fields','original_peptide_text')):
                raise ValueError('Malformed approved ledger row')
            records.append(row)
    return records


def _number(cell: dict[str, Any] | None) -> Decimal | None:
    value = cells.parse_numeric(cell)['numeric_decimal']
    return None if value is None else Decimal(value)


def strict_comparison(records: list[dict[str, Any]], approved: list[dict[str, Any]], allele: str) -> dict[str, Any]:
    """Exact peptide identifiers within the source-supported allele; duplicate keys remain ambiguous."""
    reference = defaultdict(list)
    for row in approved:
        if row['row_kind'] == 'peptide_row' and row['artifact_id'] == ARTIFACT_FOR_ALLELE[allele]:
            reference[row['original_peptide_text']].append(row)
    source = defaultdict(list)
    for row in records: source[row['original_peptide_text']].append(row)
    matched = []; absent = []; ambiguous = []; errors = []; comparisons = []
    for row in records:
        peptide = row['original_peptide_text']; targets = reference.get(peptide, [])
        if not targets: absent.append(row['row_number']); continue
        if len(targets) != 1 or len(source[peptide]) != 1: ambiguous.append(row['row_number']); continue
        matched.append(peptide)
        target = targets[0]
        tm = next((f for f in row['scientific_fields'] if f['category'] == 'publication_described_tm_measurement'), None)
        prior_tm = next((f for f in target['fields'] if f['category'] == 'publication_described_tm_measurement'), None)
        if tm is not None and prior_tm is not None and tm['numeric']['numeric_decimal'] is not None and prior_tm['numeric']['numeric_decimal'] is not None:
            x, y = Decimal(tm['numeric']['numeric_decimal']), Decimal(prior_tm['numeric']['numeric_decimal'])
            with localcontext() as context:
                context.prec = 50; error = abs(x-y)
            errors.append(error); comparisons.append({'source_row':row['row_number'],'approved_row':target['row_number'],
                'peptide':peptide,'source_tm_decimal':str(x),'approved_tm_decimal':str(y),'absolute_error_Celsius':str(error)})
    return {'match_rule':'Exact original peptide text with separately source-supported HLA identity; no normalization',
        'matched_unique_peptides':len(set(matched)), 'matched_peptide_identifiers':matched,
        'source_unmatched_row_numbers':absent,'ambiguous_row_numbers':ambiguous,
        'approved_peptides_not_in_source_block':sorted(set(reference)-set(source)),
        'measurement_comparisons':comparisons,'absolute_tm_errors_Celsius':cells.distribution(errors),
        'counts_within_absolute_tm_tolerance':{t:sum(e <= Decimal(t) for e in errors) for t in ('0','1e-12','1e-5')},
        'provenance_limit':'Agreement does not establish independent experiments; raw peak areas are not Tm values.'}


def audit(*, paths: StoragePaths | None = None, source_path: str | Path | None = None,
          ledger_path: str | Path | None = None, context_report_path: str | Path | None = None,
          expected_sha256: dict[str, str] | None = None, evidence_path: str | Path | None = None) -> cells.AuditResult:
    storage = resolve_paths() if paths is None else paths
    evidence = load_evidence(evidence_path, paths=storage)
    prior = storage.project_runs_dir / evidence['approved_task16']['run_id'] / 'reports'
    overrides = {'source_data': source_path, 'approved_ledger':ledger_path, 'approved_context_report':context_report_path}
    targets = {'source_data':Path(source_path or storage.project_data_dir / 'jappe_2020' / FILENAME),
        'approved_ledger':Path(ledger_path or prior / 'jappe_rows.jsonl'),
        'approved_context_report':Path(context_report_path or prior / 'jappe_hlac_context_audit.json')}
    hashes = {'source_data':evidence['local_source_data_sha256'], 'approved_ledger':evidence['approved_task16']['ledger_sha256'],
              'approved_context_report':evidence['approved_task16']['hlac_report_sha256']}
    for key, digest in (expected_sha256 or {}).items():
        if key not in overrides or overrides[key] is None or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Fixture checksum requires matching explicit path override')
        hashes[key] = digest
    inputs = []
    for key, path in targets.items():
        checksum = raw.sha256_file(path)
        if checksum != hashes[key]: raise ValueError('Immutable input checksum mismatch: ' + key)
        inputs.append({'path':str(path.expanduser().absolute()),'sha256':checksum})
    with raw._read_file(targets['source_data']) as stream:
        if stream.seek(0,2) > MAX_BYTES: raise ValueError('Source Data exceeds 5 MiB cap')
    structure, physical = cells.read_rows(targets['source_data'])
    approved = _read_approved_ledger(targets['approved_ledger'])
    with raw._read_file(targets['approved_context_report']) as stream:
        if stream.seek(0,2) > 1024*1024: raise ValueError('Approved context report exceeds bound')
        stream.seek(0); approved_context = json.load(stream)
    if not all(k in approved_context for k in ('peptide_rows','complete_pairs','pearson_all_complete_pairs')):
        raise ValueError('Malformed approved context report')
    rows = []; summaries = []; by_sheet = {}
    for sheet in structure['sheets']:
        name = sheet['name']; original = [r for r in physical if r['worksheet'] == name]
        schema = SCHEMAS.get(name); lookup = {r['row_number']: {c['column']:c for c in r['cells']} for r in original}
        headers = {}; field_roles = {}; context = None; allele = None
        if schema is not None:
            allele, context, kind = schema
            expected_headers = ['Temperature'] if kind == 'peak_area' else (['Peptide','t1/2','Tm'] if kind == 'kinetic_and_thermal' else ['Peptide','Tm','Median peak area at 37℃'])
            observed = [lookup.get(3, {}).get(chr(65+i), {}).get('decoded_text') for i in range(len(expected_headers))]
            if observed != expected_headers: raise ValueError('Unexpected exact block headers: ' + name)
            if kind == 'peak_area':
                if lookup.get(4,{}).get('A',{}).get('decoded_text') != 'Peptide': raise ValueError('Missing raw peak-area peptide header')
                temperature = None
                for column, header in lookup[4].items():
                    if column == 'A': continue
                    if _number(lookup[3].get(column)) is not None: temperature = lookup[3][column]['decoded_text']
                    if temperature is None or not re.fullmatch('Replicate [123] ', header['decoded_text'] or ''):
                        raise ValueError('Unknown temperature/replicate peak-area header')
                    headers[column] = {'header_coordinate':header['coordinate'],'original_header_text':header['decoded_text'],
                        'temperature_Celsius_text':temperature,'category':'chromatographic_peak_area','unit':'peak_area_arbitrary_instrument_units',
                        'assay_context':context,'evidence_refs':['peak_areas']}
                field_roles = headers; first_data_row=5
            else:
                first_data_row=4
                roles = [('kinetic_half_life','hours_publication_context')] if kind == 'kinetic_and_thermal' else [('publication_described_tm_measurement','degrees_Celsius')]
                roles += [('publication_described_tm_measurement','degrees_Celsius')] if kind == 'kinetic_and_thermal' else [('median_chromatographic_peak_area','peak_area_arbitrary_instrument_units')]
                for column,(category,unit) in zip(('B','C'),roles):
                    header = lookup[3][column]
                    field_roles[column]={'header_coordinate':header['coordinate'],'original_header_text':header['decoded_text'],
                        'category':category,'unit':unit,'assay_context':context,'evidence_refs':['supp5'] if kind=='tm_and_peak_area' else ['kinetic_comparison']}
        block=[]
        for row in original:
            cs={c['column']:c for c in row['cells']};pep=cs.get('A',{}).get('decoded_text');fields=[]
            is_data=(schema is not None and row['row_number']>=first_data_row and isinstance(pep,str)
                and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{8,11}',pep) is not None and not cs['A']['formula_present']
                and cs['A']['effective_storage_type'] in {'s','inlineStr','str'} and not cs['A']['quality_flags'])
            if is_data: row_kind='peptide_identifiable_source_block_row'
            elif not cs:row_kind='empty_physical_row'
            elif all(c['text_state'] in {'empty','blank','nonprinting'} and not c['formula_present'] for c in cs.values()):row_kind='auxiliary_physical_row'
            elif schema is not None and row['row_number'] < first_data_row:row_kind='title_or_header_row'
            else:row_kind='unresolved_physical_row'
            if is_data:
                for column,role in field_roles.items():
                    cell=cs.get(column)
                    fields.append({**role,'coordinate':column+str(row['row_number']),'source_cell':cell,'numeric':cells.parse_numeric(cell),
                        'row_assay_traceability':'not_independently_verified'})
            extras=[c for c in row['cells'] if not is_data or c['column'] not in {'A',*field_roles}]
            record={**row,'source_sha256':structure['sha256'],'artifact_id':'figure_source_data','row_kind':row_kind,
                'original_peptide_text':pep if is_data else None,'hla_restriction':allele if is_data else None,
                'assay_context':context if is_data else None,'scientific_fields':fields,'uninterpreted_or_auxiliary_cells':extras,
                'training_inclusion_status':'not_assessed'}
            rows.append(record)
            if is_data:block.append(record)
        by_sheet[name]=block
        summary={'worksheet':name,'worksheet_part':sheet['worksheet_part'],'visibility':sheet['visibility'],
            'declared_dimension':sheet['declared_dimension'],'physical_rows':len(original),'physical_cells':sum(len(r['cells']) for r in original),
            'original_title':lookup.get(1,{}).get('A',{}).get('decoded_text'),
            'header_cells': [{'coordinate':c['coordinate'],'text':c['decoded_text']} for n in (3,4) for c in lookup.get(n,{}).values() if c['decoded_text'] is not None],
            'peptide_identifiable_rows':len(block),'distinct_peptides':len(set(r['original_peptide_text'] for r in block)),
            'duplicate_peptide_keys':{p:n for p,n in sorted(Counter(r['original_peptide_text'] for r in block).items()) if n>1},
            'row_kind_counts':dict(sorted(Counter(r['row_kind'] for r in rows if r['worksheet']==name).items())),
            'column_semantics':field_roles,'numeric_states':dict(sorted(Counter(f['numeric']['state'] for r in block for f in r['scientific_fields']).items())),
            'unknown_cells': [{'row_number':r['row_number'],'cells':r['uninterpreted_or_auxiliary_cells']} for r in rows if r['worksheet']==name and r['row_kind']=='unresolved_physical_row']}
        numeric_by_category = defaultdict(list)
        for record in block:
            for field in record['scientific_fields']:
                if field['numeric']['numeric_decimal'] is not None:
                    numeric_by_category[field['category']].append(Decimal(field['numeric']['numeric_decimal']))
        summary['numeric_distributions_by_category'] = {k:cells.distribution(v) for k,v in sorted(numeric_by_category.items())}
        summaries.append(summary)
    comparisons={name:strict_comparison(by_sheet.get(name,[]),approved,allele)
        for name,allele in [('Suppl Fig 3c','HLA-C*04:01'),('Suppl Fig 5a','HLA-A*02:01'),('Suppl Fig 5b','HLA-B*07:02')]}
    # This source has no Figure 2 block. Unknown additional sheets/cells are retained, never guessed into it.
    unknown_sheets=[s['name'] for s in structure['sheets'] if s['name'] not in SCHEMAS]
    figure2={'published_expectations':{'HLA-A*02:01':1094,'HLA-B*07:02':1354,'HLA-C*04:01':359},
        'source_data_figure_2e_c_values_recovered':0,'figure_2_source_block_identified':False,
        'assessment':'No Figure 2 table, aggregate table, or anonymous Tm distribution identified in the six observed worksheets.',
        'unrecognized_sheets_requiring_review':unknown_sheets,
        '359_population_status':'not_recovered_from_authorized_artifact; not a zero-sized biological population',
        '359_peptide_identity_status':'not_recovered','359_assay_context_status':'unresolved',
        'figure_2c':{'approved_task16_result_reused_without_reanalysis':approved_context,
            'source_data_has_paired_context_tm_block':False,'outlier_removed_correlation_reproduced':False},
        'figure_2d_e':{'A_B_arrays':'Peptide-identifiable Tm arrays available in Suppl Fig 5a/b and approved Task 1.6 ledger; numerical agreement reported separately.',
            'full_C_distribution_reproduced':False,'interallelic_tests_reproduced':False,
            'histogram_bins_and_plotting_conventions':'not recovered from workbook; no newly invented bins'},
        'C_peak_area_subset':comparisons['Suppl Fig 3c'],
        'scientific_limit':'12 identifiable C peak-area examples do not supply 359 Tm values; no fitting, averaging, or independent experiment inference.',
        'evidence_refs':['paired_c','fig2_distribution','source_data_link']}
    reports={'jappe_figure_source_inventory.json':{'source_id':'jappe_2020','structure':structure,'worksheet_blocks':summaries},
        'jappe_figure_population_reconciliation.json':figure2,
        'jappe_figure_value_comparison.json':comparisons,'jappe_figure_evidence_register.json':evidence}
    for item in inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Input changed during figure audit')
    return cells.AuditResult(reports,rows,inputs)


def write_reports(result: cells.AuditResult, reports_dir: str | Path, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage=resolve_paths() if paths is None else paths; directory=Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Reports require an existing project run reports directory')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record all unchanged hashed inputs')
    payloads={name:raw.json_report(document) for name,document in result.reports.items()}
    payloads['jappe_figure_rows.jsonl']=cells.row_jsonl(result.rows)
    names=[*payloads,'jappe_figure_report_checksums.json']
    import os
    with raw._directory(directory) as descriptor:
        for name in names:
            try:os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            except FileNotFoundError:continue
            raise FileExistsError('Figure report already exists: '+name)
    for name,text in payloads.items():raw.write_text_report(directory/name,text,paths=storage)
    checksums={'reports':{name:raw.sha256_file(directory/name) for name in payloads},'inputs':result.inputs,
        'physical_rows_preserved':len(result.rows),'completion':'source_data_audited; C359_population_not_recovered'}
    for item in result.inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Input changed before completion receipt')
    raw.write_report(directory/names[-1],checksums,paths=storage)
    return checksums
