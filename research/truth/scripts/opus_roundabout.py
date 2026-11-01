"""Swiss roundabouts: entering gap acceptance with censored rejected gaps; critical gap by Troutbeck MLE and Raff; follow-up headway."""
import sys,glob; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.ndimage import distance_transform_edt, uniform_filter1d
from scipy.optimize import minimize
from scipy.stats import norm
REF={'F2':('D1_AM1_F2.csv',(4.0,-1.0,8.0)),'F1':('D1_AM2_F1.csv',(-9.0,5.0,8.0)),'L1':('D2_AM1_L1.csv',(-2.0,-5.0,11.0))}
ORIGIN={}
def origin(site):
    if site not in ORIGIN:
        d=pd.read_csv(SW/REF[site][0],usecols=['lat','lon']); ORIGIN[site]=(d['lat'].mean(),d['lon'].mean())
    return ORIGIN[site]
def load_file(f):
    site=str(f).split('_')[-1][:-4]
    d=pd.read_csv(f)
    t=d['time'].str.slice(0,2).astype(int)*3600+d['time'].str.slice(3,5).astype(int)*60+d['time'].str.slice(6).astype(float)
    lat0,lon0=origin(site)
    x=(d['lon']-lon0)*111320*np.cos(np.deg2rad(lat0)); y=(d['lat']-lat0)*110574
    return pd.DataFrame(dict(id=d['track_id'].values,typ=d['type'].values,t=t.values,x=x.values,y=y.values)),lat0,lon0
def tracks(d):
    out=[]
    for i,g in d.groupby('id',sort=False):
        g=g.sort_values('t')
        if len(g)<20: continue
        out.append((i,g['typ'].iloc[0],g['t'].values,g['x'].values,g['y'].values))
    return out
def geometry(ts,guess):
    """Refines the hand-read ring (fig rb_map) per file by repeated algebraic circle fits to the annulus of positions."""
    X=np.concatenate([a[3][::3] for a in ts]);Y=np.concatenate([a[4][::3] for a in ts])
    cx,cy,R=guess
    for w in (5,4,3,2.5,2.5):
        m=abs(np.hypot(X-cx,Y-cy)-R)<w
        A=np.c_[2*X[m],2*Y[m],np.ones(m.sum())]; bb=X[m]**2+Y[m]**2
        sol=np.linalg.lstsq(A,bb,rcond=None)[0]; cx,cy=sol[0],sol[1]; R=float(np.sqrt(sol[2]+cx*cx+cy*cy))
    return cx,cy,R
def analyse(f,site):
    d,lat0,lon0=load_file(f); ts=tracks(d)
    cx,cy,ri=geometry(ts,REF[site][1])
    # ring: radial histogram of low-speed-independent occupancy
    R=[];TH=[];rec=[]
    tr=[]
    for i,typ,t,x,y in ts:
        k=max(1,int(round(.2/np.median(np.diff(t)))))
        t2=t[::k];x2=uniform_filter1d(x,k*3)[::k];y2=uniform_filter1d(y,k*3)[::k]
        r=np.hypot(x2-cx,y2-cy);th=np.unwrap(np.arctan2(y2-cy,x2-cx))
        v=np.hypot(np.gradient(x2,t2),np.gradient(y2,t2))
        tr.append(dict(id=i,typ=typ,t=t2,r=r,th=th,v=v,x=x2,y=y2))
    pk=ri
    Ry=pk+3.0   # outer edge of the circulating lane, line for entering vehicles
    Rin=Ry
    passes={} ; entries=[]
    for a in tr:
        r,th,t=a['r'],a['th'],a['t']
        inside=r<Ry
        if not inside.any(): continue
        kin=np.argmax(inside)
        a['kin']=kin
        entered=kin>0 and r[0]>Ry+8
        if entered:
            ang=th[kin]; a['ang']=ang%(2*np.pi)
            entries.append(a)
    # circulation direction
    dirs=[np.sign(a['th'][min(a['kin']+15,len(a['th'])-1)]-a['th'][a['kin']]) for a in entries if a['kin']+15<len(a['th'])]
    sgn=np.sign(np.sum(dirs))
    # arms by entry angle clusters
    angs=np.array([a['ang'] for a in entries]);h,e=np.histogram(angs,bins=72,range=(0,2*np.pi))
    from scipy.signal import find_peaks
    hh=np.r_[h,h]; pk_,_=find_peaks(uniform_filter1d(hh.astype(float),3),distance=8,height=max(10,.1*h.max()))
    arm_ang=sorted(set(np.round(((pk_%72)+.5)*2*np.pi/72,3)))
    def arm_of(a):
        dd=[abs((a-b+np.pi)%(2*np.pi)-np.pi) for b in arm_ang]; j=int(np.argmin(dd)); return j if dd[j]<.5 else -1
    # for each arm: passage times of ring vehicles past the entry angle, inside the ring
    pas={j:[] for j in range(len(arm_ang))}
    for a in tr:
        r,th,t=a['r'],a['th'],a['t']
        ring=r<Ry
        if ring.sum()<3: continue
        for j,b in enumerate(arm_ang):
            ks=th%(2*np.pi)
            for m in np.where(ring[:-1]&ring[1:])[0]:
                d0=(th[m]-b+np.pi)%(2*np.pi)-np.pi; d1=(th[m+1]-b+np.pi)%(2*np.pi)-np.pi
                if d0*sgn<0<=d1*sgn and abs(d0-d1)<1:
                    pas[j].append((t[m+1],a['id']))
    res=[];followups=[]
    for j in pas: pas[j]=sorted(pas[j])
    for a in entries:
        j=arm_of(a['ang'])
        if j<0 or a['typ']!='Car': continue
        kin=a['kin'];t=a['t'];r=a['r'];v=a['v']
        tc=t[kin]
        # arrival at the yield line: first time inside Ry+6 m
        ka=np.argmax(r<Ry+6)
        ta=t[ka]
        # subject must be first in line: no other entering vehicle crossed the line between ta and tc on this arm
        others=[b for b in entries if b is not a and arm_of(b['ang'])==j and ta<b['t'][b['kin']]<tc]
        first=len(others)==0
        pp=np.array([p[0] for p in pas[j] if p[1]!=a['id']])
        if len(pp)==0: continue
        next_after=pp[pp>tc]
        prev=pp[pp<=tc]
        if len(next_after)==0: continue
        nx=next_after[0]; pv=prev[-1] if len(prev) else -1e9
        # rejected: gaps entirely after arrival, ending before tc; lag from arrival to the first passage
        if first:
            btw=pp[(pp>ta)&(pp<=tc)]
            rej=[]
            if len(btw):
                rej.append(btw[0]-ta)  # lag
                rej+=list(np.diff(btw))
            acc=nx-max(pv,ta)
            lag_acc=pv<ta
            minv=v[max(ka-2,0):kin+1].min()
            res.append(dict(site=site,file=f.split('/')[-1],arm=j,id=int(a['id']),ta=float(ta),tc=float(tc),acc=float(acc),acc_is_lag=bool(lag_acc),rmax=float(max(rej)) if rej else 0.0,nrej=len(rej),wait=float(tc-ta),minv=float(minv)))
        # follow-up: this vehicle crossed the line right after another on the same arm while no ring vehicle in between, and was queued behind
        prevent=[b for b in entries if b is not a and arm_of(b['ang'])==j and b['t'][b['kin']]<tc and tc-b['t'][b['kin']]<8]
        if prevent:
            b=max(prevent,key=lambda z:z['t'][z['kin']]); tb=b['t'][b['kin']]
            if not ((pp>tb)&(pp<tc)).any() and v[max(kin-15,0):kin].min()<2.5:
                followups.append(tc-tb)
    return dict(site=site,centre=(cx,cy),island_r=ri,ring_peak=pk,Ry=Ry,arms=len(arm_ang),n_tracks=len(tr),entries=len(entries),sgn=int(sgn)),res,followups
def mle(acc,rmax):
    acc=np.maximum(np.asarray(acc),.05); r=np.asarray(rmax)
    def nll(p):
        mu,ls=p; s=np.exp(ls)
        Fa=norm.cdf((np.log(acc)-mu)/s)
        Fr=np.where(r>0,norm.cdf((np.log(np.maximum(r,1e-3))-mu)/s),0.0)
        return -np.sum(np.log(np.maximum(Fa-Fr,1e-9)))
    best=minimize(nll,[1.5,-1],method='Nelder-Mead',options=dict(maxiter=800))
    mu,ls=best.x; s=np.exp(ls)
    return dict(mu=mu,sigma=s,median=float(np.exp(mu)),mean=float(np.exp(mu+s*s/2)),sd_ln=s)
def raff(acc,rej):
    grid=np.arange(.5,15,.05)
    A=np.array([(np.asarray(acc)<g).sum() for g in grid]);R=np.array([(np.asarray(rej)>g).sum() for g in grid])
    k=np.argmin(abs(A-R)); return float(grid[k])
if __name__=='__main__':
    fs=sorted(glob.glob(str(SW/'*.csv')));Geo=[];Rs=[];Fu={}
    for f in fs:
        site=f.split('_')[-1][:-4]
        g,r,fu=analyse(f,site); Geo.append(g);Rs+=r;Fu.setdefault(site,[]).extend(fu); print(f.split('/')[-1],{k:(round(v,1) if isinstance(v,float) else v) for k,v in g.items() if k!='centre'},len(r),len(fu),flush=True)
    D=pd.DataFrame(Rs); D.to_csv(CACHE/'roundabout_decisions.csv',index=False)
    out={'source':'https://zenodo.org/records/15077435','geometry':Geo,'n_decisions':len(D),'sites':{}}
    for s,g in list(D.groupby('site'))+[('ALL',D)]:
        decided=g[(g['nrej']>0)|(g['acc']<25)]
        est=mle(decided['acc'],decided['rmax'])
        rng=np.random.default_rng(1);boot=[]
        fi=decided['file'].values
        fn=np.unique(fi)
        for _ in range(60):
            pick=rng.choice(len(decided),len(decided));boot.append(mle(decided['acc'].values[pick],decided['rmax'].values[pick])['median'])
        rejs=decided[decided['nrej']>0]
        out['sites'][s]=dict(n=len(g),n_with_rejected=int((g['nrej']>0).sum()),accepted=q(g['acc'],(5,10,25,50,75)),accepted_lag_only_frac=float(g['acc_is_lag'].mean()),wait=q(g['wait'],(50,90)),largest_rejected=q(rejs['rmax'],(25,50,75,90,95)),mle=est,mle_median_ci=np.percentile(boot,[2.5,97.5]).tolist(),raff=raff(decided['acc'],rejs['rmax']),followup=q(Fu.get(s,sum(Fu.values(),[])),(25,50,75)))
        print(s,json.dumps(out['sites'][s])[:500],flush=True)
    save('roundabout',out)
