#!/usr/bin/env python3
"""City runs with each human rule on and off, teleports off: what gets stuck, where, and at what cost.

    python3 scripts/human_city.py berlin-morning stockholm --cases base,humans,no-courtesy --out DIR [--cars BIN]

Takes the GPU lock once per group of cases. Writes one JSON and one line of results per run, and one table.
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('/home/erikf/projects/personal/cars-data')
STOCKHOLM = dict(net=DATA / 'truth/maps/builds/v5_inventory/net.xml', routes=DATA / 'physics/stockholm/morning.repaired.rou.xml.gz')
BERLIN = dict(net=DATA / 'best/berlin.net.xml', routes=DATA / 'best/berlin.rou.gz')
PLACES = {
    'berlin-morning': dict(BERLIN, begin=21600, end=32400, capacity=350000, extra=[]),
    'berlin-day': dict(BERLIN, begin=0, end=86400, capacity=450000, extra=[]),
    'stockholm': dict(STOCKHOLM, begin=25200, end=32400, capacity=250000, extra=['--region', 'sweden']),
}
RULES = ('courtesy', 'shrink', 'offset', 'anticipate', 'miss', 'gate', 'yellow')
CASES = {
    'base': (),
    'humans': ('--humans',),
    'sumo': ('--sumo-compat',),
}
for r in RULES:
    CASES[f'no-{r}'] = ('--humans', '--human-off', r)
for v in (30, 60, 240):
    CASES[f'tmiss{v}'] = ('--humans', '--tune', f't_miss={v}')
for v in (0, 0.2, 0.8, 1.0):
    CASES[f'coop{v}'] = ('--humans', '--tune', f'cooperation={v}')
for v in (0.5, 1.0):
    CASES[f'comply{v}'] = ('--humans', '--tune', f'exit_comply={v}')
CASES['no-arbiter'] = ('--humans', '--tune', 'arbiter=0')
CASES['no-exit-clear'] = ('--humans', '--tune', 'exit_clear=0')
CASES['no-cert'] = ('--humans', '--tune', 'certificate=0')
CASES['frac05'] = ('--humans', '--demand-fraction', '0.5')
CASES['frac01'] = ('--humans', '--demand-fraction', '0.1')


def one(place, case, a):
    p = PLACES[place]
    out = Path(a.out) / place
    out.mkdir(parents=True, exist_ok=True)
    extra = list(p['extra']) if case != 'sumo' and case != 'base' else []
    cmd = [a.cars, 'run', '--net', p['net'], '--routes', p['routes'], '--dt', a.dt, '--begin', p['begin'], '--end', p['end'], '--capacity', p['capacity'], '--seed', a.seed,
           '--report-json', out / f'{case}.json', '--trip-csv', out / f'{case}.trips.csv', *extra, *CASES[case]]
    if case != 'sumo':
        cmd += ['--time-to-teleport', '0']
    t = time.time()
    # The PC's load guard kills a big job when the desktop stalls. Just try again.
    for _ in range(4):
        r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
        if r.returncode != -15:
            break
        time.sleep(60)
    (out / f'{case}.log').write_text(r.stdout + r.stderr)
    row = dict(place=place, case=case, exit=r.returncode, wall=round(time.time() - t, 1))
    text = r.stdout + r.stderr
    m = re.search(r'wall ([0-9.]+)s, ([0-9.]+) M updates/s, speed ([0-9.]+), running ([0-9.]+), trips done (\d+), duration ([0-9.]+), wait ([0-9.]+), loss ([0-9.]+)', text)
    if m:
        row.update(m_updates=float(m[2]), speed=float(m[3]), running=float(m[4]), trips=int(m[5]), duration=float(m[6]), wait=float(m[7]), loss=float(m[8]))
    m = re.search(r'teleports jam (\d+) yield (\d+) wrong lane (\d+)', text)
    if m:
        row.update(stuck_jam=int(m[1]), stuck_yield=int(m[2]), stuck_gap=int(m[3]))
    j = out / f'{case}.json'
    if j.exists() and case != 'sumo':
        rep = json.loads(j.read_text())
        g = rep.get('gridlock_end') or {}
        row.update(collisions=rep.get('collision_incidents'), teleports=rep.get('teleports'), lane_changes=rep.get('lane_changes'), cert_floor=rep.get('cert_floor'), stuck_end=g.get('stuck', 0), stuck_worst=rep.get('gridlock_worst_stuck'), cycles=len(g.get('cycles', [])), causes=g.get('causes'), by_kind=rep.get('incidents_by_kind'), arrived=rep.get('arrived'), inserted=rep.get('inserted'), humans=rep.get('humans'), like=rep.get('stuck_like_teleports'))
    print(json.dumps(row), flush=True)
    with (Path(a.out) / 'table.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('places', nargs='+', choices=list(PLACES))
    p.add_argument('--cases', default='base,humans')
    p.add_argument('--out', required=True)
    p.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    p.add_argument('--dt', type=float, default=1.0)
    p.add_argument('--seed', type=int, default=1)
    a = p.parse_args()
    for place in a.places:
        for case in a.cases.split(','):
            one(place, case, a)


if __name__ == '__main__':
    main()
