"""Deterministic fake HTTPS and small adversarial tar fixtures; no network/data payloads."""
from contextlib import redirect_stdout
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability_label_curation import artifact_restore as r


def sha(blob):return hashlib.sha256(blob).hexdigest()


def tar_bytes(entries):
    output=io.BytesIO()
    with gzip.GzipFile(fileobj=output,mode='wb',filename='',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            for name,blob,kind in entries:
                info=tarfile.TarInfo(name);info.size=len(blob);info.type=kind;info.mode=0o600
                if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):info.linkname='/escape'
                tar.addfile(info,io.BytesIO(blob) if kind==tarfile.REGTYPE else None)
    return output.getvalue()


class Response(io.BytesIO):
    def __init__(self,blob,headers=None,url='https://files.example.test/archive'):
        super().__init__(blob);self.status=200;self.url=url
        self.headers={'Content-Length':str(len(blob)),'Content-Type':'application/gzip'} if headers is None else headers
    def geturl(self):return self.url


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.paths=r.storage(self.root/'workspace')
        self.members=[{'archive_path':'codex/data/stability-label-curation/source/a.txt','area':'data','relative_path':'source/a.txt','sha256':sha(b'alpha'),'size_bytes':5},
                      {'archive_path':'codex/runs/stability-label-curation/run/reports/b.txt','area':'runs','relative_path':'run/reports/b.txt','sha256':sha(b'beta'),'size_bytes':4}]
        self.blob=tar_bytes([(m['archive_path'],b'alpha' if i==0 else b'beta',tarfile.REGTYPE) for i,m in enumerate(self.members)])
        self.a={'artifact_id':'fixture','version':'1','role':'external_input','format':'tar.gz','filename':'fixture.tar.gz',
                'sha256':sha(self.blob),'size_bytes':len(self.blob),'expanded_size_bytes':9,'member_count':2,'members':deepcopy(self.members),
                'locator':{'environment_variable':'SLC_TEST_URL','allowed_hosts':['files.example.test']},'dependencies':[]}
        self.registry=self.root/'registry.json';self.save_registry(self.a)
        self.calls=0
        self.net=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No external network in tests'))
        self.net.start();self.addCleanup(self.net.stop)
        self.env=patch.dict('os.environ',{'SLC_TEST_URL':'https://files.example.test/archive?secret=never-record'})
        self.env.start();self.addCleanup(self.env.stop)

    def save_registry(self,*artifacts):
        self.registry.write_text(json.dumps({'schema_version':1,'project_name':'stability-label-curation','artifacts':list(artifacts)}))

    def client(self,response=None):
        def open_(request,timeout):
            self.calls+=1;self.assertEqual(timeout,30)
            return response or Response(self.blob)
        return SimpleNamespace(open=open_)

    def seed_cache(self,blob=None):
        path=r.cache_path(self.a,self.paths);path.parent.mkdir(parents=True)
        path.write_bytes(self.blob if blob is None else blob);return path

    def test_registry_linked_production_manifests(self):
        items=r.load_registry();self.assertEqual(items['gpu-inputs-23af9966']['member_count'],21)
        self.assertEqual(sum(m['size_bytes'] for m in items['gpu-inputs-23af9966']['members']),207979774)
        self.assertEqual(items['el-positive-scores-task2-13']['member_count'],2)

    def test_registry_rejects_missing_hash_locator_or_mapping(self):
        for key in ('sha256','locator','members'):
            broken=deepcopy(self.a);broken.pop(key);self.save_registry(broken)
            with self.assertRaises((ValueError,KeyError)):r.load_registry(self.registry)

    def test_registry_rejects_destinations_and_duplicate_ids(self):
        for value in ('../escape','/absolute','a\\b','a//b','a/./b','C:/file'):
            a=deepcopy(self.a);a['members'][0]['relative_path']=value;self.save_registry(a)
            with self.assertRaises(ValueError):r.load_registry(self.registry)
        self.save_registry(self.a,self.a)
        with self.assertRaises(ValueError):r.load_registry(self.registry)

    def test_conflicting_destination_hashes(self):
        a=deepcopy(self.a);a['artifact_id']='second';a['members'][0]['sha256']='0'*64
        self.save_registry(self.a,a)
        with self.assertRaisesRegex(ValueError,'Conflicting'):r.load_registry(self.registry)

    def test_strict_https_redirect_allowlist(self):
        for url in ('http://files.example.test/a','https://files.example.test.evil/a','https://user:pass@files.example.test/a','https://files.example.test:123/a'):
            with self.assertRaises(ValueError):r.validate_url(url,['files.example.test'])
        with self.assertRaises(ValueError):r.Redirects(['files.example.test']).redirect_request(None,None,302,'',{},'http://files.example.test/a')

    def test_complete_download_restore_and_portable_layout(self):
        result=r.restore(self.a,self.paths,opener=self.client())
        self.assertEqual(self.calls,1);self.assertEqual(len(result['published']),2)
        for m in self.members:self.assertEqual(r.file_status(r.destination(m,self.paths),m),'verified')
        self.assertTrue(r.cache_path(self.a,self.paths).is_relative_to(self.paths.project_data_dir/'artifacts/cache'))

    def test_cache_reuse_without_locator(self):
        self.seed_cache()
        with patch.dict('os.environ',{},clear=True):
            result=r.restore(self.a,self.paths,opener=SimpleNamespace(open=lambda *a,**k:self.fail('No redownload')))
        self.assertEqual(result['download']['bytes_downloaded'],0)

    def test_valid_destinations_reused_even_without_cache(self):
        r.restore(self.a,self.paths,opener=self.client())
        # Only remove the synthetic cache in this private temporary fixture.
        r.cache_path(self.a,self.paths).unlink()
        result=r.restore(self.a,self.paths,opener=SimpleNamespace(open=lambda *a,**k:self.fail('No network')))
        self.assertEqual(result['action'],'all_destinations_reused')

    def test_wrong_cache_hash_never_overwritten(self):
        cache=self.seed_cache(b'bad')
        with self.assertRaises(ValueError):r.fetch(self.a,self.paths,opener=self.client())
        self.assertEqual(cache.read_bytes(),b'bad');self.assertEqual(self.calls,0)

    def test_wrong_destination_fails_before_download(self):
        target=r.destination(self.members[0],self.paths);target.parent.mkdir(parents=True);target.write_bytes(b'wrong')
        with self.assertRaises(ValueError):r.restore(self.a,self.paths,opener=self.client())
        self.assertEqual(target.read_bytes(),b'wrong');self.assertEqual(self.calls,0)

    def test_html_and_headerless_html_rejected(self):
        for headers in ({'Content-Type':'text/html'},{'Content-Type':'application/octet-stream'}):
            with self.assertRaises(ValueError):r.fetch(self.a,self.paths,opener=self.client(Response(b'<html>denied</html>',headers)))
            self.assertFalse(r.cache_path(self.a,self.paths).exists())
            self.assertFalse(list(self.root.rglob('*.partial')))

    def test_length_and_sha_mismatch_remove_only_partial(self):
        for response in (Response(self.blob,{'Content-Length':'999999999'}),Response(self.blob[:-1]),Response(b'\x1f\x8b'+b'x'*(len(self.blob)-2))):
            with self.assertRaises(ValueError):r.fetch(self.a,self.paths,opener=self.client(response))
            self.assertFalse(r.cache_path(self.a,self.paths).exists());self.assertFalse(list(self.root.rglob('*.partial')))

    def test_missing_locator_does_not_create_cache(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(ValueError,'Authorized locator'):r.fetch(self.a,self.paths)
        self.assertFalse(self.paths.project_data_dir.exists())

    def test_forbidden_redirect_checked_after_response(self):
        with self.assertRaises(ValueError):r.fetch(self.a,self.paths,opener=self.client(Response(self.blob,url='https://evil.example/a')))

    def test_network_exception_redacts_private_url(self):
        def bad(*a,**k):raise OSError('https://private/secret?token=abcdef')
        with self.assertRaises(ValueError) as error:r.fetch(self.a,self.paths,opener=SimpleNamespace(open=bad))
        self.assertNotIn('abcdef',str(error.exception));self.assertNotIn('https://',str(error.exception))

    def malicious(self,entries):
        blob=tar_bytes(entries);a={**self.a,'sha256':sha(blob),'size_bytes':len(blob)}
        cache=r.cache_path(a,self.paths);cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(blob)
        with self.assertRaises((ValueError,tarfile.TarError,OSError,EOFError)):r.check_archive(a,self.paths)
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_traversal_absolute_and_unexpected_members(self):
        for name in ('../escape','/absolute','codex/data/stability-label-curation/extra'):
            self.malicious([(name,b'alpha',tarfile.REGTYPE)])

    def test_symlink_hardlink_and_special_files_rejected(self):
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE,tarfile.DIRTYPE):
            self.malicious([(self.members[0]['archive_path'],b'',kind)])

    def test_duplicate_missing_and_wrong_member_hash(self):
        name=self.members[0]['archive_path']
        for entries in ([(name,b'alpha',tarfile.REGTYPE)],[(name,b'alpha',tarfile.REGTYPE)]*2,
                        [(name,b'wrong',tarfile.REGTYPE),(self.members[1]['archive_path'],b'beta',tarfile.REGTYPE)]):self.malicious(entries)

    def test_full_validation_before_materialization(self):
        blob=tar_bytes([(self.members[0]['archive_path'],b'alpha',tarfile.REGTYPE),('unexpected',b'extra',tarfile.REGTYPE)])
        a={**self.a,'sha256':sha(blob),'size_bytes':len(blob)}
        cache=r.cache_path(a,self.paths);cache.parent.mkdir(parents=True);cache.write_bytes(blob)
        with self.assertRaises(ValueError):r.restore(a,self.paths)
        self.assertFalse(r.destination(self.members[0],self.paths).exists())

    def test_symlink_parent_cannot_escape(self):
        outside=self.root/'outside';outside.mkdir();self.paths.project_data_dir.mkdir(parents=True)
        (self.paths.project_data_dir/'source').symlink_to(outside,target_is_directory=True)
        with self.assertRaises((ValueError,OSError)):r.restore(self.a,self.paths,opener=self.client())
        self.assertEqual(list(outside.iterdir()),[])

    def test_workspace_symlink_alias_rejected(self):
        self.paths.data_root.mkdir(parents=True);outside=self.root/'elsewhere';outside.mkdir()
        (self.paths.data_root/'stability-label-curation').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):r.storage(self.paths.codex_root)

    def test_dryrun_no_writes_no_locator(self):
        out=io.StringIO()
        with patch.dict('os.environ',{},clear=True),redirect_stdout(out):
            code=r.main(['dry-run','fixture','--registry',str(self.registry),'--workspace-root',str(self.paths.codex_root)])
        self.assertEqual(code,0);self.assertFalse(self.paths.codex_root.exists())
        self.assertFalse(json.loads(out.getvalue())['artifacts'][0]['writes_performed'])

    def test_status_verify_json_missing_and_receipt_bounds(self):
        out=io.StringIO()
        with redirect_stdout(out):code=r.main(['verify','fixture','--registry',str(self.registry),'--workspace-root',str(self.paths.codex_root)])
        self.assertEqual(code,1);self.assertFalse(json.loads(out.getvalue())['artifacts'][0]['complete'])
        self.assertNotIn('never-record',out.getvalue())

    def test_invalid_registry_structure_returns_json(self):
        self.registry.write_text('[]')
        out=io.StringIO()
        with redirect_stdout(out):code=r.main(['list','--registry',str(self.registry)])
        self.assertEqual(code,1);self.assertFalse(json.loads(out.getvalue())['success'])

    def test_explicit_receipt_rejects_outside_storage(self):
        out=io.StringIO();target=self.root/'outside.json'
        with redirect_stdout(out):
            code=r.main(['status','fixture','--registry',str(self.registry),
                         '--workspace-root',str(self.paths.codex_root),'--receipt',str(target)])
        self.assertEqual(code,1);self.assertFalse(target.exists())

    def test_gzip_crc_and_expansion_bound(self):
        for blob in (self.blob[:-8]+b'bad CRC!', self.blob+gzip.compress(b'x'*1000000,mtime=0)):
            with self.subTest(kind=len(blob)):
                a={**self.a,'sha256':sha(blob),'size_bytes':len(blob)}
                path=r.cache_path(a,self.paths);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
                with self.assertRaises((ValueError,OSError,EOFError,tarfile.TarError)):
                    r.restore(a,self.paths,opener=self.client())
                self.assertFalse(self.paths.project_runs_dir.exists())

    def test_raw_file_artifact(self):
        blob=b'raw source';member={**self.members[0],'sha256':sha(blob),'size_bytes':len(blob)}
        a={**self.a,'format':'file','sha256':sha(blob),'size_bytes':len(blob),'expanded_size_bytes':len(blob),'members':[member],'member_count':1}
        result=r.restore(a,self.paths,opener=self.client(Response(blob,{'Content-Type':'text/plain'})))
        self.assertTrue(result['status']['complete'])


if __name__=='__main__':unittest.main()
