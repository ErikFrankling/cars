"""DLR UT, one signalised approach (signal group 6: one lane, straight on, northbound), 14:00-17:00 of Sunday
24 September 2023. F100 replays every vehicle on the lane; F104 and F107 simulate every car that used signal group 6
from its recorded entry, with the recorded controller states, and replay everything else on the lane.

The lane is built from the tracks, as for TGSIM: the OpenDRIVE map converts with netconvert but its junction comes out
as overlapping fragments and no signal program (research/truth/replay/RESULTS.md). Coordinates are report 05's cache:
easting - 604625, northing - 5792650.

    python3 -I scripts/replay/dlrut_approach.py build
    python3 -I scripts/replay/dlrut_approach.py f100
    python3 -I scripts/replay/dlrut_approach.py f104 0..4
    python3 -I scripts/replay/dlrut_approach.py score
"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import *
import numpy as np, pandas as pd

CACHE = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-cache'
D = os.path.join(OUT, 'dlrut-sg6')
SG = 6
STOP = np.array([604784.549 - 604625, 5792776.031 - 5792650])      # dataset documentation, Table 3
CENTRE = np.array([146.72, 142.82])                                   # mean of all stop-line points of report 05's table
BEGIN, END = 14 * 3600 - 300.0, 17 * 3600 + 120.0
SCORE_FROM = 14 * 3600.0                                              # warm-up of 300 s, longer than any trip here
LAT = 1.4                                                             # on the lane; the next lane's cars sit 3 m or more off
H_SAT, LOST = 2.0, 2.7                                                # report 05, DLR UT: the null model's numbers
STATE = {3: 'r', 4: 'r', 5: 'G', 7: 'y'}                              # red, red-yellow, green, yellow


def load_tracks():
    d = np.load(f'{CACHE}/ut_veh.npz')
    m = (d['t'] >= BEGIN - 60) & (d['t'] <= END + 60)
    df = pd.DataFrame({k: d[k][m] for k in ('id', 't', 'x', 'y', 'vx', 'vy', 'v', 'L', 'truck')})
    return df.sort_values(['id', 't']).reset_index(drop=True)


def centreline(df):
    """Straight-on users of the approach: through the stop-line point, inbound, leaving within 25 degrees."""
    users = []
    for vid, g in df.groupby('id'):
        dd = np.hypot(g.x.values - STOP[0], g.y.values - STOP[1]); k = int(np.argmin(dd))
        if dd[k] > 2.2 or k < 2 or k > len(g) - 3:
            continue
        x, y = g.x.values, g.y.values
        if np.dot([x[k + 2] - x[k - 2], y[k + 2] - y[k - 2]], CENTRE - STOP) <= 0:
            continue
        h0 = np.arctan2(y[k] - y[max(k - 10, 0)], x[k] - x[max(k - 10, 0)]); h1 = np.arctan2(y[-1] - y[k], x[-1] - x[k])
        turn = (np.degrees(h1 - h0) + 180) % 360 - 180
        users.append((vid, turn))
    users = pd.DataFrame(users, columns=['id', 'turn'])
    straight = users[users.turn.abs() < 25].id.values
    pts = df[df.id.isin(straight)]
    # Axis through the stop line along the median heading, then the median lateral offset per 2 m.
    hd = np.array([np.median(pts.vx), np.median(pts.vy)]); hd /= np.linalg.norm(hd); nv = np.array([-hd[1], hd[0]])
    a = (pts.x - STOP[0]) * hd[0] + (pts.y - STOP[1]) * hd[1]; b = (pts.x - STOP[0]) * nv[0] + (pts.y - STOP[1]) * nv[1]
    bins = np.arange(np.floor(a.min() / 2) * 2, a.max() + 2, 2.0)
    k = np.digitize(a, bins); med = pd.Series(b.values).groupby(k).median(); cnt = pd.Series(b.values).groupby(k).size()
    med = med[cnt >= 30]
    along = bins[med.index.values - 1] + 1.0
    lat = med.values
    lat = np.convolve(np.pad(lat, 2, mode='edge'), np.ones(5) / 5, mode='valid')
    P = STOP + along[:, None] * hd + lat[:, None] * nv
    return P, users, straight


def build():
    os.makedirs(D, exist_ok=True)
    df = load_tracks()
    P, users, straight = centreline(df)
    poly = Polyline(P)
    s_stop = float(poly.project([STOP[0]], [STOP[1]])[0][0])
    i_stop = int(np.searchsorted(poly.cum, s_stop))
    Pin = np.vstack([P[:i_stop], np.array(poly.point(s_stop)).reshape(1, 2)])
    Pout = np.vstack([np.array(poly.point(s_stop)).reshape(1, 2), P[i_stop:]])
    with open(f'{D}/plain.nod.xml', 'w') as f:
        f.write(f'<nodes>\n  <node id="A" x="{Pin[0,0]:.3f}" y="{Pin[0,1]:.3f}"/>\n  <node id="J" x="{Pin[-1,0]:.3f}" y="{Pin[-1,1]:.3f}" type="traffic_light" tl="sg6"/>\n'
                f'  <node id="B" x="{Pout[-1,0]:.3f}" y="{Pout[-1,1]:.3f}"/>\n</nodes>\n')
    with open(f'{D}/plain.edg.xml', 'w') as f:
        f.write(f'<edges>\n  <edge id="in" from="A" to="J" numLanes="1" speed="13.89" spreadType="center" shape="{fmt_shape(Pin)}"/>\n'
                f'  <edge id="out" from="J" to="B" numLanes="1" speed="13.89" spreadType="center" shape="{fmt_shape(Pout)}"/>\n</edges>\n')
    netconvert(f'{D}/plain', f'{D}/net.xml', ['--junctions.corner-detail', '0', '--default.junctions.radius', '0'])
    LS = lane_shapes(f'{D}/net.xml')
    pin, pout = Polyline(LS['in_0']['shape'], LS['in_0']['length']), Polyline(LS['out_0']['shape'], LS['out_0']['length'])
    len_in = LS['in_0']['length']

    # Recorded controller states of signal group 6 as one long fixed program, from BEGIN on.
    tl = np.load(f'{CACHE}/ut_tl.npz'); m = tl['id'] == SG
    t, st = tl['t'][m], tl['state'][m]; o = np.argsort(t); t, st = t[o], st[o]
    ch = np.r_[0, np.where(np.diff(st) != 0)[0] + 1]
    ts, ss = t[ch], st[ch]
    k0 = np.searchsorted(ts, BEGIN, side='right') - 1
    phases = []
    cur_t, cur_s = BEGIN, ss[k0]
    for k in range(k0 + 1, len(ts)):
        if ts[k] > END + 200:
            break
        phases.append((round(ts[k] - cur_t, 3), STATE[int(cur_s)])); cur_t, cur_s = ts[k], ss[k]
    phases.append((600.0, STATE[int(cur_s)]))
    with open(f'{D}/tls.add.xml', 'w') as f:
        f.write('<additional>\n  <tlLogic id="sg6" type="static" programID="recorded" offset="0">\n')
        for dur, s in phases:
            if dur > 0:
                f.write(f'    <phase duration="{dur}" state="{s}"/>\n')
        f.write('  </tlLogic>\n</additional>\n')
    greens = [(float(ts[k]), float(ts[k + 1])) for k in range(len(ts) - 1) if ss[k] == 5 and BEGIN <= ts[k] <= END]

    # Map matching: a sample is on the lane when within LAT of it and heading along it.
    df['s_in'], df['lat_in'] = pin.project(df.x.values, df.y.values)
    df['s_out'], df['lat_out'] = pout.project(df.x.values, df.y.values)
    tan = np.diff(P, axis=0); tan = tan / np.linalg.norm(tan, axis=1)[:, None]
    head_ok = (df.vx * np.median(tan[:, 0]) + df.vy * np.median(tan[:, 1])) > 0.5 * np.maximum(df.v, 0.1)
    stopped = df.v < 0.5
    on_in = (df.lat_in.abs() < LAT) & (df.s_in > 0.5) & (df.s_in < len_in - 0.05) & (head_ok | stopped)
    on_out = (df.lat_out.abs() < LAT) & (df.s_out > 0.05) & (df.s_out < LS['out_0']['length'] - 0.5) & (head_ok | stopped) & ~on_in
    df['lane'] = np.where(on_in, 'in_0', np.where(on_out, 'out_0', ''))
    df['pos'] = np.where(on_in, df.s_in, df.s_out) + df.L / 2         # front, as the simulator keeps it
    df['lat'] = np.where(on_in, df.lat_in, df.lat_out)
    df = df[df.lane != ''].copy()
    df['ti'] = np.round(df.t * 5).astype(int)                         # 5 Hz
    simset = set(int(v) for v in straight)

    tracks_all, tracks_mix, trips_all, trips_mix, recs = [], [], [], [], []
    started, dropped = set(), 0
    for vid, g in df.groupby('id'):
        g = g[(g.t >= BEGIN) & (g.t <= END)]
        if len(g) < 3:
            continue
        # contiguous on-lane pieces at 5 Hz that never go backwards from out to in
        brk = (np.diff(g.ti.values, prepend=g.ti.values[0] - 1) != 1) | ((g.lane.values == 'in_0') & (np.r_[False, g.lane.values[:-1] == 'out_0']))
        for p, gp in g.groupby(np.cumsum(brk)):
            if len(gp) < 3:
                continue
            tid = f'{vid}_{p}'
            li = [0 if l == 'in_0' else 1 for l in gp.lane]
            pos = np.where(np.array(li) == 1, gp.pos.values - 0.0, gp.pos.values)
            # A front past the end of 'in' belongs on 'out'.
            over = (np.array(li) == 0) & (pos > len_in)
            pos = np.where(over, pos - len_in, pos); li = np.where(over, 1, li)
            t0 = gp.ti.values[0] / 5
            e0 = 'in' if li[0] == 0 else 'out'; e1 = 'out' if li.max() == 1 else 'in'
            L = float(np.clip(np.median(gp.L), 2.5, 18.0))
            simulated = vid in simset and e0 == 'in' and vid not in started
            row = (t0, tid, li[0], float(pos[0]), float(max(gp.v.values[0], 0)), e0, e1, L)
            tracks_all.append((tid, t0, 0.2, INF, li, pos, gp.v.values))
            trips_all.append(row + ('rep',))
            if simulated:
                started.add(vid)
                trips_mix.append((t0, tid, li[0], float(pos[0]), float(max(gp.v.values[0], 0)), e0, 'out', L, 'drv'))
            elif vid in simset:
                dropped += 1          # a later piece of a car the driver already has
            else:
                tracks_mix.append((tid, t0, 0.2, INF, li, pos, gp.v.values)); trips_mix.append(row + ('rep',))
            recs.append(pd.DataFrame(dict(trip=tid, id=vid, ti=gp.ti.values, lane=np.where(li == 0, 'in_0', 'out_0'), pos=pos, v=gp.v.values,
                                          lat=gp.lat.values, x=gp.x.values, y=gp.y.values, L=L, sim=simulated, user=vid in simset)))
    pd.concat(recs).to_csv(f'{D}/matched.csv.gz', index=False)
    lanes = ['in_0', 'out_0']
    write_rpl(f'{D}/all.rpl', lanes, tracks_all)
    write_rpl(f'{D}/mix.rpl', lanes, tracks_mix)
    for name, trips in (('all', trips_all), ('mix', trips_mix)):
        lens = sorted({round(r[7], 1) for r in trips if r[8] == 'rep'})
        with open(f'{D}/routes_{name}.xml', 'w') as f:
            f.write('<routes>\n  <vType id="drv" carFollowModel="Krauss"/>\n')
            for Lr in lens:
                f.write(f'  <vType id="rep{Lr}" length="{Lr}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
            for t0, tid, ln, pos, v, e0, e1, Lr, kind in sorted(trips):
                vt = 'drv' if kind == 'drv' else f'rep{round(Lr, 1)}'
                route = e0 if e0 == e1 else f'{e0} {e1}'
                f.write(f'  <vehicle id="{tid}" type="{vt}" depart="{t0:.1f}" departLane="0" departPos="{min(pos, 1e4):.3f}" departSpeed="{v:.3f}"><route edges="{route}"/></vehicle>\n')
            f.write('</routes>\n')
    meta = dict(begin=BEGIN, end=END, score_from=SCORE_FROM, len_in=len_in, len_out=LS['out_0']['length'],
                users_of_sg6=int(len(users)), straight=int(len(straight)), turning_replayed=int((users.turn.abs() >= 25).sum()),
                later_pieces_of_simulated_dropped=dropped, trips_all=len(trips_all), simulated=int(sum(1 for r in trips_mix if r[8] == 'drv')), greens=greens,
                lateral_abs_m=dict(p50=float(df.lat.abs().median()), p95=float(df.lat.abs().quantile(.95))))
    json.dump(meta, open(f'{D}/scene.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != 'greens'}), 'greens', len(greens))


def cars_args(name, rpl, fcd, seed=0, every=0.1):
    return ['--net', f'{D}/net.xml', '--additional', f'{D}/tls.add.xml', '--routes', f'{D}/routes_{name}.xml', '--replay', f'{D}/{rpl}',
            '--dt', '0.1', '--begin', BEGIN, '--end', END, '--seed', seed, '--time-to-teleport', '0', '--static-tls',
            '--fcd', fcd, '--fcd-interval', every]


def f100():
    log = run_cars(cars_args('all', 'all.rpl', f'{D}/f100.fcd.csv'), log=f'{D}/f100.log')
    print([l for l in log.splitlines() if 'replay' in l])
    m = pd.read_csv(f'{D}/matched.csv.gz')
    f = pd.read_csv(f'{D}/f100.fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed'])
    f['t10'] = np.round(f.time * 10).astype(int); m['t10'] = m.ti * 2
    j = m.merge(f, on=['trip', 't10'], how='left', suffixes=('', '_sim'))
    k = j[j.pos_sim.notna()]
    L = lane_shapes(f'{D}/net.xml'); poly = {l: Polyline(v['shape'], v['length']) for l, v in L.items() if l in ('in_0', 'out_0')}
    x = np.zeros(len(k)); y = np.zeros(len(k))
    for l, g in k.groupby('lane_sim'):
        px, py = poly[l].point(g.pos_sim.values - g.L.values / 2); ix = k.index.get_indexer(g.index); x[ix] = px; y[ix] = py
    q = lambda v: {f'p{p}': round(float(np.percentile(v, p)), 4) for p in (50, 90, 99, 100)}
    miss = j[j.pos_sim.isna()]
    res = dict(samples=len(j), in_output=int(len(k)), missing_last_key_of_piece=int((miss.ti == miss.groupby('trip').ti.transform('max')).sum()), lane_mismatch=float((k.lane_sim != k.lane).mean()),
               harness_pos_abs_m=q((k.pos_sim - k.pos).abs()), harness_speed_abs=q((k.speed - k.v).abs()),
               map_2d_m=q(np.hypot(x - k.x, y - k.y)), map_lateral_abs_m=q(k.lat.abs()))
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/f100_dlrut_sg6.json'), 'w'), indent=1)


def f104(seeds):
    for sd in seeds:
        log = run_cars(cars_args('mix', 'mix.rpl', f'{D}/mix_s{sd}.fcd.csv', sd, 0.2), log=f'{D}/mix_s{sd}.log')
        print(sd, [l for l in log.splitlines() if l.startswith('replay') or 'collisions' in l][:3])


def crossings_rec(m, len_in):
    """Time the front crossed the stop line, per trip, interpolated from 5 Hz."""
    out = {}
    for tid, g in m.groupby('trip'):
        z = np.where(g.lane.values == 'in_0', g.pos.values - len_in, g.pos.values)
        tt = g.ti.values / 5
        k = np.where((z[:-1] < 0) & (z[1:] >= 0))[0]
        if len(k):
            a = k[0]; out[tid] = tt[a] + (0 - z[a]) / max(z[a + 1] - z[a], 1e-6) * (tt[a + 1] - tt[a])
    return out


def crossings_sim(f, len_in):
    out = {}
    f = f.sort_values(['trip', 'time'])
    for tid, g in f.groupby('trip'):
        z = np.where(g.lane.values == 'in_0', g.pos.values - len_in, g.pos.values)
        k = np.where((z[:-1] < 0) & (z[1:] >= 0))[0]
        if len(k):
            a = k[0]; tt = g.time.values; out[tid] = tt[a] + (0 - z[a]) / max(z[a + 1] - z[a], 1e-6) * (tt[a + 1] - tt[a])
    return out


def point_queue(entries, greens, len_in, v_free):
    """Null model: each simulated car reaches the line at free speed; a queue discharges at H_SAT after LOST."""
    out = {}; prev = -1e9
    for tid, t0, pos0 in sorted(entries, key=lambda r: r[1] + (len_in - r[2]) / v_free):
        ta = t0 + max(len_in - pos0, 0) / v_free
        d = max(ta, prev + H_SAT)
        for g0, g1 in greens:
            if g1 + 3.0 <= d:
                continue
            start = g0 + LOST + H_SAT if prev < g0 else -1e9      # first of a queue that stood through red
            cand = max(d, start if ta < g0 + LOST + H_SAT else d)
            if cand < g1 + 3.0:
                d = cand; break
        out[tid] = d; prev = d
    return out


def score():
    meta = json.load(open(f'{D}/scene.json')); len_in = meta['len_in']; greens = meta['greens']
    m = pd.read_csv(f'{D}/matched.csv.gz')
    sim_m = m[m.sim]
    ent = sim_m.sort_values('ti').groupby('trip').first()
    trip_of = dict(zip(ent.id, ent.index))
    users = m[m.user].copy(); users['trip'] = users.id.map(trip_of)
    rec = crossings_rec(users.dropna(subset=['trip']).sort_values(['trip', 'ti']), len_in)
    # Free speed: median speed 40-60 m before the line of cars with no car within 50 m ahead, while green.
    v_free = float(np.median(sim_m[(sim_m.lane == 'in_0') & (sim_m.pos > len_in - 60) & (sim_m.pos < len_in - 40) & (sim_m.v > 5)].v))
    null = point_queue([(tid, r.ti / 5, r.pos) for tid, r in ent.iterrows()], greens, len_in, v_free)
    res = dict(v_free=v_free, runs={})
    # Saturated cycles: report 05's queue table, queues of 4 or more at green onset on this signal group.
    R = np.load(f'{CACHE}/ut_queue.npz')['R']; R = R[(R[:, 0] == SG) & (R[:, 2] >= SCORE_FROM) & (R[:, 2] <= END - 120)]
    sat = [g for g in np.unique(R[:, 2]) if R[R[:, 2] == g, 3].max() >= 4]
    gmap = {round(g0): (g0, g1) for g0, g1 in greens}
    sat_g = [min(greens, key=lambda gg: abs(gg[0] - g)) for g in sat]

    def per_cycle(cross):
        return np.array([sum(1 for t in cross.values() if g0 <= t < g1 + 3.0) for g0, g1 in sat_g])

    rc = per_cycle(rec); nc = per_cycle(null)
    def cmp(cross):
        ids = [t for t in rec if t in cross and rec[t] >= SCORE_FROM]
        e = np.array([cross[t] - rec[t] for t in ids]); tt = np.array([rec[t] for t in ids])
        bins = {}
        for b0 in np.arange(SCORE_FROM, END, 1800):
            k = (tt >= b0) & (tt < b0 + 1800)
            if k.any():
                bins[f'{int(b0 // 3600):02d}:{int(b0 % 3600 // 60):02d}'] = round(float(np.mean(np.abs(e[k]))), 2)
        return dict(n=len(ids), crossing_mae_s=float(np.mean(np.abs(e))), crossing_bias_s=float(np.mean(e)), mae_by_half_hour=bins)
    res['null_point_queue'] = dict(**cmp(null), discharge_per_sat_cycle_mae=float(np.mean(np.abs(nc - rc))), discharge_bias=float(np.mean(nc - rc)))
    res['recorded'] = dict(saturated_cycles=len(sat_g), discharge_mean=float(rc.mean()), vehicles_simulated=int(len(ent)), crossing_recorded=len(rec))
    for p in sorted(glob.glob(f'{D}/mix_s*.fcd.csv')):
        f = pd.read_csv(p, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'depart_step'])
        sim_ids = set(ent.index)
        fs = f[f.trip.isin(sim_ids)]
        cross = crossings_sim(fs, len_in)
        sc = per_cycle(cross)
        first = fs.groupby('trip').time.min()
        delay = np.array([first[t] - ent.loc[t].ti / 5 for t in first.index])
        # overlaps of a simulated car with a replayed one on the same lane: a harness artefact, counted
        fr = f[~f.trip.isin(sim_ids)]
        res['runs'][os.path.basename(p)] = dict(**cmp(cross), discharge_per_sat_cycle_mae=float(np.mean(np.abs(sc - rc))), discharge_bias=float(np.mean(sc - rc)),
                                                never_entered=int(len(sim_ids - set(first.index))), entry_delay_s=dict(p50=float(np.median(delay)), p95=float(np.percentile(delay, 95)), max=float(delay.max())),
                                                replayed_vehicle_samples=int(len(fr)))
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/f104_dlrut_sg6.json'), 'w'), indent=1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'build':
        build()
    elif c == 'f100':
        f100()
    elif c == 'f104':
        a, b = sys.argv[2].split('..'); f104(range(int(a), int(b) + 1))
    elif c == 'score':
        score()
