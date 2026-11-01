"""Motor-only census of Årstrafik + comparison with the estimated Trafikflöde product on shared NVDB keys.
Usage: city_review_arstrafik2.py run_dir out.json"""
import collections as C, json, math, pathlib, resource, statistics as S, sys
resource.setrlimit(resource.RLIMIT_AS, (2900*1024**2, 2900*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
fs = json.load(open(d/'sthlm-arstrafik-all.body', encoding='utf-8'))['features']
endy = lambda p: str(p.get('datum_för_slut_av_perioden') or '')[:4]
isb = lambda p: False  # 'cykelväg' in a name only labels an endpoint; flows are motor traffic
out['features_named_cykel'] = sum('cykel' in (f['properties'].get('namn') or '').lower() for f in fs)
ex = [f['properties'] for f in fs if 'cykel' in (f['properties'].get('namn') or '').lower()][:2]
out['cykel_examples'] = [(p['namn'], p.get('trafikflöde__fordon_dygn__alla_fordon'), p.get('hastighet_medel')) for p in ex]
# unique site-direction-year records
rec = {}
for f in fs:
    p = f['properties']
    if isb(p) or f['geometry'] is None: continue
    k = (p['mätplats'], p['riktningsbeskrivning'], endy(p))
    if k not in rec: rec[k] = f
out['unique_site_dir_year_motor'] = len(rec)
sample = next(iter(rec.values()))['properties']
out['period_examples'] = [(f['properties']['namn'], f['properties']['datum_för_start_av_perioden'], f['properties']['datum_för_slut_av_perioden'], f['properties']['antal_mätdygn']) for f in list(rec.values())[-3:]]
yr = {}
for y in ['2019','2021','2022','2023','2024','2025','2026']:
    q = [f['properties'] for k, f in rec.items() if k[2] == y]
    dirq = [p for p in q if str(p['riktningsuppdelad']) == 'true' and p['riktning'] in ('Med','Mot')]
    both = C.Counter(p['mätplats'] for p in dirq)
    days = [p['antal_mätdygn'] for p in dirq]
    yr[y] = {'site_dir_records': len(q), 'directional_records': len(dirq), 'sites': len({p['mätplats'] for p in q}), 'sites_both_dirs': sum(v >= 2 for v in both.values()),
             'ge5d': sum(x >= 5 for x in days), 'ge30d': sum(x >= 30 for x in days), 'ge100d': sum(x >= 100 for x in days),
             'speed': sum(p.get('hastighet_medel') is not None for p in dirq), 'flow_ge5000': sum((p.get('trafikflöde__fordon_dygn__alla_fordon') or 0) >= 5000 for p in dirq)}
out['per_end_year'] = yr
r3 = [(k, f) for k, f in rec.items() if k[2] in ('2023','2024','2025') and f['properties']['riktning'] in ('Med','Mot')]
out['sites_2023_25_directional'] = len({k[0] for k, f in r3})
top = sorted(r3, key=lambda kf: -(kf[1]['properties'].get('trafikflöde__fordon_dygn__alla_fordon') or 0))[:12]
out['largest_flows'] = [(f['properties']['namn'], f['properties']['trafikflöde__fordon_dygn__alla_fordon'], f['properties']['antal_mätdygn'], f['properties'].get('hastighet_medel')) for k, f in top]
# peak hour share sanity on busy directional 2025 sites
pk = []; am = []; pm = []
H = [f'trafikflöde_{h:02d}-{h+1:02d}__fordon_dygn__alla_fordon' for h in range(24)]
for k, f in r3:
    p = f['properties']; t = p.get('trafikflöde__fordon_dygn__alla_fordon') or 0
    if t < 5000: continue
    v = [p.get(x) or 0 for x in H]; s = sum(v)
    if s <= 0: continue
    pk.append(max(v)/s); am.append(v.index(max(v[6:10]))); pm.append(sum(v)/t)
out['busy_max_hour_share_q10_50_90'] = [round(x, 3) for x in (S.quantiles(pk, n=10)[0], S.median(pk), S.quantiles(pk, n=10)[-1])]
out['hourly_sum_over_daily_median'] = round(S.median(pm), 3)
# Trafikflöde comparison by nvdb_key + direction agnostic totals
tf = json.load(open(d/'sthlm-trafikflode-all.body', encoding='utf-8'))['features']
out['trafikflode_features'] = len(tf); out['trafikflode_fields'] = sorted(tf[0]['properties'].keys())[:24]
meth = C.Counter(f['properties'].get('metod_för_datainsamling') for f in tf); out['trafikflode_method'] = meth.most_common()
key = 'nvdb_key' if 'nvdb_key' in tf[0]['properties'] else None; out['tf_has_nvdb_key'] = bool(key)
est = {}; flowk = next((k for k in tf[0]['properties'] if k.startswith('trafikflöde') and 'alla' in k and k.count('_') < 8 and ('dygn' in k)), None); out['tf_flow_field'] = flowk
if key:
    for f in tf:
        p = f['properties']
        if p.get(key) and p.get(flowk): est[p[key]] = p
    m = C.defaultdict(list)
    for f in fs:
        p = f['properties']
        if endy(p) in ('2024','2025') and not isb(p) and p['riktning'] == 'Båda' and p.get(key) in est and (p.get('trafikflöde__fordon_dygn__alla_fordon') or 0) > 500:
            m[p['mätplats']].append(p['trafikflöde__fordon_dygn__alla_fordon']/est[p[key]][flowk])
    rat = [S.median(v) for v in m.values()]
    out['ratio_measured_over_estimate_sites'] = len(rat)
    if rat:
        rat.sort(); q = S.quantiles(rat, n=20)
        out['ratio_q05_q25_q50_q75_q95'] = [round(q[0],3), round(q[4],3), round(q[9],3), round(q[14],3), round(q[18],3)]
        out['ratio_within_10pct'] = round(sum(0.9 <= r <= 1.1 for r in rat)/len(rat), 3); out['ratio_off_by_gt_30pct'] = round(sum(r < .7 or r > 1.3 for r in rat)/len(rat), 3)
print(json.dumps(out, ensure_ascii=False, indent=1)); pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
