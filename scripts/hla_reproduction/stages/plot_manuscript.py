"""Draw HLA manuscript figures from aggregate rows."""

import argparse
import csv
from itertools import product
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
arms=['A','W_two','L','W_two_perm','L_perm','L_const']
names=['Unweighted','Two-sided','Downweight','Two-sided shuffle','Downweight shuffle','Mean downweight']
contrasts=['W_two-A','L-A','W_two-W_two_perm','L-L_perm','L-L_const']
cnames=['Two-sided − unweighted','Downweight − unweighted','Two-sided − shuffle','Downweight − shuffle','Downweight − mean']
seeds=['42','123','456']
col=['#00788b','#b64e19','#605396']
markers=['o','s','^']
cohorts = ('IMPROVE', 'Neo')
stages = ('EL20', 'IM30')


def read_csv(directory, filename):
    with (directory / filename).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(None in row or None in row.values() for row in rows):
        raise ValueError(f"Empty or malformed CSV: {filename}")
    return rows


def check_grid(rows, columns, expected):
    keys = [tuple(str(row[column]) for column in columns) for row in rows]
    expected = set(expected)
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError(f"Missing, unexpected or repeated keys for {columns}")


def save(fig, path):
    if path is not None:
        with path.open("xb") as stream:
            fig.savefig(stream, format="pdf", metadata={"CreationDate": None})
        plt.close(fig)
    return fig


def render_metric(data, metric, *, absolute, path=None):
    if absolute:
        check_grid(data, ('cohort', 'stage', 'arm'), product(cohorts, stages, arms))
    else:
        check_grid(data, ('cohort', 'stage', 'contrast', 'seed'),
                   product(cohorts, stages, contrasts, seeds))
        for row in data:
            if row['metric'] != metric:
                raise ValueError(f"Expected {metric}, found {row['metric']}")
    title = {'AP': 'Average precision', 'AUROC': 'AUROC',
             'PPV10': 'Precision at 10', 'PPV20': 'Precision at 20'}[metric]
    with plt.rc_context({'font.size': 9, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.spines.left': False, 'xtick.labelsize': 8, 'ytick.labelsize': 8}):
        return _render_metric(data, metric, absolute, title, path)


def _render_metric(data, metric, absolute, title, path):
    fig,ax=plt.subplots(2,2,figsize=(8,5.9),sharex='row',sharey='row')
    fig.subplots_adjust(left=.242,right=.98,bottom=.115,top=.825,wspace=.13,hspace=.52)
    fig.text(.03,.956,title if absolute else 'Paired difference in ' + ('AUROC' if metric == 'AUROC' else title.lower()),weight='bold',fontsize=14)
    handles=[Line2D([],[],ls='',marker=m,color=c,ms=4,label='Seed '+s) for m,c,s in zip(markers,col,seeds)]
    handles.append(Line2D([],[],color='#20262a',lw=0 if absolute else 1.4,marker='D',ms=4,label='Mean' if absolute else 'Mean and conditional 95% interval'))
    if absolute:handles.append(Line2D([],[],color='#686868',ls='--',lw=1,label='Chance AUROC' if metric == 'AUROC' else 'Positive fraction'))
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.025,.937),frameon=False,ncol=5,columnspacing=1.4,fontsize=8)
    for i,cohort in enumerate(['IMPROVE','Neo']):
        for j,stage in enumerate(['EL20','IM30']):
            panel=ax[i,j]
            cells=[r for r in data if r['cohort']==cohort and r['stage']==stage]
            labels=names if absolute else cnames
            for k,key in enumerate(arms if absolute else contrasts):
                rs=[r for r in cells if r['arm' if absolute else 'contrast']==key]
                if not absolute and len({tuple(r[v] for v in ('mean_delta', 'lower_95', 'upper_95')) for r in rs}) != 1:
                    raise ValueError(f'Inconsistent repeated mean or interval for {cohort}, {stage}, {key}')
                if not absolute:panel.plot([float(rs[0][v]) for v in ('lower_95','upper_95')],[k,k],color='#20262a',lw=1.3,zorder=2)
                for s,m,c,offset in zip(seeds,markers,col,[-.22,.12,.22]):
                    val=float(rs[0][metric+'_seed'+s]) if absolute else float(next(r['seed_delta'] for r in rs if r['seed']==s))
                    panel.plot(val,k+offset,marker=m,color=c,ms=3.7,ls='',zorder=3)
                panel.plot(float(rs[0][metric+'_mean' if absolute else 'mean_delta']),k,marker='D',color='#20262a',ms=3.8,ls='',zorder=4)
            reference = (.5 if metric == 'AUROC' else float(cells[0]['prevalence'])) if absolute else 0
            panel.axvline(reference, ls='--', lw=.8, color='#666')
            panel.set_ylim(len(labels)-.55,-.5);panel.set_yticks(range(len(labels)),labels)
            panel.set_title(f'{cohort}  ·  {stage}',loc='left',fontsize=10,fontweight='bold')
            panel.xaxis.set_major_locator(MaxNLocator(5));panel.xaxis.set_major_formatter(FormatStrFormatter('%.3f' if i==0 else '%.2f'))
            panel.grid(axis='x',color='#dddddd',lw=.5);panel.tick_params(axis='y',length=0,pad=5)
            panel.set_xlabel(metric if absolute else 'Δ' + metric)
    return save(fig, path)


def render_curve(rows, stage, metric, path=None):
    epochs = range(1, (20 if stage == "EL" else 30) + 1)
    check_grid(rows, ("stage", "seed", "arm", "epoch"),
               product((stage,), seeds, arms, map(str, epochs)))
    ylabel = {"train_update_BCE": "Training update BCE", "validation_AP": "Validation AP",
              "validation_BCE": "Validation BCE"}[metric]
    with plt.rc_context({"pdf.fonttype": 42, "font.size": 9}):
        fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True, layout="constrained")
        for ax, seed in zip(axes, seeds, strict=True):
            for arm in arms:
                points = sorted((int(row["epoch"]), float(row[metric])) for row in rows
                                if row["arm"] == arm and str(row["seed"]) == seed)
                ax.plot(*zip(*points), label=arm, marker=".", ms=3)
            ax.set(xlabel="Completed epoch", title=f"{stage} · seed {seed}")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.grid(alpha=.2)
        axes[0].set_ylabel(ylabel)
        axes[-1].legend(fontsize=7)
        return save(fig, path)


def main():
    parser = argparse.ArgumentParser(description="Render the two main figures from aggregate CSVs.")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=True, parents=True)
    for absolute, stem in ((True, "ABSOLUTE_AP"), (False, "ALL_FIVE_PAIRED_CONTRASTS_AP")):
        render_metric(read_csv(args.source_dir, f"{stem}_SOURCE.csv"), "AP", absolute=absolute,
                      path=args.output_dir / f"{stem}.pdf")


if __name__ == "__main__":
    main()
