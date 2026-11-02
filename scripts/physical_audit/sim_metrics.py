#!/usr/bin/env python3
"""Measure each simulated run the way the real tracks are measured: from speed and position, not from any config.

    python3 sim_metrics.py --root LAB [--only scene_driver_dt]

Reads LAB/out/<scene>_<driver>_dt<dt>/fcd.csv (or f.trace) and writes metrics.json and samples.npy beside it.
Speed goes through the same Savitzky-Golay window as the real tracks when dt is under 0.5 s;
at dt 0.5 and 1 a step already holds one acceleration, so the raw step value is what a car does there.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def pct(x, q=(5, 50, 95)):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    out = {f'p{p}': round(float(np.percentile(x, p)), 3) for p in q}
    out['n'] = int(len(x))
    return out


def load(path):
    head = pd.read_csv(path, nrows=0).columns
    use = [c for c in ['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'length', 'width', 'flags', 'vtype', 'offset'] if c in head]
    df = pd.read_csv(path, usecols=use, dtype={'trip': str, 'lane': str})
    return df


def tracks(df, dt):
    """Per vehicle arrays. s is distance along the path, rebuilt across lanes."""
    out = {}
    for trip, g in df.groupby('trip', sort=False):
        g = g.sort_values('time')
        t = g.time.values
        v = g.speed.values.astype(float)
        if len(t) < 5:
            continue
        pos = g.pos.values.astype(float)
        lane = g.lane.values
        ds = np.diff(pos)
        same = lane[1:] == lane[:-1]
        ds = np.where(same & (ds >= -1e-3), ds, v[1:] * np.diff(t))
        s = np.concatenate(([0], np.cumsum(ds)))
        out[trip] = dict(t=t, v=v, s=s, pos=pos, lane=lane, g=g)
    return out


def accel(tr, dt):
    v = tr['v']
    if dt < 0.5 and len(v) > int(1.0 / dt) + 2:
        w = int(round(1.0 / dt)) | 1
        vs = savgol_filter(v, w, 3)
        a = savgol_filter(v, w, 3, deriv=1, delta=dt)
        j = np.gradient(savgol_filter(a, w, 2), dt)
        raw = np.gradient(v, dt)
        return vs, a, j, raw
    a = np.concatenate((np.diff(v) / dt, [0]))
    j = np.concatenate((np.diff(a) / dt, [0]))
    return v, a, j, a


def stops_launches(tr, a, vs, dt):
    t, s = tr['t'], tr['s']
    stand = vs < 0.25
    st, la = [], []
    for i in range(1, len(vs)):
        if stand[i] and not stand[i - 1]:
            j = i - 1
            while j > 0 and a[j] < -0.1:
                j -= 1
            if vs[j] >= 3 and (i - j) * dt >= 0.2:
                dist = s[i] - s[j]
                st.append(dict(t=float(t[i]), v0=float(vs[j]), dur=float((i - j) * dt), dist=float(dist), mean=float(vs[j] / ((i - j) * dt)),
                               peak=float(a[j:i + 1].min()), lane=str(tr['lane'][i]), pos=float(tr['pos'][i])))
        if stand[i - 1] and not stand[i]:
            k = i
            lim = int(25 / dt)
            while k < len(vs) and vs[k] < 10.5 and k - i < lim:
                k += 1
            k = min(k, len(vs) - 1)
            if vs[k] >= 3:
                seg = vs[i:k + 1]
                r = dict(t=float(t[i]), peak=float(a[i:k + 1].max()), top=float(seg.max()))
                for target in (3, 5, 8, 10):
                    hit = int(np.argmax(seg >= target)) if (seg >= target).any() else -1
                    r[f't{target}'] = float(hit * dt) if hit >= 0 else None
                    r[f'd{target}'] = float(s[i + hit] - s[i]) if hit >= 0 else None
                la.append(r)
    return st, la


def summarize(st, la):
    d = {}
    if st:
        f = pd.DataFrame(st)
        f['bin'] = pd.cut(f.v0, [3, 6, 9, 12, 15, 20, 30, 45])
        d['stops'] = dict(n=len(f), mean=pct(f['mean']), peak=pct(f.peak, (1, 5, 50, 95)), by_v0={str(k): dict(n=len(g), mean=round(float(g['mean'].median()), 2), peak=round(float(g.peak.median()), 2), peak_p5=round(float(g.peak.quantile(.05)), 2), dist=round(float(g.dist.median()), 1)) for k, g in f.groupby('bin', observed=True)})
    if la:
        f = pd.DataFrame(la)
        d['launches'] = dict(n=len(f), peak=pct(f.peak), t5=pct(f.t5.dropna()), d5=pct(f.d5.dropna()), t10=pct(f.t10.dropna()), d10=pct(f.d10.dropna()))
    return d


def acc_table(vs, a, j, raw):
    d = dict(acc_max=round(float(a.max()), 2), acc_min=round(float(a.min()), 2), raw_max=round(float(raw.max()), 2), raw_min=round(float(raw.min()), 2))
    table = {}
    for lo, hi in [(0.5, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 45)]:
        q = (vs >= lo) & (vs < hi)
        if q.sum() < 20:
            continue
        pos, neg = a[q & (a > 0.1)], -a[q & (a < -0.1)]
        table[f'{lo}-{hi}'] = dict(n=int(q.sum()), acc=pct(pos, (50, 95, 99)) if len(pos) > 5 else None, dec=pct(neg, (50, 95, 99)) if len(neg) > 5 else None, jerk_p95=round(float(np.percentile(np.abs(j[q]), 95)), 2))
    d['by_speed'] = table
    moving = vs > 0.5
    d['jerk'] = pct(np.abs(j[moving]), (50, 95, 99))
    d['jerk_max'] = round(float(np.abs(j).max()), 2)
    n = moving.sum()
    d['share_dec_gt'] = {str(x): round(float((a[moving] < -x).sum() / max(n, 1)), 6) for x in (2, 3, 4.5, 6, 8.9)}
    d['share_acc_gt'] = {str(x): round(float((a[moving] > x).sum() / max(n, 1)), 6) for x in (1.5, 2, 2.6, 3.5)}
    return d


def time_gaps(df, dt):
    rows = []
    f = df[df.speed > 1]
    # Sample every 2 s to avoid counting one pair many times.
    tt = np.unique(df.time.values)
    tt = tt[:: max(int(round(2 / dt)), 1)]
    sub = df[df.time.isin(tt)]
    for (_, _), g in sub.groupby(['time', 'lane'], sort=False):
        if len(g) < 2:
            continue
        g = g.sort_values('pos')
        pos, v, length = g.pos.values, g.speed.values, g.length.values if 'length' in g else np.full(len(g), 5.0)
        gap = pos[1:] - length[1:] - pos[:-1]
        rows.append(np.c_[v[:-1], gap, v[1:]])
    if not rows:
        return {}, None
    r = np.concatenate(rows)
    out = {}
    following = (r[:, 1] < 100) & (r[:, 1] > -5)
    for lo, hi in [(1, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 40)]:
        q = following & (r[:, 0] >= lo) & (r[:, 0] < hi)
        if q.sum() > 20:
            out[f'{lo}-{hi}'] = pct(r[q, 1] / r[q, 0], (5, 25, 50, 95))
    stand = following & (r[:, 0] < 0.1) & (r[:, 2] < 0.1)
    return out, r[following]


def standing_gaps(df, dt):
    tt = np.unique(df.time.values)[:: max(int(round(5 / dt)), 1)]
    sub = df[df.time.isin(tt) & (df.speed < 0.05)]
    gaps = []
    for _, g in sub.groupby(['time', 'lane'], sort=False):
        if len(g) < 2:
            continue
        g = g.sort_values('pos')
        gaps.extend((g.pos.values[1:] - g.length.values[1:] - g.pos.values[:-1]).tolist())
    gaps = np.array(gaps)
    return pct(gaps[(gaps < 15)], (5, 50, 95)) if len(gaps) else None


def scene_signal(df, trs, dt, info):
    """Crossing times, discharge, launch delay, yellow decisions at the fixed signal."""
    cycle = sum(info['phase'].values())
    green_len = info['phase']['green']
    y = info['phase']['yellow']
    in_len = None
    rows = []
    for trip, tr in trs.items():
        lane = tr['lane']
        on = np.flatnonzero(lane == 'in_0')
        if len(on) == 0 or on[-1] + 1 >= len(lane):
            continue
        last = on[-1]
        in_len = max(in_len or 0, tr['pos'][last])
        rows.append(dict(trip=trip, cross=float(tr['t'][last + 1]), last=last))
    cross = pd.DataFrame(rows).sort_values('cross') if rows else pd.DataFrame(columns=['cross'])
    head = {}
    firsts, lags, positions, first_launch = [], [], {}, []
    if len(cross) == 0:
        return {}
    in_len = in_len or 1200.0
    lane_len = max((tr['pos'][tr['lane'] == 'in_0'].max() for tr in trs.values() if (tr['lane'] == 'in_0').any()), default=1200.0)
    for c in range(40):
        g0 = c * cycle
        # Who stood in the queue when this green began.
        queue = []
        for trip, tr in trs.items():
            k = np.searchsorted(tr['t'], g0)
            if k >= len(tr['t']) or abs(tr['t'][k] - g0) > dt or tr['lane'][k] != 'in_0' or tr['v'][k] > 0.3:
                continue
            start = k + np.argmax(tr['v'][k:] > 1.5) if (tr['v'][k:] > 1.5).any() else None
            out = np.flatnonzero((tr['lane'][k:] != 'in_0'))
            after = tr['v'][k:k + int(25 / dt)]
            hit = {x: (float(np.argmax(after >= x) * dt) if (after >= x).any() else None) for x in (5, 10)}
            queue.append(dict(pos=tr['pos'][k], start=float(tr['t'][start]) if start is not None else None, cross=float(tr['t'][k + out[0]]) if len(out) else None, t5=hit[5], t10=hit[10], peak=float(np.diff(after).max() / dt) if len(after) > 2 else None))
        queue.sort(key=lambda r: -r['pos'])
        if not queue or queue[0]['pos'] < lane_len - 12:
            continue
        prev_cross, prev_start = g0, None
        for i, r in enumerate(queue):
            if r['cross'] is None or r['cross'] > g0 + green_len + y:
                break
            positions.setdefault(i + 1, []).append(r['cross'] - prev_cross)
            prev_cross = r['cross']
            if i == 0 and r['start'] is not None:
                firsts.append(r['start'] - g0)
                first_launch.append((r['t5'], r['t10'], r['peak']))
            elif r['start'] is not None and prev_start is not None:
                lags.append(r['start'] - prev_start)
            prev_start = r['start']
    head = {str(k): dict(n=len(v), median=round(float(np.median(v)), 2)) for k, v in sorted(positions.items())}
    sat = [x for k, v in positions.items() if k >= 5 for x in v]
    base = float(np.median(sat)) if sat else None
    lost = float(sum(np.median(positions[k]) - base for k in range(1, 5) if k in positions)) if sat else None
    # Yellow: every car above 2 m/s when yellow begins.
    decisions = []
    for c in range(40):
        ty = c * cycle + green_len
        for trip, tr in trs.items():
            k = np.searchsorted(tr['t'], ty)
            if k >= len(tr['t']) or abs(tr['t'][k] - ty) > dt or tr['lane'][k] != 'in_0' or tr['v'][k] < 2:
                continue
            dist = lane_len - tr['pos'][k]
            if dist > 150:
                continue
            ttl = dist / tr['v'][k]
            out = np.flatnonzero(tr['lane'][k:] != 'in_0')
            went = len(out) and tr['t'][k + out[0]] < ty + y + info['phase']['red'] - 2
            after = tr['v'][k:k + int(25 / dt)]
            ac = np.gradient(tr['v'][k:k + int(25 / dt)], dt) if len(after) > 3 else np.array([0.0])
            decisions.append(dict(ttl=float(ttl), v=float(tr['v'][k]), dist=float(dist), stopped=not went, need=float(tr['v'][k] ** 2 / max(2 * dist, .1)), peak=float(ac.min()), red_cross=float(tr['t'][k + out[0]] - (ty + y)) if len(out) and went else None))
    yellow = {}
    if decisions:
        d = pd.DataFrame(decisions)
        d['b'] = pd.cut(d.ttl, [0, 1, 2, 3, 4, 5, 6, 8, 12])
        yellow = dict(n=len(d), stop_by_ttl={str(k): dict(n=len(g), stop=round(float(g.stopped.mean()), 3)) for k, g in d.groupby('b', observed=True)},
                      stop_need=pct(d[d.stopped].need, (50, 95)), stop_peak=pct(-d[d.stopped].peak, (50, 95)),
                      ran_red=pct(d[~d.stopped].red_cross.dropna().clip(lower=-5), (50, 95)))
    return dict(headway=head, sat_headway=round(base, 3) if base else None, lost_time=round(lost, 2) if lost is not None else None,
                first_start=pct(firsts), start_lag=pct(lags), yellow=yellow,
                first_t5=pct([x[0] for x in first_launch if x[0] is not None]), first_t10=pct([x[1] for x in first_launch if x[1] is not None]), first_peak=pct([x[2] for x in first_launch if x[2] is not None]))


def scene_free(df, info):
    out = {}
    for i, l in enumerate(info['limits']):
        q = df[(df.lane == f'e{i}_0') & (df.pos > 700) & (df.pos < 1300)]
        if len(q):
            per = q.groupby('trip').speed.median()
            out[str(l)] = dict(limit_ms=round(l / 3.6, 3), median=round(float(per.median()), 3), p5=round(float(per.quantile(.05)), 3), p95=round(float(per.quantile(.95)), 3), ratio=round(float(per.median() / (l / 3.6)), 3), n=len(per))
    return out


def scene_curves(df, info):
    rows = []
    for edge, b in info['bends'].items():
        q = df[(df.lane == edge + '_0')]
        if q.empty:
            continue
        # Middle half of the arc: netconvert's lane length can differ from the drawn one, so scale by the longest position.
        length = q.pos.max()
        L = 2 * 400 + b['R'] * math.pi / 2
        scale = length / L
        s0, s1 = (b['s0'] + 0.25 * (b['s1'] - b['s0'])) * scale, (b['s0'] + 0.75 * (b['s1'] - b['s0'])) * scale
        core = q[(q.pos >= s0) & (q.pos <= s1)]
        if core.empty:
            continue
        v = core.groupby('trip').speed.min()
        vm = core.groupby('trip').speed.mean()
        rows.append(dict(limit=b['limit'], R=b['R'], n=len(v), v_min=round(float(v.median()), 2), v_mean=round(float(vm.median()), 2), ay=round(float(vm.median() ** 2 / b['R']), 2), ay_max=round(float((v.max() ** 2) / b['R']), 2), limit_ay=round((b['limit'] / 3.6) ** 2 / b['R'], 2)))
    return rows


def scene_wall(df, trs, a_of, dt, info=None):
    rows = []
    went = {}
    limits = {0: 30, 1: 50, 2: 70, 3: 100}
    for trip, tr in trs.items():
        lane = tr['lane'][0]
        if not lane.startswith('in'):
            continue
        i = int(lane[2])
        vs, a, _, _ = a_of[trip]
        lim = limits[i] / 3.6
        out = np.flatnonzero(tr['lane'] != lane)
        if len(out):
            # Crossed on red? Cycle in the add file: green then red.
            cycle, green = (40.0, 23.0) if info and info.get('wall2') else (20.0, 11.0)
            went.setdefault(limits[i], []).append((tr['t'][out[0]] % cycle) >= green)
        st, _ = stops_launches(tr, a, vs, dt)
        for r in st:
            if r['v0'] < 0.85 * lim:
                continue
            rows.append(dict(limit=limits[i], v0=r['v0'], dist=r['dist'], peak=r['peak'], mean=r['mean'], implied=r['v0'] ** 2 / max(2 * r['dist'], 0.1)))
    if not rows:
        return {}
    f = pd.DataFrame(rows)
    out = {}
    for l, g in f.groupby('limit'):
        if l in went:
            pass
        g = g.sort_values('dist')
        out[str(l)] = dict(n=len(g), dist_min=round(float(g.dist.min()), 1), dist_p5=round(float(g.dist.quantile(.05)), 1), dist_p50=round(float(g.dist.median()), 1), peak_hardest=round(float(g.peak.min()), 2), peak_p50=round(float(g.peak.median()), 2),
                           implied_max=round(float(g.implied.max()), 2), implied_p50=round(float(g.implied.median()), 2),
                           crossed=len(went.get(l, [])), crossed_on_red=round(float(np.mean(went[l])), 3) if l in went and went[l] else None)
    return out


def scene_mix(df, trs, a_of, dt):
    out = {}
    for prefix in ('car', 'van', 'truck', 'artic', 'bus'):
        st_all, la_all = [], []
        length = None
        for trip, tr in trs.items():
            if not trip.startswith(prefix + '.'):
                continue
            vs, a, _, _ = a_of[trip]
            s, l = stops_launches(tr, a, vs, dt)
            st_all += s
            la_all += l
            length = float(tr['g'].length.iloc[0])
        out[prefix] = dict(length=length, **summarize(st_all, la_all))
    return out


def lane_changes(df, dt):
    """Lateral motion from the engine's own offset. Instant when the engine has no offset."""
    if 'offset' not in df.columns:
        return dict(has_offset=False, note='no lateral state in this driver: a change is a jump between lanes')
    q = df[np.abs(df.offset) > 1e-3]
    if q.empty:
        return dict(has_offset=True, n=0)
    durs, speeds = [], []
    for _, g in q.groupby('trip', sort=False):
        g = g.sort_values('time')
        t = g.time.values
        cut = np.flatnonzero(np.diff(t) > 2 * dt + 1e-6)
        for seg in np.split(np.arange(len(t)), cut + 1):
            if len(seg) < 3:
                continue
            o = g.offset.values[seg]
            lat = np.abs(np.diff(o)) / dt
            lat = lat[lat < 10]
            if len(lat) == 0:
                continue
            speeds.append(float(lat.max()))
            durs.append(float(t[seg[-1]] - t[seg[0]] + dt))
    return dict(has_offset=True, n=len(durs), duration=pct(durs), peak_lat_speed=pct(speeds))


def run_dir(o, root):
    name = o.name
    scene, driver, dts = name.rsplit('_', 2)
    dt = float(dts[2:])
    info = json.loads((Path(root) / 'scenes' / scene / 'scene.json').read_text())
    if not (o / 'fcd.csv').exists():
        if (o / 'f.trace').exists():
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import cars_trace_local as ct
            df = ct.Trace(str(o / 'f.trace')).table()
        else:
            return None
    else:
        df = load(o / 'fcd.csv')
    if df.empty:
        return None
    trs = tracks(df, dt)
    a_of = {k: accel(tr, dt) for k, tr in trs.items()}
    # The first 5 s of a trip are left out: a car inserted at full speed behind a slower one brakes hard, which says nothing about drivers.
    skip = max(int(round(5 / dt)), 1)
    stack = [np.c_[a_of[k][0][skip:], a_of[k][1][skip:], a_of[k][2][skip:]] for k in a_of]
    all_ = np.concatenate(stack) if stack else np.zeros((0, 3))
    vs, a, j = all_.T
    raw = np.concatenate([a_of[k][3][skip:] for k in a_of]) if a_of else np.zeros(0)
    m = dict(scene=scene, driver=driver, dt=dt, vehicles=len(trs), samples=int(len(vs)), **acc_table(vs, a, j, raw))
    st, la = [], []
    for k, tr in trs.items():
        s, l = stops_launches(tr, a_of[k][1], a_of[k][0], dt)
        st += s
        la += l
    m.update(summarize(st, la))
    tg, _ = time_gaps(df, dt)
    m['time_gap'] = tg
    m['standing_gap'] = standing_gaps(df, dt)
    m['lc'] = lane_changes(df, dt)
    if scene in ('signal', 'mix'):
        m['signal'] = scene_signal(df, trs, dt, info)
    if scene == 'free':
        m['free'] = scene_free(df, info)
    if scene == 'curves':
        m['curves'] = scene_curves(df, info)
    if scene in ('wall', 'wall2'):
        m['wall'] = scene_wall(df, trs, a_of, dt, info)
    if scene == 'mix':
        m['mix'] = scene_mix(df, trs, a_of, dt)
    if (o / 'report.json').exists():
        try:
            rep = json.loads((o / 'report.json').read_text())
            m['report'] = {k: rep[k] for k in rep if isinstance(rep[k], (int, float)) and ('collision' in k or 'teleport' in k or 'gridlock' in k or 'contact' in k or 'overlap' in k)}
        except Exception:
            pass
    (o / 'metrics.json').write_text(json.dumps(m, indent=1, default=float))
    keep = vs > 0.25
    step = max(int(round(0.5 / dt)), 1)
    np.save(o / 'samples.npy', np.c_[vs[keep][::step], a[keep][::step], j[keep][::step]].astype('f4'))
    if st:
        pd.DataFrame(st).to_csv(o / 'stops.csv', index=False)
    if la:
        pd.DataFrame(la).to_csv(o / 'launches.csv', index=False)
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    p.add_argument('--only')
    a = p.parse_args()
    for o in sorted((Path(a.root) / 'out').iterdir()):
        if a.only and a.only not in o.name:
            continue
        if not (o / 'done.json').exists() or (o / 'metrics.json').exists() and not a.only:
            continue
        try:
            m = run_dir(o, a.root)
            print(o.name, 'ok' if m else 'empty', m['vehicles'] if m else '', flush=True)
        except Exception as e:
            print(o.name, 'FAILED', repr(e), flush=True)


if __name__ == '__main__':
    main()
