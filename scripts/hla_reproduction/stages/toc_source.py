"""Generate the numerical source of the editorial graphical abstract."""
from common import D, csvout
from render_main import tab


def graphical_toc_rows():
    means = tab("MAIN_ABSOLUTE_METRIC_MEANS.csv")
    contrasts = tab("MAIN_20_MEAN_CONTRASTS.csv")
    intervals = tab("MAIN_CONDITIONAL_CI.csv")
    result = []
    for cohort in ("IMPROVE", "Neo"):
        def match(r):
            return r["cohort"] == cohort and r["stage"] == "IM30"
        def contrast(r):
            return match(r) and r["contrast"] == "W_two-W_two_perm"
        point = next(r["AUROC_mean"] for r in means if match(r) and r["arm"] == "A")
        diff = next(r["mean_delta_AP"] for r in contrasts if contrast(r))
        ci = next(r for r in intervals if contrast(r) and r["metric"] == "AP")
        result.append({"cohort": cohort, "unweighted_AUROC": point, "mean_delta_AP": diff,
                       "conditional_AP_lower_95": ci["lower_95"], "conditional_AP_upper_95": ci["upper_95"]})
    return result


if __name__ == "__main__":
    csvout(D / "figures/Graphical_TOC_Source.csv", graphical_toc_rows())
