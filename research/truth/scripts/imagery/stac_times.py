# Lists all Lantmäteriet orthophoto capture windows over Stockholm: date, weekday, local time, resolution, tile counts.
import json,sys,urllib.request,datetime as dt
from zoneinfo import ZoneInfo
B="https://api.lantmateriet.se/stac-bild/v1/search"
def get(url,body=None):
    r=urllib.request.Request(url,data=json.dumps(body).encode() if body else None,headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=60))
out=[];url=None
body={"bbox":[17.90,59.25,18.20,59.42],"limit":500}
d=get(B,body)
out+=d['features']
while True:
    nx=[l for l in d.get('links',[]) if l['rel']=='next']
    if not nx or len(out)>12000: break
    l=nx[0]
    d=get(l['href'],l.get('body')) if l.get('method','GET')=='POST' else get(l['href'])
    out+=d['features']
print(len(out),'items')
json.dump(out,open(sys.argv[1],'w'))
S=ZoneInfo('Europe/Stockholm')
from collections import defaultdict
g=defaultdict(list)
for f in out:
    p=f['properties']
    s=p.get('start_datetime') or p.get('datetime');e=p.get('end_datetime') or s
    if not s: continue
    g[(f['collection'],p.get('upplosning'),p.get('spektraltyp'))].append((s,e,f['assets']['data'].get('file:size') or 0))
for k in sorted(g,key=lambda k:k[0]):
    v=g[k]
    days=sorted({x[0][:10] for x in v})
    def loc(t): return dt.datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(S)
    ts=[loc(x[0]) for x in v]+[loc(x[1]) for x in v]
    wd=sorted({dt.date.fromisoformat(d).strftime('%a') for d in days})
    print(k[0],k[1],k[2],'tiles',len(v),'days',len(days),days[0],days[-1],wd,'localtime %s-%s'%(min(t.strftime('%H:%M') for t in ts),max(t.strftime('%H:%M') for t in ts)),'GB %.1f'%(sum(x[2] for x in v)/1e9))
