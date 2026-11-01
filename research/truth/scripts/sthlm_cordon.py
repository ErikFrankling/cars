"""Independent demand check: simulated crossings of an approximated congestion-tax cordon, plus an Essingeleden screenline,
 against Transportstyrelsen's real registered passages. usage: sthlm_cordon.py IDX ROUTES [ROUTES...]"""
import sys,pickle,gzip,re,collections,json
from pyproj import Transformer
N=pickle.load(open(sys.argv[1],'rb'));E=N['E']
tr=Transformer.from_crs('EPSG:4326','+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',always_xy=True)
POLY=[(18.012,59.313),(18.012,59.343),(18.036,59.353),(18.052,59.368),(18.07,59.375),(18.12,59.365),(18.115,59.33),(18.112,59.313),(18.095,59.3075),(18.075,59.3047),(18.06,59.3085),(18.045,59.312),(18.025,59.3125)]
xy=[]
for lo,la in POLY:
    x,y=tr.transform(lo,la);xy.append((x-651972.09,y-6565003.78))
def inside(p):
    x,y=p;c=False
    for (x1,y1),(x2,y2) in zip(xy,xy[1:]+xy[:1]):
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def ends(v):
    s=v['lanes'][0]['shape'].split();a=tuple(map(float,s[0].split(',')));b=tuple(map(float,s[-1].split(',')));return a,b
st={}
cross=collections.Counter();names=collections.Counter()
for e,v in E.items():
    if v['fn'] is not None: continue
    a,b=ends(v);ia,ib=inside(a),inside(b);st[e]=ib
    if ia!=ib: cross[e]=1;names[v['name']]+=1
print('cordon edges',len(cross));print(names.most_common(60))
_,ly=tr.transform(18.0,59.3245);ly-=6565003.78
ess=set()
for e,v in E.items():
    if v['fn'] is None and (v['name'] or '').startswith('Essingeleden'):
        a,b=ends(v)
        if (a[1]-ly)*(b[1]-ly)<0: ess.add(e)
print('essinge screen edges',ess)
rx=re.compile(r'depart="([\d.]+)".*route="([^"]+)"')
res={}
for path in sys.argv[2:]:
    R={};cnt=collections.Counter()
    with gzip.open(path,'rt') as f:
        for l in f:
            if l.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',l);R[m[1]]=m[2].split()
            elif l.startswith('<vehicle'):
                m=rx.search(l)
                if 21600<=float(m[1])<66600: cnt[m[2]]+=1
    tot=ess_tot=by=veh=km=0
    tot_all=collections.Counter()
    for k,n in cnt.items():
        r=R[k];veh+=n
        c=sum(e in cross for e in r);tot+=n*c;ess_tot+=n*sum(e in ess for e in r)
    res[path.rsplit('/',1)[1]]=dict(vehicles_0600_1830=veh,cordon_crossings=tot,essingeleden=ess_tot,total=tot+ess_tot,ratio_to_real=(tot+ess_tot)/400976)
    print(path.rsplit('/',1)[1],res[path.rsplit('/',1)[1]],flush=True)
json.dump(res,open('research/truth/stockholm-cordon.json','w'),indent=1)
