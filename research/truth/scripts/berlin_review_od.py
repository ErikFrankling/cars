# Where do BeST trips begin and end, compared with MATSim v5.5.3? Tests area filter, sampling and clone structure.
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from pyproj import Transformer
O=Path('research/truth/berlin-review'); C=O/'cache'; DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031/matsim')
E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str}); shapes=json.loads((C/'shapes.json').read_text()); loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(','))))
mid=np.array([np.array([list(map(float,q.split(',')))[:2] for q in shapes[e].split()]).mean(axis=0) for e in E.edge])
M=np.load(C/'route_meta.npy'); dep,fe,le,ne,ln=M[:,0],M[:,1].astype(int),M[:,2].astype(int),M[:,3],M[:,4]
print('BeST depart fractional share',np.mean(dep%1>0),'max depart',dep.max(),'mean ext km',ln.mean()/1000,'median',np.median(ln)/1000,'p90',np.percentile(ln,90)/1000,'p99',np.percentile(ln,99)/1000,'max',ln.max()/1000)
print('distinct start edges',len(np.unique(fe)),'distinct end edges',len(np.unique(le)))
t=pd.read_csv(DL/'berlin-v5.5.3-10pct.output_trips.csv.gz',sep=';',usecols=['dep_time','traveled_distance','main_mode','start_x','start_y','end_x','end_y'])
t=t[t.main_mode.isin(['car','freight'])].copy(); a=t.dep_time.str.split(':',expand=True).astype(int); t['dep']=a[0]*3600+a[1]*60+a[2]
tr=Transformer.from_crs('EPSG:31468',loc['projParameter'],always_xy=True)
for k in('start','end'):
    x,y=tr.transform(t[k+'_x'].values,t[k+'_y'].values); t[k+'X']=x+off[0]; t[k+'Y']=y+off[1]
G=1000; xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(','))
nx=int((xmax-xmin)//G)+1; ny=int((ymax-ymin)//G)+1
def grid(x,y):
    a=((x-xmin)//G).astype(int); b=((y-ymin)//G).astype(int); h=np.zeros((nx,ny)); k=(a>=0)&(a<nx)&(b>=0)&(b<ny); np.add.at(h,(a[k],b[k]),1); return h
Bs=grid(mid[fe,0],mid[fe,1]); Be=grid(mid[le,0],mid[le,1])
netc=grid(mid[:,0],mid[:,1])>0
# strict interior: cells whose 8 neighbours all hold network, eroded twice
er=netc.copy()
for _ in range(2):
    e2=er.copy(); e2[1:]&=er[:-1]; e2[:-1]&=er[1:]; e2[:,1:]&=er[:,:-1]; e2[:,:-1]&=er[:,1:]; er=e2
inside=lambda x,y,mask:(lambda a,b:((a>=0)&(a<nx)&(b>=0)&(b<ny))&mask[np.clip(a,0,nx-1),np.clip(b,0,ny-1)])(((x-xmin)//G).astype(int),((y-ymin)//G).astype(int))
sn=inside(t.startX.values,t.startY.values,netc); en=inside(t.endX.values,t.endY.values,netc); si=inside(t.startX.values,t.startY.values,er); ei=inside(t.endX.values,t.endY.values,er)
print('net cells km2',netc.sum(),'interior km2',er.sum())
print('MATSim x10: both ends in net cells',10*int((sn&en).sum()),'one end',10*int((sn^en).sum()),'both interior',10*int((si&ei).sum()),'one interior',10*int((si^ei).sum()))
both=t[sn&en]; Ms=grid(both.startX.values,both.startY.values)*10; Me=grid(both.endX.values,both.endY.values)*10
Mi=grid(t.startX.values[si&ei],t.startY.values[si&ei])*10
ak=(Ms>0)&(Bs>0); print('cell corr start BeST vs MATSim both-in',np.corrcoef(Bs[er],Ms[er])[0,1],'interior ratio BeST/MATSim',Bs[er].sum()/Ms[er].sum(),'edge-cells ratio',Bs[netc&~er].sum()/max(Ms[netc&~er].sum(),1))
ratio=Bs[er]/np.maximum(Ms[er],1); print('interior cell ratio quantiles',np.quantile(ratio[Ms[er]>2000],[.05,.25,.5,.75,.95]))
# BeST trips starting or ending on the fringe, against interior
fs=inside(mid[fe,0],mid[fe,1],netc&~er); fl=inside(mid[le,0],mid[le,1],netc&~er); print('BeST start on fringe',fs.mean(),'end on fringe',fl.mean(),'either',(fs|fl).mean(),'both',(fs&fl).mean())
print('BeST km start or end on fringe',ln[fs|fl].mean()/1000,'interior',ln[~(fs|fl)].mean()/1000)
print('MATSim x10 inside-mask fringe start share',(t.startX.values[sn&en]*0+inside(both.startX.values,both.startY.values,netc&~er)).mean())
# dead-end entries
J=json.loads((C/'junctions.json').read_text()); dead={k for k,v in J.items() if v[0]=='dead_end'}; se=E.fr.isin(dead).values; ee=E.to.isin(dead).values; print('dead-end start share',se[fe].mean(),'dead-end end share',ee[le].mean())
# top origin edges
u,c=np.unique(fe,return_counts=True); ot=np.argsort(-c)[:12]; print('top start edges',[(E.edge[u[i]],int(c[i]),E.type[u[i]]) for i in ot])
print('share of starts on top 100 edges',np.sort(c)[-100:].sum()/c.sum())
print('motorway starts',E.type.str.contains('motorway').values[fe].mean(),'ends',E.type.str.contains('motorway').values[le].mean())
# temporal fingerprint: does the 5-min profile of MATSim recur in BeST?
keep=t[si&ei]; hb=np.bincount((dep//300).astype(int),minlength=288)[:288]; hm=np.bincount(np.minimum(keep.dep.values//300,287),minlength=288)[:288]; print('5-min corr',np.corrcoef(hb,hm)[0,1]); print('BeST 5 min 07:00-08:00',hb[84:96].tolist()); print('MATSim*10',(hm[84:96]*10).tolist())
hb1=np.bincount((dep//60).astype(int),minlength=1440)[:1440]; hm1=np.bincount(np.minimum(keep.dep.values//60,1439),minlength=1440)[:1440]; print('1-min corr',np.corrcoef(hb1,hm1)[0,1])
# crossing-trip kilometres inside Berlin: straight-line share inside the net cells times driven distance
cross=t[sn^en]; f=np.zeros(len(cross))
for k in np.linspace(0.025,.975,20): f+=inside(cross.startX.values*(1-k)+cross.endX.values*k,cross.startY.values*(1-k)+cross.endY.values*k,netc)
f/=20; print('crossing trips x10',10*len(cross),'km total x10',cross.traveled_distance.sum()/100,'in-net km x10',(cross.traveled_distance.values*f).sum()/100,'mean in-net km',(cross.traveled_distance.values*f).mean()/1000)
nn=t[~sn&~en]; g=np.zeros(len(nn))
for k in np.linspace(0.025,.975,20): g+=inside(nn.startX.values*(1-k)+nn.endX.values*k,nn.startY.values*(1-k)+nn.endY.values*k,netc)
g/=20; print('both outside touching net trips x10',10*int((g>0).sum()),'in-net km x10',(nn.traveled_distance.values*g).sum()/100)
print('MATSim both-in x10 km',both.traveled_distance.sum()/100,'mean',both.traveled_distance.mean()/1000,'BeST external',ln.sum()/1000)
fr=t[t.main_mode=='freight']; print('freight trips x10 touching net',10*int((sn|en)[t.main_mode.values=='freight'].sum()),'km',fr.traveled_distance.sum()/100,'share of trips touching net',(sn|en)[t.main_mode.values=='freight'].sum()/(sn|en).sum())
np.savez(O/'od_grid.npz',best_start=Bs,best_end=Be,matsim_start=Ms,matsim_end=Me,net=netc,interior=er)
