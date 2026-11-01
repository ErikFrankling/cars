# Daily bus crossings per edge from berlin_bus.rou.xml; flow times may be hh:mm:ss.
import re
from pathlib import Path
import numpy as np,pandas as pd
from lxml import etree
D=Path('/home/erikf/projects/personal/cars-data/best'); O=Path('research/truth/berlin-review')
E=pd.read_csv(O/'edges.csv',usecols=['edge'],dtype=str,keep_default_na=False); idx={e:i for i,e in enumerate(E.edge)}; bus=np.zeros(len(E))
def sec(v):
    if ':' in v:
        a=[float(x) for x in v.split(':')]; return sum(x*60**k for k,x in enumerate(reversed(a)))
    return float(v)
routes={}; n=0; bad=0; ex=None
for _,x in etree.iterparse(str(D/'berlin_bus.rou.xml'),events=('end',),tag=('route','flow','vehicle','trip'),resolve_entities=False,no_network=True):
    if x.tag=='route' and x.get('id'): routes[x.get('id')]=x.get('edges')
    elif x.tag in('flow','vehicle','trip'):
        if ex is None: ex=dict(x.attrib); print(ex)
        e=routes.get(x.get('route')) if x.get('route') else (x.find('route').get('edges') if x.find('route') is not None else None)
        if x.tag=='flow':
            b=sec(x.get('begin')); en=sec(x.get('end')); k=float(x.get('number')) if x.get('number') else (en-b)/sec(x.get('period')) if x.get('period') else float(x.get('vehsPerHour',0))*(en-b)/3600
        else: k=1
        if e is None: bad+=1
        else:
            n+=k
            for z in e.split():
                if z in idx: bus[idx[z]]+=k
    x.clear()
print('bus trips',n,'unresolved',bad); np.save(O/'static_bus.npy',bus); print('bus km/day',(bus*pd.read_csv(O/'edges.csv',usecols=['length']).length.values).sum()/1000)
