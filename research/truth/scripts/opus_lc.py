"""Lane changes on TGSIM freeways: duration, lateral speed, accepted and rejected gaps. Centerlines from the provider, I-395 from empirical lane medians."""
import sys,glob,re; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_pairs import load,SITES
from scipy.optimize import least_squares
FLAT={'I90stat':('I90stat','I-90-stationary-Run_{}-geometry-with-ramps.csv'),'I90mov':('I90mov','I-90-moving-Run_{}-geometry-with-ramps.csv'),'I294L1':('I294L1','I-294-L1-Run_{}-geometry-with-ramps.csv'),'I294L2':('I294L2','I294_L2_Run_{}-geometry-with-ramps.csv')}
def centerlines(site,run):
    p=TGA/FLAT[site][0]/FLAT[site][1].format(run)
    if not p.exists(): return None
    c=pd.read_csv(p); cl={}
    for col in c.columns:
        m=re.match(r'x_(-?\d+)',col)
        if m:
            k=int(m.group(1)); df=c[[f'x_{k}',f'y_{k}',f'ramp_{k}']].dropna().sort_values(f'x_{k}')
            cl[k]=(df[f'x_{k}'].values,df[f'y_{k}'].values,df[f'ramp_{k}'].values)
    return cl
def lateral(xs,ys,cl):
    """signed offset of points from a polyline parameterised by x, and ramp flag."""
    xc,yc,rc=cl
    yi=np.interp(xs,xc,yc); slope=np.gradient(yc,xc+1e-9*np.arange(len(xc))); sl=np.interp(xs,xc,slope)
    return (ys-yi)/np.sqrt(1+sl*sl), np.interp(xs,xc,rc)
def fit_tanh(t,y):
    def f(p): return p[0]+p[1]*.5*(1+np.tanh((t-p[2])/np.maximum(p[3],.05)))-y
    y0=np.median(y[:20]);y1=np.median(y[-20:])
    r=least_squares(f,[y0,y1-y0,0.0,1.0],bounds=([-80,-80,-6,.05],[80,80,6,8]))
    res=f(r.x); return r.x,float(np.sqrt(np.mean(res**2)))
def process(site,HW=8.0):
    d=load(site); d=d.drop_duplicates(['run_index','id','time'])
    d['ti']=np.round(d['time']*10).astype(int)
    axis=SITES[site][0]; key='yloc_kf' if axis=='y' else 'xloc_kf'
    d=d.sort_values(['run_index','ti']).reset_index(drop=True)
    frame_key=d['run_index'].values.astype(np.int64)*10000000+d['ti'].values
    X,Y,LANE,VV,AA,TYPE,ID=[d[c].values for c in ['xloc_kf','yloc_kf','lane_kf','speed_kf','acceleration_kf','type_most_common','id']]
    flag=SITES[site][1]; AUTO=d[flag].values if flag else (TYPE==4).astype(int)
    sign=d.sort_values(['run_index','id','ti']).groupby(['run_index','id'])[key].agg(lambda s:np.sign(s.iloc[-1]-s.iloc[0])); 
    d2=d.set_index(['run_index','id']); SGN=pd.Series(sign).reindex(d2.index).values; d=None
    order=np.lexsort((frame_key,ID,d2.index.get_level_values(0).values))
    RUN=d2.index.get_level_values(0).values
    empirical={}
    if site=='I395':
        # lateral = x, lane centres from medians by lane and 20 m y bin
        B=(Y/20).astype(int)
        for l in np.unique(LANE):
            m=(LANE==l)
            empirical[l]=pd.Series(X[m]).groupby(B[m]).median()
    ev=[];stable=[]
    runs=np.unique(RUN)
    for run in runs:
        rm=np.where(RUN==run)[0]
        cl=centerlines(site,int(run)) if site!='I395' else None
        if site!='I395' and cl is None: print('no centerline',site,run); continue
        ids=ID[rm]; o=rm[np.lexsort((frame_key[rm],ids))]
        ub=np.r_[0,np.where(np.diff(ID[o])!=0)[0]+1,len(o)]
        for a,b in zip(ub[:-1],ub[1:]):
            ix=o[a:b]
            if len(ix)<170 or AUTO[ix[0]]: continue
            ti=frame_key[ix]%10000000
            l=LANE[ix]; ch=np.where(l[1:]!=l[:-1])[0]+1
            t=ti/10.0
            if len(ch)==0:
                continue
            for kk,k in enumerate(ch):
                old,new=l[k-1],l[k]
                if abs(old-new)!=1: continue
                if t[k]-t[0]<HW or t[-1]-t[k]<HW: continue
                w=(t>=t[k]-HW)&(t<=t[k]+HW)
                if (ti[w][1:]-ti[w][:-1]).max()>1: continue
                if np.any(np.abs(np.diff(l[w]))>0) and (np.diff(l[w])!=0).sum()!=1: continue
                xs,ys=X[ix][w],Y[ix][w]; tt=t[w]-t[k]
                if cl is not None:
                    if int(old) not in cl: continue
                    off,ramp=lateral(xs,ys,cl[int(old)])
                    rampflag=float(np.nanmax(ramp)) if int(new) not in cl else float(max(np.nanmax(ramp),np.nanmax(lateral(xs,ys,cl[int(new)])[1])))
                else:
                    centre=empirical[old].reindex((ys/20).astype(int)).interpolate(limit_direction='both').values
                    off=xs-centre; rampflag=float(old in(-2,-1,-6) or new in(-2,-1,-6))
                if not np.isfinite(off).all(): continue
                if np.abs(off).max()>70: continue
                p,rms=fit_tanh(tt,off); y0,dw,tc,k_=p
                # direct crossing durations from endpoint medians
                pre=np.median(off[tt<-5]);post=np.median(off[tt>5]); W=post-pre
                if abs(W)<2.2 or abs(W)>5.5: continue
                qq=(off-pre)/W
                a10=np.where(qq>=.1)[0];a90=np.where(qq>=.9)[0];a05=np.where(qq>=.05)[0];a95=np.where(qq>=.95)[0]
                if len(a10)==0 or len(a90)==0: continue
                d1090=tt[a90[0]]-tt[a10[0]]; d0595=tt[a95[0]]-tt[a05[0]] if len(a95) and len(a05) else np.nan
                if d1090<=0: continue
                mono=float(np.min(np.diff(qq[a10[0]:a90[0]+1])) if a90[0]>a10[0] else 0)
                vl=np.gradient(off,tt); vlat=pd.Series(vl).rolling(10,center=True,min_periods=1).mean().values
                peak=float(np.nanmax(np.abs(vlat[(tt>tt[a10[0]])&(tt<tt[a90[0]])]))) if a90[0]>a10[0]+1 else np.nan
                v=float(VV[ix][k]); 
                # surrounding vehicles in the target lane at crossing and earlier opportunities
                fk=int(run)*10000000
                sign_=SGN[ix[0]]
                s_ego=(Y if axis=='y' else X)[ix]*sign_
                # sample 1 Hz from -10 s to 0
                rows=[]
                for dts in range(-10,1):
                    n=np.searchsorted(t,t[k]+dts)
                    if n>=len(ix) or abs(t[n]-(t[k]+dts))>.05: continue
                    tk=fk+int(ti[n])
                    lo=np.searchsorted(frame_key,tk,'left');hi=np.searchsorted(frame_key,tk,'right')
                    fr=np.arange(lo,hi); fr=fr[(LANE[fr]==new)&(SGN[fr]==sign_)&(ID[fr]!=ID[ix[0]])]
                    own=np.arange(lo,hi); own=own[(LANE[own]==l[n])&(SGN[own]==sign_)&(ID[own]!=ID[ix[0]])]
                    def nb(fr):
                        if len(fr)==0: return (np.nan,np.nan,np.nan,np.nan)
                        s=(Y if axis=='y' else X)[fr]*sign_; dd=s-s_ego[n]
                        ah=fr[dd>0]; bh=fr[dd<=0]
                        lead=np.nan;vlead=np.nan;lag=np.nan;vlag=np.nan
                        if len(ah):
                            f=ah[np.argmin(dd[dd>0])]; lead=np.hypot(X[f]-X[ix][n],Y[f]-Y[ix][n]); vlead=VV[f]
                        if len(bh):
                            f=bh[np.argmax(dd[dd<=0])]; lag=np.hypot(X[f]-X[ix][n],Y[f]-Y[ix][n]); vlag=VV[f]
                        return lead,vlead,lag,vlag
                    tl=nb(fr); ol=nb(own)
                    rows.append((dts,VV[ix][n])+tl+ol[:2])
                ev.append(dict(site=site,run=int(run),id=int(ID[ix[0]]),tc=float(t[k]),old=float(old),new=float(new),ramp=rampflag,type=int(TYPE[ix[0]]),curve=(tt.astype('f4'),qq.astype('f4')),speed=v,width=abs(W),d1090=float(d1090),d0595=float(d0595),tanh_k=float(k_),tanh_rms=rms,tanh_w=float(dw),tc_fit=float(tc),peak=peak,mono=mono,rows=rows))
    return ev
if __name__=='__main__':
    all_=[]
    for s in sys.argv[1:]:
        e=process(s); print(s,len(e),flush=True); all_+=e
    import pickle
    pickle.dump(all_,open(CACHE/('lc_events_curves.pkl' if 'I395' not in sys.argv else 'lc_events.pkl'),'wb'))
