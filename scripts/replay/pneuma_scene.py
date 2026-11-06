"""A pNEUMA drone area as a T3 replay scene: recorded entries and exits, read signals, buses and motorcycles replayed.

Net: the OSM net (pneuma.py osmnet) cut to the drone's view, with the lanes of every edge that has enough traffic
replaced by the lanes found from car density (pneuma.py lanes): their number, and their lateral place along the OSM
edge's rightmost lane. Junctions keep their internal lanes.
Signals: every signalised approach read from crossings in this file (pneuma.py signals: fixed-time fit, onset bias
D_START, end bias D_END_ARC), one long program per junction from the union of its approaches' change points.
Links of approaches that could not be read stay green; they are counted in scene.json.
Tracks: every sample matched to the nearest lane (internal lanes too) whose direction agrees within 45 degrees, front
projected onto it, lateral offset kept; a stopped vehicle keeps its lane. A track is cut where it leaves the net or
where its edge sequence is not a path of the net. Pieces are trips.

'all': every piece replayed (F100). 'mix': cars, taxis, medium and heavy vehicles simulated from their first piece's
entry to its exit; buses, motorcycles and unknown classes replayed (PLAN, T3).

    python3 -I scripts/replay/pneuma_scene.py build [DRONE DAY HHMM]
    python3 -I scripts/replay/pneuma_scene.py f100 [DRONE DAY HHMM] [--gpu]
"""
import os, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import write_rpl, lane_shapes, fmt_shape, Polyline, run_cars, INF
import pneuma as PN
import numpy as np, pandas as pd

DRONE, DAY, HH = 8, '20181029', '0900'
SIM_TYPES = {0, 1, 3, 4}          # Car, Taxi, Medium Vehicle, Heavy Vehicle
KEY_DT = PN.DT
WIDTH = {k: v[1] for k, v in PN.DIMS.items()}
MOTO = 5
CAR_HALF = 0.9                    # half the width of a car centred on its lane: the lane's car path
MIN_RUN = 5                       # on/off-path runs shorter than this many samples (1 s) join their neighbours
STITCH_MAX_ERR = 15.0             # m: a later piece joins when distance along the net and the speeds agree this well


def outdir(dr, day, hh):
    return os.path.join(PN.OUTD, f'scene-d{dr}-{day}-{hh}')


def offset_line(P, d):
    """Polyline P moved sideways by d (left positive), vertex normals averaged."""
    t = np.diff(P, axis=0); t = t / np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)[:, None]
    nrm = np.c_[-t[:, 1], t[:, 0]]
    nv = np.vstack([nrm[:1], 0.5 * (nrm[1:] + nrm[:-1]), nrm[-1:]])
    nv = nv / np.maximum(np.hypot(nv[:, 0], nv[:, 1]), 1e-9)[:, None]
    return P + d * nv


def build_net(D, dr):
    box = PN.area_box(dr, pad=5.0)
    subprocess.run(['netconvert', '-s', PN.OSM_NET, '--keep-edges.in-boundary', ','.join(f'{v:.1f}' for v in box), '-o', f'{D}/osm_area.net.xml',
                    '--offset.disable-normalization', '--no-warnings'], check=True, stdout=subprocess.DEVNULL)
    L = json.load(open(os.path.join(PN.OUTD, 'lanes', f'd{dr}.json')))['edges']
    E = PN.net_lanes(f'{D}/osm_area.net.xml')
    patched = 0
    with open(f'{D}/lanes.edg.xml', 'w') as f:
        f.write('<edges>\n')
        for eid, r in L.items():
            if eid not in E or r['density_lanes'] < 1:
                continue
            P = E[eid]['lanes'][0]['shape']
            lat = r['density_lane_lat']; w = r['spacing'] or 3.0
            f.write(f'  <edge id="{eid}" numLanes="{len(lat)}" spreadType="center">\n')
            for i, l in enumerate(lat):
                f.write(f'    <lane index="{i}" width="{max(min(w, 3.8), 2.4):.2f}" shape="{fmt_shape(offset_line(P, l))}"/>\n')
            f.write('  </edge>\n')
            patched += 1
        f.write('</edges>\n')
    subprocess.run(['netconvert', '-s', f'{D}/osm_area.net.xml', '-e', f'{D}/lanes.edg.xml', '-o', f'{D}/net.xml', '--offset.disable-normalization',
                    '--no-warnings', '--no-turnarounds'], check=True, stdout=subprocess.DEVNULL)
    if os.path.exists(f'{D}/observed.con.xml'):
        # lane-to-lane movements the recorded cars make that netconvert did not guess (observed_connections)
        subprocess.run(['netconvert', '-s', f'{D}/net.xml', '-x', f'{D}/observed.con.xml', '-o', f'{D}/net2.xml', '--offset.disable-normalization',
                        '--no-warnings', '--no-turnarounds'], check=True, stdout=subprocess.DEVNULL)
        os.replace(f'{D}/net2.xml', f'{D}/net.xml')
    return patched, box


def observed_connections(D, df, lanes, conn_lanes, min_cars=3):
    """Lane-to-lane movements of recorded cars (not two-wheelers) with no connection in the net: from the last lane
    on the edge before a junction to the first lane on the edge after it, kept where at least `min_cars` make it and
    both lanes are open to cars. Returns (movements checked, without a connection, the connections to add)."""
    ne = df[(~df.internal) & (df.type != MOTO)].sort_values(['vid', 'ti'])
    e, v, l = ne.edge.values, ne.vid.values, ne.lane.values
    k = np.flatnonzero((e[1:] != e[:-1]) & (v[1:] == v[:-1]))
    mv = pd.DataFrame(dict(frm=e[k], to=e[k + 1], fl=l[k], tl=l[k + 1]))
    mv = mv[[(a, b) in conn_lanes for a, b in zip(mv.frm, mv.to)]]
    bad = mv[[int(x.rsplit('_', 1)[1]) not in conn_lanes[(a, b)] for a, b, x in zip(mv.frm, mv.to, mv.fl)]]
    add = []
    for (a, b, fl), g in bad.groupby(['frm', 'to', 'fl']):
        tl = g.tl.mode().iloc[0]
        if len(g) >= min_cars and lanes[fl]['car'] and lanes[tl]['car']:
            add.append((a, b, int(fl.rsplit('_', 1)[1]), int(tl.rsplit('_', 1)[1]), len(g)))
    return len(mv), len(bad), add


def net_info(path):
    import xml.etree.ElementTree as ET
    r = ET.parse(path).getroot()
    lanes = {}
    for e in r.iter('edge'):
        internal = e.get('function') == 'internal'
        for ln in e.iter('lane'):
            pts = np.array([[float(a) for a in p.split(',')[:2]] for p in ln.get('shape').split()])
            if len(pts) < 2 or float(ln.get('length')) < 0.1 or np.hypot(*np.diff(pts, axis=0).T).sum() < 0.1:
                continue
            allow, dis = ln.get('allow') or '', ln.get('disallow') or ''
            car = ('passenger' in allow.split()) if allow else ('passenger' not in dis.split())
            lanes[ln.get('id')] = dict(edge=e.get('id'), internal=internal, shape=pts, length=float(ln.get('length')), car=car)
    conn, links = set(), {}
    via_to = {}
    net_info.conn_lanes = {}
    for c in r.iter('connection'):
        if c.get('from', '').startswith(':'):
            continue
        conn.add((c.get('from'), c.get('to')))
        net_info.conn_lanes.setdefault((c.get('from'), c.get('to')), set()).add(int(c.get('fromLane')))
        if c.get('via'):
            via_to[c.get('via')] = (c.get('from'), c.get('to'))
        if c.get('tl'):
            links.setdefault(c.get('tl'), {})[int(c.get('linkIndex'))] = c.get('from')
    # an internal lane split into pieces keeps the connection of its first part
    for l in list(lanes):
        if lanes[l]['internal'] and l not in via_to:
            base = l.rsplit('_', 1)[0]
            for v, ft in via_to.items():
                if v.rsplit('_', 1)[0] == base:
                    via_to[l] = ft; break
    net_info.via_to = via_to
    return lanes, conn, links



def extend_back(E, conn, eid, want=60.0):
    """The edge's lane-0 shape with its straight-on predecessors' put in front, until it is `want` m long."""
    P = E[eid]['lanes'][0]['shape']
    seen = {eid}
    cur = eid
    while np.hypot(*np.diff(P, axis=0).T).sum() < want:
        preds = [a for a, b in conn if b == cur and a in E and a not in seen]
        if not preds:
            break
        u0 = P[1] - P[0]
        def turn(a):
            Q = E[a]['lanes'][0]['shape']; u = Q[-1] - Q[-2]
            return -np.dot(u, u0) / max(np.hypot(*u) * np.hypot(*u0), 1e-9)
        a = min(preds, key=turn)
        if turn(a) > -0.7:          # more than 45 degrees off straight on: not the same approach
            break
        P = np.vstack([E[a]['lanes'][0]['shape'], P])
        seen.add(a); cur = a
    return P


def scene_signals(D, dr, day, hh, conn, links):
    """Read every incoming edge of a signalised junction of the scene net (SIGNALS.md's reader, unchanged), edges
    under 60 m with their straight-on predecessors in front. -> signals_scene.csv"""
    E = PN.net_lanes(f'{D}/net.xml'); J = PN.net_junctions(f'{D}/net.xml')
    apps = sorted({frm for lk in links.values() for frm in lk.values() if frm in E})
    E2 = {}
    for eid in apps:
        e = dict(E[eid]); ln = [dict(l) for l in e['lanes']]
        ln[0]['shape'] = extend_back(E, conn, eid)
        e['lanes'] = ln; E2[eid] = e
    rows, cyc = PN.signals_file(day, dr, hh, E2, J, apps)
    A = pd.DataFrame(rows)
    # A pre-timed controller has one cycle: a read off its controller's cycle by more than 1 s (a 45 s read of two
    # greens in 90 s) is fitted again within 0.5 s of it; if that is not periodic it stays unread.
    tl_of = {frm: tl for tl, lk in links.items() for frm in lk.values()}
    A['tl'] = A.edge.map(tl_of)
    good = A[(A.R >= 0.8) & (A.green > 5) & (A.green < A.cycle - 5)]
    major = good.groupby('tl').cycle.max()           # a shorter read is a harmonic (two greens a cycle)
    off = good[(good.cycle - good.tl.map(major)).abs() > 1.0]
    A['refit'] = False
    if len(off):
        win = {r.edge: (major[r.tl] - 0.5, major[r.tl] + 0.5) for r in off.itertuples()}
        rows2, cyc2 = PN.signals_file(day, dr, hh, E2, J, list(win), win)
        A = A[~A.edge.isin(win)]
        B = pd.DataFrame(rows2); B['tl'] = B.edge.map(tl_of); B['refit'] = True
        A = pd.concat([A, B], ignore_index=True)
        cyc = [c for c in cyc if c['edge'] not in win] + cyc2
        print('refit at the controller cycle:', B[['edge', 'cycle', 'R', 'green']].to_dict('records'), flush=True)
    A.to_csv(f'{D}/signals_scene.csv', index=False)
    pd.DataFrame(cyc).to_csv(f'{D}/signals_scene_cycles.csv', index=False)
    return A



def link_census(D, df, read_edges):
    """Every signal link of the scene: recorded vehicles using it, cars standing within 30 m of its line, vehicles on
    the movements that conflict with it, and why it is or is not read. -> links.csv"""
    import xml.etree.ElementTree as ET
    r = ET.parse(f'{D}/net.xml').getroot()
    elen = {e.get('id'): float(next(e.iter('lane')).get('length')) for e in r.iter('edge') if e.get('function') != 'internal'}
    foes = {(j.get('id'), int(q.get('index'))): q.get('foes')[::-1] for j in r.iter('junction') for q in j.iter('request')}
    L = []
    for c in r.iter('connection'):
        if c.get('tl') and not c.get('from').startswith(':') and c.get('via'):
            jid, k = c.get('via')[1:].rsplit('_', 2)[:2]
            L.append(dict(tl=c.get('tl'), li=int(c.get('linkIndex')), frm=c.get('from'), to=c.get('to'), j=jid, k=int(k)))
    L = pd.DataFrame(L).drop_duplicates(['tl', 'li'])
    ne = df[~df.internal].sort_values(['vid', 'ti'])
    chg = (ne.edge.values[1:] != ne.edge.values[:-1]) & (ne.vid.values[1:] == ne.vid.values[:-1])
    mv = pd.DataFrame(dict(frm=ne.edge.values[:-1][chg], to=ne.edge.values[1:][chg], vid=ne.vid.values[1:][chg]))
    cnt = mv.groupby(['frm', 'to']).vid.nunique()
    st = ne[(ne.v < 0.5) & (ne.type != MOTO)]
    st = st[st.s > st.edge.map(elen) - 30]
    stand = st.groupby('edge').vid.nunique()
    L['veh'] = [int(cnt.get((a, b), 0)) for a, b in zip(L.frm, L.to)]
    L['standing_at_line'] = L.frm.map(stand).fillna(0).astype(int)
    use = {(x.j, x.k): x.veh for x in L.itertuples()}
    L['foe_veh'] = [sum(use.get((x.j, i), 0) for i, ch in enumerate(foes.get((x.j, x.k), '')) if ch == '1') for x in L.itertuples()]
    def why(x):
        if x.frm in read_edges: return 'read'
        if x.veh < 5: return 'no traffic'
        if x.standing_at_line < 5: return 'no conflicting traffic, nobody stops' if x.foe_veh == 0 else 'never stopped'
        return 'unreadable'
    L['status'] = [why(x) for x in L.itertuples()]
    L.to_csv(f'{D}/links.csv', index=False)
    return {k: int(v) for k, v in L.status.value_counts().items()}, {k: int(v) for k, v in L.groupby('status').veh.sum().items()}


def programs(D, dr, day, hh, links, t0, t1, A=None):
    """One long program per signalised junction from the read approaches of this file."""
    if A is None:
        A = pd.read_csv(os.path.join(PN.OUTD, 'signals_approaches.csv'))
        A = A[(A.drone == dr) & (A.day.astype(str) == day) & (A.period.astype(str).str.zfill(4) == hh)]
    read = {r.edge: r for r in A.itertuples() if r.R >= 0.8 and 5 < r.green < r.cycle - 5}
    stats = dict(tl=len(links), links=sum(len(v) for v in links.values()), links_read=0)
    with open(f'{D}/tls.add.xml', 'w') as f:
        f.write('<additional>\n')
        for tl, lk in links.items():
            n = max(lk) + 1
            ivals = {}
            for i, frm in lk.items():
                if frm in read:
                    r = read[frm]; k0 = int(np.floor((t0 - r.offset) / r.cycle)) - 1; k1 = int(np.ceil((t1 - r.offset) / r.cycle)) + 1
                    ivals[i] = [(r.offset + k * r.cycle, r.offset + k * r.cycle + r.green) for k in range(k0, k1)]
                    stats['links_read'] += 1
            ch = sorted({t0} | {round(x, 1) for v in ivals.values() for a, b in v for x in (a, b, b + PN.YELLOW) if t0 < x < t1})
            def state(t):
                s = []
                for i in range(n):
                    if i not in ivals:
                        s.append('G'); continue
                    c = 'r'
                    for a, b in ivals[i]:
                        if a <= t < b:
                            c = 'G'
                        elif b <= t < b + PN.YELLOW:
                            c = 'y'
                    s.append(c)
                return ''.join(s)
            f.write(f'  <tlLogic id="{tl}" type="static" programID="read" offset="{t0}">\n')
            for a, b in zip(ch, ch[1:] + [t1 + 600]):
                if b - a > 0.05:
                    f.write(f'    <phase duration="{b - a:.1f}" state="{state(a + 1e-3)}"/>\n')
            f.write('  </tlLogic>\n')
        f.write('</additional>\n')
    return stats


def match(A, lanes):
    from scipy.spatial import cKDTree
    P, H, Lid = [], [], []
    names = list(lanes)
    for k, l in enumerate(names):
        pl = Polyline(lanes[l]['shape'], lanes[l]['length'])
        s = np.arange(0, pl.cum[-1] + 0.01, 0.5)
        x, y = pl.point(s * pl.scale)
        i = np.clip(np.searchsorted(pl.cum, s, side='right') - 1, 0, len(pl.seg) - 1)
        P.append(np.c_[x, y]); H.append(np.arctan2(pl.u[i, 1], pl.u[i, 0])); Lid.append(np.full(len(s), k))
    P = np.vstack(P); H = np.concatenate(H); Lid = np.concatenate(Lid)
    tree = cKDTree(P)
    # heading: from motion, carried over standstill
    hd = np.arctan2(A['hy'], A['hx']); moving = np.hypot(A['hx'], A['hy']) > 0.02
    hd = pd.Series(np.where(moving, hd, np.nan)).groupby(A['veh']).ffill().groupby(A['veh']).bfill().fillna(0).to_numpy()
    dist, ii = tree.query(np.c_[A['x'], A['y']], k=24)
    lane = np.full(len(hd), -1)
    # strict, then relaxed for what is left (wide turns, lane changes, the kerb)
    for dmax, amax in ((3.0, 45), (6.0, 70)):
        ok = (np.cos(H[ii] - hd[:, None]) > np.cos(np.deg2rad(amax))) & (dist < dmax)
        first = np.where(ok.any(1), ok.argmax(1), -1)
        lane = np.where((lane < 0) & (first >= 0), Lid[ii[np.arange(len(first)), np.maximum(first, 0)]], lane)
    return np.array(names + [''])[lane], hd



def route_of(g):
    """The piece's edges with bridged gaps, cut back or carried on where it ends in a junction; None if unusable."""
    while len(g) and g.internal.iloc[0]:
        g = g.iloc[1:]
    if len(g) < 3:
        return None
    route = []
    for e, v in zip(g.edge[~g.internal], g.via[~g.internal]):
        if v and route:
            route += v.split()
        if not route or route[-1] != e:
            route.append(e)
    if g.internal.iloc[-1]:
        # it ends inside a junction: its route goes on to that connection's exit
        ft = net_info.via_to.get(g.lane.iloc[-1])
        if ft and ft[0] == route[-1]:
            route.append(ft[1])
        else:
            g = g[np.cumsum((~g.internal.values)[::-1])[::-1] > 0]
            if len(g) < 3:
                return None
    if len(route) != len(set(route)):
        return None
    return g, route


def entry_kinds(A, cell=3.0, min_samples=5, reach=30.0):
    """Per vehicle: time of its first raw sample and how many points up to `reach` m behind it, along its heading,
    no vehicle in the file was ever seen on. Any such point means the view ends behind it: a boundary entry."""
    x, y, veh = A['x'], A['y'], A['veh']
    x0, y0 = x.min() - 50, y.min() - 50
    nx, ny = int((x.max() - x0) / cell) + 60, int((y.max() - y0) / cell) + 60
    cnt = np.zeros((nx, ny), np.int32)
    np.add.at(cnt, (((x - x0) / cell).astype(int), ((y - y0) / cell).astype(int)), 1)
    seen = cnt >= min_samples
    fi = np.flatnonzero(np.r_[True, veh[1:] != veh[:-1]])
    nxt = np.minimum(fi + 10, np.r_[fi[1:] - 1, len(x) - 1])
    h = np.arctan2(y[nxt] - y[fi], x[nxt] - x[fi])
    unseen = np.zeros(len(fi), int)
    for d in np.arange(6.0, reach + 1, 3.0):
        a = np.clip(((x[fi] - d * np.cos(h) - x0) / cell).astype(int), 0, nx - 1)
        b = np.clip(((y[fi] - d * np.sin(h) - y0) / cell).astype(int), 0, ny - 1)
        unseen += ~seen[a, b]
    return {int(v): (float(t), int(u)) for v, t, u in zip(A['vid'][fi], A['t'][fi], unseen)}


def entry_of(pc, first_seen, t_begin):
    """Where and when a simulated vehicle enters (research/truth/replay/RESULTS.md, third round).
    snapshot: in view at the start, forced at its recorded state. boundary: at the start of its first edge (front at
    min(length + 0.1, first seen)), time carried back at its first-seen speed. boundary_queued: first seen under 1 m/s,
    so a recorded queue reaches the view's edge and nothing says when it came; it enters at the edge start when first
    seen. interior / off_net: first seen inside the view, or seen off the net before; it enters where and when first seen."""
    g = pc['g']
    t, s, v, L = float(g.ti.iloc[0] * KEY_DT), float(g.s.iloc[0]), float(g.v.iloc[0]), float(g.L.iloc[0])
    lane = int(g.lane.iloc[0].rsplit('_', 1)[1])
    out = dict(lane=lane, v=v, t_seen=t, s_seen=s)
    if t <= t_begin + 2.0:
        return dict(out, kind='snapshot', t=t, pos=s)
    t_raw, unseen = first_seen.get(pc['vid'], (t, 1))
    if t - t_raw > 1.0:
        return dict(out, kind='off_net', t=t, pos=s)
    if unseen == 0:
        return dict(out, kind='interior', t=t, pos=s)
    pos = min(L + 0.1, s)
    if v < 1.0:
        return dict(out, kind='boundary_queued', t=t, pos=pos)
    return dict(out, kind='boundary', t=max(t - (s - pos) / v, t_begin), pos=pos)


def runs(mask):
    """(start, end, value) of the runs of a boolean array."""
    if not len(mask):
        return []
    cut = np.flatnonzero(mask[1:] != mask[:-1]) + 1
    a = np.r_[0, cut]; b = np.r_[cut, len(mask)]
    return list(zip(a, b, mask[a]))


def on_path_pieces(pc):
    """A replayed vehicle takes a lane only while its body overlaps the path of a car centred on that lane
    (|offset| under CAR_HALF + half its width); the rest of the time it is not in the simulation: a two-wheeler
    filtering between lanes, a car parked at the kerb. Inside junctions it always counts."""
    g = pc['g']
    on = (g.internal.values | (np.abs(g.lat.values) < CAR_HALF + 0.5 * WIDTH[pc['type']])).copy()
    for _ in range(3):
        rr = runs(on)
        for k, (a, b, val) in enumerate(rr):
            if b - a < MIN_RUN and len(rr) > 1:
                on[a:b] = rr[k - 1][2] if k > 0 else rr[k + 1][2]
    out = []
    for k, (a, b, val) in enumerate(runs(on)):
        if not val:
            continue
        sub = g.iloc[a:b].copy()
        sub.iloc[0, sub.columns.get_loc('via')] = ''
        r = route_of(sub)
        if r is None:
            continue
        out.append(dict(pc, tid=f"{pc['tid']}m{k}", g=r[0], route=r[1]))
    return out


def trim_to(pc, sub):
    """A simulated vehicle's piece from its first on-path sample to its last: it joins the road where it pulls out."""
    g = pc['g']
    a, b = sub[0]['g'].ti.iloc[0], sub[-1]['g'].ti.iloc[-1]
    gg = g[(g.ti >= a) & (g.ti <= b)].copy()
    gg.iloc[0, gg.columns.get_loc('via')] = '' if gg.ti.iloc[0] != g.ti.iloc[0] else gg.via.iloc[0]
    r = route_of(gg)
    return None if r is None else dict(pc, g=r[0], route=r[1])


def stitch(first_piece, later, conn_next, lanes):
    """Join a simulated vehicle's later pieces to its route where the net has a path between them and the distance
    along it agrees with the time and speeds: |distance - mean speed x gap time| under STITCH_MAX_ERR."""
    elen = {}
    for l, d in lanes.items():
        if not d['internal']:
            elen.setdefault(d['edge'], d['length'])
    out = {}
    for vid, fp in first_piece.items():
        route = list(fp['route']); g_end = fp['g']; joined = 0; info = []; ids = [fp['tid'].rsplit('_', 1)[1]]
        for pc in sorted(later.get(vid, []), key=lambda q: q['g'].ti.iloc[0]):
            a, b = route[-1], pc['route'][0]
            gap_t = (pc['g'].ti.iloc[0] - g_end.ti.iloc[-1]) * KEY_DT
            via = [] if a == b else path(conn_next, a, b, hops=4)
            if via is None:
                info.append(dict(result='no_path', gap_t=gap_t)); break
            s_end = g_end.s.iloc[-1] if not g_end.internal.iloc[-1] else 0.0
            if a == b:
                dist = pc['g'].s.iloc[0] - s_end
            else:
                dist = elen.get(a, 0) - s_end + sum(elen.get(e, 0) for e in via) + pc['g'].s.iloc[0]
            vbar = 0.5 * (g_end.v.iloc[-1] + pc['g'].v.iloc[0])
            err = dist - vbar * gap_t
            rest = [e for e in pc['route'] if e != b] if a == b else pc['route']
            new = route + via + ([] if a == b else [b]) + [e for e in pc['route'][1:]]
            if abs(err) > STITCH_MAX_ERR or gap_t <= 0 or len(new) != len(set(new)):
                info.append(dict(result='disagree' if abs(err) > STITCH_MAX_ERR else 'loop', gap_t=gap_t, dist=dist, err=err)); break
            info.append(dict(result='joined', gap_t=gap_t, dist=dist, err=err, a=a, b=b, t=float(g_end.ti.iloc[-1] * KEY_DT)))
            route = new; g_end = pc['g']; joined += 1; ids.append(pc['tid'].rsplit('_', 1)[1])
        ex = g_end[~g_end.internal.values].iloc[-1]
        out[vid] = dict(route=route, joined=joined, later=len(later.get(vid, [])), info=json.dumps(info), pieces=' '.join(ids),
                        exit_edge=ex.edge, exit_s=float(ex.s), exit_t=float(ex.ti * KEY_DT))
    return out


def path(conn_next, a, b, hops=3):
    """Shortest edge path a -> ... -> b with at most `hops` steps, as the edges between them, or None."""
    frontier = [(a, [])]
    for _ in range(hops):
        nxt = []
        for e, via in frontier:
            for f in conn_next.get(e, ()):
                if f == b:
                    return via
                nxt.append((f, via + [f]))
        frontier = nxt
    return None


def build(dr=DRONE, day=DAY, hh=HH, again=False):
    D = outdir(dr, day, hh); os.makedirs(D, exist_ok=True)
    if not again and os.path.exists(f'{D}/observed.con.xml'):
        os.remove(f'{D}/observed.con.xml')
    patched, box = build_net(D, dr)
    lanes, conn, links = net_info(f'{D}/net.xml')
    A = PN.samples(day, dr, hh)
    t0, t1 = float(A['t'].min()), float(A['t'].max())
    if not os.path.exists(f'{D}/signals_scene.csv') or ('--signals' in sys.argv and not again):
        scene_signals(D, dr, day, hh, conn, links)
    SA = pd.read_csv(f'{D}/signals_scene.csv') if os.path.getsize(f'{D}/signals_scene.csv') > 5 else None
    tls = programs(D, dr, day, hh, links, t0, t1, SA)
    lane, hd = match(A, lanes)
    df = pd.DataFrame(dict(vid=A['vid'], veh=A['veh'], type=A['type'], t=A['t'], x=A['x'], y=A['y'], v=A['v'], h=hd, lane=lane))
    df['L'] = [PN.DIMS[int(k)][0] for k in df.type]
    df['ti'] = np.round(df.t / KEY_DT).astype(np.int64)
    on = df.lane != ''
    off_net = float(1 - on.mean())
    df = df[on].copy()
    df['edge'] = [lanes[l]['edge'] for l in df.lane]; df['internal'] = [lanes[l]['internal'] for l in df.lane]
    # front point, projected; lateral of the centre
    df['xf'] = df.x + 0.5 * df.L * np.cos(df.h); df['yf'] = df.y + 0.5 * df.L * np.sin(df.h)
    df['s'] = 0.0; df['lat'] = 0.0
    polys = {l: Polyline(lanes[l]['shape'], lanes[l]['length']) for l in df.lane.unique()}
    for l, g in df.groupby('lane'):
        sc, la = polys[l].project(g.x.values, g.y.values)
        sf, _ = polys[l].project(g.xf.values, g.yf.values)
        df.loc[g.index, 's'] = sf; df.loc[g.index, 'lat'] = la
    df = df.sort_values(['vid', 'ti']).reset_index(drop=True)
    # A front past the end of the centre's lane is on the next lane the track takes (internal or the next edge).
    ln_len = df.lane.map(lambda l: lanes[l]['length']).to_numpy()
    lane_a = df.lane.to_numpy().copy(); s_a = df.s.to_numpy().copy(); lat_a = df.lat.to_numpy().copy()
    vid_a = df.vid.to_numpy(); ti_a = df.ti.to_numpy()
    cont = np.r_[False, (vid_a[1:] == vid_a[:-1]) & (ti_a[1:] == ti_a[:-1] + 1)]
    seg_id = np.cumsum(~cont)
    chg = np.flatnonzero((lane_a[1:] != lane_a[:-1]) & (seg_id[1:] == seg_id[:-1])) + 1
    moved, leaving = 0, np.zeros(len(df), bool)
    for i in np.flatnonzero(s_a >= ln_len - 0.01):
        k = np.searchsorted(chg, i, side='right')
        if k < len(chg) and seg_id[chg[k]] == seg_id[i]:
            nl = lane_a[chg[k]]
            pl = polys.setdefault(nl, Polyline(lanes[nl]['shape'], lanes[nl]['length']))
            a_, b_ = pl.project([df.xf.iat[i]], [df.yf.iat[i]])
            lane_a[i] = nl; s_a[i] = float(a_[0]); lat_a[i] = float(b_[0]); moved += 1
        else:
            leaving[i] = True            # its front has left the last lane it is seen on: it is leaving the net
    df['lane'] = lane_a; df['s'] = np.minimum(s_a, df.lane.map(lambda l: lanes[l]['length']).to_numpy() - 0.05); df['lat'] = lat_a
    df['edge'] = [lanes[l]['edge'] for l in df.lane]; df['internal'] = [lanes[l]['internal'] for l in df.lane]
    df = df[~leaving].reset_index(drop=True)
    # pieces: contiguous in time and a path of the net
    vid = df.vid.to_numpy(); ti = df.ti.to_numpy(); ed = df.edge.to_numpy(); inn = df.internal.to_numpy()
    new = np.r_[True, (vid[1:] != vid[:-1]) | (ti[1:] != ti[:-1] + 1)]
    last_edge = pd.Series(np.where(inn, None, ed)).groupby(np.cumsum(new)).ffill().to_numpy()
    prev_real = np.r_[None, last_edge[:-1]]
    step = (~inn) & (prev_real != None) & (ed != prev_real) & ~new
    n_mv, n_bad, add = observed_connections(D, df, lanes, net_info.conn_lanes)
    if not again:
        with open(f'{D}/observed.con.xml', 'w') as f:
            f.write('<connections>\n')
            for a_, b_, fl, tl, n in add:
                f.write(f'  <connection from="{a_}" to="{b_}" fromLane="{fl}" toLane="{tl}"/>  <!-- {n} cars -->\n')
            f.write('</connections>\n')
        print(f'observed connections: {n_bad} of {n_mv} car movements from a lane with no connection; adding {len(add)}', flush=True)
        return build(dr, day, hh, again=True)
    conn_next = {}
    for a_, b_ in conn:
        conn_next.setdefault(a_, []).append(b_)
    bad = np.zeros(len(df), bool); bridge = {}
    for i in np.flatnonzero(step):
        if (prev_real[i], ed[i]) in conn:
            continue
        via = path(conn_next, prev_real[i], ed[i])
        if via is None:
            bad[i] = True
        else:
            bridge[i] = via
    df['piece'] = np.cumsum(new | bad)
    df['via'] = ''
    for i, v in bridge.items():
        df.iat[i, df.columns.get_loc('via')] = ' '.join(v)
    lane_list = sorted(lanes)
    lidx = {l: i for i, l in enumerate(lane_list)}
    first_seen = entry_kinds(A)
    pieces, skipped = [], 0
    for p, g in df.groupby('piece', sort=False):
        r = route_of(g)
        if r is None:
            skipped += 1
            continue
        g, route = r
        pieces.append(dict(tid=f'{int(g.vid.iloc[0])}_{p}', vid=int(g.vid.iloc[0]), type=int(g.type.iloc[0]), g=g, route=route))
    key = lambda pc, rel=INF: (pc['tid'], float(pc['g'].ti.iloc[0] * KEY_DT), KEY_DT, rel, [lidx[l] for l in pc['g'].lane], pc['g'].s.values, pc['g'].v.values, pc['g'].lat.values)
    def row(pc, kind):
        g = pc['g']
        return dict(t0=float(g.ti.iloc[0] * KEY_DT), tid=pc['tid'], lane=int(g.lane.iloc[0].rsplit('_', 1)[1]), pos=float(g.s.iloc[0]), v=float(g.v.iloc[0]),
                    route=' '.join(pc['route']), type=pc['type'], kind=kind)
    # Off the car path (parked at the kerb, filtering between lanes) a vehicle takes no lane: replayed ones are split
    # into their on-path runs, simulated ones start where they join a car path and end where they leave it.
    onpath = {pc['tid']: on_path_pieces(pc) for pc in pieces}
    first_piece, later = {}, {}
    for pc in pieces:
        if pc['type'] not in SIM_TYPES:
            continue
        sp = onpath[pc['tid']]
        if not sp:
            continue
        tr = trim_to(pc, sp)
        if tr is None:
            continue
        if pc['vid'] in first_piece:
            later.setdefault(pc['vid'], []).append(tr)
        else:
            first_piece[pc['vid']] = tr
    stitched = stitch(first_piece, later, conn_next, lanes)
    entries = {vid: entry_of(pc, first_seen, t0) for vid, pc in first_piece.items()}
    for vid, en in entries.items():
        # recorded on a lane cars may not use (a bus lane): the nearest one they may
        e0 = first_piece[vid]['route'][0]
        ok = [int(l.rsplit('_', 1)[1]) for l, d in lanes.items() if d['edge'] == e0 and d['car']]
        if ok and en['lane'] not in ok:
            en['lane'] = min(ok, key=lambda i: abs(i - en['lane']))
    variants = {}
    # all: every piece replayed and forced (F100). entry: cars enter through the checked entry, then are replayed (F520).
    # mix: cars enter checked and are simulated. mix_keep2w: as mix, but two-wheelers keep their nearest lane throughout.
    for name in ('all', 'entry', 'mix', 'mix_keep2w'):
        tracks, trips, flags = [], [], {}
        for pc in pieces:
            fp = first_piece.get(pc['vid'])
            is_first = fp is not None and fp['tid'] == pc['tid']
            if name == 'all':
                tracks.append(key(pc)); trips.append(row(pc, 'rep')); continue
            sim = pc['type'] in SIM_TYPES and name in ('mix', 'mix_keep2w')
            if sim and not is_first:
                continue
            if not is_first:
                for sp in ([pc] if name == 'mix_keep2w' and pc['type'] == MOTO else onpath[pc['tid']]):
                    tracks.append(key(sp)); trips.append(row(sp, 'rep'))
                continue
            en = entries[pc['vid']]
            r = row(fp, 'drv' if sim else 'rep')
            if sim:
                r['route'] = ' '.join(stitched[pc['vid']]['route'])
            if en['kind'] == 'snapshot':
                # In view at the start: forced in at its recorded state (a recorded gap is never refused); a car
                # recorded on a lane cars may not use is put on the nearest one they may.
                k = key(fp, r['t0'] + 0.5 * KEY_DT) if sim else key(fp)
                if sim:
                    k = k[:4] + tuple(x[:2] for x in k[4:])
                    lane0 = f"{fp['route'][0]}_{en['lane']}"
                    if r['lane'] != en['lane']:
                        k = k[:4] + ([lidx[lane0]] * 2,) + k[5:]
                        r['lane'] = en['lane']
                tracks.append(k)
            else:
                r.update(t0=en['t'], pos=en['pos'], lane=en['lane'], v=en['v'])
                flags[fp['tid']] = 1
                tracks.append(key(fp) if not sim else (fp['tid'], en['t'], KEY_DT, en['t'], [], [], [], []))
            trips.append(r)
            if not sim:
                # the rest of the piece after it leaves the car path, if it comes back
                for sp in onpath[pc['tid']]:
                    if sp['g'].ti.iloc[0] > fp['g'].ti.iloc[-1]:
                        tracks.append(key(sp)); trips.append(row(sp, 'rep'))
        variants[name] = (tracks, trips, flags)
    df[['vid', 'piece', 'ti', 'type', 'lane', 'internal', 's', 'lat', 'x', 'y', 'xf', 'yf', 'v', 'L']].to_csv(f'{D}/matched.csv.gz', index=False)
    for name, (tracks, trips, flags) in variants.items():
        write_rpl(f'{D}/{name}.rpl', lane_list, tracks, flags if name != 'all' else None)
        with open(f'{D}/routes_{name}.xml', 'w') as f:
            f.write('<routes>\n  <vType id="drv" carFollowModel="Krauss"/>\n')
            for k, (L, W) in PN.DIMS.items():
                f.write(f'  <vType id="rep{k}" length="{L}" width="{W}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
            for r in sorted(trips, key=lambda r: (r['t0'], r['tid'])):
                vt = 'drv' if r['kind'] == 'drv' else f'rep{r["type"]}'
                f.write(f'  <vehicle id="{r["tid"]}" type="{vt}" depart="{r["t0"]:.2f}" departLane="{r["lane"]}" departPos="{max(r["pos"], 0):.3f}" '
                        f'departSpeed="{max(r["v"], 0):.3f}"><route edges="{r["route"]}"/></vehicle>\n')
            f.write('</routes>\n')
    E = pd.DataFrame([dict(vid=v, tid=first_piece[v]['tid'], edge=first_piece[v]['route'][0], **{k: x for k, x in e.items()}) for v, e in entries.items()])
    E.to_csv(f'{D}/entries.csv', index=False)
    pd.DataFrame([dict(vid=v, **{k: x for k, x in s_.items() if k != 'route'}, route=' '.join(s_['route'])) for v, s_ in stitched.items()]).to_csv(f'{D}/stitched.csv', index=False)
    nveh = df.vid.nunique()
    mov = df[~df.internal]
    n2w = sum(len(pc['g']) for pc in pieces if pc['type'] == MOTO); on2w = sum(len(sp['g']) for pc in pieces if pc['type'] == MOTO for sp in onpath[pc['tid']])
    nall = sum(len(pc['g']) for pc in pieces if pc['type'] != MOTO); onall = sum(len(sp['g']) for pc in pieces if pc['type'] != MOTO for sp in onpath[pc['tid']])
    read_edges = set(SA[(SA.R >= 0.8) & (SA.green > 5) & (SA.green < SA.cycle - 5)].edge) if SA is not None else set()
    census, census_veh = link_census(D, df, read_edges)
    tls.update(links_by_status=census, movements_by_status=census_veh)
    import xml.etree.ElementTree as ET
    json.dump({e.get('id'): e.get('name') for e in ET.parse(f'{D}/net.xml').getroot().iter('edge') if e.get('name')}, open(f'{D}/names.json', 'w'), ensure_ascii=False)
    tls.update(lane_movements=n_mv, lane_movements_without_connection=n_bad, connections_added=sum(1 for _ in open(f'{D}/observed.con.xml')) - 2)
    meta = dict(drone=dr, day=day, period=hh, begin=float(np.floor(t0)), end=float(np.ceil(t1)), box=box, edges_with_density_lanes=patched, tls=tls,
                samples=int(len(A['x'])), off_net_share=round(off_net, 4), fronts_moved_to_next_lane=moved, samples_leaving_dropped=int(leaving.sum()), bridged_through_unseen_edges=len(bridge), cut_not_a_path=int(bad.sum()), vehicles=int(nveh), pieces=len(pieces), pieces_per_vehicle=round(len(pieces) / max(nveh, 1), 2),
                pieces_skipped=skipped, simulated=len(first_piece), later_pieces_of_simulated=sum(len(v) for v in later.values()),
                later_pieces_stitched=int(sum(s_['joined'] for s_ in stitched.values())),
                entry_kinds={k: int(v) for k, v in E.kind.value_counts().items()},
                two_wheeler_samples_on_car_path=round(on2w / max(n2w, 1), 4), two_wheeler_trips_mix=sum(len(onpath[pc['tid']]) for pc in pieces if pc['type'] == MOTO),
                other_samples_on_car_path=round(onall / max(nall, 1), 4),
                by_class_pieces={PN.TYPES[k]: int(sum(1 for pc in pieces if pc['type'] == k)) for k in range(7)},
                lateral_abs_m=dict(p50=round(float(mov.lat.abs().median()), 3), p90=round(float(mov.lat.abs().quantile(.9)), 3)),
                lateral_abs_cars_m=dict(p50=round(float(mov[mov.type.isin([0, 1])].lat.abs().median()), 3)), internal_share=round(float(df.internal.mean()), 3))
    json.dump(meta, open(f'{D}/scene.json', 'w'), indent=1)
    print(json.dumps(meta))


def f100(dr=DRONE, day=DAY, hh=HH, gpu=False, dt=0.2):
    import levelx_f100 as LF
    D = outdir(dr, day, hh); meta = json.load(open(f'{D}/scene.json'))
    args = ['--net', f'{D}/net.xml', '--additional', f'{D}/tls.add.xml', '--routes', f'{D}/routes_all.xml', '--replay', f'{D}/all.rpl', '--dt', dt,
            '--begin', meta['begin'], '--end', meta['end'], '--time-to-teleport', 0, '--static-tls', '--fcd', f'{D}/f100.fcd.csv', '--fcd-interval', dt]
    log = run_cars(args, gpu=gpu, log=f'{D}/f100.log') if '--score' not in sys.argv else open(f'{D}/f100.log').read()
    m = pd.read_csv(f'{D}/matched.csv.gz')
    m['trip'] = m.vid.astype(int).astype(str) + '_' + m.piece.astype(str)
    m['k'] = np.round(m.ti * KEY_DT / dt).astype(np.int64); m = m[np.abs(m.ti * KEY_DT / dt - m.k) < 1e-3]
    f = pd.read_csv(f'{D}/f100.fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed', 'offset'])
    f['k'] = np.round(f.time / dt).astype(np.int64)
    first = f.groupby('trip').k.transform('min') == f.k
    f = f[~first]
    j = m.merge(f, on=['trip', 'k'], how='left', suffixes=('', '_sim'))
    trips = set(f.trip)
    j = j[j.trip.isin(trips)]
    k = j[j.pos.notna()].copy()
    LSx = lane_shapes(f'{D}/net.xml'); poly = {l: Polyline(v['shape'], v['length']) for l, v in LSx.items()}
    x = np.full(len(k), np.nan); y = np.full(len(k), np.nan)
    for l, g in k.groupby('lane_sim'):
        if l in poly:
            ix = k.index.get_indexer(g.index); x[ix], y[ix] = LF.centre_xy(poly[l], g.pos.values, g.offset.values)
    d2 = np.hypot(x - k.xf.values, y - k.yf.values)
    same = (k.lane_sim == k.lane).values
    q = lambda v: {f'p{p}': round(float(np.nanpercentile(v, p)), 4) for p in (50, 90, 99, 100)} if len(v) else None
    res = dict(scene=os.path.basename(D), log=[l for l in log.splitlines() if l.startswith('replay') or 'collisions' in l],
               samples_on_grid=int(len(j)), in_output=int(len(k)), missing=int(j.pos.isna().sum()), lane_mismatch=round(float((~same).mean()), 5),
               harness_pos_abs_m=q((k.pos - k.s).abs()[same]), harness_lat_abs_m=q((k.offset - k.lat).abs()[same]),
               front_2d_m=q(d2), front_2d_m_on_edges=q(d2[~k.internal.values.astype(bool)]), front_2d_m_internal=q(d2[k.internal.values.astype(bool)]),
               lateral_abs_m=meta['lateral_abs_m'], off_net_share=meta['off_net_share'], pieces_per_vehicle=meta['pieces_per_vehicle'])
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay', f'f100_pneuma_d{dr}_{day}_{hh}.json'), 'w'), indent=1)


def planned(D, name, begin, dt):
    import xml.etree.ElementTree as ET
    out = {}
    for v in ET.parse(f'{D}/routes_{name}.xml').getroot().iter('vehicle'):
        out[v.get('id')] = (v.get('type'), int(np.ceil((float(v.get('depart')) - begin) / dt - 1e-6)))
    return out


def entry_delays(f, D, name, begin, end, dt):
    """Entry delay of every checked entry: insertion step minus planned step (s); never inserted = still waiting."""
    E = pd.read_csv(f'{D}/entries.csv')
    E = E[~E.kind.isin(['snapshot'])]
    plan = planned(D, name, begin, dt)
    ins = f.groupby('trip').depart_step.first()
    E['planned'] = [plan[t][1] if t in plan else -1 for t in E.tid]
    E['delay'] = [(ins[t] - p) * dt if t in ins.index else np.nan for t, p in zip(E.tid, E.planned)]
    due = E[E.planned * dt + begin < end - 1.0]
    waiting = int(due.delay.isna().sum())
    q = lambda v: dict(n=int(len(v)), p50=round(float(np.median(v)), 2), p95=round(float(np.percentile(v, 95)), 2), max=round(float(v.max()), 2)) if len(v) else None
    ok = due[due.delay.notna()]
    names = json.load(open(f'{D}/names.json')) if os.path.exists(f'{D}/names.json') else {}
    by_app = {f'{e} {names.get(e, "")}'.strip(): q(h.delay.values) for e, h in ok.groupby('edge') if len(h) >= 5}
    return dict(checked=int(len(due)), waiting_at_end=waiting, delay_s=q(ok.delay.values), by_kind={k: q(h.delay.values) for k, h in ok.groupby('kind')}, by_approach=by_app), E


def entry(dr=DRONE, day=DAY, hh=HH, seeds=(0, 1), gpu=True, dt=0.2):
    """F520: cars enter through the checked entry, then are replayed; everything else replayed."""
    D = outdir(dr, day, hh); meta = json.load(open(f'{D}/scene.json'))
    res = {}
    for sd in seeds:
        fcd = f'{D}/entry_s{sd}.fcd.csv'
        args = ['--net', f'{D}/net.xml', '--additional', f'{D}/tls.add.xml', '--routes', f'{D}/routes_entry.xml', '--replay', f'{D}/entry.rpl', '--dt', dt,
                '--begin', meta['begin'], '--end', meta['end'], '--seed', sd, '--time-to-teleport', 0, '--static-tls', '--fcd', fcd, '--fcd-interval', 1.0]
        log = run_cars(args, gpu=gpu, log=f'{D}/entry_s{sd}.log') if '--score' not in sys.argv else open(f'{D}/entry_s{sd}.log').read()
        f = pd.read_csv(fcd, usecols=['time', 'trip', 'speed', 'depart_step'])
        r, E = entry_delays(f, D, 'entry', meta['begin'], meta['end'], dt)
        r['log'] = [l for l in log.splitlines() if l.startswith('replay') or 'collisions' in l or l.startswith('wall')]
        res[sd] = r
        print(sd, json.dumps({k: v for k, v in r.items() if k != 'log'}), flush=True)
    json.dump(dict(scene=os.path.basename(D), entry_kinds=meta['entry_kinds'], runs=res), open(os.path.join(REPO, 'research/truth/replay', f'f520_pneuma_d{dr}_{day}_{hh}.json'), 'w'), indent=1)


def recording_side(D, meta):
    """The recording's own numbers for the simulated cars: entry and exit points, travel times, approach delays."""
    import t3_metrics as TM
    m = pd.read_csv(f'{D}/matched.csv.gz')
    st = pd.read_csv(f'{D}/stitched.csv'); E = pd.read_csv(f'{D}/entries.csv')
    st = st.merge(E[['vid', 'tid', 'edge', 's_seen', 't_seen', 'kind']], on='vid')
    trips = {f'{v}_{p}': t for v, t, ps in zip(st.vid, st.tid, st.pieces) for p in str(ps).split()}
    rec = TM.from_matched(m, trips)
    return st, rec


def score_run(f, D, meta, name, dt, st, rec, apps, sim_ids, two_w):
    import t3_metrics as TM, overlaps
    r, _ = entry_delays(f, D, name, meta['begin'], meta['end'], dt)
    sim = TM.from_fcd(f[f.trip.isin(sim_ids)])
    t_in = TM.crossings_many(sim, pd.DataFrame(dict(trip=st.tid, edge=st.edge, s=st.s_seen)))
    t_out = TM.crossings_many(sim, pd.DataFrame(dict(trip=st.tid, edge=st.exit_edge, s=st.exit_s)))
    S = st.set_index('tid')
    rec_tt = S.exit_t - S.t_seen
    done_rec = S.exit_t < meta['end'] - 2.0
    both = t_in.index.intersection(t_out.index)
    tt = (t_out[both] - t_in[both]); err = tt - rec_tt[both]
    binned = ((S.exit_t[both] - meta['begin']) // TM.BIN).astype(int)
    ov = overlaps.find(f, pd.DataFrame(dict(trip=list(sim_ids), sim=True)))
    clean = [t for t in both if t not in ov['first_overlap_with_replayed'] or ov['first_overlap_with_replayed'][t] > t_out[t]]
    q = lambda v: dict(n=int(len(v)), mae=round(float(np.mean(np.abs(v))), 2), bias=round(float(np.mean(v)), 2), p90_abs=round(float(np.percentile(np.abs(v), 90)), 2)) if len(v) else None
    dl_sim = TM.approach_delays(sim, apps, meta['begin'])
    dl_rec = TM.approach_delays(rec, apps, meta['begin'])
    last = f[f.trip.isin(sim_ids)].groupby('trip').time.max()
    r.update(simulated=int(len(sim_ids)), entered=int(f[f.trip.isin(sim_ids)].trip.nunique()),
             completed=int(t_out.index.isin(S.index[done_rec]).sum()), completed_recording=int(done_rec.sum()),
             on_net_at_end=int((last >= meta['end'] - 1.5).sum()), on_net_at_end_recording=int((~done_rec).sum()),
             travel_time_error_s=q(err.values), travel_time_error_before_overlap_s=q(err[clean].values),
             travel_time_mae_by_bin={int(k): round(float(np.mean(np.abs(err[binned == k]))), 2) for k in sorted(set(binned))},
             recorded_travel_time_s=round(float(rec_tt[both].mean()), 2),
             approach_delay=TM.compare_delays(dl_rec, dl_sim), approaches=len(apps),
             sim_cars_meeting_replayed=len(ov['first_overlap_with_replayed']), overlap_pairs=ov['pairs_by_kind'],
             held_by_two_wheeler=TM.held_by(f, sim_ids, two_w))
    # the same aggregates as the noise floor (t3_floor.py): per-approach mean delay over the run, per-route mean travel
    # time over the cars that reached their exit (recording restricted to the same cars)
    key = (S.edge + '>' + S.exit_edge)[both]
    r['session_delay'] = TM.compare_means(TM.session_delay(dl_rec, 30), TM.session_delay(dl_sim, 10), 10)
    r['route_travel_time'] = TM.compare_means(TM.route_tt(pd.DataFrame(dict(route=key, tt=rec_tt[both]))), TM.route_tt(pd.DataFrame(dict(route=key, tt=tt))))
    return r


def mix(dr=DRONE, day=DAY, hh=HH, seeds=range(5), gpu=True, dt=0.25, name='mix'):
    """F515 again as a harness check: every car simulated from its checked entry, everything else replayed."""
    import t3_metrics as TM, xml.etree.ElementTree as ET
    D = outdir(dr, day, hh); meta = json.load(open(f'{D}/scene.json'))
    st, rec = recording_side(D, meta)
    lanes, conn, links = net_info(f'{D}/net.xml')
    lengths = {d['edge']: d['length'] for l, d in lanes.items() if not d['internal']}
    incoming = sorted({a for a, b in conn})
    apps = TM.approaches(rec, lengths, incoming)
    trips = {v.get('id'): v.get('type') for v in ET.parse(f'{D}/routes_{name}.xml').getroot().iter('vehicle')}
    sim_ids = {t for t, ty in trips.items() if ty == 'drv'}; two_w = {t for t, ty in trips.items() if ty == f'rep{MOTO}'}
    res = {}
    for sd in seeds:
        fcd = f'{D}/{name}_s{sd}.fcd.csv'
        args = ['--net', f'{D}/net.xml', '--additional', f'{D}/tls.add.xml', '--routes', f'{D}/routes_{name}.xml', '--replay', f'{D}/{name}.rpl', '--dt', dt,
                '--begin', meta['begin'], '--end', meta['end'], '--seed', sd, '--time-to-teleport', 0, '--static-tls', '--fcd', fcd, '--fcd-interval', 1.0]
        log = run_cars(args, gpu=gpu, log=f'{D}/{name}_s{sd}.log') if '--score' not in sys.argv else open(f'{D}/{name}_s{sd}.log').read()
        f = pd.read_csv(fcd, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'length', 'depart_step'])
        r = score_run(f, D, meta, name, dt, st, rec, apps, sim_ids, two_w)
        r['log'] = [l for l in log.splitlines() if l.startswith('replay') or 'collisions' in l or l.startswith('wall')]
        res[sd] = r
        print(sd, json.dumps({k: v for k, v in r.items() if k not in ('log', 'by_approach')}), flush=True)
    out = dict(scene=os.path.basename(D), variant=name, entry_kinds=meta['entry_kinds'], tls=meta['tls'], runs=res)
    json.dump(out, open(os.path.join(REPO, 'research/truth/replay', f'f515_{name}_pneuma_d{dr}_{day}_{hh}.json'), 'w'), indent=1)


if __name__ == '__main__':
    c = sys.argv[1]
    a = [x for x in sys.argv[2:] if not x.startswith('--')]
    dr, day, hh = (int(a[0]), a[1], a[2]) if len(a) >= 3 else (DRONE, DAY, HH)
    if c == 'build':
        build(dr, day, hh)
    elif c == 'f100':
        f100(dr, day, hh, '--gpu' in sys.argv)
    elif c == 'entry':
        entry(dr, day, hh)
    elif c == 'mix':
        mix(dr, day, hh, name=next((x[7:] for x in sys.argv if x.startswith('--name=')), 'mix'),
            seeds=[int(x) for x in next((x[8:] for x in sys.argv if x.startswith('--seeds=')), '0,1,2,3,4').split(',')])
