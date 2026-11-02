"""Turns cached roundabout events into targets. python3 -I rb_metrics.py NAME site:type:source:split ..."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, gap_mle, raff, boot_gap, q, spread_of, Rows, gap_rows


def turn(s):
    """Sweep angle in the ring: first exit is a right turn, about half way is straight on."""
    if not np.isfinite(s):
        return 'unknown'
    return 'right' if s < 1.9 else 'through' if s < 3.7 else 'left' if s < 5.6 else 'uturn'


def fit_capacity(P):
    """Saturated minutes only. Poisson fit of entry flow on circulating flow, so a zero minute does not break it."""
    s = P[P['qshare'] >= .8]
    if len(s) < 20:
        return None
    x = s['qc'].values * 60.
    y = s['qe'].values * 60.
    b = np.array([np.log(max(y.mean(), 1)), 0.])
    X = np.c_[np.ones(len(x)), x]
    for _ in range(30):
        mu = np.exp(X @ b)
        b = b + np.linalg.solve((X * mu[:, None]).T @ X, X.T @ (y - mu))
    return float(np.exp(b[0])), float(-b[1]), len(s)


def block(fl, n=5):
    u = {f: i // n for i, f in enumerate(pd.unique(fl))}
    return fl.map(u).values


def do(rw, site, jt, src, split, label=None):
    label = label or site
    R = pd.read_csv(OUT / f'rb_{site}_entries.csv.gz')
    F = pd.read_csv(OUT / f'rb_{site}_followup.csv.gz')
    P = pd.read_csv(OUT / f'rb_{site}_minutes.csv.gz')
    hours = R.groupby('flight')['tc'].agg(lambda s: s.max() - s.min()).sum() / 3600
    add = lambda *a, **k: rw.add(a[0], jt, label, a[1], a[2], src, split, *a[3:], **k)
    dec = R[R['first'] & R['acc'].notna() & ((R['nrej'] > 0) | (R['acc'] < 25))]
    tc, sd = gap_mle(dec['acc'].values, dec['rmax'].values)
    g = pd.factorize(dec['flight'])[0]
    lo, hi = boot_gap(dec['acc'].values, dec['rmax'].values, g, n=30)
    blk = block(dec['flight'])
    per = [gap_mle(d['acc'].values, d['rmax'].values)[0] for _, d in dec.groupby(blk) if (d['nrej'] > 0).sum() >= 15]
    add('critical_gap_median', tc, spread_of(per) if len(per) > 2 else None, 's', len(dec), 'block_of_5_flights', lo=lo, hi=hi, bench_id='JR1', note=f'All first-in-line cars, approach zone 6 m. Depends on the instrument, see report 25. Censored lognormal, CI cluster bootstrap by flight; rejected in {int((dec.nrej > 0).sum())}; log-SD {sd:.2f}')
    add('critical_gap_logsd', sd, None, 'log s', len(dec), 'none', bench_id='JR1')
    gap_rows(add, R[R['first']].assign(stopped=lambda d: d['stop']), 'JR1')
    rj = dec[dec['nrej'] > 0]
    add('critical_gap_raff', raff(dec['acc'].values, rj['rmax'].values) if len(rj) else None, None, 's', len(dec), 'none', bench_id='JR1', note='cross-check')
    arm_tc = []
    for a, d in dec.groupby('arm'):
        if (d['nrej'] > 0).sum() >= 30:
            v = gap_mle(d['acc'].values, d['rmax'].values)[0]
            arm_tc.append(v)
            add('critical_gap_median', v, None, 's', len(d), 'none', movement=f'arm{a}', bench_id='JR1')
    if len(arm_tc) > 1:
        add('critical_gap_arm_spread', spread_of(arm_tc), None, 's', len(arm_tc), 'between_arms', bench_id='JR1')
    F2 = F[F['dw'] < 2.]
    if len(F2):
        fb = F2.groupby(block(F2['flight']))['h'].median()
        add('follow_up_headway_median', F2['h'].median(), spread_of(fb) if len(fb) > 2 else None, 's', len(F2), 'block_of_5_flights', lo=q(F2['h'], 25), hi=q(F2['h'], 75), bench_id='JR2', note='same entry lane, no ring car between, follower queued; lo and hi are p25 and p75')
    fh = R.groupby('flight').apply(lambda d: pd.Series(dict(n=len(d), T=d['tc'].max() - d['tc'].min())), include_groups=False)
    fl = 3600 * fh['n'] / fh['T'].clip(lower=60)
    add('entry_flow_total', fl.median(), spread_of(fl), 'veh/h', len(R), 'flight_to_flight', bench_id='JR3')
    for a, d in R.groupby('arm'):
        f = 3600 * d.groupby('flight').size() / fh['T'].clip(lower=60)
        add('entry_flow', f.median(), spread_of(f.fillna(0)), 'veh/h', len(d), 'flight_to_flight', movement=f'arm{a}', bench_id='JR3')
    R['turn'] = R['sweep'].map(turn)
    for m, d in R.groupby('turn'):
        if m == 'unknown':
            continue
        f = 3600 * d.groupby('flight').size() / fh['T'].clip(lower=60)
        add('flow_by_movement', f.median(), spread_of(f.fillna(0)), 'veh/h', len(d), 'flight_to_flight', movement=m, bench_id='JR3')
        add('ring_speed_median', d['vring'].median(), spread_of(d.groupby('flight')['vring'].median()), 'm/s', len(d), 'flight_to_flight', lo=q(d['vring'], 10), hi=q(d['vring'], 90), movement=m, bench_id='JR4', note='lo and hi are p10 and p90 of cars')
    ok = R[~R['stop']]
    add('entry_speed_unstopped_median', ok['vin'].median(), spread_of(ok.groupby('flight')['vin'].median()), 'm/s', len(ok), 'flight_to_flight', lo=q(ok['vin'], 10), hi=q(ok['vin'], 90), bench_id='JR4')
    add('exit_speed_median', R['vout'].median(), spread_of(R.groupby('flight')['vout'].median()), 'm/s', R['vout'].notna().sum(), 'flight_to_flight', lo=q(R['vout'], 10), hi=q(R['vout'], 90), bench_id='JR4', note='5 samples, about 1 s, past the yield radius')
    st = R.groupby('flight')['stop'].mean()
    add('stop_share', R['stop'].mean(), spread_of(st), 'share', len(R), 'flight_to_flight', bench_id='JR5', note='entering cars below 1 m/s before the line')
    trav = R['trav'].dropna()
    if len(trav) > 30:
        free = {a: d['trav'].quantile(.15) for a, d in R.groupby('arm')}
        dl = R['trav'] - R['arm'].map(free)
        add('entry_delay_mean', dl.mean(), spread_of(dl.groupby(R['flight']).mean()), 's', dl.notna().sum(), 'flight_to_flight', lo=q(dl, 50), hi=q(dl, 95), bench_id='JR5', note='last 25 m before the yield radius against the arm p15; lo and hi are p50 and p95 of cars')
    add('queue_len_p95', P['qmax'].quantile(.95), None, 'veh', len(P), 'none', hi=P['qmax'].max(), bench_id='JR5', note='largest count of stopped cars per arm-minute; hi is the maximum seen')
    add('saturated_arm_minutes_share', (P['qshare'] >= .8).mean(), None, 'share', len(P), 'none', bench_id='JR3', note='a queue at least 80% of the minute')
    c = fit_capacity(P)
    if c:
        add('capacity_at_zero_circulating', c[0], None, 'veh/h', c[2], 'none', bench_id='JR3', note=f'saturated minutes only; exp fit with B={c[1]:.5f} per veh/h')
        add('capacity_slope_B', c[1], None, 'per veh/h', c[2], 'none', bench_id='JR3')
        s = P[P['qshare'] >= .8]
        for lo_, hi_ in ((0, 300), (300, 600), (600, 900), (900, 1300)):
            d = s[(s['qc'] * 60 >= lo_) & (s['qc'] * 60 < hi_)]
            if len(d) >= 8:
                add('entry_capacity_observed', d['qe'].mean() * 60, d['qe'].std() * 60 / np.sqrt(len(d)), 'veh/h', len(d), 'standard_error', movement=f'circ_{lo_}_{hi_}', bench_id='JR3')
    pet = R['pet'].dropna()
    add('pet_after_entry_p5', q(pet, 5), None, 's', len(pet), 'none', hi=q(pet, 50), bench_id='JR6', note='entry to next ring car at that angle; hi is the median')
    add('entered_ahead_under_2s_share', (pet < 2).mean(), spread_of((R['pet'] < 2).groupby(R['flight']).mean()), 'share', len(pet), 'flight_to_flight', bench_id='JR6')
    add('entrant_rejected_a_gap_share', (R['nrej'] > 0).mean(), spread_of((R['nrej'] > 0).groupby(R['flight']).mean()), 'share', len(R), 'flight_to_flight', bench_id='JR6')
    w = R['rring'].dropna()
    add('ring_radial_p10_p90', q(w, 90) - q(w, 10), None, 'm', len(w), 'none', lo=q(w, 10), hi=q(w, 90), bench_id='JR7', note='width of used ring; over about 5 m means two lanes used')
    print(label, 'hours %.1f' % hours, 'tc %.2f (%.2f-%.2f) fu %.2f n=%d fuN=%d sat %.3f stop %.2f' % (tc, lo, hi, F2['h'].median() if len(F2) else -1, len(dec), len(F2), (P['qshare'] >= .8).mean(), R['stop'].mean()), 'cap', c, flush=True)


if __name__ == '__main__':
    rw = Rows(sys.argv[1])
    for a in sys.argv[2:]:
        site, jt, rest = a.split(':', 2)
        src, split = rest.rsplit(':', 1)
        do(rw, site, jt, src, split)
    rw.write()
