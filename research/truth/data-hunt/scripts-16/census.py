"""Input audit census: one light pass over every net and route file. Regex line scan, no DOM. Usage: census.py OUT.json NETS ROUTES (comma lists)"""
import collections as C, gzip, json, re, sys, resource
resource.setrlimit(resource.RLIMIT_AS, (2000*1024**2, 2000*1024**2))
D='/home/erikf/projects/personal/cars-data'; B='/home/erikf/projects/personal/thesis-src/bachelor/config'; F=D+'/truth/stockholm/factorial'; L=D+'/lust/LuSTScenario-2.0/scenario'
ALLNETS={'stockholm_old':D+'/stockholm/stockholm.net.xml','stockholm_n7':F+'/n7_ramps.net.xml','stockholm_v5':D+'/truth/maps/builds/v5_inventory/net.xml','berlin':D+'/best/berlin.net.xml','charlottenburg':D+'/charlottenburg/charlottenburg.net.xml','mitte':D+'/mitte/mitte.net.xml','lust':L+'/lust.net.xml','bologna':B+'/scenarios/bologna/joined_buslanes.net.xml','i80':B+'/networks/i80_vsl.net.xml','ring':B+'/networks/ring.net.xml','glosa':B+'/networks/glosa_two_signal.net.xml'}
ALLROUTES={'stockholm60':D+'/stockholm/stockholm60.rou.gz','v2_c4':F+'/v2_c4.rou.gz','v2_a26':F+'/v2_a26.rou.gz','berlin':D+'/best/berlin.rou.gz','berlin_bus':D+'/best/berlin_bus.rou.xml','charlottenburg':D+'/charlottenburg/charlottenburg.rou.gz','mitte':D+'/mitte/mitte.rou.gz','lust_local0':L+'/DUERoutes/local.actuated.0.rou.xml','lust_local1':L+'/DUERoutes/local.actuated.1.rou.xml','lust_local2':L+'/DUERoutes/local.actuated.2.rou.xml','lust_transit':L+'/transit.rou.xml','lust_bus':L+'/buslines.rou.xml','bologna':B+'/scenarios/bologna/bologna_cars.rou.xml','i80':B+'/demand/i80_vsl.rou.xml','ring':B+'/demand/ring.rou.xml','glosa':B+'/demand/glosa_two_signal.rou.xml'}
NETS={k:ALLNETS[k] for k in sys.argv[2].split(',') if k}
ROUTES={k:ALLROUTES[k] for k in sys.argv[3].split(',') if k}
at=lambda s,k:(re.search(r'\b'+k+r'="([^"]*)"',s) or [None,None])[1]
def opn(p): return gzip.open(p,'rt',errors='replace') if p.endswith('.gz') else open(p,errors='replace')
def net(p):
    o=C.Counter(); jt=C.Counter(); tt=C.Counter(); cyc=C.Counter(); pat=C.Counter(); speed=C.Counter(); lanes=C.Counter(); typ=C.Counter(); cur=None; dur=[]; minmax=C.Counter(); z=0; shortE=0; edge=None;elen=None;conn_allow=0;conn_dis=0
    for l in opn(p):
        s=l.lstrip()
        if s.startswith('<edge '):
            edge=None if 'function="' in s else at(s,'id')
            if edge: o['edges']+=1; typ[at(s,'type') or 'none']+=1; elen=True
            else: elen=None
        elif s.startswith('<lane ') and edge:
            o['lanes']+=1
            a=at(s,'allow'); d=at(s,'disallow'); carok=(('passenger' in a.split()) if a is not None else ('passenger' not in (d or '').split()))
            if carok: o['car_lanes']+=1
            else: o['closed_to_cars']+=1
            speed[round(float(at(s,'speed'))*3.6)]+=1
            ln=float(at(s,'length'))
            if elen:
                if ln<7.5: shortE+=1
                elen=None
            sh=at(s,'shape') or ''
            if sh and len(sh.split(' ')[0].split(','))==3: z+=1
        elif s.startswith('<junction '):
            t=at(s,'type')
            if t!='internal': jt[t]+=1
        elif s.startswith('<tlLogic '):
            if cur is not None: cyc[round(sum(dur))]+=1; pat['-'.join(str(round(x)) for x in dur)]+=1
            cur=at(s,'id'); dur=[]; tt[at(s,'type')]+=1; off=at(s,'offset')
            if off and float(off)!=0: o['tls_offset_nonzero']+=1
            o['tls']+=1
        elif s.startswith('<phase ') and cur is not None:
            dur.append(float(at(s,'duration')))
            a,b=at(s,'minDur'),at(s,'maxDur')
            if a and b and a!=b: minmax[f'{float(a):g}-{float(b):g}']+=1
        elif s.startswith('<connection '):
            if ' allow="' in s: conn_allow+=1
            if ' disallow="' in s: conn_dis+=1
    if cur is not None: cyc[round(sum(dur))]+=1; pat['-'.join(str(round(x)) for x in dur)]+=1
    o.update(edges_under_7_5m=shortE,lanes_with_z=z,conn_allow=conn_allow,conn_disallow=conn_dis)
    return dict(o,junctions=dict(jt),tls_types=dict(tt),cycle_top=cyc.most_common(6),pattern_top=pat.most_common(4),green_limits_top=minmax.most_common(4),speed_kmh_lanes_top=speed.most_common(8),type_top=typ.most_common(10))
def routes(p):
    hours=[0]*30; o=C.Counter(); vt={}; defs={}; lane=C.Counter(); sp=C.Counter(); typ=C.Counter(); dtimes=[]; rev=0;rev1=0;nroutes=0
    weights=C.Counter(); routecount=C.Counter(); first=C.Counter()
    cur=None
    for l in opn(p):
        s=l.lstrip()
        if s.startswith('<vType'): vt[at(s,'id')]={k:at(s,k) for k in ['vClass','accel','decel','sigma','tau','length','minGap','maxSpeed','speedDev','speedFactor','carFollowModel','probability'] if at(s,k)}
        elif s.startswith('<route ') and at(s,'id'):
            defs[at(s,'id')]=at(s,'edges'); 
        elif s.startswith('<vehicle ') or s.startswith('<trip '):
            o['vehicles']+=1; d=float(at(s,'depart') or 0); hours[min(int(d//3600),29)]+=1
            lane[at(s,'departLane')]+=1; sp[at(s,'departSpeed')]+=1; typ[at(s,'type')]+=1
            r=at(s,'route')
            if r: routecount[r]+=1
            cur=r
        elif s.startswith('<flow '):
            o['flows']+=1
            typ[at(s,'type')]+=1
        elif s.startswith('<stop '): o['stops']+=1
        elif s.startswith('<route ') and at(s,'edges'):
            e=at(s,'edges').split(); routecount['#inline']+=0; nroutes+=1
            sh=[i for i in range(len(e)-1) if e[i+1]==('-'+e[i] if not e[i].startswith('-') else e[i][1:])]
            if sh: rev+=1
            if sh and sh[0]==0: rev1+=1
            first[e[0]]+=1
    rv=0;rv1=0;fo=C.Counter();n=0
    for r,c in routecount.items():
        if r in defs:
            e=defs[r].split(); n+=c
            sh=[i for i in range(len(e)-1) if e[i+1]==('-'+e[i] if not e[i].startswith('-') else e[i][1:])]
            if sh: rv+=c
            if sh and (sh[0]==0 or sh[-1]==len(e)-2): rv1+=c
            fo[e[0]]+=c
    res=dict(o,hours=hours,vtypes=vt,depart_lane=lane.most_common(3),depart_speed=sp.most_common(3),types=typ.most_common(8),inline_routes=nroutes,inline_reversal=rev,inline_first_reversal=rev1)
    if n:
        res.update(defined_route_vehicles=n,routes_used=len(routecount),reversal_vehicles=rv,reversal_at_trip_end_vehicles=rv1,distinct_origin_edges=len(fo),top100_origin_share=sum(x for _,x in fo.most_common(100))/n,top1000_route_share=sum(x for _,x in routecount.most_common(1000))/n)
    else:
        res.update(distinct_origin_edges=len(first),top100_origin_share=(sum(x for _,x in first.most_common(100))/max(1,nroutes)))
    return res
out={'nets':{},'routes':{}}
for k,p in NETS.items():
    out['nets'][k]=net(p); print(k,flush=True); json.dump(out,open(sys.argv[1],'w'),indent=1)
for k,p in ROUTES.items():
    out['routes'][k]=routes(p); print(k,flush=True); json.dump(out,open(sys.argv[1],'w'),indent=1)
json.dump(out,open(sys.argv[1],'w'),indent=1)
