import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/home/erikf/.t3/projects/cars/research/truth/fig/.mpl')
import csv,json,collections
from pathlib import Path
from lxml import etree as E
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path('research/truth')
for city in ['stockholm','berlin']:
 r=json.loads((O/f'{city}-map-audit.json').read_text()); cs=list(csv.DictReader(open(O/f'{city}-map-link-capacity.csv'))); tls=list(csv.DictReader(open(O/f'{city}-map-signals.csv')))
 print(city,'approaches by junction',collections.Counter(collections.Counter(c['junction'] for c in cs if c['signalised']=='1').values()))
 print('green_min',sorted(collections.Counter(round(float(t['green_min']),3) for t in tls).items()))
 print('largest loss',r['low_capacity'][:6])
 print('signal major lowgreen',sum(c['signalised']=='1' and float(c['fraction_ideal'])<.15 for c in cs),'signal motorway',sum(c['signalised']=='1' and c['type']=='highway.motorway' for c in cs))
rows=list(csv.DictReader(open(O/'stockholm-map-osm-comparison.csv')));flags=[];known=[]
for r in rows:
 ts=json.loads(r['osm_turn_tags']); key='turn:lanes:backward' if r['edge'].startswith('-') else 'turn:lanes:forward';v=ts.get(key)
 if v is None and r['osm_oneway'] in ('yes','1','true') and not r['edge'].startswith('-'):v=ts.get('turn:lanes')
 if v is None:continue
 exclusive=sum(bool(set(s.split(';')) & {'left','right','slight_left','slight_right','sharp_left','sharp_right'}) and not (set(s.split(';'))-{'left','right','slight_left','slight_right','sharp_left','sharp_right'}) for s in v.split('|'))
 if r['signalised']=='1':
  known.append(r)
  if exclusive>int(r['net_turn_only']):flags.append(dict(**r,expected_turn_only=exclusive,osm_selected=v))
with open(O/'stockholm-map-turn-flags.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(flags[0]) if flags else ['edge']);w.writeheader();w.writerows(flags)
print('direction_known',len(known),'turn flags',len(flags));print('flags',flags[:8])
samples=list(csv.DictReader(open(O/'stockholm-map-samples.csv'))); selected={e for s in samples for e in s['edges'].split()}; paths=collections.defaultdict(list)
for _,e in E.iterparse('/home/erikf/projects/personal/cars-data/stockholm/stockholm.net.xml',events=('end',),tag='edge'):
 id=e.get('id')
 if id in selected:
  paths[id]=[[tuple(map(float,p.split(','))) for p in l.get('shape','').split()] for l in e.findall('lane')]
 e.clear()
 while e.getprevious() is not None:del e.getparent()[0]
fig,axs=plt.subplots(5,4,figsize=(14,17))
for i,(ax,s) in enumerate(zip(axs.flat,samples)):
 for id in s['edges'].split():
  for line in paths[id]:
   if not line:continue
   # Only final 150 m of approach, preserving existing vertices.
   end=line[-1]; q=[p for p in line if (p[0]-end[0])**2+(p[1]-end[1])**2<150**2]
   if len(q)<2:q=line[-2:]
   ax.plot([p[0] for p in q],[p[1] for p in q],lw=1)
 ax.set_title(f"{i+1}. {s['label']}\n{s['jtype']}; {s['incoming_lanes']} lanes",fontsize=9);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
fig.suptitle('Measured incoming net lane geometry; no real-world imagery or inferred extra lanes',fontsize=13);fig.tight_layout();fig.savefig(O/'fig/maps-20-approaches.png',dpi=160)
(O/'maps-detail.json').write_text(json.dumps(dict(direction_known=len(known),turn_flags=len(flags),examples=flags[:12]),indent=2))
