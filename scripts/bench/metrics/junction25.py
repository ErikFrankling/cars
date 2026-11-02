"""Level 2 against report 25: real targets by junction type, measured from simulated tracks by the code that measured the real ones.
Only rows with split=tune are in floors/junction_targets.csv: held-out sites have no numbers here, and nothing reads them."""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import score

HERE = Path(__file__).resolve().parents[1]
JT = HERE.parent / 'junction_targets'
OUT = Path(os.environ.setdefault('JT_OUT', tempfile.mkdtemp(prefix='bench-jt-')))
sys.path.insert(0, str(JT))
_T = None


def targets():
    global _T
    if _T is None:
        _T = pd.read_csv(HERE / 'floors/junction_targets.csv')
        if (_T.split != 'tune').any():
            raise SystemExit('held-out rows in the targets: refused')
    return _T


def band_of(metric, jt, movement='all'):
    """The range of the real sites, and whether it is thin: fewer than 3 sites, or a soft floor."""
    t = targets()
    types = jt if isinstance(jt, (list, tuple)) else [jt]
    x = t[t.metric.eq(metric) & t.junction_type.isin(types) & t.movement.fillna('all').eq(movement) & ~t.site.str.startswith('ALL_') & t.value.notna()]
    if not len(x):
        return None
    lo, hi = float(x.value.min()), float(x.value.max())
    thin = x.site.nunique() < 3
    if hi - lo < 1e-6 or hi - lo < .1 * abs(hi):
        pad = max(float(x.spread.fillna(0).max()), .1 * abs(hi))
        lo, hi = lo - pad, hi + pad
    return lo, hi, thin, x.site.nunique()


def cell(values, metric, jt, movement='all', null=None):
    b = band_of(metric, jt, movement)
    v = [float(x) for x in values if x is not None and np.isfinite(x)]
    if b is None:
        return score.no_data(f'no real row for {metric} / {movement}')
    if not v:
        c = score.judge([[np.nan]], (b[1] - b[0]) / 2)
        c.update(D=[[None]], lo=round(b[0], 3), hi=round(b[1], 3))
        return c
    lo, hi, thin, n = b
    c = score.band(v, lo, hi, N=null, thin=thin)
    c['D'] = [[abs(x - (lo + hi) / 2)] for x in v]
    c['note'] = (c.get('note', '') + f' real range over {n} site(s)').strip()
    return c


def table(rows_by_seed):
    """{(metric, movement): [value per seed]}"""
    out = {}
    for rows in rows_by_seed:
        for r in rows:
            if r['value'] != '':
                out.setdefault((r['metric'], r['movement']), []).append(float(r['value']))
    return out


def pick(tab, wanted, jt):
    """wanted: (metric, movement, null). Cells named by metric and movement."""
    cells = {}
    for m, mv, nul in wanted:
        name = m if mv == 'all' else f'{m}|{mv}'
        cells[name] = cell(tab.get((m, mv), []), m, jt, mv, nul)
    return cells


def roundabout_rows(tr, radius, seed, cx=0., cy=0.):
    """rb.py and rb_metrics.py on one run, cut into flights of 150 s so that their per-flight spreads exist."""
    import rb
    import rb_metrics
    from common import Rows
    site = f'sim{os.getpid()}_{seed}'
    Ry = radius + 3.
    d = [a for a in rb.polar(tr, cx, cy)]
    E = rb.mark(d, Ry)[0]
    if len(E) < 20:
        return []
    sgn, arms = rb.sense(E), rb.arm_angles(np.array([a['ang'] for a in E]))
    t0 = min(x[2][0] for x in tr)
    t1 = max(x[2][-1] for x in tr)
    rec, fu, flows = [], [], []
    for k, b in enumerate(np.arange(t0, t1, 150.)):
        cut = []
        for i, c, t, x, y, v in tr:
            m = (t >= b) & (t < b + 150)
            if m.sum() >= 8:
                cut.append((i, c, t[m], x[m], y[m], v[m]))
        r, f, fl, _ = rb.analyse(cut, cx, cy, Ry, arms, sgn, None, f'b{k}')
        rec += r
        fu += f
        flows.append(fl)
    pairs = []
    for i, fl in enumerate(flows):
        if not fl:
            continue
        g = fl['grid']
        for j in fl['Q']:
            for b0 in np.arange(g[0], g[-1] - 60, 60):
                m = (g >= b0) & (g < b0 + 60)
                pe, pc = fl['entries'][j], fl['passes'][j]
                pairs.append((i, j, (fl['Q'][j][m] > 0).mean(), ((pe >= b0) & (pe < b0 + 60)).sum(), ((pc >= b0) & (pc < b0 + 60)).sum(), fl['Q'][j][m].max()))
    pd.DataFrame(rec).to_csv(OUT / f'rb_{site}_entries.csv.gz', index=False)
    pd.DataFrame(fu, columns=['flight', 'arm', 'h', 'dw']).to_csv(OUT / f'rb_{site}_followup.csv.gz', index=False)
    pd.DataFrame(pairs, columns=['flight', 'arm', 'qshare', 'qe', 'qc', 'qmax']).to_csv(OUT / f'rb_{site}_minutes.csv.gz', index=False)
    rw = Rows(site)
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        rb_metrics.do(rw, site, 'roundabout_single', 'sim', 'sim')
    return rw.r


def roundabout_cells(rows_by_seed):
    tab = table(rows_by_seed)
    jt = 'roundabout_single'
    bins = sorted({m for (k, m) in tab if k == 'gap_acceptance_share'} | {m for m in targets()[targets().metric.eq('gap_acceptance_share') & targets().junction_type.eq(jt)].movement.unique()}) if rows_by_seed else []
    nullacc = 1.0
    jr1 = pick(tab, [('critical_gap_median', 'all', 0.0), ('critical_gap_those_who_rejected', 'all', 0.0), ('critical_gap_stopped_and_rejected', 'all', 0.0)] + [('gap_acceptance_share', m, nullacc) for m in bins if m in ('gap_2_3', 'gap_3_4', 'gap_4_5', 'gap_5_6', 'gap_6_8')], jt)
    return dict(JR1=jr1,
                JR2=pick(tab, [('follow_up_headway_median', 'all', 0.0)], jt),
                JR4=pick(tab, [('entry_speed_unstopped_median', 'all', 13.89), ('exit_speed_median', 'all', 13.89)], jt),
                JR5=pick(tab, [('stop_share', 'all', 0.0), ('entry_delay_mean', 'all', 0.0), ('queue_len_p95', 'all', 0.0)], jt),
                JR6=pick(tab, [('entered_ahead_under_2s_share', 'all', 1.0), ('entrant_rejected_a_gap_share', 'all', 0.0)], jt))


def junction_tables(tr, cx, cy, label, core=15.):
    import jx
    df, P = jx.per_vehicle(jx_tracks(tr), cx, cy, R=core, U=60., label=label)
    if not len(df):
        return df, None
    df = jx.lane_clusters(df)
    return df, jx.discharge(df)


def jx_tracks(tr):
    from .trackio import as_dicts
    return as_dicts(tr)


def signal_rows(tr, cx, cy, span, seed):
    import sig
    from common import Rows
    df, ds = junction_tables(tr, cx, cy, f's{seed}')
    if not len(df):
        return []
    rw = Rows(f'sig{seed}')
    sig.rows(rw, df, ds, 'sim', 'signal', 'sim', 'sim', {f's{seed}': span}, dict(flow='JS7', stops='JS7', delay='JS7', speed='JS9', core='JS9', entry='JS9', lane='JS10', pos='JS1', sat='JS2', q='JS1', queue='JS1', qhead='JS1', head='JS1'))
    return rw.r


def signal_cells(rows_by_seed):
    tab = table(rows_by_seed)
    jt = 'signal'
    moves = ('through', 'left', 'right')
    return dict(JS1b=pick(tab, [('queue_headway_by_position', f'pos{p}', 2.2 if p > 2 else 2.2) for p in (2, 3, 4)], jt),
                JS2b=pick(tab, [('saturation_headway', 'all', 1.0), ('saturation_flow', 'all', 3600.)], jt),
                JS7b=pick(tab, [('stop_share', m, 0.0) for m in moves] + [('approach_delay_mean', m, 0.0) for m in moves], jt),
                JS9=pick(tab, [('core_speed_median', m, 13.89) for m in moves] + [('entry_speed_unstopped', m, 13.89) for m in moves], jt))


def priority_rows(tr, seed, lines):
    """Same events as the real sites, measured at each minor arm's line. lines: (x, y, heading)."""
    import priority as pr
    from common import Rows
    d = jx_tracks(tr)
    recs, fus = [], []
    for k, (x, y, hd) in enumerate(lines):
        r, fu, _ = pr.events(d, x, y, hd, f's{seed}a{k}')
        recs += r
        fus += fu
    if not recs:
        return []
    span = max(a['t'][-1] for a in d) - min(a['t'][0] for a in d)
    rw = Rows(f'pr{seed}')
    F = pd.DataFrame(fus) if fus else pd.DataFrame(columns=['flight', 'h'])
    pr.rows(rw, pd.DataFrame(recs), F, 'sim', 'priority_stop', 'sim', 'sim', {f's{seed}a{k}': span for k in range(len(lines))})
    return rw.r


def priority_cells(rows_by_seed, jt):
    tab = table(rows_by_seed)
    cells = dict(JP1=pick(tab, [('critical_gap_median', 'all', 0.0)] + [('gap_acceptance_share', m, 1.0) for m in ('gap_2_3', 'gap_3_4', 'gap_4_5', 'gap_5_6', 'gap_6_8')], jt),
                 JP2=pick(tab, [('follow_up_headway_median', 'all', 0.0)], jt))
    if jt == 'priority_stop':
        cells['JP4'] = pick(tab, [('full_stop_share', 'all', 1.0), ('rolling_share', 'all', 0.0), ('no_slowdown_share', 'all', 0.0)], jt)
    return cells


def merges(f, lane_from, lane_to, length, interval, X):
    """Report 25's merge facts on a simulated lane: where (share of the lane), speed, gaps to new follower and leader, stopping."""
    ev = X.halfway(f)
    ev = X.lane_changes(f, interval) if ev is None else ev
    ev = ev[ev.lane == lane_to]
    src = set(f[f.lane == lane_from].trip)
    ev = ev[ev.trip.isin(src)]
    if len(ev) < 5:
        return dict(n=len(ev))
    g = X.gaps_at_change(f, ev)
    stopped = f[(f.lane == lane_from)].groupby('trip').speed.min() < 1.0
    return dict(n=len(ev), share=float((ev.pos / length).median()), last_third=float((ev.pos / length > 2 / 3).mean()), v=float(ev.speed.median()), lag=float(g.lag.median()), lead=float(g.lead.median()), stopped=float(stopped.mean()))


def merge_cells(st, jt, regime='congested'):
    jts = [jt]
    one = lambda k: [s[k] for s in st if k in s]
    wanted = [('merge_position_physical_share_p50', 'share', 0.0), ('merge_physical_last_third_share', 'last_third', 0.0), ('merge_speed_median', 'v', 0.0), ('accepted_time_gap_new_follower_p50', 'lag', 0.0), ('accepted_time_gap_new_leader_p50', 'lead', 0.0), ('stopped_in_source_lane_share', 'stopped', 1.0)]
    cells = {}
    for m, k, nul in wanted:
        c = cell(one(k), m, jts, 'all', nul)
        cells[m] = c
    return cells


def alternation(f, up_lanes, down_prefix, interval):
    """Order past the merge: share of consecutive cars that came from different lanes. Random is about 0.5."""
    d = f[f.lane.str.startswith(down_prefix)]
    first = d.groupby('trip').time.min().sort_values()
    last_lane = f[f.lane.isin(up_lanes)].sort_values('time').groupby('trip').lane.first()
    seq = [last_lane.get(t) for t in first.index if t in last_lane.index]
    if len(seq) < 30:
        return np.nan
    a = np.array(seq)
    return float((a[1:] != a[:-1]).mean())
