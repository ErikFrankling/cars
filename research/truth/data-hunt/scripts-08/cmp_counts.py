"""Calibrate-role Årstrafik sites against assigned flows. usage: cmp_counts.py net.npz cal.csv flow..."""
import sys,csv,re,json,collections as C,numpy as np
from pyproj import Transformer
N=np.load(sys.argv[1]);A,B=N['A'],N['B'];name=N['name'];ty=N['type']
tr=Transformer.from_crs('EPSG:4326','+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',always_xy=True)
norm=lambda s:re.sub(r'[^a-z0-9åäö]','',(s or '').lower())
nm=np.array([norm(x) for x in name]);mid=(A+B)/2
from scipy.spatial import cKDTree
T=cKDTree(mid)
by=C.defaultdict(lambda:C.defaultdict(list));meta={};hv=[0,0]
for r in csv.DictReader(open(sys.argv[2],encoding='utf-8')):
    by[r['site']][r['year']].append((r['dir'],float(r['adt'])));meta[r['site']]=r;hv[0]+=float(r['heavy']);hv[1]+=float(r['adt'])
print('heavy share at calibrate sites',hv[0]/hv[1])
sites=[];fail=0
for s,ys in by.items():
    y=max(ys);rows=ys[y]
    if any(d=='Båda' for d,_ in rows): adt=np.mean([a for d,a in rows if d=='Båda'])
    else:
        c=C.defaultdict(list)
        for d,a in rows:c[d].append(a)
        adt=sum(np.mean(v) for v in c.values())
        if len(c)<2: adt=None
    if not adt or adt<500: continue
    r=meta[s];x,yy=tr.transform(float(r['lon']),float(r['lat']));x-=651972.09;yy-=6565003.78
    n0=norm(r['name'].split(' 20')[0]);idx=T.query_ball_point([x,yy],120)
    idx=[i for i in idx if nm[i] and (nm[i]==n0 or nm[i] in n0 or n0 in nm[i])]
    if not idx: fail+=1;continue
    i=np.array(idx);d=B[i]-A[i];h=np.where(np.abs(d[:,1])>=np.abs(d[:,0]),np.sign(d[:,1]),np.sign(d[:,0]))
    sites.append((s,adt,i,h,ty[i[0]]))
print('sites matched',len(sites),'name-unmatched',fail)
y=np.array([x[1] for x in sites]);res={}
for p in sys.argv[3:]:
    F=np.load(p)['F'].sum(0);m=np.array([sum(F[i[h==q]].max() if (h==q).any() else 0 for q in(-1,1)) for _,_,i,h,_ in sites])
    ok=m>0;lr=np.log(np.maximum(m,1)/y);k=float(np.exp(np.median(lr)));mk=m/k
    geh=np.sqrt(2*(mk-y)**2/(mk+y+1e-6))/np.sqrt(24)*1.0
    res[p.split('/')[-1]]=dict(n=len(y),zero_flow=int((~ok).sum()),median_ratio=round(k,3),total_ratio=round(float(m.sum()/y.sum()),3),r2_log=round(float(np.corrcoef(np.log1p(m),np.log1p(y))[0,1]**2),3),spearman=round(float(__import__('scipy.stats').stats.spearmanr(m,y)[0]),3),mape_after_k=round(float(np.median(np.abs(mk-y)/y)*100),1),within_50pct_after_k=round(float(np.mean(np.abs(mk-y)/y<.5)),3))
    print(p,res[p.split('/')[-1]],flush=True)
json.dump(res,open('out/counts_cmp.json','w'),indent=1)
