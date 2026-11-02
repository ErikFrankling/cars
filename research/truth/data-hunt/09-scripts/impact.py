# Speeds, bus-lane impact, junction table, Overture tests. usage: impact.py scratchdir layersdir oldwfsdir
import sys,json,re,csv,math,collections
import pyproj
from shapely.geometry import LineString,Point
from shapely import wkt as W
from shapely.strtree import STRtree
csv.field_size_limit(10**8)
D,LY,OLD=sys.argv[1:4]
utm='+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
t3=pyproj.Transformer.from_crs('EPSG:3011',utm,always_xy=True);tl=pyproj.Transformer.from_crs('EPSG:4326',utm,always_xy=True)
car=lambda l:(not l['allow'] or 'passenger' in l['allow'].split()) and 'passenger' not in (l['dis'] or '').split()
bus=lambda l:bool(l['allow']) and 'bus' in l['allow'].split() and 'passenger' not in l['allow'].split()
def bear(a,b): return math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
def lb(g,s):
    a=g.interpolate(max(0,s-2));b=g.interpolate(min(g.length,s+2));return bear((a.x,a.y),(b.x,b.y))
ad=lambda a,b:abs((a-b+180)%360-180)
v5=json.load(open(D+'/v5.json'));n7=json.load(open(D+'/n7.json'));off=v5['off'];O=json.load(open(D+'/osm.json'))
OW=O['ways']
def load(name,base=LY):
    G=[];P=[]
    for f in json.load(open(f'{base}/{name}.geojson',encoding='utf-8'))['features']:
        g=f['geometry']
        if not g or g['type'] not in('LineString','Point'):continue
        co=g['coordinates'] if g['type']=='LineString' else [g['coordinates']]
        x,y=t3.transform([c[0] for c in co],[c[1] for c in co])
        G.append(LineString(zip(x,y)) if len(co)>1 else Point(x[0],y[0]));P.append(f['properties'])
    return STRtree(G),G,P
# 1 speeds
sp=load('nvdb_speed')
import os
for name,N in (() if os.environ.get('SKIP') else (('v5',v5),('n7',n7))):
    tot=collections.Counter();bad=collections.Counter();st=collections.Counter();ex={}
    for k,e in N['E'].items():
        if not e.get('type') or not any(car(l) for l in e['lanes']):continue
        L=e['lanes'][len(e['lanes'])//2];p=[tuple(map(float,q.split(',')[:2])) for q in L['shape'].split()]
        if len(p)<2 or L['len']<20:continue
        g=LineString(p);m=g.interpolate(.5,normalized=True);u=Point(m.x-off[0],m.y-off[1]);br=lb(g,g.length/2)
        vals=set()
        for i in sp[0].query(u.buffer(6)):
            ge=sp[1][i]
            if ge.distance(u)>6:continue
            b2=lb(ge,ge.project(u))
            if ad(b2,br)<30 or ad(b2,br+180)<30:
                v=sp[2][i].get('Högsta_tillåtna_hastighet') or sp[2][i].get('MAIN_ATTRIBUTE_VALUE')
                if isinstance(v,(int,float)):vals.add(v)
        if not vals:continue
        kph=max(l['sp'] for l in e['lanes'])*3.6;c=e['type'].replace('highway.','');g2='major' if c in('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link') else 'minor'
        tot[g2]+=L['len']/1000
        if min(abs(kph-v) for v in vals)>5:
            bad[g2]+=L['len']/1000;d=round(kph-min(vals,key=lambda v:abs(kph-v)));st[(e.get('name'),round(kph),tuple(sorted(vals)))]+=L['len']/1000
    print('SPEED',name,{g:(round(tot[g],1),round(bad[g],1),round(100*bad[g]/tot[g],1)) for g in tot})
    if name=='v5':
        for (a,b,c),v in st.most_common(16):print('   ',a,'net',b,'nvdb',c,round(v,2),'km')
# 2 bus impact
for name,N in (() if os.environ.get('SKIP') else (('v5',v5),('n7',n7))):
    R=list(csv.DictReader(open(f'{D}/lr_{name}_bus.csv')))
    E=N['E'];openE=collections.defaultdict(set);honE=set()
    for r in R:
        for k in r['edges'].split(';'):
            if k in E:
                if r['res']=='open':openE[k].add(r['citation'])
                elif r['res']=='honoured':honE.add(k)
    M=[k for k in openE if k not in honE]
    lk=sum(sum(car(l) for l in E[k]['lanes'])*E[k]['lanes'][0]['len'] for k in M)/1000
    two=[k for k in M if sum(car(l) for l in E[k]['lanes'])>=2]
    one=[k for k in M if sum(car(l) for l in E[k]['lanes'])==1]
    km2=sum(E[k]['lanes'][0]['len'] for k in two)/1000;km1=sum(E[k]['lanes'][0]['len'] for k in one)/1000
    major=[e for e in E.values() if e.get('type') and re.sub('highway.','',e['type']) in('motorway','trunk','primary','secondary','tertiary','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link')]
    mlk=sum(sum(car(l) for l in e['lanes'])*e['lanes'][0]['len'] for e in major)/1000
    print('BUS',name,'open edges',len(M),'two+ car lanes:',len(two),round(km2,1),'km; one lane:',len(one),round(km1,1),'km; major lane-km',round(mlk,1),'share of major lane-km lost if each 2+ edge loses one lane',round(100*km2/mlk,2))
    tagged=sum(1 for k in two if any('psv' in t or 'bus' in t for t in OW.get(re.sub('#.*','',k).lstrip('-'),{}).get('tags',{})))
    print('    of two+ open edges, way already has a psv/bus tag:',tagged)
    yr=collections.Counter(r['vf'][:4] for r in R if r['res']=='open')
    print('    open rules by year',sorted(yr.items()))
    if name=='v5':
        st=collections.Counter()
        for k in two: st[E[k].get('name')]+=E[k]['lanes'][0]['len']/1000
        print('    streets',[(a,round(b,2)) for a,b in st.most_common(15)])
    json.dump(dict(two=two,one=one),open(f'{D}/bus_edges_{name}.json','w'))
# 3 Overture
G=[];P=[]
with open(D+'/overture.csv',encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        g=W.loads(r['wkt']);x,y=tl.transform(*zip(*g.coords));G.append(LineString(zip(x,y)));P.append(r)
net=[]
for e in v5['E'].values():
    p=[tuple(map(float,q.split(',')[:2])) for q in e['lanes'][0]['shape'].split()]
    if len(p)>=2:net.append(LineString([(a-off[0],b-off[1]) for a,b in p]))
T=STRtree(net)
tt=[i for i,r in enumerate(P) if 'TomTom' in r['src']]
d=[]
for i in tt:
    m=G[i].interpolate(.5,normalized=True);j=T.nearest(m);d.append(net[j].distance(m))
d.sort();n=len(d)
print('TOMTOM segs',n,'len km',round(sum(G[i].length for i in tt)/1000,1),'dist to net p50',round(d[n//2],1),'share within 15m',round(sum(x<15 for x in d)/n,3),'over 50m',sum(x>50 for x in d),collections.Counter(P[i]['class'] for i in tt).most_common(4))
print('OVERTURE fields',{k:sum(1 for r in P if r[k] not in('',None,'NULL')) for k in('acc','spd','pt','w')},len(P))
S=list(csv.DictReader(open(D+'/sections_compare.csv')))
oc=collections.Counter((r['osm_oneway'] in('yes','-1'),r['ov_oneway']=='True') for r in S)
print('OVERTURE oneway vs OSM tag on 100 sections',oc,'class eq',sum(r['ov_class']==r['type'].replace('highway.','') for r in S),'speed eq osm',sum(bool(r['osm_maxspeed']) and r['ov_speed']==f"[{r['osm_maxspeed']}]" for r in S),'of',sum(bool(r['osm_maxspeed']) for r in S))
# 4 junctions
kor=load('NVDB_Korsning',OLD);sig=load('Signallykta',OLD);ban=load('nvdb_turnban')
LF=load('ltfr_rules')
tr5=None
allr=[(e['id'] if False else None) for e in []]
pts=[]
rest=collections.Counter()
ovpt=[(G[i],P[i]) for i in range(len(G)) if P[i]['pt'] not in('',None,'NULL')]
OT=STRtree([g for g,_ in ovpt])
banres={r['oid']:r for r in csv.DictReader(open(D+'/lr_v5_turnban.csv'))}
conn5=collections.defaultdict(list);conn7=collections.defaultdict(list)
for c in v5['C']:conn5[c[0]].append(c)
for c in n7['C']:conn7[c[0]].append(c)
def appr(N,conn,xy):
    # approach edges ending within 45 m of the junction centre (net frame)
    o=[]
    for k,e in N['E'].items():
        if k.startswith(':') or not any(car(l) for l in e['lanes']):continue
        last=e['lanes'][0]['shape'].split()[-1].split(',');d=math.hypot(float(last[0])-xy[0],float(last[1])-xy[1])
        if d<45 and e['lanes'][0]['len']>=7.5:
            ms=collections.defaultdict(set)
            for c in conn[k]:ms[c[2]].add(c[4])
            nc=sum(car(l) for l in e['lanes']);tonly=sum(1 for i,s in ms.items() if s and s<=set('lLrRt'))
            t=OW.get(re.sub('#.*','',k).lstrip('-'),{}).get('tags',{})
            o.append(dict(edge=k,name=e.get('name'),car=nc,bus=sum(bus(l) for l in e['lanes']),turnonly=tonly,dirs=''.join(sorted({d for s in ms.values() for d in s})),arrows=t.get('turn:lanes') or t.get('turn:lanes:forward') or ''))
    return o
rows=[]
for j in json.load(open(D+'/junctions.json')):
    xy=(j['x'],j['y']);u=Point(xy[0]-off[0],xy[1]-off[1])
    A5=appr(v5,conn5,xy);A7=appr(n7,conn7,xy)
    near=lambda T_,r:[T_[2][i] for i in T_[0].query(u.buffer(r)) if T_[1][i].distance(u)<=r]
    K=near(kor,60);Sg=near(sig,70);B=near(ban,50);Lr=near(LF,70)
    tl_=collections.Counter(str(k.get('Signalreglering')) for k in K)
    ids=sorted({str(s.get('anläggnings-id') or s.get('tillhör') or '') for s in Sg})[:5]
    kinds=collections.Counter()
    for p in Lr:
        m=re.search(r'föreskrifter om (.*?) (på|i|vid|inom|för|mellan|längs)\b',p.get('TITLE') or '');k=(m.group(1) if m else '')[:18]
        if re.search('sväng|körriktning|infart|enkelrikt|körfält|körbana',k):kinds[k]+=1
    open_b=sum(1 for b in B if banres.get(str(b.get('OBJECT_ID')),{}).get('res')=='open_in_net')
    ovc=sum(1 for i in OT.query(u.buffer(60)) if ovpt[i][0].distance(u)<=60)
    rows.append(dict(id=j['id'],junction=j['junction'][:30],type=j['type'],lon=round(j['lon'],5),lat=round(j['lat'],5),names='/'.join(sorted({a['name'] or '?' for a in A5}))[:48],
      v5_appr=len(A5),v5_lanes=sum(a['car'] for a in A5),v5_bus=sum(a['bus'] for a in A5),v5_turnonly=sum(a['turnonly'] for a in A5),n7_appr=len(A7),n7_lanes=sum(a['car'] for a in A7),n7_turnonly=sum(a['turnonly'] for a in A7),
      osm_arrows=sum(bool(a['arrows']) for a in A5),nvdb_sig=dict(tl_).get('ja',0),nvdb_nosig=dict(tl_).get('nej',0),register=len(Sg),nvdb_bans=len(B),bans_open_v5=open_b,ltfr=';'.join(f'{a}x{b}' for a,b in kinds.items())[:70],ov_turn=ovc,pano=0))
w=csv.DictWriter(open(D+'/junctions_compare.csv','w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for r in rows:print(r['id'],r['type'][:7],r['names'][:40],'v5',r['v5_appr'],r['v5_lanes'],r['v5_bus'],r['v5_turnonly'],'n7',r['n7_appr'],r['n7_lanes'],r['n7_turnonly'],'arrows',r['osm_arrows'],'sig',r['nvdb_sig'],r['nvdb_nosig'],'reg',r['register'],'bans',r['nvdb_bans'],r['bans_open_v5'],'ov',r['ov_turn'],'|',r['ltfr'][:50])
