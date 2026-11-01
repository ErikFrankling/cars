"""Compact views of saved untrusted JSON bodies. Usage: city_review_peek.py run_dir"""
import json, pathlib, sys, re
d = pathlib.Path(sys.argv[1])
def J(n): return json.loads((d/(n+'.body')).read_bytes().decode('utf-8', 'replace'))
for n in ['paris-sample', 'nyc-crz', 'nyc-speeds', 'newcastle-sensors', 'koda-anon', 'hh-lsa', 'hh-things']:
    print('==', n, (d/(n+'.body')).read_bytes()[:900].decode('utf-8', 'replace'))
m = J('nyc-crz-meta'); print('== nyc meta', m.get('name'), m.get('rowsUpdatedAt'), (m.get('description') or '')[:900], [c['name'] for c in m.get('columns', [])], m.get('license'))
for n in ['vic-search-travel', 'vic-search-bluetooth', 'vic-search-vista', 'vic-search-speed']:
    r = J(n)['result']; print('==', n, r['count']); print([(p['name'], p.get('license_id')) for p in r['results']][:20])
r = J('madrid-traf-search')['result']; print('== madrid', r['count'], [p['name'] for p in r['results']])
r = J('madrid-semaforos')['result']; print('== madrid sem', r['count'], [p['name'] for p in r['results']])
r = J('hh-count-search')['result']; print('== hh', r['count'], [p['name'] for p in r['results']])
m = J('madrid-api')['result']; print('== madrid api', m.get('title'), m.get('license_id'), m.get('temporal_coverage'), len(m['resources']))
print([ (x.get('name'), (x.get('url') or '')[-60:]) for x in m['resources']][:6], '...', [ (x.get('name')) for x in m['resources']][-6:])
print(json.dumps({k: m.get(k) for k in m if k not in ('resources', 'notes') and isinstance(m.get(k), (str, int))}, ensure_ascii=False)[:800])
c = J('crtm-open-api'); print('== crtm', len(c.get('data', [])), [(x['attributes'].get('name'), x['attributes'].get('type'), x['attributes'].get('url') or x['attributes'].get('landingPage')) for x in c.get('data', [])][:12])
m = J('vic-volume-api')['result']; print('== vic', m.get('title'), m.get('license_id'), len(m['resources'])); print((m.get('notes') or '')[:1500]);
print(sorted(x.get('name','') for x in m['resources'])[:4], sorted(x.get('name','') for x in m['resources'])[-4:])
m = J('vic-config-api')['result']; print('== vic cfg', m.get('title'), m.get('license_id'), len(m['resources'])); print((m.get('notes') or '')[:1500]); print([(x.get('name'), x.get('size')) for x in m['resources']][:6])
