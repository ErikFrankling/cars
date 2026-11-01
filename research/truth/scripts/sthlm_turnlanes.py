"""Lanes whose only outgoing connection is a turnaround, and short-edge pockets."""
import sys,pickle,collections,json
N=pickle.load(open(sys.argv[1],'rb'));E,C=N['E'],N['C']
only=0;multi=0;bytype=collections.Counter();totlanes=0;spec=collections.Counter();ex=[]
for e,v in E.items():
    if v['fn'] is not None: continue
    n=len(v['lanes']);totlanes+=n
    by=collections.defaultdict(set)
    for c in C.get(e,[]): by[int(c['fromLane'])].add(c['dir'])
    if n>1:
        multi+=n
        for l,d in by.items():
            if d=={'t'}:
                only+=1;bytype[(v['type'] or '').split('.')[-1]]+=1
                if len(ex)<8: ex.append((e,v['name'],l,v['lanes'][0]['length']))
print(json.dumps(dict(total_lanes=totlanes,lanes_on_multilane_edges=multi,lanes_only_turnaround=only,by_type=bytype,examples=ex),ensure_ascii=False))
dirs=collections.Counter(c['dir'] for e,cs in C.items() if not e.startswith(':') for c in cs)
print(dict(dirs))
