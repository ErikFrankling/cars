"""On-ramp, off-ramp, lane drop, zipper proxy and weaving targets from lane-labelled freeway tracks.
Uses the cached lane tables of the merging study (research/truth/scripts/merging). Lane labels are the source's, or that study's for A39.
Time gap uses centre spacing less 5 m, as report 05 does, because several trackers carry default lengths."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'research/truth/scripts/merging'))
import numpy as np
import pandas as pd
from common import OUT, Rows, q, spread_of
from mg_lib import Site

SRC = {'i-80': 'NGSIM I-80 https://data.transportation.gov/d/8ect-6jqj', 'us-101': 'NGSIM US-101 https://data.transportation.gov/d/8ect-6jqj',
       'I395': 'TGSIM I-395 https://data.transportation.gov/api/views/97n2-kuqi.json', 'ht': 'DLR Highway Traffic A39 https://zenodo.org/records/18540070',
       'I90mov': 'TGSIM I-90/94 moving https://data.transportation.gov/api/views/6a6e-vfvi.json'}
# site, label, type, source lanes, target lane
MERGES = [('i-80', 'i80_powell_onramp', 'on_ramp', (7,), 6), ('us-101', 'us101_ventura_onramp', 'on_ramp', (6,), 5), ('I395', 'i395_aux_lane_end', 'lane_drop', (-2,), -3),
          ('ht', 'a39_onramp_south', 'on_ramp', (-9,), -10), ('ht', 'a39_onramp_north', 'on_ramp', (10,), 11)]
DIVERGES = [('us-101', 'us101_cahuenga_offramp', (6,), 8), ('I395', 'i395_left_exit', (-5,), -6)]
WEAVE = [('us-101', 'us101_ventura_cahuenga_weave', (7, 6), 8, 5, 6)]
BLOCK = 300.
# A39's lanes are reconstructed, and the outer labels exist along the whole road at low counts. The real acceleration lanes are where they are dense.
GEOM = {'a39_onramp_north': (-84., 900.), 'a39_onramp_south': (5100., 6498.)}
CENSORED = {'a39_onramp_south': 'the lane runs past the end of the view, so positions are lower bounds on the lane length'}


def lane_runs(st):
    """Changes per car, with both sides held at least 1 s, so label flicker does not count."""
    out = []
    hz = st.hz
    for key, (a, b) in st.veh.items():
        l = st.LA[a:b]
        ch = np.flatnonzero(np.diff(l)) + 1
        if not len(ch):
            continue
        cut = np.r_[0, ch, len(l)]
        for i in range(1, len(cut) - 1):
            if cut[i] - cut[i - 1] >= hz and cut[i + 1] - cut[i] >= hz:
                out.append((key, a + cut[i], int(l[cut[i] - 1]), int(l[cut[i]])))
    return out


def gaps(st, i, new):
    r, t, sf, vid, v, L = int(st.R[i]), int(st.T[i]), float(st.S[i]), int(st.I[i]), float(st.V[i]), float(st.LL[i])
    F, Le = st.around(r, t, new, sf, vid)
    lag = (sf - F[1] - 5.) / max(F[3], .5) if F else np.nan
    lead = (Le[1] - sf - 5.) / max(v, .5) if Le else np.nan
    vt = np.nanmean([F[3] if F else np.nan, Le[3] if Le else np.nan]) if (F or Le) else np.nan
    return lag, lead, vt


def crossing(st, s0, lanes=None):
    """Who crosses s0, in which lane, at what time and speed."""
    out = []
    for key, (a, b) in st.veh.items():
        s = st.S[a:b]
        if s[0] < s0 <= s[-1]:
            k = int(np.argmax(s >= s0))
            out.append((int(st.R[a + k]), st.T[a + k] / st.hz, int(st.LA[a + k]), float(st.V[a + k]), key))
    return pd.DataFrame(out, columns=['run', 't', 'lane', 'v', 'key'])


def block_of(r, t):
    return r * 100000 + (t // BLOCK).astype(int)


def geom(st, lanes):
    m = np.isin(st.LA, lanes)
    return np.percentile(st.S[m], .5), np.percentile(st.S[m], 99.5)


def merges(rw, st, ev, site, label, jt, src, tgt):
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, jt, label, v, sp, SRC[site], 'tune', u, n, kind, **k)
    bid = {'on_ramp': 'JO', 'lane_drop': 'JL'}[jt]
    s0, s1 = GEOM.get(label) or geom(st, list(src))
    E = [(k, i) for k, i, o, n in ev if o in src and n == tgt and s0 - 5 <= st.S[i] <= s1 + 5]
    rec = []
    for key, i in E:
        lag, lead, vt = gaps(st, i, tgt)
        a, b = st.veh[key]
        ins = np.flatnonzero(np.isin(st.LA[a:i], src))
        vmin = st.V[a:i][ins].min() if len(ins) else np.nan
        # report 18: on I-80 and I-395 the lane label changes at an imaginary line, so the physical position is where the car centre comes within half a lane of the target lane's path
        e = min(i + 5 * st.hz, b)
        off = np.abs(st.LT[a:e] - st.centre(st.R[a], tgt, st.S[a:e]))
        hit = np.flatnonzero(off < 1.8)
        s_line = float(st.S[a + hit[0]]) if len(hit) else np.nan
        rec.append(dict(run=int(st.R[i]), t=st.T[i] / st.hz, s=float(st.S[i]), v=float(st.V[i]), lag=lag, lead=lead, vt=vt, vmin=vmin, wait=len(ins) / st.hz, s_line=s_line))
    R = pd.DataFrame(rec)
    if not len(R):
        print(label, 'no events', flush=True)
        return
    R['share'] = (R['s'] - s0) / (s1 - s0)
    R['share_line'] = (R['s_line'] - s0) / (s1 - s0)
    R['block'] = block_of(R['run'].values, R['t'].values)
    R.to_csv(OUT / f'merge_{label}.csv.gz', index=False)
    bs = R.groupby('block')['s'].size()
    nb = R['block'].nunique()
    note = f'lane runs {s0:.0f} to {s1:.0f} m in the source frame. ' + CENSORED.get(label, '')
    add('merge_events', len(R), None, 'count', len(R), 'none', bench_id=bid + '1', note=note)
    add('merge_position_share_p50', R['share'].median(), spread_of(R.groupby('block')['share'].median()), 'share of lane', len(R), 'block_to_block', lo=q(R['share'], 10), hi=q(R['share'], 90), bench_id=bid + '1', note='By lane label. lo and hi are p10 and p90 of cars. ' + note)
    lv = R['share_line'].dropna()
    if len(lv) > 10:
        add('merge_position_physical_share_p50', lv.median(), spread_of(R.groupby('block')['share_line'].median()), 'share of lane', len(lv), 'block_to_block', lo=q(lv, 10), hi=q(lv, 90), bench_id=bid + '1', note='car centre within 1.8 m of the target lane path. Use this one: report 18 shows the label is an artefact on I-80. Below 0 means already beside the target lane where the lane is first seen')
        add('merge_physical_last_third_share', (lv > 2 / 3).mean(), None, 'share', len(lv), 'none', bench_id='JZ1' if jt == 'lane_drop' else bid + '1')
    add('merge_last_third_share', (R['share'] > 2 / 3).mean(), spread_of((R['share'] > 2 / 3).groupby(R['block']).mean()), 'share', len(R), 'block_to_block', bench_id='JZ1' if jt == 'lane_drop' else bid + '1')
    add('merge_speed_median', R['v'].median(), spread_of(R.groupby('block')['v'].median()), 'm/s', len(R), 'block_to_block', lo=q(R['v'], 10), hi=q(R['v'], 90), bench_id=bid + '2')
    dv = R['v'] - R['vt']
    add('merge_speed_minus_target_lane_median', dv.median(), spread_of(dv.groupby(R['block']).median()), 'm/s', dv.notna().sum(), 'block_to_block', lo=q(dv, 10), hi=q(dv, 90), bench_id=bid + '2')
    for nm, x in (('new_follower', R['lag']), ('new_leader', R['lead'])):
        x = x.clip(-1, 30)
        add(f'accepted_time_gap_{nm}_p50', x.median(), spread_of(x.groupby(R['block']).median()), 's', x.notna().sum(), 'block_to_block', lo=q(x, 5), hi=q(x, 95), bench_id=bid + '2', note='spacing less 5 m over speed; lo and hi are p5 and p95')
    add('stopped_in_source_lane_share', (R['vmin'] < 1).mean(), spread_of((R['vmin'] < 1).groupby(R['block']).mean()), 'share', len(R), 'block_to_block', bench_id=bid + '2')
    add('time_in_source_lane_median', R['wait'].median(), None, 's', len(R), 'none', lo=q(R['wait'], 10), hi=q(R['wait'], 90), bench_id=bid + '2', note='censored where the lane starts inside the view')
    for reg, m in (('congested', R['vt'] < 10), ('free', R['vt'] >= 15)):
        g = R[m]
        if len(g) >= 15:
            add('merge_position_share_p50', g['share'].median(), None, 'share of lane', len(g), 'none', lo=q(g['share'], 10), hi=q(g['share'], 90), movement=reg, bench_id=bid + '1')
            add('accepted_time_gap_new_follower_p50', g['lag'].clip(-1, 30).median(), None, 's', len(g), 'none', lo=q(g['lag'].clip(-1, 30), 5), hi=q(g['lag'].clip(-1, 30), 95), movement=reg, bench_id=bid + '2')
    # flows just past the lane's end, and upstream of its start
    up, dn = crossing(st, max(s0 - 30, np.percentile(st.S, 2))), crossing(st, min(s1 + 40, np.percentile(st.S, 98)))
    t_span = {}
    for x, tag in ((up, 'upstream'), (dn, 'downstream')):
        if not len(x):
            continue
        x['block'] = block_of(x['run'].values, x['t'].values)
        main = x[~x['lane'].isin(list(src))]
        nl = main['lane'].nunique()
        counts = main.groupby('block').size()
        fl = counts * 3600 / BLOCK / max(nl, 1)
        full = fl.iloc[1:-1] if len(fl) > 3 else fl
        add('flow_per_lane', full.median(), spread_of(full), 'veh/h/lane', len(main), 'block_to_block', lo=full.min(), hi=full.max(), movement=tag, bench_id=bid + '3', note=f'{nl} lanes; 5 min blocks; hi is the largest block')
        add('speed_median', main['v'].median(), spread_of(main.groupby('block')['v'].median()), 'm/s', len(main), 'block_to_block', movement=tag, bench_id=bid + '3')
        sh = main.groupby('lane').size() / len(main)
        for l, v in sh.items():
            add('lane_use_share', v, spread_of((main['lane'] == l).groupby(main['block']).mean()), 'share', int((main['lane'] == l).sum()), 'block_to_block', movement=f'{tag}_lane{l}', bench_id=bid + '3')
    rf = R.groupby('block').size() * 3600 / BLOCK
    add('merging_flow', rf.median(), spread_of(rf), 'veh/h', len(R), 'block_to_block', lo=rf.min(), hi=rf.max(), bench_id=bid + '3')
    # zipper: order of cars passing the end of the lane in the target lane, joined or already there
    merged = {k: st.S[i] for k, i in E}
    z = crossing(st, s1 + 5)
    z = z[z['lane'] == tgt].sort_values(['run', 't'])
    if len(z) > 30:
        z['m'] = z['key'].isin(merged)
        for reg, g in (('congested', z[z['v'] < 8]), ('all', z)):
            if len(g) < 20 or g['m'].sum() < 8:
                continue
            same_run = (g['run'].values[1:] == g['run'].values[:-1]) & (np.diff(g['t'].values) < 15)
            alt = (g['m'].values[1:] != g['m'].values[:-1])[same_run]
            p = g['m'].mean()
            add('alternation_share', alt.mean(), None, 'share', same_run.sum(), 'none', lo=2 * p * (1 - p), movement=reg, bench_id='JZ1', note=f'consecutive cars past the lane end from different lanes. lo is what random order gives at merging share {p:.2f}. 1.0 is a perfect zipper')
    print(label, 'events', len(R), 'share p50 %.2f' % R['share'].median(), 'lag %.2f lead %.2f' % (R['lag'].median(), R['lead'].median()), 'vt %.1f' % R['vt'].median(), flush=True)


def diverges(rw, st, ev, site, label, src, tgt):
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, 'off_ramp', label, v, sp, SRC[site], 'tune', u, n, kind, **k)
    s0, s1 = geom(st, [tgt])
    rec = []
    for key, i, o, n in ev:
        if n != tgt:
            continue
        a, b = st.veh[key]
        rec.append(dict(run=int(st.R[i]), t=st.T[i] / st.hz, s=float(st.S[i]), v=float(st.V[i]), src=o, vexit=float(st.V[b - 1]), s_first=float(st.S[a]), l_first=int(st.LA[a])))
    R = pd.DataFrame(rec)
    if len(R) < 5:
        print(label, 'few', len(R), flush=True)
        return
    R['block'] = block_of(R['run'].values, R['t'].values)
    R['rel'] = R['s'] - s0
    add('diverge_events', len(R), None, 'count', len(R), 'none', bench_id='JF1', note=f'exit lane runs {s0:.0f} to {s1:.0f} m in the source frame')
    add('diverge_position_from_exit_lane_start_p50', R['rel'].median(), spread_of(R.groupby('block')['rel'].median()), 'm', len(R), 'block_to_block', lo=q(R['rel'], 10), hi=q(R['rel'], 90), bench_id='JF1', note='lo and hi are p10 and p90')
    add('diverge_speed_median', R['v'].median(), spread_of(R.groupby('block')['v'].median()), 'm/s', len(R), 'block_to_block', lo=q(R['v'], 10), hi=q(R['v'], 90), bench_id='JF2')
    add('exit_lane_end_speed_median', R['vexit'].median(), None, 'm/s', len(R), 'none', lo=q(R['vexit'], 10), hi=q(R['vexit'], 90), bench_id='JF2')
    fl = R.groupby('block').size() * 3600 / BLOCK
    add('exit_flow', fl.median(), spread_of(fl), 'veh/h', len(R), 'block_to_block', lo=fl.min(), hi=fl.max(), bench_id='JF3')
    for o, g in R.groupby('src'):
        add('diverge_source_lane_share', len(g) / len(R), None, 'share', len(g), 'none', movement=f'lane{o}', bench_id='JF1')
    print(label, 'events', len(R), 'rel p50 %.1f' % R['rel'].median(), 'v %.1f' % R['v'].median(), flush=True)


def weave(rw, st, ev, site, label, ons, off, main, aux):
    add = lambda m, v, sp, u, n, kind, **k: rw.add(m, 'weaving', label, v, sp, SRC[site], 'tune', u, n, kind, **k)
    s0, s1 = geom(st, [aux])
    mov = []
    for key, (a, b) in st.veh.items():
        l = st.LA[a:b]
        s = st.S[a:b]
        m = (s >= s0) & (s <= s1)
        if m.sum() < st.hz:
            continue
        first, last = int(l[0]), int(l[-1])
        src_ramp = first in ons
        to_ramp = last == off
        kind = 'ramp_to_ramp' if src_ramp and to_ramp else 'ramp_to_main' if src_ramp else 'main_to_ramp' if to_ramp else 'main_to_main'
        vm = float(np.median(st.V[a:b][m]))
        ch = np.flatnonzero(np.diff(l[m])) + 1
        mov.append(dict(key=key, kind=kind, v=vm, n_lc=len(ch), t=st.T[a] / st.hz, run=int(st.R[a]), dist=float(s[m][-1] - s[m][0])))
    M = pd.DataFrame(mov)
    M['block'] = block_of(M['run'].values, M['t'].values)
    tot = len(M)
    for k, g in M.groupby('kind'):
        add('movement_share', len(g) / tot, spread_of((M['kind'] == k).groupby(M['block']).mean()), 'share', len(g), 'block_to_block', movement=k, bench_id='JW1')
        f = g.groupby('block').size() * 3600 / BLOCK
        add('flow_by_movement', f.median(), spread_of(f), 'veh/h', len(g), 'block_to_block', movement=k, bench_id='JW1')
        add('speed_in_weave_median', g['v'].median(), spread_of(g.groupby('block')['v'].median()), 'm/s', len(g), 'block_to_block', lo=q(g['v'], 10), hi=q(g['v'], 90), movement=k, bench_id='JW2')
    weavers = M[M['kind'].isin(['ramp_to_main', 'main_to_ramp'])]
    add('weaving_volume_ratio', len(weavers) / tot, spread_of(M['kind'].isin(['ramp_to_main', 'main_to_ramp']).groupby(M['block']).mean()), 'share', tot, 'block_to_block', bench_id='JW1', note=f'weave {s1 - s0:.0f} m long')
    add('lane_changes_per_veh_km', M['n_lc'].sum() / (M['dist'].sum() / 1000), None, 'per veh-km', tot, 'none', bench_id='JW3', note='inside the weave, unfiltered lane-label changes')
    pos = [(st.S[i] - s0) / (s1 - s0) for k, i, o, n in ev if s0 <= st.S[i] <= s1 and (o == aux or n == aux)]
    add('lane_change_position_share_p50', np.median(pos), None, 'share of weave', len(pos), 'none', lo=q(pos, 10), hi=q(pos, 90), bench_id='JW3', note='changes in or out of the auxiliary lane')
    print(label, tot, M.groupby('kind').size().to_dict(), flush=True)


def main():
    rw = Rows('ramps')
    sites = {}
    for s in ('i-80', 'us-101', 'I395', 'ht'):
        print('load', s, flush=True)
        st = Site(s)
        ev = lane_runs(st)
        print(s, 'changes', len(ev), flush=True)
        for site, lab, jt, src, tgt in MERGES:
            if site == s:
                merges(rw, st, ev, s, lab, jt, src, tgt)
        for site, lab, src, tgt in DIVERGES:
            if site == s:
                diverges(rw, st, ev, s, lab, src, tgt)
        for site, lab, ons, off, mn, aux in WEAVE:
            if site == s:
                weave(rw, st, ev, s, lab, ons, off, mn, aux)
        del st
    rw.write()


if __name__ == '__main__':
    main()
