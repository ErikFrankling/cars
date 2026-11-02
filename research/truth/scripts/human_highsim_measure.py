import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import zipfile,xml.etree.ElementTree as E,json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
raw=Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-highsim');out=Path('research/truth')
ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
a=[]
with zipfile.ZipFile(raw/'1-90.xlsx') as z:
 with z.open('xl/worksheets/sheet1.xml') as f:
  for event,e in E.iterparse(f,events=('end',)):
   if e.tag==ns+'row':
    a.append([float(c.find(ns+'v').text) if c.find(ns+'v') is not None else np.nan for c in e]);e.clear()
a=np.asarray(a);ids=np.unique(a[:,0]);lengths={i:np.median(a[a[:,0]==i,8])*.3048 for i in ids}
rows=[];lateral=[];changes=[];stopped=[];traces=[]
for i in ids:
 t=a[a[:,0]==i];t=t[np.argsort(t[:,1])];s=t[::3].copy();s[:,[3,4,7,8,10,11,14]]*=.3048;rows.append(s)
 # 1 s central derivative of cross-road position, not road curvature corrected
 if len(t)>60:
  dt=t[60:,1]-t[:-60,1]; vy=(t[60:,3]-t[:-60,3])*.3048/dt
  lateral.extend(vy[np.isfinite(vy)] [::3]);traces.append((int(i),t[::15,1]-t[0,1],t[::15,3]*.3048))
 changes.extend([(int(i),float(t[k,1]),float(t[k-1,12]),float(t[k,12])) for k in np.where(np.diff(t[:,12])!=0)[0]+1])
r=np.concatenate(rows); gap=np.array([h-lengths.get(l,np.nan) if l>0 and h>0 else np.nan for h,l in r[:,[14,13]]]);q=lambda x:dict(zip(['p05','p50','p95'],map(float,np.quantile(x,[.05,.5,.95])))) if len(x) else None
summary={'source':'https://github.com/CATS-Lab/Filed-Experiment-Data-HIGH_Sim','tracks':len(ids),'native_rows':len(a),'sampled_rows':len(r),'lane_boundary_changes':len(changes),'changes':changes,'lateral_coordinate_speed_mps':q(lateral),'speed_bins':[]}
for lo,hi in [(0,2),(2,5),(5,10),(10,15),(15,25),(25,40)]:
 m=(r[:,10]>=lo)&(r[:,10]<hi);valid=m&np.isfinite(gap)&(gap>=0)&(r[:,10]>1)
 summary['speed_bins'].append(dict(range_mps=[lo,hi],n=int(m.sum()),accel=q(r[m,11]),gap_n=int(valid.sum()),gap_m=q(gap[valid]),time_gap_s=q(gap[valid]/r[valid,10])))
stop=(r[:,10]<.1)&np.isfinite(gap)&(gap>=0);summary['standstill_n']=int(stop.sum());summary['standstill_gap_m']=q(gap[stop])
(out/'human-highsim-summary.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for lo,hi in [(5,10),(10,15),(15,25),(25,40)]:
 m=(r[:,10]>=lo)&(r[:,10]<hi)&np.isfinite(gap)&(gap>=0)
 if m.sum()>10: ax[0].hist(gap[m]/r[m,10],bins=np.linspace(0,6,61),density=True,histtype='step',label=f'{lo}–{hi} m/s')
ax[0].set(xlabel='Net time gap (s), known leader length',ylabel='Density',title='HIGH-SIM first 90 trajectories');ax[0].legend(fontsize=8)
for i,t,x in traces[:20]: ax[1].plot(t,x,lw=.7)
ax[1].set(xlabel='Time since track start (s)',ylabel='Cross-road coordinate (m)',title='First 20 tracks; curvature/drift not removed')
fig.savefig(out/'fig/05-highsim-measurements.png',dpi=160)
print(json.dumps(summary,indent=2))
