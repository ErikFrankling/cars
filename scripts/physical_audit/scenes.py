#!/usr/bin/env python3
"""Small scenes for the physical audit, built with netconvert into DIR/<scene>/.

    python3 scenes.py --out DIR [scene ...]

Vehicles carry no parameters of their own except vClass, so each driver shows its own defaults.
"""
import argparse
import math
import subprocess
from pathlib import Path

KMH = 1 / 3.6


def netconvert(d, nodes, edges, *extra):
    (d / 'n.nod.xml').write_text('<nodes>' + nodes + '</nodes>')
    (d / 'n.edg.xml').write_text('<edges>' + edges + '</edges>')
    subprocess.run(['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-turnarounds', '--no-warnings', *extra], check=True, capture_output=True)


def flow(id_, route, vph, end, extra=''):
    return f'<flow id="{id_}" route="{route}" begin="0" end="{end}" vehsPerHour="{vph}" departSpeed="max" departLane="best" {extra}/>'


def write_routes(d, body):
    (d / 'r.xml').write_text('<routes>' + body + '</routes>')


def tl(ids_states, offset=0):
    return ''.join(f'<tlLogic id="{i}" type="static" programID="audit" offset="{offset}">' + ''.join(f'<phase duration="{p}" state="{s}"/>' for p, s in phases) + '</tlLogic>' for i, phases in ids_states)


def signal(d):
    """One lane, 50 km/h, a fixed signal: stopping at a queue, launching, discharge, yellow."""
    nodes = '<node id="a" x="-1200" y="0"/><node id="t" x="0" y="0" type="traffic_light"/><node id="b" x="500" y="0"/>'
    edges = f'<edge id="in" from="a" to="t" numLanes="1" speed="{50*KMH:.3f}"/><edge id="out" from="t" to="b" numLanes="1" speed="{50*KMH:.3f}"/>'
    netconvert(d, nodes, edges)
    (d / 'add.xml').write_text('<additional>' + tl([('t', [(35, 'G'), (3, 'y'), (52, 'r')])]) + '</additional>')
    write_routes(d, '<route id="r" edges="in out"/>' + flow('f', 'r', 720, 1800))
    return dict(end=1800, additional='add.xml', green=[(90 * k) for k in range(21)], phase=dict(green=35, yellow=3, red=52))


def mix(d):
    """The same signal with vans, trucks, articulated trucks and buses."""
    r = signal(d)
    types = ''.join(f'<vType id="{c}" vClass="{v}"/>' for c, v in [('car', 'passenger'), ('van', 'delivery'), ('truck', 'truck'), ('artic', 'trailer'), ('bus', 'bus')])
    shares = dict(car=0.5, van=0.15, truck=0.15, artic=0.1, bus=0.1)
    fl = ''.join(flow(c, 'r', 600 * s, 1800, f'type="{c}"') for c, s in shares.items())
    write_routes(d, types + '<route id="r" edges="in out"/>' + fl)
    return r


def speeds(d):
    """Limits falling and rising on one lane, at light and near-capacity flow: free speed, time gaps, braking for a lower limit."""
    limits = [110, 70, 50, 30, 50, 70, 110]
    x, nodes, edges = 0, '<node id="n0" x="0" y="0"/>', ''
    for i, l in enumerate(limits):
        x += 1500 if l >= 70 else 800
        nodes += f'<node id="n{i+1}" x="{x}" y="0"/>'
        edges += f'<edge id="e{i}" from="n{i}" to="n{i+1}" numLanes="1" speed="{l*KMH:.3f}"/>'
    netconvert(d, nodes, edges)
    route = ' '.join(f'e{i}' for i in range(len(limits)))
    write_routes(d, f'<route id="r" edges="{route}"/>' + flow('f', 'r', 600, 900) + '<flow id="g" route="r" begin="900" end="1800" vehsPerHour="1500" departSpeed="max" departLane="best"/>')
    return dict(end=2400, limits=limits)


def free(d):
    """One vehicle every 40 s on each limit: free speed against the limit."""
    limits = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    nodes, edges, rf = '', '', ''
    for i, l in enumerate(limits):
        y = i * 200
        nodes += f'<node id="a{i}" x="0" y="{y}"/><node id="b{i}" x="1500" y="{y}"/>'
        edges += f'<edge id="e{i}" from="a{i}" to="b{i}" numLanes="1" speed="{l*KMH:.3f}"/>'
        rf += f'<route id="r{i}" edges="e{i}"/>' + flow(f'f{i}', f'r{i}', 90, 1200)
    netconvert(d, nodes, edges)
    write_routes(d, rf)
    return dict(end=1500, limits=limits)


def lanedrop(d):
    nodes = '<node id="a" x="-800" y="0"/><node id="m" x="0" y="0"/><node id="b" x="600" y="0"/>'
    edges = f'<edge id="in" from="a" to="m" numLanes="2" speed="{50*KMH:.3f}"/><edge id="out" from="m" to="b" numLanes="1" speed="{50*KMH:.3f}"/>'
    netconvert(d, nodes, edges)
    write_routes(d, '<route id="r" edges="in out"/>' + flow('f', 'r', 1100, 900))
    return dict(end=1000)


def merge(d):
    nodes = '<node id="a" x="-1500" y="0"/><node id="m" x="0" y="0"/><node id="e" x="250" y="0"/><node id="b" x="1500" y="0"/><node id="r" x="-600" y="-150"/>'
    edges = (f'<edge id="main" from="a" to="m" numLanes="2" speed="{110*KMH:.3f}"/>'
             f'<edge id="ramp" from="r" to="m" numLanes="1" speed="{70*KMH:.3f}"/>'
             f'<edge id="acc" from="m" to="e" numLanes="3" speed="{110*KMH:.3f}"/>'
             f'<edge id="out" from="e" to="b" numLanes="2" speed="{110*KMH:.3f}"/>')
    (d / 'n.con.xml').write_text('<connections>'
                                 '<connection from="main" to="acc" fromLane="0" toLane="1"/><connection from="main" to="acc" fromLane="1" toLane="2"/>'
                                 '<connection from="ramp" to="acc" fromLane="0" toLane="0"/>'
                                 '<connection from="acc" to="out" fromLane="1" toLane="0"/><connection from="acc" to="out" fromLane="2" toLane="1"/>'
                                 '</connections>')
    netconvert(d, nodes, edges, '-x', d / 'n.con.xml')
    write_routes(d, '<route id="m" edges="main acc out"/><route id="q" edges="ramp acc out"/>' + flow('f', 'm', 2600, 900) + flow('g', 'q', 500, 900))
    return dict(end=1000)


def junction(d):
    """A signalled crossroads, one lane each way, turns in all directions."""
    size = 400
    pts = dict(w=(-size, 0), e=(size, 0), s=(0, -size), n=(0, size))
    nodes = '<node id="c" x="0" y="0" type="traffic_light"/>' + ''.join(f'<node id="{k}" x="{x}" y="{y}"/>' for k, (x, y) in pts.items())
    edges = ''.join(f'<edge id="{k}c" from="{k}" to="c" numLanes="1" speed="{50*KMH:.3f}"/><edge id="c{k}" from="c" to="{k}" numLanes="1" speed="{50*KMH:.3f}"/>' for k in pts)
    netconvert(d, nodes, edges, '--tls.cycle.time', '60', '--tls.yellow.time', '3')
    rf, n = '', 0
    for a in pts:
        for b in pts:
            if a != b:
                rf += f'<route id="r{a}{b}" edges="{a}c c{b}"/>' + flow(f'f{a}{b}', f'r{a}{b}', 80, 1200)
    write_routes(d, rf)
    return dict(end=1300)


def priority(d):
    """The same crossroads, no signal, a major road: gap acceptance and give-way turns."""
    size = 400
    pts = dict(w=(-size, 0), e=(size, 0), s=(0, -size), n=(0, size))
    nodes = '<node id="c" x="0" y="0" type="priority"/>' + ''.join(f'<node id="{k}" x="{x}" y="{y}"/>' for k, (x, y) in pts.items())
    edges = ''
    for k in pts:
        pr = 3 if k in 'we' else 1
        edges += f'<edge id="{k}c" from="{k}" to="c" numLanes="1" speed="{50*KMH:.3f}" priority="{pr}"/><edge id="c{k}" from="c" to="{k}" numLanes="1" speed="{50*KMH:.3f}" priority="{pr}"/>'
    netconvert(d, nodes, edges)
    rf = ''
    for a in pts:
        for b in pts:
            if a != b:
                rf += f'<route id="r{a}{b}" edges="{a}c c{b}"/>' + flow(f'f{a}{b}', f'r{a}{b}', 40 if a in 'ns' else 90, 1200)
    write_routes(d, rf)
    return dict(end=1300)


def curves(d):
    """Open-road bends of known radius, at two limits, light traffic: cornering speed by radius."""
    nodes, edges, rf = '', '', ''
    k = 0
    info = {}
    for limit in (50, 90):
        for R in (10, 15, 20, 30, 50, 80, 120, 200, 350):
            y = k * 900
            lead = 400
            # A straight, a 90 degree arc, a straight.
            pts = [(0, y), (lead, y)]
            for i in range(1, 37):
                th = math.radians(i * 2.5)
                pts.append((lead + R * math.sin(th), y + R * (1 - math.cos(th))))
            xe, ye = pts[-1]
            pts.append((xe, ye + lead))
            shape = ' '.join(f'{px:.2f},{py:.2f}' for px, py in pts)
            nodes += f'<node id="a{k}" x="0" y="{y}"/><node id="b{k}" x="{xe:.2f}" y="{ye+lead:.2f}"/>'
            edges += f'<edge id="e{k}" from="a{k}" to="b{k}" numLanes="1" speed="{limit*KMH:.3f}" shape="{shape}"/>'
            rf += f'<route id="r{k}" edges="e{k}"/>' + flow(f'f{k}', f'r{k}', 60, 900)
            info[f'e{k}'] = dict(limit=limit, R=R, s0=lead, s1=lead + R * math.pi / 2)
            k += 1
    netconvert(d, nodes, edges)
    write_routes(d, rf)
    return dict(end=1100, bends=info)


def wall(d):
    """A signal turning red with no yellow, on roads of 30, 50, 70, 100 km/h: the hardest stop each driver will make."""
    nodes, edges, rf, add = '', '', '', []
    for i, l in enumerate((30, 50, 70, 100)):
        y = i * 300
        nodes += f'<node id="a{i}" x="-900" y="{y}"/><node id="t{i}" x="0" y="{y}" type="traffic_light"/><node id="b{i}" x="300" y="{y}"/>'
        edges += f'<edge id="in{i}" from="a{i}" to="t{i}" numLanes="1" speed="{l*KMH:.3f}"/><edge id="out{i}" from="t{i}" to="b{i}" numLanes="1" speed="{l*KMH:.3f}"/>'
        rf += f'<route id="r{i}" edges="in{i} out{i}"/>' + flow(f'f{i}', f'r{i}', 700, 1800)
        add.append((f't{i}', [(11, 'G'), (9, 'r')]))
    netconvert(d, nodes, edges)
    (d / 'add.xml').write_text('<additional>' + tl(add) + '</additional>')
    write_routes(d, rf)
    return dict(end=1900, additional='add.xml')


def wall2(d):
    """The same, with lone cars: 120 an hour, so nothing queues and every car meets the red at its own distance."""
    r = wall(d)
    body = (d / 'r.xml').read_text().replace('vehsPerHour="700"', 'vehsPerHour="150"')
    (d / 'r.xml').write_text(body)
    add = (d / 'add.xml').read_text().replace('duration="11"', 'duration="23"').replace('duration="9"', 'duration="17"')
    (d / 'add.xml').write_text(add)
    return r


SCENES = dict(wall2=wall2, signal=signal, mix=mix, speeds=speeds, free=free, lanedrop=lanedrop, merge=merge, junction=junction, priority=priority, curves=curves, wall=wall)


def main():
    import json
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('scenes', nargs='*')
    a = p.parse_args()
    for name in a.scenes or SCENES:
        d = Path(a.out) / name
        d.mkdir(parents=True, exist_ok=True)
        info = SCENES[name](d)
        (d / 'scene.json').write_text(json.dumps(info))
        print(name, info.get('end'))


if __name__ == '__main__':
    main()
