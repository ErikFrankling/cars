import json,datetime as dt,statistics as st
from collections import defaultdict
H=json.load(open('research/truth/data-hunt/14-data/paris_hours.json'))['results']
print(len(H),H[0])
rows=[]
def key(r):
    for k,v in r.items():
        if isinstance(v,str) and len(v)>=13: return v
for r in H:
    t=key(r)
    rows.append((t[:10],int(t[11:13]),r['q'],r['k'],r['qm'],r['n']))
byd=defaultdict(dict)
for d,h,q,k,qm,n in rows: byd[d][h]=(q,k,qm,n)
wd=[d for d in byd if dt.date.fromisoformat(d).weekday() in (1,2,3) and len(byd[d])==24 and d not in('2025-11-11',)]
print('days',len(wd),wd[:3])
q=[st.mean(byd[d][h][2] for d in wd) for h in range(24)]
k=[st.mean(byd[d][h][1] for d in wd) for h in range(24)]
tot=sum(q); mid=sum(q[10:15])/5
print('NOTE times are stored with offset? hour peak',max(range(24),key=lambda h:q[h]))
print('mean veh/h per link by UTC-stamp hour',[round(x) for x in q]); print('occ',[round(x,1) for x in k])
print('am',max(q[6:10])/tot,'pm',max(q[15:20])/tot,'night',(sum(q[22:])+sum(q[:6]))/tot,'am/mid',max(q[6:10])/mid,'pm/mid',max(q[15:20])/mid,'min/mid',min(q)/mid)
# MFD
pts=sorted((byd[d][h][1],byd[d][h][2],d,h) for d in byd for h in byd[d])
print('max avg occupancy',pts[-1],'max flow',max(pts,key=lambda x:x[1]))
bins=defaultdict(list)
for o,f,_,_h in pts: bins[int(o//2)*2].append(f)
print('MFD occ-bin mean flow',{b:(round(st.mean(v)),len(v)) for b,v in sorted(bins.items())})
S=json.load(open('research/truth/data-hunt/14-data/paris_states.json'))['results']
print(S[0])
tab=defaultdict(lambda:defaultdict(int))
for r in S:
    hh=[v for kk,v in r.items() if kk.startswith('date_format') or kk=='h']; h=[x for x in hh if x][0]
    tab[int(h)][r['e']]+=r['n']
for h in sorted(tab):
    t=sum(tab[h].values()); print(h,{e:round(100*n/t,1) for e,n in sorted(tab[h].items())})
all_=defaultdict(int)
for h in tab:
    for e,n in tab[h].items(): all_[e]+=n
print({e:round(100*n/sum(all_.values()),1) for e,n in all_.items()})
D=json.load(open('research/truth/data-hunt/14-data/paris_days.json'))['results']
days={}
for r in D:
    d=key(r)
    if d is None or len(d)<10: d=[v for v in r.values() if isinstance(v,str)][0]
    days[d[:10]]=r['q']/r['n']*24
print(len(days))
term=[(d,v) for d,v in sorted(days.items())]
tw=[v for d,v in term if dt.date.fromisoformat(d).weekday() in (1,2,3)]
print('Tue-Thu mean',st.mean(tw),'cv',st.pstdev(tw)/st.mean(tw),'n',len(tw))
for wdn,name in enumerate('Mon Tue Wed Thu Fri Sat Sun'.split()):
    a=[v for d,v in term if dt.date.fromisoformat(d).weekday()==wdn]; print(name,round(st.mean(a)/st.mean(tw),3),len(a))
