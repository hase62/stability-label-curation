"""Small synthetic source snapshots only. Never import external source or torch."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import bigmhc_source_audit as a
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main

COMMIT = 'a' * 40


class Response(io.BytesIO):
    def __init__(self, data, url, headers=None, status=200):
        super().__init__(data); self.url = url; self.headers = headers or {}; self.status = status
    def geturl(self): return self.url


class Opener:
    def __init__(self, data=b'# fixture\n', headers=None, url=None, fail=False):
        self.data, self.headers, self.url, self.fail = data, headers, url, fail
        self.requests = []
    def open(self, req, timeout):
        self.requests.append((req.full_url, timeout))
        if self.fail: raise OSError('synthetic network failure')
        return Response(self.data, self.url or req.full_url, self.headers)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.paths = resolve_paths({'CODEX_ROOT': str(self.root)})
        self.opener = Opener()
        p = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No actual network'))
        p.start(); self.addCleanup(p.stop)
    def fetch(self, files=('src/train.py',), **kwargs):
        return a.fetch_sources(COMMIT, files, paths=self.paths, opener_factory=lambda c,p: self.opener, **kwargs)
    def target(self): return self.paths.project_data_dir / 'bigmhc_source' / COMMIT / 'src/train.py'

    def test_source_allowlist_rejects_data_weights_and_extra_code(self):
        for path in ['data/pseudoseqs.csv', 'datasets.zip', 'models/bat512/0.lyr', 'src/extra.py']:
            with self.subTest(path=path), self.assertRaises(ValueError): self.fetch([path])
        self.assertEqual(self.opener.requests, [])
    def test_traversal_and_absolute_paths_rejected(self):
        for path in ['../train.py', '/src/train.py', 'src/../src/train.py', 'src\\train.py']:
            with self.assertRaises(ValueError): a.validate_source_path(path)
    def test_unpinned_url_rejected(self):
        for commit in ['master', 'main', 'a'*7, 'A'*40, 'a'*39]:
            with self.assertRaises(ValueError): a.source_url(commit, 'src/train.py')
        with self.assertRaises(ValueError): a.validate_source_url(a.source_url(COMMIT,'src/train.py')+'?x=1', COMMIT, 'src/train.py')
    def test_http_and_redirect_host_rejected(self):
        for url in [a.source_url(COMMIT,'src/train.py').replace('https:', 'http:'), 'https://example.org/train.py',
                    a.source_url(COMMIT,'src/train.py').replace('/'+COMMIT+'/', '/master/')]:
            with self.assertRaises(ValueError): a.validate_source_url(url, COMMIT, 'src/train.py')
            with self.assertRaises(ValueError): a._SourceRedirect(COMMIT,'src/train.py').redirect_request(None,None,302,'',{},url)
    def test_final_response_url_validated(self):
        self.opener.url = 'https://example.org/not-source'
        with self.assertRaises(ValueError): self.fetch()
        self.assertFalse(self.target().exists())
    def test_success_stream_and_exact_sha(self):
        result = self.fetch(); entry = result['files'][0]
        self.assertEqual(entry['sha256'], hashlib.sha256(self.opener.data).hexdigest())
        self.assertEqual(self.target().read_bytes(), self.opener.data)
        self.assertEqual(entry['publisher_sha256'], None)
        self.assertEqual(self.opener.requests[0][1], 30)
    def test_existing_source_preserved_without_new_request(self):
        self.fetch(); before = self.target().read_bytes(); self.opener.requests.clear(); self.opener.data = b'changed'
        result = self.fetch()
        self.assertEqual(result['files'][0]['acquisition'], 'reused')
        self.assertEqual(self.target().read_bytes(), before); self.assertEqual(self.opener.requests, [])
    def test_server_length_cap_rejected_before_body(self):
        self.opener.headers = {'Content-Length': str(a.FILE_CAP + 1)}
        with self.assertRaisesRegex(ValueError, 'Content-Length'): self.fetch()
        self.assertFalse(self.target().exists())
    def test_stream_overrun_rejected_and_cleanup(self):
        self.opener.data = b'#'+b'x'*a.FILE_CAP
        with self.assertRaisesRegex(ValueError, 'cap'): self.fetch()
        self.assertFalse(self.target().exists())
        self.assertEqual(list(self.target().parent.glob('*.partial')), [])
    def test_aggregate_cap_including_reused_files(self):
        self.opener.data = b'# synthetic\n'
        with patch.object(a, 'TOTAL_CAP', 20):
            with self.assertRaisesRegex(ValueError, 'cap'):
                self.fetch(['src/train.py', 'src/predict.py'])
        self.assertTrue(self.target().exists())
        self.assertFalse(self.target().with_name('predict.py').exists())
    def test_invalid_download_or_python_not_published(self):
        for data in [b'<html>no</html>', b'version https://git-lfs.github.com/spec/v1', b'def broken(:']:
            self.opener.data = data
            with self.assertRaises(ValueError): self.fetch()
            self.assertFalse(self.target().exists())
    def test_download_failure_does_not_leave_completed_file(self):
        self.opener.fail = True
        with self.assertRaises(OSError): self.fetch()
        self.assertFalse(self.target().exists())
    def test_length_mismatch_and_encoding_rejected(self):
        for headers in [{'Content-Length':'999'}, {'Content-Encoding':'gzip'}]:
            self.opener.headers = headers
            with self.assertRaises(ValueError): self.fetch()
        self.assertFalse(self.target().exists())
    def test_symlink_destination_and_parent_rejected(self):
        self.target().parent.mkdir(parents=True); other = self.root/'other'; other.write_text('original')
        self.target().symlink_to(other)
        with self.assertRaises(OSError): self.fetch()
        self.assertEqual(other.read_text(), 'original')
    def test_symlink_root_rejected(self):
        parent = self.paths.project_data_dir/'bigmhc_source'; parent.mkdir(parents=True)
        other = self.root/'other'; other.mkdir(); (parent/COMMIT).symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError): self.fetch()
    def test_project_data_alias_cannot_write_another_project(self):
        self.paths.data_root.mkdir(parents=True)
        other=self.root/'another-project';other.mkdir()
        (self.paths.data_root/'stability-label-curation').symlink_to(other,target_is_directory=True)
        resolved=resolve_paths({'CODEX_ROOT':str(self.root)})
        with self.assertRaisesRegex(ValueError,'alias another project'):
            a.fetch_sources(COMMIT,['src/train.py'],paths=resolved,opener_factory=lambda c,p:self.opener)
        self.assertEqual(list(other.iterdir()),[])
    def test_atomic_no_overwrite_and_own_partial_cleanup(self):
        destination = self.root/'dest'; destination.mkdir(); (destination/'source').write_bytes(b'old')
        with self.assertRaises(FileExistsError): a._publish_bytes(destination, 'source', b'new')
        self.assertEqual((destination/'source').read_bytes(), b'old')
        self.assertEqual(list(destination.glob('.*.partial')), [])
    def test_finite_timeout(self):
        for timeout in (0, float('inf'), float('nan'), 121):
            with self.assertRaises(ValueError): self.fetch(timeout=timeout)


class StaticTests(unittest.TestCase):
    def test_invalid_python_rejected(self):
        with self.assertRaises(ValueError): a.parse_source('def broken(:')
    def test_external_code_is_not_executed(self):
        tree = a.parse_source('raise RuntimeError("MUST NOT RUN")\nimport nonexistent_external_dependency\ndef f():\n return 3\n')
        self.assertIn('f', a.syntax_index(tree))
    def test_static_index_determinism_and_line_refs(self):
        source = '\nclass Fixture:\n def f(self):\n  return unknown_call()\n'
        one = a.syntax_index(a.parse_source(source)); two = a.syntax_index(a.parse_source(source))
        self.assertEqual(one, two); self.assertEqual(one['Fixture.f']['line'], 3)
        self.assertEqual(one['Fixture.f']['calls'][0]['target'], 'unknown_call')
    def test_transfer_layer_literal_identification(self):
        source = 'class BigMHC:\n def tllayers():\n  return ["final.weight", "final.bias"]\n'
        facts = a.static_facts({'src/bigmhc.py': a.parse_source(source)})
        self.assertEqual(facts['transfer_parameter_names_literal'], ['final.weight', 'final.bias'])
        self.assertFalse(facts['weights_opened_or_loaded'])
    def test_unknown_dynamic_layers_remain_unresolved(self):
        source = 'class BigMHC:\n def tllayers():\n  return external_function()\n'
        self.assertIsNone(a.static_facts({'src/bigmhc.py': a.parse_source(source)})['transfer_parameter_names_literal'])
    def test_non_JSON_literal_returns_not_emitted(self):
        result=a.syntax_index(a.parse_source('def f():\n return [b"binary"]\ndef g():\n return 1e999\n'))
        self.assertEqual(result['f']['literal_returns'],[])
        self.assertEqual(result['g']['literal_returns'],[])
    def test_IM_skip_and_loss_call_detection(self):
        source = 'def train(model,data,args):\n loss = torch.nn.BCEWithLogitsLoss()\n for batch in data:\n  if args.transferlearn and not tgt.sum():\n   continue\n'
        facts = a.static_facts({'src/train.py': a.parse_source(source)})
        self.assertEqual(facts['loss_constructor_call_lines'], [2])
        self.assertEqual(facts['all_negative_transfer_continue_lines'], [4])
    def test_zero_positive_group_omitted(self):
        result = a.batch_count_diagnostic(0,100,32)
        self.assertEqual(result['planned_batches'], 0); self.assertEqual(result['omitted_negative_references'], 100)
        self.assertIn('IndexError', result['all_groups_without_positives_consequence'])
    def test_no_negative_group_emits_positives(self):
        result = a.batch_count_diagnostic(5,0,32)
        self.assertEqual(result['positive_row_references'], 5); self.assertEqual(result['negative_row_references'], 0)
    def test_sparse_positive_consumption_not_equal_to_group_size(self):
        result = a.batch_count_diagnostic(1,9999,32)
        self.assertEqual(result['planned_batches'], 1); self.assertEqual(result['negative_row_references'], 32)
        self.assertEqual(result['omitted_negative_references'], 9967)
    def test_requested_maxbat_not_a_hard_bound(self):
        result = a.batch_count_diagnostic(1,3,2)
        self.assertEqual(result['maximum_planned_batch_size'], 3); self.assertTrue(result['may_exceed_requested_maxbat'])
    def test_float_truncation_and_no_replacement(self):
        result = a.batch_count_diagnostic(1,9999,32768)
        self.assertEqual(result['negative_step'], 98)
        self.assertFalse(result['sampling_with_replacement']); self.assertFalse(result['actual_consumption_verified'])
    def test_invalid_and_empty_count_inputs(self):
        self.assertEqual(a.batch_count_diagnostic(0,0,32)['status'], 'empty_group')
        for values in [(-1,1,32), (1,2,0), (True,3,32)]:
            with self.assertRaises(ValueError): a.batch_count_diagnostic(*values)


class OfflineAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.env = {'CODEX_ROOT': str(self.root)}
        self.paths = resolve_paths(self.env)
        self.snapshot = self.paths.project_data_dir/'fixture-source'; (self.snapshot/'src').mkdir(parents=True)
        self.config = json.loads((self.paths.repository_root/a.CONFIG).read_text())
        self.config.update(commit=COMMIT, source_files=[], metadata_files=[], expected_functions={}, reviewed_findings=[])
        self.source = {'src/train.py': 'raise RuntimeError("DO NOT EXECUTE")\ndef train(model,data,args):\n loss = torch.nn.BCEWithLogitsLoss()\n',
                       'src/bigmhc.py': 'class BigMHC:\n def tllayers():\n  return ["final.weight", "final.bias"]\n',
                       'src/dataset.py': 'class Dataset:\n def makebats(self):\n  return None\n',
                       'src/mhcenc.py': 'class MHCEncoder:\n def nearestMHC(self, text):\n  return unknown_reference(text)\n'}
        for path, text in self.source.items():
            (self.snapshot/path).write_text(text)
            scopes = a.syntax_index(a.parse_source(text)); self.config['expected_functions'][path] = list(scopes)
            for function, info in scopes.items():
                category='allele' if 'mhcenc' in path else ('transfer' if 'bigmhc' in path else 'training')
                self.config['reviewed_findings'].append({'id':path+function,'category':category,
                    'claim':'Synthetic reviewed behavior only', 'limitations':'Fixture; no biological claim',
                    'scopes':[{'path':path,'function':function,'source_sha256':raw.sha256_file(self.snapshot/path),'ast_sha256':info['ast_sha256']}]})
        self.config_path = self.root/'evidence.json'; self.refresh()
        p=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Offline only'))
        p.start();self.addCleanup(p.stop)
    def refresh(self):
        self.config['source_files']=[{'path':p,'byte_size':(self.snapshot/p).stat().st_size,
            'sha256':raw.sha256_file(self.snapshot/p),'source_url':a.source_url(COMMIT,p)} for p in self.source]
        self.config_path.write_text(json.dumps(self.config))
    def result(self): return a.inspect(paths=self.paths,snapshot=self.snapshot,evidence_path=self.config_path)
    def add_tree(self, bad=False):
        tree={'sha':COMMIT,'truncated':False,'tree':[]}
        for entry in self.config['source_files']:
            data=(self.snapshot/entry['path']).read_bytes()
            tree['tree'].append({'type':'blob','path':entry['path'],'size':len(data),
                'sha':'b'*40 if bad else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
        p=self.snapshot/'repository_tree.json';p.write_text(json.dumps(tree))
        self.config['metadata_files']=[{'path':p.name,'byte_size':p.stat().st_size,'sha256':raw.sha256_file(p)}]
        self.config_path.write_text(json.dumps(self.config))
    def test_hash_validation_before_AST_parse(self):
        (self.snapshot/'src/train.py').write_text('changed')
        with patch.object(a,'parse_source',side_effect=AssertionError('hash first')):
            with self.assertRaisesRegex(ValueError,'identity'):self.result()
    def test_known_source_AST_matches(self):
        reports=self.result().reports
        self.assertTrue(all(f['status']=='locally_verified_static_path' for f in reports['bigmhc_transfer_lineage.json']['findings']))
    def test_changed_semantics_unresolved_after_explicit_repin(self):
        (self.snapshot/'src/bigmhc.py').write_text('class BigMHC:\n def tllayers():\n  return ["different.weight"]\n');self.refresh()
        findings=self.result().reports['bigmhc_transfer_lineage.json']['findings']
        self.assertTrue(any(f['status']=='unresolved_changed_or_missing_source' for f in findings))
    def test_changed_training_loss_not_reported_as_reviewed(self):
        path=self.snapshot/'src/train.py'
        path.write_text(path.read_text().replace('BCEWithLogitsLoss','MSELoss'));self.refresh()
        report=self.result().reports['bigmhc_training_semantics.json']
        self.assertEqual(report['static_facts']['loss_constructor_call_lines'],[])
        self.assertTrue(any(f['status']=='unresolved_changed_or_missing_source' for f in report['findings']))
    def test_missing_function_schema_reported(self):
        (self.snapshot/'src/bigmhc.py').write_text('class BigMHC: pass\n');self.refresh()
        result=self.result().reports['bigmhc_source_inventory.json']
        self.assertEqual(result['schema_checks']['src/bigmhc.py']['missing'],['BigMHC.tllayers'])
    def test_no_checkpoint_metadata_is_not_clean_ancestry(self):
        meta=self.result().reports['bigmhc_transfer_lineage.json']['model_directory_metadata']
        self.assertEqual(meta['status'],'unavailable');self.assertFalse(meta['checkpoint_ancestry_verified'])
    def test_tree_blob_identity_without_blob_payload_fetch(self):
        self.add_tree();self.assertEqual(self.result().reports['bigmhc_source_inventory.json']['commit'],COMMIT)
        self.add_tree(bad=True)
        with self.assertRaisesRegex(ValueError,'blob identity'):self.result()
    def test_published_hash_not_locally_verified(self):
        data=self.result().reports['bigmhc_published_data_manifest.json']
        self.assertTrue(all(e['local_sha256'] is None and e['downloaded'] is False for e in data['published_checksums']))
        self.config['published_data']['published_checksums'][0]['local_sha256']='d'*64
        self.config_path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'Publisher claims'):self.result()
    def test_unknown_HLA_not_given_a_resolution(self):
        report=self.result().reports['bigmhc_allele_mapping_risks.json']
        self.assertFalse(report['unknown_alleles_are_accepted_as_equivalent'])
        self.assertFalse(report['coverage_of_72_DTU_alleles_verified'])
    def test_deterministic_read_only_and_no_source_execution(self):
        before={p:(self.snapshot/p).read_bytes() for p in self.source}; listing=list(self.root.rglob('*'))
        first,second=self.result(),self.result()
        self.assertEqual(raw.json_report(first.reports),raw.json_report(second.reports))
        self.assertEqual(before,{p:(self.snapshot/p).read_bytes() for p in self.source})
        self.assertEqual(listing,list(self.root.rglob('*')));self.assertFalse(self.paths.project_runs_dir.exists())
    def test_CLI_offline_override_and_compatibility(self):
        out=io.StringIO()
        with redirect_stdout(out),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['bigmhc','source-audit','--json','--snapshot',str(self.snapshot),'--evidence',str(self.config_path)],env=self.env),0)
        self.assertEqual(json.loads(out.getvalue())['bigmhc_source_inventory.json']['commit'],COMMIT)
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['sources','validate'],env=self.env),0)
    def test_no_weight_or_unknown_source_can_be_read(self):
        self.config['source_files'][0]['path']='models/0.lyr';self.config_path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'allowlist'):self.result()
    def test_safe_report_run_inputs_and_no_overwrite(self):
        result=self.result();run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],inputs=[p['path'] for p in result.inputs],allow_dirty=True)
        receipt=a.write_reports(result,run/'reports',paths=self.paths);self.assertEqual(len(receipt['reports']),6)
        with self.assertRaises(FileExistsError):a.write_reports(result,run/'reports',paths=self.paths)
        with self.assertRaises(ValueError):a.write_reports(result,self.root/'reports',paths=self.paths)
    def test_unrecorded_inputs_rejected(self):
        run=runs.create_run(paths=self.paths,kind='test',argv=['fixture'],allow_dirty=True)
        with self.assertRaises(ValueError):a.write_reports(self.result(),run/'reports',paths=self.paths)
    def test_source_symlink_rejected(self):
        other=self.root/'other';other.write_bytes((self.snapshot/'src/train.py').read_bytes())
        (self.snapshot/'src/train.py').unlink();(self.snapshot/'src/train.py').symlink_to(other)
        with self.assertRaises(OSError):self.result()


if __name__=='__main__':unittest.main()
