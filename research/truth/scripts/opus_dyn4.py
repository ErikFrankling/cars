"""Final closed-loop comparison on held-out chains, training chains for the lag choice, Sugiyama ring, longer ring, queue. Parameters frozen from fit_params_all."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_sim import *
from opus_dyn import chains,simulate_chain,wave_lag,sample
from opus_fit import SUM_KR
res=json.loads((OUT/'fit_params_all.json').read_text());VR=30.0
def un(p):
    p=dict(p)
    if 'gamma' in p: p['v0']=p.pop('gamma')*VR
    return p
F=un(res['helly_sqrt_s0fix_tau1']['params']);F.update(s0=2.8,m=.5,tau_a=1.0)
L=un(res['helly_sqrt_s0fix_lag']['params']);L.update(s0=2.8,m=.5)
N0=un(res['helly_sqrt_s0fix']['params']);N0.update(s0=2.8,m=.5)
M={'krauss_default_dt01':('krauss',SUM_KR,.1,1),'krauss_default_dt1':('krauss',SUM_KR,1.,1),'krauss_calibrated_dt1':('krauss',{**un(res['krauss_dt1']['params'])},1.,1),'krauss_calibrated_dt01':('krauss',{**un(res['krauss_dt01']['params'])},.1,1),
 'idm_calibrated':('idm',un(res['idm']['params']),.1,1),'idm_hdm_table1':('idm',dict(a=1.,b=1.5,T=1.1,s0=2.,v0=128/3.6),.1,1),'idmplus_calibrated':('idmplus',un(res['idmplus']['params']),.1,1),'gipps_calibrated':('gipps',un(res['gipps']['params']),.5,1),
 'feedback_no_lag':('helly',N0,.1,1),'feedback_fit_lag':('helly',L,.1,1),'feedback_lag1':('helly',F,.1,1),
 'human_noise':('helly',{**F,'q':.027,'tc':3.0},.1,3),'human_noise_start':('helly',{**F,'q':.027,'tc':3.0,'t_start':.6},.1,3),'human_full':('helly',{**F,'q':.027,'tc':3.0,'t_start':.6,'het':dict(T=.25)},.1,3),'human_full_dt1':('helly',{**F,'q':.027,'tc':3.0,'t_start':.6,'het':dict(T=.25)},1.,3)}
Cte=[];Ctr=[]
for s in ('I395','I90stat','I90mov'):
    c=chains(s)
    if s=='I395': Cte+=[x for x in c if x['t0']>=39000];Ctr+=[x for x in c if x['t0']<30000]
    elif s=='I90stat': Cte+=[x for x in c if x['run']==6];Ctr+=[x for x in c if x['run'] in(1,2,3,4)]
    else: Cte+=c
r=np.random.default_rng(3);Ctr=[Ctr[i] for i in r.choice(len(Ctr),min(250,len(Ctr)),replace=False)] if Ctr else []
pos=(1,2,3,4,5,6,7,8)
def prof(Vs): return {p:float(np.mean([v[p-1].std() for v in Vs if v.shape[0]>=p])) for p in pos}
def tgq(Ss,Vs):
    a=np.concatenate([((s_-5)/np.maximum(v_,1))[v_>3][::20] for s_,v_ in zip(Ss,Vs)]);return q(a,(5,25,50,75,95))
def meas(C):
    l=[];w=[]
    for c in C:
        tl=wave_lag(np.vstack([c['vh'],c['V']]))
        if tl: l+=tl;w.append(c['S'].mean()/np.median(tl)*3.6)
    return dict(chains=len(C),vehicles=int(sum(c['V'].shape[0] for c in C)),sd=prof([c['V'] for c in C]),time_gap=tgq([c['S'] for c in C],[c['V'] for c in C]),head_sd=float(np.mean([c['vh'].std() for c in C])),lag=q(l),wave=q(w))
out={'measured_heldout':meas(Cte),'measured_train':meas(Ctr) if Ctr else {}}
print(out['measured_heldout'],out['measured_train'].get('sd'),flush=True)
def run(C,kind,p,dt,seeds):
    Rs=[]
    for seed in range(seeds):
        Vo=[];So=[];ev=[];es=[];wv=[];col=0
        for i,c in enumerate(C):
            VO,SO=simulate_chain(c,kind,p,dt,seed=seed*1000+i)
            Vo.append(VO);So.append(SO);ev.append(((VO-c['V'])**2).mean(1));es.append(((SO-c['S'])**2).mean(1));col+=int((SO.min(1)<3.05).sum())
            tl=wave_lag(np.vstack([c['vh'],VO]))
            if tl: wv.append(SO.mean()/np.median(tl)*3.6)
        Rs.append(dict(sd=prof(Vo),tg=tgq(So,Vo),wave=float(np.median(wv)) if wv else np.nan,col=col,v={p_:float(np.sqrt(np.mean([e[p_-1] for e in ev if len(e)>=p_]))) for p_ in pos},s={p_:float(np.sqrt(np.mean([e[p_-1] for e in es if len(e)>=p_]))) for p_ in pos}))
    return dict(sd={p_:float(np.mean([x['sd'][p_] for x in Rs])) for p_ in pos},tg={k:float(np.mean([x['tg'][k] for x in Rs])) for k in Rs[0]['tg']},wave=float(np.nanmean([x['wave'] for x in Rs])),col=float(np.mean([x['col'] for x in Rs])),v={p_:float(np.mean([x['v'][p_] for x in Rs])) for p_ in pos},s={p_:float(np.mean([x['s'][p_] for x in Rs])) for p_ in pos})
for name,(kind,p,dt,seeds) in M.items():
    t0=time.time();o=dict(heldout=run(Cte,kind,p,dt,seeds))
    if Ctr and name.startswith('feedback'): o['train']=run(Ctr,kind,p,dt,seeds)
    rg=[ring(kind,sample({**p,'v0':11.0},22,s_),dt=dt,T=600.0,seed=s_) for s_ in (1,2,3)]
    rl=[ring(kind,sample({**p,'v0':15.0},22,s_),L=400.0,dt=dt,T=600.0,seed=s_) for s_ in (1,2,3)]
    o['ring_230']=dict(mean_v=float(np.mean([x['mean_v'] for x in rg])),sd_v=float(np.mean([x['sd_v'] for x in rg])),stopped=float(np.mean([x['stopped_frac'] for x in rg])),wave=[x['wave_kmh'] for x in rg],max_v=float(np.mean([x['max_v'] for x in rg])))
    o['ring_400']=dict(mean_v=float(np.mean([x['mean_v'] for x in rl])),sd_v=float(np.mean([x['sd_v'] for x in rl])),stopped=float(np.mean([x['stopped_frac'] for x in rl])),wave=[x['wave_kmh'] for x in rl])
    qs=[queue(kind,sample({**p,'v0':13.89},15,s_),dt=dt,seed=s_) for s_ in range(12)]
    o['queue']=dict(h=np.mean([x['h'] for x in qs],axis=0).round(2).tolist(),hsat=float(np.mean([x['hsat'] for x in qs])),lost=float(np.mean([x['lost'] for x in qs])),start=np.mean([x['start'] for x in qs],axis=0).round(2).tolist())
    out[name]=o;save('dynamics_final',out)
    h=o['heldout'];print(name,round(time.time()-t0),'sd',[round(h['sd'][k],2) for k in (1,4,8)],'tg',[round(h['tg'][k],2) for k in('p05','p50','p95')],'wave',round(h['wave'],1),'v',[round(h['v'][k],2) for k in (1,8)],'s',[round(h['s'][k],2) for k in (1,8)],'col',h['col'],'ring',round(o['ring_230']['mean_v'],2),round(o['ring_230']['sd_v'],2),round(o['ring_230']['stopped'],2),o['ring_230']['wave'],'r400',round(o['ring_400']['sd_v'],2),o['ring_400']['wave'],'q',o['queue']['h'][:6],round(o['queue']['hsat'],2),round(o['queue']['lost'],2),('train_sd',[round(o['train']['sd'][k],2) for k in (1,4,8)],round(o['train']['wave'],1)) if 'train' in o else '',flush=True)
print('DYN4_DONE')
