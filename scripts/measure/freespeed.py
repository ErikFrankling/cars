"""Part 8: desired speed by road type, from unconstrained cars (F147).

One value per car: the median of its speed over samples where it is free, with at least 2 s free.
  highD:  no preceding car within 150 m (dhw), same lane, not in a lane change (laneId constant for 2 s around).
  exiD:   main-carriageway lanelets only (no on- or off-ramp tag), no lead vehicle within 150 m (leadDHW), lane constant;
          the posted limit is the lanelet's speed_limit tag.
  inD:    priority-road lanelets of the site's right_of_way elements, moving at over 2 m/s, no moving road user
          ahead within 60 m in a 20-degree cone, speed not falling (not braking for the junction: 1 s acceleration over -0.3 m/s2).
  DLR HT: blocks from dlrht.py, no same-lane vehicle within 150 m ahead.
The spread across cars is the desired-speed spread (SUMO speedDev 0.1 means a coefficient of variation of 0.1).

    python3 -I scripts/measure/freespeed.py      # -> research/truth/measure/freespeed.json
"""
import os, sys, json, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
rng = np.random.default_rng(9)


def summary(v):
    v = np.asarray(v, float)
    if len(v) < 20:
        return {'n': int(len(v))}
    b = [np.median(v[rng.integers(0, len(v), len(v))]) for _ in range(400)]
    return dict(n=int(len(v)), median=round(float(np.median(v)), 2), ci=[round(float(np.percentile(b, 2.5)), 2), round(float(np.percentile(b, 97.5)), 2)],
                sd=round(float(v.std()), 2), cv=round(float(v.std() / v.mean()), 3), p5=round(float(np.percentile(v, 5)), 2),
                p95=round(float(np.percentile(v, 95)), 2), kmh_median=round(float(np.median(v)) * 3.6, 1))


def per_car(ids, v, free, minfree=50):
    df = pd.DataFrame(dict(id=ids, v=v))[free]
    g = df.groupby('id').v
    n = g.size()
    return g.median()[n >= minfree]


def highd():
    rows = []
    for _, m in LX.recordings('highD').iterrows():
        d = LX.tracks('highD', int(m.rec))
        cls = LX.tracks_meta('highD', int(m.rec)).set_index('id')['class']
        car = cls.reindex(d.id).values == 'Car'
        lane = d.lane.to_numpy(); ids = d.id.to_numpy()
        same = pd.Series(lane).groupby(ids).transform(lambda s: s.rolling(51, center=True, min_periods=1).std().fillna(0)).to_numpy() == 0
        free = car & ((d.prec.to_numpy() == 0) | (d.dhw.to_numpy() > 150)) & same
        pc = per_car(ids, np.abs(d.vx.to_numpy()), free)
        # Lane of the car while free: the leftmost lane is index 0 from the median.
        rows += [(int(m.rec), int(m.site), m.day, m.limit, i, v) for i, v in pc.items()]
    return pd.DataFrame(rows, columns=['rec', 'site', 'day', 'limit', 'id', 'v'])


def exid():
    rows = []
    for _, m in LX.recordings('exiD').iterrows():
        ll = LX.lanelets('exiD', int(m.site))
        main = {k: v['tags'].get('speed_limit', 'none') for k, v in ll.items() if v['tags'].get('subtype') == 'highway'
                and v['tags'].get('onramp') != 'yes' and v['tags'].get('offramp') != 'yes'}
        d = LX.tracks('exiD', int(m.rec))
        cls = LX.tracks_meta('exiD', int(m.rec)).set_index('trackId')['class']
        car = np.isin(cls.reindex(d.id).values, ['car', 'van'])
        ln = d.laneletId.to_numpy()
        onmain = np.isin(ln, list(main))
        lead = d.leadDHW.to_numpy()
        free = car & onmain & ((lead < 0) | (lead > 150) | ~np.isfinite(lead)) & (d.laneChange.to_numpy() != 1)
        v = np.hypot(d.vx, d.vy).to_numpy()
        lim = np.array([main.get(x, 'none') for x in ln])
        df = pd.DataFrame(dict(id=d.id.to_numpy(), v=v, lim=lim))[free]
        g = df.groupby('id')
        n = g.size()
        pc = g.v.median()[n >= 50]; pl = g.lim.agg(lambda s: s.mode().iat[0])
        rows += [(int(m.rec), int(m.site), m.day, pl[i], i, v_) for i, v_ in pc.items()]
    return pd.DataFrame(rows, columns=['rec', 'site', 'day', 'limit', 'id', 'v'])


def ind():
    import gaps as G
    rows = []
    for _, m in LX.recordings('inD').iterrows():
        rec, site = int(m.rec), int(m.site)
        cons = site == 1 and 11 <= rec <= 17
        ll = LX.lanelets('inD', site, cons)
        prio = set()
        for el in G.regulatory('inD', site, cons):
            prio |= set(el['prio'])
        d = LX.tracks('inD', rec)
        cls = LX.tracks_meta('inD', rec).set_index('trackId')['class']
        d['cls'] = cls.reindex(d.id).values
        d = d[d['cls'].isin(['car', 'truck_bus', 'motorcycle', 'bicycle'])].reset_index(drop=True)
        d['lanelet'] = G.match(d, {k: v for k, v in ll.items() if v['tags'].get('subtype') in ('road', 'bus_lane')})
        d = d[d.frame % 5 == 0].reset_index(drop=True)
        v = np.hypot(d.vx, d.vy).to_numpy(); hd = np.arctan2(d.vy, d.vx).to_numpy()
        free = np.zeros(len(d), bool)
        for fr, g in d.groupby('frame'):
            ix = g.index.to_numpy()
            if len(ix) < 1:
                continue
            x, y = g.xc.to_numpy(), g.yc.to_numpy()
            for a in ix[(g.cls.to_numpy() == 'car') & np.isin(g.lanelet.to_numpy(), list(prio))]:
                dx, dy = x - d.xc.iat[a], y - d.yc.iat[a]
                lon = dx * np.cos(hd[a]) + dy * np.sin(hd[a]); lat = -dx * np.sin(hd[a]) + dy * np.cos(hd[a])
                moving = v[ix] > 1.0                       # parked cars along the kerb are not leaders
                ahead = (lon > 0.5) & (lon < 60) & (np.abs(lat) < np.tan(np.deg2rad(20)) * lon + 1.5) & moving
                free[a] = (not ahead.any()) and v[a] > 2.0
        free &= d.lonAcceleration.to_numpy() > -0.3
        pc = per_car(d.id.to_numpy(), v, free, minfree=10)
        rows += [(rec, site, m.day, 13.89, i, x) for i, x in pc.items()]
    return pd.DataFrame(rows, columns=['rec', 'site', 'day', 'limit', 'id', 'v'])


def dlrht():
    rows = []
    for p in sorted(glob.glob('/home/erikf/projects/personal/cars-data/measure/dlrht/b*.npz')):
        zf = np.load(p); z = {k: zf[k] for k in ('id', 'cc', 'v', 'tr', 'L', 'lane')}
        free = (~np.isfinite(z['cc']) | (z['cc'] > 150)) & (z['tr'] == 0) & (z['L'] < 7)
        pc = per_car(z['id'], z['v'], free, minfree=10)
        rows += [(int(os.path.basename(p)[1:3]), i, x) for i, x in pc.items()]
    return pd.DataFrame(rows, columns=['blk', 'id', 'v'])


if __name__ == '__main__':
    res = {}
    h = highd()
    res['highD'] = {'all': summary(h.v)}
    for (lim, site), g in h.groupby([h.limit.fillna(0), 'site']):
        res['highD'][f'limit {round(lim * 3.6) if lim else "none"} site {site}'] = summary(g.v)
    for lim, g in h.groupby(h.limit.fillna(0)):
        res['highD'][f'limit {round(lim * 3.6) if lim else "none"}'] = summary(g.v)
    for (site, day), g in h.groupby(['site', 'day']):
        res['highD'][f'site {site} {day}'] = summary(g.v)
    print('highD', json.dumps(res['highD'])[:1500], flush=True)
    e = exid()
    res['exiD'] = {f'limit {lim}': summary(g.v) for lim, g in e.groupby('limit')}
    for (site, lim), g in e.groupby(['site', 'limit']):
        res['exiD'][f'site {site} limit {lim}'] = summary(g.v)
    print('exiD', json.dumps(res['exiD'])[:1500], flush=True)
    i = ind()
    res['inD'] = {'all': summary(i.v)} | {f'site {s}': summary(g.v) for s, g in i.groupby('site')}
    print('inD', json.dumps(res['inD']), flush=True)
    t = dlrht()
    res['DLR HT'] = summary(t.v)
    json.dump(res, open(os.path.join(RES, 'freespeed.json'), 'w'), indent=1)
    print(json.dumps(res['DLR HT']))
