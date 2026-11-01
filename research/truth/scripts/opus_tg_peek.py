import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
for name in sys.argv[1:]:
    d=pd.read_csv(TG/f'{name}.csv',dtype={'lane_kf':'float32'})
    d.columns=[c.strip() for c in d.columns]
    print('==',name,len(d),list(d.columns))
    print(d.describe().T[['min','50%','max']].round(2).to_string())
    print(d.groupby('type_most_common')['id'].nunique().to_dict())
    if 'run_index' in d: print(d.groupby('run_index').agg(ids=('id','nunique'),t0=('time','min'),t1=('time','max'),xmin=('xloc_kf','min'),xmax=('xloc_kf','max'),ymin=('yloc_kf','min'),ymax=('yloc_kf','max'),v=('speed_kf','median')).round(1).to_string())
    print('lanes',d['lane_kf'].value_counts().head(12).to_dict())
    # kinematic consistency
    k=['run_index','id','time'] if 'run_index' in d else ['id','time']
    d=d.sort_values(k); g=d.groupby(k[:-1])
    dt=g['time'].diff(); ds=np.hypot(g['xloc_kf'].diff(),g['yloc_kf'].diff())/dt
    sp=d['speed_kf'] if 'speed_kf' in d else np.hypot(d['speed_kf_x'],d['speed_kf_y'])
    m=(dt>0.05)&(dt<0.15)
    print('dt',dt.round(2).value_counts().head(4).to_dict(),'|ds/dt-v| q50,q95,q99',np.nanpercentile(abs(ds-sp)[m],[50,95,99]).round(3))
    if 'acceleration_kf' in d:
        dv=g['speed_kf'].diff()/dt; print('|dv/dt-a| q50,q95,q99',np.nanpercentile(abs(dv-d['acceleration_kf'])[m],[50,95,99]).round(3),'a q0.1,50,99.9',np.nanpercentile(d['acceleration_kf'],[.1,50,99.9]).round(2))
    print('L q',np.percentile(d['length_smoothed'],[1,50,99]).round(2),'W',np.percentile(d['width_smoothed'],[1,50,99]).round(2),'track dur',np.percentile(g['time'].agg(lambda x:x.max()-x.min()),[5,50,95]).round(1))
