"""`cars compare`: real against simulated at any level. Per-sensor time series, an error map, error by road class, hour and junction type, and the worst sensors with reasons they might be.

--ref takes a long CSV: sensor,edge,time,flow_vph[,speed_kmh]. `time` is seconds from midnight of the interval's start, `-1` for a whole-day figure.
With --ref-format site_hours, --ref is the site_hours.csv that scripts/reference_day.py writes: it already holds real and simulated values per matched site and hour, with the spread of normal days, so --sim is not needed.
--sim takes `cars run --edge-csv` output, with --edge-interval as its interval."""
import argparse
import json
import os

import numpy as np
import pandas as pd

from .run import Net, ensure_net


def read_sim(path, scale):
    d = pd.read_csv(path)
    interval = float(np.median(np.diff(np.sort(d['begin'].unique())))) if d['begin'].nunique() > 1 else 3600.0
    d['flow_vph'] = d['entered'] / interval * 3600.0 * scale
    with np.errstate(invalid='ignore', divide='ignore'):
        d['speed_kmh'] = np.where(d['samples'] > 0, d['distance'] / d['samples'] * 3.6, np.nan)
    return d, interval


def read_ref(path, fmt, day_seconds):
    d = pd.read_csv(path)
    if fmt == 'stockholm':
        # truth/stockholm/factorial/count_clean.csv: daily figures and shares by period, per edge.
        rows = []
        split = day_seconds
        for _, r in d.iterrows():
            rows.append(dict(sensor=str(r['feature'])[-12:], edge=r['edge'], time=-1, flow_vph=float(r['daily']) / (split / 3600.0) / max(float(r.get('directions', 1)), 1.0), method=r.get('method', ''), year=r.get('year', '')))
        return pd.DataFrame(rows)
    if fmt == 'site_hours':
        return pd.DataFrame(dict(sensor=d['site'].astype(str), edge=d['edge'].astype(str), time=d['hour'] * 3600.0, flow_vph=d['flow'], speed_kmh=d['speed'], sim_flow=d['sim'], sim_speed=d['sim_speed'], sim_teleports=0.0, noise_geh=d.get('geh_noise'), real_p10=d.get('flow_p10'), real_p90=d.get('flow_p90')))
    return d


def geh(sim, ref):
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(sim + ref > 0, np.sqrt(2 * (sim - ref) ** 2 / (sim + ref)), 0.0)


def join(sim, interval, ref, begin_ok):
    """Mean simulated flow and speed over each reference row's time."""
    daily = ref['time'] < 0
    rows = []
    by_edge = {e: g for e, g in sim.groupby('edge')}
    span = (sim['begin'].max() - sim['begin'].min() + interval) if len(sim) else interval
    for _, r in ref.iterrows():
        g = by_edge.get(r['edge'])
        if g is None:
            rows.append((0.0, np.nan, 0.0))
            continue
        if r['time'] >= 0:
            width = r.get('width', 3600.0) if 'width' in ref else 3600.0
            g = g[(g['begin'] >= r['time']) & (g['begin'] < r['time'] + width)]
            n = max(width / interval, 1.0)
        else:
            n = span / interval
        if not len(g):
            rows.append((0.0, np.nan, 0.0))
            continue
        flow = float(g['flow_vph'].sum() / n)
        samples = float(g['samples'].sum())
        speed = float(g['distance'].sum() / samples * 3.6) if samples > 0 else np.nan
        rows.append((flow, speed, float(g['teleports'].sum()) if 'teleports' in g else 0.0))
    out = ref.copy()
    out['sim_flow'], out['sim_speed'], out['sim_teleports'] = zip(*rows)
    return out


def why_this_bad(row, free_speed):
    """Plain guesses from what the row itself shows, to send a person or an agent to the right place first."""
    r, s = row['flow_vph'], row['sim_flow']
    out = []
    if row['road'] == 'not in net':
        out.append('this edge is not in this net: the sensor was matched on another net')
    elif s == 0:
        out.append('no simulated traffic on this edge: not on any route, or the sensor is matched to a wrong or side edge')
    elif s < 0.5 * r:
        if row['sim_speed'] < 0.4 * free_speed:
            out.append('too little flow and slow: congestion holds it, look upstream with `cars jam --edge`')
        else:
            out.append('too little flow at free speed: demand or routes miss this road')
    elif s > 1.5 * r:
        if row['road'] in ('highway.residential', 'highway.living_street', 'highway.unclassified', 'highway.tertiary'):
            out.append('too much flow on a minor road: routes cut through, assignment or a missing major link')
        else:
            out.append('too much flow: sensor may be one direction of two, or demand too high')
    if 'real_p10' in row and pd.notna(row['real_p10']) and row['real_p10'] <= s <= row['real_p90']:
        out.append('inside what normal days do here')
    if row['sim_teleports'] > 0:
        out.append(f"{int(row['sim_teleports'])} teleports here")
    if 'speed_kmh' in row and pd.notna(row.get('speed_kmh')) and pd.notna(row['sim_speed']) and row['sim_speed'] < row['speed_kmh'] - 15:
        out.append(f"{row['speed_kmh'] - row['sim_speed']:.0f} km/h slower than real")
    if row.get('method') == 'Skattad trafik':
        out.append('reference is an estimate, not a measured count')
    return '; '.join(out)


def group(df, key):
    rows = []
    for k, g in df.groupby(key):
        if len(g) < 1:
            continue
        rows.append(dict(group=k, sites=len(g), ref=round(float(g['flow_vph'].sum()), 0), sim=round(float(g['sim_flow'].sum()), 0), ratio=round(float(g['sim_flow'].sum() / max(g['flow_vph'].sum(), 1e-9)), 3),
                         mape=round(float((np.abs(g['sim_flow'] - g['flow_vph']) / g['flow_vph'].clip(lower=1)).mean()), 3), geh_median=round(float(np.median(g['geh'])), 2), share_geh_under_5=round(float((g['geh'] < 5).mean()), 3)))
    return sorted(rows, key=lambda r: -r['ref'])


def main(argv):
    a = argparse.ArgumentParser(prog='cars compare', description=__doc__)
    a.add_argument('--sim', help='edge CSV from `cars run --edge-csv`')
    a.add_argument('--ref', required=True, help='reference CSV')
    a.add_argument('--ref-format', default='long', choices=['long', 'stockholm', 'site_hours'])
    a.add_argument('--net', required=True, help='the net, or a `cars netinfo` or `<trace>.net.json` file')
    a.add_argument('--scale', type=float, default=1.0, help='multiply simulated flows, when demand was scaled')
    a.add_argument('--day-seconds', type=float, default=86400.0, help='seconds that a whole-day reference spreads over')
    a.add_argument('--top', type=int, default=20)
    a.add_argument('--series', type=int, default=9, help='sensors in the time series chart')
    a.add_argument('--out', default='compare')
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    if a.net.endswith('.json'):
        net = Net(a.net)
    else:
        stamp = int(os.path.getmtime(a.net))
        side = os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'cars-dbg', f'{os.path.basename(a.net)}.{stamp}.json')
        if not os.path.exists(side):
            os.makedirs(os.path.dirname(side) or '.', exist_ok=True)
            import subprocess
            subprocess.run([os.environ.get('CARS_BIN', 'cars'), 'netinfo', '--net', a.net, '--out', side], check=True)
        net = Net(side)
    ref = read_ref(a.ref, a.ref_format, a.day_seconds)
    ref = ref[ref['flow_vph'].notna()].copy()
    if a.ref_format == 'site_hours':
        d = ref[ref['sim_flow'].notna()].copy()
    else:
        if not a.sim:
            raise SystemExit('--sim is needed with this --ref-format')
        sim, interval = read_sim(a.sim, a.scale)
        d = join(sim, interval, ref, None)
    d['geh'] = geh(d['sim_flow'].to_numpy(), d['flow_vph'].to_numpy())
    d['err'] = d['sim_flow'] - d['flow_vph']
    if 'noise_geh' in d:
        # How far outside what one real day does compared with another.
        d['beyond_noise'] = d['geh'] - d['noise_geh'].fillna(0.0)
    known = [net.edge_index.get(e) for e in d['edge']]
    d['road'] = [net.edge_road[k] if k is not None else 'not in net' for k in known]
    d['junction_type'] = [net.junction_type.get(net.edge_to[k], '') if k is not None else '' for k in known]
    d['hour'] = np.where(d['time'] >= 0, (d['time'] // 3600).astype(int), -1)
    free = np.array([float(net.lane_speed[net.edge_first[k]]) * 3.6 if k is not None else 50.0 for k in known])
    d['free_kmh'] = free
    d['why'] = [why_this_bad(r, r['free_kmh']) for _, r in d.iterrows()]
    sites = d.groupby('sensor').agg(flow_vph=('flow_vph', 'mean'), sim_flow=('sim_flow', 'mean'), geh=('geh', 'mean'), edge=('edge', 'first'), road=('road', 'first')).reset_index()
    # The reason its worst row gives, which for a sensor series is its worst hour.
    worst_row = d.loc[d.groupby('sensor')['geh'].idxmax(), ['sensor', 'why']]
    sites = sites.merge(worst_row, on='sensor')
    sites['abs_err'] = (sites['sim_flow'] - sites['flow_vph']).abs()
    worst = sites.sort_values('geh', ascending=False).head(a.top)
    missing = int(d.loc[d['road'] == 'not in net', 'sensor'].nunique())
    total = dict(rows=len(d), sensors_not_in_net=missing, sites=int(d['sensor'].nunique()), ref_sum=round(float(d['flow_vph'].sum()), 0), sim_sum=round(float(d['sim_flow'].sum()), 0), ratio=round(float(d['sim_flow'].sum() / max(d['flow_vph'].sum(), 1e-9)), 3), geh_median=round(float(np.median(d['geh'])), 2), share_geh_under_5=round(float((d['geh'] < 5).mean()), 3), correlation=round(float(np.corrcoef(d['sim_flow'], d['flow_vph'])[0, 1]), 3) if len(d) > 2 else None)
    report = dict(total=total, by_road=group(d, 'road'), by_hour=group(d[d['hour'] >= 0], 'hour') if (d['hour'] >= 0).any() else [], by_junction_type=group(d, 'junction_type'), worst=worst[['sensor', 'edge', 'road', 'flow_vph', 'sim_flow', 'geh', 'why']].round(1).to_dict('records'))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'compare.json'), 'w') as f:
        json.dump(report, f, indent=1, default=str)
    d.drop(columns=['free_kmh']).to_csv(os.path.join(a.out, 'rows.csv'), index=False)
    if a.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        print(json.dumps(total))
        for title, rows in (('road class', report['by_road'][:14]), ('hour', report['by_hour']), ('junction type at the end of the road', report['by_junction_type'])):
            if rows:
                print(f'\nby {title}:')
                print(f"  {'':<26} {'sites':>6} {'ref':>10} {'sim':>10} {'ratio':>6} {'median GEH':>10} {'GEH<5':>6}")
                for r in rows:
                    print(f"  {str(r['group'])[:26]:<26} {r['sites']:6} {r['ref']:10.0f} {r['sim']:10.0f} {r['ratio']:6.2f} {r['geh_median']:10.1f} {r['share_geh_under_5']:6.2f}")
        print(f"\nworst {len(worst)} sensors:")
        for _, r in worst.iterrows():
            print(f"  {str(r['sensor'])[:18]:<18} {str(r['edge'])[:22]:<22} {str(r['road']).replace('highway.', '')[:16]:<16} ref {r['flow_vph']:7.0f} sim {r['sim_flow']:7.0f} GEH {r['geh']:5.1f}  {r['why']}")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(15, 7))
    xs, ys, cs = [], [], []
    for _, r in sites.iterrows():
        k = net.edge_index.get(r['edge'])
        if k is None:
            continue
        lane = int(net.edge_first[k])
        xs.append((net.lane_x0[lane] + net.lane_x1[lane]) / 2)
        ys.append((net.lane_y0[lane] + net.lane_y1[lane]) / 2)
        cs.append((r['sim_flow'] - r['flow_vph']) / max(r['flow_vph'], 1.0))
    axs[0].plot(np.c_[net.lane_x0[::4], net.lane_x1[::4]].T, np.c_[net.lane_y0[::4], net.lane_y1[::4]].T, color='#e0e0e0', lw=0.25)
    sc = axs[0].scatter(xs, ys, c=np.clip(cs, -1, 1), cmap='coolwarm', s=16, vmin=-1, vmax=1, edgecolor='#333', lw=0.15)
    fig.colorbar(sc, ax=axs[0], fraction=0.035, label='(sim - real) / real, red is too much')
    axs[0].set(aspect='equal', title='Error map')
    axs[1].scatter(d['flow_vph'], d['sim_flow'], s=6, alpha=0.5)
    top = float(max(d['flow_vph'].max(), d['sim_flow'].max(), 1))
    axs[1].plot([0, top], [0, top], color='black', lw=0.8)
    axs[1].set(xlabel='real, veh/h', ylabel='simulated, veh/h', title=f"correlation {total['correlation']}, sim/real {total['ratio']}, median GEH {total['geh_median']}")
    fig.tight_layout()
    path = os.path.join(a.out, 'map.png')
    fig.savefig(path, dpi=110)
    plt.close(fig)
    timed = d[d['time'] >= 0]
    worst_ids = list(worst['sensor'])[:a.series]
    if len(timed) and a.series:
        cols = 3
        rows = int(np.ceil(len(worst_ids) / cols)) or 1
        fig, axs = plt.subplots(rows, cols, figsize=(15, 3 * rows), squeeze=False)
        for ax, s in zip(axs.flat, worst_ids):
            g = timed[timed['sensor'] == s].sort_values('time')
            ax.plot(g['time'] / 3600, g['flow_vph'], label='real', color='black')
            ax.plot(g['time'] / 3600, g['sim_flow'], label='sim', color='#e45756')
            ax.set(title=str(s)[:30], xlabel='hour', ylabel='veh/h')
            ax.legend(fontsize=7)
        fig.tight_layout()
        series = os.path.join(a.out, 'series.png')
        fig.savefig(series, dpi=110)
        plt.close(fig)
        print(f'series {series}')
    print(f"map {path}\nreport {os.path.join(a.out, 'compare.json')}\nrows {os.path.join(a.out, 'rows.csv')}")
