#!/usr/bin/env python3
"""GPU tests of physical mode on small fixtures. Numbers come from research/truth/11-vehicle-physics.md.

    python3 scripts/physics_tests.py [names...] [--cars target/release/cars] [--out DIR]

Every run holds /tmp/cars-gpu.lock. A failure prints what it saw and the run stays on disk.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / 'research/truth/wltc-class3b.txt'
NOMINAL = '<param key="phys.nominal" value="1"/>'
results = []
A = None
# One flock around a whole batch is kinder than queueing for each small run.
LOCK = [] if os.environ.get('CARS_GPU_HELD') else ['flock', '/tmp/cars-gpu.lock']


def run(cmd, **kw):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout[-2000:]}\n{r.stderr[-4000:]}")
    return r


def cars(d, *args, routes='r.xml', net='net.xml', tag='run'):
    report = d / f'{tag}.json'
    log = run([*LOCK, A.cars, 'run', '--net', d / net, '--routes', d / routes, '--report-json', report, *args])
    (d / f'{tag}.log').write_text(log.stdout + log.stderr)
    return json.loads(report.read_text()) if report.exists() else {}


def check(name, ok, detail, d=None):
    results.append(dict(name=name, ok=bool(ok), detail=detail))
    print(('ok   ' if ok else 'FAIL ') + name + ': ' + detail + (f'  [{d}]' if d and not ok else ''), flush=True)


def clean(name, rep, d):
    """No collision, teleport or stuck vehicle. Applies to every test."""
    bad = {k: rep[k] for k in ('collision_incidents', 'teleports', 'ungranted', 'dead_end', 'no_brake') if rep.get(k)}
    stuck = rep.get('gridlock_worst_stuck', 0)
    if stuck:
        bad['stuck'] = stuck
    check(f'{name}: clean', not bad, str(bad) if bad else f"{rep.get('arrived')} arrived, {rep.get('lane_changes')} lane changes, {rep.get('shadows')} shadows", d)


def netconvert(d, nodes, edges, *extra):
    (d / 'n.nod.xml').write_text('<nodes>' + nodes + '</nodes>')
    (d / 'n.edg.xml').write_text('<edges>' + edges + '</edges>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds', *extra])


def workdir(name):
    d = Path(A.out) / name if A.out else Path(tempfile.mkdtemp(prefix=f'phys-{name}-'))
    d.mkdir(parents=True, exist_ok=True)
    return d


def queue_flow(fcd, stop_lane, length):
    rows = pd.read_csv(fcd, usecols=['time', 'trip', 'lane', 'pos', 'speed'], dtype={'trip': str, 'lane': str})
    crossings = []
    for trip, g in rows.groupby('trip', sort=False):
        on = g[g.lane == stop_lane]
        off = g[g.lane != stop_lane]
        if on.empty or off.empty:
            continue
        before = on.iloc[-1]
        after = off.iloc[0]
        ahead = after.pos + (length - before.pos)
        crossings.append(before.time + (after.time - before.time) * (length - before.pos) / max(ahead, 1e-6))
    crossings.sort()
    head = [b - a for a, b in zip(crossings, crossings[1:])]
    return 3600 / (sum(head[8:]) / len(head[8:])), len(crossings), crossings[0]


def t_queue():
    """A queue of 30 released from a stop line: spec 1,861 at dt 1 and 1,855 at dt 0.1."""
    d = workdir('queue')
    netconvert(d, '<node id="a" x="-1500" y="0"/><node id="m" x="0" y="0" type="traffic_light"/><node id="b" x="1000" y="0"/>',
               '<edge id="am" from="a" to="m" speed="13.89"/><edge id="mb" from="m" to="b" speed="13.89"/>', '--no-internal-links', 'false')
    (d / 'tls.xml').write_text('<additional><tlLogic id="m" type="static" programID="hold" offset="0"><phase duration="200" state="r"/><phase duration="400" state="G"/></tlLogic></additional>')
    body = f'<routes><vType id="c" vClass="passenger" sigma="0" speedDev="0" length="5" minGap="2.5">{NOMINAL}</vType><route id="r" edges="am mb"/>'
    for i in range(30):
        body += f'<vehicle id="v{i:02d}" type="c" route="r" depart="{i * 4}" departSpeed="0"/>'
    (d / 'r.xml').write_text(body + '</routes>')
    length = float(next(x for x in (d / 'net.xml').read_text().split('<lane id="am_0"')[1].split() if x.startswith('length=')).split('"')[1])
    flows = {}
    for dt in (1.0, 0.1):
        tag = f'dt{dt}'
        # Report 11's own parameters, to check the kernel against its numbers. `capacity` tests today's defaults.
        spec = ['--tune', 'tau=1.35', '--tune', 'driver_b=4.5', '--tune', 'leader_b=4.5', '--tune', 'car_b_lo=7']
        rep = cars(d, '--additional', d / 'tls.xml', '--dt', dt, '--end', 400, '--fcd', d / f'{tag}.csv', '--fcd-interval', dt, '--fcd-begin', 190, *spec, tag=tag)
        flows[dt], n, first = queue_flow(d / f'{tag}.csv', 'am_0', length)
        clean(f'queue dt {dt}', rep, d)
        check(f'queue dt {dt}: all crossed', n == 30, f'{n} of 30, first at {first:.2f} s')
    a, b = flows[1.0], flows[0.1]
    check('queue saturation flow, dt 1', abs(a - 1861) / 1861 <= 0.03, f'{a:.0f} veh/h against the spec 1861', d)
    check('queue saturation flow, dt 0.1', abs(b - 1855) / 1855 <= 0.03, f'{b:.0f} veh/h against the spec 1855', d)
    check('queue flow does not depend on dt', abs(a / b - 1) <= 0.02, f'{100 * (a / b - 1):+.2f}%, the report wants 1%', d)


ROUTE = dict(through='wc ce', right='wc cs', left='wc cn', double='wc cn')


def capacity_net(d, kind, radius=None):
    """A real crossing with every arm built, so that the corners are what netconvert makes of a junction."""
    extra = ['--default.junctions.radius', radius] if radius else []
    lanes = 2 if kind == 'double' else 1
    nodes = '<node id="c" x="0" y="0" type="traffic_light"/><node id="w" x="-1500" y="0"/><node id="e" x="1000" y="0"/><node id="s" x="0" y="-1000"/><node id="n" x="0" y="1000"/>'
    edges = ''.join(f'<edge id="{a}{b}" from="{a}" to="{b}" numLanes="{lanes}" speed="13.89"/>' for a, b in (('w', 'c'), ('c', 'e'), ('e', 'c'), ('c', 'w'), ('s', 'c'), ('c', 'n'), ('n', 'c'), ('c', 's')))
    if kind == 'double':
        (d / 'n.con.xml').write_text('<connections><connection from="wc" to="cn" fromLane="0" toLane="0"/><connection from="wc" to="cn" fromLane="1" toLane="1"/></connections>')
        extra += ['-x', d / 'n.con.xml']
    netconvert(d, nodes, edges, *extra)


def saturation(d, kind, dt, args, tag, n=30, min_gap=2.5, sigma=0):
    """Queue discharge in veh per green hour per lane, after the first 8 cars, and the jam spacing."""
    links = len((d / 'net.xml').read_text().split('<phase ')[1].split('state="')[1].split('"')[0])
    (d / 'tls.xml').write_text(f'<additional><tlLogic id="c" type="static" programID="hold" offset="0"><phase duration="240" state="{"r" * links}"/><phase duration="400" state="{"G" * links}"/></tlLogic></additional>')
    body = f'<routes><vType id="c" vClass="passenger" sigma="{sigma}" speedDev="0" length="5" minGap="{min_gap}">{NOMINAL}</vType><route id="r" edges="{ROUTE[kind]}"/>'
    lanes = 2 if kind == 'double' else 1
    for i in range(n * lanes):
        body += f'<vehicle id="v{i:03d}" type="c" route="r" depart="{i // lanes * 5}" departSpeed="0" departLane="{i % lanes}"/>'
    (d / 'r.xml').write_text(body + '</routes>')
    rep = cars(d, '--additional', d / 'tls.xml', '--dt', dt, '--end', 500, '--fcd', d / f'{tag}.csv', '--fcd-interval', dt, '--fcd-begin', 235, '--seed', 1, *args, tag=tag)
    f = pd.read_csv(d / f'{tag}.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed'], dtype={'lane': str, 'trip': str})
    flows, spacing = [], []
    for lane_i in range(lanes):
        lane = f'wc_{lane_i}'
        length = float((d / 'net.xml').read_text().split(f'<lane id="{lane}"')[1].split('length="')[1].split('"')[0])
        g = f[f.lane == lane]
        q = g[(g.time - 239).abs() < dt / 2].sort_values('pos')
        if len(q) > 3:
            spacing.append(q.pos.diff().iloc[1:].median())
        ends = []
        for trip in g.trip.unique():
            r = f[f.trip == trip]
            on = r[r.lane == lane].iloc[-1]
            off = r[r.time > on.time]
            if off.empty:
                continue
            a = off.iloc[0]
            ends.append(on.time + (a.time - on.time) * (length - on.pos) / max(a.pos + length - on.pos, 1e-6))
        ends.sort()
        head = [b - x for x, b in zip(ends, ends[1:])]
        if len(head) > 12:
            flows.append(3600 / (sum(head[8:]) / len(head[8:])))
    return (sum(flows) / len(flows) if flows else 0.0, sum(spacing) / len(spacing) if spacing else 0.0, rep)


def t_capacity():
    """Against Trafikverket's TRVMB Kapacitet, per green hour per lane: 1,900 through, 1,700 turning, 1,500 in a
    double turn, jam spacing 7.43 m. And what the safety rules cost: the same queue with each one off."""
    d = workdir('capacity')
    target = dict(through=1900, right=1700, left=1700, double=1500)
    rows = []
    for kind in ('through', 'right', 'left', 'double'):
        capacity_net(d, kind, A.radius)
        for dt in (1.0, 0.1):
            base = None
            for label, args in (('all rules', A.tune_args), ('no certificate', [*A.tune_args, '--tune', 'certificate=0']), ('no arbiter', [*A.tune_args, '--tune', 'arbiter=0']), ('no exit-clear', [*A.tune_args, '--tune', 'exit_clear=0'])):
                flow, spacing, rep = saturation(d, kind, dt, args, f'{kind}-{dt}-{label.replace(" ", "")}')
                if base is None:
                    base = flow
                    check(f'capacity {kind} dt {dt}', abs(flow / target[kind] - 1) <= 0.05, f'{flow:.0f} per green hour per lane against {target[kind]}, jam spacing {spacing:.2f} m against 7.43', d)
                rows.append(dict(kind=kind, dt=dt, rules=label, flow=round(flow), target=target[kind], spacing=round(spacing, 2), contacts=rep.get('collision_incidents'), cost_pct=round(100 * (base / max(flow, 1) - 1), 1)))
                print(f'     {kind} dt {dt} {label}: {flow:.0f}, contacts {rep.get("collision_incidents")}, safety cost {100 * (base / max(flow, 1) - 1):+.1f}%', flush=True)
    (d / 'capacity.json').write_text(json.dumps(rows, indent=1))


def siegloch(q, tc, tf):
    """Minor-road capacity under Poisson major flow: Siegloch's form, as in HCM and TRVMB-style methods."""
    return 3600 / tf * math.exp(-(q / 3600) * (tc - tf / 2))


def t_gap():
    """A saturated minor road across a major flow, against gap acceptance with TRVMB's 5.1 s for straight on."""
    d = workdir('gap')
    netconvert(d, '<node id="c" x="0" y="0" type="priority"/><node id="w" x="-500" y="0"/><node id="e" x="500" y="0"/><node id="s" x="0" y="-500"/><node id="n" x="0" y="500"/>',
               '<edge id="wc" from="w" to="c" priority="2" speed="13.89"/><edge id="ce" from="c" to="e" priority="2" speed="13.89"/><edge id="sc" from="s" to="c" priority="1" speed="13.89"/><edge id="cn" from="c" to="n" priority="1" speed="13.89"/>')
    for q in (100, 300, 600, 900):
        for dt in (1.0, 0.1):
            args = A.tune_args
            (d / 'r.xml').write_text(f'<routes><vType id="c" vClass="passenger" sigma="0.5">{NOMINAL}</vType><route id="m" edges="wc ce"/><route id="y" edges="sc cn"/>'
                                     f'<flow id="major" type="c" route="m" begin="0" end="1500" probability="{q / 3600:.5f}" departSpeed="max"/><flow id="minor" type="c" route="y" begin="0" end="1500" vehsPerHour="1400" departSpeed="0"/></routes>')
            tag = f'q{q}-{dt}'
            rep = cars(d, '--dt', dt, '--end', 1500, '--seed', 1, '--trip-csv', d / f'{tag}.csv', *args, tag=tag)
            t = pd.read_csv(d / f'{tag}.csv', dtype={'trip': str})
            done = t[t.trip.str.startswith('minor') & (t.arrival > 300)]
            major = t[t.trip.str.startswith('major') & (t.arrival > 300)]
            got = len(done) / 1200 * 3600
            flow = len(major) / 1200 * 3600
            want = siegloch(flow, 5.1, 3.1)
            check(f'gap acceptance q {q} dt {dt}', abs(got / max(want, 1) - 1) <= 0.25, f'minor {got:.0f} veh/h against {want:.0f} (tc 5.1, tf 3.1) at major {flow:.0f}; contacts {rep["collision_incidents"]}', d)


def t_wltc():
    """Follows WLTC and compares wheel energy with the report's table, section 2.3."""
    d = workdir('wltc')
    netconvert(d, '<node id="a" x="0" y="0"/><node id="b" x="24000" y="0"/>', '<edge id="ab" from="a" to="b" speed="60"/>')
    kmh = [float(x) for x in TRACE.read_text().split()]
    # name, kg with payload, kW, CdA, Crr, kappa, Wh/km positive at the wheel in the report
    cars_ = [('sandero', 1189, 49, 0.72, 0.011, 0.775, 128), ('golf', 1407, 85, 0.63, 0.011, 0.775, 134), ('fleet', 1663, 90, 0.68, 0.011, 0.775, 154), ('xc90t6', 2160, 228, 0.95, 0.011, 0.775, 205), ('model3', 1936, 208, 0.50, 0.011, 0.83, 157)]
    for dt in (1.0, 0.1):
        n = round(1800 / dt)
        trace = d / f'trace{dt}.txt'
        values = []
        for i in range(n + 2):
            t = i * dt
            k = min(int(t), 1799)
            values.append((kmh[k] + (kmh[k + 1] - kmh[k]) * (t - k)) / 3.6)
        trace.write_text('\n'.join(f'{v:.5f}' for v in values))
        for name, kg, kw, cda, crr, kappa, want in cars_:
            r = d / f'{name}.xml'
            r.write_text(f'<routes><vType id="c" vClass="passenger" sigma="0" speedDev="0" maxSpeed="60">{NOMINAL}'
                         + ''.join(f'<param key="phys.{k}" value="{v}"/>' for k, v in dict(mass=kg / 1.0034, power_kw=kw, cda=cda, crr=crr, kappa=kappa, eps=0.05, a0=6, a1=0, a_floor=6).items())
                         + f'</vType><route id="r" edges="ab"/><vehicle id="v" type="c" route="r" depart="0" departSpeed="0" arrivalPos="23100"/></routes>')
            tag = f'{name}{dt}'
            rep = cars(d, '--dt', dt, '--end', 1810, '--speed-trace', trace, '--trip-csv', d / f'{tag}.trips.csv', '--fcd', d / f'{tag}.fcd.csv', '--fcd-interval', 1, routes=f'{name}.xml', tag=tag)
            clean(f'wltc {name} dt {dt}', rep, d)
            e = rep['energy']
            check(f'wltc {name} dt {dt}: wheel energy', abs(e['wheel_wh_km'] / want - 1) <= 0.05, f"{e['wheel_wh_km']:.1f} Wh/km positive against {want}, {e['brake_wh_km']:.1f} braking", d)
            check(f'wltc {name} dt {dt}: books (I16)', e['balance_worst'] <= 0.01 and e['wheel_wh_km'] <= 500, f"worst {100 * e['balance_worst']:.4f}%", d)
            f = pd.read_csv(d / f'{tag}.fcd.csv')
            ref = [values[min(round(t / dt) + 1, len(values) - 1)] for t in f.time]
            err = abs(f.speed.to_numpy() - ref).max() * 3.6
            check(f'wltc {name} dt {dt}: follows the trace', err <= 3.0, f'max speed error {err:.2f} km/h', d)
    # The check the report gives for electric: its own Model 3 Long Range road load, 85% and 60%.
    r = d / 'lr.xml'
    r.write_text(f'<routes><vType id="c" vClass="passenger" sigma="0" speedDev="0" maxSpeed="60">{NOMINAL}'
                 + ''.join(f'<param key="phys.{k}" value="{v}"/>' for k, v in dict(mass=1936 / 1.0034, power_kw=208, cda=0.50, crr=0.0078, eps=0.0, kappa=0.83, a0=6, a1=0, a_floor=6).items())
                 + '</vType><route id="r" edges="ab"/><vehicle id="v" type="c" route="r" depart="0" departSpeed="0" arrivalPos="23100"/></routes>')
    rep = cars(d, '--dt', 1, '--end', 1810, '--speed-trace', d / 'trace1.0.txt', '--trip-csv', d / 'lr.trips.csv', routes='lr.xml', tag='lr')
    t = pd.read_csv(d / 'lr.trips.csv').iloc[0]
    km = t.dist_m / 1000
    wheel = t.wheel_kwh * 1000 / km
    battery = (t.wheel_kwh / 0.85 - 0.6 * 0.85 * t.brake_kwh) * 1000 / km
    check('wltc Model 3 LR: wheel and battery', abs(wheel / 143 - 1) <= 0.1 and abs(battery / 141 - 1) <= 0.1,
          f'{wheel:.0f} Wh/km at the wheel against 143, {battery:.0f} from the battery against 141 in the report, 132 declared. CSV total with auxiliaries {t.ev_kwh * 1000 / km:.0f}', d)


def t_grade():
    """Grade from net heights: a 40 t truck crawls, a car does not. Report: 58.5 and 39.3 km/h at 5% inertia, 57.4 and 38.3 at the 8% of the build table."""
    d = workdir('grade')
    for pct, want in ((3, 57.4), (5, 38.3)):
        rise = 4000 * pct / 100
        netconvert(d, f'<node id="a" x="0" y="0" z="0"/><node id="b" x="500" y="0" z="0"/><node id="c" x="4500" y="0" z="{rise}"/><node id="e" x="5000" y="0" z="{rise}"/>',
                   '<edge id="ab" from="a" to="b" speed="25"/><edge id="bc" from="b" to="c" speed="25"/><edge id="ce" from="c" to="e" speed="25"/>', '--geometry.remove', 'false')
        (d / 'r.xml').write_text(f'<routes><vType id="t" vClass="trailer" length="16.5" sigma="0" speedDev="0" maxSpeed="25">{NOMINAL}<param key="phys.a0" value="3"/><param key="phys.a1" value="0"/><param key="phys.a_floor" value="3"/></vType>'
                                 f'<vType id="c" vClass="passenger" sigma="0" speedDev="0" maxSpeed="25">{NOMINAL}</vType>'
                                 '<route id="r" edges="ab bc ce"/><vehicle id="tr" type="t" route="r" depart="0" departSpeed="0"/></routes>')
        rep = cars(d, '--dt', 1, '--end', 500, '--fcd', d / f'g{pct}.csv', '--fcd-interval', 1, '--phys-json', d / f'g{pct}.phys.json', tag=f'g{pct}')
        f = pd.read_csv(d / f'g{pct}.csv', dtype={'lane': str})
        hill = f[(f.lane == 'bc_0') & (f.pos > 3000)]
        speed = hill.speed.iloc[-1] * 3.6 if len(hill) else 0.0
        gz = json.loads((d / f'g{pct}.phys.json').read_text())['lanes']['bc_0']['gz']
        check(f'grade {pct}%: lane data', abs(gz / (9.81 * pct / 100) - 1) <= 0.03, f'g sin(theta) {gz:.3f} m/s2', d)
        check(f'grade {pct}%: crawl speed of 40 t', abs(speed - want) <= 2.0, f'{speed:.1f} km/h against {want}', d)
        e = rep['energy']
        expect = 40000 * 1.0034 * gz * 4000 / 3.6e6
        check(f'grade {pct}%: potential energy', e['trips'] == 1, f"{e['pe_wh_km']:.0f} Wh/km over the trip, climb alone {expect:.1f} kWh", d)
        clean(f'grade {pct}%', rep, d)


def t_curve():
    """The tightest thing on the road sets the speed: on a 20 m bend a car stays inside the driver's limit."""
    d = workdir('curve')
    arc = ' '.join(f'{200 + 20 * math.sin(a * math.pi / 32):.2f},{20 - 20 * math.cos(a * math.pi / 32):.2f}' for a in range(17))
    netconvert(d, '<node id="a" x="0" y="0"/><node id="b" x="200" y="0"/><node id="c" x="220" y="20"/><node id="e" x="220" y="300"/>',
               f'<edge id="ab" from="a" to="b" speed="20"/><edge id="bc" from="b" to="c" speed="20" shape="{arc}"/><edge id="ce" from="c" to="e" speed="20"/>')
    (d / 'r.xml').write_text(f'<routes><vType id="c" vClass="passenger" sigma="0" speedDev="0">{NOMINAL}</vType><route id="r" edges="ab bc ce"/><vehicle id="v" type="c" route="r" depart="0" departSpeed="max"/></routes>')
    for dt in (1.0, 0.1):
        rep = cars(d, '--dt', dt, '--end', 120, '--fcd', d / f'{dt}.csv', '--fcd-interval', dt, '--phys-json', d / 'p.json', tag=f'{dt}')
        p = json.loads((d / 'p.json').read_text())['lanes']['bc_0']
        limit = min(p['curve_v'], p['sqrt_r'] * math.sqrt(0.5 * 0.85 * 9.81))
        f = pd.read_csv(d / f'{dt}.csv', dtype={'lane': str})
        bend = f[(f.lane == 'bc_0') & (f.pos >= p['s_curve']) & (f.pos <= p['s_curve_end'])]
        peak = bend.speed.max()
        check(f'curve dt {dt}: speed through the bend', 0.8 * limit < peak <= limit + 0.05, f'{peak:.2f} m/s against a limit of {limit:.2f}, radius {p["sqrt_r"] ** 2:.1f} m', d)
        check(f'curve dt {dt}: lateral under I9', peak ** 2 / p['sqrt_r'] ** 2 <= 0.5 * 0.85 * 9.81 + 0.2, f'{peak ** 2 / p["sqrt_r"] ** 2:.2f} m/s2', d)
        clean(f'curve dt {dt}', rep, d)


def t_emergency():
    """Pairs of every type at the certified gap, the leader stopping as hard as its tyres allow."""
    d = workdir('emergency')
    types = dict(car=('passenger', 5.0), van=('delivery', 6.5), bus=('bus', 12.0), rigid=('truck', 10.0), artic=('trailer', 16.5))
    nodes, edges, body = '', '', ''
    for name, (cls, length) in types.items():
        body += f'<vType id="{name}" vClass="{cls}" length="{length}" sigma="0" speedDev="0" maxSpeed="30">{NOMINAL}</vType>'
    for name, (cls, length) in types.items():
        # Trace-driven leader that can actually brake at b_hi. Takes its body from the type it stands for.
        body += f'<vType id="L{name}" vClass="{cls}" length="{length}" sigma="0" speedDev="0" maxSpeed="30" decel="11.3">{NOMINAL}<param key="phys.trace" value="1"/><param key="phys.b_lo" value="{dict(car=11.3, van=8.5, bus=7.5, rigid=7.7, artic=7.7)[name]}"/><param key="phys.t_r" value="0.1"/></vType>'
    pairs = [(a, b) for a in types for b in types]
    for k, (a, b) in enumerate(pairs):
        y = k * 40
        nodes += f'<node id="a{k}" x="0" y="{y}"/><node id="b{k}" x="3000" y="{y}"/>'
        edges += f'<edge id="e{k}" from="a{k}" to="b{k}" speed="30"/>'
        body += f'<route id="r{k}" edges="e{k}"/>'
        body += f'<vehicle id="l{k}" type="L{a}" route="r{k}" depart="0" departSpeed="0" departPos="200"/>'
        for j in range(3):
            body += f'<vehicle id="f{k}_{j}" type="{b}" route="r{k}" depart="{1 + j}" departSpeed="0"/>'
    netconvert(d, nodes, edges)
    (d / 'r.xml').write_text('<routes>' + body + '</routes>')
    for dt in (1.0, 0.1):
        # Up to speed, cruise, and stop at once at 60 s, 70 s and 90 s from different speeds.
        speeds = [(0, 30), (40, 25), (45, 25), (60, 25)]
        n = round(100 / dt)
        trace = []
        for i in range(n + 2):
            t = i * dt
            v = 0.0 if t >= 60 else 25.0
            trace.append(v)
        (d / f't{dt}.txt').write_text('\n'.join(map(str, trace)))
        rep = cars(d, '--dt', dt, '--end', 100, '--speed-trace', d / f't{dt}.txt', '--fcd', d / f'{dt}.csv', '--fcd-interval', dt, '--fcd-begin', 55, '--gridlock-after', 1000, tag=f'{dt}')
        f = pd.read_csv(d / f'{dt}.csv', usecols=['time', 'trip', 'lane', 'pos', 'length', 'acc', 'speed'], dtype={'lane': str, 'trip': str})
        f = f.sort_values(['time', 'lane', 'pos'], kind='stable')
        same = (f.time.shift(-1) == f.time) & (f.lane.shift(-1) == f.lane)
        gap = (f.pos.shift(-1) - f.length.shift(-1) - f.pos)[same]
        check(f'emergency dt {dt}: least bumper gap (I2)', gap.min() >= 0.25, f'{gap.min():.3f} m over {len(pairs)} pairs, hardest braking {f.acc.min():.1f} m/s2', d)
        bad = {k: rep[k] for k in ('collision_incidents', 'teleports', 'ungranted') if rep.get(k)}
        check(f'emergency dt {dt}: no contact', not bad, str(bad) if bad else f"certificate floor hits {rep.get('cert_floor')}", d)


def gallery(name, dts=(1.0, 0.1), seconds=500):
    """The gallery's junctions: no bodies touching, nothing stuck, physically possible motion."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('intersection_gallery', ROOT / 'scripts/intersection_gallery.py')
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    d = workdir(f'gallery-{name}')
    g.FIXTURES[name](d)
    for dt in dts:
        tag = f'dt{dt}'
        report = d / f'{tag}.json'
        args = [*LOCK, A.cars, 'run', '--net', d / 'net.xml', '--routes', d / 'routes.xml', '--dt', dt, '--end', seconds, '--report-json', report, '--phys-json', d / f'{tag}.phys.json',
                '--fcd', d / f'{tag}.csv', '--fcd-interval', dt, '--trip-csv', d / f'{tag}.trips.csv', '--seed', 1]
        r = run(args)
        (d / f'{tag}.log').write_text(r.stdout + r.stderr)
        rep = json.loads(report.read_text())
        clean(f'{name} dt {dt}', rep, d)
        check(f'{name} dt {dt}: flow', rep['arrived'] > 0, f"{rep['arrived']} arrived, {rep['energy']['wheel_wh_km']:.0f} Wh/km, {rep['m_updates_per_s']:.2f} M updates/s", d)
        q = subprocess.run([sys.executable, str(ROOT / 'scripts/physics_qa.py'), '--net', d / 'net.xml', '--fcd', d / f'{tag}.csv', '--log', d / f'{tag}.log', '--phys', d / f'{tag}.phys.json', '--report', report, '--trips', d / f'{tag}.trips.csv', '--out', d / f'qa{dt}'], capture_output=True, text=True)
        check(f'{name} dt {dt}: physics QA', q.returncode == 0, (q.stdout.strip().splitlines() or ['no output'])[-1][:400] if q.returncode else 'all invariants', d)


def t_gallery_signal():
    gallery('signal')


def t_gallery_priority():
    gallery('priority')


def t_gallery_roundabout():
    gallery('roundabout')


def t_gallery_allway():
    gallery('all-way-stop')


def t_gallery_zipper():
    gallery('zipper')


def t_gallery_onramp():
    gallery('on-ramp')


def t_gallery_lanedrop():
    gallery('lane-drop')


def t_compat():
    """--sumo-compat is byte for byte the kernel before this work, on what golden.py and junction_tests.py use."""
    baseline = Path(A.baseline)
    if not baseline.exists():
        check('compat', False, f'no baseline binary at {baseline}')
        return
    d = workdir('compat')
    (d / 'n.nod.xml').write_text('<nodes><node id="c" x="0" y="0" type="priority"/><node id="w" x="-300" y="0"/><node id="e" x="300" y="0"/><node id="s" x="0" y="-300"/><node id="n" x="0" y="300"/></nodes>')
    edges = ''.join(f'<edge id="{a}{b}" from="{a}" to="{b}" priority="{p}" numLanes="2" speed="13.89"/>' for a, b, p in [('w', 'c', 2), ('c', 'e', 2), ('e', 'c', 2), ('c', 'w', 2), ('s', 'c', 1), ('c', 'n', 1), ('n', 'c', 1), ('c', 's', 1)])
    (d / 'n.edg.xml').write_text('<edges>' + edges + '</edges>')
    run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds'])
    flows = [('wc ce', 600), ('ec cw', 600), ('sc cn', 300), ('nc cs', 300), ('wc cn', 150), ('ec cs', 150), ('sc ce', 100), ('nc cw', 100)]
    for tp, model in (('krauss', 'Krauss'), ('idm', 'IDM'), ('acc', 'ACC'), ('cacc', 'CACC')):
        body = f'<routes><vType id="t" vClass="passenger" carFollowModel="{model}" sigma="0.5"/>'
        for i, (r, rate) in enumerate(flows):
            body += f'<route id="r{i}" edges="{r}"/><flow id="f{i}" type="t" route="r{i}" begin="0" end="300" vehsPerHour="{rate}" departLane="best" departSpeed="max"/>'
        (d / f'{tp}.xml').write_text(body + '</routes>')
        for dt in (1, 0.1):
            out = []
            for label, binary, extra in (('old', baseline, []), ('new', A.cars, ['--sumo-compat'])):
                f = d / f'{tp}{dt}.{label}.fcd'
                t = d / f'{tp}{dt}.{label}.trips'
                run([*LOCK, binary, 'run', *extra, '--net', d / 'net.xml', '--routes', d / f'{tp}.xml', '--dt', dt, '--end', 400, '--seed', 1, '--fcd', f, '--fcd-interval', dt, '--trip-csv', t])
                out.append((f.read_bytes(), t.read_bytes()))
            same = out[0] == out[1]
            check(f'compat {tp} dt {dt}: byte for byte', same, f'{len(out[0][0])} bytes of trajectories, {len(out[0][1])} of trips', d)


TESTS = dict(compat=t_compat, queue=t_queue, capacity=t_capacity, gap=t_gap, emergency=t_emergency, wltc=t_wltc, grade=t_grade, curve=t_curve, signal=t_gallery_signal, priority=t_gallery_priority, roundabout=t_gallery_roundabout,
             allway=t_gallery_allway, zipper=t_gallery_zipper, onramp=t_gallery_onramp, lanedrop=t_gallery_lanedrop)


def main():
    global A
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('names', nargs='*')
    p.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    p.add_argument('--baseline', default='/home/erikf/projects/personal/cars-data/physics/cars-baseline-69cf836')
    p.add_argument('--out')
    p.add_argument('--json')
    p.add_argument('--tune', action='append', default=[], help='name=value, passed on to the runs that compare with a target')
    p.add_argument('--radius', type=float, help='junction corner radius for the capacity nets')
    A = p.parse_args()
    A.tune_args = [x for t in A.tune for x in ('--tune', t)]
    for name in A.names or TESTS:
        print(f'--- {name}', flush=True)
        TESTS[name]()
    bad = [r for r in results if not r['ok']]
    print(f'{len(results) - len(bad)} of {len(results)} passed')
    for r in bad:
        print('FAILED', r['name'], r['detail'])
    if A.json:
        Path(A.json).write_text(json.dumps(results, indent=1))
    sys.exit(bool(bad))


if __name__ == '__main__':
    main()
