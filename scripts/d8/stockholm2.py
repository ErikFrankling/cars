#!/usr/bin/env python3
"""Stockholm on report 02's net and demand: a district cut from factorial/n7_ramps.net.xml, with the part of each
v2_c4 trip inside it. Same arrivals for every policy. Signal timing is netconvert's generated programs, not real plans.
Usage: stockholm2.py build|run [--scale ...]. Results in research/truth/fig/d8/plan/stockholm2.jsonl."""
import argparse, gzip, json, os, random, re, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path('/home/erikf/projects/personal/cars-data/truth/stockholm/factorial')
WORK = Path('/home/erikf/projects/personal/cars-data/truth/d8/st2')
OUT = ROOT / 'research/truth/fig/d8/plan/stockholm2.jsonl'
CARS = Path(os.environ.get('CARS_BIN', ROOT / 'target/release/cars'))
PLACES = {'district': ('22100,15900,23100,16900', []), 'district_j30': ('22100,15900,23100,16900', ['--junctions.join', 'true', '--junctions.join-dist', '30'])}
BEGIN, SPAN = 7 * 3600.0, 3600.0
AV = '<vType id="av" carFollowModel="CarsAV" length="5" width="1.8" minGap="2.0" accel="2.6" decel="4.5" tau="0.8" reaction="0.3" sigma="0" lcStrategic="1"/>'
HUMAN = '<vType id="av" length="5" minGap="2" accel="2.6" decel="4.5" sigma="0.5" tau="1"/>'


def edge_times():
    t = {}
    for ev, el in ET.iterparse(SRC / 'n7_ramps.net.xml', events=('end',)):
        if el.tag == 'edge':
            if el.get('function') != 'internal':
                ln = el.find('lane')
                if ln is not None:
                    t[el.get('id')] = float(ln.get('length')) / max(float(ln.get('speed')), 1.0)
            el.clear()
    return t


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    times = edge_times()
    for place, (box, extra) in PLACES.items():
        net = WORK / f'{place}.net.xml'
        if not net.exists():
            subprocess.run(['netconvert', '-s', str(SRC / 'n7_ramps.net.xml'), '--keep-edges.in-boundary', box, '--keep-edges.components', '1', '--no-warnings', 'true', *extra, '-o', str(net)], check=True)
        root = ET.parse(net).getroot()
        keep = {e.get('id') for e in root.findall('edge') if e.get('function') != 'internal'}
        conn = {}
        for c in root.findall('connection'):
            conn.setdefault(c.get('from'), set()).add(c.get('to'))
        print(place, 'edges', len(keep), flush=True)
        routes = {}
        out = []
        n_all = 0
        with gzip.open(SRC / 'v2_c4.rou.gz', 'rt') as f:
            for line in f:
                if line.startswith('<route '):
                    m = re.match(r'<route id="([^"]+)" edges="([^"]+)"', line)
                    routes[m.group(1)] = m.group(2).split()
                elif line.startswith('<vehicle'):
                    n_all += 1
                    r = re.search(r'route="([^"]+)"', line)
                    d = float(re.search(r'depart="([\d.]+)"', line).group(1))
                    if d > BEGIN + SPAN or d < BEGIN - 1800:
                        continue
                    e = routes[r.group(1)]
                    i = next((k for k, x in enumerate(e) if x in keep), None)
                    if i is None:
                        continue
                    # Inside it, as far as it stays connected. A merged junction swallows the short links in it.
                    piece = [e[i]]
                    for x in e[i + 1:]:
                        if x in keep:
                            if x not in conn.get(piece[-1], ()):
                                break
                            piece.append(x)
                        elif times.get(x, 99.0) > 8.0:
                            break
                    t = d + 1.3 * sum(times.get(x, 0.0) for x in e[:i])
                    if BEGIN <= t < BEGIN + SPAN and len(piece) > 1:
                        out.append((t - BEGIN, piece))
        out.sort(key=lambda x: x[0])
        print(place, 'trips of', n_all, 'in the hour:', len(out), flush=True)
        (WORK / f'{place}.trips.json').write_text(json.dumps(out))


def routes_file(place, scale, seed, typ):
    trips = json.loads((WORK / f'{place}.trips.json').read_text())
    rng = random.Random(seed * 7919 + 13)
    p = WORK / f'{place}_{scale}_{seed}_{typ}.rou.xml'
    picked = []
    for t, e in trips:
        n = int(scale) + (1 if rng.random() < scale - int(scale) else 0)
        for _ in range(n):
            picked.append((t + rng.uniform(0, 5.0) * (n > 1), e))
    picked.sort(key=lambda x: x[0])
    with p.open('w') as f:
        f.write('<routes>\n' + (AV if typ == 'av' else HUMAN) + '\n')
        for i, (t, e) in enumerate(picked):
            f.write(f'<vehicle id="v{i}" type="av" depart="{t:.1f}" departLane="best" departSpeed="max"><route edges="{" ".join(e)}"/></vehicle>\n')
        f.write('</routes>\n')
    return p, len(picked)


POLICIES = (('krauss_signals', 'krauss', []), ('av_signals', 'av', []), ('av_free', 'av', ['--cj', 'all']), ('av_full', 'av', ['--cj', 'all', '--cj-plan', 'full']), ('av_route', 'av', ['--cj', 'all', '--cj-plan', 'route']))


def run(scales, seeds, policies, places):
    done = {json.dumps(json.loads(l)['case'], sort_keys=True) for l in OUT.read_text().splitlines() if 'error' not in json.loads(l)['result']} if OUT.exists() else set()
    for place in PLACES:
        if places and place not in places:
            continue
        net = WORK / f'{place}.net.xml'
        for scale in scales:
            for seed in seeds:
                for name, typ, args in POLICIES:
                    if policies and name not in policies:
                        continue
                    c = dict(place=place, scale=scale, seed=seed, policy=name)
                    if json.dumps(c, sort_keys=True) in done:
                        continue
                    rou, n = routes_file(place, scale, seed, 'av' if typ == 'av' else 'human')
                    p = subprocess.run([str(CARS), 'av', '--net', str(net), '--routes', str(rou), '--end', str(SPAN + 300), '--cj-warm', '300', '--seed', str(seed)] + args, capture_output=True, text=True)
                    r = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else dict(error=p.stderr[-500:])
                    r.pop('profile', None)
                    r.pop('ids', None)
                    r['n_trips'] = n
                    with OUT.open('a') as f:
                        f.write(json.dumps(dict(case=c, result=r)) + '\n')
                    print(place, scale, seed, name, 'trips', n, 'flow', round(r.get('flow', -1)), 'loss', round(r.get('time_loss', -1), 1), 'arrived', r.get('arrived'), 'ov', r.get('overlap'), 'coll', r.get('collisions'), 'tele', r.get('teleports'), 'stuck', r.get('stuck'), 'j', r.get('junctions'), 'ref', r.get('refused'), 'wall', round(r.get('wall', 0)), r.get('error', '')[-160:], flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('what')
    ap.add_argument('--scales', default='1.0')
    ap.add_argument('--seeds', default='0')
    ap.add_argument('--policies', default='')
    ap.add_argument('--places', default='')
    a = ap.parse_args()
    if a.what == 'build':
        build()
    else:
        run(list(map(float, a.scales.split(','))), list(map(int, a.seeds.split(','))), set(filter(None, a.policies.split(','))), set(filter(None, a.places.split(','))))
