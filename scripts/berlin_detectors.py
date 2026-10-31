#!/usr/bin/env python3
"""Reproducible Berlin lane-count comparison; run with python3 -I."""
import argparse
import json
import tarfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from lxml import etree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.spatial import cKDTree
from pyproj import Transformer

ROOT = Path('/home/erikf/projects/personal/cars-data')
COLORS = {'real': '#1baf7a', 'SUMO': '#eb6834', 'cars': '#2a78d6'}
DIRECTIONS = dict(zip(['Nord','Nordost','Ost','Südost','Süd','Südwest','West','Nordwest'], range(0,360,45)))


def metadata(path):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row', ns):
            rows.append({c.get('r').rstrip('0123456789'): strings[int(c.find('m:v',ns).text)] if c.get('t') == 's' else c.findtext('m:v',default='',namespaces=ns) for c in row})
    d = pd.DataFrame(rows[1:]).rename(columns={'A':'site','B':'detector','I':'direction','L':'lon','M':'lat'})
    return d


def network(path):
    edges = []
    location = None
    for _, e in etree.iterparse(str(path), events=('end',), tag=('location','edge'), resolve_entities=False, no_network=True):
        if e.tag == 'location':
            location = dict(e.attrib)
        elif not e.get('id','').startswith(':'):
            lanes = [l for l in e.findall('lane') if 'passenger' not in l.get('disallow','').split() and (not l.get('allow') or 'passenger' in l.get('allow').split() or 'all' in l.get('allow').split())]
            if lanes:
                shape = np.array([list(map(float,p.split(','))) for p in lanes[0].get('shape').split()])[:,:2]
                edges.append((e.get('id'), len(lanes), shape))
        e.clear()
        while e.getprevious() is not None:
            del e.getparent()[0]
    return location, edges


def mapping(a):
    meta = metadata(a.metadata)
    loc, edges = network(a.net)
    transform = Transformer.from_crs('EPSG:4326', loc['projParameter'], always_xy=True)
    offset = np.array(list(map(float,loc['netOffset'].split(','))))
    starts=[]; ends=[]; ids=[]
    for i,(_,_,shape) in enumerate(edges):
        for x,y in zip(shape[:-1],shape[1:]):
            n=max(1,int(np.ceil(np.linalg.norm(y-x)/20)))
            for j in range(n):
                starts.append(x+(y-x)*j/n); ends.append(x+(y-x)*(j+1)/n); ids.append(i)
    starts=np.array(starts); ends=np.array(ends); delta=ends-starts; tree=cKDTree((starts+ends)/2)
    rows=[]
    for site,g in meta.groupby('site'):
        r=g.iloc[0]; xy=np.array(transform.transform(float(r.lon),float(r.lat)))+offset
        candidates={}
        for j in tree.query_ball_point(xy, a.max_distance+15):
            v=delta[j]; point=starts[j]+v*np.clip(np.dot(xy-starts[j],v)/max(np.dot(v,v),1e-12),0,1)
            dist=np.linalg.norm(point-xy); bearing=np.degrees(np.arctan2(v[0],v[1]))%360
            angle=abs((bearing-DIRECTIONS[r.direction]+180)%360-180)
            edge,n,_=edges[ids[j]]; mismatch=abs(n-len(g))
            score=dist+angle*.5+mismatch*20
            if edge not in candidates or score<candidates[edge][0]: candidates[edge]=(score,dist,angle,mismatch,n)
        ranked=sorted(candidates.items(),key=lambda x:x[1][0]); edge,best=ranked[0] if ranked else ('',(np.inf,)*5)
        score,dist,angle,mismatch,n=best
        margin=ranked[1][1][0]-score if len(ranked)>1 else np.inf
        reason='accepted' if dist<=a.max_distance and angle<=45 and mismatch==0 and margin>=10 else 'distance/bearing/lanes/ambiguity'
        rows.append(dict(site=site,edge=edge,x=xy[0],y=xy[1],lanes=len(g),edge_lanes=n,distance_m=dist,bearing_error_deg=angle,score_margin=margin,quality=reason))
    out=pd.DataFrame(rows)
    dup=out.quality.eq('accepted') & out.loc[out.quality.eq('accepted'),'edge'].duplicated(keep=False).reindex(out.index,fill_value=False)
    out.loc[dup,'quality']='duplicate_edge'
    out.to_csv(a.out/'detector_map.csv',index=False,float_format='%.3f')
    print(out.quality.value_counts().to_string())


def profile(a):
    meta=metadata(a.metadata); lookup=meta.set_index('detector').site.to_dict(); frames=[]
    with tarfile.open(a.archive) as tar:
        for member in tar:
            if not member.isfile() or Path(member.name).stem not in lookup: continue
            d=pd.read_csv(tar.extractfile(member),sep=';'); d=d.rename(columns={d.columns[0]:'date',d.columns[1]:'hour'})
            dates=pd.to_datetime(d.date)
            # September 2024: Berlin summer break ended August 30; autumn starts October 21.
            d=d[(dates.dt.dayofweek<5) & (d['Vollständigkeit']>=75) & (d.hist_cor>=a.hist_cor) & (d.qkfz>=0)].copy()
            d['site']=lookup[Path(member.name).stem]; d['detector']=Path(member.name).stem
            frames.append(d[['site','detector','date','hour','qkfz']])
    d=pd.concat(frames); daily=d.groupby(['site','date','hour']).agg(real=('qkfz','sum'),n=('detector','nunique')).reset_index()
    counts=meta.groupby('site').size(); daily=daily[daily.n==daily.site.map(counts)]
    p=daily.groupby(['site','hour']).agg(real=('real','mean'),days=('real','size'),std=('real','std')).reset_index()
    p=p[p.days>=5]; m=pd.read_csv(a.out/'detector_map.csv'); p=p.merge(m[m.quality=='accepted'][['site','edge']],on='site')
    p.to_csv(a.out/'detector_profile.csv',index=False,float_format='%.3f')
    (a.out/'profile_method.json').write_text(json.dumps({'hist_cor':a.hist_cor,'archive':str(a.archive),'min_days':5,'rows':len(p)},indent=2))
    print(f'{len(p)} site-hours, {p.site.nunique()} sites')


def sumo_counts(path, edges):
    rows=[]; covered=[]; current={}
    try:
        for event,e in etree.iterparse(str(path),events=('start','end'),tag=('interval','edge'),resolve_entities=False,no_network=True):
            if e.tag=='interval' and event=='start':
                begin=float(e.get('begin')); end=float(e.get('end')); current={}
            elif e.tag=='edge' and event=='end':
                if e.get('id') in edges: current[e.get('id')]=float(e.get('entered','0'))
                e.clear()
                while e.getprevious() is not None: del e.getparent()[0]
            elif e.tag=='interval' and event=='end':
                if begin%3600 in (0,900,1800,2700) and end-begin==900:
                    h=int(begin//3600); covered.append((h,int(begin%3600)))
                    rows.extend((h,edge,current.get(edge,0)) for edge in edges)
                e.clear()
    except etree.XMLSyntaxError as ex:
        if 'Premature end' not in str(ex): raise
    complete={h for h in range(24) if {q for hh,q in covered if hh==h}=={0,900,1800,2700}}
    return pd.DataFrame(rows,columns=['hour','edge','SUMO']).groupby(['hour','edge'],as_index=False).sum().query('hour in @complete')


def geh(s,o):
    return np.sqrt(np.divide(2*(s-o)**2,s+o,out=np.zeros_like(s,dtype=float),where=(s+o)>0))


def compare(a):
    p=pd.read_csv(a.out/'detector_profile.csv'); m=pd.read_csv(a.out/'detector_map.csv'); edges=set(p.edge); chunks=[]; hours=set()
    for c in pd.read_csv(a.cars,chunksize=100000):
        hours.update((c.begin//3600).astype(int)); c=c[c.edge.isin(edges)].copy(); c['hour']=(c.begin//3600).astype(int); chunks.append(c[['hour','edge','entered']])
    cars=pd.concat(chunks).groupby(['hour','edge']).entered.sum()
    d=p.copy(); d['cars']=[cars.get((r.hour,r.edge),0) if r.hour in hours else np.nan for r in d.itertuples()]
    sims=['cars']
    if a.sumo:
        d=d.merge(sumo_counts(a.sumo,edges),on=['hour','edge'],how='left'); sims.append('SUMO')
    for s in sims: d['GEH_'+s]=geh(d[s].to_numpy(),d.real.to_numpy())
    d.to_csv(a.out/'detector_compare.csv',index=False,float_format='%.3f')
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1,'font.size':9})
    def save(name):
        plt.tight_layout(); plt.savefig(a.out/(name+'.png'),dpi=160); plt.close()
    stable=d.groupby('site').hour.nunique(); stable=set(stable[stable==24].index); fixed=d[d.site.isin(stable)]
    plt.figure(figsize=(9,4))
    for s in ['real']+sims:
        t=fixed.groupby('hour')[s].sum(min_count=1); plt.plot(t.index,t,color=COLORS[s],label=s)
    plt.xlabel('Local hour [h]'); plt.ylabel('Summed cross-section counts [vehicles/h]'); plt.title(f'Berlin hourly counts at {len(stable)} fixed cross-sections'); plt.legend(); save('hourly_total')
    for label,window in [('morning',range(6,11)),('evening',range(15,20))]:
        peak=int(fixed[fixed.hour.isin(window)].groupby('hour').real.sum().idxmax())
        q=d[d.hour==peak]; fig,ax=plt.subplots(figsize=(5,5)); lim=max(q[['real']+sims].max().max()*1.05,100)
        grid=np.linspace(0,lim,220); x,y=np.meshgrid(grid,grid); ax.contour(x,y,geh(y,x),levels=[5,10],colors=['#888888','#bbbbbb'],linewidths=.6); ax.text(.03,.95,'Contours: GEH 5, 10',transform=ax.transAxes)
        for s in sims:
            ax.scatter(q.real,q[s],s=9,alpha=.6,color=COLORS[s],label=s)
        ax.plot([0,lim],[0,lim],color=COLORS['real'],lw=.6,label='Equality'); ax.set(xlabel='Real volume [vehicles/h]',ylabel='Simulated volume [vehicles/h]',title=f'Berlin {label} peak, {peak:02}:00'); ax.legend(); save('scatter_'+label)
    plt.figure(figsize=(7,4))
    for s in sims:
        v=np.sort(d['GEH_'+s].dropna()); plt.plot(v,np.arange(1,len(v)+1)/len(v),color=COLORS[s],label=s)
    plt.axvline(5,color='gray',lw=.6); plt.axvline(10,color='gray',lw=.6); plt.xlabel('GEH [dimensionless]'); plt.ylabel('Cumulative share [fraction]'); plt.title('Berlin hourly GEH distribution (available hours)'); plt.legend(); save('geh_distribution')
    _,net=network(a.net); segments=[shape/1000 for _,_,shape in net]
    fig,axes=plt.subplots(1,len(sims),figsize=(7*len(sims),6),squeeze=False)
    for ax,s in zip(axes[0],sims):
        ax.add_collection(LineCollection(segments,colors='#dddddd',linewidths=.15)); q=d.dropna(subset=[s]).groupby('site').apply(lambda g:(g[s]-g.real).mean(),include_groups=False).rename('residual').reset_index().merge(m,on='site'); bound=max(abs(q.residual).max(),1)
        sc=ax.scatter(q.x/1000,q.y/1000,c=q.residual,cmap='coolwarm',vmin=-bound,vmax=bound,s=9); ax.autoscale(); ax.set_aspect('equal'); ax.set(xlabel='Network x [km]',ylabel='Network y [km]',title=f'{s} mean hourly residual'); fig.colorbar(sc,ax=ax,label='Simulated − real [vehicles/h]')
    save('residual_map')
    totals=fixed.groupby('site').real.sum().sort_values(); chosen=totals.iloc[np.linspace(0,len(totals)-1,min(6,len(totals))).astype(int)].index
    fig,axes=plt.subplots(3,2,figsize=(11,9))
    for ax,site in zip(axes.flat,chosen):
        q=d[d.site==site].sort_values('hour')
        for s in ['real']+sims: ax.plot(q.hour,q[s],color=COLORS[s],label=s)
        ax.set(title=site,xlabel='Local hour [h]',ylabel='Volume [vehicles/h]'); ax.legend()
    save('representative_series')
    metrics=[]
    for s in sims:
        for h,g in d.dropna(subset=[s]).groupby('hour'):
            o=g.real.to_numpy(); v=g[s].to_numpy(); den=((o-o.mean())**2).sum()
            metrics.append(dict(simulator=s,hour=h,n=len(g),geh5=(geh(v,o)<5).mean(),r2=1-((v-o)**2).sum()/den if den else np.nan,slope=np.dot(o,v)/np.dot(o,o) if np.dot(o,o) else np.nan))
    metrics=pd.DataFrame(metrics); metrics.to_csv(a.out/'hourly_metrics.csv',index=False,float_format='%.4f')
    method=json.loads((a.out/'profile_method.json').read_text())
    text=f'''# Berlin detector comparison

Re-run (paths may be replaced):

```sh
nix develop --command python3 -I scripts/berlin_detectors.py map
nix develop --command python3 -I scripts/berlin_detectors.py profile
nix develop --command python3 -I scripts/berlin_detectors.py compare --cars {a.cars} --sumo {a.sumo}
```

## Method and coverage

Metadata: actual workbook has one lane table with WGS84 coordinates, old detector names and eight compass directions (not the GK4 sheets described in the inventory). Transform using network projParameter and netOffset. External passenger-compatible edges only; closest polyline segment bearing. Score = distance metres + 0.5 × bearing error degrees + 20 × lane-count mismatch. Accept distance ≤40 m, bearing error ≤45°, exact passenger lane count and runner-up score margin ≥10. Reject repeated accepted edge assignments. Automated matches have not had manual bridge/parallel-road review.

{len(m)} cross-sections considered; {sum(m.quality=='accepted')} accepted; {sum(m.quality!='accepted')} rejected. Profile retains {d.site.nunique()} sites / {len(d)} site-hours. Daily total uses {len(stable)} sites with all 24 real hours, held fixed for all curves. This is a sum of detector passages, not unique city trips or all Berlin traffic.

September 2024 is the only locally downloaded month, selected as a recent ordinary working-month baseline, not a reconstruction of the scenario's original year. Monday–Friday; Berlin summer break ended August 30 and autumn break begins October 21; no September Berlin public holidays. Provider docs contain no calendar exclusion mechanism; calendar basis: https://www.berlin.de/sen/bjf/service/kalender/ferien/ . No incident/weather filtering. At least five complete dates per site-hour. Every metadata lane must have finite nonnegative qkfz, completeness ≥75 (archive units are percent), hist_cor ≥{method['hist_cor']}. Hist_cor cutoff is our moderate positive-correlation heuristic, not a provider recommendation; it may preferentially retain typical traffic. Z-scores are not thresholded because documented rejection cutoffs are absent. Sum lanes on each common date before averaging dates. Missing lanes never become zero observations. Profile standard deviation and sample days are supplied.

Counts are all motor vehicles. Simulation entered counts are at upstream edge boundaries, not physical detector crossings; travel delay, mid-edge departures and queues cause differences. Sparse simulator edge omissions within a complete interval mean zero. Cars CSV is assumed to contain complete hourly intervals; it has no end marker. SUMO accepts only closed 900-second intervals and four quarters per hour, discarding truncated tails and incomplete hours, without extrapolation. Clock assumes simulation zero is local midnight. SUMO missing hours remain missing. Current cars input is an intermediate engine build and must be rerun later. No GPU was used.

## Independence and limitations

[BeST upstream documentation](https://github.com/mosaic-addons/best-scenario) states demand was extracted from MATSim Open Berlin and routes re-calibrated to user equilibrium. It also compares selected street counts against Digitale Plattform Berlin, the same provider as this archive. It does not establish which detector-years were used or that this September 2024 sample was held out. Thus a good fit is an external temporal consistency check, **not proven independent validation**. Demand year, fleet mix, bus support, road changes since metadata (2022), direction quantization and automatic matching all limit conclusions. No calibration was done here. Six examples span observed daily-volume quantiles; they are not selected by fit. SUMO coverage differs from the full-day cars run; compare common hours for simulator ranking.

Real data attribution: Digitale Plattform Stadtverkehr Berlin / Verkehrsdetektion Berlin, Datenlizenz Deutschland – Namensnennung 2.0. BeST: Schrab, Protzmann, Radusch (2023), CC BY 4.0.

## Results

R² = 1 − SSE/SST (may be negative); slope is least squares through origin, simulated on real. GEH = sqrt(2(S−O)²/(S+O)); both zero →0. Shares weight site-hours equally; no acceptance target is asserted.

|Simulator|Hour|Sites|GEH <5 share|R²|Slope|
|---|---:|---:|---:|---:|---:|
'''
    for r in metrics.itertuples(): text+=f'|{r.simulator}|{r.hour}|{r.n}|{r.geh5:.3f}|{r.r2:.3f}|{r.slope:.3f}|\n'
    for s in sims:
        q=d.dropna(subset=[s]); text+=f'\n{s}: pooled GEH<5 {(q["GEH_"+s]<5).mean():.1%}; simulated/real total {q[s].sum()/q.real.sum():.3f}, over {len(q)} site-hours.\n'
    sensitivity=a.out/'quality_sensitivity.csv'
    if sensitivity.exists():
        text+='\n## Quality cutoff sensitivity\n\nCoverage only (changing populations, not paired fit):\n\n```csv\n'+sensitivity.read_text()+'```\nRepeat profile with --hist-cor 0, 0.5 and 0.8 in separate --out directories containing detector_map.csv. Means are unweighted over retained site-hours, not a paired volume comparison.\n'
    text+='\nVerification: synthetic XML checks passed for four-quarter aggregation, sparse zero edges, truncated final interval discard and zero/zero GEH. Representative-series and residual-map PNGs were visually inspected. CSVs are below 3 MB each.\n'
    (a.out/'README.md').write_text(text)
    print(text[text.index('## Results'):])


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['map','profile','compare']); p.add_argument('--net',type=Path,default=ROOT/'best/berlin.net.xml'); p.add_argument('--metadata',type=Path,default=ROOT/'berlin-detectors/Stammdaten_Verkehrsdetektion_2022_07_20.xlsx'); p.add_argument('--archive',type=Path,default=ROOT/'berlin-detectors/detektoren_2024_09.tgz'); p.add_argument('--out',type=Path,default=Path('results/berlin')); p.add_argument('--hist-cor',type=float,default=.5); p.add_argument('--max-distance',type=float,default=40); p.add_argument('--cars',type=Path); p.add_argument('--sumo',type=Path); a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    if a.command=='compare' and not a.cars: p.error('compare requires --cars')
    if a.command=='profile' and a.archive.name!='detektoren_2024_09.tgz': p.error('calendar exclusion currently audited only for September 2024')
    {'map':mapping,'profile':profile,'compare':compare}[a.command](a)

if __name__=='__main__': main()
