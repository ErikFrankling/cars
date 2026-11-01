# Plots NVDB forbidden turns that the sanity match calls open, over the net, to judge whether the match is right; also explains real installations without a net controller.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,csv,math,numpy as np
from scipy.spatial import cKDTree
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
n=load_net(DATA/'stockholm/stockholm.net.xml');fwd,back=net_tf(n);W=MAPS/'wfs-20261031';t3=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
fb=json.loads((W/'NVDB_Forbjuden_svang.geojson').read_text())['features'];E_=n['edges']
ex=[('542554512','42277132'),('-411449793','622465149#0'),('25555568','-257319261'),('36933048#7','-37548499#5'),('459163013#3','1338916519'),('1071324151#0','31737869'),('-252922303','62140866'),('1337695410#0','4425745#0')]
L=[[fwd(*t3.transform(c[0],c[1])) for c in f['geometry']['coordinates']] for f in fb if f['geometry']]
mid=cKDTree(np.array([l[len(l)//2] for l in L]))
fig,axs=plt.subplots(2,4,figsize=(15,8))
sh=lambda e:[tuple(map(float,p.split(','))) for p in E_[e]['lanes'][0]['shape'].split()]
for ax,(a,b) in zip(axs.flat,ex):
    e=sh(a)[-1];cx,cy=e;k=mid.query((cx,cy),k=4)[1]
    for ed,d in E_.items():
        p=sh(ed) if False else None
    for ed,d in E_.items():
        s=d['lanes'][0]['shape'].split()
        x0,y0=map(float,s[-1].split(','))
        if abs(x0-cx)<70 and abs(y0-cy)<70:
            q=[tuple(map(float,v.split(','))) for v in s];ax.plot(*zip(*q),color='#bbbbbb',lw=1)
    ax.plot(*zip(*sh(a)),color='blue',lw=2);ax.plot(*zip(*sh(b)),color='green',lw=2)
    for i in k:
        ax.plot(*zip(*L[i]),color='red',lw=2.5,alpha=.7,marker='>',ms=4,markevery=[-1])
    ax.set_xlim(cx-45,cx+45);ax.set_ylim(cy-45,cy+45);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([]);ax.set_title(f"{E_[a]['name'] or a}\n→ {E_[b]['name'] or b}",fontsize=8)
fig.suptitle('Blue=from edge, green=to edge of a net connection; red=nearest NVDB Förbjuden sväng lines (arrow marks line end)');fig.tight_layout();fig.savefig('research/truth/fig/maps07/nvdb_forbidden_samples.png',dpi=100)
# installations without a controller
rows=list(csv.DictReader(open('research/truth/maps-signal-installations-baseline.csv')));zero=[r for r in rows if r['veh']=='1' and r['net_controllers_40m']=='0']
J=list(n['junctions'].items());TJ=cKDTree(np.array([[d['x'],d['y']] for _,d in J]))
seg=[];own=[]
for e,d in E_.items():
    if not any(passenger(l) for l in d['lanes']):continue
    for p in d['lanes'][0]['shape'].split():
        seg.append(tuple(map(float,p.split(','))));own.append(e)
TE=cKDTree(np.array(seg))
o=load_osm(MAPS/'builds/osm/highway.osm.xml');sigs=[(v['lon'],v['lat']) for v in o['tagged'].values() if v['tags'].get('highway')=='traffic_signals' or v['tags'].get('crossing')=='traffic_signals']
TS=cKDTree(np.array([fwd(*p) for p in sigs]));c=collections.Counter();out=[]
for r in zero:
    x,y=fwd(float(r['lon']),float(r['lat']));de,ie=TE.query((x,y));ds,_=TS.query((x,y));dj,ij=TJ.query((x,y))
    k='road removed/absent (>25 m from car edge)' if de>25 else 'OSM signal node within 60 m but not on car network' if ds<=60 else 'no OSM signal; car road present'
    c[k]+=1;out.append(dict(r,edge_dist=round(float(de),1),osm_signal_dist=round(float(ds),1),nearest_edge=own[ie],name=E_[own[ie]]['name'],junction_type=J[ij][1]['type'],reason=k))
print(len(zero),c)
with open('research/truth/maps-signal-missing-baseline.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print([(x['inst'],x['lat'],x['lon'],x['name'],x['groups'],x['reason'][:12]) for x in out][:14])
