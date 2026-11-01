"""Replacement demand. Candidate ODs with a distance kernel, routed by duarouter elsewhere, fitted to cleaned counts with the same multiplicative update as scripts/stockholm/demand.py.
 gen IDX SCALE_KM N SEED OUT.trips     write candidate ODs
 fit IDX count_matches.csv features.geojson DUA.rou.xml OUT.rou.gz OUT.json SCALE  fit, retime with retime.py's profile, write routes
"""
import os,sys,pickle,json,csv,re,gzip,random,collections
import numpy as np
def load(idx): return pickle.load(open(idx,'rb'))
def allowed(v): return v['fn'] is None and any('passenger' in (l['allow'] or 'passenger') and 'passenger' not in (l['disallow'] or '') for l in v['lanes'])
def mid(v):
    p=v['lanes'][0]['shape'].split();x,y=p[len(p)//2].split(',');return float(x),float(y)
def gen(idx,scale,n,seed,out):
    N=load(idx);E,C=N['E'],N['C'];rng=np.random.default_rng(int(seed));scale=float(scale);n=int(n)
    ids=[e for e,v in E.items() if allowed(v)]
    inc=collections.Counter()
    for e,cs in C.items():
        if not e.startswith(':'):
            for c in cs: inc[c['to']]+=1
    src=[e for e in ids if inc[e]==0 and (E[e]['type'] or '').split('.')[-1].replace('_link','') in('motorway','trunk','primary','secondary')]
    snk=[e for e in ids if not C.get(e) and (E[e]['type'] or '').split('.')[-1].replace('_link','') in('motorway','trunk','primary','secondary')]
    local=[e for e in ids if (E[e]['type'] or '').split('.')[-1] in('residential','living_street','unclassified','tertiary')]
    w=np.array([E[e]['lanes'][0]['length'] for e in local]);w=w/w.sum()
    xy=np.array([mid(E[e]) for e in local]);res=[]
    # Internal ODs accepted with exp(-d/scale): a gravity kernel on road length as the only activity proxy.
    while len(res)<n*.8:
        a=rng.choice(len(local),200000,p=w);b=rng.choice(len(local),200000,p=w)
        d=np.hypot(*(xy[a]-xy[b]).T);keep=(d>800)&(rng.random(200000)<np.exp(-d/(scale*1000)))
        res+=[(local[i],local[j]) for i,j in zip(a[keep],b[keep])]
    res=res[:int(n*.8)]
    # External portals keep their own share of candidates. The fit decides how many vehicles they get.
    k=n-len(res)
    for _ in range(k):
        t=rng.random()
        if t<.45: res.append((src[rng.integers(len(src))],local[rng.choice(len(local),p=w)]))
        elif t<.9: res.append((local[rng.choice(len(local),p=w)],snk[rng.integers(len(snk))]))
        else: res.append((src[rng.integers(len(src))],snk[rng.integers(len(snk))]))
    with open(out,'w') as f:
        f.write('<routes>\n')
        for i,(a,b) in enumerate(res): f.write(f'<trip id="p{i}" depart="0" from="{a}" to="{b}"/>\n')
        f.write('</routes>\n')
    print('pool',len(res),'sources',len(src),'sinks',len(snk))
def norm(s): return re.sub(r'[^a-z0-9åäö]','',(s or '').lower())
def clean_targets(E,matches,features):
    fs={f['id']:f['properties'] for f in json.load(open(features))['features']}
    by=collections.defaultdict(list)
    for r in csv.DictReader(open(matches)):
        e=r['edge']
        if e not in E: continue
        a,b=norm(fs[r['feature']].get('gatunamn')),norm(E[e]['name']);r['same']=bool(a and b and (a==b or a in b or b in a));by[e].append(r)
    T={};kept=collections.Counter()
    for e,rs in by.items():
        k=(E[e]['type'] or '').split('.')[-1].replace('_link','')
        same=[r for r in rs if r['same']]
        if same: use=same;kept['same_name']+=1
        elif k in('motorway','trunk','primary') and max(float(r['daily']) for r in rs)>=3000:
            top=max(float(r['daily']) for r in rs);use=[r for r in rs if float(r['daily'])>=top/2];kept['major_top']+=1
        else: kept['dropped']+=1;continue
        T[e]=[np.mean([float(r[b]) for r in use]) for b in('06_18','18_22','22_06')]
    return T,kept
BANDS=[(6,18,[.06,.11,.10,.07,.06,.065,.07,.07,.075,.095,.125,.11]),(18,22,[.45,.25,.17,.13]),(22,30,[.35,.2,.12,.07,.05,.04,.07,.1])]
def fit(idx,matches,features,dua,out,rep,scale):
    from scipy.sparse import coo_matrix
    N=load(idx);E=N['E'];scale=float(scale)
    T,kept=clean_targets(E,matches,features)
    ids=sorted(T);ix={e:i for i,e in enumerate(ids)};target=np.array([T[e] for e in ids])
    routes=[]
    for l in open(dua):
        if l.strip(): routes.append(l.split())
    # dedupe paths
    seen={};
    for r in routes: seen.setdefault(tuple(r),None)
    routes=[list(k) for k in seen]
    ln=np.array([sum(E[e]['lanes'][0]['length'] for e in r if e in E) for r in routes])
    a=[];b=[]
    for j,r in enumerate(routes):
        for e in set(r):
            if e in ix: a.append(ix[e]);b.append(j)
    A=coo_matrix((np.ones(len(a)),(a,b)),shape=(len(ids),len(routes))).tocsr()
    # Counted edges that no candidate reaches cannot constrain anything and would blow up the ratio.
    cov=np.asarray(A.sum(axis=1)).ravel()>0;ncov=int((~cov).sum());A=A[cov];target=target[cov];ids=[e for e,c in zip(ids,cov) if c]
    rng=random.Random(42);veh=[];report={}
    cl=lambda e:(E[e]['type'] or 'none').split('.')[-1].replace('_link','')
    pred_all=np.zeros(len(ids))
    for k,band in enumerate(BANDS):
        w=np.full(len(routes),max(1,target[:,k].sum()/max(A.nnz,1)));den=np.maximum(np.asarray(A.sum(axis=0)).ravel(),1)
        for _ in range(int(os.environ.get('FIT_ITER','300'))):
            w*=np.asarray(A.T@(target[:,k]/np.maximum(A@w,1e-9))).ravel()/den
        pred=A@w;pred_all+=pred;geh=np.sqrt(2*(pred-target[:,k])**2/np.maximum(pred+target[:,k],1))
        report[f'band{k}']=dict(trips=float(w.sum()),geh_lt5=float((geh<5).mean()),mean_km=float((w*ln).sum()/w.sum()/1000))
        for j,x in enumerate(w*scale):
            n=int(x)+(rng.random()<x%1)
            for _ in range(n):
                t=rng.random()
                for i,s in enumerate(band[2]):
                    t-=s
                    if t<=0: break
                veh.append((((band[0]+i+rng.random())%24)*3600,j))
    tall=target.sum(axis=1);L=np.array([E[e]['lanes'][0]['length'] for e in ids])/1000
    C=np.array([cl(e) for e in ids]);byc={}
    for c in sorted(set(C)):
        s=C==c;g=np.sqrt(2*(pred_all[s]-tall[s])**2/np.maximum(pred_all[s]+tall[s],1))
        byc[c]=dict(edges=int(s.sum()),target_vkm=float((tall[s]*L[s]).sum()),fit_vkm=float((pred_all[s]*L[s]).sum()),ratio=float((pred_all[s]*L[s]).sum()/max((tall[s]*L[s]).sum(),1)),geh_lt5=float((g<5).mean()))
    veh.sort();used=sorted({j for _,j in veh})
    lens=np.array([ln[j] for _,j in veh])
    with gzip.open(out,'wt',compresslevel=3) as f:
        f.write('<routes>\n<vType id="passenger" accel="1.5" decel="4.5" sigma="0.5" tau="1" length="5" minGap="2"/>\n')
        for j in used: f.write(f'<route id="r{j}" edges="{" ".join(routes[j])}"/>\n')
        for i,(t,j) in enumerate(veh): f.write(f'<vehicle id="s{i}" type="passenger" depart="{t:.2f}" departLane="best" departSpeed="max" route="r{j}"/>\n')
        f.write('</routes>\n')
    report.update(kept=dict(kept),edges=len(ids),uncovered=ncov,pool=len(routes),used=len(used),trips=len(veh),scale=scale,vkm=float(lens.sum()/1000),mean_km=float(lens.mean()/1000),median_km=float(np.median(lens)/1000),p95_km=float(np.quantile(lens,.95)/1000),target_passages=float(tall.sum()),by_class=byc)
    json.dump(report,open(rep,'w'),indent=1);print(json.dumps(report))
if __name__=='__main__':{'gen':gen,'fit':fit}[sys.argv[1]](*sys.argv[2:])
