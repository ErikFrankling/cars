# Gives one controller per real installation inside Stockholm municipality. Usage: maps_patch_tls.py PLAIN_PREFIX OUT.nod.xml REPORT.json
# Evidence: city Signallykta/Signalstolpe/Tryckknapp (installation id) and NVDB_Korsning Signalreglering=ja. Without evidence a signal node becomes a priority node.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,re,numpy as np
from scipy.spatial import cKDTree
from matplotlib.path import Path as MP
W=MAPS/'wfs-20261031';pre,outp,rep=sys.argv[1:4]
src=open(pre+'.nod.xml').read()
loc=re.search(r'<location [^>]*>',src).group(0);m=dict(re.findall(r'(\w+)="([^"]*)"',loc));fwd,back=net_tf(dict(location=m))
t=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
def L(l,k):
    o=[]
    for f in json.loads((W/f'{l}.geojson').read_text())['features']:
        if f['geometry']:
            c=f['geometry']['coordinates'];lo,la=t.transform(c[0],c[1]);o.append((str(f['properties'].get(k)).lstrip('0'),*fwd(lo,la),f['properties']))
    return o
inv=L('Signallykta','anläggnings-id')+L('Signalstolpe','Anläggnings_id')+L('Tryckknapp','anläggnings-id')
K=L('NVDB_Korsning','x');ja=np.array([[a[1],a[2]] for a in K if a[3].get('Signalreglering')=='ja'])
T=cKDTree(np.array([[a[1],a[2]] for a in inv]));J=cKDTree(ja);ids=[a[0] for a in inv]
P=[MP(np.array([fwd(*p) for p in r])) for r in json.loads((MAPS/'builds/osm/kommun.json').read_text())]
inside=lambda x,y:any(p.contains_point((x,y)) for p in P)
nodes=[dict(re.findall(r'([\w:.]+)="([^"]*)"',s)) for s in re.findall(r'<node [^>]*/>',src)]
tln=[n for n in nodes if n.get('type','').startswith('traffic_light')]
stat=collections.Counter();assign={};nvdb=[]
for n in tln:
    x,y=float(n['x']),float(n['y'])
    if not inside(x,y):stat['outside kept']+=1;continue
    d,i=T.query((x,y))
    if d<=45:assign[n['id']]='S'+ids[i];stat['inside installation']+=1
    elif J.query((x,y))[0]<=60:nvdb.append(n);stat['inside NVDB signal only']+=1
    else:assign[n['id']]=None;stat['inside no evidence, removed']+=1
# NVDB-only nodes: one controller per connected group within 60 m
if nvdb:
    xy=np.array([[float(n['x']),float(n['y'])] for n in nvdb]);par=list(range(len(nvdb)))
    def fd(a):
        while par[a]!=a:par[a]=par[par[a]];a=par[a]
        return a
    for a,b in cKDTree(xy).query_pairs(60):par[fd(a)]=fd(b)
    for i,n in enumerate(nvdb):assign[n['id']]=f'N{fd(i)}'
inst=collections.Counter(v for v in assign.values() if v and v[0]=='S')
print(stat,'controllers inside',len(set(v for v in assign.values() if v)),'nodes per S-installation',sorted(collections.Counter(inst.values()).items())[:12])
def rw(mo):
    s=mo.group(0);i=re.search(r' id="([^"]*)"',s).group(1)
    if i not in assign:return s
    s=re.sub(r' tl="[^"]*"','',s)
    if assign[i] is None:return re.sub(r'type="[^"]*"','type="priority"',s)
    return s.replace('/>',f' tl="{assign[i]}"/>')
open(outp,'w').write(re.sub(r'<node [^>]*/>',rw,src))
Path(rep).write_text(json.dumps(dict(stat=stat,controllers_inside=len(set(v for v in assign.values() if v)),removed=[k for k,v in assign.items() if v is None]),indent=0))
