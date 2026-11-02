import re, sys, json, collections, statistics as st
import numpy as np
L=279.2; M=1500.0
pat=re.compile(r'tr t=([\d.]+) trip (\d+) lane (\S+) pos ([\d.\-]+) v ([\d.\-]+) a ([\d.\-]+) st (\S+) link (\S+) seq (\d+) tl ([\d.\-]+) vl ([\d.\-]+) cmd ([\d.\-]+)')
def load(p):
    d=collections.defaultdict(list)
    for line in open(p):
        if not line.startswith('tr '): continue
        m=pat.match(line)
        if not m: continue
        t,trip,lane,pos,v,a,st_,link,seq,tl,vl,cmd=m.groups()
        if not lane.endswith(('_0','_1')): continue
        e=lane.rsplit('_',1)[0]
        if e in('A1B1','B0B1','B2B1','C1B1') :
            d[int(trip)].append((float(t),L-float(pos),float(v),float(a),int(st_,16)&7,float(tl),float(vl)))
    return d
for p in sys.argv[1:]:
    d=load(p); dt=0.1
    n=0; rows=[]; bins=collections.defaultdict(lambda:[0,0.0]); ever=[]
    for trip,r in d.items():
        r=np.array(r)
        if r[0,1]<270 or r[-1,1]>3: continue  # whole approach seen
        n+=1
        t,dd,v,a=r[:,0],r[:,1],r[:,2],r[:,3]
        dv=np.diff(v); brake=-dv[dv<0].sum()
        ke=0.5*M*np.maximum(v[:-1]**2-v[1:]**2,0).sum()/3600 # Wh
        T=t[-1]-t[0]; vc=dd[0]/T; vend=v[-1]
        # gentlest profile hitting the same place at the same time: slow once to the average speed, never brake again
        ideal=max(v[0]-vc,0)
        ideal_ke=0.5*M*max(v[0]**2-vc**2,0)/3600
        # where braking occurs
        for i in range(len(dv)):
            if dv[i]<0:
                b=min(int(dd[i]//50),5); bins[b][1]+=-dv[i]
        bins_peak=a.min()
        rows.append((brake,ideal,ke,ideal_ke,-bins_peak,v.min(),vend,T,dd[0]/13.89))
    R=np.array(rows)
    print(p,'cars',n)
    print(' mean speed thrown away by braking per approach m/s',R[:,0].mean().round(2),' ideal',R[:,1].mean().round(2),' ratio',(R[:,0].sum()/max(R[:,1].sum(),1e-9)).round(1))
    print(' kinetic energy braked away Wh/approach',R[:,2].mean().round(1),' ideal',R[:,3].mean().round(1))
    print(' share of cars braking at all (>0.5 m/s speed lost)',(R[:,0]>0.5).mean().round(3))
    print(' peak decel percentiles 50/90/99',np.percentile(R[:,4],[50,90,99]).round(2),' share >2',(R[:,4]>2).mean().round(3),' >3',(R[:,4]>3).mean().round(3),' >4',(R[:,4]>4).mean().round(3))
    print(' min speed percentiles 10/50',np.percentile(R[:,5],[10,50]).round(1),' arrive speed 10/50',np.percentile(R[:,6],[10,50]).round(1))
    print(' extra approach time mean s',(R[:,7]-R[:,8]).mean().round(2))
    tot=sum(v[1] for v in bins.values())
    print(' where the braking happens (metres before the line):',{f'{k*50}-{(k+1)*50}':round(bins[k][1]/tot,2) for k in sorted(bins)})
