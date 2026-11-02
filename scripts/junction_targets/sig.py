"""Signal and generic junction targets from the per-vehicle table of jx.per_vehicle. One function for every source."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import q, spread_of


def flow_table(df, spans):
    """veh/h per block and movement. spans: block label to seconds observed."""
    n = df.groupby(['flight', 'arm', 'move']).size().rename('n').reset_index()
    n['q'] = n['n'] * 3600 / n['flight'].map(spans)
    return n


def block_spread(s, spans_index):
    v = s.reindex(spans_index).fillna(0.)
    return v.median(), spread_of(v)


def rows(rw, df, ds, site, jt, src, split, spans, ids, day_of=None, core=None):
    """ids maps a short key to a bench id. day_of maps a flight to a day, for day-to-day spread."""
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, jt, site, v, sp, src, split, u, n, kind, **k)
    spans = pd.Series(spans)
    blocks = spans.index
    d = df[df['arm'] >= 0].copy()
    total = d.groupby('flight').size() * 3600 / spans
    add('junction_flow_total', total.reindex(blocks).fillna(0).median(), spread_of(total.reindex(blocks).fillna(0)), 'veh/h', len(d), 'block_to_block', bench_id=ids['flow'])
    for m, g in d.groupby('move'):
        if m == 'unknown' or len(g) < 10:
            continue
        v = g.groupby('flight').size() * 3600 / spans
        add('flow_by_movement', *block_spread(v, blocks), 'veh/h', len(g), 'block_to_block', movement=m, bench_id=ids['flow'])
        st = g.groupby('flight')['stop'].mean()
        add('stop_share', g['stop'].mean(), spread_of(st), 'share', len(g), 'block_to_block', movement=m, bench_id=ids['stops'])
        ok = g[g['complete'] & g['up_full']]
        if len(ok) >= 15:
            free = ok['t_up'].quantile(.15)
            dl = ok['t_up'] - free
            add('approach_delay_mean', dl.mean(), spread_of(dl.groupby(ok['flight']).mean()), 's', len(ok), 'block_to_block', lo=q(dl, 50), hi=q(dl, 95), movement=m, bench_id=ids['delay'], note='last 50 to 60 m against the movement p15; lo and hi are p50 and p95 of cars')
        mv = g[g['vmin_core'] >= 1.5]
        if len(mv) >= 10:
            add('core_speed_median', mv['vmed_core'].median(), spread_of(mv.groupby('flight')['vmed_core'].median()), 'm/s', len(mv), 'block_to_block', lo=q(mv['vmed_core'], 10), hi=q(mv['vmed_core'], 90), movement=m, bench_id=ids['speed'], note=f'inside {core} m of the centre, cars that did not stop there; lo and hi are p10 and p90' if core else 'cars that did not stop there')
        un = g[~g['stop']]
        if len(un) >= 10:
            add('entry_speed_unstopped', un['vin'].median(), spread_of(un.groupby('flight')['vin'].median()), 'm/s', len(un), 'block_to_block', lo=q(un['vin'], 10), hi=q(un['vin'], 90), movement=m, bench_id=ids['speed'])
    for (arm, m), g in d.groupby(['arm', 'move']):
        if m == 'unknown' or len(g) < 20:
            continue
        v = g.groupby('flight').size() * 3600 / spans
        add('flow_by_arm_movement', *block_spread(v, blocks), 'veh/h', len(g), 'block_to_block', movement=f'arm{arm}_{m}', bench_id=ids['flow'])
    # lane use on approaches, from the stop positions
    lu = d[d['lane'] >= 0] if 'lane' in d else d.iloc[:0]
    if len(lu):
        sh = lu.groupby(['arm', 'lane']).size() / lu.groupby('arm').size()
        for (arm, lane), v in sh.items():
            nn = int((lu['arm'].eq(arm) & lu['lane'].eq(lane)).sum())
            if nn >= 20:
                add('lane_share_stopped', v, None, 'share', nn, 'none', movement=f'arm{arm}_lane{lane}', bench_id=ids['lane'], note='lanes clustered from stop positions, not a map')
    if ds is not None and len(ds):
        ok = ds[(ds['h'] > .8) & (ds['h'] < 8)]
        for p in (2, 3, 4):
            g = ok[ok['pos'] == p]
            if len(g) >= 10:
                add('queue_headway_by_position', g['h'].median(), spread_of(g.groupby('flight')['h'].median()) if g['flight'].nunique() > 2 else None, 's', len(g), 'block_to_block', lo=q(g['h'], 25), hi=q(g['h'], 75), movement=f'pos{p}', bench_id=ids['sat'], note='lo and hi are p25 and p75')
        sat = ok[ok['pos'] >= 5]
        if len(sat) >= 10:
            med = sat['h'].median()
            byarm = sat.groupby(['arm', 'lane'])['h'].agg(['median', 'size'])
            byarm = byarm[byarm['size'] >= 10]['median']
            add('saturation_headway', med, spread_of(sat.groupby('flight')['h'].median()) if sat['flight'].nunique() > 2 else None, 's', len(sat), 'block_to_block', lo=q(sat['h'], 25), hi=q(sat['h'], 75), bench_id=ids['sat'], note='positions 5 and up; lo and hi are p25 and p75')
            add('saturation_flow', 3600 / med, None, 'veh/h/lane', len(sat), 'none', lo=3600 / q(sat['h'], 75), hi=3600 / q(sat['h'], 25), bench_id=ids['sat'], note='3600 over the median headway')
            if len(byarm) > 1:
                add('saturation_headway_between_lanes', spread_of(byarm), None, 's', len(byarm), 'between_lanes', lo=byarm.min(), hi=byarm.max(), bench_id=ids['sat'])
        for m, g in ok[(ok['pos'] >= 4) & (ok['move'] == ok['prevmove'])].groupby('move'):
            if m != 'unknown' and len(g) >= 8:
                add('discharge_headway_pos4plus', g['h'].median(), None, 's', len(g), 'none', lo=q(g['h'], 25), hi=q(g['h'], 75), movement=m, bench_id=ids['sat'], note='leader and follower same movement; by turn')
    return d
