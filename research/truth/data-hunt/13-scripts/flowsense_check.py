# Reproduce FlowSense correlation with Stockholm measured counts, stream-parsing the GeoJSON line by line.
# Usage: python3 -I flowsense_check.py traffic_flows.zip ground_truth.zip
import sys, json, zipfile, math, resource, collections
resource.setrlimit(resource.RLIMIT_AS, (1800*1024*1024,)*2)
flows, gt = sys.argv[1], sys.argv[2]
zg = zipfile.ZipFile(gt)
pts = []
keys = None
for line in zg.open('ground_truth/preprocessed/ground_truth_flows_cars_sthlm_2024.geojson'):
    line = line.decode().strip().rstrip(',')
    if not line.startswith('{ "type": "Feature"'): continue
    f = json.loads(line); p = f['properties']
    if keys is None:
        keys = list(p); print('gt fields', keys)
    c = f['geometry']['coordinates']
    if f['geometry']['type'].startswith('Multi'): c = c[0]
    m = c[len(c)//2]
    pts.append((m[0], m[1], p))
print('gt features', len(pts))
flowkey = [k for k in keys if 'flöde' in k.lower() or 'trafik' in k.lower()]
print('flow-ish keys', flowkey)
def val(p):
    for k in ('adt','ÅMVD','amvd','antal_fordon','trafikflöde_alla','trafikflöde'):
        if p.get(k) is not None: return p[k]
    return None
print('sample', {k: pts[0][2][k] for k in keys[:60] if pts[0][2][k] is not None})
grid = collections.defaultdict(list)
for i, (x, y, p) in enumerate(pts): grid[(int(x//50), int(y//50))].append(i)
zf = zipfile.ZipFile(flows)
for name in sys.argv[3:]:
    best = {}; n = 0; tot = 0; maxc = 0; lens = 0.0
    for line in zf.open(f'traffic_flows/{name}.geojson'):
        if not line.startswith(b'{ "type": "Feature"'): continue
        f = json.loads(line.decode().strip().rstrip(','))
        n += 1
        p = f['properties']
        ck = [k for k in p if k.startswith('trajcount')][0]
        v = p[ck] or 0; tot += v; maxc = max(maxc, v)
        c = f['geometry']['coordinates']
        for a in c[:: max(1, len(c)//8)] + [c[-1]]:
            g = (int(a[0]//50), int(a[1]//50))
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for i in grid.get((g[0]+dx, g[1]+dy), ()):
                        d = math.hypot(a[0]-pts[i][0], a[1]-pts[i][1])
                        if d <= 25 and (i not in best or d < best[i][0]): best[i] = (d, v, p.get('maxspeed'))
    print(name, 'segments', n, 'sum trajcount', tot, 'max', maxc, 'count_key', ck, 'matched_gt', len(best))
    import pickle
    pickle.dump({i:(best[i], pts[i][2]) for i in best}, open(f'/home/erikf/projects/personal/cars-data/datasets/flowsense-se/match_{name}.pkl','wb'))
