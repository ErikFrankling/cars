#!/usr/bin/env python3
"""The runs behind section 09's tables. Usage: ci_runs.py <part>. Parts: crossover capacity tune demand faults stalls network sens.
Each part is small enough for two threads and a few minutes. Set PYTHONHASHSEED=0. ci_sweep.py defines the shared helpers."""
import ast, csv, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_model as M
import ci_sweep as S

FIG = Path(__file__).resolve().parents[1] / 'fig'
CASES = [('j2', 'M', 0.5, (600, 1500, 3000, 4200, 5200, 6500)), ('j2', 'H', 0.5, (1500, 3000, 4200, 5200)),
         ('j2', 'M', 0.8, (1500, 3000, 4200, 5200)), ('j1', 'T', 0.5, (1000, 2500, 4000, 5000))]


def capacity():
    out = []
    for j in S.capacity():
        l = j[0]
        case = l['net'] + l['mix']
        main = ('sig_h', 'sig_av', 'ges', 'poll')
        if l['seed'] == 0 and case in ('j1T', 'j2M'):
            out.append(j)
        elif l['seed'] == 0 and l['policy'] in main + ('fcfs_conf',):
            out.append(j)
        elif l['seed'] == 1 and l['policy'] in main:
            out.append(j)
    return out


def tune_one(a):
    net, mix, ew, d, pol = a
    best, bv = None, 1e18
    for g in S.SIG_GRID:
        r = M.run_cfg(dict(S.base(net, mix, policy=pol, demand=d, seed=101, ew_share=ew), end=350.0, warm=100.0, audit=False, **g))
        if r['delay'] < bv:
            best, bv = g, r['delay']
    return a, best


def tune():
    keys = [(n, m, e, d, p) for n, m, e, ds in CASES for d in ds for p in ('sig_av', 'sig_h')]
    with Pool(2) as p:
        out = p.map(tune_one, keys)
    (FIG / '09b-signal-tuning.json').write_text(json.dumps({str(k): v for k, v in out}, indent=0))
    return []


def demand():
    tuned = {ast.literal_eval(k): v for k, v in json.loads((FIG / '09b-signal-tuning.json').read_text()).items()}
    out = []
    for net, mix, ew, ds in CASES:
        for d in ds:
            for pol in ('sig_h', 'sig_av', 'poll', 'fcfs_conf', 'ges'):
                for seed in (0, 1):
                    g = tuned[(net, mix, ew, d, pol)] if pol.startswith('sig') else {}
                    out.append((dict(part='demand', net=net, mix=mix, ew=ew, demand=d, policy=pol, seed=seed), S.base(net, mix, policy=pol, demand=d, seed=seed, ew_share=ew, **g)))
    return out


def faults():
    out = []
    for d in (3000, 5000):
        b = S.base('j2', 'M', policy='ges', seed=0, demand=d)
        c = dict(part='faults', demand=d, policy='ges', level='A', seed=0, chk=True)
        for p in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9):
            out.append((dict(c, fault='loss', x=p), dict(b, p_loss=p)))
        for T in (2.0, 10.0, 30.0):
            out.append((dict(c, fault='blackout', x=T), dict(b, blackout=(400.0, 400.0 + T))))
        out.append((dict(c, fault='crash_awsc', x=60.0), dict(b, crash=(400.0, 460.0), fallback='awsc')))
        out.append((dict(c, fault='crash_none', x=60.0), dict(b, crash=(400.0, 460.0), fallback='none')))
    for chk in (True, False):
        b = S.base('j2', 'M', policy='ges', seed=0, demand=3000, exit_check=chk, ponr=chk)
        c = dict(part='faults', demand=3000, policy='ges', level='A', seed=0, chk=chk)
        out.append((dict(c, fault='exit_block', x=450.0), dict(b, exit_block=(250.0, 700.0, 'B1C1'))))
        out.append((dict(c, fault='exit_cap', x=250.0), dict(b, exit_cap=('B1C1', 250.0))))
    return out


def stalls():
    out = []
    for d in (3000, 5000):
        for lvl in 'AB':
            for seed in (0, 1, 2):
                out.append((dict(part='stall', demand=d, level=lvl, seed=seed, perception=True), dict(S.base('j2', 'M', policy='ges', seed=seed, demand=d, level=lvl), stall_rate=120.0, stall_T=15.0)))
        out.append((dict(part='stall', demand=d, level='A', seed=0, perception=False), dict(S.base('j2', 'M', policy='ges', seed=0, demand=d), stall_rate=120.0, stall_T=15.0, perception=False)))
    return out


def network():
    out = []
    for net, ds in (('grid1', (4000, 9000, 14000)), ('grid2', (8000, 16000, 20000, 24000))):
        for d in ds:
            for pol, lvl, chk in (('sig_av', 'A', True), ('sig_h', 'A', True), ('ges', 'A', True), ('ges', 'B', True), ('ges', 'A', False)):
                out.append((dict(part='network', net=net, demand=d, policy=pol, level=lvl, chk=chk), dict(net=net, left=0.1, right=0.1, end=600.0, warm=150.0, policy=pol, level=lvl, demand=d, seed=0, exit_check=chk, ponr=chk, sig_max=30.0, sig_gap=2.0)))
    return out


def sens():
    out = []
    grid = dict(tau=(0.6, 1.0, 1.5), m_t=(0.15, 0.5, 0.8), m_lat=(0.25, 1.0), a_lat=(1.5, 5.5), tick=(0.25, 1.0), T_firm=(2.0, 8.0), A_max=(30.0, 300.0), a=(1.5, 3.5), K_lane=(2, 12))
    for k, vals in grid.items():
        for v in vals:
            out.append((dict(part='sens', param=k, value=v, policy='ges'), S.base('j2', 'M', policy='ges', demand=11000, seed=0, **{k: v})))
    out.append((dict(part='sens', param='baseline', value=0, policy='ges'), S.base('j2', 'M', policy='ges', demand=11000, seed=0)))
    for tau in (0.6, 1.0, 1.5):
        out.append((dict(part='sens', param='tau', value=tau, policy='sig_av'), S.base('j2', 'M', policy='sig_av', demand=11000, seed=0, tau=tau, sig_max=60.0, sig_gap=1.0)))
    out.append((dict(part='sens', param='baseline', value=0, policy='sig_av'), S.base('j2', 'M', policy='sig_av', demand=11000, seed=0, sig_max=60.0, sig_gap=1.0)))
    return out


PARTS = dict(crossover=S.crossover, capacity=capacity, tune=tune, demand=demand, faults=faults, stalls=stalls, network=network, sens=sens)

if __name__ == '__main__':
    part = sys.argv[1]
    jobs = PARTS[part]()
    if jobs:
        t0 = time.time()
        keys = []
        for j in jobs:
            keys += [k for k in j[0] if k not in keys]
        path = FIG / f'09b-{part}.csv'
        # resume: rows already on disk are kept
        done = set()
        if path.exists():
            with path.open() as f:
                done = {tuple(r[k] for k in keys) for r in csv.DictReader(f) if r.get('flow')}
        jobs = [j for j in jobs if tuple(str(j[0].get(k, '')) for k in keys) not in done]
        fresh = not done
        with Pool(2) as p, path.open('w' if fresh else 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=keys + S.KEYS + ['error'])
            if fresh:
                w.writeheader()
            for label, over, r in p.imap_unordered(S.job, jobs):
                row = dict(label)
                row.update({k: r.get(k, '') for k in S.KEYS})
                row['error'] = r.get('error', '')
                w.writerow(row)
                f.flush()
        print('done', part, len(jobs), round(time.time() - t0))
