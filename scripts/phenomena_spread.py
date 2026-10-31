#!/usr/bin/env python3
"""Plot independent run traces, preserving engine colors and seed identities."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parents[1]/'results/phenomena'
COLORS={'SUMO':'#eb6834','cars':'#2a78d6'}

def main():
    summaries=[]
    for base in sorted(OUT.glob('*_edges.csv')):
        name=base.stem.removesuffix('_edges')
        if '_seed' in name: continue
        paths=[base,*sorted(OUT.glob(name+'_seed*_edges.csv'))]
        fig,axs=plt.subplots(1,3,figsize=(14,4))
        for path in paths:
            seed=path.stem.split('_seed')[-1].split('_')[0] if '_seed' in path.stem else '42'
            data=pd.read_csv(path)
            for sim,g in data.groupby('simulator'):
                a=g.groupby('begin_s')[['vehicle_seconds','distance_m']].sum()/30
                a.columns=['N','P']
                label=f'{sim}, seed {seed}'
                kw=dict(color=COLORS[sim],lw=.7,alpha=.7,label=label)
                axs[0].plot(a.index,a.N,**kw)
                axs[1].plot(a.index,a.P,**kw)
                midpoint=a.index.max()/2
                for loading,branch in a.groupby(a.index<=midpoint):
                    axs[2].plot(branch.N,branch.P,color=COLORS[sim],lw=.7,alpha=.7,
                                ls='-' if loading else '--',label=label+(' loading' if loading else ' recovery'))
                summaries.append([name,sim,seed,a.N.max(),a.P.max()])
        for ax,title,x,y in zip(axs,['Accumulation across independent runs','Production across independent runs','Loading (solid) and recovery (dashed)'],['Time (s)','Time (s)','Accumulation (veh)'],['Accumulation (veh)','Production (veh m/s)','Production (veh m/s)']):
            ax.set(title=title,xlabel=x,ylabel=y);ax.grid(alpha=.2);ax.legend(fontsize=5)
        fig.suptitle(name);fig.tight_layout();fig.savefig(OUT/f'{name}_spread.png',dpi=140);plt.close(fig)
    pd.DataFrame(summaries,columns=['scenario','simulator','seed','peak_accumulation_veh','peak_production_veh_m_s']).to_csv(OUT/'run_summary.csv',index=False,float_format='%.3f')

if __name__=='__main__': main()
