import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import xml.etree.ElementTree as E,zipfile,numpy as np,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-highsim/1-90.xlsx');ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
a=[]
with zipfile.ZipFile(p) as z:
 with z.open('xl/worksheets/sheet1.xml') as f:
  for _,e in E.iterparse(f,events=('end',)):
   if e.tag==ns+'row': a.append([float(c.find(ns+'v').text) if c.find(ns+'v') is not None else np.nan for c in e]);e.clear()
a=np.asarray(a);events=[];curves=[]
for i in np.unique(a[:,0]):
 t=a[a[:,0]==i];t=t[np.argsort(t[:,1])];tt=t[:,1];x=t[:,3]*.3048
 for k in np.where(np.diff(t[:,12])!=0)[0]+1:
  old,new=t[k-1,12],t[k,12];tc=tt[k]
  if min(old,new)<0 or abs(old-new)!=1: continue
  w=(tt>tc-6)&(tt<tc+6)
  if tc-tt[0]<6 or tt[-1]-tc<6 or np.any(t[w,12]<0):continue
  pre=(tt>tc-6)&(tt<tc-4);post=(tt>tc+4)&(tt<tc+6)
  if min(pre.sum(),post.sum())<20:continue
  x0,x1=np.median(x[pre]),np.median(x[post]);width=x1-x0
  if not 2.5<abs(width)<4.5 or max(np.std(x[pre]),np.std(x[post]))>.3:continue
  q=(x[w]-x0)/width;ts=tt[w]
  # conservative single transition through 10%-90%, exclude reversal/noisy ambiguous endpoints
  ka=np.where(q>=.1)[0][0];kb=np.where(q>=.9)[0]
  if not len(kb):continue
  kb=kb[0];duration=ts[kb]-ts[ka]
  if not 1<duration<10 or np.any(np.diff(q[ka:kb])<-.05):continue
  vel=(x[30:]-x[:-30])/(tt[30:]-tt[:-30]);vtime=(tt[30:]+tt[:-30])/2
  peak=np.max(np.abs(vel[(vtime>=ts[ka])&(vtime<=ts[kb])]))
  events.append(dict(id=int(i),crossing_time=float(tc),old_lane=int(old),new_lane=int(new),duration10_90_s=float(duration),width_m=float(abs(width)),peak_1s_lateral_mps=float(peak),speed_mps=float(t[k,10]*.3048),supplied_front_headway_m=float(t[k,14]*.3048)))
  curves.append((ts-tc,q))
q=lambda vals: dict(zip(['p05','p50','p95'],map(float,np.quantile(vals,[.05,.5,.95])))) if vals else None
summary=dict(source='https://github.com/CATS-Lab/Filed-Experiment-Data-HIGH_Sim',events=events,n=len(events),duration10_90_s=q([e['duration10_90_s'] for e in events]),peak_1s_lateral_mps=q([e['peak_1s_lateral_mps'] for e in events]))
Path('research/truth/human-highsim-lateral.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
for t,q in curves:ax.plot(t,q,alpha=.7)
ax.axhline(.1,c='black',ls=':');ax.axhline(.9,c='black',ls=':');ax.set(xlabel='Time from lane-label crossing (s)',ylabel='Normalised cross-road displacement',title=f'HIGH-SIM: {len(events)} screened 10–90% transitions; exploratory')
fig.savefig('research/truth/fig/05-highsim-lateral.png',dpi=160);print(json.dumps(summary,indent=2))
