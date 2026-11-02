#!/usr/bin/env python3
# Measures generated signal programs in a SUMO net. Usage: tls_stats.py NET OUT.json
import sys,json,re,collections,statistics as st
from xml.etree.ElementTree import iterparse
net,out=sys.argv[1:3]
R=[];apps=collections.defaultdict(set);movs=collections.defaultdict(list)
for ev,e in iterparse(net,events=('end',)):
    if e.tag=='tlLogic':
        P=[(float(p.get('duration')),p.get('state'),float(p.get('minDur',p.get('duration'))),float(p.get('maxDur',p.get('duration')))) for p in e.findall('phase')]
        R.append(dict(id=e.get('id'),type=e.get('type'),off=e.get('offset'),P=P));e.clear()
    elif e.tag=='connection':
        if e.get('tl'):apps[e.get('tl')].add(e.get('from'));movs[e.get('tl')].append((e.get('from'),e.get('dir'),int(e.get('linkIndex'))))
        e.clear()
    elif e.tag=='edge':e.clear()
def q(x,p):
    x=sorted(x);return x[min(len(x)-1,int(p*len(x)))]
rows=[]
for r in R:
    P=r['P'];nom=sum(p[0] for p in P);mx=sum(p[3] for p in P);mn=sum(p[2] for p in P)
    gp=[p for p in P if re.search('[Gg]',p[1])]
    grn=[p for p in P if 'y' not in p[1] and re.search('[Gg]',p[1])]
    n=len(P[0][1]) if P else 0
    rows.append(dict(id=r['id'],phases=len(P),green_phases=len(grn),nom=nom,max=mx,min=mn,links=n,app=len(apps[r['id']]),S=r['id'][0]=='S' and r['id'][1:].isdigit(),lost=sum(p[0] for p in P if not re.search('[Gg]',p[1].replace('y','')) or 'y' in p[1])))
def summ(rs,tag):
    return dict(tag=tag,n=len(rs),nom_p50=q([r['nom'] for r in rs],.5),nom_p90=q([r['nom'] for r in rs],.9),nom_max=max(r['nom'] for r in rs),max_p50=q([r['max'] for r in rs],.5),max_p90=q([r['max'] for r in rs],.9),max_max=max(r['max'] for r in rs),gph_hist=sorted(collections.Counter(r['green_phases'] for r in rs).items()),app_hist=sorted(collections.Counter(min(r['app'],9) for r in rs).items()),nom_gt100=sum(r['nom']>100 for r in rs),nom_gt120=sum(r['nom']>120 for r in rs),nom_gt180=sum(r['nom']>180 for r in rs),max_gt100=sum(r['max']>100 for r in rs),max_gt180=sum(r['max']>180 for r in rs),lost_p50=q([r['lost'] for r in rs],.5),lost_p90=q([r['lost'] for r in rs],.9))
O=dict(all=summ(rows,'all'),register=summ([r for r in rows if r['S']],'register S*'),rest=summ([r for r in rows if not r['S']],'rest'),types=collections.Counter(r['type'] for r in R),offsets=collections.Counter(r['off'] for r in R).most_common(4),worst=sorted(rows,key=lambda r:-r['nom'])[:15])
json.dump(O,open(out,'w'),indent=0);print(json.dumps({k:O[k] for k in('all','register','rest','types','offsets')},indent=0)[:3500])
for r in O['worst']:print(r['id'],r['phases'],r['green_phases'],r['nom'],r['max'],r['app'],r['links'])
