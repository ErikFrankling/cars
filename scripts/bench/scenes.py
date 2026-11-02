"""Test scenes. A scene supplies only measured inputs: geometry, demand, signals. Driver numbers come from the
config alone, and `check_clean` refuses a scene file that carries any."""
import math
import re
import subprocess
from pathlib import Path

import numpy as np

DRIVER_ATTRS = re.compile(r'\b(tau|sigma|accel|decel|emergencyDecel|apparentDecel|carFollowModel|lc[A-Z][A-Za-z]*|speedFactor|speedDev|minGap)=')
RIG_ID = 'head'


def netconvert(d, nodes, edges, *extra, con=None):
    (d / 'n.nod.xml').write_text('<nodes>' + nodes + '</nodes>')
    (d / 'n.edg.xml').write_text('<edges>' + edges + '</edges>')
    cmd = ['netconvert', '-n', str(d / 'n.nod.xml'), '-e', str(d / 'n.edg.xml'), '-o', str(d / 'net.xml'), '--no-turnarounds', 'true', *extra]
    if con:
        (d / 'n.con.xml').write_text('<connections>' + con + '</connections>')
        cmd += ['-x', str(d / 'n.con.xml')]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-2000:])


def block_changes(d):
    """Known-bad 7: no lane may change, written into the net as SUMO's lane permissions."""
    p = d / 'net.xml'
    p.write_text(re.sub(r'<lane ', '<lane changeLeft="" changeRight="" ', p.read_text()))


def vtype(cfg, ov):
    length = ov.get('length', 5.0)
    extra = ov.get('vtype', cfg['vtype'])
    tau = f' tau="{ov["tau"]}"' if 'tau' in ov else ''
    sf = f' speedFactor="{ov["speed_factor"]}"' if 'speed_factor' in ov else ''
    return f'<vType id="car" length="{length}" minGap="2.5" speedDev="0.1" {extra}{tau}{sf}/>'


def routes(d, cfg, ov, body, name='r.xml', extra_types=''):
    p = d / name
    check_clean(body)
    p.write_text('<routes>' + vtype(cfg, ov) + extra_types + body + '</routes>')
    return p


def check_clean(body):
    m = DRIVER_ATTRS.search(body)
    if m:
        raise SystemExit(f'scene carries a driver parameter, {m.group(0)}: one configuration, no per-scene dials')


def flow(id_, route, begin, end, vph, ov, lane='best'):
    vph = vph * ov.get('demand_scale', 1.0)
    return f'<flow id="{id_}" type="car" route="{route}" begin="{begin}" end="{end}" vehsPerHour="{vph:.1f}" departLane="{lane}" departSpeed="max"/>'


def road(d, cfg, ov, fast, seed):
    """A motorway section with a lane drop: free flow upstream and downstream, a queue behind the drop."""
    if not (d / 'net.xml').exists():
        netconvert(d, '<node id="a" x="0" y="0"/><node id="b" x="3000" y="0"/><node id="c" x="3400" y="0"/><node id="e" x="5400" y="0"/>',
                   '<edge id="A" from="a" to="b" numLanes="3" speed="33"/><edge id="B" from="b" to="c" numLanes="2" speed="33"/><edge id="C" from="c" to="e" numLanes="2" speed="33"/>')
        if ov.get('no_lc'):
            block_changes(d)
    end = 600 if fast else 1200
    r = routes(d, cfg, ov, '<route id="r" edges="A B C"/>' + flow('f', 'r', 0, end, 6600, ov))
    return dict(routes=r, end=end + 60, fcd=.5, planned=6600 * ov.get('demand_scale', 1.0) * end / 3600)


def free3(d, cfg, ov, fast, seed):
    """Three free lanes, for discretionary lane changes and free speeds."""
    if not (d / 'net.xml').exists():
        netconvert(d, '<node id="a" x="0" y="0"/><node id="b" x="4000" y="0"/>', '<edge id="m" from="a" to="b" numLanes="3" speed="33"/>')
        if ov.get('no_lc'):
            block_changes(d)
    end = 300 if fast else 900
    r = routes(d, cfg, ov, '<route id="r" edges="m"/>' + flow('f', 'r', 0, end, 3600, ov, lane='free'))
    return dict(routes=r, end=end + 150, fcd=.5, planned=3600 * ov.get('demand_scale', 1.0) * end / 3600)


CYCLE = (30.0, 3.0, 57.0)


def _tl(d, phases):
    import xml.etree.ElementTree as ET
    root = ET.parse(d / 'net.xml').getroot()
    n = len(root.find('tlLogic').find('phase').get('state'))
    idx = {c.get('linkIndex'): c.get('from') for c in root.iter('connection') if c.get('tl') == 't'}
    st = lambda ci, cx: ''.join(ci if idx.get(str(i)) == 'in' else cx for i in range(n))
    return '<additional><tlLogic id="t" type="static" programID="fix" offset="0">' + ''.join(f'<phase duration="{p}" state="{st(a, b)}"/>' for p, a, b in phases) + '</tlLogic></additional>'


def signal(d, cfg, ov, fast, seed, cycle=CYCLE, vph=600, name='tl.xml', dur=None, drain=300):
    """One approach at a signal, enough arrivals to queue every cycle. Green begins at multiples of the cycle."""
    if not (d / 'net.xml').exists():
        typ = '' if ov.get('signals') == 'none' else ' type="traffic_light"'
        netconvert(d, f'<node id="a" x="-500" y="0"/><node id="t" x="0" y="0"{typ}/><node id="b" x="500" y="0"/><node id="c" x="0" y="-300"/><node id="e" x="0" y="300"/>',
                   '<edge id="in" from="a" to="t" numLanes="1" speed="13.89"/><edge id="out" from="t" to="b" numLanes="1" speed="13.89"/><edge id="cross" from="c" to="t" numLanes="1" speed="13.89"/><edge id="crossout" from="t" to="e" numLanes="1" speed="13.89"/>',
                   '--no-left-connections', 'true')
    add = []
    if ov.get('signals') != 'none':
        g, y, r_ = cycle
        if ov.get('signals') == 'fixed90':
            g, y, r_ = 43.5, 3.0, 43.5
        # Green for the approach first: a time t in the green has t mod cycle < g.
        (d / name).write_text(_tl(d, [(g, 'G', 'r'), (y, 'y', 'r'), (r_, 'r', 'G')]))
        add = [d / name]
    dur = dur or (720 if fast else 2700)
    r = routes(d, cfg, ov, '<route id="r" edges="in out"/>' + flow('f', 'r', 0, dur, vph, ov))
    return dict(routes=r, add=add, end=dur + drain, demand_end=dur, fcd=.2, cycle=sum(cycle) if ov.get('signals') != 'fixed90' else 90.0, green=cycle[0] if ov.get('signals') != 'fixed90' else 43.5, planned=vph * ov.get('demand_scale', 1.0) * dur / 3600)


def signal_real(d, cfg, ov, fast, seed, real=None):
    """As `signal`, with DLR UT's own cycle, split and per-lane flow, for the delay distribution."""
    real = real or dict(cycle=90.0, green=40.0, vph=300)
    c = real['cycle']
    g = real['green']
    return signal(d, cfg, ov, fast, seed, cycle=(g, 3.0, c - g - 3.0), vph=real['vph'], name='tl_real.xml', dur=600 if fast else 3600, drain=120)


def yellow(d, cfg, ov, fast, seed):
    if not (d / 'net.xml').exists():
        typ = '' if ov.get('signals') == 'none' else ' type="traffic_light" tl="t"'
        netconvert(d, f'<node id="a" x="-600" y="0"/><node id="t" x="0" y="0"{typ}/><node id="b" x="400" y="0"/>',
                   '<edge id="in" from="a" to="t" numLanes="1" speed="13.89"/><edge id="out" from="t" to="b" numLanes="1" speed="13.89"/>')
    add = []
    if ov.get('signals') != 'none':
        (d / 'tl.xml').write_text('<additional><tlLogic id="t" type="static" programID="x" offset="0"><phase duration="27" state="G"/><phase duration="3" state="y"/><phase duration="20" state="r"/></tlLogic></additional>')
        add = [d / 'tl.xml']
    dur = 800 if fast else 3000
    r = routes(d, cfg, ov, '<route id="r" edges="in out"/>' + flow('f', 'r', 0, dur, 900, ov))
    return dict(routes=r, add=add, end=dur, fcd=.2, planned=900 * ov.get('demand_scale', 1.0) * dur / 3600)


def roundabout(d, cfg, ov, fast, seed):
    if not (d / 'net.xml').exists():
        rad, arms = 18.0, 4
        nodes, edges = '', ''
        for i in range(arms):
            a = i * 2 * math.pi / arms
            nodes += f'<node id="j{i}" x="{rad * math.cos(a):.2f}" y="{rad * math.sin(a):.2f}" type="priority"/><node id="o{i}" x="{300 * math.cos(a):.2f}" y="{300 * math.sin(a):.2f}"/>'
            edges += f'<edge id="in{i}" from="o{i}" to="j{i}" numLanes="1" speed="13.89"/><edge id="out{i}" from="j{i}" to="o{i}" numLanes="1" speed="13.89"/>'
            b = (i + 1) % arms
            pts = ' '.join(f'{rad * math.cos(a + k / 8 * 2 * math.pi / arms):.2f},{rad * math.sin(a + k / 8 * 2 * math.pi / arms):.2f}' for k in range(9))
            edges += f'<edge id="ring{i}" from="j{i}" to="j{b}" numLanes="1" speed="8.33" priority="3" shape="{pts}"/>'
        rb = ' '.join(f'ring{i}' for i in range(arms))
        nd = ' '.join(f'j{i}' for i in range(arms))
        nodes += f'<roundabout nodes="{nd}" edges="{rb}"/>'
        netconvert(d, nodes, edges)
    dur = 900 if fast else 1800
    q = 300 * ov.get('demand_scale', 1.0)
    rng = np.random.default_rng(seed)
    rows = []
    for arm in range(4):
        for t in np.cumsum(rng.exponential(3600 / q, int(dur * q / 3600 * 1.3))):
            if t >= dur:
                break
            ex = (arm + rng.integers(1, 4)) % 4
            ring = ' '.join(f'ring{(arm + k) % 4}' for k in range(0, (ex - arm) % 4))
            rows.append((t, f'<vehicle id="a{arm}_{t:.1f}" type="car" depart="{t:.1f}" departSpeed="max"><route edges="in{arm} {ring} out{ex}"/></vehicle>'))
    rows.sort()
    r = routes(d, cfg, ov, ''.join(x[1] for x in rows), name=f'r{seed}.xml')
    return dict(routes=r, end=dur + 120, fcd=.2, planned=len(rows))


def ramp(d, cfg, ov, fast, seed):
    """On-ramp with an acceleration lane. Fast: steady demand for merge manoeuvres. Full: rising demand until it breaks down."""
    if not (d / 'net.xml').exists():
        netconvert(d, '<node id="a" x="0" y="0"/><node id="r" x="1500" y="-60"/><node id="b" x="2000" y="0"/><node id="c" x="2300" y="0"/><node id="e" x="3800" y="0"/>',
                   '<edge id="up" from="a" to="b" numLanes="2" speed="29"/><edge id="on" from="r" to="b" numLanes="1" speed="22"/><edge id="merge" from="b" to="c" numLanes="3" speed="29"/><edge id="down" from="c" to="e" numLanes="2" speed="29"/>',
                   con='<connection from="up" to="merge" fromLane="0" toLane="1"/><connection from="up" to="merge" fromLane="1" toLane="2"/><connection from="on" to="merge" fromLane="0" toLane="0"/><connection from="merge" to="down" fromLane="1" toLane="0"/><connection from="merge" to="down" fromLane="2" toLane="1"/>')
        if ov.get('no_lc'):
            block_changes(d)
    body = '<route id="rm" edges="up merge down"/><route id="rr" edges="on merge down"/>'
    if fast:
        body += flow('m', 'rm', 0, 540, 3000, ov, lane='free') + flow('o', 'rr', 0, 540, 700, ov, lane='0')
        return dict(routes=routes(d, cfg, ov, body), end=600, fcd=.5, steps=None, planned=(3700 * ov.get('demand_scale', 1.0)) * 540 / 3600)
    t = 0
    planned = 0
    for k, main in enumerate(range(2000, 4601, 400)):
        body += flow(f'm{k}', 'rm', t, t + 600, main, ov, lane='free') + flow(f'o{k}', 'rr', t, t + 600, 500, ov, lane='0')
        planned += (main + 500) * ov.get('demand_scale', 1.0) * 600 / 3600
        t += 600
    return dict(routes=routes(d, cfg, ov, body), end=t + 300, fcd=.5, steps=600, planned=planned)


def chain(d, cfg, ov, fast, seed, heads=None):
    """Eight cars behind a head that drives a real recorded leader's speed. The rig encodes the speed in each edge's
    limit, the head follows it, and followers get a high speed factor so that only the head sees the limits."""
    heads = heads or {}
    prof = sum((heads[(seed + k) % len(heads)] for k in range(4)), []) if heads else [10 + 3 * math.sin(i / 8) for i in range(240)]
    if not (d / f'net{seed}.xml').exists():
        s, nodes, edges, cuts = 0.0, '<node id="n0" x="0" y="0"/>', '', []
        k, acc = 0, 0.0
        step = 10
        for i in range(0, len(prof), step):
            v = max(float(np.mean(prof[i:i + step])), 3.0)
            dist = v * step
            s += dist
            nodes += f'<node id="n{k + 1}" x="{s:.1f}" y="0"/>'
            edges += f'<edge id="e{k}" from="n{k}" to="n{k + 1}" numLanes="1" speed="{v:.2f}"/>'
            k += 1
        nodes += f'<node id="n{k + 1}" x="{s + 1000:.1f}" y="0"/>'
        edges += f'<edge id="e{k}" from="n{k}" to="n{k + 1}" numLanes="1" speed="30"/>'
        k += 1
        netconvert(d, nodes, edges, '--no-internal-links', 'true', '--geometry.remove', 'false', '--junctions.join', 'false')
        (d / f'net{seed}.xml').write_bytes((d / 'net.xml').read_bytes())
        (d / f'edges{seed}.txt').write_text(str(k))
    n = int((d / f'edges{seed}.txt').read_text())
    route = ' '.join(f'e{i}' for i in range(n))
    head = '<vType id="head" length="5" speedDev="0" accel="2.6" decel="4.5"/>'
    types = head + vtype(cfg, ov).replace('id="car"', 'id="foll"').replace('speedDev="0.1"', 'speedDev="0" speedFactor="3"')
    body = f'<route id="r" edges="{route}"/><vehicle id="h" type="head" depart="0" departSpeed="max" route="r"/>'
    for i in range(1, 9):
        body += f'<vehicle id="c{i}" type="foll" depart="{i * 2.5:.1f}" departSpeed="max" route="r"/>'
    (d / f'r{seed}.xml').write_text('<routes>' + vtype(cfg, ov) + types + body + '</routes>')
    return dict(routes=d / f'r{seed}.xml', net=d / f'net{seed}.xml', end=len(prof) + 60, fcd=.5, planned=9)


def crossing(d, cfg, ov, fast, seed, typ='traffic_light', major=300, minor=150, name='junction4'):
    """A plain four-arm junction with turning traffic. Report 25's typical flows, generic geometry. Two lanes on signal approaches."""
    if not (d / 'net.xml').exists():
        lanes = 2 if typ == 'traffic_light' else 1
        L = 400
        nodes = f'<node id="c" x="0" y="0" type="{typ if ov.get("signals") != "none" else "priority"}"/>' + ''.join(f'<node id="{k}" x="{x}" y="{y}"/>' for k, x, y in (('w', -L, 0), ('e', L, 0), ('s', 0, -L), ('n', 0, L)))
        edges = ''
        for k in 'wesn':
            pr = 2 if k in 'we' else 1
            edges += f'<edge id="{k}i" from="{k}" to="c" numLanes="{lanes}" speed="13.89" priority="{pr}"/><edge id="{k}o" from="c" to="{k}" numLanes="{lanes}" speed="13.89" priority="{pr}"/>'
        extra = ['--tls.green.time', '40', '--tls.yellow.time', '3'] if typ == 'traffic_light' else []
        netconvert(d, nodes, edges, *extra)
        if ov.get('no_lc'):
            block_changes(d)
    dur = (600 if typ == 'traffic_light' else 1200) if fast else 2700
    body = ''
    turns = dict(w=('eo', 'no', 'so'), e=('wo', 'so', 'no'), s=('no', 'eo', 'wo'), n=('so', 'wo', 'eo'))
    for k, (t, le, ri) in turns.items():
        q = major if k in 'we' else minor
        for j, (o, sh) in enumerate(((t, .7), (le, .15), (ri, .15))):
            body += f'<route id="r{k}{j}" edges="{k}i {o}"/>' + flow(f'f{k}{j}', f'r{k}{j}', 0, dur, q * sh, ov)
    return dict(routes=routes(d, cfg, ov, body), end=dur + 150, fcd=.2, planned=(2 * major + 2 * minor) * dur / 3600 * ov.get('demand_scale', 1.0), span=dur)


def junction4(d, cfg, ov, fast, seed):
    return crossing(d, cfg, ov, fast, seed, 'traffic_light', 800, 600)


def stopsign(d, cfg, ov, fast, seed):
    return crossing(d, cfg, ov, fast, seed, 'priority_stop', 300, 150)


def giveway(d, cfg, ov, fast, seed):
    return crossing(d, cfg, ov, fast, seed, 'priority', 300, 150)


def allway(d, cfg, ov, fast, seed):
    return crossing(d, cfg, ov, fast, seed, 'allway_stop', 76, 76)


def lanedrop(d, cfg, ov, fast, seed):
    """An auxiliary lane that ends, in congestion: I-80 and I-395's shape, for merge position and the zipper proxy."""
    if not (d / 'net.xml').exists():
        netconvert(d, '<node id="a" x="0" y="0"/><node id="b" x="300" y="0"/><node id="c" x="600" y="0"/><node id="e" x="1400" y="0"/>',
                   '<edge id="up" from="a" to="b" numLanes="2" speed="20"/><edge id="aux" from="b" to="c" numLanes="2" speed="20"/><edge id="down" from="c" to="e" numLanes="1" speed="20"/>',
                   con='<connection from="up" to="aux" fromLane="0" toLane="0"/><connection from="up" to="aux" fromLane="1" toLane="1"/><connection from="aux" to="down" fromLane="1" toLane="0"/>')
        if ov.get('no_lc'):
            block_changes(d)
    dur = 480 if fast else 1500
    return dict(routes=routes(d, cfg, ov, '<route id="r" edges="up aux down"/>' + flow('f', 'r', 0, dur, 2800, ov, lane='free')), end=dur + 60, fcd=.5, planned=2800 * dur / 3600 * ov.get('demand_scale', 1.0), aux_len=300.0)


BENDS = (15, 20, 30, 50)


def curves(d, cfg, ov, fast, seed):
    """Open-road bends of known radius on a 50 km/h road, light traffic: straight, 90 degree arc, straight. As report 19."""
    if not (d / 'net.xml').exists():
        nodes, edges = '', ''
        for k, r_ in enumerate(BENDS):
            y = k * 500
            pts = [(0, y), (300, y)]
            for i in range(1, 37):
                th = math.radians(i * 2.5)
                pts.append((300 + r_ * math.sin(th), y + r_ * (1 - math.cos(th))))
            xe, ye = pts[-1]
            pts.append((xe, ye + 300))
            shape = ' '.join(f'{a:.2f},{b:.2f}' for a, b in pts)
            nodes += f'<node id="a{k}" x="0" y="{y}"/><node id="b{k}" x="{xe:.2f}" y="{ye + 300:.2f}"/>'
            edges += f'<edge id="e{k}" from="a{k}" to="b{k}" numLanes="1" speed="13.89" shape="{shape}"/>'
        netconvert(d, nodes, edges)
    dur = 240 if fast else 600
    body = ''
    for k in range(len(BENDS)):
        body += f'<route id="r{k}" edges="e{k}"/>' + flow(f'f{k}', f'r{k}', 0, dur, 120, ov)
    return dict(routes=routes(d, cfg, ov, body), end=dur + 90, fcd=.5, planned=4 * 120 * dur / 3600)


def ring(d, cfg, ov, fast, seed):
    """Fixed density on a closed two-lane loop, for drift over hours: no insertion, no arrival."""
    L, n = 2000.0, 80
    if not (d / 'net.xml').exists():
        r = L / (2 * math.pi)
        nodes = ''.join(f'<node id="n{i}" x="{r * math.cos(i * math.pi / 2):.3f}" y="{r * math.sin(i * math.pi / 2):.3f}"/>' for i in range(4))
        edges = ''
        for i in range(4):
            pts = ' '.join(f'{r * math.cos((i + k / 8) * math.pi / 2):.3f},{r * math.sin((i + k / 8) * math.pi / 2):.3f}' for k in range(9))
            edges += f'<edge id="e{i}" from="n{i}" to="n{(i + 1) % 4}" numLanes="2" speed="20" shape="{pts}"/>'
        netconvert(d, nodes, edges, '--no-internal-links', 'true')
    veh = ''
    length = L / 4
    hours = 1 if fast else 6
    reps = int(hours * 3600 * 25 / L) + 4
    for k in range(n):
        s = k * L / n
        edge = int(s // length)
        pos = s - edge * length + 5.1
        if pos > length:
            edge, pos = (edge + 1) % 4, pos - length
        rt = ' '.join(f'e{(edge + i) % 4}' for i in range(4 * reps))
        veh += f'<vehicle id="v{k}" type="car" depart="0" departPos="{pos:.2f}" departSpeed="4" departLane="{k % 2}"><route edges="{rt}"/></vehicle>'
    r = routes(d, cfg, ov, veh, name=f'r{seed}.xml')
    return dict(routes=r, end=hours * 3600, fcd=5.0, planned=n)


def lane_offsets(net):
    import xml.etree.ElementTree as ET
    out, s = {}, 0.0
    edges = [e for e in ET.parse(net).getroot().iter('edge') if e.get('function') != 'internal']
    edges.sort(key=lambda e: int(e.get('id')[1:]))
    for e in edges:
        for l in e.iter('lane'):
            out[l.get('id')] = s
            s += float(l.get('length'))
    return out


SCENES = dict(road=road, free3=free3, signal=signal, signal_real=signal_real, yellow=yellow, roundabout=roundabout, ramp=ramp, chain=chain, ring=ring, curves=curves, junction4=junction4, stopsign=stopsign, giveway=giveway, allway=allway, lanedrop=lanedrop)
