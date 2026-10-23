"""Focused parser, identity, sequence and label-blind eligibility checks only."""
import ast
from copy import deepcopy
from decimal import Decimal, localcontext
import inspect
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from stability_label_curation import measured_tm_preflight as study
from stability_label_curation.paths import resolve_paths
from stability_label_curation.sequence_hamming import NearestNineIndex


def workbook(path, rows):
    ns=study.MAIN
    header='<row r="1"><c r="A1" t="inlineStr"><is><t>Ligand</t></is></c><c r="B1" t="inlineStr"><is><t>Tm</t></is></c><c r="C1" t="inlineStr"><is><t>Transformed Tm</t></is></c></row>'
    body=''.join(f'<row r="{i}"><c r="A{i}" t="inlineStr"><is><t>{pep}</t></is></c><c r="B{i}"><v>{tm}</v></c><c r="C{i}"><v>.5</v></c><c r="D{i}"><v>NEVER_DECODE_PREDICTION</v></c></row>' for i,(pep,tm) in enumerate(rows,2))
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{study.DOCREL}"><sheets><sheet name="A0201" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="'+study.DOCREL+'/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>{header+body}</sheetData></worksheet>')


class ParserTests(unittest.TestCase):
    def test_original_numeric_measurement_and_common_target_no_prediction_column(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'table.xlsx';workbook(file,[(' AAAAAAAAA ','40.10564'),('VVVVVVVVV','73')])
            rows,summary=study.measurement_rows(file,study.HLAS[0])
            self.assertEqual(rows[0]['original_peptide'],' AAAAAAAAA ')
            self.assertEqual(rows[0]['peptide'],'AAAAAAAAA')
            with localcontext() as context:
                context.prec=50
                self.assertEqual(Decimal(rows[0]['target_decimal']),Decimal('.5')+(Decimal('40.10564')-37)/72)
            self.assertEqual(rows[1]['target'],1)
            self.assertTrue(summary['targets_in_BCE_interval'])
            self.assertNotIn('NEVER_DECODE_PREDICTION',json.dumps(rows))
            self.assertEqual(rows[0]['Tm_cell'],'B2')

    def test_unresolved_minimum_ties_retained_and_not_censored(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'table.xlsx';workbook(file,[('AAAAAAAAA','40'),('VVVVVVVVV','40'),('PPPPPPPP','50')])
            rows,summary=study.measurement_rows(file,study.HLAS[0])
            self.assertEqual(summary['canonical_ninemers'],2)
            self.assertEqual(summary['repeated_minimum_ninemers'],2)
            self.assertTrue(all(r['inclusion_status']=='candidate' for r in rows[:2]))
            self.assertTrue(all('unresolved_repeated_minimum_Tm_not_assumed_censored' in r['quality_flags'] for r in rows[:2]))
            self.assertFalse(rows[-1]['canonical_ninemer'])

    def test_out_of_interval_no_clipping_and_duplicate_identity_fail(self):
        for rows in [[('AAAAAAAAA','100')],[('AAAAAAAAA','NaN')],[('AAAAAAAAA','Infinity')],
                     [('AAAAAAAAA','50'),('AAAAAAAAA','55')]]:
            with self.subTest(rows=rows),tempfile.TemporaryDirectory() as temp:
                file=Path(temp)/'table.xlsx';workbook(file,rows)
                with self.assertRaises(ValueError):study.measurement_rows(file,study.HLAS[0])

    def test_authentic_public_counts_and_five_ninemer_flags(self):
        p=resolve_paths();flags=0
        for h,(number,expected,nine,sha) in study.EXPECTED.items():
            path=p.project_data_dir/study.SOURCE_DIR/f'41467_2020_20166_MOESM{number}_ESM.xlsx'
            study.assert_sha(path,sha);rows,summary=study.measurement_rows(path,h)
            self.assertEqual(summary['finite_measurement_rows'],expected)
            self.assertEqual(summary['canonical_ninemers'],nine)
            self.assertEqual(summary['duplicate_identities'],0)
            flags+=summary['repeated_minimum_ninemers']
        self.assertEqual(flags,5)


class IdentityAndSequenceTests(unittest.TestCase):
    def test_frozen_cohort_identity_and_order_without_outcomes(self):
        cohorts,refs=study.cohort_identities(resolve_paths())
        self.assertEqual({n:len(r) for n,r in cohorts.items()},{'IMPROVE':7788,'neoepitope':267})
        self.assertTrue(all(not r['regenerated'] for r in refs.values()))
        self.assertFalse(any('label' in r for rows in cohorts.values() for r in rows))

    def test_outcome_join_rejects_reversed_or_invalid_labels(self):
        rows=[{'source_id':'one'},{'source_id':'two'}];labels=[{'source_id':'one','label':0},{'source_id':'two','label':1}]
        self.assertEqual([r['label'] for r in study.align_outcomes(rows,labels)],[0,1])
        for bad in [list(reversed(labels)),[{'source_id':'one','label':False},labels[1]],labels[:1]]:
            with self.assertRaises(ValueError):study.align_outcomes(rows,bad)

    def test_index_matches_small_brute_force_including_distant_and_empty(self):
        rng=random.Random(235);alphabet='ACDEFGHIKLMNPQRSTVWY'
        refs={''.join(rng.choices(alphabet,k=9)) for _ in range(120)}|{'AAAAAAAAA','VVVVVVVVV'}
        index=NearestNineIndex(refs)
        for query in ['AAAAAAAAA','CAAAAAAAA','CCAAAAAAA','CCCAAAAAA','CCCCAAAAA','CCCCCCCCC']+[''.join(rng.choices(alphabet,k=9)) for _ in range(40)]:
            actual,witness=index.nearest(query);expected=min(sum(a!=b for a,b in zip(query,r)) for r in refs)
            self.assertEqual(actual,expected);self.assertIn(witness,refs)
            self.assertEqual(actual,sum(a!=b for a,b in zip(query,witness)))
        self.assertEqual(NearestNineIndex([]).nearest('AAAAAAAAA'),(None,None))
        with self.assertRaises(ValueError):index.nearest('AAAAAAAA')

    def test_pair_vs_peptide_overlap_and_cross_HLA_protection(self):
        row={'source_id':'a','peptide':'AAAAAAAAA','hla':study.HLAS[0]}
        detail,summary=study.overlaps([row],{study.HLAS[1]:{'AAAAAAAAA'}})
        self.assertTrue(detail[0]['exact_peptide']);self.assertFalse(detail[0]['exact_pair'])
        self.assertIsNone(detail[0]['minimum_same_HLA_Hamming'])
        self.assertEqual(detail[0]['minimum_Hamming'],0)
        index=NearestNineIndex({'AAAAAAAAA'})
        self.assertTrue(study.sequence_excluded('CCAAAAAAA',index))
        self.assertFalse(study.sequence_excluded('CCCAAAAAA',index))
        altered={**row,'label':1,'scores':{'fake':999}}
        self.assertEqual(study.overlaps([row],{study.HLAS[1]:{'AAAAAAAAA'}})[0],study.overlaps([altered],{study.HLAS[1]:{'AAAAAAAAA'}})[0])

    def test_support_gate_fixed_and_global_components_not_split(self):
        rows=[{'source_id':str(i),'peptide':'AAAAAAAAA','label':int(i<10),'patient':str(i%6),'study_DOI':'study','component':str(i%6)} for i in range(40)]
        summary=study.support_counts(rows,'component');self.assertTrue(summary['passes_minimum_support'])
        self.assertEqual(summary['dependence_components'],6)
        rows[0]['label']=0;self.assertFalse(study.support_counts(rows,'component')['passes_minimum_support'])
        self.assertEqual(study.SUPPORT,{'positive':10,'negative':30,'components':5})

    def test_no_model_import_or_training_inference_metric_calls(self):
        tree=ast.parse(inspect.getsource(study))
        imports={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertFalse(imports&{'torch','numpy','bigmhc_baseline_runner','third_party_evaluation','el_only_zero_shot_im'})
        calls={getattr(n.func,'attr',getattr(n.func,'id','')) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls&{'load_checkpoint','fit','backward','step','predict','WeightedRanking','average_precision_score','roc_auc_score'})
        self.assertNotIn('_outcomes.jsonl',inspect.getsource(study.identities))
        self.assertNotIn('CUDA',inspect.getsource(study))

    def test_structure_only_source_check_and_exclusive_serialization(self):
        evidence=study.source_structure(resolve_paths())
        self.assertEqual(evidence['trainable_keys'],['condenser.out.weight','condenser.out.bias'])
        self.assertEqual(evidence['trainable_values'],415)
        self.assertTrue(evidence['HLA_boolean_mask_in_native_logit'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'result.json';value={'finite':.12345678901234567,'undefined':None}
            study.write_json(path,value);self.assertEqual(study.read_json(path),value)
            with self.assertRaises(FileExistsError):study.write_json(path,value)


if __name__=='__main__':unittest.main()
