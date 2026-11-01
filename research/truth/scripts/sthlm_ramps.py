"""How on-ramps join the mainline in the net, and how much they discharge. usage: IDX [EDGES.csv H0 H1]"""
import sys,pickle,collections,csv,json
N=pickle.load(open(sys.argv[1],'rb'));E,C=N['E'],N['C']
inc=collections.defaultdict(set)
for e,cs in C.items():
    if not e.startswith(':'):
        for c in cs: inc[c['to']].add(e)
ty=lambda e:(E[e]['type'] or '').split('.')[-1]
main={'motorway','trunk'}
ramps=[]
for e,v in E.items():
    if v['fn'] is None and ty(e) in('motorway_link','trunk_link'):
        for t in {c['to'] for c in C.get(e,[])}:
            if ty(t) in main:
                others=[x for x in inc[t] if x!=e and ty(x) in main]
                sts=[c['state'] for c in C[e] if c['to']==t]
                if others: ramps.append((e,t,others[0],sts,len(E[e]['lanes']),len(E[t]['lanes']),len(E[others[0]]['lanes'])))
st=collections.Counter();add=collections.Counter()
for e,t,o,s,lr,lt,lo in ramps:
    k='minor (must yield)' if all(x in 'mw=' for x in s) else 'major or zipper' if any(x in 'MZ' for x in s) else ','.join(sorted(set(s)))
    st[k]+=1;add[(k,'adds lanes' if lt>=lo+lr else 'adds fewer lanes than ramp' if lt>lo else 'no added lane')]+=1
print(len(ramps),'on-ramp merges',dict(st));print({' / '.join(k):v for k,v in add.items()})
if len(sys.argv)>2:
    h0,h1=float(sys.argv[3])*3600,float(sys.argv[4])*3600;en=collections.Counter();sam=collections.Counter();dist=collections.Counter()
    for r in csv.DictReader(open(sys.argv[2])):
        if h0<=float(r['begin'])<h1: en[r['edge']]+=float(r['entered']);sam[r['edge']]+=float(r['samples']);dist[r['edge']]+=float(r['distance'])
    rows=[]
    for e,t,o,s,lr,lt,lo in ramps:
        if sam[e]>200:
            rows.append((dist[e]/sam[e]*3.6,en[e]/(h1-h0)*3600,e,E[e]['name'],s,lr,lt,lo,en[o]/(h1-h0)*3600))
    rows.sort();sl=[r for r in rows if r[0]<15]
    print('ramps with data',len(rows),'slower than 15 km/h',len(sl),'median discharge of slow ramps veh/h',sorted(r[1] for r in sl)[len(sl)//2] if sl else None)
    for r in rows[:14]: print([round(x,1) if isinstance(x,float) else x for x in r])
