# One-way rule conflicts: drop structural false matches, then ask NVDB (NetInfo WMS, no login) and OSM. usage: adjudicate_oneway.py rules_v5.csv osm.json v5.json out.csv
import sys,csv,json,re,time,urllib.request,pyproj,collections
rf,of,nf,out=sys.argv[1:5]
R=[r for r in csv.DictReader(open(rf)) if r['cat']=='oneway' and r['res'] in('net_two_way','net_opposite')]
O=json.load(open(of))['ways'];N=json.load(open(nf));off=N['off']
to3006=pyproj.Transformer.from_crs('+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs','EPSG:3006',always_xy=True)
# citations that come in opposite pairs on one street describe two carriageways, not one two-way street
def kind(r):
    t=r['text'].lower()
    if 'cykelban' in t: return 'cycle_path'
    if re.search(r'(västerut|söderut|österut|norrut)/.*/',t) or 'medsols' in t or 'motsols' in t: return 'loop_text'
    if re.search(r'körbana|lokalkörbana',t): return 'named_carriageway'
    return 'street'
by=collections.defaultdict(set)
for r in R:
    m=re.search(r'(nordvästlig|nordöstlig|sydvästlig|sydöstlig|nordlig|sydlig|östlig|västlig)',r['text'])
    if m: by[r['loc']].add(m.group(1))
OPP={'nordlig':'sydlig','sydlig':'nordlig','östlig':'västlig','västlig':'östlig','nordvästlig':'sydöstlig','sydöstlig':'nordvästlig','nordöstlig':'sydvästlig','sydvästlig':'nordöstlig'}
def wfs(x,y,layer):
    u=f"https://geo-netinfo.trafikverket.se/mapservice/wms.axd/NetInfo?service=WMS&version=1.1.1&request=GetFeatureInfo&layers={layer}&query_layers={layer}&styles=&srs=EPSG:3006&bbox={x-25},{y-25},{x+25},{y+25}&width=101&height=101&x=50&y=50&info_format=application/json&feature_count=5"
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'research'}),timeout=40)).get('features',[])
    except Exception as e: return [{'properties':{'err':str(e)[:40]}}]
rows=[]
for r in R:
    k=kind(r);pair=any(OPP[d] in by[r['loc']] for d in by[r['loc']])
    if pair: k='opposite_pair'
    x,y=to3006.transform(float(r['x'])-off[0],float(r['y'])-off[1])
    F=wfs(x,y,'ForbjudenFardriktning');time.sleep(0.2)
    be=sorted({f['properties'].get('Beteckning','') for f in F})
    cit=r['citation'].replace('-',':',1) if False else r['citation']
    y2=cit.replace(' ','').replace('-',':')
    same=any(b.replace(' ','').replace('-',':')==y2 for b in be)
    edges=[e for e in (r['fw'].split(';')+r['bw'].split(';')) if e]
    tags=collections.Counter()
    for e in edges:
        w=re.sub('#.*','',e).lstrip('-');t=O.get(w,{}).get('tags',{});tags[(t.get('highway'),t.get('oneway','-'))]+=1
    rows.append(dict(res=r['res'],kind=k,citation=r['citation'],loc=r['loc'],len=r['len_m'],vf=r['valid_from'],nvdb_oneway_hits=len([f for f in F if 'Beteckning' in f['properties']]),nvdb_same_rule=int(same),nvdb_rules=';'.join(be)[:60],osm=str(dict(tags))[:80],edges=';'.join(edges)[:70],text=r['text'][:150]))
w=csv.DictWriter(open(out,'w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(collections.Counter(r['kind'] for r in rows))
for r in rows:
    if r['kind'] in('street','named_carriageway'): print(r['res'][:7],r['kind'][:6],r['citation'][5:],r['vf'],r['loc'][:22],'L',r['len'],'nvdb',r['nvdb_oneway_hits'],r['nvdb_same_rule'],r['osm'][:60])
