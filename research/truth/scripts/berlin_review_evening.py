# Published SUMO running curve versus cars, departure steps, and the spatial structure of the cars evening failure.
import os,json,re
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from lxml import etree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
O=Path('research/truth/berlin-review'); C=O/'cache'; S=Path('research/truth/berlin-snapshot')
t=etree.parse(str(C/'bus11.svg'),etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True)); cur={}
for e in t.getroot().iter('{http://www.w3.org/2000/svg}path'):
    d=e.get('d',''); st=e.get('stroke','') or ''
    if len(d)>100000:
        p=np.array(re.findall(r'[ML] ([-\d.]+) ([-\d.]+)',d),dtype=float); cur['BeST' if st.startswith('rgb(100%') else 'BeST_Bus']=p
fx=lambda x:(x-101.046934)/(912.692325-101.046934)*24; fy=lambda y:(y-75.59684)/(484.976119-75.59684)*40000
s=pd.read_csv(S/'day_summary.csv'); rows=[]
for h in np.arange(0,24.01,.5):
    r=dict(hour=h)
    for k,p in cur.items():
        o=np.argsort(fx(p[:,0])); r[k]=np.interp(h,fx(p[o,0]),fy(p[o,1]))
    r['cars']=np.interp(h*3600,s.time,s.running); r['cars_teleports']=np.interp(h*3600,s.time,s.teleports); rows.append(r)
F=pd.DataFrame(rows); F['cars_minus_sumo']=F.cars-F.BeST; F['ratio']=F.cars/F.BeST.clip(lower=1); F.to_csv(O/'running_sumo_vs_cars.csv',index=False,float_format='%.1f'); print(F.round(2).to_string())
peak=F.BeST.idxmax(); print('published peak',F.hour[peak],F.BeST[peak]); p=cur['BeST']; o=np.argsort(fx(p[:,0])); print('published true max',fy(p[o,1]).max(),'at h',fx(p[o,0])[np.argmax(fy(p[o,1]))]); print('veh-h 18-23 h integral SUMO',np.trapezoid(F.BeST[F.hour.between(18,23)],dx=.5),'cars',np.trapezoid(F.cars[F.hour.between(18,23)],dx=.5))
M=np.load(C/'route_meta.npy'); dep=M[:,0]; h5=np.bincount((dep//300).astype(int),minlength=288); print('BeST 5-min departures 05:00-06:30',h5[60:78].tolist()); print('19:00-21:00',h5[228:252].tolist())
T=pd.read_csv(S/'day_trips.csv'); print(T.columns.tolist()); print('cars trips mean duration min',T.duration.mean()/60,'route km',T.route_length.mean()/1000,'waiting s',T.waiting.mean(),'km/h',T.route_length.sum()/T.duration.sum()*3.6,'completed',len(T))
T['h']=(T.depart//3600).astype(int); q=T.groupby('h').agg(n=('duration','size'),dur=('duration',lambda z:z.mean()/60),km=('route_length',lambda z:z.mean()/1000),wait=('waiting','mean')); q['kmh']=T.groupby('h').route_length.sum()/T.groupby('h').duration.sum()*3.6; print(q.round(2).to_string()); q.to_csv(O/'cars_trips_by_depart_hour.csv')
print('duration minus free-flow by departure 16-21: see kmh above; share of total delay after 18h',(T.waiting[T.h>=18].sum()/T.waiting.sum()))
e=pd.read_csv(S/'day_edges.csv'); E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str}); idx={k:i for i,k in enumerate(E.edge)}; e=e[e.edge.isin(idx)]; e['i']=e.edge.map(idx); e['h']=(e.begin//3600).astype(int)
n=len(E); juncs=pd.concat([E.fr,E.to]).unique(); jid={k:i for i,k in enumerate(juncs)}; a=E.fr.map(jid).values; b=E.to.map(jid).values
sp=E.speed.values; L=E.length.values; shapes=json.loads((C/'shapes.json').read_text()); 
mid=np.array([np.array([list(map(float,q.split(',')))[:2] for q in shapes[k].split()]).mean(axis=0) for k in E.edge]); centre=np.array([17063.,19000.])
tele=e.groupby('i').teleports.sum().sort_values(ascending=False); tt=tele.sum(); print('teleport total',tt,'edges with any',int((tele>0).sum()),'top 1 %',tele.iloc[0]/tt,'top 10',tele.iloc[:10].sum()/tt,'top 100',tele.iloc[:100].sum()/tt,'top 500',tele.iloc[:500].sum()/tt,'top 1000',tele.iloc[:1000].sum()/tt)
out=[]
for h in range(14,23):
    q=e[e.h==h]; v=q.distance.values/np.maximum(q.samples.values,1); ii=q.i.values; slow=(v<0.25*sp[ii])&(q.samples.values>=3600*.25); cong=np.zeros(n,bool); cong[ii[slow]]=True
    A=coo_matrix((np.ones(cong.sum()),(a[cong],b[cong])),shape=(len(jid),len(jid))); nc,lab=connected_components(A,directed=False)
    lc=lab[a[cong]]; c=np.bincount(lc) if cong.sum() else np.array([0]); km=np.bincount(lc,weights=L[cong])/1000 if cong.sum() else np.array([0.]); big=np.sort(c)[::-1]; top=int(np.argmax(c)); 
    if cong.sum():
        mm=mid[cong][lc==top]; ext=np.percentile(np.linalg.norm(mm-mm.mean(axis=0),axis=1),90)/1000
    else: ext=0
    samp=q.samples.sum(); slow_share=q.samples.values[slow].sum()/samp; out.append(dict(hour=h,cong_edges=int(cong.sum()),cong_km=L[cong].sum()/1000,clusters=int(len(c)),largest_edges=int(big[0]),largest_share=big[0]/max(cong.sum(),1),second=int(big[1]) if len(big)>1 else 0,largest_radius_km=ext,slow_sample_share=slow_share,teleports=int(q.teleports.sum()),teleport_top10_share=q.teleports.nlargest(10).sum()/max(q.teleports.sum(),1)))
P=pd.DataFrame(out); P.to_csv(O/'evening_percolation.csv',index=False,float_format='%.3f'); print(P.round(3).to_string())
tl=e[e.teleports>0]; ty=tl.groupby('h').apply(lambda g:pd.Series(dict(x=(mid[g.i.values,0]*g.teleports).sum()/g.teleports.sum(),y=(mid[g.i.values,1]*g.teleports).sum()/g.teleports.sum(),n=g.teleports.sum(),med_r=np.median(np.linalg.norm(mid[g.i.values]-centre,axis=1))/1000)),include_groups=False); print(ty.round(1).to_string())
print('teleports by class',e.merge(E[['edge','type']],on='edge').groupby('type').teleports.sum().sort_values(ascending=False).head(6).to_dict())
