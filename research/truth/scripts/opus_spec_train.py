"""The specification with and without between-driver spread, on training-period chains and held-out chains; queue with spread."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_sim import *
from opus_dyn import chains,sample
import opus_dyn4_helpers as H
SPEC=dict(k1=.011,k2=.52,T=1.30,s0=2.8,m=.5,amax=1.8,bmax=4.5,tau_a=1.0,q=.027,tc=3.0,t_start=.6,v0=44.5)
Ctr=[]
for s in ('I395','I90stat'):
    c=chains(s)
    Ctr+=[x for x in c if (x['t0']<30000 if s=='I395' else x['run'] in(1,2,3,4))]
r=np.random.default_rng(3);Ctr=[Ctr[i] for i in r.choice(len(Ctr),min(250,len(Ctr)),replace=False)]
C=H.heldout_chains();out={'train_measured':dict(chains=len(Ctr),sd=H.prof([c['V'] for c in Ctr]),tg=H.tgq([c['S'] for c in Ctr],[c['V'] for c in Ctr]))}
print(out,flush=True)
for nm,ex in (('spec_T',dict(het=dict(T=.25))),('spec_all',dict(het=dict(T=.25,s0=.4,amax=.19)))):
    p={**SPEC,**ex};o=dict(train=H.run(Ctr,'helly',p,.1,2),heldout=H.run(C,'helly',p,.1,2))
    qs=[queue('helly',sample({**p,'v0':13.89},15,s_),spacing=7.0,first_dist=6.67,dt=.1,seed=s_) for s_ in range(30)]
    h=np.mean([x['h'] for x in qs],axis=0);hs=float(np.median(h[4:]));o['queue']=dict(h=h.round(2).tolist(),hsat=hs,lost=float(np.sum(h[:4]-hs)))
    rg=[ring('helly',sample({**p,'v0':11.0},22,s_),dt=.1,T=600.,seed=s_) for s_ in (1,2,3)]
    o['ring']=dict(mean_v=float(np.mean([x['mean_v'] for x in rg])),sd_v=float(np.mean([x['sd_v'] for x in rg])),stopped=float(np.mean([x['stopped_frac'] for x in rg])),wave=[x['wave_kmh'] for x in rg])
    out[nm]=o;print(nm,{a:(b['sd'],b['tg'],b['wave'],b['col'],b['s'][1],b['v'][8]) for a,b in o.items() if a in('train','heldout')},o['queue'],o['ring'],flush=True)
save('spec_train',out)
