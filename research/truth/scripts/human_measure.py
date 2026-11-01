import os
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1'
import pathlib,json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
root=pathlib.Path('research/truth'); raw=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-pneuma')
tracks=[]; classes={}; full=0
with (raw/'20181024_d1_0830_0900.csv').open() as f:
 next(f)
 for line in f:
  p=line.strip().strip(';').split(';'); cls=p[1].strip(); classes[cls]=classes.get(cls,0)+1
  if cls not in ('Car','Taxi'): continue
  a=np.fromstring(';'.join(p[4:]),sep=';').reshape(-1,6); full+=len(a)
  if len(a)<26: continue
  # sample at 0.4 s; preserve supplied speed and acceleration. Heading from +/-0.52 s positions.
  ii=np.arange(13,len(a)-13,10); b=a[ii]; xy=np.c_[(b[:,1]-23.737)*111320*np.cos(np.deg2rad(37.978)),(b[:,0]-37.978)*111320]
  dx=(a[ii+13,1]-a[ii-13,1])*111320*np.cos(np.deg2rad(37.978)); dy=(a[ii+13,0]-a[ii-13,0])*111320
  norm=np.hypot(dx,dy); hx=np.divide(dx,norm,out=np.zeros_like(dx),where=norm>0.15); hy=np.divide(dy,norm,out=np.zeros_like(dy),where=norm>0.15)
  # stopped direction is not identifiable; no stopped geometric gap estimates.
  tracks.append((int(p[0]),np.c_[b[:,5],xy,b[:,2]/3.6,b[:,3],b[:,4],hx,hy]))
rows=np.concatenate([np.c_[np.full(len(a),i),a] for i,a in tracks]); rows=rows[np.isfinite(rows).all(axis=1)]
# id,t,x,y,v,a_long,a_lat,hx,hy
q=lambda x:dict(zip(['p05','p50','p95'],map(float,np.quantile(x,[.05,.5,.95])))) if len(x) else None
summary={'source':'https://zenodo.org/records/10491409','classes':classes,'car_taxi_native_rows':full,'tracks':len(tracks),'sampled_rows':len(rows),'speed_mps':q(rows[:,4]),'speed_bins':[]}
bins=[0,2,5,10,15,30]
for lo,hi in zip(bins[:-1],bins[1:]):
 r=rows[(rows[:,4]>=lo)&(rows[:,4]<hi)]
 summary['speed_bins'].append({'range_mps':[lo,hi],'n':len(r),'accel_mps2':q(r[:,5]),'positive_accel':q(r[r[:,5]>.05,5]),'braking_magnitude':q(-r[r[:,5]<-.05,5]),'lateral_accel_mps2':q(r[:,6])})
# nearest co-directional point in 1.25 m half-width corridor, 5-80 m ahead; proxy only.
pairs=[]
for frame in np.unique(np.round(rows[:,1]/.4).astype(int)):
 r=rows[np.round(rows[:,1]/.4).astype(int)==frame]
 if len(r)<2: continue
 tree=cKDTree(r[:,2:4]); neighborhoods=tree.query_ball_point(r[:,2:4],80,workers=1)
 for k,js in enumerate(neighborhoods):
  e=r[k]
  if e[4]<1 or np.hypot(*e[7:9])<.9: continue
  other=r[js]; d=other[:,2:4]-e[2:4]; along=d@e[7:9]; lateral=d[:,0]*e[8]-d[:,1]*e[7]
  mask=(along>5)&(abs(lateral)<1.25)&((other[:,7:9]@e[7:9])>.95)&(abs(other[:,1]-e[1])<.03)
  if not mask.any(): continue
  ix=np.where(mask)[0][np.argmin(along[mask])]; leader=other[ix]; gap=along[ix]-5
  pairs.append([e[0],leader[0],e[1],e[4],leader[4],e[5],leader[5],gap,along[ix]/e[4],gap/e[4]])
pairs=np.asarray(pairs); np.savez_compressed(root/'human-pneuma-proxies.npz',pairs=pairs)
summary['proxy_pairs']=len(pairs); summary['proxy_bins']=[]
for lo,hi in zip(bins[:-1],bins[1:]):
 r=pairs[(pairs[:,3]>=lo)&(pairs[:,3]<hi)]
 summary['proxy_bins'].append({'range_mps':[lo,hi],'n':len(r),'gap_m':q(r[:,7]),'front_headway_s':q(r[:,8]),'net_time_gap_s':q(r[:,9])})
vs=[np.std(a[:,3]) for i,a in tracks if len(a)>=50]
summary['within_track_speed_sd_mps']=q(vs); summary['eligible_speed_sd_tracks']=len(vs)
# apparent lag of acceleration cross-correlation; conditional on >=20 s same pair, not reaction time.
lags=[]
for ego in np.unique(pairs[:,0]):
 r=pairs[pairs[:,0]==ego]
 for lead in np.unique(r[:,1]):
  z=r[r[:,1]==lead]; z=z[np.argsort(z[:,2])]
  for s in np.split(z,np.where(np.diff(z[:,2])>.45)[0]+1):
   if len(s)<50 or min(np.std(s[:,5]),np.std(s[:,6]))<.1: continue
   cc=[np.corrcoef(s[k:,5],s[:-k,6])[0,1] if k else np.corrcoef(s[:,5],s[:,6])[0,1] for k in range(9)]
   k=int(np.nanargmax(cc)); lags.append([k*.4,float(cc[k]),len(s)])
summary['apparent_lag_segments']=len(lags); summary['apparent_lag_s']=q(np.array(lags)[:,0]) if lags else None
(root/'human-pneuma-summary.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(2,2,figsize=(11,8),layout='constrained')
for lo,hi in zip(bins[:-1],bins[1:]):
 r=rows[(rows[:,4]>=lo)&(rows[:,4]<hi)]
 if len(r)>30: ax[0,0].hist(r[:,5],bins=np.linspace(-4,4,81),density=True,histtype='step',label=f'{lo}–{hi} m/s')
ax[0,0].set(xlabel='Supplied longitudinal acceleration (m/s²)',ylabel='Density',title='Measured kinematics; Car + Taxi'); ax[0,0].legend(fontsize=8)
for lo,hi in [(1,5),(5,10),(10,15)]:
 r=pairs[(pairs[:,3]>=lo)&(pairs[:,3]<hi)]
 if len(r)>10: ax[0,1].hist(r[:,9],bins=np.linspace(0,10,61),density=True,histtype='step',label=f'{lo}–{hi} m/s')
ax[0,1].axvline(1,c='black',ls='--',label='SUMO default tau (parameter)');ax[0,1].set(xlabel='Proxy net gap / speed (s)',ylabel='Density',title='Geometric proxies, NOT verified lane leaders');ax[0,1].legend(fontsize=8)
ax[1,0].hist(vs,bins=35);ax[1,0].set(xlabel='Within-track speed SD (m/s)',ylabel='Tracks',title='Tracks ≥20 s; context + behaviour + measurement')
ax[1,1].scatter(rows[::20,2],rows[::20,3],c=rows[::20,4],s=.4,vmin=0,vmax=15); ax[1,1].set(xlabel='Local east (m)',ylabel='Local north (m)',title='Recording footprint (not a lane map)');ax[1,1].set_aspect('equal')
fig.suptitle('pNEUMA 2018-10-24 drone 1, 08:30–09:00 | source: Zenodo 10491409')
fig.savefig(root/'fig/05-pneuma-measurements.png',dpi=160);plt.close(fig)
print(json.dumps(summary,indent=2))
