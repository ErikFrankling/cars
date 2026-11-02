import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd,json,re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
S=Path('research/truth/berlin-snapshot'); F=Path('research/truth/fig'); D=Path('/home/erikf/projects/personal/cars-data'); r=Path((S/'download-dir.txt').read_text())
e=pd.read_csv(S/'day_edges.csv'); c=pd.read_csv(S/'balanced_compare.csv'); m=pd.read_csv(S/'detector_map.csv'); edges=json.loads((S/'network_edges.json').read_text()); d=pd.read_csv(S/'demand_hourly.csv'); s=pd.read_csv(S/'day_summary.csv')
x=c.merge(e[['begin','edge','entered']].assign(hour=lambda z:z.begin//3600),on=['edge','hour']); print('SNAPSHOT VS COMPARISON mismatches',int((x.cars!=x.entered).sum()),'rows',len(x))
print('RUNNING PEAK',s.loc[s.running.idxmax()].to_dict()); print('HOURLY SUMMARY',s[s.time%3600==0][['time','running','teleports']].to_string(index=False))
for hour in [6,9,15,17,18,19,20]:
 q=e[e.begin==hour*3600].copy(); q['speed']=q.distance/q.samples; q['queue']=np.where(q.speed<2,q.samples,0); print('SLOW',hour,q.nlargest(3,'queue')[['edge','queue','speed','teleports']].to_dict('records'))
txt=(r/'srv2018.pdf.txt').read_text(); part=txt[txt.index('Tab 8.1',txt.index('Tab 8.1')+1):] if txt.count('Tab 8.1')>1 else txt[txt.index('Tab 8.1'):]; vals=[]
for line in part.splitlines():
 if re.search(r'\d\d:\d\d[–-]\d\d:\d\d',line):
  vs=re.findall(r'(\d+,\d+)\s*%',line)
  if len(vs)==5: vals.append(float(vs[2].replace(',','.')))
  if len(vals)==24: break
print('SURVEY',vals)
a=np.array(vals); b=d.departures.values/d.departures.sum()*100; pd.DataFrame({'hour':range(24),'SrV_MIV_percent':a,'BeST_percent':b}).to_csv(S/'survey_comparison.csv',index=False)
for sh in range(-3,4): print('DEMAND SURVEY LAG',sh,np.corrcoef(a,np.roll(b,sh))[0,1])
f,ax=plt.subplots(figsize=(9,4)); ax.plot(range(24),a,label='SrV 2018 MIV trips (driver + passenger)'); ax.plot(range(24),b,label='BeST vehicle departures'); ax.set(xlabel='Hour beginning (SrV boundaries differ by 1 minute)',ylabel='Share of daily trips (%)'); ax.legend(); f.tight_layout(); f.savefig(F/'berlin-survey-demand.png',dpi=170)
# route class and site variation
c['road_type']=c.edge.map(lambda x:edges[x].get('type')); cl=c.groupby('road_type').agg(real=('real','sum'),cars=('cars','sum'),sites=('site','nunique')); cl['ratio']=cl.cars/cl.real; cl.to_csv(S/'roadtype_counts.csv'); print('CLASSES',cl.to_string())
# sample geometry audits against metadata: no basemap, local network traces with direction arrows
from lxml import etree
samples=['TE001','TE004','TE009','TE080','TE348','TE324']; mm=m.set_index('site'); near={z:[] for z in samples}
for _,el in etree.iterparse(str(D/'best/berlin.net.xml'),tag='edge',resolve_entities=False,no_network=True):
 if not el.get('id','').startswith(':'):
  lane=el.find('lane')
  if lane is not None:
   p=np.array([list(map(float,t.split(',')))[:2] for t in lane.get('shape').split()])
   for z in samples:
    center=mm.loc[z,['x','y']].astype(float).values
    if np.min(np.linalg.norm(p-center,axis=1))<130: near[z].append((el.get('id'),p))
 el.clear()
 while el.getprevious() is not None: del el.getparent()[0]
f,axs=plt.subplots(2,3,figsize=(12,7))
for z,ax in zip(samples,axs.flat):
 center=mm.loc[z,['x','y']].astype(float).values
 for id,p in near[z]:
  p=p-center; color='#e06a20' if id==mm.loc[z,'edge'] else '#aab4bc'; ax.plot(p[:,0],p[:,1],color=color,lw=3 if color=='#e06a20' else 1)
  if color=='#e06a20':
   j=max(0,len(p)//2-1); v=p[j+1]-p[j]; v=v/max(np.linalg.norm(v),1)*18; ax.arrow(*p[j],*v,width=1.5,color=color)
 ax.scatter(0,0,c='black',s=20); ax.set(xlim=(-100,100),ylim=(-100,100),aspect='equal',title=z+' → '+mm.loc[z,'edge']); ax.set_xlabel('metres east'); ax.set_ylabel('metres north')
f.tight_layout(); f.savefig(F/'berlin-site-geometry.png',dpi=160)
print('DAILY SUM',c.real.sum(),c.cars.sum()); print('DISTRIBUTION RATIOS',(c.groupby('site').cars.sum()/c.groupby('site').real.sum()).describe().to_dict())
