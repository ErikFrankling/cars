#!/usr/bin/env python3
"""Clips of the human driver, always rendered from a trace. Courtesy being given at the I-80 shape, and stuck places
named in a city run's report.

    python3 scripts/human_clips.py courtesy --out DIR
    python3 scripts/human_clips.py place --net N --trace T --x X --y Y --begin B --end E --name NAME --out DIR
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BIN = os.environ.get('CARS_BIN', str(ROOT / 'target/release/cars'))
LOCK = [] if os.environ.get('CARS_GPU_HELD') or os.environ.get('CARS_ADAPTER') else ['flock', '/tmp/cars-gpu.lock']
sys.path.insert(0, str(ROOT / 'scripts'))


def sh(*cmd):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(' '.join(map(str, cmd)) + '\n' + r.stderr[-1500:])
    return r.stdout + r.stderr


def courtesy(a):
    import human_tests as H
    H.A = argparse.Namespace(out=a.out, dt=0.5, interval=0.5, seeds=1)
    d = H.workdir('courtesy')
    H.merge_net(d, 11.0)
    (d / 'r.xml').write_text(f'<routes>{H.VTYPE}<route id="rr" edges="on merge down neck out"/><route id="rm" edges="up merge down neck out"/><flow id="ramp" type="h" route="rr" begin="0" end="900" vehsPerHour="800" departLane="0" departSpeed="max"/><flow id="main" type="h" route="rm" begin="0" end="900" vehsPerHour="1000" departLane="0" departSpeed="max"/></routes>')
    tr = d / 'c.trace'
    fc = d / 'c.csv'
    sh(*LOCK, BIN, 'run', '--net', d / 'net.xml', '--routes', d / 'r.xml', '--dt', 0.5, '--end', 900, '--seed', 3, '--trace', tr, '--trace-begin', 300, '--trace-end', 700, '--fcd', fc, '--fcd-begin', 300, '--fcd-interval', 0.5, '--phys-json', d / 'phys.json', '--report-json', d / 'rep.json')
    f = pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'offset'], dtype={'trip': str, 'lane': str})
    # A follower that brakes in the 4 s before a ramp car starts across in front of it, and was alongside it before.
    best = []
    m1 = f[f.lane == 'merge_1']
    for trip, g in f[f.trip.str.startswith('ramp')].groupby('trip'):
        g = g.sort_values('time')
        on = g[g.lane == 'merge_1']
        if on.empty:
            continue
        t = on.time.iloc[0]
        p = on.pos.iloc[0]
        now = m1[(m1.time == t) & (m1.pos < p) & (m1.trip != trip)].sort_values('pos')
        if now.empty:
            continue
        fol = now.iloc[-1]
        h = m1[(m1.trip == fol.trip) & m1.time.between(t - 4, t)]
        if len(h) < 6:
            continue
        best.append((float(h.acc.min()), t, p, trip, fol.trip, float(p - fol.pos - 5)))
    best.sort()
    best = [b for b in best if b[5] > 1.0]
    print('courtesy events', len(best), best[:5])
    (d / 'events.json').write_text(json.dumps(best[:30]))
    out = Path(a.gallery)
    out.mkdir(parents=True, exist_ok=True)
    net = d / 'net.xml'
    # netconvert moved the origin, so ask the net where merge starts.
    import xml.etree.ElementTree as ET
    shape = None
    for l in ET.parse(net).getroot().iter('lane'):
        if l.get('id') == 'merge_0':
            shape = [tuple(map(float, q.split(','))) for q in l.get('shape').split()]
    length = 204.0
    for k, b in enumerate(best[:2]):
        t, p = b[1], b[2]
        u = min(p / length, 1.0)
        x = shape[0][0] + (shape[-1][0] - shape[0][0]) * u
        y = shape[0][1] + (shape[-1][1] - shape[0][1]) * u
        name = f'courtesy_i80_{k}.mp4'
        sh(*LOCK, BIN, 'replay', '--net', net, '--trace', tr, '--begin', t - 12, '--end', t + 10, '--center', f'{x},{y}', '--metres-per-pixel', 0.12, '--overlay', 'all', '--width', 1600, '--height', 800, '--title', f'A driver lets {b[3]} in: {b[4]} eases off {-b[0]:.1f} m/s2', '--out', out / name)
        sh(*LOCK, BIN, 'replay', '--net', net, '--trace', tr, '--at', t, '--center', f'{x},{y}', '--metres-per-pixel', 0.12, '--overlay', 'all', '--width', 1600, '--height', 800, '--out', out / f'courtesy_i80_{k}.png')
        print(out / name)


def place(a):
    out = Path(a.gallery)
    out.mkdir(parents=True, exist_ok=True)
    sh(*LOCK, BIN, 'replay', '--net', a.net, '--trace', a.trace, '--begin', a.begin, '--end', a.end, '--center', f'{a.x},{a.y}', '--metres-per-pixel', a.mpp, '--overlay', 'all', '--speed', a.speed, '--width', 1600, '--height', 1000, '--title', a.name, '--out', out / f'{a.name}.mp4')
    sh(*LOCK, BIN, 'replay', '--net', a.net, '--trace', a.trace, '--at', a.end - 1, '--center', f'{a.x},{a.y}', '--metres-per-pixel', a.mpp, '--overlay', 'all', '--width', 1600, '--height', 1000, '--out', out / f'{a.name}.png')
    print(out / f'{a.name}.mp4')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('what', choices=['courtesy', 'place'])
    p.add_argument('--out', default='/tmp/human-clips')
    p.add_argument('--gallery', default='/home/erikf/projects/personal/cars-data/videos/gallery/humans')
    p.add_argument('--net')
    p.add_argument('--trace')
    p.add_argument('--x', type=float)
    p.add_argument('--y', type=float)
    p.add_argument('--begin', type=float)
    p.add_argument('--end', type=float)
    p.add_argument('--name')
    p.add_argument('--mpp', type=float, default=0.25)
    p.add_argument('--speed', type=float, default=4.0)
    a = p.parse_args()
    {'courtesy': courtesy, 'place': place}[a.what](a)


if __name__ == '__main__':
    main()
