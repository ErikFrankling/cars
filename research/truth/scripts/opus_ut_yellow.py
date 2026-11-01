"""DLR UT: yellow stop-or-go decisions and red crossings with true signal states; launch acceleration of the first queued car."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.optimize import minimize
PTS={1:[(604755.480,5792814.102),(604749.966,5792812.211)],2:[(604761.424,5792815.793)],3:[(604790.745,5792814.817),(604792.294,5792809.095),(604793.765,5792806.195)],4:[(604795.332,5792803.053),(604796.300,5792798.214)],5:[(604793.626,5792779.886),(604787.472,5792776.873)],6:[(604784.549,5792776.031)],7:[(604780.221,5792775.418),(604775.881,5792774.066)],8:[(604748.909,5792774.532),(604748.134,5792780.177)],9:[(604746.834,5792783.266),(604745.843,5792786.123),(604744.122,5792790.989)]}
OX,OY=604625,5792650
pts=[(sid,e-OX,n-OY) for sid,v in PTS.items() for e,n in v]
pxy=np.array([(a,b) for _,a,b in pts]);psid=np.array([s for s,_,_ in pts]);C=pxy.mean(0)
d=np.load(CACHE/'ut_veh.npz');o=np.lexsort((d['t'],d['id']))
ID,T,X,Y,V=[d[k][o] for k in ['id','t','x','y','v']]
ub=np.r_[0,np.where(np.diff(ID)!=0)[0]+1,len(ID)]
tl=np.load(CACHE/'ut_tl.npz')
sig={}
for s in PTS:
    m=tl['id']==s;t=tl['t'][m];st=tl['state'][m];oo=np.argsort(t);t=t[oo];st=st[oo]
    g=np.isin(st,[5,6]);y=np.isin(st,[7,8]);r=np.isin(st,[2,3,4])
    yon=np.where(y[1:]&g[:-1])[0]+1
    ev=[]
    for k in yon:
        rk=np.where(r[k:])[0]
        if len(rk): ev.append((t[k],t[k+rk[0]]))
    gon=np.where(g[1:]&~g[:-1])[0]+1
    sig[s]=dict(y=ev,t=t,st=st,g=t[gon])
out={'yellow_duration':{s:q([b-a for a,b in sig[s]['y']],(50,)) for s in sig if sig[s]['y']},'yellow_events':{s:len(sig[s]['y']) for s in sig}}
Dec=[];RedCross=[];Launch=[];Total=0
for a,b in zip(ub[:-1],ub[1:]):
    if b-a<20: continue
    x,y=X[a:b],Y[a:b];D=((x[:,None]-pxy[:,0])**2+(y[:,None]-pxy[:,1])**2)
    n,j=np.unravel_index(np.argmin(D),D.shape)
    if D[n,j]>2.2**2 or not 2<=n<b-a-2: continue
    if np.array([x[n]-x[n-2],y[n]-y[n-2]])@(C-pxy[j])<=0: continue
    s=psid[j];t=T[a:b];v=V[a:b];tc=t[n];Total+=1
    dist=np.hypot(x-pxy[j,0],y-pxy[j,1])
    # state at crossing
    k=np.searchsorted(sig[s]['t'],tc)-1
    if 0<=k<len(sig[s]['st']):
        st=sig[s]['st'][k]
        if st in(2,3,4):
            lastg=sig[s]['t'][:k+1][np.isin(sig[s]['st'][:k+1],[7,8])]
            into=tc-lastg[-1] if len(lastg) else np.nan
            m=v[(t<tc)&(t>tc-15)]
            RedCross.append((s,into,v[n],m.min() if len(m) else np.nan))
    for ty,tr in sig[s]['y']:
        if t[0]<=ty<tc and tc-ty<60:
            i=np.searchsorted(t,ty)
            if i>=n or dist[i]>120 or dist[i]<1: continue
            if v[i]<2: continue
            minv=v[i:n+1].min();stopped=minv<.7
            Dec.append((s,dist[i],v[i],dist[i]/max(v[i],.1),v[i]**2/(2*dist[i]),int(stopped),tc-ty,tr-ty,tc-tr))
            break
    # launch
    gs=sig[s]['g'];g=gs[(gs>tc-20)&(gs<tc)]
    if len(g):
        tg=g[-1];i=np.searchsorted(t,tg)
        if i<len(t) and v[i]<.5 and dist[i]<10:
            f=(t>tg)&(t<tg+10)
            if f.sum()>10:
                sm=np.convolve(v[f],np.ones(3)/3,'same');ac=np.gradient(sm,t[f])
                t5=np.where(v[f]>5)[0];t10=np.where(v[f]>10)[0]
                Launch.append((ac[2:-2].max(),t[f][t5[0]]-tg if len(t5) else np.nan,t[f][t10[0]]-tg if len(t10) else np.nan,v[f][-1],dist[i]))
Dc=np.array(Dec);Rd=np.array(RedCross);La=np.array(Launch)
out.update(total_inbound=Total,decisions=len(Dc),stop_frac=float(Dc[:,5].mean()),red_crossing_records=len(Rd))
bins=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,8),(8,12)]
out['stop_prob_by_time_to_line']={f'{a}-{b}':dict(n=int(((Dc[:,3]>=a)&(Dc[:,3]<b)).sum()),p_stop=float(Dc[(Dc[:,3]>=a)&(Dc[:,3]<b),5].mean()) if ((Dc[:,3]>=a)&(Dc[:,3]<b)).any() else None) for a,b in bins}
out['stop_prob_by_required_decel']={f'{a}-{b}':dict(n=int(((Dc[:,4]>=a)&(Dc[:,4]<b)).sum()),p_stop=float(Dc[(Dc[:,4]>=a)&(Dc[:,4]<b),5].mean()) if ((Dc[:,4]>=a)&(Dc[:,4]<b)).any() else None) for a,b in [(0,.5),(.5,1),(1,1.5),(1.5,2),(2,3),(3,4),(4,6),(6,20)]}
X_=np.c_[np.ones(len(Dc)),Dc[:,3]];y_=Dc[:,5]
r=minimize(lambda b:np.sum(np.logaddexp(0,-(X_@b)*(2*y_-1))),np.zeros(2),method='BFGS');out['logit_stop_vs_ttl']=dict(b0=r.x[0],b1=r.x[1],ttl50=-r.x[0]/r.x[1])
gowithin=Dc[Dc[:,5]==0]
out['go_vehicles_cross_after_red_onset_s']=q(gowithin[:,8],(50,90,95,99));out['go_cross_after_red_frac']=float((gowithin[:,8]>0).mean())
mov=Rd[(Rd[:,3]>1.5)]  # never stopped in the last 15 s: ran it
out['ran_red_share_of_inbound']=float(len(mov)/Total);out['ran_red_seconds_into_red']=q(mov[:,1],(50,75,90,95))
out['ran_red_after_1s_share_of_inbound']=float((mov[:,1]>1).sum()/Total)
out['launch_first_car']=dict(n=len(La),peak_accel=q(La[:,0],(5,25,50,75,95)),t_to_5mps=q(La[:,1],(5,25,50,75,95)),t_to_10mps=q(La[:,2],(5,25,50,75,95)),v_after_10s=q(La[:,3],(5,50,95)))
save('ut_yellow',out);print(json.dumps(out)[:2800])
