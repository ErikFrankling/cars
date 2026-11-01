import re, sys, collections
import numpy as np
import xml.etree.ElementTree as ET
NET='research/truth/fig/09-nets/j2.net.xml'
sp={}
for e in ET.parse(NET).getroot().findall('edge'):
    for l in e.findall('lane'): sp[l.get('id')]=float(l.get('speed'))
L=279.2; M=1500.0
pat=re.compile(r'tr t=([\d.]+) trip (\d+) lane (\S+) pos ([\d.\-]+) v ([\d.\-]+) a ([\d.\-]+)')
for p in sys.argv[1:]:
    app=collections.defaultdict(list); turn={}
    for line in open(p):
        if not line.startswith('tr '): continue
        t,trip,lane,pos,v,a=pat.match(line).groups(); trip=int(trip)
        if lane.startswith(':B1'):
            turn.setdefault(trip,sp.get(lane,13.89))
        elif lane.rsplit('_',1)[0] in('A1B1','B0B1','B2B1','C1B1'):
            app[trip].append((float(t),L-float(pos),float(v),float(a)))
    R=[];T=[]
    for trip,r in app.items():
        r=np.array(r)
        if r[0,1]<270 or r[-1,1]>3 or trip not in turn: continue
        t,dd,v,a=r.T
        dv=np.diff(v); act=-dv[dv<0].sum(); ke=0.5*M*np.maximum(v[:-1]**2-v[1:]**2,0).sum()/3600
        vc=dd[0]/(t[-1]-t[0]); vk=min(vc,turn[trip],v[0])
        idl=v[0]-vk; idl_ke=0.5*M*(v[0]**2-vk**2)/3600
        R.append((act,idl,ke,idl_ke,-a.min())); T.append(turn[trip]<13)
    R=np.array(R);T=np.array(T)
    print(p,'cars',len(R),'turning share',T.mean().round(2),'turn speeds',sorted(set(round(x,1) for x in turn.values())))
    for name,m in (('all',np.ones(len(R),bool)),('straight',~T),('turning',T)):
        print(f' {name:9s} n={m.sum():3d} speed lost {R[m,0].mean():.2f} gentlest {R[m,1].mean():.2f}  Wh {R[m,2].mean():.1f} gentlest {R[m,3].mean():.1f}  peak>3: {(R[m,4]>3).mean():.2f}')
