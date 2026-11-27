"""Compute HLA coverage and descriptive AUROC contrasts from aggregate CSVs."""
import argparse
import csv
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import mean

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path, help="Existing directory of final aggregate CSVs")
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)

def read(name):
    with (args.source / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def save(name, rows):
    with (args.output / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

constants = read("CONTROL_CONSTANT_FP32_DIAGNOSTICS.csv")
el_hla_by_seed = defaultdict(dict)
for row in constants:
    assert row["exact_mean_match"] == "True"
    n, w = (int(row["positive_n"]), Fraction(row["L_mean_exact"]))
    assert row["hla"] not in el_hla_by_seed[row["seed"]]
    el_hla_by_seed[row["seed"]][row["hla"]] = (n, w)
assert set(el_hla_by_seed) == {"42", "123", "456"}
assert el_hla_by_seed["42"] == el_hla_by_seed["123"] == el_hla_by_seed["456"]
el_hla = el_hla_by_seed["42"]
assert len(el_hla) == 49 and sum(n for n, w in el_hla.values()) == 63053
training = [{"HLA": h, "EL_positive_n": n, "mean_L_exact": str(w), "mean_L": float(w)}
            for h, (n, w) in sorted(el_hla.items())]
save("HLA_EL_WEIGHTING_COVERAGE_SOURCE.csv", training)

valid_cohorts = ("IMPROVE", "Neo")
valid_arms = ("W_two", "W_two_perm")
seeds = ("42", "123", "456")
hla_metrics = defaultdict(dict)
for row in read("ALL_HLA_DESCRIPTIVE_METRICS.csv"):
    key = tuple(row[k] for k in ("cohort", "stage", "arm", "seed"))
    assert row["hla"] not in hla_metrics[key]
    hla_metrics[key][row["hla"]] = (int(row["n"]), int(row["positive"]), row["AUROC"])
pooled_metrics = {tuple(row[k] for k in ("cohort", "stage", "arm", "seed")): row
                  for row in read("MAIN_72_METRICS.csv")}
coverage_detail, coverage = [], []
for cohort in valid_cohorts:
    counts = {h: (n, p) for h, (n, p, v) in hla_metrics[cohort, "IM30", "A", "42"].items()}
    assert all(counts == {h: (n, p) for h,(n,p,v) in hist.items()}
               for (c, *rest), hist in hla_metrics.items() if c == cohort)
    for h, (n, p) in sorted(counts.items()):
        coverage_detail.append(dict(cohort=cohort, HLA=h, direct_EL_weighting=h in el_hla, n=n, positive=p))
    n = sum(r[0] for r in counts.values())
    selected = [vals for h, vals in counts.items() if h in el_hla]
    covered, covered_p = map(sum, zip(*selected))
    coverage.append(dict(cohort=cohort, evaluated_HLAs=len(counts), covered_HLAs=len(selected),
                         noncovered_HLAs=len(counts)-len(selected), n=n, positive=sum(r[1] for r in counts.values()),
                         covered_n=covered, covered_positive=covered_p, noncovered_n=n-covered,
                         noncovered_positive=sum(r[1] for r in counts.values())-covered_p,
                         noncovered_fraction=(n-covered)/n))
save("EVAL_HLA_COVERAGE.csv", coverage)
save("EVAL_HLA_COVERAGE_BY_ALLELE.csv", coverage_detail)

auroc_rows, contrasts = [], []
for cohort, stage in (("Neo","EL20"),("IMPROVE","IM30"),("Neo","IM30")):
    seed_values = {}
    for seed in seeds:
        for arm in valid_arms:
            key = (cohort,stage,arm,seed)
            strata = hla_metrics[key]
            total = pooled_metrics[key]
            assert sum(n for n,p,v in strata.values()) == int(total["n"])
            assert sum(p for n,p,v in strata.values()) == int(total["positive"])
            all_pairs = int(total["positive"]) * int(total["negative"])
            same_pairs = sum(p * (n-p) for n,p,v in strata.values())
            same_credit = sum(p * (n-p) * float(v) for n,p,v in strata.values() if p*(n-p))
            overall = float(total["AUROC"])
            r = dict(cohort=cohort, stage=stage, seed=seed, arm=arm, total_pairs=all_pairs,
                     same_HLA_pairs=same_pairs, different_HLA_pairs=all_pairs-same_pairs,
                     pooled_AUROC=overall, same_HLA_AUROC=same_credit/same_pairs,
                     different_HLA_AUROC=(all_pairs*overall-same_credit)/(all_pairs-same_pairs))
            auroc_rows.append(r)
            seed_values[seed,arm] = r
    pairs = seed_values[seeds[0],valid_arms[0]]
    differences = dict(cohort=cohort,stage=stage,contrast="W_two-W_two_perm",
                       total_pairs=pairs["total_pairs"],same_HLA_pairs=pairs["same_HLA_pairs"],
                       different_HLA_pairs=pairs["different_HLA_pairs"])
    for k in ("pooled_AUROC","same_HLA_AUROC","different_HLA_AUROC"):
        differences["delta_"+k] = mean(seed_values[seed,valid_arms[0]][k] -
                                       seed_values[seed,valid_arms[1]][k] for seed in seeds)
    contrasts.append(differences)
save("HLA_PAIR_AUROC_BY_SEED.csv", auroc_rows)
save("HLA_PAIR_AUROC_CONTRASTS.csv", contrasts)
weights = [w for n,w in el_hla.values()]
print(f"L mean range: {float(min(weights)):.10f} to {float(max(weights)):.10f}")
print(coverage)
print(contrasts)
