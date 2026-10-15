"""Version 4 acquisition and aggregate audit with sealed evaluation members.

No checkpoint code, corrections, split construction, or model training.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import sqlite3
import ssl
import stat
from typing import Any
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener
import zipfile

from . import netmhcstabpan_2016 as raw
from . import dtu2016_source_audit as dtu
from . import bigmhc_source_audit as source_tools
from . import run_manifest as runs
from .data_sources import load_manifest
from .paths import PROJECT_NAME, StoragePaths, resolve_paths

CONFIG = 'configs/bigmhc_v4_audit.json'
DOWNLOAD_URL = 'https://data.mendeley.com/public-files/datasets/dvmz6pkzvb/files/1da0314f-692d-4c39-b81f-fa2a7dba86bf/file_downloaded?version=4'
FINAL_URL = 'https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/b7ef294a-1a96-45af-8a16-ab060251e131'
REFERENCE_URL = 'https://data.mendeley.com/public-files/datasets/dvmz6pkzvb/files/6e3754c4-53dd-4e6c-8a8d-10e0ef2e61a2/file_downloaded?version=4'
REFERENCE_FINAL_URL = 'https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/4257cd1f-d936-4e81-9227-8584d7f8b24c'
REFERENCE_SHA = 'cd1fa24fb4c9fc0ee592a3d753458c4e3abed0d5cc4ca76e325aa274df8e900a'
REFERENCE_BYTES = 15921144
ARCHIVE_CAP = 256 * 1024 * 1024
MEMBER_CAP = 1024 * 1024 * 1024
EXPANDED_CAP = 2 * 1024 * 1024 * 1024
PUBLISHED_BYTES = 144274974
DATA_MEMBERS = ('el_train.csv', 'el_val.csv', 'im_train.csv', 'im_val.csv')
READABLE_MEMBERS = (*DATA_MEMBERS, 'pseudoseqs.csv')
SEALED_MEMBERS = ('el_test.csv', 'im_test.csv', 'iedb.csv', 'manafest.csv')


def validate_download_url(url: str, artifact: str='datasets.zip') -> None:
    allowed={'datasets.zip':{DOWNLOAD_URL,FINAL_URL},'pseudoseqs.csv':{REFERENCE_URL,REFERENCE_FINAL_URL}}
    if artifact not in allowed or url not in allowed[artifact]:
        raise ValueError('URL outside exact publisher/archive allowlist')


class _Redirect(HTTPRedirectHandler):
    def __init__(self,artifact='datasets.zip'):
        super().__init__();self.artifact=artifact
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_download_url(newurl,self.artifact)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(*, paths: StoragePaths | None = None, timeout: float = 30, artifact: str='datasets.zip',
          expected_size: int | None = PUBLISHED_BYTES, opener=None) -> dict[str, Any]:
    storage = resolve_paths() if paths is None else paths
    storage.validate()
    expected_root = storage.data_root / PROJECT_NAME
    if storage.project_data_dir != expected_root or expected_root.resolve() != expected_root:
        raise ValueError('Project data root must not alias another project')
    source = load_manifest(paths=storage).get('bigmhc_v4')
    if artifact not in {'datasets.zip','pseudoseqs.csv'}:raise ValueError('Unallowlisted artifact')
    is_reference=artifact=='pseudoseqs.csv'
    url=REFERENCE_URL if is_reference else DOWNLOAD_URL
    expected_sha=REFERENCE_SHA if is_reference else source.expected_sha256
    cap=32*1024*1024 if is_reference else ARCHIVE_CAP
    if is_reference and expected_size==PUBLISHED_BYTES:expected_size=REFERENCE_BYTES
    relative = PurePosixPath(source.target_relative_path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe source target')
    target = storage.project_data_dir / relative
    if is_reference:target=target.with_name('pseudoseqs.csv')
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError('Finite timeout required')
    receipt = {'source_id':source.source_id,'landing_url':source.landing_url,'version':source.published_version,
        'artifact':artifact,'source_url':url,'publisher_reported_sha256':expected_sha,
        'publisher_metadata_url':'https://data.mendeley.com/public-api/datasets/dvmz6pkzvb/files?folder_id=root&version=4'}
    with raw._directory(target.parent, create=True) as parent:
        try:
            os.stat(target.name,dir_fd=parent,follow_symlinks=False)
        except FileNotFoundError:
            exists=False
        else:
            exists=True
        if exists:
            with raw._read_file(target) as stream:
                size,checksum=raw._hash_stream(stream)
            if size>cap or checksum!=expected_sha:
                raise ValueError('Existing artifact differs; preserved without replacement')
            receipt.update(acquisition='reused',http_status=None,final_url=None,retrieved_at_utc=None,
                           limitation='No new HTTP metadata; existing exact bytes verified against publisher reference')
        else:
            partial='.'+target.name+'.'+secrets.token_hex(12)+'.partial'
            fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            try:
                client=opener or build_opener(HTTPSHandler(context=ssl.create_default_context()),_Redirect(artifact))
                with os.fdopen(fd,'wb') as output, client.open(Request(url,headers={'Accept-Encoding':'identity','User-Agent':'stability-label-curation provenance audit'}),timeout=timeout) as response:
                    validate_download_url(response.geturl(),artifact)
                    if response.status!=200:raise ValueError('Unexpected archive HTTP status')
                    length=response.headers.get('Content-Length')
                    if length is not None and (not re.fullmatch('[0-9]+',length) or int(length)>cap):
                        raise ValueError('Invalid or excessive Content-Length')
                    if response.headers.get('Content-Encoding','identity') not in {'','identity'}:
                        raise ValueError('Unexpected byte-transforming content encoding')
                    size=0;digest=hashlib.sha256();first=True
                    while chunk:=response.read(1024*1024):
                        size+=len(chunk)
                        if size>cap:raise ValueError('Artifact size cap exceeded')
                        if first and not is_reference and not chunk.startswith(b'PK\x03\x04'):raise ValueError('Response is not a ZIP archive')
                        if first and is_reference and not chunk.startswith((b'mhc,',b'\xef\xbb\xbfmhc,')):raise ValueError('Response is not the receptor CSV')
                        first=False;output.write(chunk);digest.update(chunk)
                    checksum=digest.hexdigest()
                    if length is not None and int(length)!=size:raise ValueError('Server length mismatch')
                    if expected_size is not None and size!=expected_size:raise ValueError('Publisher size mismatch')
                    if checksum!=expected_sha:raise ValueError('Publisher SHA256 mismatch')
                    output.flush();os.fsync(output.fileno())
                    receipt.update(acquisition='downloaded',http_status=response.status,final_url=response.geturl(),
                        retrieved_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                        server_metadata={'content_length':length,'content_type':response.headers.get('Content-Type'),
                            'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified')})
                os.link(partial,target.name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False);os.fsync(parent)
            finally:
                os.unlink(partial,dir_fd=parent)
    receipt.update(byte_size=size,local_sha256=checksum,local_checksum_verified=True,publisher_reference_match=True,
                   archive_target_relative_path=str(target.relative_to(storage.project_data_dir)),
                   limitation_of_checksum='Establishes released archive byte identity, not experimental origin or split independence')
    return receipt


def canonical_hla(text: str) -> str | None:
    """Two-field human HLA-I notation only; no fuzzy, field truncation or mutant mapping."""
    match=re.fullmatch(r'HLA-([ABC])\*?([0-9]{2,3}):([0-9]{2,3})',text)
    return None if match is None else f'HLA-{match[1]}*{match[2]}:{match[3]}'


def archive_inventory(z: zipfile.ZipFile) -> tuple[dict[str,zipfile.ZipInfo],list[dict[str,Any]]]:
    entries=z.infolist()
    if len(entries)>100:raise ValueError('Archive entry cap exceeded')
    mapped={};inventory=[];names=set();expanded=0
    for info in entries:
        path=PurePosixPath(info.filename)
        if (info.filename in names or path.is_absolute() or '..' in path.parts or '\\' in info.filename
                or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1):
            raise ValueError('Unsafe, duplicate, encrypted or symlink ZIP entry')
        names.add(info.filename);expanded+=info.file_size
        if info.file_size>MEMBER_CAP or expanded>EXPANDED_CAP:raise ValueError('Expanded ZIP size cap exceeded')
        if info.file_size>1024*1024 and info.file_size/max(1,info.compress_size)>1000:raise ValueError('ZIP expansion ratio cap exceeded')
        role='unopened_metadata_only'
        if path.name in READABLE_MEMBERS:
            if str(path.parent) not in {'.','datasets'} or path.name in mapped:raise ValueError('Ambiguous authorized member path')
            mapped[path.name]=info;role='authorized_for_this_audit'
        elif path.name in SEALED_MEMBERS:role='sealed_evaluation_member'
        elif path.name=='summary.csv':role='optional_summary_not_opened'
        inventory.append({'member':info.filename,'uncompressed_bytes':info.file_size,'compressed_bytes':info.compress_size,'role':role})
    if not set(DATA_MEMBERS)<=set(mapped):raise ValueError('Required training/validation ZIP members missing')
    return mapped,inventory


class _DigestReader(io.RawIOBase):
    def __init__(self,stream,maximum):
        self.stream=stream;self.maximum=maximum;self.size=0;self.digest=hashlib.sha256()
    def readable(self):return True
    def readinto(self,buffer):
        chunk=self.stream.read(len(buffer))
        self.size+=len(chunk)
        if self.size>self.maximum:raise ValueError('Actual member expansion exceeded bound')
        self.digest.update(chunk);buffer[:len(chunk)]=chunk
        return len(chunk)


def _rows(z,info,name,opened,member_hashes):
    if name not in READABLE_MEMBERS or PurePosixPath(info.filename).name!=name:
        raise ValueError('Attempt to open a sealed or unauthorized member')
    opened.append(name)
    with z.open(info) as stream:
        wrapped=_DigestReader(stream,min(MEMBER_CAP,info.file_size))
        with io.TextIOWrapper(io.BufferedReader(wrapped),encoding='utf-8-sig',newline='') as text:
            reader=csv.reader(text,strict=True)
            for row in reader:
                yield reader.line_num,row
        if wrapped.size!=info.file_size:raise ValueError('Member stream was not fully consumed')
        member_hashes[name]={'sha256':wrapped.digest.hexdigest(),'byte_size':wrapped.size,'CRC_verified_by_full_authorized_read':True}


def _reference(iterator):
    try:_,header=next(iterator)
    except StopIteration:raise ValueError('Empty pseudosequence reference')
    if len(header)<2 or header[0]!='mhc' or len(set(header))!=len(header):raise ValueError('Unsupported pseudosequence header')
    positions=defaultdict(list)
    for index,column in enumerate(header[1:],1):
        match=re.fullmatch(r'([0-9]+)_([A-Z])',column)
        if match is None:raise ValueError('Unsupported receptor feature column')
        positions[match[1]].append(index)
    names=Counter();canonical=defaultdict(list);uids=defaultdict(list);invalid=[];rows=0
    for line,row in iterator:
        rows+=1
        if rows>100000:raise ValueError('Reference row cap exceeded')
        if len(row)!=len(header):raise ValueError('Malformed receptor row')
        name=row[0];names[name]+=1;allele=canonical_hla(name)
        if allele is not None:canonical[allele].append(name)
        uids[re.sub('[^A-Z0-9]+','',name.upper())].append(name)
        if any(v not in {'0','1'} for v in row[1:]) or any(sum(row[i]=='1' for i in indices)!=1 for indices in positions.values()):
            invalid.append(line)
    return {'header':header,'rows':rows,'distinct_raw_identifiers':len(names),'feature_count':len(header)-1,
        'feature_position_count':len(positions),'invalid_one_hot_rows':len(invalid),'invalid_source_lines':invalid[:20],
        'duplicate_identifier_count':sum(n>1 for n in names.values()),
        'sanitized_UID_collision_groups':[{'UID':uid,'original_identifiers':sorted(values)} for uid,values in sorted(uids.items()) if len(set(values))>1],
        'model_default_414_features_match':len(header)-1==414,
        'coverage_rule':'Exact two-field HLA-I notation, optional asterisk only; ambiguous reference names not certified covered'},names,canonical


@dataclass(frozen=True)
class DatasetAuditResult:
    reports: dict[str,dict[str,Any]]
    inputs: list[dict[str,str]]


def inspect(*, paths: StoragePaths | None=None, archive: str | Path | None=None,
            dtu_path: str | Path | None=None, expected_archive_sha256: str | None=None,
            expected_dtu_sha256: str | None=None, pseudoseqs_path: str | Path | None=None,
            expected_reference_sha256: str | None=None) -> DatasetAuditResult:
    storage=resolve_paths() if paths is None else paths
    sources=load_manifest(paths=storage);source=sources.get('bigmhc_v4');reference_source=sources.get('netmhcstabpan_2016')
    if expected_archive_sha256 is not None and archive is None:raise ValueError('Fixture checksum requires explicit archive path')
    if expected_dtu_sha256 is not None and dtu_path is None:raise ValueError('Fixture checksum requires explicit DTU path')
    if expected_reference_sha256 is not None and pseudoseqs_path is None:raise ValueError('Fixture checksum requires explicit reference path')
    target=Path(archive).expanduser().absolute() if archive else storage.project_data_dir/source.target_relative_path
    reference=Path(dtu_path).expanduser().absolute() if dtu_path else storage.project_data_dir/reference_source.target_relative_path
    expected=expected_archive_sha256 or source.expected_sha256;dtu_expected=expected_dtu_sha256 or dtu.TASK11_LOCAL_SHA256
    if any(not re.fullmatch('[a-f0-9]{64}',v) for v in (expected,dtu_expected)):raise ValueError('Invalid expected input checksum')
    inputs=[]
    for path,checksum in ((target,expected),(reference,dtu_expected)):
        if raw.sha256_file(path)!=checksum:raise ValueError('Immutable input SHA256 mismatch: '+path.name)
        inputs.append({'path':str(path),'sha256':checksum})
    if target.stat().st_size>ARCHIVE_CAP:raise ValueError('Archive cap exceeded')
    metadata={}
    if archive is None:
        for name in ('acquisition_receipt.json','publisher_file_metadata.json','reference_acquisition_receipt.json'):
            path=target.parent/name
            if path.exists():
                with raw._read_file(path) as stream:
                    content=stream.read(1024*1024+1)
                if len(content)>1024*1024:raise ValueError('Metadata bound exceeded')
                metadata[name]=json.loads(content)
                inputs.append({'path':str(path),'sha256':hashlib.sha256(content).hexdigest()})
        receipt=metadata.get('acquisition_receipt.json')
        if receipt and receipt['local_sha256']!=expected:raise ValueError('Receipt differs from actual archive identity')
    dtu_rows=[];dtu_alleles=set();dtu_keys=set();all_dtu=0;constructs=0
    for row in raw.iter_records(reference):
        all_dtu+=1
        if row.numeric_issue or row.half_life is None or not row.half_life.is_finite():raise ValueError('Invalid immutable DTU numeric value')
        category=dtu.identifier_category(row.hla)
        if category=='c67s_annotated_hla_b':constructs+=1
        if category not in {'ordinary_hla_a','ordinary_hla_b'}:continue
        if len(row.peptide)!=9:raise ValueError('Ordinary DTU reference is not nine-mer-only')
        key=(row.peptide,row.hla)
        if key in dtu_keys:raise ValueError('Ambiguous DTU pair reference')
        dtu_keys.add(key);dtu_alleles.add(row.hla);dtu_rows.append((row.peptide,row.hla,int(row.half_life==0)))
    db=sqlite3.connect(':memory:')
    db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA cache_size=-65536');db.execute('PRAGMA max_page_count=786432')
    db.execute('CREATE TABLE pairs(pep TEXT, allele TEXT, mask INTEGER, n0 INTEGER,n1 INTEGER,n2 INTEGER,n3 INTEGER, PRIMARY KEY(pep,allele)) WITHOUT ROWID')
    db.execute('CREATE TABLE dtu(pep TEXT,allele TEXT,is_zero INTEGER,PRIMARY KEY(pep,allele)) WITHOUT ROWID')
    db.executemany('INSERT INTO dtu VALUES(?,?,?)',dtu_rows)
    db.execute('CREATE TABLE hla_map(raw TEXT PRIMARY KEY,canonical TEXT) WITHOUT ROWID')
    stats={};opened=[];member_hashes={};total=0
    insert='INSERT INTO pairs VALUES(?,?,?,?,?,?,?) ON CONFLICT(pep,allele) DO UPDATE SET mask=mask|excluded.mask,n0=n0+excluded.n0,n1=n1+excluded.n1,n2=n2+excluded.n2,n3=n3+excluded.n3'
    try:
        with raw._read_file(target) as stream,zipfile.ZipFile(stream) as z:
            mapped,inventory=archive_inventory(z)
            if pseudoseqs_path is None and 'pseudoseqs.csv' in mapped:
                ref,names,canonical_reference=_reference(_rows(z,mapped['pseudoseqs.csv'],'pseudoseqs.csv',opened,member_hashes))
            else:
                refpath=Path(pseudoseqs_path).expanduser().absolute() if pseudoseqs_path else target.parent/'pseudoseqs.csv'
                refsha=expected_reference_sha256 or REFERENCE_SHA
                if not re.fullmatch('[a-f0-9]{64}',refsha):raise ValueError('Invalid reference checksum')
                if refpath.stat().st_size>32*1024*1024:raise ValueError('Reference byte cap exceeded')
                if raw.sha256_file(refpath)!=refsha:raise ValueError('Receptor reference SHA256 mismatch')
                inputs.append({'path':str(refpath),'sha256':refsha})
                with raw._read_file(refpath) as refstream,io.TextIOWrapper(refstream,encoding='utf-8-sig',newline='') as reftext:
                    reader=csv.reader(reftext,strict=True)
                    ref,names,canonical_reference=_reference((reader.line_num,row) for row in reader)
                ref['standalone_file_sha256']=refsha
            for split,name in enumerate(DATA_MEMBERS):
                iterator=_rows(z,mapped[name],name,opened,member_hashes)
                try:_,header=next(iterator)
                except StopIteration:raise ValueError('Empty training/validation member')
                if len(header)!=len(set(header)) or not {'mhc','pep','tgt'}<=set(header):raise ValueError('Unsupported training/validation CSV header')
                indices=[header.index(k) for k in ('mhc','pep','tgt')]
                labels=Counter();texts=Counter();lengths=Counter();alleles=defaultdict(Counter);malformed=[];invalid=Counter();compatible=Counter();batch=[];count=0
                rand_counts=Counter();unusual_characters=Counter();unusual_lines=[];raw_rows=Counter() if name.startswith('im_') else None
                for line,row in iterator:
                    count+=1;total+=1
                    if total>25000000:raise ValueError('Training/validation row inspection cap exceeded')
                    if len(row)!=len(header):
                        malformed.append(line);continue
                    allele,pep,text=(row[i] for i in indices);texts[text]+=1
                    if raw_rows is not None:
                        if len(raw_rows)<100000:raw_rows[tuple(row)]+=1
                        else:raw_rows=None
                    if 'rand' in header:rand_counts[(row[header.index('rand')],text)]+=1
                    if text in {'0','1'}:label=int(text)
                    else:
                        try:
                            value=raw.parse_record('X P '+text,1)
                            label=int(value.half_life) if value.numeric_issue is None and value.half_life in (0,1) else None
                        except ValueError:label=None
                    if label is None:
                        invalid['non_binary_or_nonfinite_label']+=1;continue
                    if not allele or not pep or len(pep)>100 or len(allele)>128:
                        invalid['missing_or_excessive_identity']+=1;continue
                    labels[str(label)]+=1;lengths[str(len(pep))]+=1;alleles[allele][str(label)]+=1
                    canonical=canonical_hla(allele);aa=all(c in raw.CANONICAL_AMINO_ACIDS for c in pep)
                    if not aa:
                        invalid['noncanonical_peptide_characters']+=1
                        unusual_characters.update(c for c in pep if c not in raw.CANONICAL_AMINO_ACIDS)
                        if len(unusual_lines)<20:unusual_lines.append(line)
                    if canonical is None:invalid['unsupported_HLA_notation']+=1
                    if canonical in dtu_alleles:
                        compatible['ordinary_DTU_allele_rows']+=1
                        if len(pep)==9:
                            compatible['ordinary_DTU_allele_ninemer_rows']+=1
                            if aa and len(canonical_reference.get(canonical,[]))==1:
                                compatible['ninemer_canonical_peptide_and_unique_reference_rows']+=1
                    values=[0,0,0,0];values[split]=1
                    batch.append((pep,allele,1<<(2*split+label),*values))
                    if len(batch)==10000:db.executemany(insert,batch);batch.clear()
                if batch:db.executemany(insert,batch)
                stats[name]={'header':header,'total_rows':count,'parsed_binary_identity_rows':sum(labels.values()),
                    'label_counts':dict(sorted(labels.items())),'original_label_text_counts':dict(sorted(texts.items())),
                    'peptide_length_counts':dict(sorted(lengths.items())),'distinct_raw_HLA_identifiers':len(alleles),
                    'by_original_HLA':{a:dict(sorted(v.items())) for a,v in sorted(alleles.items())},
                    'malformed_row_count':len(malformed),'malformed_source_lines':malformed[:20],
                    'quality_flag_counts':dict(sorted(invalid.items())),
                    'noncanonical_character_counts':dict(sorted(unusual_characters.items())),
                    'noncanonical_source_line_examples':unusual_lines,'DTU_input_scope_counts':dict(sorted(compatible.items())),
                    'rand_flag_by_original_label':[{'original_rand_flag':flag,'original_label':label,'rows':n} for (flag,label),n in sorted(rand_counts.items())],
                    'exact_all_field_duplicate_extra_rows':None if raw_rows is None else sum(n-1 for n in raw_rows.values()),
                    'ordinary_DTU_alleles_present':len({canonical_hla(a) for a in alleles}&dtu_alleles),
                    'scope_counts_are_training_eligibility':False}
        all_alleles=sorted({a for s in stats.values() for a in s['by_original_HLA']})
        db.executemany('INSERT INTO hla_map VALUES(?,?)',[(a,canonical_hla(a)) for a in all_alleles])
        duplicate={};pair_overlaps=[]
        for s,name in enumerate(DATA_MEMBERS):
            mask=3<<(2*s);column='n'+str(s)
            unique,repeated,conflicting=db.execute(f'SELECT count(*),coalesce(sum({column}>1),0),coalesce(sum((mask&?)=?),0) FROM pairs WHERE {column}>0',(mask,mask)).fetchone()
            rows=stats[name]['parsed_binary_identity_rows']
            duplicate[name]={'distinct_raw_pair_keys':unique,'repeated_raw_pair_keys':repeated,
                'conflicting_binary_label_keys':conflicting,'same_pair_and_binary_label_extra_rows':rows-unique-conflicting,
                'definition':'Original HLA+peptide key; duplicate label identity uses parsed binary value, not raw CSV byte equality. No rows changed.'}
            if stats[name]['header']==['mhc','pep','tgt'] and set(stats[name]['original_label_text_counts'])<={'0','1'}:
                stats[name]['exact_all_field_duplicate_extra_rows']=rows-unique-conflicting
        for s,left in enumerate(DATA_MEMBERS):
            for t in range(s+1,len(DATA_MEMBERS)):
                right=DATA_MEMBERS[t];m1=3<<(2*s);m2=3<<(2*t)
                n=db.execute('SELECT count(*) FROM pairs WHERE (mask&?)!=0 AND (mask&?)!=0',(m1,m2)).fetchone()[0]
                same_task=left[:2]==right[:2]
                disagreement=db.execute('SELECT count(*) FROM pairs WHERE ((mask&?)!=0 AND (mask&?)!=0) OR ((mask&?)!=0 AND (mask&?)!=0)',
                    (1<<(2*s),1<<(2*t+1),1<<(2*s+1),1<<(2*t))).fetchone()[0]
                pair_overlaps.append({'left':left,'right':right,'shared_raw_pair_keys':n,
                    'opposite_label_pair_keys':disagreement,'same_label_task':same_task,
                    'interpretation':'Potential train/validation pair overlap; conflicting labels need source review.' if same_task else 'EL and IM are different outcomes; disagreement does not establish erroneous labels.'})
        group='SELECT pep,'+','.join(f'max((mask&{3<<(2*s)})!=0) AS s{s}' for s in range(4))+' FROM pairs GROUP BY pep'
        expressions=['count(*)']+[f'sum(s{s})' for s in range(4)]+[f'sum(s{s} AND s{t})' for s in range(4) for t in range(s+1,4)]
        expressions+=['sum((s0 OR s1) AND (s2 OR s3))']
        seq_values=db.execute('SELECT '+','.join(expressions)+' FROM ('+group+')').fetchone()
        sequence={'distinct_peptides_all_authorized_data':seq_values[0],
            'distinct_peptides_by_file':{n:seq_values[1+i] for i,n in enumerate(DATA_MEMBERS)},
            'pairwise_shared_peptides':[],'EL_IM_shared_distinct_peptides':seq_values[-1]}
        index=5
        for s,left in enumerate(DATA_MEMBERS):
            for t in range(s+1,4):
                sequence['pairwise_shared_peptides'].append({'left':left,'right':DATA_MEMBERS[t],'shared_peptides':seq_values[index]});index+=1
        dtu_overlap={}
        for s,name in enumerate(DATA_MEMBERS):
            mask=3<<(2*s);column='n'+str(s)
            strict=db.execute(f'SELECT count(*) FROM dtu d CROSS JOIN pairs p ON p.pep=d.pep AND p.allele=d.allele WHERE p.{column}>0').fetchone()[0]
            matched,record_count,zero_count=db.execute(f'SELECT count(*),coalesce(sum(p.{column}),0),coalesce(sum(d.is_zero),0) FROM dtu d CROSS JOIN hla_map m ON m.canonical=d.allele CROSS JOIN pairs p ON p.pep=d.pep AND p.allele=m.raw WHERE p.{column}>0').fetchone()
            peptides=db.execute(f'SELECT count(DISTINCT p.pep) FROM (SELECT DISTINCT pep FROM dtu) d CROSS JOIN pairs p ON p.pep=d.pep WHERE p.{column}>0').fetchone()[0]
            dtu_overlap[name]={'strict_raw_pair_matches':strict,'notation_mapped_pair_matches':matched,'matched_source_rows':record_count,
                'matched_DTU_reported_zero_keys':zero_count,'shared_distinct_peptides_any_HLA':peptides,
                'measurement_values_comparable':False}
        mapping=[{'original_HLA':a,'canonical_two_field_HLA':canonical_hla(a),'rule':'Exact or optional-asterisk notation only; no fuzzy mapping',
            'exact_reference_identifier':a in names,'unique_canonical_reference_match':len(canonical_reference.get(canonical_hla(a),[]))==1,
            'ordinary_DTU_allele':canonical_hla(a) in dtu_alleles} for a in all_alleles]
        covered=[a for a in sorted(dtu_alleles) if len(canonical_reference.get(a,[]))==1]
        reports={
            'bigmhc_archive_inventory.json':{'source_id':'bigmhc_v4','version':4,'archive_sha256':expected,'byte_size':target.stat().st_size,
                'central_directory':inventory,'opened_members':opened,'member_identities':member_hashes,
                'publisher_described_members_absent_from_archive':[name for name in (*READABLE_MEMBERS,*SEALED_MEMBERS,'summary.csv') if not any(PurePosixPath(i['member']).name==name for i in inventory)],
                'sealed_member_status':{name:('present_sealed_not_opened' if any(PurePosixPath(i['member']).name==name for i in inventory) else 'absent_not_acquired') for name in SEALED_MEMBERS},
                'sealed_members_opened':[],'whole_archive_testzip_performed':False,'metadata':metadata},
            'bigmhc_training_inventory.json':{'files':stats,'duplicates':duplicate,'raw_records_modified':False,'training_tables_created':False},
            'bigmhc_dtu_compatibility.json':{'DTU_raw_rows':all_dtu,'ordinary_DTU_rows':len(dtu_rows),'ordinary_DTU_alleles':len(dtu_alleles),
                'C67S_rows_separate':constructs,'ordinary_DTU_reported_zeros':sum(r[2] for r in dtu_rows),
                'receptor_reference':ref,'ordinary_DTU_alleles_uniquely_in_reference':covered,
                'ordinary_DTU_alleles_missing_or_ambiguous_in_reference':sorted(dtu_alleles-set(covered)),
                'data_HLA_mapping':mapping,'DTU_overlap':dtu_overlap,'scope':'Computational compatibility, not correction or training eligibility'},
            'bigmhc_overlap_audit.json':{'raw_pair_overlap':pair_overlaps,'sequence_overlap':sequence,
                'near_sequence_similarity_assessed':False,'evaluation_overlap_assessed':False,
                'DTU_zero_semantics':'Unresolved; not synthetic-negative labels'},
            'bigmhc_provenance_and_blockers.json':{
                'future_conditions':{'A':'Original EL -> original IM','B':'Stability-corrected EL -> original IM',
                    'C':'Original EL -> stability-corrected IM','D':'Stability-corrected EL -> stability-corrected IM'},
                'objective_status':'Latest Task 2.2 user direction; experiments not implemented; original labels and independent experimental test outcomes preserved',
                'source_evidence_references':['docs/BIGMHC_SOURCE_AND_CHECKPOINT_PROVENANCE.md','configs/bigmhc_source_evidence.json','https://data.mendeley.com/datasets/dvmz6pkzvb/4','https://doi.org/10.1038/s42256-023-00694-6'],
                'EL_negative_provenance':'Publisher describes EL positives as MS ligands and negatives as decoys; these three fields do not identify individual decoy-generation source/process.',
                'IM_label_provenance':'Publication describes transfer using nonrandom PRIME examples; Released CSV labels alone do not independently verify each assay or negative definition.',
                'missing_metadata':['Row-level study/donor/assay and antigen lineage','Individual EL decoy generation provenance','Independent IM test exposure; evaluation files remain sealed','Teacher coverage and generalization for non-nine-mers or unsupported alleles','Future correction confidence and thresholds'],
                'deferred_not_prerequisites':['Sampler equalization','Optimizer-step matching','Multiple seeds','Causal sampling decomposition','Extensive controls','Final thresholds','Full hard-split construction'],
                'license':'Mendeley metadata CC BY 4.0; separate from BigMHC Academic software license',
                'corrections_created':False,'models_trained':False,'original_labels_modified':False}}
    except sqlite3.Error as error:
        raise ValueError('Bounded in-memory audit index failed: '+str(error)) from error
    finally:db.close()
    for item in inputs:
        if raw.sha256_file(item['path'])!=item['sha256']:raise ValueError('Immutable audit input changed')
    return DatasetAuditResult(reports,inputs)


def write_reports(result: DatasetAuditResult,reports_dir: str | Path,*,paths: StoragePaths | None=None):
    storage=resolve_paths() if paths is None else paths;directory=Path(reports_dir).expanduser().absolute()
    if '..' in directory.parts or directory.name!='reports' or directory.parent.parent!=storage.project_runs_dir:
        raise ValueError('Report directory must belong to an existing project run')
    manifest=runs.load_manifest(directory.parent.name,paths=storage)
    for item in result.inputs:
        if item not in manifest['data_provenance']['input_artifacts'] or raw.sha256_file(item['path'])!=item['sha256']:
            raise ValueError('Run must record every unchanged input')
    names=[*result.reports,'execution_verification.json']
    with raw._directory(directory) as parent:
        for name in names:
            try:os.stat(name,dir_fd=parent,follow_symlinks=False)
            except FileNotFoundError:continue
            raise FileExistsError('Existing audit report preserved: '+name)
    for name,doc in result.reports.items():raw.write_report(directory/name,doc,paths=storage)
    receipt={'code_commit':manifest['git']['commit_sha'],'inputs':result.inputs,
        'report_sha256':{name:raw.sha256_file(directory/name) for name in result.reports},
        'sealed_evaluation_members_opened':[],'scope':'Aggregate training/reference audit; no label changes, experiments or test outcomes inspected'}
    raw.write_report(directory/'execution_verification.json',receipt,paths=storage)
    return receipt
