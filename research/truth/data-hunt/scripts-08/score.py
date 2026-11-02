"""Score edge flows (5 x n: early, am, mid, pm, night) against 2018 screenlines. usage: score.py net.npz screens.npz flows.npz..."""
import sys,json,numpy as np
TRUTH=[('toll_op_plus_ess',424390,'06:00-18:30','Transportstyrelsen, Sept 2018: 8,487,800 passages over 20 days'),
('innerstad_0630_1830',311500,'06:30-18:30','Trafikutveckling 2018, Oct: charging passages excl. Essingeleden'),
('innerstad_dygn',412100,'all day','Trafikutveckling 2018, Oct weekday'),
('saltsjo_malar',310200,'all day','Trafikutveckling 2018'),
('essingeleden_grondal',170500,'all day','Trafikutveckling 2018'),
('centralbron',99000,'all day','Trafikutveckling 2018'),
('vasterbron',22000,'all day','Trafikutveckling 2018'),
('munkbroleden',13000,'all day','Trafikutveckling 2018'),
('skeppsbron',5500,'all day','Trafikutveckling 2018'),
('sodra_lanken_aby',107200,'all day','Trafikutveckling 2018'),
('citysnittet',227500,'all day','Trafikutveckling 2018'),
('regioncentrum',974200,'all day','Trafikutveckling 2018')]
def heads(mask,N,F):
    i=np.where(mask)[0];d=N['B'][i]-N['A'][i];h=np.where(np.abs(d[:,1])>=np.abs(d[:,0]),np.sign(d[:,1]),np.sign(d[:,0]))
    return sum(F[i[h==s]].max() if (h==s).any() else 0 for s in(-1,1))
def measure(F,N,S):
    day=F.sum(0);w06=F[[0,1,2,3]].sum(0);w0630=F[[1,2,3]].sum(0)
    M={}
    M['toll_op_plus_ess']=w06[S['toll_op']].sum()+w06[S['ess_op']].sum()
    M['innerstad_0630_1830']=w0630[S['inner']].sum()
    M['innerstad_dygn']=day[S['inner']].sum()
    M['essingeleden_grondal']=day[S['ess_grondal']].sum()
    M['centralbron']=heads(S['b_centralbron'],N,day);M['vasterbron']=heads(S['b_vasterbron'],N,day);M['munkbroleden']=heads(S['b_munkbroleden'],N,day);M['skeppsbron']=heads(S['b_skeppsbron'],N,day)
    M['saltsjo_malar']=M['essingeleden_grondal']+M['centralbron']+M['vasterbron']+M['munkbroleden']+M['skeppsbron']
    M['sodra_lanken_aby']=day[S['sodra_aby']].sum();M['citysnittet']=day[S['city']].sum();M['regioncentrum']=day[S['region']].sum()
    M['vkm_stockholm_kommun_M']=float((day*N['L'])[S['in_stockholm_kommun']].sum()/1e6)
    return {k:float(v) for k,v in M.items()}
def report(M):
    names=[t[0] for t in TRUTH];r=np.array([M[n]/t for n,t in zip(names,[x[1] for x in TRUTH])])
    # k = scale that best matches all screenlines in log space; residual is the shape error
    big=np.array([t[1]>=20000 for t in TRUTH]);lr=np.log(np.maximum(r,1e-6));k=float(np.exp(lr[big].mean()));res=lr[big]-lr[big].mean()
    return dict(ratios={n:round(float(x),3) for n,x in zip(names,r)},geomean_ratio=round(k,3),shape_rmse_log=round(float(np.sqrt((res**2).mean())),3),shape_mape_pct=round(float(100*np.mean(np.abs(np.exp(res)-1))),1),vkm_stockholm_kommun_M=round(M['vkm_stockholm_kommun_M'],2))
if __name__=='__main__':
    N=np.load(sys.argv[1]);S=np.load(sys.argv[2]);out={}
    for p in sys.argv[3:]:
        F=np.load(p)['F'];M=measure(F,N,S);R=report(M);R['raw']={k:round(v) for k,v in M.items()};out[p.rsplit('/',1)[1]]=R;print(p,json.dumps(R['ratios']),'k',R['geomean_ratio'],'shape',R['shape_mape_pct'],'vkm',R['vkm_stockholm_kommun_M'],flush=True)
    json.dump(out,open(sys.argv[2]+'.scores.json','w'),indent=1)
