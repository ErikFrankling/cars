# Lane-level legal rules vs a net extract: bus lanes per direction, lane-position lower bounds, turn rules.
# usage: lane_rules.py net.json ltfr_rules.geojson nvdb_turnban.geojson osm.json out_prefix
import sys,json,re,csv,math,collections
import pyproj
from shapely.geometry import LineString,Point
from shapely.strtree import STRtree
netf,rulef,banf,osmf,out=sys.argv[1:6]
N=json.load(open(netf));E=N['E'];off=N['off'];C=N['C']
tf=pyproj.Transformer.from_crs('EPSG:3011','+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',always_xy=True)
car=lambda l:(not l['allow'] or 'passenger' in l['allow'].split()) and 'passenger' not in (l['dis'] or '').split()
bus=lambda l:bool(l['allow']) and 'bus' in l['allow'].split() and 'passenger' not in l['allow'].split()
geoms=[];ids=[]
for k,e in E.items():
    m=e['lanes'][len(e['lanes'])//2]
    pts=[tuple(map(float,p.split(',')[:2])) for p in m['shape'].split()]
    if len(pts)>=2: geoms.append(LineString(pts));ids.append(k)
tree=STRtree(geoms);gi=dict(zip(ids,geoms))
def bearing(a,b): return math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
def lb(g,s):
    a=g.interpolate(max(0,s-2));b=g.interpolate(min(g.length,s+2));return bearing((a.x,a.y),(b.x,b.y))
ad=lambda a,b:abs((a-b+180)%360-180)
def body(t):
    t=(t or '').replace('\r\n',' ');t=re.split(r'följande\.\s*',t,maxsplit=1)[-1]
    return re.split(r'Dessa föreskrifter|Denna författning|Denna föreskrift|På trafik|Paragrafen',t)[0].strip()
def toline(co):
    x,y=tf.transform([q[0] for q in co],[q[1] for q in co]);return LineString([(a+off[0],b+off[1]) for a,b in zip(x,y)])
SIDE={'norra':270,'södra':90,'östra':0,'västra':180,'nordöstra':315,'nordvästra':225,'sydöstra':45,'sydvästra':135}
COMP={'nordvästlig':315,'nordöstlig':45,'sydvästlig':225,'sydöstlig':135,'nordlig':0,'sydlig':180,'östlig':90,'västlig':270}
rows=[];S=collections.Counter();km=collections.Counter()
D=json.load(open(rulef,encoding='utf-8'))
for f in D['features']:
    p=f['properties'];t=p.get('TITLE') or ''
    if not re.search(r'om (körfält|påbjudet körfält|påbjuden körbana)',t) or not f['geometry']: continue
    b=body(p.get('FORESKRIFTSTEXT'))
    g=toline(f['geometry']['coordinates'])
    if g.length<3: continue
    if not tree.query(g.interpolate(0.5,normalized=True).buffer(300)).size: continue
    m=re.search(r'(nordöstra|nordvästra|sydöstra|sydvästra|norra|södra|östra|västra) körban',b)
    m2=re.search(r'(nordvästlig|nordöstlig|sydvästlig|sydöstlig|nordlig|sydlig|östlig|västlig) färdrikt',b)
    want=COMP[m2.group(1)] if m2 else (SIDE[m.group(1)] if m else None)
    pos='right' if re.search('höger körfält|högra körfält',b) else 'mid' if re.search('mittkörfält|mittre',b) else 'left' if re.search('vänster körfält|vänstra körfält',b) else 'cway' if re.search(r'körbana (för|ska)|skall vara körbana|ska vara körbana|körbanan? på',b) else 'lane'
    n=max(3,int(g.length//15));hit=collections.Counter()
    R=7 if pos=='cway' else 15
    for i in range(n):
        s=g.length*(i+.5)/n;pt=g.interpolate(s);br=lb(g,s)
        for j in tree.query(pt.buffer(R)):
            ge=geoms[j]
            if ge.distance(pt)>R: continue
            be=lb(ge,ge.project(pt))
            if ad(be,br)>=35 and ad(be,br+180)>=35: continue
            if want is not None and ad(be,want)>=80: continue
            if any(car(l) or bus(l) for l in E[ids[j]]['lanes']): hit[ids[j]]+=1
    use=[k for k,v in hit.items() if v>=max(1,0.25*n)] or list(hit)[:3]
    if not use: res='no_edge';nc=nb=0
    else:
        nb=max(sum(bus(l) for l in E[k]['lanes']) for k in use)
        nc=min(sum(car(l) for l in E[k]['lanes']) for k in use)
        res='honoured' if nb>0 else ('closed_no_car' if nc==0 else 'open')
    lower=None
    if pos=='mid':lower=3
    elif pos in('right','left'):lower=2
    tot=max((len([l for l in E[k]['lanes'] if car(l) or bus(l)]) for k in use),default=0)
    short=int(lower is not None and bool(use) and tot<lower)
    S[(pos,res)]+=1;km[res]+=g.length/1000;S[('lower_bound_checked',int(lower is not None and bool(use)))]+=1;S[('lane_short',short)]+=1
    rows.append(dict(citation=p['CITATION'],loc=p['LOCATION_APPROX'],pos=pos,want=want,res=res,len=round(g.length),car=nc,bus=nb,tot=tot,lower=lower,short=short,edges=';'.join(use)[:120],vf=(p.get('VALID_FROM') or '')[:10],text=b[:220]))
w=csv.DictWriter(open(out+'_bus.csv','w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for k,v in sorted(S.items(),key=str): print(k,v)
print({k:round(v,1) for k,v in km.items()})
# movement test helpers
mv=collections.defaultdict(lambda:collections.defaultdict(set))
for fr,to,fl,tl,dr,st,tl_ in C: mv[fr][to].add(dr)
# NVDB forbidden turns: polyline p0..pn crossing a junction; find a net movement
B=json.load(open(banf));res=collections.Counter();ban_rows=[]
for f in B['features']:
    co=f['geometry']['coordinates'];g=toline(co)
    if not tree.query(g.interpolate(.5,normalized=True).buffer(100)).size: continue
    pts=list(g.coords);a=pts[0];z=pts[-1]
    if g.length<0.5: continue
    # approach = edges ending near the polyline, heading along the first leg; exit = edges starting near, heading along the last leg
    b0=bearing(pts[0],pts[1]);b1=bearing(pts[-2],pts[-1])
    mid=g.interpolate(.5,normalized=True)
    fr=[]
    for j in tree.query(mid.buffer(45)):
        k=ids[j];ge=geoms[j];end=Point(ge.coords[-1])
        if end.distance(mid)<45 and ad(lb(ge,ge.length-1),b0)<50 and any(car(l) for l in E[k]['lanes']): fr.append((end.distance(mid),k))
    found=None
    for d,k in sorted(fr):
        for to,dirs in mv[k].items():
            if to in gi and to in E and any(car(l) for l in E[to]['lanes']):
                ge=gi[to];st=Point(ge.coords[0])
                if st.distance(mid)<60 and ad(lb(ge,1),b1)<50:
                    found=(k,to,''.join(sorted(dirs)));break
        if found:break
    S2='open_in_net' if found else ('approach_only' if fr else 'no_approach')
    res[S2]+=1
    x,y=mid.x,mid.y
    ban_rows.append(dict(oid=f['properties']['OBJECT_ID'],res=S2,x=round(x,1),y=round(y,1),frm=found[0] if found else '',to=found[1] if found else '',dirs=found[2] if found else '',vf=f['properties'].get('VALID_FROM')))
print('NVDB turn bans',dict(res))
w=csv.DictWriter(open(out+'_turnban.csv','w',newline=''),fieldnames=list(ban_rows[0]));w.writeheader();w.writerows(ban_rows)
