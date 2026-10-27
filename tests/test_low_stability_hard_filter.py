"""Synthetic focused checks; never load scientific cohorts or outcomes."""
import ast,csv,gzip,inspect,json,tempfile,unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path
from stability_label_curation import low_stability_hard_filter as f
from stability_label_curation import hard_filter_evaluation as e

def training():
    return [{'prepared_row_index':i,'source_row_id':f'row{i:03}','hla':'HLA-A*02:01' if i<20 else 'HLA-B*07:02',
             'peptide':'A'*9,'original_label':'1' if i<40 else '0'} for i in range(42)]

def ranking_rows():
    return [{'source_id':str(i),'peptide':'A'*9+str(i),'hla':'HLA-A*02:01','study_DOI':'study','patient':str(i//2),
             'patient_peptide_component':str(i//2),'label':y,'scores':{a:v for a in e.ARMS}} for i,(y,v) in enumerate([(1,.8),(0,.8),(1,.1),(0,.1)])]

class SelectionTests(unittest.TestCase):
    def test_floor_ties_and_matched_counts(self):
        rows=training();ranks={r['source_row_id']:Fraction(1,2) for r in rows if r['original_label']=='1'}
        chosen,summary=f.select_exclusions(rows,ranks,list(range(5)))
        self.assertEqual(chosen['H'],['row000','row001','row020','row021'])
        self.assertEqual(summary['excluded'],4)
        for ids in chosen.values():
            self.assertEqual(Counter(f.stratum(rows[int(i[3:])]) for i in ids),{('HLA-A*02:01',9):2,('HLA-B*07:02',9):2})

    def test_missing_scores_and_negatives_retained(self):
        rows=training();ranks={r['source_row_id']:Fraction(i,40) for i,r in enumerate(rows[:39])}
        selected,summary=f.select_exclusions(rows,ranks,list(range(5)))
        self.assertEqual(summary['missing_or_outside_positive'],1)
        self.assertTrue(all('row039' not in ids and 'row040' not in ids and 'row041' not in ids for ids in selected.values()))

    def test_random_uses_only_eligible_identities_and_fixed_quotas(self):
        rows=training()[:40];quota=Counter({('HLA-A*02:01',9):2,('HLA-B*07:02',9):2})
        self.assertEqual(f.random_exclusions(rows,quota,123),f.random_exclusions(list(reversed(rows)),quota,123))
        self.assertNotEqual(f.random_exclusions(rows,quota,123),f.random_exclusions(rows,quota,456))
        self.assertNotIn('ranks',inspect.signature(f.random_exclusions).parameters)

    def test_no_entire_stratum_erasure(self):
        rows=training()[:20];rows[0]['peptide']='A'*8
        with self.assertRaisesRegex(ValueError,'entire'):f.select_exclusions(rows,{r['source_row_id']:Fraction(i,20) for i,r in enumerate(rows)},list(range(5)))

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):f.select_exclusions(training()+training()[:1],{},list(range(5)))

    def test_physical_filter_original_labels_and_serialization(self):
        rows=training();chosen,_=f.select_exclusions(rows,{r['source_row_id']:Fraction(i,40) for i,r in enumerate(rows[:40])},list(range(5)))
        kept=[r for r in rows if r['source_row_id'] not in chosen['H']]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rows.gz';q=Path(tmp)/'again.gz';f.save_rows(p,kept);f.save_rows(q,kept)
            self.assertEqual(p.read_bytes(),q.read_bytes());self.assertEqual(f.load_rows(p),kept)
            self.assertEqual(f.row_fingerprints(kept)['ordered_negative_rows_sha256'],f.row_fingerprints(rows)['ordered_negative_rows_sha256'])

class EvaluationTests(unittest.TestCase):
    def test_tied_AP_AUC(self):
        point=e.points(ranking_rows())
        self.assertAlmostEqual(point['arms']['A']['AP'],.5);self.assertAlmostEqual(point['arms']['A']['AUROC'],.5)
        self.assertEqual(point['contrasts']['H-A']['AP'],0)

    def test_defined_contrast_mean_not_ensemble(self):
        values={a:{'AP':i/10,'AUROC':.5} for i,a in enumerate(e.ARMS)}
        self.assertAlmostEqual(e.contrasts(values)['H-mean_R']['AP'],.1-(.2+.3+.4+.5+.6)/5)

    def test_bootstrap_deterministic_paired(self):
        a=e.paired_bootstrap(ranking_rows(),seed=3,draws=30);b=e.paired_bootstrap(ranking_rows(),seed=3,draws=30)
        self.assertEqual(a,b);self.assertEqual(a['intervals']['H-A']['AP']['lower_95'],0)
        self.assertEqual(a['components'],2);self.assertEqual(a['attempts'],30)

    def test_undefined_single_class(self):
        rows=ranking_rows()
        for r in rows:r['label']=0
        self.assertIsNone(e.points(rows)['arms']['A']['AP'])
        b=e.paired_bootstrap(rows,seed=4,draws=5)
        self.assertEqual(b['invalid_reasons'],{'single_outcome_class':5});self.assertIsNone(b['intervals']['H-A']['AP']['lower_95'])

    def test_alignment_duplicates_nonfinite(self):
        ids=[{'source_id':'a','hla':'A','peptide':'AAA'}];pred=[{**ids[0],'raw_EL_logit':1.,'EL_probability':.7}]
        e.valid_scores(ids,pred)
        with self.assertRaises(ValueError):e.valid_scores(ids+ids,pred+pred)
        for key,value in [('source_id','b'),('raw_EL_logit',float('nan')),('EL_probability',2)]:
            with self.assertRaises(ValueError):e.valid_scores(ids,[{**pred[0],key:value}])

    def test_class_metrics(self):
        d=e.class_diagnostics([0,1],[.1,.8]);self.assertAlmostEqual(d['1']['Brier'],.04)
        self.assertEqual(d['0']['correct_fraction_at_fixed_0_5'],1)

    def test_no_IM_outcome_access_in_training_or_prediction(self):
        for name in ['preflight','load_parent','train','infer','random_exclusions','select_exclusions']:
            src=inspect.getsource(getattr(f,name))
            self.assertNotIn("c['IM_outcomes']",src)
            self.assertNotIn('outcomes.jsonl',src)
        src=inspect.getsource(f.train)
        self.assertIn('loss_adapter=None',src);self.assertIn('range(1,11)',src);self.assertIn('transfer=False',src)
        self.assertNotIn('fine_tun',src)

if __name__=='__main__':unittest.main()
