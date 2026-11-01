"""Independent census of the claims in 02/07. Streams files, no GPU."""
import gzip,json,re,sys,collections,xml.etree.ElementTree as ET
from pathlib import Path
D=Path('/home/erikf/projects/personal/cars-data/stockholm')
out={}
def rou(path):
    routes={};veh=collections.Counter();hour=collections.Counter();n=0
    with gzip.open(path,'rt') as f:
        for line in f:
            if line.startswith('<route '):
                m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',line); routes[m[1]]=m[2].split()
            elif line.startswith('<vehicle'):
                m=re.search(r'depart="([\d.]+)".*route="([^"]+)"',line); veh[m[2]]+=1; hour[int(float(m[1])//3600)]+=1; n+=1
    return routes,veh,hour,n
def rev(e): return e[1:] if e.startswith('-') else '-'+e
for name in ['stockholm.rou.gz','stockholm60.rou.gz','stockholm45.rou.gz']:
    routes,veh,hour,n=rou(D/name)
    u=[r for r,e in routes.items() if any(rev(a)==b for a,b in zip(e,e[1:]))]
    uv=sum(veh[r] for r in u)
    nu=collections.Counter(sum(rev(a)==b for a,b in zip(e,e[1:])) for e in routes.values())
    uturns_total=sum(veh[r]*sum(rev(a)==b for a,b in zip(e,e[1:])) for r,e in routes.items())
    out[name]=dict(vehicles=n,routes=len(routes),routes_used=len(veh),routes_with_uturn=len(u),route_share=len(u)/len(routes),veh_with_uturn=uv,veh_share=uv/n,uturn_events=uturns_total,uturns_per_route_hist={str(k):v for k,v in sorted(nu.items())[:8]},hourly=[hour[h] for h in range(24)])
    print(name,{k:v for k,v in out[name].items() if k!='hourly'},flush=True)
gj=json.load(open(D/'trafikflode_motorfordon.geojson'))
fs=gj['features']; p0=fs[0]['properties']
print('feature keys',list(p0))
m=collections.Counter(f['properties'].get('metod_för_datainsamling') for f in fs)
y=collections.Counter(str(f['properties'].get('uppdaterad'))[:4] for f in fs)
out['counts']=dict(features=len(fs),method=dict(m),year=dict(y),year2016_share=y['2016']/len(fs))
print(out['counts'])
print('sample',json.dumps(p0,ensure_ascii=False)[:800])
tl=collections.Counter();off=collections.Counter();typ=collections.Counter();progs=0;cyc=collections.Counter();mins=collections.Counter()
cur=None
for _,el in ET.iterparse(D/'stockholm.net.xml',events=['end']):
    if el.tag=='tlLogic':
        progs+=1;typ[el.get('type')]+=1;off[el.get('offset')]+=1
        d=sum(float(p.get('duration')) for p in el.findall('phase')); cyc[round(d)]+=1
        mins[round(sum(float(p.get('minDur',p.get('duration'))) for p in el.findall('phase')))]+=1
    if el.tag in('edge','junction','connection','tlLogic'): el.clear()
out['tls']=dict(programs=progs,type=dict(typ),offset=dict(off),cycle=dict(cyc),sum_minDur=dict(mins))
print(out['tls'])
Path('research/truth/stockholm-recheck.json').write_text(json.dumps(out,indent=1,ensure_ascii=False))
