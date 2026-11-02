# First-order paper screen of one hour of route flows against map capacity. No simulation.
import sys, gzip, csv, json, math, collections, itertools
import xml.etree.ElementTree as ET
NET,LOAD,OUT=sys.argv[1:4]
edges={}; jn={}; conns=[]; tls={}
for ev,el in ET.iterparse(NET,events=('end',)):
    t=el.tag
    if t=='edge':
        if el.get('function')!='internal':
            ls=el.findall('lane')
            car=[l for l in ls if ('passenger' in (l.get('allow') or 'passenger')) and 'passenger' not in (l.get('disallow') or '')]
            l0=(car or ls)[0]
            edges[el.get('id')]=dict(type=(el.get('type') or '').replace('highway.',''),to=el.get('to'),frm=el.get('from'),name=el.get('name') or '',nlanes=len(car),L=float(l0.get('length')),v=float(l0.get('speed')),carlanes={l.get('id').rsplit('_',1)[1] for l in car})
        el.clear()
    elif t=='junction':
        if el.get('type')!='internal':
            rq={int(r.get('index')):(r.get('response'),r.get('foes')) for r in el.findall('request')}
            jn[el.get('id')]=dict(type=el.get('type'),x=float(el.get('x')),y=float(el.get('y')),il=(el.get('intLanes') or '').split(),rq=rq)
        el.clear()
    elif t=='tlLogic':
        tls[el.get('id')]=[(float(p.get('duration')),p.get('state')) for p in el.findall('phase')]
        el.clear()
    elif t=='connection':
        if el.get('from') in edges:
            conns.append(dict(frm=el.get('from'),to=el.get('to'),fl=el.get('fromLane'),via=el.get('via'),tl=el.get('tl'),li=el.get('linkIndex'),dir=el.get('dir'),state=el.get('state')))
        el.clear()
flow=collections.defaultdict(dict)
with gzip.open(LOAD,'rt') as f:
    for r in csv.DictReader(f):
        flow[int(r['h'])][(r['edge'],r['next'])]=float(r['q'])
def run(h,scale,s_through,s_right,s_left,lost=4.0):
    Q={k:v*scale for k,v in flow[h].items()}
    # index connection → movement
    bylink={}  # (junction, reqindex) -> movement
    mv=collections.defaultdict(list)
    for c in conns:
        if edges.get(c['to']) is None: continue
        if c['fl'] not in edges[c['frm']]['carlanes']: continue
        mv[(c['frm'],c['to'])].append(c)
        J=edges[c['frm']]['to']; j=jn.get(J)
        if j and c['via'] in j['il']:
            bylink[(J,j['il'].index(c['via']))]=(c['frm'],c['to'])
    def conflict(c):
        J=edges[c['frm']]['to']; j=jn[J]
        if c['via'] not in j['il']: return {}
        i=j['il'].index(c['via'])
        if i not in j['rq']: return {}
        resp=j['rq'][i][0]; n=len(resp); out=set()
        for k in range(n):
            if resp[n-1-k]=='1':
                m=bylink.get((J,k))
                if m: out.add(m)
        return out
    def freecap(e):
        v=edges[e]['v']; T=1.4; s=7.5
        return 3600/(T+s/v)
    # movement capacity per lane
    res=[]; 
    byedge=collections.defaultdict(list)
    for m,cs in mv.items(): byedge[m[0]].append(m)
    for e,ms in byedge.items():
        ed=edges[e]; j=jn.get(ed['to'])
        if not j: continue
        lanes=ed['carlanes']
        cap={}; lanesof={}
        kind=j['type']
        anyq=sum(Q.get(m,0) for m in ms)
        for m in ms:
            cs=mv[m]; lanesof[m]={c['fl'] for c in cs}
            c0=cs[0]; d=c0['dir']
            s_dir={'r':s_right,'R':s_right,'l':s_left,'L':s_left,'t':s_left}.get(d,s_through)
            s_dir=min(s_dir,freecap(e))
            if c0['tl']:
                ph=tls[c0['tl']]; C=sum(p[0] for p in ph); li=int(c0['li'])
                cap_h=0; lostused=False
                foes=conflict(c0)
                g_any=sum(p[0] for p in ph if p[1][li] in 'Gg')
                for p in ph:
                    st=p[1][li]
                    if st=='G': cap_h+=p[0]/C*s_dir
                    elif st=='g':
                        qop=0
                        for f in foes:
                            fl=mv[f][0]
                            if fl['tl'] and p[1][int(fl['li'])] in 'G':
                                # opposing flow concentrated in its own green
                                gf=sum(q[0] for q in ph if q[1][int(fl['li'])] in 'Gg')
                                qop+=Q.get(f,0)*C/max(gf,1)
                        tf,tg=2.8,5.5
                        cap_h+=p[0]/C*min(s_dir,3600/tf*math.exp(-qop/3600*(tg-tf/2)))
                # lost time per green stretch
                nst=sum(1 for a,b in zip(ph,ph[1:]+ph[:1]) if a[1][li] not in 'Gg' and b[1][li] in 'Gg')
                eff=max(g_any+3*nst-lost*nst,0)/max(g_any,1)
                cap[m]=cap_h*min(eff,1)
                kindm='signal'
            else:
                st=c0['state']; foes=conflict(c0)
                qp=sum(Q.get(f,0) for f in foes)
                if st in('M','O') and qp==0:
                    cap[m]=s_dir; kindm='major'
                elif st=='=':
                    C0=3600/3.9
                    cap[m]=max(C0*(1-qp/C0),30); kindm='rbl'
                else:
                    tg,tf={'r':(5.9,3.0),'R':(5.9,3.0),'l':(6.5,3.2) if st in('m','w') else (5.5,2.8),'L':(6.5,3.2) if st in('m','w') else (5.5,2.8),'s':(6.7,3.3),'S':(6.7,3.3)}.get(d,(6.7,3.3)) if not isinstance({'r':1}.get(d),tuple) else (6.7,3.3)
                    if st in('M',) : tg,tf=5.5,2.8
                    cap[m]=max(min(s_dir,3600/tf*math.exp(-qp/3600*(tg-tf/2))),15); kindm='giveway'
            res.append(None)
        # Hall bound
        mlist=[m for m in ms if Q.get(m,0)>0]
        if not mlist: continue
        x=0; 
        for r in range(1,len(mlist)+1):
            for S in itertools.combinations(mlist,r):
                N=set().union(*[lanesof[m] for m in S])
                need=sum(Q[m]/max(cap[m],1) for m in S)
                x=max(x,need/max(len(N),1))
        qt=sum(Q[m] for m in mlist)
        over=qt*(1-1/x) if x>1 else 0
        # storage and time to spill
        stor=ed['nlanes']*ed['L']/7.5
        cmin=qt/x if x>0 else 0
        t_spill=stor/over*60 if over>0 else None
        k='signal' if mv[mlist[0]][0]['tl'] else ('rbl' if j['type']=='right_before_left' else 'priority')
        yield dict(edge=e,name=ed['name'],type=ed['type'],kind=k,x=x,q=qt,over=over,L=ed['L'],lanes=ed['nlanes'],storage=stor,t_spill_min=t_spill)
rows={}
for scale,lab in ((0.5,'50%'),(1.0,'100%')):
  for sset,sl in (((1800,1285,1600),'s1800'),((1636,1285,1500),'s1636'),((1900,1900,1900),'s1900flat')):
    R=list(run(7,scale,*sset))
    rows[(lab,sl)]=R
    print(f'--- {lab} demand, 07-08h, {sl}')
    for k in ('signal','priority','rbl'):
        S=[r for r in R if r['kind']==k]
        o=[r for r in S if r['x']>1]
        print(f" {k:9s} loaded approaches {len(S):5d}  x>1 {len(o):4d}  x>0.85 {sum(1 for r in S if r['x']>0.85):4d}  overflow veh/h {sum(r['over'] for r in o):8.0f}  median x {sorted(r['x'] for r in S)[len(S)//2]:.2f}")
    allo=[r for r in R if r['x']>1]
    print(f" TOTAL overflow veh/h {sum(r['over'] for r in allo):.0f}; approaches over {len(allo)}; spill within 15 min {sum(1 for r in allo if r['t_spill_min'] and r['t_spill_min']<15)}; within 5 min {sum(1 for r in allo if r['t_spill_min'] and r['t_spill_min']<5)}")
for lab in ('50%','100%'):
    R=sorted(rows[(lab,'s1800')],key=lambda r:-r['over'])[:15]
    print('top overflow',lab)
    for r in R:
        print(f"  {r['edge'][:22]:22s} {r['name'][:24]:24s} {r['type'][:9]:9s} {r['kind'][:8]:8s} q={r['q']:6.0f} x={r['x']:5.2f} over={r['over']:6.0f} L={r['L']:5.0f} n={r['lanes']} spill={r['t_spill_min'] or 0:6.1f}min")
json.dump({f'{a}|{b}':v for (a,b),v in rows.items()},open(OUT,'w'))
