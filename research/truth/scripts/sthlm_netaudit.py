"""Census of structural net artefacts that can lock traffic regardless of demand."""
import sys,pickle,json,collections
N=pickle.load(open(sys.argv[1],'rb'));E,C,J,T=N['E'],N['C'],N['J'],N['T']
ext={k:v for k,v in E.items() if v['fn'] is None}
pas={k:v for k,v in ext.items() if any('passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '') for l in v['lanes'])}
L=lambda e:e['lanes'][0]['length']
cut=[0.5,1,2,3,5,7,7.5,10,15]
out={'external_edges':len(pas)}
out['edges_shorter_than']={str(c):sum(L(v)<c for v in pas.values()) for c in cut}
tls_of={}
for e,cs in C.items():
    if e.startswith(':'):continue
    for c in cs:
        if c['tl']: tls_of.setdefault(c['tl'],[]).append((e,c))
appr={t:collections.Counter(e for e,_ in v) for t,v in tls_of.items()}
na=collections.Counter(len(a) for a in appr.values()); out['tls_by_approach_edges']={str(k):v for k,v in sorted(na.items())}
def conflict_free(t):
    # single approach: nothing else ever crosses it, the only reason for red is a pedestrian call.
    return len(appr[t])==1
single=[t for t in appr if conflict_free(t)]
out['tls_single_approach']=len(single)
two_opp=0
tw=[]
for t,a in appr.items():
    if len(a)==2:
        # two approaches all going straight: mid-block crossing on a two-way road.
        if all(c['dir']=='s' or c['dir']=='t' for _,c in tls_of[t]): two_opp+=1; tw.append(t)
out['tls_two_approach_straight_only']=two_opp
Path=None
# red share per controller at nominal durations
red=collections.Counter();rs=[]
for t,q in T.items():
    p=q['phases']
    cyc=sum(x[0] for x in p)
    n=len(p[0][1]);
    best=max(sum(x[0] for x in p if x[1][i] in 'Gg') for i in range(n))/cyc if n else 0
    rs.append(best)
import numpy as np
out['tls_best_green_share_quantiles']=[float(q) for q in np.quantile(rs,[.05,.25,.5,.75,.95])]
# short storage between two signals
tj=set(T)
short=[]
for k,v in pas.items():
    if v['frm'] in tj and v['to'] in tj: short.append((L(v),k,v['name']))
short.sort()
out['edges_between_two_tls']=len(short)
out['edges_between_two_tls_lt7m']=sum(s[0]<7 for s in short)
out['edges_between_two_tls_lt15m']=sum(s[0]<15 for s in short)
out['edges_between_two_tls_lt30m']=sum(s[0]<30 for s in short)
out['worst_short']=short[:15]
# junctions with very short edge on non-tls
tot=collections.Counter()
for k,cs in C.items():
    if k.startswith(':'):continue
    for c in cs:
        tot[c['dir']]+=1
out['connections_by_dir']=dict(tot)
tt=collections.Counter(c['state'] for k,cs in C.items() if not k.startswith(':') for c in cs if c['dir']=='t')
out['turnaround_state']=dict(tt)
# Lanes with no connection, on edges with other lanes that do
nolanes=0;dead=0
for k,v in pas.items():
    cs=C.get(k,[]);conn={int(c['fromLane']) for c in cs}
    miss=[i for i in range(len(v['lanes'])) if i not in conn]
    if miss and conn: nolanes+=len(miss)
    if not conn: dead+=1
out['lanes_without_connection_on_connected_edges']=nolanes
out['edges_no_outgoing']=dead
json.dump(dict(out,single=single,two_opp=tw),open(sys.argv[2],'w'),indent=1,ensure_ascii=False)
print(json.dumps(out,indent=1,ensure_ascii=False))
