"""Clip SCATS weekday sample and TIRTL to Greater Melbourne; range-read an operation-sheet ZIP directory and one member.
Usage: city_review_melb2.py run_dir out.json"""
import collections as C, csv, io, json, pathlib, re, resource, sys, urllib.request, zipfile
resource.setrlimit(resource.RLIMIT_AS, (2800*1024**2, 2800*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
def rows(n):
    return list(csv.DictReader(io.StringIO((d/(n+'.body')).read_bytes().decode('utf-8-sig', 'replace'))))
sig = rows('vic-signals-csv'); print(sig[0]); out['signals_rows'] = len(sig); out['signal_columns'] = list(sig[0].keys())
latk = next(k for k in sig[0] if 'lat' in k.lower()); lonk = next(k for k in sig[0] if 'lon' in k.lower() or 'lng' in k.lower())
idk = next(k for k in sig[0] if 'site' in k.lower() and 'id' in k.lower() or k.lower() in ('site_no', 'tfm_id', 'site_number', 'siteno'))
print('keys', latk, lonk, idk)
B = (-38.25, -37.45, 144.55, 145.55)  # Greater Melbourne bounding box, chosen here
mel = {}
for s in sig:
    try: a, o = float(s[latk]), float(s[lonk])
    except: continue
    if B[0] < a < B[1] and B[2] < o < B[3]: mel[str(s[idk]).strip().lstrip('0')] = (a, o)
out['signals_melb_bbox'] = len(mel); out['bbox'] = B
for k in sig[0]:
    v = C.Counter(s[k] for s in sig)
    if 1 < len(v) < 12: out['sig_col_'+k] = v.most_common(8)
z = zipfile.ZipFile(d/'melb-zip.body')
day = 'VSDATA_20261020.csv'  # a Tuesday
stats = C.Counter(); perM = C.Counter(); liveM = C.Counter(); peak = []
with z.open(day) as f:
    r = csv.DictReader(io.TextIOWrapper(f)); vc = [f'V{i:02d}' for i in range(96)]
    for row in r:
        sid = row['NB_SCATS_SITE'].strip().lstrip('0'); inm = sid in mel
        v = [int(row[c] or 0) for c in vc]
        neg = sum(x < 0 for x in v); pos = sum(x > 0 for x in v)
        stats['rows'] += 1; stats['neg_values'] += neg; stats['rows_with_neg'] += neg > 0; stats['rows_all_nonpos'] += pos == 0
        if inm:
            stats['melb_rows'] += 1; perM[sid] += 1; live = pos >= 48 and neg == 0
            stats['melb_live'] += live; stats['melb_nonpos'] += pos == 0; stats['melb_neg'] += neg > 0
            if live: liveM[sid] += 1; peak.append(max(v[28:38]))
out['day'] = day; out.update(stats)
out['melb_sites_in_file'] = len(perM); out['melb_sites_with_ge1_live_detector'] = len(liveM); out['melb_sites_ge4_live'] = sum(c >= 4 for c in liveM.values())
out['melb_live_detectors_per_site_median'] = sorted(liveM.values())[len(liveM)//2] if liveM else None
peak.sort(); out['melb_live_peak15_q50_q95_max'] = (peak[len(peak)//2], peak[int(len(peak)*.95)], peak[-1])
ti = rows('vic-tirtl-sites'); print(ti[0]); out['tirtl_sites'] = len(ti); out['tirtl_cols'] = list(ti[0].keys())
la = next(k for k in ti[0] if 'lat' in k.lower()); lo = next(k for k in ti[0] if 'lon' in k.lower())
tin = [t for t in ti if t[la] and t[lo] and B[0] < float(t[la]) < B[1] and B[2] < float(t[lo]) < B[3]]; out['tirtl_melb'] = len(tin)
for k in ti[0]:
    v = C.Counter(t[k] for t in ti)
    if 1 < len(v) < 8: out['ti_'+k] = v.most_common(6)
b = (d/'vic-tirtl-oct.body').read_bytes()[:4]
try:
    z2 = zipfile.ZipFile(d/'vic-tirtl-oct.body'); n = z2.namelist(); out['tirtl_zip'] = n[:3]; f = z2.open(n[0])
except zipfile.BadZipFile:
    f = open(d/'vic-tirtl-oct.body', 'rb')
r = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig')); first = next(r); out['tirtl_row'] = first
n = 1; s = set(); ts = set()
keyS = next(k for k in first if 'site' in k.lower()); 
for row in r:
    n += 1; s.add(row[keyS])
    if n > 3000000: break
out['tirtl_rows_scanned'] = n; out['tirtl_active_sites_scanned'] = len(s)
print(json.dumps(out, indent=1)); pathlib.Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
