"""Measured Årstrafik 2024-25 two-way totals vs nearest estimated Trafikflöde on the same street; NVDB_Korsning signal census.
Usage: city_review_arstrafik3.py run_dir out.json"""
import collections as C, json, math, pathlib, re, resource, statistics as S, sys
resource.setrlimit(resource.RLIMIT_AS, (2900*1024**2, 2900*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
def mid(g):
    if g is None: return None
    c = g['coordinates']; parts = c if g['type'] == 'MultiLineString' else [c]
    pts = [p for part in parts for p in part]; return pts[len(pts)//2][:2]
tf = json.load(open(d/'sthlm-trafikflode-all.body', encoding='utf-8'))['features']
print('crs tf', tf[0]['geometry']['coordinates'][0][:1] if tf[0]['geometry'] else None)
G = C.defaultdict(list)
for f in tf:
    m = mid(f['geometry']); p = f['properties']
    if m and p.get('totalflöde_alla_riktningar'):
        G[(round(m[0]/0.002), round(m[1]/0.001))].append((m, p))
fs = json.load(open(d/'sthlm-arstrafik-all.body', encoding='utf-8'))['features']
endy = lambda p: str(p.get('datum_för_slut_av_perioden') or '')[:4]
best = {}; un = 0
for f in fs:
    p = f['properties']
    if endy(p) not in ('2024', '2025') or p.get('riktning') != 'Båda': continue
    t = p.get('trafikflöde__fordon_dygn__alla_fordon') or 0
    if t < 1000 or f['geometry'] is None: continue
    m = mid(f['geometry']); name = (p.get('namn') or '').split(' 20')[0].lower()
    a, b = round(m[0]/0.002), round(m[1]/0.001); bd = 1e9; bp = None
    for i in (a-1, a, a+1):
        for j in (b-1, b, b+1):
            for q, e in G.get((i, j), ()):
                if (e.get('gatunamn') or '').lower() != name: continue
                dd = math.hypot((q[0]-m[0])*56000, (q[1]-m[1])*111000)
                if dd < bd: bd, bp = dd, e
    if bp and bd < 80:
        best.setdefault((p['mätplats'], endy(p)), (t, bp['totalflöde_alla_riktningar'], str(bp.get('uppdaterad') or '')[:4], p.get('antal_mätdygn')))
    else: un += 1
r = [v[0]/v[1] for v in best.values()]
r2 = {k[0]: v for k, v in best.items()}
out['matched_site_years'] = len(best); out['unmatched_features'] = un
q = S.quantiles(r, n=20); out['ratio_measured_2024_25_over_estimate_q05_q25_q50_q75_q95'] = [round(q[i], 3) for i in (0, 4, 9, 14, 18)]
out['within_10pct'] = round(sum(.9 <= x <= 1.1 for x in r)/len(r), 3); out['off_gt_30pct'] = round(sum(x < .7 or x > 1.3 for x in r)/len(r), 3); out['sum_ratio'] = round(sum(v[0] for v in best.values())/sum(v[1] for v in best.values()), 3)
out['estimate_update_years'] = C.Counter(v[2] for v in best.values()).most_common(5)
out['ge5days_only_median'] = round(S.median([v[0]/v[1] for v in best.values() if (v[3] or 0) >= 5]), 3)
ko = json.load(open(d/'sthlm-korsning-all.body', encoding='utf-8'))['features']
out['korsning_features'] = len(ko); out['korsning_signalreglering'] = C.Counter(str(f['properties'].get('Signalreglering')) for f in ko).most_common(); out['korsning_type'] = C.Counter(f['properties'].get('Generaliseringstyp') for f in ko).most_common(8)
print(json.dumps(out, ensure_ascii=False, indent=1)); pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
