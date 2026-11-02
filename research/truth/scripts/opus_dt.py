"""Step-size sensitivity of the chosen model on the same held-out windows; the simulator runs 0.1 s and 1 s."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_windows import *
from opus_fit import split,vr
from opus_sim import ring,queue
base=sys.argv[1]; P=dict(json.loads((OUT/'fit_params_all.json').read_text())[base]['params'])
if 's0fix' in base: P['s0']=2.8
if 'sqrt' in base: P['m']=.5
if 'tau1' in base: P['tau_a']=1.0
tr,va,te=split(False);out={}
for sn,b in te.items():
    out[sn]={}
    for dt in (.1,.2,.5,1.0):
        S,V=helly(b,vr(P,b),dt);out[sn][str(dt)]=score(b,S,V)
    print(sn,{k:(round(v['spacing_rmse_30s'],2),round(v['speed_rmse_30s'],2),v['collision_frac']) for k,v in out[sn].items()},flush=True)
pp={k:v for k,v in P.items() if k!='gamma'}
out['ring']={};out['queue']={}
for dt in (.1,.5,1.0):
    out['ring'][str(dt)]=ring('helly',{**pp,'v0':11.0},dt=dt,T=600.0)
    out['queue'][str(dt)]=queue('helly',{**pp,'v0':13.89},dt=dt)
    print(dt,out['ring'][str(dt)],out['queue'][str(dt)]['h'][:6],out['queue'][str(dt)]['hsat'],flush=True)
save('dt_sensitivity',out)
