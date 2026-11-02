"""Shared paths and readers for the Berlin 2019 first gate. Run scripts with python3 -I."""
import gzip
import pickle
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

DATA = Path('/home/erikf/projects/personal/cars-data')
B19 = DATA / 'berlin2019'
RAW = B19 / 'raw'
STAMM = DATA / 'berlin-detectors/Stammdaten_Verkehrsdetektion_2022_07_20.xlsx'
MQ = DATA / 'datasets/berlin-2019-detectors/mq_hr_2019_05.csv.gz'
DET = DATA / 'datasets/berlin-2019-detectors/det_val_hr_2019_05.csv.gz'
COMPASS = dict(zip(['Nord', 'Nordost', 'Ost', 'Südost', 'Süd', 'Südwest', 'West', 'Nordwest'], range(0, 360, 45)))
# Berlin in May 2019: 1 May holiday, 30 May Ascension, 2 and 31 May next to a holiday, 26 May election Sunday.
NORMAL_DAYS = ['2019-05-07', '2019-05-08', '2019-05-09', '2019-05-14', '2019-05-15', '2019-05-16', '2019-05-21', '2019-05-22', '2019-05-23', '2019-05-28', '2019-05-29']
TEST_DAY = '2019-05-15'


def stammdaten():
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(STAMM) as z:
        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row', ns):
            rows.append({c.get('r').rstrip('0123456789'): strings[int(c.find('m:v', ns).text)] if c.get('t') == 's' else c.findtext('m:v', default='', namespaces=ns) for c in row})
    d = pd.DataFrame(rows[1:]).rename(columns={'A': 'site', 'B': 'det_old', 'C': 'det_new', 'D': 'det_id', 'F': 'street', 'G': 'position', 'H': 'pos_detail', 'I': 'direction', 'J': 'spur', 'K': 'annotation', 'L': 'lon', 'M': 'lat', 'N': 'installed', 'O': 'removed'})
    d['lon'] = pd.to_numeric(d.lon)
    d['lat'] = pd.to_numeric(d.lat)
    d['installed'] = pd.to_datetime(pd.to_numeric(d.installed, errors='coerce'), unit='D', origin='1899-12-30')
    d['removed'] = pd.to_datetime(pd.to_numeric(d.removed, errors='coerce'), unit='D', origin='1899-12-30')
    return d[['site', 'det_old', 'det_new', 'det_id', 'street', 'position', 'pos_detail', 'direction', 'spur', 'annotation', 'lon', 'lat', 'installed', 'removed']]


def read_net(path, cache=None):
    """Edges with every lane, as netconvert wrote them. Internal edges are left out."""
    path, cache = Path(path), Path(cache) if cache else None
    if cache and cache.exists() and cache.stat().st_mtime > path.stat().st_mtime:
        return pickle.loads(cache.read_bytes())
    location, edges, tls, conns, junctions = None, {}, 0, [], {}
    opener = gzip.open(path, 'rb') if str(path).endswith('.gz') else open(path, 'rb')
    with opener as f:
        for _, e in etree.iterparse(f, events=('end',), tag=('location', 'edge', 'tlLogic', 'connection', 'junction'), resolve_entities=False, no_network=True, huge_tree=True):
            if e.tag == 'location':
                location = dict(e.attrib)
            elif e.tag == 'edge' and e.get('function') != 'internal':
                lanes = []
                for l in e.findall('lane'):
                    lanes.append(dict(index=int(l.get('index')), speed=float(l.get('speed')), length=float(l.get('length')), allow=l.get('allow', ''), disallow=l.get('disallow', ''), width=float(l.get('width', 3.2)), shape=np.array([list(map(float, p.split(',')))[:2] for p in l.get('shape').split()])))
                edges[e.get('id')] = dict(id=e.get('id'), start=e.get('from'), end=e.get('to'), type=e.get('type', ''), name=e.get('name', ''), priority=int(e.get('priority', 0)), lanes=lanes)
            elif e.tag == 'tlLogic':
                tls += 1
            elif e.tag == 'connection' and not e.get('from', '').startswith(':'):
                conns.append((e.get('from'), e.get('to'), int(e.get('fromLane')), int(e.get('toLane')), e.get('tl', ''), e.get('dir', ''), e.get('state', ''), e.get('allow', ''), e.get('disallow', '')))
            elif e.tag == 'junction' and e.get('type') != 'internal':
                junctions[e.get('id')] = (e.get('type'), float(e.get('x')), float(e.get('y')))
            e.clear()
            while e.getprevious() is not None:
                del e.getparent()[0]
    out = dict(location=location, edges=edges, tls=tls, conns=conns, junctions=junctions)
    if cache:
        cache.write_bytes(pickle.dumps(out, protocol=4))
    return out


def car_lanes(edge):
    def ok(l):
        if l['allow']:
            return bool({'passenger', 'all'} & set(l['allow'].split()))
        return 'passenger' not in l['disallow'].split()
    return [l for l in edge['lanes'] if ok(l)]
