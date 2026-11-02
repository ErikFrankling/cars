"""Route variants with identical vehicles, endpoints and departures.
usage: sthlm_routes.py census SRC | nouturn SRC IDX DST | od SRC DST.trips | apply SRC DUA.rou.xml DST
"""
import gzip,re,sys,pickle,collections,heapq,json
def rev(e): return e[1:] if e.startswith('-') else '-'+e
def read(src):
    head=[];R={};V=[]
    with gzip.open(src,'rt') as f:
        for line in f:
            if line.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',line);R[m[1]]=m[2].split()
            elif line.startswith('<vehicle'):
                V.append(line)
            elif line.startswith('<vType'): head.append(line)
    return head,R,V
vr=re.compile(r'route="([^"]+)"')
def census(src):
    _,R,V=read(src);c=collections.Counter(vr.search(v)[1] for v in V);n=len(V)
    top=[x for _,x in sorted(((v,k) for k,v in c.items()),reverse=True)]
    s=sorted(c.values(),reverse=True);cum=lambda k:sum(s[:k])/n
    org=collections.Counter()
    for k,v in c.items(): org[R[k][0]]+=v
    print(json.dumps(dict(n=n,used=len(c),top1=s[0],top100_share=cum(100),top1000_share=cum(1000),top5000_share=cum(5000),median_used=s[len(s)//2],distinct_origins=len(org),top_origin=org.most_common(5))))
def nouturn(src,idx,dst):
    N=pickle.load(open(idx,'rb'));E,C=N['E'],N['C']
    def allowed(l): return 'passenger' in (l.get('allow') or 'passenger') and 'passenger' not in (l.get('disallow') or '')
    pas={e for e,v in E.items() if v['fn'] is None and any(allowed(l) for l in v['lanes'])}
    out=collections.defaultdict(set)
    for e,cs in C.items():
        if e in pas:
            for c in cs:
                if c['to'] in pas and allowed(c) and allowed(E[e]['lanes'][int(c['fromLane'])]) and allowed(E[c['to']]['lanes'][int(c['toLane'])]): out[e].add(c['to'])
    cost={e:E[e]['lanes'][0]['length']/max(E[e]['lanes'][0]['speed'],1)+1 for e in pas}
    def path(a,b):
        # shortest a->b never using an edge's immediate reverse. State is the edge, so reverse pairs are banned on relax.
        d={a:0};prev={};h=[(0,a)]
        while h:
            x,u=heapq.heappop(h)
            if u==b: break
            if x>d[u] or x>600: continue
            for v in out[u]:
                if v==rev(u): continue
                nd=x+cost[v]
                if nd<d.get(v,1e18): d[v]=nd;prev[v]=u;heapq.heappush(h,(nd,v))
        if b not in prev: return None
        p=[b]
        while p[-1]!=a: p.append(prev[p[-1]])
        return p[::-1]
    head,R,V=read(src);used={vr.search(v)[1] for v in V}
    st=collections.Counter();NR={}
    for k in used:
        r=list(R[k]);i=0;had=False
        for _ in range(500):
            i=next((i for i in range(len(r)-1) if rev(r[i])==r[i+1]),None)
            if i is None: break
            had=True
            # Spur a,-a. Drop it and bridge x -> y; at the route ends just trim the spur.
            x=r[i-1] if i>0 else None; y=r[i+2] if i+2<len(r) else None
            if x is None: r=r[i+1:];st['trim_head']+=1;continue
            if y is None: r=r[:i+1];st['trim_tail']+=1;continue
            if y in out[x] and y!=rev(x): r=r[:i]+r[i+2:];st['splice']+=1;continue
            p=path(x,y)
            if p: r=r[:i]+p[:-1]+r[i+2:];st['bridge']+=1;continue
            # no bridge: keep the stretch before the spur, it stays a valid trip with one endpoint moved.
            r=r[:i+1];st['cut']+=1
        r=[e for j,e in enumerate(r) if j==0 or e!=r[j-1]]
        st['routes_changed']+=had; NR[k]=r if len(r)>=1 else R[k]
    left=sum(any(rev(a)==b for a,b in zip(e,e[1:])) for e in NR.values())
    bad=sum(any(b not in out[a] for a,b in zip(e,e[1:])) for e in NR.values())
    print(dict(st),'left',left,'disconnected',bad,flush=True)
    write(dst,head,NR,V)
def transfer(src,idx,dst):
    # Same vehicles on another net: keep the edges that survive, bridge the gaps, U-turns of the source route stay when still connected.
    N=pickle.load(open(idx,'rb'));E,C=N['E'],N['C']
    def allowed(l): return 'passenger' in (l.get('allow') or 'passenger') and 'passenger' not in (l.get('disallow') or '')
    pas={e for e,v in E.items() if v['fn'] is None and any(allowed(l) for l in v['lanes'])}
    out=collections.defaultdict(set)
    for e,cs in C.items():
        if e in pas:
            for c in cs:
                if c['to'] in pas and allowed(c) and allowed(E[e]['lanes'][int(c['fromLane'])]) and allowed(E[c['to']]['lanes'][int(c['toLane'])]): out[e].add(c['to'])
    cost={e:E[e]['lanes'][0]['length']/max(E[e]['lanes'][0]['speed'],1)+1 for e in pas}
    def path(a,b):
        d={a:0};prev={};h=[(0,a)]
        while h:
            x,u=heapq.heappop(h)
            if u==b: break
            if x>d[u] or x>300: continue
            for v in out[u]:
                nd=x+cost[v]
                if nd<d.get(v,1e18): d[v]=nd;prev[v]=u;heapq.heappush(h,(nd,v))
        if b not in prev: return None
        p=[b]
        while p[-1]!=a: p.append(prev[p[-1]])
        return p[::-1]
    head,R,V=read(src);used={vr.search(v)[1] for v in V};st=collections.Counter();NR={}
    for k in used:
        r=[e for e in R[k] if e in pas];res=r[:1]
        for b in r[1:]:
            a=res[-1]
            if a==b: continue
            if b in out[a]: res.append(b);continue
            p=path(a,b)
            if p: res+=p[1:];st['bridged']+=1
            else: st['skipped']+=1
        st['changed']+=res!=R[k];NR[k]=res if res else None
    keep=[v for v in V if NR[vr.search(v)[1]] and len(NR[vr.search(v)[1]])>=1]
    print(dict(st),'vehicles',len(keep),'of',len(V));write(dst,head,{k:v for k,v in NR.items() if v},keep)
def write(dst,head,R,V):
    with gzip.open(dst,'wt',compresslevel=3) as w:
        w.write('<routes>\n');w.writelines(head)
        for k,e in R.items(): w.write(f'<route id="{k}" edges="{" ".join(e)}"/>\n')
        w.writelines(V);w.write('</routes>\n')
def od(src,dst):
    _,R,V=read(src);used=sorted({vr.search(v)[1] for v in V},key=lambda s:int(s[1:]))
    with open(dst,'w') as w:
        w.write('<routes>\n')
        for k in used:
            w.write(f'<trip id="{k}" depart="0" from="{R[k][0]}" to="{R[k][-1]}"/>\n')
        w.write('</routes>\n')
    print(len(used),'od pairs')
def apply(src,dua,dst):
    head,R,V=read(src);NR=dict(R);n=0
    with open(dua) as f:
        cur=None
        for line in f:
            m=re.search(r'<vehicle id="([^"]+)"',line)
            if m: cur=m[1]
            m=re.search(r'<route edges="([^"]+)"',line)
            if m and cur: NR[cur]=m[1].split();n+=1;cur=None
    used={vr.search(v)[1] for v in V}
    miss=[k for k in used if k not in NR]
    kept=[v for v in V]
    print('routes replaced',n,'used',len(used))
    write(dst,head,{k:v for k,v in NR.items() if k in used},kept)
if __name__=='__main__':
    {'census':census,'nouturn':nouturn,'od':od,'apply':apply,'transfer':transfer}[sys.argv[1]](*sys.argv[2:])
