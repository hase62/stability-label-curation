"""Render historical figures from aggregate tables."""

from __future__ import annotations

from plot_manuscript import check_grid, plt, save
from matplotlib.ticker import FormatStrFormatter, MultipleLocator


def interval(ax, values, label, point, lower, upper, xlabel, color="#087f8c"):
    for i, row in enumerate(values):
        ax.scatter(float(row[point]), i, color=color, marker="D", zorder=3)
        if bool(row[lower]) != bool(row[upper]):
            raise ValueError("An interval must have both endpoints or be missing")
        if row[lower]:
            endpoints = [float(row[lower]), float(row[upper])]
            ax.hlines(i, *endpoints, color=color)
            ax.plot(endpoints, [i, i], color=color, marker="|", linestyle="", ms=9)
    ax.axvline(0, color="#173c56", linestyle="--", linewidth=.9)
    ax.set(yticks=range(len(values)), yticklabels=[label(r) for r in values], xlabel=xlabel)
    ax.set_ylim(len(values) - .5, -.5)
    ax.grid(axis="x", alpha=.25)


def render_s9(rows, path=None):
    contrasts = {"P_seed_mean": "T − P", "A_seed_mean": "T − A", "D_seed_mean": "T − D"}
    shown_cohorts = (("IMPROVE_A02", "A*02:01 (primary)"),
                     ("IMPROVE_full", "Full IMPROVE"), ("neoepitope", "Neo"))
    check_grid(rows, ("Cohort", "Baseline"),
               ((cohort, baseline) for cohort, _ in shown_cohorts for baseline in contrasts))
    with plt.rc_context({"pdf.fonttype": 42}):
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.3), sharex=True, layout="constrained")
        for ax, (cohort, title) in zip(axes, shown_cohorts, strict=True):
            subset = [next(r for r in rows if r["Cohort"] == cohort and r["Baseline"] == arm)
                      for arm in contrasts]
            interval(ax, subset, lambda r: contrasts[r["Baseline"]], "Saved delta AP",
                     "CI lower", "CI upper", "Mean paired ΔAP (95% interval)")
            ax.set_title(title)
        return save(fig, path)


def render_s10(rows, contrasts, path=None):
    arms = ("A", "H", "R1", "R2", "R3", "R4", "R5")
    comparisons = ("H − A", "H − mean(R1–R5)")
    check_grid(rows, ("Arm",), ((arm,) for arm in arms))
    check_grid(contrasts, ("Contrast",), ((contrast,) for contrast in comparisons))
    ordered = [next(row for row in rows if row["Arm"] == arm) for arm in arms]
    contrasts = [next(row for row in contrasts if row["Contrast"] == value)
                 for value in comparisons]
    navy, orange, grey = "#173c56", "#cd813b", "#6d808d"
    colors = [navy, orange, *([grey] * 5)]
    panels = (
        ("IM_AP", "a  IMPROVE zero-shot IM AP", (.0295, .0412), .002, 3),
        ("EL_validation_AP", "b  EL validation pooled AP", (.873, .8881), .002, 3),
        ("Macro_HLA_EL_AP", "c  EL validation macro-HLA AP", (.813, .853), .01, 2),
    )
    with plt.rc_context({"font.size": 9, "pdf.fonttype": 42, "axes.spines.top": False,
                         "axes.spines.right": False}):
        fig, axes = plt.subplots(2, 2, figsize=(8.2, 7.6))
        fig.subplots_adjust(left=.10, right=.97, bottom=.09, top=.94, wspace=.45, hspace=.53)
        for ax, (key, title, bounds, step, decimals) in zip(axes.flat, panels):
            values = [float(row[key]) for row in ordered]
            lo = min(bounds[0], min(values) - .2 * step)
            hi = max(bounds[1], max(values) + step)
            ax.scatter(values, range(len(arms)), c=colors, zorder=3, s=30)
            for i, (value, color) in enumerate(zip(values, colors, strict=True)):
                ax.annotate(f"{value:.4f}", (value, i), xytext=(5, 0),
                            textcoords="offset points", va="center", color=color, fontsize=8)
            ax.axvline(values[0], color=navy, linestyle="--", linewidth=.9)
            ax.set(yticks=range(len(arms)), yticklabels=arms, xlim=(lo, hi), ylim=(6.5, -.5),
                   xlabel="Average precision (magnified axis)")
            ax.xaxis.set_major_locator(MultipleLocator(step))
            ax.xaxis.set_major_formatter(FormatStrFormatter(f"%.{decimals}f"))
            ax.set_title(title, loc="left", weight="bold", color=navy)
            ax.grid(axis="x", alpha=.25)
        ax = axes[1, 1]
        interval(ax, contrasts, lambda row: row["Contrast"].replace(" − ", "−"),
                 "Delta AP", "CI lower", "CI upper", "IM AP difference", color=orange)
        endpoints = [float(row[key]) for row in contrasts
                     for key in ("Delta AP", "CI lower", "CI upper") if row[key]]
        ax.set_xlim(min(-.007, min(endpoints) - .0005), max(.0041, max(endpoints) + .0005))
        ax.xaxis.set_major_locator(MultipleLocator(.002))
        ax.set_title("d  Paired IM AP contrasts", loc="left", weight="bold", color=navy)
        return save(fig, path)


def main():
    import argparse

    from common import D
    from historical_common import check_files
    from plot_manuscript import read_csv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("figure", choices=("S9", "S10"))
    figure = parser.parse_args().figure
    check_files(D / "receipts/historical" / f"{figure.lower()}_evaluation.json")
    metrics = D / "metrics"
    if figure == "S9":
        render_s9(read_csv(metrics, "S_Thermal_Transfer_9.csv"),
                  D / "figures/Figure_S9_Measured_Tm_Transfer.pdf")
    else:
        render_s10(read_csv(metrics, "S_LowStability_Removal_7_Arms.csv"),
                   read_csv(metrics, "Historical_Deletion_Contrasts.csv"),
                   D / "figures/Figure_S10_Hard_Filtering.pdf")


if __name__ == "__main__":
    main()
