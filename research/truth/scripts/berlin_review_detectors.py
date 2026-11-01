# All-sites detector profile (same filters as scripts/berlin_detectors.py, but no map filter) and BeST plot digitising.
import os,re,tarfile,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from lxml import etree
O=Path('research/truth/berlin-review'); S=Path('research/truth/berlin-snapshot'); A=Path('/home/erikf/projects/personal/cars-data/berlin-detectors/detektoren_2024_09.tgz'); DL=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031')
m=pd.read_csv(S/'metadata_det.csv',dtype=str); lookup=m.set_index('B').A.to_dict(); counts=m.groupby('A').size()
fr=[]
with tarfile.open(A) as tar:
    for mem in tar:
        det=Path(mem.name).stem
        if not mem.isfile() or det not in lookup: continue
        q=pd.read_csv(tar.extractfile(mem),sep=';'); q=q.rename(columns={q.columns[0]:'date',q.columns[1]:'hour'})
        q=q[(pd.to_datetime(q.date).dt.dayofweek<5)&(q['Vollständigkeit']>=75)&(q.hist_cor>=.5)&(q.qkfz>=0)].copy()
        q['site']=lookup[det]; q['detector']=det; fr.append(q[['site','detector','date','hour','qkfz','qpkw','qlkw','vkfz']])
d=pd.concat(fr); print('detector rows',len(d),'detectors',d.detector.nunique(),'sites',d.site.nunique(),'metadata sites',m.A.nunique())
la=d.groupby(['site','detector','hour'])[['qkfz','qlkw']].mean().reset_index(); la.to_csv(O/'detector_lane_hourly.csv',index=False,float_format='%.2f')
g=d.groupby(['site','date','hour']).agg(real=('qkfz','sum'),pkw=('qpkw','sum'),lkw=('qlkw','sum'),n=('detector','nunique'),v=('vkfz','mean')).reset_index()
g=g[g.n==g.site.map(counts)]
p=g.groupby(['site','hour']).agg(real=('real','mean'),pkw=('pkw','mean'),lkw=('lkw','mean'),days=('real','size'),v=('v','mean')).reset_index(); p=p[p.days>=5]; p.to_csv(O/'detector_all_hourly.csv',index=False,float_format='%.2f')
full=p.groupby('site').hour.nunique(); print('sites with 24 hours',int((full==24).sum()),'of',len(full))
# BeST README plots are vector: 24 points per series, axis ticks give the scale.
def series(path):
    t=etree.parse(str(path),etree.XMLParser(resolve_entities=False,no_network=True)); ticks=[]; out={}
    for e in t.getroot().iter('{http://www.w3.org/2000/svg}path'):
        st=e.get('style',''); c=re.search(r'stroke:(#\w+)',st); c=c.group(1) if c else None; d=e.get('d')
        if c=='#000000' and re.fullmatch(r'm [\d.]+,[\d.]+ h -3\.5',d): ticks.append(float(d.split()[1].split(',')[1]))
        if c in('#0000ff','#ff0000','#808080') and len(d)>100:
            toks=re.findall(r'[mMlLhHvVzZ]|-?\d+\.?\d*(?:e-?\d+)?',d); x=y=0; pts=[]; cmd=None; i=0
            while i<len(toks):
                k=toks[i]
                if k.isalpha(): cmd=k; i+=1; continue
                if cmd in 'mMlL':
                    a,b=float(toks[i]),float(toks[i+1]); i+=2
                    if cmd.islower(): x+=a; y+=b
                    else: x,y=a,b
                    pts.append((x,y))
                    if cmd=='m': cmd='l'
                    if cmd=='M': cmd='L'
                elif cmd in 'hH': a=float(toks[i]); i+=1; x=x+a if cmd=='h' else a; pts.append((x,y))
                elif cmd in 'vV': a=float(toks[i]); i+=1; y=y+a if cmd=='v' else a; pts.append((x,y))
            out[{'#0000ff':'real','#ff0000':'sumo','#808080':'matsim'}[c]]=np.array(pts)
    return out,sorted(ticks)
step={'a100-east':2500,'altmoabit-east':500,'siemensdamm-east':1000,'treskowallee-south':500}
rows=[]
for n,dy in step.items():
    s,tk=series(DL/f'best-repo/counts-{n}.svg'); y0=tk[0]; sc=dy/(tk[1]-tk[0])
    print(n,'ticks',tk,{k:len(v) for k,v in s.items()})
    for k,v in s.items():
        for h,(a,b) in enumerate(v): rows.append(dict(plot=n,series=k,hour=h,value=(b-y0)*sc))
b=pd.DataFrame(rows); b.to_csv(O/'best_plot_digitised.csv',index=False,float_format='%.1f'); print(b.pivot_table(index='plot',columns='series',values='value',aggfunc='sum').round(0))
print(m[m.F.fillna('').str.contains('A ?100|Stadtring|Stadtautobahn|BAB')|m.G.fillna('').str.contains('Friedenau|Innsbrucker|Wexstra')][['A','B','F','G','H','I','J']].to_string())
