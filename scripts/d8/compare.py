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
    ref = {'stallA': 0.23, 'stallB': 0.07, 'stallA_noperc': None}
    for (n, d), (s, o) in sorted(agg.items()):
        print(f"| {n} | {d:.0f} | {s} | {o} | {o / max(s, 1):.2f} | {ref.get(n)} |")


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


if __name__ == '__main__':
    capacity()
    demand()
    faults()
    stalls()
    generic('t', 'T junction')
    generic('grid', 'Grid of 9 junctions')
    generic('meter', 'Grid overload with perimeter metering')
