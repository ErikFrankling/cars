"""DLR HT (A39, Germany): road frame, lane labels, leader-follower pairs at 5 Hz upsampled to 10 Hz, lane changes, headways, free speeds."""
import sys,zipfile,time; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d, median_filter
from scipy.optimize import least_squares
HOURS=int(sys.argv[1]) if len(sys.argv)>1 else 4
GAPS=len(sys.argv)>2 and sys.argv[2]=='gaps'
gaprec=[]
z=zipfile.ZipFile(HT/'DLR-Highway-Traffic-dataset_v1-2-0.zip')
fs=sorted(n for n in z.namelist() if '/trajectories/' in n and n.endswith('.csv'))
print(len(fs),fs[0],z.getinfo(fs[0]).file_size,flush=True)
cols=['timestamp','id','center_easting','center_northing','velocity_magnitude','dimension_length','dimension_width','classifications_car','classifications_van','classifications_truck','classifications_motorbike','interpolated']
def secs(s):
    s=s.str.slice(11,-6); return s.str.slice(0,2).astype(int)*3600+s.str.slice(3,5).astype(int)*60+s.str.slice(6).astype(float)
def read(n):
    with z.open(n) as f: d=pd.read_csv(f,usecols=cols)
    d['t']=secs(d['timestamp']); d=d[(np.round(d['t']*20).astype(int)%4)==0]
    veh=d['classifications_car']+d['classifications_van']+d['classifications_truck']; d=d[veh>.5]
    return pd.DataFrame(dict(id=d['id'].values,ti=np.round(d['t'].values*5).astype('i4'),x=(d['center_easting'].values-600000).astype('f4'),y=(d['center_northing'].values-5790000).astype('f4'),v=d['velocity_magnitude'].values.astype('f4'),L=d['dimension_length'].values.astype('f4'),W=d['dimension_width'].values.astype('f4'),tr=(d['classifications_truck'].values>.5).astype('i1')))
LW=3.75
refs=None; allpairs=[];lcs=[];free=[];heads=[];stats={'files':0,'rows':0,'ids':0}
def mkrefs(d):
    g=d.groupby('id'); ends=g.agg(x0=('x','first'),y0=('y','first'),x1=('x','last'),y1=('y','last'),n=('x','size'))
    ends['len']=np.hypot(ends.x1-ends.x0,ends.y1-ends.y0)
    pts=d[['x','y']].values[::50]; c=pts.mean(0); u,s,vt=np.linalg.svd(pts-c,full_matrices=False); ax=vt[0]
    ends['dir']=np.sign((ends.x1-ends.x0)*ax[0]+(ends.y1-ends.y0)*ax[1])
    R={}
    for sg in (-1,1):
        best=ends[ends['dir']==sg].sort_values('len').index[-1]
        t=d[d['id']==best].sort_values('ti'); xy=t[['x','y']].values.astype('f8')
        seg=np.r_[0,np.cumsum(np.hypot(*np.diff(xy,axis=0).T))]; ss=np.arange(0,seg[-1],2.0)
        rx=gaussian_filter1d(np.interp(ss,seg,xy[:,0]),100,mode='nearest');ry=gaussian_filter1d(np.interp(ss,seg,xy[:,1]),100,mode='nearest')
        tx=np.gradient(rx);ty=np.gradient(ry);n=np.hypot(tx,ty);R[sg]=dict(x=rx,y=ry,tx=tx/n,ty=ty/n,tree=cKDTree(np.c_[rx,ry]),len=seg[-1],id=int(best))
        print('ref',sg,round(seg[-1]),flush=True)
    return R
def frame(d):
    """adds dir,s,dd"""
    o=np.lexsort((d['ti'].values,d['id'].values)); d=d.iloc[o].reset_index(drop=True)
    ub=np.r_[0,np.where(np.diff(d['id'].values)!=0)[0]+1,len(d)]
    S=np.full(len(d),np.nan,'f4');DD=np.full(len(d),np.nan,'f4');DIR=np.zeros(len(d),'i1')
    X,Y=d['x'].values,d['y'].values
    for a,b in zip(ub[:-1],ub[1:]):
        if b-a<25: continue
        best=None
        for sg,r in refs.items():
            dist,idx=r['tree'].query(np.c_[X[a:b],Y[a:b]],k=1)
            dx=X[b-1]-X[a];dy=Y[b-1]-Y[a]; k=len(idx)//2
            aligned=dx*r['tx'][idx[k]]+dy*r['ty'][idx[k]]
            if aligned>0 and np.median(dist)<15:
                best=(sg,idx,r)
        if best is None: continue
        sg,idx,r=best
        rel_x=X[a:b]-r['x'][idx];rel_y=Y[a:b]-r['y'][idx]
        S[a:b]=idx*2.0+rel_x*r['tx'][idx]+rel_y*r['ty'][idx]
        DD[a:b]=rel_x*-r['ty'][idx]+rel_y*r['tx'][idx]; DIR[a:b]=sg
    d['s']=S;d['dd']=DD;d['dir']=DIR
    return d[d['dir']!=0].reset_index(drop=True)
def centres(d):
    """lane origin c(s) per direction, modulo lane width, continuous along s."""
    C={}
    for sg in (-1,1):
        m=(d['dir'].values==sg)&(np.abs(d['dd'].values)<12)
        s=d['s'].values[m];dd=d['dd'].values[m]
        bins=(s/100).astype(int);nb=bins.max()+1;c=np.full(nb,np.nan)
        for b in range(nb):
            z_=dd[bins==b]
            if len(z_)<300: continue
            h,e=np.histogram(z_,bins=np.arange(-12,12.01,.25)); hs=gaussian_filter1d(h.astype(float),2)
            c[b]=e[np.argmax(hs)]+.125
        v=np.where(np.isfinite(c))[0]
        cc=np.interp(np.arange(nb),v,c[v])
        # unwrap modulo lane width
        for i in range(1,nb):
            while cc[i]-cc[i-1]>LW/2: cc[i]-=LW
            while cc[i]-cc[i-1]<-LW/2: cc[i]+=LW
        C[sg]=gaussian_filter1d(median_filter(cc,9),1)
    return C
def lane_label(d,C):
    L=np.zeros(len(d),'i1');off=np.zeros(len(d),'f4')
    for sg in (-1,1):
        m=d['dir'].values==sg
        cs=np.interp(d['s'].values[m]/100,np.arange(len(C[sg])),C[sg])
        rel=d['dd'].values[m]-cs
        L[m]=np.round(rel/LW).astype('i1');off[m]=rel
    d['lane']=L;d['rel']=off
    return d
def fit_tanh(t,y):
    def f(p): return p[0]+p[1]*.5*(1+np.tanh((t-p[2])/np.maximum(p[3],.05)))-y
    r=least_squares(f,[np.median(y[:10]),np.median(y[-10:])-np.median(y[:10]),0,1],bounds=([-40,-40,-6,.05],[40,40,6,8]))
    return r.x,float(np.sqrt(np.mean(f(r.x)**2)))
def changes(d,hour):
    fo=np.argsort(d['ti'].values,kind='stable');FT=d['ti'].values[fo];FS=d['s'].values[fo];FL=d['lane'].values[fo];FD=d['dir'].values[fo];FV=d['v'].values[fo];FI=d['id'].values[fo];FTR=d['tr'].values[fo]
    o=np.lexsort((d['ti'].values,d['id'].values));d=d.iloc[o]
    ID,TI,LA,REL,V,TR,W_,SS,DI=d['id'].values,d['ti'].values,d['lane'].values,d['rel'].values,d['v'].values,d['tr'].values,d['W'].values,d['s'].values,d['dir'].values
    ub=np.r_[0,np.where(np.diff(ID)!=0)[0]+1,len(ID)];HW=40
    for a,b in zip(ub[:-1],ub[1:]):
        if b-a<2*HW+1: continue
        l=LA[a:b]; ch=np.where(l[1:]!=l[:-1])[0]+1
        ch=ch[(ch>=HW)&(ch<b-a-HW)]
        for k in ch:
            w=slice(a+k-HW,a+k+HW+1)
            lw=LA[w]
            if (np.diff(lw)!=0).sum()!=1 or abs(lw[0]-lw[-1])!=1: continue
            if (TI[w][-1]-TI[w][0])!=2*HW: continue
            y=REL[w].astype('f8');t=(TI[w]-TI[a+k])/5.0
            pre=np.median(y[t<-5]);post=np.median(y[t>5]);W=post-pre
            if not 2.5<abs(W)<5.0: continue
            qq=(y-pre)/W
            i10=np.where(qq>=.1)[0];i90=np.where(qq>=.9)[0]
            if not len(i10) or not len(i90) or i90[0]<=i10[0]: continue
            d1090=t[i90[0]]-t[i10[0]]
            i25=np.where(qq>=.25)[0][0];i75=np.where(qq>=.75)[0][0]
            mono=float(np.min(np.diff(qq[i10[0]:i90[0]+1])))
            p,rms=fit_tanh(t,y)
            vl=np.gradient(y,t);vs=np.convolve(vl,np.ones(5)/5,'same')
            if GAPS and TR[a]==0 and rms<.3 and mono>-.15 and d1090<12:
                for off in (0,-10):
                    tk=TI[a+k+off]; lo=np.searchsorted(FT,tk,'left');hi=np.searchsorted(FT,tk,'right')
                    m=(FL[lo:hi]==lw[-1])&(FD[lo:hi]==DI[a])&(FI[lo:hi]!=ID[a]);ss=FS[lo:hi][m];vv=FV[lo:hi][m];sx=SS[a+k+off];vx=V[a+k+off]
                    ah=ss>sx;be=ss<=sx
                    lead=(ss[ah]-sx).min() if ah.any() else np.nan;vlead=vv[ah][np.argmin(ss[ah])] if ah.any() else np.nan
                    lag=(sx-ss[be]).min() if be.any() else np.nan;vlag=vv[be][np.argmax(ss[be])] if be.any() else np.nan
                    gaprec.append((off/5,vx,lead,vlead,lag,vlag,int(ID[a])%1000000))
            lcs.append(dict(hour=hour,id=int(ID[a]),speed=float(V[a+k]),truck=int(TR[a]),d1090=float(d1090),d2575=float(t[i75]-t[i25]),width=abs(float(W)),tanh1090=float(p[3]*2.1972),rms=rms,mono=mono,peak=float(np.abs(vs[i10[0]:i90[0]+1]).max()),lane_from=int(lw[0]),lane_to=int(lw[-1]),s=float(SS[a+k]),dir=int(DI[a])))
def pairs(d,hour):
    ov=np.lexsort((d['s'].values,d['lane'].values,d['dir'].values,d['ti'].values)); e=d.iloc[ov]
    ti,di,la,ss,ids,vv,L,tr=[e[c].values for c in ('ti','dir','lane','s','id','v','L','tr')]
    sm=(ti[1:]==ti[:-1])&(di[1:]==di[:-1])&(la[1:]==la[:-1])
    f=np.where(sm)[0];l=f+1
    cc=ss[l]-ss[f]; ok=(cc>2)&(cc<150)
    # free vehicles: front vehicle in the lane or leader beyond 150 m
    last=np.r_[~sm,True]; freeidx=np.where(last|np.r_[(cc>150) if False else np.zeros(0,bool),np.zeros(len(ti)-0,bool)][:len(ti)])[0]
    far=f[(ss[l]-ss[f])>200]
    free.append(np.c_[vv[far],la[far],di[far],tr[far]])
    P=pd.DataFrame(dict(run=hour,t=ti[f][ok],fid=ids[f][ok],lid=ids[l][ok],lane=(la[f]*10+di[f])[ok],cc=cc[ok],vf=vv[f][ok],vl=vv[l][ok],Lf=L[f][ok],Ll=L[l][ok],tf=tr[f][ok]+1,tl=tr[l][ok]+1))
    P=P.sort_values(['fid','lid','t']).reset_index(drop=True)
    brk=(P['fid'].diff()!=0)|(P['lid'].diff()!=0)|(P['t'].diff()!=1)|(P['lane'].diff()!=0)
    P['seg']=brk.cumsum(); n=P.groupby('seg')['t'].transform('size'); P=P[n>=75]
    heads.append(P[(P['tf']==1)&(P['tl']==1)][['vf','cc']].values[::5].astype('f4'))
    out=[]
    for sg,g in P.groupby('seg'):
        t=g['t'].values; tn=np.arange(t[0]*2,t[-1]*2+1)
        ci=np.interp(tn,t*2,g['cc'].values);vf=np.interp(tn,t*2,g['vf'].values);vl=np.interp(tn,t*2,g['vl'].values)
        af=np.gradient(vf,.1)
        out.append(pd.DataFrame(dict(run=hour,t=tn,fid=g['fid'].iloc[0],lid=g['lid'].iloc[0],lane=g['lane'].iloc[0],cc=ci.astype('f4'),vf=vf.astype('f4'),vl=vl.astype('f4'),af=af.astype('f4'),al=0.0,Lf=g['Lf'].median(),Ll=g['Ll'].median(),tf=g['tf'].iloc[0],tl=g['tl'].iloc[0],autof=0,autol=0,seg=sg+hour*10000000)))
    if out: allpairs.append(pd.concat(out,ignore_index=True))
for hour in range(HOURS):
    t0=time.time(); parts=[]
    for n in fs[hour*4:hour*4+4]:
        p=read(n); stats['rows']+=len(p); parts.append(p); print(n[-45:],len(p),flush=True)
    d=pd.concat(parts,ignore_index=True); del parts
    if refs is None: refs=mkrefs(d)
    d=frame(d); C=centres(d); d=lane_label(d,C)
    print('hour',hour,len(d),'lanes',np.unique(d['lane'],return_counts=True),'t',round(time.time()-t0),flush=True)
    stats['ids']+=int(d['id'].nunique())
    changes(d,hour)
    if not GAPS: pairs(d,hour)
    del d
    print(' pairs',sum(len(a) for a in allpairs),'lc',len(lcs),'t',round(time.time()-t0),flush=True)
if GAPS:
    G=pd.DataFrame(gaprec,columns='dt v lead vlead lag vlag id'.split());L=5.0
    def sg(vf,vl,tau=1.0,b=4.5,bl=4.5,mg=2.5): return np.maximum(0,vf*tau+vf*vf/(2*b)-vl*vl/(2*bl))+mg
    z=G[G['dt']==0];o2=G[G['dt']==-2]
    m=z.dropna(subset=['lead','lag'])
    lagok=(m['lag']-L)>=sg(m['vlag'],m['v']);leadok=(m['lead']-L)>=sg(m['v'],m['vlead'])
    res=dict(source='https://zenodo.org/records/18540070',n=len(z),both_known=len(m),lag_spacing=q(z['lag'],(1,5,10,25,50,75,90)),lead_spacing=q(z['lead'],(1,5,10,25,50,75,90)),lag_time_gap=q((z['lag']-L)/z['vlag'].clip(lower=.5),(1,5,10,25,50,75)),lead_time_gap=q((z['lead']-L)/z['v'].clip(lower=.5),(1,5,10,25,50,75)),lag_closing=q(z['vlag']-z['v'],(5,25,50,75,95)),lead_closing=q(z['v']-z['vlead'],(5,25,50,75,95)),secure=dict(lag_ok=float(lagok.mean()),lead_ok=float(leadok.mean()),both_ok=float((lagok&leadok).mean())),before_2s=dict(lag_time_gap=q((o2['lag']-L)/o2['vlag'].clip(lower=.5),(5,10,25,50)),lead_time_gap=q((o2['lead']-L)/o2['v'].clip(lower=.5),(5,10,25,50))))
    save('ht_gaps',res);print(json.dumps(res)[:1500]);sys.exit(0)
P=pd.concat(allpairs,ignore_index=True)
P['seg']=P['seg'].rank(method='dense').astype(int)-1
np.savez_compressed(CACHE/'pairs_HT.npz',**{k:P[k].values for k in P.columns})
LC=pd.DataFrame(lcs);LC.to_csv(CACHE/'ht_lc.csv',index=False)
G=LC[(LC['rms']<.3)&(LC['mono']>-.15)&(LC['d1090']<12)&(LC['truck']==0)]
tab=lambda g:dict(n=len(g),d1090=q(g['d1090'],(5,10,25,50,75,90,95)),d2575=q(g['d2575'],(5,25,50,75,95)),tanh=q(g['tanh1090'],(5,25,50,75,95)),peak=q(g['peak'],(5,25,50,75,95)),width=q(g['width'],(5,50,95)),speed=q(g['speed'],(5,50,95)))
F=np.vstack(free);H=np.vstack(heads)
fr={}
for la in np.unique(F[:,1]):
    m=(F[:,1]==la)&(F[:,3]==0)
    if m.sum()>200: fr[int(la)]=q(F[m,0],(5,15,50,85,95))
htab={}
for lo,hi in [(0,1),(1,3),(3,5),(5,10),(10,15),(15,20),(20,25),(25,30),(30,40)]:
    m=(H[:,0]>=lo)&(H[:,0]<hi)
    if m.sum()>50: htab[f'{lo}-{hi}']=dict(spacing=q(H[m,1],(5,25,50,75,95)),tg=q((H[m,1]-5)/np.maximum(H[m,0],.3),(5,15,25,50,75,95)))
R=[]
for sg in (-1,1):
    z=G[G['dir']==sg]
    h,e=np.histogram(z['s'],bins=np.arange(0,z['s'].max()+200,200)); R.append(dict(dir=sg,counts=h.tolist()))
save('ht',dict(lc_by_s=R,source='https://zenodo.org/records/18540070',hours=HOURS,stats=stats,lane_changes_all=len(LC),screened=tab(G),trucks=tab(LC[(LC['rms']<.3)&(LC['mono']>-.15)&(LC['d1090']<12)&(LC['truck']==1)]),free_speed_by_lane=fr,spacing_by_speed=htab,segments=int(P['seg'].max()+1),pair_hours=len(P)/36000,v_q=q(P['vf'].values[::50],(5,25,50,75,95))))
print('done',len(P),len(LC))
