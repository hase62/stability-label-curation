"""Render historical supplements using newly evaluated CSVs from the same run."""
from __future__ import annotations

import argparse

from common import D
from historical_common import check_files
from render_main import plt, tab

RECEIPTS = D / "receipts/historical"


def interval(ax, values, label, point, lower, upper, xlabel):
    for i, row in enumerate(values):
        v = float(row[point])
        ax.scatter(v, i, color="#087f8c", marker="D", zorder=2)
        if row[lower] and row[upper]:
            ax.hlines(i, float(row[lower]), float(row[upper]), color="#087f8c")
    ax.axvline(0, color="grey", linestyle="--", linewidth=.9)
    ax.set(yticks=range(len(values)), yticklabels=[label(r) for r in values], xlabel=xlabel)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.25)


def save(fig, name):
    path = D / "figures" / name
    with path.open("xb") as stream:
        fig.savefig(stream, format="pdf", metadata={"CreationDate": None}, bbox_inches="tight")
    plt.close(fig)


def s9():
    check_files(RECEIPTS / "s9_evaluation.json")
    rows = tab("S_Thermal_Transfer_9.csv")
    if len(rows) != 9:
        raise ValueError("S9 requires three predefined contrasts in each of three cohorts")
    contrasts = {"P_seed_mean": "T − P", "A_seed_mean": "T − A", "D_seed_mean": "T − D"}
    shown_cohorts = (("IMPROVE_A02", "A*02:01 (primary)"),
                     ("IMPROVE_full", "Full IMPROVE"), ("neoepitope", "Neo"))
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.3), sharex=True, layout="constrained")
    for ax, (cohort, title) in zip(axes, shown_cohorts, strict=True):
        subset = [next(r for r in rows if r["Cohort"] == cohort and r["Baseline"] == arm) for arm in contrasts]
        interval(ax, subset, lambda r: contrasts[r["Baseline"]], "Saved delta AP", "CI lower", "CI upper",
                 "Mean paired ΔAP (95% interval)")
        ax.set_title(title)
    save(fig, "Figure_S9_Measured_Tm_Transfer.pdf")


def s10():
    check_files(RECEIPTS / "s10_evaluation.json")
    rows = tab("S_LowStability_Removal_7_Arms.csv")
    contrasts = tab("Historical_Deletion_Contrasts.csv")
    if [r["Arm"] for r in rows] != ["A", "H", "R1", "R2", "R3", "R4", "R5"] or len(contrasts) != 2:
        raise ValueError("S10 requires seven arms and two predefined primary contrasts")
    fig, axes = plt.subplots(1, 3, figsize=(11, 4), layout="constrained")
    for ax, key, title in ((axes[0], "IM_AP", "IMPROVE AP"), (axes[1], "EL_validation_AP", "EL validation AP")):
        ax.scatter([float(r[key]) for r in rows], range(len(rows)),
                   c=["#087f8c" if r["Arm"] == "H" else "#4f5863" for r in rows])
        ax.set(yticks=range(len(rows)), yticklabels=[r["Arm"] for r in rows], xlabel=title)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.25)
    interval(axes[2], contrasts, lambda row: row["Contrast"], "Delta AP", "CI lower", "CI upper",
             "Paired IMPROVE ΔAP (95% interval)")
    save(fig, "Figure_S10_Hard_Filtering.pdf")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("figure", choices=("S9", "S10"))
    {"S9": s9, "S10": s10}[p.parse_args().figure]()
