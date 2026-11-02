"""Measured Årstrafik against what the scenarios assume: hourly shape, heavy share, speed against the net's limit. Usage: arstrafik.py body site_matches.csv n7.net.xml OUT.json"""
import collections as C, csv, json, re, statistics as S, sys, resource
resource.setrlimit(resource.RLIMIT_AS, (1800*1024**2, 1800*1024**2))
fs=json.load(open(sys.argv[1],encoding='utf-8'))['features']
yr=lambda p:str(p.get('datum_för_slut_av_perioden') or '')[:4]
H=[f'{h:02d}-{h+1:02d}' for h in range(24)]
rec=[]
for f in fs:
    p=f['properties']
    if p.get('riktningsuppdelad')!='true' and p.get('riktning')=='Båda': continue
    if yr(p) not in('2023','2024','2025'): continue
    if (p.get('antal_mätdygn') or 0)<5: continue
    a=[p.get(f'trafikflöde_{h}__fordon_dygn__alla_fordon') for h in H]; t=[p.get(f'trafikflöde_{h}__fordon_dygn__tunga_fordon') for h in H]
    if any(x is None for x in a): continue
    rec.append((p,a,t))
out={'records':len(rec)}
tot=[sum(r[1][i] for r in rec) for i in range(24)]; T=sum(tot)
out['hourly_share_all_sites_pct']=[round(100*x/T,2) for x in tot]
big=[r for r in rec if sum(r[1])>=5000]
tb=[sum(r[1][i] for r in big) for i in range(24)]; out['big_records']=len(big); out['hourly_share_big_pct']=[round(100*x/sum(tb),2) for x in tb]
out['band_share_big_pct']={'06-18':round(100*sum(tb[6:18])/sum(tb),1),'18-22':round(100*sum(tb[18:22])/sum(tb),1),'22-06':round(100*(sum(tb[22:])+sum(tb[:6]))/sum(tb),1)}
mx=[max(r[1])/sum(r[1]) for r in big]; out['max_hour_share_q10_50_90']=[round(100*S.quantiles(mx,n=10)[i],1) for i in(0,4,8)]
amp=[max(r[1][6:10])/max(r[1][14:19]) for r in big if max(r[1][14:19])]; out['am_over_pm_peak_q10_50_90']=[round(S.quantiles(amp,n=10)[i],2) for i in(0,4,8)]
hv=[sum(x or 0 for x in r[2])/sum(r[1]) for r in rec if sum(r[1])>=1000 and any(x is not None for x in r[2])]
out['heavy_share_records']=len(hv); out['heavy_share_q10_50_90_pct']=[round(100*S.quantiles(hv,n=10)[i],1) for i in(0,4,8)]
out['heavy_share_vkm_weighted_pct']=round(100*sum(sum(x or 0 for x in r[2]) for r in rec)/T,2)
# speed against the edge's limit in the recipe net
speed={}
ed=None
for l in open(sys.argv[3],errors='replace'):
    s=l.lstrip()
    if s.startswith('<edge '):
        ed=None if 'function="' in s else re.search(r'id="([^"]*)"',s)[1]
    elif s.startswith('<lane ') and ed and ed not in speed:
        speed[ed]=float(re.search(r'speed="([^"]*)"',s)[1])*3.6
site=C.defaultdict(list)
for r in csv.DictReader(open(sys.argv[2])):
    site[r['site'].split(':')[0]+':'+r['site'].split(':')[1]].append(r['edge'])
rows=[]
for p,a,t in rec:
    if p.get('hastighet_medel') is None: continue
    k=f"{p['mätplats']}:{p.get('riktning')}"
    for e in site.get(k,[])[:1]:
        if e in speed: rows.append((round(speed[e]/10)*10,p['hastighet_medel'],p.get('hastighet_85-percentil'),sum(a)))
by=C.defaultdict(list)
for r in rows: by[r[0]].append(r)
out['speed_rows']=len(rows)
out['speed_by_limit']={str(k):dict(n=len(v),mean_of_mean=round(S.mean(x[1] for x in v),1),median_of_mean=S.median(x[1] for x in v),mean_p85=round(S.mean([x[2] for x in v if x[2] is not None] or [0]),1),flow_weighted_mean=round(sum(x[1]*x[3] for x in v)/sum(x[3] for x in v),1)) for k,v in sorted(by.items())}
out['speed_null_records']=sum(1 for p,_,_ in rec if p.get('hastighet_medel') is None)
json.dump(out,open(sys.argv[4],'w'),indent=1,ensure_ascii=False); print(json.dumps(out,ensure_ascii=False))
