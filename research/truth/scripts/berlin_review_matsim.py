# MATSim Open Berlin v5.5.3 10% output trips against BeST: count, area, time-of-day. Reads downloads as data only.
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from pyproj import Transformer
O=Path('research/truth/berlin-review'); DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031/matsim'); C=O/'cache'
t=pd.read_csv(DL/'berlin-v5.5.3-10pct.output_trips.csv.gz',sep=';',usecols=['person','dep_time','trav_time','traveled_distance','euclidean_distance','main_mode','start_x','start_y','end_x','end_y','start_activity_type','end_activity_type'],dtype={'person':str})
def sec(s):
    a=s.str.split(':',expand=True).astype(int); return a[0]*3600+a[1]*60+a[2]
t['dep']=sec(t.dep_time); t['tt']=sec(t.trav_time); print('trips',len(t)); print(t.main_mode.value_counts(dropna=False).to_string())
t['freight']=t.person.str.contains('freight'); print('freight persons trips',t.groupby('main_mode').freight.sum().to_dict())
loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(',')))); print(loc)
tr=Transformer.from_crs('EPSG:31468',loc['projParameter'],always_xy=True)
for k in('start','end'):
    x,y=tr.transform(t[k+'_x'].values,t[k+'_y'].values); t[k+'X']=x+off[0]; t[k+'Y']=y+off[1]
shapes=json.loads((C/'shapes.json').read_text()); G=500; xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(','))
nx=int((xmax-xmin)//G)+3; ny=int((ymax-ymin)//G)+3; occ=np.zeros((nx,ny),dtype=np.int32)
for s in shapes.values():
    p=np.array([list(map(float,q.split(',')))[:2] for q in s.split()]); a=((p[:,0]-xmin)//G+1).astype(int); b=((p[:,1]-ymin)//G+1).astype(int); occ[a,b]+=1
inside=occ>0; print('occupied cells',inside.sum(),'area km2',inside.sum()*.25)
# fill holes (lakes, forests) and keep the outer shape: a column-wise and row-wise span test
fill=np.zeros_like(inside)
for i in range(nx):
    w=np.where(inside[i])[0]
    if len(w): fill[i,w[0]:w[-1]+1]=True
fill2=np.zeros_like(inside)
for j in range(ny):
    w=np.where(inside[:,j])[0]
    if len(w): fill2[w[0]:w[-1]+1,j]=True
A=fill&fill2; print('filled area km2',A.sum()*.25); np.save(O/'best_area_mask.npy',A)
def isin(x,y):
    a=((x-xmin)//G+1).astype(int); b=((y-ymin)//G+1).astype(int); ok=(a>=0)&(a<nx)&(b>=0)&(b<ny); r=np.zeros(len(x),bool); r[ok]=A[a[ok],b[ok]]; return r
t['si']=isin(t.startX.values,t.startY.values); t['ei']=isin(t.endX.values,t.endY.values)
car=t[t.main_mode.isin(['car','freight'])].copy()
# straight-line through test for trips with both ends outside
through=np.zeros(len(car),bool); ids=np.where(~car.si.values&~car.ei.values)[0]
for k in np.linspace(.05,.95,19):
    x=car.startX.values[ids]*(1-k)+car.endX.values[ids]*k; y=car.startY.values[ids]*(1-k)+car.endY.values[ids]*k; through[ids]|=isin(x,y)
car['through']=through
car['cls']=np.select([car.si&car.ei,car.si^car.ei,car.through],['inside','crossing','through'],'outside')
s=car.groupby(['main_mode','cls']).agg(trips=('dep','size'),km=('traveled_distance',lambda z:z.sum()/1000),tt=('tt','mean')); s['trips_x10']=s.trips*10; s['km_x10']=s.km*10; print(s.round(0).to_string()); s.to_csv(O/'matsim_area_classes.csv')
print('car+freight relevant trips x10',10*car[car.cls!='outside'].shape[0],' inside only x10',10*(car.cls=='inside').sum(),' km x10 inside',car[car.cls=='inside'].traveled_distance.sum()/100)
car['hour']=(car.dep//3600).astype(int); print('dep after 24h',int((car.hour>=24).sum()),'trips; of relevant x10',10*int(((car.hour>=24)&(car.cls!='outside')).sum()))
rel=car[car.cls!='outside']
d=pd.read_csv(O/'../berlin-snapshot/demand_hourly.csv').set_index('hour').departures
h=pd.DataFrame({'matsim_relevant_x10':rel[rel.main_mode=='car'].groupby('hour').size()*10,'matsim_freight_x10':rel[rel.main_mode=='freight'].groupby('hour').size()*10,'matsim_inside_x10':rel[(rel.cls=='inside')&(rel.main_mode=='car')].groupby('hour').size()*10,'best':d}).fillna(0); h.to_csv(O/'matsim_vs_best_hourly.csv'); print(h.astype(int).to_string())
hh=h.loc[0:23]
print('corr shares best~matsim',np.corrcoef(hh.best,hh.matsim_relevant_x10)[0,1],'inside',np.corrcoef(hh.best,hh.matsim_inside_x10)[0,1])
for sh in range(-3,4): print('lag',sh,round(np.corrcoef(hh.matsim_relevant_x10,np.roll(hh.best,sh))[0,1],4))
print('mean traveled km by cls',rel.groupby('cls').traveled_distance.mean().round(0).to_dict())
