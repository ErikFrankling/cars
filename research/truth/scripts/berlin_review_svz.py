# Compares static BeST demand and the cars day run with the official 2019 count network, cordons and all detector sites.
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
O=Path('research/truth/berlin-review'); C=O/'cache'; S=Path('research/truth/berlin-snapshot'); DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031')
E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str}); shapes=json.loads((C/'shapes.json').read_text()); loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(','))))
E['static']=np.load(O/'static_hourly.npy').sum(axis=1); E['bus']=np.load(O/'static_bus.npy')
cars=pd.read_csv(S/'day_edges.csv',usecols=['edge','entered','distance','teleports']); ca=cars.groupby('edge').agg(cars=('entered','sum'),cars_m=('distance','sum')); E=E.merge(ca,left_on='edge',right_index=True,how='left').fillna({'cars':0,'cars_m':0})
E['linkish']=E.type.str.contains('_link'); E['vkm']=E.static*E.length/1000
print('static ext km',E.vkm.sum(),'cars ext km',E.cars_m.sum()/1000)
print((E.groupby('type').agg(km_net=('length',lambda z:z.sum()/1000),edges=('edge','size'),vkm=('vkm','sum')).assign(share=lambda t:t.vkm/t.vkm.sum())).sort_values('vkm',ascending=False).head(16).round(3).to_string()); 
# pieces
xy=[];dv=[];ii=[]
usable=(E.pass_lanes>0).values
parsed={}
for i,e in enumerate(E.edge):
    p=np.array([list(map(float,q.split(',')))[:2] for q in shapes[e].split()]); parsed[i]=p
    if not usable[i]: continue
    for a,b in zip(p[:-1],p[1:]):
        n=max(1,int(np.ceil(np.linalg.norm(b-a)/15)))
        for j in range(n):
            xy.append(a+(b-a)*(j+.5)/n); dv.append(b-a); ii.append(i)
xy=np.array(xy); dv=np.array(dv); dv/=np.maximum(np.linalg.norm(dv,axis=1,keepdims=True),1e-9); ii=np.array(ii); T=cKDTree(xy); print('pieces',len(xy))
g=json.load(open(DL/'dtvw2019kfz.geojson')); lk={f['properties']['elem_nr']:f['properties'].get('dtvw_lkw') for f in json.load(open(DL/'dtvw2019lkw.geojson'))['features']}
rows=[]; fgeom=[]
for f in g['features']:
    P=f['properties']; lines=[np.array(c)[:,:2]+off for c in f['geometry']['coordinates']]; L=sum(np.linalg.norm(np.diff(l,axis=0),axis=1).sum() for l in lines)
    pts=[];tan=[]
    for l in lines:
        seg=np.linalg.norm(np.diff(l,axis=0),axis=1); cum=np.concatenate(([0],np.cumsum(seg))); tot=cum[-1]
        if tot<=0: continue
        s=np.arange(min(15,tot/2),max(tot-14.9,min(15,tot/2)+.1),30)
        for v in s:
            k=min(np.searchsorted(cum,v,side='right')-1,len(seg)-1); d=(l[k+1]-l[k])/max(seg[k],1e-9); pts.append(l[k]+d*(v-cum[k])); tan.append(d)
    if not pts: continue
    pts=np.array(pts); tan=np.array(tan); vals=[];vc=[];hit=0;edges=set();both=0
    R=45 if P['str_typ']=='A' else 30
    for q,t,nb in zip(pts,tan,T.query_ball_point(pts,R)):
        nb=np.array(nb,dtype=int)
        if len(nb)==0: continue
        co=dv[nb]@t; par=np.abs(co)>=np.cos(np.radians(25)); nb=nb[par]; co=co[par]
        if len(nb)==0: continue
        d=np.linalg.norm(xy[nb]-q,axis=1); lnk=E.linkish.values[ii[nb]]
        if (~lnk).any(): nb,co,d=nb[~lnk],co[~lnk],d[~lnk]
        chosen=[]
        if P['vricht']=='B':
            for sign in (1,-1):
                m=np.where(np.sign(co)==sign)[0]
                if len(m): chosen.append(ii[nb[m[np.argmin(d[m])]]])
        else: chosen.append(ii[nb[np.argmin(d)]])
        if chosen:
            hit+=1; vals.append(E.static.values[chosen].sum()); vc.append(E.cars.values[chosen].sum()); both+=len(chosen)==2; edges.update(chosen)
    rows.append(dict(elem=P['elem_nr'],name=P['str_name'],bezirk=P['bezirk'],stadtteil=P['stadtteil'],typ=P['str_typ'],vricht=P['vricht'],klasse=P['strklasse1'],dtv=P['dtvw_kfz'],lkw=lk.get(P['elem_nr']),L=L,samples=len(pts),hit=hit,both=both,static=np.median(vals) if vals else np.nan,cars=np.median(vc) if vc else np.nan,cx=pts[:,0].mean(),cy=pts[:,1].mean()))
    fgeom.append(lines)
F=pd.DataFrame(rows); F['cover']=F.hit/F.samples; F.to_csv(O/'svz_match.csv',index=False,float_format='%.2f')
A=np.load(O/'best_area_mask.npy') if (O/'best_area_mask.npy').exists() else None
print('features',len(F),'km',F.L.sum()/1000,'real Mkm/day',(F.L*F.dtv).sum()/1e9,'of which A',(F[F.typ=='A'].L*F[F.typ=='A'].dtv).sum()/1e9)
print('SVZ Table 4 implied days: count net',7268.4e6/((F.L*F.dtv).sum()/1000),'BAB',1837.7e6/((F[F.typ=='A'].L*F[F.typ=='A'].dtv).sum()/1000),'city',5430.7e6/((F[F.typ=='S'].L*F[F.typ=='S'].dtv).sum()/1000))
ok=F.cover>=.8
print('well matched km share',F[ok].L.sum()/F.L.sum(),'real vkm share',(F[ok].L*F[ok].dtv).sum()/(F.L*F.dtv).sum())
def rep(q,lab):
    r=(q.L*q.dtv).sum(); s=(q.L*q.static.fillna(0)).sum(); c=(q.L*q.cars.fillna(0)).sum(); print(f'{lab:34s} n={len(q):5d} km={q.L.sum()/1000:7.1f} real_Mkm={r/1e9:6.2f} static_Mkm={s/1e9:6.2f} cars_Mkm={c/1e9:6.2f} static/real={s/r:.3f} cars/real={c/r:.3f}')
rep(F,'all features (unmatched=0)'); rep(F[ok],'cover>=0.8')
for t,q in F[ok].groupby('typ'): rep(q,'typ '+t)
for t,q in F[ok].groupby('klasse'): rep(q,'class '+t)
for t,q in F[ok].groupby('vricht'): rep(q,'vricht '+t)
for lo,hi in [(0,10000),(10000,20000),(20000,30000),(30000,40000),(40000,60000),(60000,200000)]: rep(F[ok&(F.dtv>=lo)&(F.dtv<hi)],f'dtv {lo}-{hi}')
for t,q in F[ok].groupby('bezirk'): rep(q,'bezirk '+t)
# bootstrap by feature groups, median link ratio
q=F[ok&(F.dtv>0)]; rng=np.random.default_rng(1); r=[]
for _ in range(2000):
    z=q.iloc[rng.integers(0,len(q),len(q))]; r.append((z.L*z.static).sum()/(z.L*z.dtv).sum())
print('static/real VKT bootstrap 95%',np.percentile(r,[2.5,97.5]),'median link ratio',(q.static/q.dtv).median(),'iqr',(q.static/q.dtv).quantile([.25,.75]).values)
geh=np.sqrt(2*(q.static-q.dtv)**2/(q.static+q.dtv).clip(lower=1)); print('daily GEH<10 share static',(geh<10).mean(),'<30',(geh<30).mean(),'R2 through origin',1-((q.static-q.dtv)**2).sum()/((q.dtv-q.dtv.mean())**2).sum(),'slope',(q.static*q.dtv).sum()/(q.dtv**2).sum())
# shares of VKT
used=set()
print('BeST VKT by class share: motorway+link',E[E.type.str.contains('motorway')].vkm.sum()/E.vkm.sum(),'trunk/primary/secondary+links',E[E.type.str.contains('trunk|primary|secondary')].vkm.sum()/E.vkm.sum(),'tertiary',E[E.type.str.contains('tertiary')].vkm.sum()/E.vkm.sum(),'residential+other',E[~E.type.str.contains('motorway|trunk|primary|secondary|tertiary')].vkm.sum()/E.vkm.sum())
print('Static VKT on matched count network',(F[ok].L*F[ok].static).sum()/1e9,'share of static external',(F[ok].L*F[ok].static).sum()/1e6/E.vkm.sum())
# cordons and screenlines: real counts only the main network, simulation counts every road, so the ratio is an upper bound
fx=loc; tr=Transformer.from_crs('EPSG:4326',loc['projParameter'],always_xy=True); c=np.array(tr.transform(13.4050,52.5200))+off
def crossings_circle(p,r):
    d=np.linalg.norm(p-c,axis=1)-r; return np.sum(np.sign(d[:-1])*np.sign(d[1:])<0)
def crossings_line(p,axis,v):
    d=p[:,axis]-v; return np.sum(np.sign(d[:-1])*np.sign(d[1:])<0)
Ep=[parsed[i] for i in range(len(E))]; sv=E.static.values; cv=E.cars.values; real=F.dtv.values
out=[]
for kind,val in [('circle',r) for r in (3000,5000,7000,9000,11000,13000)]+[('x',c[0]+d) for d in (-12000,-8000,-4000,0,4000,8000)]+[('y',c[1]+d) for d in (-9000,-6000,-3000,0,3000,6000,9000)]:
    fn=(lambda p:crossings_circle(p,val)) if kind=='circle' else (lambda p:crossings_line(p,0 if kind=='x' else 1,val))
    rv=sum(min(1,sum(fn(l) for l in ls))*d for ls,d in zip(fgeom,real)); sc=0.;cc=0.;mn=0.
    for i,p in enumerate(Ep):
        if len(p)<2 or sv[i]==0: continue
        n=fn(p)
        if n:
            sc+=sv[i]*n; cc+=cv[i]*n
            if not E.type.values[i].startswith(('highway.resid','highway.living','highway.unclass','highway.service')): mn+=sv[i]*n
    out.append(dict(kind=kind,val=round(val),real_svz=rv,static_all_roads=sc,static_main_roads=mn,cars_all_roads=cc,ratio_all=sc/rv,ratio_main=mn/rv))
o=pd.DataFrame(out); o.to_csv(O/'cordons.csv',index=False,float_format='%.3f'); print(o.round(3).to_string()); print('cordon ratio all roads: median',o.ratio_all.median(),'range',o.ratio_all.min(),o.ratio_all.max())
# detector sites, relaxed match
m=pd.read_csv(S/'metadata_det.csv',dtype=str); DIR=dict(zip(['Nord','Nordost','Ost','Südost','Süd','Südwest','West','Nordwest'],range(0,360,45)))
tw=Transformer.from_crs('EPSG:4326',loc['projParameter'],always_xy=True); site=m.groupby('A').first(); nl=m.groupby('A').size()
pv=pd.read_csv(O/'detector_all_hourly.csv'); full=pv.groupby('site').hour.nunique(); fs=full[full==24].index; day=pv[pv.site.isin(fs)].groupby('site').agg(real=('real','sum'),pkw=('pkw','sum'),lkw=('lkw','sum'))
dm=pd.read_csv(S/'detector_map.csv').set_index('site'); acc=set(dm[dm.quality=='accepted'].index)
fc=cKDTree(F[['cx','cy']].values); rs=[]
for s,r in site.iterrows():
    xyz=np.array(tw.transform(float(r.L),float(r.M)))+off; nb=np.array(T.query_ball_point(xyz,40),dtype=int)
    if len(nb)==0: continue
    b=DIR[r.I]; br=np.degrees(np.arctan2(dv[nb,0],dv[nb,1]))%360; ang=np.abs((br-b+180)%360-180); k=ang<=45; 
    if not k.any(): continue
    nb=nb[k]; ang=ang[k]; d=np.linalg.norm(xy[nb]-xyz,axis=1); lnk=E.linkish.values[ii[nb]]
    sc=d+.5*ang+1000*lnk; j=np.argmin(sc); e=ii[nb[j]]
    fd,fi=fc.query(xyz,k=8); nm=[x for x in fi if F.name.values[x]==r.F and np.hypot(*(F[['cx','cy']].values[x]-xyz))<300]; sv_dtv=F.dtv.values[nm[0]] if nm else np.nan; sv_v=F.vricht.values[nm[0]] if nm else ''
    rs.append(dict(site=s,street=r.F,dir=r.I,lanes=nl[s],edge=E.edge.values[e],etype=E.type.values[e],edge_lanes=E.pass_lanes.values[e],dist=d[j],accepted=s in acc,static=E.static.values[e],cars=E.cars.values[e],bus=E.bus.values[e],svz_dtv=sv_dtv,svz_v=sv_v,dist_center=np.hypot(*(xyz-c))))
D=pd.DataFrame(rs).merge(day,left_on='site',right_index=True); D.to_csv(O/'detector_relaxed.csv',index=False,float_format='%.2f')
print('detector sites 24h with relaxed edge',len(D),'accepted',int(D.accepted.sum()))
def rd(q,l): print(f'{l:30s} n={len(q):3d} real={q.real.sum():9.0f} static/real={q.static.sum()/q.real.sum():.3f} cars/real={q.cars.sum()/q.real.sum():.3f} median_site={(q.static/q.real).median():.3f} lkw={q.lkw.sum()/q.real.sum():.4f} (static+bus)/real={(q.static.sum()+q.bus.sum())/q.real.sum():.3f}')
rd(D,'all relaxed'); rd(D[D.accepted],'accepted (93-style)'); rd(D[~D.accepted],'rejected, relaxed match'); rd(D[D.edge_lanes==D.lanes],'lanes equal'); rd(D[D.edge_lanes!=D.lanes],'lanes differ')
for t,q in D.groupby('etype'):
    if len(q)>=1: rd(q,t)
for a,b in [(0,4000),(4000,8000),(8000,12000),(12000,16000),(16000,40000)]: rd(D[(D.dist_center>=a)&(D.dist_center<b)],f'center {a}-{b}')
rng=np.random.default_rng(2); br=[]
for _ in range(4000):
    z=D.iloc[rng.integers(0,len(D),len(D))]; br.append(z.static.sum()/z.real.sum())
print('all relaxed static/real boot95',np.percentile(br,[2.5,97.5]))
dd=D[D.svz_dtv.notna()].copy(); dd['exp']=np.where(dd.svz_v=='B',dd.svz_dtv/2,dd.svz_dtv); print('detector 2024 / SVZ 2019 (B halved): n',len(dd),'sum ratio',dd.real.sum()/dd.exp.sum(),'median',(dd.real/dd.exp).median(),'iqr',(dd.real/dd.exp).quantile([.25,.75]).values)
print(D[D.site.isin(['TE106','TE232','TE452','TE503','TE129','TE001','TE002','TE256'])][['site','street','dir','lanes','edge','edge_lanes','etype','accepted','real','lkw','static','cars','bus','svz_dtv','svz_v']].round(0).to_string())
print('A100 Friedenau SVZ:',F[F.name.str.contains('A 100')&F.stadtteil.str.contains('Friedenau|Schöneberg|Wilmersdorf')][['name','stadtteil','vricht','dtv','static','cars','L']].sort_values('stadtteil').round(0).head(30).to_string())
