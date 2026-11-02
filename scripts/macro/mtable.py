"""Movement table of a SUMO-format net: rung 3, D step 1 and B 5.2. No simulation.

A movement is (from edge, to edge). A connection is one lane's way of making it. Capacities follow D's table:
signal protected s*f_dir*g/C; permissive g/C*Siegloch against the flow it yields to; give-way Siegloch with HBS gaps;
right before left the same with shorter gaps (weakly grounded, flagged); no foes the mid-block value.
Everything that depends on flows takes them as an argument. Labels: lanes ESTIMATED (OSM 2019), programs INVENTED.
"""
import collections
import csv
import gzip
import math
import pickle
from pathlib import Path

from lxml import etree

F_DIR = {'s': 1.0, 'r': 0.85, 'R': 0.85, 'l': 0.90, 'L': 0.90, 't': 0.7, 'T': 0.7}
GAPS = {'right': (5.9, 3.0), 'cross': (6.5, 3.4), 'major_left': (5.5, 2.6), 'rbl': (4.5, 2.5), 'stop': (6.5, 3.5), 'perm': (5.5, 2.8)}
MAIN = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link')
LOST_PER_STRETCH = 1.0  # G + 3 s yellow - 4 s lost, B 5.2
SPACING = 7.5
RAMPS = ('motorway_link', 'trunk_link', 'motorway', 'trunk')


def car_ok(allow, disallow):
    return bool({'passenger', 'all'} & set(allow.split())) if allow else 'passenger' not in disallow.split()


def class_mask(allow, disallow):
    """Bits: passenger, delivery, truck, trailer."""
    m = 0
    for i, c in enumerate(('passenger', 'delivery', 'truck', 'trailer')):
        if allow:
            if {c, 'all'} & set(allow.split()):
                m |= 1 << i
        elif c not in disallow.split():
            m |= 1 << i
    return m


def midblock(v):
    """Per lane, D's mid-block form, 2,400 ceiling."""
    return min(3600 / (1.2 + 7 / max(v, 1.0)), 2400.0)


def siegloch(qp, tg, tf):
    return 3600 / tf * math.exp(-(qp / 3600) * (tg - tf / 2))


def read(path, cache=True):
    path = Path(path)
    pk = path.with_suffix('.movetable2.pkl')
    if cache and pk.exists() and pk.stat().st_mtime > path.stat().st_mtime:
        return pickle.loads(pk.read_bytes())
    edges, conns, tl, junc = {}, [], {}, {}
    op = gzip.open(path, 'rb') if str(path).endswith('.gz') else open(path, 'rb')
    with op as f:
        for _, e in etree.iterparse(f, events=('end',), tag=('edge', 'connection', 'tlLogic', 'junction'), resolve_entities=False, no_network=True, huge_tree=True):
            t = e.tag
            if t == 'edge':
                if e.get('function') != 'internal':
                    lanes = []
                    for l in e.findall('lane'):
                        shape = l.get('shape').split()
                        a, b = shape[0].split(','), shape[-1].split(',')
                        lanes.append(dict(i=int(l.get('index')), v=float(l.get('speed')), L=float(l.get('length')), car=car_ok(l.get('allow', ''), l.get('disallow', '')), mask=class_mask(l.get('allow', ''), l.get('disallow', '')), xy=((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))))
                    edges[e.get('id')] = dict(frm=e.get('from'), to=e.get('to'), type=(e.get('type') or '').replace('highway.', ''), name=e.get('name', ''), lanes=lanes)
            elif t == 'connection':
                if not e.get('from', '').startswith(':'):
                    conns.append(dict(frm=e.get('from'), to=e.get('to'), fl=int(e.get('fromLane')), tl=int(e.get('toLane')), via=e.get('via', ''), ctrl=e.get('tl', ''), idx=int(e.get('linkIndex', -1)), dir=e.get('dir', ''), state=e.get('state', ''), mask=class_mask(e.get('allow', ''), e.get('disallow', ''))))
            elif t == 'tlLogic':
                tl[e.get('id')] = [(float(p.get('duration')), p.get('state')) for p in e.findall('phase')]
            elif t == 'junction':
                if e.get('type') != 'internal':
                    junc[e.get('id')] = dict(type=e.get('type'), x=float(e.get('x')), y=float(e.get('y')), intl=(e.get('intLanes') or '').split(), req={int(r.get('index')): r.get('response') for r in e.findall('request')})
            e.clear()
            while e.getprevious() is not None:
                del e.getparent()[0]
    out = build(edges, conns, tl, junc)
    if cache:
        pk.write_bytes(pickle.dumps(out, protocol=4))
    return out


def green(ph, idx):
    """Protected and permissive seconds of a link index, cycle, and how many separate green stretches."""
    cyc = sum(d for d, _ in ph)
    prot = sum(d for d, s in ph if idx < len(s) and s[idx] == 'G')
    perm = sum(d for d, s in ph if idx < len(s) and s[idx] == 'g')
    on = [idx < len(s) and s[idx] in 'Gg' for _, s in ph]
    stretch = sum(1 for a, b in zip(on, on[1:] + on[:1]) if not a and b)
    return prot, perm, cyc, stretch if any(on) else 0


def build(edges, conns, tl, junc):
    for k, e in edges.items():
        e['car'] = [l for l in e['lanes'] if l['car']]
        e['any'] = [l for l in e['lanes'] if l['mask']]
        l0 = (e['car'] or e['any'] or e['lanes'])[0]
        e['L'], e['v'] = l0['L'], l0['v']
        e['xy'] = ((l0['xy'][0][0] + l0['xy'][1][0]) / 2, (l0['xy'][0][1] + l0['xy'][1][1]) / 2)
    by_via = {}
    cs = []
    for c in conns:
        if c['frm'] not in edges or c['to'] not in edges:
            continue
        a, b = edges[c['frm']], edges[c['to']]
        la = next((l for l in a['lanes'] if l['i'] == c['fl']), None)
        lb = next((l for l in b['lanes'] if l['i'] == c['tl']), None)
        if la is None or lb is None:
            continue
        c['mask'] = c['mask'] & la['mask'] & lb['mask']
        if not c['mask']:
            continue
        c['j'] = a['to']
        cs.append(c)
        if c['via']:
            by_via[c['via']] = c
    moves = collections.defaultdict(list)
    for c in cs:
        moves[(c['frm'], c['to'])].append(c)
    index = {m: i for i, m in enumerate(moves)}
    for c in cs:
        c['m'] = index[(c['frm'], c['to'])]
        j = junc.get(c['j'])
        c['foes'] = []
        c['rank3'] = False
        if j and c['via'] in j['intl']:
            i = j['intl'].index(c['via'])
            r = j['req'].get(i)
            if r:
                n = len(r)
                seen = set()
                for bit in range(n):
                    if r[n - 1 - bit] == '1' and bit < len(j['intl']):
                        o = by_via.get(j['intl'][bit])
                        if o is not None and (o['frm'], o['to']) not in seen:
                            seen.add((o['frm'], o['to']))
                            c['foes'].append(o)
        if c['ctrl'] and c['ctrl'] not in tl:
            c['ctrl'] = ''
        if c['ctrl']:
            c['gp'], c['gq'], c['C'], c['nst'] = green(tl[c['ctrl']], c['idx'])
    for c in cs:
        c['foe_m'] = sorted({index[(o['frm'], o['to'])] for o in c['foes']})
        c['foe_yield'] = sorted({index[(o['frm'], o['to'])] for o in c['foes'] if not o['ctrl'] and o['state'] not in ('M', 'O', 'o')})
        c['merge'] = c['dir'] == 's' and bool(c['foes']) and all(o['to'] == c['to'] for o in c['foes'])
        c.pop('foes')
    mlist = [None] * len(moves)
    for m, l in moves.items():
        i = index[m]
        a = edges[m[0]]
        kinds = {kind(c) for c in l}
        mlist[i] = dict(id=i, frm=m[0], to=m[1], lanes=sorted({c['fl'] for c in l}), dir=l[0]['dir'], kinds=sorted(kinds), conns=l, mask=_or(c['mask'] for c in l), L=a['L'], v=a['v'], j=a['to'])
    return dict(edges=edges, conns=cs, moves=mlist, index=index, tl=tl, junc=junc)


def repair(T, base, reopen=(), log=None, none_lanes=None):
    """Table fixes on the lane-marked map, one named cause each.
    stranded: an open car lane with no connection left that had one before marking gets it back, as a copy of the movement's connection on a neighbouring lane
    (a lane tagged none has no arrow, and a target the tag names may not be on the map; neither closes the lane).
    reopen: (edge, lane, reason) a bus closure that real counts contradict."""
    edges = T['edges']
    index = T['index']
    by_move = collections.defaultdict(list)
    for c in T['conns']:
        by_move[(c['frm'], c['to'])].append(c)
    for e, lane, why in reopen:
        for l in edges[e]['lanes']:
            if l['i'] == lane:
                l['car'], l['mask'] = True, 15
        edges[e]['car'] = [l for l in edges[e]['lanes'] if l['car']]
        if log is not None:
            log.append(dict(edge=e, lane=lane, fix='reopen', why=why))
    have = collections.defaultdict(set)
    for c in T['conns']:
        have[c['frm']].add(c['fl'])
    # a lane the tag leaves as none has no arrow: it also serves the way straight on
    if none_lanes:
        through = {}
        for m in T['moves']:
            if m['dir'] == 's':
                through.setdefault(m['frm'], m)
        for e, lane in none_lanes:
            m = through.get(e)
            if m is None or lane in m['lanes'] or e not in edges or lane not in {l['i'] for l in edges[e]['car']}:
                continue
            c = dict(m['conns'][0])
            c['fl'] = lane
            T['conns'].append(c)
            m['conns'].append(c)
            m['lanes'] = sorted({x['fl'] for x in m['conns']})
            have[e].add(lane)
            if log is not None:
                log.append(dict(edge=e, lane=lane, fix='none_lane_through', why=''))
    bb = collections.defaultdict(list)
    for c in base['conns']:
        bb[(c['frm'], c['fl'])].append(c)
    added = 0
    for e, ed in edges.items():
        for l in ed['car']:
            if l['i'] in have[e]:
                continue
            for b in bb.get((e, l['i']), []):
                sib = by_move.get((b['frm'], b['to']))
                if not sib:
                    continue
                c = dict(sib[0])
                c['fl'] = l['i']
                T['conns'].append(c)
                T['moves'][c['m']]['conns'].append(c)
                T['moves'][c['m']]['lanes'] = sorted({x['fl'] for x in T['moves'][c['m']]['conns']})
                added += 1
                if log is not None:
                    log.append(dict(edge=e, lane=l['i'], fix='stranded', why=f"to {b['to']}"))
    return added


def read_none_lanes(path):
    """Lanes a turn:lanes tag marks none or empty, from step2_lanes.py's log."""
    out = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r['kind'] == 'turn' and r['applied'] == 'yes':
                parts = r['tag'].split('|')
                for i, p in enumerate(parts):
                    if p.strip() in ('none', ''):
                        out.append((r['edge'], len(parts) - 1 - i))
    return out


def _or(it):
    m = 0
    for x in it:
        m |= x
    return m


def kind(c):
    if c['ctrl']:
        return 'signal_perm' if c['gq'] > 0 and c['gp'] == 0 else 'signal'
    st = c['state']
    if st in ('M', 'O', 'o'):
        return 'major'
    if st == '=':
        return 'rbl'
    if st in ('s', 'w'):
        return 'stop'
    return 'minor'


def gap_key(c, ftype):
    st = c['state']
    if st == '=':
        return 'rbl'
    if st in ('s', 'w'):
        return 'stop'
    if c['dir'] in ('r', 'R'):
        return 'right'
    if c['dir'] in ('l', 'L', 't', 'T') and ftype in MAIN:
        return 'major_left'
    return 'cross'


def conn_capacity(c, edge, s, Q=None, green_s=None, qfloor=0.0, gw=1.0):
    """veh/h of this connection's lane if the lane served only this movement. Q: flow per movement id, None means no foe flow (the charitable bound).
    green_s: optional (gp, gq, C) overriding the program. gw scales give-way, for parity with an engine."""
    f = F_DIR.get(c['dir'], 1.0)
    vcap = midblock(edge['v'])
    qp = 0.0
    if Q is not None:
        qp = sum(Q.get(m, 0.0) for m in c['foe_m'])
    if c['ctrl']:
        gp, gq, C, nst = green_s if green_s else (c['gp'], c['gq'], c['C'], c['nst'])
        if C <= 0 or gp + gq <= 0:
            return 0.0
        S = min(s * f, vcap)
        eff = max(gp + gq - LOST_PER_STRETCH * max(nst, 1), 0.0) / (gp + gq)
        cap = S * gp / C
        if gq > 0:
            qg = qp * C / max(gp + gq, 1.0)
            tg, tf = GAPS['perm']
            cap += gq / C * min(S, siegloch(qg, tg, tf))
        return cap * eff
    st = c['state']
    if st in ('M', 'O', 'o') or not c['foe_m']:
        return vcap * f
    if (edge['type'] in RAMPS and edge['v'] >= 11) or c.get('merge'):
        # a ramp or a carriageway joining straight on zips in; Daganzo's merge: what the road below leaves, with a floor share, not a gap search (B 5.3)
        return max(vcap * f - qp / 2, 0.4 * vcap)
    tg, tf = GAPS[gap_key(c, edge['type'])]
    cap = siegloch(max(qp, qfloor), tg, tf)
    return min(vcap * f, gw * cap)


def lane_capacity_charitable(T, edge_id, lane, s):
    """The most a lane can pass whatever the turn split and with nothing to yield to."""
    e = T['edges'][edge_id]
    best = 0.0
    for c in T['by_lane'].get((edge_id, lane), []):
        best = max(best, conn_capacity(c, e, s))
    return best


def index_lanes(T):
    by = collections.defaultdict(list)
    for c in T['conns']:
        by[(c['frm'], c['fl'])].append(c)
    T['by_lane'] = by
    out = collections.defaultdict(list)
    inc = collections.defaultdict(list)
    for m in T['moves']:
        out[m['frm']].append(m)
        inc[m['to']].append(m)
    T['out'] = out
    T['inc'] = inc
    return T


def lane_groups(T):
    """Per edge, connected components of movements that share a lane."""
    groups = []
    gof = {}
    for e, ms in T['out'].items():
        parent = {m['id']: m['id'] for m in ms}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        lane_m = {}
        for m in ms:
            for l in m['lanes']:
                if l in lane_m:
                    parent[find(m['id'])] = find(lane_m[l])
                lane_m[l] = m['id']
        comp = collections.defaultdict(list)
        for m in ms:
            comp[find(m['id'])].append(m)
        for g in comp.values():
            gid = len(groups)
            ls = sorted({l for m in g for l in m['lanes']})
            groups.append(dict(id=gid, edge=e, moves=[m['id'] for m in g], lanes=ls, storage=T['edges'][e]['L'] * len(ls) / SPACING))
            for m in g:
                gof[m['id']] = gid
    T['groups'] = groups
    T['gof'] = gof
    return T


def group_load(T, g, Q, s, green_of=None, gw=1.0):
    """Min-max lane use over the split of movements across a group's lanes (the screen's method). Returns utilisation and per-movement capacity share."""
    e = T['edges'][g['edge']]
    dem = {m: Q.get(m, 0.0) for m in g['moves'] if Q.get(m, 0.0) > 0}
    if not dem:
        return 0.0
    cap = collections.defaultdict(dict)
    for m in g['moves']:
        for c in T['moves'][m]['conns']:
            gs = green_of(c) if green_of else None
            cap[c['fl']][m] = max(conn_capacity(c, e, s, Q, gs, gw=gw), 1.0)
    x = {m: {l: dem[m] / sum(1 for f in cap if m in cap[f]) for l in cap if m in cap[l]} for m in dem}
    u = {l: sum(x[m].get(l, 0.0) / cap[l][m] for m in cap[l] if m in x) for l in cap}
    for _ in range(40):
        moved = False
        for m in x:
            if len(x[m]) < 2:
                continue
            hi = max(x[m], key=lambda l: u[l])
            lo = min(x[m], key=lambda l: u[l])
            if u[hi] - u[lo] > 1e-3 and x[m][hi] > 0:
                d = min(x[m][hi], (u[hi] - u[lo]) / (1 / cap[hi][m] + 1 / cap[lo][m]) / 2)
                x[m][hi] -= d
                x[m][lo] += d
                u[hi] -= d / cap[hi][m]
                u[lo] += d / cap[lo][m]
                moved = True
        if not moved:
            break
    return max(u.values())
