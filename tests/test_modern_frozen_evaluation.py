from __future__ import annotations
import gzip
import inspect
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from stability_label_curation import modern_frozen_scoring as scoring
from stability_label_curation.modern_frozen_evaluation import FrozenRanking,bootstrap,metrics
from stability_label_curation.modern_model_preflight import (fixed_fusion,within_hla_percentiles,verify_digest,digest,parse_mix,full_hla_reference,assay_contract)
from stability_label_curation.paths import resolve_paths


def fixture(labels,scores):
    return [{'source_id':str(i),'peptide':'GILGFVFTL','hla':'HLA-A*02:01','study_DOI':'s','patient':'p',
             'patient_peptide_component':str(i%3),'label':y,'scores':{c:float(scores[i]) for c in scoring.COLUMNS}}
            for i,y in enumerate(labels)]


class FrozenEvaluationTests(unittest.TestCase):
    def test_exact_hash_and_row_alignment(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model';p.write_bytes(b'authentic');verify_digest(p,digest(p))
            with self.assertRaises(ValueError):verify_digest(p,'bad')
        rows=[{'source_id':'a','peptide':'GILGFVFTL','hla':'HLA-A*02:01'}]
        pred=[{**rows[0],'s':1.0}];scoring.integrity(rows,pred,'s')
        for p in ([],[{**pred[0],'source_id':'b'}],[{**pred[0],'s':float('nan')}],pred*2):
            with self.assertRaises(ValueError):scoring.integrity(rows,p,'s')
        with self.assertRaises(ValueError):scoring.integrity(rows*2,pred*2,'s')

    def test_designated_column_not_best(self):
        t='Peptide\tScore_A0201\t%Rank_A0201\tScore_bestAllele\nGILGFVFTL\t-2\t99\t9\n'
        self.assertEqual(parse_mix(t,['GILGFVFTL'],'A0201')[0]['native_score'],-2)
        with self.assertRaises(ValueError):parse_mix(t,['GILGFVFTL'],'B0702')

    def test_full_chain_exact_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'hla';p.write_text('>HLA:00005 A*02:01:01:01\n'+'A'*365+'\n')
            r=full_hla_reference(['HLA-A*02:01','HLA-B*07:02'],{'HLA-A*02:01':'A'*365,'HLA-B*07:02':'A'*181},p)
            self.assertTrue(r['HLA-A*02:01']['eligible']);self.assertFalse(r['HLA-B*07:02']['eligible'])

    def test_fixed_assay_temperature_and_offline_contract(self):
        self.assertEqual(assay_contract(['SPA','Purified_Fluor','Cellular_Fluor','Other']),(0,37.0))
        with self.assertRaises(ValueError):assay_contract(['SPA','Purified_Fluor','Cellular_Fluor','Other'],temperature=25)
        source=inspect.getsource(scoring.predict)
        for text in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','snapshot_download=forbidden','torch_load=forbidden','local_files_only=True',".eval()",'model.requires_grad_(False)'):
            self.assertIn(text,source)

    def test_stage_A_imports_no_evaluation_and_guard_denies_other_science(self):
        source=inspect.getsource(scoring)
        self.assertNotIn('import modern_frozen_evaluation',source)
        self.assertNotIn('load_outcomes',source)
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);paths=resolve_paths(home=base,env={});allowed=paths.project_runs_dir/scoring.PARENT/'identity.json'
            audit=set();guard=scoring.access_guard(paths,{allowed},audit)
            guard('open',(str(allowed),'r',0))
            with self.assertRaises(PermissionError):guard('open',(str(paths.project_runs_dir/'historical/outcomes.json'),'r',0))
            with self.assertRaises(PermissionError):guard('open',(str(paths.project_data_dir/'IM_data.csv'),'r',0))

    def test_midranks_and_exact_half_fusion(self):
        a,s,f=fixed_fusion([1,2,2,9],[9,2,2,1],['HLA-A*02:01']*4)
        self.assertEqual(a,[.125,.5,.5,.875]);self.assertEqual(f,[.5]*4)
        self.assertEqual(within_hla_percentiles([1],['HLA-A*02:01']),[.5])

    def test_tied_AP_and_AUROC(self):
        rows=fixture([1,0,1],[.5,.5,.2]);r=FrozenRanking(rows,scoring.COLUMNS[0]).metrics(np.ones(3,dtype=int))
        self.assertAlmostEqual(r['AP'],7/12);self.assertEqual(r['AUROC'],.25)
        self.assertEqual(metrics(rows)['contrasts']['fusion_minus_EL_rank']['AP'],0)

    def test_weighted_metrics_match_expanded_pairwise_oracle(self):
        rng=random.Random(12)
        for _ in range(30):
            labels=[rng.randrange(2) for _ in range(12)];scores=[rng.randrange(4) for _ in labels];weights=[rng.randrange(3) for _ in labels]
            rows=fixture(labels,scores);r=FrozenRanking(rows,scoring.COLUMNS[0]).metrics(weights,top_k=False)
            expanded=[(s,y) for s,y,w in zip(scores,labels,weights) for _ in range(w)];p=sum(y for s,y in expanded);n=len(expanded)-p
            if not p or not n:self.assertIsNone(r['AP']);continue
            seen=tp=0;ap=0
            for s in sorted({s for s,y in expanded},reverse=True):
                group=[y for score,y in expanded if score==s];tp+=sum(group);seen+=len(group);ap+=(sum(group)/p)*tp/seen
            auc=sum((a>b)+.5*(a==b) for a,y in expanded if y for b,z in expanded if not z)/(p*n)
            self.assertAlmostEqual(r['AP'],ap);self.assertAlmostEqual(r['AUROC'],auc)

    def test_fractional_topk_tie(self):
        rows=fixture([1]*10+[0]*10,[.5]*20);r=FrozenRanking(rows,scoring.COLUMNS[0]).metrics(np.ones(20,dtype=int))
        self.assertEqual(r['precision_at_10'],.5);self.assertEqual(r['precision_at_20'],.5)

    def test_undefined_and_invalid_draws_no_reroll(self):
        rows=fixture([0,0],[1,2]);r=FrozenRanking(rows,scoring.COLUMNS[0]).metrics([1,1]);self.assertIsNone(r['AP']);self.assertIsNone(r['AUROC'])
        r=bootstrap(rows,['0','1'],draws=11,seed=24040)
        self.assertEqual(r['attempted'],11);self.assertEqual(r['valid'],0);self.assertEqual(r['invalid_reasons'],{'no_positive':11})
        self.assertIsNone(r['intervals']['fusion_minus_EL_rank']['AP']['lower_95'])

    def test_paired_choices_original_fixed_ranks_and_serialization(self):
        rows=fixture([1,0,1,0,0,1],[.9,.8,.7,.4,.2,.1]);before=json.dumps(rows,sort_keys=True)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'draws.gz'
            with patch.object(scoring,'fixed_fusion',side_effect=AssertionError('must not recompute ranks')):
                a=bootstrap(rows,['0','1','2'],draws=17,seed=24040,evidence=p)
            with gzip.open(p,'rt') as stream:draws=[json.loads(s) for s in stream]
            rng=random.Random(24040)
            for draw in draws:
                chosen=rng.choices(['0','1','2'],k=3)
                self.assertEqual(draw['component_multiplicities'],[chosen.count(str(i)) for i in range(3)])
                self.assertEqual(draw['contrasts']['fusion_minus_EL_rank']['AP'],None if draw['invalid_reason'] else 0)
            b=bootstrap(rows,['0','1','2'],draws=17,seed=24040)
            self.assertEqual(a,b);self.assertEqual(json.dumps(rows,sort_keys=True),before)
            p=Path(d)/'table';scoring.write_rows(p,rows);self.assertEqual(scoring.read_rows(p),rows)
            with self.assertRaises(FileExistsError):scoring.write_rows(p,rows)

    def test_exact_sensitivity_flag_rule(self):
        rows=[{'source_id':str(i)} for i in range(10)]
        flags=[{'source_id':str(i),'exposure':{'s2_train':{'min_hamming':2 if i<8 else 3},'s3_train':{'min_hamming':None}}} for i in range(10)]
        self.assertEqual(scoring.sensitivity_exclusions(rows,flags),[str(i) for i in range(8)])
        with self.assertRaises(ValueError):scoring.sensitivity_exclusions(rows,list(reversed(flags)))
        flags[0]['exposure']['s2_train']['min_hamming']=3
        with self.assertRaises(ValueError):scoring.sensitivity_exclusions(rows,flags)


if __name__=='__main__':unittest.main()
