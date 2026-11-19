"""Supplementary exact-identity audit and Neo EL20 AUROC pair decomposition."""
from __future__ import annotations

from collections import Counter
import statistics

from common import D, SEEDS, csvout, native, read, records, rows, sha, validate_seal
from prepare import INPUTS


def overlap_table():
    populations = {"EL fitting": rows("EL_train"), "EL validation": rows("EL_validation"),
                   "IM fitting": rows("IM_train")}
    partition = {a["observation_id"]: a["partition"] for a in read(INPUTS / "teacher_partition.json")["assignments"]}
    # DTU row identities are regenerated from the authenticated raw source by the Teacher stage.
    for stage in ("train", "validation"):
        populations[f"Teacher {stage}"] = [
            {"peptide": record["peptide"], "hla": record["hla"]}
            for record in records(INPUTS / "teacher_identities.jsonl")
            if partition[record["observation_id"]] == stage]
    output = []
    for cohort in ("IMPROVE", "Neo"):
        identities = records(D / f"cohorts/{cohort}_identities.jsonl")
        outcomes = records(D / f"cohorts/{cohort}_outcomes.jsonl")
        native.assert_alignment([r["source_id"] for r in identities], [r["source_id"] for r in outcomes])
        for key, reference in populations.items():
            peptides = {r["peptide"] for r in reference}
            pairs = {(r["peptide"], r["hla"]) for r in reference}
            hits = [y["label"] for r, y in zip(identities, outcomes, strict=True) if r["peptide"] in peptides]
            pair_hits = [y["label"] for r, y in zip(identities, outcomes, strict=True) if (r["peptide"], r["hla"]) in pairs]
            output.append({"development_input": key, "source_rows": len(reference), "evaluation_cohort": cohort,
                           "exact_peptide_matches": len(hits), "exact_peptide_match_positives": sum(hits),
                           "exact_peptide_HLA_matches": len(pair_hits), "exact_pair_match_positives": sum(pair_hits),
                           "evidence": "Fresh exact comparison of hash-validated frozen inventories"})
    csvout(D / "metrics/ACTUAL_DEVELOPMENT_OVERLAP_EVIDENCE.csv", output)


def pair_auc(labels, scores, alleles):
    """Count concordant positive-negative pairs, giving a tied pair half credit."""
    totals = Counter()
    concordant = Counter()
    positives = [(score, allele) for y, score, allele in zip(labels, scores, alleles, strict=True) if y == 1]
    negatives = [(score, allele) for y, score, allele in zip(labels, scores, alleles, strict=True) if y == 0]
    for ps, pa in positives:
        for ns, na in negatives:
            group = "within" if pa == na else "between"
            totals[group] += 1
            concordant[group] += (ps > ns) + 0.5 * (ps == ns)
    total = sum(totals.values())
    return {"total_pairs": total, "within_HLA_pairs": totals["within"], "between_HLA_pairs": totals["between"],
            "pooled_AUROC": sum(concordant.values()) / total,
            **{f"{group}_HLA_AUROC": concordant[group] / totals[group] for group in ("within", "between")}}


def neo_decomposition():
    arms = ("W_two", "W_two_perm")
    rr = records(D / "cohorts/Neo_identities.jsonl")
    yy = records(D / "cohorts/Neo_outcomes.jsonl")
    keys = [r["source_id"] for r in rr]
    alleles = [r["hla"] for r in rr]
    native.assert_alignment(keys, [r["source_id"] for r in yy])
    labels = [int(r["label"]) for r in yy]
    observed = {}
    for arm in arms:
        for seed in SEEDS:
            name = f"{arm}_{seed}_EL20_Neo.jsonl"
            path = D / "private/predictions" / name
            manifest = read(D / f"receipts/{arm}_{seed}_predictions_frozen.json")
            if sha(path) != manifest[name]["sha256"]:
                raise ValueError("Changed Neo prediction")
            scores = records(path)
            native.assert_alignment(keys, [r["source_id"] for r in scores])
            observed[arm, str(seed)] = pair_auc(labels, [r["positive_probability"] for r in scores], alleles)
    metrics = ("pooled_AUROC", "within_HLA_AUROC", "between_HLA_AUROC")
    counts = {k: v for k, v in observed[arms[0], "42"].items() if k.endswith("_pairs")}
    output = []
    for arm in arms:
        for seed in SEEDS:
            output.append({"cohort": "Neo", "endpoint": "EL20", "arm_or_contrast": arm, "summary": seed,
                           **observed[arm, str(seed)]})
        means = {key: statistics.mean(observed[arm, str(seed)][key] for seed in SEEDS) for key in metrics}
        output.append({"cohort": "Neo", "endpoint": "EL20", "arm_or_contrast": arm, "summary": "arithmetic mean of three seeds",
                       **counts, **means})
    output.append({"cohort": "Neo", "endpoint": "EL20", "arm_or_contrast": "W_two-W_two_perm", "summary": "arithmetic mean of three seeds",
                   **counts, **{key: statistics.mean(observed["W_two", str(seed)][key] - observed["W_two_perm", str(seed)][key]
                                                      for seed in SEEDS) for key in metrics}})
    csvout(D / "metrics/NEO_EL20_AUROC_PAIR_DECOMPOSITION.csv", output)


if __name__ == "__main__":
    validate_seal()
    overlap_table()
    neo_decomposition()
