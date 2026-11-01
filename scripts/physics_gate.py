#!/usr/bin/env python3
"""The low-demand check: extremely low demand, then 50%, teleports off. Trafikverket's handbook and the TRB
DTA primer use it to find coding errors, since nothing should jam when the roads are nearly empty.

    python3 scripts/physics_gate.py --out DIR [--cars BIN] [--only stockholm-1 ...]

Writes one CSV of stuck lanes per run, with location and cause, and a summary. Reports; fixes nothing.
"""
import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('/home/erikf/projects/personal/cars-data')
LOCK = [] if os.environ.get('CARS_GPU_HELD') else ['flock', '/tmp/cars-gpu.lock']
STOCKHOLM = dict(net=DATA / 'truth/maps/builds/v5_inventory/net.xml', routes=DATA / 'physics/stockholm/morning.repaired.rou.xml.gz')
BERLIN = dict(net=DATA / 'best/berlin.net.xml', routes=DATA / 'best/berlin.rou.gz')
RUNS = {
    'stockholm-1': dict(STOCKHOLM, fraction=0.01, begin=25200, end=34200),
    'stockholm-50': dict(STOCKHOLM, fraction=0.5, begin=25200, end=34200),
    'berlin-1': dict(BERLIN, fraction=0.01, begin=0, end=86400),
    'berlin-50-morning': dict(BERLIN, fraction=0.5, begin=21600, end=36000),
    'berlin-50-evening': dict(BERLIN, fraction=0.5, begin=54000, end=68400),
}


def gate(name, spec, a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = out / f'{name}.json'
    cmd = [*LOCK, a.cars, 'run', '--net', spec['net'], '--routes', spec['routes'], '--dt', 1, '--begin', spec['begin'], '--end', spec['end'], '--capacity', a.capacity,
           '--demand-fraction', spec['fraction'], '--gridlock-after', a.after, '--seed', 1, '--report-json', report, '--trip-csv', out / f'{name}.trips.csv']
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    (out / f'{name}.log').write_text(r.stdout + r.stderr)
    if r.returncode or not report.exists():
        print(name, 'FAILED, exit', r.returncode, r.stderr[-500:], flush=True)
        return dict(name=name, failed=True)
    rep = json.loads(report.read_text())
    stuck = rep.get('stuck_lanes', [])
    with open(out / f'{name}.stuck.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['lane', 'x', 'y', 'first', 'last', 'wait', 'cars', 'cause'])
        w.writeheader()
        w.writerows(stuck)
    causes = {}
    for s in stuck:
        k = s['cause'].split(';')[0]
        causes[k] = causes.get(k, 0) + 1
    g = rep.get('gridlock_end') or {}
    row = dict(name=name, fraction=spec['fraction'], inserted=rep['inserted'], arrived=rep['arrived'], teleports=rep['teleports'], collision_incidents=rep['collision_incidents'],
               incidents_by_kind=rep['incidents_by_kind'], stuck_lanes=len(stuck), stuck_causes=causes, worst_stuck_vehicles=rep['gridlock_worst_stuck'], stuck_at_end=g.get('stuck', 0), cycles_at_end=len(g.get('cycles', [])),
               ungranted=rep['ungranted'], dead_end=rep['dead_end'], m_updates=rep['m_updates_per_s'], top=[{k: s[k] for k in ('lane', 'x', 'y', 'wait', 'cars', 'cause')} for s in stuck[:12]])
    print(json.dumps(row), flush=True)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', required=True)
    p.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    p.add_argument('--capacity', type=int, default=300000)
    p.add_argument('--after', type=float, default=180, help='seconds stuck that count; above any signal cycle in these nets')
    p.add_argument('--only', nargs='*')
    a = p.parse_args()
    rows = [gate(n, s, a) for n, s in RUNS.items() if not a.only or n in a.only]
    (Path(a.out) / 'gate.json').write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
