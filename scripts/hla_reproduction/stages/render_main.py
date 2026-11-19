"""Final figures/reports/package from completed new experiment only. No training."""
from common import *
import shutil,zipfile,base64,re,statistics
from datetime import datetime, timezone
os.environ['MPLCONFIGDIR']=str(D/'private/matplotlib_config')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'pdf.fonttype':42,'font.size':10})

def tab(name):return list(csv.DictReader((D/'metrics'/name).open()))
def text(p,s):
 with Path(p).open('x') as f:f.write(s)
def export_figure_sources(mapping, absolute, means, intervals, by_seed, curves):
    """Write exactly the records used by each figure, alongside its PDF."""
    for entry in mapping:
        filename = entry['figure']
        source = entry['source']
        if filename.startswith('ABSOLUTE_'):
            rows = absolute
        elif filename.startswith('ALL_FIVE_PAIRED_CONTRASTS_'):
            metric = Path(filename).stem.rsplit('_', 1)[1]
            key = ('cohort', 'stage', 'contrast')
            index = {tuple(row[k] for k in key): row for row in means}
            ci_index = {tuple(row[k] for k in key): row for row in intervals
                        if row['metric'] == metric}
            rows = []
            for seed_row in by_seed:
                identity = tuple(seed_row[k] for k in key)
                rows.append({
                    **{k: seed_row[k] for k in key},
                    'seed': seed_row['seed'], 'metric': metric,
                    'seed_delta': seed_row['delta_' + metric],
                    'mean_delta': index[identity]['mean_delta_' + metric],
                    **{k: ci_index[identity][k] for k in
                       ('lower_95', 'upper_95', 'attempts', 'valid_draws', 'component_n')},
                })
        else:
            assert filename.startswith('CURVE_')
            _, stage, metric = Path(filename).stem.split('_', 2)
            rows = [{k: row[k] for k in ('arm', 'seed', 'stage', 'epoch', metric)}
                    for row in curves if row['stage'] == stage]
        csv_name = Path(filename).stem + '_SOURCE.csv'
        csvout(D / 'figures' / csv_name, rows)
        entry.update(source='figures/' + csv_name, upstream_tables=source, source_rows=len(rows))


def main():
 commands();validate_seal();qa=read(D/'reports/FINAL_QA.json');assert qa['status']=='PASS';assert read(D/'reports/evaluation_completed.json')['status']=='COMPLETE'
 absolute=tab('MAIN_ABSOLUTE_METRIC_MEANS.csv');diff=tab('MAIN_20_MEAN_CONTRASTS.csv');ci=tab('MAIN_CONDITIONAL_CI.csv');seed=tab('MAIN_60_SEED_CONTRASTS.csv');assert (len(absolute),len(diff),len(ci),len(seed))==(24,20,40,60);mapping=[]
 # Plot source files remain complete, fixed order all arms and all five contrasts.
 for metric in ['AP','AUROC','PPV10','PPV20']:
  fig,axes=plt.subplots(2,2,figsize=(14,9))
  for ax,(cohort,stage) in zip(axes.flat,[(n,s) for n in ['IMPROVE','Neo'] for s in ['EL20','IM30']]):
   rr=[next(r for r in absolute if r['cohort']==cohort and r['stage']==stage and r['arm']==a) for a in ARMS];x=np.arange(6)
   for col,offset in [('seed42',-.1),('seed123',0),('seed456',.1)]:ax.scatter(x+offset,[float(r[metric+'_'+col]) for r in rr],s=18,label=col)
   ax.scatter(x,[float(r[metric+'_mean']) for r in rr],marker='_',s=200,color='black',label='arithmetic mean metric');ax.set(xticks=x,xticklabels=ARMS,ylabel=metric,title=f'{cohort} {stage}');ax.tick_params(axis='x',rotation=35);ax.legend(fontsize=7);ax.grid(axis='y',alpha=.2)
  fig.tight_layout();name=f'ABSOLUTE_{metric}.pdf';fig.savefig(D/'figures'/name,bbox_inches='tight',metadata={'CreationDate':None});plt.close(fig);mapping.append({'figure':name,'source':'metrics/MAIN_ABSOLUTE_METRIC_MEANS.csv','definition':'all six arms, all seeds, arithmetic mean metric; not score ensemble'})
 for metric in ['AP','AUROC']:
  fig,axes=plt.subplots(2,2,figsize=(15,10))
  for ax,(cohort,stage) in zip(axes.flat,[(n,s) for n in ['IMPROVE','Neo'] for s in ['EL20','IM30']]):
   for i,(contrast,a,b) in enumerate(CONTRASTS):
    p=next(r for r in diff if r['cohort']==cohort and r['stage']==stage and r['contrast']==contrast);interval=next(r for r in ci if r['cohort']==cohort and r['stage']==stage and r['contrast']==contrast and r['metric']==metric);v=float(p['mean_delta_'+metric]);lo=float(interval['lower_95']);hi=float(interval['upper_95']);ax.plot([lo,hi],[i,i],color='black');ax.scatter([v],[i],color='black',marker='D')
    rr=[r for r in seed if r['cohort']==cohort and r['stage']==stage and r['contrast']==contrast];ax.scatter([float(r['delta_'+metric]) for r in rr],[i-.12,i,i+.12],s=18)
   ax.set(yticks=np.arange(5),yticklabels=[r[0] for r in CONTRASTS],xlabel='paired difference '+metric,title=f'{cohort} {stage}');ax.axvline(0,color='grey',ls='--');ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
  fig.tight_layout();name=f'ALL_FIVE_PAIRED_CONTRASTS_{metric}.pdf';fig.savefig(D/'figures'/name,bbox_inches='tight',metadata={'CreationDate':None});plt.close(fig);mapping.append({'figure':name,'source':'metrics/MAIN_20_MEAN_CONTRASTS.csv; MAIN_60_SEED_CONTRASTS.csv; MAIN_CONDITIONAL_CI.csv','definition':'seed points / mean paired delta / unadjusted conditional component bootstrap95 interval; all five contrasts'})
 curves=tab('ALL900_EPOCH_METRICS.csv')
 for stage,col in [('EL','train_update_BCE'),('IM','train_update_BCE'),('EL','validation_BCE'),('EL','validation_AP')]:
  if col not in curves[0]:continue
  fig,axes=plt.subplots(1,3,figsize=(17,4.5),sharey=True)
  for ax,s in zip(axes,SEEDS):
   for a in ARMS:
    rs=sorted([r for r in curves if r['arm']==a and int(r['seed'])==s and r['stage']==stage],key=lambda r:int(r['epoch']));assert len(rs)==(20 if stage=='EL' else 30);ax.plot([int(r['epoch']) for r in rs],[float(r[col]) for r in rs],label=a,marker='.',ms=3)
   ax.set(xlabel='completed epoch',ylabel=col,title=f'{stage} seed{s}');ax.legend(fontsize=7);ax.grid(alpha=.2)
  fig.tight_layout();name=f'CURVE_{stage}_{col}.pdf';fig.savefig(D/'figures'/name,bbox_inches='tight',metadata={'CreationDate':None});plt.close(fig);mapping.append({'figure':name,'source':'metrics/ALL900_EPOCH_METRICS.csv','definition':'measured epochs only, no smoothing; IM full-fit BCE is not validation'})
 assert len(mapping) == 10
 export_figure_sources(mapping, absolute, diff, ci, seed, curves)
 csvout(D/'figures/FIGURE_TABLE_SOURCE_MAP.csv',mapping)

 put(D/'reports/render_completed.json',{'status':'PASS','figure_count':len(mapping),'source_csv_count':len(mapping)})

if __name__ == '__main__':
    main()
