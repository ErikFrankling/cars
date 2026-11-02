"""Simulated edge flows against cleaned counts, hourly tables. usage: RUN IDX [RUN IDX ...]"""
import sys,csv,json,pickle,re,collections
import numpy as np
sys.path.insert(0,'research/truth/scripts')
T='/home/erikf/projects/personal/cars-data/truth/stockholm/factorial/';D='/home/erikf/projects/personal/cars-data/stockholm/'
fs={f['id']:f['properties'] for f in json.load(open(D+'trafikflode_motorfordon.geojson'))['features']}
def norm(s): return re.sub(r'[^a-z0-9åäö]','',(s or '').lower())
M=list(csv.DictReader(open(D+'count_matches.csv')))
out={}
A=sys.argv[1:]
for run,idx in zip(A[0::2],A[1::2]):
    E=pickle.load(open(T+idx,'rb'))['E'];by=collections.defaultdict(list)
    for r in M:
        e=r['edge']
        if e not in E: continue
        a,b=norm(fs[r['feature']].get('gatunamn')),norm(E[e]['name']);r2=dict(r,same=bool(a and b and (a==b or a in b or b in a)));by[e].append(r2)
    tg={}
    for e,rs in by.items():
        k=(E[e]['type'] or '').split('.')[-1].replace('_link','');same=[r for r in rs if r['same']]
        if same: tg[e]=np.mean([float(r['daily']) for r in same])
        elif k in('motorway','trunk','primary') and max(float(r['daily']) for r in rs)>=3000:
            t=max(float(r['daily']) for r in rs);tg[e]=np.mean([float(r['daily']) for r in rs if float(r['daily'])>=t/2])
    fl=collections.Counter();sd=collections.Counter();ss=collections.Counter();tp=collections.Counter();H=collections.defaultdict(lambda:[0,0,0])
    for r in csv.DictReader(open(T+run+'/edges.csv')):
        fl[r['edge']]+=float(r['entered']);b=int(float(r['begin'])//3600);H[b][0]+=float(r['distance']);H[b][1]+=float(r['samples']);H[b][2]+=int(r['teleports']);tp[r['edge']]+=int(r['teleports'])
    es=[e for e in tg];t=np.array([tg[e] for e in es]);m=np.array([fl[e] for e in es]);L=np.array([E[e]['lanes'][0]['length'] for e in es])/1000
    g=np.sqrt(2*(m-t)**2/np.maximum(m+t,1));cl=np.array([(E[e]['type'] or '').split('.')[-1].replace('_link','') for e in es])
    res=dict(edges=len(es),geh_lt5=float((g<5).mean()),slope=float((t*m).sum()/(t*t).sum()),r2=float(np.corrcoef(t,m)[0,1]**2),vkm_ratio=float((m*L).sum()/(t*L).sum()),by_class={k:dict(n=int((cl==k).sum()),geh_lt5=float((g[cl==k]<5).mean()),vkm_ratio=float((m[cl==k]*L[cl==k]).sum()/max((t[cl==k]*L[cl==k]).sum(),1))) for k in sorted(set(cl))},hourly_speed_kmh={str(h):round(v[0]/max(v[1],1)*3.6,1) for h,v in sorted(H.items())},hourly_teleports={str(h):v[2] for h,v in sorted(H.items())},vkm=sum(v[0] for v in H.values())/1000)
    out[run]=res;print(run,json.dumps({k:v for k,v in res.items() if k not in('hourly_speed_kmh','hourly_teleports','by_class')}));print(' class',{k:(v['geh_lt5'],round(v['vkm_ratio'],2)) for k,v in res['by_class'].items()});print(' speed',res['hourly_speed_kmh']);print(' tp',res['hourly_teleports'],flush=True)
json.dump(out,open('research/truth/stockholm-final.json','w'),indent=1,ensure_ascii=False)
