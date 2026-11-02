"""Real against real. Every floor the benchmark uses comes from here, measured with the same metric code as the simulation."""
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

import network as net
import score

HERE = Path(__file__).resolve().parent
DATA = Path('/home/erikf/projects/personal/cars-data')
MQ = DATA / 'datasets/berlin-2019-detectors/mq_hr_2019_05.csv.gz'
DET = DATA / 'datasets/berlin-2019-detectors/det_val_hr_2019_05.csv.gz'
REG = DATA / 'datasets/reference-days/berlin/sites.csv'
CACHE = DATA / 'truth/trajectories/opus-20261031-cache'
TUNE_DAYS = ['07.05.2019', '14.05.2019', '15.05.2019', '16.05.2019', '21.05.2019', '22.05.2019', '23.05.2019', '28.05.2019']
BANDS = [(1, 5), (5, 10), (10, 15), (15, 25), (25, 40)]
P = np.linspace(.01, .99, 99)
MAX_BLOCKS = 12


def w1q(a, b):
    return float(np.abs(np.asarray(a) - np.asarray(b)).mean())


def site_split(site, cls):
    """sha256(site + "cars-bench-v1") per road class: 70% tuning, 30% locked."""
    h = int(hashlib.sha256((site + 'cars-bench-v1').encode()).hexdigest()[:8], 16) / 2 ** 32
    return 'tune' if h < .7 else 'locked'


class Berlin:
    """May 2019, 8 normal days. Hours may be missing; a site needs 80% of them."""

    def __init__(self, sites=None, split='tune', path=MQ):
        rows = {}
        with gzip.open(path, 'rt', errors='replace') as f:
            for x in csv.DictReader(f, delimiter=';'):
                if x['tag'] in TUNE_DAYS:
                    try:
                        rows[(x['mq_name'], x['tag'], int(x['stunde']))] = (float(x['q_kfz_mq_hr']), float(x['v_kfz_mq_hr']))
                    except ValueError:
                        pass
        all_sites = sorted({k[0] for k in rows})
        need = .8 * 24 * len(TUNE_DAYS)
        counts = {}
        for k in rows:
            counts[k[0]] = counts.get(k[0], 0) + 1
        reg = {x['site']: x for x in csv.DictReader(open(REG))}
        keep = [s for s in all_sites if counts[s] >= need and s in reg]
        if sites is not None:
            wanted = set(sites)
            keep = [s for s in keep if s in wanted]
        self.dropped = [s for s in (sites or all_sites) if s not in keep]
        Q = np.full((len(TUNE_DAYS), len(keep), 24), np.nan)
        V = Q.copy()
        for i, d in enumerate(TUNE_DAYS):
            for j, s in enumerate(keep):
                for h in range(24):
                    r = rows.get((s, d, h))
                    if r:
                        Q[i, j, h], V[i, j, h] = r
        V[V <= 0] = np.nan
        free = np.nanquantile(V, .9, axis=(0, 2))
        cls = np.array([2 if reg[s]['road_class'] == 'motorway' else 1 if f >= 50 else 0 for s, f in zip(keep, free)])
        if split:
            mask = np.array([site_split(s, c) == split for s, c in zip(keep, cls)])
            keep = [s for s, m in zip(keep, mask) if m]
            Q, V, cls = Q[:, mask], V[:, mask], cls[mask]
        self.sites, self.Q, self.V, self.cls = keep, Q, V, cls
        xy = [[float(reg[s]['lon']) * 67.6, float(reg[s]['lat']) * 111.2] for s in keep]
        self.panel = net.Panel(keep, cls, xy)
        self.days = TUNE_DAYS

    def real_pairs(self):
        out = {}
        for a, b in itertools.permutations(range(len(self.days)), 2):
            out[(a, b)] = net.metrics(self.Q[a], self.V[a], self.Q[b], self.V[b], self.panel)
        return out

    def floors(self):
        pairs = self.real_pairs()
        return {k: dict(F=score.floor_of([p[k] for p in pairs.values()]), p50=float(np.nanmedian([p[k] for p in pairs.values()]))) for k in net.KEYS}

    def nulls(self):
        """Class mean and network mean profiles built from the other days, as report 22 section 5. Where the
        class mean knows the answer by construction, the null knows less: for total and day shape a flat day 50% too high, for class speeds free flow all day."""
        D, S = self.Q.shape[:2]
        out = {k: [] for k in net.KEYS}
        for r in range(D):
            others = [i for i in range(D) if i != r]
            q = np.nanmean(self.Q[others], axis=0)
            v = np.nanmean(self.V[others], axis=0)
            nq, nv = q.copy(), v.copy()
            for c in np.unique(self.cls):
                nq[self.cls == c] = np.nanmean(q[self.cls == c], axis=0)
                nv[self.cls == c] = np.nanmean(v[self.cls == c], axis=0)
            m = net.metrics(nq, nv, self.Q[r], self.V[r], self.panel)
            flat = np.tile(np.nanmean(q, axis=1, keepdims=True) * 1.5, (1, 24))
            fm = net.metrics(flat, nv, self.Q[r], self.V[r], self.panel)
            free = net.free_speed(v)
            ff = net.metrics(nq, np.tile(free[:, None], (1, 24)), self.Q[r], self.V[r], self.panel)
            for k in net.KEYS:
                out[k].append(fm[k] if k in ('N1', 'N3', 'N4.am', 'N4.pm', 'N19.flow', 'N19.peak') else ff[k] if k[:3] in ('N10', 'N12', 'N19') else m[k])
        return {k: float(np.nanmedian(v)) for k, v in out.items()}


def corruptions(rng, cls):
    S = len(cls)

    def class_perm():
        p = np.arange(S)
        for k in np.unique(cls):
            i = np.where(cls == k)[0]
            p[i] = rng.permutation(i)
        return p

    def scale(f):
        return lambda q, v: (q * f, v)

    def shift(s):
        return lambda q, v: (np.roll(q, s, axis=1), np.roll(v, s, axis=1))

    def sites(q, v):
        p = class_perm()
        return q[p], v[p]

    def speeds(q, v):
        return q, v[class_perm()]

    def flat(q, v):
        q2 = q.copy()
        q2[:, 6:21] = np.nansum(q[:, 6:21], axis=1, keepdims=True) / 15
        return q2, v

    def nodip(q, v):
        return q, np.repeat(np.nanmedian(v[:, 6:21], axis=1, keepdims=True), 24, axis=1)

    def free(q, v):
        return q, np.repeat(np.nanquantile(v, .9, axis=1, keepdims=True), 24, axis=1)

    def capped(q, v):
        q2 = np.nan_to_num(q).copy()
        for s in range(q.shape[0]):
            cap, carry = .85 * np.nanmax(q[s]), 0.0
            for h in range(24):
                t = q2[s, h] + carry
                q2[s, h] = min(t, cap)
                carry = t - q2[s, h]
        return q2, v

    def late(q, v):
        J = net.jam(v, net.free_speed(v))
        v2 = v.copy()
        for s in range(q.shape[0]):
            for h in range(1, 24):
                if J[s, h - 1] and not J[s, h]:
                    v2[s, h] = v[s, h - 1]
        return q, v2

    def compensate(q, v):
        q2, mw = q.copy(), cls >= 1
        lost = .25 * np.nansum(q[mw])
        q2[mw] *= .75
        q2[~mw] *= 1 + lost / np.nansum(q[~mw])
        return q2, v

    return {
        'control: another real day': (lambda q, v: (q, v)),
        'flow x0.97': scale(.97), 'flow x0.95': scale(.95), 'flow x0.9': scale(.9), 'flow x0.8': scale(.8), 'flow x1.2': scale(1.2),
        'clock +1 h': shift(1), 'clock -1 h': shift(-1), 'flat demand 06-20': flat,
        'sites shuffled within class': sites, 'speeds shuffled within class': speeds, 'fast roads -25%, slow compensate': compensate,
        'peaks clipped 15%, spread later': capped, 'no rush-hour dip': nodip, 'free flow all day': free,
        'speed x0.9': (lambda q, v: (q, v * .9)), 'jams clear 1 h late': late,
    }


NETWORK_LEVEL = ('N1', 'N3', 'N4.am', 'N4.pm', 'N10.mean', 'N10.max', 'N12.am', 'N12.mid', 'N12.pm', 'N19.flow', 'N19.density', 'N19.peak')


def selftest(out=None):
    """Report 22 section 5: corruptions of real days, with no simulator. Returns (passed, table)."""
    B = Berlin(split="tune")
    fl = B.floors()
    rng = np.random.default_rng(20261102)
    rows, ok = [], True
    D = len(B.days)
    for name, fn in corruptions(rng, B.cls).items():
        runs = []
        for a in range(0, D, 2):
            b = (a + 1) % D
            q, v = fn(B.Q[a].copy(), B.V[a].copy())
            runs.append(net.metrics(q, v, B.Q[b], B.V[b], B.panel))
        med = {k: float(np.nanmedian([r[k] for r in runs])) for k in net.KEYS}
        over = [k for k in net.KEYS if med[k] > 1.25 * fl[k]['F'] + 1e-9 and fl[k]['F'] > 0]
        netw = [k for k in over if k in NETWORK_LEVEL]
        rows.append(dict(name=name, over=len(over), network=netw, fine=[k for k in over if k not in NETWORK_LEVEL]))
    sites = len(B.sites)
    by = {r['name']: r for r in rows}
    checks = {
        'control flags nothing': by['control: another real day']['over'] == 0,
        'shuffled sites: no network metric notices, finer ones do': len(by['sites shuffled within class']['network']) == 0 and by['sites shuffled within class']['over'] >= 5,
        'shuffled speeds: no network flow metric notices, jam metrics do': not [k for k in by['speeds shuffled within class']['network'] if k[:2] in ('N1', 'N3')] and by['speeds shuffled within class']['over'] >= 3,
        'every other corruption is caught, except late clearance and 3% flow, which hourly real noise hides': all(r['over'] > 0 for r in rows if r['name'] not in ('control: another real day', 'jams clear 1 h late', 'flow x0.97')),
    }
    falses = {}
    pairs = B.real_pairs()
    for i, d in enumerate(B.days):
        n = 0
        for k in net.KEYS:
            s = np.nanmedian([pairs[(i, b)][k] for b in range(D) if b != i])
            rest = [pairs[(a, b)][k] for (a, b) in pairs if i not in (a, b)]
            if s > 1.25 * np.nanmax(rest) + 1e-9:
                n += 1
        falses[d] = n
    checks['real day as control: at most 3 metrics over 1.25 x max on any day'] = max(falses.values()) <= 3
    res = dict(sites=sites, rows=rows, checks=checks, false_alarms=falses, floors={k: {a: round(b, 4) for a, b in v.items()} for k, v in fl.items()}, nulls={k: round(v, 4) for k, v in B.nulls().items()})
    if out:
        Path(out).write_text(json.dumps(res, indent=1))
    return all(checks.values()), res


def run_block(r, *_):
    return r['run']


def time_block(r, minutes=15):
    return r['run'].astype('i8') * 100000 + (r['t'].astype('i8') // (10 * 60 * minutes))


TRACKERS = {'I90stat': run_block, 'I90mov': run_block, 'I395': time_block, 'I294L1': run_block, 'HT': time_block}
EXCLUDE = {'I395': lambda lo: lo >= 15}


def tracker_series(v, t, seg, hz=10):
    """1 s speed differences on one sample stream: acceleration, jerk."""
    h = int(round(.5 * hz))
    a = np.full(v.shape, np.nan, 'f4')
    ok = (seg[2 * h:] == seg[:-2 * h]) & (t[2 * h:] - t[:-2 * h] == 2 * h)
    a[h:-h][ok] = (v[2 * h:] - v[:-2 * h])[ok]
    j = np.full(v.shape, np.nan, 'f4')
    ok2 = np.isfinite(a[2 * h:]) & np.isfinite(a[:-2 * h]) & (seg[2 * h:] == seg[:-2 * h])
    j[h:-h][ok2] = (a[2 * h:] - a[:-2 * h])[ok2]
    return a, j


def wave_stats(v, t, seg, block, lo=5.0, hi=15.0, hz=10):
    """Per block: median speed swing and period of tracks at least 60 s long that stay in the congested range."""
    out = {}
    order = np.argsort(seg, kind='stable')
    v2, t2, s2, b2 = v[order], t[order], seg[order], block[order]
    cuts = np.flatnonzero(np.diff(s2)) + 1
    amp, per = {}, {}
    for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(s2)]):
        if b - a < 60 * hz:
            continue
        x = v2[a:b]
        if not (lo <= np.median(x) <= hi):
            continue
        m, p = swing(x, 1 / hz)
        amp.setdefault(int(b2[a]), []).append(m)
        if np.isfinite(p):
            per.setdefault(int(b2[a]), []).append(p)
    for k in amp:
        if len(amp[k]) >= 8:
            out[k] = dict(amp=float(np.median(amp[k])), per=float(np.median(per.get(k, [np.nan]))), n=len(amp[k]))
    return out


def swing(x, dt):
    """Speed swing p90-p10 and period between upward mean crossings, on a track smoothed over 5 s."""
    k = max(1, int(round(5 / dt)))
    s = np.convolve(x, np.ones(k) / k, mode='valid')
    d = s - s.mean()
    up = np.flatnonzero((d[:-1] < 0) & (d[1:] >= 0))
    per = float(np.median(np.diff(up)) * dt) if len(up) >= 2 else np.nan
    return float(np.quantile(x, .9) - np.quantile(x, .1)), per


def micro(out):
    res = {}
    for site, blockfn in TRACKERS.items():
        d = np.load(CACHE / f'pairs_{site}.npz')
        seg = d['seg'].astype('i4')
        keep = seg % 4 == 0 if site == 'HT' else np.ones(seg.shape, bool)
        r = dict(seg=seg[keep])
        for k, ty in (('vf', 'f4'), ('cc', 'f4'), ('run', 'i4'), ('t', 'i4')):
            r[k] = d[k][keep].astype(ty)
        d.close()
        v, t, sg, cc = r['vf'], r['t'], r['seg'], r['cc']
        a, j = tracker_series(v, t, sg)
        T = np.clip((cc - 5) / np.maximum(v, .1), None, 10.0)
        T[(cc > 100) | (v < 1)] = np.nan
        block = blockfn(r)
        site_res = dict(bands={})
        for lo, hi in BANDS:
            if EXCLUDE.get(site, lambda _: False)(lo):
                continue
            m = (v >= lo) & (v < hi)
            if m.sum() < 20000:
                continue
            uniq, cnt = np.unique(block[m], return_counts=True)
            uniq = uniq[cnt >= 5000]
            if len(uniq) > MAX_BLOCKS:
                uniq = uniq[np.argsort(-cnt[cnt >= 5000])[:MAX_BLOCKS]]
            rows = []
            for b in uniq:
                mb = m & (block == b)
                rows.append(dict(a=np.nanquantile(a[mb], P).round(4).tolist(), j=np.nanquantile(j[mb], P).round(4).tolist(), T=np.nanquantile(T[mb], P).round(4).tolist()))
            if len(rows) < 2:
                continue
            band = dict(n=int(m.sum()), blocks=rows)
            for k in 'ajT':
                band['F_' + k] = score.floor_of([w1q(x[k], y[k]) for x, y in itertools.permutations(rows, 2)])
                band['p50_' + k] = float(np.median([w1q(x[k], y[k]) for x, y in itertools.permutations(rows, 2)]))
                band['N_' + k] = float(np.median([np.abs(np.asarray(x[k])).mean() if k != 'T' else w1q(x[k], np.full(99, np.median(x[k]))) for x in rows]))
            site_res['bands'][f'{lo}-{hi}'] = band
        if site != 'HT':
            ws = wave_stats(v, t, sg, block)
            if len(ws) >= 3:
                site_res['waves'] = dict(blocks=list(ws.values()))
        res[site] = site_res
        del a, j, T, block, r, v, t, sg, cc
    between = {}
    for s1, s2 in itertools.combinations(res, 2):
        for b in res[s1]['bands']:
            if b in res[s2]['bands']:
                for k in 'ajT':
                    x = np.mean([y[k] for y in res[s1]['bands'][b]['blocks']], axis=0)
                    y2 = np.mean([y[k] for y in res[s2]['bands'][b]['blocks']], axis=0)
                    between.setdefault(k, []).append(w1q(x, y2))
    res['_between'] = {k: dict(lo=float(min(v)), hi=float(max(v))) for k, v in between.items()}
    with gzip.open(out, 'wt') as f:
        json.dump(res, f)
    return res


def signal_queue():
    """Queue positions by signal group, with held-out group sid 7 left out, from DLR UT. Sunday, tuning data."""
    d = np.load(CACHE / 'ut_queue.npz')['R']
    n = 'sid pt tg pos h t_front start_delay start_lag L W truck turn v_cross dist'.split()
    ix = {k: i for i, k in enumerate(n)}
    keep = (d[:, ix['sid']] != 7) & (d[:, ix['truck']] == 0)
    d = d[keep]
    sid, pos, h, sd = d[:, ix['sid']], d[:, ix['pos']], d[:, ix['h']], d[:, ix['start_delay']]
    res = {}
    for p in range(1, 8):
        m = pos == p
        byg = [float(np.median(h[m & (sid == g)])) for g in np.unique(sid[m]) if (m & (sid == g)).sum() >= (30 if p <= 4 else 10)]
        res[f'pos{p}'] = dict(n=int(m.sum()), median=float(np.median(h[m])) if m.any() else None, lo=min(byg) if byg else None, hi=max(byg) if byg else None)
    m = pos == 1
    byg = [float(np.median(sd[m & (sid == g)])) for g in np.unique(sid[m]) if (m & (sid == g)).sum() >= 30]
    res['start_delay'] = dict(median=float(np.median(sd[m])), lo=min(byg), hi=max(byg))
    return res


def signal_delay():
    """Vehicle delay at DLR UT, per 15 minute block: time lost against 50 km/h, per track, seconds. Group sid 7 stays in here: tracks are not tagged by group."""
    d = np.load(CACHE / 'ut_veh.npz')
    vid, t, v = d['id'], d['t'], d['v'].astype('f8')
    order = np.lexsort((t, vid))
    vid, t, v = vid[order], t[order], v[order]
    cuts = np.flatnonzero(np.diff(vid)) + 1
    rows = []
    for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(vid)]):
        if b - a < 50:
            continue
        dt = np.diff(t[a:b], prepend=t[a])
        lost = float((np.maximum(1 - v[a:b] / 13.89, 0) * dt).sum())
        stops = int(((v[a:b][:-1] >= 1) & (v[a:b][1:] < 1)).sum())
        rows.append((t[a], lost, stops, t[b - 1] - t[a]))
    rows = np.array(rows)
    block = (rows[:, 0] // 900).astype(int)
    blocks = []
    for b in np.unique(block):
        m = block == b
        delayed = rows[m & (rows[:, 1] > 2), 1]
        if m.sum() >= 50 and len(delayed) >= 30:
            blocks.append(dict(q=np.quantile(delayed, P).round(3).tolist(), stops=float(rows[m, 2].mean()), n=int(m.sum())))
    pairs = [w1q(x['q'], y['q']) for x, y in itertools.permutations(blocks, 2)]
    return dict(blocks=blocks[:24], F=score.floor_of(pairs), p50=float(np.median(pairs)), N=float(np.median([np.abs(np.asarray(x['q'])).mean() for x in blocks])), stops_F=score.floor_of([abs(x['stops'] - y['stops']) for x, y in itertools.permutations(blocks, 2)]))


def junction(out):
    res = dict(queue=signal_queue(), delay=signal_delay())
    Path(out).write_text(json.dumps(res))
    return res


def heads(out, n=6, secs=240):
    """Real leaders' speed, 1 Hz, for the chain rig. The liveliest segments of I-90/94 that stay above a crawl."""
    d = np.load(CACHE / 'pairs_I90stat.npz')
    seg, vl, t = d['seg'], d['vl'].astype('f8'), d['t']
    cuts = np.flatnonzero(np.diff(seg)) + 1
    cand = []
    for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(seg)]):
        if b - a >= secs * 10:
            x = vl[a:a + secs * 10:10]
            if x.min() > 3 and 1.0 < x.std() < 3.5:
                cand.append((abs(x.std() - 1.87), x.round(2).tolist()))
    cand.sort(key=lambda c: c[0])
    Path(out).write_text(json.dumps([c[1] for c in cand[:n]]))
    return len(cand)


def signal_cycle():
    """DLR UT's own cycle and green, per signal id with a clear pattern, and flow per approach lane from the tracks."""
    d = np.load(CACHE / 'ut_tl.npz')
    t, sid, st = d['t'], d['id'], d['state']
    cycles, greens = [], []
    for i in np.unique(sid):
        m = sid == i
        x, s = t[m], st[m]
        change = np.flatnonzero(np.diff(s)) + 1
        green = s == 3
        on = x[change][green[change]]
        off = x[change][~green[change]]
        if len(on) > 10:
            p = np.diff(on)
            p = p[p > 20]
            if len(p):
                cycles.append(float(np.median(p)))
                ends = [off[off > o][0] - o for o in on if (off > o).any()]
                greens.append(float(np.median(ends)))
    return dict(cycle=float(np.median(cycles)), green=float(np.median(greens)), n=len(cycles), cycles=cycles[:12], greens=greens[:12])
