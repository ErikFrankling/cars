"""SinD Tianjin, one signalised approach (approach 2, straight on): F512-F514, F120 as far as the data allows.

SinD has tracks and light states but no map. The approach is built from the tracks: the axis is the approach's entry
direction (scripts/measure/sind.py), the stop line is where queue heads stand (signals.stop_line), the centreline the
median lateral of straight-going cars per 2 m, lanes the peaks of motor-vehicle density across it. 'in' ends at the
stop line, 'out' carries on straight to where the recording loses the cars. The light that governs the approach is the
one whose green onsets the standing cars start after (as sind.py and signals.py pick it); its logged states are one
fixed program.

Every car (car, truck, bus) going straight from this approach is simulated from where the recording first sees it on
'in'. Everyone else on the corridor is replayed with lateral keys: turning cars until they turn off, motorcycles,
bicycles and tricycles while they are over a car lane. Off-lane two-wheelers (kerb side) are left out and counted.

    python3 -I scripts/replay/sind_approach.py build
    python3 -I scripts/replay/sind_approach.py f100          # all replayed
    python3 -I scripts/replay/sind_approach.py run 0..4
    python3 -I scripts/replay/sind_approach.py score
"""
import os, sys, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, 'scripts', 'measure'))
from rpl import *
import signals as SG
import sind as SM
from holdout import HOLD
import numpy as np, pandas as pd

CITY, APP = 'Tianjin', 2
D = os.path.join(OUT, f'sind-{CITY.lower()}-app{APP}')
DT = 0.25
KEY_DT = 0.1
CODE = {1: 'G', 3: 'y', 0: 'r'}
TWO = {'motorcycle', 'bicycle', 'tricycle'}


def load():
    assert CITY not in HOLD['sind']
    tp, lp = SG.SIND_REC[CITY]
    t = pd.read_csv(SG.SIND + tp, usecols=['track_id', 'timestamp_ms', 'agent_type', 'x', 'y', 'vx', 'vy', 'length', 'width', 'heading_rad'])
    t['t'] = t.timestamp_ms / 1000.0; t['v'] = np.hypot(t.vx, t.vy)
    t = t.sort_values(['track_id', 't']).reset_index(drop=True)
    motor = t[t.agent_type.isin(SM.MOTOR)]
    T = SM.describe_tracks(motor)
    lab, Cc = SM.approaches(T)
    rows = []
    for i, g in t.groupby('track_id'):
        mv = g[g.v > 1.0]
        if len(mv) < 10:
            continue
        h0 = np.arctan2(mv.vy.iloc[:10].mean(), mv.vx.iloc[:10].mean()); h1 = np.arctan2(mv.vy.iloc[-10:].mean(), mv.vx.iloc[-10:].mean())
        turn = np.rad2deg(np.angle(np.exp(1j * (h1 - h0))))
        rows.append((i, int(np.argmax(np.array([np.cos(h0), np.sin(h0)]) @ Cc.T)), 'left' if turn > 45 else 'right' if turn < -45 else 'straight'))
    A = pd.DataFrame(rows, columns=['id', 'app', 'mv']).set_index('id')
    t = t[t.track_id.isin(A.index)].copy()
    t['app'] = A.app.reindex(t.track_id).values; t['mv'] = A.mv.reindex(t.track_id).values
    L = pd.read_csv(SG.SIND + lp)
    return t, Cc, L


def build():
    os.makedirs(D, exist_ok=True)
    t, Cc, Lg = load()
    u = Cc[APP]; n = np.array([-u[1], u[0]])
    t['a'] = t.x * u[0] + t.y * u[1]; t['lat'] = t.x * n[0] + t.y * n[1]
    straight = t[(t.app == APP) & (t.mv == 'straight') & t.agent_type.isin(SM.MOTOR)]
    # Stop line: the 95th percentile of first-in-queue stops (sind.py), then moved to where queue heads stand.
    stops = []
    for i, gg in t[(t.app == APP) & t.agent_type.isin(SM.MOTOR)].groupby('track_id'):
        st = gg.v.to_numpy() < 0.5
        if st.sum() >= 20:
            stops.append(float((gg.a + gg.length / 2).to_numpy()[st].max()))
    s95 = float(np.percentile(stops, 95))
    veh = [dict(t=g.t.to_numpy(), s=(g.a + g.length / 2).to_numpy() - s95, v=g.v.to_numpy(), lat=g.lat.to_numpy(),
                kind='car' if g.agent_type.iloc[0] in SM.MOTOR else 'two', id=int(i)) for i, g in t[(t.app == APP) & (t.mv == 'straight')].groupby('track_id')]
    C, S = SG.events(veh)
    shift, nheads = SG.stop_line(S)
    a0 = s95 - shift                                   # road coordinate of the stop line
    t['a'] = t.a - a0
    straight = t[(t.app == APP) & (t.mv == 'straight') & t.agent_type.isin(SM.MOTOR)]
    # Centreline: median lateral of straight cars per 2 m, smoothed.
    bins = np.arange(-120, 120, 2.0)
    k = np.digitize(straight.a, bins)
    med = straight.groupby(k).lat.median(); cnt = straight.groupby(k).size(); med = med[cnt >= 30]
    ac = bins[med.index.values - 1] + 1.0
    lc = np.convolve(np.pad(med.values, 2, mode='edge'), np.ones(5) / 5, mode='valid')
    centre = lambda a: np.interp(a, ac, lc)
    a_min = float(np.percentile(straight.groupby('track_id').a.min(), 10)); a_min = max(a_min, ac[0])
    a_max = float(min(np.percentile(straight.groupby('track_id').a.max(), 50), ac[-1]))
    t['lr'] = t.lat - centre(t.a)
    mot = t[(t.app == APP) & t.agent_type.isin(SM.MOTOR)]
    straight = mot[mot.mv == 'straight']
    lanes_in = np.array(SG_peaks(mot[(mot.a > -45) & (mot.a < -3)].lr))
    lanes_out = np.array(SG_peaks(straight[(straight.a > 10) & (straight.a < a_max - 5)].lr))
    w_in = float(np.median(np.diff(lanes_in))) if len(lanes_in) > 1 else 3.2
    w_out = float(np.median(np.diff(lanes_out))) if len(lanes_out) > 1 else 3.2
    P = lambda a, l: (a + a0) * u + l * n
    with open(f'{D}/plain.nod.xml', 'w') as f:
        for nm, a in (('A', a_min), ('J', 0.0), ('B', a_max)):
            p = P(a, centre(a))
            extra = ' type="traffic_light" tl="J"' if nm == 'J' else ''
            f.write(('<nodes>\n' if nm == 'A' else '') + f'  <node id="{nm}" x="{p[0]:.3f}" y="{p[1]:.3f}"{extra}/>\n')
        f.write('</nodes>\n')
    def edge(eid, fr, to, a0_, a1_, lanes, w):
        aa = np.linspace(a0_, a1_, max(int((a1_ - a0_) / 2), 2))
        s = f'  <edge id="{eid}" from="{fr}" to="{to}" numLanes="{len(lanes)}" speed="13.89" spreadType="center" shape="{fmt_shape([P(a, centre(a)) for a in aa])}">\n'
        for i, l in enumerate(lanes):
            s += f'    <lane index="{i}" width="{w:.2f}" shape="{fmt_shape([P(a, centre(a) + l) for a in aa])}"/>\n'
        return s + '  </edge>\n'
    with open(f'{D}/plain.edg.xml', 'w') as f:
        f.write('<edges>\n' + edge('in', 'A', 'J', a_min, 0.0, lanes_in, w_in) + edge('out', 'J', 'B', 0.0, a_max, lanes_out, w_out) + '</edges>\n')
    netconvert(f'{D}/plain', f'{D}/net.xml', ['--default.junctions.radius', '0', '--junctions.corner-detail', '0'])
    LS = lane_shapes(f'{D}/net.xml')
    import xml.etree.ElementTree as ET
    nlinks = max(int(c.get('linkIndex')) for c in ET.parse(f'{D}/net.xml').getroot().iter('connection') if c.get('tl') == 'J') + 1
    len_in = LS['in_0']['length']
    # Signals: the light whose green onsets the standing cars of this approach start after.
    cols = [c for c in Lg.columns if 'light' in c.lower() and 'pedestrian' not in c.lower()]
    ts = Lg['timestamp(ms)'].to_numpy(float) / 1000
    groups = SG.sind_groups(CITY)
    light = groups[f'{CITY} app{APP} straight']['light']
    st = Lg[light].to_numpy()
    BEGIN, END = 0.0, float(np.ceil(t.t.max()))
    k0 = np.searchsorted(ts, BEGIN, side='right') - 1
    phases, cur_t, cur_s = [], BEGIN, st[k0]
    for k in range(k0 + 1, len(ts)):
        tk = round(float(ts[k]) / DT) * DT
        phases.append((round(tk - cur_t, 3), CODE[int(cur_s)])); cur_t, cur_s = tk, st[k]
    phases.append((600.0, CODE[int(cur_s)]))
    with open(f'{D}/tls.add.xml', 'w') as f:
        f.write(f'<additional>\n  <tlLogic id="J" type="static" programID="recorded" offset="{BEGIN}">\n')
        for dur, s in phases:
            if dur > 0:
                f.write(f'    <phase duration="{dur}" state="{s * nlinks}"/>\n')
        f.write('  </tlLogic>\n</additional>\n')
    greens = SG.truth_cycles(ts, st == 1, -1e9, 1e9)
    # Map matching onto the corridor.
    t['af'] = t.a + t.length / 2
    hd_ok = (np.cos(t.heading_rad - np.arctan2(u[1], u[0])) > np.cos(np.deg2rad(40))) | (t.v < 0.5)
    on_in = (t.af >= a_min + 0.5) & (t.af < len_in + a_min - 0.05) & (t.af < 0)
    on_out = (t.af >= 0.05) & (t.af < a_max - 0.5)
    lane_lat = {'in': lanes_in, 'out': lanes_out}
    t['edge'] = np.where(on_in, 'in', np.where(on_out, 'out', ''))
    t = t[hd_ok & (t.edge != '')].copy()
    li = np.zeros(len(t), int); dl = np.zeros(len(t))
    for e in ('in', 'out'):
        m = (t.edge == e).to_numpy()
        d_ = t.lr.to_numpy()[m][:, None] - lane_lat[e][None, :]
        j = np.argmin(np.abs(d_), 1); li[m] = j; dl[m] = d_[np.arange(len(j)), j]
    t['li'] = li; t['lat_left'] = dl
    w_of = np.where(t.edge == 'in', w_in, w_out)
    two = t.agent_type.isin(TWO).to_numpy()
    over_lane = np.abs(dl) < 0.5 * w_of + 0.3
    off_lane = int((~over_lane & two).sum()); off_lane_cars = int((~over_lane & ~two).sum())
    t = t[over_lane].copy()
    t['pos'] = np.where(t.edge == 'in', t.af - a_min, t.af)
    t['lane'] = t.edge + '_' + t.li.astype(str)
    t['ti'] = np.round(t.t / KEY_DT).astype(int)
    tracks_all, tracks_mix, trips_all, trips_mix, recs = [], [], [], [], []
    lanes = sorted(LS)
    lidx = {l: i for i, l in enumerate(lanes)}
    simulated, dropped_pieces = set(), 0
    for vid, g in t.groupby('track_id'):
        brk = (np.diff(g.ti.values, prepend=g.ti.values[0] - 1) != 1) | ((g.edge.values == 'in') & np.r_[False, g.edge.values[:-1] == 'out'])
        pieces = list(g.groupby(np.cumsum(brk)))
        for p, gp in pieces[:1]:
            if len(gp) < 3:
                continue
            tid = f'{vid}_{p}'
            e0 = gp.edge.iloc[0]; e1 = gp.edge.iloc[-1]
            route = e0 if e0 == e1 else 'in out'
            Lr = float(np.clip(gp.length.median(), 1.2, 18.0))
            ty = gp.agent_type.iloc[0]
            t0 = gp.ti.values[0] * KEY_DT
            key = (tid, t0, KEY_DT, INF, [lidx[l] for l in gp.lane], gp.pos.values, gp.v.values, gp.lat_left.values)
            row = dict(t0=t0, tid=tid, lane=int(gp.li.iloc[0]), pos=float(gp.pos.iloc[0]), v=float(max(gp.v.iloc[0], 0)), route=route, L=round(Lr, 1), cls=ty)
            tracks_all.append(key); trips_all.append(dict(row, kind='rep'))
            sim = ty in SM.MOTOR and gp.mv.iloc[0] == 'straight' and gp.app.iloc[0] == APP and e0 == 'in'
            if sim:
                simulated.add(tid); trips_mix.append(dict(row, kind='drv', route='in out'))
            else:
                tracks_mix.append(key); trips_mix.append(dict(row, kind='rep'))
            recs.append(pd.DataFrame(dict(trip=tid, id=vid, ti=gp.ti.values, lane=gp.lane.values, pos=gp.pos.values, v=gp.v.values, lat_left=gp.lat_left.values,
                                          x=gp.x.values, y=gp.y.values, heading=gp.heading_rad.values, L=Lr, cls=ty, sim=sim)))
        dropped_pieces += max(len(pieces) - 1, 0)
    pd.concat(recs).to_csv(f'{D}/matched.csv.gz', index=False)
    write_rpl(f'{D}/all.rpl', lanes, tracks_all)
    write_rpl(f'{D}/mix.rpl', lanes, tracks_mix)
    # The same without two- and three-wheelers, to size their effect (PLAN, motorcycles)
    keep = {r['tid'] for r in trips_mix if r['cls'] not in TWO}
    write_rpl(f'{D}/mix_no2w.rpl', lanes, [k for k in tracks_mix if k[0] in keep])
    for name, trips in (('all', trips_all), ('mix', trips_mix), ('mix_no2w', [r for r in trips_mix if r['tid'] in keep])):
        with open(f'{D}/routes_{name}.xml', 'w') as f:
            f.write('<routes>\n  <vType id="drv" carFollowModel="Krauss"/>\n')
            for L_ in sorted({r['L'] for r in trips if r['kind'] == 'rep'}):
                f.write(f'  <vType id="rep{L_}" length="{L_}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
            for r in sorted(trips, key=lambda r: (r['t0'], r['tid'])):
                vt = 'drv' if r['kind'] == 'drv' else f'rep{r["L"]}'
                f.write(f'  <vehicle id="{r["tid"]}" type="{vt}" depart="{r["t0"]:.2f}" departLane="{r["lane"]}" departPos="{r["pos"]:.3f}" departSpeed="{r["v"]:.3f}"><route edges="{r["route"]}"/></vehicle>\n')
            f.write('</routes>\n')
    meta = dict(city=CITY, approach=APP, light=light, begin=BEGIN, end=END, stop_line_moved_m=round(shift, 2), stop_line_heads=nheads,
                a_min=a_min, a_max=a_max, len_in=len_in, lanes_in=lanes_in.round(2).tolist(), lanes_out=lanes_out.round(2).tolist(), width_in=w_in, width_out=w_out,
                simulated=len(simulated), replayed=len(tracks_mix), by_class={c: int(sum(1 for r in trips_all if r['cls'] == c)) for c in sorted({r['cls'] for r in trips_all})},
                later_pieces_dropped=dropped_pieces, off_lane_samples_two_wheelers=off_lane, off_lane_samples_cars=off_lane_cars, greens=greens, n_links=nlinks,
                lateral_abs_m=dict(p50=round(float(t.lat_left.abs().median()), 3), p90=round(float(t.lat_left.abs().quantile(.9)), 3)))
    json.dump(meta, open(f'{D}/scene.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != 'greens'}))


def SG_peaks(lat):
    from pneuma import peaks
    return peaks(np.asarray(lat, float), -12, 12, sep=2.4, rel=0.2)


def cars_args(name, rpl, fcd, seed=0):
    m = json.load(open(f'{D}/scene.json'))
    return ['--net', f'{D}/net.xml', '--additional', f'{D}/tls.add.xml', '--routes', f'{D}/routes_{name}.xml', '--replay', f'{D}/{rpl}',
            '--dt', DT, '--begin', m['begin'], '--end', m['end'], '--seed', seed, '--time-to-teleport', 0, '--static-tls',
            '--fcd', fcd, '--fcd-interval', DT]


def f100():
    import levelx_f100 as LF
    log = run_cars(cars_args('all', 'all.rpl', f'{D}/f100.fcd.csv'), log=f'{D}/f100.log')
    m = pd.read_csv(f'{D}/matched.csv.gz')
    f = pd.read_csv(f'{D}/f100.fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed', 'offset'])
    f['k'] = np.round(f.time / DT).astype(int)
    first = f.groupby('trip').k.transform('min') == f.k
    f = f[~first]
    m['k'] = np.round(m.ti * KEY_DT / DT).astype(int); m = m[np.abs(m.ti * KEY_DT / DT - m.k) < 1e-3]
    j = m.merge(f, on=['trip', 'k'], how='left', suffixes=('', '_sim'))
    k = j[j.pos_sim.notna()].copy()
    LS = lane_shapes(f'{D}/net.xml'); poly = {l: Polyline(v['shape'], v['length']) for l, v in LS.items()}
    x = np.zeros(len(k)); y = np.zeros(len(k))
    for l, g in k.groupby('lane_sim'):
        ix = k.index.get_indexer(g.index); x[ix], y[ix] = LF.centre_xy(poly[l], g.pos_sim.values, g.offset.values)
    fx = k.x + 0.5 * k.L * np.cos(k.heading); fy = k.y + 0.5 * k.L * np.sin(k.heading)
    q = lambda v: {f'p{p}': round(float(np.percentile(v, p)), 4) for p in (50, 90, 99, 100)}
    same = k.lane_sim == k.lane
    res = dict(log=[l for l in log.splitlines() if l.startswith('replay')], samples=len(j), in_output=len(k), lane_mismatch=round(float((~same).mean()), 5),
               harness_pos_abs_m=q((k.pos_sim - k.pos).abs()[same]), harness_lat_abs_m=q((k.offset - k.lat_left).abs()[same]), front_2d_m=q(np.hypot(x - fx, y - fy)))
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/f100_sind_tianjin_app2.json'), 'w'), indent=1)


def run(seeds, gpu=False, name='mix'):
    for sd in seeds:
        log = run_cars(cars_args(name, f'{name}.rpl', f'{D}/{name}_s{sd}.fcd.csv', sd), gpu=gpu, log=f'{D}/{name}_s{sd}.log')
        print(sd, [l for l in log.splitlines() if l.startswith('replay') or 'collision' in l.lower()][:3], flush=True)


def crossings(df, len_in, tcol, poscol, lanecol):
    out = {}
    for tid, g in df.sort_values([ 'trip', tcol]).groupby('trip'):
        z = np.where(g[lanecol].str.startswith('in'), g[poscol].values - len_in, g[poscol].values)
        tt = g[tcol].values
        k = np.flatnonzero((z[:-1] < 0) & (z[1:] >= 0))
        if len(k):
            a = k[0]; out[tid] = tt[a] + (0 - z[a]) / max(z[a + 1] - z[a], 1e-6) * (tt[a + 1] - tt[a])
    return out


def other_approach_discharge():
    """Saturation headway and lost time from Tianjin's other straight approaches, with their recorded lights:
    queued cars (standing before the line at green) per lane, crossing times."""
    ev = pd.read_pickle(f'{SG.OUT}/sind_events.pkl')
    hw, first = [], []
    for g, d in ev.items():
        if not g.startswith(CITY) or g == f'{CITY} app{APP} straight' or 'straight' not in g:
            continue
        S, C = d['S'], d['C']
        for g0, g1 in SG.truth_cycles(d['truth_t'], d['truth_green'], *d['t_range']):
            q = S[(S.kind == 'car') & (S.s < 0) & ~(S.tcross < S.t0) & (S.t0 <= g0) & (S.t1 >= g0 - 0.5) & S.tcross.notna()]
            if not len(q):
                continue
            for _, lane in q.groupby(np.round(q.lat / SG.LANE_BAND)):
                tc = np.sort(lane.tcross.values)
                first.append(tc[0] - g0)
                hw += list(np.diff(tc))
    # Queues on Tianjin's other approaches are single cars per lane: too few headways for a saturation headway, so
    # it comes from SinD's clock-free measurement (positions 4 on, measure/sind.json, 2.6 s); the first car's
    # crossing after green is Tianjin's own.
    sj = json.load(open(os.path.join(REPO, 'research/truth/measure/sind.json')))
    h_sind = float(sj['clock_split']['clock_free']['saturation_pos4plus'][0])
    h = float(np.median(hw)) if len(hw) >= 10 else h_sind
    return dict(h_sat=h, h_source='Tianjin other approaches' if len(hw) >= 10 else 'SinD clock-free saturation headway (measure/sind.json)',
                first_car_crossing_after_green=float(np.median(first)), lost=float(np.median(first)) - h, n_headways=len(hw), n_queues=len(first))


def point_queue(entries, greens, len_in, v_free, h, lost):
    out = {}; prev = -1e9
    for tid, t0, pos0 in sorted(entries, key=lambda r: r[1] + (len_in - r[2]) / v_free):
        ta = t0 + max(len_in - pos0, 0) / v_free
        d = max(ta, prev + h)
        for g0, g1 in greens:
            if g1 + 3.0 <= d:
                continue
            start = g0 + lost + h if prev < g0 else -1e9
            cand = max(d, start if ta < g0 + lost + h else d)
            if cand < g1 + 3.0:
                d = cand; break
        out[tid] = d; prev = d
    return out


def score():
    meta = json.load(open(f'{D}/scene.json')); len_in = meta['len_in']; greens = meta['greens']
    m = pd.read_csv(f'{D}/matched.csv.gz')
    sm = m[m.sim].copy(); sm['t'] = sm.ti * KEY_DT
    rec = crossings(sm, len_in, 't', 'pos', 'lane')
    ent = sm.sort_values('t').groupby('trip').first()
    # free speed: entry speed of the simulated cars that come in moving (the approach in view is short)
    v_free = float(np.median(ent[ent.v > 3].v))
    dq = other_approach_discharge()
    null = point_queue([(tid, r.t, r.pos) for tid, r in ent.iterrows()], greens, len_in, v_free, dq['h_sat'], dq['lost'])
    ev = pd.read_pickle(f'{SG.OUT}/sind_events.pkl')[f'{CITY} app{APP} straight']
    S = ev['S']
    cyc = []
    for g0, g1 in greens:
        q = S[(S.kind == 'car') & (S.s < 0) & ~(S.tcross < S.t0) & (S.t0 <= g0) & (S.t1 >= g0 - 0.5)]
        cyc.append((g0, g1, len(q)))
    sat = [(g0, g1) for g0, g1, n in cyc if n >= 4]
    queued = [(g0, g1) for g0, g1, n in cyc if n >= 1]
    # only cars whose recorded track reaches the line, on both sides
    per_cycle = lambda cr, gs: np.array([sum(1 for k_, t in cr.items() if k_ in rec and g0 <= t < g1 + 3.0) for g0, g1 in gs])
    rc = per_cycle(rec, queued)
    def cmp(cr):
        ids = [t for t in rec if t in cr and rec[t] >= 20.0]
        e = np.array([cr[t] - rec[t] for t in ids])
        return dict(n=len(ids), errors=[round(float(v), 2) for v in e], crossing_mae_s=round(float(np.mean(np.abs(e))), 2), crossing_bias_s=round(float(np.mean(e)), 2),
                    discharge_queued_cycles_mae=round(float(np.mean(np.abs(per_cycle(cr, queued) - rc))), 3), discharge_bias=round(float(np.mean(per_cycle(cr, queued) - rc)), 3))
    res = dict(v_free=v_free, null_params=dq, cycles=len(cyc), saturated_cycles_4plus=len(sat), cycles_with_queue=len(queued),
               recorded=dict(simulated_cars=int(len(ent)), crossing=len(rec), discharge_mean=round(float(rc.mean()), 2)), null_point_queue=cmp(null), runs={})
    for p in sorted(glob.glob(f'{D}/mix_s*.fcd.csv')) + sorted(glob.glob(f'{D}/mix_no2w_s*.fcd.csv')):
        f = pd.read_csv(p, usecols=['time', 'trip', 'lane', 'pos', 'speed'])
        fs = f[f.trip.isin(set(ent.index))]
        cr = crossings(fs, len_in, 'time', 'pos', 'lane')
        first = fs.groupby('trip').time.min()
        delay = np.array([first[t] - ent.loc[t].t for t in first.index])
        res['runs'][os.path.basename(p)] = dict(**cmp(cr), never_entered=int(len(set(ent.index) - set(first.index))),
                                                entry_delay_s=dict(p50=round(float(np.median(delay)), 2), p95=round(float(np.percentile(delay, 95)), 2), max=round(float(delay.max()), 2)))
    for variant in ('mix_s', 'mix_no2w_s'):
        r = [v for k, v in res['runs'].items() if k.startswith(variant)]
        if not r:
            continue
        res['driver_over_seeds' + ('' if variant == 'mix_s' else '_no_two_wheelers')] = dict(crossing_mae_s=[min(x['crossing_mae_s'] for x in r), max(x['crossing_mae_s'] for x in r)],
                                        crossing_bias_s=[min(x['crossing_bias_s'] for x in r), max(x['crossing_bias_s'] for x in r)],
                                        discharge_queued_cycles_mae=[min(x['discharge_queued_cycles_mae'] for x in r), max(x['discharge_queued_cycles_mae'] for x in r)],
                                        crossing_mae_without_3_largest_s=[round(float(np.mean(np.sort(np.abs(x['errors']))[:-3])), 2) for x in r])
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/f120_sind_tianjin_app2.json'), 'w'), indent=1)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'build':
        build()
    elif c == 'f100':
        f100()
    elif c == 'run':
        a, b = sys.argv[2].split('..'); run(range(int(a), int(b) + 1), '--gpu' in sys.argv, sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else 'mix')
    elif c == 'score':
        score()
