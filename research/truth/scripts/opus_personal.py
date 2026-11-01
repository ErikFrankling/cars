"""Per-vehicle calibration: fit on one 30 s window, predict the next window of the same vehicle; split-half persistence of parameters."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_windows import *
def de_each(fun,lo,hi,names,N,pop=16,gens=30,seed=3,F=.6,CR=.8):
    r=np.random.default_rng(seed);D=len(names)
    X=lo[None,None,:]+(hi-lo)[None,None,:]*r.random((pop,N,D))
    def ev(X):
        return fun({n:X[:,:,i] for i,n in enumerate(names)})
    fx=ev(X)
    for g in range(gens):
        a,b,c=[r.integers(0,pop,(pop,N)) for _ in range(3)]
        best=X[np.argmin(fx,axis=0),np.arange(N)]
        ix=np.arange(N)[None,:]
        V_=X+F*(best[None,:,:]-X)+F*(X[b,ix]-X[c,ix])
        U=np.clip(np.where(r.random(X.shape)<CR,V_,X),lo,hi)
        fu=ev(U);m=fu<fx
        X[m]=U[m];fx[m]=fu[m]
    k=np.argmin(fx,axis=0)
    return X[k,np.arange(N)],fx[k,np.arange(N)]
def obj_each(b,S,V):
    return np.mean((S-b.s[:,None,:])**2,axis=0)/25.0+np.mean((V-b.v[:,None,:])**2,axis=0)
def wpairs(site,maxn=1500):
    w=windows(site,stride=30.0)
    key=np.array([f"{r}:{f}" for r,f in zip(w.meta['run'],w.meta['fid'])])
    order=np.lexsort((w.meta['t'],key));i1=[];i2=[]
    prev=None
    for a,b in zip(order[:-1],order[1:]):
        if key[a]==key[b] and w.meta['t'][b]-w.meta['t'][a]>=29.9 and (not i1 or i1[-1]!=a) and (not i2 or i2[-1]!=a):
            i1.append(a);i2.append(b)
    i1=np.array(i1);i2=np.array(i2)
    if len(i1)>maxn:
        p=np.random.default_rng(1).choice(len(i1),maxn,replace=False);i1=i1[p];i2=i2[p]
    return w.subset(i1),w.subset(i2)
LO=dict(k1=.005,k2=.02,T=.2,s0=.2);HI=dict(k1=1.0,k2=2.0,T=4.0,s0=8.0)
pop=json.loads((OUT/'fit_params_all.json').read_text())
out={}
for site in sys.argv[1:]:
    b1,b2=wpairs(site);print(site,'pairs',b1.N,flush=True)
    for fam,names,fixed,lo,hi in [('helly',['k1','k2','T','s0'],dict(amax=5.0,bmax=8.0,v0=45.0,m=.5),None,None),('idm',['a','b','T','s0'],dict(v0=45.0),np.array([.2,.3,.2,.2]),np.array([4,6,4,8.]))]:
        if lo is None: lo=np.array([LO[n] for n in names]);hi=np.array([HI[n] for n in names])
        def f1(p,b):
            pp={**p,**{k:np.full(p[names[0]].shape,v) for k,v in fixed.items()}}
            S,V=(helly(b,pp) if fam=='helly' else idm_family(b,pp)); return obj_each(b,S,V)
        X1,_=de_each(lambda p:f1(p,b1),lo,hi,names,b1.N)
        X2,_=de_each(lambda p:f1(p,b2),lo,hi,names,b2.N,seed=4)
        # out of sample: fit on window 1, score on window 2
        pp={n:X1[:,i].reshape(1,-1) for i,n in enumerate(names)};pp.update({k:np.full((1,b2.N),v) for k,v in fixed.items()})
        S,V=(helly(b2,pp) if fam=='helly' else idm_family(b2,pp))
        pers_s=np.sqrt(np.mean((S[:,0]-b2.s)**2));pers_v=np.sqrt(np.mean((V[:,0]-b2.v)**2))
        P=dict(pop['helly_sqrt_s0fix' if fam=='helly' else 'idm_wide']['params']);P['v0']=P.pop('gamma')*b2.meta['vref'][None,:]
        if fam=='helly': P['m']=.5;P['s0']=2.8
        S0,V0=(helly(b2,P) if fam=='helly' else idm_family(b2,P))
        pop_s=np.sqrt(np.mean((S0[:,0]-b2.s)**2));pop_v=np.sqrt(np.mean((V0[:,0]-b2.v)**2))
        # refit in sample as a floor
        pp2={n:X2[:,i].reshape(1,-1) for i,n in enumerate(names)};pp2.update({k:np.full((1,b2.N),v) for k,v in fixed.items()})
        S2,V2=(helly(b2,pp2) if fam=='helly' else idm_family(b2,pp2))
        floor_s=np.sqrt(np.mean((S2[:,0]-b2.s)**2));floor_v=np.sqrt(np.mean((V2[:,0]-b2.v)**2))
        R=dict(n=b1.N,population_on_w2=dict(s=pop_s,v=pop_v),personal_w1_on_w2=dict(s=pers_s,v=pers_v),insample_floor_w2=dict(s=floor_s,v=floor_v),params={})
        for i,n in enumerate(names):
            a=np.log(X1[:,i]);c=np.log(X2[:,i]);cov=np.cov(a,c)
            R['params'][n]=dict(median=float(np.exp(np.median(a))),q=q(X1[:,i],(5,25,50,75,95)),log_sd_total=float(a.std()),split_half_r=float(np.corrcoef(a,c)[0,1]),log_sd_persistent=float(np.sqrt(max(cov[0,1],0))))
        cm=np.corrcoef(np.log(X1).T);R['log_corr_w1']=cm.round(3).tolist()
        R['names']=names
        out.setdefault(site,{})[fam]=R
        print(site,fam,{k:R[k] for k in('population_on_w2','personal_w1_on_w2','insample_floor_w2')},{n:(round(R['params'][n]['median'],3),round(R['params'][n]['log_sd_total'],2),round(R['params'][n]['split_half_r'],2),round(R['params'][n]['log_sd_persistent'],2)) for n in names},flush=True)
save('personal',out)
