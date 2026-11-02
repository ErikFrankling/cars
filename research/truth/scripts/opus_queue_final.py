"""Queue discharge for all final models with the measured first-car standing distance and standing spacing."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_sim import *
from opus_dyn import sample
from opus_fit import SUM_KR
d=np.load(CACHE/'ut_queue.npz')['R'];n='sid pt tg pos h t_front start_delay start_lag L W truck turn v_cross dist'.split();ix={k:i for i,k in enumerate(n)}
f=d[(d[:,ix['pos']]==1)&(d[:,ix['truck']]==0)]
front=f[:,ix['dist']]-f[:,ix['L']]/2
fd=float(np.median(front));print('first car centre distance',q(f[:,ix['dist']],(25,50,75)),'front distance',q(front,(25,50,75)),flush=True)
res=json.loads((OUT/'fit_params_all.json').read_text());VR=30.
def un(p):
    p=dict(p)
    if 'gamma' in p: p['v0']=p.pop('gamma')*VR
    return p
SPEC=dict(k1=.011,k2=.52,T=1.30,s0=2.8,m=.5,amax=1.8,bmax=4.5,tau_a=1.0,q=.027,tc=3.0)
M={'krauss_default_dt1':('krauss',SUM_KR,1.),'krauss_default_dt01':('krauss',SUM_KR,.1),'krauss_calibrated_dt1':('krauss',un(res['krauss_dt1']['params']),1.),'krauss_calibrated_dt01':('krauss',un(res['krauss_dt01']['params']),.1),'idm_calibrated':('idm',un(res['idm']['params']),.1),'idm_hdm_table1':('idm',dict(a=1.,b=1.5,T=1.1,s0=2.,v0=35.),.1),
 'spec_no_start':('helly',SPEC,.1),'spec_start06':('helly',{**SPEC,'t_start':.6},.1),'spec_start08':('helly',{**SPEC,'t_start':.8},.1),'spec_start10':('helly',{**SPEC,'t_start':1.0},.1),'spec_start06_dt1':('helly',{**SPEC,'t_start':.6},1.),'spec_k2_fit':('helly',{**SPEC,'k2':.445,'t_start':.6},.1)}
out=dict(first_car_front_distance=fd,standing_spacing=7.0,measured=dict(h=[3.62,2.4,2.2,2.2,2.0,2.0,2.0],hsat=2.0,lost=2.74))
for nm,(k,p,dt) in M.items():
    qs=[queue(k,sample({**p,'v0':13.89},15,s_),spacing=7.0,first_dist=fd,dt=dt,seed=s_) for s_ in range(30)]
    h=np.mean([x['h'] for x in qs],axis=0);hsat=float(np.median(h[4:]));lost=float(np.sum(h[:4]-hsat))
    st=np.mean([x['start'] for x in qs],axis=0)
    out[nm]=dict(h=h.round(2).tolist(),hsat=hsat,lost=lost,start=st.round(2).tolist())
    print(nm,h[:8].round(2),round(hsat,2),round(lost,2),st[:4].round(2),flush=True)
save('queue_final',out)
