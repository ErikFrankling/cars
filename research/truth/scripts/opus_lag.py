"""Reaction lags three ways, steady-state speed-spacing relation, acceleration and braking distributions, queue start lags on freeways."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.ndimage import uniform_filter1d
sites=sys.argv[1:] or ['I395','I90stat','I90mov','I294L1','HT']
out={}
for site in sites:
    if not (CACHE/f'pairs_{site}.npz').exists(): continue
    d=dict(np.load(CACHE/f'pairs_{site}.npz'))
    if site=='HT':
        keep=d['run']%3==0
        d={k:v[keep] for k,v in d.items()}
    seg=d['seg']; u=np.r_[0,np.where(np.diff(seg)!=0)[0]+1,len(seg)]
    relax=[];onset=[];accl=[];spd=[];start=[];stop_sp=[];steady=[];brk=[];acc_free=[];acorr=[]
    for a,b in zip(u[:-1],u[1:]):
        if d['autof'][a] or d['tf'][a]!=1 or d['tl'][a]!=1: continue
        vf,vl,s=d['vf'][a:b].astype('f8'),d['vl'][a:b].astype('f8'),d['cc'][a:b].astype('f8')
        if s.min()<3: continue
        n=len(vf)
        if n>=250 and vf[:30].mean()>3:
            tg=(s-5)/np.maximum(vf,1.0)
            relax.append((tg[:10].mean(),)+tuple(tg[int(k*10)-5:int(k*10)+5].mean() for k in (2,5,10,15,20,25)))
        afs=np.gradient(uniform_filter1d(vf,5),.1);als=np.gradient(uniform_filter1d(vl,5),.1)
        # cross-correlation on 30 s pieces with variation
        for i in range(0,n-300,300):
            x=vl[i:i+300];y=vf[i:i+300]
            if x.std()<.5: continue
            xc=x-x.mean();yc=y-y.mean();mx=50
            cc=[np.dot(xc[:300-m],yc[m:])/np.sqrt(np.dot(xc[:300-m],xc[:300-m])*np.dot(yc[m:],yc[m:])+1e-9) for m in range(0,mx,2)]
            k=int(np.argmax(cc));
            if cc[k]>.7: spd.append((k*.2,cc[k],s[i:i+300].mean(),y.mean(),k==len(cc)-1,k==0))
            xa=als[i:i+300]-als[i:i+300].mean();ya=afs[i:i+300]-afs[i:i+300].mean()
            ca=[np.dot(xa[:300-m],ya[m:])/np.sqrt(np.dot(xa[:300-m],xa[:300-m])*np.dot(ya[m:],ya[m:])+1e-9) for m in range(0,mx,2)]
            k=int(np.argmax(ca))
            if ca[k]>.5: acorr.append((k*.2,ca[k],k==len(ca)-1,k==0))
        # leader brake onset after a quiet period
        quiet=uniform_filter1d((np.abs(als)<.25).astype(float),20)
        i=25
        while i<n-60:
            if als[i]<-.5 and quiet[i-11]>.99 and als[i:i+10].mean()<-.4 and vf[i]>1:
                j=np.where(afs[i:i+60]<-.3)[0]
                if len(j) and abs(afs[max(i-5,0):i]).max()<.3:
                    onset.append((j[0]*.1,vf[i],s[i]/max(vf[i],.1),s[i]))
                i+=60
            i+=1
        # standing start of the leader and of the follower
        ms=(vl<.3)&(vf<.3)
        k=np.where(ms[:-1]&~ms[1:])[0]
        for m in k:
            tl=np.where(vl[m:]>.5)[0];tf=np.where(vf[m:]>.5)[0]
            if len(tl) and len(tf) and tf[0]+m<n and m>10:
                start.append(((tf[0]-tl[0])*.1,s[m]))
                g=np.where(vf[m:]>4)[0]
                if len(g) and g[0]<80: acc_free.append((afs[m:m+g[0]].max(),4/(g[0]*.1)))
        if ms.any(): stop_sp.append(np.median(s[ms]))
        st=(np.abs(afs)<.15)&(np.abs(vf-vl)<.3)&(np.abs(als)<.15)
        stm=uniform_filter1d(st.astype(float),30)>.99
        if stm.any(): steady.append(np.c_[vf[stm][::20],s[stm][::20]])
        brk.append((afs.min(),afs.max()));accl.append(np.c_[vf[::10],afs[::10],(s/np.maximum(vf,.3))[::10]])
    A=np.vstack(accl) if accl else np.zeros((0,3));R={'samples':len(A)}
    R['speed_xcorr_lag_s']=q([x[0] for x in spd if not x[4] and not x[5]],(5,10,25,50,75,90,95)) if spd else {}
    R['speed_xcorr_boundary_frac']=float(np.mean([x[4] or x[5] for x in spd])) if spd else None
    R['accel_xcorr_lag_s']=q([x[0] for x in acorr if not x[2] and not x[3]],(5,10,25,50,75,90,95)) if acorr else {}
    R['accel_xcorr_boundary_frac']=float(np.mean([x[2] or x[3] for x in acorr])) if acorr else None
    R['brake_onset_lag_s']=q([x[0] for x in onset],(5,10,25,50,75,90,95)) if onset else {}
    R['stand_start_lag_s']=q([x[0] for x in start if x[0]>0],(5,10,25,50,75,90,95)) if start else {}
    R['stopped_spacing_m']=q(stop_sp,(5,10,25,50,75,90,95)) if stop_sp else {}
    R['launch_peak_accel']=q([x[0] for x in acc_free],(5,25,50,75,95)) if acc_free else {}
    R['launch_mean_accel_to_4mps']=q([x[1] for x in acc_free],(5,25,50,75,95)) if acc_free else {}
    if steady:
        Sd=np.vstack(steady);R['steady_points']=len(Sd)
        m=(Sd[:,0]>1)&(Sd[:,0]<25);c=np.polyfit(Sd[m,0],Sd[m,1],1);R['steady_fit_T_s']=float(c[0]);R['steady_fit_s0_spacing']=float(c[1]);R['wave_speed_kmh_from_fit']=float(c[1]/c[0]*3.6)
        R['steady_by_speed']={f'{lo}-{hi}':q(Sd[(Sd[:,0]>=lo)&(Sd[:,0]<hi),1],(10,50,90)) for lo,hi in [(0,1),(1,3),(3,5),(5,8),(8,12),(12,16),(16,22),(22,30),(30,40)] if ((Sd[:,0]>=lo)&(Sd[:,0]<hi)).sum()>30}
    R['accel_by_speed']={};
    for lo,hi in [(0,2),(2,5),(5,10),(10,15),(15,25),(25,40)]:
        z=A[(A[:,0]>=lo)&(A[:,0]<hi),1]
        if len(z)>50: R['accel_by_speed'][f'{lo}-{hi}']=q(z,(1,5,50,95,99))
    b=np.array(brk);R['segment_min_accel']=q(b[:,0],(1,5,25,50));R['segment_max_accel']=q(b[:,1],(50,75,95,99))
    R['time_gap_by_speed']={f'{lo}-{hi}':q(A[(A[:,0]>=lo)&(A[:,0]<hi),2],(5,15,25,50,75,95)) for lo,hi in [(2,5),(5,10),(10,15),(15,25),(25,40)] if ((A[:,0]>=lo)&(A[:,0]<hi)).sum()>50}
    if relax:
        Rx=np.array(relax);lowT=np.percentile(Rx[:,0],25);hiT=np.percentile(Rx[:,0],75)
        R['relax_small_start']=dict(n=int((Rx[:,0]<=lowT).sum()),start=float(np.median(Rx[Rx[:,0]<=lowT,0])),at_2_5_10_15_20_25=np.median(Rx[Rx[:,0]<=lowT,1:],axis=0).round(3).tolist())
        R['relax_large_start']=dict(n=int((Rx[:,0]>=hiT).sum()),start=float(np.median(Rx[Rx[:,0]>=hiT,0])),at_2_5_10_15_20_25=np.median(Rx[Rx[:,0]>=hiT,1:],axis=0).round(3).tolist())
    out[site]=R
    print(site,{k:R.get(k,{}).get('p50') if isinstance(R.get(k),dict) else R.get(k) for k in ('speed_xcorr_lag_s','accel_xcorr_lag_s','brake_onset_lag_s','stand_start_lag_s','stopped_spacing_m','steady_fit_T_s','steady_fit_s0_spacing','wave_speed_kmh_from_fit','launch_peak_accel')},flush=True)
save('lags',out)
