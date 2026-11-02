"""Open-data demands and the commuting test. usage: build_demands.py in/ sysmo.npz.json OUTDIR"""
import sys,json,struct;sys.path.insert(0,'.')
import numpy as np,gpk,sqlite3,collections as C,assignlib as al
from matplotlib.path import Path
from pyproj import Transformer
from scipy.stats import spearmanr
I=sys.argv[1];OUT=sys.argv[3];OX,OY=al.OX,al.OY
K=json.load(open(I+'kommun.json'))
cm={};
for r in json.load(open(I+'commute_2019.json'))['data']:
    v=r['values'][0]
    if v not in('..','-'): cm[(r['key'][0],r['key'][1])]=int(v)
def tot(p):
    c=C.Counter()
    for r in json.load(open(p))['data']:
        v=r['values'][0]
        if v not in('..','-'): c[r['key'][0]]+=int(v)
    return c
dag=tot(I+'dag_2019.json');nat=tot(I+'natt_2019.json');kl=sorted({a for a,b in cm});ki={k:i for i,k in enumerate(kl)}
print('kommuner',len(kl),'jobs',sum(dag[k] for k in kl if k[:2]=='01'),'workers',sum(nat[k] for k in kl if k[:2]=='01'),flush=True)
rings={};rc=[]
for (k,),rs in gpk.read(I+'DeSO_2018.gpkg',['kommunkod']):
    if k in ki:
        for r in rs:
            rc.append((k,Path(r),r.min(0),r.max(0)))
def kom_of(xy):
    o=np.full(len(xy),-1);
    for k,p,a,b in rc:
        m=(o<0)&(xy[:,0]>=a[0])&(xy[:,0]<=b[0])&(xy[:,1]>=a[1])&(xy[:,1]<=b[1])
        if m.any():
            i=np.where(m)[0];h=p.contains_points(xy[i]);o[i[h]]=ki[k]
    return o
c=sqlite3.connect(I+'befolkning_1km_2018.gpkg');rows=c.execute('select rutid_scb,beftotalt,ald20_24,ald25_29,ald30_34,ald35_39,ald40_44,ald45_49,ald50_54,ald55_59,ald60_64 from befolkning_1km_2018').fetchall()
E=np.array([int(r[0][:6]) for r in rows]);Nn=np.array([int(r[0][6:]) for r in rows]);pop=np.array([r[1] for r in rows],float);wa=np.array([sum(x or 0 for x in r[2:]) for r in rows],float)
xy=np.c_[E+500.,Nn+500.]
print('grid',len(xy),'pop',pop.sum(),flush=True)
BB=(OX,OX+34380,OY,OY+30511)
box=(xy[:,0]>BB[0]-160000)&(xy[:,0]<BB[1]+160000)&(xy[:,1]>BB[2]-200000)&(xy[:,1]<BB[3]+200000);xy,pop,wa=xy[box],pop[box],wa[box]
kc=kom_of(xy);m=kc>=0;print('in kommun set',m.sum(),'unassigned pop',pop[~m].sum(),flush=True);xy,pop,wa,kc=xy[m],pop[m],wa[m],kc[m]
inn=(xy[:,0]>=BB[0])&(xy[:,0]<BB[1])&(xy[:,1]>=BB[2])&(xy[:,1]<BB[3])
# zones: 1 km cells in the net, one zone per kommun beyond it
Z=[];ZK=[];ZP=[];ZW=[];cellz=np.zeros(len(xy),int)
for i in np.where(inn)[0]:
    cellz[i]=len(Z);Z.append(xy[i]);ZK.append(kc[i]);ZP.append(pop[i]);ZW.append(wa[i])
for k in range(len(kl)):
    s=(~inn)&(kc==k)
    if s.any():
        w=pop[s]+1e-6;cellz[s]=len(Z);Z.append((xy[s]*w[:,None]).sum(0)/w.sum());ZK.append(k);ZP.append(pop[s].sum());ZW.append(wa[s].sum())
Z,ZK,ZP,ZW=np.array(Z),np.array(ZK),np.array(ZP),np.array(ZW);nz=len(Z);print('zones',nz,flush=True)
from scipy.spatial import cKDTree
tree=cKDTree(Z)
A=np.zeros(nz);Pj=np.load('poi.npz');pz=np.c_[Pj['x'],Pj['y']]
d,ii=tree.query(pz);nearok=d<3000
jobw=np.bincount(ii[nearok],Pj['job'][nearok],minlength=nz);othw=np.bincount(ii[nearok],Pj['oth'][nearok],minlength=nz)
vo=np.zeros(nz);vk=C.Counter()
for (k,a),rs in gpk.read(I+'Verksamhetsomraden_2020.gpkg',['kommunkod','anstallda']):
    if k in ki and a:
        pt=rs[0].mean(0)-0;zi=tree.query(pt)[1];vo[zi]+=a;vk[k]+=a
for k,kn in enumerate(kl):
    s=ZK==k;r=max(dag[kn]-vk[kn],0)
    if vk[kn]>dag[kn] and vk[kn]>0: vo[s]*=dag[kn]/vk[kn]
    w=jobw[s] if jobw[s].sum()>0 else ZP[s]+1e-6
    A[s]=vo[s]+r*w/w.sum()
dd=np.hypot(Z[:,None,0]-Z[None,:,0],Z[:,None,1]-Z[None,:,1])+500.
WORK=np.zeros(nz)
for k,kn in enumerate(kl):
    s=ZK==k;WORK[s]=nat[kn]*ZW[s]/max(ZW[s].sum(),1)
# G2: gravity to kommun margins only, the fair twin of a learned generator
def ipf(O,D,f,it=40):
    a=np.ones(len(O));b=np.ones(len(D))
    for _ in range(it):
        a=O/np.maximum((f*b).sum(1),1e-12);b=D/np.maximum((f.T*a).sum(1),1e-12)
    return f*a[:,None]*b[None,:]
G2=ipf(WORK,A,np.exp(-dd/10000.))
# G1: same gravity inside each kommun pair, constrained to SCB's register matrix
F=np.zeros((nz,nz));f=A[None,:]*WORK[:,None]*np.exp(-dd/10000.)
idx=[np.where(ZK==k)[0] for k in range(len(kl))]
for (a,b),v in cm.items():
    i,j=idx[ki[a]],idx[ki[b]]
    if len(i)==0 or len(j)==0: continue
    p=f[np.ix_(i,j)];s=p.sum()
    if s>0: F[np.ix_(i,j)]=v*p/s
print('G1 commuters',F.sum(),'county',sum(v for (a,b),v in cm.items() if a[:2]=='01'),flush=True)
# car shares by home area: assumption from RVU's level, not fitted. k absorbs the scale.
tr=Transformer.from_crs('EPSG:3006','EPSG:4326',always_xy=True);lon,lat=tr.transform(Z[:,0],Z[:,1])
inner=(lon>18.012)&(lon<18.12)&(lat>59.307)&(lat<59.372)
core=np.isin(np.array(kl)[ZK],['0180','0184','0183'])
county=np.array([kl[k][:2]=='01' for k in ZK])
pw=np.where(inner,.15,np.where(core,.25,np.where(county,.45,.55)));po=np.where(inner,.18,np.where(core,.3,np.where(county,.5,.6)))
ATT=.8
WF=F*pw[:,None]*ATT
Oth=ZP*po
Ds=(othw+1e-3*ZP/max(ZP.sum(),1)*othw.sum()+.002*ZP);OF=(Ds[None,:]*np.exp(-dd/5000.));OF=OF/OF.sum(1,keepdims=True)*Oth[:,None]
B_OUT=np.array([.06,.55,.20,.10,.09]);B_RET=np.array([.00,.02,.15,.65,.18]);B_OTH=np.array([.01,.12,.45,.30,.12])
def save(name,ms):
    """ms: list of (matrix, bins)"""
    Mt=sum(x for x,_ in ms);nzz=np.argwhere(Mt>1e-4);i,j=nzz[:,0],nzz[:,1]
    w=np.zeros((5,len(i)))
    for x,b in ms: w+=b[:,None]*x[i,j][None,:]
    np.savez_compressed(f'{OUT}/d_{name}.npz',ox=Z[i,0]-OX,oy=Z[i,1]-OY,dx=Z[j,0]-OX,dy=Z[j,1]-OY,w=w);print(name,'trips',w.sum(),flush=True)
save('G1',[(WF,B_OUT),(WF.T,B_RET),(.5*OF,B_OTH),(.5*OF.T,B_OTH)])
save('G1W',[(WF,B_OUT),(WF.T,B_RET)])
g=(ZP[None,:]+1)*np.exp(-dd/6000.);g=g/g.sum(1,keepdims=True)*(ZP[:,None]+1);g=g/g.sum()*(WF.sum()*2+OF.sum());B_ALL=(B_OUT+B_RET+B_OTH*(OF.sum()/WF.sum()))/ (2+OF.sum()/WF.sum())
save('G0',[(g,B_ALL)])
np.savez_compressed(f'{OUT}/zones.npz',Z=Z,ZK=ZK,ZP=ZP,A=A,WORK=WORK,kl=np.array(kl))
# Learned global OD
def shp(path):
    b=open(path,'rb').read();p=100;out=[]
    while p<len(b):
        n,l=struct.unpack('>ii',b[p:p+8]);t,=struct.unpack('<i',b[p+8:p+12])
        if t==5:
            np_,nv=struct.unpack('<ii',b[p+44:p+52]);a=np.frombuffer(b,'<f8',2*nv,p+52+4*np_).reshape(-1,2);out.append(a)
        else: out.append(np.empty((0,2)))
        p+=8+2*l
    return out
T=I+'worldod/';R=shp(T+'CityAndRegionSplit__GHSL-678_SWE_Stockholm__regions.shp');O=np.load(T+'CommutingODFlows__GHSL-678_SWE_Stockholm__generation.npy').astype(float);WP=np.load(T+'GeneratingCodeData__data__GHSL_744__GHSL-678_SWE_Stockholm__nfeat__worldpop.npy')
tf=Transformer.from_crs('EPSG:32634','EPSG:3006',always_xy=True)
Rc=np.array([tf.transform(*r.mean(0)) for r in R]);area=[]
for r in R:
    x,y=r[:,0],r[:,1];area.append(abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))/2e6)
Rk=kom_of(Rc);print('world regions',len(R),'area km2 median',np.median(area),'sum',sum(area),'kommuner',sorted({kl[k] for k in Rk if k>=0}),'outside',(Rk<0).sum(),flush=True)
# population check by polygon against SCB
inv=Transformer.from_crs('EPSG:3006','EPSG:32634',always_xy=True);clon,clat=inv.transform(xy[:,0],xy[:,1]);cl=np.c_[clon,clat];scb=np.array([pop[Path(r).contains_points(cl)].sum() for r in R])
print('worldpop feature totals',WP.sum(0),'SCB in same polygons',scb.sum(),'corr',np.corrcoef(WP[:,0],scb)[0,1],'spearman',spearmanr(WP[:,0],scb)[0],'ratio median',np.median(WP[:,0]/np.maximum(scb,1)),flush=True)
print('worldpop col1 corr',np.corrcoef(WP[:,1],scb)[0,1],'col0/area',np.median(WP[:,0]/np.maximum(area,1e-3)),'col0 corr log',np.corrcoef(np.log1p(WP[:,0]),np.log1p(scb))[0,1],flush=True);print('world od total',O.sum(),'row sums vs scb workers corr',np.corrcoef(O.sum(1),scb)[0,1],'col sums top regions',np.argsort(-O.sum(0))[:5],flush=True)
oq=O*.35*.8;ms=[(oq,B_OUT),(oq.T,B_RET)];Mt=oq;nn=np.argwhere(Mt>1e-4);i,j=nn[:,0],nn[:,1];w=np.zeros((5,len(i)))
for x,b in ms: w+=b[:,None]*x[i,j][None,:]
np.savez_compressed(f'{OUT}/d_W.npz',ox=Rc[i,0]-OX,oy=Rc[i,1]-OY,dx=Rc[j,0]-OX,dy=Rc[j,1]-OY,w=w)
# Commuting test against SCB's register matrix, kommun by kommun
n=len(kl);truth=np.zeros((n,n))
for (a,b),v in cm.items(): truth[ki[a],ki[b]]=v
S=json.load(open(sys.argv[2]));sm=np.zeros((n,n));sc=np.zeros((n,n))
for key,v in S['cm'].items():
    a,b=key.split('|')
    if a in ki and b in ki: sm[ki[a],ki[b]]=v
for key,v in S['cmcar'].items():
    a,b=key.split('|')
    if a in ki and b in ki: sc[ki[a],ki[b]]=v
def agg(M,zk):
    o=np.zeros((n,n));np.add.at(o,(np.repeat(zk,len(zk)),np.tile(zk,len(zk))),M.ravel());return o
g2k=agg(G2,ZK);gpop=agg(g*1.0,ZK)
wk=np.zeros((n,n));ok=Rk>=0
for i_ in np.where(ok)[0]:
    for j_ in np.where(ok)[0]:
        wk[Rk[i_],Rk[j_]]+=O[i_,j_]
def cpc(a,b):
    a=a/a.sum();b=b/b.sum();return float(2*np.minimum(a,b).sum()/(a.sum()+b.sum()))
def met(a,b,mask):
    x,y=a[mask],b[mask];sel=(x>0)|(y>0);return dict(cpc=round(cpc(x,y),3),spearman=round(float(spearmanr(x[sel],y[sel])[0]),3),r2_log=round(float(np.corrcoef(np.log1p(x[sel]),np.log1p(y[sel]))[0,1]**2),3),share_ratio=round(float(x.sum()/y.sum()),3))
cc=np.array([k[:2]=='01' for k in kl]);m1=np.outer(cc,cc);off=~np.eye(n,dtype=bool)
wset=np.zeros(n,bool);wset[np.unique(Rk[ok])]=True;m2=np.outer(wset,wset)
res={}
for nm,M in dict(sysmo_all=sm,gravity_margins=g2k,gravity_pop_only=gpop,global_learned=wk).items():
    res[nm]=dict(county_with_diag=met(M,truth,m1),county_off_diag=met(M,truth,m1&off),world_set_off_diag=met(M,truth,m2&off),world_set_with_diag=met(M,truth,m2))
    print(nm,json.dumps(res[nm]),flush=True)
print('world set kommuner',wset.sum(),'share of county commuters in set',truth[m2].sum()/truth[m1].sum())
res['meta']=dict(sysmo_car_share_of_workers_county=float(sc[m1].sum()/sm[m1].sum()),sysmo_workers_county=float(sm[m1].sum()),scb_workers_county=float(truth[m1].sum()),world_total=float(O.sum()),world_set=[kl[i] for i in np.where(wset)[0]])
k0=ki['0180'];to=np.argsort(-truth[:,k0])[:8]
res['top_to_stockholm']=[dict(k=K[kl[i]],scb=int(truth[i,k0]),sysmo=int(sm[i,k0]),world=int(wk[i,k0]),grav=int(g2k[i,k0])) for i in to]
json.dump(res,open(f'{OUT}/commute_test.json','w'),indent=1);print(json.dumps(res['meta'])[:400],res['top_to_stockholm'])
pop_k=S['pop'];tk=S['cartrips'];cty=[k for k in pop_k if k[:2]=='01']
print('sysmo county pop',sum(pop_k[k] for k in cty),'car trips by origin kommun',sum(tk.get(k,0) for k in cty),'km straight',sum(S['tripkm'].get(k,0) for k in cty),'stockholm car trips/person',tk.get('0180',0)/pop_k['0180'],'county',sum(tk.get(k,0) for k in cty)/sum(pop_k[k] for k in cty));print(S['mode'],S['purp']);print(sorted((int(a),b) for a,b in S['hours'].items()))
