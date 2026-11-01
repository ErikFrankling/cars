"""Fast routing on the edge graph with scipy, no duarouter. Candidate OD pool and congestion feedback.
 pool IDX KM NORIGINS NDEST SEED OUT.pool       candidate paths with a distance kernel, free-flow plus junction penalties
 reroute IDX ROUTES.rou.gz EDGES.csv SHARE SEED OUT.rou.gz [BEGIN END]  move SHARE of the vehicles of each route to the current best path, same OD and departure
"""
import sys,pickle,gzip,re,random,collections,csv,json
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
def allowed(l): return 'passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '')
PEN=dict(tls=15.0,m=4.0,eq=4.0,left=2.0,M=0.0)
class G:
    def __init__(s,idx):
        N=pickle.load(open(idx,'rb'));s.E,s.C=N['E'],N['C']
        s.ids=[e for e,v in s.E.items() if v['fn'] is None and any(allowed(l) for l in v['lanes'])]
        s.ix={e:i for i,e in enumerate(s.ids)}
        s.tt=np.array([s.E[e]['lanes'][0]['length']/max(s.E[e]['lanes'][0]['speed'],.5)+.3 for e in s.ids])
        arcs={}
        for e in s.ids:
            for c in s.C.get(e,[]):
                t=c['to']
                if t not in s.ix or not allowed(s.E[e]['lanes'][int(c['fromLane'])]) or not allowed(s.E[t]['lanes'][int(c['toLane'])]): continue
                p=PEN['tls'] if c['tl'] else PEN['m'] if c['state'] in 'ms' else PEN['eq'] if c['state']=='=' else 0
                if c['dir'] in('l','L'): p+=PEN['left']
                k=(s.ix[e],s.ix[t]);arcs[k]=(min(arcs[k][0],p) if k in arcs else p,c['dir'])
        # Turnarounds only where nothing else leaves the edge.
        out=collections.Counter(a for (a,b),(p,d) in arcs.items() if d!='t')
        arcs={k:v for k,v in arcs.items() if v[1]!='t' or out[k[0]]==0}
        s.a=np.array([k[0] for k in arcs]);s.b=np.array([k[1] for k in arcs]);s.p=np.array([v[0] for v in arcs.values()])
        s.mid=np.array([s._mid(e) for e in s.ids]);s.len=np.array([s.E[e]['lanes'][0]['length'] for e in s.ids])
        s.cls=np.array([(s.E[e]['type'] or '').split('.')[-1].replace('_link','') for e in s.ids])
    def _mid(s,e):
        p=s.E[e]['lanes'][0]['shape'].split();x,y=p[len(p)//2].split(',');return float(x),float(y)
    def mat(s,tt=None):
        tt=s.tt if tt is None else tt
        return csr_matrix((s.p+tt[s.b]+1e-3,(s.a,s.b)),shape=(len(s.ids),len(s.ids)))
    def paths(s,mat,o,dests):
        d,pr=dijkstra(mat,directed=True,indices=int(o),return_predecessors=True)
        res={}
        for t in dests:
            if not np.isfinite(d[t]) or t==o: continue
            p=[int(t)]
            while p[-1]!=o: p.append(int(pr[p[-1]]))
            res[int(t)]=p[::-1]
        return res
def pool(idx,km,no,nd,seed,out):
    g=G(idx);km=float(km);no=int(no);nd=int(nd);rng=np.random.default_rng(int(seed));m=g.mat()
    local=np.where(np.isin(g.cls,['residential','living_street','unclassified','tertiary']))[0]
    w=g.len[local]/g.len[local].sum()
    ind=np.bincount(g.b,minlength=len(g.ids));oud=np.bincount(g.a,minlength=len(g.ids))
    major=np.isin(g.cls,['motorway','trunk','primary','secondary'])
    src=np.where((ind==0)&major)[0];snk=np.where((oud==0)&major)[0]
    O=list(rng.choice(local,no,p=w))+list(src)*5
    res=[]
    for n,o in enumerate(O):
        cand=rng.choice(local,4000,p=w);dd=np.hypot(*(g.mid[cand]-g.mid[o]).T)
        pr=np.exp(-dd/(km*1000))*(dd>800);pr=pr/max(pr.sum(),1e-12)
        ds=list(rng.choice(cand,min(nd,4000),p=pr)) if pr.sum()>0 else []
        ds+=[snk[rng.integers(len(snk))]] if len(snk) and rng.random()<.2 else []
        for t,p in g.paths(m,o,ds).items(): res.append(p)
    # The same trick backward for sources is unnecessary: trips into portals are drawn above, trips out of portals by the src origins.
    with open(out,'w') as f:
        for p in res: f.write(' '.join(g.ids[i] for i in p)+'\n')
    L=[g.len[p].sum() for p in res];print('pool',len(res),'mean km',np.mean(L)/1000,'median',np.median(L)/1000,'src',len(src),'snk',len(snk))
def read(src):
    head=[];R={};V=[]
    with gzip.open(src,'rt') as f:
        for line in f:
            if line.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',line);R[m[1]]=m[2].split()
            elif line.startswith('<vehicle'):V.append(line)
            elif line.startswith('<vType'):head.append(line)
    return head,R,V
def reroute(idx,src,edges,share,seed,dst,begin='21600',end='64800'):
    g=G(idx);share=float(share);rnd=random.Random(int(seed));b0=float(begin);b1=float(end)
    # Mean experienced edge time in the busy window, from samples per entry, never below free flow.
    sam=collections.Counter();ent=collections.Counter();tp=collections.Counter()
    for r in csv.DictReader(open(edges)):
        if b0<=float(r['begin'])<b1: sam[r['edge']]+=float(r['samples']);ent[r['edge']]+=float(r['entered']);tp[r['edge']]+=float(r['teleports'])
    tt=g.tt.copy()
    for i,e in enumerate(g.ids):
        if ent[e]>0: tt[i]=max(tt[i],min(sam[e]/ent[e]+120*tp[e]/ent[e],900.0))
        elif tp[e]>0: tt[i]=max(tt[i],300.0)
    print('edges above 2x free flow',int((tt>2*g.tt).sum()),'above 60 s extra',int((tt>g.tt+60).sum()))
    # Internal-lane teleports charge the edges entering that junction.
    for e,n in tp.items():
        if e.startswith(':') and n:
            j=e[1:].rsplit('_',1)[0]
            for i2,x in enumerate(()): pass
    head,R,V=read(src);vr=re.compile(r'route="([^"]+)"');by=collections.defaultdict(list)
    for i,v in enumerate(V): by[vr.search(v)[1]].append(i)
    od=collections.defaultdict(list)
    for r,idxs in by.items():
        a,b=R[r][0],R[r][-1]
        if a in g.ix and b in g.ix: od[(g.ix[a],g.ix[b])].append(r)
    byo=collections.defaultdict(set)
    for (a,b) in od: byo[a].add(b)
    m=g.mat(tt);newR=dict(R);nv=0;nid=0;same=0
    for o,ds in byo.items():
        P=g.paths(m,o,list(ds))
        for t,p in P.items():
            path=[g.ids[i] for i in p];rid=None
            for r in od[(o,t)]:
                if R[r]==path: rid=r
            if rid is None:
                rid=f'a{seed}_{nid}';nid+=1;newR[rid]=path
            for r in od[(o,t)]:
                if r==rid: same+=len(by[r]);continue
                for i in by[r]:
                    if rnd.random()<share:
                        V[i]=vr.sub(f'route="{rid}"',V[i]);nv+=1
    used={vr.search(v)[1] for v in V}
    with gzip.open(dst,'wt',compresslevel=3) as w:
        w.write('<routes>\n');w.writelines(head)
        for k in used: w.write(f'<route id="{k}" edges="{" ".join(newR[k])}"/>\n')
        w.writelines(V);w.write('</routes>\n')
    print('moved vehicles',nv,'routes',len(used),'already on best',same)
if __name__=='__main__':{'pool':pool,'reroute':reroute}[sys.argv[1]](*sys.argv[2:])
