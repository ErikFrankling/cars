"""Melbourne audit: SCATS sample + signal sites + range-read of an operation-sheet ZIP (only central directory + 1 small member).
Usage: city_review_melb.py run_dir out.json"""
import collections as C, csv, io, json, pathlib, re, resource, sys, urllib.request, zipfile
resource.setrlimit(resource.RLIMIT_AS, (2800*1024**2, 2800*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
def J(n): return json.loads((d/(n+'.body')).read_bytes().decode('utf-8', 'replace'))
pk = {p['name']: p for n in ['vic-search-signals', 'vic-search-count'] for p in J(n)['result']['results']}
for n in ['victorian-traffic-signals', 'tirtl-traffic-counts', 'telemetry-traffic-counts-and-classification', 'historical-annual-average-daily-traffic-volume']:
    p = pk[n]; print('==', n, p.get('license_id'), p.get('metadata_modified')); print((p.get('notes') or '')[:900])
    print([(x.get('name'), x.get('format'), x.get('size')) for x in p['resources']][:8])
    print([x.get('url') for x in p['resources']][:3])
# SCATS one-day stats on the sampled ZIP
z = zipfile.ZipFile(d/'melb-zip.body')
names = sorted(z.namelist()); out['members'] = len(names); out['first_last'] = (names[0], names[-1])
with z.open(names[10]) as f:
    r = csv.DictReader(io.TextIOWrapper(f)); h = r.fieldnames; sites = C.Counter(); det = set(); rows = 0; zero = 0; neg = 0; first = None; vcols = [c for c in h if re.match(r'V\d+$', c)]
    for row in r:
        first = first or row; rows += 1; sites[row['NB_SCATS_SITE']] += 1; det.add((row['NB_SCATS_SITE'], row['NB_DETECTOR']))
        vs = [int(row[c] or 0) for c in vcols]; neg += sum(v < 0 for v in vs); zero += all(v <= 0 for v in vs)
out['day'] = names[10]; out['columns'] = h[:6]+h[-6:]; out['nV'] = len(vcols); out['rows'] = rows; out['sites'] = len(sites); out['detector_rows_unique'] = len(det); out['allzero_rows'] = zero; out['neg_values'] = neg; out['max_det_per_site'] = max(sites.values())
out['first'] = {k: first[k] for k in h[:5]}
print(json.dumps(out, indent=1))
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
