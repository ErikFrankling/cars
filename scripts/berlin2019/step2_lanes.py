#!/usr/bin/env python3
"""Recipe step 2. Lane markings of January 2019 on a finished map, without touching its edges, so the routes stay valid.

    step2_lanes.py NAME BASE [--no-turn] [--no-bus] [--lane-fix FILE] [--signals AUDIT.csv] [--dry]

Plain-outputs district/BASE, then:
  bus lanes: a lane tagged designated or only in bus:lanes or psv:lanes, or no in vehicle:lanes and its kin, closes to cars. lanes:psv with no positions closes the rightmost lane only when the lane count includes it.
             Cars turning right from a road with one get their turn from the first lane open to them. The real dashed end of a bus lane, where they share it, is left out.
  turn lanes: turn:lanes on the last piece of a way, when it has as many entries as the piece has lanes. Each target is fed from the lanes marked for its direction; a target no marking reaches keeps its old lanes.
  --lane-fix: cars lanes --json of the previous build; extra feeds on unmarked roads only.
  --signals: signal_audit.py's output. Real crossings (three neighbours or more) with an OSM 2019 signal and none on the map get one.
Every edge seen is logged in district/NAME/lane_tags.csv. Signals are generated again, as they must be when links change."""
import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

D = DISTRICT
CODES = {'left': 'l', 'slight_left': 'L', 'sharp_left': 'l', 'through': 's', 'right': 'r', 'slight_right': 'R', 'sharp_right': 'r', 'reverse': 't', 'merge_to_left': 's', 'merge_to_right': 's', 'none': '', '': ''}


def ways2019():
    txt = subprocess.run(['osmium', 'cat', str(RAW / 'osm/highway2019.osm.pbf'), '-t', 'way', '-f', 'opl', '--no-progress'], capture_output=True, text=True).stdout
    out = {}
    for line in txt.splitlines():
        f = line.split(' ')
        t = next((x[1:] for x in f if x.startswith('T')), '')
        if 'highway=' in t:
            out[f[0][1:]] = {k: re.sub(r'%([0-9a-f]+)%', lambda m: chr(int(m[1], 16)), v) for k, _, v in (x.partition('=') for x in t.split(','))}
    return out


def closed_lanes(t, rev, n):
    """SUMO lane indices closed to cars, and how we know. Lanes in OSM run left to right, in SUMO right to left."""
    side = 'backward' if rev else 'forward'
    keys = [f'{k}:{side}' for k in ('bus:lanes', 'psv:lanes', 'vehicle:lanes', 'motor_vehicle:lanes', 'access:lanes')]
    one = t.get('oneway') in ('yes', '1', '-1')
    if one:
        keys += ['bus:lanes', 'psv:lanes', 'vehicle:lanes', 'motor_vehicle:lanes', 'access:lanes']
    closed, how = set(), []
    for k in keys:
        v = t.get(k)
        if not v:
            continue
        parts = v.split('|')
        bad = ('designated', 'only') if 'bus' in k or 'psv' in k else ('no',)
        if len(parts) == n:
            hit = {n - 1 - i for i, p in enumerate(parts) if p in bad}
            closed |= hit
            how.append(f'{k}={v}')
        elif len(parts) == n + 1 and any(p in bad for p in parts):
            how.append(f'{k}={v}: bus lane not among the {n} on the map, nothing to close')
        else:
            how.append(f'{k}={v}: {len(parts)} entries for {n} lanes, ignored')
    if closed or how:
        return closed, '; '.join(how)
    psv = t.get(f'lanes:psv:{side}') or (t.get('lanes:psv') if one else None) or (t.get('lanes:bus') if one else None)
    if psv and psv.isdigit() and n >= 2:
        f, b, total = t.get('lanes:forward'), t.get('lanes:backward'), t.get('lanes')
        fw, bw = (t.get('lanes:psv:forward') or '0'), (t.get('lanes:psv:backward') or '0')
        if f and b and total and f.isdigit() and b.isdigit() and total.isdigit() and int(f) + int(b) < int(total) and fw.isdigit() and bw.isdigit() and int(f) + int(b) + int(fw) + int(bw) == int(total):
            return set(), f'lanes:psv={psv}, not counted in lanes:{side}, nothing to close'
        return {0}, f'lanes:psv={psv}, counted in the lanes'
    return set(), ''


def turn_tag(t, rev, n):
    side = 'backward' if rev else 'forward'
    v = t.get(f'turn:lanes:{side}') or (t.get('turn:lanes') if t.get('oneway') in ('yes', '1', '-1') or t.get('highway') in ('motorway', 'motorway_link') else None)
    if not v:
        return None, ''
    parts = v.split('|')
    if len(parts) != n:
        return None, f'{v}: {len(parts)} entries for {n} lanes, ignored'
    out = {}
    for i, p in enumerate(parts):
        out[n - 1 - i] = {CODES.get(x.strip(), '') for x in p.split(';')} - {''}
    return out, v


def lanes_for(direction, marks, free):
    """Lanes that may serve a direction: marked for it, else, for a slight turn, marked through, else unmarked."""
    alts = {'L': 'Ls', 'R': 'Rs', 'l': 'lL', 'r': 'rR', 's': 's', 't': 't'}.get(direction, direction)
    for code in alts:
        got = sorted(i for i, m in marks.items() if code in m and i in free)
        if got:
            return got
    return sorted(i for i, m in marks.items() if not m and i in free)


def feed(direction, sources, targets):
    """Pairs of source lane and target lane. A right turn fills from the right, a left from the left, through lanes line up."""
    sources, targets = sorted(sources), sorted(targets)
    if direction in 'lLt':
        sources, targets = sources[::-1], targets[::-1]
    if len(sources) <= len(targets):
        off = 0
        if direction == 's':
            off = (len(targets) - len(sources)) // 2
        return [(s, targets[off + i]) for i, s in enumerate(sources)]
    return [(s, targets[min(i, len(targets) - 1)]) for i, s in enumerate(sources)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('name')
    p.add_argument('base')
    p.add_argument('--no-turn', action='store_true')
    p.add_argument('--no-bus', action='store_true')
    p.add_argument('--lane-fix')
    p.add_argument('--signals')
    p.add_argument('--dry', action='store_true')
    a = p.parse_args()
    out = D / a.name
    out.mkdir(exist_ok=True)
    base = read_net(D / a.base / 'net.net.xml', D / a.base / 'net.pkl')
    ways = ways2019()
    edges = {k: e for k, e in base['edges'].items() if car_lanes(e)}
    last = {}
    for k in edges:
        w, _, i = k.lstrip('-').partition('#')
        r = k.startswith('-')
        i = int(i) if i.isdigit() else 0
        key = (w, r)
        if key not in last or (i < last[key][0] if r else i > last[key][0]):
            last[key] = (i, k)
    last = {v[1] for v in last.values()}
    by_from = collections.defaultdict(list)
    for c in base['conns']:
        by_from[c[0]].append(c)
    log, close, marks = [], {}, {}
    for k, e in edges.items():
        w = ways.get(k.lstrip('-').split('#')[0])
        if w is None:
            continue
        rev = k.startswith('-')
        n = len(e['lanes'])
        if not a.no_bus:
            c, how = closed_lanes(w, rev, n)
            if how:
                log.append(dict(edge=k, name=e['name'], kind='bus', lanes=n, tag=how, applied=','.join(map(str, sorted(c)))))
            if c and len(c) < n:
                close[k] = c
            elif c:
                log[-1]['applied'] = 'would close every lane, ignored'
        if not a.no_turn and k in last:
            m, how = turn_tag(w, rev, n)
            if how:
                log.append(dict(edge=k, name=e['name'], kind='turn', lanes=n, tag=how, applied='yes' if m else ''))
            if m and len({c[1] for c in by_from[k]}) > 1:
                marks[k] = m
    d = pd.DataFrame(log, columns=['edge', 'name', 'kind', 'lanes', 'tag', 'applied'])
    d.to_csv(out / 'lane_tags.csv', index=False)
    print('bus tags', (d.kind == 'bus').sum(), 'edges closed lanes', len(close), 'lanes closed', sum(map(len, close.values())), '| turn tags', (d.kind == 'turn').sum(), 'edges with lanes reassigned', len(marks))
    print(d[d.kind == 'bus'].tag.str.replace(r'=.*?(:|;|$)', r'\1', regex=True).value_counts().head(10).to_string())
    if a.dry:
        return
    pfx = out / 'p'
    subprocess.run(['netconvert', '--sumo-net-file', str(D / a.base / 'net.net.xml'), '--plain-output-prefix', str(pfx), '--no-internal-links', 'false', '--offset.disable-normalization', 'true', '--no-turnarounds', 'true'], check=True, capture_output=True)
    parser = etree.XMLParser(huge_tree=True, resolve_entities=False, no_network=True)
    tree = etree.parse(str(pfx) + '.edg.xml', parser)
    root = tree.getroot()
    xedges = {e.get('id'): e for e in root.findall('edge')}
    for r in root.findall('roundabout'):
        root.remove(r)
    for k, c in close.items():
        e = xedges[k]
        have = {int(l.get('index')): l for l in e.findall('lane')}
        for i in sorted(c):
            l = have.get(i)
            if l is None:
                l = etree.SubElement(e, 'lane', index=str(i))
            l.attrib.pop('disallow', None)
            l.set('allow', 'bus')
    tree.write(str(pfx) + '_fixed.edg.xml')
    con = etree.parse(str(pfx) + '.con.xml', parser).getroot()
    redo = set(close) | set(marks)
    for c in list(con):
        if c.tag in ('crossing', 'walkingArea') or (c.tag == 'connection' and c.get('from') in redo):
            con.remove(c)
    fallback, n_fed = 0, 0
    for k in sorted(redo):
        n = len(edges[k]['lanes'])
        free = set(range(n)) - close.get(k, set())
        by_target = collections.defaultdict(list)
        for c in by_from[k]:
            by_target[c[1]].append(c)
        m = marks.get(k, {i: set() for i in range(n)})
        # a direction no lane is marked for may use an unmarked lane; a marked road with no such lane keeps its old lanes
        for v, cs in sorted(by_target.items()):
            direction = cs[0][5]
            targets = sorted({c[3] for c in cs})
            if k in marks:
                src = lanes_for(direction, m, free)
                if not src:
                    fallback += 1
                    src = sorted({c[2] for c in cs} & free) or [min(free)]
            else:
                src = sorted({c[2] for c in cs} & free)
                if not src:
                    src = [min(free)]
            for s, t in feed(direction, src, targets):
                etree.SubElement(con, 'connection', {'from': k, 'to': v, 'fromLane': str(s), 'toLane': str(t)})
                n_fed += 1
            # a bus lane still goes on, for the buses
            for s in sorted(close.get(k, set())):
                if direction == 's' and any(c[2] == s for c in cs):
                    t = min((c[3] for c in cs if c[2] == s), default=targets[0])
                    etree.SubElement(con, 'connection', {'from': k, 'to': v, 'fromLane': str(s), 'toLane': str(t)})
    print('connections written', n_fed, 'targets no marking reached', fallback)
    if a.lane_fix:
        extra = collections.defaultdict(set)
        into = collections.defaultdict(list)
        for c in base['conns']:
            into[c[1]].append(c)
        skipped = 0
        for pl in json.load(open(a.lane_fix))['top']:
            x, need = pl['edge'], pl['lanes_that_go_there']
            for c in into[x]:
                lj = min(need, key=lambda q: abs(q - c[3]))
                best = min((y for y in into[x] if y[0] == c[0]), key=lambda y: abs(y[3] - lj))
                if any(y[0] == c[0] and y[2] == best[2] and y[3] == lj for y in into[x]):
                    continue
                if c[0] in marks or best[2] in close.get(c[0], ()):
                    skipped += 1
                    continue
                extra[c[0]].add((best[2], x, lj))
        for u, new in extra.items():
            for li, x, lj in sorted(new):
                etree.SubElement(con, 'connection', {'from': u, 'to': x, 'fromLane': str(li), 'toLane': str(lj)})
        print('roads given an extra lane feed', len(extra), 'feeds', sum(map(len, extra.values())), 'skipped, marked or closed', skipped)
    etree.ElementTree(con).write(str(pfx) + '_fixed.con.xml')
    nod = etree.parse(str(pfx) + '.nod.xml', parser)
    if a.signals:
        sg = pd.read_csv(a.signals)
        want = set(sg[(sg.kind == 'osm_signal_not_on_net') & (sg.neighbours >= 3)].junction)
        n_set = 0
        for x in nod.getroot().findall('node'):
            if x.get('id') in want:
                x.set('type', 'traffic_light')
                x.attrib.pop('tl', None)
                n_set += 1
        print('signals added from OSM 2019', n_set, 'of', len(want))
    nod.write(str(pfx) + '_fixed.nod.xml')
    cmd = ['netconvert', '-n', str(pfx) + '_fixed.nod.xml', '-e', str(pfx) + '_fixed.edg.xml', '-x', str(pfx) + '_fixed.con.xml', '-t', str(pfx) + '.typ.xml', '--no-internal-links', 'false', '--offset.disable-normalization', 'true', '--no-turnarounds', 'true', '--geometry.remove', 'false', '--tls.default-type', 'actuated', '--output.original-names', 'false', '--remove-edges.isolated', 'true', '--junctions.corner-detail', '5', '--roundabouts.guess', 'true', '-o', str(out / 'net.net.xml')]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stderr[-500:] if r.returncode else '\n'.join(l for l in r.stderr.splitlines() if 'total messages' in l)[:300])
    r.check_returncode()
    (out / 'net.pkl').unlink(missing_ok=True)
    n = read_net(out / 'net.net.xml', out / 'net.pkl')
    e2 = {k: v for k, v in n['edges'].items() if car_lanes(v)}
    pairs0 = {(c[0], c[1]) for c in base['conns']}
    pairs1 = {(c[0], c[1]) for c in n['conns']}
    print('edges', len(edges), '->', len(e2), 'missing', len(set(edges) - set(e2)), 'added', len(set(e2) - set(edges)), '| turns', len(pairs0), '->', len(pairs1), 'lost', len(pairs0 - pairs1), 'new', len(pairs1 - pairs0), '| tls', base['tls'], '->', n['tls'])
    lost = sorted(pairs0 - pairs1)
    if lost:
        print('lost turns', lost[:12])


if __name__ == '__main__':
    main()
