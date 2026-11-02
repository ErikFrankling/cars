# netconvert cannot build a sane default program for some large joined controllers (cycles up to 444 s). Splits those controllers into node groups. Usage: maps_split_tls.py IN.nod.xml NET.xml OUT.nod.xml DIST_M
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import re,numpy as np
from scipy.spatial import cKDTree
inp,netp,outp,dist=sys.argv[1:5];dist=float(dist)
n=load_net(netp,cache=False);cyc=collections.defaultdict(float)
for t in n['tls'].values():cyc[t['id']]=sum(p[0] for p in t['phases'])
big={k for k,v in cyc.items() if v>120};print('oversize controllers',len(big),sorted(cyc[k] for k in big))
src=open(inp).read();nodes=[dict(re.findall(r'([\w:.]+)="([^"]*)"',s)) for s in re.findall(r'<node [^>]*/>',src)]
grp=collections.defaultdict(list)
for x in nodes:
    if x.get('tl') in big:grp[x['tl']].append(x)
new={}
for t,ns in grp.items():
    xy=np.array([[float(q['x']),float(q['y'])] for q in ns]);par=list(range(len(ns)))
    def fd(a):
        while par[a]!=a:par[a]=par[par[a]];a=par[a]
        return a
    for a,b in cKDTree(xy).query_pairs(dist):par[fd(a)]=fd(b)
    roots=sorted({fd(i) for i in range(len(ns))})
    for i,q in enumerate(ns):new[q['id']]=f"{t[:40]}_{roots.index(fd(i))}"
def rw(m):
    s=m.group(0);i=re.search(r' id="([^"]*)"',s).group(1)
    return re.sub(r' tl="[^"]*"',f' tl="{new[i]}"',s) if i in new else s
open(outp,'w').write(re.sub(r'<node [^>]*/>',rw,src));print('nodes moved',len(new),'new controllers',len(set(new.values())))
