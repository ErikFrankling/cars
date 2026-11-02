#!/usr/bin/env python3
"""Charts of real against simulated driving. Reads the audit's outputs, writes PNGs to --out.

    python3 charts.py --data DATA --out research/truth/fig/physical
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

INK, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
COL = dict(real=INK, main='#2a78d6', phys='#eb6834', hum='#1baf7a')
NAME = dict(real='Real drivers', main='Main (default)', phys='Physics layer', hum='Human driver')
DRV = ['main', 'phys', 'hum']
plt.rcParams.update({'font.size': 11, 'axes.edgecolor': MUTED, 'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8, 'axes.axisbelow': True, 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE, 'legend.frameon': False, 'lines.linewidth': 2})


def title(fig, ax, head, sub):
    fig.text(0.01, 0.985, head, fontsize=14, fontweight='bold', color=INK, va='top')
    fig.text(0.01, 0.935, sub, fontsize=10.5, color=MUTED, va='top')


def metric(data, scene, drv, dt=1):
    p = Path(data) / 'local/out' / f'{scene}_{drv}_dt{dt:g}' / 'metrics.json'
    return json.loads(p.read_text()) if p.exists() else None


def csv(data, scene, drv, what, dt=1):
    p = Path(data) / 'local/out' / f'{scene}_{drv}_dt{dt:g}' / f'{what}.csv'
    return pd.read_csv(p) if p.exists() else None


def samples(data, scene, drv, dt=1):
    p = Path(data) / 'local/out' / f'{scene}_{drv}_dt{dt:g}' / 'samples.npy'
    return np.load(p) if p.exists() else None


def ecdf_line(ax, x, label, color, lw=2, ls='-'):
    x = np.sort(np.asarray(x, float))
    y = np.arange(1, len(x) + 1) / len(x) * 100
    ax.plot(x, y, color=color, lw=lw, ls=ls, label=label)


def braking(data, out):
    ut = pd.read_csv(Path(data) / 'ut/ut_stops_w1.csv')
    ut = ut[ut.kind == 'car']
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
    fig.subplots_adjust(top=0.78, left=0.07, right=0.98, bottom=0.14, wspace=0.08)
    title(fig, axes[0], 'How hard cars brake when they come to a stop', 'Share of stops at or below each braking level, in a signal queue, step 0.1 s. Further right means harder braking.')
    a, b = axes
    ecdf_line(a, ut['mean'], NAME['real'] + ' (Braunschweig)', INK, 3)
    ecdf_line(b, -ut.peak, NAME['real'] + ' (Braunschweig)', INK, 3)
    for d in DRV:
        s = csv(data, 'signal', d, 'stops', 0.1)
        if s is not None and len(s):
            ecdf_line(a, s['mean'], NAME[d], COL[d])
            ecdf_line(b, -s.peak, NAME[d], COL[d])
    a.set_xlim(0, 5)
    b.set_xlim(0, 9.5)
    a.set_xlabel('Average braking over the whole stop, m/s²')
    b.set_xlabel('Hardest moment of the stop, m/s²')
    a.set_ylabel('Share of stops, %')
    b.axvline(8.9, color=MUTED, ls=':', lw=1.5)
    b.text(8.85, 8, 'dry tyre limit\n(ADAC)', color=MUTED, ha='right', fontsize=9)
    a.legend(loc='lower right')
    fig.savefig(out / 'braking.png', dpi=130)
    plt.close(fig)


def launch(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'How hard cars accelerate, by speed', 'Line: typical (median) acceleration while speeding up. Band for real drivers: typical to the top 5%.')
    s = np.load(Path(data) / 'ut/ut_samples_w1.npy')
    v, al, kind = s[:, 0], s[:, 1], s[:, 4]
    bins = np.array([0.5, 2, 4, 6, 8, 10, 12, 14])
    mid = (bins[1:] + bins[:-1]) / 2
    q = lambda f, p: [np.percentile(f[(v[(kind == 0) & (al > 0.1)] >= lo) & (v[(kind == 0) & (al > 0.1)] < hi)], p) for lo, hi in zip(bins[:-1], bins[1:])]
    pos = al[(kind == 0) & (al > 0.1)]
    ax.fill_between(mid, q(pos, 50), q(pos, 95), color=INK, alpha=0.12, lw=0)
    ax.plot(mid, q(pos, 50), color=INK, lw=3, label=NAME['real'] + ' (Braunschweig)')
    xs = np.linspace(0, 14, 50)
    ax.plot(xs, 2.02 - 0.125 * xs, color=MUTED, ls='--', lw=1.5, label='Long 2000, measured at signals: 2.02 − 0.125 v')
    for d in DRV:
        sm = samples(data, 'signal', d, 0.1)
        if sm is None:
            continue
        vv, aa = sm[:, 0], sm[:, 1]
        y = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            k = (vv >= lo) & (vv < hi) & (aa > 0.1)
            y.append(np.percentile(aa[k], 50) if k.sum() > 20 else np.nan)
        ax.plot(mid, y, color=COL[d], label=NAME[d], marker='o', ms=5)
    ax.set_xlabel('Speed, m/s (14 m/s = 50 km/h)')
    ax.set_ylabel('Acceleration, m/s²')
    ax.set_ylim(0, 3.2)
    ax.legend(loc='upper right')
    fig.savefig(out / 'acceleration.png', dpi=130)
    plt.close(fig)


def curves(data, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    fig.subplots_adjust(top=0.78, left=0.06, right=0.98, bottom=0.14, wspace=0.2)
    title(fig, axes[0], 'How fast cars take a bend of each radius', 'Left: speed through the bend. Right: the sideways acceleration that demands. Dotted: 4 m/s², the most real drivers use; 8 m/s², tyres near their limit.')
    a, b = axes
    t = pd.read_csv(Path(data) / 'ut/ut_turns_w2.csv')
    t = t[(t.kind == 'car') & (t.turn_deg > 40)]
    others = []
    for n in ['pneuma', 'swiss', 'foggy']:
        p = Path(data) / f'realout/{n}_w2_turns.csv'
        if p.exists():
            f = pd.read_csv(p)
            others.append(f[f.turn_deg > 40])
    if others:
        t = pd.concat([t] + others)
    edges = np.array([6, 8, 10, 13, 16, 20, 25, 30, 40, 60, 100])
    t['b'] = pd.cut(t.r_core, edges)
    g = t.groupby('b', observed=True)
    x = np.array([np.sqrt(i.left * i.right) for i in g.groups])
    n = g.size().values
    keep = n >= 15
    a.fill_between(x[keep], g.v_core.quantile(.15).values[keep], g.v_core.quantile(.85).values[keep], color=INK, alpha=0.12, lw=0)
    a.plot(x[keep], g.v_core.median().values[keep], color=INK, lw=3, label='Real drivers (4 cities)')
    b.fill_between(x[keep], g.ay_core.quantile(.15).values[keep], g.ay_core.quantile(.85).values[keep], color=INK, alpha=0.12, lw=0)
    b.plot(x[keep], g.ay_core.median().values[keep], color=INK, lw=3, label='Real drivers (4 cities)')
    for d in DRV:
        m = metric(data, 'curves', d)
        if not m:
            continue
        for limit, ls in [(50, '-'), (90, '--')]:
            r = sorted([c for c in m['curves'] if c['limit'] == limit], key=lambda c: c['R'])
            a.plot([c['R'] for c in r], [c['v_mean'] for c in r], color=COL[d], ls=ls, label=f"{NAME[d]}, {limit} km/h road")
            b.plot([c['R'] for c in r], [c['ay'] for c in r], color=COL[d], ls=ls)
    a.set_xscale('log')
    b.set_xscale('log')
    for ax in axes:
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel('Bend radius, m')
        ax.set_xticks([10, 20, 50, 100, 200, 350])
        ax.set_xticklabels(['10', '20', '50', '100', '200', '350'])
    a.set_ylabel('Speed through the bend, m/s')
    b.set_ylabel('Sideways acceleration, m/s²')
    for y in (4, 8):
        b.axhline(y, color=MUTED, ls=':', lw=1.3)
    b.set_ylim(0, 14)
    a.legend(loc='upper left', fontsize=9)
    fig.savefig(out / 'cornering.png', dpi=130)
    plt.close(fig)


def time_gap(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'How closely cars follow, by speed', 'Time gap: seconds between the car ahead passing a point and this car reaching it. Typical value per speed band.')
    g = json.loads((Path(data) / 'realout/gaps.json').read_text())
    centre = lambda k: sum(float(x) for x in k.split('-')) / 2
    for name, lab, mk in [('I90stat', 'Real, Chicago motorway', 'o'), ('I395', 'Real, Washington motorway', 's'), ('HT', 'Real, German motorway', '^')]:
        t = g[name]['time_gap']
        ks = list(t)
        ax.plot([centre(k) for k in ks], [t[k]['p50'] for k in ks], color=INK, marker=mk, ms=7, ls=':', lw=1.3, label=lab)
    for d in DRV:
        m = metric(data, 'speeds', d, 0.1) or metric(data, 'speeds', d)
        if m and m['time_gap']:
            ks = [k for k in m['time_gap'] if m['time_gap'][k]['n'] > 30]
            ax.plot([centre(k) for k in ks], [m['time_gap'][k]['p50'] for k in ks], color=COL[d], marker='o', ms=7, label=NAME[d])
    ax.set_xlabel('Follower speed, m/s')
    ax.set_ylabel('Time gap, s')
    ax.set_ylim(0, 4)
    ax.legend(loc='upper right', ncol=2)
    fig.savefig(out / 'time_gap.png', dpi=130)
    plt.close(fig)


def discharge(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'How a queue drains when the light turns green', 'Seconds between one car crossing the line and the next. The first car counts from the start of green.')
    real = {1: 3.62, 2: 2.4, 3: 2.2, 4: 2.2, 5: 2.0, 6: 2.0, 7: 2.0}
    ax.plot(list(real), list(real.values()), color=INK, lw=3, marker='s', label='Real, Braunschweig (report 05)')
    for d in DRV:
        m = metric(data, 'signal', d, 0.1)
        if m and m['signal'].get('headway'):
            h = m['signal']['headway']
            ks = sorted(int(k) for k in h if int(k) <= 12)
            ax.plot(ks, [h[str(k)]['median'] for k in ks], color=COL[d], marker='o', ms=6, label=NAME[d])
    ax.set_xlabel('Place in the queue')
    ax.set_ylabel('Seconds per car')
    ax.set_ylim(0, 6)
    ax.legend(loc='upper right')
    fig.savefig(out / 'queue_discharge.png', dpi=130)
    plt.close(fig)


def free_flow(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'How fast cars drive against the speed limit', 'Mean speed divided by the limit. Real: Swedish town streets, every vehicle at mid-block, VTI 2018.')
    real = {40: 39 / 40, 50: 45 / 50, 60: 51 / 60, 70: 62 / 70}
    ax.plot(list(real), list(real.values()), color=INK, lw=3, marker='s', label='Real, Sweden (VTI rapport 1001)')
    for d in DRV:
        m = metric(data, 'free', d)
        if m and m.get('free'):
            ks = sorted(int(k) for k in m['free'])
            ax.plot(ks, [m['free'][str(k)]['ratio'] for k in ks], color=COL[d], marker='o', ms=6, label=NAME[d])
    ax.axhline(1, color=MUTED, ls=':', lw=1.3)
    ax.set_xlabel('Speed limit, km/h')
    ax.set_ylabel('Speed ÷ limit')
    ax.set_ylim(0.7, 1.15)
    ax.legend(loc='lower right')
    fig.savefig(out / 'free_speed.png', dpi=130)
    plt.close(fig)


def stopping(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'The shortest stop each driver makes when a light turns red with no warning', 'Lone cars, step 0.1 s. Grey band: the most real tyres allow on a dry road (ADAC). Above the band is physically possible.')
    lim = np.array([30, 50, 70, 100])
    v = lim / 3.6
    lo, hi = v ** 2 / (2 * 8.91), v ** 2 / (2 * 8.30)
    ax.fill_between(lim, lo, hi, color=MUTED, alpha=0.35, lw=0, label='Dry tyre limit, ADAC')
    ax.plot(lim, v ** 2 / (2 * 3.05), color=INK, ls='--', lw=1.5, label='A firm stop at 3 m/s²')
    for d in DRV:
        m = metric(data, 'wall2', d, 0.1)
        if m and m.get('wall'):
            ks = sorted(int(k) for k in m['wall'] if m['wall'][k]['n'] >= 5)
            ax.plot(ks, [m['wall'][str(k)]['dist_min'] for k in ks], color=COL[d], marker='o', ms=6, label=NAME[d])
    ax.set_xlabel('Speed limit of the road, km/h')
    ax.set_ylabel('Stopping distance, m')
    ax.legend(loc='upper left', fontsize=10)
    fig.savefig(out / 'stopping_distance.png', dpi=130)
    plt.close(fig)


def maps(data, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    fig.subplots_adjust(top=0.78, left=0.13, right=0.98, bottom=0.14, wspace=0.22)
    title(fig, axes[0], 'Why city maps demand impossible corners', 'Left: the radius a map draws for a junction turn against the radius real cars drove. Right: the sideways force at those radii.')
    a, b = axes
    t = pd.concat([pd.read_csv(Path(data) / 'ut/ut_turns_w2.csv')] + [pd.read_csv(Path(data) / f'realout/{n}_w2_turns.csv') for n in ('pneuma', 'swiss', 'foggy')])
    t = t[(t.kind.isin(['car', 'taxi'])) & (t.turn_deg > 60)]
    st, be = [json.loads((Path(data) / f'maps_{n}.json').read_text())['all_internal'] for n in ('stockholm', 'berlin')]
    rows = [('Stockholm map', st['r_mean']), ('Berlin map', be['r_mean']), ('Real cars, 4 cities', dict(p10=float(t.r_mean.quantile(.1)), p50=float(t.r_mean.median()), p90=float(t.r_mean.quantile(.9))))]
    for i, (n, r) in enumerate(rows):
        a.barh(i, r['p90'] - r['p10'], left=r['p10'], color=(INK if 'Real' in n else COL['main']), alpha=0.25, height=0.5)
        a.plot([r['p50']], [i], marker='o', color=(INK if 'Real' in n else COL['main']), ms=9)
        a.text(r['p90'] + 1, i, f"typical {r['p50']:.1f} m", va='center', color=MUTED, fontsize=10)
    a.set_yticks(range(3))
    a.set_yticklabels([r[0] for r in rows])
    a.set_xlabel('Turn radius, m (dot: typical; bar: 10th to 90th percentile)')
    a.set_xlim(0, 55)
    a.grid(axis='y', visible=False)
    r = np.logspace(np.log10(2), np.log10(40), 60)
    b.plot(r, 8 ** 2 / r, color=COL['hum'], label='At the human driver’s 8 m/s floor')
    b.plot(r, np.minimum(5.5 + 0 * r, 5.5), color=COL['main'], label='At map speed: netconvert’s 5.5 m/s² rule')
    b.axhspan(0, 3, color=INK, alpha=0.1, lw=0)
    b.text(30, 1.1, 'Real drivers\n(typical to top 15%)', color=INK, fontsize=9, ha='center')
    b.axhline(8.3, color=MUTED, ls=':', lw=1.3)
    b.text(39, 8.6, 'dry tyre limit', color=MUTED, ha='right', fontsize=9)
    b.set_xscale('log')
    b.set_xticks([2, 5, 10, 20, 40])
    b.set_xticklabels(['2', '5', '10', '20', '40'])
    b.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    b.set_ylim(0, 20)
    b.set_xlabel('Turn radius drawn on the map, m')
    b.set_ylabel('Sideways acceleration, m/s²')
    b.legend(loc='upper right', fontsize=9)
    fig.savefig(out / 'map_corners.png', dpi=130)
    plt.close(fig)


def jerk(data, out):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.8, left=0.08, right=0.98, bottom=0.13)
    title(fig, ax, 'How abruptly the pedal moves (jerk)', 'Share of moving time with jerk at or below each level, all through the same 1 s fit. Real tracks include tracker noise.')
    s = np.load(Path(data) / 'ut/ut_samples_w1.npy')
    k = (s[:, 0] > 0.5) & (s[:, 4] == 0)
    ecdf_line(ax, np.abs(s[k, 3]), NAME['real'] + ' (Braunschweig)', INK, 3)
    for d in DRV:
        sm = samples(data, 'signal', d, 0.1)
        if sm is not None:
            q = sm[:, 0] > 0.5
            ecdf_line(ax, np.abs(sm[q, 2]), NAME[d], COL[d])
    ax.set_xlim(0, 4)
    ax.set_xlabel('Jerk, m/s³')
    ax.set_ylabel('Share of time, %')
    ax.legend(loc='lower right')
    fig.savefig(out / 'jerk.png', dpi=130)
    plt.close(fig)


def city(data, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    fig.subplots_adjust(top=0.78, left=0.14, right=0.98, bottom=0.14, wspace=0.28)
    title(fig, axes[0], 'A real piece of city: Charlottenburg, morning, step 1 s', 'Left: how often cars brake harder than 3 m/s². Right: speed through junction turns, by the radius of the turn.')
    a, b = axes
    real = json.loads((Path(data) / 'real_summary.json').read_text())['cities']
    rows = [(f'Real, {n.capitalize()}', real[n]['share_dec_over']['3'] * 100, INK) for n in ('switzerland', 'athens', 'braunschweig')]
    for d in DRV:
        m = metric(data, 'city', d)
        rows.append((NAME[d], m['share_dec_gt']['3'] * 100, COL[d]))
    for i, (n, v, c) in enumerate(rows):
        a.barh(i, v, color=c, height=0.6)
        a.text(v + 0.08, i, f'{v:.2f}%', va='center', color=MUTED, fontsize=10)
    a.set_yticks(range(len(rows)))
    a.set_yticklabels([r[0] for r in rows])
    a.set_xlabel('Share of moving time braking over 3 m/s², %')
    a.grid(axis='y', visible=False)
    a.set_xlim(0, 6)
    r = np.linspace(5, 45, 40)
    b.plot(r, 1.284 * r ** 0.505, color=INK, lw=3, label='Real drivers, 3,584 turns: 1.28 √R')
    for d in DRV:
        t = json.loads((Path(data) / f'city_{d}.json').read_text())['turning_by_radius']
        x, y = [], []
        for k, v in t.items():
            lo, hi = (float(q) for q in k.split('-'))
            if lo >= 5:
                x.append((lo + hi) / 2)
                y.append(v['v'])
        b.plot(x, y, color=COL[d], marker='o', ms=6, label=NAME[d])
    b.set_xlabel('Radius of the turn on the map, m')
    b.set_ylabel('Speed through the turn, m/s')
    b.set_ylim(0, 10)
    b.legend(loc='lower right')
    fig.savefig(out / 'city.png', dpi=130)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--only')
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (braking, launch, curves, time_gap, discharge, free_flow, stopping, maps, jerk, city):
        if a.only and f.__name__ != a.only:
            continue
        try:
            f(a.data, out)
            print(f.__name__, 'ok', flush=True)
        except Exception as e:
            print(f.__name__, 'FAILED', repr(e), flush=True)


if __name__ == '__main__':
    main()
