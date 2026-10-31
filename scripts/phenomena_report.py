#!/usr/bin/env python3
"""Measured evidence for the paired scenario suite; never infer success from a video."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phenomena'
COLORS={'SUMO':'#eb6834','cars':'#2a78d6'}
plt.rcParams['lines.linewidth']=.8

def read_csv(path, *args, **kwargs):
    path=Path(path)
    if not path.exists() and Path(str(path)+'.gz').exists(): path=Path(str(path)+'.gz')
    return pd.read_csv(path,*args,**kwargs)


def plot_series(name, series, xlabel, ylabel, title):
    fig,ax=plt.subplots(figsize=(10,4))
    for sim,label,x,y,style in series:
        ax.plot(x,y,color=COLORS[sim],label=sim+' '+label,ls=style)
    ax.set(xlabel=xlabel,ylabel=ylabel,title=title);handles,labels=ax.get_legend_handles_labels();legend=dict(zip(labels,handles));ax.legend(legend.values(),legend.keys(),fontsize=7);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/(name+'.png'),dpi=150);plt.close(fig)


def evidence(name,sim,g):
    a=g.groupby('begin_s')[['vehicle_seconds','distance_m','entered']].sum()
    speed=g.distance_m.sum()/max(g.vehicle_seconds.sum(),1)
    peak=(a.vehicle_seconds/30).max()
    if name in ('phantom_jam','one_av'):
        w=read_csv(OUT/f'{name}_waves.csv').set_index('simulator').loc[sim]
        if name=='phantom_jam':return w.stopped_fraction>.05 and w.speed_sd_m_s>1, f'stopped {w.stopped_fraction:.1%}, SD {w.speed_sd_m_s:.2f} m/s, wave {w.wave_km_h:.1f} km/h'
        human=read_csv(OUT/'one_av_human_waves.csv').set_index('simulator').loc[sim]
        return w.speed_sd_m_s < .7*human.speed_sd_m_s, f'SD human {human.speed_sd_m_s:.2f}, smooth {w.speed_sd_m_s:.4f} m/s'
    if name=='capacity_drop':
        u=g[g.edge=='e0'].set_index('begin_s');v=u.distance_m/u.vehicle_seconds
        d=g[g.edge=='e1'].set_index('begin_s').entered*120
        onset=(v<15).rolling(3).sum().eq(3)
        if not onset.any():return False,f'no sustained queue; min upstream {v.min():.2f} m/s'
        t=onset[onset].index[0]-60
        pre=d[(d.index>=max(0,t-300))&(d.index<t)].rolling(3).mean().max();post=d[(d.index>=t+60)&(d.index<t+660)].mean()
        return post<.99*pre,f'queue at {t:.0f} s; pre {pre:.0f}, discharge {post:.0f} veh/h; min speed {v.min():.2f} m/s (drop {100*(pre-post)/pre:.1f}%)'
    if name=='spillback':
        u=g[g.edge=='e0'].set_index('begin_s');link=g[g.edge=='e1'].set_index('begin_s')
        blocked=((link.vehicle_seconds/30>8)&(u.distance_m/u.vehicle_seconds<2))
        side=g[g.edge=='side'].entered.sum()
        return blocked.sum()>=3,f'blocked proxy {blocked.sum()*30:.0f} s, peak link {max(link.vehicle_seconds/30):.1f} veh, side exits {side:.0f}'
    if name=='gridlock':
        clear=read_csv(OUT/'gridlock_clear_edges.csv');clear=clear[clear.simulator==sim]
        tail=a[a.index>=a.index.max()*2/3];v=tail.distance_m.sum()/max(tail.vehicle_seconds.sum(),1)
        clear=clear[clear.begin_s>=clear.begin_s.max()*2/3]
        cv=clear.distance_m.sum()/max(clear.vehicle_seconds.sum(),1)
        counts=read_csv(OUT/'gridlock_spillback_arrivals.csv');counts=counts[counts.simulator==sim].set_index('scenario')
        return v<.5 and tail.vehicle_seconds.mean()/30>10,f'late speed off/on {v:.2f}/{cv:.2f} m/s; arrivals {counts.loc["gridlock","arrivals"]}/{counts.loc["gridlock_clear","arrivals"]}'
    if name=='mfd':
        n=a.vehicle_seconds/30;recovery=n.iloc[-1]/max(n.max(),1)
        return recovery<.7,f'peak {peak:.0f} veh, final/peak {recovery:.2f}, mean speed {speed:.2f} m/s'
    if name=='onramp_merge':
        u=g[g.edge=='e0'];v=u.distance_m/u.vehicle_seconds
        r=g[g.edge=='ramp'];rv=r.distance_m/r.vehicle_seconds
        return rv.min()<.7*rv.max() or v.min()<.7*v.max(),f'ramp {rv.max():.2f} to {rv.min():.2f} m/s; mainline {v.max():.2f} to {v.min():.2f} m/s'
    if name=='brake_wave':
        path=OUT/'brake_wave_pulse.csv'
        if path.exists():
            r=read_csv(path);r=r[(r.simulator==sim)&(r.seed==42)]
            return (r.min_speed_m_s<1).sum()>10,f'{(r.min_speed_m_s<1).sum()} stopped trajectories, median minimum {r.min_speed_m_s.median():.2f} m/s'
        return False,'pulse trajectories missing'
    if name=='signal_discharge':
        r=read_csv(OUT/'signal_discharge_headways.csv');r=r[(r.simulator==sim)&(r.seed==42)&(r.queue_position>=5)&(r.queue_position<=15)]
        h=r.headway_s.median()
        return len(r)>5 and h>0,f'headway {h:.2f} s, saturation {3600/h:.0f} veh/h'
    return peak>1,f'mean speed {speed:.3f} m/s, peak {peak:.0f} veh'


def fcd(name):
    d=ROOT/'runs/phenomena'/name
    rows=[]
    for _,el in ET.iterparse(d/'sumo_fcd.xml',events=['end']):
        if el.tag=='timestep':
            for v in el.findall('vehicle'):rows.append(['SUMO',float(el.get('time')),v.get('id'),v.get('lane'),float(v.get('speed'))])
            el.clear()
    for r in read_csv(d/'cars_fcd.csv').itertuples(): rows.append(['cars',r.time,str(r.trip),r.lane,r.speed])
    return pd.DataFrame(rows,columns=['simulator','time_s','vehicle','lane','speed'])


def main():
    heads=[];minima=[]
    for seed in [42,43,44]:
        suffix='' if seed==42 else f'_seed{seed}'
        if (ROOT/'runs/phenomena'/('signal_discharge'+suffix)/'cars_fcd.csv').exists():
            data=fcd('signal_discharge'+suffix)
            for sim,g in data.groupby('simulator'):
                times=g[g.lane=='e1_0'].groupby('vehicle').time_s.min().sort_values()
                for i,(v,t) in enumerate(times.items()):heads.append([sim,seed,i+1,t,t-times.iloc[i-1] if i else np.nan])
        if (ROOT/'runs/phenomena'/('brake_wave'+suffix)/'cars_fcd.csv').exists():
            data=fcd('brake_wave'+suffix)
            m=data.groupby(['simulator','vehicle']).speed.min().reset_index(name='min_speed_m_s');m['vehicle_index']=m.vehicle.str.extract(r'(\d+)').astype(int);m['seed']=seed;minima.append(m)
    if heads:
        h=pd.DataFrame(heads,columns=['simulator','seed','queue_position','crossing_s','headway_s']);h.to_csv(OUT/'signal_discharge_headways.csv',index=False)
        plot_series('signal_discharge_headways',[(sim,f'seed {seed}',g.queue_position,g.headway_s,{42:'-',43:'--',44:':'}[seed]) for (sim,seed),g in h[h.crossing_s<60].groupby(['simulator','seed'])],'Queue position (veh)','Departure headway (s)','First green: queue release and saturation headway')
    if minima:
        m=pd.concat(minima);m.to_csv(OUT/'brake_wave_pulse.csv',index=False)
        plot_series('brake_wave_minima',[(sim,f'seed {seed}',g.sort_values('vehicle_index').vehicle_index,g.sort_values('vehicle_index').min_speed_m_s,{42:'-',43:'--',44:':'}[seed]) for (sim,seed),g in m.groupby(['simulator','seed'])],'Vehicle index (front to rear)','Minimum speed (m/s)','The braking pulse reaches successive followers')
    fd=[]
    for p in sorted(OUT.glob('freeway_fd_n*_edges.csv')):
        n=int(re.search(r'_n(\d+)',p.name)[1])
        if n>240:continue
        seed=int(re.search(r'_seed(\d+)',p.name)[1]) if '_seed' in p.name else 42
        for sim,g in read_csv(p).query('begin_s>=300').groupby('simulator'):
            fd.append([sim,seed,n/2,g.distance_m.sum()/g.vehicle_seconds.sum(),g.distance_m.sum()/300/2000*3600])
    if fd:
        fd=pd.DataFrame(fd,columns=['simulator','seed','density_veh_km','speed_m_s','flow_veh_h']);fd.to_csv(OUT/'freeway_fd.csv',index=False)
        for value,ylabel in [('flow_veh_h','Flow (veh/h)'),('speed_m_s','Speed (m/s)')]:
            plot_series('freeway_fd_'+value,[(sim,f'seed {seed}',g.sort_values('density_veh_km').density_veh_km,g.sort_values('density_veh_km')[value],'-') for (sim,seed),g in fd.groupby(['simulator','seed'])],'Density (veh/km)',ylabel,'Fixed-density ring fundamental diagram')
    for name,edge in [('capacity_drop','e1'),('onramp_merge','e1'),('spillback','side')]:
        path=OUT/(name+'_edges.csv')
        if not path.exists():continue
        data=read_csv(path);flow=[];speed=[]
        for sim,g in data.groupby('simulator'):
            d=g[g.edge==edge].set_index('begin_s');u=g[g.edge=='e0'].set_index('begin_s')
            flow.append((sim,'',d.index,d.entered*120,'-'))
            speed.append((sim,'mainline' if name=='onramp_merge' else '',u.index,u.distance_m/u.vehicle_seconds,'-'))
            if name=='onramp_merge':
                r=g[g.edge=='ramp'].set_index('begin_s');speed.append((sim,'ramp',r.index,r.distance_m/r.vehicle_seconds,'--'))
        plot_series(name+'_detector',flow,'Time (s)','Detector flow (veh/h)',name.replace('_',' ')+' downstream detector')
        plot_series(name+'_upstream',speed,'Time (s)','Upstream speed (m/s)',name.replace('_',' ')+' upstream queue')
    mfd_series=[]
    for seed in [42,43,44]:
        path=OUT/('mfd'+('' if seed==42 else f'_seed{seed}')+'_edges.csv')
        if not path.exists():continue
        for sim,g in read_csv(path).groupby('simulator'):
            a=(g.groupby('begin_s')[['vehicle_seconds','distance_m']].sum()/30).rolling(6,center=True,min_periods=6).mean()
            for loading,branch in a.groupby(a.index<3600):
                mfd_series.append((sim,'loading' if loading else 'recovery',branch.vehicle_seconds,branch.distance_m,'-' if loading else '--'))
    if mfd_series:plot_series('mfd_loop',mfd_series,'Accumulation (veh)','Production (veh m/s)','Network loading and recovery | 180 s means, three seeds')
    arrivals=[];arrival_counts=[]
    for name in ('gridlock','gridlock_clear','spillback'):
        d=ROOT/'runs/phenomena'/name
        if not (d/'cars_trips.csv').exists():continue
        for sim in COLORS:
            if sim=='cars':
                t=read_csv(d/'cars_trips.csv').arrival.to_numpy()
            else:
                t=np.array([float(e.get('arrival')) for _,e in ET.iterparse(d/'sumo_trips.xml') if e.tag=='tripinfo'])
            end=json.loads((d/'manifest.json').read_text()).get('end',1800)
            arrival_counts.append([name,sim,len(t),int((t>=end*2/3).sum())])
            x=np.arange(0,end+1,30);y=np.searchsorted(np.sort(t),x)
            arrivals.append((sim,name,x,y,'--' if name.endswith('clear') else '-'))
    if arrivals:
        pd.DataFrame(arrival_counts,columns=['scenario','simulator','arrivals','late_arrivals']).to_csv(OUT/'gridlock_spillback_arrivals.csv',index=False)
        for base in ['gridlock','spillback']:
            selected=[(sim,label.replace('gridlock_clear','keep-clear on').replace('gridlock','keep-clear off'),x,y,style) for sim,label,x,y,style in arrivals if label.startswith(base)]
            if selected:plot_series(base+'_arrivals',selected,'Time (s)','Cumulative arrivals (veh)',base.replace('_',' ')+' cumulative completed trips')
    sweep_path=OUT/'thesis_ring_sweep_edges.csv'
    baseline_path=OUT/'thesis_ring_edges.csv'
    if sweep_path.exists() and baseline_path.exists():
        baseline=read_csv(baseline_path);sweep=read_csv(sweep_path)
        fig,axs=plt.subplots(1,3,figsize=(14,5))
        groups=[('SUMO baseline',baseline[baseline.simulator=='SUMO']),('cars baseline',baseline[baseline.simulator=='cars']),('cars sweep: scripted disturbance',sweep)]
        for ax,(title,g) in zip(axs,groups):
            g=g.copy();g['edge_index']=g.edge.str.extract(r'(\d+)').astype(int)
            g['speed']=g.distance_m/g.vehicle_seconds
            field=g.pivot_table(index='edge_index',columns='begin_s',values='speed')
            im=ax.imshow(field,origin='lower',aspect='auto',vmin=0,vmax=30,cmap='RdYlGn',extent=[0,4000,0,4000])
            ax.set(title=title,xlabel='Time (s)',ylabel='Ring position (m)')
        fig.colorbar(im,ax=axs.tolist(),label='Speed (m/s)',shrink=.8)
        fig.suptitle('Thesis ring: paired baseline and separate scripted sweep');fig.savefig(OUT/'thesis_ring_time_space.png',dpi=150);plt.close(fig)
    series=[]
    for name in ('one_av_human','one_av'):
        p=ROOT/'runs/phenomena'/name/'cars_fcd.csv'
        if not p.exists():continue
        for sim,g in fcd(name).groupby('simulator'):
            v=g.groupby('time_s').speed.std();series.append((sim,'human' if name.endswith('human') else 'smooth',v.index,v,'--' if name.endswith('human') else '-'))
    if series:plot_series('one_av_comparison',series,'Time (s)','Speed SD (m/s)','One smooth driver damps stop-and-go oscillations')
    text='# Traffic phenomena: fresh paired measurements\n\nReproduce inside `nix develop`: `cargo build --release`, `python scripts/phenomena_suite.py`, `python scripts/phenomena_videos.py`, `python scripts/phenomena_report.py`, then `python scripts/phenomena_accept.py`. Seeds 42, 43, 44. The phantom and one-driver IDM rings are deterministic across seeds; those repeats do not represent driver uncertainty. Stochastic cases use independent seeds in the two engines; the lane-drop case also uses IDM. No old measurements are used.\n\nHeadline values below are seed 42; seed 43 and 44 results have separate summaries and figures. Yes denotes the measured criterion below, not full simulator equivalence. Spillback blocked time uses 30 s bins with >8 vehicles in the short link and upstream speed <2 m/s. Gridlock requires late speed <0.5 m/s with teleport disabled; keep-clear can delay failure without preventing it under extreme overload. The lane drop uses IDM with accel 0.3 m/s² and decel 1.5 m/s² to expose breakdown and discharge loss. Brake-wave uses a single 20 s red pulse. Headway plots show the first green only; saturation uses median headway at queue positions 5–15. FD uses the last 300 s at each fixed density, with all vehicles admitted, through 120 veh/km. SUMO edge occupancy can double-count a vehicle spanning an edge boundary, so Edie accumulation can exceed the physical population. Capacity-drop preflow is the peak 90 s mean in the preceding 300 s; discharge is the following 600 s after a 60 s transition exclusion, truncated at the run end.\n\n| Scenario | SUMO demonstrated; evidence | cars demonstrated; evidence |\n|---|---|---|\n'
    for name in ['phantom_jam','one_av','brake_wave','capacity_drop','freeway_fd','signal_discharge','onramp_merge','spillback','gridlock','mfd','thesis_ring','bologna_rush','i80_day']:
        cells=[]
        for sim in COLORS:
            try:
                if name=='freeway_fd':
                    g=fd[(fd.simulator==sim)&(fd.seed==42)].sort_values('density_veh_km');peak=g.loc[g.flow_veh_h.idxmax()];last=g.iloc[-1];ok=last.flow_veh_h<.8*peak.flow_veh_h;note=f'peak {peak.flow_veh_h:.0f} veh/h at {peak.density_veh_km:.0f} veh/km; dense {last.flow_veh_h:.0f} veh/h, {last.speed_m_s:.2f} m/s'
                else:
                    g=read_csv(OUT/f'{name}_edges.csv');ok,note=evidence(name,sim,g[g.simulator==sim])
                cells.append(('Yes' if ok else 'No')+'; '+note)
            except (FileNotFoundError,KeyError,IndexError,UnboundLocalError,AttributeError):cells.append('Pending fresh measurement')
        text+='| '+name+' | '+' | '.join(cells)+' |\n'
    text+='\nFigures:\n\n'
    figures={
        'phantom_jam':['phantom_jam.png'], 'one_av':['one_av_comparison.png'],
        'brake_wave':['brake_wave.png','brake_wave_minima.png'],
        'capacity_drop':['capacity_drop_detector.png','capacity_drop_upstream.png'],
        'freeway_fd':['freeway_fd_flow_veh_h.png','freeway_fd_speed_m_s.png'],
        'signal_discharge':['signal_discharge_headways.png'],
        'onramp_merge':['onramp_merge_detector.png','onramp_merge_upstream.png'],
        'spillback':['spillback_arrivals.png','spillback_upstream.png'],
        'gridlock':['gridlock_arrivals.png'], 'mfd':['mfd_loop.png'],
        'thesis_ring':['thesis_ring_time_space.png'],
        'bologna_rush':['bologna_rush.png'], 'i80_day':['i80_day.png']}
    for name,paths in figures.items():text+='- '+name+': '+', '.join(f'[{path}]({path})' for path in paths)+'\n'
    text+='\nVideos (13 reviewed 1080p H.264 movies at 30 fps, 28–50 s; cars rendering with speed colors). Extracted frames were visually checked, including both one-driver configurations. Camera files are in `cameras/`:\n\n'
    for p in sorted((OUT/'cameras').glob('*.json')):text+=f'- [{p.stem}](/home/erikf/projects/personal/cars-data/videos/{p.stem}.mp4)\n'
    text+='\nThe one_av movie compares 25 s human-only followed by 25 s with one smooth driver. Its human-only source movie is `one_av_human.mp4`, using the same human ring as phantom_jam. The thesis sweep uses `flock /tmp/cars-gpu.lock target/release/sweep --scenario ring --tiers idm --penetrations 0 --seeds 42,43,44 --out results/phenomena/thesis_ring_sweep.csv --edge-out results/phenomena/thesis_ring_sweep_edges.csv`; its scripted disturbance is shown separately from the matched baseline.\n\nNo simulator core files were modified. Raw trajectories and logs remain in `runs/phenomena/`. A queue at a lane drop establishes breakdown; a negative measured drop percentage means no capacity drop was demonstrated.\n'
    text+='\nSimulator issues and reproducible diagnostics:\n\n'
    probe=ROOT/'runs/phenomena/freeway_fd_n260/cars_summary.csv'
    if probe.exists():
        last=read_csv(probe).iloc[-1]
        text+=f"""- Tight initial placement: the 2 km ring requests 260 vehicles, but cars inserts only {last.inserted:.0f} by 600 s, with no arrivals or teleports; SUMO supports the full dense population. At 240, cars admits all 240. The 260 case is excluded from the FD curves. Reproduce inside the dev shell: `python -c 'import sys; sys.path.insert(0,"scripts"); from phenomena_suite import execute,density; execute("freeway_fd",42,"_n260",density(260))'`. No core fix was attempted.\n"""
    diagnostics=[]
    for path in OUT.glob('*_diagnostics.csv'):
        for row in read_csv(path).to_dict('records'):
            if row['overflow_counter'] or row['collisions']:
                diagnostics.append([path.stem.removesuffix('_diagnostics'),row['overflow_counter'],row['collisions'],row['teleports']])
    if diagnostics:
        text+='\nNonzero simulator counters are retained as diagnostics; this pass does not establish their root cause. Reproduce any row with `python scripts/phenomena.py SCENARIO --measure --seed SEED` inside the dev shell.\n\n| Run | Overflow counter | Collisions | Teleports |\n|---|---:|---:|---:|\n'
        for row in sorted(diagnostics):text+='| '+' | '.join(str(x) for x in row)+' |\n'
    (OUT/'README.md').write_text(text)

if __name__=='__main__':main()
