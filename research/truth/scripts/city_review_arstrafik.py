"""Census of Stockholm od_gis:Arstrafik (untrusted JSON). Usage: city_review_arstrafik.py <body.json> <out.json>"""
import collections as C, json, math, pathlib, resource, statistics as S, sys
resource.setrlimit(resource.RLIMIT_AS, (2800*1024**2, 2800*1024**2))
d = json.load(open(sys.argv[1], encoding='utf-8'))
fs = d['features']; P = [f['properties'] for f in fs]
out = {'features': len(P), 'crs': d.get('crs'), 'fields': sorted(P[0].keys())[:30]}
for k in ['metod_för_datainsamling', 'metod_för_årstrafikberäkning', 'riktningsuppdelad', 'riktning']:
    out[k] = dict(C.Counter(str(p.get(k)) for p in P).most_common(12))
year = lambda p: str(p.get('datum_för_start_av_perioden') or '')[:4]
endy = lambda p: str(p.get('datum_för_slut_av_perioden') or '')[:4]
out['by_end_year'] = dict(sorted(C.Counter(endy(p) for p in P).items()))
meas = [p for p in P if p.get('metod_för_datainsamling') == 'Uppmätt']
out['measured'] = len(meas)
out['measured_by_end_year'] = dict(sorted(C.Counter(endy(p) for p in meas).items()))
out['sites_all'] = len({p.get('mätplats') for p in P})
out['sites_measured'] = len({p.get('mätplats') for p in meas})
days = [p['antal_mätdygn'] for p in meas if p.get('antal_mätdygn') is not None]
out['measured_days'] = {'n': len(days), 'quantiles': S.quantiles(days, n=20) if len(days) > 20 else None, 'max': max(days) if days else None,
                        'hist': dict(sorted(C.Counter(min(x, 400) // 5 * 5 for x in days).items())[:30]), 'null': len(meas) - len(days)}
hr = [k for k in P[0] if k.startswith('trafikflöde_') and k.endswith('alla_fordon')]
out['flow_fields'] = hr
h1 = [k for k in hr if k[12:17].count('-') == 1 and '__fordon_dygn__' in k]
out['hourly_fields'] = len(h1)
out['measured_with_full_hourly'] = sum(all(p.get(k) is not None for k in h1) for p in meas)
out['measured_with_speed'] = sum(p.get('hastighet_medel') is not None for p in meas)
out['measured_with_heavy'] = sum(p.get('trafikflöde_07-08__fordon_dygn__tunga_fordon') is not None for p in meas)
out['measured_directional'] = dict(C.Counter(str(p.get('riktningsuppdelad')) for p in meas))
for yr in ['2019', '2022', '2023', '2024', '2025', '2026']:
    q = [p for p in meas if endy(p) == yr]
    out['y'+yr] = {'features': len(q), 'sites': len({p.get('mätplats') for p in q}),
                   'directional_sites': len({p.get('mätplats') for p in q if str(p.get('riktningsuppdelad')) == 'true'}),
                   'median_days': S.median([p['antal_mätdygn'] for p in q if p.get('antal_mätdygn') is not None] or [0]),
                   'ge_30d_sites': len({p.get('mätplats') for p in q if (p.get('antal_mätdygn') or 0) >= 30}),
                   'with_speed': sum(p.get('hastighet_medel') is not None for p in q)}
# site persistence and length of measured network
def llen(g):
    t = 0.0
    for part in (g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]):
        for a, b in zip(part, part[1:]):
            lat = math.radians((a[1]+b[1])/2)
            t += math.hypot((a[0]-b[0])*111320*math.cos(lat), (a[1]-b[1])*110540)
    return t
ys = C.defaultdict(set)
for p in meas: ys[p.get('mätplats')].add(endy(p))
out['site_years_hist'] = dict(sorted(C.Counter(len(v) for v in ys.values()).items()))
seen = {}
xs, ysc = [], []
for f in fs:
    p = f['properties']
    if p.get('metod_för_datainsamling') != 'Uppmätt' or endy(p) < '2023' or f['geometry'] is None: continue
    if p.get('mätplats') in seen: continue
    seen[p['mätplats']] = llen(f['geometry'])
    g = f['geometry']['coordinates']
    c = (g[0][0] if f['geometry']['type'] == 'MultiLineString' else g[0])
    xs.append(c[0]); ysc.append(c[1])
out['sites_2023on'] = len(seen); out['length_km_2023on_one_per_site'] = round(sum(seen.values())/1000, 1)
out['bbox_2023on'] = [min(xs), min(ysc), max(xs), max(ysc)] if xs else None
# peak-speed and named corridors
names = C.Counter()
for p in meas:
    if endy(p) >= '2023': names[(p.get('namn') or '').split(' 20')[0]] += 1
out['top_streets_2023on'] = names.most_common(25)
def corridor(s): return [(p.get('namn'), p.get('antal_mätdygn'), p.get('hastighet_medel')) for p in meas if endy(p) >= '2024' and s.lower() in (p.get('namn') or '').lower()][:8]
out['corridor_samples'] = {s: corridor(s) for s in ['Essingeleden', 'Norra länken', 'Södra länken', 'Hornsgatan', 'Valhallavägen', 'Sveavägen', 'Klarastrandsleden', 'E4', 'Roslagsvägen', 'Nynäsvägen']}
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1)[:9000])
