#!/usr/bin/env python3
"""Polite collector for Hamburg's open traffic-signal SensorThings API (dl-de/by-2.0,
attribution: "Freie und Hansestadt Hamburg, zuständige Behörde"). The API keeps ~9 days.

  hamburg_signals.py static           save lights, lane connections, geometry, datastreams (once)
  hamburg_signals.py pick [N]         choose a district of N (default 50) live, connected lights
  hamburg_signals.py run              backfill the kept history, then poll forever (restart-safe)
  hamburg_signals.py stats            size per day and rows per layer

Data: $HS_ROOT (default /home/erikf/projects/personal/cars-data/datasets/hamburg-signals)
  static/*.json.gz, district.json, state.json, days/YYYY-MM-DD.tsv.gz  (junction layer stream time result)
Standard library only. Sequential requests, ~3/s, backoff on errors.
"""
import gzip, json, math, os, sys, time, urllib.parse, urllib.request, urllib.error, datetime as dt, collections

B = 'https://tld.iot.hamburg.de/v1.1'
ROOT = os.environ.get('HS_ROOT', '/home/erikf/projects/personal/cars-data/datasets/hamburg-signals')
LAYERS = ['primary_signal', 'signal_program', 'detector_car', 'detector_pt', 'detector_bike']
GAP = 0.2          # seconds between requests
POLL = 600         # seconds between rounds
WINDOW = 2 * 3600  # seconds of history per query chunk
HISTORY = 9 * 86400
OVERLAP = 300      # seconds re-read each round to catch late rows
UA = 'cars-research-hamburg-signals/1 (polite, sequential, ~3 req/s)'
last_req = 0.0


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse(s):
    return dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc)


def get(url, params=None):
    global last_req
    if params:
        url += '?' + urllib.parse.urlencode(params)
    for a in range(8):
        w = last_req + GAP - time.time()
        if w > 0:
            time.sleep(w)
        last_req = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(min(600, 10 * 2 ** a)); continue
            if e.code in (403, 404) and a < 2:
                time.sleep(30); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            time.sleep(min(600, 10 * 2 ** a))
    raise RuntimeError('giving up on ' + url)


def pages(url, params):
    d = get(url, params)
    while True:
        yield d
        nl = d.get('@iot.nextLink')
        if not nl or not d.get('value'):
            return
        d = get(nl)


def atomic_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def static():
    os.makedirs(ROOT + '/static', exist_ok=True)
    out = gzip.open(ROOT + '/static/things.jsonl.gz', 'wt')
    n = 0
    for d in pages(B + '/Things', {'$top': 100, '$orderby': '@iot.id asc', '$count': 'false',
                                   '$expand': 'Datastreams($select=@iot.id,name,properties,unitOfMeasurement),Locations($select=@iot.id,location)'}):
        for t in d['value']:
            out.write(json.dumps(t, separators=(',', ':')) + '\n'); n += 1
        if n % 2000 == 0:
            print('things', n, flush=True)
    out.close()
    for name in ('Sensors', 'ObservedProperties'):
        rows = [v for d in pages(B + '/' + name, {'$top': 1000}) for v in d['value']]
        with gzip.open(ROOT + f'/static/{name}.json.gz', 'wt') as f:
            json.dump(rows, f)
    with gzip.open(ROOT + '/static/datastreams_sample_layers.json.gz', 'wt') as f:
        json.dump({'saved': iso(now()), 'licence': 'dl-de/by-2.0', 'attribution': 'Freie und Hansestadt Hamburg, zuständige Behörde'}, f)
    print('static done', n, 'things', flush=True)


def load_things():
    J = {}
    with gzip.open(ROOT + '/static/things.jsonl.gz', 'rt') as f:
        for line in f:
            t = json.loads(line)
            p = t['properties']
            j = J.setdefault(p.get('trafficLightsID') or t['name'].split('_')[0], {'conns': [], 'pts': [], 'ds': collections.defaultdict(list)})
            j['conns'].append(t['name'])
            for loc in t.get('Locations', []):
                g = (loc.get('location') or {}).get('geometry')
                if not g or not g.get('coordinates'):
                    continue
                lines = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
                j['pts'].append(lines[0][0])
            for ds in t.get('Datastreams', []):
                j['ds'][ds['properties'].get('layerName')].append(ds['@iot.id'])
    return J


def centre(j):
    xs = [p[0] for p in j['pts']]; ys = [p[1] for p in j['pts']]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def km(a, b):
    dx = (a[0] - b[0]) * 111.32 * math.cos(math.radians(a[1])); dy = (a[1] - b[1]) * 110.57
    return math.hypot(dx, dy)


def pick(n=50):
    J = load_things()
    cen = {k: centre(j) for k, j in J.items() if j['pts']}
    live = {}
    cutoff = now() - dt.timedelta(hours=1)
    for k in cen:
        ids = J[k]['ds'].get('primary_signal', [])
        d = get(B + '/Observations', {'$top': 1, '$select': 'phenomenonTime',
                '$filter': f"Datastream/Thing/properties/trafficLightsID eq '{k}' and Datastream/properties/layerName eq 'primary_signal' and phenomenonTime ge {iso(cutoff)} and phenomenonTime lt {iso(now())}"})
        if d['value']:
            live[k] = True
    ks = list(live)
    print('lights', len(cen), 'live', len(ks), flush=True)
    best = None
    for s in ks:   # seed with the most live neighbours; district = n nearest live lights, weighted by connections
        near = sorted(ks, key=lambda k: km(cen[s], cen[k]))[:n]
        r = km(cen[s], cen[near[-1]])
        if best is None or r < best[0]:
            best = (r, s, near)
    r, s, near = best
    dist = {'seed': s, 'radius_km': round(r, 2), 'n': len(near), 'connections': sum(len(J[k]['conns']) for k in near),
            'lights': {k: {'centre': cen[k], 'connections': len(J[k]['conns'])} for k in near}}
    atomic_json(ROOT + '/district.json', dist)
    print(json.dumps({x: dist[x] for x in ('seed', 'radius_km', 'n', 'connections')}))


def append_rows(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[r[3][:10]].append('\t'.join(map(str, r)) + '\n')
    for day, lines in by.items():
        data = gzip.compress(''.join(lines).encode(), 6)
        with open(f'{ROOT}/days/{day}.tsv.gz', 'ab') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())


def run():
    os.makedirs(ROOT + '/days', exist_ok=True)
    lights = list(json.load(open(ROOT + '/district.json'))['lights'])
    sp = ROOT + '/state.json'
    state = json.load(open(sp)) if os.path.exists(sp) else {}
    while True:
        t0 = time.time(); total = 0; behind = False
        if os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize < 5e9:
            print('disk low, pausing', flush=True); time.sleep(3600); continue
        for k in lights:
            for layer in LAYERS:
                key = f'{k}/{layer}'
                st = state.setdefault(key, {'floor': iso(now() - dt.timedelta(seconds=HISTORY - 600)), 'seen': []})
                while True:
                    floor = parse(st['floor']); end = min(floor + dt.timedelta(seconds=WINDOW), now() - dt.timedelta(seconds=5))
                    if end <= floor:
                        break
                    seen = {tuple(x) for x in st['seen']}
                    flt = (f"Datastream/Thing/properties/trafficLightsID eq '{k}' and Datastream/properties/layerName eq '{layer}' "
                           f"and phenomenonTime ge {iso(floor)} and phenomenonTime lt {iso(end)}")
                    rows = []; keep = []
                    newfloor = end - dt.timedelta(seconds=OVERLAP)
                    for d in pages(B + '/Observations', {'$top': 1000, '$filter': flt, '$orderby': 'phenomenonTime asc',
                                                         '$select': 'phenomenonTime,result', '$expand': 'Datastream($select=@iot.id)'}):
                        for o in d['value']:
                            sid = o['Datastream']['@iot.id']; t = o['phenomenonTime'][:19] + 'Z'
                            if (sid, t) in seen:
                                if parse(t) >= newfloor: keep.append([sid, t])
                                continue
                            rows.append((k, layer, sid, t, o['result']))
                            if parse(t) >= newfloor: keep.append([sid, t])
                    if rows:
                        append_rows(rows); total += len(rows)
                    st['floor'] = iso(newfloor) if newfloor > floor else iso(end); st['seen'] = keep
                    atomic_json(sp, state)
                    if end < now() - dt.timedelta(seconds=POLL):
                        behind = True
                    break
        print(iso(now()), 'round rows', total, 'took', int(time.time() - t0), 's', flush=True)
        if not behind:
            time.sleep(max(30, POLL - (time.time() - t0)))


def stats():
    tot = 0
    for f in sorted(os.listdir(ROOT + '/days')):
        sz = os.path.getsize(f'{ROOT}/days/{f}'); tot += sz
        n = sum(1 for _ in gzip.open(f'{ROOT}/days/{f}', 'rt'))
        print(f, f'{sz/1e6:.1f} MB', n, 'rows')
    print('total', f'{tot/1e6:.1f} MB')


if __name__ == '__main__':
    c = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if c == 'static': static()
    elif c == 'pick': pick(int(sys.argv[2]) if len(sys.argv) > 2 else 50)
    elif c == 'run': run()
    elif c == 'stats': stats()
    else: sys.exit(__doc__)
