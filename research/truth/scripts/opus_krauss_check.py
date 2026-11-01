"""Replays a real SUMO leader through the Python Krauss and compares the follower with SUMO itself, sigma 0, both step sizes."""
import sys,os,subprocess,shutil,tempfile; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import Batch,krauss,L_EFF
import xml.etree.ElementTree as E
print(shutil.which('sumo'),shutil.which('netconvert'))
d=tempfile.mkdtemp(prefix='opus_kr')
open(d+'/n.nod.xml','w').write('<nodes><node id="a" x="0" y="0"/><node id="b" x="4000" y="0"/></nodes>')
open(d+'/n.edg.xml','w').write('<edges><edge id="e" from="a" to="b" numLanes="1" speed="30"/></edges>')
subprocess.run(['netconvert','-n',d+'/n.nod.xml','-e',d+'/n.edg.xml','-o',d+'/n.net.xml','--no-turnarounds'],check=True,capture_output=True)
out={}
for dt,ml in ((1.0,'1'),(0.1,'.1')):
    open(d+'/r.rou.xml','w').write('''<routes><vType id="k" accel="2.6" decel="4.5" sigma="0" tau="1" minGap="2.5" length="5" emergencyDecel="9" apparentDecel="4.5" maxSpeed="30"/>
<route id="r" edges="e"/>
<vehicle id="L" type="k" route="r" depart="0" departPos="60" departSpeed="10"><stop lane="e_0" endPos="1500" duration="10"/></vehicle>
<vehicle id="F" type="k" route="r" depart="0" departPos="0" departSpeed="10"/></routes>''')
    subprocess.run(['sumo','-n',d+'/n.net.xml','-r',d+'/r.rou.xml','--step-length',str(dt),'--fcd-output',d+'/f.xml','--no-step-log','true','--end','260','--default.speeddev','0','--collision.action','none'],check=True,capture_output=True)
    R={'L':[],'F':[]}
    for ts in E.parse(d+'/f.xml').getroot():
        for v in ts: R[v.get('id')].append((float(ts.get('time')),float(v.get('pos')),float(v.get('speed'))))
    Lt={t:(p,s) for t,p,s in R['L']};F=[x for x in R['F'] if x[0] in Lt]
    t=np.array([x[0] for x in F]);xf=np.array([x[1] for x in F]);vf=np.array([x[2] for x in F]);xl=np.array([Lt[x[0]][0] for x in F]);vl=np.array([Lt[x[0]][1] for x in F])
    # front to front spacing on a 0.1 s grid, linear between SUMO outputs
    grid=np.arange(t[0],t[-1]+1e-6,.1)
    s=np.interp(grid,t,xl-xf);vI=np.interp(grid,t,vf);vlI=np.interp(grid,t,vl)
    b=Batch(s[:,None],vI[:,None],vlI[:,None])
    b.xf=np.interp(grid,t,xf)[:,None];b.xl=np.interp(grid,t,xl)[:,None]
    if dt==1.0:
        # leader held on the SUMO step: replay exactly
        S,V=krauss(b,dict(accel=2.6,decel=4.5,tau=1.0,minGap=2.5,v0=30.0,sigma=0.0),1.0)
    else:
        S,V=krauss(b,dict(accel=2.6,decel=4.5,tau=1.0,minGap=2.5,v0=30.0,sigma=0.0),0.1)
    e=V[:,0,0]-vI;es=S[:,0,0]-s
    out[str(dt)]=dict(steps=len(t),speed_err_rmse=float(np.sqrt(np.mean(e**2))),speed_err_max=float(np.abs(e).max()),spacing_err_rmse=float(np.sqrt(np.mean(es**2))),spacing_err_max=float(np.abs(es).max()),v_range=[float(vI.min()),float(vI.max())])
    print(dt,out[str(dt)],flush=True)
save('krauss_vs_sumo',out);shutil.rmtree(d)
