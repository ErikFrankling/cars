"""Scores exactly the parameters written into the WGSL specification: replay on all held-out sets, step sizes, closed-loop tests."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_sim import *
from opus_dyn import chains,simulate_chain,wave_lag,sample
from opus_fit import split,vr,SUM_KR
import opus_dyn4_helpers as H
SPEC=dict(k1=.011,k2=.52,T=1.30,s0=2.8,m=.5,amax=1.8,bmax=4.5,tau_a=1.0)
res=json.loads((OUT/'fit_params_all.json').read_text());g=res['helly_sqrt_s0fix_tau1']['params']['gamma']
out={'spec':SPEC,'gamma_used':g}
tr,va,te=split(False)
for sn,b in {'val':va,**te}.items():
    out[sn]={}
    for dt in (.1,.5,1.0):
        S,V=helly(b,{**SPEC,'v0':g*b.meta['vref'][None,:]},dt);sc=score(b,S,V);out[sn][str(dt)]=sc
    print(sn,{k:(round(v['spacing_rmse_30s'],2),round(v['speed_rmse_30s'],2),round(v['collision_frac'],4)) for k,v in out[sn].items()},flush=True)
_,_,te2=split(True);b=te2['HT_all_external'];S,V=helly(b,{**SPEC,'v0':g*b.meta['vref'][None,:]});out['HT_all_external']={'0.1':score(b,S,V)};print('HT ext',out['HT_all_external']['0.1'],flush=True)
del tr,va,te,te2
C=H.heldout_chains()
Vs={'spec_det':{},'spec_noise':dict(q=.027,tc=3.0),'spec_full':dict(q=.027,tc=3.0,t_start=.6,het=dict(T=.25)),'spec_full_s10':dict(q=.027,tc=3.0,t_start=1.0,het=dict(T=.25))}
for name,ex in Vs.items():
    p={**SPEC,'v0':g*30.0,**ex};o=dict(heldout=H.run(C,'helly',p,.1,3 if ex else 1))
    if name=='spec_full': o['heldout_dt1']=H.run(C,'helly',p,1.0,3)
    for lab,L,v0 in (('ring_230',230.,11.),('ring_400',400.,15.)):
        rg=[ring('helly',sample({**p,'v0':v0},22,s_),L=L,dt=.1,T=600.,seed=s_) for s_ in (1,2,3)]
        o[lab]=dict(mean_v=float(np.mean([x['mean_v'] for x in rg])),sd_v=float(np.mean([x['sd_v'] for x in rg])),stopped=float(np.mean([x['stopped_frac'] for x in rg])),wave=[x['wave_kmh'] for x in rg])
    qs=[queue('helly',sample({**p,'v0':13.89},15,s_),dt=.1,seed=s_) for s_ in range(30)]
    o['queue']=dict(h=np.mean([x['h'] for x in qs],axis=0).round(2).tolist(),hsat=float(np.mean([x['hsat'] for x in qs])),lost=float(np.mean([x['lost'] for x in qs])),start=np.mean([x['start'] for x in qs],axis=0).round(2).tolist())
    out[name]=o;save('spec_score',out)
    h=o['heldout'];print(name,'sd',[round(h['sd'][k],2) for k in (1,4,8)],'tg',[round(h['tg'][k],2) for k in('p05','p50','p95')],'wave',round(h['wave'],1),'v',[round(h['v'][k],2) for k in (1,8)],'s',[round(h['s'][k],2) for k in (1,8)],'col',h['col'],o['ring_230'],o['ring_400'],o['queue']['h'][:6],round(o['queue']['hsat'],2),round(o['queue']['lost'],2),flush=True)
print('SPEC_DONE')
