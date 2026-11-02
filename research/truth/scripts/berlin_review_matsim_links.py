# MATSim v5.5.3 10% link volumes x10 against the official count network, cordons and detectors, using the BeST comparison method.
import os,json,gzip
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from lxml import etree
from pyproj import Transformer
from scipy.spatial import cKDTree
O=Path('research/truth/berlin-review'); S=Path('research/truth/berlin-snapshot'); DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031'); M=DL/'matsim'
loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(',')))); tr=Transformer.from_crs('EPSG:31468',loc['projParameter'],always_xy=True)
nodes={}; links=[]
with gzip.open(M/'berlin-v5.5.3-10pct.output_network.xml.gz','rb') as f:
    for _,x in etree.iterparse(f,events=('end',),tag=('node','link'),resolve_entities=False,no_network=True,load_dtd=False,dtd_validation=False):
        if x.tag=='node': nodes[x.get('id')]=(float(x.get('x')),float(x.get('y')))
        else:
            if 'car' in x.get('modes','').split(','): links.append((x.get('id'),x.get('from'),x.get('to'),float(x.get('length')),float(x.get('capacity')),float(x.get('permlanes'))))
        x.clear()
        while x.getprevious() is not None: del x.getparent()[0]
L=pd.DataFrame(links,columns=['id','fr','to','length','cap','lanes']); print('car links',len(L))
st=pd.read_csv(M/'berlin-v5.5.3-10pct.500.linkstats.txt.gz',sep='\t',usecols=['LINK','HRS0-24avg'],dtype={'LINK':str}); L=L.merge(st,left_on='id',right_on='LINK'); L['v']=L['HRS0-24avg']*10; print('link km x10 Mkm all',(L.length*L.v).sum()/1e9)
tp=np.array([nodes[a] for a in L.fr]); tq=np.array([nodes[a] for a in L.to]); x,y=tr.transform(tp[:,0],tp[:,1]); P=np.c_[x,y]+off; x,y=tr.transform(tq[:,0],tq[:,1]); Q=np.c_[x,y]+off
xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(',')); k=((P[:,0]>xmin-25000)&(P[:,0]<xmax+25000)&(P[:,1]>ymin-25000)&(P[:,1]<ymax+25000)); L=L[k].reset_index(drop=True); P=P[k]; Q=Q[k]
xy=[];dv=[];ii=[]
for i,(a,b) in enumerate(zip(P,Q)):
    n=max(1,int(np.ceil(np.linalg.norm(b-a)/15))); d=(b-a)/max(np.linalg.norm(b-a),1e-9)
    for j in range(n): xy.append(a+(b-a)*(j+.5)/n); dv.append(d); ii.append(i)
xy=np.array(xy);dv=np.array(dv);ii=np.array(ii);T=cKDTree(xy);print('pieces',len(xy))
V=L.v.values
g=json.load(open(DL/'dtvw2019kfz.geojson')); rows=[]; geoms=[]
for f in g['features']:
    pr=f['properties']; lines=[np.array(c)[:,:2]+off for c in f['geometry']['coordinates']]; pts=[];tan=[]; Lf=0
    for l in lines:
        seg=np.linalg.norm(np.diff(l,axis=0),axis=1); cum=np.concatenate(([0],np.cumsum(seg))); tot=cum[-1]; Lf+=tot
        if tot<=0: continue
        for v in np.arange(min(15,tot/2),max(tot-14.9,min(15,tot/2)+.1),30):
            k=min(np.searchsorted(cum,v,side='right')-1,len(seg)-1); d=(l[k+1]-l[k])/max(seg[k],1e-9); pts.append(l[k]+d*(v-cum[k])); tan.append(d)
    if not pts: continue
    pts=np.array(pts);tan=np.array(tan); vals=[]
    R=45 if pr['str_typ']=='A' else 30
    for q,t,nb in zip(pts,tan,T.query_ball_point(pts,R)):
        nb=np.array(nb,dtype=int)
        if len(nb)==0: continue
        co=dv[nb]@t; par=np.abs(co)>=np.cos(np.radians(25)); nb=nb[par]; co=co[par]
        if len(nb)==0: continue
        d=np.linalg.norm(xy[nb]-q,axis=1)
        if pr['vricht']=='B':
            s=0;hit=False
            for sign in (1,-1):
                m=np.where(np.sign(co)==sign)[0]
                if len(m): s+=V[ii[nb[m[np.argmin(d[m])]]]]; hit=True
            if hit: vals.append(s)
        else: vals.append(V[ii[nb[np.argmin(d)]]])
    rows.append(dict(elem=pr['elem_nr'],typ=pr['str_typ'],name=pr['str_name'],vricht=pr['vricht'],dtv=pr['dtvw_kfz'],L=Lf,samples=len(pts),hit=len(vals),matsim=np.median(vals) if vals else np.nan,cx=pts[:,0].mean(),cy=pts[:,1].mean())); geoms.append(lines)
F=pd.DataFrame(rows); F['cover']=F.hit/F.samples; F.to_csv(O/'svz_matsim.csv',index=False,float_format='%.2f'); ok=F.cover>=.8; print('cover>=.8 km share',F[ok].L.sum()/F.L.sum())
def rep(q,l): r=(q.L*q.dtv).sum(); s=(q.L*q.matsim).sum(); print(f'{l:32s} n={len(q):5d} real_Mkm={r/1e9:6.2f} matsim_x10_Mkm={s/1e9:6.2f} ratio={s/r:.3f}')
rep(F[ok],'all matched'); 
for t,q in F[ok].groupby('typ'): rep(q,t)
for t,q in F[ok&(F.typ=='A')].groupby('name'):
    if q.L.sum()>2000: rep(q,t[:32])
c=np.array([17063.,19000.]); F['r']=np.hypot(F.cx-c[0],F.cy-c[1])/1000
for a,b in [(0,6),(6,10),(10,14),(14,18),(18,40)]: rep(F[ok&(F.typ=='S')&(F.r>=a)&(F.r<b)],f'S {a}-{b} km')
S2=pd.read_csv(O/'svz_match.csv')[['elem','static','cars','cover']]; X=F[ok].merge(S2,on='elem'); q=X[(X.dtv>0)&(X.cover_y>=.8)] if 'cover_y' in X else X[X.dtv>0]; print('static/matsim VKT on common links',(q.L*q.static).sum()/(q.L*q.matsim).sum(),'median link static/matsim',(q.static/q.matsim.clip(lower=1)).median(),'matsim r2',1-((q.matsim-q.dtv)**2).sum()/((q.dtv-q.dtv.mean())**2).sum(),'corr',np.corrcoef(q.matsim,q.dtv)[0,1],'static r2',1-((q.static-q.dtv)**2).sum()/((q.dtv-q.dtv.mean())**2).sum(),'corr',np.corrcoef(q.static,q.dtv)[0,1],'mal',np.median(np.abs(np.log(q.matsim.clip(lower=1)/q.dtv))),'static mal',np.median(np.abs(np.log(q.static.clip(lower=1)/q.dtv))))
m=pd.read_csv(S/'metadata_det.csv',dtype=str); DIR=dict(zip(['Nord','Nordost','Ost','Südost','Süd','Südwest','West','Nordwest'],range(0,360,45))); tw=Transformer.from_crs('EPSG:4326',loc['projParameter'],always_xy=True); site=m.groupby('A').first()
D=pd.read_csv(O/'detector_relaxed.csv'); vals=[]
for s,r in site.loc[D.site].iterrows():
    z=np.array(tw.transform(float(r.L),float(r.M)))+off; nb=np.array(T.query_ball_point(z,45),dtype=int)
    if len(nb)==0: vals.append(np.nan); continue
    br=np.degrees(np.arctan2(dv[nb,0],dv[nb,1]))%360; ang=np.abs((br-DIR[r.I]+180)%360-180); k=ang<=45
    if not k.any(): vals.append(np.nan); continue
    nb=nb[k]; ang=ang[k]; d=np.linalg.norm(xy[nb]-z,axis=1); vals.append(V[ii[nb[np.argmin(d+.5*ang)]]])
D['matsim']=vals; q=D[D.matsim.notna()]; print('detector sites',len(q),'matsim/real',q.matsim.sum()/q.real.sum(),'static/real',q.static.sum()/q.real.sum(),'median',(q.matsim/q.real).median(),'accepted',q[q.accepted].matsim.sum()/q[q.accepted].real.sum()); D.to_csv(O/'detector_relaxed_matsim.csv',index=False,float_format='%.2f')
print(D[D.site.isin(['TE106','TE129','TE452','TE001','TE002','TE256'])][['site','street','real','static','matsim']].round(0).to_string())
