#!/usr/bin/env python3
"""Run coordinated junction cases on the GPU and keep one JSON per case. Usage: runs.py <part>...

Holds /tmp/cars-gpu.lock for at most three minutes of runs, then lets other jobs have a turn. Results land in
<out>/<part>.jsonl; finished cases are not rerun. Parts: smoke capacity demand faults stalls crossover t grid
meter stockholm."""
import argparse, fcntl, itertools, json, os, subprocess, sys, hashlib, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NETS = ROOT / 'research/truth/fig/09-nets'
D8 = ROOT / 'research/truth/fig/d8'
CARS = ROOT / 'target/release/cars'
SAT = {'j1': 7000, 'j2': 11000, 'j3': 15000, 't1': 6000}
TUNED = json.loads((ROOT / 'research/truth/fig/09b-signal-tuning.json').read_text())


def case(net, mix='M', demand=3000.0, seed=0, end=800.0, warm=200.0, level='A', mode='free', human=False, ew=0.5, sig=(60.0, 1.0), **kw):
    return dict(net=net, mix=mix, demand=demand, seed=seed, end=end, warm=warm, level=level, mode=mode, human=human, ew=ew, sig=sig, **kw)


def capacity():
    out = []
    for net, mixes in (('j1', 'TMH'), ('j2', 'TMH'), ('j3', 'M')):
        for mix in mixes:
            for seed in (0, 1, 2, 3):
                out.append(case(net, mix, SAT[net], seed))
                out.append(case(net, mix, SAT[net], seed, mode='signal'))
                out.append(case(net, mix, SAT[net], seed, mode='signal', human=True))
                out.append(case(net, mix, SAT[net], seed, level='B'))
    return out


def tuned(net, mix, ew, d, pol):
    g = TUNED.get(str((net, mix, ew, d, pol)))
    return (g['sig_max'], g['sig_gap']) if g else (30.0, 2.0)


def demand():
    out = []
    for net, mix, ew, ds in (('j2', 'M', 0.5, (600, 1500, 3000, 4200, 5200, 6500)), ('j2', 'H', 0.5, (1500, 3000, 4200, 5200)),
                             ('j2', 'M', 0.8, (1500, 3000, 4200, 5200)), ('j1', 'T', 0.5, (1000, 2500, 4000, 5000))):
        for d in ds:
            for seed in (0, 1):
                out.append(case(net, mix, d, seed, ew=ew))
                out.append(case(net, mix, d, seed, ew=ew, mode='signal', sig=tuned(net, mix, ew, d, 'sig_av')))
                out.append(case(net, mix, d, seed, ew=ew, mode='signal', human=True, sig=tuned(net, mix, ew, d, 'sig_h')))
    return out


def faults():
    out = []
    for d in (3000, 5000):
        b = dict(net='j2', mix='M', demand=d)
        for p in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9):
            out.append(case(**b, loss=p, fault=f'loss{p}'))
        for T in (2.0, 10.0, 30.0):
            out.append(case(**b, blackout=(400.0, 400.0 + T), fault=f'blackout{T}'))
        out.append(case(**b, crash=(400.0, 460.0), fault='crash_awsc'))
        out.append(case(**b, crash=(400.0, 460.0), no_fallback=True, fault='crash_none'))
        out.append(case(**b, chan=1, fault='channel08'))
    for chk in (True, False):
        b = dict(net='j2', mix='M', demand=3000, no_exit_check=not chk)
        out.append(case(**b, exit_fault='B1C1:250:700', fault=f'exit_block_chk{chk}'))
        out.append(case(**b, exit_fault='B1C1:0:800:250', fault=f'exit_cap_chk{chk}'))
    return out


def faults2():
    # Radio gone for good, every message dropped from one tick on. Past 10 s of silence cars use sensing alone.
    out = []
    for d in (3000, 5000):
        b = dict(net='j2', mix='M', demand=d)
        out.append(case(**b, blackout=(400.0, 400.0 + 30.0), fault='blackout30_fallback'))
        out.append(case(**b, blackout=(400.0, 1e9), fault='radio_off'))
        out.append(case(**b, blackout=(400.0, 1e9), no_fallback=True, fault='radio_off_wait'))
        out.append(case(**b, loss=1.0, fault='loss1.0_from_start'))
    return out


def stalls():
    out = []
    for d in (3000, 5000):
        for lvl in 'AB':
            for seed in (0, 1, 2):
                out.append(case('j2', 'M', d, seed, level=lvl, stall=120.0, fault=f'stall{lvl}'))
        out.append(case('j2', 'M', d, 0, stall=120.0, no_perception=True, fault='stallA_noperc'))
    return out


def t_junction():
    out = []
    for d in (1500, 3000, 4500, SAT['t1']):
        for mode, human in (('free', False), ('signal', False), ('signal', True)):
            for seed in (0, 1):
                out.append(case('t1', 'M', d, seed, mode=mode, human=human))
    return out


def grid():
    out = []
    for net, ds in (('grid1', (4000, 9000, 14000)), ('grid2', (8000, 16000, 20000, 24000))):
        for d in ds:
            b = dict(net=net, mix='M', demand=d, end=600.0, warm=150.0, sig=(30.0, 2.0), junctions='grid')
            out.append(case(**b))
            out.append(case(**b, mode='signal'))
            out.append(case(**b, mode='signal', human=True))
            out.append(case(**b, level='B'))
            out.append(case(**b, no_exit_check=True))
    return out


def meter():
    out = []
    for net, d, ns in (('grid2', 24000, (120, 160, 200, 240, 280, 320, 360, 420)), ('grid1', 14000, (60, 80, 100, 120, 140, 170, 200))):
        for n in ns:
            out.append(case(net=net, mix='M', demand=d, end=600.0, warm=150.0, junctions='grid', meter=n))
    return out


def meter_seeds():
    out = []
    for net, d, ns in (('grid2', 24000, (200, 220, 240, 260, 280)), ('grid2', 20000, (240, 280)), ('grid1', 14000, (140, 170, 200))):
        for n in ns:
            for seed in (0, 1, 2):
                out.append(case(net=net, mix='M', demand=d, end=600.0, warm=150.0, junctions='grid', meter=n, seed=seed))
    for net, d in (('grid2', 24000), ('grid2', 20000), ('grid1', 14000)):
        for seed in (1, 2):
            out.append(case(net=net, mix='M', demand=d, end=600.0, warm=150.0, junctions='grid', seed=seed))
            out.append(case(net=net, mix='M', demand=d, end=600.0, warm=150.0, junctions='grid', seed=seed, mode='signal', sig=(30.0, 2.0)))
    return out


def headway():
    # Build spec test 3: one through stream each way, no crossing traffic.
    return [case('j1', 'T', 7000, seed, ew=1.0) for seed in (0, 1)]


def smoke():
    return [case('j1', 'T', 150.0, end=300.0, warm=50.0), case('j2', 'M', 3000.0)]


PARTS = dict(smoke=smoke, capacity=capacity, demand=demand, faults=faults, stalls=stalls, t=t_junction, grid=grid, meter=meter, meter_seeds=meter_seeds, headway=headway, faults2=faults2)


def key(c):
    return hashlib.sha1(json.dumps(c, sort_keys=True).encode()).hexdigest()[:12]


class Gate:
    def __init__(self, budget=180.0):
        self.f = open('/tmp/cars-gpu.lock', 'a')
        self.since = None
        self.budget = budget

    def enter(self):
        if os.environ.get('CARS_ADAPTER') == 'llvmpipe':
            return
        if self.since is not None and time.time() - self.since > self.budget:
            self.leave()
            time.sleep(1.0)
        if self.since is None:
            fcntl.flock(self.f, fcntl.LOCK_EX)
            self.since = time.time()

    def leave(self):
        if self.since is not None:
            fcntl.flock(self.f, fcntl.LOCK_UN)
            self.since = None


GATE = Gate()


def run_case(c, work, cars):
    net = (D8 / 'nets' / f"{c['net']}.net.xml") if c['net'] == 't1' else NETS / f"{c['net']}.net.xml"
    k = key(c)
    routes = work / f'{k}.rou.xml'
    ctl = '--controlled=B1' if c['net'] == 't1' else ''
    cmd = [sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(net), '--out', str(routes), '--demand', str(c['demand']), '--mix', c['mix'],
           '--ew', str(c['ew']), '--seed', str(c['seed']), '--end', str(c['end']), '--type', 'human' if c['human'] else 'av']
    if ctl:
        cmd.append(ctl)
    subprocess.run(cmd, check=True)
    if c.get('junctions') == 'grid':
        js = ','.join(f'{x}{y}' for x in 'BCD' for y in '123')
    else:
        js = 'B1'
    args = ['--net', str(net), '--routes', str(routes), '--end', str(c['end']), '--cj', js, '--cj-warm', str(c['warm']), '--cj-mode', c['mode'],
            '--cj-sig-max', str(c['sig'][0]), '--cj-sig-gap', str(c['sig'][1]), '--seed', str(c['seed'])]
    if c['level'] == 'B':
        args.append('--cj-level-b')
    if c['human']:
        args.append('--cj-human')
    for name, flag in (('loss', '--cj-loss'), ('stall', '--cj-stall-rate'), ('chan', '--cj-chan'), ('meter', '--cj-meter')):
        if c.get(name):
            args += [flag, str(c[name])]
    for name, flag in (('blackout', '--cj-blackout'), ('crash', '--cj-crash')):
        if c.get(name):
            args += [flag, ','.join(map(str, c[name]))]
    if c.get('exit_fault'):
        args += ['--cj-exit-fault', c['exit_fault']]
    for name, flag in (('no_fallback', '--cj-no-fallback'), ('no_exit_check', '--cj-no-exit-check'), ('no_perception', '--cj-no-perception')):
        if c.get(name):
            args.append(flag)
    GATE.enter()
    p = subprocess.run([str(cars), 'av'] + args, capture_output=True, text=True)
    routes.unlink(missing_ok=True)
    if p.returncode:
        return dict(error=p.stderr[-800:])
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parts', nargs='+')
    ap.add_argument('--out', default=str(D8))
    ap.add_argument('--work', default='/tmp/d8/work')
    ap.add_argument('--cars', default=str(CARS))
    ap.add_argument('--retry-errors', action='store_true')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    for part in a.parts:
        path = out / f'{part}.jsonl'
        done = {}
        if path.exists():
            for line in path.read_text().splitlines():
                r = json.loads(line)
                done[r['key']] = r
        jobs = [c for c in PARTS[part]() if key(c) not in done or (a.retry_errors and 'error' in done[key(c)]['result'])]
        print(part, len(jobs), 'to run', flush=True)
        for i, c in enumerate(jobs):
            r = run_case(c, work, a.cars)
            r.pop('profile', None)
            with path.open('a') as f:
                f.write(json.dumps(dict(key=key(c), case=c, result=r)) + '\n')
            print(part, i + 1, len(jobs), c['net'], c['mix'], c['demand'], c['mode'], c['level'], c.get('fault', ''), 'flow', round(r.get('flow', -1)), 'delay', round(r.get('delay', -1), 1), 'overlap', r.get('overlap'), 'inv', r.get('invariant'), r.get('error', '')[:200], flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        GATE.leave()
