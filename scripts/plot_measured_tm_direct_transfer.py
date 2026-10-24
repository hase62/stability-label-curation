#!/usr/bin/env python3
"""Task2.37 figures from saved metrics/intervals only, no new analysis."""
import json,os
from stability_label_curation.paths import resolve_paths
from stability_label_curation import measured_tm_direct_transfer as study


def main():
    paths=resolve_paths();d=paths.project_runs_dir/study.RUN
    if not (d/'reports/evaluation_complete.json').exists():raise ValueError('Evaluation incomplete')
    out=d/'figures';out.mkdir(exist_ok=True);os.environ['MPLCONFIGDIR']=str(out/'matplotlib_config')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    points=json.loads((d/'evaluation/point_metrics.json').read_text())
    hla=json.loads((d/'evaluation/per_HLA_metrics.json').read_text())['IMPROVE']
    ci={name:json.loads((d/f'evaluation/{name}_paired_uncertainty.json').read_text()) for name in ('IMPROVE_A02','IMPROVE_full')}
    fig,axes=plt.subplots(2,2,figsize=(16,11));colors={'A':'#777777','D':'#7d5ba6','P':'#ca8a28','T':'#087f8c'}
    for axis,name,title in [(axes[0,0],'IMPROVE_A02','Primary A*02:01: 21/616 recognized'),(axes[0,1],'IMPROVE_full','Secondary full IMPROVE: 227/7,788 recognized')]:
        values=points[name]
        for index,arm in enumerate(('A','D','P','T')):
            axis.bar(index,values['seed_means'][arm]['AP'],color=colors[arm],alpha=.55,label=arm)
            if arm!='A':
                for j,seed in enumerate(study.SEEDS):axis.plot(index+(j-1)*.12,values['per_seed'][str(seed)][arm]['AP'],marker=('o','s','^')[j],color=colors[arm])
        axis.axhline(values['population']['prevalence'],color='black',linestyle='--',linewidth=.7)
        axis.set_xticks(range(4),['A','D','P','T']);axis.set_ylabel('Non-interpolated IM AP');axis.set_title(title)
    ax=axes[1,0]
    for j,(name,label,color) in enumerate([('IMPROVE_A02','A*02:01; 16 components','#087f8c'),('IMPROVE_full','Full cohort; 38 components','#7d5ba6')]):
        for i,pair in enumerate(('T-P','T-A','T-D')):
            interval=ci[name]['confidence_intervals'][pair]['AP'];value=points[name]['seed_mean_paired_contrasts'][pair]['AP'];y=i+j*.22
            ax.plot([interval['lower_95'],interval['upper_95']],[y,y],color=color)
            ax.plot(value,y,'o',color=color,label=label if i==0 else None)
    ax.axvline(0,color='black',linewidth=.7);ax.set_yticks([.11,1.11,2.11],['T-P','T-A','T-D']);ax.invert_yaxis()
    ax.set_xlabel('Mean seed-paired AP difference; exploratory 95% interval');ax.legend(fontsize=9)
    ax.set_title('Patient/peptide component bootstrap; no seed bootstrap')
    ax=axes[1,1];evaluable=[(h,v) for h,v in hla.items() if v['adequately_evaluable']]
    changes=[v['point']['seed_mean_paired_contrasts']['T-A']['AP'] for h,v in evaluable]
    ax.bar(range(len(changes)),changes,color=['#087f8c' if v>=0 else '#bb5348' for v in changes])
    ax.axhline(0,color='black',linewidth=.7);ax.set_xticks(range(len(changes)),[h.replace('HLA-','') for h,v in evaluable],rotation=65,ha='right')
    ax.set_ylabel('Mean T-A AP change');ax.set_title('All 20 predeclared evaluable HLAs; descriptive points only')
    fig.suptitle('Task2.37: measured-Tm direct output adaptation; previously inspected IM cohorts\nSeed markers: circle123, square456, triangle789; scores are not calibrated immunogenicity probabilities')
    fig.tight_layout();written=[]
    for suffix in ('png','pdf'):
        path=out/f'measured_Tm_A02_direct_transfer.{suffix}'
        if path.exists():raise ValueError('Refuse figure overwrite')
        fig.savefig(path,dpi=180);written.append(path)
    plt.close(fig)
    study.write_json(d/'reports/figures.json',{'matplotlib_version':matplotlib.__version__,
        'script_sha256':study.sha(paths.repository_root/'scripts/plot_measured_tm_direct_transfer.py'),
        'point_metrics_sha256':study.sha(d/'evaluation/point_metrics.json'),
        'figure_sha256':{str(f.relative_to(d)):study.sha(f) for f in written},'model_or_metric_recomputation':False})


if __name__=='__main__':main()
