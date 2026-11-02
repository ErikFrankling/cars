"""DLR UT: queue discharge with real signal state: per-position start delay, stop-line headways, saturation headway,
start-up lost time, standstill gaps. Stop-line points come from Table 3 of the dataset documentation."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
import datetime
print('weekday',datetime.date(2023,9,24).strftime('%A'))
PTS={1:[(604755.480,5792814.102),(604749.966,5792812.211)],2:[(604761.424,5792815.793)],3:[(604790.745,5792814.817),(604792.294,5792809.095),(604793.765,5792806.195)],4:[(604795.332,5792803.053),(604796.300,5792798.214)],
5:[(604793.626,5792779.886),(604787.472,5792776.873)],6:[(604784.549,5792776.031)],7:[(604780.221,5792775.418),(604775.881,5792774.066)],8:[(604748.909,5792774.532),(604748.134,5792780.177)],9:[(604746.834,5792783.266),(604745.843,5792786.123),(604744.122,5792790.989)]}
OX,OY=604625,5792650
pts=[(sid,e-OX,n-OY) for sid,v in PTS.items() for e,n in v]
pxy=np.array([(a,b) for _,a,b in pts]); psid=np.array([s for s,_,_ in pts]); C=pxy.mean(0); print('centre',C)
d=np.load(CACHE/'ut_veh.npz'); o=np.lexsort((d['t'],d['id']))
ID,T,X,Y,V,VX,VY,LL,WW,TR,YAW=[d[k][o] for k in ['id','t','x','y','v','vx','vy','L','W','truck','yaw']]
ub=np.r_[0,np.where(np.diff(ID)!=0)[0]+1,len(ID)]
tl=np.load(CACHE/'ut_tl.npz')
print('tracks',len(ub)-1,'rows',len(ID))
print({int(i):dict(zip(*[x.tolist() for x in np.unique(tl['state'][tl['id']==i],return_counts=True)])) for i in np.unique(tl['id'])[:12]})
# green onsets per signal
green={}
for s in PTS:
    m=tl['id']==s; t=tl['t'][m]; st=tl['state'][m]; oo=np.argsort(t); t=t[oo]; st=st[oo]
    g=np.isin(st,[5,6]); on=np.where(g[1:]&~g[:-1])[0]+1
    off=np.where(~g[1:]&g[:-1])[0]+1
    green[s]=[(t[k],st[k-1],(off[off>k][0] if (off>k).any() else None)) for k in on]
    green[s]=[(a,b,(t[c] if c is not None else np.nan)) for a,b,c in green[s]]
print({s:len(v) for s,v in green.items()},'green dur p50',{s:round(float(np.nanmedian([c-a for a,b,c in v])),1) for s,v in green.items() if v},'prior states',{s:dict(zip(*[x.tolist() for x in np.unique([b for a,b,c in v],return_counts=True)])) for s,v in green.items() if v})
# per-track stop line assignment
cross=[]  # track idx, point idx, t_cross_center, v_at_cross, L, W, truck, turn angle
for i in range(len(ub)-1):
    a,b=ub[i],ub[i+1]
    if b-a<20: continue
    x,y=X[a:b],Y[a:b]
    D=((x[:,None]-pxy[:,0])**2+(y[:,None]-pxy[:,1])**2)
    k=np.unravel_index(np.argmin(D),D.shape)
    if D[k]>2.2**2: continue
    j=k[1]; n=k[0]
    if not 2<=n<b-a-2: continue
    # inbound: motion toward centre
    dirv=np.array([x[n+2]-x[n-2],y[n+2]-y[n-2]]); toC=C-pxy[j]
    if dirv@toC<=0: continue
    h0=np.arctan2(*(np.array([y[n]-y[max(n-10,0)],x[n]-x[max(n-10,0)]])))
    h1=np.arctan2(*(np.array([y[-1]-y[n],x[-1]-x[n]])))
    turn=(np.rad2deg(h1-h0)+180)%360-180
    cross.append((i,j,T[a+n],V[a+n],np.median(LL[a:b]),np.median(WW[a:b]),np.median(TR[a:b]),turn,b-a))
cross=np.array(cross); print('inbound crossings',len(cross),{int(k):int((cross[:,1]==k).sum()) for k in np.unique(cross[:,1])})
queues=[]
for j in np.unique(cross[:,1]).astype(int):
    sid=psid[j]; cj=cross[cross[:,1]==j]
    for tg,prev,tr in green[sid]:
        c=cj[(cj[:,2]>tg-1)&(cj[:,2]<tg+90)]
        rows=[]
        for r in c:
            i=int(r[0]); a,b=ub[i],ub[i+1]; tt=T[a:b]
            if tt[0]>tg-1.0: continue
            n=np.searchsorted(tt,tg); n=min(n,b-a-1)
            if abs(tt[n]-tg)>.3 or V[a+n]>1.0: continue
            dist=np.hypot(X[a+n]-pxy[j,0],Y[a+n]-pxy[j,1])
            if dist>120: continue
            v=V[a:b]; mv=np.where((tt>tg-3)&(v>1.5))[0]
            mv=mv[tt[mv]>=tg-3]
            t_move=tt[mv[0]] if len(mv) else np.nan
            # front crossing: first time centre-to-stopline distance along path <= L/2
            dd=np.hypot(X[a:b]-pxy[j,0],Y[a:b]-pxy[j,1]); nc=np.argmin(dd)
            ks=np.where((tt<tt[nc]+1e-6)&(dd<=r[4]/2))[0]
            t_front=tt[ks[0]] if len(ks) else tt[nc]
            rows.append((dist,t_move,t_front,r[4],r[5],r[6],r[7],i,X[a+n],Y[a+n],V[a+n],r[3]))
        if not rows: continue
        rows=np.array(sorted(rows,key=lambda z:z[0]))
        queues.append(dict(sid=int(sid),pt=int(j),tg=float(tg),prev=int(prev),rows=rows))
print('queues',len(queues),'sizes',np.bincount([len(q['rows']) for q in queues])[:15])
# position stats: only contiguous queues: first vehicle within 12 m front of stop line; successive gap 0-10 m
rec=[];gaps=[]
for qu in queues:
    r=qu['rows']; n=len(r)
    if r[0,0]-r[0,3]/2>12: continue
    ok=True; prevt=qu['tg']; prevm=qu['tg']
    for k in range(n):
        if k:
            cc=np.hypot(r[k,8]-r[k-1,8],r[k,9]-r[k-1,9]); g=cc-(r[k,3]+r[k-1,3])/2
            if g<-0.5 or g>10: break
            gaps.append((qu['sid'],k+1,g,cc,r[k,3],r[k-1,3],r[k,5],r[k-1,5],qu['tg']))
        h=r[k,2]-prevt
        if h<=0 or h>12: break
        trk=r[k,5]>.5
        rec.append((qu['sid'],qu['pt'],qu['tg'],k+1,h,r[k,2]-qu['tg'],r[k,1]-qu['tg'],(r[k,1]-prevm) if k else r[k,1]-qu['tg'],r[k,3],r[k,4],trk,r[k,6],r[k,11],r[k,0]))
        prevt=r[k,2]; prevm=r[k,1]
R=np.array(rec);G=np.array(gaps)
np.savez_compressed(CACHE/'ut_queue.npz',R=R,G=G)
names='sid pt tg pos h t_front start_delay start_lag L W truck turn v_cross dist'.split()
ix={n:i for i,n in enumerate(names)}
straight=(np.abs(R[:,ix['turn']])<25)&(R[:,ix['truck']]==0)
out={'source':'https://zenodo.org/records/20919480','weekday':datetime.date(2023,9,24).strftime('%A'),'tracks':len(ub)-1,'inbound_crossings':len(cross),'queues_detected':len(queues),'records':len(R),'green_onsets':{s:len(v) for s,v in green.items()}}
tab={}
for label,mask in [('straight_car',straight),('all_movements_car',R[:,ix['truck']]==0)]:
    S=R[mask]; t={}
    for p in range(1,13):
        z=S[S[:,ix['pos']]==p]
        t[p]=dict(n=len(z),h=q(z[:,ix['h']],(25,50,75)),front_cross_after_green=q(z[:,ix['t_front']],(25,50,75)),start_delay=q(z[:,ix['start_delay']],(10,25,50,75,90)),start_lag_vs_leader=q(z[:,ix['start_lag']],(10,25,50,75,90)),v_cross=q(z[:,ix['v_cross']],(50,)))
    hs=S[S[:,ix['pos']]>=5,ix['h']]
    hsat=float(np.median(hs)) if len(hs) else np.nan
    # bootstrap by queue event
    ev=np.unique(S[:,ix['tg']]); rng=np.random.default_rng(1); boots=[]; lts=[]
    def calc(Sb):
        hb=Sb[Sb[:,ix['pos']]>=5,ix['h']]
        hm=np.median(hb) if len(hb) else np.nan
        lt=sum(np.mean(Sb[Sb[:,ix['pos']]==p,ix['h']])-hm for p in range(1,5))
        return hm,lt,np.mean(hb) if len(hb) else np.nan
    base=calc(S)
    for _ in range(400):
        pick=rng.choice(ev,len(ev)); Sb=np.vstack([S[S[:,ix['tg']]==e] for e in pick[:len(pick)]]) if len(ev)<400 else S[np.isin(S[:,ix['tg']],pick)]
        boots.append(calc(Sb))
    boots=np.array(boots)
    tab[label]=dict(by_position=t,hsat_median=base[0],hsat_mean=base[2],lost_time_first4=base[1],hsat_ci=np.nanpercentile(boots[:,0],[2.5,97.5]).tolist(),lost_ci=np.nanpercentile(boots[:,1],[2.5,97.5]).tolist(),n_events=len(ev),n_pos5plus=len(hs),sat_flow_vphpl=3600/base[0] if base[0]>0 else None)
out['tables']=tab
sg=G[(G[:,6]<.5)&(G[:,7]<.5)]
out['standstill_bumper_gap_m']=q(sg[:,2],(5,10,25,50,75,90,95)); out['standstill_center_spacing_m']=q(sg[:,3]); out['length_cars_m']=q(sg[:,4])
save('ut_queue',out); print(json.dumps({k:out[k] for k in out if k!='tables'},indent=0)[:1500])
for l,t in tab.items():
    print(l,{k:t[k] for k in t if k!='by_position'})
    for p,v in t['by_position'].items():
        print(p,v['n'],'h',v['h'].get('p50'),'tfront',v['front_cross_after_green'].get('p50'),'delay',v['start_delay'].get('p50'),'lag',v['start_lag_vs_leader'].get('p50'),v['start_lag_vs_leader'].get('p10'),v['start_lag_vs_leader'].get('p90'),'v',v['v_cross'].get('p50'))
