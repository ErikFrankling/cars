"""Audit passenger connectivity and match undirected weekday count geometry."""
import os, sys, json, csv, math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
sys.path.append(os.environ['SUMO_HOME'] + '/tools')
import sumolib
D = Path(sys.argv[1] if len(sys.argv)>1 else '/home/erikf/projects/personal/cars-data/stockholm')
net = sumolib.net.readNet(str(D/'stockholm.net.xml'))
edges = [e for e in net.getEdges() if e.allows('passenger')]
idx = {e.getID():i for i,e in enumerate(edges)}
a,b=[],[]
for e in edges:
    for o,cs in e.getOutgoing().items():
        if o.getID() in idx and any(c.allows('passenger') and c.getFromLane().allows('passenger') and c.getToLane().allows('passenger') for c in cs):
            a.append(idx[e.getID()]); b.append(idx[o.getID()])
graph=csr_matrix((np.ones(len(a)),(a,b)),shape=(len(edges),len(edges)))
n,labels=connected_components(graph,directed=True,connection='strong')
sizes=np.bincount(labels); main=int(sizes.argmax())
audit={'passenger_edges':len(edges),'strong_components':n,'largest_strong_component':int(sizes[main]),'tls':len(net.getTrafficLights()),'corridors':{}}
for name in ['E4','E20','Södra länken','Norra länken','Västerbron','Centralbron','Essingeleden']:
    es=[e for e in edges if name.lower() in e.getName().lower()]
    audit['corridors'][name]={'edges':len(es),'in_main_scc':int(sum(labels[idx[e.getID()]]==main for e in es))}
(D/'audit.json').write_text(json.dumps(audit,indent=2))
if '--audit-only' in sys.argv: print(audit); sys.exit(0)
points=[]; refs=[]; bearings=[]
for i,e in enumerate(edges):
    s=np.array(e.getShape())
    for p,q in zip(s[:-1],s[1:]):
        v=q-p; length=np.linalg.norm(v)
        if length<1: continue
        for t in np.linspace(0,1,max(2,int(length/15)+1)):
            points.append(p+t*v); refs.append(i); bearings.append(v/length)
tree=cKDTree(points); bearings=np.array(bearings)
features=json.load(open(D/'trafikflode_motorfordon.geojson'))['features']
rows=[]
for f in features:
    p=f['properties']; coords=max(f['geometry']['coordinates'],key=len)
    xy=np.array([net.convertLonLat2XY(*c[:2]) for c in coords]); mid=xy[len(xy)//2]; v=xy[-1]-xy[0]; norm=np.linalg.norm(v)
    if norm<1: continue
    v/=norm; ds,ks=tree.query(mid,k=40); choices={}
    for dist,k in zip(ds,ks):
        dot=float(v@bearings[k]); angle=math.degrees(math.acos(min(1,abs(dot))))
        score=dist+angle*2
        side=1 if dot>=0 else -1
        if angle<35 and dist<60 and (side not in choices or score<choices[side][0]): choices[side]=(score,refs[k],dist,angle)
    total=p.get('totalflöde_alla_riktningar') or p.get('trafikflöde_alla_fordon') or 0
    for side,(_,i,dist,angle) in choices.items():
        row=dict(feature=f['id'],edge=edges[i].getID(),distance_m=round(dist,2),angle_deg=round(angle,2),directions=len(choices),daily=float(total)/len(choices),method=p.get('metod_för_datainsamling'),year=p.get('uppdaterad'))
        for band in ['06_18','18_22','22_06']:
            value=p.get('trafikflöde_'+band+'_fordon_tidperiod_alla_fordon')
            row[band]=float(value if value is not None else total*{'06_18':.76,'18_22':.18,'22_06':.06}[band])/len(choices)
        rows.append(row)
with open(D/'count_matches.csv','w') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
fig,ax=plt.subplots(figsize=(10,10)); palette={'motorway':'#eb6834','trunk':'#aa7755','primary':'#2a78d6','secondary':'#1baf7a'}
for cls in ['other',*palette]:
    shapes=[e.getShape() for e in edges if (e.getType().split('.')[-1] if e.getType().split('.')[-1] in palette else 'other')==cls]
    ax.add_collection(LineCollection(shapes,colors=palette.get(cls,'#bbbbbb'),linewidths=.25,label=cls))
ax.autoscale(); ax.set_aspect('equal'); ax.set_xlabel('Network easting (m)'); ax.set_ylabel('Network northing (m)'); ax.legend(); fig.savefig('results/stockholm/network.png',dpi=160); print(audit); print('matches',len(rows))
