"""Tabulate released IMPROVE cohort metadata using regenerated selection masks."""
import csv
import io
import math

import numpy as np

from common import D, csvout, put
from stability_label_curation.third_party_hard_split import describe


def report(member, source, candidates, selected, config):
    reader = csv.DictReader(io.StringIO(member.decode("utf-8-sig")), delimiter="\t")
    raw = list(reader)
    if "Mut_MHCrank_EL" not in (reader.fieldnames or []):
        raise ValueError("Released RankEL field missing")
    summaries, ranks, hla, studies, sections = [], [], [], [], []
    for stage, rows in (("source", source), ("candidates", candidates), ("primary_Hamming_ge3", selected)):
        values = []
        for row in rows:
            entry = raw[row["source_row_index"] - 1]
            if (entry["Mut_peptide"], entry["HLA_allele"]) != (row["raw_peptide"], row["raw_hla"]):
                raise ValueError("Original RankEL row alignment failed")
            try:
                value = float(entry["Mut_MHCrank_EL"])
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                values.append(value)
        expected = describe(rows)
        summary = {"population": stage, "n": len(rows), "positive": expected["positive"],
                   "negative": expected["negative"], "prevalence": expected["prevalence"],
                   "unique_peptides": expected["unique_peptides"], "HLAs": expected["unique_HLAs"],
                   "patients": expected["patients"]}
        summaries.append(summary)
        public_keys = ("N", "positive", "negative", "prevalence", "unique_peptides", "unique_pairs",
                       "unique_HLAs", "HLA_counts", "patients", "studies")
        sections.append({"stage": stage, **{key: expected[key] for key in public_keys}})
        ranks.append({"population": stage, "n": len(rows), "field": "Mut_MHCrank_EL",
                      "n_available": len(values), "n_missing_or_nonfinite": len(rows)-len(values),
                      "minimum": min(values), "maximum": max(values), "mean": float(np.mean(values)),
                      **{f"q{q}": float(np.quantile(values, q/100, method="linear")) for q in (5,25,50,75,95)},
                      "direction": "lower released percentile rank = stronger predicted EL; diagnostic only",
                      "source_archive_SHA256": config["archive_sha256"], "source_member_SHA256": config["member_sha256"]})
        hla.extend({"population": stage, "hla": key, "n": n} for key,n in sorted(expected["HLA_counts"].items()))
        studies.extend({"population": stage, "study": key, "n": row["N"], "positive": row["positive"],
                        "negative": row["negative"], "patients": row["patients"], "DOI": row["study_DOI"]}
                       for key,row in sorted(expected["studies"].items()))
    for name, table in (("IMPROVE_SELECTION_COMPLETE_COUNTS", summaries), ("IMPROVE_ORIGINAL_RANKEL_DISTRIBUTION", ranks),
                        ("IMPROVE_SELECTION_HLA_DISTRIBUTION", hla), ("IMPROVE_SELECTION_STUDY_DISTRIBUTION", studies)):
        csvout(D / f"metrics/{name}.csv", table)
    put(D / "metrics/IMPROVE_SELECTION_AND_METADATA.json", {"sections": sections,
        "RankEL": "Original released Mut_MHCrank_EL; matched by row index, peptide and HLA.",
        "Neo_patient_specimen_assay_crosswalk": "Unresolved beyond original metadata."})
