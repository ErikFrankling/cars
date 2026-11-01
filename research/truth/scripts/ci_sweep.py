#!/usr/bin/env python3
"""Shared helpers and a wider sweep for ci_model.py. The published tables come from ci_runs.py; the wider
parts here (faults, sens, network, demand) were written for the homelab worker and were not run, because its queue stayed full."""
import csv, itertools, json, sys, time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_model as M

FIG = Path(__file__).resolve().parents[1] / 'fig'
MIX = {'T': (0.0, 0.0), 'M': (0.1, 0.1), 'H': (0.25, 0.1)}
KEYS = 'flow offered delay stops p95 p99 trip pending growth overlap invariant late late_committed aborts ponr_abort rms_a peakq grants err_p99 stalls box_block wall'.split()
SIG_GRID = [dict(sig_max=m, sig_gap=g) for m, g in ((20.0, 1.0), (30.0, 1.0), (30.0, 2.0), (45.0, 1.0), (60.0, 1.0), (60.0, 2.0))]


def job(a):
    label, over = a
    try:
        r = M.run_cfg(over)
    except Exception as e:  # keep the sweep alive and report the failure in the csv
        r = {'error': repr(e)}
    return label, over, r


def base(net, mix, **k):
    l, r = MIX[mix]
    return dict(net=net, left=l, right=r, end=800.0, warm=200.0, **k)


def capacity():
    SAT = {'j1': 7000, 'j2': 11000, 'j3': 15000}
    out = []
    for net, mixes in (('j1', 'TMH'), ('j2', 'TMH'), ('j3', 'M')):
        for mix in mixes:
            for pol, lvl in (('sig_h', 'A'), ('sig_av', 'A'), ('poll', 'A'), ('fcfs_box', 'A'), ('fcfs_conf', 'A'), ('fcfs_scalar', 'A'), ('ges', 'A'), ('wspt', 'A'),
                             ('poll', 'B'), ('fcfs_conf', 'B'), ('ges', 'B'), ('wspt', 'B')):
                for seed in (0, 1):
                    out.append((dict(part='capacity', net=net, mix=mix, policy=pol, level=lvl, seed=seed),
                                base(net, mix, policy=pol, level=lvl, seed=seed, demand=SAT[net], sig_max=60.0, sig_gap=1.0)))
    return out


def tune_signal(net, mix, pol, demand, ew=0.5):
    # 8 settings on one training seed that the evaluation never uses
    best, bv = None, 1e18
    for g in SIG_GRID:
        r = M.run_cfg(dict(base(net, mix, policy=pol, demand=demand, seed=101, ew_share=ew), end=400.0, warm=100.0, audit=False, **g))
        if r['delay'] < bv:
            best, bv = g, r['delay']
    return best


def demand_curve_jobs():
    D = {'j1': (400, 1000, 1800, 2500, 3200, 4000), 'j2': (600, 1500, 3000, 4200, 5200, 6500)}
    out = []
    for net, ew, mixes in (('j1', 0.5, 'TM'), ('j2', 0.5, 'MH'), ('j2', 0.8, 'M')):
        for mix in mixes:
            for d in D[net]:
                for pol in ('sig_h', 'sig_av', 'poll', 'fcfs_conf', 'ges'):
                    for seed in (0, 1):
                        out.append((dict(part='demand', net=net, mix=mix, ew=ew, demand=d, policy=pol, seed=seed),
                                    base(net, mix, policy=pol, demand=d, seed=seed, ew_share=ew)))
    return out


def tune_one(a):
    return a, tune_signal(*a)


def demand():
    jobs = demand_curve_jobs()
    keys = sorted({(j[1]['net'], [m for m, v in MIX.items() if v == (j[1]['left'], j[1]['right'])][0], j[1]['policy'], j[1]['demand'], j[1]['ew_share'])
                   for j in jobs if j[1]['policy'].startswith('sig')})
    with Pool(PROCS) as p:
        tuned = dict(p.map(tune_one, keys))
    (FIG / '09b-signal-tuning.json').write_text(json.dumps({str(k): v for k, v in tuned.items()}, indent=0))
    for label, over in jobs:
        if over['policy'].startswith('sig'):
            mix = label['mix']
            over.update(tuned[(over['net'], mix, over['policy'], over['demand'], over['ew_share'])])
    return jobs


def faults():
    out = []
    for d in (3000, 5000):
        for pol, lvl in (('ges', 'A'), ('poll', 'A'), ('ges', 'B')):
            for seed in (0, 1):
                common = dict(part='faults', demand=d, policy=pol, level=lvl, seed=seed)
                b = base('j2', 'M', policy=pol, level=lvl, seed=seed, demand=d)
                for p in (0.0, 0.01, 0.1, 0.3, 0.5, 0.7, 0.9):
                    out.append((dict(common, fault='loss', x=p), dict(b, p_loss=p)))
                for T in (2.0, 10.0, 30.0):
                    out.append((dict(common, fault='blackout', x=T), dict(b, blackout=(400.0, 400.0 + T))))
                for T in (10.0, 60.0):
                    out.append((dict(common, fault='crash_awsc', x=T), dict(b, crash=(400.0, 400.0 + T), fallback='awsc')))
                    out.append((dict(common, fault='crash_none', x=T), dict(b, crash=(400.0, 400.0 + T), fallback='none')))
                out.append((dict(common, fault='stall', x=60.0), dict(b, stall_rate=60.0, stall_T=15.0)))
    for d in (3000,):
        for seed in (0, 1):
            for chk in (True, False):
                b = base('j2', 'M', policy='ges', seed=seed, demand=d, exit_check=chk)
                c = dict(part='faults', demand=d, policy='ges', level='A', seed=seed, chk=chk)
                out.append((dict(c, fault='exit_block', x=450.0), dict(b, exit_block=(250.0, 700.0, 'B1C1'))))
                out.append((dict(c, fault='exit_cap', x=250.0), dict(b, exit_cap=('B1C1', 250.0))))
            b = base('j2', 'M', policy='sig_av', seed=seed, demand=d, sig_max=30.0, sig_gap=2.0)
            c = dict(part='faults', demand=d, policy='sig_av', level='A', seed=seed, chk=True)
            out.append((dict(c, fault='exit_block', x=450.0), dict(b, exit_block=(250.0, 700.0, 'B1C1'))))
            out.append((dict(c, fault='exit_cap', x=250.0), dict(b, exit_cap=('B1C1', 250.0))))
    return out


def crossover():
    out = []
    for lvl in 'AB':
        for tau in (0.6, 0.8, 1.2):
            for K in (1, 2, 4, 8, 16, 32):
                out.append((dict(part='crossover', policy='poll', level=lvl, tau=tau, K=K),
                            base('j1', 'T', policy='poll', level=lvl, tau=tau, K_max=K, demand=9000, seed=0)))
            out.append((dict(part='crossover', policy='ges', level=lvl, tau=tau, K=0),
                        base('j1', 'T', policy='ges', level=lvl, tau=tau, demand=9000, seed=0)))
    return out


def sens():
    out = []
    grid = dict(tau=(0.6, 0.8, 1.0, 1.5), m_t=(0.15, 0.3, 0.5, 0.8), m_lat=(0.25, 0.5, 1.0), a_lat=(1.5, 2.5, 5.5), tick=(0.25, 0.5, 1.0),
                T_firm=(2.0, 4.0, 8.0), A_max=(30.0, 90.0, 300.0), a=(1.5, 2.6, 3.5), K_lane=(2, 6, 12))
    for k, vals in grid.items():
        for v in vals:
            for seed in (0,):
                out.append((dict(part='sens', param=k, value=v, seed=seed), base('j2', 'M', policy='ges', demand=11000, seed=seed, **{k: v})))
    for dq in (40.0, 60.0, 120.0, 250.0):
        out.append((dict(part='sens', param='fcfs_D_req_j2M', value=dq, seed=0), base('j2', 'M', policy='fcfs_conf', demand=11000, seed=0, D_req=dq)))
        out.append((dict(part='sens', param='fcfs_D_req_j1T', value=dq, seed=0), base('j1', 'T', policy='fcfs_conf', demand=7000, seed=0, D_req=dq)))
    for tau in (0.6, 0.8, 1.0, 1.5):
        out.append((dict(part='sens', param='sig_av_tau', value=tau, seed=0), base('j2', 'M', policy='sig_av', demand=11000, seed=0, tau=tau, sig_max=60.0, sig_gap=1.0)))
    for tau in (1.0, 1.2, 1.4):
        out.append((dict(part='sens', param='human_tau_satflow', value=tau, seed=0), dict(net='j1', left=0.0, right=0.0, end=500.0, warm=100.0, policy='sig_h', demand=7000, ew_share=1.0, tau=tau, sig_max=300.0, seed=0)))
    return out


def network():
    out = []
    for net, ds in (('grid1', (4000, 9000, 14000, 20000)), ('grid2', (8000, 16000, 24000, 32000))):
        for d in ds:
            for pol, chk, lvl in (('sig_av', True, 'A'), ('sig_h', True, 'A'), ('ges', True, 'A'), ('ges', True, 'B'), ('ges', False, 'A')):
                out.append((dict(part='network', net=net, demand=d, policy=pol, chk=chk, level=lvl, seed=0, abl=''),
                            dict(net=net, left=0.1, right=0.1, end=800.0, warm=200.0, policy=pol, level=lvl, demand=d, seed=0, exit_check=chk, sig_max=30.0, sig_gap=2.0)))
    g = dict(net='grid1', left=0.1, right=0.1, end=800.0, warm=200.0, policy='ges', demand=14000, seed=0)
    for name, over in (('no_ponr', dict(ponr=False)), ('no_perception', dict(perception=False)), ('adaptive', dict(adaptive=True)), ('intent', dict(intent=True)),
                       ('exit_aware', dict(exit_aware=True)), ('m_t_0.6', dict(m_t=0.6)), ('tau_1.2', dict(tau=1.2))):
        out.append((dict(part='network', net='grid1', demand=14000, policy='ges', chk=True, level='A', seed=0, abl=name), dict(g, **over)))
    return out


PARTS = dict(capacity=capacity, demand=demand, faults=faults, crossover=crossover, sens=sens, network=network)
PROCS = 2

if __name__ == '__main__':
    part = sys.argv[1]
    PROCS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    jobs = PARTS[part]()
    path = FIG / f'09b-{part}.csv'
    t0 = time.time()
    with Pool(PROCS) as p, path.open('w', newline='') as f:
        w = None
        for n, (label, over, r) in enumerate(p.imap_unordered(job, jobs, chunksize=1)):
            row = dict(label)
            row.update({k: r.get(k, '') for k in KEYS})
            row['error'] = r.get('error', '')
            if w is None:
                fields = sorted({k for j in jobs for k in j[0]}, key=lambda k: list(jobs[0][0]).index(k) if k in jobs[0][0] else 99) + KEYS + ['error']
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
            w.writerow(row)
            f.flush()
            if n % 10 == 0:
                print(part, n, len(jobs), round(time.time() - t0), flush=True)
    print('done', part, len(jobs), round(time.time() - t0), flush=True)
