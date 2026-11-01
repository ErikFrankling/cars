#!/usr/bin/env python3
"""GPU results against the CPU model (research/truth/fig/09b-*.csv): tables on stdout, figures in fig/d8."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FIG = Path(__file__).resolve().parents[2] / 'research/truth/fig'
D8 = FIG / 'd8'


def rows(part):
    p = D8 / f'{part}.jsonl'
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines()]


def cpu(name):
    with (FIG / f'09b-{name}.csv').open() as f:
        return list(csv.DictReader(f))


def mean(v):
    return float(np.mean(v)) if len(v) else float('nan')


def pol(c):
    if c['mode'] == 'signal':
        return 'sig_h' if c['human'] else 'sig_av'
    return 'ges'


def capacity():
    gpu = defaultdict(list)
    for r in rows('capacity'):
        c = r['case']
        gpu[(c['net'], c['mix'], pol(c), c['level'])].append(r['result'])
    cp = defaultdict(list)
    for r in cpu('capacity'):
        if r.get('flow'):
            cp[(r['net'], r['mix'], r['policy'], r['level'])].append(float(r['flow']))
    print('\n## Capacity, veh/h: GPU against the CPU model')
    print('| Case | Policy | GPU | CPU | Diff | Overlaps | Invariant | Teleports |')
    print('|---|---|---:|---:|---:|---:|---:|---:|')
    names = dict(ges='Earliest start', sig_av='AV signal', sig_h='Human signal')
    out = []
    for k in sorted(gpu):
        net, mix, p, lvl = k
        g = gpu[k]
        f = mean([x['flow'] for x in g if 'flow' in x])
        c = mean(cp.get(k, []))
        d = (f / c - 1) * 100 if c == c else float('nan')
        print(f"| {net} {mix} | {names[p]}{' B' if lvl == 'B' else ''} | {f:.0f} | {c:.0f} | {d:+.1f}% | {sum(x.get('overlap', 0) for x in g)} | {sum(x.get('invariant', 0) for x in g)} | {sum(x.get('teleports', 0) for x in g)} |")
        out.append((f"{net} {mix}", names[p] + (' B' if lvl == 'B' else ''), f, c))
    if out:
        cases = sorted({o[0] for o in out})
        pols = ['Human signal', 'AV signal', 'Earliest start', 'Earliest start B']
        colors = ['#8a8f98', '#3b6fb6', '#1b9e77', '#b0d9c9']
        fig, ax = plt.subplots(figsize=(10, 4.2))
        w = 0.2
        for i, p in enumerate(pols):
            xs, gv, cv = [], [], []
            for j, c in enumerate(cases):
                m = [o for o in out if o[0] == c and o[1] == p]
                if m:
                    xs.append(j + (i - 1.5) * w)
                    gv.append(m[0][2])
                    cv.append(m[0][3])
            ax.bar(xs, gv, w * 0.92, label=p + ' (GPU)', color=colors[i])
            ax.scatter(xs, cv, marker='_', s=120, color='black', zorder=3, label='CPU model' if i == 0 else None)
        ax.set_xticks(range(len(cases)), cases)
        ax.set_ylabel('Saturated flow, veh/h')
        ax.legend(frameon=False, ncols=3, fontsize=8)
        ax.spines[['top', 'right']].set_visible(False)
        fig.tight_layout()
        fig.savefig(D8 / 'capacity.png', dpi=140)


def demand():
    gpu = defaultdict(list)
    for r in rows('demand'):
        c = r['case']
        gpu[(c['net'], c['mix'], float(c['ew']), float(c['demand']), pol(c))].append(r['result'])
    cp = defaultdict(list)
    for r in cpu('demand'):
        if r.get('delay'):
            cp[(r['net'], r['mix'], float(r['ew']), float(r['demand']), r['policy'])].append((float(r['delay']), float(r['stops'])))
    if not gpu:
        return
    print('\n## Delay, s per offered vehicle, and stops per car')
    print('| Case | veh/h | Policy | GPU delay | CPU delay | GPU stops | CPU stops | Overlaps |')
    print('|---|---:|---|---:|---:|---:|---:|---:|')
    for k in sorted(gpu):
        g = gpu[k]
        c = cp.get(k, [])
        print(f"| {k[0]} {k[1]} ew{k[2]} | {k[3]:.0f} | {k[4]} | {mean([x['delay'] for x in g if 'delay' in x]):.1f} | {mean([x[0] for x in c]):.1f} | {mean([x['stops'] for x in g if 'stops' in x]):.2f} | {mean([x[1] for x in c]):.2f} | {sum(x.get('overlap', 0) for x in g)} |")
    fig, ax = plt.subplots(figsize=(7, 4))
    for p, name, col in (('sig_h', 'Human signal', '#8a8f98'), ('sig_av', 'AV signal', '#3b6fb6'), ('ges', 'Earliest start', '#1b9e77')):
        ds = sorted({k[3] for k in gpu if k[:3] == ('j2', 'M', 0.5) and k[4] == p})
        ax.plot(ds, [mean([x['delay'] for x in gpu[('j2', 'M', 0.5, d, p)] if 'delay' in x]) for d in ds], 'o-', color=col, label=f'{name}, GPU')
        ax.plot(ds, [mean([x[0] for x in cp.get(('j2', 'M', 0.5, d, p), [])]) for d in ds], 'x--', color=col, alpha=0.6, label=f'{name}, CPU')
    ax.set_yscale('log')
    ax.set_xlabel('Offered veh/h, 2 lanes, 20% turns')
    ax.set_ylabel('Delay, s per vehicle')
    ax.legend(frameon=False, fontsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(D8 / 'demand.png', dpi=140)


def faults():
    cp = {}
    for r in cpu('faults'):
        if r.get('flow'):
            x = r['x']
            cp[(r['fault'], float(x), float(r['demand']), r['chk'])] = r
    print('\n## Faults, 2 lanes, 20% turns')
    print('| Fault | veh/h | GPU flow | CPU flow | GPU delay | CPU delay | Overlaps | Ungranted crossings | Stopped in box, veh·s |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for r in rows('faults'):
        c, g = r['case'], r['result']
        name = c['fault']
        ref = None
        for (f, x, d, chk), v in cp.items():
            if d != c['demand']:
                continue
            if (name.startswith('loss') and f == 'loss' and abs(x - float(name[4:])) < 1e-6) or (name.startswith('blackout') and f == 'blackout' and abs(x - float(name[8:])) < 1e-6) or (name == f) or (name.startswith('exit_block') and f == 'exit_block' and name.endswith(chk)) or (name.startswith('exit_cap') and f == 'exit_cap' and name.endswith(chk)):
                ref = v
        print(f"| {name} | {c['demand']:.0f} | {g.get('flow', -1):.0f} | {float(ref['flow']) if ref else float('nan'):.0f} | {g.get('delay', -1):.1f} | {float(ref['delay']) if ref else float('nan'):.1f} | {g.get('overlap')} | {g.get('cross_ungranted')} | {g.get('box_block', 0):.1f} |")


def stalls():
    print('\n## Injected stalls in the box (reported separately)')
    print('| Case | veh/h | Stalls | Collision events | Per stall | CPU per stall |')
    print('|---|---:|---:|---:|---:|---:|')
    agg = defaultdict(lambda: [0, 0])
    for r in rows('stalls'):
        c, g = r['case'], r['result']
        a = agg[(c['fault'], c['demand'])]
        a[0] += g.get('stalls', 0)
        a[1] += g.get('overlap', 0)
    ref = {('stallA', 3000): 0.24, ('stallA', 5000): 0.23, ('stallB', 3000): 0.07, ('stallB', 5000): 0.06, ('stallA_noperc', 3000): 0.38, ('stallA_noperc', 5000): 0.71}
    for (n, d), (s, o) in sorted(agg.items()):
        print(f"| {n} | {d:.0f} | {s} | {o} | {o / max(s, 1):.2f} | {ref.get((n, d))} |")


def generic(part, title):
    rs = rows(part)
    if not rs:
        return
    print(f'\n## {title}')
    print('| Net | Offered | Policy | Meter | Flow | Delay | Overlap events | Invariant | Pending | ms/step | Vehicles |')
    print('|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for r in rs:
        c, g = r['case'], r['result']
        print(f"| {c['net']} {c['mix']} | {c['demand']:.0f} | {pol(c)} {c['level']}{' nocheck' if c.get('no_exit_check') else ''} | {c.get('meter', 0)} | {g.get('flow', -1):.0f} | {g.get('delay', -1):.1f} | {g.get('overlap')} | {g.get('invariant')} | {g.get('pending')} | {g.get('ms_per_step', 0):.2f} | {g.get('mean_active', 0):.0f} |")


def headway():
    rs = rows('headway')
    if rs:
        f = mean([r['result']['flow'] for r in rs])
        print(f"\n## Saturation headway, one through stream each way: {f:.0f} veh/h over 2 streams, {2 * 3600 / f:.3f} s per car; reference 1.304 s")


def faults2():
    rs = rows('faults2')
    if not rs:
        return
    print('\n## Links gone for good (not in the CPU model)')
    print('| Case | veh/h | Flow | Delay | Overlaps | Ungranted crossings | Stuck cars at the end |')
    print('|---|---:|---:|---:|---:|---:|---:|')
    for r in rs:
        c, g = r['case'], r['result']
        print(f"| {c['fault']} | {c['demand']:.0f} | {g.get('flow', -1):.0f} | {g.get('delay', -1):.1f} | {g.get('overlap')} | {g.get('cross_ungranted')} | {g.get('stuck')} |")


def meter_table():
    rs = rows('meter') + rows('meter_seeds')
    if not rs:
        return
    agg = defaultdict(list)
    for r in rs:
        c = r['case']
        agg[(c['net'], c['demand'], c.get('meter', 0))].append(r['result'])
    base = rows('grid') + rows('meter_seeds')
    b = defaultdict(list)
    for r in base:
        c = r['case']
        if c.get('meter') or c.get('no_exit_check') or c['level'] != 'A' or c['human']:
            continue
        if c['net'] in ('grid1', 'grid2'):
            b[(c['net'], c['demand'], pol(c))].append(r['result'])
    print('\n## Grid overload: metering at the edge, mean of seeds')
    print('| Net | Offered | Network held at | Seeds | Flow | Delay incl. waiting outside | Overlap events, total | Stuck |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|')
    fig, ax = plt.subplots(figsize=(7, 4))
    for k in sorted(agg):
        g = agg[k]
        print(f"| {k[0]} | {k[1]:.0f} | {k[2]} | {len(g)} | {mean([x['flow'] for x in g]):.0f} | {mean([x['delay'] for x in g]):.0f} | {sum(x['overlap'] for x in g)} | {sum(x.get('stuck', 0) for x in g)} |")
    for key, v in sorted(b.items()):
        if key[2] in ('ges', 'sig_av'):
            print(f"| {key[0]} | {key[1]:.0f} | {'none, signal-free' if key[2] == 'ges' else 'AV signal'} | {len(v)} | {mean([x['flow'] for x in v]):.0f} | {mean([x['delay'] for x in v]):.0f} | {sum(x['overlap'] for x in v)} | {sum(x.get('stuck', 0) for x in v)} |")
    for net, d, col in (('grid2', 24000, '#1b9e77'), ('grid1', 14000, '#7570b3')):
        ks = sorted(k[2] for k in agg if k[0] == net and k[1] == d)
        ax.plot(ks, [mean([x['flow'] for x in agg[(net, d, n)]]) for n in ks], 'o-', color=col, label=f'{net}, {d} veh/h offered, metered')
        for name, ls in (('ges', ':'), ('sig_av', '--')):
            v = b.get((net, d, name))
            if v:
                ax.axhline(mean([x['flow'] for x in v]), color=col, ls=ls, lw=1, label=f"{net} {'no metering' if name == 'ges' else 'AV signal'}")
    ax.set_xlabel('Cars allowed on the network')
    ax.set_ylabel('Flow, veh/h')
    ax.legend(frameon=False, fontsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(D8 / 'metering.png', dpi=140)


def stockholm():
    rs = rows('stockholm')
    if not rs:
        return
    agg = defaultdict(list)
    for r in rs:
        c = r['case']
        agg[(c['place'], c['demand'], c['policy'])].append(r['result'])
    print('\n## Stockholm, through traffic, no count data, no pedestrians in the net')
    print('| Place | Offered | Policy | Coordinated | Refused | Flow | Time lost per trip, s | Overlaps | Lane contacts | Teleports | Invariant | Stuck over 120 s |')
    print('|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for k in sorted(agg):
        g = [x for x in agg[k] if 'flow' in x]
        print(f"| {k[0]} | {k[1]} | {k[2]} | {g[0].get('junctions')} | {g[0].get('refused')} | {mean([x['flow'] for x in g]):.0f} | {mean([x['time_loss'] for x in g]):.1f} | {sum(x['overlap'] for x in g)} | {sum(x['collisions'] for x in g)} | {sum(x['teleports'] for x in g)} | {sum(x['invariant'] for x in g)} | {sum(x['stuck'] for x in g)} |")


def scale():
    p = D8 / 'scale.jsonl'
    if not p.exists():
        return
    print('\n## Compute on the RX 7900 XT, bounds checks on')
    print('| Net | Junctions | Mean vehicles | ms per step | Without coordinator | Coordinator kernels at t=200, ms | Coordinator memory, MB |')
    print('|---|---:|---:|---:|---:|---:|---:|')
    rs = [json.loads(l) for l in p.read_text().splitlines()]
    for r in rs:
        if not r['cj']:
            continue
        g = r['result']
        other = [x['result'] for x in rs if x['net'] == r['net'] and not x['cj']]
        kern = sum(m for pr in g.get('profile', []) for n, m in pr['kernels'] if n.startswith('cj_'))
        print(f"| {r['net']} | {g.get('junctions')} | {g.get('mean_active', 0):.0f} | {g.get('ms_per_step', 0):.2f} | {other[0].get('ms_per_step', 0) if other else float('nan'):.2f} | {kern:.2f} | {g.get('coord_mb', 0):.1f} |")


if __name__ == '__main__':
    headway()
    capacity()
    demand()
    faults()
    stalls()
    generic('t', 'T junction')
    generic('grid', 'Grid of 9 junctions')
    faults2()
    meter_table()
    stockholm()
    scale()
