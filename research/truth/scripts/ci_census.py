#!/usr/bin/env python3
"""Size the per-junction buffers: links and SUMO foe pairs per junction on the real city nets."""
import json, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

base = Path('/home/erikf/projects/personal/cars-data')
out = {}
for name in sys.argv[1:]:
    links, pairs, types, internal, has_via = [], [], {}, 0, 0
    conns = 0
    for _, e in ET.iterparse(base / name, events=('end',)):
        if e.tag == 'junction':
            reqs = e.findall('request')
            t = e.get('type')
            types[t] = types.get(t, 0) + 1
            if reqs:
                links.append(len(reqs))
                pairs.append(sum(r.get('foes', '').count('1') for r in reqs))
            e.clear()
        elif e.tag == 'connection':
            if not e.get('from', '').startswith(':'):
                conns += 1
                has_via += e.get('via') is not None
            e.clear()
        elif e.tag in ('edge', 'tlLogic'):
            e.clear()
    L, P = np.array(links), np.array(pairs)
    out[name] = dict(junctions_with_requests=len(L), types=types, links_mean=float(L.mean()), links_p50=int(np.percentile(L, 50)),
                     links_p99=int(np.percentile(L, 99)), links_max=int(L.max()), ordered_foe_pairs_mean=float(P.mean()),
                     ordered_foe_pairs_p50=int(np.percentile(P, 50)), ordered_foe_pairs_p99=int(np.percentile(P, 99)), ordered_foe_pairs_max=int(P.max()),
                     total_links=int(L.sum()), total_pairs=int(P.sum()), connections=conns, connections_with_via=has_via)
    print(name, json.dumps(out[name]), flush=True)
(Path(__file__).resolve().parents[1] / 'fig' / '09b-census.json').write_text(json.dumps(out, indent=1))
