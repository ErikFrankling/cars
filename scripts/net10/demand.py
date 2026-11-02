#!/usr/bin/env python3
"""One demand for every net: the part of each v2_c4 trip inside the box, as an origin and destination in coordinates, then snapped to each net.
Usage: demand.py od OUT.json | demand.py trips OD.json NET.xml OUT.trips.xml SCALE SEED. Report data-hunt/10."""
import sys, os, gzip, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.spatial import cKDTree
F = DATA / 'truth/stockholm/factorial'
W = DATA / 'truth/maps/net10'
BEGIN, SPAN = 7 * 3600.0, 3600.0

def od(outp):
    n = load_net(W / 'n7.net.xml')
    fwd, back = tf_from_location(n['location'])
    keep = {e: d for e, d in n['edges'].items() if d['lanes']}
    conn = collections.defaultdict(set)
    for c in n['conns']:
        conn[c['frm']].add(c['to'])
    # n7 free-flow times need the full net: approximate outside the box from the file of edge times built once.
    tp = W / 'n7_times.json'
    if tp.exists():
        times = json.loads(tp.read_text())
    else:
        times = {}
        for ev, el in E.iterparse(str(F / 'n7_ramps.net.xml'), events=('end',), tag='edge'):
            if el.get('function') != 'internal':
                ln = el.find('lane')
                if ln is not None:
                    times[el.get('id')] = round(float(ln.get('length')) / max(float(ln.get('speed')), 1.0), 2)
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
        tp.write_text(json.dumps(times))
    def anchor(e):
        s = keep[e]['lanes'][0]['shape']
        a, b = s[len(s) // 2 - 1 if len(s) > 1 else 0], s[len(s) // 2]
        xm, ym = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        lo, la = back(xm, ym)
        return round(lo, 6), round(la, 6), round(math.degrees(math.atan2(s[-1][0] - s[0][0], s[-1][1] - s[0][1])), 0)
    routes = {}; rows = []; total = 0
    with gzip.open(F / 'v2_c4.rou.gz', 'rt') as f:
        for line in f:
            if line.startswith('<route '):
                m = re.match(r'<route id="([^"]+)" edges="([^"]+)"', line)
                routes[m.group(1)] = m.group(2).split()
            elif line.startswith('<vehicle'):
                total += 1
                d = float(re.search(r'depart="([\d.]+)"', line).group(1))
                if d > BEGIN + SPAN or d < BEGIN - 1800:
                    continue
                e = routes[re.search(r'route="([^"]+)"', line).group(1)]
                i = next((k for k, x in enumerate(e) if x in keep), None)
                if i is None:
                    continue
                j = i
                for k in range(i + 1, len(e)):
                    if e[k] in keep:
                        j = k
                    elif times.get(e[k], 99.0) > 8.0:
                        break
                t = d + 1.3 * sum(times.get(x, 0.0) for x in e[:i])
                if BEGIN <= t < BEGIN + SPAN and j > i:
                    rows.append((round(t - BEGIN, 1), e[i], e[j]))
    rows.sort()
    names = sorted({r[1] for r in rows} | {r[2] for r in rows})
    Path(outp).write_text(json.dumps(dict(anchors={e: anchor(e) for e in names}, trips=rows, source_vehicles=total)))
    print('v2_c4 vehicles', total, 'trips through the box in the hour', len(rows), 'distinct ends', len(names))

def trips(odp, netp, outp, scale, seed):
    D = json.loads(Path(odp).read_text()); n = load_net(netp)
    fwd, back = tf_from_location(n['location'])
    samples, owner, bearing = [], [], {}
    into = collections.Counter(); outof = collections.Counter()
    for c in n['conns']:
        into[c['to']] += 1; outof[c['frm']] += 1
    for e, d in n['edges'].items():
        ls = [l for l in d['lanes'] if passenger(l)]
        if not ls:
            continue
        s = ls[0]['shape']
        bearing[e] = math.degrees(math.atan2(s[-1][0] - s[0][0], s[-1][1] - s[0][1]))
        for a, b in zip(s, s[1:]):
            k = max(1, int(math.dist(a, b) / 8))
            for q in range(k + 1):
                samples.append((a[0] + (b[0] - a[0]) * q / k, a[1] + (b[1] - a[1]) * q / k)); owner.append(e)
    T = cKDTree(np.array(samples))
    def snap(an, need_out):
        p = fwd(an[0], an[1])
        d, ix = T.query(p, k=min(60, len(samples)), distance_upper_bound=60)
        best = None
        for dd, i in zip(d, ix):
            if not math.isfinite(dd):
                break
            e = owner[i]
            da = abs((bearing[e] - an[2] + 180) % 360 - 180)
            if da > 50:
                continue
            if need_out and not outof[e]:
                continue
            if not need_out and not into[e]:
                continue
            best = e; break
        return best
    fr = {e: snap(a, True) for e, a in D['anchors'].items()}; to = {e: snap(a, False) for e, a in D['anchors'].items()}
    rng = random.Random(seed * 7919 + 13); miss = 0; k = 0
    with open(outp, 'w') as f:
        f.write('<routes>\n<vType id="h" length="5" minGap="2" accel="2.6" decel="4.5" sigma="0.5" tau="1"/>\n')
        rows = []
        for t, a, b in D['trips']:
            c = int(scale) + (1 if rng.random() < scale - int(scale) else 0)
            for q in range(c):
                x, y = fr.get(a), to.get(b)
                if not x or not y or x == y:
                    miss += 1; continue
                rows.append((t + (rng.uniform(0, 5) if c > 1 else 0), x, y))
        rows.sort()
        for t, x, y in rows:
            f.write(f'<trip id="v{k}" type="h" depart="{t:.1f}" departLane="best" departSpeed="max" from="{x}" to="{y}"/>\n'); k += 1
        f.write('</routes>\n')
    print(netp, 'trips', k, 'unsnapped or identical', miss, 'ends unmapped', sum(v is None for v in fr.values()), sum(v is None for v in to.values()))

if sys.argv[1] == 'od':
    od(sys.argv[2])
else:
    trips(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), int(sys.argv[6]))
