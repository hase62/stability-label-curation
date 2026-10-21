#!/usr/bin/env python3
"""Render completed Task 2.31 artifacts; never score or fit models."""
import json
import os

from stability_label_curation.paths import resolve_paths
from stability_label_curation.bigmhc_el_positive_upweighting import RUN
from stability_label_curation.monoallelic_replicate_rescue import sha256
from stability_label_curation.replicate_stability_association import write_json


def main():
    paths = resolve_paths()
    directory = paths.project_runs_dir/RUN
    if not (directory/'reports/evaluation_completed.json').exists():
        raise ValueError('Wait for the fixed epoch-10 analysis to complete')
    figure_dir = directory/'figures'
    figure_dir.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(figure_dir/'matplotlib_config')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    point = json.loads((directory/'reports/point_estimates.json').read_text())
    bootstrap = json.loads((directory/'reports/paired_peptide_bootstrap.json').read_text())
    config = json.loads((directory/'reports/scientific_configuration.json').read_text())
    base = paths.project_runs_dir/config['baseline_run_id']
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for arm, color in [('A', '#606060'), ('W', '#087f8c'), ('P', '#c47327')]:
        curve = [json.loads(((base if arm == 'A' else directory)/f'reports/{"" if arm == "A" else arm+"_"}EL_metrics_{epoch:02d}.json').read_text()) for epoch in range(1, 11)]
        axes[0, 0].plot(range(1, 11), [v['validation_AP'] for v in curve], '.-', color=color, label=arm)
        axes[0, 1].plot(range(1, 11), [v['validation_AUROC'] for v in curve], '.-', color=color, label=arm)
    axes[0, 0].set_ylabel('Pooled EL average precision')
    axes[0, 1].set_ylabel('EL AUROC')
    for axis in axes[0]:
        axis.set_xlabel('EL epoch (comparison fixed at 10)')
        axis.legend()
        axis.set_xticks(range(1, 11))
    names = ['W-A', 'W-P', 'P-A']
    for i, name in enumerate(names):
        value = point['contrasts'][name]['AP']
        interval = bootstrap['contrasts'][name]['AP']
        lo, hi = interval['lower_95'], interval['upper_95']
        axes[1, 0].plot([lo, hi], [i, i], color='#555555')
        axes[1, 0].plot(value, i, 'o', color='#087f8c')
    axes[1, 0].axvline(0, color='gray', linewidth=.8)
    axes[1, 0].set_yticks(range(3), names)
    axes[1, 0].invert_yaxis()
    axes[1, 0].set_xlabel('Paired pooled AP difference')
    axes[1, 0].set_title('Exploratory peptide-group bootstrap 95% intervals')
    hla = sorted(point['per_HLA_consistency']['W-A']['per_HLA'])
    x = [point['per_HLA_consistency']['W-A']['per_HLA'][h]['AP'] for h in hla]
    y = [point['per_HLA_consistency']['W-P']['per_HLA'][h]['AP'] for h in hla]
    axes[1, 1].scatter(x, y, s=18, alpha=.75, color='#087f8c')
    axes[1, 1].axvline(0, color='gray', linewidth=.8)
    axes[1, 1].axhline(0, color='gray', linewidth=.8)
    axes[1, 1].set_xlabel('Per-HLA AP: W-A')
    axes[1, 1].set_ylabel('Per-HLA AP: W-P')
    axes[1, 1].set_title(f'All {len(hla)} evaluable HLAs; no selected subgroup')
    fig.suptitle('Task 2.31: developmental EL-only comparison; original labels preserved')
    fig.tight_layout()
    for suffix in ('png', 'pdf'):
        target = figure_dir/f'EL_positive_upweighting.{suffix}'
        if target.exists():
            raise ValueError('Refuse figure overwrite')
        fig.savefig(target, dpi=180)
    plt.close(fig)
    write_json(directory/'reports/figures.json', {'matplotlib_version': matplotlib.__version__,
        'input_point_estimates_sha256': sha256(directory/'reports/point_estimates.json'),
        'input_bootstrap_sha256': sha256(directory/'reports/paired_peptide_bootstrap.json'),
        'script_sha256': sha256(paths.repository_root/'scripts/plot_bigmhc_el_positive_upweighting.py'),
        'figure_sha256': {str(f.relative_to(directory)): sha256(f) for f in figure_dir.glob('EL_positive_upweighting.*')},
        'new_predictions_or_association_tests': False})


if __name__ == '__main__':
    main()
