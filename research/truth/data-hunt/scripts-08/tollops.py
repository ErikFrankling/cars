"""Toll cordon from an OSM-keyed link list (way id + segment + direction) on the SUMO net. usage: tollops.py net.npz toll_osm.xml flows..."""
import sys,re,json,collections as C,numpy as np
N=np.load(sys.argv[1]);ids=N['ids'];name=N['name'];A=N['A'];B=N['B']
links=re.findall(r'<link id="(\d+)(\d{4})([fr])"',open(sys.argv[2]).read());print('links',len(links))
by=C.defaultdict(list)
for i,e in enumerate(ids):
    m=re.match(r'^(-?)(\d+)(#\d+)?$',str(e))
    if m: by[(m[2],'r' if m[1] else 'f')].append(i)
hit=[];miss=[]
seen=set()
for w,s,d in links:
    if (w,d) in seen: continue
    seen.add((w,d))
    v=by.get((w,d))
    if v: hit.append(v)
    else: miss.append((w,d))
print('ways with a net edge',len(hit),'missing',len(miss),miss[:12])
print(C.Counter(str(name[v[0]]) for v in hit).most_common(40))
cx=np.array([A[v].mean(0) for v in hit]);print('xy extent',cx.min(0).round(),cx.max(0).round())
res={}
for p in sys.argv[3:]:
    F=np.load(p)['F'];w=F[[0,1,2,3]].sum(0);m=sum(w[v].max() for v in hit);res[p.split('/')[-1]]=round(float(m));print(p,round(m),'ratio to 424390: %.3f'%(m/424390))
json.dump(res,open('out/toll_links.json','w'),indent=1)
