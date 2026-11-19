import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('source_dir', type=Path)
parser.add_argument('output_dir', type=Path)
args=parser.parse_args()
f=args.source_dir
output_dir=args.output_dir
output_dir.mkdir(exist_ok=True, parents=True)
arms=['A','W_two','L','W_two_perm','L_perm','L_const']
names=['Unweighted','Two-sided','Downweight','Two-sided shuffle','Downweight shuffle','Mean downweight']
contrasts=['W_two-A','L-A','W_two-W_two_perm','L-L_perm','L-L_const']
cnames=['Two-sided − unweighted','Downweight − unweighted','Two-sided − shuffle','Downweight − shuffle','Downweight − mean']
seeds=['42','123','456']
col=['#00788b','#b64e19','#605396']
markers=['o','s','^']
plt.rcParams.update({'font.size':9,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'xtick.labelsize':8,'ytick.labelsize':8})
for absolute,fn in [(True,'ABSOLUTE_AP'),(False,'ALL_FIVE_PAIRED_CONTRASTS_AP')]:
 with (f/(fn+'_SOURCE.csv')).open() as h:data=list(csv.DictReader(h))
 fig,ax=plt.subplots(2,2,figsize=(8,5.9),sharex='row',sharey='row')
 fig.subplots_adjust(left=.242,right=.98,bottom=.115,top=.825,wspace=.13,hspace=.52)
 fig.text(.03,.956,'Average precision' if absolute else 'Paired difference in average precision',weight='bold',fontsize=14)
 handles=[Line2D([],[],ls='',marker=m,color=c,ms=4,label='Seed '+s) for m,c,s in zip(markers,col,seeds)]
 handles.append(Line2D([],[],color='#20262a',lw=0 if absolute else 1.4,marker='D',ms=4,label='Mean' if absolute else 'Mean and conditional 95% interval'))
 if absolute:handles.append(Line2D([],[],color='#686868',ls='--',lw=1,label='Positive fraction'))
 fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.025,.937),frameon=False,ncol=5,columnspacing=1.4,fontsize=8)
 for i,cohort in enumerate(['IMPROVE','Neo']):
  for j,stage in enumerate(['EL20','IM30']):
   panel=ax[i,j]
   cells=[r for r in data if r['cohort']==cohort and r['stage']==stage]
   labels=names if absolute else cnames
   for k,key in enumerate(arms if absolute else contrasts):
    rs=[r for r in cells if r['arm' if absolute else 'contrast']==key]
    assert len(rs)==(1 if absolute else 3)
    if not absolute:panel.plot([float(rs[0][v]) for v in ('lower_95','upper_95')],[k,k],color='#20262a',lw=1.3,zorder=2)
    for s,m,c,offset in zip(seeds,markers,col,[-.22,.12,.22]):
     val=float(rs[0]['AP_seed'+s]) if absolute else float(next(r['seed_delta'] for r in rs if r['seed']==s))
     panel.plot(val,k+offset,marker=m,color=c,ms=3.7,ls='',zorder=3)
    panel.plot(float(rs[0]['AP_mean' if absolute else 'mean_delta']),k,marker='D',color='#20262a',ms=3.8,ls='',zorder=4)
   panel.axvline(float(cells[0]['prevalence']) if absolute else 0,ls='--',lw=.8,color='#666')
   panel.set_ylim(len(labels)-.55,-.5);panel.set_yticks(range(len(labels)),labels)
   panel.set_title(f'{cohort}  ·  {stage}',loc='left',fontsize=10,fontweight='bold')
   panel.xaxis.set_major_locator(MaxNLocator(5));panel.xaxis.set_major_formatter(FormatStrFormatter('%.3f' if i==0 else '%.2f'))
   panel.grid(axis='x',color='#dddddd',lw=.5);panel.tick_params(axis='y',length=0,pad=5)
   panel.set_xlabel('AP' if absolute else 'ΔAP')
 fig.savefig(output_dir/(fn+'.pdf'));plt.close(fig)
