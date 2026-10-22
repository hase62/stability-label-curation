#!/usr/bin/env python3
"""Task 2.32 figures from saved endpoints only; no model calls or new tests."""
import json
import os
from stability_label_curation.paths import resolve_paths
from stability_label_curation.el_only_zero_shot_im import RUN
from stability_label_curation.replicate_stability_association import write_json
from stability_label_curation.monoallelic_replicate_rescue import sha256


def main():
    paths = resolve_paths(); directory = paths.project_runs_dir/RUN
    if not (directory/'reports/evaluation_completed.json').exists():
        raise ValueError('Evaluation is not complete')
    target = directory/'figures'; target.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(target/'matplotlib_config')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    points = json.loads((directory/'evaluation/point_metrics.json').read_text())
    uncertainty = {name: json.loads((directory/f'evaluation/{name}_paired_uncertainty.json').read_text())
                   for name in ('IMPROVE','neoepitope')}
    fig, axes = plt.subplots(2,2,figsize=(12,8))
    colors = {'A':'#666666','W':'#087f8c','P':'#c47327'}
    for i, arm in enumerate(('A','W','P')):
        axes[0,0].bar([x+(i-1)*.23 for x in (0,1)],
            [points[n]['arms'][arm]['AP_over_prevalence'] for n in ('IMPROVE','neoepitope')],
            width=.23,label=arm,color=colors[arm])
        axes[0,1].plot([0,1],[points[n]['arms'][arm]['AUROC'] for n in ('IMPROVE','neoepitope')],
                       'o-',label=arm,color=colors[arm])
    axes[0,0].axhline(1,color='black',linewidth=.7,linestyle='--')
    axes[0,0].set_ylabel('AP / positive prevalence')
    axes[0,0].set_title('Different assay contexts and prevalence')
    axes[0,1].axhline(.5,color='black',linewidth=.7,linestyle='--')
    axes[0,1].set_ylabel('AUROC')
    axes[0,1].set_title('Frozen direct EL scores')
    for ax in axes[0]:
        ax.set_xticks([0,1],['IMPROVE ≥3\n227/7,788 positive','Neoepitope\n57/267 positive'])
        ax.legend()
    for column, (dataset, field) in enumerate([('IMPROVE','patient_peptide'),('neoepitope','peptide')]):
        ax = axes[1,column]
        for i, contrast in enumerate(('W-A','W-P','P-A')):
            ci = uncertainty[dataset][field]['confidence_intervals'][contrast]['AP']
            value = points[dataset]['contrasts'][contrast]['AP']
            ax.plot([ci['lower_95'],ci['upper_95']],[i,i],color='#555555')
            ax.plot(value,i,'o',color='#087f8c')
        ax.axvline(0,color='black',linewidth=.7)
        ax.set_yticks(range(3),['W-A','W-P','P-A']); ax.invert_yaxis()
        ax.set_xlabel('Paired AP difference; exploratory 95% interval')
        ax.set_title(dataset+(' — 38 patient/peptide components' if column==0 else ' — 265 peptide clusters'))
    fig.suptitle('Task 2.32: EL-only zero-shot T-cell recognition ranking; previously evaluated sources')
    fig.tight_layout()
    files=[]
    for suffix in ('png','pdf'):
        path=target/f'EL_only_zero_shot_IM.{suffix}'
        if path.exists():raise ValueError('Refuse figure overwrite')
        fig.savefig(path,dpi=180);files.append(path)
    plt.close(fig)
    write_json(directory/'reports/figures.json',{'matplotlib_version':matplotlib.__version__,
        'script_sha256':sha256(paths.repository_root/'scripts/plot_el_only_zero_shot_im.py'),
        'point_metrics_sha256':sha256(directory/'evaluation/point_metrics.json'),
        'figure_sha256':{str(f.relative_to(directory)):sha256(f) for f in files},
        'new_inference_performance_or_resampling':False})


if __name__=='__main__':main()
