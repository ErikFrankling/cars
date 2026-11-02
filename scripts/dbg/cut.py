"""`cars cut`: a small scene around one place of a city recipe: the net inside a box, and the part of each trip inside it, at about the time it gets there. For studying a seed tick by tick on llvmpipe, when a city will not fit it or the GPU is taken. Traffic that a jam elsewhere would have held back comes through, so a cut shows mechanisms, not city totals."""
import argparse
import gzip
import os
import re
import subprocess
import xml.etree.ElementTree as ET


def edge_times(net):
    t = {}
    for _, el in ET.iterparse(net, events=('end',)):
        if el.tag == 'edge':
            if el.get('function') != 'internal':
                lane = el.find('lane')
                if lane is not None:
                    t[el.get('id')] = float(lane.get('length')) / max(float(lane.get('speed')), 1.0)
            el.clear()
    return t


def opener(path):
    return gzip.open(path, 'rt') if path.endswith('.gz') else open(path)


def main(argv):
    a = argparse.ArgumentParser(prog='cars cut', description=__doc__)
    a.add_argument('--net', required=True)
    a.add_argument('--routes', required=True)
    a.add_argument('--center', required=True, help='x,y in net metres')
    a.add_argument('--radius', type=float, default=800.0)
    a.add_argument('--begin', type=float, required=True, help='simulation seconds: cars reaching the box from here on')
    a.add_argument('--end', type=float, required=True)
    a.add_argument('--scale', type=float, default=1.0, help='keep this share of the trips')
    a.add_argument('--out', required=True, help='directory for net.xml and routes.xml')
    a = a.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    x, y = (float(v) for v in a.center.split(','))
    box = f'{x - a.radius},{y - a.radius},{x + a.radius},{y + a.radius}'
    net = os.path.join(a.out, 'net.xml')
    if not os.path.exists(net):
        subprocess.run(['netconvert', '-s', a.net, '--keep-edges.in-boundary', box, '--keep-edges.components', '1', '--no-warnings', 'true', '-o', net], check=True)
    root = ET.parse(net).getroot()
    keep = {e.get('id') for e in root.findall('edge') if e.get('function') != 'internal'}
    conn = {}
    for c in root.findall('connection'):
        conn.setdefault(c.get('from'), set()).add(c.get('to'))
    times = edge_times(a.net)
    types, out, routes = [], [], {}
    total = 0
    step = 0.0
    with opener(a.routes) as f:
        for line in f:
            s = line.strip()
            if s.startswith('<vType'):
                types.append(s if s.endswith('/>') else s)
            elif s.startswith('<route '):
                m = re.search(r'id="([^"]+)" edges="([^"]+)"', s)
                if m:
                    routes[m.group(1)] = m.group(2).split()
            elif s.startswith('<vehicle'):
                total += 1
                depart = re.search(r'depart="([\d.]+)"', s)
                if not depart:
                    continue
                d = float(depart.group(1))
                # Long trips reach the box long after they depart; 1.3 times free flow is near enough.
                if d > a.end:
                    continue
                r = re.search(r'route="([^"]+)"', s)
                if r:
                    edges = routes.get(r.group(1), [])
                else:
                    inner = re.search(r'edges="([^"]+)"', s)
                    if not inner:
                        inner = re.search(r'edges="([^"]+)"', next(f))
                    edges = inner.group(1).split() if inner else []
                i = next((k for k, e in enumerate(edges) if e in keep), None)
                if i is None:
                    continue
                t = d + 1.3 * sum(times.get(e, 0.0) for e in edges[:i])
                if not a.begin <= t < a.end:
                    continue
                piece = [edges[i]]
                for e in edges[i + 1:]:
                    if e in keep:
                        if e not in conn.get(piece[-1], ()):
                            break
                        piece.append(e)
                    elif times.get(e, 99.0) > 8.0:
                        break
                if len(piece) < 2:
                    continue
                step += a.scale
                if step >= 1.0:
                    step -= 1.0
                    vt = re.search(r' type="([^"]+)"', s)
                    out.append((t - a.begin, piece, vt.group(1) if vt else None))
    out.sort(key=lambda p: p[0])
    path = os.path.join(a.out, 'routes.xml')
    with open(path, 'w') as f:
        f.write('<routes>\n')
        for t in types:
            f.write(t + '\n')
        for n, (t, e, vt) in enumerate(out):
            ty = f' type="{vt}"' if vt else ''
            f.write(f'<vehicle id="v{n}"{ty} depart="{t:.1f}" departLane="best" departSpeed="max"><route edges="{" ".join(e)}"/></vehicle>\n')
        f.write('</routes>\n')
    span = a.end - a.begin
    print(f'{len(keep)} edges in the box, {len(out)} of {total} trips cross it in those {span:.0f} s')
    print(f'CARS_ADAPTER=llvmpipe VK_ICD_FILENAMES=/run/opengl-driver/share/vulkan/icd.d/lvp_icd.x86_64.json cars run --net {net} --routes {path} --dt 1 --begin 0 --end {span:.0f} --time-to-teleport 0 --ignore-junction-blocker 20 --trace {a.out}/f.trace --why')
