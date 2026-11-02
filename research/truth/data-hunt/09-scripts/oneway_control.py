import csv,json,random,time,urllib.request,pyproj,collections,re
N=json.load(open('v5.json'));off=N['off']
to=pyproj.Transformer.from_crs('+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs','EPSG:3006',always_xy=True)
R=list(csv.DictReader(open('rules_v5.csv')))
def q(r,hw=25):
    x,y=to.transform(float(r['x'])-off[0],float(r['y'])-off[1])
    u=f"https://geo-netinfo.trafikverket.se/mapservice/wms.axd/NetInfo?service=WMS&version=1.1.1&request=GetFeatureInfo&layers=ForbjudenFardriktning&query_layers=ForbjudenFardriktning&styles=&srs=EPSG:3006&bbox={x-hw},{y-hw},{x+hw},{y+hw}&width=101&height=101&x=50&y=50&info_format=application/json&feature_count=5"
    try: F=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'r'}),timeout=40)).get('features',[])
    except Exception as e: return None
    return sorted({f['properties'].get('Beteckning','') for f in F})
ok=[r for r in R if r['cat']=='oneway' and r['res']=='ok' and float(r['len_m'])>30]
random.seed(4);S=random.sample(ok,30)
c=collections.Counter()
for r in S:
    b=q(r);c['hit']+=bool(b);c['n']+=1;time.sleep(.2)
    print('OK',r['citation'][5:],r['loc'][:20],'L',r['len_m'],b)
print(dict(c))
# conflicts on longer plain streets, wider query
A=list(csv.DictReader(open('oneway_adjudicated.csv')))
seen=set()
for a in A:
    if a['kind']!='street' or float(a['len'])<20 or a['citation'] in seen: continue
    seen.add(a['citation'])
    r=[x for x in R if x['citation']==a['citation'] and x['cat']=='oneway' and x['len_m']==a['len']][0]
    b=q(r);time.sleep(.2)
    u=f"https://rdt.transportstyrelsen.se/rdt/AF06_View.aspx?BeslutsMyndighetKod=0180&BeslutadAr={a['citation'][5:9]}&LopNr={a['citation'][10:]}"
    try:
        t=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read().decode('utf-8','replace')
        tx=re.sub(r'<[^>]+>',' ',t);st=re.findall(r'(Upphäv[a-zåäö]*[^\n]{0,60}|Gällande[^\n]{0,30}|Beslutad[^\n]{0,20})',tx)
        up=[s.strip()[:60] for s in st if 'Gör upphävd' not in s and 'Godkänna' not in s][:3]
    except Exception as e: up=['err']
    print('CONFLICT',a['citation'][5:],a['loc'][:20],'L',a['len'],'nvdb',b,'|',a['osm'][:40],'| rdt',up)
    time.sleep(.3)
