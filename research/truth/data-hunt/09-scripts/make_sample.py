# Choose 100 sections and 30 junctions in central Stockholm, deterministic. usage: make_sample.py v5.json osm.json sections.json junctions.json
import sys,json,random,re,math,collections
import pyproj
v5,osmf,sf,jf=sys.argv[1:5]
N=json.load(open(v5));E=N['E'];off=N['off'];O=json.load(open(osmf))['ways'];J=N['J']
tf=pyproj.Transformer.from_crs('+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs','EPSG:4326',always_xy=True)
def ll(x,y): return tf.transform(x-off[0],y-off[1])
BB=(18.00,59.305,18.11,59.355)
car=lambda l:(not l['allow'] or 'passenger' in l['allow'].split()) and 'passenger' not in (l['dis'] or '').split()
G={'major':[],'secondary':[],'tertiary':[],'local':[]}
seen=set()
for k,e in sorted(E.items()):
    if k.startswith(':') or not e['type'] or not any(car(l) for l in e['lanes']): continue
    w=re.sub('#.*','',k).lstrip('-');t=O.get(w,{}).get('tags',{})
    if t.get('tunnel') or t.get('covered') or t.get('bridge'): continue
    L=e['lanes'][0]
    if L['len']<40: continue
    pts=L['shape'].split();mx,my=map(float,pts[len(pts)//2].split(',')[:2]);lon,lat=ll(mx,my)
    if not(BB[0]<=lon<=BB[2] and BB[1]<=lat<=BB[3]): continue
    h=e['type'].replace('highway.','')
    g='major' if h in('trunk','primary','primary_link','trunk_link') else 'secondary' if h in('secondary','secondary_link') else 'tertiary' if h in('tertiary','tertiary_link') else 'local' if h in('residential','unclassified','living_street') else None
    if not g: continue
    G[g].append((k,w,lon,lat))
r=random.Random(9);out=[]
for g,n in (('major',15),('secondary',40),('tertiary',25),('local',20)):
    r.shuffle(G[g]);got=0
    for k,w,lon,lat in G[g]:
        if w in seen: continue
        seen.add(w);out.append(dict(id=f'S{len(out)+1:03d}',edge=k,way=w,cls=g,lon=lon,lat=lat));got+=1
        if got==n:break
print({g:len(v) for g,v in G.items()},len(out))
json.dump(out,open(sf,'w'))
# junctions: named sites from report 07 inside the area, plus random signalised and unsignalised with several approaches
named=['cluster_1673767222_1673767225_1673767231_1673767233_#10more','cluster_119698_1673767356_1673767360_1673767364_#8more','cluster_12184692946_12184692947_159868_1645783034_#9more','cluster_12957251835_13910476913_13910476914_13910476916_#12more','21760826','cluster_12723882194_12723898812_12726719633_6003359904','2453067331','208343357']
inc=collections.Counter()
for k,e in E.items():
    if any(car(l) for l in e['lanes']): inc[e['to']]+=1
S=[j for j in sorted(J) if J[j]['type'] in('traffic_light','traffic_light_unregulated') and inc[j]>=3]
P=[j for j in sorted(J) if J[j]['type'] in('priority','right_before_left','allway_stop','zipper') and inc[j]>=3]
def ok(j):
    lon,lat=ll(J[j]['x'],J[j]['y']);return BB[0]<=lon<=BB[2] and BB[1]<=lat<=BB[3]
S=[j for j in S if ok(j)];P=[j for j in P if ok(j)]
r.shuffle(S);r.shuffle(P)
sel=[j for j in named if j in J]
sel+= [j for j in S if j not in sel][:20-min(20,len(sel))]
sel+= P[:30-len(sel)]
JO=[]
for i,j in enumerate(sel):
    lon,lat=ll(J[j]['x'],J[j]['y']);JO.append(dict(id=f'J{i+1:02d}',junction=j,type=J[j]['type'],lon=lon,lat=lat,x=J[j]['x'],y=J[j]['y']))
print(len(S),len(P),len(JO),[j['type'] for j in JO].count('traffic_light'))
json.dump(JO,open(jf,'w'))
