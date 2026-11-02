#!/usr/bin/env python3
"""Recipe step 3. Capacity with no city: isolated tests per road class at real speeds, against report 04's bands.

    step3_capacity.py --cars BIN [--flags "--humans"] --dt 1 --out DIR

Signal discharge at 30 and 50 km/h, lane-drop discharge at 100 km/h, jam spacing, start wave, give-way
minor-road capacity. Numbers come from the same fcd and sensors a city run has. Runs on CPU Vulkan: small nets.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ENV = dict(os.environ, CARS_ADAPTER='llvmpipe', LP_NUM_THREADS='2')
CAR = '<vType id="car" vClass="passenger" length="4.6" width="1.8"/>'


def nc(d, nodes, edges, extra=(), conns=None, tll=None):
    (d / 'n.nod.xml').write_text('<nodes>' + ''.join(f'<node id="{i}" x="{x}" y="{y}" type="{t}"/>' for i, x, y, t in nodes) + '</nodes>')
    (d / 'e.edg.xml').write_text('<edges>' + ''.join(f'<edge id="{i}" from="{a}" to="{b}" numLanes="{n}" speed="{v:.3f}" priority="{p}"/>' for i, a, b, n, v, p in edges) + '</edges>')
    cmd = ['netconvert', '-n', str(d / 'n.nod.xml'), '-e', str(d / 'e.edg.xml'), '-o', str(d / 'net.xml'), '--no-turnarounds', '--tls.green.time', '60', '--tls.yellow.time', '3', '--tls.red.time', '0', '--tls.allred.time', '0', '--junctions.corner-detail', '5'] + list(extra)
    subprocess.run(cmd, check=True, capture_output=True)


def sim(d, a, end, routes, sensors=None, seed=0, fcd=True):
    cmd = [a.cars, 'run', '--net', str(d / 'net.xml'), '--routes', str(routes), '--dt', str(a.dt), '--begin', '0', '--end', str(end), '--time-to-teleport', '0', '--seed', str(seed), '--capacity', '2000', '--trip-csv', str(d / 'trips.csv'), '--edge-csv', str(d / 'edges.csv'), '--edge-interval', '60'] + shlex.split(a.flags)
    if fcd:
        cmd += ['--fcd', str(d / 'fcd.csv'), '--fcd-interval', str(a.dt)]
    if sensors:
        (d / 's.csv').write_text('\n'.join(sensors) + '\n')
        cmd += ['--sensors', str(d / 's.csv'), '--sensor-csv', str(d / 'sensor_out.csv')]
    r = subprocess.run(cmd, env=ENV, capture_output=True, text=True, timeout=1200)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])


def signal(a, kmh, seed):
    d = Path(a.out) / f'sig{kmh}_{seed}'
    d.mkdir(parents=True, exist_ok=True)
    v = kmh / 3.6
    nc(d, [('a', 0, 0, 'priority'), ('s', 800, 0, 'traffic_light'), ('b', 1200, 0, 'priority')], [('in', 'a', 's', 1, v, 1), ('out', 's', 'b', 1, v, 1)])
    # a fixed program with one long red, then green until the queue has gone
    x = (d / 'net.xml').read_text()
    import re
    x = re.sub(r'(<tlLogic id="s"[^>]*>).*?(</tlLogic>)', r'\1<phase duration="150" state="r"/><phase duration="200" state="G"/>\2', x, flags=re.S).replace('type="actuated"', 'type="static"')
    (d / 'net.xml').write_text(x)
    (d / 'r.xml').write_text(f'<routes>{CAR}<flow id="f" type="car" begin="0" end="140" period="3" departLane="0" departSpeed="max"><route edges="in out"/></flow></routes>')
    sim(d, a, 350, d / 'r.xml', seed=seed)
    f = pd.read_csv(d / 'fcd.csv')
    f = f[f.lane.str.startswith('in')]
    t_green = 150
    stop = f[f.time == f[f.time <= t_green - 1].time.max()].sort_values('pos', ascending=False)
    spacing = np.diff(-stop.pos.values)
    queued = stop[stop.speed < .1]
    gone = f.groupby('trip').time.max().sort_values()
    gone = gone[gone >= t_green].values
    h = np.diff(gone)
    starts = []
    for i, tr in enumerate(queued.trip.values[:25]):
        g = f[(f.trip == tr) & (f.time >= t_green) & (f.speed > 1.0)]
        if len(g):
            starts.append((queued.pos.values[0] - queued.pos.values[i], g.time.min()))
    st = np.array(starts)
    wave = -np.polyfit(st[:, 1], st[:, 0], 1)[0] * 3.6 if len(st) > 5 else np.nan
    sat_h = float(np.mean(h[4:min(len(h), 24)])) if len(h) > 8 else np.nan
    lost = float(gone[3] - t_green - 4 * sat_h) if len(gone) > 4 else np.nan
    return dict(kmh=kmh, queued=int(len(queued)), sat_headway_s=sat_h, sat_flow=3600 / sat_h, jam_spacing_m=float(np.median(spacing[:15])), start_wave_kmh=float(abs(wave)), lost_time_s=lost)


def lanedrop(a, kmh, seed):
    d = Path(a.out) / f'drop{kmh}_{seed}'
    d.mkdir(parents=True, exist_ok=True)
    v = kmh / 3.6
    nc(d, [('a', 0, 0, 'priority'), ('m', 3000, 0, 'priority'), ('b', 5000, 0, 'priority')], [('up', 'a', 'm', 2, v, 3), ('down', 'm', 'b', 1, v, 3)])
    (d / 'r.xml').write_text(f'<routes>{CAR}<flow id="f" type="car" begin="0" end="2400" vehsPerHour="3000" departLane="free" departSpeed="max"><route edges="up down"/></flow></routes>')
    sim(d, a, 2400, d / 'r.xml', sensors=['q,down_0,1000'], seed=seed, fcd=False)
    (d / 's.csv').unlink(missing_ok=True)
    e = pd.read_csv(d / 'edges.csv')
    q = e[e.edge == 'down'].set_index('begin').entered * 60.0
    u = e[e.edge == 'up'].copy()
    u['v'] = u.distance / u.samples.replace(0, np.nan)
    jam = u[u.v < .6 * v].begin
    onset = float(jam.min()) if len(jam) else np.nan
    sustained = float(q[(q.index >= 1200) & (q.index < 2400)].mean())
    pre = float(q[(q.index >= onset - 300) & (q.index < onset)].max()) if len(jam) else np.nan
    return dict(kmh=kmh, sustained_veh_h_lane=sustained, peak_before_jam=pre, drop_pct=100 * (1 - sustained / pre) if pre and pre > 0 else np.nan, onset_s=onset, up_speed_end=float(u.v.iloc[-5:].mean()))


def giveway(a, major, seed):
    d = Path(a.out) / f'give{major}_{seed}'
    d.mkdir(parents=True, exist_ok=True)
    nc(d, [('w', 0, 0, 'priority'), ('c', 500, 0, 'priority'), ('e', 1000, 0, 'priority'), ('s', 500, -500, 'priority')], [('we', 'w', 'c', 1, 13.89, 5), ('ce', 'c', 'e', 1, 13.89, 5), ('sc', 's', 'c', 1, 13.89, 1)])
    # major road arrivals are random, as Siegloch's formula assumes: a flow with even gaps would admit a wrong number
    rng = np.random.default_rng(100 + seed + major)
    times, t = [], 0.0
    while major and t < 1800:
        t += 1.2 + rng.exponential(3600 / major - 1.2) if 3600 / major > 1.2 else 1.2
        times.append(t)
    fl = ''.join(f'<vehicle id="m{i}" type="car" depart="{x:.1f}" departLane="0" departSpeed="max"><route edges="we ce"/></vehicle>' for i, x in enumerate(times))
    mins = ''.join(f'<vehicle id="s{i}" type="car" depart="{i * 2.0:.1f}" departLane="0" departSpeed="max"><route edges="sc ce"/></vehicle>' for i in range(900))
    all_v = sorted(re.findall(r'<vehicle .*?</vehicle>', fl + mins), key=lambda v: float(re.search(r'depart="([^"]+)"', v)[1]))
    (d / 'r.xml').write_text(f'<routes>{CAR}' + ''.join(all_v) + '</routes>')
    sim(d, a, 1800, d / 'r.xml', seed=seed, fcd=False)
    t = pd.read_csv(d / 'trips.csv')
    n = t[t.trip.str.startswith('s') & (t.arrival >= 600) & (t.arrival < 1800)]
    # Siegloch with HBS critical gap and follow-up for a right turn from the minor road, 5.9 and 3.0 s
    tc, tf = 5.9, 3.0
    m = t[t.trip.str.startswith('m') & (t.arrival >= 600) & (t.arrival < 1800)]
    return dict(major=major, major_arrived_per_h=len(m) * 3, minor_capacity=len(n) * 3, siegloch=3600 / tf * np.exp(-major * (tc - tf / 2) / 3600))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cars', required=True)
    p.add_argument('--flags', default='')
    p.add_argument('--dt', type=float, default=1.0)
    p.add_argument('--out', required=True)
    p.add_argument('--seeds', type=int, default=3)
    a = p.parse_args()
    res = dict(cars=a.cars, flags=a.flags, dt=a.dt)
    prev = Path(a.out, 'result.json')
    old = json.loads(prev.read_text()) if prev.exists() else {}
    res['signal'] = old.get('signal') or [signal(a, k, s) for k in (30, 50) for s in range(a.seeds)]
    res['lanedrop'] = old.get('lanedrop') or [lanedrop(a, 100, s) for s in range(a.seeds)]
    res['giveway'] = [giveway(a, m, s) for m in (0, 400, 800, 1200) for s in range(2)]
    tab = pd.DataFrame(res['signal']).groupby('kmh').mean().round(2)
    print(tab.to_string())
    print(pd.DataFrame(res['lanedrop']).mean().round(1).to_dict())
    print(pd.DataFrame(res['giveway']).groupby('major').mean().round(0).to_string())
    Path(a.out, 'result.json').write_text(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
