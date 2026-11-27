"""Render the HLA manuscript's 12 figures from publicly released aggregates."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "stages"))
from historical_figures import render_s9, render_s10
from plot_manuscript import read_csv, render_curve, render_metric


ABSOLUTE = "ABSOLUTE_AP_SOURCE.csv"
METRIC_FIGURES = (
    ("Figure_1", ABSOLUTE, "AP", True),
    ("Figure_2", "ALL_FIVE_PAIRED_CONTRASTS_AP_SOURCE.csv", "AP", False),
    ("Figure_S1", ABSOLUTE, "AUROC", True),
    ("Figure_S2", "ALL_FIVE_PAIRED_CONTRASTS_AUROC_SOURCE.csv", "AUROC", False),
    ("Figure_S3", ABSOLUTE, "PPV10", True),
    ("Figure_S4", ABSOLUTE, "PPV20", True),
)
CURVE_FIGURES = (
    ("Figure_S5", "EL", "train_update_BCE"),
    ("Figure_S6", "EL", "validation_AP"),
    ("Figure_S7", "EL", "validation_BCE"),
    ("Figure_S8", "IM", "train_update_BCE"),
)


def render(source, output):
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Choose an output directory outside the published source directory")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Output directory must be empty: {output}")
    figures = []

    def record(name, sources, panels):
        filename = f"{name}.pdf"
        figures.append((name.replace("_", " "), filename, ";".join(sources), panels))
        return output / filename

    for name, filename, metric, absolute in METRIC_FIGURES:
        render_metric(read_csv(source, filename), metric, absolute=absolute,
                      path=record(name, [filename], 4))
    for name, stage, metric in CURVE_FIGURES:
        filename = f"CURVE_{stage}_{metric}_SOURCE.csv"
        render_curve(read_csv(source, filename), stage, metric, record(name, [filename], 3))

    thermal = "S_Thermal_Transfer_9.csv"
    render_s9(read_csv(source, thermal), record("Figure_S9", [thermal], 3))
    arms, contrasts = "S_LowStability_Removal_7_Arms.csv", "Historical_Deletion_Contrasts.csv"
    render_s10(read_csv(source, arms), read_csv(source, contrasts),
               record("Figure_S10", [arms, contrasts], 4))
    with (output / "figure_source_map.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("manuscript_item", "pdf", "source_csv", "panels"))
        writer.writerows(figures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory of public source_data CSVs")
    parser.add_argument("output_dir", type=Path, help="New or empty output directory")
    args = parser.parse_args()
    render(args.source_dir, args.output_dir)


if __name__ == "__main__":
    main()
