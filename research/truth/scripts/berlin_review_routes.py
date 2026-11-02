# Streams berlin.net.xml, berlin.rou.gz and berlin_bus.rou.xml into a static edge table, no simulator involved.
import gzip,json,os,re
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from lxml import etree
D=Path('/home/erikf/projects/personal/cars-data/best'); O=Path('research/truth/berlin-review'); C=O/'cache'
def strip(x):
    x.clear()
    while x.getprevious() is not None: del x.getparent()[0]
rows=[]; shapes={}; junction={}; loc=None
for _,x in etree.iterparse(str(D/'berlin.net.xml'),events=('end',),tag=('location','edge','junction'),resolve_entities=False,no_network=True):
    if x.tag=='location': loc=dict(x.attrib)
    elif x.tag=='junction':
        if x.get('type')!='internal': junction[x.get('id')]=(x.get('type'),float(x.get('x')),float(x.get('y')))
    elif not x.get('id','').startswith(':'):
        lanes=x.findall('lane')
        pass_lanes=[l for l in lanes if 'passenger' not in l.get('disallow','').split() and (not l.get('allow') or 'passenger' in l.get('allow').split() or 'all' in l.get('allow').split())]
        ref=pass_lanes[len(pass_lanes)//2] if pass_lanes else lanes[0]
        rows.append(dict(edge=x.get('id'),fr=x.get('from'),to=x.get('to'),type=x.get('type'),name=x.get('name'),lanes=len(lanes),pass_lanes=len(pass_lanes),length=float(lanes[0].get('length')),speed=float(lanes[0].get('speed'))))
        shapes[x.get('id')]=ref.get('shape')
    strip(x)
E=pd.DataFrame(rows); E.to_csv(O/'edges.csv',index=False); (C/'shapes.json').write_text(json.dumps(shapes)); (C/'junctions.json').write_text(json.dumps(junction)); (O/'net_location.json').write_text(json.dumps(loc))
idx={e:i for i,e in enumerate(E.edge)}; L=E.length.values; S=E.speed.values
N=len(E); hourly=np.zeros((N,24),dtype=np.int32); dep=np.zeros((N,24),dtype=np.int32)
buf=[]; off=[0]; meta=[]; total=0
fh=open(C/'routes.i32','wb')
with gzip.open(D/'berlin.rou.gz','rb') as f:
    for _,x in etree.iterparse(f,events=('end',),tag=('vehicle','vType'),resolve_entities=False,no_network=True):
        if x.tag=='vType': print('VTYPE',dict(x.attrib),flush=True); strip(x); continue
        rt=x.find('route'); ids=np.fromiter((idx[z] for z in rt.get('edges').split()),dtype=np.int32)
        t=float(x.get('depart')); h=int(t//3600)
        ft=np.cumsum(L[ids]/(0.7*S[ids])); ft=np.concatenate(([0.],ft[:-1]))
        bins=np.minimum(((t+ft)//3600).astype(int),23); np.add.at(hourly,(ids,bins),1)
        ln=L[ids].sum(); meta.append((t,ids[0],ids[-1],len(ids),ln)); ids.tofile(fh); off.append(off[-1]+len(ids)); total+=1
        if total==1: print('FIRST',dict(x.attrib),flush=True)
        if total%500000==0: print(total,flush=True)
        strip(x)
fh.close()
m=np.array(meta); np.save(C/'route_meta.npy',m); np.save(C/'route_off.npy',np.array(off,dtype=np.int64)); np.save(O/'static_hourly.npy',hourly)
print('vehicles',total,'edge visits',off[-1],'ext km',m[:,4].sum()/1000,'mean ext km',m[:,4].mean()/1000)
