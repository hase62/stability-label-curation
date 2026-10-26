import json
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation.modern_model_preflight import (
    align_scores, assay_contract, audit_identities, coverage, digest, fixed_fusion,
    full_hla_reference, hamming, load_identities, normalize_hla, parse_mix,
    read_identity_csv, verify_digest, verify_git_tree, within_hla_percentiles,
)

A='HLA-A*02:01'
B='HLA-B*07:02'


class PreflightTests(unittest.TestCase):
    def test_git_tree_contents_not_api_echoed_commit(self):
        blob=hashlib.sha1(b'blob 2\0x\n').hexdigest()
        content=b'100644 x.txt\0'+bytes.fromhex(blob)
        tree=hashlib.sha1(b'tree '+str(len(content)).encode()+b'\0'+content).hexdigest()
        entries=[{'path':'x.txt','type':'blob','mode':'100644','sha':blob}]
        verify_git_tree(entries,tree)
        with self.assertRaises(ValueError):verify_git_tree(entries,'0'*40)

    def test_script_imports_do_not_resolve_or_write_storage(self):
        root=Path(__file__).resolve().parents[1]
        with patch('stability_label_curation.paths.resolve_paths',side_effect=AssertionError('import resolved storage')):
            for script in sorted((root/'scripts').glob('task239_*.py')):
                spec=importlib.util.spec_from_file_location('import_check_'+script.stem,script)
                module=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

    def test_conservative_allele(self):
        for x in ('A0201','HLA-A*02:01','A*02:01','A02:01'):
            self.assertEqual(normalize_hla(x),A)
        for x in ('A2','HLA-A*02','A*02:01:01','HLA-A*02:01N','DRB1*01:01','A12345','A020101'):
            with self.assertRaises(ValueError):normalize_hla(x)

    def test_exact_designated_not_best(self):
        text='# Output from MixMHCpred (v3.0)\nPeptide\tScore_bestAllele\tScore_A0201\t%Rank_A0201\nGILGFVFTL\t9\t-2\t90\n'
        r=parse_mix(text,['GILGFVFTL'],A)
        self.assertEqual(r[0]['native_score'],-2)
        with self.assertRaises(ValueError):parse_mix(text,['GILGFVFTL'],B)

    def test_mix_missing_duplicate_alignment(self):
        text='Peptide\tScore_A0201\t%Rank_A0201\nGILGFVFTL\t1\t2\n'
        for peptides in ([],['NLVPMVATV'],['GILGFVFTL','GILGFVFTL']):
            with self.assertRaises(ValueError):parse_mix(text,peptides,A)
        self.assertEqual(len(parse_mix(text+text.splitlines()[1]+'\n',['GILGFVFTL']*2,A)),2)
        with self.assertRaises(ValueError):parse_mix(text.replace('\t1\t','\tnan\t'),['GILGFVFTL'],A)

    def test_alignment(self):
        align_scores(['1','2'],[{'source_id':'1','score':2},{'source_id':'2','score':1}])
        for rows in ([{'source_id':'2','score':1},{'source_id':'1','score':2}],
                     [{'source_id':'1','score':float('inf')}],[]):
            with self.assertRaises(ValueError):align_scores(['1','2'],rows)

    def test_assay(self):
        v=['SPA','Purified_Fluor','Cellular_Fluor','Other']
        self.assertEqual(assay_contract(v),(0,37.0))
        for kwargs in ({'assay':'Other'},{'temperature':25.0}):
            with self.assertRaises(ValueError):assay_contract(v,**kwargs)

    def test_ranks_ties_direction_and_duplicates(self):
        self.assertEqual(within_hla_percentiles([1,2,2,9,4],[A,A,A,A,B]),[.125,.5,.5,.875,.5])
        self.assertEqual(within_hla_percentiles([2,1,2],[A]*3),[2/3,1/6,2/3])
        with self.assertRaises(ValueError):within_hla_percentiles([float('nan')],[A])
        with self.assertRaises(ValueError):within_hla_percentiles([1],[])

    def test_fusion(self):
        el,st,f=fixed_fusion([1,3,2],[3,1,2],[A]*3)
        self.assertEqual(f,[.5]*3)
        self.assertGreater(el[1],el[0]);self.assertGreater(st[0],st[1])

    def test_hamming_bruteforce_and_partition(self):
        refs=[{'peptide':s,'hla':a} for s,a in [('AAAAAAAAA',A),('AAAAAACCC',B),('CCCCCCCCC',A),('AAAAAAAA',A)]]
        candidates=[{'source_id':str(i),'peptide':s,'hla':a} for i,(s,a) in enumerate([('AAAAAAAAA',B),('AAAAAAAAC',A),('AAAAAACCC',B),('GGGGGGGGG',A)])]
        r=audit_identities(candidates,refs)
        for c,x in zip(candidates,r):
            self.assertEqual(x['min_hamming'],min(hamming(c['peptide'],q['peptide']) for q in refs if len(q['peptide'])==9))
        self.assertFalse(r[0]['exact_pair']);self.assertTrue(r[0]['exact_peptide'])
        with self.assertRaises(ValueError):hamming('AA','AAA')
        self.assertIsNone(audit_identities(candidates,[])[0]['min_hamming'])

    def test_full_reference_no_nearest_or_fragment(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'hla.fasta';p.write_text('>HLA:HLA00005 A*02:01:01:01 365 bp\n'+'A'*365+'\n')
            r=full_hla_reference([A,B],{A:'A'*365,B:'A'*181},p)
            self.assertTrue(r[A]['eligible']);self.assertFalse(r[B]['eligible'])
            self.assertEqual(r[A]['length'],365)

    def test_hash_identity_outcome_schema_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'id.jsonl';r={'source_id':'1','peptide':'GILGFVFTL','hla':A}
            p.write_text(json.dumps(r)+'\n');h=digest(p)
            self.assertEqual(load_identities(p,h,1)[0]['source_id'],'1')
            with self.assertRaises(ValueError):verify_digest(p,'bad')
            with self.assertRaises(ValueError):load_identities(p,h,2)
            r['tgt']='MUST NOT READ';p.write_text(json.dumps(r)+'\n')
            with self.assertRaisesRegex(ValueError,'schema rejected'):load_identities(p,digest(p),1)

    def test_source_indexes_do_not_access_numerical_label(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.csv';p.write_text('peptide_sequence,mhc_sequence,allele,label\nGILGFVFTL,AAA,HLA-A*02:01,DO_NOT_PARSE\n')
            r=read_identity_csv(p,'s3','train')
            self.assertEqual(r[0]['peptide'],'GILGFVFTL');self.assertNotIn('label',r[0])

    def test_coverage_no_score_filter(self):
        rows=[{'source_id':'1','peptide':'GILGFVFTL','hla':A,'patient_peptide_component':'c'}]
        r=coverage(rows,{A:{'eligible':True}},{A:{'eligible':True}})
        self.assertTrue(r[0]['common_eligible']);self.assertTrue(r[0]['unknown_ancestry'])
        self.assertFalse(coverage(rows,{A:{'eligible':False}},{A:{'eligible':True}})[0]['common_eligible'])


if __name__=='__main__':unittest.main()
