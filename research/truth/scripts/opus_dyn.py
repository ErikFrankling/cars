"""Wave and queue tests with frozen parameters: measured chains vs closed-loop models, Sugiyama ring, queue discharge."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_sim import *
from opus_fit import SUM_KR
def chains(site,W=40.0,minlen=5,stride=20.0):
    d=dict(np.load(CACHE/f'pairs_{site}.npz')); out=[]
    wn=int(W*10)
    for run in np.unique(d['run']):
        mr=d['run']==run
        P=pd.DataFrame({k:d[k][mr] for k in ('t','fid','lid','lane','cc','vf','vl','tf','tl','autof','autol')})
        t0s=np.arange(P['t'].min(),P['t'].max()-wn,int(stride*10))
        for lane,g in P.groupby('lane'):
            for t0 in t0s:
                w=g[(g['t']>=t0)&(g['t']<t0+wn)]
                if len(w)<wn: continue
                c=w.groupby(['fid','lid']).size(); c=c[c==wn]
                if len(c)<minlen-1: continue
                link={f:l for (f,l) in c.index}
                heads=set(link.values())-set(link.keys())
                for h in heads:
                    chain=[h]; rev={l:f for f,l in link.items()}
                    while chain[-1] in rev: chain.append(rev[chain[-1]])
                    if len(chain)<minlen: continue
                    V=[];S=[];ok=True
                    w2=w.sort_values('t')
                    for k in range(1,len(chain)):
                        z=w2[(w2['fid']==chain[k])&(w2['lid']==chain[k-1])]
                        if len(z)!=wn or z['autof'].iloc[0] or z['tf'].iloc[0]!=1: ok=False;break
                        if k==1: VH=z['vl'].values
                        V.append(z['vf'].values);S.append(z['cc'].values)
                    if ok: out.append(dict(site=site,run=int(run),lane=float(lane),t0=int(t0),n=len(chain),vh=VH.astype('f8'),V=np.array(V,'f8'),S=np.array(S,'f8')))
    return out
def sample(p,K,seed):
    p=dict(p);het=p.pop('het',None)
    if het:
        r=np.random.default_rng(seed)
        for k,sd in het.items(): p[k]=np.asarray(p[k])*np.exp(r.normal(0,sd,K))
    return p
def simulate_chain(c,kind,p,dt=0.1,seed=0):
    K=c['V'].shape[0];T=c['V'].shape[1];p=sample(p,K,seed)
    d=Driver(kind,p,K,dt,seed)
    steps=T-1; k=max(1,int(round(dt/0.1)))
    # positions along the lane relative to head start
    xh=np.r_[0,np.cumsum((c['vh'][1:]+c['vh'][:-1])*.05)]
    x=-np.cumsum(c['S'][:,0]); v=c['V'][:,0].copy()
    VO=np.empty_like(c['V']);SO=np.empty_like(c['S']);VO[:,0]=v;SO[:,0]=c['S'][:,0]
    for i in range(0,steps,k):
        lx=np.r_[xh[i],x[:-1]];lv=np.r_[c['vh'][i],v[:-1]]
        vn=d.step(v,lx-x,lv)
        xn,vn=advance(x,v,vn,dt,lx,3.0)
        for m in range(1,k+1):
            f=m/k; 
            if i+m<T:
                VO[:,i+m]=v+(vn-v)*f; xx=x+(xn-x)*f
                lxx=np.r_[xh[i+m],x[:-1]+(xn[:-1]-x[:-1])*f]
                SO[:,i+m]=lxx-xx
        x,v=xn,vn
    return VO,SO
def wave_lag(V,dt=0.1,maxlag=8.0):
    out=[]
    for k in range(V.shape[0]-1):
        a=V[k]-V[k].mean();b=V[k+1]-V[k+1].mean()
        if a.std()<.3 or b.std()<.3: continue
        cc=[np.dot(a[:len(a)-m],b[m:])/(len(a)-m) for m in range(0,int(maxlag/dt),5)]
        m=int(np.argmax(cc))
        if 0<m<len(cc)-1: out.append(m*.5)
    return out
def models(res,vref=30.0):
    P={}
    def un(q_):
        q_=dict(q_)
        if 'gamma' in q_: q_['v0']=q_.pop('gamma')*vref
        return q_
    def krp(n): return ('krauss',{**un(res[n]['params']),'sigma':res[n]['params'].get('sigma',0.0)},0.1 if 'dt01' in n else 1.0)
    P['krauss_default_dt01']=('krauss',SUM_KR,0.1);P['krauss_default_dt1']=('krauss',SUM_KR,1.0)
    for n in ('krauss_dt1','krauss_dt01','krauss_dt1_wide','krauss_dt01_wide'):
        if n in res: P[n]=krp(n)
    P['idm_sumo_default']=('idm',dict(a=2.6,b=4.5,T=1.0,s0=2.5,v0=33.3),0.1)
    P['idm_hdm_table1']=('idm',dict(a=1.0,b=1.5,T=1.1,s0=2.0,v0=128/3.6),0.1)
    for n in res:
        if n.startswith('krauss') or n in('newell','ctg','const_speed','speed_copy','idm_sumo_default','idm_hdm_table1') or n.startswith('human'): continue
        k='helly' if n.startswith('helly') else ('gipps' if n=='gipps' else ('idmplus' if n.startswith('idmplus') else 'idm'))
        if n=='hdm': continue
        q_=un(res[n]['params'])
        if 's0fix' in n: q_['s0']=2.8
        if 'sqrt' in n: q_['m']=0.5
        P[n]=(k,q_,0.5 if k=='gipps' else 0.1)
    for n,e in res.items():
        if n.startswith('human'): P[n]=(e['kind'],{**un(e['params']),**({'het':e['het']} if 'het' in e else {})},0.1)
    return P
def main():
    res=json.loads((OUT/'fit_params_all.json').read_text())
    res={k:v for k,v in res.items() if k in('krauss_dt1','krauss_dt01','gipps','idm','idmplus','idm_lag','helly','helly_sqrt','helly_sqrt_s0fix','krauss_dt1_wide','krauss_dt01_wide','idm_wide')}
    if (OUT/'human_params.json').exists(): res.update(json.loads((OUT/'human_params.json').read_text()))
    M=models(res); out={}
    # measured chains
    C=[]
    for s in ('I395','I90stat','I90mov'):
        c=chains(s)
        if s=='I395': c=[x for x in c if x['t0']>=39000]
        if s=='I90stat': c=[x for x in c if x['run']==6]
        print(s,'held-out chains',len(c),flush=True); C+=c
    # keep test-time chains too; report all, split later by site
    meas_sd={};poslist=(1,2,3,4,5,6,7,8)
    def sdprof(Vs):
        pf={}
        for p in poslist:
            x=[v[p-1].std() for v in Vs if v.shape[0]>=p]
            pf[p]=float(np.mean(x)) if x else None
        return pf
    out['chains']={'n':len(C),'mean_len':float(np.mean([c['n'] for c in C])),'measured_sd_by_pos':sdprof([c['V'] for c in C]),'head_sd':float(np.mean([c['vh'].std() for c in C]))}
    l=[];w=[]
    for c in C:
        for m in wave_lag(np.vstack([c['vh'],c['V']])):
            l.append(m)
        tau=wave_lag(np.vstack([c['vh'],c['V']]))
        if tau: w.append(c['S'].mean()/np.median(tau)*3.6)
    out['chains']['measured_lag']=q(l);out['chains']['measured_wave_kmh']=q(w)
    for name,(k,p,dt) in M.items():
        Vs=[];E_v=[];E_s=[];lag=[];wv=[];col=0
        for c in C:
            VO,SO=simulate_chain(c,k,p,dt)
            Vs.append(VO);E_v.append(((VO-c['V'])**2).mean(1));E_s.append(((SO-c['S'])**2).mean(1));col+=int((SO.min(1)<3.05).sum())
            tl=wave_lag(np.vstack([c['vh'],VO]))
            if tl: wv.append(SO.mean()/np.median(tl)*3.6);lag+=tl
        rm={}
        for p_ in poslist:
            ev=[e[p_-1] for e in E_v if len(e)>=p_];es=[e[p_-1] for e in E_s if len(e)>=p_]
            if ev: rm[p_]=dict(v=float(np.sqrt(np.mean(ev))),s=float(np.sqrt(np.mean(es))))
        out[name]=dict(chain_sd_by_pos=sdprof(Vs),chain_rmse=rm,chain_collisions=col,chain_lag=q(lag),chain_wave_kmh=q(wv))
        print(name,'chain v rmse pos1,4,8',[round(rm[x]['v'],2) for x in (1,4,8) if x in rm],'s',[round(rm[x]['s'],2) for x in (1,4,8) if x in rm],'SDpos',[round(out[name]['chain_sd_by_pos'][x] or 0,2) for x in (1,4,8)],'wave',out[name]['chain_wave_kmh'].get('p50'),flush=True)
        # ring at Sugiyama geometry
        pr=sample(p,22,5);pr['v0']=11.0
        out[name]['ring']=ring(k,pr,dt=dt,T=600.0)
        # queue with urban desired speed
        pq=sample(p,15,6);pq['v0']=13.89
        out[name]['queue']=queue(k,pq,dt=dt)
        print('   ring',{a:(round(b,2) if isinstance(b,float) else b) for a,b in out[name]['ring'].items()},'queue h',out[name]['queue']['h'][:8],'hsat',out[name]['queue']['hsat'],'lost',round(out[name]['queue']['lost'],2),flush=True)
    save('dynamics',out)
if __name__=='__main__': main()
