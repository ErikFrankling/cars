# For chosen measured sites: fetches a 0.16 m crop from Lantmäteriet's public viewing WMS (small sample) and per-photo capture time.
import json,sys,os,time,math,urllib.request,datetime as dt
from zoneinfo import ZoneInfo
from pyproj import Transformer
from shapely.geometry import shape,Point,LineString
base=sys.argv[1]
rows=json.load(open(base+'/caps/central_sites.json'))
T=Transformer.from_crs(4326,3006,always_xy=True)
WANT=[("TS 08",2025,"Med","essingeleden_kristineberg"),("TS 08",2025,"Mot","essingeleden_kristineberg_mot"),("TS 04",2025,"Mot","johanneshovsbron"),("TS 03",2025,None,"skanstullsbron"),("TS 10",2025,None,"klarastrandsleden"),("0115X001",2025,None,"sveavagen"),("03090203",2025,None,"hornsgatan"),("06230103",2025,"Mot","drottningholmsvagen"),("03160897",2025,None,"stadsgardsleden")]
SP=ZoneInfo('Europe/Stockholm');UA={'User-Agent':'Mozilla/5.0'}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60) as f: return f.read()
fl={}
def photo(E,N):
    te=int(E//2500*2500);tn=int(N//2500*2500)
    name=f"o{tn//100}_{te//100}_25_mr25"
    if name not in fl:
        u=f"https://dl1.lantmateriet.se/bild/pub/orto/se0_16m_sweref/2025_O2/{name}_flygbild.json"
        try: fl[name]=json.loads(get(u))['features']
        except Exception as e: print('no',name,e);fl[name]=[]
    for f in fl[name]:
        if shape(f['geometry']).contains(Point(E,N)): return f['properties']
out=[]
os.makedirs(base+'/tiles',exist_ok=True)
for site,yr,d,slug in WANT:
    c=[r for r in rows if r['site']==site and r['year']==yr and (d is None or r['dir']==d)]
    c.sort(key=lambda r:(r['split']=='true',-r['adt']))
    if not c: print('none',site);continue
    r=c[0]
    L=sum(LineString([T.transform(x,y) for x,y,*_ in l]).length for l in r['geom'])
    E,N=T.transform(r['lon'],r['lat'])
    S=2048;W=S*.16
    u=("https://minkarta.lantmateriet.se/map/ortofoto/wms/v1.3?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image/jpeg&LAYERS=Ortofoto_0.16&STYLES=&CRS=EPSG:3006"
       f"&WIDTH={S}&HEIGHT={S}&BBOX={N-W/2},{E-W/2},{N+W/2},{E+W/2}")
    p=f"{base}/tiles/{slug}.jpg"
    if not os.path.exists(p): open(p,'wb').write(get(u));time.sleep(1)
    ph=photo(E,N)
    t=dt.datetime.fromisoformat(ph['tidpunkt'].replace('Z','+00:00')).astimezone(SP) if ph else None
    rec=dict(slug=slug,site=site,year=yr,dir=r['dir'],split=r['split'],name=r['name'],days=r['days'],adt=r['adt'],h=r['h'],heavy=r['heavy'],v_mean=r['v_mean'],v_p85=r['v_p85'],E=E,N=N,geom_len_m=round(L),S=S,gsd=.16,photo=ph and ph['bildidentitet'],time_local=t and t.isoformat())
    out.append(rec);print(slug,r['name'][:60],'days',r['days'],'adt',r['adt'],'L',round(L),'time',t,'h9,10',r['h'][9],r['h'][10],'v',r['v_mean'],os.path.getsize(p)//1024,'KB')
json.dump(out,open(base+'/caps/sites_selected.json','w'),ensure_ascii=False,indent=0)
