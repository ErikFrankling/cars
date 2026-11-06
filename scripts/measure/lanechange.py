"""Part 6: lane changes and on-ramp merges (exiD, highD): accepted gaps, duration, where along the on-ramp, and whether
the car behind yields (F142-F145).

An event is the frame where the car's lane (exiD laneletId with the provider's laneChange flag; highD laneId) changes,
i.e. where its centre crosses the marking. At that frame:
  lag gap  = new follower's bumper gap to the changer (along the changer's heading), time gap = lag / follower speed
  lead gap = changer's bumper gap to the new leader, time gap = lead / changer speed
Duration: lateral position made continuous across the marking, end plateaus = median of the first and last 0.5 s of a
window of 5 s each side, displacement 2.5-5.5 m, then 10%-90% time (report 05 used 8 s each side; these recordings
are too short, so long changes are cut: a lower bound).
Merge: the old lanelet is an on-ramp lanelet that shares a boundary with the main carriageway (the acceleration lane)
and the new one is main carriageway. Position = the changer's centre projected on the acceleration lane, as a share of
its length from where it first touches the main carriageway.
Yield: the new follower's mean acceleration over the 3 s before the crossing against followers in the same lanelet and
speed band (2 m/s) with no lane change ahead of them within 5 s.

    python3 -I scripts/measure/lanechange.py exiD      # -> research/truth/measure/lanechange_exiD.json
    python3 -I scripts/measure/lanechange.py highD
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
WORK = '/home/erikf/projects/personal/cars-data/measure/lanechange'
rng = np.random.default_rng(5)
FPS = 25


def q(v, ps=(5, 10, 25, 50, 75, 90, 95)):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return ({f'p{p}': round(float(np.percentile(v, p)), 3) for p in ps} | {'n': int(len(v))}) if len(v) else {'n': 0}


def boot_q(v, p, reps=400):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    if len(v) < 10:
        return None
    b = [np.percentile(v[rng.integers(0, len(v), len(v))], p) for _ in range(reps)]
    return [round(float(np.percentile(v, p)), 3), round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)]


def duration(y, k, w=5 * FPS, plat=FPS // 2):
    """10-90% time around index k of a continuous lateral series y; None if the window or displacement fails."""
    a, b = k - w, k + w
    if a < 0 or b > len(y):
        return None
    s = y[a:b]
    y0, y1 = np.median(s[:plat]), np.median(s[-plat:])
    D = y1 - y0
    if not 2.5 <= abs(D) <= 5.5:
        return None
    f = (s - y0) / D
    i10 = np.flatnonzero(f >= 0.1); i90 = np.flatnonzero(f >= 0.9)
    if not len(i10) or not len(i90):
        return None
    lat_speed = np.abs(np.diff(s)) * FPS
    return (i90[0] - i10[0]) / FPS, float(abs(D)), float(lat_speed.max())


def unwrap_lateral(off, lane_change_rows):
    y = off.astype(float).copy()
    for k in lane_change_rows:
        if 2 <= k < len(y):
            jump = y[k] - y[k - 1]
            if abs(jump) > 1.5:
                y[k:] -= jump - (y[k - 1] - y[k - 2])
    return y


def accel_lane_chains(ll):
    """On-ramp lanelets sharing a boundary with a main-carriageway lanelet, chained by succession: list of polylines."""
    main_bounds = set()
    for v in ll.values():
        if v['tags'].get('subtype') == 'highway' and v['tags'].get('onramp') != 'yes' and v['tags'].get('offramp') != 'yes':
            main_bounds.add(frozenset(v['left_nodes'])); main_bounds.add(frozenset(v['right_nodes']))
    adj = {k for k, v in ll.items() if v['tags'].get('onramp') == 'yes' and
           (frozenset(v['left_nodes']) in main_bounds or frozenset(v['right_nodes']) in main_bounds)}
    succ = {}
    for a in adj:
        for b in adj:
            if a != b and ll[a]['left_nodes'][-1] == ll[b]['left_nodes'][0] and ll[a]['right_nodes'][-1] == ll[b]['right_nodes'][0]:
                succ[a] = b
    heads = [a for a in adj if a not in succ.values()]
    chains = []
    for h in heads:
        c = [h]
        while c[-1] in succ and len(c) < 50:
            c.append(succ[c[-1]])
        pts = np.vstack([ll[k]['centre'] for k in c])
        chains.append(dict(lanelets=set(c), centre=pts, length=float(np.hypot(*np.diff(pts, axis=0).T).sum())))
    return chains, adj


def project(pts, x, y):
    seg = np.diff(pts, axis=0); L = np.hypot(*seg.T); cum = np.r_[0, np.cumsum(L)]
    u = seg / np.maximum(L, 1e-9)[:, None]
    best, s_best = np.inf, 0.0
    for i in range(len(seg)):
        t = np.clip((x - pts[i, 0]) * u[i, 0] + (y - pts[i, 1]) * u[i, 1], 0, L[i])
        dd = np.hypot(x - pts[i, 0] - t * u[i, 0], y - pts[i, 1] - t * u[i, 1])
        if dd < best:
            best, s_best = dd, cum[i] + t
    return s_best, best


def gaps_at(d, look, i, fid, lid, heading):
    """Lag and lead bumper gaps (m) and the follower's speed, from positions at the event frame."""
    fr = d.frame.iat[i]; ux, uy = np.cos(heading), np.sin(heading)
    xm, ym, Lm = d.xc.iat[i], d.yc.iat[i], d.length.iat[i]
    out = {}
    for role, oid in (('lag', fid), ('lead', lid)):
        j = look.get((fr, oid)) if oid is not None and oid > 0 else None
        if j is None:
            out[role] = (np.nan, np.nan, np.nan); continue
        dx, dy = d.xc.iat[j] - xm, d.yc.iat[j] - ym
        lon = dx * ux + dy * uy
        g = (-lon if role == 'lag' else lon) - (Lm + d.length.iat[j]) / 2
        out[role] = (g, float(np.hypot(d.vx.iat[j], d.vy.iat[j])), j)
    return out


def run_exid():
    meta = LX.recordings('exiD')
    ev_rows, base_rows = [], []
    for _, m in meta.iterrows():
        rec, site = int(m.rec), int(m.site)
        ll = LX.lanelets('exiD', site)
        chains, adj = accel_lane_chains(ll)
        d = LX.tracks('exiD', rec)
        cls = LX.tracks_meta('exiD', rec).set_index('trackId')['class']
        d['cls'] = cls.reindex(d.id).values
        look = {(f, i): k for k, (f, i) in enumerate(zip(d.frame.to_numpy(), d.id.to_numpy()))}
        v = np.hypot(d.vx, d.vy).to_numpy(); acc = d.lonAcceleration.to_numpy()
        ids, st, en = LX.by_track(d)
        lane = d.laneletId.to_numpy()
        lc = d.laneChange.to_numpy() == 1
        rear_events = []
        for tid, a, b in zip(ids, st, en):
            rows = np.flatnonzero(lc[a:b])
            if not len(rows):
                continue
            y = unwrap_lateral(d.latLaneCenterOffset.to_numpy()[a:b], rows)
            for k in rows:
                i = a + k
                if k < 1:
                    continue
                old, new = lane[i - 1], lane[i]
                if not (np.isfinite(old) and np.isfinite(new)) or old not in ll or new not in ll:
                    continue
                to_, tn = ll[old]['tags'], ll[new]['tags']
                kind = 'merge' if (old in adj and tn.get('onramp') != 'yes') else \
                       'exit' if (tn.get('offramp') == 'yes' and to_.get('offramp') != 'yes') else \
                       'mainline' if to_.get('onramp') != 'yes' and to_.get('offramp') != 'yes' and tn.get('offramp') != 'yes' else 'other'
                hd = np.deg2rad(d.heading.iat[i])
                fid = d.rearId.iat[i]; lid = d.leadId.iat[i]
                fid = int(fid) if np.isfinite(fid) and fid >= 0 else None; lid = int(lid) if np.isfinite(lid) and lid >= 0 else None
                g = gaps_at(d, look, i, fid, lid, hd)
                dur = duration(y, k)
                pos = None
                if kind == 'merge':
                    for c in chains:
                        if old in c['lanelets']:
                            s, dist = project(c['centre'], d.xc.iat[i], d.yc.iat[i])
                            pos = (s, c['length'], dist)
                # Follower's mean acceleration over the 3 s before the crossing, from its own record.
                ya = np.nan
                if fid is not None:
                    js = [look.get((d.frame.iat[i] - kk, fid)) for kk in range(0, 3 * FPS)]
                    js = [j for j in js if j is not None]
                    if len(js) >= 2 * FPS:
                        ya = float(np.mean(acc[js]))
                    rear_events.append((fid, d.frame.iat[i]))
                ev_rows.append(dict(rec=rec, site=site, day=m.day, id=int(tid), cls=d.cls.iat[i], kind=kind, v=float(v[i]),
                                    lag_gap=g['lag'][0], lag_v=g['lag'][1], lead_gap=g['lead'][0], lead_v=g['lead'][1],
                                    lag_tg=g['lag'][0] / max(g['lag'][1], 0.5) if np.isfinite(g['lag'][0]) else np.nan,
                                    lead_tg=g['lead'][0] / max(v[i], 0.5) if np.isfinite(g['lead'][0]) else np.nan,
                                    dur=dur[0] if dur else np.nan, width=dur[1] if dur else np.nan, peak_lat=dur[2] if dur else np.nan,
                                    pos=pos[0] if pos else np.nan, acc_len=pos[1] if pos else np.nan, pos_dist=pos[2] if pos else np.nan,
                                    follower_acc3=ya, new_lanelet=int(new)))
        # Baseline followers: vehicles in the lanelets merges go into, every second, no lane change ahead within 5 s.
        merge_new = {e['new_lanelet'] for e in ev_rows if e['rec'] == rec and e['kind'] == 'merge'}
        if merge_new:
            rear = pd.DataFrame(rear_events, columns=['id', 'frame'])
            near = set()
            for fid_, fr in rear.itertuples(index=False):
                for f in range(fr - 5 * FPS, fr + 5 * FPS + 1, FPS):
                    near.add((fid_, f - f % FPS))
            for tid, a, b in zip(ids, st, en):
                for i in range(a + 3 * FPS, b, FPS):
                    if lane[i] in merge_new and d.cls.iat[i] in ('car', 'van') and (tid, d.frame.iat[i] - d.frame.iat[i] % FPS) not in near \
                            and not lc[i - 3 * FPS:i + 1].any():
                        base_rows.append((rec, site, float(v[i]), float(acc[i - 3 * FPS:i].mean())))
        print('exiD', rec, site, len(ev_rows), len(base_rows), flush=True)
    E = pd.DataFrame(ev_rows); B = pd.DataFrame(base_rows, columns=['rec', 'site', 'v', 'acc3'])
    os.makedirs(WORK, exist_ok=True)
    E.to_csv(f'{WORK}/exiD_events.csv', index=False); B.to_csv(f'{WORK}/exiD_baseline.csv', index=False)
    summarise('exiD', E, B, meta)


def summarise(ds, E, B, meta):
    res = {'recordings': meta.rec.tolist(), 'events': int(len(E))}
    E = E[E.cls.isin(['car', 'van', 'Car'])]
    for kind, g in E.groupby('kind'):
        r = dict(n=len(g), speed=q(g.v, (5, 50, 95)), lag_time_gap_s=q(g.lag_tg), lead_time_gap_s=q(g.lead_tg), lag_gap_m=q(g.lag_gap, (5, 50, 95)),
                 lead_gap_m=q(g.lead_gap, (5, 50, 95)), lag_tg_p5_ci=boot_q(g.lag_tg, 5), lag_tg_p50_ci=boot_q(g.lag_tg, 50),
                 lead_tg_p5_ci=boot_q(g.lead_tg, 5), lead_tg_p50_ci=boot_q(g.lead_tg, 50),
                 duration_10_90_s=q(g.dur, (5, 25, 50, 75, 95)), duration_p50_ci=boot_q(g.dur, 50), width_m=q(g.width, (5, 50, 95)),
                 peak_lateral_speed=q(g.peak_lat, (5, 50, 95)), closing_lag=q(g.lag_v - g.v, (5, 50, 95)),
                 by_site={int(s): dict(n=len(gg), lag_tg_p50=round(float(gg.lag_tg.median()), 2) if gg.lag_tg.notna().any() else None,
                                       lead_tg_p50=round(float(gg.lead_tg.median()), 2) if gg.lead_tg.notna().any() else None,
                                       dur_p50=round(float(gg.dur.median()), 2) if gg.dur.notna().any() else None) for s, gg in g.groupby('site')})
        if kind == 'merge' and g.pos.notna().any():
            share = (g.pos / g.acc_len).clip(0, 1)
            left = g.acc_len - g.pos
            r['position_share'] = q(share, (10, 25, 50, 75, 90)); r['position_share_p50_ci'] = boot_q(share, 50)
            r['in_last_10pct'] = round(float((share > 0.9).mean()), 3)
            r['metres_left'] = q(left, (10, 25, 50, 75, 90)); r['accel_lane_length_m'] = q(g.acc_len, (5, 50, 95))
            r['position_by_site'] = {int(s): dict(n=int(gg.pos.notna().sum()), share_p50=round(float((gg.pos / gg.acc_len).median()), 3),
                                                  left_p50=round(float((gg.acc_len - gg.pos).median()), 1), lane_m=round(float(gg.acc_len.median()), 1))
                                     for s, gg in g.groupby('site') if gg.pos.notna().sum() > 10}
        if len(B) and g.follower_acc3.notna().any():
            B2 = B.copy(); B2['vb'] = (B2.v // 2).astype(int)
            mu = B2.groupby('vb').acc3.mean(); sd = B2.groupby('vb').acc3.std()
            gg = g[g.follower_acc3.notna() & g.lag_v.notna()].copy(); gg['vb'] = (gg.lag_v // 2).astype(int)
            gg['z'] = gg.follower_acc3 - mu.reindex(gg.vb).to_numpy()
            B2['z'] = B2.acc3 - mu.reindex(B2.vb).to_numpy()
            gg = gg[np.isfinite(gg.z)]
            yshare = float((gg.z <= -0.3).mean()); bshare = float((B2.z <= -0.3).mean())
            bs = [float((gg.z.values[rng.integers(0, len(gg), len(gg))] <= -0.3).mean()) for _ in range(400)]
            r['follower_yield'] = dict(n=len(gg), share_0_3_below=round(yshare, 3), ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                                       baseline_share=round(bshare, 3), excess=round(yshare - bshare, 3), baseline_windows=len(B2),
                                       mean_relative_acc=round(float(gg.z.mean()), 3))
        res[kind] = r
    json.dump(res, open(os.path.join(RES, f'lanechange_{ds}.json'), 'w'), indent=1)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in list(v)[:12]}) for k, v in res.items()})[:6000])


def run_highd():
    meta = LX.recordings('highD')
    rows = []
    for _, m in meta.iterrows():
        rec = int(m.rec)
        d = LX.tracks('highD', rec)
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        d['cls'] = cls.reindex(d.id).values
        look = {(f, i): k for k, (f, i) in enumerate(zip(d.frame.to_numpy(), d.id.to_numpy()))}
        ids, st, en = LX.by_track(d)
        lane = d.lane.to_numpy(); yc = d.yc.to_numpy(); v = np.abs(d.vx.to_numpy())
        for tid, a, b in zip(ids, st, en):
            ch = np.flatnonzero(lane[a + 1:b] != lane[a:b - 1]) + 1
            for k in ch:
                i = a + k
                hd = 0.0 if d.dir.iat[i] == 2 else np.pi
                fid = int(d.foll.iat[i]) or None; lid = int(d.prec.iat[i]) or None
                g = gaps_at(d, look, i, fid, lid, hd)
                dur = duration(yc[a:b], k)
                rows.append(dict(rec=rec, site=int(m.site), day=m.day, id=int(tid), cls=d.cls.iat[i], kind='mainline', v=float(v[i]),
                                 lag_gap=g['lag'][0], lag_v=g['lag'][1], lead_gap=g['lead'][0], lead_v=g['lead'][1],
                                 lag_tg=g['lag'][0] / max(g['lag'][1], 0.5) if np.isfinite(g['lag'][0]) else np.nan,
                                 lead_tg=g['lead'][0] / max(v[i], 0.5) if np.isfinite(g['lead'][0]) else np.nan,
                                 dur=dur[0] if dur else np.nan, width=dur[1] if dur else np.nan, peak_lat=dur[2] if dur else np.nan,
                                 pos=np.nan, acc_len=np.nan, pos_dist=np.nan, follower_acc3=np.nan,
                                 direction='left' if (d.dir.iat[i] == 1) == (yc[i] > yc[i - 1]) else 'right'))
        print('highD', rec, len(rows), flush=True)
    E = pd.DataFrame(rows)
    os.makedirs(WORK, exist_ok=True); E.to_csv(f'{WORK}/highD_events.csv', index=False)
    summarise('highD', E, pd.DataFrame(), meta)
    # Left (overtaking) and right changes separately.
    res = json.load(open(os.path.join(RES, 'lanechange_highD.json')))
    res['by_direction'] = {dr: dict(n=len(g), lag_tg=q(g.lag_tg, (5, 50)), lead_tg=q(g.lead_tg, (5, 50)), dur=q(g.dur, (50,)))
                           for dr, g in E[E.cls == 'Car'].groupby('direction')}
    json.dump(res, open(os.path.join(RES, 'lanechange_highD.json'), 'w'), indent=1)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] == 'summary':
        summarise('exiD', pd.read_csv(f'{WORK}/exiD_events.csv'), pd.read_csv(f'{WORK}/exiD_baseline.csv'), LX.recordings('exiD'))
    else:
        {'exiD': run_exid, 'highD': run_highd}[sys.argv[1]]()
