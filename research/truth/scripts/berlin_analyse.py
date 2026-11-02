import os
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import json,hashlib,gzip,collections,tarfile,zipfile,xml.etree.ElementTree as ET
import numpy as np,pandas as pd
from lxml import etree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=Path('research/truth'); S=B/'berlin-snapshot'; D=Path('/home/erikf/projects/personal/cars-data'); fig=B/'fig'
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in S.glob('*.csv')}; (S/'manifest.json').write_text(json.dumps(manifest,indent=2))
s=pd.read_csv(S/'day_summary.csv'); t=pd.read_csv(S/'day_trips.csv'); e=pd.read_csv(S/'day_edges.csv'); m=pd.read_csv(S/'detector_map.csv'); c=pd.read_csv(S/'detector_compare.csv')
print('LAST SUMMARY',s.tail(1).to_dict('records'))
print('EDGE TIMES',e.begin.unique()); print('MAP',m.quality.value_counts().to_dict())
full=c.groupby('site').hour.nunique(); sites=full[full==24].index; c=c[c.site.isin(sites)].copy(); c.to_csv(S/'balanced_compare.csv',index=False)
R=c.pivot(index='site',columns='hour',values='real').sort_index(); C=c.pivot(index='site',columns='hour',values='cars').reindex(R.index)
rows=[]
for shift in range(-6,7):
 v=np.roll(C.values,shift,axis=1); corr=[np.corrcoef(a,b)[0,1] if np.std(b)>0 else np.nan for a,b in zip(R.values,v)]
 rows.append(dict(shift_added_to_sim_hours=shift,aggregate_r=np.corrcoef(R.sum().values,v.sum(axis=0))[0,1],median_site_r=np.nanmedian(corr),rmse_after_global_scaling=np.sqrt(np.mean((R.values-v*(R.values*v).sum()/(v*v).sum())**2))))
lags=pd.DataFrame(rows); lags.to_csv(S/'lags.csv',index=False); print('LAGS',lags.to_string(index=False))
best=[]
for site in R.index:
 rs=[np.corrcoef(R.loc[site],np.roll(C.loc[site],h))[0,1] if C.loc[site].std()>0 else -2 for h in range(-4,5)]
 best.append((site,list(range(-4,5))[int(np.argmax(rs))],max(rs)))
pd.DataFrame(best,columns=['site','best_shift','r']).to_csv(S/'site_lags.csv',index=False)
print('SITE LAGS',collections.Counter(x[1] for x in best))
h=c.groupby('hour')[['real','cars']].sum(); h.to_csv(S/'balanced_hourly.csv'); print('HOURS',h.to_string()); print('DAILY RATIO',h.cars.sum()/h.real.sum())
acc=m[m.quality=='accepted']; print('ACCEPTED DIST',acc.distance_m.describe().to_dict())
for cutoff in [5,10,20]:
 ids=acc[acc.distance_m<=cutoff].site; q=c[c.site.isin(ids)]; print('STRICT',cutoff,q.site.nunique(),q.cars.sum()/q.real.sum())
# stream network, retain external edge attributes and geometry only
edges={}; tls=[]; junctions=collections.Counter()
for _,x in etree.iterparse(str(D/'best/berlin.net.xml'),events=('end',),tag=('edge','tlLogic','junction'),resolve_entities=False,no_network=True):
 if x.tag=='edge' and not x.get('id','').startswith(':'):
  lanes=x.findall('lane'); a=dict(x.attrib); a.update(length=float(lanes[0].get('length')),speed=float(lanes[0].get('speed')),lanes=len(lanes),shape=lanes[0].get('shape')); edges[x.get('id')]=a
 elif x.tag=='tlLogic': tls.append(dict(x.attrib,cycle=sum(float(p.get('duration')) for p in x.findall('phase')),phases=len(x.findall('phase'))))
 elif x.tag=='junction': junctions[x.get('type')]+=1
 x.clear()
 while x.getprevious() is not None: del x.getparent()[0]
pd.DataFrame(tls).to_csv(S/'tls.csv',index=False)
print('TLS',len(tls),collections.Counter(x['type'] for x in tls),collections.Counter(x.get('programID') for x in tls)); print('CYCLES',collections.Counter(x['cycle'] for x in tls).most_common(10)); print('JUNCTIONS',junctions)
# hourly edge speeds and teleport concentration
te=e.groupby('edge').teleports.sum().sort_values(ascending=False); print('TOP TELEPORTS',[(k,int(v),edges.get(k,{}).get('name'),edges.get(k,{}).get('type')) for k,v in te.head(12).items()]); print('TE SHARE',te.head(1).sum()/te.sum(),te.head(5).sum()/te.sum())
top=te.head(12).index; ee=e[e.edge.isin(top)].copy(); ee['speed']=ee.distance/ee.samples.clip(lower=1); ee['name']=ee.edge.map(lambda z:edges.get(z,{}).get('name')); ee.to_csv(S/'bottlenecks.csv',index=False)
# edge data distance in m, speed m/s from one-second samples
print('EDGE DIST KM',e.distance.sum()/1000,'USED EDGES',e.edge.nunique(),'EXTERNAL EDGES',len(edges))
print('TRIP KM',t.route_length.sum()/1000,'completed',len(t))
e['hour']=(e.begin//3600).astype(int); e['slow_samples']=np.where(e.distance/e.samples.clip(lower=1)<2,e.samples,0); hourly=e.groupby('hour').agg(samples=('samples','sum'),distance=('distance','sum'),slow_samples=('slow_samples','sum'),teleports=('teleports','sum')); hourly['speed_kmh']=hourly.distance/hourly.samples*3.6; hourly.to_csv(S/'edge_hourly.csv'); print('NETWORK',hourly.to_string())
t['hour']=(t.depart//3600).astype(int); th=t.groupby('hour').agg(completed=('trip','size'),waiting=('waiting','mean'),duration=('duration','mean')); th.to_csv(S/'trip_hourly.csv')
# routes, all type counts, duplicates and hourly departures
hist=collections.Counter(); types=collections.Counter(); routes=collections.Counter(); lengthsum=0; n=0; missing=0
with gzip.open(D/'best/berlin.rou.gz','rb') as f:
 for _,x in etree.iterparse(f,events=('end',),tag=('vehicle','vType'),resolve_entities=False,no_network=True):
  if x.tag=='vType': print('VTYPE',dict(x.attrib))
  else:
   n+=1; hist[int(float(x.get('depart'))//3600)]+=1; types[x.get('type','DEFAULT')]+=1
   rt=x.find('route')
   if rt is not None:
    ids=rt.get('edges','').split(); routes[hashlib.blake2b(rt.get('edges','').encode(),digest_size=12).hexdigest()]+=1
    for z in ids:
     if z in edges: lengthsum+=edges[z]['length']
     else: missing+=1
  x.clear()
  while x.getprevious() is not None: del x.getparent()[0]
demand=pd.DataFrame(sorted(hist.items()),columns=['hour','departures']); demand.to_csv(S/'demand_hourly.csv',index=False); print('DEMAND',n,types,'KM',lengthsum/1000,'MISSING EDGES',missing,'UNIQUE ROUTES',len(routes),'MAX DUP',max(routes.values())); print(demand.to_string(index=False))
# metadata and representative manual audit candidates, retain all spreadsheet columns
with zipfile.ZipFile(D/'berlin-detectors/Stammdaten_Verkehrsdetektion_2022_07_20.xlsx') as z:
 ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}; st=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]; rows=[]
 for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row',ns):
  rows.append({x.get('r').rstrip('0123456789'):st[int(x.find('m:v',ns).text)] if x.get('t')=='s' else x.findtext('m:v',default='',namespaces=ns) for x in row})
 meta=pd.DataFrame(rows[1:]); meta.to_csv(S/'metadata_det.csv',index=False)
 selected=list(R.index[:4])+list((C.sum(axis=1)/R.sum(axis=1)).sort_values().head(3).index)+list((C.sum(axis=1)/R.sum(axis=1)).sort_values().tail(3).index)
 audit=[]
 for site in dict.fromkeys(selected):
  mm=m[m.site==site].iloc[0].to_dict(); net=edges.get(mm['edge'],{}); md=meta[meta.A==site].iloc[0].to_dict(); audit.append(dict(**mm,road=net.get('name'),edge_type=net.get('type'),metadata=str(md),ratio=float(C.loc[site].sum()/R.loc[site].sum())))
pd.DataFrame(audit).to_csv(S/'site_audit.csv',index=False); print('AUDIT',[(x['site'],x['edge'],x['road'],x['ratio']) for x in audit])
# freight using exact quality and balanced sample, aggregate at site/day/hour before mean
lookup=meta.set_index('B').A.to_dict(); fs=[]
with tarfile.open(D/'berlin-detectors/detektoren_2024_09.tgz') as tar:
 for member in tar:
  det=Path(member.name).stem
  if not member.isfile() or lookup.get(det) not in R.index: continue
  q=pd.read_csv(tar.extractfile(member),sep=';');
  if not fs: print('RAW',member.name,q.head(3).to_dict('records'))
  q=q.rename(columns={q.columns[0]:'date',q.columns[1]:'hour'}); q=q[(pd.to_datetime(q.date).dt.dayofweek<5)&(q['Vollständigkeit']>=75)&(q.hist_cor>=.5)&(q.qkfz>=0)]; q['site']=lookup[det]; q['detector']=det; fs.append(q[['site','detector','date','hour','qkfz','qpkw','qlkw']])
f=pd.concat(fs); f=f.groupby(['site','date','hour']).agg(qkfz=('qkfz','sum'),qpkw=('qpkw','sum'),qlkw=('qlkw','sum'),n=('detector','nunique')).reset_index(); cnt=meta.groupby('A').size(); f=f[f.n==f.site.map(cnt)]; f=f.groupby(['site','hour'])[['qkfz','qpkw','qlkw']].mean(); f.to_csv(S/'freight.csv'); print('FREIGHT',f.sum().to_dict(),f.qlkw.sum()/f.qkfz.sum())
figs,ax=plt.subplots(2,2,figsize=(12,8)); ax[0,0].plot(h.index,h.real/1000,label='Observed, 93 sites'); ax[0,0].plot(h.index,h.cars/1000,label='cars, same sites'); ax[0,0].set(ylabel='Thousand crossings/h',xlabel='Local hour'); ax[0,0].legend(); ax[0,1].plot(demand.hour,demand.departures/1000); ax[0,1].set(ylabel='Thousand BeST departures/h',xlabel='Scenario hour'); ax[1,0].plot(s.time/3600,s.running/1000,label='Running (thousands)'); ax[1,0].plot(s.time/3600,s.teleports/1000,label='Cumulative teleports (thousands)'); ax[1,0].legend(); ax[1,0].set(xlabel='Scenario hour'); ax[1,1].plot(th.index,th.waiting); ax[1,1].set(ylabel='Mean waiting, completed trips (s)',xlabel='Departure hour'); figs.tight_layout(); figs.savefig(fig/'berlin-forensics.png',dpi=170); plt.close(figs)
f,ax=plt.subplots(1,2,figsize=(11,4)); ax[0].plot(lags.shift_added_to_sim_hours,lags.aggregate_r,label='Aggregate'); ax[0].plot(lags.shift_added_to_sim_hours,lags.median_site_r,label='Median site'); ax[0].set(xlabel='Hours added to simulation clock',ylabel='Pearson correlation'); ax[0].legend();
for edge in te.head(4).index:
 q=ee[ee.edge==edge]; ax[1].plot(q.begin/3600,q.teleports,label=edge)
ax[1].set(xlabel='Scenario hour',ylabel='Teleports per edge interval'); ax[1].legend(fontsize=7); f.tight_layout(); f.savefig(fig/'berlin-lags-bottlenecks.png',dpi=170)
(S/'network_edges.json').write_text(json.dumps({k:edges[k] for k in set(top)|set(acc.edge) if k in edges}))
