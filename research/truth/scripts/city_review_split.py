"""Freeze a spatial hold-out for Stockholm Årstrafik before any fit: ~2 km blocks ranked by hash until 30% of sites are held out.
Usage: city_review_split.py sthlm-arstrafik-all.body out.csv"""
import collections as C, csv, hashlib, json, sys
SEED = 'cars-holdout-v1'
fs = json.load(open(sys.argv[1], encoding='utf-8'))['features']
endy = lambda p: str(p.get('datum_för_slut_av_perioden') or '')[:4]
S = {}
for f in fs:
    p = f['properties']; y = endy(p)
    if y not in ('2023', '2024', '2025') or f['geometry'] is None: continue
    g = f['geometry']['coordinates']; c = g[0][0] if f['geometry']['type'] == 'MultiLineString' else g[0]
    s = S.setdefault(p['mätplats'], {'lon': c[0], 'lat': c[1], 'years': set(), 'days': 0, 'name': (p.get('namn') or '').split(' 20')[0]})
    s['years'].add(y); s['days'] = max(s['days'], p.get('antal_mätdygn') or 0)
cells = C.Counter()
for s in S.values():
    s['cell'] = f"{int(s['lon']//0.04)}:{int(s['lat']//0.02)}"; cells[s['cell']] += 1
held = set(); n = 0
for c in sorted(cells, key=lambda c: hashlib.sha256((SEED+c).encode()).hexdigest()):
    if n >= 0.30*len(S): break
    held.add(c); n += cells[c]
for s in S.values(): s['role'] = 'holdout_space' if s['cell'] in held else 'calibrate'
with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['site', 'name', 'cell', 'role', 'years', 'max_days', 'lon', 'lat'])
    for k, s in sorted(S.items()): w.writerow([k, s['name'], s['cell'], s['role'], ' '.join(sorted(s['years'])), s['days'], s['lon'], s['lat']])
print('sites', len(S), 'cells', len({s['cell'] for s in S.values()}), C.Counter(s['role'] for s in S.values()))
print('ge100d by role', C.Counter(s['role'] for s in S.values() if s['days'] >= 100))
print('calibrate sites with 2023/2024 data', sum(s['role'] == 'calibrate' and bool(s['years'] & {'2023', '2024'}) for s in S.values()))
print('holdout sites with 2025 data', sum(s['role'] == 'holdout_space' and '2025' in s['years'] for s in S.values()))
