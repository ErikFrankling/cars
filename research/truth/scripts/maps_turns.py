# What --osm.turn-lanes really changes: compares the baseline net to a turn-lane net, connection by connection, and rechecks the 07 report's 556/546/411 counts.
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,re,gzip,math,csv
B=load_net(sys.argv[1]);V=load_net(sys.argv[2]);logp=sys.argv[3];rou=sys.argv[4]
osm=load_osm(MAPS/'builds/osm/highway.osm.xml');fwd,back=net_tf(B)
def groups(n):
    g=collections.defaultdict(list)
    for c in n['conns']:g[c[0]].append(c)
    return g
GB,GV=groups(B),groups(V)
TURN={'l','L','r','R','t'}
def lanes_dirs(n,g,e):
    pl={l['i'] for l in n['edges'][e]['lanes'] if passenger(l)};d=collections.defaultdict(set)
    for c in g.get(e,[]):
        if c[2] in pl:d[c[2]].add(c[4])
    return pl,d
def excl(n,g,e):
    pl,d=lanes_dirs(n,g,e);return sum(bool(s) and s<=set('lLrR') for s in d.values())
sig=lambda g,e:any(c[6] for c in g.get(e,[]))
common=set(B['edges'])&set(V['edges'])
print('edges base/var/common',len(B['edges']),len(V['edges']),len(common))
ch=[e for e in common if {c[:4] for c in GB.get(e,[])}!={c[:4] for c in GV.get(e,[])}]
print('edges whose lane-to-lane connections changed',len(ch),'of them signalised in base',sum(sig(GB,e) for e in ch))
print('total connections',len(B['conns']),len(V['conns']))
excl_b=sum(excl(B,GB,e)>0 and sig(GB,e) for e in common);excl_v=sum(excl(V,GV,e)>0 and sig(GV,e) for e in common)
print('signalised approaches with a turn-only lane base/var',excl_b,excl_v)
print('total turn-only lanes on all edges base/var',sum(excl(B,GB,e) for e in common),sum(excl(V,GV,e) for e in common))
pb={(c[0],c[1]) for c in B['conns']};pv={(c[0],c[1]) for c in V['conns']}
lost=pb-pv;gain=pv-pb;print('edge-to-edge movements lost',len(lost),'gained',len(gain))
print('lost by dir',collections.Counter(next(c[4] for c in GB[a] if c[1]==b) for a,b in lost).most_common())
big=collections.Counter()
if rou:
    with gzip.open(rou) as f:
        for _,e in E.iterparse(f,events=('end',),tag='route'):
            r=(e.get('edges') or '').split()
            for a,b in zip(r,r[1:]):
                if (a,b) in lost or (a,b) in gain:big[(a,b)]+=1
            e.clear()
            while e.getprevious() is not None:del e.getparent()[0]
    u=[v for k,v in big.items() if k in lost];print('route bigrams on lost movements',sum(u),'distinct',len(u),'routes total n/a')
    print('top lost by routes',[(k,v,B['edges'][k[0]]['name'],B['edges'][k[1]]['name']) for k,v in big.most_common(12) if k in lost])
w=collections.Counter();ex=collections.defaultdict(list)
for line in open(logp,errors='replace'):
    m=re.match(r"Warning: (Ignoring turn sign|Cannot apply turn sign|Turn sign)[^']*",line)
    if 'turn sign' in line.lower():
        k=re.sub(r"'[^']*'|\d+",'%',line.strip())[:110];w[k]+=1
print('turn warnings');[print(' ',v,k) for k,v in w.most_common(12)]
# recheck 556/546/411
rows=list(csv.DictReader(open('research/truth/stockholm-map-osm-comparison.csv')))
sigrows=[r for r in rows if r['signalised']=='1']
tagged=[r for r in sigrows if json.loads(r['osm_turn_tags'])]
print('signalised rows',len(sigrows),'tagged any key',len(tagged))
def v_for(edge,ts,oneway):
    back_=edge.startswith('-');k='turn:lanes:backward' if back_ else 'turn:lanes:forward';v=ts.get(k)
    if v is None and not back_ and oneway in('yes','1','true'):v=ts.get('turn:lanes')
    return v
EX={'left','right','slight_left','slight_right','sharp_left','sharp_right'}
ex_count=lambda v:sum(bool(set(s.split(';'))&EX) and not(set(s.split(';'))-EX) for s in v.split('|'))
cat=collections.Counter();out=[]
for r in tagged:
    ts=json.loads(r['osm_turn_tags']);e=r['edge'];v=v_for(e,ts,r['osm_oneway'])
    if v is None:
        cat['no tag for this direction']+=1;continue
    wid=int(r['osm_way']);w_=osm['ways'].get(wid);last=w_['nds'][0] if e.startswith('-') else w_['nds'][-1];lx,ly=fwd(*osm['nodes'][last])
    s=B['edges'][e]['lanes'][0]['shape'].split()[-1];x,y=map(float,s.split(','));term=math.hypot(x-lx,y-ly)
    n=len(v.split('|'));nl=len(B['edges'][e]['lanes']);npl=int(r['net_lanes'])
    terminal=term<40;ee=ex_count(v);b=excl(B,GB,e);a=excl(V,GV,e) if e in V['edges'] else None
    cat['direction known']+=1;cat['terminal <40 m' if terminal else 'non-terminal segment']+=1
    if terminal:
        cat['terminal, lane count equal' if n==nl else 'terminal, lane count differs']+=1
    cat['flag base']+=ee>b
    if a is not None:cat['flag after turn-lanes']+=ee>a
    if terminal and n==nl:
        cat['term+count flag base']+=ee>b
        if a is not None:cat['term+count flag after']+=ee>a
    if ee==0:cat['no exclusive arrow tagged']+=1
    out.append(dict(edge=e,name=r['name'],tag=v,terminal=int(terminal),tag_lanes=n,net_lanes=nl,tag_excl=ee,base_excl=b,after_excl=a,changed=int(e in set(ch))))
for k,v in sorted(cat.items()):print(' ',k,v)
print('changed among direction-known',sum(o['changed'] for o in out))
with open('research/truth/maps-turnlane-recheck.csv','w') as f:
    w_=csv.DictWriter(f,fieldnames=list(out[0]));w_.writeheader();w_.writerows(out)
# all OSM ways with turn tags, whole net
tags=collections.Counter();nt=0
for wid,wd in osm['ways'].items():
    t=wd['tags']
    if any(k.startswith('turn:lanes') for k in t):
        nt+=1;tags[t['highway']]+=1
print('OSM ways with turn:lanes*',nt,tags.most_common(12))
for k in ('lanes','maxspeed','turn:lanes','bus:lanes','psv:lanes','lanes:psv','lanes:bus','vehicle:lanes','access:lanes','destination:lanes','width','width:lanes','change:lanes','surface','cycleway','junction','placement','oneway:bus','oneway:psv','maxspeed:forward','motor_vehicle','sidewalk'):
    print(k,sum(any(x==k or x.startswith(k+':') for x in w['tags']) for w in osm['ways'].values()),end='; ')
print()
drv={'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street'}
for k in ('lanes','maxspeed'):
    c=collections.Counter();t=collections.Counter()
    for w in osm['ways'].values():
        h=w['tags']['highway']
        if h in drv:
            t[h]+=1;c[h]+=k in w['tags'] or k+':forward' in w['tags']
    print(k,'tagged share',{h:round(c[h]/t[h],3) for h in sorted(t)})
print('highway node tags',collections.Counter(n['tags'].get('highway') for n in osm['tagged'].values()).most_common(8))
