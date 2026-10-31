"""Fit a deterministic random-walk route pool by multiplicative balancing.

Counts constrain edge passages, not unique trips. All vehicles are passenger proxies.
"""
import os,sys,csv,json,gzip,random,collections
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix

sys.path.append(os.environ['SUMO_HOME']+'/tools')
import sumolib
D=Path(sys.argv[1] if len(sys.argv)>1 else '/home/erikf/projects/personal/cars-data/stockholm')
rng=random.Random(42); net=sumolib.net.readNet(str(D/'stockholm.net.xml'))
rows=list(csv.DictReader(open(D/'count_matches.csv')))
# Multiple observations of the same directed edge are averaged, never summed.
groups=collections.defaultdict(list)
for r in rows: groups[r['edge']].append(r)
ids=sorted(groups); ix={e:i for i,e in enumerate(ids)}
target=np.array([[np.mean([float(r[b]) for r in groups[e]]) for b in ['06_18','18_22','22_06']] for e in ids])
routes=[]; seen=set()
for edge in ids:
    for replica in range(4):
        e=net.getEdge(edge); route=[e]; visited={e.getID()}; length=e.getLength()
        # Extend around a count segment in both directions; avoid loops.
        for backward in [True,False]:
            cur=e
            for step in range(60):
                opts=list(cur.getIncoming() if backward else cur.getOutgoing())
                opts=[x for x in opts if x.allows('passenger') and x.getID() not in visited and any(c.allows('passenger') and c.getFromLane().allows('passenger') and c.getToLane().allows('passenger') for c in (x.getOutgoing().get(cur,[]) if backward else cur.getOutgoing().get(x,[])))]
                if not opts or length>rng.uniform(3000,12000): break
                x=rng.choices(opts,weights=[max(1,o.getSpeed()) for o in opts])[0]
                if backward:
                    if cur not in x.getOutgoing(): break
                    route.insert(0,x)
                else: route.append(x)
                visited.add(x.getID()); length+=x.getLength(); cur=x
        key=tuple(x.getID() for x in route)
        if key not in seen and len(key)>1: seen.add(key); routes.append(key)
a=[];b=[]
for j,r in enumerate(routes):
    for e in r:
        if e in ix:a.append(ix[e]);b.append(j)
A=coo_matrix((np.ones(len(a)),(a,b)),shape=(len(ids),len(routes))).tocsr()
weights=[]; report={}
for k,band in enumerate(['06_18','18_22','22_06']):
    w=np.full(len(routes),max(1,target[:,k].sum()/max(A.nnz,1)))
    denom=np.maximum(np.asarray(A.sum(axis=0)).ravel(),1)
    for iteration in range(300):
        pred=A@w
        ratio=target[:,k]/np.maximum(pred,1e-9)
        w*=np.asarray(A.T@ratio).ravel()/denom
    weights.append(w); pred=A@w; geh=np.sqrt(2*(pred-target[:,k])**2/np.maximum(pred+target[:,k],1))
    report[band]={'route_fit_geh_lt5':float(np.mean(geh<5)),'target_passages':float(target[:,k].sum()),'fitted_passages':float(pred.sum()),'iterations':300}
vehicles=[]; hourly=np.zeros(24)
for k,hours in enumerate([list(range(6,18)),list(range(18,22)),list(range(22,24))+list(range(6))]):
    for j,w in enumerate(weights[k]):
        n=int(w)+(rng.random()<w%1)
        for _ in range(n):
            h=rng.choice(hours); vehicles.append((h*3600+rng.random()*3600,j)); hourly[h]+=1
vehicles.sort()
with gzip.open(D/'stockholm.rou.gz','wt') as f:
    f.write('<routes>\n<vType id="passenger" accel="1.5" decel="4.5" sigma="0.5" tau="1" length="5" minGap="2"/>\n')
    for j,r in enumerate(routes): f.write(f'<route id="r{j}" edges="{" ".join(r)}"/>\n')
    for i,(depart,j) in enumerate(vehicles):f.write(f'<vehicle id="s{i}" type="passenger" depart="{depart:.3f}" departLane="best" departSpeed="max" route="r{j}"/>\n')
    f.write('</routes>\n')
report.update(trips=len(vehicles),route_pool=len(routes),hourly=hourly.tolist(),note='Estimated OD fit to weekday edge counts; uniform hours within measured bands. Route fit is not simulated validation.')
(D/'demand_fit.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots();ax.plot(range(24),hourly,color='#1baf7a',lw=1);ax.set(xlabel='Hour',ylabel='Estimated departures (vehicles/h)');fig.savefig('results/stockholm/hourly_profile.png',dpi=160)
