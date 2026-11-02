# Merge every source for the 100 sections. usage: compare_sections.py scratchdir layersdir out.csv
import sys,json,re,csv,math,collections,gzip
import pyproj
from shapely.geometry import LineString,Point
from shapely import wkt as W
from shapely.strtree import STRtree
csv.field_size_limit(10**8)
D,LY,out=sys.argv[1:4]
v5=json.load(open(D+'/v5.json'));n7=json.load(open(D+'/n7.json'));O=json.load(open(D+'/osm.json'))['ways'];off=v5['off']
utm='+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
t3011=pyproj.Transformer.from_crs('EPSG:3011',utm,always_xy=True);tll=pyproj.Transformer.from_crs('EPSG:4326',utm,always_xy=True)
car=lambda l:(not l['allow'] or 'passenger' in l['allow'].split()) and 'passenger' not in (l['dis'] or '').split()
bus=lambda l:bool(l['allow']) and 'bus' in l['allow'].split() and 'passenger' not in l['allow'].split()
def bear(a,b): return math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
def lb(g,s):
    a=g.interpolate(max(0,s-2));b=g.interpolate(min(g.length,s+2));return bear((a.x,a.y),(b.x,b.y))
ad=lambda a,b:abs((a-b+180)%360-180)
def nettree(N):
    G=[];I=[]
    for k,e in N['E'].items():
        m=e['lanes'][len(e['lanes'])//2];p=[tuple(map(float,q.split(',')[:2])) for q in m['shape'].split()]
        if len(p)>=2:G.append(LineString(p));I.append(k)
    return STRtree(G),G,I
def layer(name,tf=None,offs=None):
    F=json.load(open(f'{LY}/{name}.geojson',encoding='utf-8'))['features'];G=[];P=[]
    for f in F:
        if not f['geometry']:continue
        co=f['geometry']['coordinates']
        if f['geometry']['type']!='LineString':continue
        x,y=t3011.transform([q[0] for q in co],[q[1] for q in co])
        G.append(LineString(zip(x,y)));P.append(f['properties'])
    return STRtree(G),G,P
def near(T,pt,br,R,want=None):
    tr,G,P=T;o=[]
    for i in tr.query(pt.buffer(R)):
        g=G[i]
        if g.distance(pt)>R:continue
        be=lb(g,g.project(pt))
        if ad(be,br)<35:o.append((g.distance(pt),P[i],1))
        elif ad(be,br+180)<35:o.append((g.distance(pt),P[i],-1))
    return sorted(o,key=lambda x:x[0])
width=layer('nvdb_width');speed=layer('nvdb_speed');bust=layer('nvdb_bus')
# LTFR
LF=json.load(open(f'{LY}/ltfr_rules.geojson',encoding='utf-8'))['features'];G=[];P=[]
for f in LF:
    co=f['geometry']['coordinates'];x,y=t3011.transform([q[0] for q in co],[q[1] for q in co]);G.append(LineString(zip(x,y)));P.append(f['properties'])
ltfr=(STRtree(G),G,P)
# Overture
OG=[];OP=[]
with open(D+'/overture.csv',encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        g=W.loads(r['wkt']);x,y=tll.transform(*zip(*g.coords));OG.append(LineString(zip(x,y)));OP.append(r)
ov=(STRtree(OG),OG,OP)
def lanes_at(N,T,pt,br):
    tr,G,I=T;f=[];b=[]
    for i in tr.query(pt.buffer(12)):
        g=G[i]
        if g.distance(pt)>12:continue
        be=lb(g,g.project(pt))
        if ad(be,br)<30:f.append((g.distance(pt),I[i]))
        elif ad(be,br+180)<30:b.append((g.distance(pt),I[i]))
    def s(L):
        if not L:return (0,0,None,None)
        k=sorted(L)[0][1];e=N['E'][k];return (sum(car(l) for l in e['lanes']),sum(bus(l) for l in e['lanes']),round(max(l['sp'] for l in e['lanes'])*3.6),k)
    return s(f),s(b)
T5=nettree(v5);T7=nettree(n7)
Lb=json.load(open(D+'/blind_labels.json'))
PJ=json.load(open(D+'/pano.json'))
rows=[]
for it in json.load(open(D+'/sections.json')):
    k=it['edge'];e=v5['E'][k];L=e['lanes'][len(e['lanes'])//2];p=[tuple(map(float,q.split(',')[:2])) for q in L['shape'].split()]
    g=LineString(p);s=g.length/2;mid=g.interpolate(s);br=lb(g,s)
    f5,b5=lanes_at(v5,T5,mid,br);f7,b7=lanes_at(n7,T7,mid,br)
    u=Point(mid.x-off[0],mid.y-off[1])
    t=O.get(it['way'],{}).get('tags',{})
    rev=k.startswith('-')
    osmlanes=t.get('lanes:backward' if rev else 'lanes:forward') or t.get('lanes')
    w=near(width,u,br,10);sp=near(speed,u,br,10);bu=near(bust,u,br,10)
    wv=w[0][1].get('Bredd') if w else None
    wm=w[0][1].get('Mätmetod_Avslutad_2009_06_30_') if w else None
    spv=sorted({x[1].get('Högsta_tillåtna_hastighet') or x[1].get('MAIN_ATTRIBUTE_VALUE') for x in sp},key=str) if sp else []
    bv=sorted({str(x[1].get('MAIN_ATTRIBUTE_DESCRIPTION')) for x in bu})
    ru=near(ltfr,u,br,12)
    kinds=collections.Counter()
    for d,pp,sg in ru:
        ti=pp.get('TITLE') or ''
        m=re.search(r'föreskrifter om (.*?) (på|i|vid|inom|för|mellan|längs)\b',ti)
        kinds[(m.group(1) if m else ti[:30])[:28]]+=1
    ovn=near(ov,u,br,12)
    # Overture one-way: a car-wide denied heading
    oow=None;ocl=None;ospd=None;ow=None
    if ovn:
        r=ovn[0][1];ocl=r['class']
        a=json.loads(r['acc']) if r['acc'] and r['acc']!='NULL' else []
        oow=any(x.get('access_type')=='denied' and (x.get('when') or {}).get('heading') and not (x.get('when') or {}).get('mode') and not (x.get('when') or {}).get('using') for x in (a or []))
        sq=json.loads(r['spd']) if r['spd'] and r['spd']!='NULL' else []
        ospd=sorted({(x.get('max_speed') or {}).get('value') for x in (sq or [])},key=str)
        ow=r['w'] if r['w'] not in('','NULL',None) else None
    rows.append(dict(id=it['id'],cls=it['cls'],name=e.get('name'),edge=k,type=e['type'],len=round(L['len']),
      v5_fw=f5[0],v5_fw_bus=f5[1],v5_bw=b5[0],v5_bw_bus=b5[1],v5_sp=f5[2],n7_fw=f7[0],n7_fw_bus=f7[1],n7_bw=b7[0],n7_sp=f7[2],n7_edge=f7[3],
      osm_lanes=t.get('lanes'),osm_dir_lanes=osmlanes,osm_oneway=t.get('oneway'),osm_turn=t.get('turn:lanes') or t.get('turn:lanes:forward') or '',osm_psv=t.get('psv:lanes') or t.get('bus:lanes') or t.get('psv:lanes:forward') or t.get('bus:lanes:forward') or '',osm_maxspeed=t.get('maxspeed'),
      nvdb_width=wv,nvdb_width_method=wm,nvdb_speed=';'.join(map(str,spv)),nvdb_bus=';'.join(bv),
      ltfr=';'.join(f'{a}x{b}' for a,b in kinds.items()),ov_class=ocl,ov_oneway=oow,ov_speed=ospd,ov_width=ow,blind=Lb.get(it['id']),pano=len(PJ.get(it['id'],[])),lon=round(it['lon'],6),lat=round(it['lat'],6)))
w=csv.DictWriter(open(out,'w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
