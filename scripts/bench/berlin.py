"""Level 4 and the Berlin parts of level 3: site-hour flows and speeds through virtual detectors, scored against all 8 real days of May 2019."""
import csv
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import floors
import network as net
import runner
import scenes
import score

B19 = Path('/home/erikf/projects/personal/cars-data/berlin2019')
CREDIBLE = {'N1': .10, 'N5': .24, 'N6': .32, 'N7.geh5': .40, 'N14.1h1km': .30, 'N16.miss': .65, 'N16.false': .55, 'N17': .64, 'N18.onset': 1.0, 'N18.clear': 1.0, 'N19.peak': .20, 'N19.flow': .20}
ABS_MARGIN = {'N4.am': 1.0, 'N4.pm': 1.0}
ROUND = True


def read_sensors(path, sites, scale=1.0):
    """The instrument: count and arithmetic mean of spot speeds per lane, summed per site, rounded as the source rounds."""
    s = pd.read_csv(path)
    name = 'site' if 'site' in s else 'sensor'
    s['hour'] = (s.begin // 3600).astype(int)
    s = s[(s.hour >= 0) & (s.hour < 24)]
    s['vs'] = s['count'] * s['speed']
    g = s.groupby([name, 'hour']).agg(n=('count', 'sum'), vs=('vs', 'sum')).reset_index()
    idx = {x: i for i, x in enumerate(sites)}
    Q, V = np.full((len(sites), 24), np.nan), np.full((len(sites), 24), np.nan)
    Q[[i for i in range(len(sites)) if sites[i] in set(g[name])]] = 0.0
    for r in g.itertuples():
        i = idx.get(getattr(r, name))
        if i is None:
            continue
        Q[i, r.hour] = np.round(r.n * scale)
        V[i, r.hour] = np.round(r.vs / r.n * 3.6) if r.n else np.nan
    Q[:, sorted(set(range(24)) - set(g.hour))] = np.nan
    return Q, V


def score_runs(runs, B, nulls=None, fl=None):
    """runs: list of (Q, V), one per replicate. Every replicate against every real day; floors and nulls on the same sites and hours."""
    fl = fl or B.floors()
    nulls = nulls or B.nulls()
    D = {k: np.full((len(runs), len(B.days)), np.nan) for k in net.KEYS}
    for i, (q, v) in enumerate(runs):
        for j in range(len(B.days)):
            m = net.metrics(q, v, B.Q[j], B.V[j], B.panel)
            for k in net.KEYS:
                D[k][i, j] = m.get(k, np.nan)
    out = {}
    for k in net.KEYS:
        id_, _, sub = k.partition('.')
        F = max(fl[k]['F'], ABS_MARGIN.get(k, 0.0))
        c = score.judge(D[k], F, nulls.get(k), credible=CREDIBLE.get(k))
        c.update(D=np.round(D[k], 4).tolist(), p50=round(fl[k]['p50'], 4), n_sites=len(B.sites), real_days=len(B.days), note='tuning sites only')
        out.setdefault(id_, {})[sub or 'value'] = c
    if len(runs) >= 2:
        sp = net.spread([r[0] for r in runs], [r[1] for r in runs], B.Q, B.V)
        rc = sp['ratio']
        a = score.band([rc], .5, 1.5)
        a['D'] = [[abs(rc - 1)]]
        out['N15'] = {'ratio': a, 'crps_flow': dict(score.no_data('reported'), value=round(sp['crps_flow'], 4)), 'crps_speed': dict(score.no_data('reported'), value=round(sp['crps_speed'], 3)), 'rank_outer': dict(score.no_data('reported; real days 27.8%'), value=round(sp['rank_outer'], 3))}
    else:
        out['N15'] = {'ratio': score.no_data('needs at least 2 replicates')}
    out['C5'] = c5(runs, B)
    return out


def c5(runs, B):
    """Top real bottlenecks: is a jam at that site within an hour of the real one? Against every real day, ruled by real days."""
    day = net.DAY

    def tops(V, f, n=8):
        d = np.nansum(np.maximum(f[:, None] - V[:, day], 0), axis=1)
        return np.argsort(-d)[:n]

    def miss(Va, Vr):
        f = net.free_speed(Vr)
        Ja, Jr = net.jam(Va, f)[:, day], net.jam(Vr, f)[:, day]
        idx = tops(Vr, f)
        m = []
        for s in idx:
            if not Jr[s].any():
                continue
            hit = sum(1 for h in np.flatnonzero(Jr[s]) if Ja[s, max(0, h - 1):h + 2].any())
            m.append(1 - hit / Jr[s].sum())
        return float(np.mean(m)) if m else np.nan
    real = [miss(B.V[a], B.V[b]) for a in range(len(B.days)) for b in range(len(B.days)) if a != b]
    D = [[miss(v, B.V[j]) for j in range(len(B.days))] for _, v in runs]
    c = score.judge(D, score.floor_of(real), 1.0)
    c.update(D=np.round(D, 4).tolist(), p50=round(float(np.nanmedian(real)), 4), n_sites=len(B.sites))
    return {'jam_at_top_sites': c}


def n0(edges_csv, trips_csv, hours=24):
    """Report 14's bands that do not need a whole city's population. Hard band only, as N0 asks."""
    by = {}
    for c in pd.read_csv(edges_csv, chunksize=500000, usecols=['begin', 'samples', 'distance']):
        c['h'] = (c.begin // 3600).astype(int)
        g = c.groupby('h').agg(s=('samples', 'sum'), d=('distance', 'sum'))
        for h, r in g.iterrows():
            a = by.setdefault(int(h), [0.0, 0.0])
            a[0] += r.s
            a[1] += r.d
    d = np.array([by.get(h, [0, 0])[1] for h in range(24)], float)
    s = np.array([by.get(h, [0, 0])[0] for h in range(24)], float)
    sh = d / max(d.sum(), 1)
    v = np.divide(d, s, out=np.full(24, np.nan), where=s > 0) * 3.6
    mid = sh[10:15].mean()
    night = np.nanmean(v[2:5])
    midv = np.nanmean(v[10:15])
    worst = np.nanmin(v[6:23])
    vals = dict(am_peak=(sh[6:10].max(), .045, .10), pm_peak=(sh[15:20].max(), .05, .11), am_over_mid=(sh[6:10].max() / mid, .9, 1.7), pm_over_mid=(sh[15:20].max() / mid, .95, 1.9), night_share=(sh[list(range(0, 6)) + [22, 23]].sum(), .04, .17), day_07_19=(sh[7:19].sum(), .65, .85),
                worst_over_night=(worst / night, .42, .84), worst_over_mid=(worst / midv, .67, .95), worst_hour=(float(np.nanargmin(v[6:23]) + 6), 7, 19))
    cells = {}
    for k, (x, lo, hi) in vals.items():
        c = score.band([float(x)], lo, hi)
        c['D'] = [[abs(float(x) - (lo + hi) / 2)]]
        cells[k] = c
    return cells


def district_sites():
    return [x['site'] for x in csv.DictReader(open(B19 / 'step0/sites.csv'))] if (B19 / 'step1/freeze.json').exists() else []


def frozen_sites():
    return json.loads((B19 / 'step1/freeze.json').read_text())['district_sites']


def score_district(sensor_csvs, scale=1.0, edges=None, trips=None, B=None):
    sites = frozen_sites()
    B = B or floors.Berlin(sites=sites, split='tune')
    runs = [read_sensors(p, B.sites, scale) for p in sensor_csvs]
    M = score_runs(runs, B)
    if edges:
        M['N0'] = n0(edges, trips)
    M['N2'] = {'-': score.no_data('official 41.3 M km is for all Berlin; a district has no official total')}
    M['N20'] = {'-': score.no_data('district trips are cut at its edge, not whole trips: run on the city')}
    return M


def evaluate(cfg, folder=None, gpu=False, factor='10', seeds=(1,), runs=None):
    """The district. Either run it here, or score runs already made by the same commit. Demand factor 10 is the whole demand."""
    folder = Path(folder or B19)
    scale = {'01': .1, '05': .5, '10': 1.0}[factor]
    paths = []
    secs = 0.0
    extras = dict(teleports=0, unfinished=[])
    if runs:
        ds = [folder / 'runs' / r for r in runs]
    else:
        ds = []
        for seed in seeds:
            d = runner.STORE / 'work' / f"{cfg['name']}-berlin-f{factor}" / f's{seed}'
            d.mkdir(parents=True, exist_ok=True)
            plan = dict(net=folder / 'district/net.net.xml', routes=folder / f'district/routes_f{factor}.rou.gz', end=93600, fcd=None, sensors=folder / 'district/sensors.csv', edge_interval=900, edges=True, extra=['--capacity', str(int(factor) * 4000 + 4000), '--trusted'])
            r = runner.launch(cfg, plan, d, seed, {}, plan['net'], dt=cfg['dt_network'], gpu=gpu)
            secs += r.secs
            ds.append(d)
    for d in ds:
        paths.append(d / 'sensors.csv')
        sm = d / ('summary.csv')
        if sm.exists():
            t = pd.read_csv(sm)
            if len(t):
                last = t.iloc[-1]
                extras['teleports'] += int(last.teleports)
                extras['unfinished'].append(float(last.running) / max(float(last.inserted), 1))
    edges = next((d / 'edges.csv' for d in ds if (d / 'edges.csv').exists()), None)
    trips = next((d / 'trips.csv' for d in ds if (d / 'trips.csv').exists()), None)
    M = score_district(paths, 1.0, edges, trips)
    if extras['unfinished']:
        v = extras['unfinished']
        c = score.judge([[x] for x in v], .005)
        c.update(D=[[x] for x in v], value=round(float(np.median(v)), 5), note='running at the end of 26 h, of those inserted')
        M['V6'] = {'district_end': c}
    M['_V8_scale'] = scale
    M['_V1_teleports'] = extras['teleports']
    M['_runs'] = [str(d) for d in ds]
    return M, secs


def mini_day(d, cfg, ov, B, sites=30):
    """An engine test: separate roads, one per real site, with that site's mean hourly flow as demand. Its demand comes from
    the data that scores it, so it can never count as validation. It is what lets demand-side known-bad cases be run in minutes."""
    use = np.linspace(0, len(B.sites) - 1, min(sites, len(B.sites))).astype(int)
    Qm = np.nanmean(B.Q, axis=0)[use]
    vm = np.nanquantile(B.V, .9, axis=(0, 2))[use]
    names = [B.sites[i] for i in use]
    cls = B.cls[use]
    if not (d / 'net.xml').exists():
        nodes, edges, sensors = '', '', []
        for k, (name, v) in enumerate(zip(names, vm)):
            nodes += f'<node id="a{k}" x="{k * 40}" y="0"/><node id="b{k}" x="{k * 40}" y="1000"/>'
            edges += f'<edge id="e{k}" from="a{k}" to="b{k}" numLanes="2" speed="{max(v, 20) / 3.6:.2f}"/>'
        scenes.netconvert(d, nodes, edges)
        for k, name in enumerate(names):
            sensors += [f'{name},e{k}_0,500', f'{name},e{k}_1,500']
        (d / 'sensors.csv').write_text('\n'.join(sensors) + '\n')
    body = ''
    Q = Qm.copy()
    if ov.get('free_routes'):
        fast = np.flatnonzero(cls >= 1)
        for k in np.flatnonzero(cls == 0):
            if len(fast):
                t = fast[np.argmin(np.abs(fast - k))]
                Q[t] += Q[k] * .8
                Q[k] *= .2
    shift = int(ov.get('clock', 0))
    for k in range(len(names)):
        body += f'<route id="r{k}" edges="e{k}"/>'
    for k, name in enumerate(names):
        q = np.nan_to_num(Q[k])
        if ov.get('flat'):
            q[6:21] = q[6:21].sum() / 15
        if shift:
            q = np.roll(q, shift)
        for h in range(24):
            f = q[h] * ov.get('demand_scale', 1.0)
            if f >= 1:
                body += f'<flow id="f{k}_{h}" type="car" route="r{k}" begin="{h * 3600}" end="{(h + 1) * 3600}" vehsPerHour="{f:.1f}" departLane="free" departSpeed="max"/>'
    r = scenes.routes(d, cfg, ov, body)
    return dict(routes=r, end=86400, fcd=None, sensors=d / 'sensors.csv', edge_interval=3600, extra=['--capacity', '6000']), names, use


def engine_test(cfg, ov, seed=1, work=None, gpu=False, B=None, log=print):
    """Runs mini_day and scores it with the network metrics. Labelled an engine test: never in a driver's scorecard."""
    import hashlib
    B = B or floors.Berlin(split='tune')
    key = hashlib.sha256(json.dumps([cfg['name'], cfg['hash'], ov], sort_keys=True, default=str).encode()).hexdigest()[:10]
    d = Path(work or runner.STORE / 'work') / f'{cfg["name"]}-mini-{key}'
    d.mkdir(parents=True, exist_ok=True)
    plan, names, use = mini_day(d, cfg, ov, B)
    sd = d / f's{seed}'
    sd.mkdir(exist_ok=True)
    r = runner.launch(cfg, plan, sd, seed, ov, d / 'net.xml', dt=cfg['dt_network'], gpu=gpu)
    log(f'mini_day {r.secs:.0f}s')
    sub = floors.Berlin.__new__(floors.Berlin)
    sub.sites, sub.Q, sub.V, sub.cls, sub.days = names, B.Q[:, use], B.V[:, use], B.cls[use], B.days
    sub.panel = net.Panel(names, sub.cls, [[0, 0]] * len(names))
    q, v = read_sensors(sd / 'sensors.csv', names)
    M = score_runs([(q, v)], sub)
    M['V1'] = {'count': score.zero([r.teleports or 0], 'teleports')}
    scale = ov.get('demand_scale', 1.0)
    M['V8'] = {'scale': score.zero([0 if scale >= .95 else 1], f'demand scale {scale}')}
    return M, r.secs
