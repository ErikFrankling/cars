#!/usr/bin/env python3
# Samples real signal behaviour from Hamburg's open SensorThings API. Usage: hamburg_sample.py OUTDIR N_LIGHTS
import json,sys,time,urllib.request,urllib.parse,random,statistics as st,collections
B='https://tld.iot.hamburg.de/v1.1'
out,n=sys.argv[1],int(sys.argv[2])
def get(u):
    r=urllib.request.Request(u,headers={'User-Agent':'cars-research'})
    for a in range(4):
        try:
            with urllib.request.urlopen(r,timeout=60) as f:return json.load(f)
        except Exception as e:
            time.sleep(2+3*a);err=e
    print('fail',u,err,file=sys.stderr);return {'value':[]}
def q(path,**k):return B+path+'?'+urllib.parse.urlencode({'$'+a:b for a,b in k.items()})
ids=collections.defaultdict(list);u=q('/Datastreams',filter="properties/layerName eq 'primary_signal'",select='@iot.id,name',top=1000)
while u:
    d=get(u)
    for v in d['value']:
        t=v['name'].split(' at ')[1];ids[t.split('_')[0]].append((v['@iot.id'],t))
    u=d.get('@iot.nextLink')
print('lights',len(ids),'streams',sum(map(len,ids.values())),flush=True)
random.seed(11);pick=random.sample(sorted(ids),n)
W=[('morning','2026-10-30T06:00:00Z','2026-10-30T08:00:00Z'),('midday','2026-10-30T10:00:00Z','2026-10-30T12:00:00Z'),('evening','2026-10-30T15:00:00Z','2026-10-30T17:00:00Z'),('late','2026-10-30T21:00:00Z','2026-10-30T22:00:00Z')]
R=[]
for L in pick:
    strm=random.sample(ids[L],min(3,len(ids[L])))
    for sid,name in strm:
        for w,a,b in W:
            obs=[];u=q(f'/Datastreams({sid})/Observations',filter=f'phenomenonTime ge {a} and phenomenonTime lt {b}',select='phenomenonTime,result',orderby='phenomenonTime asc',top=1000)
            while u:
                d=get(u);obs+=[(v['phenomenonTime'],v['result']) for v in d['value']];u=d.get('@iot.nextLink')
            R.append(dict(light=L,conn=name,sid=sid,win=w,obs=obs));time.sleep(.05)
    print(L,len(R),flush=True)
json.dump(dict(lights=len(ids),streams=sum(map(len,ids.values())),rows=R),open(out+'/hamburg_raw.json','w'))
