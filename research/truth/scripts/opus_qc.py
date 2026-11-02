"""Data flaw table: kinematic consistency, length defaults, clamps, per source."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
out={}
for s in ['I395','I90stat','I90mov','I294L1','I294L2']:
    d=pd.read_csv(TG/f'{s}.csv',nrows=None,usecols=lambda c:c.strip().lower() in('id','time','xloc_kf','yloc_kf','speed_kf','acceleration_kf','length_smoothed','run_index'))
    d.columns=[c.strip().lower() for c in d.columns]
    if 'run_index' not in d: d['run_index']=0
    d=d.sort_values(['run_index','id','time']);g=d.groupby(['run_index','id'])
    dt=g['time'].diff();ds=np.hypot(g['xloc_kf'].diff(),g['yloc_kf'].diff())/dt;dv=g['speed_kf'].diff()/dt;m=(dt>.05)&(dt<.15)
    L=d.drop_duplicates(['run_index','id'])['length_smoothed']
    # residual high-frequency noise left in position: second difference of position against acceleration
    out[s]=dict(rows=len(d),tracks=len(L),track_seconds=q(g['time'].agg(lambda x:x.max()-x.min()),(5,50,95)),pos_vs_speed_abs=q(abs(ds-d['speed_kf'])[m],(50,95,99)),speed_vs_acc_abs=q(abs(dv-d['acceleration_kf'])[m],(50,95,99)),length=q(L,(5,25,50,75,95)),length_modal_frac=float((L.round(1)==L.round(1).mode().iloc[0]).mean()),length_modal=float(L.round(1).mode().iloc[0]),accel_clamp_hi=float(d['acceleration_kf'].max()),accel_clamp_lo=float(d['acceleration_kf'].min()),abs_accel_over_4_frac=float((abs(d['acceleration_kf'])>4).mean()),speed_max=float(d['speed_kf'].max()),speed_q=q(d['speed_kf'].values[::50],(5,50,95)))
    print(s,json.dumps(out[s])[:600],flush=True)
h=dict(np.load(CACHE/'pairs_HT.npz'))
u=h['seg'];dcc=np.diff(h['cc'])/.1;m=np.diff(u)==0;res=dcc[m]-(h['vl'][:-1]-h['vf'][:-1])[m]
out['HT']=dict(rows_0p1s=len(u),segments=int(u.max()+1),spacing_rate_abs=q(abs(res)[::7],(50,95,99)),length_f=q(h['Lf'][::200],(5,25,50,75,95)),speed_q=q(h['vf'][::200],(5,50,95)),spacing_q=q(h['cc'][::200],(5,50,95)))
ud=np.load(CACHE/'ut_veh.npz');o=np.lexsort((ud['t'],ud['id']));ID=ud['id'][o];T=ud['t'][o];X=ud['x'][o];Y=ud['y'][o];V=ud['v'][o];L=ud['L'][o]
m=(np.diff(ID)==0)&(np.diff(T)<.25);rate=np.hypot(np.diff(X),np.diff(Y))[m]/np.diff(T)[m]
out['DLR_UT']=dict(rows_5hz=len(ID),tracks=int(len(np.unique(ID))),pos_vs_speed_abs=q(abs(rate-V[:-1][m])[::5],(50,95,99)),length_moving=q(L[V>5][::50],(5,25,50,75,95)),length_stopped=q(L[V<.3][::50],(5,25,50,75,95)))
nl=pd.read_csv(NG/'lankershim.csv',usecols=['vehicle_id','frame_id','local_y','v_vel','v_acc','v_length','space_headway','preceding'])
nl=nl.sort_values(['vehicle_id','frame_id']);g=nl.groupby('vehicle_id');dyy=g['local_y'].diff()/.1*.3048;dv=g['v_vel'].diff()/.1*.3048;a=nl['v_acc']*.3048
ok=g['frame_id'].diff()==1
out['NGSIM_Lankershim']=dict(rows=len(nl),abs_accel_over_3_frac=float((abs(a)>3).mean()),accel_q=q(a.values[::20],(1,5,50,95,99)),jerk_over_10_frac=float((abs((a-g['v_acc'].shift()*.3048)/.1)>10)[ok].mean()),pos_vs_speed_abs=q(abs(dyy-nl['v_vel']*.3048)[ok].dropna().values[::20],(50,95,99)))
save('qc',out);print({k:out[k] for k in ('HT','DLR_UT','NGSIM_Lankershim')})
