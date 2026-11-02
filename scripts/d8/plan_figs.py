#!/usr/bin/env python3
"""Figures for research/truth/09d from `cars av --trace` logs, same arrivals old and new.
Usage: plan_figs.py <net> <off3000.log> <full3000.log> <off5200.log> <full5200.log> <outdir>"""
import collections, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
import brake

OLD, NEW = '#eb6834', '#2a78d6'
INK, MUTED = '#0b0b0b', '#52514e'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.grid': True, 'grid.color': '#e6e5e0', 'grid.linewidth': 0.6, 'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb'})


def cars_of(net, log):
    speed, length, app = brake.net_info(net)
    cars, turn = brake.read(log, speed, length, app)
    L = max(length[l] for l in length if l.rsplit('_', 1)[0] in app)
    keep = {}
    for trip, r in cars.items():
        r = np.array(r)
        if r[0, 1] >= L - 10 and r[-1, 1] <= 3 and trip in turn:
            keep[trip] = (r, turn[trip] < 13)
    return keep, L


def speed_distance(net, off, full, out, demand):
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.4), sharex=True, sharey=True)
    for col, (log, name, colr) in enumerate(((off, 'today', OLD), (full, 'planned', NEW))):
        cars, L = cars_of(net, log)
        for row, (turning, what) in enumerate(((False, 'straight'), (True, 'turning'))):
            ax = axes[row, col]
            n = 0
            for r, t in cars.values():
                if t == turning:
                    ax.plot(r[:, 1], r[:, 2], color=colr, lw=0.6, alpha=0.35)
                    n += 1
            ax.set_title(f'{name}, {what}: {n} cars', fontsize=10, loc='left', color=INK)
            ax.set_xlim(L, 0)
            ax.set_ylim(0, 15)
            if row == 1:
                ax.set_xlabel('distance to the line, m')
            if col == 0:
                ax.set_ylabel('speed, m/s')
    fig.suptitle(f'Every car\'s speed on its approach, {demand} veh/h, same arrivals', x=0.01, ha='left', fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out / f'speed_distance_{demand}.png', dpi=130)
    plt.close(fig)


def time_distance(net, off, full, out, demand, lane='A1B1', t0=120, t1=170):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    speed, length, app = brake.net_info(net)
    for ax, log, name, colr in ((axes[0], off, 'today', OLD), (axes[1], full, 'planned', NEW)):
        tracks = collections.defaultdict(list)
        for line in open(log):
            if not line.startswith('tr '):
                continue
            m = brake.PAT.match(line)
            if not m:
                continue
            t, trip, ln, pos, v, a, st, tl = m.groups()
            t = float(t)
            if ln.rsplit('_', 1)[0] == lane and t0 - 25 <= t <= t1:
                tracks[trip].append((t, length[ln] - float(pos), int(st, 16) & 7, float(tl)))
        for r in tracks.values():
            r = np.array(r)
            ax.plot(r[:, 0], r[:, 1], color=colr, lw=1.0, alpha=0.8)
            firm = r[r[:, 2] == 2]
            if len(firm) and r[-1, 1] < 5:
                ax.scatter([firm[-1, 3]], [0], s=22, color=INK, zorder=3)
        ax.set_xlim(t0, t1)
        ax.set_ylim(0, max(length[f'{lane}_0'], 1))
        ax.invert_yaxis()
        ax.set_title(name, fontsize=10, loc='left', color=INK)
        ax.set_xlabel('time, s')
    axes[0].set_ylabel('distance to the line, m')
    fig.suptitle(f'Time and distance on approach {lane}, {demand} veh/h. Dots: firm slots at the line', x=0.01, ha='left', fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out / f'time_distance_{demand}.png', dpi=130)
    plt.close(fig)


def where(net, logs, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for ax, (d, off, full) in zip(axes, logs):
        ticks = None
        for j, (log, name, colr) in enumerate(((off, 'today', OLD), (full, 'planned', NEW))):
            cars, L = cars_of(net, log)
            bins = np.zeros(6)
            for r, _ in cars.values():
                dv = np.diff(r[:, 2])
                for i in np.nonzero(dv < 0)[0]:
                    bins[min(int(r[i, 1] // 50), 5)] -= dv[i]
            bins /= max(len(cars), 1)
            x = np.arange(6) + (j - 0.5) * 0.38
            ax.bar(x, bins, 0.36, color=colr, label=name)
            ticks = ['0-50', '50-100', '100-150', '150-200', '200-250', '250+']
        ax.set_xticks(range(6), ticks)
        ax.set_xlabel('metres before the line')
        ax.set_title(f'{d} veh/h', fontsize=10, loc='left', color=INK)
        ax.grid(axis='x', visible=False)
        ax.legend(frameon=False)
    axes[0].set_ylabel('speed lost per car, m/s')
    fig.suptitle('Where the speed is thrown away', x=0.01, ha='left', fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out / 'braking_by_distance.png', dpi=130)
    plt.close(fig)


def main():
    net, o3, f3, o5, f5, out = sys.argv[1:7]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    speed_distance(net, o3, f3, out, 3000)
    speed_distance(net, o5, f5, out, 5200)
    time_distance(net, o3, f3, out, 3000)
    time_distance(net, o5, f5, out, 5200)
    where(net, ((3000, o3, f3), (5200, o5, f5)), out)


if __name__ == '__main__':
    main()
