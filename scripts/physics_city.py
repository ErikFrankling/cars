#!/usr/bin/env python3
"""City mornings, before and after physical mode: collisions, teleports, gridlock, speed.

    python3 scripts/physics_city.py stockholm berlin --out DIR [--cars BIN] [--baseline BIN]

"Before" is the SUMO-parity kernel with its usual teleport settings. Every run holds the GPU lock,
unless CARS_GPU_HELD says the caller already does.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('/home/erikf/projects/personal/cars-data')
CITIES = {
    'stockholm': dict(net=DATA / 'truth/maps/builds/v5_inventory/net.xml', routes=DATA / 'physics/stockholm/morning.repaired.rou.xml.gz'),
    'berlin': dict(net=DATA / 'best/berlin.net.xml', routes=DATA / 'best/berlin.rou.gz'),
}
LOCK = [] if os.environ.get('CARS_GPU_HELD') else ['flock', '/tmp/cars-gpu.lock']


def speed_of(text):
    m = re.search(r'wall ([0-9.]+)s, ([0-9.]+) M updates/s, speed ([0-9.]+), running ([0-9.]+), trips done (\d+), duration ([0-9.]+)', text)
    return dict(wall=float(m[1]), m_updates=float(m[2]), speed=float(m[3]), running=float(m[4]), trips=int(m[5]), duration=float(m[6])) if m else {}


def run(cmd, log):
    t = time.time()
    r = subprocess.run(list(map(str, [*LOCK, *cmd])), capture_output=True, text=True)
    Path(log).write_text(r.stdout + r.stderr)
    if r.returncode:
        print(f'run failed, exit {r.returncode}: see {log}', flush=True)
    return r.stdout + r.stderr, time.time() - t, r.returncode


def city(name, a):
    c = CITIES[name]
    out = Path(a.out) / name
    out.mkdir(parents=True, exist_ok=True)
    common = ['--net', c['net'], '--routes', c['routes'], '--dt', 1, '--begin', a.begin, '--capacity', a.capacity, '--seed', 1]
    result = {}
    text, wall, code = run([a.baseline, 'run', *common, '--end', a.end, '--time-to-teleport', 300], out / 'before.log')
    m = re.search(r'lane changes (\d+), teleports (\d+), collisions (\d+) \(lane change (\d+), junction (\d+), lane start (\d+), other (\d+)\)', text)
    result['before'] = dict(speed_of(text), exit=code, **({'lane_changes': int(m[1]), 'teleports': int(m[2]), 'collisions': int(m[3])} if m else {}))
    print(name, 'before', result['before'], flush=True)
    text, wall, code = run([a.cars, 'run', *common, '--end', a.end, '--detect-every', 0, '--report-json', out / 'nodetect.json'], out / 'nodetect.log')
    result['physical_no_detector'] = dict(speed_of(text), exit=code)
    print(name, 'physical, detector off', result['physical_no_detector'], flush=True)
    text, wall, code = run([a.cars, 'run', *common, '--end', a.end, '--report-json', out / 'after.json', '--phys-json', out / 'phys.json', '--trip-csv', out / 'trips.csv',
                            '--fcd', out / 'fcd.csv', '--fcd-begin', a.window, '--fcd-interval', 1, '--profile-at', a.window - 60, '--diagnose-at', a.end - 1], out / 'after.log')
    # FCD writing and readback slow this run down, so its speed is not the figure to quote.
    result['physical'] = dict(speed_of(text), exit=code)
    if (out / 'after.json').exists():
        rep = json.loads((out / 'after.json').read_text())
        result['physical'].update({k: rep.get(k) for k in ('collision_incidents', 'contact_samples', 'incidents_by_kind', 'teleports', 'lane_changes', 'shadows', 'shadow_refused', 'cert_floor', 'ungranted', 'dead_end', 'no_brake', 'denied', 'lc_refused_room', 'inserted', 'arrived', 'gridlock_worst_stuck', 'energy')})
        g = rep.get('gridlock_end') or {}
        result['physical']['gridlock_end'] = dict(stuck=g.get('stuck', 0), cycles=len(g.get('cycles', [])), causes=g.get('causes', {}), first_cycles=g.get('cycles', [])[:5], worst=g.get('worst_heads', [])[:5])
        result['physical']['worst_incidents'] = rep.get('worst_incidents', [])[:15]
    print(name, 'physical', json.dumps(result['physical'])[:1500], flush=True)
    if (out / 'fcd.csv').exists() and not a.no_qa:
        q = subprocess.run([sys.executable, str(ROOT / 'scripts/physics_qa.py'), '--net', c['net'], '--fcd', out / 'fcd.csv', '--log', out / 'after.log', '--phys', out / 'phys.json', '--report', out / 'after.json', '--trips', out / 'trips.csv', '--out', out / 'qa'], capture_output=True, text=True)
        result['qa'] = dict(exit=q.returncode, last=(q.stdout.strip().splitlines() or [''])[-1][:600], err=q.stderr[-1500:] if q.returncode not in (0, 1) else '')
        print(name, 'qa', result['qa'], flush=True)
    (out / 'summary.json').write_text(json.dumps(result, indent=1))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('names', nargs='+', choices=list(CITIES))
    p.add_argument('--out', required=True)
    p.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    p.add_argument('--baseline', default=str(DATA / 'physics/cars-baseline-69cf836'))
    p.add_argument('--begin', type=float, default=25200)
    p.add_argument('--end', type=float, default=29100)
    p.add_argument('--window', type=float, default=28800, help='start of the second-by-second trajectories')
    p.add_argument('--capacity', type=int, default=300000)
    p.add_argument('--no-qa', action='store_true')
    a = p.parse_args()
    for name in a.names:
        city(name, a)


if __name__ == '__main__':
    main()
