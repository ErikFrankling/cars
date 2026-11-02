#!/usr/bin/env python3
"""Road graph for the MeTS-10 spatial join: the sim's own edges in WGS84, so probe speeds land per edge.

Writes t4c_job/edges.csv.gz. Every edge is directed, with its own two nodes at its ends. Main roads across
Berlin, plus all car edges of the district. Only geometry and limits: no probe data here.
"""
import csv
import gzip
import json
import pickle
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from pyproj import Transformer

net = pickle.loads((B19 / 'step0/net_berlin.pkl').read_bytes())
box = json.load(open(B19 / 'step0/district.json'))['box']
off = np.array(list(map(float, net['location']['netOffset'].split(','))))
tr = Transformer.from_crs(net['location']['projParameter'], 'EPSG:4326', always_xy=True)
n = 0
with gzip.open(B19 / 't4c_job/edges.csv.gz', 'wt') as f:
    w = csv.writer(f)
    w.writerow(['gkey', 'highway', 'lanes', 'speed_kph', 'length_m', 'wkt'])
    for k, e in net['edges'].items():
        cl = car_lanes(e)
        if not cl or k.startswith(':'):
            continue
        s = cl[len(cl) // 2]['shape']
        mid = s.mean(axis=0)
        t = e['type'].replace('highway.', '')
        in_box = box[0] - 500 <= mid[0] < box[2] + 500 and box[1] - 500 <= mid[1] < box[3] + 500
        if t in ('residential', 'living_street', 'service', 'unclassified', 'cycleway', 'track', 'path', 'pedestrian', 'footway', '') and not in_box:
            continue
        lon, lat = tr.transform(*(s - off).T)
        w.writerow([k, t, len(cl), round(cl[0]['speed'] * 3.6, 1), round(cl[0]['length'], 1), 'LINESTRING(' + ','.join(f'{a:.6f} {b:.6f}' for a, b in zip(lon, lat)) + ')'])
        n += 1
print('edges', n)
