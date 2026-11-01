#!/usr/bin/env python3
"""Close-up clips and stills of intersections. Restartable: finished files are skipped.

Run inside nix develop. GPU jobs hold /tmp/cars-gpu.lock. Each place is simulated once into a
trace, then every camera is drawn from it, so clips, stills and physics_qa all see the same run.
Delete a trace to simulate again.
"""
import argparse
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('/home/erikf/projects/personal/cars-data')
GALLERY = DATA / 'videos/gallery'
CITIES = {
    'berlin': (DATA / 'best/berlin.net.xml', DATA / 'best/berlin.rou.gz'),
    'stockholm': (DATA / 'stockholm/stockholm.net.xml', DATA / 'stockholm/stockholm60.rou.gz'),
}
CITY_ARGS = ['--capacity', '300000', '--dt', '1', '--time-to-teleport', '120', '--ignore-junction-blocker', '20']
KINDS = ['signal', 'priority', 'roundabout', 'zipper', 'ramp']
LEAD = 5  # seconds traced before a clip, so a lane change in progress is drawn right


def run(args, **kw):
    print(' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kw)


def write_net(d, nodes, edges, extra=''):
    (d / 'n.nod.xml').write_text('<nodes>' + ''.join(
        f'<node id="{i}" x="{x}" y="{y}" type="{t}"/>' for i, x, y, t in nodes) + '</nodes>')
    body = ''
    for e in edges:
        shape = f' shape="{e["shape"]}"' if 'shape' in e else ''
        body += (f'<edge id="{e["id"]}" from="{e["from"]}" to="{e["to"]}" priority="{e.get("priority", 1)}" '
                 f'numLanes="{e.get("lanes", 1)}" speed="{e.get("speed", 13.89)}"{shape}/>')
    (d / 'n.edg.xml').write_text('<edges>' + body + extra + '</edges>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds',
         '--junctions.corner-detail', '8', '--no-internal-links', 'false'], capture_output=True)


def net_offset(net):
    for _, e in ET.iterparse(net, events=('start',)):
        if e.tag == 'location':
            return [float(v) for v in e.get('netOffset').split(',')]
    return [0.0, 0.0]


def write_routes(d, flows):
    vt = '<vType id="car" vClass="passenger" sigma="0.5"/><vType id="truck" vClass="truck" length="10" sigma="0.5"/>'
    body = vt
    for i, (edges, rate, *rest) in enumerate(flows):
        kind = rest[0] if rest else 'car'
        body += (f'<route id="r{i}" edges="{edges}"/><flow id="f{i}" type="{kind}" route="r{i}" begin="0" end="900" '
                 f'vehsPerHour="{rate}" departLane="best" departSpeed="max"/>')
    (d / 'routes.xml').write_text('<routes>' + body + '</routes>')


def cross(d, kind, main_lanes=2, side_lanes=1, arm=220):
    nodes = [('c', 0, 0, kind), ('w', -arm, 0, 'priority'), ('e', arm, 0, 'priority'), ('s', 0, -arm, 'priority'), ('n', 0, arm, 'priority')]
    edges = []
    for a, b, lanes, pr in [('w', 'c', main_lanes, 3), ('c', 'e', main_lanes, 3), ('e', 'c', main_lanes, 3), ('c', 'w', main_lanes, 3),
                            ('s', 'c', side_lanes, 1), ('c', 'n', side_lanes, 1), ('n', 'c', side_lanes, 1), ('c', 's', side_lanes, 1)]:
        edges.append(dict(id=a + b, **{'from': a, 'to': b}, lanes=lanes, priority=pr))
    write_net(d, nodes, edges)
    write_routes(d, [('wc ce', 700), ('ec cw', 700), ('sc cn', 300), ('nc cs', 300), ('wc cn', 180), ('ec cs', 150), ('sc ce', 150), ('nc cw', 120),
                     ('wc cs', 150), ('ec cn', 140), ('wc ce', 60, 'truck')])
    return dict(junction='c')


def roundabout(d, radius=22, arm=220):
    ring = ['a', 'b', 'c', 'd']
    angles = {'a': 180, 'b': 270, 'c': 0, 'd': 90}
    outer = {'a': 'w', 'b': 's', 'c': 'e', 'd': 'n'}
    point = lambda deg, r=radius: (round(r * math.cos(math.radians(deg)), 2), round(r * math.sin(math.radians(deg)), 2))
    nodes = [(k, *point(angles[k]), 'priority') for k in ring]
    nodes += [(outer[k], *point(angles[k], arm), 'priority') for k in ring]
    edges = []
    for i, k in enumerate(ring):
        nxt = ring[(i + 1) % 4]
        arc = ' '.join('%g,%g' % point(angles[k] + 90 * t / 16) for t in range(17))
        edges.append(dict(id=k + nxt, **{'from': k, 'to': nxt}, priority=3, shape=arc, speed=8.33))
        edges.append(dict(id=outer[k] + k, **{'from': outer[k], 'to': k}))
        edges.append(dict(id=k + outer[k], **{'from': k, 'to': outer[k]}))
    write_net(d, nodes, edges, '<roundabout nodes="a b c d" edges="ab bc cd da"/>')
    write_routes(d, [('wa ab bc ce', 500), ('sb bc cd dn', 400), ('ec cd da aw', 500), ('nd da ab bs', 400), ('wa ab bs', 200), ('ec cd dn', 200), ('sb bc ce', 200), ('nd da aw', 200)])
    return dict(center=[0, 0], metres_per_pixel=0.07)


def zipper(d):
    nodes = [('c', 0, 0, 'zipper'), ('a', -220, 10, 'priority'), ('b', -220, -10, 'priority'), ('e', 220, 0, 'priority')]
    edges = [dict(id='ac', **{'from': 'a', 'to': 'c'}), dict(id='bc', **{'from': 'b', 'to': 'c'}), dict(id='ce', **{'from': 'c', 'to': 'e'})]
    write_net(d, nodes, edges)
    write_routes(d, [('ac ce', 800), ('bc ce', 800)])
    return dict(junction='c')


def on_ramp(d):
    nodes = [('w', -400, 0, 'priority'), ('m', 0, 0, 'priority'), ('r', -260, -60, 'priority'), ('k', 180, 0, 'priority'), ('e', 500, 0, 'priority')]
    edges = [dict(id='wm', **{'from': 'w', 'to': 'm'}, lanes=2, speed=27.78, priority=5),
             dict(id='rm', **{'from': 'r', 'to': 'm'}, lanes=1, speed=19.44, priority=2),
             dict(id='mk', **{'from': 'm', 'to': 'k'}, lanes=3, speed=27.78, priority=5),
             dict(id='ke', **{'from': 'k', 'to': 'e'}, lanes=2, speed=27.78, priority=5)]
    write_net(d, nodes, edges)
    write_routes(d, [('wm mk ke', 2600), ('rm mk ke', 700), ('wm mk ke', 200, 'truck')])
    return dict(center=[90, -5], metres_per_pixel=0.16)


def lane_drop(d):
    nodes = [('w', -400, 0, 'priority'), ('k', 0, 0, 'priority'), ('e', 300, 0, 'priority')]
    edges = [dict(id='wk', **{'from': 'w', 'to': 'k'}, lanes=3, priority=3), dict(id='ke', **{'from': 'k', 'to': 'e'}, lanes=2, priority=3)]
    write_net(d, nodes, edges)
    write_routes(d, [('wk ke', 2700), ('wk ke', 150, 'truck')])
    return dict(junction='k', metres_per_pixel=0.12)


FOLLOW = {'signal': 'f6.6', 'priority': 'f4.7', 'roundabout': 'f0.19'}
FIXTURES = {
    'signal': lambda d: cross(d, 'traffic_light'),
    'priority': lambda d: cross(d, 'priority'),
    'roundabout': roundabout,
    'all-way-stop': lambda d: cross(d, 'allway_stop', main_lanes=1),
    'zipper': zipper,
    'on-ramp': on_ramp,
    'lane-drop': lane_drop,
}


def small_job(name, a):
    d = a.out / 'fixtures' / name
    d.mkdir(parents=True, exist_ok=True)
    meta = d / 'camera.json'
    if not meta.exists() or not (d / 'net.xml').exists():
        camera = FIXTURES[name](d)
        if 'center' in camera:
            camera['center'] = [c + o for c, o in zip(camera['center'], net_offset(d / 'net.xml'))]
        meta.write_text(json.dumps(camera))
    camera = json.loads(meta.read_text())
    base = a.out / name
    begin, end = 150.0, 150.0 + a.seconds
    views = make_views(base, name, camera, begin, end, 'Generated test junction, dt 0.1, sigma 0.5')
    follow = base / 'follow.mp4'
    if name in FOLLOW and not follow.exists():
        views.append(dict(follow=FOLLOW[name], metres_per_pixel=0.09, title=f'{name}: following {FOLLOW[name]}', overlay=['speed', 'state', 'leader', 'braking'], out=str(follow)))
    if not views:
        print(name, 'done')
        return
    spec = base / 'views.json'
    base.mkdir(parents=True, exist_ok=True)
    spec.write_text(json.dumps({'views': views}))
    trace = base / 'run.trace'
    if not trace.exists():
        partial = trace.with_suffix('.partial')
        run(['flock', '/tmp/cars-gpu.lock', a.cars, 'run', '--net', d / 'net.xml', '--routes', d / 'routes.xml', '--dt', '0.1', '--end', end + 1,
             '--trace', partial, '--trace-begin', begin - LEAD, '--trace-end', end + 1], stdout=subprocess.DEVNULL)
        partial.replace(trace)
    run(['flock', '/tmp/cars-gpu.lock', a.cars, 'replay', '--net', d / 'net.xml', '--trace', trace, '--begin', begin, '--end', end, '--views', spec])


def make_views(base, title, camera, begin, end, subtitle):
    """A plain clip and a debug clip with stills, leaving out whatever already exists."""
    views = []
    middle = (begin + end) / 2
    plain = base / 'clip.mp4'
    debug = base / 'clip-debug.mp4'
    stills = [(begin, base / 'start.png'), (middle, base / 'middle.png')]
    missing = [t for t, p in stills if not p.exists()]
    if not plain.exists() or missing:
        v = dict(camera, title=title, subtitle=subtitle)
        if not plain.exists():
            v['out'] = str(plain)
        if missing:
            # The renderer names several stills by time; give each its own view to keep names stable.
            views += [dict(camera, title=title, subtitle=subtitle, png=str(p), shots=[t]) for t, p in stills if not p.exists()]
        if 'out' in v:
            views.append(v)
    overlay = ['speed', 'leader', 'braking', 'state', 'foes', 'events']
    if not debug.exists():
        views.append(dict(camera, title=title, subtitle=subtitle + ' | debug', overlay=overlay, out=str(debug)))
    still = base / 'debug.png'
    if not still.exists():
        views.append(dict(camera, title=title, subtitle=subtitle + ' | debug', overlay=overlay, png=str(still), shots=[middle]))
    return views


def city_job(city, a):
    net, routes = CITIES[city]
    cache = a.out / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    sim_begin, begin = a.city_warm_from, a.city_begin
    end = begin + a.seconds
    edge_csv = cache / f'{city}.edges.csv'
    trace = cache / f'{city}.trace'
    if not trace.exists() or not edge_csv.exists():
        run(['free', '-g'])
        partial, temporary = trace.with_suffix('.partial'), edge_csv.with_suffix('.partial')
        run(['flock', '/tmp/cars-gpu.lock', a.cars, 'run', '--net', net, '--routes', routes, *CITY_ARGS, '--begin', sim_begin, '--end', end + 1, '--edge-csv', temporary, '--edge-interval', 900,
             '--trace', partial, '--trace-begin', begin - LEAD, '--trace-end', end + 1], stdout=subprocess.DEVNULL)
        partial.replace(trace)
        temporary.replace(edge_csv)
    listing = cache / f'{city}.junctions.json'
    if not listing.exists():
        out = subprocess.run([str(a.cars), 'junctions', '--net', str(net), '--edge-csv', str(edge_csv), '--window', f'{sim_begin},{begin}', '--limit', str(a.per_kind + 1), '--json'], check=True, capture_output=True, text=True).stdout
        listing.write_text(out)
    rows = json.loads(listing.read_text())
    views = []
    for kind in KINDS:
        chosen = [r for r in rows if r['type'] == kind][:a.per_kind]
        if not chosen:
            print(city, 'has no', kind, 'junction')
        for i, r in enumerate(chosen):
            base = a.out / f'{city}-{kind}-{i}'
            base.mkdir(parents=True, exist_ok=True)
            (base / 'camera.json').write_text(json.dumps(dict(r, begin=begin, end=end)))
            title = f'{city.title()} {kind}, junction {r["id"]}'
            subtitle = f'{r["score"]:.0f} vehicles entered in the hour before, {int(begin // 3600):02d}:{int(begin % 3600 // 60):02d} peak, dt 1'
            views += make_views(base, title, dict(junction=r['id']), begin, end, subtitle)
    if not views:
        print(city, 'done')
        return
    spec = cache / f'{city}.views.json'
    spec.write_text(json.dumps({'views': views}))
    run(['free', '-g'])
    run(['flock', '/tmp/cars-gpu.lock', a.cars, 'replay', '--net', net, '--trace', trace, '--begin', begin, '--end', end, '--views', spec])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cars', type=Path, default=ROOT / 'target/release/cars')
    p.add_argument('--out', type=Path, default=GALLERY)
    p.add_argument('--only', nargs='+', help='fixture or city names')
    p.add_argument('--seconds', type=float, default=15)
    p.add_argument('--city-begin', type=float, default=28800, help='start of clips in a city, seconds')
    p.add_argument('--city-warm-from', type=float, default=25200)
    p.add_argument('--per-kind', type=int, default=2)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for name in FIXTURES:
        if not a.only or name in a.only:
            small_job(name, a)
    for city in CITIES:
        if not a.only or city in a.only:
            city_job(city, a)


if __name__ == '__main__':
    main()
