# Do MATSim v6.4 trip end links name BeST edges, and how many v6.4 kilometres fall inside the BeST network?
import json
from pathlib import Path
import numpy as np,pandas as pd
from pyproj import Transformer
O=Path('research/truth/berlin-review'); M=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031/matsim64')
E=set(pd.read_csv(O/'edges.csv',usecols=['edge'],dtype=str,keep_default_na=False).edge)
t=pd.read_csv(M/'berlin-v6.4.output_trips.csv.gz',sep=';',usecols=['main_mode','start_link','end_link','start_x','start_y','end_x','end_y','traveled_distance'],dtype={'start_link':str,'end_link':str}); c=t[t.main_mode.isin(['car','truck','freight'])].copy()
loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(',')))); tr=Transformer.from_crs('EPSG:25832',loc['projParameter'],always_xy=True); G=1000; xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(','))
netc=np.load(O/'od_grid.npz')['net']; nx,ny=netc.shape
ins=lambda x,y:(lambda a,b:((a>=0)&(a<nx)&(b>=0)&(b<ny))&netc[np.clip(a,0,nx-1),np.clip(b,0,ny-1)])(((x-xmin)//G).astype(int),((y-ymin)//G).astype(int))
sx,sy=tr.transform(c.start_x.values,c.start_y.values); ex,ey=tr.transform(c.end_x.values,c.end_y.values); sx=sx+off[0];sy=sy+off[1];ex=ex+off[0];ey=ey+off[1]; si=ins(sx,sy); ei=ins(ex,ey)
print('sample start_link',c.start_link.iloc[:5].tolist())
sm=c.start_link.isin(E).values; em=c.end_link.isin(E).values; both=si&ei; print('both in net x10',10*int(both.sum()),'start link in BeST',sm[both].mean(),'end link',em[both].mean(),'both links',(sm&em)[both].mean())
cross=si^ei; f=np.zeros(cross.sum())
for k in np.linspace(.025,.975,20): f+=ins(sx[cross]*(1-k)+ex[cross]*k,sy[cross]*(1-k)+ey[cross]*k)
f/=20; print('crossing x10',10*int(cross.sum()),'in-net km x10',(c.traveled_distance.values[cross]*f).sum()/100,'both-in km x10',c.traveled_distance.values[both].sum()/100)
out=~si&~ei; g=np.zeros(out.sum())
for k in np.linspace(.025,.975,20): g+=ins(sx[out]*(1-k)+ex[out]*k,sy[out]*(1-k)+ey[out]*k)
g/=20; print('through x10',10*int((g>0).sum()),'in-net km x10',(c.traveled_distance.values[out]*g).sum()/100)
