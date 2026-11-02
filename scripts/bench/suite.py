"""One configuration, every scene, one scorecard."""
import gzip
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

import network as net_
import runner
import score
from metrics import extract as X
from metrics import levels as L

HERE = Path(__file__).resolve().parent
NO_SCENE = {
    'M5': 'needs a kernel that replays a real leader; only the human branch has one, so it cannot be scored across drivers yet',
    'JS8': 'real queue-per-cycle data (Songdo) is not analysed yet',
    'JP1': 'no clean real source for give-way junctions in hand (report 22)', 'JP2': 'no clean real source for give-way junctions in hand', 'JP3': 'no clean real source for give-way junctions in hand',
    'JR3': 'entry-against-circulating curve from the Swiss data is not computed yet',
    'JO1': 'report 18 pending: real merge positions are not tagged yet',
    'JL1': 'DRaT has 45 forced merges, not analysed into a target yet', 'JL2': 'DRaT discharge per lane not analysed into a target yet',
    'JZ1': 'no clean real source for zipper merges yet (report 18 pending)',
    'C1': 'real camera data (Cambridge) in hand for one day; no Cambridge scene built yet, and no floor until the other seven days are fetched',
    'C2': 'needs a rebuild of a tracked road, not yet built',
}
BERLIN_ONLY = ['N0', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9', 'N10', 'N11', 'N12', 'N13', 'N14', 'N15', 'N16', 'N17', 'N18', 'N19', 'N20', 'N21', 'N22', 'C5', 'C6']


def load_registry():
    import tomllib
    return tomllib.loads((HERE / 'registry.toml').read_text())['metric']


def code_sha():
    h = hashlib.sha256()
    for p in sorted(list(HERE.glob('*.py')) + list(HERE.glob('metrics/*.py')) + [HERE / 'registry.toml']):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def floors_micro():
    with gzip.open(HERE / 'floors/micro.json.gz', 'rt') as f:
        return json.load(f)


def floors_junction():
    return json.loads((HERE / 'floors/junction.json').read_text())


class Tally:
    """Counts across all runs for level 0 and M12."""

    def __init__(self):
        self.teleports, self.collisions, self.neg, self.veh_km, self.conserve, self.acc_bad = [], [], [], [], [], []
        self.seconds = {}

    def add(self, name, r, f=None, interval=None):
        self.seconds[name] = self.seconds.get(name, 0) + r.secs
        self.teleports.append(r.teleports or 0)
        self.collisions.append(r.collisions or 0)
        c = r.counts(f)
        if c:
            self.conserve.append(abs(c[0] - c[1] - c[2]))
        if f is not None:
            self.acc_bad.append(int(((f.acc < -8.91) | (f.acc > 5.0)).sum()))
            self.veh_km.append(X.veh_km(f, interval))


def road_stats(r, interval, tally):
    f = r.table()
    tally.add('road', r, f, interval)
    f = X.track_arrays(f, interval)
    f = X.leaders(f)
    f['T'] = X.time_gap(f)
    tally.neg.append(int(((f.bumper < -.05) & (f.offset.abs() < .5) & (f.lead_off.abs() < .5)).sum()))
    a, j, T = {}, {}, {}
    for lo, hi in X.BANDS:
        name = f'{lo}-{hi}'
        a[name], j[name], T[name] = X.band_samples(f, lo, hi, 'a1'), X.band_samples(f, lo, hi, 'j1'), X.band_samples(f, lo, hi, 'T')
    relax = X.relaxation(f, interval)
    amp, per = [], []
    A = f[f.lane.str.startswith('A_')]
    for _, g in A.groupby('trip'):
        if len(g) * interval >= 60 and 5 <= g.speed.median() <= 15:
            x, p = X.swing(g.sort_values('time').speed.to_numpy(), interval)
            amp.append(x)
            if np.isfinite(p):
                per.append(p)
    t_end = float(f.time.max())
    C = f[f.lane.str.startswith('C_') & (f.pos > 800) & (f.time > t_end / 2)]
    counted = C.groupby('trip').time.min()
    lanes = 2
    window = max(float(counted.max() - counted.min()), 1.0) if len(counted) else 1.0
    rate = len(counted) / window * 3600 / lanes if len(counted) >= 50 else np.nan
    cuts = {}
    for x in (2850, 2550):
        m = A[(np.abs(A.pos - x) < 40) & (A.time > 60)]
        cuts[x] = m.groupby((m.time // 2).astype(int)).speed.mean()
    both = pd.concat(cuts, axis=1).interpolate(limit=3).dropna()
    both = both[(both[2850] < 20) & (both[2550] < 20)]
    wave = X.wave_lag(both[2850], both[2550], 2.0, 300.0) if len(both) > 60 else np.nan
    ev = X.halfway(f)
    ev = X.lane_changes(f, interval) if ev is None else ev
    ev = ev[ev.speed < 15]
    gaps = X.gaps_at_change(f, ev) if len(ev) else pd.DataFrame(columns=['lag', 'lead', 'v'])
    del f
    return dict(relax=relax, a=a, j=j, T=T, amp=float(np.median(amp)) if amp else np.nan, per=float(np.median(per)) if per else np.nan, rate=rate, wave=wave, gaps=gaps)


def free_stats(r, interval, tally):
    f = r.table()
    tally.add('free3', r, f, interval)
    f = X.leaders(f)
    tally.neg.append(int(((f.bumper < -.05) & (f.offset.abs() < .5) & (f.lead_off.abs() < .5)).sum()))
    ev = X.lane_changes(f, interval)
    km = X.veh_km(f, interval)
    half = X.halfway(f)
    half = ev if half is None else half
    gaps = X.gaps_at_change(f, half[half.speed >= 15]) if len(half) else pd.DataFrame(columns=['lag', 'lead', 'v'])
    shapes = X.lc_shapes(f)
    speeds = f[f.bumper.isna() | (f.bumper > 150)].speed.to_numpy()
    return dict(rate=len(ev) / max(km, 1e-3), gaps=gaps, shapes=shapes, speeds=speeds)


def signal_table(r, plan, length, tally, name='signal'):
    f = r.table()
    interval = float(np.median(np.diff(np.unique(f.time.values)[:50])))
    tally.add(name, r, f, interval)
    return X.queue_table(f, 'in_0', length, plan['cycle'], plan['green'], plan.get('demand_end', plan['end'])), f, interval


def lane_length(net, lane):
    import xml.etree.ElementTree as ET
    for l in ET.parse(net).getroot().iter('lane'):
        if l.get('id') == lane:
            return float(l.get('length'))
    raise SystemExit(f'no lane {lane}')


def physical(f, interval):
    """Report 19's quantities on one run: stops, launches, shares of moving time, everyday jerk."""
    f = X.track_arrays(f, interval)
    moving = f[f.speed > 1.0]
    a = moving.a1.dropna().to_numpy()
    j = moving.j1.dropna().abs().to_numpy()
    stops, launches = X.stops_launches(f)
    share = {'2': float((a < -2).mean()) if len(a) else np.nan, '3': float((a < -3).mean()) if len(a) else np.nan, '4.5': float((a < -4.5).mean()) if len(a) else np.nan}
    return dict(stops=stops, launches=launches, share=share, up2=float((a > 2).mean()) if len(a) else np.nan, j50=float(np.median(j)) if len(j) else np.nan, j95=float(np.quantile(j, .95)) if len(j) else np.nan)


def real_heads():
    h = HERE / 'floors/heads.json'
    return {i: v for i, v in enumerate(json.loads(h.read_text()))}


def evaluate(cfg, fast=True, ov=None, seeds=None, gpu=False, only=None, berlin=None, work=None, log=print):
    ov = ov or {}
    seeds = seeds or ([1] if fast else [1, 2, 3, 4, 5, 6])
    micro, junc = floors_micro(), floors_junction()
    tally = Tally()
    M = {}
    want = lambda s: only is None or s in only
    rr = lambda s, seed, **k: runner.run(cfg, s, seed, fast, ov, work=work, gpu=gpu, **k)

    if want('road'):
        st = []
        for s in seeds:
            r = rr('road', s)
            log(f'road s{s} {r.secs:.0f}s')
            st.append(road_stats(r, max(r.plan['fcd'], ov.get('dt', cfg['dt'])), tally))
            runner.clean(r)
        M['M1'] = thin_blocks(L.per_tracker([x['a'] for x in st], micro, 'a'))
        M['M2'] = thin_blocks(L.per_tracker([x['j'] for x in st], micro, 'j'))
        M['M3'] = thin_blocks(L.per_tracker([x['T'] for x in st], micro, 'T'))
        M['M13'] = L.M13([x['amp'] for x in st], [x['per'] for x in st], micro)
        M['C4'] = L.c4([x['wave'] for x in st])
        M['M10'] = L.M10([x['relax'] for x in st])
        rates = [x['rate'] for x in st]
        M['M9'] = L.M9([x['gaps'] for x in st], 'congested')
        r1 = []
        if not fast or True:
            r = rr('road', seeds[0], dt=1.0, tag='_dt1')
            r1.append(road_stats(r, 1.0, tally)['rate'])
            runner.clean(r)
        M['C3'] = L.c3(rates, r1)
    if want('free3'):
        st = []
        for s in seeds:
            r = rr('free3', s)
            log(f'free3 s{s} {r.secs:.0f}s')
            st.append(free_stats(r, max(r.plan['fcd'], ov.get('dt', cfg['dt'])), tally))
            runner.clean(r)
        M['M7'] = L.M7([x['shapes'] for x in st])
        M['M8'] = L.M8([x['rate'] for x in st])
        M.setdefault('M9', {}).update(L.M9([x['gaps'] for x in st], 'free'))
        M['M11'] = L.M11([x['speeds'] for x in st])
    if want('signal'):
        tabs, tabs_dt1, spac = [], [], []
        fin, wait = [], []
        for s in seeds:
            r = rr('signal', s)
            log(f'signal s{s} {r.secs:.0f}s')
            base = r.d.parent
            length = lane_length(base / 'net.xml', 'in_0') if ov.get('signals') != 'none' else None
            if length is None:
                tally.add('signal', r)
                continue
            t, f, interval = signal_table(r, r.plan, length, tally)
            _l = X.leaders(f)
            tally.neg.append(int(((_l.bumper < -.05) & (_l.offset.abs() < .5) & (_l.lead_off.abs() < .5)).sum()))
            tabs.append(t)
            spac.append(t.spacing.dropna().to_numpy() if len(t) else np.array([]))
            ins, _, running = r.counts(f)
            fin.append(running / max(ins, 1))
            wait.append(max(0.0, 1 - ins / max(r.plan['planned'], 1)))
            runner.clean(r)
        if ov.get('signals') != 'none':
            short = dict(dur=300, drain=60)
            a1 = rr('signal', seeds[0], ctx=short, tag='_a')
            a2 = rr('signal', seeds[0], ctx=short, tag='_b')
            M['V4'] = {'bits': score.zero([0 if runner.sha(a1.fcd) == runner.sha(a2.fcd) else 1], 'runs of the same seed that differ')}
            runner.clean(a1), runner.clean(a2)
            half = rr('signal', seeds[0], dt=ov.get('dt', cfg['dt']) / 2, tag='_h')
            th, _, _ = signal_table(half, half.plan, length, tally)
            runner.clean(half)
            M['V5'] = v5(tabs[0], th)
        for s in seeds:
            r = rr('signal', s, dt=1.0, tag='_dt1')
            if ov.get('signals') != 'none':
                t1, _, _ = signal_table(r, r.plan, length, tally)
                tabs_dt1.append(t1)
            runner.clean(r)
        if tabs:
            M['JS1'], M['JS3'], M['JS4'], M['JS5'] = L.js1(tabs), L.js3(tabs), L.js4(tabs), L.js5(tabs)
            M['JS2'] = L.js2(tabs, tabs_dt1)
            M['M4'] = L.M4(spac)
            M['V6'] = {'unfinished_share': _le(fin, .005)}
            M['V7'] = {'not_entered_share': _le(wait, .01)}
    if want('signal_real'):
        s_, stops, phys = [], [], []
        ctx = dict(real=junc.get('cycle') or dict(cycle=90.0, green=40.0, vph=300))
        for s in seeds:
            r = rr('signal_real', s, ctx=ctx)
            log(f'signal_real s{s} {r.secs:.0f}s')
            f = r.table()
            interval = max(r.plan['fcd'], ov.get('dt', cfg['dt']))
            tally.add('signal_real', r, f, interval)
            phys.append(physical(f, interval))
            a_, b_ = L.delay_samples(f, interval)
            s_.append(a_)
            stops.append(b_)
            runner.clean(r)
        M['JS7'] = L.js7(s_, stops, junc)
        M['M15'] = L.M15([x['stops'] for x in phys])
        M['M16'] = L.M16([x['share'] for x in phys])
        M['M17'] = L.M17([x['launches'] for x in phys], [x['up2'] for x in phys])
        M['M19'] = L.M19([x['j50'] for x in phys], [x['j95'] for x in phys])
    if want('yellow'):
        rows = []
        for s in seeds:
            r = rr('yellow', s)
            log(f'yellow s{s} {r.secs:.0f}s')
            f = r.table()
            interval = max(r.plan['fcd'], ov.get('dt', cfg['dt']))
            tally.add('yellow', r, f, interval)
            if ov.get('signals') != 'none':
                rows.append(L.yellow_decisions(f, lane_length(r.d.parent / 'net.xml', 'in_0'), interval, r.plan['end']))
            runner.clean(r)
        if rows:
            M['JS6'] = L.js6(rows)
    if want('roundabout'):
        rows, fol, vs = [], [], []
        for s in seeds:
            r = rr('roundabout', s)
            log(f'roundabout s{s} {r.secs:.0f}s')
            f = r.table()
            tally.add('roundabout', r, f, max(r.plan['fcd'], ov.get('dt', cfg['dt'])))
            a, b = L.roundabout_decisions(f)
            rows.append(a)
            fol.append(b)
            ring = f[f.lane.str.startswith('ring')]
            vs.append(float(ring.speed.mean()) if len(ring) else np.nan)
            runner.clean(r)
        M['JR1'], M['JR2'] = L.jr(rows, fol)
        M['JR4'] = {'ring_mps': dict(score.no_data('reported only'), value=round(float(np.nanmean(vs)), 2))}
    if want('ramp'):
        gaps, drops = [], []
        for s in seeds:
            r = rr('ramp', s)
            log(f'ramp s{s} {r.secs:.0f}s')
            f = r.table()
            interval = max(r.plan['fcd'], ov.get('dt', cfg['dt']))
            tally.add('ramp', r, f, interval)
            ev = X.halfway(f)
            ev = X.lane_changes(f, interval) if ev is None else ev
            ev = ev[ev.lane.str.startswith('merge_1')]
            gaps.append(X.gaps_at_change(f, ev) if len(ev) else pd.DataFrame(columns=['lag', 'lead', 'v']))
            if r.plan.get('steps'):
                drops.append(L.capacity_drop(f, interval, r.plan['steps']))
            runner.clean(r)
        c = L.M9(gaps, 'congested')['congested']
        M['JO2'] = {'gaps': c}
        M['JO3'] = L.jo3(drops) if drops else {'drop': score.no_data('only the full run raises demand until it breaks down')}
    if want('curves'):
        sideways = {r_: [] for r_ in __import__('scenes').BENDS}
        for s in seeds:
            r = rr('curves', s)
            log(f'curves s{s} {r.secs:.0f}s')
            f = r.table()
            interval = max(r.plan['fcd'], ov.get('dt', cfg['dt']))
            tally.add('curves', r, f, interval)
            for k, r_ in enumerate(sideways):
                arc = f[f.lane == f'e{k}_0']
                arc = arc[(arc.pos > 300 + .2 * r_ * 1.57) & (arc.pos < 300 + .8 * r_ * 1.57)]
                sideways[r_].append(float((arc.speed ** 2 / r_).median()) if len(arc) else np.nan)
            runner.clean(r)
        M['M18'] = L.M18(sideways)
    if want('chain'):
        ch = []
        ctx = dict(heads=real_heads())
        for s in seeds:
            r = rr('chain', s, ctx=ctx)
            log(f'chain s{s} {r.secs:.0f}s')
            f = r.table()
            interval = max(r.plan['fcd'], ov.get('dt', cfg['dt']))
            tally.add('chain', r, f, interval)
            ch.append(L.chain_stats(f, interval, __import__('scenes').lane_offsets(r.plan['net'])))
            runner.clean(r)
        M['M6'] = L.M6(ch)
    if want('ring') and not fast:
        ser = []
        for s in seeds[:2]:
            r = rr('ring', s)
            log(f'ring s{s} {r.secs:.0f}s')
            f = r.table()
            tally.add('ring', r, f, r.plan['fcd'])
            g = f.groupby((f.time // 300).astype(int)).speed.mean().to_numpy()
            ser.append(g)
            runner.clean(r)
        M['M14'] = L.M14(ser)
    berlin = dict(berlin or {})
    b_scale, b_tele, b_runs = berlin.pop('_V8_scale', None), berlin.pop('_V1_teleports', None), berlin.pop('_runs', None)
    for k, v in berlin.items():
        M.setdefault(k, {}).update(v)
    if b_tele is not None:
        tally.teleports.append(b_tele)
    M['V1'] = {'count': score.zero(tally.teleports, 'teleports') if cfg.get('time_to_teleport', 0) == 0 and not ov.get('teleport') else dict(score.zero(tally.teleports, 'teleports on: not a valid run'), status='FAIL', z=score.Z_CAP)}
    if tally.collisions or tally.neg:
        M['V2'] = {'overlaps_per_veh_km': score.zero([sum(tally.collisions) + sum(tally.neg)], f'{sum(tally.collisions)} engine collisions, {sum(tally.neg)} negative bumper gap samples, over {sum(tally.veh_km):.0f} veh-km')}
    if tally.conserve:
        M['V3'] = {'mismatch': score.zero(tally.conserve, 'inserted minus arrived minus running')}
    scale = min(ov.get('demand_scale', 1.0), b_scale if b_scale is not None else 1.0)
    M['V8'] = {'scale': score.zero([0 if scale >= .95 else 1], f'demand scale {scale}')}
    if tally.acc_bad:
        M['M12'] = L.M12(tally.acc_bad)
    return M, tally.seconds, seeds


def thin_blocks(cells):
    """Fewer than 8 real blocks is THIN: never a pass, however close."""
    for c in cells.values():
        if c.get('real_blocks', 8) < 8 and c['status'] == 'FLOOR':
            c['status'] = 'THIN'
    return cells


def _le(values, limit):
    c = score.judge([[x] for x in values], limit)
    c['D'] = [[x] for x in values]
    c['value'] = round(float(np.nanmedian(values)), 5)
    return c


def v5(t, th):
    cells = {}
    for name, fn, F in (('sat_flow', L.sat_flow, 150.0), ('lost_time', lambda x: L.js3([x])['lost_s'].get('value') or np.nan, .57)):
        a, b = fn(t), fn(th)
        d = abs(a - b) if np.isfinite(a) and np.isfinite(b) else np.nan
        c = score.judge([[d]], .25 * F)
        c['D'] = [[d]]
        cells[name] = c
    return cells


def assemble(M, cfg, mode, seeds, seconds, registry, ov=None, name=None, bench_commit='', scene_notes=None):
    metrics, ids = {}, {r['id']: r for r in registry}
    scene_notes = scene_notes or {}
    for r in registry:
        i = r['id']
        cells = M.get(i)
        if not cells:
            note = NO_SCENE.get(i) or ('Berlin district scene not run yet' if i in BERLIN_ONLY else 'its scene was not run in this mode')
            cells = {'-': score.no_data(note)}
        for c in cells.values():
            c.setdefault('note', '')
        ro = score.rollup(cells)
        metrics[i] = dict(id=i, level=r['level'], tag=r['tag'], gate=r['gate'], name=r['name'], plain=r['plain'], status=ro['status'], z=ro['z'], cells=_clean(cells))
    return dict(run_id=name, driver=cfg['name'], mode=mode, commit=cfg['commit'], branch=cfg['branch'], binary_sha=cfg['binary_sha'], config_hash=cfg['hash'], instrument_patch=cfg['patch_sha'],
                seeds=seeds, overrides=ov or {}, seconds={k: round(v) for k, v in seconds.items()}, bench_code=code_sha(), bench_commit=bench_commit, metrics=metrics, levels=levels(metrics), created=time.strftime('%Y-%m-%dT%H:%M:%S'))


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 5)
    if isinstance(x, np.integer):
        return int(x)
    return x


def levels(metrics):
    """Worst status of P and W metrics per level, leximax vector, counts. No total, by construction."""
    out = {}
    for lv in sorted({m['level'] for m in metrics.values()}):
        ms = [m for m in metrics.values() if m['level'] == lv]
        pw = [m for m in ms if m['tag'] in 'PW']
        zs = sorted([m['z'] for m in pw if m['z'] is not None and m['status'] not in ('NO DATA',)], reverse=True)
        counts = {s: sum(1 for m in pw if m['status'] == s) for s in score.ORDER}
        out[str(lv)] = dict(status=score.worst([m['status'] for m in pw]), top_z=zs[:3], counts=counts)
    return out
