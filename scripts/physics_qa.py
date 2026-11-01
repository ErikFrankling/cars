#!/usr/bin/env python3
"""Does the motion in an FCD file or a trace make physical sense? Reports findings, changes nothing.

    cars run --net n.xml --routes r.xml --dt .1 --end 300 --trace f.trace 2> run.log
    python3 scripts/physics_qa.py --net n.xml --trace f.trace --log run.log --out qa/

A trace is the same run the pictures of `cars replay` come from, and names its teleports and
collisions. --fcd takes the CSV of `cars run --fcd` instead.

Thresholds come from research/truth/11-vehicle-physics.md, which grades them: dry tyre braking is
measured, comfort targets are design values. Nothing here decides what is acceptable.
"""
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

import cars_trace

BOUNDS = dict(
    accel_comfort=2.0,        # design target, car normal driving
    brake_comfort=-2.5,       # design target, car normal driving
    brake_type=-4.5,          # the default decel of the vehicle type
    brake_dry_limit=-8.91,    # best measured dry braking in the ADAC tyre test
    jerk_comfort=1.0,         # design target, car normal driving
    jerk_suspect=10.0,        # screening value, no physical claim
    lateral_comfort=1.5,      # design target
    lateral_high=4.0,         # asked for; far beyond normal driving
    lateral_tyre=8.0,         # close to the dry tyre limit, .85 g
)
TELEPORT_ACCEL = -20.0        # no road vehicle does this; only an administrative stop can
CURVE_WINDOW = 5.0            # metres, about a car, so polyline kinks do not read as 1 m radii
HEADING_STEP = 15.0           # degrees between two samples, screening value
CONNECTOR_KINK = 5.0          # degrees between the end of a lane and the start of the next
CONNECTOR_GAP = 0.5           # metres between the same two points


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


class Lanes:
    """Lane polylines for the lanes that appear in the data, with SUMO's length scaling."""

    def __init__(self, net, wanted):
        self.shape, self.s, self.length, self.limit, self.junction = {}, {}, {}, {}, {}
        self.next = defaultdict(set)
        self.edge = {}
        self.internal = set()
        with open(net, 'rb') as f:
            for _, e in etree.iterparse(f, events=('end',), tag=('edge', 'junction', 'connection')):
                if e.tag == 'edge':
                    internal = e.get('function') == 'internal'
                    for l in e:
                        if l.tag != 'lane':
                            continue
                        i = l.get('id')
                        self.edge[i] = e.get('id')
                        if internal:
                            self.internal.add(i)
                        if i in wanted:
                            p = np.array([[float(v) for v in q.split(',')[:2]] for q in l.get('shape').split()])
                            self.shape[i] = p
                            self.s[i] = np.concatenate(([0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))))
                            self.length[i] = float(l.get('length'))
                            self.limit[i] = float(l.get('speed'))
                elif e.tag == 'junction':
                    for i in (e.get('intLanes') or '').split():
                        self.junction[i] = e.get('id')
                elif e.tag == 'connection':
                    a, b = f"{e.get('from')}_{e.get('fromLane')}", f"{e.get('to')}_{e.get('toLane')}"
                    via = e.get('via')
                    if via:
                        self.next[a].add(via)
                    else:
                        self.next[a].add(b)
                e.clear()
        self.curve = {i: self.curvature(i) for i in self.shape}

    def curvature(self, i):
        """Heading change per metre over the curve window, sampled each metre along the geometry."""
        p, s = self.shape[i], self.s[i]
        n = int(s[-1]) + 2
        at = np.arange(n, dtype=float)
        half = CURVE_WINDOW / 2
        k = np.zeros(n)
        heading = np.arctan2(*np.diff(p, axis=0).T[::-1])
        index = np.clip(np.searchsorted(s, at, side='right') - 1, 0, len(heading) - 1)
        lo = np.clip(np.searchsorted(s, at - half, side='right') - 1, 0, len(heading) - 1)
        hi = np.clip(np.searchsorted(s, at + half, side='right') - 1, 0, len(heading) - 1)
        span = np.maximum(np.minimum(at + half, s[-1]) - np.maximum(at - half, 0), 1.0)
        k = np.abs(wrap(heading[hi] - heading[lo])) / span
        return k

    def mean_radius(self, i):
        """Length of the whole lane over its total turning: what a smooth curve would be."""
        h = np.arctan2(*np.diff(self.shape[i], axis=0).T[::-1])
        turn = np.abs(wrap(np.diff(h))).sum() if len(h) > 1 else 0.0
        return self.s[i][-1] / max(turn, 1e-4)

    def place(self, frame):
        """Adds x, y, heading and curvature to rows of one lane."""
        i = frame.name
        p, s = self.shape[i], self.s[i]
        d = np.clip(frame['pos'].to_numpy() / max(self.length[i], 1e-3), 0, 1) * s[-1]
        k = np.clip(np.searchsorted(s, d, side='right') - 1, 0, len(p) - 2)
        h = np.arctan2(p[k + 1, 1] - p[k, 1], p[k + 1, 0] - p[k, 0])
        u = np.clip((d - s[k]) / np.maximum(s[k + 1] - s[k], 1e-3), 0, 1)
        return pd.DataFrame({
            'x': p[k, 0] + (p[k + 1, 0] - p[k, 0]) * u,
            'y': p[k, 1] + (p[k + 1, 1] - p[k, 1]) * u,
            'heading': h,
            'kappa': self.curve[i][np.clip(d.astype(int), 0, len(self.curve[i]) - 1)],
        }, index=frame.index)

    def reachable(self, a, b, hops=4):
        """Can a car get from lane a to lane b along connections? One step at dt 1 can skip lanes."""
        seen, front = {a}, {a}
        for _ in range(hops):
            front = {n for x in front for n in self.next.get(x, ())} - seen
            if b in front:
                return True
            seen |= front
        return False

    def end_point(self, i, back):
        """Point this far from the lane's end, or from its start for a negative distance."""
        s, p = self.s[i], self.shape[i]
        d = s[-1] - back if back > 0 else -back
        d = min(max(d, 0.0), s[-1])
        return np.array([np.interp(d, s, p[:, 0]), np.interp(d, s, p[:, 1])])

    def connector(self, a, b):
        """Heading kink in degrees and position gap in metres where lane a meets lane b.
        Uses 2 m of each lane, as nets often end a lane in a segment of a few millimetres."""
        pa, pb = self.shape[a][-1], self.shape[b][0]
        u, v = pa - self.end_point(a, 2.0), self.end_point(b, -2.0) - pb
        kink = wrap(math.atan2(v[1], v[0]) - math.atan2(u[1], u[0]))
        return abs(math.degrees(kink)), float(np.hypot(*(pb - pa)))


def rectangle(r):
    ux, uy = math.cos(r.body), math.sin(r.body)
    cx, cy = r.x - ux * r.length / 2, r.y - uy * r.length / 2
    return np.array([[cx + ux * a - uy * b, cy + uy * a + ux * b]
                     for a, b in ((-r.length / 2, -r.width / 2), (r.length / 2, -r.width / 2), (r.length / 2, r.width / 2), (-r.length / 2, r.width / 2))])


def penetration(a, b):
    """Separating axis test. Positive depth means the bodies overlap by that many metres."""
    ca, cb = rectangle(a), rectangle(b)
    depth = 1e9
    for h in (a.body, a.body + math.pi / 2, b.body, b.body + math.pi / 2):
        axis = np.array([math.cos(h), math.sin(h)])
        pa, pb = ca @ axis, cb @ axis
        depth = min(depth, min(pa.max(), pb.max()) - max(pa.min(), pb.min()))
        if depth <= 0:
            return 0.0
    return depth


def same_lane_gaps(df, lanes):
    """Negative bumper gaps on a lane, counting tails that hang back from the next lane."""
    tails = df[(df['pos'] < df['length']) & df['prev_lane'].isin(lanes.length)].copy()
    tails = tails[np.array([b in lanes.next.get(a, ()) for a, b in zip(tails['prev_lane'], tails['lane'])], dtype=bool)]
    tails['pos'] = tails['pos'] + tails['prev_lane'].map(lanes.length)
    tails['lane'] = tails['prev_lane']
    rows = pd.concat([df[['time', 'trip', 'lane', 'pos', 'length']], tails[['time', 'trip', 'lane', 'pos', 'length']]])
    rows = rows.sort_values(['time', 'lane', 'pos'], kind='stable').reset_index(drop=True)
    same = (rows['time'].shift(-1) == rows['time']) & (rows['lane'].shift(-1) == rows['lane'])
    gap = rows['pos'].shift(-1) - rows['length'].shift(-1) - rows['pos']
    mask = (same & (gap < -0.05)).to_numpy()
    trips = rows['trip'].to_numpy(dtype=object)
    bad = rows[mask].assign(gap=gap.to_numpy()[mask], other=np.roll(trips, -1)[mask])
    if bad.empty:
        return pd.DataFrame(columns=['pair', 'lane', 'first', 'samples', 'worst'])
    bad['pair'] = [' & '.join(sorted(p)) for p in zip(bad['trip'].astype(str), bad['other'].astype(str))]
    return bad.groupby(['pair', 'lane'], as_index=False).agg(first=('time', 'min'), samples=('time', 'size'), worst=('gap', 'min')).sort_values('worst')


def junction_overlaps(df, lanes, limit):
    """Body overlaps between vehicles on different internal lanes of one junction."""
    rows = df[df['lane'].isin(lanes.junction)].assign(junction=lambda d: d['lane'].map(lanes.junction))
    found = defaultdict(lambda: dict(samples=0, worst=0.0, first=None))
    checked = 0
    for (time, junction), g in rows.groupby(['time', 'junction'], sort=False):
        if g['lane'].nunique() < 2:
            continue
        items = list(g.itertuples())
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if a.lane == b.lane or math.hypot(a.x - b.x, a.y - b.y) > a.length + b.length + 3:
                    continue
                checked += 1
                d = penetration(a, b)
                if d > 0.05:
                    start_a, start_b = lanes.shape[a.lane][0], lanes.shape[b.lane][0]
                    end_a, end_b = lanes.shape[a.lane][-1], lanes.shape[b.lane][-1]
                    kind = 'diverge' if np.hypot(*(start_a - start_b)) < 1 else 'merge' if np.hypot(*(end_a - end_b)) < 1 else 'crossing'
                    key = (' & '.join(sorted((a.trip, b.trip))), junction, kind)
                    f = found[key]
                    f['samples'] += 1
                    f['worst'] = max(f['worst'], d)
                    f['first'] = time if f['first'] is None else f['first']
        if checked > limit:
            break
    out = [dict(pair=k[0], junction=k[1], kind=k[2], **v) for k, v in found.items()]
    frame = pd.DataFrame(out, columns=['pair', 'junction', 'kind', 'samples', 'worst', 'first'])
    return frame.sort_values('worst', ascending=False), checked > limit


def body_heading(df, lanes):
    """Heading of the chord from rear to front bumper, the way the renderer places a car."""
    rear = df[['lane', 'pos']].assign(pos=df['pos'] - df['length'])
    tail = (rear['pos'] < 0).to_numpy() & df['prev_lane'].isin(lanes.shape).to_numpy()
    tail &= np.array([b in lanes.next.get(a, ()) for a, b in zip(df['prev_lane'], df['lane'])], dtype=bool)
    rear.loc[tail, 'lane'] = df.loc[tail, 'prev_lane']
    rear.loc[tail, 'pos'] = rear.loc[tail, 'pos'] + df.loc[tail, 'prev_lane'].map(lanes.length)
    at = rear.groupby('lane', sort=False)[['pos']].apply(lanes.place).reset_index(level=0, drop=True).reindex(df.index)
    dx, dy = (df['x'] - at['x']).to_numpy(), (df['y'] - at['y']).to_numpy()
    short = np.hypot(dx, dy) < 0.2 * df['length'].to_numpy()
    return np.where(short, df['heading'].to_numpy(), np.arctan2(dy, dx))


def percentiles(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {}
    q = np.percentile(values, [0, 1, 50, 99, 100])
    return dict(zip(('min', 'p1', 'p50', 'p99', 'max'), map(float, q)), n=int(values.size))


def table(frame, columns=None, digits=2):
    if frame is None or len(frame) == 0:
        return ['None found.', '']
    frame = frame[columns] if columns else frame
    head = ['| ' + ' | '.join(frame.columns) + ' |', '|' + '---|' * len(frame.columns)]
    fmt = lambda v: f'{v:.{digits}f}' if isinstance(v, (float, np.floating)) else str(v)
    return head + ['| ' + ' | '.join(fmt(v) for v in row) + ' |' for row in frame.itertuples(index=False)] + ['']


def figure(out, d, summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ink, grid, bar = '#3b3b3b', '#e4e4e4', '#2a78b5'
    panels = [
        ('Longitudinal acceleration, m/s²', d['acc'], [(BOUNDS['brake_comfort'], 'comfort'), (BOUNDS['brake_dry_limit'], 'dry tyre limit')]),
        ('Jerk magnitude, m/s³', d['jerk'], [(BOUNDS['jerk_comfort'], 'comfort'), (BOUNDS['jerk_suspect'], 'suspect')]),
        ('Implied lateral acceleration, m/s²', d['lateral'], [(BOUNDS['lateral_comfort'], 'comfort'), (BOUNDS['lateral_high'], 'high'), (BOUNDS['lateral_tyre'], 'tyre limit')]),
        ('Heading change per sample, degrees', d['heading'], [(HEADING_STEP, 'screen')]),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.2), dpi=150)
    for ax, (title, values, marks) in zip(axes.flat, panels):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        ax.set_title(title, fontsize=10, color=ink, loc='left')
        ax.set_yscale('log')
        ax.grid(axis='y', color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right', 'left'):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=ink, labelsize=8, length=0)
        ax.set_ylabel('samples', fontsize=8, color=ink)
        if values.size == 0:
            ax.text(0.5, 0.5, 'no samples', transform=ax.transAxes, ha='center', color=ink, fontsize=9)
            continue
        ax.hist(values, bins=70, color=bar, rwidth=0.9)
        top = ax.get_ylim()[1]
        for x, name in marks:
            ax.axvline(x, color=ink, lw=0.8, ls=(0, (3, 3)))
            ax.text(x, top * 0.7, ' ' + name, fontsize=7.5, color=ink, ha='left', va='top')
    fig.suptitle(f"{summary['vehicles']} vehicles, {summary['samples']} samples at {summary['interval']:g} s", fontsize=11, color=ink, x=0.01, ha='left')
    fig.tight_layout()
    fig.savefig(out / 'distributions.png')
    plt.close(fig)


def analyse(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    events, window = None, {}
    if a.trace:
        trace = cars_trace.Trace(a.trace)
        df = trace.table(a.begin, a.end)
        events = trace.events(a.begin, a.end)
        kept = trace.selected(a.begin, a.end)
        if kept:
            window = dict(teleports=kept[-1]['teleports'] - kept[0]['teleports'], collisions=kept[-1]['collisions'] - kept[0]['collisions'])
        if not df.empty:
            # A vehicle taken off the road keeps its last place in the trace. It did not drive there.
            df = df[(df['flags'] & (cars_trace.TELEPORT | cars_trace.COLLISION)) == 0].reset_index(drop=True)
    else:
        df = pd.read_csv(a.fcd, dtype={'trip': str, 'lane': str, 'prev_lane': str, 'time': float}, keep_default_na=False)
    if df.empty:
        raise SystemExit('no rows in FCD')
    for c in ('pos', 'speed', 'acc', 'length', 'width'):
        df[c] = pd.to_numeric(df[c])
    lanes = Lanes(a.net, set(df['lane']) | set(df['prev_lane']))
    known = df['lane'].isin(lanes.shape)
    dropped = int((~known).sum())
    df = df[known].reset_index(drop=True)
    placed = df.groupby('lane', sort=False)[['pos']].apply(lanes.place)
    df = df.join(placed.reset_index(level=0, drop=True))
    df['body'] = body_heading(df, lanes)
    df['lateral'] = df['speed'] ** 2 * df['kappa']
    df['limit'] = df['lane'].map(lanes.limit)
    df['edge'] = df['lane'].map(lanes.edge)
    df = df.sort_values(['trip', 'time'], kind='stable').reset_index(drop=True)
    times = np.sort(df['time'].unique())
    interval = float(np.median(np.diff(times))) if len(times) > 1 else 0.0
    prev = df.groupby('trip', sort=False).shift(1)
    dt = df['time'] - prev['time']
    gap = dt > interval * 1.5
    has_prev = prev['time'].notna()
    reinsert = has_prev & (df['depart_step'] != prev['depart_step'])
    steady = has_prev & ~gap & ~reinsert
    # The engine moves by pos += v_new * dt, so that is the expected step on a lane.
    d_xy = np.hypot(df['x'] - prev['x'], df['y'] - prev['y'])
    expected = df['speed'] * dt
    same_lane = df['lane'] == prev['lane']
    same_edge = df['edge'] == prev['edge']
    lane_change = steady & same_edge & ~same_lane
    connector = steady & ~same_edge
    d_pos = df['pos'] - prev['pos']
    residual = d_pos - expected
    backward = steady & same_lane & (d_pos < -0.01)
    longitudinal = steady & same_lane & (residual.abs() > 0.1)
    known_pairs = {}
    def linked_pair(a, b):
        if (a, b) not in known_pairs:
            known_pairs[(a, b)] = lanes.reachable(a, b)
        return known_pairs[(a, b)]
    linked = pd.Series(False, index=df.index)
    crossing = connector[connector].index
    linked.loc[crossing] = [linked_pair(a, b) for a, b in zip(prev.loc[crossing, 'lane'], df.loc[crossing, 'lane'])]
    direct = pd.Series(False, index=df.index)
    direct.loc[crossing] = [b in lanes.next.get(a, ()) for a, b in zip(prev.loc[crossing, 'lane'], df.loc[crossing, 'lane'])]
    connect_jump = connector & direct & (d_xy > expected + 1.0)
    both_at_once = connector & ~linked
    standing_change = lane_change & (df['speed'] < 0.5)
    lateral_step = np.sqrt(np.maximum(d_xy ** 2 - expected ** 2, 0))
    a_speed = (df['speed'] - prev['speed']) / dt
    acc_mismatch = steady & ((a_speed - df['acc']).abs() > 0.05)
    prev_acc = df.groupby('trip', sort=False)['acc'].shift(1)
    jerk = (df['acc'] - prev_acc) / dt
    jerk = jerk.where(steady)
    head = np.degrees(np.abs(wrap((df['heading'] - prev['heading']).to_numpy())))
    head = pd.Series(head, index=df.index).where(steady & ~lane_change & ~both_at_once)
    body_step = np.degrees(np.abs(wrap((df['body'] - prev['body']).to_numpy())))
    body_step = pd.Series(body_step, index=df.index).where(steady & ~lane_change & ~both_at_once)
    heading_jump = head > HEADING_STEP
    over_speed = df['speed'] > df['limit'] * 1.3
    administrative = steady & (df['acc'] < TELEPORT_ACCEL)
    # Connectors as driven, geometry only.
    seam = connector & direct
    pairs = df.loc[seam, ['lane']].assign(prev=prev.loc[seam, 'lane'])
    driven = pairs.groupby(['prev', 'lane']).size().reset_index(name='crossings')
    kinks = []
    for r in driven.itertuples():
        kink, gap_m = lanes.connector(r.prev, r.lane)
        kinks.append((r.prev, r.lane, r.crossings, kink, gap_m))
    kinks = pd.DataFrame(kinks, columns=['from', 'to', 'crossings', 'kink_deg', 'gap_m'])
    bad_kinks = kinks[(kinks['kink_deg'] > CONNECTOR_KINK) | (kinks['gap_m'] > CONNECTOR_GAP)].sort_values('kink_deg', ascending=False)
    # Where turns ask too much.
    turn = df.groupby('lane').agg(samples=('lateral', 'size'), peak=('lateral', 'max'), over4=('lateral', lambda s: int((s > 4).sum())), over8=('lateral', lambda s: int((s > 8).sum())),
                                  fastest=('speed', 'max'), kappa=('kappa', 'max'), limit=('limit', 'first')).reset_index()
    turn['radius_m'] = 1 / turn['kappa'].clip(lower=1e-4)
    turn['mean_radius_m'] = turn['lane'].map(lanes.mean_radius)
    turn['mean_lateral'] = turn['fastest'] ** 2 / turn['mean_radius_m']
    turn['internal'] = turn['lane'].isin(lanes.internal)
    hot = turn[turn['over4'] > 0].sort_values(['over8', 'peak'], ascending=False)
    hot_table = hot.assign(speed_kmh=hot['fastest'] * 3.6)[['lane', 'internal', 'samples', 'over4', 'over8', 'peak', 'speed_kmh', 'radius_m', 'mean_radius_m', 'mean_lateral']]
    gaps = same_lane_gaps(df, lanes)
    overlaps, truncated = junction_overlaps(df, lanes, a.pair_limit)
    # Per vehicle.
    df = df.assign(jerk=jerk, lc=lane_change, cjump=connect_jump, back=backward, hjump=heading_jump, km=(df['speed'] * interval / 1000), fast=over_speed, lat4=df['lateral'] > 4, lat8=df['lateral'] > 8)
    per = df.groupby('trip').agg(samples=('time', 'size'), km=('km', 'sum'), acc_min=('acc', 'min'), acc_max=('acc', 'max'), jerk_abs_max=('jerk', lambda s: s.abs().max()),
                                 lateral_max=('lateral', 'max'), lane_changes=('lc', 'sum'), connector_jumps=('cjump', 'sum'), backward=('back', 'sum'), heading_jumps=('hjump', 'sum'),
                                 over_speed=('fast', 'sum'), lateral_over_4=('lat4', 'sum'), lateral_over_8=('lat8', 'sum')).reset_index()
    per.to_csv(out / 'vehicles.csv', index=False, float_format='%.3f')
    log = {}
    if a.log:
        m = re.search(r'lane changes (\d+), teleports (\d+), collisions (\d+) \(lane change (\d+), junction (\d+), lane start (\d+), other (\d+)\)', Path(a.log).read_text(errors='replace'))
        if m:
            log = dict(zip(('lane_changes', 'teleports', 'collisions', 'collision_lane_change', 'collision_junction', 'collision_lane_start', 'collision_other'), map(int, m.groups())))
    acc = df['acc'].to_numpy()
    jerk_abs = jerk.abs().to_numpy()
    summary = dict(
        interval=interval, vehicles=int(df['trip'].nunique()), samples=int(len(df)), vehicle_km=float(df['km'].sum()), time=[float(times[0]), float(times[-1])],
        rows_on_unknown_lanes=dropped,
        gaps_in_trajectory=int(gap.sum()), reinsertions=int(reinsert.sum()),
        lane_changes=int(lane_change.sum()), lane_changes_at_a_stand=int(standing_change.sum()), connectors_crossed=int(connector.sum()),
        lane_change_step_m=percentiles(lateral_step[lane_change]),
        lane_change_lateral_speed=percentiles((lateral_step / dt)[lane_change]),
        backward_steps=int(backward.sum()), longitudinal_mismatch=int(longitudinal.sum()), longitudinal_residual=percentiles(residual[steady & same_lane]),
        connector_jumps=int(connect_jump.sum()), crossing_and_lane_change_in_one_step=int(both_at_once.sum()), body_heading_step=percentiles(body_step), acc_field_mismatch=int(acc_mismatch.sum()),
        heading_jumps=int(heading_jump.sum()), body_heading_jumps=int((body_step > HEADING_STEP).sum()), driven_connectors=int(len(kinks)), kinked_connectors=int(len(bad_kinks)),
        crossings_over_kinks=int(bad_kinks['crossings'].sum()) if len(bad_kinks) else 0,
        over_speed_30pct=int(over_speed.sum()),
        acceleration=percentiles(acc), jerk_abs=percentiles(jerk_abs), lateral=percentiles(df['lateral']),
        accel_over_comfort=int((acc > BOUNDS['accel_comfort']).sum()), brake_over_comfort=int((acc < BOUNDS['brake_comfort']).sum()),
        brake_over_type=int((acc < BOUNDS['brake_type']).sum()), brake_over_dry_limit=int((acc < BOUNDS['brake_dry_limit']).sum()),
        administrative_stops=int(administrative.sum()),
        jerk_over_comfort=int((jerk_abs > BOUNDS['jerk_comfort']).sum()), jerk_over_suspect=int((jerk_abs > BOUNDS['jerk_suspect']).sum()),
        lateral_samples_over_comfort=int((df['lateral'] > BOUNDS['lateral_comfort']).sum()),
        lateral_samples_over_4=int((df['lateral'] > 4).sum()), lateral_samples_over_8=int((df['lateral'] > 8).sum()),
        lanes_over_4=int((turn['over4'] > 0).sum()), lanes_over_8=int((turn['over8'] > 0).sum()),
        lanes_whole_curve_over_4=int((turn['mean_lateral'] > 4).sum()), lanes_whole_curve_over_8=int((turn['mean_lateral'] > 8).sum()),
        negative_gap_incidents=int(len(gaps)), negative_gap_worst=float(gaps['worst'].min()) if len(gaps) else 0.0,
        junction_overlap_incidents=int(len(overlaps)), junction_crossing_incidents=int((overlaps['kind'] == 'crossing').sum()) if len(overlaps) else 0,
        junction_overlap_worst=float(overlaps['worst'].max()) if len(overlaps) else 0.0,
        junction_pairs_truncated=bool(truncated), engine_counters=log,
    )
    if events is not None:
        if len(events):
            where = events.assign(x=0.0, y=0.0)
            where[['x', 'y']] = cars_trace.lane_points(a.net, list(events['lane']), list(events['pos']))
            events = where
        events.to_csv(out / 'events.csv', index=False, float_format='%.2f')
        summary.update(teleports_in_trace=int((events['kind'] == 'teleport').sum()), collisions_in_trace=int((events['kind'] == 'collision').sum()), counters_in_window=window)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    gaps.to_csv(out / 'negative_gaps.csv', index=False, float_format='%.3f')
    overlaps.to_csv(out / 'junction_overlaps.csv', index=False, float_format='%.3f')
    hot_table.to_csv(out / 'lanes_over_lateral.csv', index=False, float_format='%.3f')
    bad_kinks.to_csv(out / 'connector_kinks.csv', index=False, float_format='%.3f')
    jumps = df.loc[connect_jump, ['time', 'trip', 'lane', 'pos', 'speed']].assign(prev_lane=prev.loc[connect_jump, 'lane'], metres=d_xy[connect_jump], expected=expected[connect_jump])
    jumps.to_csv(out / 'connector_jumps.csv', index=False, float_format='%.3f')
    figure(out, dict(acc=acc, jerk=jerk_abs, lateral=df['lateral'].to_numpy(), heading=head.to_numpy()), summary)
    s = summary
    share = lambda n: f'{n} ({100 * n / max(s["samples"], 1):.3f}% of samples)'
    pct = lambda d: ', '.join(f'{k} {v:.2f}' for k, v in d.items() if k != 'n') if d else 'no data'
    lines = ['# Physics QA', '', f'Net `{a.net}`, ' + (f'trace `{a.trace}`.' if a.trace else f'FCD `{a.fcd}`.'), '',
             f'{s["vehicles"]} vehicles, {s["samples"]} samples every {interval:g} s, {s["vehicle_km"]:.0f} vehicle km, simulation time {s["time"][0]:g} to {s["time"][1]:g}.', '']
    if log:
        lines += [f'Engine counters for the whole run: {log["lane_changes"]} lane changes, {log["teleports"]} teleports, {log["collisions"]} collisions '
                  f'({log["collision_lane_change"]} lane change, {log["collision_junction"]} junction, {log["collision_lane_start"]} lane start, {log["collision_other"]} other).', '']
    if events is not None:
        lines += ['## Teleports and collisions', '',
                  f'In scope of the trace: {s["teleports_in_trace"]} teleports and {s["collisions_in_trace"]} collisions, where the vehicle was just before (`events.csv`). Engine counters over the frames, whole net: {window.get("teleports", 0)} and {window.get("collisions", 0)}. `cars replay --at <time> --center x,y` shows each one in this very run.', '']
        lines += table(events.head(a.top))
    lines += ['## Position', '',
              f'- Missing stretches in a trajectory, teleports or leaving the sampled box: {s["gaps_in_trajectory"]}. Reinsertions: {s["reinsertions"]}. These are excluded below.',
              f'- Backward steps on a lane: {s["backward_steps"]}.',
              f'- Lane position disagreeing with speed by over 0.1 m in a step: {s["longitudinal_mismatch"]} (residual {pct(s["longitudinal_residual"])}).',
              f'- Jumps over 1 m beyond the distance driven, crossing directly between two lanes that connect: {s["connector_jumps"]} of {s["connectors_crossed"]} crossings (`connector_jumps.csv`).',
              f'- Arriving on a lane no connection leads to, so crossing and changing lane within one sample: {s["crossing_and_lane_change_in_one_step"]}.',
              f'- Reported acc differs from the speed change by over 0.05 m/s²: {s["acc_field_mismatch"]}.', '',
              '## Acceleration and jerk', '',
              f'- Acceleration, m/s²: {pct(s["acceleration"])}.',
              f'- Over comfort: accelerating above +{BOUNDS["accel_comfort"]:g}: {share(s["accel_over_comfort"])}; braking below {BOUNDS["brake_comfort"]:g}: {share(s["brake_over_comfort"])}.',
              f'- Braking harder than the default type decel of {BOUNDS["brake_type"]:g}: {share(s["brake_over_type"])}. Harder than measured dry tyres, {BOUNDS["brake_dry_limit"]:g}: {share(s["brake_over_dry_limit"])}.',
              f'- Stops no vehicle could make, below {TELEPORT_ACCEL:g} m/s²: {s["administrative_stops"]}.',
              f'- Jerk magnitude, m/s³: {pct(s["jerk_abs"])}. Above comfort {BOUNDS["jerk_comfort"]:g}: {share(s["jerk_over_comfort"])}. Above {BOUNDS["jerk_suspect"]:g}: {share(s["jerk_over_suspect"])}. At a sample interval of {interval:g} s, jerk is a difference of step accelerations.', '',
              '![Distributions](distributions.png)', '',
              '## Turns', '',
              f'Implied lateral acceleration is v² times the heading change per metre over a {CURVE_WINDOW:g} m window of lane geometry, a local peak. mean_lateral is the fastest speed squared over the radius of the whole lane, what a smooth curve would demand. The engine limits neither; netconvert caps turn speeds at about 5.5 m/s² on its own average radius.', '',
              f'- m/s²: {pct(s["lateral"])}.',
              f'- Samples over comfort {BOUNDS["lateral_comfort"]:g}: {share(s["lateral_samples_over_comfort"])}; over 4: {share(s["lateral_samples_over_4"])}; over 8: {share(s["lateral_samples_over_8"])}.',
              f'- Lanes with any sample over 4: {s["lanes_over_4"]}; over 8: {s["lanes_over_8"]}. Taking the whole lane as one smooth curve: {s["lanes_whole_curve_over_4"]} and {s["lanes_whole_curve_over_8"]}. Worst first, all in `lanes_over_lateral.csv`:', '']
    lines += table(hot_table.head(a.top))
    lines += ['## Connectors', '',
              f'{s["driven_connectors"]} lane-to-lane connections were driven. {s["kinked_connectors"]} have a heading kink over {CONNECTOR_KINK:g} degrees or a gap over {CONNECTOR_GAP:g} m between the two polylines, and took {s["crossings_over_kinks"]} crossings. Samples where the lane tangent turns more than {HEADING_STEP:g} degrees in one step: {s["heading_jumps"]}. The body, as a chord from rear to front bumper, does so in {s["body_heading_jumps"]}; per step, degrees: {pct(s["body_heading_step"])}. All in `connector_kinks.csv`:', '']
    lines += table(bad_kinks.head(a.top))
    lines += ['## Lane changes', '',
              f'{s["lane_changes"]} lane changes in the samples, every one instantaneous: the vehicle is on the old lane in one sample and the new lane in the next. {s["lane_changes_at_a_stand"]} happen below 0.5 m/s, a pure sideways slide. Sideways step, m: {pct(s["lane_change_step_m"])}. Implied lateral speed, m/s: {pct(s["lane_change_lateral_speed"])}. Research note 11 gives about 1.26 m/s² peak for a 3.5 m change over 4 s; the engine has no such duration.', '',
              '## Overlaps', '',
              f'Negative bumper gaps on one lane, counting tails hanging back from the next lane: {s["negative_gap_incidents"]} pairs, worst {s["negative_gap_worst"]:.2f} m. Below -0.05 m only (`negative_gaps.csv`):', '']
    lines += table(gaps.head(a.top))
    lines += [f'Bodies overlapping on different internal lanes of a junction, as rectangles along the chord from rear to front bumper: {s["junction_overlap_incidents"]} pairs, {s["junction_crossing_incidents"]} on crossing paths, the rest diverging from or merging to the same lane; worst {s["junction_overlap_worst"]:.2f} m (`junction_overlaps.csv`):', '']
    if truncated:
        lines += ['The pair check stopped at its limit; raise `--pair-limit` for the rest.', '']
    lines += table(overlaps.head(a.top))
    lines += ['## What this cannot tell', '',
              '- Samples, not events: a pair counted here may overlap for many samples, and a short window says nothing about a whole run.',
              '- Width comes from the vehicle type, not the engine. A rectangle on a chord is not a swept path: on a tight turn the real corners differ by some decimetres.',
              '- Polylines are coarse and are not the engine\'s own idea of a curve; the curvature window smooths kinks but cannot recover a true radius. Treat a single lane\'s peak as a pointer to go and look.',
              '- A teleported vehicle is off the road, so it shows as a gap in its trajectory. In an FCD only the engine counters above count them; a trace also says who and where.', '']
    (out / 'report.md').write_text('\n'.join(lines))
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, (dict, list))}))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--net', required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--fcd')
    source.add_argument('--trace', help='file from cars run --trace')
    p.add_argument('--begin', type=float, help='with --trace, the first time to look at')
    p.add_argument('--end', type=float, help='with --trace, the last time to look at')
    p.add_argument('--out', required=True)
    p.add_argument('--log', help='stderr of cars run, for its counters')
    p.add_argument('--top', type=int, default=20, help='rows in each table of the report')
    p.add_argument('--pair-limit', type=int, default=3_000_000)
    analyse(p.parse_args())


if __name__ == '__main__':
    main()
