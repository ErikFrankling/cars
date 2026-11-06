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
    return patched, box


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
            lanes[ln.get('id')] = dict(edge=e.get('id'), internal=internal, shape=pts, length=float(ln.get('length')))
    conn, links = set(), {}
    via_to = {}
    for c in r.iter('connection'):
        if c.get('from', '').startswith(':'):
            continue
        conn.add((c.get('from'), c.get('to')))
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


def programs(D, dr, day, hh, links, t0, t1):
    """One long program per signalised junction from the read approaches of this file."""
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


def build(dr=DRONE, day=DAY, hh=HH):
    D = outdir(dr, day, hh); os.makedirs(D, exist_ok=True)
    patched, box = build_net(D, dr)
    lanes, conn, links = net_info(f'{D}/net.xml')
    A = PN.samples(day, dr, hh)
    t0, t1 = float(A['t'].min()), float(A['t'].max())
    tls = programs(D, dr, day, hh, links, t0, t1)
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
    LS = {l: lanes[l]['length'] for l in lanes}
    lane_list = sorted(lanes)
    lidx = {l: i for i, l in enumerate(lane_list)}
    tracks_all, tracks_mix, trips_all, trips_mix = [], [], [], []
    sim_started, dropped = set(), 0
    for p, g in df.groupby('piece', sort=False):
        if len(g) < 3 or g.internal.iloc[0]:
            continue
        route = []
        for e, v in zip(g.edge[~g.internal], g.via[~g.internal]):
            if v:
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
                    continue
        if len(route) != len(set(route)):
            continue
        tid = f'{int(g.vid.iloc[0])}_{p}'
        ty = int(g.type.iloc[0])
        key = (tid, float(g.ti.iloc[0] * KEY_DT), KEY_DT, INF, [lidx[l] for l in g.lane], g.s.values, g.v.values, g.lat.values)
        row = dict(t0=float(g.ti.iloc[0] * KEY_DT), tid=tid, lane=int(g.lane.iloc[0].rsplit('_', 1)[1]), pos=float(g.s.iloc[0]), v=float(g.v.iloc[0]),
                   route=' '.join(route), type=ty)
        tracks_all.append(key); trips_all.append(dict(row, kind='rep'))
        if ty in SIM_TYPES:
            if g.vid.iloc[0] in sim_started:
                dropped += 1
                continue
            sim_started.add(g.vid.iloc[0]); trips_mix.append(dict(row, kind='drv'))
        else:
            tracks_mix.append(key); trips_mix.append(dict(row, kind='rep'))
    df[['vid', 'piece', 'ti', 'type', 'lane', 'internal', 's', 'lat', 'x', 'y', 'xf', 'yf', 'v', 'L']].to_csv(f'{D}/matched.csv.gz', index=False)
    write_rpl(f'{D}/all.rpl', lane_list, tracks_all)
    write_rpl(f'{D}/mix.rpl', lane_list, tracks_mix)
    for name, trips in (('all', trips_all), ('mix', trips_mix)):
        with open(f'{D}/routes_{name}.xml', 'w') as f:
            f.write('<routes>\n  <vType id="drv" carFollowModel="Krauss"/>\n')
            for k, (L, W) in PN.DIMS.items():
                f.write(f'  <vType id="rep{k}" length="{L}" width="{W}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
            for r in sorted(trips, key=lambda r: (r['t0'], r['tid'])):
                vt = 'drv' if r['kind'] == 'drv' else f'rep{r["type"]}'
                f.write(f'  <vehicle id="{r["tid"]}" type="{vt}" depart="{r["t0"]:.2f}" departLane="{r["lane"]}" departPos="{max(r["pos"], 0):.3f}" '
                        f'departSpeed="{max(r["v"], 0):.3f}"><route edges="{r["route"]}"/></vehicle>\n')
            f.write('</routes>\n')
    nveh = df.vid.nunique()
    mov = df[~df.internal]
    meta = dict(drone=dr, day=day, period=hh, begin=float(np.floor(t0)), end=float(np.ceil(t1)), box=box, edges_with_density_lanes=patched, tls=tls,
                samples=int(len(A['x'])), off_net_share=round(off_net, 4), fronts_moved_to_next_lane=moved, samples_leaving_dropped=int(leaving.sum()), bridged_through_unseen_edges=len(bridge), cut_not_a_path=int(bad.sum()), vehicles=int(nveh), pieces=len(tracks_all), pieces_per_vehicle=round(len(tracks_all) / max(nveh, 1), 2),
                simulated=len(sim_started), later_pieces_of_simulated_dropped=dropped, replayed_in_mix=len(tracks_mix),
                by_class_pieces={PN.TYPES[k]: int(sum(1 for r in trips_all if r['type'] == k)) for k in range(7)},
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


if __name__ == '__main__':
    c = sys.argv[1]
    a = [x for x in sys.argv[2:] if not x.startswith('--')]
    dr, day, hh = (int(a[0]), a[1], a[2]) if len(a) >= 3 else (DRONE, DAY, HH)
    if c == 'build':
        build(dr, day, hh)
    elif c == 'f100':
        f100(dr, day, hh, '--gpu' in sys.argv)
