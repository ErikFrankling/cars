# Is there a cheap demand fix? Static, spatially held-out tests of uniform scaling and route reweighting (route-sampler style).
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree
O=Path('research/truth/berlin-review'); C=O/'cache'; S=Path('research/truth/berlin-snapshot'); DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031')
E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str}); idx={k:i for i,k in enumerate(E.edge)}; loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(','))))
hourly=np.load(O/'static_hourly.npy'); E['static']=hourly.sum(axis=1); shapes=json.loads((C/'shapes.json').read_text())
print('edges with any vehicle',int((E.static>0).sum()),'of',len(E))
# SVZ extras
F=pd.read_csv(O/'svz_match.csv'); F['vkm']=F.L*F.dtv; print('official truck share of vehicle-km on count network',(F.L*F.lkw.fillna(0)).sum()/F.vkm.sum(),'non-null',F.lkw.notna().mean(),'motorway',(F[F.typ=='A'].L*F[F.typ=='A'].lkw.fillna(0)).sum()/F[F.typ=='A'].vkm.sum(),'city',(F[F.typ=='S'].L*F[F.typ=='S'].lkw.fillna(0)).sum()/F[F.typ=='S'].vkm.sum())
c=np.array([17063.,19000.]); F['r']=np.hypot(F.cx-c[0],F.cy-c[1])/1000; ok=F.cover>=.8
for typ in 'AS':
    for a,b in [(0,6),(6,10),(10,14),(14,18),(18,40)]:
        q=F[ok&(F.typ==typ)&(F.r>=a)&(F.r<b)]
        if len(q): print(f'radial {typ} {a}-{b} km links={len(q)} km={q.L.sum()/1000:.1f} real_Mkm={q.vkm.sum()/1e9:.2f} static/real={(q.L*q.static).sum()/q.vkm.sum():.3f}')
print(F[ok&(F.typ=='A')].assign(ratio=lambda z:z.static/z.dtv).groupby('name').apply(lambda z:pd.Series(dict(km=z.L.sum()/1000,real=(z.L*z.dtv).sum()/z.L.sum(),static=(z.L*z.static).sum()/z.L.sum(),ratio=(z.L*z.static).sum()/(z.L*z.dtv).sum())),include_groups=False).query('km>1').round(2).to_string())
# ratio at detector sites: how unusual is a good fit?
D=pd.read_csv(O/'detector_relaxed.csv'); ra=D.static/D.real; print('sites',len(D),'ratio within 0.8-1.2',((ra>=.8)&(ra<=1.2)).mean(),'>=1.2',(ra>1.2).mean(),'<0.8',(ra<.8).mean(),'<0.5',(ra<.5).mean(),'quartiles',ra.quantile([.25,.5,.75]).round(3).tolist())
print('published sites', D[D.site.isin(['TE106','TE129','TE452'])].assign(r=lambda z:z.static/z.real)[['site','street','real','static','r']].round(3).to_string())
# Rebuild link to edge table, one pair per link near its middle.
from scipy.spatial import cKDTree as KD
us=(E.pass_lanes>0).values; xy=[];dv=[];ii=[]
for i,e in enumerate(E.edge):
    if not us[i]: continue
    p=np.array([list(map(float,q.split(',')))[:2] for q in shapes[e].split()])
    for a,b in zip(p[:-1],p[1:]):
        n=max(1,int(np.ceil(np.linalg.norm(b-a)/15)))
        for j in range(n): xy.append(a+(b-a)*(j+.5)/n); dv.append(b-a); ii.append(i)
xy=np.array(xy); dv=np.array(dv); dv/=np.maximum(np.linalg.norm(dv,axis=1,keepdims=True),1e-9); ii=np.array(ii); T=KD(xy); lnk=E.type.str.contains('_link').values
g=json.load(open(DL/'dtvw2019kfz.geojson')); pairs={}
for f in g['features']:
    P=f['properties']; l=np.array(max(f['geometry']['coordinates'],key=len))[:,:2]+off; seg=np.linalg.norm(np.diff(l,axis=0),axis=1); cum=np.concatenate(([0],np.cumsum(seg))); v=cum[-1]/2; k=min(np.searchsorted(cum,v,side='right')-1,len(seg)-1); d=(l[k+1]-l[k])/max(seg[k],1e-9); q=l[k]+d*(v-cum[k])
    nb=np.array(T.query_ball_point(q,45 if P['str_typ']=='A' else 30),dtype=int)
    if len(nb)==0: continue
    co=dv[nb]@d; par=np.abs(co)>=np.cos(np.radians(25)); nb=nb[par]; co=co[par]
    if len(nb)==0: continue
    dd=np.linalg.norm(xy[nb]-q,axis=1); li=lnk[ii[nb]]
    if (~li).any(): nb,co,dd=nb[~li],co[~li],dd[~li]
    if P['vricht']=='B':
        ch=[]
        for s in (1,-1):
            m=np.where(np.sign(co)==s)[0]
            if len(m): ch.append(int(ii[nb[m[np.argmin(dd[m])]]]))
    else: ch=[int(ii[nb[np.argmin(dd)]])]
    pairs[P['elem_nr']]=ch
F=F[F.elem.isin(pairs)&ok].reset_index(drop=True); edge_link=[(e,l) for l,el in enumerate(F.elem) for e in pairs[el]]; print('links in fit',len(F))
Be=csr_matrix((np.ones(len(edge_link)),([a for a,_ in edge_link],[b for _,b in edge_link])),shape=(len(E),len(F)))
# Route sample
off_r=np.load(C/'route_off.npy'); R=np.memmap(C/'routes.i32',dtype=np.int32,mode='r'); nr=len(off_r)-1; sel=np.arange(0,nr,10); rows=[];cols=[]
inset=np.asarray(Be.sum(axis=1)).ravel()>0
for k,r in enumerate(sel):
    z=R[off_r[r]:off_r[r+1]]; z=z[inset[z]]
    if len(z): rows.append(np.full(len(z),k,dtype=np.int32)); cols.append(np.asarray(z))
rows=np.concatenate(rows); cols=np.concatenate(cols); Rr=csr_matrix((np.ones(len(rows),dtype=np.float32),(rows,cols)),shape=(len(sel),len(E))); A=(Be.T@Rr.T).tocsr(); print('A',A.shape,A.nnz)
meta=np.load(C/'route_meta.npy')[sel]; rlen=meta[:,4]; target=F.dtv.values.astype(float)
blk=(F.cx//3000).astype(int).astype(str)+'_'+(F.cy//3000).astype(int).astype(str); ub=blk.unique(); rng=np.random.default_rng(7); fold=dict(zip(ub,rng.integers(0,5,len(ub)))); fo=blk.map(fold).values
def metrics(p,o,l):
    k=(o>0); r=p[k]/np.maximum(o[k],1); ss=1-((p[k]-o[k])**2).sum()/((o[k]-o[k].mean())**2).sum(); gh=np.sqrt(2*(p[k]-o[k])**2/np.maximum(p[k]+o[k],1)); return dict(vkm_ratio=(l[k]*p[k]).sum()/(l[k]*o[k]).sum(),r2=ss,mal=np.median(np.abs(np.log(np.maximum(r,1e-3)))),geh10=(gh<10).mean(),geh20=(gh<20).mean(),corr=np.corrcoef(p[k],o[k])[0,1])
# detector sites held out entirely: real counts, 2024
sd=D[D.edge.isin(idx)].copy(); sd['e']=sd.edge.map(idx); sites=csr_matrix((np.ones(len(sd)),(sd.e.values,np.arange(len(sd)))),shape=(len(E),len(sd))); inset2=np.asarray(sites.sum(axis=1)).ravel()>0
rows2=[];cols2=[]
for k,r in enumerate(sel):
    z=R[off_r[r]:off_r[r+1]]; z=z[inset2[z]]
    if len(z): rows2.append(np.full(len(z),k,dtype=np.int32)); cols2.append(np.asarray(z))
Rs=csr_matrix((np.ones(sum(map(len,rows2)),dtype=np.float32),(np.concatenate(rows2),np.concatenate(cols2))),shape=(len(sel),len(E))); As=(sites.T@Rs.T).tocsr(); ob=sd.real.values
res=[]; allw=np.zeros((5,len(sel)))
base=np.asarray(A.sum(axis=1)).ravel()*10; print('base all',metrics(base,target,F.L.values))
for fd in range(5):
    tr=fo!=fd; te=~tr; Atr=A[tr]; t=target[tr]; good=t>0
    Atr=Atr[good]; t=t[good]; pre=np.asarray(Atr.sum(axis=1)).ravel()*10; k=(pre*t).sum()/(pre*pre).sum(); kv=(F.L.values[tr][good]*t).sum()/(F.L.values[tr][good]*pre).sum()
    w=np.ones(len(sel)); cnt=np.asarray(Atr.sum(axis=0)).ravel(); At=Atr.T.tocsr()
    for it in range(40):
        p=Atr@w*10; rho=np.clip(t/np.maximum(p,1),.25,4); w*=np.exp(.7*(At@np.log(rho))/np.maximum(cnt,1)); w=np.clip(w,0,25)
    allw[fd]=w; ph=A[te]@w*10; ob0=A[te]@np.ones(len(sel))*10; L=F.L.values[te]; o=target[te]
    sdb=As@np.ones(len(sel))*10; sdf=As@w*10
    res.append(dict(fold=fd,links=int(te.sum()),k_ls=k,k_vkm=kv,trip_mult=w.mean(),vkm_mult=(w*rlen).sum()/rlen.sum(),wmax=np.quantile(w,.999),**{'base_'+a:b for a,b in metrics(ob0,o,L).items()},**{'scale_'+a:b for a,b in metrics(ob0*kv,o,L).items()},**{'fit_'+a:b for a,b in metrics(ph,o,L).items()},det_base_ratio=sdb.sum()/ob.sum(),det_base_corr=np.corrcoef(sdb,ob)[0,1],det_scale_ratio=(sdb*kv).sum()/ob.sum(),det_fit_ratio=sdf.sum()/ob.sum(),det_fit_corr=np.corrcoef(sdf,ob)[0,1],det_base_mal=np.median(np.abs(np.log(np.maximum(sdb,1)/ob))),det_scale_mal=np.median(np.abs(np.log(np.maximum(sdb*kv,1)/ob))),det_fit_mal=np.median(np.abs(np.log(np.maximum(sdf,1)/ob)))))
Z=pd.DataFrame(res); Z.to_csv(O/'fix_holdout.csv',index=False,float_format='%.4f'); print(Z.mean(numeric_only=True).round(3).to_string()); print(Z[['fold','links','k_vkm','trip_mult','vkm_mult','scale_r2','fit_r2','scale_mal','fit_mal','scale_geh10','fit_geh10','det_scale_mal','det_fit_mal']].round(3).to_string())
# capacity: static hourly load against the audited saturation capacity per edge
cap=pd.read_csv(Path('research/truth/berlin-map-link-capacity.csv')); print(cap.columns.tolist()); cg=cap.groupby('edge').agg(cap=('cap_Gg_vph','sum'),signal=('signalised','max')); cv=E.edge.map(cg.cap).values; print('edges with capacity',np.isfinite(cv).mean())
hh=hourly.astype(float); mx=hh.max(axis=1); sim=np.isfinite(cv)&(mx>=200)
vc=[]
for k in (1,1.25,1.5,1.75,2.0):
    over=(hh[sim]*k/cv[sim,None]>=1); vc.append(dict(k=k,edges_any_hour_over=int(over.any(axis=1).sum()),edge_hours_over=int(over.sum()),km_over_peak=E.length.values[sim][over.any(axis=1)].sum()/1000,veh_over_share=(hh[sim][over]*k).sum()/(hh[sim]*k).sum()))
pd.DataFrame(vc).to_csv(O/'capacity_scaling.csv',index=False); print(pd.DataFrame(vc).round(3).to_string(),'edges tested',int(sim.sum()))
pv=pd.read_csv(O/'detector_all_hourly.csv'); pm=pv.groupby('site').real.max(); da=D.assign(peak=D.site.map(pm),cap=D.edge.map(cg.cap),sig=D.edge.map(cg.signal)); da=da[da.cap.notna()]; da['pc']=da.peak/da.cap; print('real peak-hour flow / model edge capacity: median',da.pc.median(),'p90',da.pc.quantile(.9),'share>1',(da.pc>1).mean(),'n',len(da),'static peak/cap median',(E.set_index('edge').loc[da.edge].static.values/24*2/da.cap.values).mean())
# hourly factors: real/cars and real/static at fixed sites, target profile implied
cmp=pd.read_csv(S/'balanced_compare.csv'); hb=cmp.groupby('hour')[['real','cars']].sum(); hb['factor']=hb.real/hb.cars; print(hb.round(2).to_string()); dm=pd.read_csv(S/'demand_hourly.csv').set_index('hour').departures; hb['best_dep']=dm; hb['implied_dep']=dm*hb.factor; print('implied daily departures',hb.implied_dep.sum(),'am peak h',hb.implied_dep.idxmax(), hb.implied_dep.round(0).astype(int).tolist()); hb.to_csv(O/'hourly_factors.csv',float_format='%.3f')
