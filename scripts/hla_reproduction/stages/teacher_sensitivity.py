"""Recreate the supplementary zero-retention comparison on the original DTU split."""
from collections import defaultdict
import math
import statistics

from scipy.stats import spearmanr

from common import D, P, csvout, put, read, sha
from prepare import INPUTS, raw_path, teacher_rows
from stability_label_curation import observation_registry as registry
from stability_label_curation import stability_teacher as teacher


def main():
    receipt = read(D / "preflight/teacher_generated.json")
    original_path = INPUTS / "teacher.json"
    partition_path = INPUTS / "teacher_partition.json"
    if sha(original_path) != receipt["teacher_sha256"] or sha(partition_path) != receipt["partition_sha256"]:
        raise ValueError("Regenerated Teacher inputs changed")
    model = teacher.load_model(original_path)
    population = teacher_rows(raw_path("dtu"))
    partition = read(partition_path)
    membership = {a["observation_id"]: a["partition"] for a in partition["assignments"]}
    eligible = [r for r in population if membership[r.observation_id] != "train"
                or registry.decimal_value(r.original_measurement_text) > 0]
    ids = {r.observation_id for r in eligible}
    reduced = {**partition, "assignments": [a for a in partition["assignments"] if a["observation_id"] in ids]}
    cfg = teacher.load_config(P.repository_root / "configs/stability_teacher_v0.json")
    excluded = teacher.fit(eligible, reduced, cfg, provenance={"original_split_sha256": receipt["partition_sha256"],
                                                               "training_only_reported_zero_exclusion": True})
    put(INPUTS / "teacher_zero_excluded.json", excluded.document)
    groups = defaultdict(list)
    for row in population:
        if membership[row.observation_id] == "validation":
            groups[row.original_allele].append(row)
    output = []
    for positive_only, population_name in (
        (False, "All scoreable validation"),
        (True, "Common validation with half-life greater than zero"),
    ):
        retained, dropped, n = [], [], 0
        for allele, group in sorted(groups.items()):
            eligible = [r for r in group if not positive_only or registry.decimal_value(r.original_measurement_text) > 0]
            if not eligible:
                continue
            if any(t.document["alleles"].get(allele, {}).get("status") != "trained" for t in (model, excluded)):
                continue
            n += len(eligible)
            truth = [float(registry.decimal_value(r.original_measurement_text)) for r in eligible]
            values = [[t.predict_stability(r.original_peptide, allele)["predicted_half_life_hours"] for r in eligible]
                      for t in (model, excluded)]
            for target, predictions in zip((retained, dropped), values, strict=True):
                if len(set(truth)) > 1 and len(set(predictions)) > 1:
                    rho = float(spearmanr(truth, predictions).statistic)
                    if math.isfinite(rho):
                        target.append(rho)
        if n != (4482 if positive_only else 5394):
            raise ValueError("Teacher sensitivity coverage differs")
        output.append({"validation_population": population_name, "scoreable_rows": n,
                       "macro_HLA_Spearman_zero_retained": f"{statistics.mean(retained):.6f}",
                       "macro_HLA_Spearman_zero_excluded": f"{statistics.mean(dropped):.6f}"})
    csvout(D / "metrics/STABILITY_TEACHER_ZERO_SENSITIVITY_REPORTED.csv", output)


if __name__ == "__main__":
    main()
