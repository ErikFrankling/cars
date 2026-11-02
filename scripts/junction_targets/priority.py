"""Give-way and stop-controlled junctions: critical gap, follow-up, minor delay against major flow, compliance.
python3 -I priority.py   reads the list in priority_sites.json (written after the scan) and the pNEUMA and Peachtree tracks."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, Rows, gap_mle, raff, boot_gap, q, spread_of, gap_rows
import jx


def minor_heading(tr, x, y):
    """The approach that slows: heading of cars that drop below 3 m/s within 8 m of the node."""
    H, P = [], []
    for a in tr:
        d = np.hypot(a['x'] - x, a['y'] - y)
        k = int(d.argmin())
        if d[k] > 8 or k < 3 or k > len(d) - 3:
            continue
        s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
        u = max(jx.index_arc(s, s[k] - 15), 0)
        w = min(jx.index_arc(s, s[k] + 6), len(s) - 1)
        if u >= w:
            continue
        j = u + int(a['v'][u:w + 1].argmin())
        if a['v'][j] < 3:
            H.append(jx.heading(a['x'], a['y'], u, max(j, u + 1)))
            P.append((a['x'][j], a['y'][j]))
    if len(H) < 5:
        return None
    z = np.exp(1j * np.array(H))
    hd = np.angle(z.mean())
    keep = np.abs(jx.wrap(np.array(H) - hd)) < .7
    P = np.array(P)[keep]
    return float(hd), float(np.median(P[:, 0])), float(np.median(P[:, 1])), int(keep.sum())


def minor_tracks(tr, lx, ly, hd):
    out = []
    for a in tr:
        d = np.hypot(a['x'] - lx, a['y'] - ly)
        k = int(d.argmin())
        if d[k] > 5 or k < 3 or k > len(d) - 3:
            continue
        s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
        u = max(jx.index_arc(s, s[k] - 10), 0)
        if u >= k or abs(jx.wrap(jx.heading(a['x'], a['y'], u, k) - hd)) > .6:
            continue
        out.append(a)
    return out


def events(tr, lx, ly, hd, flight, near=1.6, up=8., forward=25., t_lim=45.):
    M = minor_tracks(tr, lx, ly, hd)
    if not M:
        return [], [], 0
    ids = {a['id'] for a in M}
    K = []
    for a in M:
        K.append(int(np.hypot(a['x'] - lx, a['y'] - ly).argmin()))
    order = np.argsort([a['t'][k] for a, k in zip(M, K)])
    M = [M[i] for i in order]
    K = [K[i] for i in order]
    tcs = np.array([a['t'][k] for a, k in zip(M, K)])
    res, fu = [], []
    others = [b for b in tr if b['id'] not in ids and np.hypot(b['x'] - lx, b['y'] - ly).min() < forward + 10]
    for n, (a, k) in enumerate(zip(M, K)):
        s = np.r_[0, np.cumsum(np.hypot(np.diff(a['x']), np.diff(a['y'])))]
        if s[k] < up:
            continue
        ka = max(jx.index_arc(s, s[k] - up), 0)
        ke = min(jx.index_arc(s, s[k] + forward), len(s) - 1)
        if ke - k < 5:
            continue
        ta, tc = a['t'][ka], a['t'][k]
        fx, fy, ft = a['x'][k:ke + 1], a['y'][k:ke + 1], a['t'][k:ke + 1]
        ps = []
        for b in others:
            if b['t'][-1] < ta - 2 or b['t'][0] > tc + t_lim:
                continue
            m = (b['t'] >= ta - 2) & (b['t'] <= tc + t_lim)
            if m.sum() < 3:
                continue
            bx, by, bt, bv = b['x'][m], b['y'][m], b['t'][m], b['v'][m]
            dd = np.hypot(fx[:, None] - bx[None, :], fy[:, None] - by[None, :])
            hit = np.argwhere(dd < near)
            if not len(hit):
                continue
            i0 = hit[:, 0].min()
            j0 = hit[hit[:, 0] == i0][0, 1]
            if bv[j0] < 1.:
                continue
            ps.append(bt[j0] - (ft[i0] - tc))
        ps = np.sort(ps) if ps else np.zeros(0)
        first = not np.any((tcs > ta) & (tcs < tc))
        nx, pv = ps[ps > tc], ps[ps <= tc]
        acc = rmax = np.nan
        nrej = 0
        if len(nx):
            acc = nx[0] - max(pv[-1] if len(pv) else -1e9, ta)
            btw = ps[(ps > ta) & (ps <= tc)]
            rej = ([btw[0] - ta] + list(np.diff(btw))) if len(btw) else []
            nrej = len(rej)
            rmax = max(rej) if rej else 0.
        u15 = max(jx.index_arc(s, s[k] - 12), 0)
        vs = a['v'][u15:k + 2]
        hout = jx.heading(a['x'], a['y'], k, min(jx.index_arc(s, s[k] + 15), len(s) - 1))
        hin = jx.heading(a['x'], a['y'], u15, k)
        u40 = jx.index_arc(s, s[k] - 40)
        res.append(dict(flight=flight, id=a['id'], tc=tc, ta=ta, first=first, acc=acc, rmax=rmax, nrej=nrej, pet=(nx[0] - tc) if len(nx) else np.nan, vmin=float(vs.min()), vline=float(a['v'][k]), turn=float(jx.wrap(hout - hin)),
                        t40=float(tc - a['t'][u40]) if s[k] >= 40 else np.nan, npass_60=int(((ps > tc - 30) & (ps < tc + 30)).sum())))
        if n and tc - tcs[n - 1] < 8 and not np.any((ps > tcs[n - 1]) & (ps < tc)) and a['v'][max(k - 15, 0):k].min() < 2.5:
            fu.append(dict(flight=flight, h=float(tc - tcs[n - 1])))
    return res, fu, len(M)


def rows(rw, R, F, site, jt, src, split, spans, day=None):
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, jt, site, v, sp, src, split, u, n, kind, **k)
    if not len(R):
        return
    gap_rows(add, R[R['first']].assign(stopped=lambda d: d['vmin'] < 1), 'JP1')
    dec = R[R['first'] & R['acc'].notna() & ((R['nrej'] > 0) | (R['acc'] < 25))]
    nr = int((dec['nrej'] > 0).sum())
    if len(dec) >= 25 and nr >= 8:
        tc, sd = gap_mle(dec['acc'].values, dec['rmax'].values)
        lo, hi = boot_gap(dec['acc'].values, dec['rmax'].values, pd.factorize(dec['flight'])[0], n=25)
        per = [gap_mle(d['acc'].values, d['rmax'].values)[0] for _, d in dec.groupby('flight') if (d['nrej'] > 0).sum() >= 8]
        add('critical_gap_median', tc, spread_of(per) if len(per) > 2 else None, 's', len(dec), 'session_to_session', lo=lo, hi=hi, bench_id='JP1', note=f'censored lognormal; rejected in {nr}; log-SD {sd:.2f}')
        rj = dec[dec['nrej'] > 0]
        add('critical_gap_raff', raff(dec['acc'].values, rj['rmax'].values), None, 's', len(dec), 'none', bench_id='JP1', note='cross-check')
        for nm, m in (('right', dec['turn'] < -.6), ('through', dec['turn'].abs() <= .6), ('left', dec['turn'] > .6)):
            g = dec[m]
            if len(g) >= 25 and (g['nrej'] > 0).sum() >= 8:
                add('critical_gap_median', gap_mle(g['acc'].values, g['rmax'].values)[0], None, 's', len(g), 'none', movement=nm, bench_id='JP1')
    if len(F) >= 5:
        add('follow_up_headway_median', F['h'].median(), spread_of(F.groupby('flight')['h'].median()) if F['flight'].nunique() > 2 else None, 's', len(F), 'session_to_session', lo=q(F['h'], 25), hi=q(F['h'], 75), bench_id='JP2')
    tot = pd.Series(spans)
    fl = R.groupby('flight').size().reindex(tot.index).fillna(0) * 3600 / tot
    add('minor_flow', fl.median(), spread_of(fl), 'veh/h', len(R), 'session_to_session', bench_id='JP3')
    R = R.copy()
    R['mv'] = np.where(R['turn'] < -.6, 'right', np.where(R['turn'] > .6, 'left', 'through'))
    for m, g in R.groupby('mv'):
        f = g.groupby('flight').size().reindex(tot.index).fillna(0) * 3600 / tot
        add('minor_flow_by_movement', f.median(), spread_of(f), 'veh/h', len(g), 'session_to_session', movement=m, bench_id='JP3')
    pf = R['npass_60'] * 60
    add('major_flow_seen_by_minor', pf.median(), spread_of(R.groupby('flight')['npass_60'].median() * 60), 'veh/h', len(R), 'session_to_session', bench_id='JP3', note='conflicting cars per hour, within 30 s either side of each minor car')
    add('full_stop_share', (R['vmin'] < 1).mean(), spread_of((R['vmin'] < 1).groupby(R['flight']).mean()), 'share', len(R), 'session_to_session', bench_id='JP4')
    add('rolling_share', ((R['vmin'] >= 1) & (R['vmin'] < 3)).mean(), None, 'share', len(R), 'none', bench_id='JP4')
    add('no_slowdown_share', (R['vmin'] >= 3).mean(), None, 'share', len(R), 'none', bench_id='JP4')
    add('speed_at_line_median', R['vline'].median(), spread_of(R.groupby('flight')['vline'].median()), 'm/s', len(R), 'session_to_session', lo=q(R['vline'], 10), hi=q(R['vline'], 90), bench_id='JP4')
    t = R['t40'].dropna()
    if len(t) >= 15:
        free = t.quantile(.15)
        dl = t - free
        add('minor_delay_mean', dl.mean(), spread_of(dl.groupby(R.loc[t.index, 'flight']).mean()), 's', len(t), 'session_to_session', lo=q(dl, 50), hi=q(dl, 95), bench_id='JP3', note='last 40 m to the line against the site p15')
        for a, b in ((0, 300), (300, 600), (600, 900), (900, 1500), (1500, 3000)):
            m = (pf.loc[t.index] >= a) & (pf.loc[t.index] < b)
            if m.sum() >= 12:
                add('minor_delay_by_major_flow', dl[m].mean(), None, 's', int(m.sum()), 'none', movement=f'major_{a}_{b}', bench_id='JP3')
    pet = R['pet'].dropna()
    if len(pet):
        add('pet_after_minor_entry_p5', q(pet, 5), None, 's', len(pet), 'none', hi=q(pet, 50), bench_id='JP5', note='entry to next major car at the meeting point; hi is the median')
        add('entered_ahead_under_2s_share', (pet < 2).mean(), spread_of((R['pet'] < 2).groupby(R['flight']).mean()), 'share', len(pet), 'session_to_session', bench_id='JP5', note='a major car had to arrive within 2 s: forced or tight entries')
    add('rejected_a_gap_share', (R['nrej'] > 0).mean(), None, 'share', len(R), 'none', bench_id='JP5')
