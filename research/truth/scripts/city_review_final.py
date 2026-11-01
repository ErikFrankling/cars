"""A10 mainline detector spacing from NDW ids, TIRTL site types, remaining text checks. Usage: city_review_final.py run_dir out.json"""
import collections as C, csv, html, io, json, pathlib, re, statistics as S, sys
d = pathlib.Path(sys.argv[1]); out = {}
pt = json.load(open('/tmp/ndw_points.json'))
ma = C.defaultdict(list); ram = 0
for p in pt:
    m = re.match(r'RWS01_MONIBAS_(\d{3})(\d)(hr[lr])(\d{4})', p[0])
    if m and m.group(1) == '010': ma[m.group(3)].append(int(m.group(4))/10)
    if re.match(r'RWS01_MONIBAS_0100?(vw|)', p[0]) and 'vw' in p[0][:24]: ram += 1
out['a10_mainline_by_direction'] = {k: len(v) for k, v in ma.items()}
out['a10_ramp_like_vw_ids'] = ram
for k, v in ma.items():
    v = sorted(set(v)); g = [b-a for a, b in zip(v, v[1:]) if b-a < 5]
    out['a10_'+k] = {'unique_positions': len(v), 'km_min': v[0], 'km_max': v[-1], 'median_gap_km': S.median(g) if g else None, 'p90_gap_km': S.quantiles(g, n=10)[-1] if len(g) > 10 else None}
t = list(csv.DictReader(io.StringIO((d/'vic-tirtl-sites.body').read_bytes().decode('utf-8-sig', 'replace'))))
kinds = C.Counter()
for r in t:
    s = r['site_description']
    kinds['M/freeway' if re.match(r'^(M\d|FWY|.*(Freeway|Fwy|Tollway|Ring Rd|Ramp))', s) else 'other'] += 1
out['tirtl_kinds'] = kinds.most_common(); out['tirtl_examples'] = [r['site_description'] for r in t[::60]]
def T(n):
    raw = (d/(n+'.body')).read_bytes().decode('utf-8', 'replace'); raw = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', raw)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'(?s)<[^>]+>', ' ', raw)))
def G(n, pat, c=140, k=4): return [T(n)[max(0, m.start()-c):m.end()+c] for m in list(re.finditer(pat, T(n), re.I))[:k]]
out['utd_method'] = G('utd-paper', r'random|Google', k=3)
out['digiroad'] = G('fi-digiroad', r'30\.9\.2026|CC BY|Creative Commons|lakkaa|päättyy', k=4)
out['trafiklab_reg'] = G('trafiklab-gtfs-reg', r'VehiclePositions|licen[sc]e|API key', k=4)
print(json.dumps(out, ensure_ascii=False, indent=1)); pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
