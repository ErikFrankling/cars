import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import json,csv,gzip,collections,math,hashlib
from pathlib import Path
from lxml import etree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path('/home/erikf/projects/personal/cars-data/stockholm'); O=Path('research/truth'); F=O/'fig'
def stream(path,tag):
    f=gzip.open(path,'rb') if str(path).endswith('.gz') else open(path,'rb')
    with f:
        for _,e in ET.iterparse(f,events=('end',),tag=tag):
            yield e
            e.clear()
            while e.getprevious() is not None: del e.getparent()[0]
def stat(x):
    a=np.asarray(x); return dict(n=len(a),mean=float(a.mean()),p05=float(np.percentile(a,5)),median=float(np.median(a)),p95=float(np.percentile(a,95)),sum=float(a.sum()))
edges={}; tls=[]; junctions={}; loc={}; conns=[]
for e in stream(D/'stockholm.net.xml',('edge','tlLogic','junction','location','connection')):
    if e.tag=='location':loc=dict(e.attrib)
    elif e.tag=='edge':
        lanes=e.findall('lane'); passenger=[l for l in lanes if ('allow' not in l.attrib or 'passenger' in l.get('allow','').split() or 'all' in l.get('allow','').split()) and 'passenger' not in l.get('disallow','').split()]
        if passenger and not e.get('id').startswith(':'):
            l=passenger[0]; edges[e.get('id')]=dict(name=e.get('name',''),type=e.get('type',''),fr=e.get('from'),to=e.get('to'),lanes=len(passenger),length=float(l.get('length')),speed=max(float(x.get('speed')) for x in passenger),shape=l.get('shape',''))
    elif e.tag=='tlLogic':tls.append(dict(e.attrib))
    elif e.tag=='junction':junctions[e.get('id')]=dict(e.attrib)
    elif e.tag=='connection':conns.append(dict(e.attrib))
print('network',len(edges),flush=True)
ids=list(edges); ix={e:i for i,e in enumerate(ids)}; length=np.array([edges[e]['length'] for e in ids]); lanes=np.array([edges[e]['lanes'] for e in ids]); speed=np.array([edges[e]['speed'] for e in ids]); cap=np.minimum(2400,3600/(1+7/np.maximum(speed,0.1)))*lanes
routes={}; lengths=[]; uturn=[]; starts=[]; ends=[]; counts=[]; hours={}; lengths_stats={}; vkms={}; scheduled={}; bins=[0,1000,3000,5000,10000,15000,30000,1e9]; hist={}
for filename in ['stockholm.rou.gz','stockholm60.rou.gz']:
    cc=np.zeros((79013,3),dtype=np.int64); hh=np.zeros(24,dtype=np.int64)
    for e in stream(D/filename,('route','vehicle')):
        if e.tag=='route' and filename=='stockholm.rou.gz':
            r=e.get('edges').split(); rid=e.get('id'); k=int(rid[1:]); a=[ix[x] for x in r]; routes[k]=a
            lengths.append(sum(length[a])); starts.append(a[0]); ends.append(a[-1]); uturn.append(any(y==('-'+x if not x.startswith('-') else x[1:]) for x,y in zip(r,r[1:])))
        elif e.tag=='vehicle':
            h=int(float(e.get('depart'))//3600)%24; hh[h]+=1; cc[int(e.get('route')[1:]),0 if 6<=h<18 else 1 if 18<=h<22 else 2]+=1
    weights=cc.sum(axis=1); ls=np.array(lengths); total=int(weights.sum()); scheduled[filename]=total; hours[filename]=hh.tolist(); vkms[filename]=float(weights@ls/1000); vals=np.repeat(ls,weights); lengths_stats[filename]=stat(vals); hist[filename]=np.histogram(vals,bins)[0].tolist(); del vals
    counts.append(cc); print(filename,total,flush=True)
load=np.zeros((len(ids),3)); load60=load.copy()
for k,a in routes.items():
    load[a]+=counts[0][k]; load60[a]+=counts[1][k]
rows=list(csv.DictReader(open(D/'count_matches.csv'))); groups=collections.defaultdict(list)
for r in rows:groups[r['edge']].append(r)
capacity_rows=[]
for i,e in enumerate(ids):
    target=np.mean([[float(r[b]) for b in ['06_18','18_22','22_06']] for r in groups[e]],axis=0) if e in groups else [0,0,0]
    rr=dict(edge=e,name=edges[e]['name'],lanes=int(lanes[i]),speed_kmh=float(speed[i]*3.6),capacity_hour=float(cap[i]),fitted_day=float(load[i].sum()),fitted_06_18_hour=float(load[i,0]/12),target_06_18_hour=float(target[0]/12),ratio=float(load[i,0]/12/cap[i]),ratio60=float(load60[i,0]/12/cap[i]))
    capacity_rows.append(rr)
capacity_rows.sort(key=lambda r:r['ratio'],reverse=True)
with open(O/'stockholm-link-capacity.csv','w') as f:
    w=csv.DictWriter(f,capacity_rows[0]);w.writeheader();w.writerows(capacity_rows)
gj=json.load(open(D/'trafikflode_motorfordon.geojson'))['features']; methods=collections.Counter(f['properties'].get('metod_för_datainsamling') for f in gj); years=collections.Counter(str(f['properties'].get('uppdaterad'))[:4] for f in gj)
summary=list(csv.DictReader(open(D/'cars.summary.csv'))); tele=collections.Counter(); first=collections.Counter(); slow=[]
for r in csv.DictReader(open(D/'cars.edges.csv')):
    n=int(r['teleports']);tele[r['edge']]+=n
    if float(r['begin'])==0: first[r['edge']]+=n
    if float(r['samples'])>0 and float(r['distance'])/float(r['samples'])<1: slow.append((float(r['begin']),r['edge'],float(r['samples'])))
tripcols={k:[] for k in ['duration','waiting','time_loss','route_length']}
for r in csv.DictReader(open(D/'cars.trips.csv')):
    for k in tripcols:tripcols[k].append(float(r[k]))
corr={}
for name in ['Norra länken','Södra länken','Essingeleden','Slussen']:
    a=[i for i,e in enumerate(ids) if name.lower() in edges[e]['name'].lower()]; corr[name]=dict(edges=len(a),lane_counts=dict(collections.Counter(int(lanes[i]) for i in a)),speeds_kmh=dict(collections.Counter(round(float(speed[i]*3.6)) for i in a)),km=float(length[a].sum()/1000),max_ratio=max([float(load[i,0]/12/cap[i]) for i in a],default=0))
signal_edges={c.get('from') for c in conns if c.get('tl')}; motorway=[e for e in ids if 'motorway' in edges[e]['type']]; in_deg=collections.Counter(c.get('to') for c in conns);out_deg=collections.Counter(c.get('from') for c in conns)
result=dict(network=dict(edges=len(ids),tls=len(tls),location=loc,lane_counts=dict(collections.Counter(lanes.tolist())),speed_counts_kmh=dict(collections.Counter(round(x*3.6) for x in speed)),motorway_edges=len(motorway),motorway_directed_km=sum(edges[e]['length'] for e in motorway)/1000,motorway_signal_edges=len(set(motorway)&signal_edges),signal_approach_edges=len(signal_edges),sources=sum(not in_deg[e] for e in ids),sinks=sum(not out_deg[e] for e in ids)),corridors=corr,scheduled=scheduled,hours=hours,planned_vkm=vkms,route_length_m=lengths_stats,route_pool=len(routes),uturn_routes=sum(uturn),uturn_scheduled=int(counts[0].sum(axis=1)@np.array(uturn)),counts=dict(features=len(gj),matches=len(rows),edges=len(groups),methods=dict(methods),years=dict(years),one_direction_features=len({r['feature'] for r in rows if r['directions']=='1'})),capacity=dict(formula='lanes * min(2400,3600/(1+7/speed_mps)); optimistic screening assumption, not measured capacity',over_full=sum(r['ratio']>1 for r in capacity_rows),over_60=sum(r['ratio60']>1 for r in capacity_rows),targets_over=sum(r['target_06_18_hour']>r['capacity_hour'] for r in capacity_rows),top=capacity_rows[:20]),simulation=dict(final=summary[-1],peak=max(int(r['running']) for r in summary),trips={k:stat(v) for k,v in tripcols.items()},first_teleport=next(r for r in summary if int(r['teleports'])>0),first_interval_teleports=first.most_common(12),top_teleports=tele.most_common(20),earliest_slow=sorted(slow)[:15]))
(O/'stockholm-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
plt.rcParams.update({'font.size':10})
fig,ax=plt.subplots(figsize=(9,4));
for fn,hh in hours.items():ax.plot(range(24),np.array(hh)/1000,label=fn)
ax.set(xlabel='Departure hour',ylabel='Scheduled vehicles (thousands)',title='Synthetic departure profiles; neither is observed');ax.legend();fig.tight_layout();fig.savefig(F/'stockholm-hourly.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(9,4)); w=counts[0].sum(axis=1);ax.hist(np.array(lengths)/1000,weights=w,bins=np.arange(0,32,1));ax.set(xlabel='Planned route length (km)',ylabel='Scheduled vehicles',title='Full fitted demand: random-walk routes');fig.tight_layout();fig.savefig(F/'stockholm-lengths.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4));t=np.array([float(r['time'])/3600 for r in summary]);axs[0].plot(t,[int(r['running']) for r in summary]);axs[0].set(xlabel='Hour',ylabel='Running vehicles',title='Existing output: 60% retimed run');axs[1].plot(t,[int(r['teleports']) for r in summary]);axs[1].set(xlabel='Hour',ylabel='Cumulative teleport events');fig.tight_layout();fig.savefig(F/'stockholm-gridlock.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(9,4)); rr=capacity_rows[:15];ax.barh([r['edge'] for r in rr][::-1],[r['ratio'] for r in rr][::-1]);ax.axvline(1,color='r');ax.set(xlabel='Fitted 06–18 average flow / optimistic capacity',title='Worst planned link loads (not simulated flows)');fig.tight_layout();fig.savefig(F/'stockholm-capacity.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4));ax.bar(['Full clip planned','60% clip planned','City annual-average\nrough 2024 reference'],[vkms['stockholm.rou.gz']/1e6,vkms['stockholm60.rou.gz']/1e6,3.3e9/366/1e6],color=['#d65','#39a','#888']);ax.set(ylabel='Million vehicle-km/day',title='Different geographic domains: diagnostic, not a calibration ratio');fig.tight_layout();fig.savefig(F/'stockholm-vkm.png',dpi=150);plt.close(fig)
print(json.dumps(result,ensure_ascii=False)[:1400])
