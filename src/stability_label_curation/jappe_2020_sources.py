"""Four allowlisted Jappe supplements and bounded, read-only OOXML inventory."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import secrets
import ssl
import stat
import unicodedata
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from http.client import HTTPException
import xml.etree.ElementTree as ET
import zipfile

from . import netmhcstabpan_2016 as raw
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import StoragePaths, resolve_paths

SOURCE_ID = 'jappe_2020'
CONFIG = 'configs/jappe_2020_artifacts.json'
ARTIFACT_IDS = ('supplementary_data_3','supplementary_data_4','supplementary_data_5','descriptions')
MAX_ARTIFACT_BYTES = 15 * 1024 * 1024
MAX_TASK_BYTES = 50 * 1024 * 1024
MAX_XML_BYTES = 32 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOCREL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
DOI_PATH = '/art:10.1038/s41467-020-20166-4/MediaObjects/'


def allowed_url(url: str, filename: str) -> None:
    """Redirects may only retain the selected artifact identity on official publisher CDNs."""
    p = urlsplit(url)
    if (p.scheme != 'https' or p.hostname not in {'media.springernature.com','static-content.springer-cdn.com'}
        or p.port not in {None,443} or p.username or p.password or p.query or p.fragment
        or any(c.isspace() for c in url) or '\\' in url
        or not unquote(p.path).endswith(DOI_PATH + filename)):
        raise ValueError('URL is outside the selected official publisher artifact allowlist')
    if '..' in PurePosixPath(unquote(p.path)).parts:
        raise ValueError('Unsafe publisher URL path')


def load_artifacts(*, paths: StoragePaths | None = None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    source = load_manifest(paths=storage).get(SOURCE_ID)
    with raw._read_file(storage.repository_root/CONFIG) as f:
        document = json.load(f)
    if (document.get('schema_version') != 1 or document.get('source_id') != source.source_id
        or document.get('publication_doi') != source.publication_doi
        or document.get('official_article_url') != source.landing_url):
        raise ValueError('Source-specific manifest does not agree with the source registry')
    entries = document.get('artifacts',[])
    if len(entries) != 4 or {x['artifact_id'] for x in entries} != set(ARTIFACT_IDS):
        raise ValueError('Exactly the four authorized supplements must be allowlisted')
    filenames = set()
    for entry in entries:
        name = entry['filename']
        expected = 'pdf' if entry['artifact_id'] == 'descriptions' else 'xlsx'
        if (not re.fullmatch(r'[A-Za-z0-9_-]+\.'+expected,name) or name in filenames
            or entry['format'] != expected or entry['publisher_sha256'] is not None):
            raise ValueError('Unsafe/duplicate filename, format, or unverified publisher checksum')
        filenames.add(name); allowed_url(entry['source_hyperlink_url'],name)
    return document


def _part(base: str, target: str) -> str:
    """OOXML internal relationship resolution; never extract archive members."""
    p = urlsplit(target)
    decoded = unquote(p.path)
    if p.scheme or p.netloc or p.query or p.fragment or '\\' in decoded:
        raise ValueError('Unsupported or external OOXML relationship target')
    result = posixpath.normpath(decoded.lstrip('/') if decoded.startswith('/') else posixpath.join(posixpath.dirname(base),decoded))
    if result in {'','.'} or result.startswith('../') or result.startswith('/'):
        raise ValueError('OOXML relationship escapes the archive root')
    return result


def _rels_part(part: str) -> str:
    return posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')


def _xml(archive: zipfile.ZipFile, part: str) -> ET.Element:
    try:
        content = archive.read(part)
    except KeyError as error:
        raise ValueError('Required OOXML part is missing: '+part) from error
    if len(content) > MAX_XML_BYTES:
        raise ValueError('XML part exceeds narrow inspection bound')
    text = content.decode('utf-8-sig')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD/entities or unsupported XML encoding')
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError('Malformed OOXML part: '+part) from error


def _relationships(archive: zipfile.ZipFile, name: str) -> dict[str, dict[str, str]]:
    root = _xml(archive,name)
    if root.tag != '{'+REL+'}Relationships':
        raise ValueError('Unsupported relationship XML root')
    result = {}
    for child in root:
        if child.tag != '{'+REL+'}Relationship' or not all(k in child.attrib for k in ('Id','Type','Target')):
            raise ValueError('Invalid relationship structure')
        if child.attrib['Id'] in result:
            raise ValueError('Duplicate relationship ID')
        result[child.attrib['Id']] = dict(child.attrib)
    return result


def _check_archive(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist(); names = [x.filename for x in infos]
    if len(infos) > MAX_ZIP_ENTRIES or len(names) != len(set(names)):
        raise ValueError('Too many or duplicate ZIP members')
    for info in infos:
        name = PurePosixPath(info.filename)
        if (name.is_absolute() or '..' in name.parts or '\\' in info.filename or info.flag_bits & 1
            or info.file_size > MAX_XML_BYTES or stat.S_ISLNK(info.external_attr >> 16)):
            raise ValueError('Unsafe, encrypted, or oversized ZIP member')
    if sum(x.file_size for x in infos) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError('ZIP uncompressed inspection limit exceeded')
    if not {'[Content_Types].xml','_rels/.rels'}.issubset(names):
        raise ValueError('ZIP is not an OOXML workbook package')
    bad = archive.testzip()
    if bad is not None:
        raise ValueError('ZIP CRC failure: '+bad)
    roots = [x for x in _relationships(archive,'_rels/.rels').values() if x['Type']==DOCREL+'/officeDocument']
    if len(roots) != 1 or roots[0].get('TargetMode') == 'External':
        raise ValueError('Missing or ambiguous internal workbook relationship')
    workbook = _part('',roots[0]['Target'])
    root = _xml(archive,workbook)
    if root.tag != '{'+MAIN+'}workbook' or root.find('{'+MAIN+'}sheets') is None:
        raise ValueError('Invalid or unsupported workbook XML')
    return {'crc_integrity':'all_members_passed','workbook_part':workbook,
            'parts':[{'name':i.filename,'compressed_bytes':i.compress_size,'uncompressed_bytes':i.file_size} for i in infos]}


def validate_artifact(path: str | Path, format: str) -> dict[str, Any]:
    with raw._read_file(path) as f:
        if os.fstat(f.fileno()).st_size > MAX_ARTIFACT_BYTES:
            raise ValueError('Artifact exceeds 15 MiB limit')
        if format == 'xlsx':
            with zipfile.ZipFile(f) as archive:
                return _check_archive(archive)
        if format != 'pdf' or f.read(5) != b'%PDF-':
            raise ValueError('Unexpected artifact signature; HTML/error pages rejected')
        f.seek(max(0,os.fstat(f.fileno()).st_size-1024))
        if b'%%EOF' not in f.read():
            raise ValueError('Missing PDF end marker')
        return {'archive_integrity':'not_applicable_pdf','pdf_validation':'signature_and_end_marker_only; not a full PDF validator'}


class _Redirects(HTTPRedirectHandler):
    def __init__(self, filename: str):
        super().__init__(); self.filename = filename

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Request | None:
        allowed_url(newurl,self.filename)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def _fetch_one(entry: dict[str, Any], document: dict[str, Any], storage: StoragePaths,
               timeout: float, budget: list[int], *, max_artifact_bytes: int | None = None) -> dict[str, Any]:
    max_artifact_bytes = MAX_ARTIFACT_BYTES if max_artifact_bytes is None else max_artifact_bytes
    if not 0 < max_artifact_bytes <= MAX_ARTIFACT_BYTES:
        raise ValueError('Invalid artifact byte limit')
    target = storage.project_data_dir/SOURCE_ID/entry['filename']
    # Use unresolved root construction to detect source-directory symlink escapes.
    if (storage.project_data_dir != storage.data_root/'stability-label-curation'
        or storage.project_data_dir.resolve() != storage.project_data_dir):
        raise ValueError('Unsafe project data root')
    receipt = {'source_id':SOURCE_ID,'artifact_id':entry['artifact_id'],'official_article_url':document['official_article_url'],
        'source_hyperlink_url':entry['source_hyperlink_url'],'final_download_url':None,
        'retrieved_at_utc':None,'http_status':None,'original_filename':entry['filename'],'local_path':str(target),
        'publisher_sha256':None,'server_metadata':{'content_length':None,'etag':None,'last_modified':None,'content_type':None},
        'role':entry['role'],'limitations':['Local SHA256 identifies exact bytes; not publisher checksum verification or row validity.','No experimental/synthetic/derived assignment to workbook rows.']}
    allowed_url(entry['source_hyperlink_url'],entry['filename'])
    with raw._directory(target.parent,create=True) as parent:
        try: existing = os.stat(target.name,dir_fd=parent,follow_symlinks=False)
        except FileNotFoundError: existing = None
        if existing is not None:
            if not stat.S_ISREG(existing.st_mode):
                raise ValueError('Existing artifact must be a regular non-symlink file')
            if existing.st_size > max_artifact_bytes:
                raise ValueError('Existing artifact exceeds selected byte limit')
            receipt['acquisition'] = 'existing_artifact_reused'
            receipt['limitations'].append('Reused bytes were not compared with current publisher content; prior HTTP metadata is unavailable in this receipt.')
        else:
            if budget[0] >= MAX_TASK_BYTES:
                raise ValueError('50 MiB task download budget exhausted')
            partial = '.'+target.name+'.'+secrets.token_hex(12)+'.partial'
            fd = os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            try:
                with os.fdopen(fd,'wb') as output:
                    opener = build_opener(_Redirects(entry['filename']),HTTPSHandler(context=ssl.create_default_context()))
                    with opener.open(Request(entry['source_hyperlink_url'],headers={'Accept-Encoding':'identity'}),timeout=timeout) as response:
                        allowed_url(response.geturl(),entry['filename'])
                        if response.status != 200 or response.headers.get('Content-Encoding','identity').lower() != 'identity':
                            raise ValueError('Expected complete HTTP 200 identity-encoded response')
                        length = response.headers.get('Content-Length')
                        if length is not None and (not re.fullmatch('[0-9]+',length) or int(length)>min(max_artifact_bytes,MAX_TASK_BYTES-budget[0])):
                            raise ValueError('Server Content-Length invalid or exceeds download limit')
                        if 'html' in response.headers.get('Content-Type','').lower():
                            raise ValueError('Publisher returned HTML instead of the requested artifact')
                        size = 0
                        while True:
                            allowance = min(max_artifact_bytes-size,MAX_TASK_BYTES-budget[0])
                            if allowance <= 0:
                                if length is not None and size == int(length):break
                                raise ValueError('Download byte limit reached before EOF could be verified')
                            block = response.read(min(65536,allowance))
                            if not block:break
                            size += len(block);budget[0] += len(block)
                            if size>max_artifact_bytes or budget[0]>MAX_TASK_BYTES:
                                raise ValueError('Streaming download exceeds artifact/task byte limit')
                            output.write(block)
                        if length is not None and int(length) != size:
                            raise ValueError('Server Content-Length does not match actual bytes')
                        receipt.update(final_download_url=response.geturl(),retrieved_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                            http_status=response.status,server_metadata={'content_length':length,'etag':response.headers.get('ETag'),
                            'last_modified':response.headers.get('Last-Modified'),'content_type':response.headers.get('Content-Type')})
                    output.flush();os.fsync(output.fileno())
                # Validate before final publication: failed partials never look completed.
                validate_artifact(target.parent/partial,entry['format'])
                os.link(partial,target.name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False);os.fsync(parent)
                receipt['acquisition'] = 'downloaded'
            finally:os.unlink(partial,dir_fd=parent)
    receipt['integrity'] = validate_artifact(target,entry['format'])
    with raw._read_file(target) as stream:
        size,checksum = raw._hash_stream(stream)
    receipt.update(byte_size=size,local_sha256=checksum,validation_status='format_and_local_bytes_verified; scientific_row_classification_deferred')
    # Container parts are inventoried separately, keep receipts compact.
    receipt['integrity'].pop('parts',None)
    return receipt


def fetch(*, paths: StoragePaths | None = None, artifacts: list[str] | None = None,
          timeout: float = 30) -> dict[str, Any]:
    """Sole network entry point; bounded allowlisted requests, no automatic retries."""
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 120:
        raise ValueError('Timeout must be finite, positive, and at most 120 seconds')
    storage = resolve_paths() if paths is None else paths
    storage.validate()
    if storage.project_data_dir != storage.data_root/'stability-label-curation' or storage.project_data_dir.resolve() != storage.project_data_dir:
        raise ValueError('Unsafe project data root')
    document = load_artifacts(paths=storage)
    selected = list(ARTIFACT_IDS) if artifacts is None else artifacts
    if not selected or len(set(selected)) != len(selected) or any(x not in ARTIFACT_IDS for x in selected):
        raise ValueError('Only unique authorized artifact IDs may be downloaded')
    entries = {x['artifact_id']:x for x in document['artifacts']}
    receipts = [];errors = [];budget = [0]
    for identifier in selected:
        try:receipts.append(_fetch_one(entries[identifier],document,storage,timeout,budget))
        except (ValueError,OSError,HTTPException,zipfile.BadZipFile,ET.ParseError,NotImplementedError) as error:
            errors.append({'artifact_id':identifier,'error_type':type(error).__name__,'error':str(error)})
    return {'source_id':SOURCE_ID,'artifacts':receipts,'errors':errors,'downloaded_bytes_this_invocation':budget[0],
            'limits':{'artifact_bytes':MAX_ARTIFACT_BYTES,'task_bytes':MAX_TASK_BYTES},
            'unintended_requests':'none; only selected allowlisted publisher artifacts; redirects validated before following'}


def _ranges(indices: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for index in sorted(set(indices)):
        if result and result[-1][1]+1==index:result[-1][1]=index
        else:result.append([index,index])
    return result


def _tables(archive: zipfile.ZipFile, worksheet: str, root: ET.Element) -> list[dict[str, Any]]:
    """Table definitions are declared metadata, never expanded into worksheet rows."""
    nodes = root.find('{'+MAIN+'}tableParts')
    if nodes is None:return []
    relationships = _relationships(archive,_rels_part(worksheet))
    tables = []
    for node in nodes:
        rid = node.get('{'+DOCREL+'}id');rel = relationships.get(rid)
        if not rel or rel.get('TargetMode')=='External' or rel['Type']!=DOCREL+'/table':
            tables.append({'relationship_id':rid,'status':'unresolved_table_relationship'});continue
        part = _part(worksheet,rel['Target']);table = _xml(archive,part)
        if table.tag!='{'+MAIN+'}table':
            tables.append({'relationship_id':rid,'table_part':part,'status':'unsupported_table_root'});continue
        tables.append({'relationship_id':rid,'table_part':part,'status':'metadata_inspected',
            'attributes':dict(table.attrib),'columns':[dict(c.attrib) for c in table.iter('{'+MAIN+'}tableColumn')]})
    return tables


def _sheet(archive: zipfile.ZipFile, part: str, strings: list[str]) -> dict[str, Any]:
    root = _xml(archive,part)
    if root.tag != '{'+MAIN+'}worksheet':
        return {'status':'unsupported_worksheet_root','root_tag':root.tag,'scientific_row_count':None}
    data = root.find('{'+MAIN+'}sheetData');rows = [] if data is None else list(data)
    types: Counter[str] = Counter();populated_rows = [];columns = [];cells_count = populated = formulas = 0
    headers = [];relevant = [];formula_samples = [];whitespace_cells = [];format_cells = [];anomalies = [];unknown = set();raw_row_count = populated_row_count = 0
    for row in rows:
        if row.tag != '{'+MAIN+'}row':unknown.add(row.tag);continue
        raw_row_count += 1;row_content = False;sample = [];row_ref = row.get('r')
        for cell in row:
            if cell.tag != '{'+MAIN+'}c':unknown.add(cell.tag);continue
            cells_count += 1;kind = cell.get('t','n');types[kind] += 1
            v = cell.find('{'+MAIN+'}v');f = cell.find('{'+MAIN+'}f');inline = cell.find('{'+MAIN+'}is')
            value = None if v is None else v.text
            inline_text = None if inline is None else ''.join(x.text or '' for x in inline.iter('{'+MAIN+'}t'))
            resolved = None
            if kind=='s':
                if value is not None and re.fullmatch('[0-9]+',value) and int(value)<len(strings):resolved=strings[int(value)]
                else:anomalies.append({'cell':cell.get('r'),'issue':'invalid_shared_string_index'})
            if kind not in {'n','s','inlineStr','str','b','e','d'}:unknown.add('cell_storage_type:'+kind)
            for child in cell:
                if child.tag not in {'{'+MAIN+'}v','{'+MAIN+'}f','{'+MAIN+'}is'}:unknown.add(child.tag)
            if f is not None:formulas += 1
            content = bool(value is not None and value!='' or inline_text or f is not None)
            if not content:continue
            row_content = True;populated += 1
            ref = cell.get('r');match = re.fullmatch('([A-Z]+)([1-9][0-9]*)',ref or '')
            if match:
                col=0
                for char in match[1]:col=col*26+ord(char)-64
                columns.append(col)
            else:anomalies.append({'cell':ref,'issue':'missing_or_unsupported_cell_reference'})
            observation = {'cell_reference':ref,'storage_type':kind,'stored_value_text':value,
                'inline_text':inline_text,'resolved_shared_string_text':resolved,
                'formula_text':None if f is None else f.text,'formula_attributes':None if f is None else dict(f.attrib)}
            if f is not None and len(formula_samples)<10:formula_samples.append(observation)
            if kind in {'s','inlineStr','str'}:sample.append(observation)
            label=resolved if resolved is not None else inline_text if inline_text is not None else value or ''
            if kind in {'s','inlineStr','str'} and not label.strip():whitespace_cells.append(ref)
            if kind in {'s','inlineStr','str'} and label and all(unicodedata.category(c)=='Cf' for c in label):
                format_cells.append({'cell_reference':ref,'text':label,'unicode_codepoints':['U+%04X'%ord(c) for c in label]})
            if kind in {'s','inlineStr','str'} and re.search(r'\bTm\b|peptide|ligand|transfor|negative|predict|temperature',label,re.I):
                if len(relevant)<100:relevant.append(observation)
        if row_content:
            populated_row_count += 1
            if row_ref and re.fullmatch('[1-9][0-9]*',row_ref):populated_rows.append(int(row_ref))
            else:anomalies.append({'row':row_ref,'issue':'missing_or_unsupported_row_reference'})
            if sample and len(headers)<8:headers.append({'source_row_reference':row_ref,'text_cells':sample})
    known = {'sheetPr','dimension','sheetViews','sheetFormatPr','cols','sheetData','mergeCells'}
    unsupported = sorted({child.tag for child in root if child.tag not in {'{'+MAIN+'}'+x for x in known}} | unknown)
    dimension = root.find('{'+MAIN+'}dimension')
    merges = root.find('{'+MAIN+'}mergeCells')
    tables = _tables(archive,part,root)
    for table in tables:
        ref = table.get('attributes',{}).get('ref','')
        match = re.fullmatch('[A-Z]+[0-9]+:[A-Z]+([0-9]+)',ref)
        if match and populated_rows and int(match[1])>max(populated_rows):
            anomalies.append({'issue':'table_range_extends_beyond_populated_row_references',
                'table_part':table['table_part'],'declared_table_range':ref,'maximum_populated_row_reference':max(populated_rows)})
    return {'status':'structurally_inspected','declared_dimension':None if dimension is None else dimension.get('ref'),
        'physical_row_elements':raw_row_count,'populated_row_elements':populated_row_count,
        'populated_rows_with_valid_references':len(populated_rows),
        'physical_cell_elements':cells_count,'populated_cell_elements':populated,'storage_type_counts':dict(sorted(types.items())),
        'formula_cell_count':formulas,'formula_cell_samples':formula_samples,
        'candidate_header_text_rows':headers,'relevant_text_cells':relevant,
        'whitespace_only_string_cell_references':whitespace_cells,
        'format_character_only_string_cells':format_cells,'table_definitions':tables,
        'populated_row_ranges':_ranges(populated_rows),'populated_column_ranges':_ranges(columns),
        'multiple_block_indications':{'separated_row_ranges':len(_ranges(populated_rows))>1,'separated_column_ranges':len(_ranges(columns))>1},
        'merged_ranges':[] if merges is None else [x.get('ref') for x in merges],
        'uninterpreted_or_unsupported_xml_structures':unsupported,'anomalies':anomalies,
        'scientific_row_count':None,'cell_content_policy':'Original bytes preserved; sample value/formula text retained; no evaluation, numeric conversion, or scientific labeling.'}


def workbook_inventory(path: str | Path) -> dict[str, Any]:
    """Bounded ZIP/XML metadata; stored rows/dimensions are never measurement counts."""
    checksum=raw.sha256_file(path);container=validate_artifact(path,'xlsx')
    with raw._read_file(path) as stream,zipfile.ZipFile(stream) as archive:
        workbook=container['workbook_part'];root=_xml(archive,workbook)
        relationships=_relationships(archive,_rels_part(workbook))
        strings=[];shared_part=None;warnings=[]
        for rel in relationships.values():
            if rel.get('TargetMode')=='External':warnings.append({'issue':'external_relationship_not_followed','relationship':rel})
            elif rel['Type']==DOCREL+'/sharedStrings':
                if shared_part is not None:raise ValueError('Multiple shared-string relationships')
                shared_part=_part(workbook,rel['Target']);shared_root=_xml(archive,shared_part)
                if shared_root.tag!='{'+MAIN+'}sst':raise ValueError('Unsupported shared-string table root')
                strings=[''.join(t.text or '' for t in x.iter('{'+MAIN+'}t')) for x in shared_root if x.tag=='{'+MAIN+'}si']
        sheets=[];seen=set()
        for order,sheet in enumerate(root.find('{'+MAIN+'}sheets'),1):
            rid=sheet.get('{'+DOCREL+'}id');rel=relationships.get(rid)
            if not sheet.get('name') or sheet.get('name') in seen:raise ValueError('Missing or duplicate sheet name')
            seen.add(sheet.get('name'))
            entry={'order':order,'name':sheet.get('name'),'sheet_id':sheet.get('sheetId'),'visibility':sheet.get('state','visible'),'relationship_id':rid}
            if not rel:raise ValueError('Sheet relationship is missing')
            if rel.get('TargetMode')=='External' or rel['Type']!=DOCREL+'/worksheet':
                entry.update(status='unsupported_sheet_relationship',relationship=rel,scientific_row_count=None)
            else:
                part=_part(workbook,rel['Target']);entry.update(worksheet_part=part,**_sheet(archive,part,strings))
            sheets.append(entry)
        if not sheets:raise ValueError('Workbook has no sheet entries')
        known={'fileVersion','workbookPr','bookViews','sheets','calcPr'}
        unknown=sorted({x.tag for x in root if x.tag not in {'{'+MAIN+'}'+k for k in known}})
        unusual=[x.filename for x in archive.infolist() if any(flag in x.filename.lower() for flag in ('vbaproject','externallinks','embeddings'))]
        size=os.fstat(stream.fileno()).st_size
    if raw.sha256_file(path)!=checksum:raise ValueError('Workbook changed during inventory')
    return {'local_path':str(Path(path).absolute()),'byte_size':size,'sha256':checksum,**container,
        'sheet_count':len(sheets),'sheets':sheets,'shared_strings':{'present':shared_part is not None,'part':shared_part,'entry_count':len(strings)},
        'workbook_uninterpreted_or_unsupported_xml_structures':unknown,'unusual_archive_parts':unusual,'anomalies':warnings,
        'limitations':['Dimensions and populated cell/row counts are structural metadata, not experimental counts.',
        'UTF-8 transitional OOXML only; rich text samples concatenated, original runs retained in raw archive.',
        'Styles, dates, formulas/caches, charts and modeling blocks are not interpreted. No Tm or half-life conversions.']}


def inventory(*, paths: StoragePaths | None = None, files: dict[str,str | Path] | None = None) -> dict[str, Any]:
    storage=resolve_paths() if paths is None else paths;document=load_artifacts(paths=storage)
    overrides={} if files is None else files
    if any(x not in ARTIFACT_IDS for x in overrides):raise ValueError('Unknown artifact override')
    artifacts=[]
    for entry in document['artifacts']:
        path=Path(overrides.get(entry['artifact_id'],storage.project_data_dir/SOURCE_ID/entry['filename']))
        if entry['format']=='xlsx':result=workbook_inventory(path)
        else:
            integrity=validate_artifact(path,'pdf');checksum=raw.sha256_file(path)
            with raw._read_file(path) as stream:size=os.fstat(stream.fileno()).st_size
            result={'local_path':str(path.absolute()),'byte_size':size,'sha256':checksum,**integrity}
        artifacts.append({'artifact_id':entry['artifact_id'],'publisher_role':entry['role'],**result})
    return {'source_id':SOURCE_ID,'artifact_manifest':document,'artifacts':artifacts,
        'published_expectations':document['published_expectations'],'verified_scientific_observation_counts':None,
        'classification_status':'Workbook structure only; all row-level scientific classification deferred to Task 1.6.'}


def write_inventory(document: dict[str, Any], reports_dir: str | Path, *, paths: StoragePaths | None = None) -> None:
    storage=resolve_paths() if paths is None else paths;directory=Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Reports require an existing project run reports directory')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for artifact in document['artifacts']:
        item={'path':artifact['local_path'],'sha256':artifact['sha256']}
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record every unchanged hashed workbook/PDF input')
    raw.write_report(directory/'jappe_workbook_inventory.json',document,paths=storage)
