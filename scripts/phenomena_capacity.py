#!/usr/bin/env python3
"""Lane-drop detector flows around observed upstream breakdown."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path(__file__).resolve().parents[1]/'results/phenomena'
rows=[]
fig,ax=plt.subplots(figsize=(9,4))
for path in sorted(out.glob('capacity_drop*_edges.csv')):
    seed=path.stem.split('_seed')[-1].split('_')[0] if '_seed' in path.stem else '42'
    for sim,g in pd.read_csv(path).groupby('simulator'):
        upstream=g[g.edge=='e0'].set_index('begin_s')
        downstream=g[g.edge=='e1'].set_index('begin_s')
        speed=upstream.distance_m/upstream.vehicle_seconds
        congested=(speed<15)&(upstream.vehicle_seconds>0)
        onset=congested.rolling(3).sum().eq(3)
        q=downstream.entered*120
        ax.plot(q.index,q,color={'SUMO':'#eb6834','cars':'#2a78d6'}[sim],lw=.7,label=f'{sim}, seed {seed}')
        if onset.any():
            t=onset[onset].index[0]-60
            pre=q[(q.index>=t-300)&(q.index<t)].mean()
            post=q[(q.index>=t+60)&(q.index<t+660)].mean()
            drop=100*(pre-post)/pre if pre>0 else float('nan')
        else:t=pre=post=drop=float('nan')
        rows.append([sim,seed,t,pre,post,drop])
ax.set(title='Lane-drop discharge at downstream edge entry',xlabel='Time (s)',ylabel='Detector flow (veh/h)');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(out/'capacity_drop_detector.png',dpi=140)
pd.DataFrame(rows,columns=['simulator','seed','breakdown_s','pre_veh_h','post_veh_h','drop_percent']).to_csv(out/'capacity_drop_detector.csv',index=False,float_format='%.3f')
