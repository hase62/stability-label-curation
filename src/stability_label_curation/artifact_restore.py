"""Authenticated, non-overwriting artifact transport; never executes regeneration."""
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import tarfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener

from . import netmhcstabpan_2016 as raw
from .paths import PROJECT_NAME, resolve_paths

REGISTRY = 'configs/artifact_registry.json'


def relative(value: str) -> str:
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value) or value != str(PurePosixPath(value))
            or PurePosixPath(value).is_absolute() or any(p in {'.','..',''} for p in value.split('/'))):
        raise ValueError('Unsafe relative artifact path')
    return value


def sha(value): return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_json(path):
    def unique(pairs):
        result = {}
        for k,v in pairs:
            if k in result: raise ValueError('Duplicate registry/receipt key')
            result[k] = v
        return result
    with raw._read_file(path) as stream:
        return json.loads(stream.read(), object_pairs_hook=unique)


def storage(workspace_root=None):
    paths=resolve_paths() if workspace_root is None else resolve_paths({'CODEX_ROOT':str(Path(workspace_root).expanduser().absolute())})
    if (paths.project_data_dir != paths.data_root/PROJECT_NAME or paths.project_runs_dir != paths.runs_root/PROJECT_NAME
            or workspace_root is not None and (paths.data_root != paths.codex_root/'data' or paths.runs_root != paths.codex_root/'runs')):
        raise ValueError('Artifact workspace/project roots must not be symlink aliases')
    return paths


def load_registry(path=None):
    repository = Path(__file__).resolve().parents[2]
    path = Path(path or repository / REGISTRY).absolute()
    document = read_json(path)
    if not isinstance(document,dict) or document.get('schema_version') != 1 or document.get('project_name') != PROJECT_NAME or not isinstance(document.get('artifacts'), list):
        raise ValueError('Invalid artifact registry schema')
    result, destinations = {}, {}
    for artifact in document['artifacts']:
        if not isinstance(artifact,dict): raise ValueError('Artifact identity must be an object')
        aid = artifact.get('artifact_id','')
        if (not re.fullmatch('[a-z0-9][a-z0-9_-]{0,95}',aid) or aid in result
                or artifact.get('role') not in {'external_input','precomputed_output'}
                or not artifact.get('version') or artifact.get('format') not in {'tar.gz','file'}
                or not sha(artifact.get('sha256')) or type(artifact.get('size_bytes')) is not int
                or not 0 < artifact['size_bytes'] <= 512*1024**2):
            raise ValueError('Incomplete or invalid artifact identity')
        relative(artifact['filename'])
        if '/' in artifact['filename']: raise ValueError('Archive filename must be a basename')
        locator = artifact.get('locator',{})
        if (not isinstance(locator,dict) or set(locator) not in ({'environment_variable','allowed_hosts'}, {'url','allowed_hosts'})
                or not isinstance(locator['allowed_hosts'],list) or not locator['allowed_hosts']):
            raise ValueError('Missing download locator or host allowlist')
        if 'environment_variable' in locator and not re.fullmatch('[A-Z][A-Z0-9_]+',locator['environment_variable']):
            raise ValueError('Invalid secure locator reference')
        if 'url' in locator: validate_url(locator['url'],locator['allowed_hosts'])
        if 'member_manifest' in artifact:
            ref = artifact['member_manifest']; relative(ref['repository_path'])
            linked = repository / ref['repository_path']
            if raw.sha256_file(linked) != ref['sha256']: raise ValueError('Linked member manifest SHA256 mismatch')
            source = read_json(linked)
            members = [{'archive_path':f'codex/{i["area"]}/{PROJECT_NAME}/{i["relative_path"]}',
                        **{k:i[k] for k in ('area','relative_path','sha256','size_bytes')}} for _,i in sorted(source['inputs'].items())]
            if source['input_count'] != len(members) or source['total_bytes'] != sum(i['size_bytes'] for i in members):
                raise ValueError('Linked member inventory inconsistent')
        else: members = artifact.get('members',[])
        if not isinstance(members,list) or not members or len(members) != artifact.get('member_count'):
            raise ValueError('Missing/invalid restoration mapping')
        names = set()
        for member in members:
            if not isinstance(member,dict): raise ValueError('Member mapping must be an object')
            relative(member.get('relative_path')); relative(member.get('archive_path'))
            if (member.get('area') not in {'data','runs'} or not sha(member.get('sha256'))
                    or type(member.get('size_bytes')) is not int or not 0 <= member['size_bytes'] <= 2*1024**3
                    or member['archive_path'] != f'codex/{member["area"]}/{PROJECT_NAME}/{member["relative_path"]}'
                    or member['archive_path'].casefold() in names):
                raise ValueError('Unsafe or duplicate archive member mapping')
            names.add(member['archive_path'].casefold())
            key=(member['area'],member['relative_path'].casefold())
            if key in destinations and destinations[key] != member['sha256']:
                raise ValueError('Conflicting canonical destination hashes')
            destinations[key]=member['sha256']
        if artifact['format']=='file' and (len(members)!=1 or members[0]['sha256']!=artifact['sha256'] or members[0]['size_bytes']!=artifact['size_bytes']):
            raise ValueError('Raw-file restoration mapping disagrees with download')
        if sum(m['size_bytes'] for m in members) != artifact.get('expanded_size_bytes'):
            raise ValueError('Uncompressed size expectation mismatch')
        result[aid]={**artifact,'members':members}
    for artifact in result.values():
        if any(d not in result for d in artifact.get('dependencies',[])): raise ValueError('Unknown dependency artifact')
    def visit(aid, stack):
        if aid in stack: raise ValueError('Artifact dependency cycle')
        for other in result[aid].get('dependencies',[]): visit(other,stack|{aid})
    for aid in result: visit(aid,set())
    return result


def validate_url(url, hosts):
    try: parsed=urlsplit(url)
    except ValueError: raise ValueError('Invalid artifact URL') from None
    host=(parsed.hostname or '').lower()
    allowed=any(host==h or (h.startswith('*.') and host.endswith('.'+h[2:])) for h in hosts)
    if (parsed.scheme!='https' or not allowed or parsed.username or parsed.password
            or parsed.port not in (None,443) or parsed.fragment or any(ord(c)<32 for c in url)):
        raise ValueError('Artifact URL/redirect violates HTTPS host allowlist')


class Redirects(HTTPRedirectHandler):
    def __init__(self, hosts): self.hosts=hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl,self.hosts)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def destination(member, paths):
    root=paths.project_data_dir if member['area']=='data' else paths.project_runs_dir
    return root / member['relative_path']


def cache_path(artifact, paths):
    return paths.project_data_dir/'artifacts/cache'/(artifact['sha256']+'--'+artifact['filename'])


def file_status(path, expected):
    try:
        with raw._read_file(path) as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode): raise ValueError('Nonregular artifact destination')
            if info.st_size != expected['size_bytes']: return 'wrong_hash'
            h=hashlib.sha256()
            while block:=stream.read(1024*1024): h.update(block)
            return 'verified' if h.hexdigest()==expected['sha256'] else 'wrong_hash'
    except FileNotFoundError:
        # Missing is allowed, but no dangling symlink component may be followed.
        current=path
        while current != current.parent:
            if current.is_symlink(): raise ValueError('Symlink artifact path rejected')
            current=current.parent
        return 'missing'


def status(artifact, paths):
    files=[{'area':m['area'],'relative_path':m['relative_path'],'status':file_status(destination(m,paths),m),
            'expected_sha256':m['sha256'],'expected_size_bytes':m['size_bytes']} for m in artifact['members']]
    return {'artifact_id':artifact['artifact_id'],'files':files,
            'complete':all(m['status']=='verified' for m in files),
            'cache':file_status(cache_path(artifact,paths),artifact),
            'locator_configured':bool(artifact['locator'].get('url') or os.environ.get(artifact['locator'].get('environment_variable','')))}


def preflight(artifact, paths):
    report=status(artifact,paths)
    if report['cache']=='wrong_hash' or any(f['status']=='wrong_hash' for f in report['files']):
        raise ValueError('Existing wrong-hash artifact preserved; resolve collision explicitly')
    return report


@contextmanager
def atomic_destination(path):
    """No-replace publication; only our own temporary file is removed."""
    with raw._directory(path.parent,create=True) as parent:
        temporary='.'+path.name+'.'+secrets.token_hex(12)+'.partial'
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600,dir_fd=parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                yield stream
                stream.flush();os.fsync(stream.fileno())
            os.link(temporary,path.name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
            os.fsync(parent)
        finally: os.unlink(temporary,dir_fd=parent)


def fetch(artifact, paths, *, opener=None, timeout=30):
    before=preflight(artifact,paths)
    if before['cache']=='verified': return {'artifact_id':artifact['artifact_id'],'action':'verified_cache_reused','bytes_downloaded':0}
    if before['complete']: return {'artifact_id':artifact['artifact_id'],'action':'verified_destinations_reused','bytes_downloaded':0}
    locator=artifact['locator'];url=locator.get('url') or os.environ.get(locator.get('environment_variable',''))
    if not url: raise ValueError('Authorized locator required via '+locator['environment_variable'])
    validate_url(url,locator['allowed_hosts'])
    opener=opener or build_opener(HTTPSHandler(),Redirects(locator['allowed_hosts']))
    start=time.monotonic();size=0;digest=hashlib.sha256()
    try:
        with opener.open(Request(url,headers={'User-Agent':'stability-artifact-restore/1','Accept-Encoding':'identity'}),timeout=timeout) as response:
            validate_url(response.geturl(),locator['allowed_hosts'])
            if response.status!=200: raise ValueError('Unexpected artifact HTTP status')
            length=response.headers.get('Content-Length')
            if length is not None and (not length.isdecimal() or int(length)!=artifact['size_bytes']):
                raise ValueError('Server length disagrees with authenticated artifact size')
            if response.headers.get('Content-Encoding','identity').lower() not in ('identity',''): raise ValueError('Unexpected HTTP content encoding')
            if 'text/html' in response.headers.get('Content-Type','').lower(): raise ValueError('HTML response is not an artifact')
            with atomic_destination(cache_path(artifact,paths)) as output:
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>artifact['size_bytes'] or time.monotonic()-start>600: raise ValueError('Artifact size/time bound exceeded')
                    if size==len(chunk) and artifact['format']=='tar.gz' and not chunk.startswith(b'\x1f\x8b'):
                        raise ValueError('Expected gzip archive, not HTML/error content')
                    digest.update(chunk);output.write(chunk)
                if size!=artifact['size_bytes'] or digest.hexdigest()!=artifact['sha256']:
                    raise ValueError('Downloaded artifact SHA256/length mismatch')
    except (ValueError,OSError) as error:
        # Never emit capability-bearing URLs or redirect exception strings.
        if isinstance(error,ValueError): raise
        raise ValueError('Artifact HTTPS acquisition failed ('+type(error).__name__+'); locator omitted') from None
    return {'artifact_id':artifact['artifact_id'],'action':'downloaded','bytes_downloaded':size,
            'sha256':digest.hexdigest(),'cache_relative_path':str(cache_path(artifact,paths).relative_to(paths.project_data_dir))}


def check_archive(artifact, paths):
    archive=cache_path(artifact,paths)
    if file_status(archive,artifact)!='verified': raise ValueError('Authenticated cache archive is required')
    if artifact['format']=='file': return
    expected={m['archive_path']:m for m in artifact['members']};seen=set()
    with raw._read_file(archive) as stream,tarfile.open(fileobj=stream,mode='r:gz') as bundle:
        for member in bundle:
            relative(member.name)
            if (not member.isreg() or member.issparse() or member.pax_headers or member.name not in expected
                    or member.name in seen or len(seen)>=len(expected)):
                raise ValueError('Unexpected/unsafe/duplicate archive entry')
            item=expected[member.name];seen.add(member.name)
            if member.size!=item['size_bytes']: raise ValueError('Archive member size mismatch')
            digest=hashlib.sha256();size=0
            with bundle.extractfile(member) as source:
                while chunk:=source.read(1024*1024):digest.update(chunk);size+=len(chunk)
            if size!=item['size_bytes'] or digest.hexdigest()!=item['sha256']: raise ValueError('Extracted-file SHA256 mismatch')
    if seen!=set(expected): raise ValueError('Missing expected archive member')
    # Consume gzip trailers too, with a bound on padding/trailing expansion.
    size=0;limit=artifact['expanded_size_bytes']+len(expected)*4096+65536
    with raw._read_file(archive) as stream,gzip.GzipFile(fileobj=stream) as gz:
        while chunk:=gz.read(1024*1024):
            size+=len(chunk)
            if size>limit: raise ValueError('Archive expansion bound exceeded')


def restore(artifact, paths, *, opener=None):
    before=preflight(artifact,paths)
    if before['complete']: return {'artifact_id':artifact['artifact_id'],'action':'all_destinations_reused','status':before,'bytes_downloaded':0}
    acquisition=fetch(artifact,paths,opener=opener)
    check_archive(artifact,paths)  # Entire archive validated before any file publication.
    expected={m['archive_path']:m for m in artifact['members']};written=[]
    def publish(member, source):
        target=destination(member,paths)
        if file_status(target,member)=='verified': return
        if file_status(target,member)!='missing': raise ValueError('Destination collision preserved')
        digest=hashlib.sha256();size=0
        with atomic_destination(target) as output:
            while chunk:=source.read(1024*1024):
                size+=len(chunk)
                if size>member['size_bytes']: raise ValueError('Member expansion bound exceeded')
                digest.update(chunk);output.write(chunk)
            if size!=member['size_bytes'] or digest.hexdigest()!=member['sha256']: raise ValueError('Materialized-file SHA256 mismatch')
        written.append({'area':member['area'],'relative_path':member['relative_path'],'sha256':member['sha256']})
    archive=cache_path(artifact,paths)
    if artifact['format']=='file':
        with raw._read_file(archive) as stream:publish(artifact['members'][0],stream)
    else:
        with raw._read_file(archive) as stream,tarfile.open(fileobj=stream,mode='r:gz') as bundle:
            for member in bundle:
                with bundle.extractfile(member) as source:publish(expected[member.name],source)
    after=status(artifact,paths)
    if not after['complete']: raise ValueError('Restoration did not authenticate all destinations')
    return {'artifact_id':artifact['artifact_id'],'action':'restored','download':acquisition,'published':written,'status':after}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['list','status','fetch','restore','verify','dry-run'])
    parser.add_argument('artifact_ids',nargs='*')
    parser.add_argument('--registry')
    parser.add_argument('--workspace-root',help='codex root containing data/ and runs/; never a home-directory tar extraction')
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--receipt',help='New JSON file under project data/artifacts or project runs; never replaced')
    args=parser.parse_args(argv)
    try:
        artifacts=load_registry(args.registry);paths=storage(args.workspace_root)
        selected=list(artifacts) if args.all or args.operation=='list' and not args.artifact_ids else args.artifact_ids
        if not selected or any(a not in artifacts for a in selected): raise ValueError('Select registered artifact IDs or --all')
        report=[];failed=False
        for aid in selected:
            item=artifacts[aid]
            if args.operation=='list':report.append({k:item[k] for k in ['artifact_id','version','role','filename','size_bytes','sha256','member_count']})
            elif args.dry_run or args.operation=='dry-run':
                report.append({'artifact_id':aid,'planned_cache_relative_path':str(cache_path(item,paths).relative_to(paths.project_data_dir)),
                    'restoration_mapping':item['members'],'current':status(item,paths),'writes_performed':False})
            elif args.operation in ('status','verify'):
                found=status(item,paths);report.append(found)
                if args.operation=='verify' and not found['complete']:failed=True
            elif args.operation=='fetch':report.append(fetch(item,paths))
            else:report.append(restore(item,paths))
        receipt={'schema_version':1,'operation':args.operation,'artifacts':report,'success':not failed,
                 'training_executed':False,'locator_values_recorded':False}
        if args.receipt and not (args.dry_run or args.operation=='dry-run'):
            target=Path(args.receipt).expanduser().absolute()
            if not (target.is_relative_to(paths.project_data_dir/'artifacts') or target.is_relative_to(paths.project_runs_dir)):
                raise ValueError('Receipt outside controlled artifact/run storage')
            with atomic_destination(target) as stream:stream.write(raw.json_report(receipt).encode())
        print(raw.json_report(receipt),end='');return int(failed)
    except (ValueError,OSError,tarfile.TarError,EOFError,KeyError,TypeError) as error:
        # Controlled diagnostics contain IDs/paths, never network exception URLs.
        print(raw.json_report({'success':False,'error_type':type(error).__name__,
                              'error':str(error) if not 'http' in str(error).lower() else 'HTTPS/artifact error; locator omitted'}),end='')
        return 1
