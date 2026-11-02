#!/usr/bin/env python3
"""OSMnx consolidate_intersections against the city's register. Usage: osmnx_test.py HIGHWAY.osm.xml OUT.json"""
import sys, os, json, re, collections
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import register
import osmnx as ox, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
ox.settings.log_console = False
G = ox.graph_from_xml(sys.argv[1], retain_all=False, simplify=True, bidirectional=False)
Gp = ox.project_graph(G, to_crs='EPSG:32633')
res = dict(version=ox.__version__, nodes=len(Gp.nodes), edges=len(Gp.edges))
reg = register(); veh = {k: v['veh'] for k, v in reg.items() if v['veh']}
t = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
for tol in (5, 7.5, 10, 15, 20, 25, 30):
    C = ox.consolidate_intersections(Gp, tolerance=tol, rebuild_graph=True, dead_ends=False, reconnect_edges=True)
    L = np.array([d['length'] for *_, d in C.edges(data=True)])
    ni = [n for n, d in C.nodes(data=True) if d.get('street_count', 0) >= 3]
    xy = np.array([(C.nodes[n]['x'], C.nodes[n]['y']) for n in ni]); T = cKDTree(xy)
    per = collections.Counter(); of = collections.Counter()
    for k, ls in veh.items():
        s = set()
        for x, y in (t.transform(*p) for p in ls):
            s.update(T.query_ball_point((x, y), 40))
        per[min(len(s), 3)] += 1
        for i in s:
            of[i] += 1
    res[f'tol{tol}'] = dict(nodes=C.number_of_nodes(), intersections=len(ni), edges=C.number_of_edges(), under_7_5=int((L < 7.5).sum()), under_25=int((L < 25).sum()), median=float(np.median(L)),
                            installations_0_1_2_3plus=[per[0], per[1], per[2], per[3]], intersections_touching_2plus_installations=sum(v >= 2 for v in of.values()))
    print(tol, res[f'tol{tol}'], flush=True)
json.dump(res, open(sys.argv[2], 'w'), indent=1)
