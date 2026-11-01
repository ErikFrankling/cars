"""Shared chain test for the specification score."""
from opus_common import *
from opus_dyn import chains,simulate_chain,wave_lag
pos=(1,2,3,4,5,6,7,8)
def heldout_chains():
    C=[]
    for s in ('I395','I90stat','I90mov'):
        c=chains(s)
        if s=='I395': c=[x for x in c if x['t0']>=39000]
        if s=='I90stat': c=[x for x in c if x['run']==6]
        C+=c
    return C
def prof(Vs): return {p:float(np.mean([v[p-1].std() for v in Vs if v.shape[0]>=p])) for p in pos}
def tgq(Ss,Vs):
    a=np.concatenate([((s_-5)/np.maximum(v_,1))[v_>3][::20] for s_,v_ in zip(Ss,Vs)]);return q(a,(5,25,50,75,95))
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
