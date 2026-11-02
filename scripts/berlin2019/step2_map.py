#!/usr/bin/env python3
"""Recipe step 2. Audit the cut map against OSM of January 2019 and the real loops, log every issue, write a patch.

Demand is not read here. Writes district/map_issues.csv, district/patch.edg.xml, and prints the audit.
"""
import collections
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

OUT = DISTRICT
OSM = RAW / 'osm'


def ways2019():
    txt = subprocess.run(['osmium', 'cat', str(OSM / 'highway2019.osm.pbf'), '-t', 'way', '-f', 'opl', '--no-progress'], capture_output=True, text=True).stdout
    def tag(t, k):
        m = re.search(r'(?:^|,)' + re.escape(k) + r'=([^,]*)', t)
        return m[1] if m else ''
    out = {}
    for line in txt.splitlines():
        f = line.split(' ')
        t = next((x[1:] for x in f if x.startswith('T')), '')
        if 'highway=' in t:
            out[f[0][1:]] = {k: tag(t, k) for k in ('highway', 'lanes', 'lanes:forward', 'lanes:backward', 'maxspeed', 'oneway', 'bus:lanes:forward', 'bus:lanes:backward', 'bus:lanes', 'turn:lanes', 'lanes:psv', 'busway')}
    return out


def lanes_2019(w, reverse):
    tag = 'lanes:backward' if reverse else 'lanes:forward'
    for k in (tag,):
        if w[k].isdigit():
            return int(w[k])
    if w['lanes'].isdigit():
        n = int(w['lanes'])
        one = w['oneway'] in ('yes', '1', '-1') or w['highway'] in ('motorway', 'motorway_link')
        return n if one else max(1, n // 2) if n % 2 == 0 else None
    return None


def speed_2019(w):
    s = w['maxspeed']
    if s.isdigit():
        return float(s)
    if s in ('DE:urban',):
        return 50.0
    if s in ('DE:zone30', 'DE:zone:30'):
        return 30.0
    return None


def main():
    net = read_net(OUT / 'net.net.xml', OUT / 'net.pkl')
    ways = ways2019()
    print('2019 ways', len(ways))
    edges = {k: e for k, e in net['edges'].items() if car_lanes(e)}
    issues = []
    patch = {}
    stats = collections.Counter()
    def log(kind, edge, detail, action):
        issues.append(dict(kind=kind, edge=edge, detail=detail, action=action))
        stats[kind] += 1

    # the road as it was in 2019
    for k, e in edges.items():
        if k.startswith(':'):
            continue
        rev = k.startswith('-')
        way = k.lstrip('-').split('#')[0]
        cl = car_lanes(e)
        w = ways.get(way)
        if w is None:
            log('way_not_in_osm_2019', k, f'{e["name"]} {e["type"]}', 'kept: edge may be a re-mapped or new road, not checked')
            continue
        n19 = lanes_2019(w, rev)
        if n19 is not None and n19 != len(cl) and len(cl) == len(e['lanes']):
            log('lanes_2023_vs_2019', k, f'{e["name"]} {len(cl)} lanes on the 2023 map, {n19} in 2019', f'set {n19}')
            patch.setdefault(k, {})['numLanes'] = n19
        v19 = speed_2019(w)
        v = cl[0]['speed'] * 3.6
        if v19 is not None and abs(v19 - v) > 3:
            log('speed_2023_vs_2019', k, f'{e["name"]} {v:.0f} km/h on the 2023 map, {v19:.0f} in 2019', f'set {v19:.0f}')
            patch.setdefault(k, {})['speed'] = v19 / 3.6
        elif v19 is None and abs(v - 30) < 3 and w['highway'] in ('primary', 'secondary', 'trunk', 'tertiary', 'primary_link', 'secondary_link'):
            log('speed_30_with_no_2019_tag', k, f'{e["name"]} {w["highway"]} is 30 on the 2023 map, untagged in 2019', 'set 50, the urban default')
            patch.setdefault(k, {})['speed'] = 50 / 3.6
        if any(w[t] for t in ('bus:lanes:forward', 'bus:lanes:backward', 'bus:lanes', 'lanes:psv')) or w['busway']:
            log('bus_lane_2019_not_on_map', k, f'{e["name"]} bus lane tagged in 2019; the v6.4 recipe ignores lane access', 'not patched: cars may use it; to test')

    # loops the real site had against the map; a loop is direct evidence for a lane in May 2019
    sites = pd.read_csv(B19 / 'step0/sites.csv')
    freeze = json.load(open(B19 / 'step1/freeze.json'))
    lanes = pd.read_csv(B19 / 'step0/site_lanes.csv')
    for site in freeze['district_sites']:
        r = sites[sites.site == site].iloc[0]
        ls = lanes[(lanes.site == site) & ~lanes.spur.fillna('').str.contains('BUS|Park|LA')]
        if r.edge not in edges:
            log('site_edge_not_in_cut', r.edge, site, 'site dropped from sensors')
            continue
        n = patch.get(r.edge, {}).get('numLanes', len(car_lanes(edges[r.edge])))
        if len(ls) > n:
            log('more_loops_than_lanes', r.edge, f'{site} {r.street}: {len(ls)} traffic loops, {n} lanes after the OSM patch', f'set {len(ls)}, measured')
            patch.setdefault(r.edge, {})['numLanes'] = len(ls)
        elif len(ls) < n:
            log('loops_cover_part', r.edge, f'{site} {r.street}: {len(ls)} traffic loops, {n} lanes', 'count the loops\' lanes only')

    # junctions and links
    for k, e in edges.items():
        l = car_lanes(e)[0]['length']
        if l < 7.5:
            log('edge_shorter_than_a_car', k, f'{l:.1f} m {e["name"]} {e["type"]}', 'logged, kept')
    conn_out = collections.Counter(c[0] for c in net['conns'])
    conn_in = collections.Counter(c[1] for c in net['conns'])
    for k, e in edges.items():
        if conn_out[k] == 0:
            log('edge_no_exit', k, f'{e["name"]} {e["type"]}', 'boundary or dead end')
        if conn_in[k] == 0:
            log('edge_no_entry', k, f'{e["name"]} {e["type"]}', 'boundary or dead end')
    lane_out = collections.Counter((c[0], c[2]) for c in net['conns'])
    for k, e in edges.items():
        for l in car_lanes(e):
            if conn_out[k] and lane_out[(k, l['index'])] == 0:
                log('lane_no_exit', k, f'lane {l["index"]} of {len(e["lanes"])}, {e["name"]}', 'cars must leave it early')
    jt = collections.Counter(v[0] for v in net['junctions'].values())
    print('junction types', jt.most_common())
    print('tlLogic', net['tls'])
    pd.DataFrame(issues).to_csv(OUT / 'map_issues.csv', index=False)
    with open(OUT / 'patch.edg.xml', 'w') as f:
        f.write('<edges>\n')
        for k, a in sorted(patch.items()):
            f.write(f'  <edge id="{k.replace("&", "&amp;")}"' + ''.join(f' {x}="{v:.3f}"' if isinstance(v, float) else f' {x}="{v}"' for x, v in a.items()) + '/>\n')
        f.write('</edges>\n')
    print('patched edges', len(patch))
    for k, v in stats.most_common():
        print(f'{v:6}  {k}')
    d = pd.DataFrame(issues)
    print(d[d.kind == 'more_loops_than_lanes'].detail.to_string()[:1500])
    print(d[d.kind == 'speed_2023_vs_2019'].detail.str.extract(r'^(.*?) \d+ km/h')[0].value_counts().head(20).to_string())
    print(d[d.kind == 'lanes_2023_vs_2019'].detail.str.extract(r'^(.*?) \d+ lanes')[0].value_counts().head(20).to_string())


if __name__ == '__main__':
    main()
