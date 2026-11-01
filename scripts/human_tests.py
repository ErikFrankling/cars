#!/usr/bin/env python3
"""GPU scenes for the human driver: research/truth/05-real-human-driving.md section 9 and
research/truth/14-human-courtesy.md section 5. Numbers come from those reports.

    python3 scripts/human_tests.py ring queue ... [--out DIR] [--dt 0.5] [--seeds 3]

Every run holds /tmp/cars-gpu.lock. Results are written to DIR/results.json as well as printed.
"""
import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A = None
RESULTS = {}


def run(cmd):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout[-2000:]}\n{r.stderr[-4000:]}")
    return r


def cars(d, *args, routes='r.xml', net='net.xml', tag='run', fcd=True, interval=None):
    report = d / f'{tag}.json'
    fc = d / f'{tag}.fcd.csv'
    extra = ['--fcd', fc, '--fcd-interval', interval or A.interval] if fcd else []
    log = run(['flock', '/tmp/cars-gpu.lock', os.environ.get('CARS_BIN', ROOT / 'target/release/cars'), 'run', '--net', d / net, '--routes', d / routes, '--report-json', report, *extra, *args])
    (d / f'{tag}.log').write_text(log.stdout + log.stderr)
    return json.loads(report.read_text()), fc


def workdir(name):
    d = Path(A.out) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def netconvert(d, nodes, edges, *extra):
    (d / 'n.nod.xml').write_text('<nodes>' + nodes + '</nodes>')
    (d / 'n.edg.xml').write_text('<edges>' + edges + '</edges>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds', *extra])


def record(name, value):
    RESULTS[name] = value
    Path(A.out).mkdir(parents=True, exist_ok=True)
    (Path(A.out) / 'results.json').write_text(json.dumps(RESULTS, indent=1, default=float))
    print(name, json.dumps(value, default=lambda x: round(float(x), 3)), flush=True)


VTYPE = '<vType id="h" carFollowModel="Human" length="5" minGap="2.5" speedDev="0"/>'


def ring(L=230.0, n=22, v0=11.0, seeds=3, dt=None, T=600.0):
    d = workdir(f'ring{int(L)}')
    r = L / (2 * math.pi)
    nodes = ''.join(f'<node id="n{i}" x="{r*math.cos(i*math.pi/2):.3f}" y="{r*math.sin(i*math.pi/2):.3f}"/>' for i in range(4))
    edges = ''
    for i in range(4):
        pts = ' '.join(f'{r*math.cos((i+k/8)*math.pi/2):.3f},{r*math.sin((i+k/8)*math.pi/2):.3f}' for k in range(9))
        edges += f'<edge id="e{i}" from="n{i}" to="n{(i+1)%4}" numLanes="1" speed="{v0}" shape="{pts}"/>'
    netconvert(d, nodes, edges, '--no-internal-links')
    route = ' '.join(f'e{(i%4)}' for i in range(4000))
    out = []
    length = L / 4
    for seed in range(seeds):
        # Evenly spaced on the ring, one edge at a time.
        veh = ''
        for k in range(n):
            s = k * L / n
            edge = int(s // length)
            pos = s - edge * length + 5.1
            if pos > length:
                edge = (edge + 1) % 4
                pos -= length
            rt = ' '.join(f'e{((edge + i) % 4)}' for i in range(4000))
            veh += f'<vehicle id="v{k}" type="h" depart="0" departPos="{pos:.2f}" departSpeed="0"><route edges="{rt}"/></vehicle>'
        (d / 'r.xml').write_text(f'<routes>{VTYPE}{veh}</routes>')
        rep, fc = cars(d, '--dt', dt or A.dt, '--end', T, '--seed', seed, '--detect-every', 1, tag=f's{seed}')
        f = pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc'], dtype={'trip': str, 'lane': str})
        f = f[f.time >= T / 2]
        stopped = float((f.speed < 0.5).mean())
        # Wave speed from where the slowest car of each second is.
        f['edge'] = f.lane.str.split('_').str[0].str[1:].astype(int)
        f['s'] = f.edge * length + f.pos
        slow = f.sort_values('speed').groupby('time').first().reset_index()
        ds = np.diff(np.unwrap(slow.s.values * 2 * np.pi / L)) * L / (2 * np.pi)
        dtm = np.diff(slow.time.values)
        wave = -np.median(ds[np.abs(ds) < 30] / dtm[np.abs(ds) < 30]) * 3.6
        tracks = f.groupby('trip').speed
        stop_frac = stopped
        wave2 = wave_from_arrivals(f, L)
        out.append(dict(stopped=stop_frac, mean_v=f.speed.mean(), sd_v=f.speed.std(), wave_kmh=wave2, wave_slowest=wave, collisions=rep['collision_incidents'], cert_floor=rep['cert_floor'], guard=rep['humans']['guard_steps'] / max(rep['humans']['human_steps'], 1)))
    record(f'ring_{int(L)}_dt{dt or A.dt}', out)


def wave_from_arrivals(f, L):
    """Upstream speed of a jam: when car k stops against when the car ahead of it stopped."""
    events = []
    for trip, g in f.groupby('trip'):
        g = g.sort_values('time')
        v = g.speed.values
        t = g.time.values
        s = g.s.values
        down = np.where((v[1:] < 1.0) & (v[:-1] >= 1.0))[0]
        for k in down:
            events.append((t[k + 1], s[k + 1]))
    if len(events) < 8:
        return float('nan')
    ev = np.array(sorted(events))
    rates = []
    for i in range(len(ev) - 1):
        dt_ = ev[i + 1, 0] - ev[i, 0]
        ds_ = (ev[i, 1] - ev[i + 1, 1]) % L
        if 0.2 <= dt_ <= 5 and 2 <= ds_ <= 20:
            rates.append(ds_ / dt_)
    return float(np.median(rates) * 3.6) if rates else float('nan')


def queue(seeds=8, n=15, dt=None):
    d = workdir('queue')
    nodes = '<node id="a" x="-800" y="0"/><node id="t" x="0" y="0" type="traffic_light"/><node id="b" x="500" y="0"/><node id="c" x="0" y="-300"/><node id="e" x="0" y="300"/>'
    edges = '<edge id="in" from="a" to="t" numLanes="1" speed="13.89"/><edge id="out" from="t" to="b" numLanes="1" speed="13.89"/><edge id="cross" from="c" to="t" numLanes="1" speed="13.89"/><edge id="crossout" from="t" to="e" numLanes="1" speed="13.89"/>'
    netconvert(d, nodes, edges, '--tls.yellow.time', '3', '--tls.allred.time', '0', '--tls.left-green.time', '0', '--no-left-connections')
    add = '<additional><tlLogic id="t" type="static" programID="fix" offset="0"><phase duration="60" state="rr"/><phase duration="60" state="GG"/></tlLogic></additional>'
    (d / 'tl.xml').write_text(_tl_program(d))
    out = []
    stand = []
    for seed in range(seeds):
        veh = ''.join(f'<vehicle id="v{k:02d}" type="h" depart="{k*2}" departSpeed="max" route="r"/>' for k in range(n))
        (d / 'r.xml').write_text(f'<routes>{VTYPE}<route id="r" edges="in out"/>{veh}</routes>')
        rep, fc = cars(d, '--dt', dt or A.dt, '--end', 130, '--seed', seed, '--additional', d / 'tl.xml', tag=f's{seed}', interval=dt or A.dt)
        f = pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed'], dtype={'trip': str, 'lane': str})
        green = float(_first_green(d))
        cross = []
        for trip, g in f.groupby('trip'):
            g = g.sort_values('time')
            on_in = g[g.lane.str.startswith('in_')]
            after = g[~g.lane.str.startswith('in_')]
            if on_in.empty or after.empty:
                continue
            last = on_in.iloc[-1]
            first = after.iloc[0]
            length_in = LANE_IN[d]
            rate = max(first.speed, 0.1)
            cross.append((trip, last.time + (length_in - last.pos) / max(last.speed, rate)))
        cross.sort(key=lambda x: x[1])
        times = np.array([c[1] for c in cross])
        h = np.diff(np.concatenate([[green], times]))
        out.append(h)
        # Standing spacing: head to head just before green.
        snap = f[(f.time >= green - dt_of() * 3) & (f.time < green) & f.lane.str.startswith('in_') & (f.speed < 0.05)]
        last_snap = snap[snap.time == snap.time.max()].sort_values('pos', ascending=False)
        stand.extend(np.abs(np.diff(last_snap.pos.values)).tolist())
    m = np.nanmean([x[:n] for x in out if len(x) >= n], axis=0)
    hsat = float(np.mean(m[4:12]))
    lost = float(np.sum(m[:4] - hsat))
    record(f'queue_dt{dt or A.dt}', dict(h=m[:8].tolist(), hsat=hsat, lost=lost, stand_median=float(np.median(stand)), stand_p10=float(np.percentile(stand, 10)), stand_p90=float(np.percentile(stand, 90))))


LANE_IN = {}


def dt_of():
    return A.dt


def _tl_program(d):
    import xml.etree.ElementTree as ET
    root = ET.parse(d / 'net.xml').getroot()
    for lane in root.iter('lane'):
        if lane.get('id') == 'in_0':
            LANE_IN[d] = float(lane.get('length'))
    tl = root.find('tlLogic')
    n = len(tl.find('phase').get('state'))
    # Keep the approach under test red first, as the second half of netconvert's own program.
    conn = [c for c in root.iter('connection') if c.get('tl') == 't']
    idx = {c.get('linkIndex'): c.get('from') for c in conn}
    def state(ch_in, ch_x):
        return ''.join(ch_in if idx.get(str(i)) == 'in' else ch_x for i in range(n))
    phases = [(50, state('r', 'G')), (3, state('r', 'y')), (1, state('r', 'r')), (60, state('G', 'r')), (3, state('y', 'r')), (1, state('r', 'r'))]
    body = ''.join(f'<phase duration="{p[0]}" state="{p[1]}"/>' for p in phases)
    (d / 'green.txt').write_text(str(54.0))
    return f'<additional><tlLogic id="t" type="static" programID="fix" offset="0">{body}</tlLogic></additional>'


def _first_green(d):
    return (d / 'green.txt').read_text()


I80 = None


def i80_waits():
    global I80
    if I80 is None:
        I80 = pd.read_csv(ROOT / 'research/truth/courtesy/merge_cars_i-80.csv.gz').wait.values
    return I80


def ks(a, b):
    a = np.sort(a)
    b = np.sort(b)
    xs = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, xs, side='right') / len(a) - np.searchsorted(b, xs, side='right') / len(b))))


def load_fcd(fc):
    return pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'wait', 'own', 'offset', 'length'], dtype={'trip': str, 'lane': str})


def label_time(g, lane_to, width):
    """When a change into `lane_to` passes half way: the lane id flips at the start of the change here."""
    on = g[g.lane == lane_to]
    if on.empty:
        return None
    moved = on[on.offset.abs() <= width / 2]
    return moved.iloc[0] if not moved.empty else on.iloc[0]


def merge_net(d, vb):
    (d / 'n.nod.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="800" y="0"/><node id="c" x="1004" y="0"/><node id="d" x="1304" y="0"/><node id="e" x="1404" y="0"/><node id="f" x="2000" y="0"/></nodes>')
    (d / 'n.edg.xml').write_text(f'''<edges><edge id="up" from="a" to="b" numLanes="2" speed="20"/><edge id="merge" from="b" to="c" numLanes="2" speed="20"/><edge id="down" from="c" to="d" numLanes="1" speed="20"/><edge id="neck" from="d" to="e" numLanes="1" speed="{vb}"/><edge id="out" from="e" to="f" numLanes="1" speed="20"/></edges>''')
    (d / 'n.con.xml').write_text('<connections><connection from="up" to="merge" fromLane="0" toLane="0"/><connection from="up" to="merge" fromLane="1" toLane="1"/><connection from="merge" to="down" fromLane="1" toLane="0"/></connections>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-x', d / 'n.con.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'])


def score_merge(fc, dur):
    """Same quantities as courtesy_merge.py and courtesy_zipper.py."""
    f = load_fcd(fc)
    width = 3.2
    f = f.sort_values(['trip', 'time'])
    by_t = {t: g for t, g in f[f.lane == 'merge_1'].groupby('time')}
    waits, stopped, v_c, rem, passes, never, letin = [], [], [], [], [], 0, []
    groups = dict(tuple(f.groupby('trip')))
    for trip, g in groups.items():
        if not trip.startswith('ramp'):
            continue
        y = g[g.lane == 'merge_0']
        if y.empty:
            continue
        r = label_time(g, 'merge_1', width)
        if r is None:
            never += 1
            continue
        waits.append(r.time - y.time.iloc[0])
        stopped.append(y.speed.min() < 1.0)
        v_c.append(r.speed)
        rem.append(204 - r.pos)
        # Every target lane vehicle alongside either got ahead, or ended up behind.
        seen = {}
        for t, p, v in zip(y.time.values, y.pos.values, y.speed.values):
            o = by_t.get(t)
            if o is None:
                continue
            lag = o[o.pos <= p]
            if lag.empty:
                continue
            q = lag.iloc[-1]
            if q.trip not in seen:
                seen[q.trip] = q.speed - v
        at = by_t.get(r.time)
        ahead = set(at[at.pos > r.pos].trip) if at is not None else set()
        np_ = 0
        for other, closing in seen.items():
            went_ahead = other in ahead or (groups[other].lane == 'down_0').any() and groups[other].time[groups[other].lane == 'down_0'].min() <= r.time
            letin.append((closing, not went_ahead))
            np_ += went_ahead
        passes.append(np_)
    cross = []
    for trip, g in groups.items():
        y = g[g.lane == 'down_0']
        if not y.empty:
            cross.append((y.time.iloc[0], trip.startswith('ramp')))
    cross.sort()
    a = np.array([c[1] for c in cross], bool)
    idx = np.where(a)[0]
    rl = np.diff(idx) - 1 if len(idx) > 1 else np.array([0])
    w = np.array(waits)
    li = np.array(letin, float).reshape(-1, 2)
    bins = [(-99, -3), (-3, -1), (-1, 1), (1, 3), (3, 99)]
    by_close = {f'{lo}..{hi}': float(li[(li[:, 0] >= lo) & (li[:, 0] < hi), 1].mean()) if ((li[:, 0] >= lo) & (li[:, 0] < hi)).any() else None for lo, hi in bins}
    p = np.array(passes)
    return dict(n=len(w), never=never, p50=np.percentile(w, 50), p90=np.percentile(w, 90), p99=np.percentile(w, 99), max=w.max(), ks=ks(w, i80_waits()),
                between={int(k): float((rl == k).mean()) for k in range(4)}, between_mean=float(rl.mean()), ramp_share=float(a.mean()), flow=len(cross) / dur * 3600,
                pass0=float((p == 0).mean()), pass_max=int(p.max()), letin=float(li[:, 1].mean()) if len(li) else None, letin_by_closing=by_close,
                stopped=float(np.mean(stopped)), v_cross=float(np.median(v_c)), rem_cross=float(np.median(rem)))


def merge(main=1180, ramp=920, vb=5.0, dur=1800, off=(), tag='', seeds=None, dt=None):
    d = workdir(f'merge{tag}')
    merge_net(d, vb)
    (d / 'r.xml').write_text(f'''<routes>{VTYPE}<route id="r" edges="up merge down neck out"/>
<flow id="ramp" type="h" route="r" begin="0" end="{dur}" vehsPerHour="{ramp}" departLane="0" departSpeed="max"/>
<flow id="main" type="h" route="r" begin="0" end="{dur}" vehsPerHour="{main}" departLane="1" departSpeed="max"/></routes>''')
    extra = ['--human-off', ','.join(off)] if off else []
    out = []
    for seed in range(seeds or A.seeds):
        rep, fc = cars(d, '--dt', dt or A.dt, '--end', dur + 900, '--seed', seed, *extra, tag=f's{seed}', interval=1.0)
        s = score_merge(fc, dur)
        s.update(arrived=rep['arrived'], inserted=rep['inserted'], collisions=rep['collision_incidents'], contact_samples=rep['contact_samples'], cert_floor=rep['cert_floor'], teleports=rep['teleports'], humans=rep['humans'], stuck=rep['gridlock_worst_stuck'], wall=rep['wall_s'])
        out.append(s)
    record(f'merge{tag}_{main}_{ramp}_{vb}_dt{dt or A.dt}', out)


def merge_free():
    # The A39 shape: a long ramp lane and free traffic.
    d = workdir('merge_free')
    (d / 'n.nod.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="800" y="0"/><node id="c" x="1100" y="0"/><node id="f" x="2200" y="0"/></nodes>')
    (d / 'n.edg.xml').write_text('<edges><edge id="up" from="a" to="b" numLanes="3" speed="33"/><edge id="merge" from="b" to="c" numLanes="3" speed="33"/><edge id="out" from="c" to="f" numLanes="2" speed="33"/></edges>')
    (d / 'n.con.xml').write_text('<connections><connection from="up" to="merge" fromLane="0" toLane="0"/><connection from="up" to="merge" fromLane="1" toLane="1"/><connection from="up" to="merge" fromLane="2" toLane="2"/><connection from="merge" to="out" fromLane="1" toLane="0"/><connection from="merge" to="out" fromLane="2" toLane="1"/></connections>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-x', d / 'n.con.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'])
    dur = 900
    (d / 'r.xml').write_text(f'''<routes>{VTYPE}<route id="r" edges="up merge out"/><flow id="ramp" type="h" route="r" begin="0" end="{dur}" vehsPerHour="300" departLane="0" departSpeed="max"/><flow id="main" type="h" route="r" begin="0" end="{dur}" vehsPerHour="1500" departLane="1" departSpeed="max"/></routes>''')
    out = []
    gaps = []
    for seed in range(A.seeds):
        rep, fc = cars(d, '--dt', A.dt, '--end', dur + 300, '--seed', seed, tag=f's{seed}', interval=0.5)
        f = load_fcd(fc).sort_values(['trip', 'time'])
        waits, passes = [], []
        for trip, g in f.groupby('trip'):
            if not trip.startswith('ramp'):
                continue
            y = g[g.lane == 'merge_0']
            if y.empty:
                continue
            r = label_time(g, 'merge_1', 3.2)
            if r is None:
                continue
            waits.append(r.time - y.time.iloc[0])
        out.append(dict(wait_p50=np.median(waits), n=len(waits), arrived=rep['arrived'], collisions=rep['collision_incidents']))
    record('merge_free', out)


def signal_net(d, La, spill):
    (d / 'n.nod.xml').write_text(f'''<nodes><node id="a" x="0" y="0"/><node id="b" x="150" y="0"/><node id="c" x="{150+La}" y="0" type="traffic_light" tl="c"/><node id="l" x="{150+La}" y="300"/><node id="t" x="{450+La}" y="0"/><node id="r" x="{150+La}" y="-300"/><node id="t2" x="{750+La}" y="0"/></nodes>''')
    neck = 2.0 if spill else 13.9
    (d / 'n.edg.xml').write_text(f'''<edges><edge id="up" from="a" to="b" numLanes="3" speed="13.9"/><edge id="app" from="b" to="c" numLanes="3" speed="13.9"/><edge id="L" from="c" to="l" numLanes="1" speed="13.9"/><edge id="T" from="c" to="t" numLanes="1" speed="13.9"/><edge id="R" from="c" to="r" numLanes="1" speed="13.9"/><edge id="T2" from="t" to="t2" numLanes="1" speed="{neck}"/></edges>''')
    (d / 'n.con.xml').write_text('<connections><connection from="up" to="app" fromLane="0" toLane="0"/><connection from="up" to="app" fromLane="1" toLane="1"/><connection from="up" to="app" fromLane="2" toLane="2"/><connection from="app" to="R" fromLane="0" toLane="0"/><connection from="app" to="T" fromLane="1" toLane="0"/><connection from="app" to="L" fromLane="2" toLane="0"/></connections>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-x', d / 'n.con.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true', '--tls.green.time', '40', '--tls.yellow.time', '3'])
    import xml.etree.ElementTree as ET
    ln = len(ET.parse(d / 'net.xml').getroot().find('tlLogic').find('phase').get('state'))
    (d / 'tl.xml').write_text(f'<additional><tlLogic id="c" type="static" programID="x" offset="0"><phase duration="40" state="{"G"*ln}"/><phase duration="3" state="{"y"*ln}"/><phase duration="47" state="{"r"*ln}"/></tlLogic></additional>')


SUMO_SIGNAL = {(150, 1200, 0): (2, 8, 9), (60, 2000, 0): (14, 42, 54), (60, 1200, 1): (20, 50, 61), (30, 2000, 1): (15, 50, 62), (150, 2000, 1): (43, 92, 164)}


def signal_case(La, vph, spill, off=(), seed=7, tag='', dt=None, model='Human'):
    import random
    d = workdir(f'signal_{La}_{vph}_{spill}{tag}')
    signal_net(d, La, spill)
    dur = 1800
    rnd = random.Random(seed)
    rows = []
    for i in range(int(vph * dur / 3600)):
        t = rnd.uniform(0, dur)
        u = rnd.random()
        rt = 'rL' if u < .3 else ('rR' if u < .5 else 'rT')
        rows.append((t, f'<vehicle id="{i}" type="h" route="{rt}" depart="{t:.1f}" departLane="random" departSpeed="max"/>'))
    rows.sort()
    (d / 'r.xml').write_text(f'<routes>{VTYPE}<route id="rL" edges="up app L"/><route id="rT" edges="up app T T2"/><route id="rR" edges="up app R"/>' + ''.join(x[1] for x in rows) + '</routes>')
    extra = ['--human-off', ','.join(off)] if off else []
    rep, fc = cars(d, '--dt', dt or A.dt, '--end', dur + 1200, '--seed', seed, '--additional', d / 'tl.xml', *extra, tag=f's{seed}', interval=1.0)
    f = load_fcd(fc)
    f = f[f.lane.str.startswith('app_')].copy()
    f['li'] = f.lane.str[-1].astype(int)
    need = {}
    for i, (t, x) in enumerate(rows):
        need[str(x.split('"')[1])] = {'rL': 2, 'rT': 1, 'rR': 0}[x.split('route="')[1].split('"')[0]]
    wrong_time, stop_wrong = [], []
    for trip, g in f.groupby('trip'):
        w = g[g.li != need[trip]]
        if not w.empty:
            wrong_time.append(w.time.iloc[-1] - w.time.iloc[0] + 1)
        stop_wrong.append((w.speed < 0.1).sum() if not w.empty else 0)
    w = np.array(wrong_time or [0.0])
    sw = np.array(stop_wrong or [0])
    h = rep['humans']
    res = dict(wrong_p50=np.percentile(w, 50), wrong_p90=np.percentile(w, 90), wrong_max=w.max(), stop_wrong_max=int(sw.max()), share_stop_wrong=float((sw > 0).mean()), arrived=rep['arrived'], inserted=rep['inserted'], demand=len(rows), active_end=rep['inserted'] - rep['arrived'], collisions=rep['collision_incidents'], cert_floor=rep['cert_floor'], teleports=rep['teleports'], swaps=h['swaps'], swaps_failed=h['swaps_failed'], rerouted=h['rerouted'], reroute_failed=h['reroute_failed'], forced_steps=h['forced_steps'], yield_steps=h['yield_steps'], stuck=rep['gridlock_worst_stuck'], sumo=SUMO_SIGNAL.get((La, vph, spill)))
    record(f'signal_{La}_{vph}_{spill}{tag}', res)


def signals():
    for La, vph, spill in SUMO_SIGNAL:
        signal_case(La, vph, spill)


def yellow_scene():
    """Item 18: time to line at yellow onset against stop or go, as the DLR extraction."""
    d = workdir('yellow')
    (d / 'n.nod.xml').write_text('<nodes><node id="a" x="-600" y="0"/><node id="t" x="0" y="0" type="traffic_light" tl="t"/><node id="b" x="400" y="0"/></nodes>')
    (d / 'n.edg.xml').write_text('<edges><edge id="in" from="a" to="t" numLanes="1" speed="13.89"/><edge id="out" from="t" to="b" numLanes="1" speed="13.89"/></edges>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'])
    (d / 'tl.xml').write_text('<additional><tlLogic id="t" type="static" programID="x" offset="0"><phase duration="27" state="G"/><phase duration="3" state="y"/><phase duration="20" state="r"/></tlLogic></additional>')
    dur = 3000
    (d / 'r.xml').write_text(f'<routes>{VTYPE}<route id="r" edges="in out"/><flow id="f" type="h" route="r" begin="0" end="{dur}" vehsPerHour="900" departSpeed="max"/></routes>')
    rows = []
    for seed in range(A.seeds):
        rep, fc = cars(d, '--dt', A.dt, '--end', dur, '--seed', seed, '--additional', d / 'tl.xml', tag=f's{seed}', interval=A.dt)
        f = load_fcd(fc)
        length = float(pd.read_csv(fc, nrows=0).shape[1] and _lane_len(d, 'in_0'))
        cycle = 50.0
        for k in range(int(dur / cycle)):
            t_y = k * cycle + 27.0
            at = f[(np.abs(f.time - t_y) < A.dt / 2 + 1e-3) & (f.lane == 'in_0') & (f.speed > 2.0)]
            for _, r in at.iterrows():
                ttl = (length - r.pos) / r.speed
                later = f[(f.trip == r.trip) & (f.time >= t_y) & (f.time < t_y + 25)]
                stopped = later.speed.min() < 0.3 and (later.lane == 'in_0').all()
                brake = max(-later.acc.min(), 0.0)
                crossed = later[later.lane != 'in_0']
                after_red = crossed.time.iloc[0] - (t_y + 3) if not crossed.empty else None
                rows.append((ttl, stopped, brake, after_red))
    a = pd.DataFrame(rows, columns=['ttl', 'stopped', 'brake', 'after_red'])
    a.to_csv(d / 'decisions.csv', index=False)
    from scipy.optimize import minimize
    x, y = a.ttl.values, a.stopped.values.astype(float)
    def nll(p):
        z = np.clip((x - p[0]) / abs(p[1]), -30, 30)
        q = np.clip(1 / (1 + np.exp(-z)), 1e-6, 1 - 1e-6)
        return -(y * np.log(q) + (1 - y) * np.log(1 - q)).sum()
    fit = minimize(nll, [5.0, 0.5], method='Nelder-Mead').x
    bins = [(0, 3), (3, 4), (4, 5), (5, 6), (6, 8), (8, 99)]
    table = {f'{lo}-{hi}': (int(((x >= lo) & (x < hi)).sum()), float(y[(x >= lo) & (x < hi)].mean()) if ((x >= lo) & (x < hi)).any() else None) for lo, hi in bins}
    st = a[a.stopped]
    go = a[~a.stopped & a.after_red.notna()]
    record('yellow', dict(n=len(a), half_at=fit[0], scale=abs(fit[1]), table=table, stop_brake_p50=float(st.brake.median()), stop_brake_p95=float(st.brake.quantile(.95)), share_go_after_red=float((go.after_red > 0).mean()), go_after_red_p95=float(go.after_red.quantile(.95))))


def _lane_len(d, lane):
    import xml.etree.ElementTree as ET
    for l in ET.parse(d / 'net.xml').getroot().iter('lane'):
        if l.get('id') == lane:
            return float(l.get('length'))


def deadlocks():
    """Section 5 D: counter-wish side by side, three-lane chain, held-too-close, packed standing target."""
    d = workdir('deadlocks')
    (d / 'n.nod.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="300" y="0"/><node id="l" x="400" y="100"/><node id="t" x="500" y="0"/><node id="r" x="400" y="-100"/></nodes>')
    (d / 'n.edg.xml').write_text('<edges><edge id="app" from="a" to="b" numLanes="3" speed="13.9"/><edge id="L" from="b" to="l" numLanes="1" speed="13.9"/><edge id="T" from="b" to="t" numLanes="1" speed="13.9"/><edge id="R" from="b" to="r" numLanes="1" speed="13.9"/></edges>')
    (d / 'n.con.xml').write_text('<connections><connection from="app" to="R" fromLane="0" toLane="0"/><connection from="app" to="T" fromLane="1" toLane="0"/><connection from="app" to="L" fromLane="2" toLane="0"/></connections>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-x', d / 'n.con.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'])
    routes = '<route id="L" edges="app L"/><route id="T" edges="app T"/><route id="R" edges="app R"/>'
    def veh(i, r, lane, pos, depart=0):
        return f'<vehicle id="{i}" type="h" route="{r}" depart="{depart}" departLane="{lane}" departPos="{pos}" departSpeed="0"/>'
    cases = {
        'counter_side_by_side': veh('a', 'L', 1, 280) + veh('b', 'T', 2, 280),
        'counter_nose_to_tail': veh('a', 'L', 1, 288) + veh('b', 'T', 2, 280),
        'three_lane_chain': veh('a', 'L', 0, 280) + veh('b', 'R', 2, 280) + veh('c', 'T', 1, 280),
        'held_too_close': veh('a', 'T', 0, 288) + ''.join(veh(f'q{k}', 'T', 1, 290 - k * 7.6) for k in range(12)),
        'standing_target': veh('a', 'L', 1, 285),
    }
    out = {}
    for name, vs in cases.items():
        (d / f'{name}.xml').write_text(f'<routes>{VTYPE}{routes}{vs}</routes>')
        rep, fc = cars(d, '--dt', A.dt, '--end', 300, '--seed', 1, routes=f'{name}.xml', tag=name, interval=1.0)
        out[name] = dict(arrived=rep['arrived'], inserted=rep['inserted'], collisions=rep['collision_incidents'], cert_floor=rep['cert_floor'], swaps=rep['humans']['swaps'], rerouted=rep['humans']['rerouted'], stuck=rep['gridlock_worst_stuck'], wall=rep['wall_s'])
    record('deadlocks', out)


def main():
    global A
    p = argparse.ArgumentParser()
    p.add_argument('tests', nargs='*')
    p.add_argument('--out', default='/tmp/human-tests')
    p.add_argument('--dt', type=float, default=0.5)
    p.add_argument('--interval', type=float, default=1.0)
    p.add_argument('--seeds', type=int, default=3)
    A = p.parse_args()
    for t in A.tests:
        globals()[t]()


if __name__ == '__main__':
    main()
