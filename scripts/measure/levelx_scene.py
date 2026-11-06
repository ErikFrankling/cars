"""levelX recordings as replay scenes (research/truth/replay/README.md): net, routes, .rpl, matched samples, scene.json.

    python3 -I scripts/measure/levelx_scene.py highD 1          # -> cars-data/replay/levelx-highD-01/
    python3 -I scripts/measure/levelx_scene.py exiD 0 [--holdout]

highD: one edge per carriageway, straight lanes at the recording's lane markings, lane changes kept inside a track.
inD, rounD, exiD: every vehicle lanelet of the site's Lanelet2 map is a one-lane edge, joined where one lanelet's end
boundary is the next one's start. A track is cut where it moves to a lanelet that is not a successor (a lane change, or
a map gap); the pieces are separate replayed trips, counted in scene.json. With --merge (default for exiD) parallel
lanelets, those that share a boundary and drive the same way, are one multi-lane edge, so a lane change stays inside a
track and a simulated car can change lanes there.

Keys carry the lateral offset from the lane's centreline (RPL2), so replayed vehicles move sideways as recorded.

Positions are the vehicle front (SUMO convention), keys at the recording's 25 Hz. No simulator is run here; the check is
structural: every key's lane is on its route, consecutive route edges are connected in the net, and the map-matching
residual (distance of the recorded centre from its lane's centreline) is reported.
"""
import os, sys, json, gzip, xml.etree.ElementTree as ET
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'replay'))
import levelx as LX
from holdout import held
from rpl import write_rpl, netconvert, fmt_shape, lane_shapes, Polyline, INF

OUT = '/home/erikf/projects/personal/cars-data/replay'
VEH = {'road', 'highway', 'bus_lane'}
q = lambda v: {f'p{p}': round(float(np.percentile(v, p)), 3) for p in (50, 90, 99)} if len(v) else {}


def highd_lanes(meta, d):
    """laneId -> (edge, index, centre y, width); index 0 is the rightmost lane in the driving direction."""
    up = [float(v) for v in str(meta['upperLaneMarkings']).split(';')]
    lo = [float(v) for v in str(meta['lowerLaneMarkings']).split(';')]
    out = {}
    for lid, g in d.groupby('lane'):
        y = float(g.yc.median()); dirn = int(g.dir.iloc[0])
        mk = up if dirn == 1 else lo
        k = int(np.searchsorted(mk, y)) - 1
        if not 0 <= k < len(mk) - 1:
            continue
        # Upper carriageway drives -x with y down: its right-hand side is the smallest y.
        idx = k if dirn == 1 else len(mk) - 2 - k
        out[int(lid)] = ('U' if dirn == 1 else 'D', idx, (mk[k] + mk[k + 1]) / 2, mk[k + 1] - mk[k], len(mk) - 1)
    return out


def build_highd(rec, out):
    meta = LX.recordings('highD', holdout=True).set_index('rec').loc[rec].raw
    d = LX.tracks('highD', rec)
    lanes = highd_lanes(meta, d)
    x0, x1 = float(d.xc.min() - 20), float(d.xc.max() + 20)
    nl = {e: max(v[4] for v in lanes.values() if v[0] == e) for e in ('U', 'D')}
    with open(f'{out}/plain.nod.xml', 'w') as f:
        f.write('<nodes>\n')
        for e in ('U', 'D'):
            ys = [v[2] for v in lanes.values() if v[0] == e]; ym = -float(np.mean(ys))
            a, b = (x1, x0) if e == 'U' else (x0, x1)
            f.write(f'  <node id="{e}a" x="{a:.2f}" y="{ym:.3f}"/>\n  <node id="{e}b" x="{b:.2f}" y="{ym:.3f}"/>\n')
        f.write('</nodes>\n')
    with open(f'{out}/plain.edg.xml', 'w') as f:
        f.write('<edges>\n')
        for e in ('U', 'D'):
            a, b = (x1, x0) if e == 'U' else (x0, x1)
            f.write(f'  <edge id="{e}" from="{e}a" to="{e}b" numLanes="{nl[e]}" speed="36.11" spreadType="center">\n')
            for lid, (ee, idx, yc, w, _) in sorted(lanes.items(), key=lambda kv: kv[1][1]):
                if ee == e:
                    f.write(f'    <lane index="{idx}" width="{w:.2f}" shape="{a:.2f},{-yc:.3f} {b:.2f},{-yc:.3f}"/>\n')
            f.write('  </edge>\n')
        f.write('</edges>\n')
    netconvert(f'{out}/plain', f'{out}/net.xml')
    d = d[d.lane.isin(list(lanes))].copy()
    e = np.array([lanes[l][0] for l in d.lane]); idx = np.array([lanes[l][1] for l in d.lane])
    yc = np.array([lanes[l][2] for l in d.lane])
    up = e == 'U'
    front = np.where(up, d.xc - d.length / 2, d.xc + d.length / 2)
    d['edge'] = e; d['lane_id'] = [f'{a}_{b}' for a, b in zip(e, idx)]
    d['s'] = np.where(up, x1 - front, front - x0)
    d['lat'] = np.where(up, -(d.yc - yc), d.yc - yc)
    d['lat_left'] = -d['lat']
    d['v'] = np.abs(d.vx)
    d['ti'] = d.frame
    return finish(out, 'highD', rec, d, 25.0, lambda g: [g.edge.iloc[0]])


def lanelet_net(ds, site, out, construction=False):
    ll = {k: v for k, v in LX.lanelets(ds, site, construction).items() if v['tags'].get('subtype') in VEH}
    key = lambda v, end: (v['left_nodes'][-1 if end else 0], v['right_nodes'][-1 if end else 0])
    nodes = {}
    for k, v in ll.items():
        for end in (0, 1):
            nodes.setdefault(key(v, end), []).append(v['centre'][-1 if end else 0])
    nid = {kk: f'n{i}' for i, kk in enumerate(nodes)}
    with open(f'{out}/plain.nod.xml', 'w') as f:
        f.write('<nodes>\n')
        for kk, pts in nodes.items():
            p = np.mean(pts, axis=0)
            f.write(f'  <node id="{nid[kk]}" x="{p[0]:.3f}" y="{p[1]:.3f}"/>\n')
        f.write('</nodes>\n')
    with open(f'{out}/plain.edg.xml', 'w') as f:
        f.write('<edges>\n')
        for k, v in ll.items():
            a, b = nid[key(v, 0)], nid[key(v, 1)]
            if a == b:
                continue
            w = float(np.median(np.hypot(*(LX._resample(v['left'], 20) - LX._resample(v['right'], 20)).T)))
            sp = 13.89 if v['tags'].get('location') == 'urban' or ds in ('inD', 'rounD') else 36.11
            f.write(f'  <edge id="L{k}" from="{a}" to="{b}" numLanes="1" speed="{sp}" spreadType="center" '
                    f'width="{max(w, 2.0):.2f}" shape="{fmt_shape(v["centre"])}"/>\n')
        f.write('</edges>\n')
    netconvert(f'{out}/plain', f'{out}/net.xml', ['--geometry.remove', 'false', '--junctions.join', 'false',
                                                  '--no-turnarounds.except-deadend', 'false'])
    return ll


def merged_lanelet_net(ds, site, out, construction=False):
    """Parallel lanelets (a shared boundary way, same driving direction) as one multi-lane edge, lanes right to left;
    connections lane to lane from the lanelets' successions. Returns lanelet id -> lane id."""
    ll = {k: v for k, v in LX.lanelets(ds, site, construction).items() if v['tags'].get('subtype') in VEH}
    dirv = {k: (v['centre'][-1] - v['centre'][0]) / max(np.hypot(*(v['centre'][-1] - v['centre'][0])), 1e-9) for k, v in ll.items()}
    by_right = {}
    for k, v in ll.items():
        by_right.setdefault(v['right_way'], []).append(k)
    left_of = {}
    for k, v in ll.items():
        for o in by_right.get(v['left_way'], []):
            if o != k and dirv[k] @ dirv[o] > 0.5:
                left_of[k] = o
    right_of = {o: k for k, o in left_of.items()}
    comp, seen = {}, set()
    for k in ll:
        if k in seen:
            continue
        r = k
        while r in right_of and right_of[r] not in seen and right_of[r] != k:
            r = right_of[r]
        row = [r]; seen.add(r)
        while row[-1] in left_of and left_of[row[-1]] not in seen:
            row.append(left_of[row[-1]]); seen.add(row[-1])
        comp[f'E{row[0]}'] = row
    lane_of = {k: f'{e}_{i}' for e, row in comp.items() for i, k in enumerate(row)}
    edge_of = {k: e for e, row in comp.items() for k in row}
    start = lambda v: (v['left_nodes'][0], v['right_nodes'][0])
    end = lambda v: (v['left_nodes'][-1], v['right_nodes'][-1])
    succ = [(a, b) for a in ll for b in ll if a != b and end(ll[a]) == start(ll[b])]
    # nodes: union of edge ends that a succession joins
    par = {}
    def find(x):
        while par.setdefault(x, x) != x:
            x = par[x]
        return x
    for e in comp:
        find((e, 0)); find((e, 1))
    for a, b in succ:
        par[find((edge_of[a], 1))] = find((edge_of[b], 0))
    pts = {}
    for e, row in comp.items():
        for end_ in (0, 1):
            c = np.mean([ll[k]['centre'][-1 if end_ else 0] for k in row], axis=0)
            pts.setdefault(find((e, end_)), []).append(c)
    nid = {r: f'n{i}' for i, r in enumerate(pts)}
    with open(f'{out}/plain.nod.xml', 'w') as f:
        f.write('<nodes>\n')
        for r, ps in pts.items():
            p = np.mean(ps, axis=0)
            f.write(f'  <node id="{nid[r]}" x="{p[0]:.3f}" y="{p[1]:.3f}"/>\n')
        f.write('</nodes>\n')
    with open(f'{out}/plain.edg.xml', 'w') as f:
        f.write('<edges>\n')
        for e, row in comp.items():
            a, b = nid[find((e, 0))], nid[find((e, 1))]
            if a == b:
                continue
            sp = 13.89 if ll[row[0]]['tags'].get('location') == 'urban' or ds in ('inD', 'rounD') else 36.11
            L = LX._resample(ll[row[-1]]['left'], 40); R = LX._resample(ll[row[0]]['right'], 40)
            f.write(f'  <edge id="{e}" from="{a}" to="{b}" numLanes="{len(row)}" speed="{sp}" spreadType="center" shape="{fmt_shape((L + R) / 2)}">\n')
            for i, k in enumerate(row):
                w = float(np.median(np.hypot(*(LX._resample(ll[k]['left'], 20) - LX._resample(ll[k]['right'], 20)).T)))
                f.write(f'    <lane index="{i}" width="{max(w, 2.0):.2f}" shape="{fmt_shape(ll[k]["centre"])}"/>\n')
            f.write('  </edge>\n')
        f.write('</edges>\n')
    with open(f'{out}/plain.con.xml', 'w') as f:
        f.write('<connections>\n')
        for a, b in succ:
            if edge_of[a] != edge_of[b]:
                f.write(f'  <connection from="{edge_of[a]}" to="{edge_of[b]}" fromLane="{lane_of[a].rsplit("_", 1)[1]}" toLane="{lane_of[b].rsplit("_", 1)[1]}"/>\n')
        f.write('</connections>\n')
    netconvert(f'{out}/plain', f'{out}/net.xml', ['-x', f'{out}/plain.con.xml', '--geometry.remove', 'false', '--junctions.join', 'false', '--default.junctions.radius', '0',
                                                  '--no-turnarounds.except-deadend', 'false'])
    return {k: lane_of[k] for k in ll}, comp


def connections(net_xml):
    c = set()
    for x in ET.parse(net_xml).getroot().iter('connection'):
        c.add((x.get('from'), x.get('to')))
    return c


def match_lanelets(d, lanes, conn, provided=None, lane_of_lanelet=None):
    """Nearest lanelet centreline whose direction agrees within 45 degrees (or the provider's lanelet, exiD)."""
    from scipy.spatial import cKDTree
    P, H, L, S = [], [], [], []
    poly = {}
    for lid, v in lanes.items():
        pl = Polyline(v['shape'], v['length']); poly[lid] = pl
        s = np.arange(0, pl.cum[-1], 0.5)
        x, y = pl.point(s * pl.scale)
        i = np.clip(np.searchsorted(pl.cum, s, side='right') - 1, 0, len(pl.seg) - 1)
        P.append(np.c_[x, y]); H.append(np.arctan2(pl.u[i, 1], pl.u[i, 0])); L.extend([lid] * len(s))
    P = np.vstack(P); H = np.concatenate(H); L = np.array(L)
    tree = cKDTree(P)
    hd = np.deg2rad(d.heading.to_numpy())
    dist, ii = tree.query(np.c_[d.xc, d.yc], k=16)
    ok = np.cos(H[ii] - hd[:, None]) > np.cos(np.deg2rad(45))
    first = np.where(ok.any(1), ok.argmax(1), 0)
    lane = L[ii[np.arange(len(d)), first]]
    if provided is not None:
        lp = np.array([(lane_of_lanelet.get(int(x), '') if lane_of_lanelet else f'L{int(x)}_0') if np.isfinite(x) else '' for x in provided])
        use = np.isin(lp, list(lanes))
        lane = np.where(use, lp, lane)
    d = d.copy(); d['lane_id'] = lane; d['edge'] = [l.rsplit('_', 1)[0] for l in lane]
    d['s'] = 0.0; d['lat'] = 0.0
    h = np.deg2rad(d.heading.to_numpy())
    d['xf'] = d.xc + 0.5 * d.length * np.cos(h); d['yf'] = d.yc + 0.5 * d.length * np.sin(h)
    for lid, g in d.groupby('lane_id'):
        s, lat = poly[lid].project(g.xc.values, g.yc.values)
        sf, _ = poly[lid].project(g.xf.values, g.yf.values)
        d.loc[g.index, 'lat'] = lat
        # The front, as the simulator keeps it: the front point's projection, or past the lane's end when the
        # centre's projection says so (moved to the next lane in finish()).
        over = s + g.length.values / 2 > poly[lid].cum[-1] * poly[lid].scale
        d.loc[g.index, 's'] = np.where(over, s + g.length.values / 2, sf)
    d['v'] = np.hypot(d.vx, d.vy)
    d['lat_left'] = d['lat']
    return d


def build_drone(ds, rec, out, merge=False):
    m = LX.recordings(ds, holdout=True).set_index('rec').loc[rec]
    construction = ds == 'inD' and m.site == 1 and 11 <= rec <= 17
    lol = None
    if merge:
        lol, comp = merged_lanelet_net(ds, int(m.site), out, construction)
    else:
        lanelet_net(ds, int(m.site), out, construction)
    lanes = lane_shapes(f'{out}/net.xml')
    conn = connections(f'{out}/net.xml')
    tm = LX.tracks_meta(ds, rec).set_index('trackId')
    d = LX.tracks(ds, rec)
    cls = tm['class'].reindex(d.id).values
    d = d[np.isin(cls, ['car', 'truck', 'van', 'bus', 'truck_bus', 'trailer', 'motorcycle'])].reset_index(drop=True)
    lid = None
    if 'laneletId' in d:
        # exiD gives one or more lanelets per sample ("a;b"); take the listed one the centre projects inside
        parts = d.laneletId.astype(str).str.split(';')
        lid = pd.to_numeric(parts.str[0], errors='coerce').to_numpy()
        multi = np.flatnonzero(parts.str.len().to_numpy() > 1)
        polys = {}
        for i in multi:
            best = None
            for c in parts.iat[i]:
                try:
                    ln_ = lol.get(int(float(c))) if lol else f'L{int(float(c))}_0'
                except ValueError:
                    continue
                if ln_ not in lanes:
                    continue
                pl = polys.setdefault(ln_, Polyline(lanes[ln_]['shape'], lanes[ln_]['length']))
                sc, la = pl.project([d.xc.iat[i]], [d.yc.iat[i]])
                inside = 0.01 < sc[0] < pl.cum[-1] * pl.scale - 0.01
                key = (not inside, abs(la[0]))
                if best is None or key < best[0]:
                    best = (key, float(c))
            if best:
                lid[i] = best[1]
    d = match_lanelets(d, lanes, conn, lid, lol)
    d['ti'] = d.frame
    return finish(out, ds, rec, d, 25.0, None, conn)


def finish(out, ds, rec, d, fps, route_of, conn=None):
    """Cut tracks into pieces that are paths in the net, write .rpl, routes, matched samples and scene.json."""
    d = d.sort_values(['id', 'ti']).reset_index(drop=True)
    ed = d.edge.to_numpy(); ids = d.id.to_numpy(); ti = d.ti.to_numpy()
    newtrack = np.r_[True, (ids[1:] != ids[:-1]) | (ti[1:] != ti[:-1] + 1)]
    if conn is not None:
        step = np.r_[False, ed[1:] != ed[:-1]]
        ok = np.array([(a, b) in conn for a, b in zip(ed[:-1], ed[1:])])
        cut_conn = step & ~np.r_[True, ok]
        # A jitter back onto the previous lanelet near the boundary is also not a path: it cuts too.
    else:
        cut_conn = np.zeros(len(d), bool)
    d['piece'] = np.cumsum(newtrack | cut_conn)
    LS = lane_shapes(f'{out}/net.xml')
    lane_list = sorted(LS)
    # A front past the end of the centre's lane belongs on the next lane the track takes (the providers label the
    # lane of the centre).
    moved = 0
    ln = d.lane_id.map(lambda l: LS[l]['length']).to_numpy()
    over = np.flatnonzero(d.s.to_numpy() > ln)
    if len(over):
        lane = d.lane_id.to_numpy().copy(); sv = d.s.to_numpy().copy(); pc = d.piece.to_numpy(); latl = d.lat_left.to_numpy().copy()
        nxt = np.full(len(d), -1)
        chg = np.flatnonzero((lane[1:] != lane[:-1]) & (pc[1:] == pc[:-1])) + 1
        for i in over:
            k = np.searchsorted(chg, i, side='right')
            if k < len(chg) and pc[chg[k]] == pc[i] and lane[chg[k]].rsplit('_', 1)[0] != lane[i].rsplit('_', 1)[0]:
                lane[i] = lane[chg[k]]; moved += 1
                if 'xf' in d:
                    pl = Polyline(LS[lane[i]]['shape'], LS[lane[i]]['length'])
                    a, b = pl.project([d.xf.iat[i]], [d.yf.iat[i]])
                    sv[i] = float(a[0]); latl[i] = float(b[0])
                else:
                    sv[i] = sv[i] - ln[i]
        d['lane_id'] = lane; d['s'] = sv; d['lat_left'] = latl; d['edge'] = [l.rsplit('_', 1)[0] for l in lane]
    lidx = {l: k for k, l in enumerate(lane_list)}
    tracks, rows = [], []
    t_begin = float(np.floor(d.ti.min() / fps) - 1.0)
    for p, g in d.groupby('piece', sort=False):
        if len(g) < 2:
            continue
        route = list(dict.fromkeys(g.edge)) if route_of is None else route_of(g)
        if len(route) != len(set(g.edge)) or any(r != e for r, e in zip(route, pd.unique(g.edge))):
            continue
        tid = f'{int(g.id.iloc[0])}_{p}'
        t0 = float(g.ti.iloc[0]) / fps - t_begin
        tracks.append((tid, t0, 1.0 / fps, INF, [lidx[l] for l in g.lane_id], g.s.to_numpy(), g.v.to_numpy(), g.lat_left.to_numpy()))
        rows.append((t0, tid, ' '.join(route), float(g.s.iloc[0]), float(g.v.iloc[0]), round(float(g.length.iloc[0]), 1)))
    rows.sort()
    with open(f'{out}/routes.xml', 'w') as f:
        f.write('<routes>\n')
        for L in sorted({r[5] for r in rows}):
            f.write(f'  <vType id="rep{L}" length="{L}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
        for t0, tid, route, s, v, L in rows:
            f.write(f'  <vehicle id="{tid}" type="rep{L}" depart="{t0:.2f}" departLane="0" departPos="{s:.3f}" '
                    f'departSpeed="{max(v, 0):.3f}"><route edges="{route}"/></vehicle>\n')
        f.write('</routes>\n')
    write_rpl(f'{out}/all.rpl', lane_list, tracks)
    d[['id', 'piece', 'ti', 'lane_id', 's', 'lat', 'lat_left', 'xc', 'yc', 'v', 'length', 'heading']].to_csv(f'{out}/matched.csv.gz', index=False)
    bad_conn = 0
    if conn is not None:
        for _, _, route, *_ in rows:
            e = route.split()
            bad_conn += sum((a, b) not in conn for a, b in zip(e[:-1], e[1:]))
    meta = dict(dataset=ds, recording=rec, held_out=held(ds, rec), begin=0.0, recording_time_of_scene_zero_s=t_begin, key_dt=1.0 / fps,
                end=float(d.ti.max() / fps - t_begin + 1), samples=len(d), vehicles=int(d.id.nunique()), pieces=len(tracks),
                pieces_per_vehicle=round(len(tracks) / max(d.id.nunique(), 1), 2), lanes=len(lane_list),
                route_links_not_in_net=bad_conn, fronts_moved_to_next_lane=moved, map_lateral_abs_m=q(np.abs(d.lat)))
    json.dump(meta, open(f'{out}/scene.json', 'w'), indent=1)
    print(json.dumps(meta))
    return meta


def build(ds, rec, allow_holdout=False, merge=None):
    if held(ds, rec) and not allow_holdout:
        raise SystemExit(f'{ds} {rec} is held out (research/truth/measure/HOLDOUT.md); pass --holdout to build it')
    merge = (ds == 'exiD') if merge is None else merge
    out = os.path.join(OUT, f'levelx-{ds}-{rec:02d}' + ('-merged' if merge and ds != 'highD' else ''))
    os.makedirs(out, exist_ok=True)
    return build_highd(rec, out) if ds == 'highD' else build_drone(ds, rec, out, merge)


if __name__ == '__main__':
    build(sys.argv[1], int(sys.argv[2]), '--holdout' in sys.argv, True if '--merge' in sys.argv else False if '--no-merge' in sys.argv else None)
