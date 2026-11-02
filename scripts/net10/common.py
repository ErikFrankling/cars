# Shared readers for the register-first net prototype (report data-hunt/10).
import json, re, math, collections
from pathlib import Path
from lxml import etree as E
from pyproj import Transformer
import numpy as np
DATA = Path('/home/erikf/projects/personal/cars-data')
WFS = DATA / 'truth/maps/wfs-20261031'
BOX = (18.018, 59.322, 18.085, 59.350)
T3011 = Transformer.from_crs('EPSG:3011', 'EPSG:4326', always_xy=True)

def in_box(lo, la, m=0.0):
    return BOX[0] - m <= lo <= BOX[2] + m and BOX[1] - m <= la <= BOX[3] + m

def register():
    """Installation id -> dict(all=[(lon,lat)], veh=[(lon,lat)], groups=set of F numbers), inside the box."""
    out = collections.defaultdict(lambda: dict(all=[], veh=[], groups=set()))
    for layer, key in (('Signallykta', 'anläggnings-id'), ('Signalstolpe', 'Anläggnings_id'), ('Tryckknapp', 'anläggnings-id')):
        for f in json.loads((WFS / f'{layer}.geojson').read_text())['features']:
            g = f['geometry']
            if not g or g['type'] != 'Point':
                continue
            p = f['properties']
            i = str(p.get(key)).lstrip('0')
            lo, la = T3011.transform(g['coordinates'][0], g['coordinates'][1])
            if not in_box(lo, la):
                continue
            d = out[i]
            d['all'].append((lo, la))
            if layer == 'Signallykta':
                nm = p.get('namn') or ''
                ty = (p.get('typ') or '').lower()
                if nm.startswith('Fordon') or ty.startswith(('fordon', 'bil', 'buss', 'k')):
                    d['veh'].append((lo, la))
                    m = re.search(r'\b(F\d+)', nm)
                    if m:
                        d['groups'].add(m.group(1))
    return dict(out)

def nvdb_signal():
    o = []
    for f in json.loads((WFS / 'NVDB_Korsning.geojson').read_text())['features']:
        g = f['geometry']
        if g and g['type'] == 'Point' and f['properties'].get('Signalreglering') == 'ja':
            lo, la = T3011.transform(g['coordinates'][0], g['coordinates'][1])
            if in_box(lo, la, 0.001):
                o.append((lo, la))
    return o

def tf_from_location(loc):
    ox, oy = map(float, loc['netOffset'].split(','))
    f = Transformer.from_crs('EPSG:4326', loc['projParameter'], always_xy=True)
    b = Transformer.from_crs(loc['projParameter'], 'EPSG:4326', always_xy=True)
    def fwd(lo, la):
        x, y = f.transform(lo, la)
        return x + ox, y + oy
    def back(x, y):
        return b.transform(x - ox, y - oy)
    return fwd, back

def parse_shape(s):
    return [tuple(map(float, p.split(',')[:2])) for p in s.split()]

def plen(s):
    return sum(math.dist(a, b) for a, b in zip(s, s[1:]))

def load_net(path):
    n = dict(edges={}, junctions={}, tls={}, conns=[], location=None, internal={})
    for e in E.parse(str(path)).getroot():
        a = e.attrib
        if e.tag == 'location':
            n['location'] = dict(a)
        elif e.tag == 'edge':
            if a.get('function') == 'internal':
                for l in e.findall('lane'):
                    n['internal'][l.get('id')] = float(l.get('length'))
                continue
            n['edges'][a['id']] = dict(frm=a.get('from'), to=a.get('to'), name=a.get('name', ''), type=a.get('type', ''), lanes=[
                dict(i=int(l.get('index')), length=float(l.get('length')), speed=float(l.get('speed')), allow=l.get('allow'), disallow=l.get('disallow'), shape=parse_shape(l.get('shape'))) for l in e.findall('lane')])
        elif e.tag == 'junction':
            if a.get('type') != 'internal':
                n['junctions'][a['id']] = dict(type=a['type'], x=float(a['x']), y=float(a['y']), shape=parse_shape(a.get('shape', '')) if a.get('shape') else [])
        elif e.tag == 'tlLogic':
            n['tls'][a['id']] = dict(offset=float(a.get('offset', 0)), type=a.get('type'), phases=[(float(p.get('duration')), p.get('state')) for p in e.findall('phase')])
        elif e.tag == 'connection':
            if not a['from'].startswith(':'):
                n['conns'].append(dict(frm=a['from'], to=a['to'], fl=int(a['fromLane']), tl=int(a['toLane']), dir=a.get('dir'), state=a.get('state'), tls=a.get('tl'), li=int(a.get('linkIndex', -1)), via=a.get('via'), allow=a.get('allow'), disallow=a.get('disallow')))
    return n

def passenger(l):
    al, dis = l['allow'], l['disallow']
    if al is not None:
        return 'passenger' in al.split() or 'all' in al.split()
    return dis is None or 'passenger' not in dis.split()
