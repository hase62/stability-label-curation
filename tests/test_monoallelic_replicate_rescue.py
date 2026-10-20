"""Focused source-identity, PSM and replicate semantics tests; no scientific scores."""
import csv
from pathlib import Path
import tempfile
import unittest
import zipfile

from stability_label_curation.monoallelic_replicate_rescue import (
    canonical_hla, chemical_state, collect_psms, matrix_rows, replicate_groups,
    xlsx_rows, xlsx_sheets,
)


class MonoallelicReplicateTests(unittest.TestCase):
    def test_original_excel_row_and_column_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source.xlsx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="runs" r:id="r1"/></sheets></workbook>')
                archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
                archive.writestr('xl/sharedStrings.xml', '<sst><si><t>raw1</t></si></sst>')
                archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="7"><c r="A7" t="s"><v>0</v></c><c r="C7" t="inlineStr"><is><t>HLA-A02:01</t></is></c></row></sheetData></worksheet>')
            member = xlsx_sheets(path)['runs']
            self.assertEqual(list(xlsx_rows(path, member)), [(7, {'A': 'raw1', 'C': 'HLA-A02:01'})])

    def test_formula_cells_not_treated_as_source_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'formula.xlsx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('sheet.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="A2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
            with self.assertRaises(ValueError):
                list(xlsx_rows(path, 'sheet.xml'))

    def test_exact_allele_identity_only(self):
        self.assertEqual(canonical_hla('HLA-A02:01'), 'HLA-A*02:01')
        for value in ('HLA-A02', 'HLA-A*02:52extra', 'HLA-C*01:01', 'A*02:01'):
            with self.assertRaises(ValueError):
                canonical_hla(value)

    def test_modifications_never_silently_stripped(self):
        self.assertEqual(chemical_state('ALAAAAAAAA', 'ALAAAAAAAA', {'na'}), 'not_canonical_9mer')
        self.assertEqual(chemical_state('ALAAAAAAA', 'ALAAAAAAA', {'na'}), 'unmodified')
        self.assertEqual(chemical_state('ALCAAAAAA', 'ALCAAAAAA', {'na'}), 'modified_or_fixed_CAM')
        self.assertEqual(chemical_state('ALMAAAAAA', 'ALM(+15.99)AAAAAA', {'Oxidation'}), 'modified_or_fixed_CAM')
        self.assertEqual(chemical_state('ALXAAAAAA', 'ALXAAAAAA', {'na'}), 'not_canonical_9mer')

    def test_biological_hierarchy_and_method_separation(self):
        runs = []
        for i in range(3):
            for j, method in enumerate(('CID', 'CID', 'EThcD')):
                runs.append({'hla': 'HLA-A*02:01', 'biological_sample': f's{i}',
                             'raw_file': f's{i}_{j}', 'method': method,
                             'technical_replicate': str(j+1), 'metadata_excel_row': len(runs)+2})
        groups = replicate_groups(runs)
        bio = [g for g in groups if g['primary_candidate']]
        self.assertEqual(len(bio), 1)
        self.assertEqual(bio[0]['raw_files'], ['s0_0', 's1_0', 's2_0'])
        technical = [g for g in groups if g['type'] == 'technical']
        self.assertEqual(len(technical), 3)
        self.assertTrue(all(len(g['raw_files']) == 2 and g['method'] == 'CID' for g in technical))
        self.assertEqual(sum(g['type'] == 'nonexchangeable_method_comparison' for g in groups), 3)
        two_bio = replicate_groups(runs[:6])
        self.assertFalse(any(g['primary_candidate'] for g in two_bio))

    def test_original_code_psm_qc_and_fragment_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'ions.csv'
            fields = ['Source File', 'scan', 'fileID', 'Peptide', 'pepSeq', 'pepLen',
                      'ion', 'modification', 'protein', 'RT', 'm/z', 'z']
            with path.open('w') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for scan, peptides, count in [('F1:1', ['ALAAAAAAA'], 10),
                                              ('F1:2', ['ALAAAAAAA'], 9),
                                              ('F1:3', ['ALAAAAAAA', 'ILAAAAAAA', 'VLAAAAAAA'], 12)]:
                    for peptide in peptides:
                        for i in range(count):
                            writer.writerow(dict(zip(fields, ['r.raw', scan, 'F1', peptide, peptide, '9',
                                                              f'b{i}', 'na', 'protein1', '42', '450', '2'])))
            psms, counts = collect_psms(path)
            self.assertEqual(len(psms), 5)
            self.assertEqual(counts['r.raw'], 55)
            self.assertEqual(sum(p['source_code_PSM_QC'] for p in psms.values()), 1)
            first = next(iter(psms.values()))
            self.assertEqual(first['source_csv_row_ranges'], [[2, 11]])
            self.assertEqual(first['ion_rows'], 10)

    def test_union_absence_and_conditional_repeat_denominator(self):
        group = {'group_id': 'g', 'hla': 'HLA-A*02:01', 'type': 'biological', 'raw_files': ['a', 'b', 'c']}
        detections = {('ALAAAAAAA', 'HLA-A*02:01'): {'a': ['p1', 'p2'], 'c': ['p3']},
                      ('ILAAAAAAA', 'HLA-A*02:01'): {'b': ['p4']}}
        rows = matrix_rows(group, detections)
        self.assertEqual(rows[0]['direct_detection'], [1, 0, 1])
        self.assertEqual(rows[0]['n_detected'], 2)
        self.assertEqual(rows[0]['repeat_detection_frequency'], .5)
        self.assertIsNone(rows[1]['repeat_detection_frequency'])
        group['type'] = 'nonexchangeable_method_comparison'
        self.assertIsNone(matrix_rows(group, detections)[0]['detection_frequency'])


if __name__ == '__main__':
    unittest.main()
