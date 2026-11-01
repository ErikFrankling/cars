"""Scores frozen fits on the held-out sets, with baselines and cluster bootstrap on paired differences."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_windows import *
from opus_fit import split,mk,SUM_KR
def per_window(b,S,V,t=300):
    es=(S[:t,0]-b.s[:t])**2; ev=(V[:t,0]-b.v[:t])**2
    return es.mean(0),ev.mean(0),(S[:t,0].min(0)<3.05)
def boot_ci(x,y,cl,n=500,seed=1):
    """paired difference of RMSE with cluster bootstrap"""
    r=np.random.default_rng(seed); u,inv=np.unique(cl,return_inverse=True); K=len(u)
    sx=np.bincount(inv,x,K);sy=np.bincount(inv,y,K);c=np.bincount(inv,minlength=K)
    out=[]
    for _ in range(n):
        w=np.bincount(r.integers(0,K,K),minlength=K)
        out.append(np.sqrt((w*sx).sum()/(w*c).sum())-np.sqrt((w*sy).sum()/(w*c).sum()))
    return np.percentile(out,[2.5,97.5]).tolist()
def clusters(b):
    # time block of 300 s within site and run: neighbouring windows share traffic state
    return np.array([f"{s}:{r}:{int(t//300)}" for s,r,t in zip(b.meta['site'],b.meta['run'],b.meta['t'])])
def run_model(name,params,b):
    if name=='const_speed': return const_speed(b)
    if name=='speed_copy': return speed_copy(b)
    if name=='newell': return newell_anchor(b,params['tau'])
    if name=='ctg': return const_time_gap(b,params['T'],params['s0'])
    if name=='krauss_default_dt1': return krauss(b,{**SUM_KR,'v0':b.meta['vref'][None,:]},1.0)
    if name=='krauss_default_dt01': return krauss(b,{**SUM_KR,'v0':b.meta['vref'][None,:]},0.1)
    if name=='idm_sumo_default': return idm_family(b,dict(a=2.6,b=4.5,T=1.0,s0=2.5,v0=b.meta['vref'][None,:]))
    if name=='idm_hdm_table1': return idm_family(b,dict(a=1.0,b=1.5,T=1.1,s0=2.0,v0=b.meta['vref'][None,:]))
    f,_,_=mk(name); return f(b,params)
def main(tag):
    t0=time.time(); train,val,test=split(tag=='us'); res=json.loads((OUT/f'fit_params_{tag}.json').read_text())
    sub=train.subset(np.arange(min(3000,train.N)))
    # baselines fitted on train
    best=None
    for tau in np.arange(0,4.01,.1):
        S,V=newell_anchor(sub,float(tau)); J=objective(sub,S,V)[0]
        if best is None or J<best[0]: best=(J,float(tau))
    res['newell']=dict(params=dict(tau=best[1]),J=float(best[0]))
    best=None
    for T in np.arange(.6,2.6,.1):
        for s0 in (1,2,3,4):
            S,V=const_time_gap(sub,float(T),float(s0)); J=objective(sub,S,V)[0]
            if best is None or J<best[0]: best=(J,float(T),float(s0))
    res['ctg']=dict(params=dict(T=best[1],s0=best[2]),J=float(best[0]))
    for n in ('const_speed','speed_copy','krauss_default_dt1','krauss_default_dt01','idm_sumo_default','idm_hdm_table1'): res.setdefault(n,dict(params={},J=None))
    sets=dict(train=train,val=val,**test)
    table={};PW={}
    for sn,b in sets.items():
        dyn=dynamic_mask(b); table[sn]=dict(windows=b.N,followers=int(len(np.unique(b.meta['fid']))),dynamic=int(dyn.sum()))
        for name,e in res.items():
            S,V=run_model(name,e['params'],b)
            sc=score(b,S,V); table[sn][name]=sc
            PW[(sn,name)]=per_window(b,S,V)
            d=dyn
            table[sn][name]['dyn_spacing_rmse_30s']=float(np.sqrt(np.mean(PW[(sn,name)][0][d])));table[sn][name]['dyn_speed_rmse_30s']=float(np.sqrt(np.mean(PW[(sn,name)][1][d])))
        print(sn,round(time.time()-t0),flush=True)
    # paired comparisons on held-out sets versus calibrated Krauss and Newell
    cmp={}
    for sn,b in sets.items():
        if sn in('train',): continue
        cl=clusters(b); cmp[sn]={}
        base=[n for n in ('krauss_dt1','krauss_dt01','newell') if (sn,n) in PW]
        for name in res:
            if name in base: continue
            for ref in base:
                es,ev,_=PW[(sn,name)]; rs,rv,_=PW[(sn,ref)]
                cmp[sn][f'{name}__vs__{ref}']=dict(spacing_ci=boot_ci(es,rs,cl),speed_ci=boot_ci(ev,rv,cl))
    save(f'tournament_{tag}',dict(params=res,table=table,paired=cmp))
    names=list(res)
    for sn in table:
        print('==',sn,table[sn]['windows'])
        for n in sorted(names,key=lambda m:table[sn][m]['spacing_rmse_30s']):
            t=table[sn][n]; print(f"{n:24s} s30 {t['spacing_rmse_30s']:6.2f} v30 {t['speed_rmse_30s']:5.2f} s10 {t['spacing_rmse_10s']:6.2f} v10 {t['speed_rmse_10s']:5.2f} s5 {t['spacing_rmse_5s']:5.2f} coll {t['collision_frac']:.3f}")
if __name__=='__main__': main(sys.argv[1])
