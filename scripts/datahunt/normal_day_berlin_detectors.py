import csv,statistics as st
from collections import defaultdict
P='research/truth/berlin-review/'
q=defaultdict(lambda:[None]*24); v=defaultdict(lambda:[None]*24); lk=defaultdict(lambda:[None]*24); dd={}
for r in csv.DictReader(open(P+'detector_all_hourly.csv')):
    h=int(r['hour']); q[r['site']][h]=float(r['real']); v[r['site']][h]=float(r['v']) if r['v'] else None; lk[r['site']][h]=float(r['lkw'] or 0); dd[r['site']]=int(r['days'] or 0)
print(len(q),'sites; days e.g.',sorted(dd.values())[len(dd)//2])
def sh(a):
    t=sum(a); mid=sum(a[10:15])/5
    return dict(am=max(a[6:10])/t,pm=max(a[15:19])/t,night=(sum(a[22:])+sum(a[:6]))/t,h0719=sum(a[7:19])/t,am_mid=max(a[6:10])/mid,pm_mid=max(a[15:19])/mid,min_mid=min(a)/mid,adt=t)
rows=[]
for s,a in q.items():
    if None in a or sum(a)<2000: continue
    x=sh(a); vv=v[s]
    if None not in vv and all(i>0 for i in vv):
        nt=st.mean(vv[1:5]); x['vn']=nt; x['vw']=min(vv[6:20]); x['dip']=x['vw']/nt; x['vmid']=st.mean(vv[10:15]); x['site']=s
        rows.append(x)
print(len(rows))
for k in ('am','pm','night','h0719','am_mid','pm_mid','min_mid','adt','vn','vmid','vw','dip'):
    y=sorted(r[k] for r in rows); print(k,[round(y[int(p*(len(y)-1))],3) for p in (.1,.25,.5,.75,.9)])
tot=[sum(q[s][h] for s in q if None not in q[s]) for h in range(24)]
print('network sum',{k:round(v,3) for k,v in sh(tot).items()})
tv=[sum(q[s][h]*v[s][h] for s in q if None not in q[s] and None not in v[s])/sum(q[s][h] for s in q if None not in q[s] and None not in v[s]) for h in range(24)]
print('flow-weighted spot speed',[round(i) for i in tv])
