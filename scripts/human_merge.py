#!/usr/bin/env python3
"""Report 18's acceptance table: scenes shaped like its four merge sites, measured with its own pipeline.

    python3 scripts/human_merge.py i80 us101 --out DIR [--off edge,follow] [--tune w_f=0.5] [--seeds 2] [--tag NAME]

I-80 and US-101 are for tuning. I-395 and the A39 are held out: run them once, on a frozen build, and report them.
Scenes are the zone drivers can use, not the painted lengths: I-80 and I-395 have a wide lane that narrows, so their
zone is the last 54 and 63 m (report 18, section 2A). Real spread of desired speeds, never speedDev 0.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BIN = os.environ.get('CARS_BIN', str(ROOT / 'target/release/cars'))
MG = Path(os.environ.get('MG_SCRIPTS', '/home/erikf/.t3/projects/cars/research/truth/scripts/merging'))
W = 3.2
# zone m, approach m, main veh/h, ramp veh/h, main limit, ramp limit, neck m/s, speed spread. Flows are the measured flow
# of the target lane and the merging lane at the site. Where their sum is over the model's queue flow a queue forms and
# both lanes crawl, as they did at the congested sites.
SCENES = {
    'i80': dict(zone=54, up=800, main=875, ramp=645, v=6, von=6, neck=6, dev=0.1),
    'us101': dict(zone=216, up=800, main=1486, ramp=457, v=12, von=17, vramp=17, neck=12, dev=0.1),
    'i395': dict(zone=63, up=800, main=1167, ramp=1031, v=9, von=9, neck=9, dev=0.1),
    'a39': dict(zone=400, up=1500, main=337, ramp=144, v=36, von=22, neck=36, dev=0.18),
}
# Row: (name, key in the row dict, I-80, US-101, I-395, A39). A target is (low, high), or None.
TARGETS = [
    ('1 body over the line, m left', 'body', (-3, 17), (108, 168), (21, 41), (285, 365)),
    ('2 stopped first', 'stopped', (.18, .34), (0, .02), (0, .03), (0, .01)),
    ('3 overlap at sideways start', 'ov_start', (.24, .40), (.07, .19), (.29, .51), (0, .02)),
    ('4 overlap at centre over line', 'ov_centre', (0, .08), (0, .02), (.13, .32), (0, .01)),
    ('5 lag p25 at start, m', 'lag25', (.6, 2.6), (2, 4), (1.1, 3.1), None),
    ('6 edge while overlapped p50, lanes', 'edge50', (.03, .23), (-.1, .1), (.02, .22), (-.1, .1)),
    ('6 edge while overlapped p95, lanes', 'edge95', (.22, .52), (.04, .34), (.24, .54), (.06, .36)),
    ('7 gap ahead 5 s before', 'ahead', (.11, .27), (.52, .72), (.01, .17), (0, .11)),
    ('7 gap behind 5 s before', 'behind', (.19, .35), (0, .14), (.32, .48), (.14, .34)),
    ('8 episodes 5 s or more', 'ep5', (.25, .41), (0, .08), (.18, .34), (0, .03)),
    ('8 locked share', 'locked', (.03, .11), (0, .01), (.01, .05), (0, .01)),
    ('9 overlapped in last 5 s', 'ov5', (.36, .56), (.32, .52), (.35, .55), (0, .03)),
    ('10 excess accel -2..0 s', 'ex2', (.09, .25), (-.57, -.27), (-.16, -.04), (.42, .62)),
    ('13 follower extra speed lost', 'lost', (.4, .6), (.47, .77), (.02, .82), (.11, .51)),
    ('14 follower extra responders', 'resp', (.126, .186), (.115, .195), (.05, .21), (.03, .15)),
    # Report 18 gives 4.7%, under 2%, 10.7%, 0.2%. Its own pipeline gives these, 101 of 297 at I-80, so both sides use that.
    ('16 lag under 1 m at body over', 'lag1', (.20, .48), (0, .08), (.14, .32), (0, .01)),
]
COL = {'i80': 2, 'us101': 3, 'i395': 4, 'a39': 5}


def run(cmd, **kw):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}")
    return r


def build(d, sc):
    b = sc['up']
    c = b + sc['zone']
    (d / 'n.nod.xml').write_text(f'<nodes><node id="a" x="0" y="0"/><node id="r" x="{b - 500}" y="-60"/><node id="b" x="{b}" y="0"/><node id="c" x="{c}" y="0"/><node id="d" x="{c + 300}" y="0"/><node id="e" x="{c + 400}" y="0"/><node id="f" x="{c + 1000}" y="0"/></nodes>')
    (d / 'n.edg.xml').write_text(f'''<edges><edge id="up" from="a" to="b" numLanes="1" speed="{sc['v']}"/><edge id="on" from="r" to="b" numLanes="1" speed="{sc['von']}"/><edge id="merge" from="b" to="c" numLanes="2" speed="{sc['v']}"><lane index="0" speed="{sc.get('vramp', sc['von'] if sc['von'] > sc['v'] else sc['v'])}"/></edge><edge id="down" from="c" to="d" numLanes="1" speed="{sc['v']}"/><edge id="neck" from="d" to="e" numLanes="1" speed="{sc['neck']}"/><edge id="out" from="e" to="f" numLanes="1" speed="{sc['v']}"/></edges>''')
    (d / 'n.con.xml').write_text('<connections><connection from="up" to="merge" fromLane="0" toLane="1"/><connection from="on" to="merge" fromLane="0" toLane="0"/><connection from="merge" to="down" fromLane="1" toLane="0"/></connections>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-x', d / 'n.con.xml', '-o', d / 'net.xml', '--no-turnarounds', 'true'])


def routes(d, sc, dur):
    (d / 'r.xml').write_text(f'''<routes><vType id="h" carFollowModel="Human" length="5" minGap="2.5" speedDev="{sc['dev']}"/><route id="rr" edges="on merge down neck out"/><route id="rm" edges="up merge down neck out"/><flow id="ramp" type="h" route="rr" begin="0" end="{dur}" vehsPerHour="{sc['ramp']}" departLane="0" departSpeed="max"/><flow id="main" type="h" route="rm" begin="0" end="{dur}" vehsPerHour="{sc['main']}" departLane="0" departSpeed="max"/></routes>''')


def to_cache(work, net, fcs):
    """FCD to the cache of mg_cache.py. The lane label follows lateral position, as in real data."""
    cache = work / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    (work / 'events').mkdir(exist_ok=True)
    text = net.read_text()
    length = {m.group(1): float(m.group(2)) for m in re.finditer(r'<lane id="([\w:]+)"[^>]*?length="([\d.]+)"', text)}
    zone = length['merge_1']
    inner = next((v for k, v in length.items() if k.startswith(':c_')), 0.0)
    parts = []
    for r, fc in enumerate(fcs):
        d = pd.read_csv(fc, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'length', 'offset'])
        la = d['lane'].values
        pos = d['pos'].values.astype('f8')
        s = np.full(len(d), np.nan)
        idx = np.ones(len(d), 'i2')
        for name, base, ii in (('up_0', -length['up_0'], 2), ('on_0', -length['on_0'], 1), ('merge_0', 0.0, 1), ('merge_1', 0.0, 2), ('down_0', zone + inner, 2), ('neck_0', None, 2), ('out_0', None, 2)):
            if base is None:
                continue
            m = la == name
            s[m] = pos[m] + base
            idx[m] = ii
        for k in length:
            if k.startswith(':c_'):
                m = la == k
                s[m] = pos[m] + zone
                idx[m] = 2
        ok = np.isfinite(s)
        d = d[ok]
        s = s[ok]
        idx = idx[ok]
        lat = idx * W + d['offset'].values
        lab = np.where(idx == 2, np.where(lat < 1.5 * W, 1, 2), 1)
        parts.append(pd.DataFrame(dict(run=r, t=np.round(d['time'].values * 2).astype('i4'), id=pd.factorize(d['trip'])[0], lane=lab.astype('i2'), s=s, v=d['speed'].values, a=d['acc'].values, L=d['length'].values, lat=lat)))
    d = pd.concat(parts, ignore_index=True).sort_values(['run', 'id', 't']).reset_index(drop=True)
    np.savez(cache / 'sim.npz', run=d['run'].values.astype('i2'), t=d['t'].values, id=d['id'].values.astype('i4'), lane=d['lane'].values.astype('i2'), s=d['s'].values.astype('f4'), v=d['v'].values.astype('f4'), a=d['a'].values.astype('f4'), L=d['L'].values.astype('f4'), lat=d['lat'].values.astype('f4'), hz=2)
    b = (d['s'] / 20).astype('i4')
    pd.DataFrame(dict(r=d['run'], l=d['lane'], b=b, x=d['lat'])).groupby(['r', 'l', 'b'])['x'].agg(['median', 'size']).reset_index().to_csv(cache / 'sim.centres.csv.gz', index=False)


def pipeline(work):
    link = work / 'research/truth/scripts/merging'
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.exists():
        link.symlink_to(MG)
    (work / 'research/truth/merging').mkdir(exist_ok=True)
    env = dict(os.environ, MG_DATA=str(work), PYTHONUNBUFFERED='1')
    for s in ('mg_events.py', 'mg_analyse.py', 'mg_follow.py'):
        run(['python3', f'research/truth/scripts/merging/{s}', 'sim'], cwd=work, env=env)
    return json.loads((work / 'research/truth/merging/sim.json').read_text()), json.loads((work / 'research/truth/merging/follow_sim.json').read_text())


def row_of(a, f):
    m = a['gaps'].get('must') or {}
    if not m:
        return dict(n=a['must'], wait50=None, wait90=None)
    st, ce, to = m['at_lateral_start'], m['at_centre'], m['at_touch']
    tg = a['target_gap']['must']['5']
    par = a.get('parallel', {}).get('must', {})
    pre = a['pre_accel_excess']['must']
    all_ = f['touch']['all']
    lag_t = to.get('lag', {})
    return dict(n=a['must'], body=a['location']['rem_body_touches_line'].get('p50'), wait50=a['location']['wait_in_lane'].get('p50'), wait90=a['location']['wait_in_lane'].get('p90'),
                stopped=a['location']['stopped_below_1'], ov_start=st.get('overlap_share'), ov_centre=ce.get('overlap_share'), lag25=st.get('lag', {}).get('p25'),
                edge50=m['max_q_while_overlapping'].get('p50'), edge95=m['max_q_while_overlapping'].get('p95'), ahead=tg['gap_ahead'], behind=tg['gap_behind'],
                ep5=par.get('share_ge5'), locked=par.get('locked_3s'), ov5=a['overlap_time_share_before_start']['must'].get('-5..0'), ex2=pre.get('-2..0', {}).get('excess'),
                lost=(all_.get('lost_excess') or [None])[0], resp=(all_.get('responders_vs_20') or [None])[0], lag1=f.get('no_room_at_touch', {}).get('lag_under_1', {}).get('n', 0) / max(to.get('n', 0), 1), lag_p05=lag_t.get('p05'))


def show(scene, row, extra):
    print(f"\n== {scene}: {row['n']} must-change cars; wait p50 {row['wait50']}, p90 {row['wait90']}; {extra}")
    passed = total = 0
    for t in TARGETS:
        band = t[COL[scene]]
        v = row.get(t[1])
        if band is None:
            continue
        total += 1
        ok = v is not None and band[0] <= v <= band[1]
        passed += ok
        print(f"  {t[0]:38s} {'' if v is None else round(float(v), 3)!s:>8}   band {band[0]}..{band[1]}  {'pass' if ok else 'FAIL'}")
    print(f'  {passed} of {total} in band')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('scenes', nargs='+', choices=list(SCENES))
    p.add_argument('--out', default='/tmp/hu/mg')
    p.add_argument('--off', default='')
    p.add_argument('--tune', action='append', default=[])
    p.add_argument('--seeds', type=int, default=2)
    p.add_argument('--dt', type=float, default=0.5)
    p.add_argument('--dur', type=int, default=1200)
    p.add_argument('--tag', default='base')
    a = p.parse_args()
    for name in a.scenes:
        sc = SCENES[name]
        work = Path(a.out) / a.tag / name
        work.mkdir(parents=True, exist_ok=True)
        build(work, sc)
        routes(work, sc, a.dur)
        fcs = []
        coll = floor = guard = steps = 0
        for seed in range(a.seeds):
            fc = work / f's{seed}.csv'
            extra = [x for t in a.tune for x in ('--tune', t)] + (['--human-off', a.off] if a.off else [])
            run([BIN, 'run', '--net', work / 'net.xml', '--routes', work / 'r.xml', '--dt', a.dt, '--end', a.dur + 600, '--seed', seed, '--fcd', fc, '--fcd-interval', 0.5, '--report-json', work / f's{seed}.json', *extra])
            rep = json.loads((work / f's{seed}.json').read_text())
            coll += rep['collision_incidents']
            floor += rep['cert_floor']
            guard += rep['humans']['guard_steps']
            steps += rep['humans']['human_steps']
            fcs.append(fc)
        to_cache(work, work / 'net.xml', fcs)
        an, fo = pipeline(work)
        row = row_of(an, fo)
        (work / 'row.json').write_text(json.dumps(row, indent=1, default=float))
        show(name, row, f'collisions {coll}, floor {floor}, guard {guard / max(steps, 1):.3%}')


if __name__ == '__main__':
    main()
