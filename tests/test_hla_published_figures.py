"""Verify the historical hard-filter figure uses each published endpoint."""

from pathlib import Path
import sys
import unittest

STAGES = Path(__file__).resolve().parents[1] / "scripts/hla_reproduction/stages"
sys.path.insert(0, str(STAGES))

try:
    from historical_figures import render_s10
    from plot_manuscript import plt
except ModuleNotFoundError as error:
    if error.name != "matplotlib":
        raise
    render_s10 = None


@unittest.skipIf(render_s10 is None, "Matplotlib is required for the figure checks")
class PublishedHardFilterFigureTest(unittest.TestCase):
    def test_three_arm_panels_and_two_paired_contrasts(self):
        fields = ("IM_AP", "EL_validation_AP", "Macro_HLA_EL_AP")
        arms = ("A", "H", "R1", "R2", "R3", "R4", "R5")
        rows = [{"Arm": arm, **dict(zip(fields, (.032 + i / 1000, .88 + i / 1000, .82 + i / 1000)))}
                for i, arm in enumerate(arms)]
        contrasts = [
            {"Contrast": "H − A", "Delta AP": "-.002", "CI lower": "-.006", "CI upper": ".002"},
            {"Contrast": "H − mean(R1–R5)", "Delta AP": "-.003", "CI lower": "", "CI upper": ""},
        ]
        figure = render_s10(list(reversed(rows)), contrasts)
        self.addCleanup(plt.close, figure)
        a, b, c, d = figure.axes
        for panel, field in zip((a, b, c), fields, strict=True):
            self.assertEqual([label.get_text() for label in panel.get_yticklabels()], list(arms))
            self.assertEqual(panel.collections[0].get_offsets()[:, 0].tolist(),
                             [row[field] for row in rows])
        self.assertEqual([points.get_offsets()[0, 0] for points in (d.collections[0], d.collections[2])],
                         [-.002, -.003])
        self.assertEqual(len(d.collections), 3)
        self.assertEqual(d.collections[1].get_segments()[0][:, 0].tolist(), [-.006, .002])
