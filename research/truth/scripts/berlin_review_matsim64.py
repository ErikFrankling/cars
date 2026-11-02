# MATSim Berlin v6.4 10% output trips: is the newer public demand a better source? Departure shape and Berlin car-like trips.
import json
from pathlib import Path
import numpy as np,pandas as pd
from pyproj import Transformer
O=Path('research/truth/berlin-review'); S=Path('research/truth/berlin-snapshot'); M=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031/matsim64')
t=pd.read_csv(M/'berlin-v6.4.output_trips.csv.gz',sep=';',usecols=lambda c:c in('person','dep_time','traveled_distance','main_mode','start_x','start_y','end_x','end_y'),dtype={'person':str})
print(len(t)); print(t.main_mode.value_counts().to_string())
t['prefix']=t.person.str.extract(r'^([a-zA-Z_]+)')[0].fillna('person'); print(t.groupby('prefix').size().sort_values(ascending=False).head(10).to_string())
print(t[t.main_mode=='car'].groupby('prefix').size().sort_values(ascending=False).head(8).to_string())
loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(',')))); tr=Transformer.from_crs('EPSG:25832',loc['projParameter'],always_xy=True); G=1000; xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(','))
netc=np.load(O/'od_grid.npz')['net']; nx,ny=netc.shape
ins=lambda x,y:(lambda a,b:((a>=0)&(a<nx)&(b>=0)&(b<ny))&netc[np.clip(a,0,nx-1),np.clip(b,0,ny-1)])(((x-xmin)//G).astype(int),((y-ymin)//G).astype(int))
c=t[~t.main_mode.isin(['walk','bike','bicycle','pt','ride'])].copy(); print('sample x',c.start_x.iloc[:2].tolist(),c.start_y.iloc[:2].tolist())
x,y=tr.transform(c.start_x.values,c.start_y.values); c['si']=ins(x+off[0],y+off[1]); x,y=tr.transform(c.end_x.values,c.end_y.values); c['ei']=ins(x+off[0],y+off[1])
a=c.dep_time.str.split(':',expand=True).astype(int); c['h']=a[0]+a[1]/60; print('modes',c.main_mode.value_counts().to_dict())
print('x10 both in',10*int((c.si&c.ei).sum()),'km',c[c.si&c.ei].traveled_distance.sum()/100,'one end',10*int((c.si^c.ei).sum()),'km total',c[c.si^c.ei].traveled_distance.sum()/100)
print('by mode both/one',c[c.si|c.ei].groupby('main_mode').size().mul(10).to_dict())
rel=c[c.si|c.ei]; hh=np.bincount(rel.h.astype(int).values,minlength=30)[:24]*10; print('hourly x10',hh.tolist())
sh=pd.read_csv(O/'shape_shares.csv',index_col=0); p=hh/hh.sum()*100; print('share',np.round(p,2).tolist()); print('MAE pp vs real counts: v6.4',np.abs(p-sh.real_share).mean(),'BeST departures',np.abs(sh.best_dep_share-sh.real_share).mean(),'SrV',np.abs(sh.srv_miv-sh.real_share).mean()); print('hour 7/peak',p[7]/p.max(),'8/peak',p[8]/p.max(),'10/8',p[10]/p[8],'BeST',sh.best_dep_share[8]/sh.best_dep_share.max(),sh.best_dep_share[10]/sh.best_dep_share[8])
