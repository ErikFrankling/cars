# May 2019 Berlin: site-level day-to-day GEH and speed noise, and the same limited to stations far from v6.4 calibration links.
import csv,gzip,sys,json,collections,math,statistics as st
mq,match=sys.argv[1:3]
days=['07.05.2019','14.05.2019','15.05.2019','16.05.2019','21.05.2019','22.05.2019','23.05.2019','28.05.2019']
Q=collections.defaultdict(dict);V=collections.defaultdict(dict)
with gzip.open(mq,'rt',errors='replace') as f:
    r=csv.reader(f,delimiter=';');h=next(r);ix={k.strip():i for i,k in enumerate(h)}
    for x in r:
        d=x[ix['tag']]
        if d not in days: continue
        try:q=float(x[ix['q_kfz_mq_hr']]);v=float(x[ix['v_kfz_mq_hr']]);k=(x[ix['mq_name']],int(x[ix['stunde']]))
        except ValueError: continue
        Q[d][k]=q;V[d][k]=v
m=json.load(open(match)); far={r[0] for r in m if r[3] is None or r[3]>200}; far100={r[0] for r in m if r[3] is None or r[3]>100}
def geh(a,b): return math.sqrt(2*(a-b)**2/(a+b)) if a+b>0 else 0
g=[];sp=[];dq=[]
ds=[(a,b) for i,a in enumerate(days) for b in days[i+1:]]
for a,b in ds:
    for k in Q[a].keys()&Q[b].keys():
        if 6<=k[1]<=20:
            g.append(geh(Q[a][k],Q[b][k]))
            if V[a][k]>0 and V[b][k]>0: sp.append(abs(V[a][k]-V[b][k]))
            if Q[a][k]>=200 and Q[b][k]>0: dq.append(abs(Q[a][k]-Q[b][k])/Q[b][k])
g.sort();print('site-hour pairs 06-20',len(g),'GEH<5 share %.3f'%(sum(x<5 for x in g)/len(g)),'median GEH %.2f p95 %.2f'%(g[len(g)//2],g[int(.95*len(g))]))
sp.sort();dq.sort();print('site-hour speed abs diff km/h median %.1f p95 %.1f; flow abs pct (q>=200) median %.1f p95 %.1f'%(sp[len(sp)//2],sp[int(.95*len(sp))],100*dq[len(dq)//2],100*dq[int(.95*len(dq))]))
# congested hours share: site-hours with speed under 25 km/h on one chosen day
d='15.05.2019'; low=[k for k,v in V[d].items() if 0<v<25 and 6<=k[1]<=20]; allk=[k for k,v in V[d].items() if v>0 and 6<=k[1]<=20]
print('site-hours under 25 km/h on',d,len(low),'of',len(allk),'sites affected',len({k[0] for k in low}))
sites=set(k[0] for k in Q[d])
print('clean holdout >200m same-dir',len(far),'present on',d,len(far&sites),'; >100m',len(far100),len(far100&sites))
print('held-out names',sorted((r[0],r[4],r[5],r[3]) for r in m if r[0] in far)[:30])
