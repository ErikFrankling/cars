"""SUMO LC2013 at a lane end shaped like the I-80 ramp: a parallel lane of 204 m that has no connection onward. Measures the same quantities as the trajectory study.
Usage: courtesy_sumo.py NAME MAIN_VPH RAMP_VPH BOTTLENECK_SPEED(m/s) [SIGMA] [TELEPORT] [DURATION]"""
import sys,subprocess,os,pathlib,json,random
import xml.etree.ElementTree as ET
import numpy as np
name,main,ramp,vb=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),float(sys.argv[4])
sigma=float(sys.argv[5]) if len(sys.argv)>5 else 0.5
tele=int(sys.argv[6]) if len(sys.argv)>6 else 120
dur=int(sys.argv[7]) if len(sys.argv)>7 else 1800
W=pathlib.Path('research/truth/courtesy/sumo')/name; W.mkdir(parents=True,exist_ok=True)
(W/'n.nod.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="800" y="0"/><node id="c" x="1004" y="0"/><node id="d" x="1304" y="0"/><node id="e" x="1404" y="0"/><node id="f" x="2000" y="0"/></nodes>')
(W/'n.edg.xml').write_text(f'''<edges>
<edge id="up" from="a" to="b" numLanes="2" speed="20"/>
<edge id="merge" from="b" to="c" numLanes="2" speed="20"/>
<edge id="down" from="c" to="d" numLanes="1" speed="20"/>
<edge id="neck" from="d" to="e" numLanes="1" speed="{vb}"/>
<edge id="out" from="e" to="f" numLanes="1" speed="20"/>
</edges>''')
(W/'n.con.xml').write_text('<connections><connection from="up" to="merge" fromLane="0" toLane="0"/><connection from="up" to="merge" fromLane="1" toLane="1"/><connection from="merge" to="down" fromLane="1" toLane="0"/></connections>')
subprocess.run(['netconvert','-n',str(W/'n.nod.xml'),'-e',str(W/'n.edg.xml'),'-x',str(W/'n.con.xml'),'-o',str(W/'n.net.xml'),'--no-turnarounds','true','--no-internal-links','false'],check=True,capture_output=True)
(W/'r.rou.xml').write_text(f'''<routes>
<vType id="car" sigma="{sigma}" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1"/>
<route id="r" edges="up merge down neck out"/>
<flow id="ramp" type="car" route="r" begin="0" end="{dur}" vehsPerHour="{ramp}" departLane="0" departSpeed="max"/>
<flow id="main" type="car" route="r" begin="0" end="{dur}" vehsPerHour="{main}" departLane="1" departSpeed="max"/>
</routes>''')
r=subprocess.run(['sumo','-n',str(W/'n.net.xml'),'-r',str(W/'r.rou.xml'),'--fcd-output',str(W/'fcd.xml'),'--step-length','1','--time-to-teleport',str(tele),'--seed','7','--end',str(dur+1500),'--no-step-log','true','--statistic-output',str(W/'stat.xml'),'--collision-output',str(W/'coll.xml')],capture_output=True,text=True)
print(r.stderr[-800:])
tr={}
for ev,el in ET.iterparse(W/'fcd.xml',events=('end',)):
    if el.tag=='timestep':
        t=float(el.get('time'))
        for v in el:
            tr.setdefault(v.get('id'),[]).append((t,v.get('lane'),float(v.get('pos')),float(v.get('speed'))))
        el.clear()
L0='merge_0';L1='merge_1'
wait=[];passes=[];cross=[];stop=[];vc=[];rem=[]
by_t={}
for vid,x in tr.items():
    for t,l,p,s in x: by_t.setdefault(t,{}).setdefault(l,[]).append((p,vid))
nm=0;never=0
for vid,x in tr.items():
    if not vid.startswith('ramp'): continue
    y=[a for a in x if a[1]==L0]
    if not y: continue
    nm+=1
    i=[k for k,a in enumerate(x) if a[1]==L1]
    if not i: never+=1; wait.append(np.nan); continue
    tc=x[i[0]][0]; t0=y[0][0]; wait.append(tc-t0); stop.append(min(a[3] for a in y)<1.0); vc.append(x[i[0]][3]); rem.append(204-x[i[0]][2])
    # lag vehicles that got ahead while on the ramp lane
    seen=[];ps=0
    for t,l,p,s in y:
        o=sorted(by_t[t].get(L1,[]))
        lag=[q for q in o if q[0]<=p]
        if lag:
            if not seen or seen[-1]!=lag[-1][1]: seen.append(lag[-1][1])
    ahead_final={q[1] for q in sorted(by_t[tc].get(L1,[])) if q[0]>x[i[0]][2]}
    down=set()
    passes.append(sum(1 for z in seen[:-1] if z in ahead_final or z in {q[1] for tt in (tc,) for ll in ('down_0',) for q in by_t[tt].get(ll,[])}))
for vid,x in tr.items():
    y=[a for a in x if a[1]=='down_0']
    if y: cross.append((y[0][0],vid.startswith('ramp')))
cross.sort()
a=np.array([c[1] for c in cross],bool); idx=np.where(a)[0]; rl=np.diff(idx)-1 if len(idx)>1 else np.array([])
w=np.array(wait,float); wf=w[np.isfinite(w)]
root=ET.parse(W/'stat.xml').getroot()
tp=root.find('teleports'); veh=root.find('vehicles')
out=dict(name=name,main=main,ramp=ramp,neck=vb,sigma=sigma,teleport_after=tele,ramp_cars=nm,never_merged=never,wait=dict(p10=float(np.percentile(wf,10)),p50=float(np.percentile(wf,50)),p90=float(np.percentile(wf,90)),p99=float(np.percentile(wf,99)),max=float(wf.max())),
 passes={int(k):int((np.array(passes)==k).sum()) for k in sorted(set(passes))},stopped=float(np.mean(stop)),v_cross_p50=float(np.median(vc)),rem_cross_p50=float(np.median(rem)),main_between_ramp={int(k):int((rl==k).sum()) for k in range(0,8)},over7=int((rl>7).sum()),rl_mean=float(rl.mean()) if len(rl) else None,
 flow_vph=float(len(cross)/dur*3600),teleports=dict(tp.attrib) if tp is not None else {},vehicles=dict(veh.attrib) if veh is not None else {},collisions=(W/'coll.xml').read_text().count('<collision '))
(W/'result.json').write_text(json.dumps(out,indent=1)); print(json.dumps(out))
os.remove(W/'fcd.xml')
