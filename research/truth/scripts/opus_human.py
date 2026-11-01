"""Builds the stochastic and heterogeneous human variants from the validation-selected base, on training data only: residual acceleration noise; writes human_params.json."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_windows import *
from opus_fit import split,vr
base=sys.argv[1]; res=json.loads((OUT/'fit_params_all.json').read_text())
P=dict(res[base]['params'])
if 'sqrt' in base: P['m']=.5
train,val,test=split(False)
r=np.random.default_rng(2);b=train.subset(r.choice(train.N,3000,replace=False))
p=vr(P,b)
if 's0fix' in base: p['s0']=2.8
# one-step residual: smoothed observed acceleration minus model target at the observed state
vs=b.v; a_obs=np.gradient(pd.DataFrame(vs).rolling(5,center=True,min_periods=1).mean().values,.1,axis=0)
res_all=[];ac=[]
pp={k:(v if np.ndim(v)==0 else np.asarray(v).reshape(-1)) for k,v in p.items()}
at=np.empty_like(vs)
for t in range(b.T):
    at[t]=helly_accel(vs[t],b.s[t],b.vl[t],{k:(np.asarray(v)) for k,v in pp.items()})
er=a_obs-at
sd=float(er[10:-10].std())
lag=[1,2,5,10,20,30,50,100]
cor={k*.1:float(np.mean(er[10:-10-k]*er[10+k:-10])/er[10:-10].var()) for k in lag}
# fit an exponential to the correlation beyond the filter's own reach
ts=np.array([k for k in cor if k>=1.0]);cs=np.array([cor[k] for k in ts])
tc=float(-1/np.polyfit(ts,np.log(np.maximum(cs,1e-3)),1)[0])
# intensity reported as stationary SD and implied q=2 sd^2/tc
by={}
for lo,hi in [(0,2),(2,5),(5,10),(10,15),(15,25),(25,40)]:
    m=(vs>=lo)&(vs<hi)
    if m.sum()>200: by[f'{lo}-{hi}']=float(er[m].std())
out=dict(base=base,residual_sd=sd,autocorr=cor,tc_fit=tc,q_from_sd=2*sd*sd/tc,by_speed=by)
save('noise_residual',out);print(out)
human={}
kp={k:v for k,v in P.items()}
if 's0fix' in base: kp['s0']=2.8
if 's0fix' in base or 'sqrt' in base:
    if 'sqrt' in base: kp['m']=0.5
het=None
pf=OUT/'personal.json'
if pf.exists():
    pj=json.loads(pf.read_text());R=[pj[s]['helly']['params'] for s in pj if 'helly' in pj[s]]
    het={k:float(np.mean([r[k]['log_sd_persistent'] for r in R])) for k in ('k1','k2','T','s0') if k in R[0]}
    if 's0fix' in base: het.pop('s0',None)
for nm,q_,tcv,ts,h_ in (('human_det',None,None,None,False),('human_q1',.1,10.0,None,False),('human_q2',.2,10.0,None,False),('human_q4',.4,10.0,None,False),('human_start05',None,None,.5,False),('human_start10',None,None,1.0,False),('human_het',None,None,None,True),('human_full_q1',.1,10.0,.5,True),('human_full_q2',.2,10.0,.5,True),('human_full_q2_s10',.2,10.0,1.0,True)):
    e=dict(kind='helly',params=dict(kp))
    if q_ is not None: e['params'].update(q=q_,tc=tcv)
    if ts is not None: e['params'].update(t_start=ts)
    if h_ and het: e['het']=het
    human[nm]=e
(OUT/'human_params.json').write_text(json.dumps(human,indent=1))
