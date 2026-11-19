"""Repository-only checks with synthetic rows. No fitting or cohort access."""
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
WRAPPERS = PROJECT / "scripts/hla_reproduction"
sys.path[:0] = [str(PROJECT / "src"), str(WRAPPERS), str(WRAPPERS / "stages")]

import prepare
import run
from main_study_controls import prepare as controls
from mix_diagnostic import parse_scores
from supplement import pair_auc
from stability_label_curation import bigmhc_independent_evaluation as neo
from stability_label_curation import third_party_hard_split as improve


class HlaReproductionTest(unittest.TestCase):
    def test_pinned_native_tree_and_frozen_schedule(self):
        expected = run.read(run.CONFIG / "expected.json")
        self.assertEqual(len(expected["native_scientific_hashes"]), 20)
        for name, digest in expected["native_scientific_hashes"].items():
            self.assertEqual(run.sha(PROJECT / name), digest)
        cfg = run.read(run.CONFIG / "EXECUTION_CONFIG.json")
        self.assertEqual(cfg["execution_order"], [[arm, seed] for seed in run.SEEDS for arm in run.ARM_ORDER])
        self.assertEqual((cfg["training"]["EL_epochs"], cfg["training"]["IM_epochs"]), (20, 30))
        self.assertEqual(cfg["evaluation"]["bootstrap"]["draws"], 10000)

    def test_preparation_preserves_parsed_identity_and_original_label(self):
        test_rows = iter([(1, ["mhc", "pep", "tgt", "rand"]),
                          (2, ["HLA-A*02:01", "ACDEFGHIK", "1", "0"]),
                          (3, ["HLA-A*02:01", "ACDEFGHIQ", "0", "1"])])
        hla = "HLA-A*02:01"
        trained = prepare.teacher.Teacher({"alleles": {hla: {"status": "trained"}}})
        context = prepare.pilot.Context(trained, prepare.mapping_for({hla}), None, "", "f"*64, {})
        near = prepare.pilot.NeighborIndex({("ACDEFGHLQ", hla)}, {("ACDEFGHLQ", hla)})
        kept = list(prepare.stream_training_rows(test_rows, "im_train.csv", context, {hla: [hla]}, near))
        self.assertEqual(len(kept), 1)
        row, binding = kept[0]
        self.assertEqual(row, {"prepared_row_index": 1, "hla": hla, "peptide": "ACDEFGHIK", "original_label": "1"})
        self.assertEqual(binding["source_row_id"], prepare.pilot.row_id("f"*64, "im_train.csv", 1))

    def test_neo_identity_projection_does_not_decode_outcomes(self):
        [row] = neo.source_identities(BytesIO(b"mhc,pep,tgt\nHLA-A*02:01,ACDEFGHIK,opaque\n"))
        self.assertNotIn("label", row)
        good = {"EL_train_peptide": False, "IM_train_peptide": False}
        self.assertTrue(neo.classify(dict(row, **good), {row["hla"]})["primary"])
        self.assertFalse(neo.classify(dict(row, EL_train_peptide=True, IM_train_peptide=False), {row["hla"]})["primary"])

    def test_hamming_veto_and_study_scoped_transitivity(self):
        patient1 = {"study_DOI": "s1", "patient": "P", "peptide": "ACDEFGHIK"}
        patient2 = {"study_DOI": "s2", "patient": "P", "peptide": "ACDEFGHIL"}
        bridge = {"study_DOI": "s1", "patient": "P", "peptide": patient2["peptide"]}
        self.assertEqual(len(set(improve.components([patient1, patient2], "patient"))), 2)
        self.assertEqual(len(set(improve.components([patient1, patient2, bridge], "patient"))), 1)
        candidates = [dict(patient1, minimum_fitting_selection_distance=3, exact_prior_published_benchmark_peptide=False),
                      dict(patient2, minimum_fitting_selection_distance=2, exact_prior_published_benchmark_peptide=False),
                      dict(bridge, minimum_fitting_selection_distance=3, exact_prior_published_benchmark_peptide=True)]
        self.assertEqual(improve.select_threshold(candidates, 3), candidates[:1])

    def test_permutation_conserves_exact_rank_multiset(self):
        ledger = [{"source_row_id": "row1", "hla": "HLA-A*02:01", "rank_exact": "1/4", "W_exact": "7/8", "L_exact": "7/8"},
                  {"source_row_id": "row2", "hla": "HLA-A*02:01", "rank_exact": "3/4", "W_exact": "9/8", "L_exact": "1"}]
        weights, audit = controls(ledger, 42)
        self.assertEqual(Counter(r["permuted_rank_exact"] for r in weights), Counter(("1/4", "3/4")))
        self.assertEqual({r["L_const_exact"] for r in weights}, {"15/16"})
        self.assertTrue(audit[0]["HLA_L_sum_exactly_matched_by_constant"])

    def test_ties_and_negative_native_mix_scores(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "mix.tsv"
            path.write_text("Peptide\tScore_A0201\t%Rank_A0201\tScore_bestAllele\nACDEFGHIK\t-2\t30\t9\n")
            self.assertEqual(list(parse_scores(path, ["ACDEFGHIK"], "HLA-A*02:01")), [-2])
            with self.assertRaises(ValueError):
                list(parse_scores(path, ["ACDEFGHIQ"], "HLA-A*02:01"))
        self.assertEqual(pair_auc([1, 0, 0], [0.5, 0.5, 0], ["a", "a", "b"])["pooled_AUROC"], .75)

    def test_preexisting_fit_attempt_fails_without_worker(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(run, "worker") as worker:
            directory = Path(tmp)
            (directory / "receipts").mkdir()
            (directory / "receipts/A_42_started.json").write_text(json.dumps({"status": "RUNNING"}))
            with self.assertRaisesRegex(ValueError, "previously started"):
                run.jobs(directory, "train")
            worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
