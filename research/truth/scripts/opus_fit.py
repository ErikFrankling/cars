"""Fits every candidate on the training windows only, freezes parameters, scores train/val/test splits."""
import sys,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_windows import *
def split(us_only=False,train_only=False):
    cached=CACHE/('split_us.pkl' if us_only else 'split_all.pkl')
    if cached.exists():
        import pickle
        d=pickle.load(open(cached,'rb'))
        un=lambda x:Batch(x['s'].astype('f8'),x['v'].astype('f8'),x['vl'].astype('f8'),x['a0'].astype('f8'),x['meta'])
        if train_only: return un(d['train']),None,{}
        if 'HT_all_external' in d['test']:
            x=d['test']['HT_all_external'];k=np.arange(0,x['s'].shape[1],2)
            d['test']['HT_all_external']=dict(s=x['s'][:,k],v=x['v'][:,k],vl=x['vl'][:,k],a0=x['a0'][k],meta={a:b[k] for a,b in x['meta'].items()})
        return un(d['train']),un(d['val']),{k:un(v) for k,v in d['test'].items()}
    tr=[];va=[];te={}
    i395=windows('I395'); m=i395.meta['t']
    tr.append(i395.subset(np.where(m<3000)[0])); va.append(i395.subset(np.where((m>=3000)&(m<3900))[0])); te['I395_late']=i395.subset(np.where(m>=3900)[0])
    st=windows('I90stat'); r=st.meta['run']
    tr.append(st.subset(np.where(np.isin(r,[1,2,3,4]))[0])); va.append(st.subset(np.where(r==5)[0])); te['I90stat_run6']=st.subset(np.where(r==6)[0])
    te['I90mov']=windows('I90mov')
    i2=windows('I294L1'); r=i2.meta['run']
    tr.append(i2.subset(np.where(np.isin(r,[1,3,7,8]))[0])); va.append(i2.subset(np.where(r==9)[0])); te['I294L1_runs']=i2.subset(np.where(np.isin(r,[11,18,19,20,21]))[0])
    ht=windows('HT',maxn=12000,stride=30.0); r=ht.meta['run']
    if not us_only:
        tr.append(ht.subset(np.where(r<12)[0])); va.append(ht.subset(np.where((r>=12)&(r<16))[0])); te['HT_late']=ht.subset(np.where(r>=16)[0])
    else:
        te['HT_all_external']=ht
    return concat(tr),concat(va),te
BOUND=dict(gamma=(.8,1.6),k1=(.01,1.0),k2=(.02,2.0),k2c=(.02,2.0),k1o=(.005,1.0),m=(0,1.5),amax=(.3,5),bmax=(1,9),a=(.2,4),b=(.3,6),T=(.2,3),s0=(.2,6),v0=(12,45),tau_a=(.03,3),tau_p=(.03,3),T_acc=(.2,4),Tr=(0,2.0))
KB=dict(gamma=(.8,1.6),accel=(.3,6),decel=(.3,6),tau=(.2,3),minGap=(.2,6),v0=(12,45),sigma=(0,1))
SUM_KR=dict(accel=2.6,decel=4.5,tau=1.0,minGap=2.5,v0=33.3,sigma=.5)
def vr(p,b):
    g=np.asarray(p['gamma'],float).reshape(-1,1)
    return {**{k:v for k,v in p.items() if k!='gamma'},'v0':g*b.meta['vref'][None,:]}
def mk(name):
    KN=['accel','decel','tau','minGap','gamma','sigma']
    IN=['a','b','T','s0','gamma']
    H=['k1','k2','T','s0','amax','bmax','gamma']
    BW={**BOUND,'a':(.2,6),'b':(.02,6),'T':(.2,4),'gamma':(.8,3)};KW={**KB,'accel':(.3,8),'decel':(.05,6),'tau':(.2,4),'gamma':(.8,3)}
    table=dict(idm_wide=(lambda b,p:idm_family(b,vr(p,b)),BW,IN),krauss_dt1_wide=(lambda b,p:krauss(b,vr(p,b),1.0),KW,KN),krauss_dt01_wide=(lambda b,p:krauss(b,vr(p,b),0.1),KW,KN),krauss_dt1=(lambda b,p:krauss(b,vr(p,b),1.0),KB,KN),krauss_dt1_s0=(lambda b,p:krauss(b,{**vr(p,b),'sigma':0.0},1.0),KB,KN[:-1]),krauss_dt01=(lambda b,p:krauss(b,vr(p,b),0.1),KB,KN),
        idm=(lambda b,p:idm_family(b,vr(p,b)),BOUND,IN),idmplus=(lambda b,p:idm_family(b,vr(p,b),plus=True),BOUND,IN),hdm=(lambda b,p:hdm(b,vr(p,b)),BOUND,IN+['Tr']),
        gipps=(lambda b,p:gipps(b,{**vr(p,b),'tau':p['T']},0.5),BOUND,IN),idm_lag=(lambda b,p:idm_family(b,vr(p,b)),BOUND,IN+['tau_a']),idmplus_lag=(lambda b,p:idm_family(b,vr(p,b),plus=True),BOUND,IN+['tau_a']),
        helly=(lambda b,p:helly(b,vr(p,b)),BOUND,H),helly_lag=(lambda b,p:helly(b,vr(p,b)),BOUND,H+['tau_a']),helly_asym=(lambda b,p:helly(b,vr(p,b)),BOUND,H+['k2c']),helly_ghr=(lambda b,p:helly(b,vr(p,b)),BOUND,H+['m']),helly_ghr_lag=(lambda b,p:helly(b,vr(p,b)),BOUND,H+['m','tau_a']),helly_ghr_asym=(lambda b,p:helly(b,vr(p,b)),BOUND,H+['m','k2c']),
        helly_sqrt=(lambda b,p:helly(b,{**vr(p,b),'m':0.5}),BOUND,H),helly_sqrt_s0fix=(lambda b,p:helly(b,{**vr(p,b),'m':0.5,'s0':2.8}),BOUND,['k1','k2','T','amax','bmax','gamma']),helly_ghr_s0fix=(lambda b,p:helly(b,{**vr(p,b),'s0':2.8}),BOUND,['k1','k2','T','amax','bmax','gamma','m']),helly_ghr_s0fix_lag=(lambda b,p:helly(b,{**vr(p,b),'s0':2.8}),BOUND,['k1','k2','T','amax','bmax','gamma','m','tau_a']))
    return table[name]
MODELS=['krauss_dt1','krauss_dt01','gipps','idm','idmplus','hdm','idm_lag','idmplus_lag','helly','helly_lag','helly_asym','helly_ghr','helly_ghr_lag','helly_ghr_asym','helly_ghr_s0fix','helly_ghr_s0fix_lag']
def main(which,us_only,tag):
    t0=time.time(); train,val,test=split(us_only,True); print('windows train',train.N,time.time()-t0,flush=True)
    sub=train.subset(np.arange(min(3000,train.N)))
    res={}
    path=OUT/f'fit_params_{tag}.json'
    if path.exists(): res=json.loads(path.read_text())
    for name in which:
        f,bd,names=mk(name); t1=time.time()
        def fun(pd_):
            S,V=f(sub,pd_); return objective(sub,S,V)
        x,J,med=de_fit(fun,bd,names,pop=20,gens=35,seed=1)
        print(name,x,'J',round(J,3),round(time.time()-t1,1),flush=True)
        res[name]=dict(params=x,J=J)
        path.write_text(json.dumps(res,indent=1))
if __name__=='__main__':
    tag=sys.argv[1]; main(sys.argv[2:] or MODELS,tag=='us',tag)
