"""Recheck of the capacity screen, then a peak-hour, signal-aware version. usage: IDX ROUTES..."""
import sys,pickle,gzip,re,collections,json
import numpy as np
N=pickle.load(open(sys.argv[1],'rb'));E,C,T=N['E'],N['C'],N['T']
def allowed(l): return 'passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '')
ids=[e for e,v in E.items() if v['fn'] is None and any(allowed(l) for l in v['lanes'])]
lanes={e:sum(allowed(l) for l in E[e]['lanes']) for e in ids}
vmax={e:max(l['speed'] for l in E[e]['lanes'] if allowed(l)) for e in ids}
opt={e:lanes[e]*min(2400,3600/(1+7/vmax[e])) for e in ids}
gs={}
for e in ids:
    cs=C.get(e,[]);by=collections.defaultdict(float)
    for c in cs:
        if c['tl']:
            ph=T[c['tl']]['phases'];i=int(c['linkIndex']);cyc=sum(p[0] for p in ph)
            # protected and permissive green at nominal durations.
            by[int(c['fromLane'])]=max(by[int(c['fromLane'])],sum(p[0] for p in ph if p[1][i] in 'Gg')/cyc)
        else: by[int(c['fromLane'])]=1.0
    gs[e]=sum(by.values())
sig={e:1800*gs[e] for e in ids}
rx=re.compile(r'depart="([\d.]+)".*route="([^"]+)"');out={}
for path in sys.argv[2:]:
    R={};H=collections.defaultdict(collections.Counter)
    with gzip.open(path,'rt') as f:
        for l in f:
            if l.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',l);R[m[1]]=m[2].split()
            elif l.startswith('<vehicle'):
                m=rx.search(l);H[m[2]][int(float(m[1])//3600)]+=1
    fl=np.zeros((len(ids),24));ix={e:i for i,e in enumerate(ids)}
    for r,c in H.items():
        s=[ix[e] for e in R[r] if e in ix]
        for h,n in c.items(): fl[s,h]+=n
    a=np.array([opt[e] for e in ids]);b=np.array([max(sig[e],1) for e in ids]);L=np.array([E[e]['lanes'][0]['length'] for e in ids])
    avg=fl[:,6:18].sum(axis=1)/12
    peak=fl.sum(axis=0).argmax();pk=fl[:,peak]
    res=dict(screen_max_ratio=float((avg/a).max()),edge=ids[int((avg/a).argmax())],screen_over=int((avg>a).sum()),peak_hour=int(peak),peak_over_opt=int((pk>a).sum()),peak_over_sig=int((pk>b).sum()),peak_over_sig_km=float(L[pk>b].sum()/1000),peak_ratio_sig_q99=float(np.quantile(pk/b,.99)),over_sig_by_hour=[int((fl[:,h]>b).sum()) for h in range(24)])
    cl=collections.Counter((E[ids[i]]['type'] or '').split('.')[-1].replace('_link','') for i in np.where(pk>b)[0]);res['peak_over_sig_by_class']=dict(cl)
    out[path.rsplit('/',1)[1]]=res;print(path.rsplit('/',1)[1],json.dumps(res),flush=True)
json.dump(out,open('research/truth/stockholm-capscreen.json','w'),indent=1)
