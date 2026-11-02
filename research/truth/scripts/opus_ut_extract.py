"""DLR UT: streams all 96 trajectory batches, keeps car-like objects at 5 Hz, and traffic lights, into a cache."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
import zipfile,io
z=zipfile.ZipFile(UT/'DLR-Urban-Traffic-dataset_v1-3-1.zip')
tr=sorted(n for n in z.namelist() if '/trajectories/' in n and n.endswith('.csv'))
tl=sorted(n for n in z.namelist() if '/traffic_lights/' in n and n.endswith('.csv'))
print(len(tr),len(tl),flush=True)
cols=['timestamp','id','center_easting','center_northing','velocity_easting','velocity_northing','velocity_magnitude','acceleration_easting','acceleration_northing','yaw','dimension_length','dimension_width','classifications_car','classifications_van','classifications_truck','classifications_motorbike','classifications_bicycle','classifications_pedestrian','interpolated']
def secs(s):
    s=s.str.slice(11,-6); return s.str.slice(0,2).astype(int)*3600+s.str.slice(3,5).astype(int)*60+s.str.slice(6).astype(float)
parts=[]; totrows=0; ids=set()
for n in tr:
    with z.open(n) as f:
        d=pd.read_csv(f,usecols=cols)
    totrows+=len(d); ids.update(d['id'].unique().tolist())
    d['t']=secs(d['timestamp'])
    d=d[(np.round(d['t']*20).astype(int)%4)==0]
    veh=d['classifications_car']+d['classifications_van']+d['classifications_truck']
    d=d[(veh>0.5)]
    parts.append(pd.DataFrame(dict(id=d['id'].values,t=d['t'].values.astype('f8'),x=(d['center_easting'].values-604625).astype('f4'),y=(d['center_northing'].values-5792650).astype('f4'),vx=d['velocity_easting'].values.astype('f4'),vy=d['velocity_northing'].values.astype('f4'),v=d['velocity_magnitude'].values.astype('f4'),ax=d['acceleration_easting'].values.astype('f4'),ay=d['acceleration_northing'].values.astype('f4'),yaw=d['yaw'].values.astype('f4'),L=d['dimension_length'].values.astype('f4'),W=d['dimension_width'].values.astype('f4'),truck=d['classifications_truck'].values.astype('f4'),interp=d['interpolated'].values.astype(bool))))
    print(n[-40:],len(d),flush=True)
a=pd.concat(parts,ignore_index=True); a.to_parquet(CACHE/'ut_veh.parquet') if False else np.savez_compressed(CACHE/'ut_veh.npz',**{k:a[k].values for k in a.columns})
ls=[]
for n in tl:
    with z.open(n) as f: d=pd.read_csv(f)
    d['t']=secs(d['timestamp']); ls.append(d[['t','id','state']])
b=pd.concat(ls,ignore_index=True); np.savez_compressed(CACHE/'ut_tl.npz',t=b['t'].values,id=b['id'].values,state=b['state'].values)
save('ut_extract',dict(trajectory_files=len(tr),raw_rows=totrows,raw_ids=len(ids),kept_rows=len(a),kept_ids=int(a['id'].nunique()),tl_rows=len(b)))
