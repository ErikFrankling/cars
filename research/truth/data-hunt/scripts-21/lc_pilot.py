"""Report 21 pilot. Lane-change decision on TGSIM freeways: rule-shaped logit, full logit and small networks,
open loop, frozen splits, held out by run, day and road. Reads CSVs as inert data. One thread, under 1.5 GB.
Run from anywhere: python3 -I lc_pilot.py [out.json]"""
import os, sys, json, time
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
import numpy as np, pandas as pd
T='/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-tgsim/'
OUT=sys.argv[1] if len(sys.argv)>1 else 'lc_pilot.json'
SITES={'I90stat':'av','I90mov':'av','I294L1':'acc'}
CAP=150.; EDGE=60.
NAMES=['v','own_gap','own_dv','tl_gap','tl_dv','tf_gap','tf_dv','tg_lead','tg_foll','inv_own','inv_tl','inv_tf','da_self','a_newf']
def idm(v,dv,gap,a=1.4,b=2.,T_=1.5,s0=2.,v0=33.):
    st=s0+np.maximum(0,v*T_+v*(-dv)/(2*np.sqrt(a*b)))
    return np.clip(a*(1-(v/v0)**4-(st/np.maximum(gap,.5))**2),-9,a)
def load(site):
    flag=SITES[site]; keep=[]
    for ch in pd.read_csv(T+site+'.csv',chunksize=500000,low_memory=False):
        ch.columns=[c.strip().lower() for c in ch.columns]
        ti=np.round(ch['time'].values*10).astype(np.int32)
        m=ti%10==0
        c=ch.loc[m,['run_index','id','xloc_kf','yloc_kf','lane_kf','speed_kf','type_most_common',flag]].copy()
        c['t']=(ti[m]//10).astype(np.int32)
        c['auto']=c[flag].astype(str).str.strip().str.lower().map(lambda x:0 if x in('no','0','false','nan','') else 1).astype(np.int8)
        c['car']=(c['type_most_common'].astype(str).str.contains('small')).astype(np.int8)
        keep.append(c.drop(columns=[flag,'type_most_common']))
    d=pd.concat(keep,ignore_index=True).drop_duplicates(['run_index','id','t'])
    d=d.astype({'run_index':np.int16,'id':np.int32,'xloc_kf':np.float64,'yloc_kf':np.float64,'speed_kf':np.float32})
    d=d[np.isfinite(d['lane_kf'])]; d['lane']=d['lane_kf'].astype(np.int16)
    return d.drop(columns='lane_kf')
def samples(site):
    cache=f'/tmp/r21/pilot_{site}.npz'
    if os.path.exists(cache):
        z=np.load(cache); return z['X'],z['Y'],z['G'],json.loads(str(z['stats']))
    d=load(site); n0=len(d); d=d[np.isfinite(d['xloc_kf'])&np.isfinite(d['yloc_kf'])&np.isfinite(d['speed_kf'])]
    print(site,'rows without a finite position or speed, dropped',n0-len(d),flush=True)
    d=d.sort_values(['run_index','id','t']).reset_index(drop=True)
    stats=dict(rows=len(d),events=0,vehkm=0.,tracks=int(d.groupby(['run_index','id']).ngroups))
    along=np.zeros(len(d)); axes={}
    for r,ix in d.groupby('run_index').indices.items():
        xy=d[['xloc_kf','yloc_kf']].values[ix]; xy=xy-xy.mean(0)
        w,vec=np.linalg.eigh(xy.T@xy); u=vec[:,-1]; along[ix]=xy@u; axes[int(r)]=round(float(w[-1]/max(w[0],1e-9)),1)
    d['along']=along; stats['axis_ratio_by_run']=axes
    g=d.groupby(['run_index','id'])['along']; sg=np.sign(g.transform('last').values-g.transform('first').values)
    d=d[sg!=0].reset_index(drop=True); sg=sg[sg!=0].astype(np.int64)
    run,idv,t,lane,v=[d[c].values for c in ('run_index','id','t','lane','speed_kf')]
    s=d['along'].values.astype(np.float64)*sg; v=v.astype(np.float64); lane=lane.astype(np.int64); run=run.astype(np.int64); t=t.astype(np.int64)
    # the same vehicle at another second
    k=run*10**12+idv.astype(np.int64)*10**5+t; o=np.argsort(k); ks=k[o]; ln=lane[o]
    def at(off):
        q=np.minimum(np.searchsorted(ks,k+off),len(ks)-1); r=ln[q].copy(); r[ks[q]!=k+off]=-999; return r
    stable=(at(1)==lane)&(at(2)==lane)&(at(3)!=-999)
    for j in range(1,6):
        a_=at(-j); stable&=(a_==lane)|(a_==-999)
    ch=at(3)-lane; ev=stable&(np.abs(ch)==1); chg=np.where(ev,ch,0)
    stats['events']=int(ev.sum()); stats['vehkm']=float(v[stable].sum()/1000)
    # view limits by run and direction
    lim=pd.DataFrame(dict(r=run,g=sg,s=s)).groupby(['r','g'])['s'].agg(['min','max'])
    mi=pd.MultiIndex.from_arrays([run,sg])
    lo=lim['min'].reindex(mi).values+EDGE; hi=lim['max'].reindex(mi).values-EDGE
    # neighbours: composite key of frame, direction and lane, then position along the road
    off=s-s.min()
    def G(l): return ((run*100000+t)*2+(sg>0))*1000+(l+100)
    keyall=G(lane)*1e5+off; order=np.argsort(keyall); K=keyall[order]; Gs=G(lane)[order]
    def nb(l,own=False):
        gq=G(l); j=np.searchsorted(K,gq*1e5+off,side='right')
        jl=np.minimum(j,len(K)-1); okl=(j<len(K))&(Gs[jl]==gq)
        jf=j-2 if own else j-1      # in the own lane, position j-1 is the car itself
        jf2=np.maximum(jf,0); okf=(jf>=0)&(Gs[jf2]==gq)
        return order[jl],okl,order[jf2],okf
    ego=stable&(d['auto'].values==0)&(d['car'].values==1)&(s>lo)&(s<hi)
    ol,okl,_,_=nb(lane,True)
    gl=np.where(okl,np.minimum(s[ol]-s,CAP),CAP); dvl=np.where(okl,v[ol]-v,0.)
    X=[];Y=[];Gout=[]
    for side in (-1,1):
        tl_i,ok_tl,tf_i,ok_tf=nb(lane+side)
        m=ego&(ok_tl|ok_tf)        # no car seen in that lane in this frame: no choice to model
        tl=np.where(ok_tl,np.minimum(s[tl_i]-s,CAP),CAP); tdv=np.where(ok_tl,v[tl_i]-v,0.)
        tf=np.where(ok_tf,np.minimum(s-s[tf_i],CAP),CAP); fv=np.where(ok_tf,v[tf_i],v)
        tgl=np.clip((tl-5)/np.maximum(v,1.),0,10); tgf=np.clip((tf-5)/np.maximum(fv,1.),0,10)
        da=idm(v,tdv,np.maximum(tl-5,.5))-idm(v,dvl,np.maximum(gl-5,.5)); an=idm(fv,v-fv,np.maximum(tf-5,.5))
        F=np.stack([v,gl,dvl,tl,tdv,tf,v-fv,tgl,tgf,1/np.maximum(gl,1.),1/np.maximum(tl,1.),1/np.maximum(tf,1.),da,an],1)[m]
        X.append(F.astype(np.float32)); Y.append((chg[m]==side).astype(np.int8)); Gout.append(np.stack([run[m],idv[m].astype(np.int64)],1))
    X,Y,Gout=np.concatenate(X),np.concatenate(Y),np.concatenate(Gout)
    np.savez(cache,X=X,Y=Y,G=Gout,stats=json.dumps(stats))
    print(site,stats,'samples',len(Y),'positive',int(Y.sum()),flush=True)
    return X,Y,Gout,stats
def logloss(p,y): p=np.clip(p,1e-7,1-1e-7); return -(y*np.log(p)+(1-y)*np.log(1-p))
def auc(p,y):
    r=pd.Series(p).rank().values; n1=y.sum(); n0=len(y)-n1
    return float((r[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
class Net:
    def __init__(s,sizes,seed):
        rng=np.random.default_rng(seed); s.W=[rng.normal(0,1/np.sqrt(a),(a,b)) for a,b in zip(sizes[:-1],sizes[1:])]
        s.B=[np.zeros(b) for b in sizes[1:]]; s.p=sum(w.size for w in s.W)+sum(b.size for b in s.B)
    def f(s,x,cache=False):
        a=[x]; 
        for w,b in zip(s.W[:-1],s.B[:-1]): a.append(np.tanh(a[-1]@w+b))
        out=(a[-1]@s.W[-1]+s.B[-1])[:,0]
        return (out,a) if cache else out
def fit(net,X,y,Xv,yv,epochs=25,bs=2048,lr=2e-3,wd=1e-4,seed=0,base=None):
    rng=np.random.default_rng(seed); ps=net.W+net.B; m=[np.zeros_like(p) for p in ps]; v2=[np.zeros_like(p) for p in ps]
    net.B[-1][:]=np.log(base/(1-base)); best=(1e9,None); t=0
    for ep in range(epochs):
        idx=rng.permutation(len(y))
        for st in range(0,len(y)-bs+1,bs):
            b=idx[st:st+bs]; out,a=net.f(X[b],True); g=(1/(1+np.exp(-out))-y[b])/bs
            gW=[None]*len(net.W); gB=[None]*len(net.B); d=g[:,None]
            gW[-1]=a[-1].T@d; gB[-1]=d.sum(0); dn=d@net.W[-1].T
            for i in range(len(net.W)-2,-1,-1):
                dh=(1-np.tanh(a[i]@net.W[i]+net.B[i])**2)*dn
                gW[i]=a[i].T@dh; gB[i]=dh.sum(0); dn=dh@net.W[i].T
            gs=gW+gB; t+=1
            for p,gr,mm,vv in zip(ps,gs,m,v2):
                gr=gr+(wd*p if p.ndim==2 else 0)
                mm*=.9; mm+=.1*gr; vv*=.999; vv+=.001*gr*gr
                p-=lr*(mm/(1-.9**t))/(np.sqrt(vv/(1-.999**t))+1e-8)
        l=logloss(1/(1+np.exp(-net.f(Xv))),yv).mean()
        if l<best[0]: best=(l,[p.copy() for p in ps])
    for p,q in zip(ps,best[1]): p[:]=q
    return net
def lbfgs(X,y,base,l2=1e-5):
    from scipy.optimize import minimize
    n,d_=X.shape
    def f(th):
        o=X@th[:-1]+th[-1]; l=np.logaddexp(0,-o)*y+np.logaddexp(0,o)*(1-y)
        pr=1/(1+np.exp(-o)); g=X.T@(pr-y)/n+l2*th[:-1]
        return l.mean()+.5*l2*(th[:-1]**2).sum(),np.r_[g,(pr-y).mean()]
    r=minimize(f,np.r_[np.zeros(d_),np.log(base/(1-base))],jac=True,method='L-BFGS-B',options=dict(maxiter=500))
    net=Net([d_,1],0); net.W[0][:,0]=r.x[:-1]; net.B[0][0]=r.x[-1]; net.converged=bool(r.success); return net
def main():
    t0=time.time(); D={}
    for s in SITES: D[s]=samples(s); print('t',round(time.time()-t0),flush=True)
    res=dict(counts={s:D[s][3] for s in D},features=NAMES)
    def sel(s,runs=None):
        X,y,g,_=D[s]
        m=np.ones(len(y),bool) if runs is None else np.isin(g[:,0],runs)
        return X[m],y[m],g[m]
    splits={
     'mixed':dict(train=[('I90stat',[1,2,3,4]),('I294L1',[1,3,7,8])],val=[('I90stat',[5]),('I294L1',[9])],
        tests={'I90stat run 6':('I90stat',[6]),'I90mov other day':('I90mov',None),'I294 later runs':('I294L1',[11,18,19,20,21])}),
     'I90 only, other road':dict(train=[('I90stat',[1,2,3,4])],val=[('I90stat',[5])],
        tests={'I294 all, never seen':('I294L1',None),'I90mov other day':('I90mov',None)}),
     'I294 only, other road':dict(train=[('I294L1',[1,3,7,8])],val=[('I294L1',[9])],
        tests={'I90stat all, never seen':('I90stat',None),'I90mov all, never seen':('I90mov',None)}),
    }
    rng=np.random.default_rng(7)
    for name,sp in splits.items():
        tr=[sel(*a) for a in sp['train']]; va=[sel(*a) for a in sp['val']]
        X=np.concatenate([a[0] for a in tr]); y=np.concatenate([a[1] for a in tr]); Xv=np.concatenate([a[0] for a in va]); yv=np.concatenate([a[1] for a in va])
        mu,sd=X.mean(0),X.std(0)+1e-6; Z=lambda a:np.clip((a-mu)/sd,-8,8)
        base=y.mean(); out=dict(train_samples=int(len(y)),train_events=int(y.sum()),base_rate=float(base),tests={})
        rule=[0,1,2,3,4,5,6,7,8,9,10,11]
        M={'rule-shaped logit, 2 inputs (IDM gain, new follower decel), 3 params':lambda a:a[:,[12,13]],
           'logit, 14 inputs, 15 params':lambda a:a,
           'logit with squares, 28 inputs, 29 params':lambda a:np.hstack([a,a*a])}
        fitted={}
        Zt_=Z(X).astype(np.float64); Zv_=Z(Xv).astype(np.float64); yd=y.astype(np.float64); yvd=yv.astype(np.float64)
        for mn,pick in M.items():
            fitted[mn]=(pick,lbfgs(pick(Zt_),yd,base)); print(name,mn,fitted[mn][1].converged,round(time.time()-t0),flush=True)
        for seed,sz,lab in ((0,(14,8,8,1),'network 14-8-8-1, 201 params'),(1,(14,8,8,1),'network 14-8-8-1, 201 params'),(0,(14,32,32,1),'network 14-32-32-1, 1,537 params'),(1,(14,32,32,1),'network 14-32-32-1, 1,537 params')):
            nn=fit(Net(list(sz),seed),Zt_,yd,Zv_,yvd,epochs=40,bs=4096,base=base,seed=seed)
            fitted[f'{lab}, seed {seed}']=((lambda a:a),nn); print(name,lab,seed,round(time.time()-t0),flush=True)
        for tn,(s,runs) in sp['tests'].items():
            Xt,yt,gt=sel(s,runs); Zt=Z(Xt).astype(np.float64); rowres={}
            ll0=logloss(np.full(len(yt),base),yt); uid,inv=np.unique(gt[:,0]*10**7+gt[:,1],return_inverse=True)
            per0=np.bincount(inv,ll0,len(uid))
            ref=None
            for mn,(pick,nn) in fitted.items():
                p=1/(1+np.exp(-nn.f(pick(Zt)))); ll=logloss(p,yt); per=np.bincount(inv,ll,len(uid))
                rowres[mn]=dict(auc=round(auc(p,yt),4),ll_skill=round(float(1-ll.sum()/ll0.sum()),4),pred_rate=float(p.mean()))
                if mn.startswith('logit,'): ref=per
                if mn.startswith('logit with'): ref2=per
            for mn,(pick,nn) in fitted.items():
                if not mn.startswith('network'): continue
                p=1/(1+np.exp(-nn.f(pick(Zt)))); per=np.bincount(inv,logloss(p,yt),len(uid))
                ds=[];ds2=[]
                for _ in range(200):
                    w=rng.multinomial(len(uid),np.ones(len(uid))/len(uid))
                    ds.append(((per*w).sum()/(per0*w).sum())-((ref*w).sum()/(per0*w).sum())); ds2.append(((per*w).sum()/(per0*w).sum())-((ref2*w).sum()/(per0*w).sum()))
                rowres[mn]['ll_ratio_minus_logit_ci95']=[round(float(np.percentile(ds,2.5)),4),round(float(np.percentile(ds,97.5)),4)]
                rowres[mn]['ll_ratio_minus_squares_ci95']=[round(float(np.percentile(ds2,2.5)),4),round(float(np.percentile(ds2,97.5)),4)]
            out['tests'][tn]=dict(samples=int(len(yt)),events=int(yt.sum()),vehicles=int(len(uid)),obs_rate=float(yt.mean()),models=rowres)
            print(name,tn,json.dumps(out['tests'][tn])[:400],flush=True)
        out['logit_weights_std']={n:round(float(w),3) for n,w in zip(NAMES,fitted['logit, 14 inputs, 15 params'][1].W[0][:,0])}
        res[name]=out
        json.dump(res,open(OUT,'w'),indent=1,default=float)
    print('done',round(time.time()-t0))
main()
