"""Rewrite an OD trip file for another net: same endpoints when the edge survives, else nearest edge of the same way, else nearest edge.
usage: sthlm_remap.py OLD.idx NEW.idx IN.trips OUT.trips"""
import sys,pickle,re,collections
import numpy as np
from scipy.spatial import cKDTree
old=pickle.load(open(sys.argv[1],'rb'))['E'];new=pickle.load(open(sys.argv[2],'rb'))['E']
def allowed(v): return v['fn'] is None and any('passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '') for l in v['lanes'])
def mid(v):
    p=v['lanes'][0]['shape'].split();x,y=p[len(p)//2].split(',');return float(x),float(y)
ids=[e for e,v in new.items() if allowed(v)];pts=np.array([mid(new[e]) for e in ids]);tree=cKDTree(pts)
way=collections.defaultdict(list)
for e in ids: way[e.split('#')[0]].append(e)
cnt=collections.Counter()
def m(e):
    if e in new and allowed(new[e]): cnt['same']+=1;return e
    p=np.array(mid(old[e]));c=way.get(e.split('#')[0])
    if c:
        cnt['same_way']+=1;return min(c,key=lambda x:np.hypot(*(np.array(mid(new[x]))-p)))
    cnt['nearest']+=1;return ids[tree.query(p)[1]]
rx=re.compile(r'from="([^"]+)" to="([^"]+)"')
with open(sys.argv[3]) as f,open(sys.argv[4],'w') as w:
    for l in f:
        g=rx.search(l)
        if g:
            a,b=m(g[1]),m(g[2]);l=rx.sub(f'from="{a}" to="{b}"',l)
        w.write(l)
print(dict(cnt))
