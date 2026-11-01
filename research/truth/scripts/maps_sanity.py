# Automatic sanity checks for a Stockholm net. Usage: maps_sanity.py NET.xml TAG [BASELINE_NET.xml ROUTES.gz]. Writes research/truth/maps-sanity-TAG.json. Thresholds are this report's proposal, not traffic law.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,re,math,gzip,numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from matplotlib.path import Path as MP
netp,tag=sys.argv[1:3];basep=sys.argv[3] if len(sys.argv)>3 else None;rou=sys.argv[4] if len(sys.argv)>4 else None
n=load_net(netp);fwd,back=net_tf(n);W=MAPS/'wfs-20261031';osm=dict(ways=load_osm_tags())
t3=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
def L(l,k):
    o=[]
    for f in json.loads((W/f'{l}.geojson').read_text())['features']:
        if f['geometry'] and f['geometry']['type']=='Point':
            c=f['geometry']['coordinates'];lo,la=t3.transform(c[0],c[1]);o.append((str(f['properties'].get(k)).lstrip('0'),*fwd(lo,la),f['properties']))
    return o
inv=L('Signallykta','anläggnings-id')+L('Signalstolpe','Anläggnings_id')+L('Tryckknapp','anläggnings-id')
P=[MP(np.array([fwd(*p) for p in r])) for r in json.loads((MAPS/'builds/osm/kommun.json').read_text())]
inside=lambda x,y:any(p.contains_point((x,y)) for p in P)
E_=n['edges'];J_=n['junctions'];R={}
out=collections.defaultdict(list)
for c in n['conns']:
    if c[0] in E_:out[c[0]].append(c)
pedge=[e for e,d in E_.items() if any(passenger(l) for l in d['lanes'])];idx={e:i for i,e in enumerate(pedge)}
a=[idx[c[0]] for c in n['conns'] if c[0] in idx and c[1] in idx];b=[idx[c[1]] for c in n['conns'] if c[0] in idx and c[1] in idx]
nc,lab=connected_components(csr_matrix((np.ones(len(a)),(a,b)),shape=(len(pedge),len(pedge))),directed=True,connection='strong')
big=np.bincount(lab).max();R['passenger_edges']=len(pedge);R['largest_scc_share']=round(float(big/len(pedge)),5)
ins={j:inside(d['x'],d['y']) for j,d in J_.items()}
# controllers
tlids={t['id'] for t in n['tls'].values()};nodes=collections.defaultdict(set);app=collections.defaultdict(set)
for c in n['conns']:
    if c[6] and c[0] in E_:nodes[c[6]].add(E_[c[0]]['to']);app[c[6]].add(c[0])
tin=[t for t in tlids if nodes[t] and any(ins.get(j) for j in nodes[t])]
R['controllers_total']=len(tlids);R['controllers_in_municipality']=len(tin);R['real_installations_city_register']=len({a[0] for a in inv})
R['controllers_per_real_installation']=round(len(tin)/len({a[0] for a in inv}),2)
R['single_approach_controllers_total']=sum(len(app[t])==1 for t in tlids);R['single_approach_in_municipality']=sum(len(app[t])==1 for t in tin)
Tc=cKDTree(np.array([[np.mean([J_[j]['x'] for j in nodes[t]]),np.mean([J_[j]['y'] for j in nodes[t]])] for t in tlids if nodes[t]]))
byinst=collections.defaultdict(list)
for a_ in inv:byinst[a_[0]].append((a_[1],a_[2]))
c0=collections.Counter()
tlxy=[t for t in tlids if nodes[t]]
for i,pts in byinst.items():
    s=set()
    for r in Tc.query_ball_point(np.array(pts),40):s.update(r)
    names={tlxy[k] for k in s};c0[min(len(names),3)]+=1
R['installations_with_0_1_2_3plus_controllers']=[c0[0],c0[1],c0[2],c0[3]]
# fingerprints
cyc=[sum(p[0] for p in t['phases']) for t in n['tls'].values()]
R['share_cycle_90']=round(sum(abs(x-90)<.01 for x in cyc)/len(cyc),4);R['share_offset_0']=round(sum(t['offset']==0 for t in n['tls'].values())/len(cyc),4);R['cycle_min_max']=[min(cyc),max(cyc)]
# stranded lanes: passenger lane with no connection on an edge that has connections
st=[];stsig=0
for e in pedge:
    cs=out.get(e,[])
    if not cs:continue
    used={c[2] for c in cs}
    for l in E_[e]['lanes']:
        if passenger(l) and l['i'] not in used:
            st.append((e,l['i']));stsig+=any(c[6] for c in cs)
R['stranded_passenger_lanes']=len(st);R['stranded_on_signal_approaches']=stsig
# stubs
sh=[e for e in pedge if E_[e]['lanes'][0]['length']<7.5];R['edges_shorter_than_one_car_7_5m']=len(sh);R['of_which_signal_approach']=sum(any(c[6] for c in out.get(e,[])) for e in sh)
R['signal_approaches']=sum(any(c[6] for c in out.get(e,[])) for e in pedge)
R['signal_approaches_with_turn_only_lane']=sum(any(c[6] for c in out.get(e,[])) and any((lambda ds:ds and ds<=set('lLrR'))({c[4] for c in out[e] if c[2]==l['i']}) for l in E_[e]['lanes'] if passenger(l)) for e in pedge)
# lanes and speed against OSM
wid=lambda e:(lambda m:int(m.group(1)) if m else None)(re.match(r'-?(\d+)',e))
lanediff=collections.Counter();spd=collections.Counter();psv_ok=psv_bad=0;miss_lanes=0;defaultspeed=[]
drv=('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street')
for e in pedge:
    w=osm['ways'].get(wid(e))
    if not w:continue
    t=w['tags'];d=E_[e];nl=len(d['lanes']);npl=sum(passenger(l) for l in d['lanes']);back_=e.startswith('-');x=None
    one=t.get('oneway') in('yes','1','true') or t.get('highway') in('motorway','motorway_link') or t.get('junction') in('roundabout','circular')
    try:
        if one and t.get('lanes'):x=int(t['lanes'])
        elif t.get('lanes:backward' if back_ else 'lanes:forward'):x=int(t['lanes:backward' if back_ else 'lanes:forward'])
        elif t.get('lanes'):
            tot=int(t['lanes']);x=tot-math.ceil(tot/2) if back_ else math.ceil(tot/2)
            x=max(x,1)
    except ValueError:pass
    if x is None:miss_lanes+=1
    else:lanediff['equal' if x==nl else 'net_more' if nl>x else 'net_fewer']+=1
    pv=t.get('psv:lanes:backward' if back_ else 'psv:lanes:forward') or (t.get('psv:lanes') if not back_ else None) or t.get('bus:lanes:backward' if back_ else 'bus:lanes:forward') or (t.get('bus:lanes') if not back_ else None)
    if pv and 'designated' in pv:
        k=sum(s=='designated' for s in pv.split('|'))
        if npl<=max(nl-k,0):psv_ok+=1
        else:psv_bad+=1
    if t.get('maxspeed') is None and d['type'].split('.')[-1] not in('motorway','motorway_link','trunk','trunk_link'):
        v=max(l['speed'] for l in d['lanes'])*3.6
        if v>=75 and ins.get(d['to']):defaultspeed.append(e)
R['edges_without_osm_lanes_tag']=miss_lanes;R['lane_count_vs_osm']=dict(lanediff);R['bus_lane_ok_vs_bad']=[psv_ok,psv_bad];R['default_speed_75plus_urban_edges_municipality']=len(defaultspeed);R['default_speed_examples']=defaultspeed[:5]
# priority logic
R['right_before_left_with_secondary_or_higher_incoming']=0
inc=collections.defaultdict(set)
for e,d in E_.items():inc[d['to']].add(d['type'].split('.')[-1])
R['right_before_left_with_secondary_or_higher_incoming']=sum(bool(J_[j]['type']=='right_before_left' and inc[j]&{'secondary','primary','trunk','motorway','secondary_link','primary_link'}) for j in J_)
R['junction_types']=dict(collections.Counter(d['type'] for d in J_.values()))
def diam(s):
    if not s:return 0
    p=[tuple(map(float,x.split(',')[:2])) for x in s.split()];xs,ys=zip(*p);return max(max(xs)-min(xs),max(ys)-min(ys))
R['junctions_over_60m_across']=sum(diam(d['shape'])>60 for d in J_.values())
il=[v[0] for v in n['internal_len'].values()];R['internal_lanes_over_60m']=sum(x>60 for x in il);R['internal_lanes']=len(il)
# turn speed from the net's internal lanes
c=collections.Counter();vs=collections.defaultdict(list)
for c_ in n['conns']:
    if c_[8] and c_[4] in('l','r','L','R','t') and c_[8] in n['internal_len'] and c_[0] in E_:
        vs[c_[4]].append(n['internal_len'][c_[8]][1]*3.6)
R['internal_turn_speed_kmh_median_p90']={k:[round(float(np.median(v)),1),round(float(np.percentile(v,90)),1)] for k,v in vs.items()}
# NVDB forbidden turns still open
fb=json.loads((W/'NVDB_Forbjuden_svang.geojson').read_text())['features'];segs=[]
ends=[fwd(*t3.transform(c[0],c[1])) for f in fb if f['geometry'] for c in (f['geometry']['coordinates'][0],f['geometry']['coordinates'][-1])]
Ends=cKDTree(np.array(ends))
for e in pedge:
    pts=[tuple(map(float,p.split(','))) for p in E_[e]['lanes'][0]['shape'].split()]
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        L_=math.hypot(x1-x0,y1-y0);k=max(1,int(L_//8))
        for q in range(k+1):
            x_,y_=x0+(x1-x0)*q/k,y0+(y1-y0)*q/k
            if Ends.query((x_,y_))[0]<=16:segs.append((x_,y_,math.atan2(y1-y0,x1-x0),idx[e]))
A=np.array(segs,dtype=float);Tree=cKDTree(A[:,:2]);del segs
edge_list=pedge;pairs={(c[0],c[1]) for c in n['conns']}
def cand(x,y,h):
    r=[]
    for i in Tree.query_ball_point((x,y),14):
        dh=abs((A[i,2]-h+math.pi)%(2*math.pi)-math.pi)
        if dh<math.radians(50):r.append(edge_list[int(A[i,3])])
    return set(r)
mt=collections.Counter();openf=[]
for f in fb:
    g=f['geometry']
    if not g:continue
    co=g['coordinates']
    if g['type']=='MultiLineString':co=co[0]+co[-1]
    pts=[fwd(*t3.transform(c[0],c[1])) for c in co]
    if len(pts)<3:mt['too short']+=1;continue
    h0=math.atan2(pts[1][1]-pts[0][1],pts[1][0]-pts[0][0]);h1=math.atan2(pts[-1][1]-pts[-2][1],pts[-1][0]-pts[-2][0])
    A0=cand(*pts[0],h0);B0=cand(*pts[-1],h1)
    if not A0 or not B0:mt['unmatched']+=1;continue
    mt['matched']+=1;hit=[(x,y) for x in A0 for y in B0 if (x,y) in pairs and x!=y]
    if hit:
        mt['open_in_net']+=1;openf.append(hit[0])
R['nvdb_forbidden_turns']=dict(mt);R['nvdb_forbidden_open_examples']=[(a_,E_[a_]['name'],b_,E_[b_]['name']) for a_,b_ in openf[:8]]
if basep:
    B=load_net(basep);pb={(c[0],c[1]) for c in B['conns']};pv={(c[0],c[1]) for c in n['conns']};lost=pb-pv
    R['movements_lost_vs_baseline']=len(lost);R['movements_gained_vs_baseline']=len(pv-pb);R['edges_lost_vs_baseline']=len(set(B['edges'])-set(E_))
    if rou:
        tot=bad=vt=vb=0;badr=set()
        with gzip.open(rou) as f:
            for line in f:
                s_=line.lstrip()
                if s_.startswith(b'<route '):
                    r=re.search(rb'edges="([^"]*)"',s_).group(1).decode().split();tot+=1
                    if any((x,y) in lost or x not in E_ or y not in E_ for x,y in zip(r,r[1:])):
                        bad+=1;badr.add(re.search(rb' id="([^"]*)"',s_).group(1))
                elif s_.startswith(b'<vehicle '):
                    vt+=1;m=re.search(rb' route="([^"]*)"',s_);vb+=bool(m and m.group(1) in badr)
        R['routes_total']=tot;R['routes_broken']=bad;R['vehicles_total']=vt;R['vehicles_on_broken_routes']=vb
Path(f'research/truth/maps-sanity-{tag}.json').write_text(json.dumps(R,indent=1,ensure_ascii=False));print(tag,json.dumps(R,ensure_ascii=False))
# lane drops caused by a missing lanes tag: an edge in a major class with no OSM lanes tag, fed by an edge with more lanes
G_=collections.defaultdict(set);C_=collections.Counter();ex_=[]
for c in n['conns']:
    if c[0] in E_ and c[1] in E_:G_[c[1]].add(c[0])
for e in pedge:
    w=osm['ways'].get(wid(e))
    if not w or any(k.startswith('lanes') for k in w['tags']):continue
    h=w['tags'].get('highway')
    if h not in('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary'):continue
    nl=sum(passenger(l) for l in E_[e]['lanes']);up=[sum(passenger(l) for l in E_[u]['lanes']) for u in G_[e] if E_[u]['name']==E_[e]['name']]
    if up and max(up)>nl:
        C_[h]+=1;ex_.append(e)
R['lane_drop_from_missing_tag_same_street']=sum(C_.values());R['lane_drop_by_class']=dict(C_);R['lane_drop_length_km']=round(sum(E_[e]['lanes'][0]['length'] for e in ex_)/1000,1);R['lane_drop_examples']=[(e,E_[e]['name'],round(E_[e]['lanes'][0]['length'],1)) for e in ex_[:6]]
Path(f'research/truth/maps-sanity-{tag}.json').write_text(json.dumps(R,indent=1,ensure_ascii=False));print('lane drops',R['lane_drop_from_missing_tag_same_street'],R['lane_drop_by_class'],R['lane_drop_length_km'],R['lane_drop_examples'])
