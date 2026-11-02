#!/usr/bin/env python3
"""Turn fig/09b-*.csv into the report's tables and figures. Prints markdown to stdout."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'fig'
os.environ.setdefault('MPLCONFIGDIR', str(FIG / '.mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

NAMES = dict(sig_h='Human actuated signal', sig_av='AV actuated signal', poll='Batch polling', fcfs_box='FCFS whole box',
             fcfs_conf='FCFS conflict, gap fill', fcfs_scalar='FCFS conflict, no gap fill', ges='Earliest start', wspt='Platoon-weighted')
COL = dict(sig_h='#0e8f7e', sig_av='#d6532a', poll='#7a5cc4', fcfs_conf='#a87a00', ges='#2a78d6')
CASE_NAMES = {'j1/T/ew0.5': '1 lane, through only', 'j2/H/ew0.5': '2 lanes, 35% turns', 'j2/M/ew0.5': '2 lanes, 20% turns', 'j2/M/ew0.8': '2 lanes, 20% turns, 80:20 split'}
INK = '#0b0b0b'
MUTED = '#52514e'


def md(df, floatfmt=0):
    head = '| ' + ' | '.join(map(str, df.columns)) + ' |\n|' + '---|' * len(df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for v in r:
            cells.append(f'{v:.{floatfmt}f}' if isinstance(v, float) else str(v))
        rows.append('| ' + ' | '.join(cells) + ' |')
    return head + '\n' + '\n'.join(rows)


def load(part):
    p = FIG / f'09b-{part}.csv'
    if not p.exists():
        return None
    d = pd.read_csv(p)
    errs = d[d['error'].notna()] if 'error' in d else d.iloc[0:0]
    if len(errs):
        print(f'\n**{part}: {len(errs)} runs failed**: {errs.error.iloc[0]}')
    return d[d['flow'].notna()]


def capacity():
    d = load('capacity')
    if d is None:
        return
    print('\n### Capacity (saturated demand), veh/h, mean of 2 seeds\n')
    d['case'] = d.net + '/' + d.mix
    order = ['sig_h', 'sig_av', 'fcfs_box', 'fcfs_scalar', 'fcfs_conf', 'wspt', 'poll', 'ges']
    rows = []
    for pol in order:
        for lvl in 'AB':
            x = d[(d.policy == pol) & (d.level == lvl)]
            if x.empty:
                continue
            row = {'policy': NAMES[pol] + (' (B)' if lvl == 'B' else '')}
            for c, g in x.groupby('case'):
                row[c] = float(g.flow.mean())
            rows.append(row)
    print(md(pd.DataFrame(rows)))
    print('\nAudit over capacity runs, totals: overlaps by policy/level, invariant breaches, late committed cars, aborts.\n')
    a = d.groupby(['policy', 'level'])[['overlap', 'invariant', 'late_committed', 'aborts', 'box_block']].sum().reset_index()
    print(md(a, 1))
    d2 = d[d.mix == 'M'].groupby(['net', 'policy', 'level'])[['flow', 'stops', 'rms_a', 'p95']].mean().reset_index()
    print('\nMixed-turn detail\n')
    print(md(d2, 2))


def crossover():
    d = load('crossover')
    if d is None:
        return
    print('\n### Batch size crossover, j1 through only, veh/h\n')
    rows = []
    for (lvl, tau), g in d.groupby(['level', 'tau']):
        row = {'level': lvl, 'tau': tau}
        for _, r in g.sort_values('K').iterrows():
            row['GES' if r.policy == 'ges' else f'K={int(r.K)}'] = float(r.flow)
        rows.append(row)
    t = pd.DataFrame(rows)
    t = t[['level', 'tau'] + [f'K={k}' for k in (1, 2, 4, 8, 16, 32)] + ['GES']]
    print(md(t.assign(tau=t.tau.map(str))))
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, lvl, title in zip(axes, 'AB', ('Spec safety: stop unless holding a grant', 'Stall-tolerant: foe must clear first')):
        g = d[(d.level == lvl) & (d.tau == 0.8)]
        p = g[g.policy == 'poll'].sort_values('K')
        ax.plot(p.K, p.flow, color=COL['poll'], lw=2, marker='o', ms=6, label='Batch polling, cap K')
        e = g[g.policy == 'ges'].flow.mean()
        ax.axhline(e, color=COL['ges'], lw=2, label='Earliest start')
        ax.set_xscale('log', base=2)
        ax.set_xticks([1, 2, 4, 8, 16, 32], ['1', '2', '4', '8', '16', '32'])
        ax.set_title(title, fontsize=10, color=INK, loc='left')
        ax.set_xlabel('Batch cap K (vehicles per stream)', fontsize=9, color=MUTED)
        ax.grid(axis='y', color='#e5e4e0', lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Saturated flow (veh/h)', fontsize=9, color=MUTED)
    axes[0].legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / '09b-crossover.png', dpi=140)


def demand():
    d = load('demand')
    if d is None:
        return
    print('\n### Demand curves: delay s/veh (time loss per offered vehicle), flow veh/h, stops/veh, p99 trip s\n')
    d['case'] = d.net + '/' + d.mix + '/ew' + d.ew.astype(str)
    for case, g in d.groupby('case'):
        rows = []
        for dem, h in g.groupby('demand'):
            row = {'demand': int(dem)}
            for pol in ('sig_h', 'sig_av', 'poll', 'fcfs_conf', 'ges'):
                x = h[h.policy == pol]
                if not x.empty:
                    row[pol] = f'{x.delay.mean():.1f} / {x.flow.mean():.0f} / {x.stops.mean():.2f} / {x.p99.mean():.0f}'
            rows.append(row)
        print(f'\n**{case}** (delay / flow / stops / p99)\n')
        print(md(pd.DataFrame(rows)))
    cases = sorted(d.case.unique())
    fig, axes = plt.subplots(1, len(cases), figsize=(3.3 * len(cases), 3.4), sharey=True)
    for ax, case in zip(axes, cases):
        g = d[d.case == case]
        for pol in ('sig_h', 'sig_av', 'poll', 'fcfs_conf', 'ges'):
            x = g[g.policy == pol].groupby('demand').delay.mean()
            ax.plot(x.index, x.values, color=COL[pol], lw=2, marker='o', ms=4, label=NAMES[pol])
        ax.set_yscale('log')
        ax.set_title(CASE_NAMES.get(case, case), fontsize=10, color=INK, loc='left')
        ax.set_xlabel('Offered veh/h', fontsize=9, color=MUTED)
        ax.grid(axis='y', color='#e5e4e0', lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Delay per vehicle (s, log)', fontsize=9, color=MUTED)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8.5, ncol=5, loc='upper center')
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / '09b-demand.png', dpi=140)


def faults():
    d = load('faults')
    if d is None:
        return
    print('\n### Faults, j2 mixed, Earliest start, Level A, seed 0\n')
    cols = ['fault', 'x', 'demand', 'flow', 'delay', 'stops', 'p99', 'overlap', 'late_committed', 'aborts', 'box_block', 'peakq']
    print(md(d.sort_values(['fault', 'demand', 'x'])[cols + ['chk']], 2))


def stalls():
    d = load('stalls')
    if d is None:
        return
    print('\n### Stalled car in the box, j2 mixed, Earliest start\n')
    g = d.groupby(['demand', 'level', 'perception']).agg(overlaps=('overlap', 'sum'), stalls=('stalls', 'sum'), flow=('flow', 'mean'), delay=('delay', 'mean')).reset_index()
    g['per_stall'] = g.overlaps / g.stalls
    print(md(g, 2))


def sens():
    d = load('sens')
    if d is None:
        return
    print('\n### Sensitivity of saturated flow, j2 mixed\n')
    print(md(d.sort_values(['policy', 'param', 'value'])[['policy', 'param', 'value', 'flow', 'p99', 'rms_a', 'overlap', 'aborts']], 2))


def network():
    d = load('network')
    if d is None:
        return
    print('\n### Grid, 9 controlled junctions, 150 m links\n')
    print(md(d.sort_values(['net', 'demand', 'policy', 'level'])[['net', 'demand', 'policy', 'level', 'chk', 'flow', 'offered', 'delay', 'stops', 'p99', 'overlap', 'box_block']], 1))


def capacity_fig():
    d = load('capacity')
    if d is None:
        return
    d['case'] = d.net + '/' + d.mix
    d = d[d.level == 'A']
    cases = ['j1/T', 'j1/M', 'j1/H', 'j2/T', 'j2/M', 'j2/H', 'j3/M']
    pols = ['sig_h', 'sig_av', 'poll', 'ges']
    fig, ax = plt.subplots(figsize=(9, 3.6))
    w = 0.19
    for n, pol in enumerate(pols):
        ys = [d[(d.case == c) & (d.policy == pol)].flow.mean() for c in cases]
        ax.bar([i + (n - 1.5) * w for i in range(len(cases))], ys, w * 0.92, color=COL[pol], label=NAMES[pol])
    ax.set_xticks(range(len(cases)), ['1 lane\nthrough', '1 lane\n20% turns', '1 lane\n35% turns', '2 lanes\nthrough', '2 lanes\n20% turns', '2 lanes\n35% turns', '3 lanes\n20% turns'], fontsize=8.5, color=MUTED)
    ax.set_ylabel('Saturated flow (veh/h)', fontsize=9, color=MUTED)
    ax.grid(axis='y', color='#e5e4e0', lw=0.8)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_ylim(0, 11500)
    ax.legend(frameon=False, fontsize=8.5, ncol=4, loc='upper left')
    fig.tight_layout()
    fig.savefig(FIG / '09b-capacity.png', dpi=140)


if __name__ == '__main__':
    crossover(); capacity(); capacity_fig(); demand(); faults(); stalls(); sens(); network()
