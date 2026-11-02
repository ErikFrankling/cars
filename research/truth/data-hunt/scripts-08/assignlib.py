"""Static assignment of a zone OD on the SUMO edge graph. Nodes of the graph are edges of the net, so turn bans are respected."""
import numpy as np,time
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra,connected_components
from scipy.spatial import cKDTree
OX,OY=651972.09,6565003.78
class Net:
    def __init__(s,path):
        N=np.load(path);s.ids=N['ids'];s.L=N['L'].astype(float);s.V=N['V'].astype(float);s.LN=N['LN'].astype(float);s.name=N['name'];s.type=N['type'];s.A=N['A'];s.B=N['B'];s.con=N['con']
        s.n=len(s.ids);s.t0=s.L/np.maximum(s.V,1.0)+1.0
        s.mid=(s.A+s.B)/2
        cap={'motorway':1900,'trunk':1700,'motorway_link':1400,'trunk_link':1300,'primary':1000,'primary_link':900,'secondary':800,'secondary_link':700,'tertiary':600}
        s.cap=np.array([cap.get(t,400) for t in s.type])*s.LN
        g=csr_matrix((np.ones(len(s.con)),(s.con[:,0],s.con[:,1])),shape=(s.n,s.n))
        nc,lab=connected_components(g,directed=True,connection='strong');big=np.bincount(lab).argmax();s.scc=lab==big
        loc=np.isin(s.type,['residential','tertiary','secondary','unclassified','living_street','primary','tertiary_link','secondary_link'])&s.scc
        maj=np.isin(s.type,['motorway','trunk','primary'])&s.scc
        s.li=np.where(loc)[0];s.mi=np.where(maj)[0];s.lt=cKDTree(s.mid[s.li]);s.mt=cKDTree(s.mid[s.mi])
        s.bb=(s.mid[:,0].min(),s.mid[:,0].max(),s.mid[:,1].min(),s.mid[:,1].max());print('net',s.n,'scc',s.scc.sum(),'bbox',s.bb,flush=True)
    def snap(s,xy,major=False):
        t,i=(s.mt,s.mi) if major else (s.lt,s.li);return i[t.query(xy)[1]]
    def matrix(s,t):
        return csr_matrix((t[s.con[:,0]],(s.con[:,0],s.con[:,1])),shape=(s.n,s.n))
    def accum(s,pred,dist,dem):
        """Flow on each node of the shortest-path tree. dem is k x n."""
        n=s.n;par=pred.copy();ok=par>=0
        dep=np.full(n,-1,np.int32)
        # depth by pointer jumping over the tree
        roots=(~ok)&np.isfinite(dist);dep[roots]=0
        d=np.where(ok,1,0).astype(np.int32);j=np.where(ok,par,np.arange(n))
        for _ in range(20):
            d2=d+d[j];j2=j[j]
            if (j2==j).all(): d=d2;break
            d,j=d2,j2
        act=np.where(np.isfinite(dist)&(dem.sum(0)>=0))[0]
        act=act[ok[act]]
        lv=d[act];o=np.argsort(-lv,kind='stable');act=act[o];lv=lv[o]
        cuts=np.flatnonzero(np.diff(lv))+1
        f=dem.copy()
        for grp in np.split(act,cuts):
            for k in range(f.shape[0]): np.add.at(f[k],par[grp],f[k][grp])
        return f
    def assign(s,oz,dz,w,cost):
        """oz,dz node indices; w is k x m. Returns k x n flows."""
        G=s.matrix(cost);order=np.argsort(oz);oz,dz=oz[order],dz[order];w=w[:,order]
        k=w.shape[0];F=np.zeros((k,s.n));lost=0.0
        uo,st=np.unique(oz,return_index=True);en=np.r_[st[1:],len(oz)]
        for o,a,b in zip(uo,st,en):
            dist,pred=dijkstra(G,directed=True,indices=o,return_predecessors=True)
            dem=np.zeros((k,s.n))
            for q in range(k): np.add.at(dem[q],dz[a:b],w[q,a:b])
            dem[:,~np.isfinite(dist)]=0
            F+=s.accum(pred,dist,dem)
        return F
def bpr(net,v,hours):
    return net.t0*(1+.15*np.minimum(v/(net.cap*hours),4.0)**4)
BINS=dict(am=(6.5,9.0),mid=(9.0,15.0),pm=(15.0,18.5),early=(6.0,6.5))  # the rest is 'night'
def binof(h):
    h=h%24;b=np.full(len(h),4)
    b[(h>=6.0)&(h<6.5)]=0;b[(h>=6.5)&(h<9)]=1;b[(h>=9)&(h<15)]=2;b[(h>=15)&(h<18.5)]=3
    return b
def run(net,oz,dz,bin_w,k_cost=1.0,iters=4,label=''):
    """bin_w is 5 x m (early, am, mid, pm, night). Peaks iterate with MSA on BPR, the rest uses free flow. Returns dict of flows by bin plus free-flow total."""
    t=time.time();out=np.zeros((5,net.n))
    oth=[0,2,4]
    F=net.assign(oz,dz,bin_w[oth],net.t0);out[oth]=F;print(label,'free',time.time()-t,flush=True)
    for b,h in((1,2.5),(3,3.5)):
        v=net.assign(oz,dz,bin_w[[b]],net.t0)[0]
        for i in range(iters-1):
            c=bpr(net,v*k_cost,h);y=net.assign(oz,dz,bin_w[[b]],c)[0];v+= (y-v)/(i+2)
        out[b]=v;print(label,'bin',b,time.time()-t,'max v/c',float((v*k_cost/(net.cap*h)).max()),flush=True)
    return out
def clip(ox,oy,dx,dy,bb,mar=500.0):
    """Liang-Barsky on segments. Returns clipped end points and a keep mask, with flags for moved ends."""
    x0,x1,y0,y1=bb[0]+mar,bb[1]-mar,bb[2]+mar,bb[3]-mar
    ddx,ddy=dx-ox,dy-oy
    t0=np.zeros(len(ox));t1=np.ones(len(ox));keep=np.ones(len(ox),bool)
    for p,q in((-ddx,ox-x0),(ddx,x1-ox),(-ddy,oy-y0),(ddy,y1-oy)):
        with np.errstate(divide='ignore',invalid='ignore'):
            r=q/p
        keep&=~((p==0)&(q<0))
        neg=p<0;pos=p>0
        t0=np.where(neg,np.maximum(t0,r),t0);t1=np.where(pos,np.minimum(t1,r),t1)
    keep&=t0<=t1
    return ox+t0*ddx,oy+t0*ddy,ox+t1*ddx,oy+t1*ddy,keep,t0>0,t1<1
def zones(net,ox,oy,dx,dy,w,cell=1000.0):
    """1 km zoning of trip ends; ends beyond the net go to a gate on a major road where the straight line enters."""
    a,b,c,d,keep,om,dm=clip(ox,oy,dx,dy,net.bb)
    a,b,c,d,om,dm,w=a[keep],b[keep],c[keep],d[keep],om[keep],dm[keep],w[:,keep]
    def key(x,y,m): return (np.floor(x/cell).astype(np.int64)*100000+np.floor(y/cell).astype(np.int64))*2+m.astype(np.int64)
    ko,kd=key(a,b,om),key(c,d,dm)
    K,inv=np.unique(np.r_[ko,kd],return_inverse=True)
    wt=w.sum(0);ws=np.r_[wt,wt]
    sx=np.bincount(inv,ws*np.r_[a,c]);sy=np.bincount(inv,ws*np.r_[b,d]);sw=np.maximum(np.bincount(inv,ws),1e-9)
    xy=np.c_[sx/sw,sy/sw];maj=(K%2).astype(bool);node=np.zeros(len(K),np.int64)
    if (~maj).any(): node[~maj]=net.snap(xy[~maj])
    if maj.any(): node[maj]=net.snap(xy[maj],True)
    no,nd=node[inv[:len(ko)]],node[inv[len(ko):]]
    pair=no*net.n+nd;U,pi=np.unique(pair,return_inverse=True)
    W=np.vstack([np.bincount(pi,w[q],minlength=len(U)) for q in range(w.shape[0])])
    uo,ud=U//net.n,U%net.n;m=uo!=ud
    return uo[m],ud[m],W[:,m],dict(zones=int(len(K)),gates=int(maj.sum()),pairs=int(m.sum()),kept_w=float(w.sum()),intrazonal_w=float(W[:,~m].sum()))
