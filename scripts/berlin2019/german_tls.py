#!/usr/bin/env python3
"""Report 11's signal program generator, adapted to Germany. Rewrites every tlLogic in a SUMO net.
  german_tls.py NET ROUTES.gz - OUT.net.xml OUT.json MODE [PEAK_FROM PEAK_TO]; env CFIX=cycle for coordinated and multi-node, CISO=floor for isolated.
MODE: demand uses turning flows from ROUTES (MATSim, not validation counts), nodemand uses lane counts only.
Changed from Sweden: no register, so signals and arrows come from the map; RiLSA values from general knowledge, the guideline itself was not opened:
yellow 3/4/5 s at 50/60/70 km/h, clearance speeds 10 m/s out and 11.1 m/s in, walking 1.2 m/s. Cycles snap to 70/90/110 s:
the Senate gives 90/100/110 s on one Berlin corridor and Hamburg runs 90 s by day (report 26). Stdlib only, run with python3 -I."""
import sys,gzip,json,re,math,collections,random
from xml.etree.ElementTree import iterparse,fromstring
net,routes,reg,outnet,outjson,mode=sys.argv[1:7]
P0,P1=(float(sys.argv[7]),float(sys.argv[8])) if len(sys.argv)>8 else (25200.,32400.)
SAT=1900.;KMH=3.6
import os
CFIX=float(os.environ.get('CFIX',0));CISO=float(os.environ.get('CISO',0))
PROT=collections.Counter()
VS={30:8.,40:10.,50:12.,60:14.,70:15.}
def tsfs_speed(v):
    k=v*KMH
    for a in (30,40,50,60):
        if k<=a+2:return VS[a]
    return VS[70]
E={};L=collections.defaultdict(list);T={};J={}
for _,el in iterparse(net,events=('end',)):
    t=el.tag
    if t=='edge':
        if el.get('function') is None:
            ls=[(l.get('id'),float(l.get('speed')),float(l.get('length')),l.get('shape'),l.get('allow'),l.get('disallow'),float(l.get('width') or 3.2)) for l in el.findall('lane')]
            E[el.get('id')]=dict(frm=el.get('from'),to=el.get('to'),lanes=ls,prio=int(el.get('priority') or 0),name=el.get('name'))
        else:
            E[el.get('id')]=dict(internal=True,len=float(el.find('lane').get('length')) if el.find('lane') is not None else 0.)
        el.clear()
    elif t=='connection':
        if el.get('tl'):L[el.get('tl')].append(dict(fr=el.get('from'),to=el.get('to'),fl=int(el.get('fromLane')),tl=int(el.get('toLane')),d=el.get('dir'),i=int(el.get('linkIndex')),via=el.get('via')))
        el.clear()
    elif t=='tlLogic':
        T[el.get('id')]=dict(n=len(el.find('phase').get('state')),type=el.get('type'));el.clear()
    elif t=='junction':
        J[el.get('id')]=(float(el.get('x')),float(el.get('y')));el.clear()
print('net',len(E),'controllers',len(T),'links',sum(map(len,L.values())),flush=True)
LANE={l[0]:l for e in E.values() if not e.get('internal') for l in e['lanes']}
def vialen(v):
    if not v:return 8.
    l=LANE.get(v)
    if l:return l[2]
    return E.get(v.rsplit('_',1)[0],{}).get('len',8.)
# flows
Q=collections.Counter();EQ=collections.Counter()
if mode=='demand':
    hours=(P1-P0)/3600.;n=0
    op=gzip.open(routes,'rt') if routes.endswith('.gz') else open(routes)
    R={}
    for line in op:
        m=re.search(r'<vehicle [^>]*depart="([\d.]+)"',line)
        if m and P0-600<=float(m.group(1))<=P1:
            r=re.search(r' edges="([^"]*)"',line)
            if r:
                e=r.group(1).split()
                for a,b in zip(e,e[1:]):Q[(a,b)]+=1
                for a in e:EQ[a]+=1
                n+=1
    op.close()
    Q=collections.Counter({k:v/hours for k,v in Q.items()});EQ=collections.Counter({k:v/hours for k,v in EQ.items()})
    print('flows from',n,'vehicles',flush=True)
# register: left arrow counts per installation
ARROW=collections.defaultdict(set);PED=collections.Counter();FCOUNT=collections.defaultdict(set)
for f in []:
    p=f['properties'];i=str(p.get('anläggnings-id')).lstrip('0');n=p.get('namn') or '';ty=p.get('typ') or ''
    m=re.search(r'\bF(\d+)',n)
    if m:
        FCOUNT[i].add(m.group(1))
        if 'v-pil' in ty:ARROW[i].add(m.group(1))
    if re.search(r'\bG\d',n):PED[i]+=1
def bearing(eid):
    s=E[eid]['lanes'][0][3].split();a=tuple(map(float,s[-2].split(',')));b=tuple(map(float,s[-1].split(',')))
    return math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
def weight(k):
    if mode=='demand':return Q.get((k['fr'],k['to']),0.)
    return 0.
def capacity_lanes(links):return max(1,len({k['fl'] for k in links}))
def stages_for(node,links,arrows,speed_all):
    """returns ordered stage list; each stage is a set of (link index,state char)"""
    app=collections.defaultdict(list)
    for k in links:app[k['fr']].append(k)
    def aq(a):
        if mode=='demand':return sum(weight(k) for k in app[a])+1
        return len({k['fl'] for k in app[a]})*(1+E[a]['prio']/20.)
    order=sorted(app,key=lambda a:-aq(a));used=set();axes=[]
    for a in order:
        if a in used:continue
        used.add(a);best=None;bd=45
        for b in order:
            if b in used:continue
            d=abs(((bearing(a)-bearing(b)+180)%360)-180)
            d=abs(180-d)
            if d<bd:bd=d;best=b
        if best:used.add(best);axes.append((a,best))
        else:axes.append((a,))
    stages=[]
    left=lambda k:k['d'] in('l','L','t')
    for ax in axes:
        lefts=[k for a in ax for k in app[a] if left(k)]
        own={a:{k['fl'] for k in app[a] if left(k)}-{k['fl'] for k in app[a] if not left(k)} for a in ax}
        vmax=max(E[a]['lanes'][0][1] for a in ax)
        protect=False;split=False
        if len(ax)==2 and lefts:
            nl=[len(own[a]) for a in ax]
            q_l=sum(weight(k) for k in lefts) if mode=='demand' else 0
            q_opp=sum(weight(k) for a in ax for k in app[a] if not left(k)) if mode=='demand' else 0
            if vmax>=16.5 or max(nl)>=2:protect=True      # TSFS 2014:30 3 kap 18 s, SKL dual lanes
            elif arrows>0 and any(nl):protect=True;arrows-=sum(1 for x in nl if x)   # register: Fordon 3-skens, v-pil
            elif any(nl) and q_l>=200 and q_opp>=500:protect=True
            PROT['left_axes']+=1;PROT['protected']+=protect
            if protect and not all(nl):split=True          # no left pocket on one side: each approach alone
        if split:
            for a in ax:stages.append(({k['i']:'G' for k in app[a]},[a],[]))
        elif protect:
            stages.append(({k['i']:'G' for k in lefts},[a for a in ax if own[a]],lefts))
            rest=[k for a in ax for k in app[a] if not left(k)]
            s={k['i']:'G' for k in rest}
            for k in lefts:
                if k['fl'] not in own[k['fr']]:s[k['i']]='g'
            stages.append((s,list(ax),rest))
        else:
            s={}
            for a in ax:
                for k in app[a]:s[k['i']]='g' if (left(k) and len(ax)==2) else 'G'
            stages.append((s,list(ax),[k for a in ax for k in app[a]]))
    return stages,axes,arrows
def crit(st,links):
    """flow ratio of a stage: worst approach per lane"""
    y=0.
    sel={i for i in st[0]}
    per=collections.defaultdict(list)
    for k in links:
        if k['i'] in sel:per[k['fr']].append(k)
    for a,ks in per.items():
        n=len({k['fl'] for k in ks})
        if mode=='demand':q=sum(weight(k) for k in ks)
        else:q=n*SAT*.28*(1+E[a]['prio']/30.)
        y=max(y,q/(n*SAT))
    return y
def clearance(a,links):
    """TSFS 2014:30 2 kap 4 s: ts=(s_ut+l)/v_ut-s_in/v_in, l=6 m, conflict point at mid junction"""
    ls=[k for k in links if k['fr'] in a and k['d']=='s'] or [k for k in links if k['fr'] in a]
    s=max((vialen(k['via']) for k in ls),default=10.)
    ts=(s*.6+6)/10.-(s*.3)/11.1
    return max(1.,math.ceil(ts*2)/2)
def yellow(a):
    v=max(E[x]['lanes'][0][1] for x in a)
    return 5. if v>=18 else 4. if v>=15 else 3.
def cross_width(a,links):
    oth=[E[k['fr']] for k in links if k['fr'] not in a]
    seen=set();w=0.
    for k in links:
        if k['fr'] not in a and k['fr'] not in seen:
            seen.add(k['fr']);w+=sum(l[6] for l in E[k['fr']]['lanes'])
    return w
class Plan:pass
def plan_node(node,links,arrows,cmax,ped):
    st,axes,arrows=stages_for(node,links,arrows,None)
    pl=Plan();pl.links=links;pl.node=node;rows=[]
    speeds=[E[k['fr']]['lanes'][0][1] for k in links]
    if len(st)==1:                                    # one axis, nothing crossing but people: a crossing on a road
        s=st[0];w=sum(l[6] for a in {k['fr'] for k in links} for l in E[a]['lanes'])
        yv=yellow(s[1]);walk=max(5.,w/1.2)
        pl.C=70.;pl.rows=[dict(s=s[0],g=70.-yv-walk-1,mn=20.,y=yv,r=walk+1,kind='veh')];pl.crossing=True;pl.arrows=arrows
        return pl
    tot=0.;ys=[]
    for s in st:
        ys.append(max(crit(s,links),.02))
    Y=sum(ys);lost=0.;fl=[]
    for s in st:
        yv=yellow(s[1]);ts=clearance(s[1],links);lost+=yv+ts
        floor=5.
        if ped and len(s[2])>0 and any(k['d']=='s' for k in s[2]):floor=max(floor,cross_width(s[1],links)/1.2)
        floor=min(floor,28.)
        fl.append(floor);rows.append(dict(s=s[0],y=yv,r=ts,mn=floor,kind='stage'))
    C0=(1.5*lost+5)/max(.05,1-min(Y,.9))
    C=min(cmax,max(60. if len(st)>2 else 50.,C0))
    C=max(C,sum(fl)+lost+2)
    avail=C-lost
    gs=[y/Y*avail for y in ys]
    # raise floors by taking from the rest
    for _ in range(4):
        low=[i for i,g in enumerate(gs) if g<fl[i]]
        if not low:break
        need=sum(fl[i]-gs[i] for i in low);free=[i for i in range(len(gs)) if i not in low]
        tf=sum(gs[i]-fl[i] for i in free) or 1
        for i in low:gs[i]=fl[i]
        for i in free:gs[i]-=need*(gs[i]-fl[i])/tf
    for r,g in zip(rows,gs):r['g']=g
    pl.C=C;pl.rows=rows;pl.crossing=False;pl.arrows=arrows;pl.lost=lost;pl.Y=Y;pl.cmax=cmax
    return pl
def is_inner(p):return True
plans={};stat=collections.Counter()
for t,links in L.items():
    node=collections.defaultdict(list)
    for k in links:node[E[k['fr']]['to']].append(k)
    S=t[0]=='S' and t[1:].isdigit();ar=len(ARROW.get(t[1:],())) if S else 0;ped=PED.get(t[1:],1) if S else 1
    p0=next(iter(node));inner=is_inner(J[p0]);cmax=110.
    nodes={}
    for n,ls in sorted(node.items(),key=lambda x:-len(x[1])):
        pl=plan_node(n,ls,ar,cmax,ped>0);ar=pl.arrows;nodes[n]=pl
    plans[t]=nodes
    stat['arrows_left_over']+=max(ar,0);stat['multi' if len(nodes)>1 else 'single']+=1
# coordinate: same cycle along strong links under 350 m, classic systems up to about 21 controllers (Matsis)
par={t:t for t in T}
def fd(a):
    while par[a]!=a:par[a]=par[par[a]];a=par[a]
    return a
node2t={n:t for t,ns in plans.items() for n in ns};links_between=[]
for e,v in E.items():
    if v.get('internal'):continue
    a,b=node2t.get(v['frm']),node2t.get(v['to'])
    if a and b and a!=b and v['lanes'][0][2]<350:
        w=EQ.get(e,0.) if mode=='demand' else (len(v['lanes'])*(v['prio']+1))
        links_between.append((w,a,b,e))
links_between.sort(key=lambda x:-x[0])
size=collections.Counter({t:1 for t in T});thr=sorted(x[0] for x in links_between)[int(len(links_between)*.55)] if links_between else 0
for w,a,b,e in links_between:
    if w<thr:break
    ra,rb=fd(a),fd(b)
    if ra!=rb and size[ra]+size[rb]<=21:par[ra]=rb;size[rb]+=size[ra]
groups=collections.defaultdict(list)
for t in T:groups[fd(t)].append(t)
coord={t for g in groups.values() if len(g)>=2 for t in g}
stat['coordinated']=len(coord);stat['groups']=sum(len(g)>=2 for g in groups.values())
snap=lambda c:next((x for x in (70.,90.,110.) if c<=x),110.)
prog={};offs={}
rng=random.Random(11)
adj=collections.defaultdict(list)
for w,a,b,e in links_between:adj[a].append((w,b,e))
for g in groups.values():
    Cs=max(pl.C for t in g for pl in plans[t].values())
    C=snap(Cs) if len(g)>=2 else Cs
    if CFIX and (len(g)>=2 or len(plans[g[0]])>1):C=CFIX
    elif CFIX and not next(iter(plans[g[0]].values())).crossing:C=max(C,CISO)
    if len(g)>=2:
        start=max(g,key=lambda t:sum(w for w,b,e in adj[t]));offs[start]=0.;todo=[start];gs=set(g)
        while todo:
            a=todo.pop()
            for w,b,e in sorted(adj[a],key=lambda x:-x[0]):
                if b in gs and b not in offs:
                    v=E[e]['lanes'][0]
                    offs[b]=(offs[a]+v[2]/v[1])%C;todo.append(b)
        for t in g:offs.setdefault(t,rng.uniform(0,C))
    for t in g:prog[t]=C
def stretch(pl,C):
    if pl.crossing:
        pl.rows[0]['g']+=C-pl.C;pl.C=C;return
    extra=C-pl.C
    if extra<=0:return
    ws=[r['g'] for r in pl.rows];tw=sum(ws)
    for r,w in zip(pl.rows,ws):r['g']+=extra*w/tw
    pl.C=C
def timeline(pl,C,shift):
    """link index -> list of chars, one per 0.5 s"""
    n=int(round(C));tl={}
    idx=[k['i'] for k in pl.links]
    for i in idx:tl[i]=['r']*n
    t=0.
    for r in pl.rows:
        a=int(round(t));b=int(round(t+r['g']));y=int(round(t+r['g']+r['y']))
        for i,c in r['s'].items():
            for j in range(a,b):tl[i][(j+int(shift))%n]=c
            for j in range(b,y):tl[i][(j+int(shift))%n]='y'
        t+=r['g']+r['y']+r['r']
    return tl
blocks={};sumv=[]
for t,nodes in plans.items():
    C=prog[t];n=T[t]['n']
    single=len(nodes)==1 and t not in coord
    if single:
        pl=next(iter(nodes.values()))
        if not pl.crossing:
            stretch(pl,C)
            sfl=sum(r['mn'] for r in pl.rows);av=pl.cmax-pl.lost;run=C-pl.lost
            ph=[]
            for r in pl.rows:
                st=['r']*n
                for i,c in r['s'].items():st[i]=c
                mx=r['mn']+(r['g']-r['mn'])*max(0.,av-sfl)/max(1.,run-sfl) if run>sfl else r['g']
                ph.append(f'        <phase duration="{r["g"]:.0f}" state="{"".join(st)}" minDur="{r["mn"]:.0f}" maxDur="{max(mx,r["mn"]+1):.0f}"/>')
                ph.append(f'        <phase duration="{r["y"]:.0f}" state="{"".join(st).replace("G","y").replace("g","y")}"/>')
                ph.append(f'        <phase duration="{math.ceil(r["r"]):.0f}" state="{"r"*n}"/>')
            blocks[t]=f'    <tlLogic id="{t}" type="actuated" programID="0" offset="0">\n'+'\n'.join(ph)+'\n    </tlLogic>\n'
            stat['actuated']+=1;sumv.append(C);continue
    # static: multi-node, crossings, coordinated. Common cycle, one timeline per node.
    for pl in nodes.values():stretch(pl,C)
    N=int(round(C));tl={}
    main=max((p for p in nodes.values() if not p.crossing),key=lambda p:len(p.links),default=None)
    shift={};
    if main:
        shift[main.node]=0.;todo=[main.node]
        while todo:
            a=todo.pop()
            for e,v in E.items() if False else []:pass
    for n0,pl in nodes.items():
        if pl.crossing:continue
        sh=shift.get(n0)
        if sh is None:
            sh=0.
            if main:
                for k in main.links:
                    if E[k['fr']]['frm']==n0:sh=-E[k['fr']]['lanes'][0][2]/max(E[k['fr']]['lanes'][0][1],1.);break
                    if E[k['to']]['to']==n0:sh=E[k['to']]['lanes'][0][2]/max(E[k['to']]['lanes'][0][1],1.);break
        tl.update(timeline(pl,C,sh))
    # crossings mirror the movement next to them, otherwise run alone
    for n0,pl in nodes.items():
        if not pl.crossing:continue
        bytarget={};done=False
        for k in pl.links:
            feeder=[o for o in L[t] if o['fr']==k['to'] and o['i'] in tl]
            upstream=[o for o in L[t] if o['to']==k['fr'] and o['i'] in tl]
            src=feeder or upstream
            if src:
                arr=['r']*N
                for j in range(N):
                    for o in src:
                        if tl[o['i']][j] in 'Gg':arr[j]='G';break
                        if tl[o['i']][j]=='y' and arr[j]=='r':arr[j]='y'
                tl[k['i']]=arr;done=True
            else:done=False
        if not done or any(k['i'] not in tl for k in pl.links):
            tmp=timeline(pl,C,rng.uniform(0,C))
            for i,v in tmp.items():tl.setdefault(i,v)
    ph=[]
    cur=None;d=0
    for j in range(N):
        s=''.join(tl[i][j] if i in tl else 'r' for i in range(n))
        if s!=cur:
            if cur is not None:ph.append((d,cur))
            cur=s;d=0
        d+=1
    ph.append((d,cur))
    of=offs.get(t,rng.uniform(0,C))
    blocks[t]=f'    <tlLogic id="{t}" type="static" programID="0" offset="{of:.0f}">\n'+'\n'.join(f'        <phase duration="{a:.0f}" state="{b}"/>' for a,b in ph)+'\n    </tlLogic>\n'
    stat['static']+=1;sumv.append(C)
c=collections.Counter(round(x/10)*10 for x in sumv)
print(PROT,stat,'cycle hist',sorted(c.items()),flush=True)
# writes net, replacing the tlLogic blocks
n=0
with open(net) as f,open(outnet,'w') as o:
    skip=False
    for line in f:
        if '<tlLogic ' in line:
            m=re.search(r' id="([^"]*)"',line).group(1);o.write(blocks[m]);skip=True;n+=1;continue
        if skip:
            if '</tlLogic>' in line:skip=False
            continue
        o.write(line)
print('rewrote',n)
# screen: green share and v/c for every signal link, generated against new
def shares(path):
    res={}
    for _,el in iterparse(path,events=('end',)):
        if el.tag=='tlLogic':
            ph=[(float(p.get('duration')),p.get('state'),p.get('maxDur')) for p in el.findall('phase')]
            nom=sum(a for a,b,c in ph);top=sum(float(c) if c else a for a,b,c in ph)
            nl=len(ph[0][1]);g=[0.]*nl;gm=[0.]*nl
            for a,s,c in ph:
                for i,ch in enumerate(s):
                    if ch in 'Gg':g[i]+=a;gm[i]+=float(c) if c else a
            res[el.get('id')]=dict(nom=nom,top=top,g=g,gm=gm,type=el.get('type'));el.clear()
        elif el.tag in('edge','connection','junction'):el.clear()
    return res
A=shares(net);B=shares(outnet)
rows=[]
for t,links in L.items():
    per=collections.defaultdict(list)
    for k in links:per[(k['fr'],k['fl'])].append(k)
    for (e,fl),ks in per.items():
        q=sum(Q.get((k['fr'],k['to']),0.)/max(1,len({x['fl'] for x in links if x['fr']==k['fr'] and x['to']==k['to']})) for k in ks)
        ga=max(A[t]['g'][k['i']] for k in ks);gb=max(B[t]['g'][k['i']] for k in ks)
        ca=SAT*ga/A[t]['nom'];cb=SAT*gb/max(B[t]['nom'],1)
        rows.append((q,ca,cb,len(E[e]['lanes'][0][2:3])))
over=lambda i,thr=1.:sum(1 for r in rows if r[0]>thr*r[i] and r[0]>50)
Tt=dict(stat=dict(stat),cycles=sorted(c.items()),lanes=len(rows),over_gen=over(1),over_new=over(2),heavy=sum(1 for r in rows if r[0]>50))
Tt['gen_top_cycle_p50']=sorted(x['top'] for x in A.values())[len(A)//2];Tt['gen_top_cycle_p90']=sorted(x['top'] for x in A.values())[int(.9*len(A))]
Tt['new_top_cycle_p50']=sorted(x['top'] for x in B.values())[len(B)//2];Tt['new_top_cycle_p90']=sorted(x['top'] for x in B.values())[int(.9*len(B))];Tt['new_top_cycle_max']=max(x['top'] for x in B.values())
print(Tt);json.dump(Tt,open(outjson,'w'),indent=0)
