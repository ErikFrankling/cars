"""Mechanism ablation on the chosen model: measured noise, drifting time gap, between-driver spread, startup delay. Held-out chains, ring, queue."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_sim import *
from opus_dyn import chains,simulate_chain,wave_lag,sample
base=json.loads((OUT/'fit_params_all.json').read_text())['helly_sqrt_s0fix']['params']
P0={k:v for k,v in base.items() if k!='gamma'};P0.update(s0=2.8,m=.5,v0=base['gamma']*30.0)
V={'lag03':dict(tau_a=.3),'lag05':dict(tau_a=.5),'lag10':dict(tau_a=1.0),'lag15':dict(tau_a=1.5),
 'lag10_n02':dict(tau_a=1.0,q=.027,tc=3.0),'lag10_n03':dict(tau_a=1.0,q=.06,tc=3.0),
 'lag05_n03':dict(tau_a=.5,q=.06,tc=3.0),'lag05_n03_start':dict(tau_a=.5,q=.06,tc=3.0,t_start=.6),
 'lag10_n03_start':dict(tau_a=1.0,q=.06,tc=3.0,t_start=.6),'lag10_n03_full':dict(tau_a=1.0,q=.06,tc=3.0,t_start=.6,T_sd=.2,T_tc=20.0,het=dict(T=.25))}
from opus_fit import split,vr
tr,va,te=split(False);rp={}
for nm,ex in V.items():
    if 'q' in ex or 'T_sd' in ex or 'het' in ex: continue
    P_={**base,'s0':2.8,'m':.5,'tau_a':ex['tau_a']}
    rp[nm]={sn:(lambda sc:[round(sc['spacing_rmse_30s'],3),round(sc['speed_rmse_30s'],3),round(sc['spacing_rmse_5s'],3),round(sc['speed_rmse_5s'],3)])(score(b_,*helly(b_,vr(P_,b_)))) for sn,b_ in te.items()}
    print('replay',nm,rp[nm],flush=True)
del tr,va,te
C=[]
for s in ('I395','I90stat','I90mov'):
    c=chains(s)
    if s=='I395': c=[x for x in c if x['t0']>=39000]
    if s=='I90stat': c=[x for x in c if x['run']==6]
    C+=c
print('chains',len(C),flush=True)
pos=(1,2,3,4,5,6,7,8)
def prof(Vs): return {p:float(np.mean([v[p-1].std() for v in Vs if v.shape[0]>=p])) for p in pos}
def tgq(Ss,Vs):
    a=[]
    for s_,v_ in zip(Ss,Vs):
        m=v_>3;a.append(((s_-5)/np.maximum(v_,1))[m][::20])
    a=np.concatenate(a); return q(a,(5,25,50,75,95))
def osc(Vs):
    # fraction of chain vehicles whose speed range grows from first to last third of the chain
    return float(np.mean([v[-1].std()/max(v[0].std(),.1) for v in Vs]))
out={'measured':dict(chains=len(C),sd=prof([c['V'] for c in C]),time_gap=tgq([c['S'] for c in C],[c['V'] for c in C]),sd_ratio_last_first=osc([c['V'] for c in C]),head_sd=float(np.mean([c['vh'].std() for c in C])))}
l=[];w=[]
for c in C:
    tl=wave_lag(np.vstack([c['vh'],c['V']]))
    if tl: l+=tl; w.append(c['S'].mean()/np.median(tl)*3.6)
out['measured'].update(lag=q(l),wave=q(w))
print(out['measured'],flush=True)
for name,ex in V.items():
    p={**P0,**ex};t0=time.time();res=[]
    Rs=[]
    for seed in (0,1,2):
        Vo=[];So=[];ev=[];es=[];wv=[];col=0
        for i,c in enumerate(C):
            VO,SO=simulate_chain(c,'helly',p,.1,seed=seed*1000+i)
            Vo.append(VO);So.append(SO);ev.append(((VO-c['V'])**2).mean(1));es.append(((SO-c['S'])**2).mean(1));col+=int((SO.min(1)<3.05).sum())
            tl=wave_lag(np.vstack([c['vh'],VO]))
            if tl: wv.append(SO.mean()/np.median(tl)*3.6)
        Rs.append(dict(sd=prof(Vo),tg=tgq(So,Vo),ratio=osc(Vo),wave=float(np.median(wv)) if wv else None,col=col,v={p_:float(np.sqrt(np.mean([e[p_-1] for e in ev if len(e)>=p_]))) for p_ in pos},s={p_:float(np.sqrt(np.mean([e[p_-1] for e in es if len(e)>=p_]))) for p_ in pos}))
    r=dict(sd={p_:float(np.mean([x['sd'][p_] for x in Rs])) for p_ in pos},tg={k:float(np.mean([x['tg'][k] for x in Rs])) for k in Rs[0]['tg']},ratio=float(np.mean([x['ratio'] for x in Rs])),wave=float(np.mean([x['wave'] for x in Rs if x['wave']])),col=float(np.mean([x['col'] for x in Rs])),v={p_:float(np.mean([x['v'][p_] for x in Rs])) for p_ in pos},s={p_:float(np.mean([x['s'][p_] for x in Rs])) for p_ in pos})
    rg=[]
    for seed in (1,2):
        pr=sample({**p,'v0':11.0},22,seed);rg.append(ring('helly',pr,dt=.1,T=600.0,seed=seed))
    r['ring_sugiyama']=rg
    rl=[]
    for seed in (1,2):
        pr=sample({**p,'v0':15.0},22,seed);rl.append(ring('helly',pr,L=400.0,dt=.1,T=600.0,seed=seed))
    r['ring_400m']=rl
    qs=[queue('helly',sample({**p,'v0':13.89},15,s_),dt=.1,seed=s_) for s_ in range(12)]
    r['queue']=dict(h=np.mean([x['h'] for x in qs],axis=0).round(2).tolist(),hsat=float(np.mean([x['hsat'] for x in qs])),lost=float(np.mean([x['lost'] for x in qs])),start=np.mean([x['start'] for x in qs],axis=0).round(2).tolist())
    out[name]=r
    print(name,round(time.time()-t0),'sd',[round(r['sd'][k],2) for k in (1,4,8)],'tg',[round(r['tg'][k],2) for k in('p05','p50','p95')],'wave',round(r['wave'],1),'v',[round(r['v'][k],2) for k in (1,8)],'s',[round(r['s'][k],2) for k in (1,8)],'col',r['col'],'ring',[(round(x['mean_v'],2),round(x['sd_v'],2),x['wave_kmh']) for x in rg],'r400',[(round(x['mean_v'],2),round(x['sd_v'],2),x['wave_kmh']) for x in rl],'q',r['queue']['h'][:6],round(r['queue']['hsat'],2),round(r['queue']['lost'],2),flush=True)
    out['replay']=rp;save('dyn_ablation_lag',out)
