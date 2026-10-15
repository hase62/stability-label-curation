"""Synthetic sequences and canonical registry fixtures only; no networking."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import asdict, replace
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import sequence_leakage_audit as audit
from stability_label_curation import observation_registry as registry
from stability_label_curation import dtu2016_source_audit as dtu
from stability_label_curation import jappe_2020_row_audit as jappe
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main


def record(identifier, peptide='ACDEFGHIK', allele='HLA-A*02:01', group='given_train', **kwargs):
    return audit.SequenceRecord(identifier, peptide, allele, group, kwargs.pop('source_id', 'fixture'), **kwargs)


class SequencePrimitiveTests(unittest.TestCase):
    def setUp(self):
        p = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network in tests'))
        p.start(); self.addCleanup(p.stop)

    def test_exact_sequence_across_HLA(self):
        result = audit.audit_records([record('a'), record('b', allele='HLA-B*07:02', group='given_test')])
        self.assertEqual(result['exact_peptide_identity']['cross_group_keys'], 1)
        self.assertEqual(result['strict_pair_identity']['cross_group_keys'], 0)
        self.assertEqual(result['peptides_reused_across_alleles'], 1)

    def test_strict_pair_identity(self):
        result = audit.audit_records([record('a'), record('b', group='given_test')])
        self.assertEqual(result['strict_pair_identity']['cross_group_record_pair_count'], 1)

    def test_evidence_supported_mapping_separate_from_raw(self):
        rows = [record('a', allele='HLA-A0201'), record('b', group='given_test')]
        before = deepcopy(rows)
        mapping = audit.AlleleMapping('HLA-A0201', 'HLA-A*02:01', 'Synthetic pinned allele reference')
        result = audit.audit_records(rows, mappings=[mapping])
        self.assertEqual(result['strict_pair_identity']['cross_group_keys'], 0)
        self.assertEqual(result['evidence_mapped_pair_identity']['cross_group_keys'], 1)
        self.assertEqual(rows, before)

    def test_unsupported_mapping_fails(self):
        for mapping in [audit.AlleleMapping('HLA-A0201', 'HLA-A*02:01', ''),
                        audit.AlleleMapping('HLA-A0201', 'HLA-A*02:01', 'guess', 'unverified'),
                        audit.AlleleMapping('HLA-A0201', 'HLA-B*07:02', 'wrong locus'),
                        audit.AlleleMapping('arbitrary', 'HLA-A*02:01', 'not an HLA reference')]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                audit.allele_mapping_table([mapping])

    def test_ambiguous_mapping_fails(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            audit.allele_mapping_table([audit.AlleleMapping('HLA-A0201', 'HLA-A*02:01', 'fixture'),
                                       audit.AlleleMapping('HLA-A0201', 'HLA-A*02:02', 'conflicting fixture')])

    def test_C67S_cannot_map_to_wild_type(self):
        with self.assertRaises(ValueError):
            audit.allele_mapping_table([audit.AlleleMapping('HLA-B*14:01(C67S)', 'HLA-B*14:01', 'fixture')])

    def test_sliding_windows(self):
        self.assertEqual(audit.windows('ACDEFGHIKLM'), ('ACDEFGHIK', 'CDEFGHIKL', 'DEFGHIKLM'))

    def test_long_peptide_exposes_short_9mer(self):
        result = audit.audit_records([record('a', 'ACDEFGHIKLM'), record('b', group='given_test')])
        self.assertEqual(result['exact_peptide_identity']['cross_group_keys'], 0)
        self.assertEqual(result['shared_exact_9mer_windows_across_groups'], 1)

    def test_short_peptides_counted_separately(self):
        self.assertEqual(audit.windows('ACDEFGHI'), ())
        result = audit.audit_records([record('a', 'ACDEFGHI'), record('b', 'ACDEFGHI', group='given_test')])
        self.assertEqual(result['short_peptides']['records'], 2)
        self.assertEqual(result['exact_peptide_identity']['cross_group_keys'], 1)
        self.assertEqual(result['unique_9mer_windows'], 0)

    def test_zero_mismatch_duplicates_not_self_edges(self):
        self.assertEqual(audit.indexed_edges(['ACDEFGHIK', 'ACDEFGHIK'], 0), [])
        result = audit.audit_records([record('a'), record('b', group='given_test')], max_mismatches=0)
        self.assertEqual(result['shared_exact_9mer_windows_across_groups'], 1)
        self.assertEqual(result['exact_peptide_identity']['same_key_record_pairs'], 1)

    def test_one_mismatch_detected(self):
        self.assertEqual(audit.indexed_edges(['ACDEFGHIK', 'ACDEFGHIL']), [('ACDEFGHIK', 'ACDEFGHIL', 1)])

    def test_two_mismatches_excluded_by_candidate(self):
        self.assertEqual(audit.indexed_edges(['ACDEFGHIK', 'ACDEFGHLM'], 1), [])
        self.assertEqual(len(audit.indexed_edges(['ACDEFGHIK', 'ACDEFGHLM'], 2)), 1)

    def test_hamming_symmetry_and_equal_lengths(self):
        self.assertEqual(audit.hamming('ACDEFGHIK', 'ACDEFGHLM'), audit.hamming('ACDEFGHLM', 'ACDEFGHIK'))
        with self.assertRaises(ValueError): audit.hamming('AAA', 'AA')

    def test_index_matches_exhaustive_oracle_on_small_fixture(self):
        nodes = [''.join(x) + 'FGHIKL' for x in itertools.product('ACD', repeat=3)]
        for threshold in (0, 1, 2):
            expected = [(a, b, audit.hamming(a, b)) for a, b in itertools.combinations(sorted(nodes), 2)
                        if audit.hamming(a, b) <= threshold]
            self.assertEqual(audit.indexed_edges(nodes, threshold), expected)

    def test_components_transitive_not_all_direct(self):
        nodes = ['AAAAAAAAA', 'CAAAAAAAA', 'CCAAAAAAA', 'DDDDDDDDD']
        edges = audit.indexed_edges(nodes)
        components = audit.connected_components(nodes, edges)
        self.assertEqual(components, [('AAAAAAAAA', 'CAAAAAAAA', 'CCAAAAAAA'), ('DDDDDDDDD',)])
        self.assertEqual(audit.hamming(components[0][0], components[0][2]), 2)
        self.assertEqual(components, audit.connected_components(list(reversed(nodes)), list(reversed(edges))))

    def test_component_size_and_allele_reporting(self):
        result = audit.audit_records([record('a', 'AAAAAAAAA'), record('b', 'CAAAAAAAA'), record('c', 'DDDDDDDDD')])
        self.assertEqual(result['components']['size_distribution'], {'1': 1, '2': 1})
        self.assertEqual(result['components']['by_allele']['HLA-A*02:01']['components_touched'], 2)

    def test_alias_and_study_donor_exposure(self):
        rows = [record('a', canonical_measurement_id='m1', study_id='s1', donor_id='d1'),
                record('b', group='given_test', canonical_measurement_id='m1', study_id='s1', donor_id='d1')]
        result = audit.provenance_flags(rows)
        for field in ['source_id', 'canonical_measurement_id', 'study_id', 'donor_id']:
            self.assertEqual(result[field]['cross_group_shared_identifiers'], 1)

    def test_label_duplicates_and_conflicts(self):
        rows = [record('a', label='1'), record('b', label='0', group='given_test'), record('c', label='1')]
        result = audit.audit_records(rows)
        self.assertEqual(result['strict_pair_identity']['repeated_keys'], 1)
        self.assertEqual(result['strict_pair_identity']['label_conflicting_keys'], 1)
        self.assertEqual(result['strict_pair_identity']['same_key_record_pairs'], 3)

    def test_unknown_metadata_is_unknown(self):
        result = audit.provenance_flags([record('a')])
        self.assertEqual(result['checkpoint_exposure'], {'unknown': 1})
        self.assertEqual(result['study_id']['unknown_records'], 1)
        self.assertFalse(result['unknown_is_no_leakage'])

    def test_negative_provenance_not_collapsed(self):
        result = audit.provenance_flags([record(str(i), negative_provenance=n) for i, n in enumerate(
            ['assayed_IM_negative', 'EL_decoy', 'kinetic_zero_unresolved', 'stability_pseudolabel'])])
        self.assertEqual(len(result['negative_provenance']), 4)

    def test_mutant_relationships_explicit_only(self):
        result = audit.provenance_flags([record('a'), record('b', 'ACDEFGHIL', mutant_of='a')])
        self.assertEqual(result['mutant_relationships']['explicit_relationship_records'], 1)
        self.assertFalse(result['mutant_relationships']['relationships_inferred_from_similarity'])

    def test_exposure_matrix_unknown_and_intentionally_matched(self):
        matrix = audit.exposure_matrix()
        self.assertEqual(len(matrix['pairs']), 36)
        self.assertFalse(matrix['actual_BigMHC_or_IM_overlap_quantified'])
        self.assertTrue(all(len(p['proposed_guards']) == 7 for p in matrix['pairs']))
        self.assertEqual(sum(p['status'].startswith('intentional') for p in matrix['pairs']), 1)

    def test_determinism_and_no_split_or_label_modification(self):
        rows = [record('a', label='1'), record('b', 'ACDEFGHIL', label='0')]
        before = [asdict(r) for r in rows]
        a = audit.audit_records(rows); b = audit.audit_records(list(reversed(rows)))
        self.assertEqual(raw.json_report(a), raw.json_report(b))
        self.assertEqual(before, [asdict(r) for r in rows])
        self.assertFalse(a['split_assignments_created']); self.assertFalse(a['labels_modified'])
        self.assertIsNone(audit.rule_catalog()['approved_threshold'])

    def test_capacity_and_invalid_rules_fail_without_truncation(self):
        with self.assertRaisesRegex(ValueError, 'Edge bound'):
            audit.indexed_edges(['AAAAAAAAA', 'CAAAAAAAA'], edge_cap=0)
        for distance in (-1, 3, True):
            with self.assertRaises(ValueError): audit.indexed_edges([], distance)
        with self.assertRaises(ValueError): audit.indexed_edges(['TOOSHORT'])
        with self.assertRaises(ValueError): audit.audit_records([record('a'), record('a')])

    def test_noncanonical_characters_flagged_without_normalization(self):
        result = audit.audit_records([record('a', 'ACDEFGHIX')])
        self.assertEqual(result['noncanonical_peptide_records'], 1)
        with self.assertRaises(ValueError): record('b', 'acdefghik')


class RegistryLeakageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.env = {'CODEX_ROOT': str(self.root)}
        self.paths = resolve_paths(self.env)
        self.config = json.loads((self.paths.repository_root / audit.PROTOCOL).read_text())
        self.config['parent_registry_run_id'] = 'synthetic-parent'
        self.config['expected_reference_counts'] = {'ordinary_DTU_records': 3, 'ordinary_DTU_alleles': 2, 'ordinary_DTU_zeros': 1}
        self.parent = self.paths.project_runs_dir / 'synthetic-parent'
        (self.parent / 'reports').mkdir(parents=True)
        self.input_paths = {k: self.parent / entry['parent_relative_path'] for k, entry in self.config['inputs'].items()}
        self.config_path = self.root / 'fixture-config.json'
        self.rows = []
        for number, (a, p, v) in enumerate([('HLA-A*02:01', 'ACDEFGHIK', '0.00'),
                                         ('HLA-A*02:01', 'ACDEFGHIL', '1.00'),
                                         ('HLA-B*07:02', 'ACDEFGHIK', '2.00'),
                                         ('HLA-B*14:01(C67S)', 'AAAAAAAAA', '0.00')], 2):
            self.rows.append(registry.make_observation(source_id='netmhcstabpan_2016', sha256='a' * 64,
                locator={'kind': 'text_line', 'artifact': 'fixture/Stability.txt', 'line_number': number},
                allele=a, peptide=p, text=v, measurement_type='kinetic_half_life', unit='hours', context=registry.DTU_CONTEXT,
                provenance={}, origin=dtu.ROW_PROVENANCE, flags=[], record_context={}))
        self.rows.append(registry.make_observation(source_id='jappe_2020', sha256='b' * 64,
            locator={'kind': 'workbook_cell', 'artifact': 'fixture/data.xlsx', 'worksheet': 'A0201', 'row_number': 2, 'cell_coordinate': 'B2'},
            allele='HLA-A*02:01', peptide='AAAAAAAAA', text='55', measurement_type='thermal_melting_temperature', unit='degC',
            context='fixture', provenance={}, origin=jappe.ROW_ORIGIN, flags=[], record_context={}))
        self.input_paths['observations'].write_text(registry.jsonl(self.rows))
        self.input_paths['evidence'].write_text('{"scope":"synthetic evidence"}')
        git = {'repository_name': 'stability-label-curation', 'commit_sha': self.config['parent_registry_commit'],
               'branch': 'synthetic', 'working_tree_clean': True, 'git_dirty': False, 'working_tree_status': []}
        with patch.object(runs, 'capture_git_provenance', return_value=git):
            manifest = runs.build_manifest(paths=self.paths, run_id='synthetic-parent', kind='synthetic', argv=['fixture'])
        self.input_paths['parent_manifest'].write_text(json.dumps(manifest))
        self.refresh()
        p = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Offline'))
        p.start(); self.addCleanup(p.stop)

    def refresh(self):
        for key, path in self.input_paths.items(): self.config['inputs'][key]['sha256'] = raw.sha256_file(path)
        self.config_path.write_text(json.dumps(self.config))

    def result(self):
        return audit.inspect(paths=self.paths, config_path=self.config_path)

    def rewrite(self, change):
        rows = [json.loads(line) for line in self.input_paths['observations'].read_text().splitlines()]
        change(rows); self.input_paths['observations'].write_text(registry.jsonl(rows)); self.refresh()

    def test_only_ordinary_DTU_9mers_used(self):
        result = self.result().reports['stability_sequence_neighborhood_summary.json']
        self.assertEqual(result['input_records'], 3); self.assertEqual(result['unique_peptides'], 2)
        self.assertEqual(result['canonical_records_validated'], 5)
        self.assertEqual(result['reference_counts']['ordinary_DTU_zeros'], 1)

    def test_registry_hash_gate_before_parse(self):
        self.input_paths['observations'].write_text('corrupt')
        with patch.object(audit.readers, '_jsonl', side_effect=AssertionError('Must gate first')):
            with self.assertRaisesRegex(ValueError, 'checksum'): self.result()

    def test_invalid_registry_unit_rejected(self):
        self.rewrite(lambda rows: rows[0].__setitem__('measurement_unit', 'degC'))
        with self.assertRaises(ValueError): self.result()

    def test_invalid_registry_value_rejected(self):
        self.rewrite(lambda rows: rows[0].__setitem__('original_measurement_text', 'NaN'))
        with self.assertRaises(ValueError): self.result()

    def test_reported_zero_semantics_cannot_be_removed(self):
        self.rewrite(lambda rows: rows[0]['data_quality_flags'].remove('zero_semantics_unresolved'))
        with self.assertRaisesRegex(ValueError, 'semantics'): self.result()

    def test_zero_flag_disagreement_rejected(self):
        self.rewrite(lambda rows: rows[0]['data_quality_flags'].remove('exact_zero'))
        with self.assertRaisesRegex(ValueError, 'zero flag'): self.result()

    def test_parent_input_checksum_gate(self):
        self.input_paths['evidence'].write_text('{}')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.result()

    def test_physical_sequence_analysis_never_uses_half_life_as_EL_label(self):
        result = self.result().reports['stability_sequence_neighborhood_summary.json']
        self.assertEqual(result['exact_peptide_identity']['label_conflicting_keys'], 0)

    def test_duplicate_registry_ID_rejected(self):
        self.rewrite(lambda rows: rows.append(rows[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): self.result()

    def test_count_discrepancies_fail(self):
        self.config['expected_reference_counts']['ordinary_DTU_records'] = 4
        self.config_path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'counts'): self.result()

    def test_no_raw_source_reads_claimed(self):
        result = self.result()
        self.assertEqual(len(result.inputs), 3)
        source = result.reports['source_evidence_link.json']
        self.assertFalse(source['raw_scientific_source_artifacts_read'])
        self.assertFalse(source['supplement_pdf_read'])

    def test_input_preservation_and_offline_determinism(self):
        before = {k: p.read_bytes() for k, p in self.input_paths.items()}
        listing = sorted(str(p) for p in self.root.rglob('*'))
        a, b = self.result(), self.result()
        self.assertEqual(raw.json_report(a.reports), raw.json_report(b.reports))
        self.assertEqual(before, {k: p.read_bytes() for k, p in self.input_paths.items()})
        self.assertEqual(listing, sorted(str(p) for p in self.root.rglob('*')))

    def test_cli_read_only_explicit_fixture_and_compatibility(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['leakage', 'inspect', '--json', '--registry', str(self.input_paths['observations']),
                                   '--config', str(self.config_path)], env=self.env), 0)
        self.assertEqual(json.loads(out.getvalue())['stability_sequence_neighborhood_summary.json']['input_records'], 3)
        with redirect_stdout(io.StringIO()): self.assertEqual(main(['sources', 'validate'], env=self.env), 0)

    def test_cli_override_candidate_threshold(self):
        result = audit.inspect(paths=self.paths, config_path=self.config_path, max_mismatches=0)
        self.assertEqual(result.reports['stability_sequence_neighborhood_summary.json']['distinct_window_direct_edges'], 0)

    def test_safe_report_output_and_no_overwrite(self):
        run = runs.create_run(paths=self.paths, kind='test', argv=['fixture'], inputs=list(self.input_paths.values()), allow_dirty=True)
        receipt = audit.write_reports(self.result(), run / 'reports', paths=self.paths)
        self.assertEqual(len(receipt['reports']), 6)
        self.assertFalse(any(p.suffix == '.jsonl' for p in (run / 'reports').iterdir()))
        with self.assertRaises(FileExistsError): audit.write_reports(self.result(), run / 'reports', paths=self.paths)
        with self.assertRaises(ValueError): audit.write_reports(self.result(), self.root / 'reports', paths=self.paths)

    def test_unrecorded_input_rejected(self):
        run = runs.create_run(paths=self.paths, kind='test', argv=['fixture'], allow_dirty=True)
        with self.assertRaises(ValueError): audit.write_reports(self.result(), run / 'reports', paths=self.paths)

    def test_symlink_registry_rejected(self):
        alias = self.root / 'alias.jsonl'; alias.symlink_to(self.input_paths['observations'])
        with self.assertRaises(OSError): audit.inspect(paths=self.paths, config_path=self.config_path, registry_path=alias)

    def test_unresolved_literature_and_decision_statuses(self):
        result = self.result()
        methods = result.reports['hard_split_literature_evidence.json']['methods']
        self.assertEqual(len(methods), 6)
        self.assertTrue(all(m['fields']['code_verification']['status'] == 'unresolved' for m in methods))
        decisions = result.reports['phase2_pending_decisions.json']['decisions']
        self.assertEqual(next(d for d in decisions if d['id'] == 'D1')['status'], 'adopted')
        self.assertEqual(next(d for d in decisions if d['id'] == 'D4')['status'], 'methodology_pending')
        self.assertTrue(result.reports['phase2_pending_decisions.json']['no_actual_splits_or_corrections'])


if __name__ == '__main__':
    unittest.main()
