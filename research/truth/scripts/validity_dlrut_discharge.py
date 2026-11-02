#!/usr/bin/env python3
"""Measured queue discharge at the DLR AIM Research Intersection, Braunschweig (2023-09-24, a Sunday).

Finds cars stopped in a single-file queue behind a signal, confirms green from the controller
log, and times each front bumper across a line just ahead of the first car. Licence of the
source data is CC BY-NC-SA 4.0. Reads the zip in place, one 15-minute file at a time. CPU only.
usage: validity_dlrut_discharge.py [first_hhmm last_hhmm]
"""
import io, json, re, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

Z = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-dlrut/DLR-Urban-Traffic-dataset_v1-3-1.zip'
OUT = Path(__file__).resolve().parents[1]
FIRST, LAST = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('0600', '1800')
SIGNALS = {}
COLS = ['timestamp', 'id', 'center_easting', 'center_northing', 'velocity_magnitude', 'yaw', 'dimension_length',
        'classifications_car', 'classifications_motorbike', 'classifications_bicycle', 'classifications_pedestrian']


def episodes(g):
    """Stopped intervals of at least 2 s that end with the object moving off."""
    t, v = g.t.values, g.v.values
    out, i, n = [], 0, len(t)
    while i < n:
        if v[i] < .3:
            j = i
            while j + 1 < n and v[j + 1] < .5:
                j += 1
            if t[j] - t[i] >= 2 and j + 1 < n and v[j + 1:].max(initial=0) > 2:
                out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def direction(g, j):
    t, x, y = g.t.values, g.x.values, g.y.values
    k = np.searchsorted(t, t[j] + 4)
    if k >= len(t):
        return None
    d = np.array([x[k] - x[j], y[k] - y[j]])
    n = np.hypot(*d)
    return d / n if n > 1 else None


def analyse(tr, tl):
    tr = tr[(tr.classifications_car > .5) & tr.L.between(3, 6.5)]
    objs = {i: g.sort_values('t') for i, g in tr.groupby('id')}
    stops = []
    for i, g in objs.items():
        for a, b in episodes(g):
            d = direction(g, b)
            if d is not None:
                stops.append(dict(id=i, t0=g.t.values[a], t1=g.t.values[b], x=g.x.values[b], y=g.y.values[b], dx=d[0], dy=d[1], L=g.L.values[b], j=b))
    s = pd.DataFrame(stops)
    if s.empty:
        return [], []
    used, rows, heads = set(), [], []
    s = s.sort_values('t1')
    arr = s.to_dict('records')
    for H in arr:
        if H['id'] in used:
            continue
        # A head has no stationary car in front of it when it releases.
        active = [o for o in arr if o['t0'] <= H['t1'] <= o['t1'] + 1 and o['id'] != H['id']]
        def rel(o, base):
            ex, ey = o['x'] - base['x'], o['y'] - base['y']
            return ex * base['dx'] + ey * base['dy'], -ex * base['dy'] + ey * base['dx']
        if any(0 < rel(o, H)[0] < 25 and abs(rel(o, H)[1]) < 1.5 for o in active):
            continue
        # The head must sit behind a signal that turned green just before it moved.
        best = None
        for sid, pts in SIGNALS.items():
            for p in pts:
                a = (p[0] - H['x']) * H['dx'] + (p[1] - H['y']) * H['dy']
                if -3 < a < 18 and (best is None or a < best[1]):
                    best = (sid, a)
        if best is None:
            continue
        q = tl[(tl.id == best[0]) & (tl.t > H['t1'] - 8) & (tl.t <= H['t1'] + 1)].sort_values('t')
        green = None
        st, tt = q.state.values, q.t.values
        for k in range(1, len(st)):
            if st[k] in (5, 6) and st[k - 1] not in (5, 6):
                green = tt[k]
        if green is None:
            continue
        # Chain followers behind the head.
        chain, tail = [H], H
        pool = [o for o in arr if o['t0'] <= H['t1'] + 1 and o['t1'] >= H['t1'] - 1 and o['id'] != H['id']]
        for _ in range(25):
            cand = []
            for o in pool:
                if o['id'] in {c['id'] for c in chain}:
                    continue
                al, la = rel(o, tail)
                if -14 < al < -2.5 and abs(la) < 1.4:
                    cand.append((abs(al), o))
            if not cand:
                break
            tail = sorted(cand, key=lambda c: c[0])[0][1]
            chain.append(tail)
        if len(chain) < 2:
            continue
        line = H['L'] / 2 + 1.0  # one metre ahead of the first front bumper
        times, startwave = [], []
        for pos, c in enumerate(chain, 1):
            g = objs[c['id']]
            ex, ey = g.x.values - H['x'], g.y.values - H['y']
            al = ex * H['dx'] + ey * H['dy'] + c['L'] / 2
            la = -ex * H['dy'] + ey * H['dx']
            t, v = g.t.values, g.v.values
            k = np.where((al >= line) & (t >= H['t1'] - 3))[0]
            if not len(k) or k[0] == 0:
                break
            k = k[0]
            tc = t[k - 1] + (line - al[k - 1]) / max(al[k] - al[k - 1], 1e-6) * (t[k] - t[k - 1])
            # Reject lane changes before the line and turning cars after it.
            m = np.searchsorted(t, tc + 4)
            turn = 0.
            if m < len(t):
                turn = abs(np.degrees(np.arctan2(g.y.values[m] - g.y.values[k], g.x.values[m] - g.x.values[k]) - np.arctan2(H['dy'], H['dx'])))
                turn = min(turn % 360, 360 - turn % 360)
            mv = np.where((t > c['t1'] - .2) & (v > 1))[0]
            times.append(dict(pos=pos, tc=tc, lat=float(la[k]), turn=float(turn), crossing_speed=float(v[k]), move=float(t[mv[0]]) if len(mv) else np.nan, stop_al=float(c['x'] - H['x']) * H['dx'] + float(c['y'] - H['y']) * H['dy'], L=float(c['L'])))
        if len(times) < 2:
            continue
        prev = green
        ok = True
        for r in times:
            h = r['tc'] - prev
            prev = r['tc']
            if r['pos'] > 1 and (h > 8 or h <= .3):
                ok = False
            if abs(r['lat']) > 2.5 or not ok:
                break
            rows.append(dict(cycle=f"{H['id']}", signal=best[0], pos=r['pos'], headway=h, through=r['turn'] < 25, crossing_speed=r['crossing_speed'], since_green=r['tc'] - green, L=r['L']))
        for c in chain:
            used.add(c['id'])
        kept = [r for r in times if np.isfinite(r['move'])]
        if len(kept) >= 4:
            d = [-r['stop_al'] for r in kept]
            tm = [r['move'] for r in kept]
            slope = np.polyfit(tm, d, 1)[0]
            heads.append(dict(cycle=f"{H['id']}", signal=best[0], n=len(kept), startwave_ms=float(slope), reaction=float(tm[0] - green), spacing=float(np.mean(np.diff(d)))))
    return rows, heads


with zipfile.ZipFile(Z) as z:
    SIGNALS.update({int(k): v for k, v in json.load(open(OUT / '04-dlrut-signals.json')).items()})
    names = sorted(n for n in z.namelist() if '/raw_data/trajectories/' in n and n.endswith('.csv'))
    rows, heads, files = [], [], 0
    for n in names:
        hhmm = re.search(r'trajectories_230924-(\d{4})', n)[1]
        if not FIRST <= hhmm < LAST:
            continue
        with z.open(n) as f:
            tr = pd.read_csv(f, usecols=COLS).rename(columns={'center_easting': 'x', 'center_northing': 'y', 'velocity_magnitude': 'v', 'dimension_length': 'L'})
        t0 = pd.to_datetime(tr.timestamp.iloc[0], format='ISO8601')
        tr['t'] = (pd.to_datetime(tr.timestamp, format='ISO8601') - t0).dt.total_seconds()
        tr = tr.drop(columns='timestamp')
        with z.open(n.replace('trajectories/trajectories', 'traffic_lights/traffic-lights')) as f:
            tl = pd.read_csv(f)
        tl['t'] = (pd.to_datetime(tl.timestamp, format='ISO8601') - t0).dt.total_seconds()
        r, h = analyse(tr, tl)
        rows += r
        heads += h
        files += 1
        print(hhmm, len(r), len(h), flush=True)
d = pd.DataFrame(rows)
hd = pd.DataFrame(heads)
d.to_csv(OUT / '04-dlrut-discharge.csv', index=False)
th = d[d.through]
late = th[th.pos >= 5].headway
res = dict(source='DLR-UT v1.3.1, CC BY-NC-SA 4.0', day='2023-09-24 Sunday', files=files, signals_parsed=len(SIGNALS), cars_in_queues=int(len(d)), cycles=int(d.cycle.nunique()),
           through_positions={int(p): dict(n=int(len(g)), median=round(float(g.headway.median()), 3), mean=round(float(g.headway.mean()), 3), p10=round(float(g.headway.quantile(.1)), 3), p90=round(float(g.headway.quantile(.9)), 3), crossing_speed=round(float(g.crossing_speed.median()), 2)) for p, g in th[th.pos <= 12].groupby('pos')},
           late_positions_ge5=dict(n=int(len(late)), cycles=int(th[th.pos >= 5].cycle.nunique()), median=float(late.median()) if len(late) else None, mean=float(late.mean()) if len(late) else None, p10=float(late.quantile(.1)) if len(late) else None, p90=float(late.quantile(.9)) if len(late) else None, sat_flow_from_median=round(3600 / late.median()) if len(late) else None, sat_flow_from_mean=round(3600 / late.mean()) if len(late) else None),
           by_signal={int(s): dict(n=int(len(g)), median=round(float(g.headway.median()), 3)) for s, g in th[th.pos >= 5].groupby('signal')},
           start_wave=dict(n=int(len(hd)), median_ms=float(hd.startwave_ms.median()) if len(hd) else None, median_kmh=float(hd.startwave_ms.median() * 3.6) if len(hd) else None, p10_kmh=float(hd.startwave_ms.quantile(.1) * 3.6) if len(hd) else None, p90_kmh=float(hd.startwave_ms.quantile(.9) * 3.6) if len(hd) else None, median_spacing_m=float(hd.spacing.median()) if len(hd) else None, median_reaction_s=float(hd.reaction.median()) if len(hd) else None))
if len(late):
    hs = late.median()
    c4 = th[th.pos <= 4].pivot_table(index='cycle', columns='pos', values='headway')
    c4 = c4.dropna() if c4.shape[1] == 4 else c4.iloc[0:0]
    res['startup_lost_s'] = dict(n=int(len(c4)), median=round(float((c4 - hs).sum(axis=1).median()), 2) if len(c4) else None, mean=round(float((c4 - hs).sum(axis=1).mean()), 2) if len(c4) else None)
json.dump(res, open(OUT / '04-dlrut-discharge.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
