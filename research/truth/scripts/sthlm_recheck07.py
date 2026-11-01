"""Own recount of report 07 Stockholm numbers."""
import sys,pickle,collections,json,re
N=pickle.load(open(sys.argv[1],'rb'));E,C,J,T=N['E'],N['C'],N['J'],N['T']
def allowed(l): return 'passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '')
pas={e:v for e,v in E.items() if v['fn'] is None and any(allowed(l) for l in v['lanes'])}
ext_j=sum(1 for j in J if not j.startswith(':'));jt=collections.Counter(J[j]['type'] for j in J if not j.startswith(':'))
appr=set();turn=set()
for e,v in pas.items():
    cs=C.get(e,[])
    if any(c['tl'] for c in cs):
        appr.add(e);by=collections.defaultdict(set)
        for c in cs: by[int(c['fromLane'])].add(c['dir'])
        if any(d and d<=set('lLrR') for l,d in by.items() if allowed(v['lanes'][l])): turn.add(e)
nolane=0
for e,v in pas.items():
    conn={int(c['fromLane']) for c in C.get(e,[])}
    nolane+=sum(1 for i,l in enumerate(v['lanes']) if allowed(l) and i not in conn)
minshare=collections.Counter()
for t,q in T.items():
    ph=q['phases'];cyc=sum(p[0] for p in ph);n=len(ph[0][1])
    minshare[round(min(sum(p[0] for p in ph if p[1][i] in 'Gg') for i in range(n))/cyc,4)]+=1
single_j=collections.Counter()
for e in appr:
    for c in C[e]:
        if c['tl']: single_j[c['tl']]=0
print(json.dumps(dict(passenger_edges=len(pas),ext_junctions=ext_j,junction_types=jt,signal_approaches=len(appr),turn_only=len(turn),lanes_no_conn=nolane,min_share_top=minshare.most_common(4)),indent=0,ensure_ascii=False))
