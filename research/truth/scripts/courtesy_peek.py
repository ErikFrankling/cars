"""Lane inventory of the trajectory sets, to find lane ends and known-intent cohorts."""
import os,sys
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import numpy as np,pandas as pd
B='/home/erikf/projects/personal/cars-data/truth/trajectories/'
c=['vehicle_id','frame_id','local_x','local_y','v_vel','lane_id','int_id','section_id','direction','movement','o_zone','d_zone']
for n in ('lankershim','peachtree'):
    d=pd.read_csv(B+f'opus-20261031-ngsim/{n}.csv',usecols=c)
    print(n,len(d),d.vehicle_id.nunique(),'frames',d.frame_id.min(),d.frame_id.max())
    print(d.groupby(['direction','lane_id']).size().unstack(0).fillna(0).astype(int).to_string())
    print(d.groupby(['section_id','int_id']).size().sort_values().tail(14).to_string())
    print(d.groupby('movement').vehicle_id.nunique().to_dict())
for n in ('I395','I294L1','I294L2','I90stat','I90mov'):
    d=pd.read_csv(B+f'opus-20261031-tgsim/{n}.csv',usecols=lambda k:k.lower().strip().replace('-','_') in('lane_kf','speed_kf','run_index','id','time'),dtype={'lane_kf':'float32'})
    d.columns=[k.strip().lower().replace('-','_') for k in d.columns]
    g=d.groupby('lane_kf').agg(n=('speed_kf','size'),v=('speed_kf','mean'))
    print(n,len(d),'runs',d.run_index.nunique() if 'run_index' in d else 1);print(g.round(1).T.to_string())
