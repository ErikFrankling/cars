#!/usr/bin/env python3
"""Planned approach sweeps: old and new on the same arrivals, with the brake metric from a trace.
Usage: plan_runs.py <part>... [--tag x] [--jobs 2]. Results in research/truth/fig/d8/plan/<part><tag>.jsonl.
CPU Vulkan by default (CARS_ADAPTER=llvmpipe); finished cases are not rerun."""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brake

ROOT = Path(__file__).resolve().parents[2]
NETS = ROOT / 'research/truth/fig/09-nets'
D8 = ROOT / 'research/truth/fig/d8'
OUT = D8 / 'plan'
CARS = Path(os.environ.get('CARS_BIN', ROOT / 'target/release/cars'))
SAT = {'j1': 7000, 'j2': 11000, 'j3': 15000, 't1': 6000, 'j150': 11000, 'j280': 11000, 'j500': 11000, 'j1000': 11000}
CELLS = (('j1', 'T'), ('j1', 'M'), ('j1', 'H'), ('j2', 'T'), ('j2', 'M'), ('j2', 'H'), ('j3', 'M'))
MODES = ('off', 'route')


def case(net, mix='M', demand=3000.0, seed=0, plan='full', end=800.0, warm=200.0, trace=True, **kw):
    c = dict(net=net, mix=mix, demand=demand, seed=seed, plan=plan, end=end, warm=warm, trace=trace)
    c.update(kw)
    return c


def capacity():
    return [case(n, m, SAT[n], s, p, trace=False) for n, m in CELLS for s in (0, 1, 2, 3) for p in MODES]


def capacity_quick():
    return [case(n, m, SAT[n], s, p, end=400.0, warm=100.0, trace=False) for n, m in CELLS for s in (0, 1, 2) for p in MODES]


def capacity_quick_new():
    return [case(n, m, SAT[n], s, 'full', end=400.0, warm=100.0, trace=False) for n, m in CELLS for s in (0, 1, 2)]


def demand():
    out = []
    for n, m, ds in (('j2', 'M', (1500, 3000, 4200, 5200)), ('j2', 'T', (1500, 3000, 4200, 5200)), ('j2', 'H', (1500, 3000, 4200)),
                     ('j1', 'T', (1000, 2500, 4000)), ('j1', 'M', (1000, 2000, 3000))):
        for d in ds:
            for s in (0, 1, 2):
                for p in MODES:
                    out.append(case(n, m, d, s, p, end=600.0, warm=150.0))
    return out


def ablation():
    out = []
    for d in (3000, 5200):
        for s in (0, 1, 2):
            for p in ('off', 'profile', 'stable', 'full', 'route', 'cubic', 'dr'):
                out.append(case('j2', 'M', d, s, p, end=600.0, warm=150.0))
    for s in (0, 1, 2):
        for p in ('off', 'profile', 'stable', 'full', 'route', 'cubic', 'dr'):
            out.append(case('j2', 'M', SAT['j2'], s, p, end=500.0, warm=150.0, trace=False))
    return out


def faults():
    out = []
    for d in (3000, 5000):
        for p in MODES:
            b = dict(net='j2', mix='M', demand=d, plan=p, end=800.0, warm=200.0, trace=False)
            for loss in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0):
                out.append(case(**b, loss=loss, fault=f'loss{loss}'))
            for T in (2.0, 10.0, 30.0):
                out.append(case(**b, blackout=(400.0, 400.0 + T), fault=f'blackout{T}'))
            out.append(case(**b, blackout=(400.0, 1e9), fault='radio_off'))
            out.append(case(**b, crash=(400.0, 460.0), fault='crash_awsc'))
            out.append(case(**b, crash=(400.0, 460.0), no_fallback=True, fault='crash_none'))
            out.append(case(**b, chan=1, fault='channel08'))
    for p in MODES:
        for chk in (True, False):
            b = dict(net='j2', mix='M', demand=3000, plan=p, end=800.0, warm=200.0, trace=False, no_exit_check=not chk)
            out.append(case(**b, exit_fault='B1C1:250:700', fault=f'exit_block_chk{chk}'))
            out.append(case(**b, exit_fault='B1C1:0:800:250', fault=f'exit_cap_chk{chk}'))
        for d in (3000, 5000):
            for lvl in 'AB':
                for s in (0, 1, 2):
                    out.append(case('j2', 'M', d, s, p, trace=False, stall=120.0, level=lvl, fault=f'stall{lvl}'))
    return out


def loss():
    return [case('j2', 'M', d, s, p, end=600.0, warm=150.0, loss=x, fault=f'loss{x}') for d in (3000, 5200) for s in (0, 1) for p in MODES for x in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5)]


def length():
    out = []
    for n in ('j150', 'j280', 'j500', 'j1000'):
        for d in (3000, 5200):
            for s in (0, 1, 2):
                for p in MODES:
                    out.append(case(n, 'M', d, s, p, end=600.0 + 80.0 * (n == 'j1000'), warm=150.0 + 80.0 * (n == 'j1000')))
        for s in (0, 1):
            for p in MODES:
                out.append(case(n, 'M', SAT[n], s, p, end=500.0, warm=150.0, trace=False))
    return out


def timing():
    out = []
    for s in (0, 1):
        for x in (0.0, 0.1, 0.3, 1.0):
            out.append(case('j2', 'M', 3000, s, end=600.0, warm=150.0, pos_err=x, fault=f'pos{x}'))
            out.append(case('j2', 'M', SAT['j2'], s, end=500.0, warm=150.0, trace=False, pos_err=x, fault=f'pos{x}'))
        for x in (0.001, 0.01, 0.05, 0.1):
            out.append(case('j2', 'M', 3000, s, end=600.0, warm=150.0, clock_err=x, fault=f'clock{x}'))
            out.append(case('j2', 'M', SAT['j2'], s, end=500.0, warm=150.0, trace=False, clock_err=x, fault=f'clock{x}'))
        for m in (0.3, 0.2, 0.1, 0.05, 0.02, 0.0):
            out.append(case('j2', 'M', 3000, s, end=600.0, warm=150.0, margin=m, fault=f'margin{m}'))
            out.append(case('j2', 'M', SAT['j2'], s, end=500.0, warm=150.0, trace=False, margin=m, fault=f'margin{m}'))
            out.append(case('j2', 'M', SAT['j2'], s, end=500.0, warm=150.0, trace=False, margin=m, pos_err=0.3, fault=f'margin{m}pos0.3'))
    return out


GRID_JS = ','.join(f'{x}{y}' for x in 'BCD' for y in '123')


def grid():
    out = []
    for net, ds in (('grid1', (4000, 9000, 14000)), ('grid2', (8000, 16000, 20000, 24000))):
        for d in ds:
            for s in (0, 1, 2):
                for p in MODES:
                    out.append(case(net, 'M', d, s, p, end=600.0, warm=150.0, trace=False, junctions=GRID_JS))
    return out


def capacity_factors():
    return [case(n, m, SAT[n], s, p, trace=False) for n, m in CELLS for s in (0, 1, 2, 3) for p in ('stable', 'dr')]


def route_cap():
    return [case(n, m, SAT[n], s, 'route', trace=False) for n, m in CELLS for s in (0, 1, 2, 3)]


def route_grid():
    out = []
    for net, ds in (('grid1', (4000, 9000, 14000)), ('grid2', (8000, 16000, 20000, 24000))):
        for d in ds:
            for s in (0, 1, 2, 3, 4, 5):
                out.append(case(net, 'M', d, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS))
                out.append(case(net, 'M', d, s, 'off', end=600.0, warm=150.0, trace=False, junctions=GRID_JS))
    return out


def route_faults():
    # Message loss and stalls on the grid with planning across junctions.
    out = []
    for s in (0, 1, 2):
        for loss in (0.1, 0.3, 0.5, 0.7):
            out.append(case('grid2', 'M', 16000, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, loss=loss, fault=f'loss{loss}'))
        out.append(case('grid2', 'M', 16000, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, stall=120.0, level='B', fault='stallB'))
        out.append(case('grid2', 'M', 16000, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, stall=120.0, fault='stallA'))
        out.append(case('grid2', 'M', 16000, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, chan=1, fault='channel08'))
        out.append(case('grid2', 'M', 16000, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, blackout=(300.0, 330.0), fault='blackout30'))
    return out


def gate_route():
    # The margin on the final design: every cell, 8 seeds, with and without position error, and loads where a rare contact shows.
    out = []
    for s in range(6):
        for n, m in CELLS:
            for mg in (0.3, 0.2):
                for pos in (0.0, 0.3):
                    out.append(case(n, m, SAT[n], s, 'route', trace=False, margin=mg, pos_err=pos, fault=f'm{mg}p{pos}'))
        for d in (3000, 5200):
            for mg in (0.3, 0.2):
                for pos in (0.0, 0.3, 1.0):
                    out.append(case('j2', 'M', d, s, 'route', end=600.0, warm=150.0, trace=False, margin=mg, pos_err=pos, fault=f'm{mg}p{pos}'))
        for net, d in (('grid2', 24000), ('grid2', 16000), ('grid1', 14000)):
            for mg in (0.3, 0.2):
                out.append(case(net, 'M', d, s, 'route', end=600.0, warm=150.0, trace=False, junctions=GRID_JS, margin=mg, fault=f'm{mg}'))
    return out


def capacity_chan():
    return [case(n, m, SAT[n], s, p, trace=False, chan=1, fault='channel08') for n, m in (('j2', 'M'), ('j2', 'H'), ('j2', 'T'), ('j1', 'M'), ('j3', 'M')) for s in (0, 1) for p in MODES]


def gate():
    # Enough seeds to trust a margin: the seven capacity cells and the loads where a rare contact would show.
    out = []
    for s in range(8):
        for n, m in CELLS:
            out.append(case(n, m, SAT[n], s, 'off', trace=False))
            for mg in (0.3, 0.2):
                for pos in (0.0, 0.3):
                    out.append(case(n, m, SAT[n], s, 'full', trace=False, margin=mg, pos_err=pos, fault=f'm{mg}p{pos}'))
        for d in (3000, 5200):
            for mg in (0.3, 0.2):
                for pos in (0.0, 0.3, 1.0):
                    out.append(case('j2', 'M', d, s, 'full', end=600.0, warm=150.0, trace=False, margin=mg, pos_err=pos, fault=f'm{mg}p{pos}'))
    return out


def lateral():
    # What the corner speed buys, safe or not: peak lateral 4.0 with apex release against the old table and the map.
    out = []
    for s in (0, 1):
        for n, m in CELLS:
            out.append(case(n, m, SAT[n], s, 'route', trace=False, peak=4.0, fault='peak4'))
            out.append(case(n, m, SAT[n], s, 'route', trace=False, peak=-1.0, fault='old_table'))
            out.append(case(n, m, SAT[n], s, 'route', trace=False, peak=-1.0, a_lat=3.0, fault='alat3'))
            out.append(case(n, m, SAT[n], s, 'route', trace=False, peak=-1.0, a_lat=5.5, fault='alat5.5'))
    return out


def grid_meter():
    out = []
    for net, d, ns in (('grid2', 24000, (200, 240)), ('grid1', 14000, (140,))):
        for n in ns:
            for s in (0, 1, 2):
                for p in MODES:
                    out.append(case(net, 'M', d, s, p, end=600.0, warm=150.0, trace=False, junctions=GRID_JS, meter=n))
    return out


def smoke():
    return [case('j2', 'M', 3000, 0, 'full', end=200.0, warm=60.0)]


PARTS = dict(gate_route=gate_route, route_cap=route_cap, route_grid=route_grid, route_faults=route_faults, gate=gate, lateral=lateral, capacity_factors=capacity_factors, capacity_chan=capacity_chan, smoke=smoke, grid=grid, grid_meter=grid_meter, capacity=capacity, capacity_quick=capacity_quick, capacity_quick_new=capacity_quick_new, demand=demand, ablation=ablation, faults=faults, loss=loss, length=length, timing=timing)


def key(c):
    return hashlib.sha1(json.dumps(c, sort_keys=True).encode()).hexdigest()[:12]


def net_path(name):
    p = D8 / 'nets' / f'{name}.net.xml'
    return p if p.exists() else NETS / f'{name}.net.xml'


def run_case(c, work):
    net = net_path(c['net'])
    k = key(c)
    routes = Path(work) / f'{k}.rou.xml'
    subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(net), '--out', str(routes), '--demand', str(c['demand']), '--mix', c['mix'],
                    '--seed', str(c['seed']), '--end', str(c['end'])], check=True)
    args = ['--net', str(net), '--routes', str(routes), '--end', str(c['end']), '--cj', c.get('junctions', 'B1'), '--cj-warm', str(c['warm']), '--seed', str(c['seed']), '--cj-plan', c['plan']]
    for name, flag in (('loss', '--cj-loss'), ('stall', '--cj-stall-rate'), ('chan', '--cj-chan'), ('meter', '--cj-meter'), ('pos_err', '--cj-pos-err'), ('clock_err', '--cj-clock-err'),
                       ('margin', '--cj-margin'), ('plan_b', '--cj-plan-b'), ('freeze', '--cj-plan-freeze'), ('firm', '--cj-firm'), ('slack', '--cj-plan-slack'), ('up', '--cj-plan-up'), ('a_lat', '--cj-a-lat')):
        if c.get(name) is not None and (name in ('margin',) or c.get(name)):
            args += [flag, str(c[name])]
    if c.get('peak') is not None:
        args += ['--cj-plan-peak', str(max(c['peak'], 0.0))]
    for name, flag in (('blackout', '--cj-blackout'), ('crash', '--cj-crash')):
        if c.get(name):
            args += [flag, ','.join(map(str, c[name]))]
    if c.get('exit_fault'):
        args += ['--cj-exit-fault', c['exit_fault']]
    for name, flag in (('no_fallback', '--cj-no-fallback'), ('no_exit_check', '--cj-no-exit-check'), ('no_perception', '--cj-no-perception')):
        if c.get(name):
            args.append(flag)
    if c.get('level') == 'B':
        args.append('--cj-level-b')
    if c.get('trace'):
        args += ['--trace', f"{c['warm']},{c['end']}"]
    log = Path(work) / f'{k}.log'
    with log.open('w') as err:
        p = subprocess.run([str(CARS), 'av'] + args, stdout=subprocess.PIPE, stderr=err, text=True, timeout=3000)
    routes.unlink(missing_ok=True)
    if p.returncode:
        tail = log.read_text()[-800:]
        log.unlink(missing_ok=True)
        return dict(error=tail)
    r = json.loads(p.stdout.strip().splitlines()[-1])
    r.pop('profile', None)
    r.pop('ids', None)
    if c.get('trace'):
        r['brake'] = brake.analyse(str(net), str(log))
    log.unlink(missing_ok=True)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parts', nargs='+')
    ap.add_argument('--tag', default='')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--plan', default='', help='only this plan mode, and off when "+off" follows')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    os.makedirs('/tmp/d8', exist_ok=True)
    work = tempfile.mkdtemp(prefix='plan_', dir='/tmp/d8')
    for part in a.parts:
        path = OUT / f'{part}{a.tag}.jsonl'
        done = {}
        if path.exists():
            for line in path.read_text().splitlines():
                r = json.loads(line)
                if 'error' not in r['result']:
                    done[r['key']] = r
            path.write_text(''.join(json.dumps(r) + '\n' for r in done.values()))
        jobs = [c for c in PARTS[part]() if key(c) not in done]
        print(part, len(jobs), 'to run', flush=True)
        with cf.ThreadPoolExecutor(a.jobs) as ex:
            futs = {ex.submit(run_case, c, work): c for c in jobs}
            for i, f in enumerate(cf.as_completed(futs)):
                c = futs[f]
                try:
                    r = f.result()
                except Exception as e:
                    r = dict(error=str(e))
                with path.open('a') as fp:
                    fp.write(json.dumps(dict(key=key(c), case=c, result=r)) + '\n')
                print(part, i + 1, len(jobs), c['net'], c['mix'], c['demand'], c['plan'], c['seed'], c.get('fault', ''), 'flow', round(r.get('flow', -1)), 'delay', round(r.get('delay', -1), 1), 'ov', r.get('overlap'), r.get('error', '')[-200:], flush=True)


if __name__ == '__main__':
    main()
