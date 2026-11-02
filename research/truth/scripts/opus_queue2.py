"""Second and third sites for discharge headways: NGSIM Lankershim and Peachtree, TGSIM Foggy Bottom. No signal phases are used: positions 2+ only, from queued crossings of an inferred stop line."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
def analyse(D,name,min_stop=1.0,Lfront=0.0):
    """D columns: key,id,t,x,y,v over whole tracks, including frames inside junctions. Stops are read per approach lane, crossings on the whole track."""
    rec=[];lines=0
    D=D.sort_values(['id','t']).reset_index(drop=True)
    ID=D['id'].values;ub=np.r_[0,np.where(np.diff(ID)!=0)[0]+1,len(ID)];span={ID[a]:(a,b) for a,b in zip(ub[:-1],ub[1:])}
    X,Y,T,V,K=D['x'].values,D['y'].values,D['t'].values,D['v'].values,D['key'].values
    for key,idx in D.groupby('key',sort=False).groups.items():
        if str(key).startswith('X'): continue
        idx=np.asarray(idx)
        ids=np.unique(ID[idx])
        if len(ids)<20: continue
        xy=np.c_[X[idx],Y[idx]];c=xy.mean(0);u,s_,vt=np.linalg.svd(xy[::20]-c,full_matrices=False);ax=vt[0]
        dr=[]
        for i in ids[:300]:
            a,b=span[i]; m=K[a:b]==key
            z=(np.c_[X[a:b][m],Y[a:b][m]]-c)@ax
            if len(z)>10: dr.append(np.sign(z[-1]-z[0]))
        sg=np.sign(np.sum(dr)) if dr else 0
        if sg==0: continue
        stops=[];cands={}
        for i in ids:
            a,b=span[i]; m=(K[a:b]==key)&(V[a:b]<.3)
            if m.sum()*.1<min_stop: continue
            ss=((np.c_[X[a:b],Y[a:b]]-c)@ax)*sg
            stops.append(ss[m].max()); cands[i]=(a,b,ss)
        if len(stops)<8: continue
        st=np.array(stops);h,e=np.histogram(st,bins=np.arange(st.min(),st.max()+3,3.0))
        if len(h)<1: continue
        cand=np.where(h>=max(3,.1*h.max()))[0]
        if not len(cand): continue
        line=e[cand[-1]+1]+1.0;lines+=1
        cross=[]
        for i,(a,b,ss) in cands.items():
            k=np.where((ss[:-1]<line)&(ss[1:]>=line))[0]
            if not len(k): continue
            k=k[0];tc=T[a:b][k]
            w=(T[a:b]<tc)&(T[a:b]>tc-40)&(ss>line-120)
            ms=V[a:b][w]<.3
            if ms.sum()*.1<1.0: continue
            tt=T[a:b][w];tl=tt[ms].max();sl=ss[w][ms][-1]
            mv=np.where((T[a:b]>tl)&(V[a:b]>1.5))[0]
            cross.append((tc,tl,sl,T[a:b][mv[0]] if len(mv) else np.nan,V[a:b][k],i))
        cross=sorted(cross)
        i=0
        while i<len(cross):
            pl=[cross[i]];j=i+1
            while j<len(cross) and cross[j][0]-pl[-1][0]<7 and cross[j][2]<pl[-1][2]-3 and cross[j][2]>pl[-1][2]-15:
                pl.append(cross[j]);j+=1
            if len(pl)>=2 and line-pl[0][2]<14:
                for k in range(1,len(pl)):
                    rec.append((k+1,pl[k][0]-pl[k-1][0],pl[k][3]-pl[k-1][3],pl[k-1][2]-pl[k][2],pl[k][4],str(key)))
            i=j
    R=pd.DataFrame(rec,columns='pos h lag sp vc key'.split())
    out=dict(site=name,lanes_with_lines=lines,records=len(R),keys=int(R['key'].nunique()) if len(R) else 0)
    if len(R)==0: return out
    out['by_pos']={int(p):dict(n=len(z),h=q(z['h'],(25,50,75)),lag=q(z['lag'],(10,25,50,75,90)),standing_front_spacing=q(z['sp'],(25,50,75)),vc=q(z['vc'],(50,))) for p,z in R.groupby('pos') if p<=12}
    z=R[R['pos']>=5]; out['hsat_pos5plus']=q(z['h'],(25,50,75)); out['sat_flow_vphpl']=3600/float(z['h'].mean()) if len(z) else None
    z=R[R['pos']>=4]; out['hsat_pos4plus']=q(z['h'],(25,50,75))
    return out
res=[]
for nm in ('lankershim','peachtree'):
    d=pd.read_csv(NG/f'{nm}.csv',usecols=['vehicle_id','frame_id','local_x','local_y','v_class','v_vel','lane_id','int_id','section_id','direction'])
    d=d[(d['v_class']==2)]
    D=pd.DataFrame(dict(key=np.where(d['int_id']==0,d['direction'].astype(str)+'_'+d['section_id'].astype(str)+'_'+d['lane_id'].astype(str),'X'),id=d['vehicle_id'].values,t=d['frame_id'].values*.1,x=d['local_x'].values*.3048,y=d['local_y'].values*.3048,v=d['v_vel'].values*.3048))
    r=analyse(D,nm); res.append(r); print(json.dumps({k:r[k] for k in r if k!='by_pos'})[:500],flush=True)
    if 'by_pos' in r: print({p:(v['n'],v['h']['p50'],v['lag']['p50']) for p,v in r['by_pos'].items()},flush=True)
d=pd.read_csv(TG/'Foggy.csv',usecols=['id','time','xloc_kf','yloc_kf','lane_kf','speed_kf_x','speed_kf_y','type_most_common'])
d=d[(d['type_most_common']==3)]
D=pd.DataFrame(dict(key=np.where((d['lane_kf']>=5)&(d['lane_kf']<=34),d['lane_kf'].astype(int).astype(str),'X'),id=d['id'].values,t=d['time'].values,x=d['xloc_kf'].values,y=d['yloc_kf'].values,v=np.hypot(d['speed_kf_x'],d['speed_kf_y']).values))
r=analyse(D,'foggy_bottom'); res.append(r); print(json.dumps({k:r[k] for k in r if k!='by_pos'})[:500],flush=True)
if 'by_pos' in r: print({p:(v['n'],v['h']['p50'],v['lag']['p50']) for p,v in r['by_pos'].items()},flush=True)
save('queue_second_sites',res)
