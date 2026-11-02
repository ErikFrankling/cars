"""Cuts validated pair segments into fixed rollout windows with train/val/test labels."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import Batch
def windows(site,T=30.0,stride=15.0,car_types=None,maxspacing=100.0,maxn=None):
    d=dict(np.load(CACHE/f'pairs_{site}.npz')); seg=d['seg']; u=np.r_[0,np.where(np.diff(seg)!=0)[0]+1,len(seg)]
    W=int(T*10); St=int(stride*10); out=[]
    cts=car_types or {'I395':[1],'I90stat':[1],'I90mov':[1],'I294L1':[1],'I294L2':[1],'HT':[1]}[site]
    for a,b in zip(u[:-1],u[1:]):
        if d['autof'][a] or d['autol'][a] or d['tf'][a] not in cts or d['tl'][a] not in cts: continue
        for i in range(a,b-W,St):
            s=d['cc'][i:i+W]; v=d['vf'][i:i+W]; vl=d['vl'][i:i+W]
            if s.min()<3 or s.max()>maxspacing or np.mean(s)/max(np.mean(v),.5)>8: continue
            out.append((int(d['run'][a]),int(d['t'][i]),int(d['fid'][a]),int(d['lid'][a]),float(d['af'][i]),i,site))
    if not out: return None
    if maxn and len(out)>maxn:
        pick=np.random.default_rng(7).choice(len(out),maxn,replace=False); out=[out[i] for i in sorted(pick)]
    idx=np.array([o[5] for o in out])
    S=np.stack([d['cc'][i:i+W] for i in idx],1).astype('f8'); V=np.stack([d['vf'][i:i+W] for i in idx],1).astype('f8'); VL=np.stack([d['vl'][i:i+W] for i in idx],1).astype('f8')
    vref=float(np.percentile(d['vf'][::7],99))
    meta=dict(vref=np.full(len(out),vref),run=np.array([o[0] for o in out]),t=np.array([o[1] for o in out])/10,fid=np.array([o[2] for o in out]),lid=np.array([o[3] for o in out]),site=np.array([site]*len(out)))
    return Batch(S,V,VL,np.array([o[4] for o in out]),meta)
def concat(bs):
    bs=[b for b in bs if b is not None]
    return Batch(np.hstack([b.s for b in bs]),np.hstack([b.v for b in bs]),np.hstack([b.vl for b in bs]),np.hstack([b.a0 for b in bs]),{k:np.concatenate([b.meta[k] for b in bs]) for k in bs[0].meta})
def dynamic_mask(b):
    return (b.vl.max(0)-b.vl.min(0))>=3.0
