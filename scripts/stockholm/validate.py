"""Convert SUMO edge observations and compare to mapped band counts."""
import csv,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(sys.argv[1]); prefix=sys.argv[2]
rows=list(csv.DictReader(open(D/'count_matches.csv'))); counts={}
for r in rows: counts.setdefault(r['edge'],[]).append(r)
obs={}
if prefix=='cars':
    for r in csv.DictReader(open(D/'cars.edges.csv')):
        begin=float(r['begin']); obs.setdefault(r['edge'],[]).append((begin,begin+3600,float(r['entered'])))
else:
    for _,el in ET.iterparse(D/(prefix+'.edges.xml'),events=['end']):
        if el.tag=='interval':
            begin=float(el.get('begin')); end=float(el.get('end'))
            for e in el: obs.setdefault(e.get('id'),[]).append((begin,end,float(e.get('entered',0))))
            el.clear()
report={}
for band,hours in [('06_18',12),('18_22',4),('22_06',8)]:
    x=[];y=[]
    for edge,rs in counts.items():
        target=np.mean([float(r[band]) for r in rs]); measured=0; duration=0
        for begin,end,value in obs.get(edge,[]):
            h=(begin/3600)%24
            if ('06_18' if 6<=h<18 else '18_22' if 18<=h<22 else '22_06')==band: measured+=value;duration+=end-begin
        if duration:x.append(target*duration/(hours*3600));y.append(measured)
    if not x:continue
    x=np.array(x);y=np.array(y);geh=np.sqrt(2*(x-y)**2/np.maximum(x+y,1));report[band]={'n':len(x),'geh_lt5':float(np.mean(geh<5))}
    fig,ax=plt.subplots();ax.scatter(x,y,s=2,color=('#2a78d6' if prefix=='cars' else '#eb6834'),label=prefix); lim=max(x.max(),y.max(),1);t=np.linspace(0,lim,400)
    ax.plot(t,t,lw=.5,color='gray')
    # GEH=5: y=x+g²/4 ± g/4 sqrt(g²+16x).
    for sign in [-1,1]:ax.plot(t,t+25/4+sign*5/4*np.sqrt(25+16*t),lw=.6,color='black',label='GEH 5' if sign==1 else None)
    ax.set(xlabel='Counted vehicles (window)',ylabel='Simulated vehicles (window)',ylim=(0,lim));ax.legend();fig.savefig(f'results/stockholm/{prefix}_{band}.png',dpi=160);plt.close(fig)
(D/(prefix+'.validation.json')).write_text(json.dumps(report,indent=2));print(report)
