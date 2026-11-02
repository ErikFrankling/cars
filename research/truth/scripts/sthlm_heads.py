"""Where do queues start? Per window: slow edges whose downstream edges are not slow, ranked by excess vehicle-hours. usage: IDX EDGES.csv H0 H1"""
import sys,csv,pickle,collections
N=pickle.load(open(sys.argv[1],'rb'));E,C=N['E'],N['C'];h0,h1=float(sys.argv[3])*3600,float(sys.argv[4])*3600
sam=collections.Counter();dist=collections.Counter();tp=collections.Counter();en=collections.Counter()
for r in csv.DictReader(open(sys.argv[2])):
    if h0<=float(r['begin'])<h1:
        sam[r['edge']]+=float(r['samples']);dist[r['edge']]+=float(r['distance']);tp[r['edge']]+=float(r['teleports']);en[r['edge']]+=float(r['entered'])
def v(e):
    return dist[e]/sam[e] if sam[e]>0 else None
def vf(e): return E[e]['lanes'][0]['speed']
slow={e for e in sam if e in E and E[e]['fn'] is None and sam[e]>300 and (v(e) or 0)<.35*vf(e)}
res=[]
for e in slow:
    dn={c['to'] for c in C.get(e,[])}
    busy=[d for d in dn if d in slow]
    if busy: continue
    ex=sam[e]*(1-v(e)/vf(e))/3600;res.append((ex,e))
res.sort(reverse=True)
print('slow edges',len(slow),'heads',len(res),'excess veh-h at heads',round(sum(x for x,_ in res)))
for ex,e in res[:18]:
    d=E[e];print(f"{ex:8.0f} veh-h {e:24s} {str(d['name'])[:22]:22s} {(d['type'] or '').split('.')[-1]:12s} L={len(d['lanes'])} len={d['lanes'][0]['length']:6.1f} v={v(e)*3.6:4.1f}km/h entered={en[e]:6.0f} tp={tp[e]:4.0f}  next={sorted({c['dir']+':'+str(E[c['to']]['name'])[:14]+'/'+str(round(E[c['to']]['lanes'][0]['length'])) for c in C.get(e,[])})[:3]}")
