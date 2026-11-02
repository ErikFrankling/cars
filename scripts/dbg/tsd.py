"""`cars tsd`: position against time on a road, coloured by speed, beside real tracks; flow, density and speed by metre and minute (Edie's definitions)."""
import argparse
import json
import os

import numpy as np

from .real import load_real, real_sets
from .run import Run, lanes_of, pos_of, speeds_of, trips_of


def section(net, edges, lanes=None):
    """Metres along the road for each lane, and the length of the section."""
    offset = np.full(net.n_lanes, np.nan)
    at = 0.0
    if lanes is not None:
        for l in lanes:
            offset[net.lane_by_id[l]] = 0.0
        return offset, float(max(net.lane_length[net.lane_by_id[l]] for l in lanes))
    for n, e in enumerate(edges):
        ls = net.lanes_of_edge(e)
        for l in ls:
            offset[l] = at
        length = float(net.lane_length[ls[0]])
        if n + 1 < len(edges):
            to = net.edge_index[edges[n + 1]]
            across = 0.0
            for l in ls:
                start, count = int(net.lane_links_start[l]), int(net.lane_links_count[l])
                for k in range(start, start + count):
                    if net.link_to_edge[k] != to:
                        continue
                    lane = int(net.link_next_lane[k])
                    along = at + length
                    walked = 0.0
                    for _ in range(6):
                        if not net.lane_internal[lane]:
                            break
                        offset[lane] = along + walked
                        walked += float(net.lane_length[lane])
                        s2, c2 = int(net.lane_links_start[lane]), int(net.lane_links_count[lane])
                        if c2 == 0:
                            break
                        lane = int(net.link_next_lane[s2])
                    across = max(across, walked)
            at += length + across
        else:
            at += length
    return offset, at


def collect(run, offset, begin, end, length):
    t, s, v, trip, lane = [], [], [], [], []
    for i in run.window(begin, end):
        rec, _ = run.read(i)
        l = lanes_of(rec)
        known = l < len(offset)
        keep = np.zeros(len(rec), dtype=bool)
        keep[known] = np.isfinite(offset[l[known]])
        if not keep.any():
            continue
        r = rec[keep]
        s.append(offset[l[keep]] + pos_of(r))
        v.append(speeds_of(r))
        trip.append(trips_of(r))
        lane.append(l[keep])
        t.append(np.full(len(r), run.times[i]))
    if not t:
        return None
    return dict(t=np.concatenate(t), s=np.concatenate(s), v=np.concatenate(v), trip=np.concatenate(trip), lane=np.concatenate(lane))


def edie(d, dt, dx, length, t0, t1):
    """Flow per hour, density per km and speed in km/h per cell, from every sample's time and distance."""
    nt = max(int(np.ceil((t1 - t0) / dt)), 1)
    nx = max(int(np.ceil(length / dx)), 1)
    step = d['dt']
    # A sample covers the road it drove in its step, so a fast car does not paint stripes.
    pieces = np.clip(np.ceil(d['v'] * step / dx).astype(int), 1, 16)
    rep = np.repeat(np.arange(len(pieces)), pieces)
    frac = (np.arange(len(rep)) - np.repeat(np.cumsum(pieces) - pieces, pieces) + 0.5) / pieces[rep]
    s_at = d['s'][rep] + frac * d['v'][rep] * step
    t_at = d['t'][rep] + frac * step
    w = step / pieces[rep]
    it = np.clip(((t_at - t0) / dt).astype(int), 0, nt - 1)
    ix = np.clip((s_at / dx).astype(int), 0, nx - 1)
    time_in = np.zeros((nt, nx))
    dist_in = np.zeros((nt, nx))
    np.add.at(time_in, (it, ix), w)
    np.add.at(dist_in, (it, ix), d['v'][rep] * w)
    area = dt * dx
    q = dist_in / area * 3600.0
    k = time_in / area * 1000.0
    with np.errstate(invalid='ignore', divide='ignore'):
        u = np.where(time_in > 0, dist_in / time_in * 3.6, np.nan)
    return q, k, u


def diagram(ax, d, vmax, length, title, xlim):
    """Each car a line, coloured by speed. Too many samples to draw as lines become dots."""
    from matplotlib.collections import LineCollection
    order = np.lexsort((d['t'], d['trip']))
    t, s, v, trip = d['t'][order], d['s'][order], d['v'][order], d['trip'][order]
    step = float(np.median(np.diff(np.unique(t)))) if len(np.unique(t)) > 1 else 1.0
    same = (trip[:-1] == trip[1:]) & (np.diff(t) <= 2.5 * step)
    if same.sum() <= 1_500_000:
        seg = np.stack([np.c_[t[:-1][same], s[:-1][same]], np.c_[t[1:][same], s[1:][same]]], axis=1)
        lc = LineCollection(seg, cmap='turbo_r', linewidths=0.7, rasterized=True)
        lc.set_array(v[:-1][same] * 3.6)
        lc.set_clim(0, vmax * 3.6)
        art = ax.add_collection(lc)
    else:
        art = ax.scatter(t, s, c=v * 3.6, s=0.6, cmap='turbo_r', vmin=0, vmax=vmax * 3.6, linewidths=0, rasterized=True)
    ax.set(xlabel='time, s', ylabel='metres along the road', title=title, ylim=(0, length), xlim=xlim)
    return art


def panel_heat(fig, ax, grid, t0, t1, length, title, cmap, vmax=None):
    im = ax.imshow(grid.T, origin='lower', aspect='auto', extent=(t0, t1, 0, length), cmap=cmap, vmin=0, vmax=vmax, interpolation='nearest')
    ax.set(xlabel='time, s', ylabel='metres', title=title)
    fig.colorbar(im, ax=ax, fraction=0.04)


def main(argv):
    a = argparse.ArgumentParser(prog='cars tsd', description=__doc__)
    a.add_argument('--trace', required=True)
    a.add_argument('--edge', help='one road')
    a.add_argument('--route', help='roads in driving order, comma separated, drawn as one section')
    a.add_argument('--lane', help='lanes, comma separated: one panel each')
    a.add_argument('--by-lane', action='store_true', help='one diagram per lane number of the road')
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a.add_argument('--real', help=f'real tracks beside it, name[:lane=N] with name one of {", ".join(real_sets())}, or a CSV of time,track,pos,speed[,lane]')
    a.add_argument('--real-begin', type=float, help='first second of the real data to show. Default its first')
    a.add_argument('--bin-t', type=float, default=60.0, help='heatmap seconds')
    a.add_argument('--bin-x', type=float, default=10.0, help='heatmap metres')
    a.add_argument('--net')
    a.add_argument('--out', default='tsd')
    a = a.parse_args(argv)
    run = Run(a.trace, a.net)
    net = run.net
    edges = a.route.split(',') if a.route else ([a.edge] if a.edge else [])
    lanes = a.lane.split(',') if a.lane else None
    if not edges and not lanes:
        raise SystemExit('give --edge, --route or --lane')
    offset, length = section(net, edges, lanes)
    d = collect(run, offset, a.begin, a.end, length)
    if d is None:
        raise SystemExit('nothing on that road in that time')
    d['dt'] = run.dt
    t0, t1 = float(d['t'].min()), float(d['t'].max()) + run.dt
    if lanes:
        lane_groups = [(net.lane_name(l), d['lane'] == l) for l in np.unique(d['lane'])]
    elif a.by_lane:
        # By lane number, with junction lanes kept in the number they sit in.
        number = net.lane_index[d['lane']]
        lane_groups = [(f'lane {n}', number == n) for n in np.unique(number)]
    else:
        lane_groups = [('all lanes', np.ones(len(d['t']), dtype=bool))]
    real = load_real(a.real, a.real_begin, t1 - t0) if a.real else None
    n_lane = max(int(sum(net.edge_lanes[net.edge_index[e]] for e in edges) / max(len(edges), 1)), 1) if edges else 1
    q, k, u = edie(d, a.bin_t, a.bin_x, length, t0, t1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(a.out, exist_ok=True)
    panels = len(lane_groups) + (1 if real else 0)
    vmax = max(float(d['v'].max()), 13.9)
    if real:
        vmax = max(vmax, float(np.percentile(real['v'], 99.5)))
    fig, axs = plt.subplots(panels, 1, figsize=(13, 3.6 * panels + 0.8), squeeze=False)
    for n, (name, mask) in enumerate(lane_groups):
        sub = {x: d[x][mask] for x in ('t', 's', 'v', 'trip')}
        sc = diagram(axs[n][0], sub, vmax, length, f'Simulated: {name}, {length:.0f} m', (t0, t1))
    if real:
        rd = dict(t=real['t'], s=real['s'], v=real['v'], trip=real['track'])
        sc = diagram(axs[-1][0], rd, vmax, max(length, float(real['s'].max())), f"Real: {real['name']}, same colours", (float(real['t'].min()), float(real['t'].max())))
    fig.tight_layout()
    fig.colorbar(sc, ax=[x[0] for x in axs], label='km/h', fraction=0.02)
    path = os.path.join(a.out, 'tsd.png')
    fig.savefig(path, dpi=120)
    plt.close(fig)
    fig, axs = plt.subplots(3, 2 if real else 1, figsize=(15 if real else 11, 10), squeeze=False)
    panel_heat(fig, axs[0][0], q / n_lane, t0, t1, length, 'Simulated flow, veh/h per lane', 'viridis')
    panel_heat(fig, axs[1][0], k / n_lane, t0, t1, length, 'Simulated density, veh/km per lane', 'magma')
    panel_heat(fig, axs[2][0], u, t0, t1, length, 'Simulated speed, km/h', 'RdYlGn', vmax * 3.6)
    if real:
        r = dict(t=real['t'], s=real['s'], v=real['v'], dt=real['dt'])
        rt0, rt1, rl = float(real['t'].min()), float(real['t'].max()) + real['dt'], float(real['s'].max())
        rq, rk, ru = edie(r, a.bin_t, a.bin_x, rl, rt0, rt1)
        nl = real.get('lanes', 1)
        panel_heat(fig, axs[0][1], rq / nl, rt0, rt1, rl, 'Real flow, veh/h per lane', 'viridis')
        panel_heat(fig, axs[1][1], rk / nl, rt0, rt1, rl, 'Real density, veh/km per lane', 'magma')
        panel_heat(fig, axs[2][1], ru, rt0, rt1, rl, 'Real speed, km/h', 'RdYlGn', vmax * 3.6)
    fig.tight_layout()
    heat = os.path.join(a.out, 'heat.png')
    fig.savefig(heat, dpi=110)
    plt.close(fig)
    csv = os.path.join(a.out, 'heat.csv')
    with open(csv, 'w') as f:
        f.write('time,metre,flow_vph,density_vpkm,speed_kmh\n')
        for it in range(q.shape[0]):
            for ix in range(q.shape[1]):
                if k[it, ix] > 0:
                    f.write(f'{t0 + it * a.bin_t:.0f},{ix * a.bin_x:.0f},{q[it, ix]:.1f},{k[it, ix]:.2f},{u[it, ix]:.2f}\n')
    summary = dict(length_m=round(length, 1), lanes=n_lane, time=[t0, t1], cars=int(len(np.unique(d['trip']))), samples=len(d['t']),
                   mean_speed_kmh=round(float(d['v'].mean() * 3.6), 2), max_density_vpkm=round(float(k.max() / n_lane), 1), max_flow_vph=round(float(q.max() / n_lane), 0),
                   share_below_5kmh=round(float((d['v'] < 5 / 3.6).mean()), 3))
    low = np.nanmin(u, axis=0) if np.isfinite(u).any() else None
    if low is not None:
        jam = np.nonzero(low < 15)[0]
        if len(jam):
            summary['slower_than_15kmh_between_m'] = [float(jam.min() * a.bin_x), float((jam.max() + 1) * a.bin_x)]
    if real:
        summary['real'] = dict(name=real['name'], cars=int(len(np.unique(real['track']))), mean_speed_kmh=round(float(real['v'].mean() * 3.6), 2), share_below_5kmh=round(float((real['v'] < 5 / 3.6).mean()), 3))
    print(json.dumps(summary, indent=1))
    print(f'diagram {path}\nheatmaps {heat}\ntable {csv}')
