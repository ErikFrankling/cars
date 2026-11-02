# Compare Stockholm's legal traffic rules (LTFR, WFS) with a net extract.
# usage: rules_vs_net.py net.json ltfr_rules.geojson out.csv
import sys,json,re,csv,math,collections
import numpy as np, pyproj
from shapely.geometry import LineString,Point
from shapely.strtree import STRtree
netf,rulef,outf=sys.argv[1:4]
N=json.load(open(netf));E=N['E'];off=N['off']
tf=pyproj.Transformer.from_crs('EPSG:3011','+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',always_xy=True)
def car(l): return (not l['allow'] or 'passenger' in l['allow']) and 'passenger' not in (l['dis'] or '').split()
def busonly(l): return l['allow'] and 'bus' in l['allow'].split() and 'passenger' not in l['allow'].split()
geoms=[];ids=[]
for k,e in E.items():
    L=e['lanes'];m=L[len(L)//2]
    pts=[tuple(map(float,p.split(',')[:2])) for p in m['shape'].split()]
    if len(pts)<2: continue
    geoms.append(LineString(pts));ids.append(k)
tree=STRtree(geoms)
def bearing(a,b): return math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
def line_bearing(g,s):
    a=g.interpolate(max(0,s-2));b=g.interpolate(min(g.length,s+2));return bearing((a.x,a.y),(b.x,b.y))
def adiff(a,b): return abs((a-b+180)%360-180)
COMP={'nordvästlig':315,'nordöstlig':45,'sydvästlig':225,'sydöstlig':135,'nordlig':0,'sydlig':180,'östlig':90,'västlig':270,
 'norrut':0,'söderut':180,'österut':90,'västerut':270,'norrgående':0,'södergående':180,'östgående':90,'västgående':270}
RX=re.compile('|'.join(sorted(COMP,key=len,reverse=True)))
def body(t):
    t=(t or '').replace('\r\n',' ')
    t=re.split(r'följande\.\s*',t,maxsplit=1)[-1]
    return re.split(r'Dessa föreskrifter|Denna författning|Denna föreskrift|På trafik|Paragrafen',t)[0].strip()
def kind(title):
    m=re.search(r'föreskrifter om (.*?) (på|i|vid|inom|för|mellan|längs)\b',title or '')
    return (m.group(1) if m else (title or '')[:50]).strip()
def cat(k,b):
    if 'enkelriktad' in k: return 'oneway'
    if k.startswith(('körfält','påbjudet körfält','påbjuden körbana')): return 'bus'
    if k=='gågata': return 'pedestrian'
    if k.startswith('förbud mot U-sväng'): return 'uturn'
    if k.startswith('förbud mot sväng'): return 'turn'
    if k.startswith('påbjuden körriktning'): return 'mandatory'
    if k.startswith('förbud mot infart'): return 'noentry'
    if k.startswith('förbud mot trafik') and re.search('fordon',k) and not re.search('dubbdäck|lastbil|cykel',k):
        return 'ban'
    return None
D=json.load(open(rulef,encoding='utf-8'))
rows=[];S=collections.Counter()
def norm(s): return re.sub(r'[^a-zåäö]','',(s or '').lower().replace('sankt','st').replace('s:t','st'))
for f in D['features']:
    p=f['properties'];b=body(p.get('FORESKRIFTSTEXT'));k=kind(p.get('TITLE'));c=cat(k,b)
    if not c or not f['geometry']: continue
    co=f['geometry']['coordinates']
    x,y=tf.transform([q[0] for q in co],[q[1] for q in co])
    pts=[(a+off[0],bb+off[1]) for a,bb in zip(x,y)]
    if len(pts)<2: continue
    g=LineString(pts)
    if g.length<2: continue
    x0,y0=g.interpolate(0.5,normalized=True).coords[0]
    # outside the extract's bbox?
    env=[geoms[i] for i in tree.query(Point(x0,y0).buffer(300))]
    if not env: continue
    n=max(3,int(g.length//15))
    ss=[g.length*(i+0.5)/n for i in range(n)]
    same=collections.Counter();opp=collections.Counter();cnt=0
    R=15 if c!='pedestrian' else 8
    for s in ss:
        pt=g.interpolate(s);br=line_bearing(g,s);cnt+=1
        fs=set();os_=set()
        for i in tree.query(pt.buffer(R)):
            ge=geoms[i]
            if ge.distance(pt)>R: continue
            d=ge.project(pt);be=line_bearing(ge,d)
            if adiff(be,br)<35: fs.add(ids[i])
            elif adiff(be,br+180)<35: os_.add(ids[i])
        for i in fs: same[i]+=1
        for i in os_: opp[i]+=1
    def carE(ct): return {i for i in ct if any(car(l) for l in E[i]['lanes'])}
    fw=carE(same);bw=carE(opp)
    def cov(ct,S_):
        return sum(ct[i] for i in S_)/max(1,cnt)
    cf,cb=cov(same,fw),cov(opp,bw)
    hf,hb=cf>=0.5,cb>=0.5
    comps=[COMP[m] for m in RX.findall(b)]
    legal=None
    if comps:
        lb=bearing(pts[0],pts[-1])
        ds=[math.cos(math.radians(a-lb)) for a in comps]
        best=max(ds,key=abs)
        if abs(best)>=0.35: legal=1 if best>0 else -1
    names={E[i].get('name') for i in list(fw)+list(bw)}
    loc=p.get('LOCATION_APPROX') or ''
    nameok=any(norm(n) and (norm(n) in norm(loc) or norm(loc) in norm(n) or norm(n) in norm(b)) for n in names)
    res=''
    if c=='oneway':
        if not hf and not hb: res='no_car_edge'
        elif hf and hb: res='net_two_way'
        else:
            only=1 if hf else -1
            res='ok_no_dir' if legal is None else ('ok' if only==legal else 'net_opposite')
    elif c=='bus':
        allb=[i for i in list(same)+list(opp) if any(busonly(l) for l in E[i]['lanes'])]
        res='no_car_edge' if not hf and not hb else ('honoured' if allb else 'open_to_cars')
        if allb and not (hf or hb): res='honoured'
    elif c in('pedestrian','ban'):
        if legal is not None and c=='ban':
            banned=hf if legal==1 else hb
            res='open_dir' if banned else 'closed_dir'
        else:
            res='open' if (hf or hb) else 'closed'
        if c=='ban':
            res+=('_through' if 'genomfart' in b else '')+('_timed' if re.search('klockan',b) else '')+('_except' if re.search('gäller inte',b) else '')
    else: res='manual'
    S[(c,res)]+=1
    rows.append(dict(cat=c,res=res,citation=p.get('CITATION'),loc=loc,name_match=int(nameok),len_m=round(g.length,1),x=round(x0,1),y=round(y0,1),
      fw=';'.join(sorted(fw))[:150],bw=';'.join(sorted(bw))[:150],valid_from=(p.get('VALID_FROM') or '')[:10],url=p.get('RDT_URL'),text=b[:300]))
w=csv.DictWriter(open(outf,'w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for k,v in sorted(S.items()): print(k,v)
