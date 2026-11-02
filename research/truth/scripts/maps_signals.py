# Real signal inventory (Stockholm WFS Signallykta/Signalstolpe/NVDB_Korsning) against the net's controllers, inside Stockholm municipality.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,math,csv,re,numpy as np
from scipy.spatial import cKDTree
W=MAPS/'wfs-20261031'
netp=sys.argv[1];tag=sys.argv[2]
net=load_net(netp);fwd,back=net_tf(net)
t3011=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
def pts(layer):
    for f in json.loads((W/f'{layer}.geojson').read_text())['features']:
        if f['geometry'] is None:continue
        c=f['geometry']['coordinates'];lon,lat=t3011.transform(c[0],c[1]);yield f['properties'],lon,lat,fwd(lon,lat)
# municipality polygon from OSM relation 398021
poly=json.loads((MAPS/'builds/osm/kommun.json').read_text())
from matplotlib.path import Path as MP
paths=[MP(np.array([fwd(*p) for p in ring])) for ring in poly]
inside=lambda x,y:any(p.contains_point((x,y)) for p in paths)
L=list(pts('Signallykta'));inst=collections.defaultdict(lambda:dict(n=0,xy=[],names=collections.Counter(),types=collections.Counter()))
for p,lon,lat,xy in L:
    i=str(p.get('anläggnings-id') or 'none');d=inst[i];d['n']+=1;d['xy'].append(xy);d['names'][p.get('namn','') or '']+=1;d['types'][p.get('typ') or '']+=1
print('lanterns',len(L),'installations',len(inst))
print('lantern types',collections.Counter(p.get('typ') for p,*_ in L).most_common(12))
print('lantern name prefixes',collections.Counter(re.split(r'[ :0-9]',(p.get('namn') or '?'))[0] for p,*_ in L).most_common(10))
print('group prefixes',collections.Counter(re.sub(r'\d.*','',(p.get('namn') or '? ?').split(' ')[-1]) for p,*_ in L).most_common(12))
V=[(p,xy) for p,lon,lat,xy in L if (p.get('typ') or '').lower().startswith(('fordon','bil','buss','k')) or (p.get('namn') or '').startswith('Fordon')]
print('vehicle lanterns',len(V))
vinst={str(p.get('anläggnings-id')) for p,xy in V}
print('installations with vehicle lanterns',len(vinst))
groups=collections.defaultdict(set)
for p,xy in V:
    m=re.search(r'\b(F\d+)',p.get('namn') or '')
    if m:groups[str(p.get('anläggnings-id'))].add(m.group(1))
print('vehicle signal groups per installation',sorted(collections.Counter(len(v) for v in groups.values()).items()))
for i,d in inst.items():
    a=np.array(d['xy']);d['c']=a.mean(0);d['r']=float(np.max(np.hypot(*(a-d['c']).T)));d['veh']=i in vinst;d['lanterns']=a
ids=list(inst);C=np.array([inst[i]['c'] for i in ids])
print('inst inside municipality',sum(inside(*c) for c in C),'of',len(C),' spread p50/p90/p99 m',np.percentile([inst[i]['r'] for i in ids],[50,90,99]).round(1))
# net controllers
adj=collections.defaultdict(set);app=collections.defaultdict(set)
for f,t,fl,tl,d,s,tid,li,via in net['conns']:
    if tid and f in net['edges']:adj[tid].add(net['edges'][f]['to']);app[tid].add(f)
tlsids=sorted({t['id'] for t in net['tls'].values()})
rows=[]
allhead=np.vstack([d['lanterns'] for d in inst.values()]);htree=cKDTree(allhead);hinst=np.array([k for k,d in inst.items() for _ in range(d['n'])])
vhead=np.array([xy for p,xy in V]);vtree=cKDTree(vhead)
for t in tlsids:
    js=[net['junctions'][j] for j in adj[t] if j in net['junctions']]
    if not js:continue
    x=float(np.mean([j['x'] for j in js]));y=float(np.mean([j['y'] for j in js]))
    d,_=htree.query((x,y));dv,_=vtree.query((x,y))
    near=set(hinst[htree.query_ball_point((x,y),60)])
    rows.append(dict(tl=t,x=x,y=y,nodes=len(js),approaches=len(app[t]),inside=inside(x,y),dist_head=round(float(d),1),dist_vehhead=round(float(dv),1),inst60=' '.join(sorted(near)),way_names=' / '.join(sorted({net['edges'][e]['name'] for e in app[t]}))[:80]))
ins=[r for r in rows if r['inside']]
print('net controllers',len(rows),'inside municipality',len(ins),'junction nodes of type traffic_light inside',sum(j['type']=='traffic_light' and inside(j['x'],j['y']) for j in net['junctions'].values()))
for th in (30,60,100):print(f'inside with vehicle head within {th} m',sum(r['dist_vehhead']<=th for r in ins),'any head',sum(r['dist_head']<=th for r in ins))
print('inside, approaches==1',sum(r['approaches']==1 for r in ins),'==2',sum(r['approaches']==2 for r in ins),'>=3',sum(r['approaches']>=3 for r in ins))
for k in (1,2):
    q=[r for r in ins if r['approaches']==k];print(' approaches',k,'with veh head<=60',sum(r['dist_vehhead']<=60 for r in q),'of',len(q))
q=[r for r in ins if r['approaches']>=3];print(' approaches>=3 with veh head<=60',sum(r['dist_vehhead']<=60 for r in q),'of',len(q))
# installations and net controllers near them
T=cKDTree(np.array([[r['x'],r['y']] for r in rows]))
miss=[];mult=collections.Counter();out=[]
for i in ids:
    d=inst[i]
    if not inside(*d['c']):continue
    near=set()
    for h in d['lanterns']:near.update(T.query_ball_point(h,40))
    dmin,_=T.query(d['c']);mult[min(len(near),6)]+=1
    lon,lat=back(*d['c'])
    out.append(dict(inst=i,lat=round(lat,6),lon=round(lon,6),lanterns=d['n'],veh=int(d['veh']),groups=len(groups.get(i,())),spread_m=round(d['r'],1),net_controllers_40m=len(near),dist_nearest_controller=round(float(dmin),1)))
print('real installations inside: net controllers within 40 m of any lantern',sorted(mult.items()))
print('veh inst inside',sum(o['veh'] for o in out),'with 0 controllers',sum(o['veh'] and o['net_controllers_40m']==0 for o in out),'with >1',sum(o['veh'] and o['net_controllers_40m']>1 for o in out))
with open(f'research/truth/maps-signal-installations-{tag}.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
with open(f'research/truth/maps-signal-controllers-{tag}.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# NVDB_Korsning signal flag
K=list(pts('NVDB_Korsning'));print('NVDB korsning signalreglering',collections.Counter(p.get('Signalreglering') for p,*_ in K).most_common(),'generalisering',collections.Counter(p.get('Generaliseringstyp') for p,*_ in K).most_common(8))
