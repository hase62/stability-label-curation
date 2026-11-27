"""Final figures/reports/package from completed new experiment only. No training."""
from common import D, commands, csvout, put, read, validate_seal
from plot_manuscript import read_csv, render_curve, render_metric


def tab(name):
    return read_csv(D / "metrics", name)

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
 for metric in ('AP', 'AUROC', 'PPV10', 'PPV20'):
  mapping.append({'figure':f'ABSOLUTE_{metric}.pdf','source':'metrics/MAIN_ABSOLUTE_METRIC_MEANS.csv','definition':'all six arms, all seeds, arithmetic mean metric; not score ensemble'})
 for metric in ('AP', 'AUROC'):
  mapping.append({'figure':f'ALL_FIVE_PAIRED_CONTRASTS_{metric}.pdf','source':'metrics/MAIN_20_MEAN_CONTRASTS.csv; MAIN_60_SEED_CONTRASTS.csv; MAIN_CONDITIONAL_CI.csv','definition':'seed points / mean paired delta / unadjusted conditional component bootstrap95 interval; all five contrasts'})
 curves=tab('ALL900_EPOCH_METRICS.csv')
 for stage, metric in (('EL','train_update_BCE'), ('IM','train_update_BCE'), ('EL','validation_BCE'), ('EL','validation_AP')):
  mapping.append({'figure':f'CURVE_{stage}_{metric}.pdf','source':'metrics/ALL900_EPOCH_METRICS.csv','definition':'measured epochs only, no smoothing; IM full-fit BCE is not validation'})
 export_figure_sources(mapping, absolute, diff, ci, seed, curves)
 for entry in mapping:
  path = D / 'figures' / entry['figure']
  name = path.stem
  if name.startswith('CURVE_'):
   _, stage, metric = name.split('_', 2)
   render_curve(read_csv(D / 'figures', entry['source'].split('/')[-1]), stage, metric, path)
  else:
   metric = name.rsplit('_', 1)[1]
   source = 'ABSOLUTE_AP_SOURCE.csv' if name.startswith('ABSOLUTE_') else entry['source'].split('/')[-1]
   render_metric(read_csv(D / 'figures', source), metric, absolute=name.startswith('ABSOLUTE_'), path=path)
 csvout(D/'figures/FIGURE_TABLE_SOURCE_MAP.csv',mapping)

 put(D/'reports/render_completed.json',{'status':'PASS','figure_count':len(mapping),'source_csv_count':len(mapping)})

if __name__ == '__main__':
    main()
