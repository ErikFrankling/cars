"""Levels 0 to 3 on test scenes. One function per metric ID. Each returns {sub: cell} from replicate-level inputs."""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

import score
from . import extract as X

P = np.linspace(.01, .99, 99)
RMIN = 200


def w1(sim, q):
    return float(np.abs(np.quantile(sim, P) - np.asarray(q)).mean())


def per_tracker(samples, floors, key, witness=False):
    """M1, M2, M3: W1 of each replicate against each real block, per tracker and speed band. Never pooled."""
    cells = {}
    between = floors['_between'][key]
    for site, sr in floors.items():
        if site.startswith('_'):
            continue
        for bn, band in sr['bands'].items():
            if bn == '1-5':
                continue
            blocks = [b[key] for b in band['blocks']]
            D = []
            for s in samples:
                x = s.get(bn, np.array([]))
                D.append([w1(x, q) if len(x) >= RMIN else np.nan for q in blocks])
            c = score.judge(D, band['F_' + key], band['N_' + key], credible=between['hi'] if key != 'j' else None)
            c.update(D=np.round(D, 4).tolist(), p50=round(band['p50_' + key], 4), real_blocks=len(blocks))
            cells[f'{site}|{bn}'] = c
    return cells


def M4(spacings):
    v = [float(np.nanmedian(s)) if len(s) else np.nan for s in spacings]
    c = score.band(v, 6.5, 8.2, N=6.0)
    c['D'] = [[abs(x - 7.35)] for x in v]
    return {'spacing': c}


def M6(chains):
    ratios, waves = [], []
    for ch in chains:
        if np.isfinite(ch['ratio']):
            ratios.append(ch['ratio'])
        if np.isfinite(ch['wave']):
            waves.append(ch['wave'])
    a = score.band(ratios, .9, 1.15, N=0.0) if ratios else score.no_data('no chain')
    b = score.band(waves, 27.5, 43.0, N=200.0) if waves else score.no_data('no wave')
    a['D'] = [[abs(x - 1.025)] for x in ratios]
    b['D'] = [[abs(x - 35.25)] for x in waves]
    return {'sd_ratio': a, 'wave_kmh': b}


def chain_stats(f, interval, offsets):
    """Followers c1 to c8 behind the rig's head, while the head drives its profile."""
    f = f.assign(s=f.pos + f.lane.map(offsets).astype('f8'))
    t_max = f[f.trip == 'h'].time.max()
    f = f[(f.time > 30) & (f.time < t_max - 40)]
    g = {i: f[f.trip == f'c{i}'].sort_values('time') for i in (1, 8)}
    if not len(g[1]) or not len(g[8]):
        return dict(ratio=np.nan, wave=np.nan)
    m = g[1][['time', 'speed', 's']].merge(g[8][['time', 'speed', 's']], on='time', suffixes=('', '_b'))
    wave = X.wave_lag(m.speed, m.speed_b, interval, float((m.s - m.s_b).mean()))
    sd1, sd8 = m.speed.std(), m.speed_b.std()
    return dict(ratio=float(sd8 / sd1) if sd1 else np.nan, wave=wave)


def M7(shapes_by_seed):
    """Instant changes have a duration of nothing, which the band rules out."""
    dur, peak = [], []
    for s in shapes_by_seed:
        dur.append(float(s.t1090.median()) if len(s) else 0.0)
        peak.append(float(s.peak.median()) if len(s) else 0.0)
    a = score.band(dur, 5.0, 5.8, N=0.0)
    b = score.band(peak, .69, .83, N=0.0)
    a['D'] = [[abs(x - 5.4)] for x in dur]
    b['D'] = [[abs(x - .76)] for x in peak]
    return {'duration_s': a, 'lateral_mps': b}


def M8(rates):
    c = score.band(rates, .22, .30, N=0.0)
    c['D'] = [[abs(x - .26)] for x in rates]
    return {'per_veh_km': c}


M9_REAL = dict(congested=dict(lag=[.56, .74, 1.67], lead=[.33, .47, 1.13]), free=dict(lag=[.70, .90, 2.33], lead=[.61, .87, 4.14]))


def M9(gaps, regime):
    """Thin: report 05's pooled quantiles, ruler 30% of each, until W1 by block is computed. Null: anything goes, a gap of nothing."""
    real = M9_REAL[regime]
    qs = [.05, .1, .5]
    F = float(np.mean([.3 * x for x in real['lag'] + real['lead']]))
    N = float(np.mean(real['lag'] + real['lead']))
    D = []
    for g in gaps:
        lag, lead = g.lag.dropna(), g.lead.dropna()
        if len(lag) < 20 or len(lead) < 20:
            D.append([np.nan])
            continue
        d = [abs(a - b) for a, b in zip(np.quantile(lag, qs), real['lag'])] + [abs(a - b) for a, b in zip(np.quantile(lead, qs), real['lead'])]
        D.append([float(np.mean(d))])
    c = score.judge(D, F, N, thin=True)
    c['D'] = D
    return {regime: c}


def M11(speeds, limit=33.0):
    v = [float(np.median(s) / limit) for s in speeds if len(s)]
    return {'desired_ratio': dict(score.no_data('reported only: limit on the A39 not verified'), value=round(float(np.mean(v)), 3) if v else None)}


def M12(acc_bad):
    bad = [int(a) for a in acc_bad]
    c = score.zero(bad, 'samples braking past the -8.91 m/s2 tyre limit, or accelerating over 5 m/s2')
    return {'past_limits': c}


def M13(amps, pers, floors):
    blocks = [b for s, sr in floors.items() if not s.startswith('_') and 'waves' in sr for b in sr['waves']['blocks']]
    amp, per = [b['amp'] for b in blocks], [b['per'] for b in blocks if np.isfinite(b['per'])]
    cells = {}
    import itertools
    for name, sim, real, nul in (('swing_mps', amps, amp, 0.0), ('period_s', pers, per, 0.0)):
        F = score.floor_of([abs(a - b) for a, b in itertools.permutations(real, 2)])
        D = [[abs(s - r) if np.isfinite(s) else np.nan for r in real] for s in sim]
        c = score.judge(D, F, float(np.median(np.abs(np.asarray(real) - nul))))
        c.update(D=np.round(D, 3).tolist(), real_blocks=len(real), p50=float(np.median([abs(a - b) for a, b in itertools.permutations(real, 2)])))
        cells[name] = c
    return cells


def M14(series):
    """No trend over the run: the change from first to last third, against what the middle third itself wanders by."""
    cells = {}
    D, F = [], []
    for s in series:
        n = len(s)
        if n < 6:
            continue
        a, b, c_ = s[:n // 3], s[n // 3:2 * n // 3], s[2 * n // 3:]
        D.append([abs(float(np.mean(c_)) - float(np.mean(a)))])
        F.append(2 * float(np.std(b)) + .05)
    if not D:
        return {'speed': score.no_data('run too short')}
    c = score.judge(D, float(np.mean(F)), None)
    c['D'] = D
    return {'speed': c}


def js1(tabs):
    real = {1: (3.23, 3.92), 2: (2.20, 2.60), 3: (2.00, 2.20), 4: (2.00, 2.20), 5: (1.8, 2.2), 6: (1.8, 2.2), 7: (1.8, 2.2)}
    cells = {}
    norm_all = []
    for t in tabs:
        vals = [abs(float(np.nanmedian(t[t.pos == p].h)) - sum(real[p]) / 2) / ((real[p][1] - real[p][0]) / 2) if (t.pos == p).any() else np.nan for p in real]
        norm_all.append([float(np.nanmean(vals))] if np.isfinite(vals).any() else [np.nan])
    null = float(np.mean([abs(2.2 - sum(real[p]) / 2) / ((real[p][1] - real[p][0]) / 2) for p in real]))
    a = score.judge(norm_all, 1.0, null)
    a['D'] = norm_all
    cells['all_positions'] = a
    for p, (lo, hi) in real.items():
        v = [float(np.nanmedian(t[t.pos == p].h)) if (t.pos == p).any() else np.nan for t in tabs]
        v = [x for x in v if np.isfinite(x)]
        c = score.band(v, lo, hi) if v else score.no_data('no queue this deep')
        c['D'] = [[abs(x - (lo + hi) / 2)] for x in v]
        cells[f'pos{p}'] = c
    return cells


def sat_flow(t):
    h = t[t.pos >= 5].h
    return 3600 / float(np.median(h)) if len(h) >= 5 else np.nan


def js2(tabs, tabs_dt1):
    cells = {}
    for name, ts in (('dt_config', tabs), ('dt_1s', tabs_dt1)):
        v = [sat_flow(t) for t in ts]
        v = [x for x in v if np.isfinite(x)]
        if not v:
            cells[name] = score.no_data('no deep queue')
            continue
        c = score.band(v, 1800, 2100, N=3600.0)
        c['D'] = [[abs(x - 1950)] for x in v]
        cells[name] = c
    return cells


def js3(tabs):
    v = []
    for t in tabs:
        hs = np.nanmedian(t[t.pos >= 5].h) if (t.pos >= 5).any() else np.nan
        hk = [np.nanmedian(t[t.pos == p].h) for p in (1, 2, 3, 4) if (t.pos == p).any()]
        if len(hk) == 4 and np.isfinite(hs):
            v.append(float(sum(hk) - 4 * hs))
    c = score.band(v, 2.44, 3.58, N=0.0) if v else score.no_data('no queue')
    c['D'] = [[abs(x - 3.01)] for x in v]
    return {'lost_s': c}


def js4(tabs):
    first = [t[t.pos == 1] for t in tabs]
    start = [float(x.start.median()) for x in first if len(x)]
    peak = [float(x.peak.median()) for x in first if len(x)]
    t5 = [float(x.t5.median()) for x in first if len(x) and x.t5.notna().any()]
    cells = {}
    for name, v, lo, hi, nul in (('start_s', start, 1.42, 1.83, 0.0), ('peak_accel', peak, 1.30, 2.45, 4.0), ('time_to_5', t5, 3.2, 4.8, 2.0)):
        c = score.band(v, lo, hi, N=nul, thin=name == 'time_to_5') if v else score.no_data('no first car')
        c['D'] = [[abs(x - (lo + hi) / 2)] for x in v]
        cells[name] = c
    return cells


def js5(tabs):
    v = []
    for t in tabs:
        rows = []
        for c, g in t[t.pos <= 8].groupby('cycle'):
            g = g.sort_values('pos')
            if len(g) >= 5 and g.start.notna().all():
                d = g.stand.iloc[0] - g.stand.to_numpy()
                ds = g.start.to_numpy() - g.start.iloc[0]
                if ds[-1] > 0:
                    rows.append(np.polyfit(ds, d, 1)[0] * 3.6)
        if rows:
            v.append(float(np.median(rows)))
    c = score.band(v, 16, 28, N=200.0) if v else score.no_data('no queue')
    c['D'] = [[abs(x - 22)] for x in v]
    return {'wave_kmh': c}


def yellow_decisions(f, length, dt, end):
    rows = []
    cycle = 50.0
    for k in range(int(end / cycle)):
        t_y = k * cycle + 27.0
        at = f[(np.abs(f.time - t_y) < dt / 2 + 1e-3) & (f.lane == 'in_0') & (f.speed > 2.0)]
        for r in at.itertuples():
            ttl = (length - r.pos) / r.speed
            later = f[(f.trip == r.trip) & (f.time >= t_y) & (f.time < t_y + 25)]
            red = later[later.time < t_y + 23]
            stopped = red.speed.min() < .3 and (red.lane == 'in_0').all()
            rows.append((ttl, stopped, max(-later.acc.min(), 0.0)))
    return rows


def js6(rows_by_seed):
    half, hard = [], []
    for rows in rows_by_seed:
        a = np.array(rows, float) if rows else np.zeros((0, 3))
        a = a[a[:, 0] < 8.0] if len(a) else a
        if len(a) < 20:
            continue
        x, y = a[:, 0], a[:, 1]

        def nll(p):
            z = np.clip((x - p[0]) / abs(p[1]), -30, 30)
            q = np.clip(1 / (1 + np.exp(-z)), 1e-6, 1 - 1e-6)
            return -(y * np.log(q) + (1 - y) * np.log(1 - q)).sum()
        half.append(float(minimize(nll, [5.0, .5], method='Nelder-Mead').x[0]))
        st = a[a[:, 1] > 0]
        hard.append(float((st[:, 2] > 3).mean()) if len(st) else 0.0)
    if not half:
        return {'half_at_s': score.no_data('no decisions'), 'hard_stops': score.no_data('no decisions')}
    a = score.band(half, 4.5, 5.7, N=0.0)
    b = score.judge([[x] for x in hard], .02, 1.0)
    b['value'] = round(float(np.median(hard)), 4)
    a['D'] = [[abs(x - 5.1)] for x in half]
    b['D'] = [[x] for x in hard]
    return {'half_at_s': a, 'hard_stops': b}


def delay_samples(f, interval):
    f = f.sort_values(['trip', 'time'], kind='stable')
    lost = (1 - f.speed / 13.89).clip(lower=0) * interval
    return lost.groupby(f.trip.values).sum().to_numpy()


def js7(samples, floors):
    d = floors['delay']
    D = [[w1(s, b['q']) if len(s) >= 20 else np.nan for b in d['blocks']] for s in samples]
    c = score.judge(D, d['F'], d['N'])
    c.update(D=np.round(D, 3).tolist(), p50=d['p50'], real_blocks=len(d['blocks']))
    return {'delay_s': c}


def roundabout_decisions(f):
    """As report 05's Swiss analysis, on simulated tracks. See scripts/human_roundabout.py."""
    rows, follow = [], []
    for arm in range(4):
        ring_up, ring_on, lane = f'ring{(arm - 1) % 4}_0', f'ring{arm}_0', f'in{arm}_0'
        through = set(f[f.lane == ring_up].trip) & set(f[f.lane == ring_on].trip)
        up = f[f.lane == ring_up]
        passes = np.sort(up[up.trip.isin(through)].groupby('trip').time.max().values)
        ent = f[f.lane == lane]
        if ent.empty or len(passes) < 2:
            continue
        length = ent.pos.max()
        inside = f[f.lane.str.startswith(f':j{arm}_') & f.trip.isin(set(ent.trip))]
        if inside.empty:
            continue
        cross = inside[inside.pos >= inside.groupby('lane').pos.transform('max') - 3.0].groupby('trip').time.min()
        entries = []
        for trip, g in ent.groupby('trip'):
            near = g[length - g.pos < 2.0]
            if trip in cross.index and not near.empty:
                last3 = g[g.time >= cross[trip] - 3.0]
                entries.append((cross[trip], near.time.iloc[0], trip, last3.speed.min() if len(last3) else 99.0))
        entries.sort()
        tcs = np.array([e[0] for e in entries])
        for i, (tc, ta, trip, vmin) in enumerate(entries):
            k = np.searchsorted(passes, tc)
            if k >= len(passes):
                continue
            pv = passes[k - 1] if k > 0 else -1e9
            if not ((tcs > ta) & (tcs < tc)).any():
                btw = passes[(passes > ta) & (passes <= tc)]
                rej = ([btw[0] - ta] + list(np.diff(btw))) if len(btw) else []
                rows.append((passes[k] - max(pv, ta), max(rej) if rej else 0.0, tc - ta))
            if i and tc - tcs[i - 1] < 8.0 and not ((passes > tcs[i - 1]) & (passes < tc)).any() and vmin < 2.5:
                follow.append(tc - tcs[i - 1])
    return np.array(rows).reshape(-1, 3), np.array(follow)


def censored(rows):
    a = np.maximum(rows[:, 0], .1)
    r = rows[:, 1]

    def nll(p):
        mu, s = p
        s = abs(s) + 1e-3
        fa = norm.cdf((np.log(a) - mu) / s)
        fr = np.where(r > 0, norm.cdf((np.log(np.maximum(r, .1)) - mu) / s), 0.0)
        return -np.log(np.maximum(fa - fr, 1e-9)).sum()
    return float(np.exp(minimize(nll, [1.0, .3], method='Nelder-Mead').x[0]))


def jr(rows_by_seed, follow_by_seed):
    crit, fo = [], []
    for rows, f in zip(rows_by_seed, follow_by_seed):
        d = rows[(rows[:, 1] > 0) | (rows[:, 0] < 25)] if len(rows) else rows
        if len(d) >= 20:
            crit.append(censored(d))
        f = f[(f > .5) & (f < 10)] if len(f) else f
        if len(f) >= 5:
            fo.append(float(np.median(f)))
    out = {}
    a = score.band(crit, 2.31, 3.48, N=1.0) if crit else score.no_data('no decisions')
    a['D'] = [[abs(x - 2.895)] for x in crit]
    b = score.band(fo, 2.52, 3.15, N=1.0, thin=True) if fo else score.no_data('no follow-ups')
    b['D'] = [[abs(x - 2.835)] for x in fo]
    return {'critical_gap_s': a}, {'follow_up_s': b}


def jo3(drops):
    v = [x for x in drops if np.isfinite(x)]
    c = score.band(v, 0.0, .18) if v else score.no_data('never broke down in this run')
    c['D'] = [[abs(x - .09)] for x in v]
    return {'drop': c}


def capacity_drop(f, interval, steps):
    w = 300.0
    down = f[f.lane.str.startswith('down_') & (f.pos > 800)]
    c = down.groupby('trip').time.min().values
    t_end = float(f.time.max())
    counts = np.histogram(c, bins=np.arange(0, t_end + w, w))[0] / w * 3600
    s = f[f.lane.str.startswith('up_') & (f.pos > 1000)]
    speed = s.groupby((s.time // w).astype(int)).speed.mean()
    spd = np.array([speed.get(i, np.nan) for i in range(len(counts))])
    slow = np.where(spd < .6 * np.nanmax(spd))[0]
    if not len(slow) or slow[0] == 0:
        return np.nan
    br = int(slow[0])
    before = float(np.max(counts[max(br - 3, 0):br]))
    q = counts[br + 1:br + 7]
    return 1 - float(np.mean(q)) / before if len(q) and before else np.nan


def c3(rates, rates_dt1):
    cells = {}
    for name, v in (('dt_config', rates), ('dt_1s', rates_dt1)):
        v = [x for x in v if np.isfinite(x)]
        c = score.band(v, 1800, 2300, N=3600.0) if v else score.no_data('no queue discharge')
        c['D'] = [[abs(x - 2050)] for x in v]
        cells[name] = c
    return cells


def c4(waves):
    v = [x for x in waves if np.isfinite(x)]
    c = score.band(v, 12, 22, N=200.0) if v else score.no_data('no wave to measure')
    c['D'] = [[abs(x - 17)] for x in v]
    return {'wave_kmh': c}


def jo1(*a):
    return {'share': score.no_data('report 18 pending: real merge positions are not yet tagged')}
