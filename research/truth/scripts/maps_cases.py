# Builds the verified 20-case list: net junction ids, controllers, real installations, NVDB signal flags and lane facts around each reference point.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,csv,re,numpy as np
from scipy.spatial import cKDTree
B=load_net(DATA/'stockholm/stockholm.net.xml');V=load_net(MAPS/'builds/v5_inventory/net.xml');fwd,back=net_tf(B)
W=MAPS/'wfs-20261031';t3=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
def L(l,k):
    o=[]
    for f in json.loads((W/f'{l}.geojson').read_text())['features']:
        if f['geometry'] and f['geometry']['type']=='Point':
            c=f['geometry']['coordinates'];lo,la=t3.transform(c[0],c[1]);o.append((str(f['properties'].get(k)).lstrip('0'),*fwd(lo,la),f['properties']))
    return o
inv=L('Signallykta','anläggnings-id')+L('Signalstolpe','Anläggnings_id')+L('Tryckknapp','anläggnings-id');K=L('NVDB_Korsning','x')
Fgroups=collections.defaultdict(set)
for a in L('Signallykta','anläggnings-id'):
    m=re.search(r'\b(F\d+)',a[3].get('namn') or '')
    if m:Fgroups[a[0]].add(m.group(1))
CASES=[l for l in csv.DictReader(open('research/truth/maps-cases-input.csv'))]
out=collections.defaultdict(list)
for c in B['conns']:
    if c[0] in B['edges']:out[c[0]].append(c)
inc=collections.defaultdict(list)
for e,d in B['edges'].items():inc[d['to']].append(e)
tlnode=collections.defaultdict(set);vtl=collections.defaultdict(set)
for c in B['conns']:
    if c[6] and c[0] in B['edges']:tlnode[B['edges'][c[0]]['to']].add(c[6])
for c in V['conns']:
    if c[6] and c[0] in V['edges']:vtl[V['edges'][c[0]]['to']].add(c[6])
rows=[]
for s in CASES:
    lat,lon,r=float(s['lat']),float(s['lon']),float(s['r']);x,y=fwd(lon,lat)
    js=[(j,d) for j,d in B['junctions'].items() if np.hypot(d['x']-x,d['y']-y)<=r]
    prim=s['junction'] if s['junction'] else min(js,key=lambda q:np.hypot(q[1]['x']-x,q[1]['y']-y))[0]
    assert prim in B['junctions'],prim
    d=B['junctions'][prim];la2,lo2=back(d['x'],d['y'])[::-1]
    ctrl={t for j,_ in js for t in tlnode.get(j,())};vctrl={t for j,_ in js for t in vtl.get(j,())}
    insts=sorted({a[0] for a in inv if np.hypot(a[1]-x,a[2]-y)<=r})
    nv=collections.Counter(a[3].get('Signalreglering') for a in K if np.hypot(a[1]-x,a[2]-y)<=r)
    inl=sum(sum(passenger(l) for l in B['edges'][e]['lanes']) for e in inc[prim])
    tonly=sum(any((lambda ds:ds and ds<=set('lLrR'))({c[4] for c in out[e] if c[2]==l['i']}) for l in [l]) for e in inc[prim] for l in B['edges'][e]['lanes'] if passenger(l))
    rows.append(dict(case=s['case'],label=s['label'],lat=round(la2,6),lon=round(lo2,6),junction=prim,jtype=d['type'],in_v5=int(prim in V['junctions']),approach_edges=' '.join(inc[prim]),incoming_passenger_lanes=inl,turn_only_lanes_base=tonly,radius_m=int(r),net_controllers=len(ctrl),v5_controllers=len(vctrl),real_installations=' '.join(insts),veh_signal_groups=' '.join(f"{i}:{len(Fgroups.get(i,()))}" for i in insts),nvdb_signal_yes_no_unknown=f"{nv.get('ja',0)}/{nv.get('nej',0)}/{nv.get('okänt',0)}",names=' / '.join(sorted({B['edges'][e]['name'] for e in inc[prim]}))))
with open('research/truth/maps-cases.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for r in rows:print(r['case'],r['label'],r['lat'],r['lon'],r['junction'][:45],r['jtype'],r['in_v5'],r['incoming_passenger_lanes'],r['turn_only_lanes_base'],r['net_controllers'],r['v5_controllers'],r['real_installations'],r['veh_signal_groups'],r['nvdb_signal_yes_no_unknown'],sep=' | ')
# give_way/stop signs vs net junction type
o=load_osm(MAPS/'builds/osm/highway.osm.xml');J=list(B['junctions'].items());T=cKDTree(np.array([[d['x'],d['y']] for _,d in J]))
c=collections.Counter()
for i,n in o['tagged'].items():
    h=n['tags'].get('highway')
    if h in('give_way','stop') and n['on_way']:
        d,k=T.query(fwd(n['lon'],n['lat']))
        if d<=25:c[h,J[k][1]['type']]+=1
        else:c[h,'none within 25 m']+=1
print(sorted(c.items()))
print('cluster ids',sum(j.startswith('cluster_') for j in B['junctions']),'GS controllers',sum(t['id'].startswith('GS_') for t in B['tls'].values()),'joinedS in v5_stage1',sum(t['id'].startswith('joinedS') for t in load_net(MAPS/'builds/v5_stage1/net.xml')['tls'].values()))
