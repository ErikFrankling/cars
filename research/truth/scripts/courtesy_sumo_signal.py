"""SUMO LC2013 on short signalised approaches with turn lanes, the shape where wrong-lane cars pile up. Usage: NAME APPROACH_M TOTAL_VPH SPILL(0|1) [SEED] [TELE] [CF]"""
import sys,subprocess,pathlib,json,random
import xml.etree.ElementTree as ET
import numpy as np
name,La,vph,spill=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
seed=int(sys.argv[5]) if len(sys.argv)>5 else 7
tele=int(sys.argv[6]) if len(sys.argv)>6 else 120
W=pathlib.Path('research/truth/courtesy/sumo')/name; W.mkdir(parents=True,exist_ok=True)
(W/'n.nod.xml').write_text(f'''<nodes><node id="a" x="0" y="0"/><node id="b" x="150" y="0"/><node id="c" x="{150+La}" y="0" type="traffic_light" tl="c"/>
<node id="l" x="{150+La}" y="300"/><node id="t" x="{450+La}" y="0"/><node id="r" x="{150+La}" y="-300"/>
<node id="t2" x="{750+La}" y="0"/></nodes>''')
neck=2.0 if spill else 13.9
(W/'n.edg.xml').write_text(f'''<edges><edge id="up" from="a" to="b" numLanes="3" speed="13.9"/><edge id="app" from="b" to="c" numLanes="3" speed="13.9"/>
<edge id="L" from="c" to="l" numLanes="1" speed="13.9"/><edge id="T" from="c" to="t" numLanes="1" speed="13.9"/><edge id="R" from="c" to="r" numLanes="1" speed="13.9"/><edge id="T2" from="t" to="t2" numLanes="1" speed="{neck}"/></edges>''')
(W/'n.con.xml').write_text('<connections><connection from="up" to="app" fromLane="0" toLane="0"/><connection from="up" to="app" fromLane="1" toLane="1"/><connection from="up" to="app" fromLane="2" toLane="2"/><connection from="app" to="R" fromLane="0" toLane="0"/><connection from="app" to="T" fromLane="1" toLane="0"/><connection from="app" to="L" fromLane="2" toLane="0"/></connections>')
subprocess.run(['netconvert','-n',str(W/'n.nod.xml'),'-e',str(W/'n.edg.xml'),'-x',str(W/'n.con.xml'),'-o',str(W/'n.net.xml'),'--no-turnarounds','true','--tls.green.time','40','--tls.yellow.time','3'],check=True,capture_output=True)
# netconvert gives a lone approach only 5 s of red: force 40 s green and 50 s red, as in the prototype
tl=ET.parse(W/'n.net.xml').getroot().find('tlLogic'); ln=len(tl.find('phase').get('state'))
(W/'tl.add.xml').write_text(f'<additional><tlLogic id="c" type="static" programID="x" offset="0"><phase duration="40" state="{"G"*ln}"/><phase duration="50" state="{"r"*ln}"/></tlLogic></additional>')
dur=1800; random.seed(seed)
rows=[]
for i in range(int(vph*dur/3600)):
    t=random.uniform(0,dur); u=random.random(); rt='rL' if u<.3 else ('rR' if u<.5 else 'rT')
    rows.append((t,f'<vehicle id="{i}" type="car" route="{rt}" depart="{t:.1f}" departLane="random" departSpeed="max"/>'))
rows.sort()
(W/'r.rou.xml').write_text('<routes><vType id="car" sigma="0.5" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1"/><route id="rL" edges="up app L"/><route id="rT" edges="up app T T2"/><route id="rR" edges="up app R"/>'+''.join(x[1] for x in rows)+'</routes>')
r=subprocess.run(['sumo','-n',str(W/'n.net.xml'),'-r',str(W/'r.rou.xml'),'-a',str(W/'tl.add.xml'),'--fcd-output',str(W/'fcd.xml'),'--step-length','1','--time-to-teleport',str(tele),'--seed',str(seed),'--end',str(dur+1200),'--no-step-log','true','--statistic-output',str(W/'stat.xml'),'--tripinfo-output',str(W/'trip.xml'),'--tripinfo-output.write-unfinished','true'],capture_output=True,text=True)
print(r.stderr.count('Teleporting'),r.stderr[:0])
reasons=[l for l in r.stderr.splitlines() if 'Teleporting' in l]
wr=[l for l in reasons if 'wrong lane' in l]
# how long did wrong-lane cars sit: consecutive seconds on the approach stopped, in a lane with no link to their next edge
need={'rL':2,'rT':1,'rR':0}
routes={}
for v in ET.parse(W/'r.rou.xml').getroot().findall('vehicle'): routes[v.get('id')]=v.get('route')
tr={}
for ev,el in ET.iterparse(W/'fcd.xml',events=('end',)):
    if el.tag=='timestep':
        t=float(el.get('time'))
        for v in el:
            if v.get('lane','').startswith('app_') : tr.setdefault(v.get('id'),[]).append((t,int(v.get('lane')[-1]),float(v.get('pos')),float(v.get('speed'))))
        el.clear()
stuck=[];wrong_at_end=0;n=0;lc_v=[];stopwrong=[]
for vid,x in tr.items():
    n+=1; nd=need[routes[vid]]
    w=[a for a in x if a[1]!=nd]
    if x[-1][1]!=nd: wrong_at_end+=1
    if w: stuck.append(w[-1][0]-w[0][0]+1)
    s=[a for a in w if a[3]<0.1]
    stopwrong.append(len(s))
stuck=np.array(stuck or [0.]); sw=np.array(stopwrong or [0])
root=ET.parse(W/'stat.xml').getroot(); tp=root.find('teleports'); veh=root.find('vehicles')
out=dict(name=name,approach_m=La,vph=vph,spill=spill,teleports=dict(tp.attrib),vehicles=dict(veh.attrib),cars_on_approach=n,ended_approach_in_wrong_lane=wrong_at_end,wrong_lane_time=dict(p50=float(np.percentile(stuck,50)),p90=float(np.percentile(stuck,90)),p99=float(np.percentile(stuck,99)),max=float(stuck.max())),stopped_in_wrong_lane_s=dict(p50=float(np.percentile(sw,50)),p90=float(np.percentile(sw,90)),p99=float(np.percentile(sw,99)),max=float(sw.max())),share_stopped_wrong=float((sw>0).mean()))
(W/'result.json').write_text(json.dumps(out,indent=1)); print(json.dumps(out))
(W/'fcd.xml').unlink()
