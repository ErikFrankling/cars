"""Fitted route loading against the count targets, by road class. usage: IDX count_matches.csv ROUTES..."""
import sys,pickle,gzip,re,csv,collections,json
import numpy as np
N=pickle.load(open(sys.argv[1],'rb'));E=N['E']
rows=collections.defaultdict(list)
for r in csv.DictReader(open(sys.argv[2])): rows[r['edge']].append(r)
tg={e:np.mean([float(r['daily']) for r in rs]) for e,rs in rows.items()}
tg0618={e:np.mean([float(r['06_18']) for r in rs]) for e,rs in rows.items()}
cl=lambda e:(E[e]['type'] or 'none').split('.')[-1].replace('_link','')
out={}
rx=re.compile(r'route="([^"]+)"')
for path in sys.argv[3:]:
    R={};c=collections.Counter()
    with gzip.open(path,'rt') as f:
        for l in f:
            if l.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',l);R[m[1]]=m[2].split()
            elif l.startswith('<vehicle'): c[rx.search(l)[1]]+=1
    fl=collections.Counter()
    vkm=collections.Counter();trips=0;km=[]
    for k,n in c.items():
        trips+=n
        for e in R[k]:
            fl[e]+=n
            if e in E: vkm[cl(e)]+=n*E[e]['lanes'][0]['length']/1000
    tab={}
    for k in sorted({cl(e) for e in tg}):
        es=[e for e in tg if e in E and cl(e)==k]
        t=np.array([tg[e] for e in es]);m=np.array([fl[e] for e in es]);gl=np.array([E[e]['lanes'][0]['length'] for e in es])/1000
        geh=np.sqrt(2*(m-t)**2/np.maximum(m+t,1))
        tab[k]=dict(edges=len(es),target_vkm=float((t*gl).sum()),fitted_vkm=float((m*gl).sum()),ratio=float((m*gl).sum()/max((t*gl).sum(),1)),median_target=float(np.median(t)),geh_lt5=float((geh<5).mean()),net_vkm=vkm[k])
    tot=sum(vkm.values());out[path.rsplit('/',1)[1]]=dict(trips=trips,vkm=tot,classes=tab,vkm_share={k:v/tot for k,v in vkm.most_common()})
    print(path.rsplit('/',1)[1],'trips',trips,'vkm',round(tot))
    for k,v in sorted(tab.items(),key=lambda x:-x[1]['target_vkm']):
        print(f"  {k:14s} edges {v['edges']:6d} target_vkm {v['target_vkm']:10.0f} fitted {v['fitted_vkm']:10.0f} ratio {v['ratio']:.2f} geh<5 {v['geh_lt5']:.2f} share_of_all_vkm {out[path.rsplit('/',1)[1]]['vkm_share'].get(k,0):.3f}")
    for e in ['205889184','300183415']:
        print('  ess',e,E[e]['name'],len(E[e]['lanes']),'target day',tg.get(e),'06-18',tg0618.get(e),'fitted',fl[e],[(r['feature'],r['directions'],r['daily']) for r in rows.get(e,[])][:3])
json.dump(out,open('research/truth/stockholm-classfit.json','w'),indent=1)
